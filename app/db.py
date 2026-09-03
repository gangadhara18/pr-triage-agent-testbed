import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.environ.get("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


def get_db():
    """
    Gives out one database session per request, and always closes it
    afterward — even if something goes wrong. FastAPI endpoints will
    use this to get a working database connection.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
