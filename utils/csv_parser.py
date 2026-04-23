"""
utils/csv_parser.py
-------------------
Safe, validated CSV ingestion layer.
Returns a list of clean recruiter dicts; skips and logs invalid rows.
"""

import csv
from pathlib import Path
from typing import List, Dict
from utils.validator import validate_row, validate_csv_headers
from utils.logger import log_invalid_row, log_info, log_error


def parse_recruiters(csv_path: str) -> List[Dict[str, str]]:
    """
    Parses a recruiter CSV file.

    Expected columns (case-insensitive):
        recruiter_name, recruiter_email, organization_name

    Returns:
        List of normalised dicts with keys:
            'recruiter_name', 'recruiter_email', 'organization_name'
        Invalid / duplicate-email rows are skipped and logged.
    """
    path = Path(csv_path)
    if not path.exists():
        log_error("CSV file not found: %s", csv_path)
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    recruiters: List[Dict[str, str]] = []
    seen_emails: set[str] = set()

    with open(path, newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)

        # Normalise headers to lower-case stripped strings
        if reader.fieldnames is None:
            log_error("CSV appears to be empty: %s", csv_path)
            return []

        # Remap headers to lower-case so casing in the CSV doesn't matter
        normalised_fieldnames = [f.strip().lower() for f in reader.fieldnames]
        ok, reason = validate_csv_headers(normalised_fieldnames)
        if not ok:
            log_error("CSV header validation failed: %s", reason)
            raise ValueError(f"Invalid CSV headers — {reason}")

        for row_num, raw_row in enumerate(reader, start=2):   # row 1 = header
            # Normalise keys
            row = {k.strip().lower(): v.strip() for k, v in raw_row.items() if k}

            valid, reason = validate_row(row, row_num)
            if not valid:
                log_invalid_row(row_num, row, reason)
                continue

            email = row["recruiter_email"].lower()
            if email in seen_emails:
                log_invalid_row(
                    row_num, row,
                    f"Duplicate email in CSV: {email}"
                )
                continue

            seen_emails.add(email)
            recruiters.append({
                "recruiter_name":    row["recruiter_name"],
                "recruiter_email":   email,
                "organization_name": row["organization_name"],
            })

    log_info("CSV parsed — %d valid recruiters loaded from %s",
             len(recruiters), csv_path)
    return recruiters
