"""
tests/test_suite.py
-------------------
Unit tests for validator, dedup, and CSV parser.
Run with: pytest tests/
"""

import os
import sys
import tempfile
import sqlite3
import csv

# Allow importing from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ─────────────────────────────────────────────────────────────
# Validator tests
# ─────────────────────────────────────────────────────────────

from utils.validator import validate_email, validate_row, validate_csv_headers


class TestValidateEmail:
    def test_valid_email(self):
        ok, _ = validate_email("vishal@gmail.com")
        assert ok

    def test_invalid_no_at(self):
        ok, reason = validate_email("vishal.gmail.com")
        assert not ok
        assert "pattern" in reason

    def test_empty_email(self):
        ok, _ = validate_email("")
        assert not ok

    def test_none_email(self):
        ok, _ = validate_email(None)
        assert not ok

    def test_too_long_email(self):
        ok, _ = validate_email("a" * 250 + "@b.com")
        assert not ok


class TestValidateRow:
    def _good_row(self):
        return {
            "recruiter_name": "Priya",
            "recruiter_email": "priya@razorpay.com",
            "organization_name": "Razorpay",
        }

    def test_valid_row(self):
        ok, _ = validate_row(self._good_row(), 2)
        assert ok

    def test_missing_email(self):
        row = self._good_row()
        row["recruiter_email"] = ""
        ok, reason = validate_row(row, 2)
        assert not ok

    def test_bad_email(self):
        row = self._good_row()
        row["recruiter_email"] = "not-an-email"
        ok, reason = validate_row(row, 2)
        assert not ok

    def test_missing_column(self):
        row = {"recruiter_name": "X", "recruiter_email": "x@y.com"}
        ok, reason = validate_row(row, 2)
        assert not ok
        assert "organization_name" in reason


class TestValidateCsvHeaders:
    def test_valid_headers(self):
        ok, _ = validate_csv_headers(
            ["recruiter_name", "recruiter_email", "organization_name"]
        )
        assert ok

    def test_missing_header(self):
        ok, reason = validate_csv_headers(["recruiter_name", "recruiter_email"])
        assert not ok
        assert "organization_name" in reason

    def test_case_insensitive(self):
        ok, _ = validate_csv_headers(
            ["Recruiter_Name", "Recruiter_Email", "Organization_Name"]
        )
        assert ok


# ─────────────────────────────────────────────────────────────
# Deduplication store tests
# ─────────────────────────────────────────────────────────────

from utils.dedup import DeduplicationStore


class TestDeduplicationStore:
    def _store(self):
        """Creates an in-memory SQLite dedup store for testing."""
        tmp = tempfile.mktemp(suffix=".db")
        return DeduplicationStore(db_path=tmp)

    def test_not_sent_initially(self):
        with self._store() as s:
            assert not s.already_sent("test@example.com")

    def test_mark_and_check(self):
        with self._store() as s:
            s.mark_sent("a@b.com", "Alice", "Acme", "Test Subject")
            assert s.already_sent("a@b.com")

    def test_case_insensitive(self):
        with self._store() as s:
            s.mark_sent("UPPER@CASE.COM")
            assert s.already_sent("upper@case.com")

    def test_idempotent_mark(self):
        with self._store() as s:
            s.mark_sent("x@x.com")
            s.mark_sent("x@x.com")   # should not raise
            assert s.count() == 1

    def test_count(self):
        with self._store() as s:
            s.mark_sent("one@x.com")
            s.mark_sent("two@x.com")
            assert s.count() == 2

    def test_get_all_sent(self):
        with self._store() as s:
            s.mark_sent("a@x.com", "A", "CompA")
            records = s.get_all_sent()
            assert len(records) == 1
            assert records[0]["email"] == "a@x.com"
            assert records[0]["company"] == "CompA"


# ─────────────────────────────────────────────────────────────
# CSV parser tests
# ─────────────────────────────────────────────────────────────

from utils.csv_parser import parse_recruiters


def _write_csv(rows: list[dict], headers: list[str]) -> str:
    tmp = tempfile.mktemp(suffix=".csv")
    with open(tmp, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    return tmp


class TestCsvParser:
    def test_valid_csv(self):
        path = _write_csv(
            [
                {"recruiter_name": "Priya", "recruiter_email": "priya@r.com",
                 "organization_name": "Razorpay"},
            ],
            ["recruiter_name", "recruiter_email", "organization_name"],
        )
        result = parse_recruiters(path)
        assert len(result) == 1
        assert result[0]["recruiter_email"] == "priya@r.com"

    def test_skips_invalid_email(self):
        path = _write_csv(
            [
                {"recruiter_name": "Bad", "recruiter_email": "not-valid",
                 "organization_name": "X"},
                {"recruiter_name": "Good", "recruiter_email": "good@x.com",
                 "organization_name": "X"},
            ],
            ["recruiter_name", "recruiter_email", "organization_name"],
        )
        result = parse_recruiters(path)
        assert len(result) == 1
        assert result[0]["recruiter_email"] == "good@x.com"

    def test_deduplicates_within_csv(self):
        path = _write_csv(
            [
                {"recruiter_name": "A", "recruiter_email": "dup@x.com",
                 "organization_name": "X"},
                {"recruiter_name": "B", "recruiter_email": "dup@x.com",
                 "organization_name": "Y"},
            ],
            ["recruiter_name", "recruiter_email", "organization_name"],
        )
        result = parse_recruiters(path)
        assert len(result) == 1

    def test_missing_file_raises(self):
        import pytest
        with pytest.raises(FileNotFoundError):
            parse_recruiters("/nonexistent/file.csv")

    def test_normalises_email_to_lowercase(self):
        path = _write_csv(
            [{"recruiter_name": "X", "recruiter_email": "CAPS@EXAMPLE.COM",
              "organization_name": "Y"}],
            ["recruiter_name", "recruiter_email", "organization_name"],
        )
        result = parse_recruiters(path)
        assert result[0]["recruiter_email"] == "caps@example.com"
