import yaml
import threading
import time as pytime
with open(os.path.join(os.path.dirname(__file__), 'config.yaml'), 'r') as f:
    config = yaml.safe_load(f)

# レートリミット用
rate_limit_per_minute = config.get('rate_limit_per_minute', 30)
rate_limit_lock = threading.Lock()
rate_limit_times = []
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
import subprocess
import uuid
import os
import docker
import re
from dotenv import load_dotenv


load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CodeRequest(BaseModel):
    language: Literal['python', 'node']
    code: str

class CodeResponse(BaseModel):
    stdout: str
    stderr: str
    exit_code: int
    time: float
    debug: dict = {}


@app.post("/run", response_model=CodeResponse)
def run_code(req: CodeRequest):
    # レートリミット
    now = pytime.time()
    with rate_limit_lock:
        rate_limit_times[:] = [t for t in rate_limit_times if now-t < 60]
        if len(rate_limit_times) >= rate_limit_per_minute:
            return CodeResponse(stdout='', stderr='Rate limit exceeded', exit_code=2001, time=-1, debug={})
        rate_limit_times.append(now)

    # リクエストサイズ制限
    max_request_body_size = config.get('max_request_body_size', 1048576)
    if req.code and len(req.code.encode('utf-8')) > max_request_body_size:
        return CodeResponse(stdout='', stderr='Request body too large', exit_code=2002, time=-1, debug={})

    # コード長制限
    max_code_length = config.get('max_code_length', 10000)
    if len(req.code) > max_code_length:
        return CodeResponse(stdout='', stderr='Code too long', exit_code=2003, time=-1, debug={})
    import tempfile
    client = docker.from_env()
    image = None
    command = None
    ext = None
    if req.language == 'python':
        image = os.getenv('RUNNER_PYTHON_IMAGE', 'runner-python')
        ext = 'py'
    elif req.language == 'node':
        image = os.getenv('RUNNER_NODE_IMAGE', 'runner-node')
        ext = 'js'
    else:
        raise HTTPException(status_code=400, detail="Unsupported language")

    import shutil
    tmp_root = os.path.join(os.path.dirname(__file__), 'tmp')
    os.makedirs(tmp_root, exist_ok=True)
    tempdir = tempfile.mkdtemp(prefix='runner-', dir=tmp_root)
    code_path_host = os.path.join(tempdir, f'code.{ext}')
    stdout_path_host = os.path.join(tempdir, 'stdout.txt')
    stderr_path_host = os.path.join(tempdir, 'stderr.txt')
    time_path_host = os.path.join(tempdir, 'time.txt')
    with open(code_path_host, 'w') as tmp:
        tmp.write(req.code)
        tmp.flush()
    # ディレクトリごとマウント
    container_tmp_dir = '/home/runner/tmp'
    code_path_container = os.path.join(container_tmp_dir, f'code.{ext}')
    stdout_path_container = os.path.join(container_tmp_dir, 'stdout.txt')
    stderr_path_container = os.path.join(container_tmp_dir, 'stderr.txt')
    time_path_container = os.path.join(container_tmp_dir, 'time.txt')
    debug_info = {
        'host_code_file': code_path_host,
        'container_code_file': code_path_container,
        'host_stdout_file': stdout_path_host,
        'host_stderr_file': stderr_path_host,
        'host_time_file': time_path_host,
        'container_stdout_file': stdout_path_container,
        'container_stderr_file': stderr_path_container,
        'container_time_file': time_path_container,
        'host_tmp_dir': tempdir,
        'container_tmp_dir': container_tmp_dir,
    }

    try:
        mem_limit = config.get('mem_limit', '512m')
        cpu_limit = float(config.get('cpu_limit', 1.0))
        nano_cpus = int(cpu_limit * 1_000_000_000)
        container = client.containers.run(
            image,
            [code_path_container, stdout_path_container, stderr_path_container, time_path_container],
            detach=True,
            mem_limit=mem_limit,
            nano_cpus=nano_cpus,
            remove=False,
            tty=False,
            volumes={
                tempdir: {'bind': container_tmp_dir, 'mode': 'rw'},
            }
        )
        try:
            exit_code = 0
            max_exec_time = config.get('max_exec_time', 10)
            try:
                result = container.wait(timeout=max_exec_time)
            except Exception as e:
                # Timeout時はkillして独自エラーコード
                debug_info['wait_timeout'] = str(e)
                try:
                    container.kill()
                except Exception:
                    pass
                result = {'StatusCode': 137}
                exit_code = 1001  # 独自: タイムアウト
            # ホスト側ファイルから出力取得
            try:
                with open(stdout_path_host, 'r') as f:
                    stdout = f.read()
            except Exception:
                stdout = ''
            try:
                with open(stderr_path_host, 'r') as f:
                    stderr = f.read()
            except Exception:
                stderr = ''
            try:
                with open(time_path_host, 'r') as f:
                    exec_time = float(f.read())
            except Exception:
                exec_time = -1
            # 出力はバイト数で制限
            max_stdout_bytes = config.get('max_stdout_bytes', 1048576)
            max_stderr_bytes = config.get('max_stderr_bytes', 1048576)
            output_truncated = False
            if len(stdout.encode('utf-8')) > max_stdout_bytes:
                stdout = stdout.encode('utf-8')[:max_stdout_bytes].decode('utf-8', errors='ignore') + '\n... (truncated)'
                output_truncated = True
            if len(stderr.encode('utf-8')) > max_stderr_bytes:
                stderr = stderr.encode('utf-8')[:max_stderr_bytes].decode('utf-8', errors='ignore') + '\n... (truncated)'
                output_truncated = True
            if output_truncated and exit_code == 0:
                exit_code = 1002  # 独自: 出力過多
            if exit_code == 0:
                exit_code = result.get('StatusCode', 0)
            resp = CodeResponse(
                stdout=stdout,
                stderr=stderr,
                exit_code=exit_code,
                time=exec_time,
                debug=debug_info
            )
            try:
                container.remove(force=True)
            except Exception:
                pass
            shutil.rmtree(tempdir, ignore_errors=True)
            return resp
        except Exception as e:
            debug_info['container_stderr'] = str(e)
            try:
                container.remove(force=True)
            except Exception:
                pass
            try:
                with open(stdout_path_host, 'r') as f:
                    stdout = f.read()
            except Exception:
                stdout = ''
            try:
                with open(stderr_path_host, 'r') as f:
                    stderr = f.read()
            except Exception:
                stderr = ''
            try:
                with open(time_path_host, 'r') as f:
                    exec_time = float(f.read())
            except Exception:
                exec_time = -1
            resp = CodeResponse(stdout=stdout, stderr=stderr, exit_code=1, time=exec_time, debug=debug_info)
            shutil.rmtree(tempdir, ignore_errors=True)
            return resp
    except Exception as e:
        debug_info['container_stderr'] = str(e)
        try:
            with open(stdout_path_host, 'r') as f:
                stdout = f.read()
        except Exception:
            stdout = ''
        try:
            with open(stderr_path_host, 'r') as f:
                stderr = f.read()
        except Exception:
            stderr = ''
        try:
            with open(time_path_host, 'r') as f:
                exec_time = float(f.read())
        except Exception:
            exec_time = -1
        resp = CodeResponse(stdout=stdout, stderr=stderr, exit_code=1, time=exec_time, debug=debug_info)
        shutil.rmtree(tempdir, ignore_errors=True)
        return resp
