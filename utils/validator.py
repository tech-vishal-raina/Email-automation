"""
utils/validator.py
------------------
Input validation helpers. All functions return (is_valid: bool, reason: str).
"""

import re
from typing import Tuple

# RFC-5322 simplified pattern — catches 99 % of real-world invalid addresses
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
)

REQUIRED_COLUMNS = {"recruiter_name", "recruiter_email", "organization_name"}


def validate_email(address: str) -> Tuple[bool, str]:
    """Validates a single email address string."""
    if not address or not isinstance(address, str):
        return False, "Email is empty or not a string"
    address = address.strip()
    if not _EMAIL_RE.match(address):
        return False, f"'{address}' does not match email pattern"
    if len(address) > 254:
        return False, "Email exceeds maximum length of 254 characters"
    return True, ""


def validate_row(row: dict, row_num: int) -> Tuple[bool, str]:
    """
    Validates a CSV row dict. Returns (True, '') if all required
    fields are present and the email address is syntactically valid.
    """
    # Check required keys present
    missing = REQUIRED_COLUMNS - set(row.keys())
    if missing:
        return False, f"Missing columns: {missing}"

    # Check no required field is blank
    for col in REQUIRED_COLUMNS:
        val = row.get(col, "").strip()
        if not val:
            return False, f"Column '{col}' is blank"

    # Validate email syntax
    ok, reason = validate_email(row["recruiter_email"])
    if not ok:
        return False, reason

    return True, ""


def validate_csv_headers(headers: list[str]) -> Tuple[bool, str]:
    """Checks that a CSV has the required column headers."""
    present = set(h.strip().lower() for h in headers)
    missing = {c.lower() for c in REQUIRED_COLUMNS} - present
    if missing:
        return False, f"CSV is missing required columns: {missing}"
    return True, ""
