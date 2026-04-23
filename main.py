#!/usr/bin/env python3
"""
main.py — Email Automation CLI Entry Point
==========================================
The single executable that Antigravity (or a human) invokes.

Usage
-----
  python main.py --csv data/recruiters.csv --resume resume.pdf

Options
  --csv        Path to recruiter CSV (required)
  --resume     Path to PDF resume (required)
  --template   Override template file path (optional)
  --limit      Max emails this run — overrides config (optional)
  --dry-run    Preview without sending
  --status     Print sent-email database stats and exit
  --reset      DANGER: clear the deduplication database and exit
"""

import argparse
import sys
import time
import random
from pathlib import Path
from datetime import datetime

from config import settings, validate_config
from utils.csv_parser import parse_recruiters
from utils.dedup import get_store
from utils.logger import log_info, log_error, log_sent, log_skipped, log_failed
from sender.email_builder import build_email
from sender.smtp_client import SMTPClient


# ─────────────────────────────────────────────────────────────────────────────
# Antigravity-compatible task functions
# Each function is a discrete, composable unit of work.
# ─────────────────────────────────────────────────────────────────────────────

def task_load_recruiters(csv_path: str) -> list[dict]:
    """Task: parse and validate recruiter CSV."""
    return parse_recruiters(csv_path)


def task_filter_unsent(recruiters: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Task: split recruiter list into (to_send, already_sent).
    Uses the persistent SQLite deduplication store.
    """
    store = get_store()
    to_send, skipped = [], []
    for r in recruiters:
        if store.already_sent(r["recruiter_email"]):
            skipped.append(r)
        else:
            to_send.append(r)
    return to_send, skipped


def task_send_campaign(
    recruiters: list[dict],
    resume_path: str,
    limit: int = settings.MAX_EMAILS_PER_RUN,
    dry_run: bool = False,
) -> dict:
    """
    Task: iterate over recruiter list and send emails.
    Returns a summary dict with sent/skipped/failed counts.

    This is the core orchestration task — Antigravity can call it directly.
    """
    store = get_store()
    summary = {"sent": 0, "skipped": 0, "failed": 0, "total": len(recruiters)}
    batch = recruiters[:limit]

    if dry_run:
        log_info("DRY RUN — no emails will actually be sent.")
        # In dry run mode, we don't initialize SMTP client at all
        for idx, recruiter in enumerate(batch, start=1):
            email = recruiter["recruiter_email"]

            # Double-check dedup (guards against concurrent runs)
            if store.already_sent(email):
                log_skipped(email, "already in sent database")
                summary["skipped"] += 1
                continue

            # Build personalised email
            try:
                payload = build_email(recruiter)
            except Exception as exc:
                log_failed(email, f"Email build error: {exc}")
                summary["failed"] += 1
                continue

            log_info(
                "DRY RUN | %d/%d | to=%s | subject=%s",
                idx, len(batch), email, payload["subject"]
            )
            summary["sent"] += 1

        return summary

    # Only initialize SMTP client for actual sending
    with SMTPClient() as client:
        for idx, recruiter in enumerate(batch, start=1):
            email = recruiter["recruiter_email"]

            # Double-check dedup (guards against concurrent runs)
            if store.already_sent(email):
                log_skipped(email, "already in sent database")
                summary["skipped"] += 1
                continue

            # Build personalised email
            try:
                payload = build_email(recruiter)
            except Exception as exc:
                log_failed(email, f"Email build error: {exc}")
                summary["failed"] += 1
                continue

            # Send
            success = client.send(payload, resume_path=resume_path)

            if success:
                store.mark_sent(
                    email=email,
                    name=recruiter["recruiter_name"],
                    company=recruiter["organization_name"],
                    subject=payload["subject"],
                )
                log_sent(email, recruiter["recruiter_name"], recruiter["organization_name"])
                summary["sent"] += 1
            else:
                summary["failed"] += 1

            # Rate limiting — random delay between emails
            if idx < len(batch):
                delay = random.randint(
                    settings.DELAY_MIN_SECONDS,
                    settings.DELAY_MAX_SECONDS
                )
                log_info("Rate-limit delay: %ds before next email…", delay)
                time.sleep(delay)

    return summary


def task_print_status() -> None:
    """Task: print a report of all sent emails from the dedup store."""
    store = get_store()
    records = store.get_all_sent()
    total = len(records)
    print(f"\n{'─'*60}")
    print(f"  Sent Email Database  ({total} records)")
    print(f"{'─'*60}")
    if not records:
        print("  (empty — no emails sent yet)")
    for r in records:
        print(f"  {r['sent_at'][:19]}  {r['email']:<35} {r['company']}")
    print(f"{'─'*60}\n")


def task_reset_database() -> None:
    """
    Task: DESTRUCTIVE — wipe the deduplication database.
    Requires explicit confirmation.
    """
    ans = input("⚠️  This will erase all sent-email records. Type 'yes' to confirm: ")
    if ans.strip().lower() != "yes":
        print("Aborted.")
        return
    import sqlite3
    conn = sqlite3.connect(settings.DB_PATH)
    conn.execute("DELETE FROM sent_emails;")
    conn.commit()
    conn.close()
    print("✅  Deduplication database cleared.")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def build_cli() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="email-automation",
        description="Automated cold email outreach to recruiters",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples
  python main.py --csv data/recruiters.csv --resume resume.pdf
  python main.py --csv data/recruiters.csv --resume resume.pdf --dry-run
  python main.py --csv data/recruiters.csv --resume resume.pdf --limit 10
  python main.py --status
  python main.py --reset
        """,
    )
    p.add_argument("--csv",      metavar="PATH", help="Path to recruiter CSV file")
    p.add_argument("--resume",   metavar="PATH", help="Path to PDF resume")
    p.add_argument("--template", metavar="PATH", help="Override email template path")
    p.add_argument("--limit",    metavar="N",    type=int,
                   help=f"Max emails this run (default: {settings.MAX_EMAILS_PER_RUN})")
    p.add_argument("--dry-run",  action="store_true",
                   help="Preview emails without sending")
    p.add_argument("--status",   action="store_true",
                   help="Show sent-email database stats")
    p.add_argument("--reset",    action="store_true",
                   help="Clear deduplication database (DESTRUCTIVE)")
    return p


