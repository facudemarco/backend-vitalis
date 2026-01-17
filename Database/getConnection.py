from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import os
from sqlalchemy.ext.declarative import declarative_base

load_dotenv()

engine = create_engine(
    f"mysql+pymysql://{os.getenv('USER')}:{os.getenv('PASSWORD')}@{os.getenv('HOST')}:{os.getenv('PORT')}/{os.getenv('DATABASE')}",
    pool_size=5, # Tamaño del pool
    pool_timeout=30, # Timeout para obtener conexión
    pool_recycle=1800, # Reciclar conexiones cada 30 min
    pool_pre_ping=True # Verificar conexión antes de usar
)

Base = declarative_base()

def getConnection():
    try:
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        return db
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None
    
def getConnectionForLogin():
    try:
        engine = create_engine(f"mysql+pymysql://{os.getenv('USER')}:{os.getenv('PASSWORD')}@{os.getenv('HOST')}:{os.getenv('PORT')}/{os.getenv('DATABASE')}")
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        return db
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None