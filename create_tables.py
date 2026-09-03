from dotenv import load_dotenv
load_dotenv()

from app.db import Base, engine
from app import models  # noqa: F401 — importing this registers the models with Base

Base.metadata.create_all(bind=engine)
print("Tables created: pull_requests, suggestions, decisions")
