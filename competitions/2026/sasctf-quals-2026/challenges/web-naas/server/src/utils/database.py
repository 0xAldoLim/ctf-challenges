from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from utils.config import app_config

engine = create_engine(app_config.DATABASE_URL)
Session = sessionmaker(bind=engine)

Base = declarative_base()
