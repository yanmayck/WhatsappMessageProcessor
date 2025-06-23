from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from config import Config

# Assuming Base is defined in models.py or extensions.py
# from models import Base # Or from extensions import Base

# Use a simpler import for Base if it's available globally or via a specific import path
# For now, let's assume it's directly importable from extensions based on the previous edit
from extensions import Base # Import the Base from extensions.py

# Configure the database URL from Config
SQLALCHEMY_DATABASE_URL = Config.SQLALCHEMY_DATABASE_URL

# Create the SQLAlchemy engine
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    # connect_args={"check_same_thread": False} is needed for SQLite
    # if multiple threads/requests might access the same connection.
    # For other databases (PostgreSQL, MySQL), this is usually not needed.
    connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {},
)

# Create a SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_db_tables():
    # This function can be called at application startup to create tables
    Base.metadata.create_all(bind=engine) 