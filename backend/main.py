from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional, List
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware

try:
    from backend.database import get_db, engine
    import backend.models as models
    import backend.schemas as schemas
    import backend.crud as crud
    from backend.compatibility import get_compatible_donors, COMPATIBILITY_MAP
    from backend.ai_routes import router as ai_router
except ImportError:
    from database import get_db, engine
    import models, schemas, crud
    from compatibility import get_compatible_donors, COMPATIBILITY_MAP
    from ai_routes import router as ai_router
    
models.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Blood Bank Management System",
    description="API for managing blood donors, inventory, and blood requests with compatibility matching.",
    version="1.0.0",
)

app.include_router(ai_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # you can restrict to ["http://localhost:3000"] if using React
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────
# DONORS
# ─────────────────────────────────────────────

@app.post("/add_donor", response_model=schemas.DonorOut, status_code=201, tags=["Donors"])
def add_donor(donor: schemas.DonorCreate, db: Session = Depends(get_db)):
    """
    Register a new blood donor.

    - **name**: Full name of the donor
    - **blood_type**: ABO+Rh type (A+, A-, B+, B-, AB+, AB-, O+, O-)
    - **age**: Must be between 18 and 65
    - **contact**: Phone or email
    - **city**: City of residence
    - **last_donation_date**: ISO date string (optional)
    """
    existing = crud.get_donor_by_contact(db, donor.contact)
    if existing:
        raise HTTPException(status_code=400, detail="A donor with this contact already exists.")
    return crud.create_donor(db, donor)


@app.get("/donors", response_model=List[schemas.DonorOut], tags=["Donors"])
def list_donors(
    blood_type: Optional[str] = Query(None, description="Filter by blood type"),
    city: Optional[str] = Query(None, description="Filter by city"),
    db: Session = Depends(get_db),
):
    """List all registered donors, with optional filters."""
    return crud.get_donors(db, blood_type=blood_type, city=city)


# ─────────────────────────────────────────────
# INVENTORY
# ─────────────────────────────────────────────

@app.post("/add_inventory", response_model=schemas.InventoryOut, status_code=201, tags=["Inventory"])
def add_inventory(item: schemas.InventoryCreate, db: Session = Depends(get_db)):
    """
    Add blood units to the inventory.

    - **blood_type**: ABO+Rh type
    - **units**: Number of units to add (1 unit ≈ 450 ml)
    - **expiry_date**: ISO date string — typically 35–42 days from collection
    - **donor_id**: Optional link to the donor who provided this blood
    """
    donor = None
    if item.donor_id:
        donor = crud.get_donor(db, item.donor_id)
        if not donor:
            raise HTTPException(status_code=404, detail=f"Donor ID {item.donor_id} not found.")
        if donor.blood_type != item.blood_type:
            raise HTTPException(
                status_code=400,
                detail=f"Blood type mismatch: donor is {donor.blood_type}, inventory entry is {item.blood_type}.",
            )
    return crud.add_inventory(db, item)


@app.get("/inventory", response_model=List[schemas.InventoryOut], tags=["Inventory"])
def list_inventory(
    blood_type: Optional[str] = Query(None),
    include_expired: bool = Query(False, description="Include expired units"),
    db: Session = Depends(get_db),
):
    """View current blood inventory."""
    return crud.get_inventory(db, blood_type=blood_type, include_expired=include_expired)


# ─────────────────────────────────────────────
# BLOOD REQUESTS
# ─────────────────────────────────────────────

@app.post("/request_blood", response_model=schemas.RequestOut, status_code=201, tags=["Requests"])
def request_blood(request: schemas.RequestCreate, db: Session = Depends(get_db)):
    """
    Submit a blood request.

    - **patient_name**: Name of the patient
    - **blood_type**: Required blood type
    - **units_needed**: Number of units required
    - **hospital**: Hospital name
    - **urgency**: `critical`, `urgent`, or `routine`
    - **notes**: Optional clinical notes
    """
    return crud.create_request(db, request)


@app.get("/requests", response_model=List[schemas.RequestOut], tags=["Requests"])
def list_requests(
    status: Optional[str] = Query(None, description="Filter by status: pending, fulfilled, partial"),
    urgency: Optional[str] = Query(None, description="Filter by urgency level"),
    db: Session = Depends(get_db),
):
    """List all blood requests, sorted by urgency then time."""
    return crud.get_requests(db, status=status, urgency=urgency)


# ─────────────────────────────────────────────
# MATCHING
# ─────────────────────────────────────────────

@app.get("/match_request", response_model=schemas.MatchResult, tags=["Matching"])
def match_request(
    request_id: int = Query(..., description="ID of the blood request to match"),
    db: Session = Depends(get_db),
):
    """
    Find compatible blood inventory and eligible donors for a request.

    Returns:
    - Compatible inventory entries (sorted: exact match first, then compatible types)
    - Eligible donors sorted by last donation date
    - Whether the request can be fully fulfilled from current stock
    """
    req = crud.get_request(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail=f"Request ID {request_id} not found.")

    compatible_types = get_compatible_donors(req.blood_type)

    # Inventory: non-expired, compatible, sorted (exact first, then by expiry)
    inventory_matches = crud.get_compatible_inventory(db, compatible_types, req.blood_type)

    # Donors: compatible blood type, eligible to donate (last donation > 56 days ago or never)
    donor_matches = crud.get_compatible_donors_db(db, compatible_types)

    total_available = sum(i.units for i in inventory_matches)
    fulfillment_status = (
        "fully_fulfillable" if total_available >= req.units_needed
        else "partially_fulfillable" if total_available > 0
        else "not_fulfillable"
    )

    return schemas.MatchResult(
        request=req,
        compatible_blood_types=compatible_types,
        inventory_matches=inventory_matches,
        donor_matches=donor_matches,
        total_units_available=total_available,
        fulfillment_status=fulfillment_status,
    )


@app.post("/fulfill_request/{request_id}", response_model=schemas.RequestOut, tags=["Requests"])
def fulfill_request(request_id: int, db: Session = Depends(get_db)):
    """
    Attempt to automatically fulfill a pending request from available inventory.
    Deducts units from inventory (exact match preferred, then compatible types).
    """
    req = crud.get_request(db, request_id)
    if not req:
        raise HTTPException(status_code=404, detail="Request not found.")
    if req.status == "fulfilled":
        raise HTTPException(status_code=400, detail="Request is already fulfilled.")

    compatible_types = get_compatible_donors(req.blood_type)
    updated_req = crud.fulfill_request_from_inventory(db, req, compatible_types)
    return updated_req


# ─────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────

@app.get("/stats", tags=["Stats"])
def get_stats(db: Session = Depends(get_db)):
    """Overall blood bank statistics."""
    return crud.get_stats(db)

