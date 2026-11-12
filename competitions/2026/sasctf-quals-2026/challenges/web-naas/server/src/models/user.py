from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from utils.database import engine, Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)

    username = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)

    billings = relationship("Billing", back_populates="user")