def main(argv=None) -> int:
    parser = build_cli()
    args = parser.parse_args(argv)

    # ── Utility commands (no email sending) ───────────────────────────────────
    if args.status:
        task_print_status()
        return 0

    if args.reset:
        task_reset_database()
        return 0

    # ── Validate required args ────────────────────────────────────────────────
    if not args.csv:
        parser.error("--csv is required")
    if not args.resume:
        parser.error("--resume is required")

    # Override template if provided
    if args.template:
        settings.TEMPLATE_FILE = args.template

    # ── Config validation (skip for dry-run) ──────────────────────────────────
    if not args.dry_run:
        errors = validate_config()
        if errors:
            for e in errors:
                log_error("Config error: %s", e)
            log_error("Fix the above config errors in your .env file and retry.")
            return 1

    # ── Resume file check ──────────────────────────────────────────────────────
    if not Path(args.resume).exists():
        log_error("Resume file not found: %s", args.resume)
        return 1

    # ── Run ───────────────────────────────────────────────────────────────────
    start = datetime.now()
    log_info("=" * 60)
    log_info("Email Campaign Starting  %s", start.strftime("%Y-%m-%d %H:%M:%S"))
    log_info("CSV: %s | Resume: %s | Dry-run: %s",
             args.csv, args.resume, args.dry_run)
    log_info("=" * 60)

    # 1. Load recruiters
    try:
        all_recruiters = task_load_recruiters(args.csv)
    except (FileNotFoundError, ValueError) as exc:
        log_error("%s", exc)
        return 1

    if not all_recruiters:
        log_info("No valid recruiters found. Exiting.")
        return 0

    # 2. Filter already-sent
    to_send, already_sent = task_filter_unsent(all_recruiters)
    log_info("Total: %d | Already sent: %d | To send: %d",
             len(all_recruiters), len(already_sent), len(to_send))

    if not to_send:
        log_info("All recruiters have already been contacted. Nothing to do.")
        return 0

    # 3. Send
    limit = args.limit or settings.MAX_EMAILS_PER_RUN
    summary = task_send_campaign(
        recruiters=to_send,
        resume_path=args.resume,
        limit=limit,
        dry_run=args.dry_run,
    )

    # 4. Final summary
    elapsed = (datetime.now() - start).seconds
    log_info("=" * 60)
    log_info(
        "Campaign Complete | Sent: %d | Skipped: %d | Failed: %d | Time: %ds",
        summary["sent"], summary["skipped"], summary["failed"], elapsed
    )
    log_info("=" * 60)

    return 0 if summary["failed"] == 0 else 2


# ── Antigravity agent entry point ─────────────────────────────────────────────
# Antigravity can import and call `run_agent_task()` directly, passing kwargs.

def run_agent_task(
    csv_path: str,
    resume_path: str,
    dry_run: bool = False,
    limit: int = settings.MAX_EMAILS_PER_RUN,
) -> dict:
    """
    Antigravity-compatible function wrapper.
    Returns a summary dict; does not call sys.exit().

    Example:
        from main import run_agent_task
        result = run_agent_task(
            csv_path="data/recruiters.csv",
            resume_path="resume.pdf",
        )
        print(result)
        # {'sent': 8, 'skipped': 2, 'failed': 0, 'total': 10}
    """
    recruiters = task_load_recruiters(csv_path)
    to_send, _ = task_filter_unsent(recruiters)
    return task_send_campaign(
        recruiters=to_send,
        resume_path=resume_path,
        limit=limit,
        dry_run=dry_run,
    )


if __name__ == "__main__":
    sys.exit(main())
