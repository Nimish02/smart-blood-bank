from sqlalchemy import Column, Integer, String, Date, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
try:
    from backend.database import Base
except ImportError:
    from database import Base


class Donor(Base):
    __tablename__ = "donors"

    id             = Column(Integer, primary_key=True, index=True)
    name           = Column(String(120), nullable=False)
    blood_type     = Column(String(5), nullable=False, index=True)
    age            = Column(Integer, nullable=False)
    contact        = Column(String(120), unique=True, nullable=False)
    city           = Column(String(80), nullable=False)
    last_donation_date = Column(Date, nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    # One donor → many inventory entries
    inventory_entries = relationship("BloodInventory", back_populates="donor")


class BloodInventory(Base):
    __tablename__ = "blood_inventory"

    id          = Column(Integer, primary_key=True, index=True)
    blood_type  = Column(String(5), nullable=False, index=True)
    units       = Column(Integer, nullable=False)          # 1 unit ≈ 450 ml
    expiry_date = Column(Date, nullable=False)
    donor_id    = Column(Integer, ForeignKey("donors.id"), nullable=True)
    added_at    = Column(DateTime(timezone=True), server_default=func.now())

    donor = relationship("Donor", back_populates="inventory_entries")


class BloodRequest(Base):
    __tablename__ = "blood_requests"

    id            = Column(Integer, primary_key=True, index=True)
    patient_name  = Column(String(120), nullable=False)
    blood_type    = Column(String(5), nullable=False, index=True)
    units_needed  = Column(Integer, nullable=False)
    units_fulfilled = Column(Integer, default=0)
    hospital      = Column(String(200), nullable=False)
    urgency       = Column(String(20), nullable=False, default="routine")  # critical / urgent / routine
    status        = Column(String(20), nullable=False, default="pending")  # pending / partial / fulfilled
    notes         = Column(Text, nullable=True)
    requested_at  = Column(DateTime(timezone=True), server_default=func.now())
    fulfilled_at  = Column(DateTime(timezone=True), nullable=True)
