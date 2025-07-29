#!/usr/bin/env python3
import sys
import time
import os
import io
import contextlib
import traceback
import yaml

from sqlalchemy import create_engine, Column, Integer, String, Text, Float
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import SQLAlchemyError

# --- 定数 ---
# データベース関連（main.pyから環境変数で渡された値のみ使用）
DB_TABLE_NAME = 'code_jobs'

# ジョブステータス
JOB_STATUS_DONE = 'done'
JOB_STATUS_ERROR = 'error'
JOB_STATUS_PENDING = 'pending'

# --- モデル定義 ---
Base = declarative_base()

class CodeJob(Base):
    __tablename__ = DB_TABLE_NAME
    id = Column(Integer, primary_key=True, index=True)
    language = Column(String(16))
    code = Column(Text)
    stdin = Column(Text)
    status = Column(String(16), default=JOB_STATUS_PENDING)
    result_stdout = Column(Text)
    result_stderr = Column(Text)
    result_exit_code = Column(Integer)
    result_time = Column(Float)

# --- ヘルパー関数 ---

# --- ヘルパー関数（不要なので削除） ---

@contextlib.contextmanager
def redirect_stdout_stderr_stdin(stdout_stream: io.StringIO, stderr_stream: io.StringIO, stdin_stream: io.StringIO):
    """
    標準出力、標準エラー出力、標準入力を一時的にリダイレクトするコンテキストマネージャ。
    """
    original_stdin, original_stdout, original_stderr = sys.stdin, sys.stdout, sys.stderr
    sys.stdin = stdin_stream
    sys.stdout = stdout_stream
    sys.stderr = stderr_stream
    try:
        yield
    finally:
        sys.stdin, sys.stdout, sys.stderr = original_stdin, original_stdout, original_stderr

# --- メインロジック ---

def get_db_url(db_user, db_password, db_name, db_host, db_port) -> str:
    """データベース接続URLを引数から構築する（main.pyから渡された値のみ使用）"""
    if not all([db_user, db_password, db_name, db_host, db_port]):
        print("Error: Database connection parameters are incomplete. Exiting.", file=sys.stderr)
        sys.exit(1)
    return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

def initialize_db(database_url: str):
    """データベース接続とテーブル作成を行う"""
    global engine, SessionLocal
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    try:
        Base.metadata.create_all(bind=engine)
    except SQLAlchemyError as e:
        print(f"Error: Failed to connect to database or create tables: {e}", file=sys.stderr)
        sys.exit(1)

def execute_code_in_memory(code_str: str, stdin_data: str) -> tuple[str, str, int, float]:
    """
    メモリ上でPythonコードを実行し、標準入出力と実行時間、終了コードをキャプチャする。
    """
    stdout_stream = io.StringIO()
    stderr_stream = io.StringIO()
    stdin_stream = io.StringIO(stdin_data)
    
    exit_code = 0
    start_time = time.time()

    with redirect_stdout_stderr_stdin(stdout_stream, stderr_stream, stdin_stream):
        try:
            exec(code_str, {})
        except Exception:
            stderr_stream.write(traceback.format_exc())
            exit_code = 1

    end_time = time.time()
    
    return (
        stdout_stream.getvalue(),
        stderr_stream.getvalue(),
        exit_code,
        end_time - start_time
    )

def main():
    """スクリプトのメイン実行ロジック"""
    if len(sys.argv) < 7:
        print("Usage: python runner.py <job_id> <db_user> <db_password> <db_name> <db_host> <db_port>", file=sys.stderr)
        sys.exit(1)

    try:
        job_id = int(sys.argv[1])
        db_user = sys.argv[2]
        db_password = sys.argv[3]
        db_name = sys.argv[4]
        db_host = sys.argv[5]
        db_port = sys.argv[6]
    except Exception:
        print("Error: Invalid arguments.", file=sys.stderr)
        sys.exit(1)

    db_url = get_db_url(db_user, db_password, db_name, db_host, db_port)
    initialize_db(db_url)

    db: Session | None = None
    try:
        db = SessionLocal()
        job = db.query(CodeJob).filter(CodeJob.id == job_id).first()

        if not job:
            print(f"Error: Job with ID {job_id} not found in database.", file=sys.stderr)
            sys.exit(1)

        # DB接続後、ユーザーコード実行前にstatusを"TEST"に更新してcommit
        job.status = "TEST"
        try:
            db.commit()
            print(f"DB status TEST commit success for job_id={job_id}", file=sys.stderr)
        except Exception as e:
            print(f"DB status TEST commit failed for job_id={job_id}: {e}", file=sys.stderr)
            sys.exit(1)

        # コード実行
        stdout_result, stderr_result, exit_code_result, time_result = \
            execute_code_in_memory(job.code, job.stdin or '')

        # 結果をDBに保存
        job.result_stdout = stdout_result
        job.result_stderr = stderr_result
        job.result_exit_code = exit_code_result
        job.result_time = time_result
        job.status = JOB_STATUS_DONE if exit_code_result == 0 else JOB_STATUS_ERROR

        db.commit()

    except SQLAlchemyError as e:
        print(f"Error: Database error while processing job {job_id}: {e}", file=sys.stderr)
        if db:
            db.rollback()
        sys.exit(1)
    except Exception as e:
        print(f"Error: An unexpected error occurred while processing job {job_id}: {e}", file=sys.stderr)
        if db:
            db.rollback()
        sys.exit(1)
    finally:
        if db:
            db.close()

if __name__ == "__main__":
    main()