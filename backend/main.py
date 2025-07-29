import os
import json
import yaml
import threading
import time as pytime
from fastapi import FastAPI, HTTPException
from models import CodeJob
from db import SessionLocal
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Literal
import docker
from dotenv import load_dotenv
import logging
import sys
logger = logging.getLogger("uvicorn.error")
logger.setLevel(logging.INFO)

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
@app.get("/")
def root():
    return {"status": "OK"}
 

@app.post("/run", response_model=CodeResponse)
def run_code(req: CodeRequest):
    if not check_rate_limit():
        return CodeResponse(stdout='', stderr='Rate limit exceeded', exit_code=2001, time=-1, debug={})
    if not check_request_size(req.code):
        return CodeResponse(stdout='', stderr='Request body too large', exit_code=2002, time=-1, debug={})
    if not check_code_length(req.code):
        return CodeResponse(stdout='', stderr='Code too long', exit_code=2003, time=-1, debug={})
    # DBにジョブ保存
    db = SessionLocal()
    job = CodeJob(language=req.language, code=req.code, stdin=req.stdin, status='pending')
    db.add(job)
    try:
        db.commit()
    except Exception as e:
        logger.error(f'db commit error: {e}', exc_info=True)
        db.close()
        return CodeResponse(stdout='', stderr='db commit error', exit_code=9005, time=-1, debug={})
    try:
        db.refresh(job)
    except Exception as e:
        logger.error(f'db refresh error: {e}', exc_info=True)
    try:
        db.close()
    except Exception as e:
        logger.error(f'db close error: {e}', exc_info=True)

    logger.info(f'run_code: job_id={job.id} start (logger)')
    logging.info(f'run_code: job_id={job.id} start (logging)')
    client = docker.from_env()
    image = f"runner-{req.language}:latest"
    mem_limit, cpu_limit = get_resource_limits(client.images.get(image))
    if not cpu_limit or cpu_limit <= 0:
        cpu_limit = 1.0
    seccomp_path = os.path.join(os.path.dirname(__file__), '../runner/seccomp_profile.json')
    security_opt = None
    if os.path.exists(seccomp_path):
        with open(seccomp_path, 'r') as f:
            seccomp_json = f.read()
        security_opt = [f"seccomp={seccomp_json}"]
    host_config = client.api.create_host_config(
        network_mode='runner_backend-db-net',  # Swarm overlayネットワークを明示指定
        mem_limit=mem_limit,
        nano_cpus=int(cpu_limit * 1e9),
        #security_opt=security_opt
    )
    ext_map = {
        'python': 'py',
        'node': 'js',
        # 必要に応じて他言語追加
    }
    ext = ext_map.get(req.language, req.language)
    start = pytime.time()
    logger.info(f'run_code: job_id={job.id} before create_container')

    def read_secret(path, default):
        try:
            with open(path, 'r') as f:
                return f.read().strip()
        except Exception:
            return default

    db_user = read_secret('/run/secrets/DBUSER', 'exampleuser')
    db_password = read_secret('/run/secrets/DBPASSWORD', 'examplepass')
    db_name = read_secret('/run/secrets/DBNAME', 'exampledb')
    db_host = 'db'  # HOST名は必ずサービス名 'db' を使う
    db_port = '5432'
    logger.info(f"run_code: DB info user={db_user} pass={db_password} name={db_name} host={db_host} port={db_port}")
    try:
        cmd_str = " ".join([str(x) for x in [job.id, db_user, db_password, db_name, db_host, db_port]])
        container = client.api.create_container(
            image=image,
            entrypoint=f"./run.{ext}",
            command=cmd_str,
            host_config=host_config,
            detach=True
        )
        logger.info(f'run_code: job_id={job.id} after create_container')
    except Exception as e:
        return CodeResponse(stdout='', stderr=f'create_container error: {str(e)}', exit_code=9001, time=-1, debug={'job_id': job.id})

    logger.info(f'run_code: job_id={job.id} before start_container')
    try:
        container_id = container.get('Id')
        client.api.start(container_id)
    except Exception as e:
        logger.error(f'start_container error: {e}', exc_info=True)
        return CodeResponse(stdout='', stderr='start_container error', exit_code=9002, time=-1, debug={'job_id': job.id})

    logger.info(f'run_code: job_id={job.id} before get_container')
    try:
        container_obj = client.containers.get(container_id)
        logger.info(f'run_code: job_id={job.id} after get_container')
        container_obj.wait(timeout=60)
        logger.info(f'run_code: job_id={job.id} after wait_container')
    except Exception as e:
        logger.error(f'wait_container error: {e}', exc_info=True)
        return CodeResponse(stdout='', stderr='wait_container error', exit_code=9003, time=-1, debug={'job_id': job.id})
    # client.api.remove_container(container_id, force=True)  # 削除せず残す

    logger.info(f'run_code: job_id={job.id} before db_result')
    try:
        db = SessionLocal()
        job_result = db.query(CodeJob).filter(CodeJob.id == job.id).first()
        db.close()
        logger.info(f'run_code: job_id={job.id} after db_result')
        if job_result:
            return CodeResponse(
                stdout=job_result.result_stdout or '',
                stderr=job_result.result_stderr or '',
                exit_code=job_result.result_exit_code if job_result.result_exit_code is not None else -1,
                time=job_result.result_time if job_result.result_time is not None else -1,
                debug={'job_id': job.id, 'container_id': container_id}
            )
        else:
            return CodeResponse(stdout='', stderr='No result in DB', exit_code=9999, time=-1, debug={'job_id': job.id, 'container_id': container_id})
    except Exception as e:
        logger.error(f'db_result error: {e}', exc_info=True)
        return CodeResponse(stdout='', stderr='db_result error', exit_code=9004, time=-1, debug={'job_id': job.id, 'container_id': container_id})

