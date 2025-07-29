from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

import os
import yaml

def read_secret(path, default=None):
    try:
        with open(path, 'r') as f:
            return f.read().strip()
    except Exception:
        return default

def get_db_config():
    """
    DB接続情報を優先度: secrets > config.yaml > default で取得
    """
    def read_secret(path, default=None):
        try:
            with open(path, 'r') as f:
                return f.read().strip()
        except Exception:
            return default

    dev_mode = os.getenv('DEV', '').lower() == 'true'
    if dev_mode:
        config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
        else:
            config = {}
        db_user = config.get('db_user', 'devuser')
        db_password = config.get('db_password', 'devpass')
        db_name = config.get('db_name', 'devdb')
        db_host = config.get('db_host', 'localhost')
        db_port = str(config.get('db_port', '5432'))
    else:
        db_user = read_secret('/run/secrets/DBUSER', 'devuser')
        db_password = read_secret('/run/secrets/DBPASSWORD', 'devpass')
        db_name = read_secret('/run/secrets/DBNAME', 'devdb')
        db_host = 'db'
        db_port = '5432'
    return db_user, db_password, db_name, db_host, db_port

# config.yaml読み込み
config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
if os.path.exists(config_path):
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
else:
    config = {}


# DB接続情報を共通関数で取得
db_user, db_password, db_name, db_host, db_port = get_db_config()
DATABASE_URL = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# DB初期化
Base.metadata.create_all(bind=engine)

