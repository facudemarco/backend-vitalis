from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
from sqlalchemy.ext.declarative import declarative_base

load_dotenv()

DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('USER')}:{os.getenv('PASSWORD')}"
    f"@{os.getenv('HOST')}:{os.getenv('PORT')}/{os.getenv('DATABASE')}"
)

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,        
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def getConnection():

    try:
        db = SessionLocal()
        return db
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def getConnectionForLogin():
    try:
        db = SessionLocal()
        return db
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None
