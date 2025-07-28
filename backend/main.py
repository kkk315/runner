
import os
import yaml
import threading
import time as pytime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
import docker
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

with open(os.path.join(os.path.dirname(__file__), 'config.yaml'), 'r') as f:
    config = yaml.safe_load(f)
debug_log_keep = config.get('debug_log_keep', False)
rate_limit_per_minute = config.get('rate_limit_per_minute', 30)
rate_limit_lock = threading.Lock()
rate_limit_times = []

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

def check_rate_limit():
    # 1分間のAPIリクエスト回数制限
    now = pytime.time()
    with rate_limit_lock:
        global rate_limit_times
        rate_limit_times[:] = [t for t in rate_limit_times if now-t < 60]
        if len(rate_limit_times) >= rate_limit_per_minute:
            return False
        rate_limit_times.append(now)
    return True

def check_request_size(code: str) -> bool:
    # リクエストボディ（コード）のサイズ制限
    max_request_body_size = config.get('max_request_body_size', 1048576)
    return len(code.encode('utf-8')) <= max_request_body_size

def check_code_length(code: str) -> bool:
    # コード文字数の制限
    max_code_length = config.get('max_code_length', 10000)
    return len(code) <= max_code_length

def prepare_tempdir(ext: str, code: str, stdin: str) -> str:
    # 一時ディレクトリを作成し、コード・標準入力・実行ファイル(run.py/js)を配置
    import tempfile
    import shutil
    # 一時ディレクトリ作成
    tmp_root = os.path.join(os.path.dirname(__file__), 'tmp')
    os.makedirs(tmp_root, exist_ok=True)
    tempdir = tempfile.mkdtemp(prefix='runner-', dir=tmp_root)
    os.chmod(tempdir, 0o777)
    # ユーザーコード保存
    with open(os.path.join(tempdir, f'code.{ext}'), 'w') as tmp:
        tmp.write(code)
        tmp.flush()
    # 標準入力保存
    stdin_data = stdin or ''
    if stdin_data and not stdin_data.endswith('\n'):
        stdin_data += '\n'
    with open(os.path.join(tempdir, 'stdin.txt'), 'w') as f:
        f.write(stdin_data)
        f.flush()
    # 実行ファイル(run.py/js)をコピー
    host_run = os.path.join(os.path.dirname(__file__), f'../runner/run.{ext}')
    dest_run = os.path.join(tempdir, f'run.{ext}')
    shutil.copy2(host_run, dest_run)
    os.chmod(dest_run, 0o755)
    # コピー・存在チェック
    if not os.path.exists(dest_run):
        raise HTTPException(status_code=500, detail=f"run.{ext} not copied to tempdir: {dest_run}")
    if not os.path.exists(host_run):
        raise HTTPException(status_code=500, detail=f"host run.{ext} not found: {host_run}")
    return tempdir

def get_resource_limits(image):
    # Dockerイメージの環境変数からメモリ・CPU制限値を取得
    image_env = image.attrs.get('Config', {}).get('Env', [])
    mem_limit = None
    cpu_limit = None
    for env_var in image_env:
        if env_var.startswith('CONTAINER_MAX_MEM='):
            mem_limit = env_var.split('=')[1]
        elif env_var.startswith('CONTAINER_MAX_CPU='):
            try:
                cpu_limit = float(env_var.split('=')[1])
            except Exception:
                cpu_limit = None
    if not mem_limit:
        mem_limit = '512m'
    if not cpu_limit:
        cpu_limit = 1.0
    return mem_limit, cpu_limit

def safe_read(path):
    # ファイル読み込み（失敗時は空文字列返却）
    try:
        with open(path, 'r') as f:
            return f.read()
    except Exception:
        return ''

@app.post("/run", response_model=CodeResponse)
def run_code(req: CodeRequest):
    """
    コード実行APIエンドポイント
    - レートリミット・サイズ・長さチェック
    - 一時ディレクトリ準備
    - Dockerコンテナでコード実行
    - 実行結果（stdout/stderr/exit_code/time）を返却
    """
    if not check_rate_limit():
        return CodeResponse(stdout='', stderr='Rate limit exceeded', exit_code=2001, time=-1, debug={})
    if not check_request_size(req.code):
        return CodeResponse(stdout='', stderr='Request body too large', exit_code=2002, time=-1, debug={})
    if not check_code_length(req.code):
        return CodeResponse(stdout='', stderr='Code too long', exit_code=2003, time=-1, debug={})
    # 言語・Dockerイメージ・拡張子の決定
    ext_map = {'python': 'py', 'node': 'js'}
    dockerfiles = config.get('dockerfiles', {})
    if req.language not in dockerfiles or req.language not in ext_map:
        raise HTTPException(status_code=400, detail="Unsupported language")
    ext = ext_map[req.language]
    dockerfile_path = os.path.abspath(os.path.join(os.path.dirname(__file__), dockerfiles[req.language]))
    image_name = os.path.basename(dockerfile_path).replace('Dockerfile.', 'runner-')
    client = docker.from_env()
    image = client.images.get(image_name)
    # 一時ディレクトリ・ファイル準備
    tempdir = prepare_tempdir(ext, req.code, req.stdin)
    # リソース制限取得
    mem_limit, cpu_limit = get_resource_limits(image)
    # デバッグ情報（返却用）
    debug_info = {
        'host_tmpdir': os.path.abspath(tempdir),
        'host_run': os.path.abspath(os.path.join(tempdir, f'run.{ext}')),
        'container_cmd': [f'/home/runner/tmp/run.{ext}', '/home/runner/tmp'],
        'tempdir_mode': oct(os.stat(tempdir).st_mode & 0o777),
    }
    try:
        # Dockerコンテナでコード実行
        container = client.containers.run(
            image_name,
            ['python', f'/home/runner/tmp/run.{ext}', '/home/runner/tmp'],
            detach=True,
            remove=False,
            tty=False,
            volumes={
                tempdir: {'bind': '/home/runner/tmp', 'mode': 'rw'},
            },
            working_dir='/home/runner/tmp'
        )
        result = container.wait()
        # 実行結果ファイル読み込み
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
        # コンテナ・一時ディレクトリの後始末
        try:
            container.remove(force=True)
        except Exception:
            pass
        if not debug_log_keep:
            import shutil
            shutil.rmtree(tempdir, ignore_errors=True)
        return resp
    except Exception as e:
        # エラー時のレスポンス生成・後始末
        resp = CodeResponse(stdout='', stderr=str(e), exit_code=1, time=-1, debug=debug_info)
        if not debug_log_keep:
            import shutil
            shutil.rmtree(tempdir, ignore_errors=True)
        return resp


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
    
    # 環境変数から実際の制限を行う
    image_env = image.attrs.get('Config', {}).get('Env', [])

    mem_limit = None
    cpu_limit = None

    for env_var in image_env:
        if env_var.startswith('CONTAINER_MAX_MEM='):
            mem_limit = env_var.split('=')[1]
        elif env_var.startswith('CONTAINER_MAX_CPU='):
            cpu_limit = float(env_var.split('=')[1]) # floatに変換
            
            
    if not mem_limit :
        mem_limit = '512m'  # デフォルト値
    if not cpu_limit:
        cpu_limit = 1.0  # デフォルト値
    # パーミッション確認
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
            working_dir='/home/runner/tmp',
            mem_limit=mem_limit,
            cpu_limit=cpu_limit,
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
