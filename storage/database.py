from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from contextlib import contextmanager
from infra.settings import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@contextmanager
def get_db():
    """Context manager đảm bảo session được đóng đúng cách"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
