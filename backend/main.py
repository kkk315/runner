import os
import yaml
import threading
import time as pytime
with open(os.path.join(os.path.dirname(__file__), 'config.yaml'), 'r') as f:
    config = yaml.safe_load(f)
debug_log_keep = config.get('debug_log_keep', False)

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
    stdin: str = ''

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
    import shutil
    client = docker.from_env()
    # 言語ごとのDockerfileパスをconfig.yamlから取得
    dockerfiles = config.get('dockerfiles', {})
    ext_map = {'python': 'py', 'node': 'js'}
    if req.language not in dockerfiles or req.language not in ext_map:
        raise HTTPException(status_code=400, detail="Unsupported language")
    ext = ext_map[req.language]
    dockerfile_path = os.path.abspath(os.path.join(os.path.dirname(__file__), dockerfiles[req.language]))
    # 事前ビルド済みイメージを利用
    image = os.path.basename(dockerfile_path).replace('Dockerfile.', 'runner-')
    tmp_root = os.path.join(os.path.dirname(__file__), 'tmp')
    os.makedirs(tmp_root, exist_ok=True)
    tempdir = tempfile.mkdtemp(prefix='runner-', dir=tmp_root)
    os.chmod(tempdir, 0o777)  # 権限問題回避のため一時ディレクトリを全ユーザー書き込み可に
    # パーミッション確認
    tempdir_stat = os.stat(tempdir)
    tempdir_mode = oct(tempdir_stat.st_mode & 0o777)
    with open(os.path.join(tempdir, f'code.{ext}'), 'w') as tmp:
        tmp.write(req.code)
        tmp.flush()
    stdin_data = req.stdin or ''
    if stdin_data and not stdin_data.endswith('\n'):
        stdin_data += '\n'
    with open(os.path.join(tempdir, 'stdin.txt'), 'w') as f:
        f.write(stdin_data)
        f.flush()
    # run.{ext}をtempdirにコピーし、存在チェック
    host_run = os.path.join(os.path.dirname(__file__), f'../runner/run.{ext}')
    dest_run = os.path.join(tempdir, f'run.{ext}')
    shutil.copy2(host_run, dest_run)
    os.chmod(dest_run, 0o755)
    if not os.path.exists(dest_run):
        raise HTTPException(status_code=500, detail=f"run.{ext} not copied to tempdir: {dest_run}")
    if not os.path.exists(host_run):
        raise HTTPException(status_code=500, detail=f"host run.{ext} not found: {host_run}")
    # デバッグ情報として有用な動的値のみを記録
    debug_info = {
        'host_tmpdir': os.path.abspath(tempdir),
        'host_run': os.path.abspath(dest_run),
        'container_cmd': [f'/home/runner/tmp/run.{ext}', '/home/runner/tmp'],
        'tempdir_mode': tempdir_mode,
    }

    # debug_log_keepはconfig.yamlの値をそのまま使う
    try:
        # 本来のrun.py実行パイプラインに戻す
        container = client.containers.run(
            image,
            [f'python', f'/home/runner/tmp/run.{ext}', '/home/runner/tmp'],
            detach=True,
            remove=False,
            tty=False,
            volumes={
                tempdir: {'bind': '/home/runner/tmp', 'mode': 'rw'},
            },
            working_dir='/home/runner/tmp'
        )
        result = container.wait()
        # run.pyが全てのログ・出力ファイルを生成する前提
        def safe_read(path):
            try:
                with open(path, 'r') as f:
                    return f.read()
            except Exception:
                return ''
        stdout = safe_read(os.path.join(tempdir, 'stdout.txt'))
        stderr = safe_read(os.path.join(tempdir, 'stderr.txt'))
        try:
            exec_time = float(safe_read(os.path.join(tempdir, 'time.txt')))
        except Exception:
            exec_time = -1
        try:
            exit_code = int(safe_read(os.path.join(tempdir, 'exit_code.txt')))
        except Exception:
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
        if not debug_log_keep:
            shutil.rmtree(tempdir, ignore_errors=True)
        return resp
    except Exception as e:
        resp = CodeResponse(stdout='', stderr=str(e), exit_code=1, time=-1, debug=debug_info)
        if not debug_log_keep:
            shutil.rmtree(tempdir, ignore_errors=True)
        return resp