@app.get("/dbtest", response_model=CodeResponse)
def dbtest():
    """
    DB接続テスト用APIエンドポイント
    - DB接続可否のみ判定し、結果を返す
    """
    try:
        db = SessionLocal()
        from sqlalchemy import text
        db.execute(text('SELECT 1'))
        db.close()
        return CodeResponse(stdout='DB接続OK', stderr='', exit_code=0, time=0, debug={})
    except Exception as e:
        return CodeResponse(stdout='', stderr=str(e), exit_code=1, time=0, debug={})

# --- DB操作を1ステップずつ分離したテスト用エンドポイント ---
@app.get("/testA", response_model=CodeResponse)
def testA():
    """
    DB接続のみテスト
    """
    try:
        db = SessionLocal()
        from sqlalchemy import text
        db.execute(text('SELECT 1'))
        db.close()
        return CodeResponse(stdout='DB接続OK', stderr='', exit_code=0, time=0, debug={})
    except Exception as e:
        return CodeResponse(stdout='', stderr=str(e), exit_code=1, time=0, debug={})

@app.get("/testB", response_model=CodeResponse)
def testB():
    """
    DB書き込みのみテスト（code_jobsにダミー追加）
    """
    try:
        db = SessionLocal()
        from models import CodeJob
        job = CodeJob(language='python', code='print(1)', stdin='', status='pending')
        db.add(job)
        db.commit()
        db.refresh(job)
        db.close()
        return CodeResponse(stdout=f'書き込みOK: job_id={job.id}', stderr='', exit_code=0, time=0, debug={})
    except Exception as e:
        return CodeResponse(stdout='', stderr=str(e), exit_code=2, time=0, debug={})

@app.get("/testC", response_model=CodeResponse)
def testC():
    """
    DB読み込みのみテスト（最新ジョブ取得）
    """
    try:
        db = SessionLocal()
        from models import CodeJob
        job = db.query(CodeJob).order_by(CodeJob.id.desc()).first()
        db.close()
        if job:
            return CodeResponse(stdout=f'id={job.id}, status={job.status}', stderr='', exit_code=0, time=0, debug={})
        else:
            return CodeResponse(stdout='', stderr='No job found', exit_code=3, time=0, debug={})
    except Exception as e:
        return CodeResponse(stdout='', stderr=str(e), exit_code=3, time=0, debug={})



