from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from utils.database import Base


class PublishedRestoreRecord(Base):
    __tablename__ = "published_restore_records"

    id = Column(Integer, primary_key=True)
    storage_id = Column(
        Integer, ForeignKey("storages.id", ondelete="CASCADE"), nullable=False
    )
    key = Column(String, nullable=False)
    descriptor_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    storage = relationship("Storage")
