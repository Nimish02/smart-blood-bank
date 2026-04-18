"""
Blood Type Compatibility Logic
==============================

Compatibility map: recipient → list of blood types they can RECEIVE from.
Based on standard ABO + Rh (Rhesus) compatibility rules.

  Blood Group | Can Receive From
  ------------|-----------------------------------------------
  A+          | A+, A-, O+, O-
  A-          | A-, O-
  B+          | B+, B-, O+, O-
  B-          | B-, O-
  AB+         | All types (universal recipient)
  AB-         | AB-, A-, B-, O-
  O+          | O+, O-
  O-          | O- only (universal donor)
"""

from typing import List

# Recipient → compatible donor types
COMPATIBILITY_MAP: dict[str, List[str]] = {
    "A+":  ["A+", "A-", "O+", "O-"],
    "A-":  ["A-", "O-"],
    "B+":  ["B+", "B-", "O+", "O-"],
    "B-":  ["B-", "O-"],
    "AB+": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
    "AB-": ["A-", "B-", "AB-", "O-"],
    "O+":  ["O+", "O-"],
    "O-":  ["O-"],
}

VALID_BLOOD_TYPES = list(COMPATIBILITY_MAP.keys())

# Urgency priority weights (lower = higher priority in sorting)
URGENCY_PRIORITY = {
    "critical": 0,
    "urgent":   1,
    "routine":  2,
}


def get_compatible_donors(recipient_blood_type: str) -> List[str]:
    """Return the list of blood types that can donate to this recipient."""
    return COMPATIBILITY_MAP.get(recipient_blood_type, [])


def is_compatible(donor_type: str, recipient_type: str) -> bool:
    """Check if a donor blood type is compatible with a recipient."""
    return donor_type in COMPATIBILITY_MAP.get(recipient_type, [])


def sort_inventory_by_compatibility(inventory_items, target_blood_type: str):
    """
    Sort inventory items:
    1. Exact blood type match first
    2. Then compatible types
    3. Within each group, sort by expiry date (soonest first — use expiring stock first)
    """
    def sort_key(item):
        exact = 0 if item.blood_type == target_blood_type else 1
        return (exact, item.expiry_date)

    return sorted(inventory_items, key=sort_key)
