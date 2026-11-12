from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from utils.database import engine, Base


class Billing(Base):
    __tablename__ = "billings"

    id = Column(Integer, primary_key=True)

    uid = Column(String, nullable=False)
    balance = Column(Integer, nullable=False)
    granted = Column(Boolean, nullable=False)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    user = relationship("User", back_populates="billings")
    storages = relationship("Storage", back_populates="billing")
