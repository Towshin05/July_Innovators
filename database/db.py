
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.models import Base

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "database/witnessbridge.db")
DB_URL = f"sqlite:///{DB_PATH}"


engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    
   
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(engine)


def get_session():
  
    return SessionLocal()
