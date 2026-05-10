import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from config import settings

# Create database engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    echo=settings.sql_echo
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()


def get_db():
    """Dependency for getting database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Initialize database - create all tables"""
    Base.metadata.create_all(bind=engine)
    print("[OK] Database initialized")


def create_upload_directory():
    """Create uploads directory if it doesn't exist"""
    os.makedirs(settings.upload_dir, exist_ok=True)
    print(f"[OK] Upload directory ready: {settings.upload_dir}")
