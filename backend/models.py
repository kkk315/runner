from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class CodeJob(Base):
    __tablename__ = 'code_jobs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    language = Column(String(16), nullable=False)
    code = Column(Text, nullable=False)
    stdin = Column(Text, nullable=True)
    status = Column(String(16), default='pending')
    result_stdout = Column(Text)
    result_stderr = Column(Text)
    result_exit_code = Column(Integer)
    result_time = Column(Integer)
