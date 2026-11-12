from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from utils.database import Base


class Processor(Base):
    __tablename__ = "processors"

    id = Column(Integer, primary_key=True)
    uid = Column(String, nullable=False, unique=True)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    billing_id = Column(
        Integer, ForeignKey("billings.id", ondelete="CASCADE"), nullable=False
    )
    storage_id = Column(
        Integer, ForeignKey("storages.id", ondelete="CASCADE"), nullable=False
    )
    mode = Column(String, nullable=False)
    state = Column(String, nullable=False)
    scope_json = Column("profile_json", Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    user = relationship("User")
    billing = relationship("Billing")
    storage = relationship("Storage")
