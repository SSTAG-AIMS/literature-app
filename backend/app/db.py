from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# .env'i config.py zaten okuyor olacak ama burada direkt DB URL'i alacağız
from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
