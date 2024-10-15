from pathlib import Path

import sqlalchemy
from sqlalchemy.orm import sessionmaker
from .db import Base

__version__ = "0.0.0"

DB_PATH = Path(__file__).parent / "papers.db"

engine = sqlalchemy.create_engine(f'sqlite:///{DB_PATH}')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
