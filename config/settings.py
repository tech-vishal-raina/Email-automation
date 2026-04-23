"""
config/settings.py
------------------
Central configuration loader. Reads from .env file and environment variables.
All runtime constants live here so nothing is hard-coded elsewhere.
"""

import os
from dotenv import load_dotenv
from pathlib import Path

# Resolve project root (one level up from this file)
ROOT_DIR = Path(__file__).resolve().parent.parent

# Load .env from project root
load_dotenv(ROOT_DIR / ".env")


# ── SMTP ─────────────────────────────────────────────────────────────────────
SMTP_HOST: str       = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int       = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME: str   = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD: str   = os.getenv("SMTP_PASSWORD", "")
SENDER_NAME: str     = os.getenv("SENDER_NAME", "Your Name")
SENDER_EMAIL: str    = os.getenv("SENDER_EMAIL", SMTP_USERNAME)

# ── EMAIL CONTENT ─────────────────────────────────────────────────────────────
EMAIL_SUBJECT: str   = os.getenv(
    "EMAIL_SUBJECT",
    "Exploring Backend Developer Opportunities at {{company}}"
)
TEMPLATE_FILE: str   = os.getenv(
    "TEMPLATE_FILE",
    str(ROOT_DIR / "templates" / "cold_email.txt")
)

# ── RATE LIMITING ─────────────────────────────────────────────────────────────
DELAY_MIN_SECONDS: int   = int(os.getenv("DELAY_MIN_SECONDS", "10"))
DELAY_MAX_SECONDS: int   = int(os.getenv("DELAY_MAX_SECONDS", "30"))
MAX_EMAILS_PER_RUN: int  = int(os.getenv("MAX_EMAILS_PER_RUN", "50"))
MAX_RETRIES: int          = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY_SECONDS: int  = int(os.getenv("RETRY_DELAY_SECONDS", "60"))

# ── STORAGE & LOGS ────────────────────────────────────────────────────────────
DATA_DIR: Path   = ROOT_DIR / "data"
LOGS_DIR: Path   = ROOT_DIR / "logs"
DB_PATH: str     = str(DATA_DIR / "sent_emails.db")
SENT_LOG: str    = str(LOGS_DIR / "sent_emails.log")
FAILED_LOG: str  = str(LOGS_DIR / "failed_emails.log")

# ── AI PERSONALIZATION (OPTIONAL) ─────────────────────────────────────────────
OPENAI_API_KEY: str      = os.getenv("OPENAI_API_KEY", "")
USE_AI_PERSONALIZATION: bool = os.getenv("USE_AI_PERSONALIZATION", "false").lower() == "true"
OPENAI_MODEL: str        = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ── TRACKING (OPTIONAL) ───────────────────────────────────────────────────────
TRACKING_PIXEL_URL: str  = os.getenv("TRACKING_PIXEL_URL", "")

# ── VALIDATION ────────────────────────────────────────────────────────────────
def validate_config() -> list[str]:
    """Returns a list of missing required config keys."""
    errors = []
    if not SMTP_USERNAME:
        errors.append("SMTP_USERNAME is required")
    if not SMTP_PASSWORD:
        errors.append("SMTP_PASSWORD is required")
    if not SENDER_EMAIL:
        errors.append("SENDER_EMAIL is required")
    return errors
