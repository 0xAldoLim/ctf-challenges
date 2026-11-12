from sqlalchemy import Column, Integer, String, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship

from utils.database import engine, Base


class Storage(Base):
    __tablename__ = "storages"
    __table_args__ = (
        UniqueConstraint("billing_id", "name", name="uq_storage_billing_name"),
        UniqueConstraint("uid", name="uq_storage_uid"),
    )

    id = Column(Integer, primary_key=True)

    uid = Column(String, nullable=False)
    name = Column(String, nullable=False)
    billing_id = Column(
        Integer, ForeignKey("billings.id", ondelete="CASCADE"), nullable=False
    )

    billing = relationship("Billing", back_populates="storages")
