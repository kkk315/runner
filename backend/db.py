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

config = {}
DBUSER = read_secret('/run/secrets/DBUSER', os.getenv('DBUSER', config.get('db_user', 'devuser')))
DBPASSWORD = read_secret('/run/secrets/DBPASSWORD', os.getenv('DBPASSWORD', config.get('db_password', 'devpass')))
DBNAME = read_secret('/run/secrets/DBNAME', os.getenv('DBNAME', config.get('db_name', 'devdb')))
DBHOST = 'db'
DBPORT = os.getenv('DBPORT', str(config.get('db_port', '5432')))

DATABASE_URL = f"postgresql://{DBUSER}:{DBPASSWORD}@{DBHOST}:{DBPORT}/{DBNAME}"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# DB初期化
Base.metadata.create_all(bind=engine)
