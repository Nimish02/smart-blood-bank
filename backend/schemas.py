from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date, datetime
from compatibility import VALID_BLOOD_TYPES, URGENCY_PRIORITY


# ─────────────────────────────────────────────
# DONOR SCHEMAS
# ─────────────────────────────────────────────

class DonorCreate(BaseModel):
    name:               str        = Field(..., min_length=2, max_length=120, examples=["Arjun Mehta"])
    blood_type:         str        = Field(..., examples=["O+"])
    age:                int        = Field(..., ge=18, le=65)
    contact:            str        = Field(..., min_length=5, max_length=120, examples=["9876543210"])
    city:               str        = Field(..., min_length=2, max_length=80, examples=["Ahmedabad"])
    last_donation_date: Optional[date] = None

    @field_validator("blood_type")
    @classmethod
    def validate_blood_type(cls, v):
        if v not in VALID_BLOOD_TYPES:
            raise ValueError(f"Invalid blood type '{v}'. Must be one of: {', '.join(VALID_BLOOD_TYPES)}")
        return v


class DonorOut(DonorCreate):
    id:         int
    created_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# INVENTORY SCHEMAS
# ─────────────────────────────────────────────

class InventoryCreate(BaseModel):
    blood_type:  str  = Field(..., examples=["A+"])
    units:       int  = Field(..., ge=1, le=100, description="Number of units (1 unit ≈ 450 ml)")
    expiry_date: date = Field(..., description="Expiry date of the blood units")
    donor_id:    Optional[int] = Field(None, description="Optional donor reference")

    @field_validator("blood_type")
    @classmethod
    def validate_blood_type(cls, v):
        if v not in VALID_BLOOD_TYPES:
            raise ValueError(f"Invalid blood type. Must be one of: {', '.join(VALID_BLOOD_TYPES)}")
        return v

    @field_validator("expiry_date")
    @classmethod
    def validate_expiry(cls, v):
        if v <= date.today():
            raise ValueError("Expiry date must be in the future.")
        return v


class InventoryOut(InventoryCreate):
    id:       int
    added_at: datetime

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# BLOOD REQUEST SCHEMAS
# ─────────────────────────────────────────────

class RequestCreate(BaseModel):
    patient_name: str = Field(..., min_length=2, max_length=120, examples=["Priya Sharma"])
    blood_type:   str = Field(..., examples=["B+"])
    units_needed: int = Field(..., ge=1, le=50)
    hospital:     str = Field(..., min_length=2, max_length=200, examples=["Civil Hospital Ahmedabad"])
    urgency:      str = Field("routine", examples=["urgent"])
    notes:        Optional[str] = Field(None, max_length=500)

    @field_validator("blood_type")
    @classmethod
    def validate_blood_type(cls, v):
        if v not in VALID_BLOOD_TYPES:
            raise ValueError(f"Invalid blood type. Must be one of: {', '.join(VALID_BLOOD_TYPES)}")
        return v

    @field_validator("urgency")
    @classmethod
    def validate_urgency(cls, v):
        if v not in URGENCY_PRIORITY:
            raise ValueError(f"Urgency must be one of: {', '.join(URGENCY_PRIORITY.keys())}")
        return v


class RequestOut(RequestCreate):
    id:               int
    units_fulfilled:  int
    status:           str
    requested_at:     datetime
    fulfilled_at:     Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────
# MATCH RESULT SCHEMA
# ─────────────────────────────────────────────

class MatchResult(BaseModel):
    request:                RequestOut
    compatible_blood_types: List[str]
    inventory_matches:      List[InventoryOut]
    donor_matches:          List[DonorOut]
    total_units_available:  int
    fulfillment_status:     str   # fully_fulfillable | partially_fulfillable | not_fulfillable

    model_config = {"from_attributes": True}
