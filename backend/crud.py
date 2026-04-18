from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date, datetime, timedelta
from typing import Optional, List

import models, schemas
from compatibility import URGENCY_PRIORITY, sort_inventory_by_compatibility


# ─────────────────────────────────────────────
# DONORS
# ─────────────────────────────────────────────

def create_donor(db: Session, donor: schemas.DonorCreate) -> models.Donor:
    db_donor = models.Donor(**donor.model_dump())
    db.add(db_donor)
    db.commit()
    db.refresh(db_donor)
    return db_donor


def get_donor(db: Session, donor_id: int) -> Optional[models.Donor]:
    return db.query(models.Donor).filter(models.Donor.id == donor_id).first()


def get_donor_by_contact(db: Session, contact: str) -> Optional[models.Donor]:
    return db.query(models.Donor).filter(models.Donor.contact == contact).first()


def get_donors(
    db: Session,
    blood_type: Optional[str] = None,
    city: Optional[str] = None,
) -> List[models.Donor]:
    q = db.query(models.Donor)
    if blood_type:
        q = q.filter(models.Donor.blood_type == blood_type)
    if city:
        q = q.filter(models.Donor.city.ilike(f"%{city}%"))
    return q.order_by(models.Donor.created_at.desc()).all()


def get_compatible_donors_db(
    db: Session,
    compatible_types: List[str],
) -> List[models.Donor]:
    """
    Return donors with compatible blood types who are eligible to donate.
    Eligibility: last donation was > 56 days ago (8 weeks) or they've never donated.
    Sorted: never donated first (most available), then by oldest donation date.
    """
    cutoff = date.today() - timedelta(days=56)

    donors = (
        db.query(models.Donor)
        .filter(models.Donor.blood_type.in_(compatible_types))
        .filter(
            (models.Donor.last_donation_date == None) |
            (models.Donor.last_donation_date <= cutoff)
        )
        .all()
    )

    # Sort: never donated first, then by oldest donation (most rested)
    def donor_sort_key(d):
        if d.last_donation_date is None:
            return (0, date.min)
        return (1, d.last_donation_date)

    return sorted(donors, key=donor_sort_key)


# ─────────────────────────────────────────────
# INVENTORY
# ─────────────────────────────────────────────

def add_inventory(db: Session, item: schemas.InventoryCreate) -> models.BloodInventory:
    db_item = models.BloodInventory(**item.model_dump())
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def get_inventory(
    db: Session,
    blood_type: Optional[str] = None,
    include_expired: bool = False,
) -> List[models.BloodInventory]:
    q = db.query(models.BloodInventory)
    if blood_type:
        q = q.filter(models.BloodInventory.blood_type == blood_type)
    if not include_expired:
        q = q.filter(models.BloodInventory.expiry_date > date.today())
    return q.order_by(models.BloodInventory.expiry_date.asc()).all()


def get_compatible_inventory(
    db: Session,
    compatible_types: List[str],
    target_blood_type: str,
) -> List[models.BloodInventory]:
    """Non-expired inventory of compatible types, sorted: exact match first, then by expiry (FIFO)."""
    items = (
        db.query(models.BloodInventory)
        .filter(models.BloodInventory.blood_type.in_(compatible_types))
        .filter(models.BloodInventory.expiry_date > date.today())
        .filter(models.BloodInventory.units > 0)
        .all()
    )
    return sort_inventory_by_compatibility(items, target_blood_type)


# ─────────────────────────────────────────────
# BLOOD REQUESTS
# ─────────────────────────────────────────────

def create_request(db: Session, request: schemas.RequestCreate) -> models.BloodRequest:
    db_req = models.BloodRequest(**request.model_dump())
    db.add(db_req)
    db.commit()
    db.refresh(db_req)
    return db_req


def get_request(db: Session, request_id: int) -> Optional[models.BloodRequest]:
    return db.query(models.BloodRequest).filter(models.BloodRequest.id == request_id).first()


def get_requests(
    db: Session,
    status: Optional[str] = None,
    urgency: Optional[str] = None,
) -> List[models.BloodRequest]:
    """
    Return all requests sorted by:
    1. Urgency (critical → urgent → routine)
    2. Requested time (oldest first within same urgency)
    """
    q = db.query(models.BloodRequest)
    if status:
        q = q.filter(models.BloodRequest.status == status)
    if urgency:
        q = q.filter(models.BloodRequest.urgency == urgency)

    requests = q.all()

    # Python-side sort since SQLite doesn't support custom CASE order easily via ORM
    requests.sort(key=lambda r: (
        URGENCY_PRIORITY.get(r.urgency, 99),
        r.requested_at,
    ))
    return requests


def fulfill_request_from_inventory(
    db: Session,
    req: models.BloodRequest,
    compatible_types: List[str],
) -> models.BloodRequest:
    """
    Attempt to fulfill a request from existing inventory.
    Deducts units greedily: exact blood type first, then compatible types,
    both sorted by expiry date (use soonest-to-expire first).
    """
    still_needed = req.units_needed - req.units_fulfilled

    inventory = get_compatible_inventory(db, compatible_types, req.blood_type)

    for inv_item in inventory:
        if still_needed <= 0:
            break
        if inv_item.units == 0:
            continue

        deduct = min(inv_item.units, still_needed)
        inv_item.units -= deduct
        still_needed -= deduct
        req.units_fulfilled += deduct

    if still_needed <= 0:
        req.status = "fulfilled"
        req.fulfilled_at = datetime.utcnow()
    elif req.units_fulfilled > 0:
        req.status = "partial"
    # else: remains "pending"

    db.commit()
    db.refresh(req)
    return req


# ─────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────

def get_stats(db: Session) -> dict:
    today = date.today()

    total_donors = db.query(func.count(models.Donor.id)).scalar()
    total_inventory_units = (
        db.query(func.sum(models.BloodInventory.units))
        .filter(models.BloodInventory.expiry_date > today)
        .scalar() or 0
    )
    expiring_soon = (
        db.query(func.sum(models.BloodInventory.units))
        .filter(
            models.BloodInventory.expiry_date > today,
            models.BloodInventory.expiry_date <= today + timedelta(days=7),
        )
        .scalar() or 0
    )

    pending_requests = (
        db.query(func.count(models.BloodRequest.id))
        .filter(models.BloodRequest.status.in_(["pending", "partial"]))
        .scalar()
    )
    critical_requests = (
        db.query(func.count(models.BloodRequest.id))
        .filter(
            models.BloodRequest.urgency == "critical",
            models.BloodRequest.status != "fulfilled",
        )
        .scalar()
    )

    # Inventory breakdown by blood type
    inventory_by_type = (
        db.query(models.BloodInventory.blood_type, func.sum(models.BloodInventory.units))
        .filter(models.BloodInventory.expiry_date > today)
        .group_by(models.BloodInventory.blood_type)
        .all()
    )

    return {
        "total_donors": total_donors,
        "total_units_available": total_inventory_units,
        "units_expiring_within_7_days": expiring_soon,
        "pending_requests": pending_requests,
        "critical_unfulfilled_requests": critical_requests,
        "inventory_by_blood_type": {bt: int(units) for bt, units in inventory_by_type},
    }
