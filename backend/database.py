import os
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def _database_url() -> str:
    configured = os.getenv("DATABASE_URL", "")
    if configured.startswith("postgresql+asyncpg://"):
        return configured.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    return configured or "sqlite:///./agrimitra.db"


DATABASE_URL = _database_url()
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


def init_db() -> None:
    from . import models

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        models.seed_defaults(session)
        session.commit()


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
