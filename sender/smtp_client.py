"""
sender/smtp_client.py
---------------------
SMTP email sender with:
  • TLS (STARTTLS on port 587, SSL on port 465)
  • PDF resume attachment
  • Multipart alternative (plain text + HTML)
  • Exponential-backoff retry
  • Clean connection lifecycle (open once per run)
"""

import smtplib
import ssl
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.application import MIMEApplication
from email import encoders
from pathlib import Path
from typing import Optional

from config import settings
from utils.logger import log_info, log_error, log_failed


class SMTPClient:
    """
    Manages a persistent SMTP connection for a single campaign run.
    Use as a context manager:

        with SMTPClient() as client:
            client.send(email_payload, resume_path)
    """

    def __init__(self):
        self._server: Optional[smtplib.SMTP] = None

    # ── Connection management ──────────────────────────────────────────────────

    def connect(self) -> None:
        """Opens and authenticates the SMTP connection."""
        try:
            if settings.SMTP_PORT == 465:
                # SSL from the start
                context = ssl.create_default_context()
                self._server = smtplib.SMTP_SSL(
                    settings.SMTP_HOST, settings.SMTP_PORT, context=context
                )
            else:
                # STARTTLS (port 587 standard)
                self._server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
                self._server.ehlo()
                self._server.starttls(context=ssl.create_default_context())
                self._server.ehlo()

            self._server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            log_info("SMTP connected — %s:%s", settings.SMTP_HOST, settings.SMTP_PORT)

        except smtplib.SMTPAuthenticationError as exc:
            error_msg = (
                f"SMTP authentication failed: {exc}\n\n"
                "🔍 Common solutions for Gmail:\n"
                "1. Use an App Password, not your account password\n"
                "   → Enable 2FA: https://myaccount.google.com/security\n"
                "   → Generate App Password: https://myaccount.google.com/apppasswords\n"
                "2. Check for typos in username/password in .env file\n"
                "3. Try unlocking the captcha: https://accounts.google.com/displayunlockcaptcha"
            )
            log_error(error_msg)
            raise
        except Exception as exc:
            log_error("SMTP connection error: %s", exc)
            raise

    def disconnect(self) -> None:
        """Safely closes the SMTP connection."""
        if self._server:
            try:
                self._server.quit()
            except Exception:
                pass
            self._server = None
            log_info("SMTP disconnected.")

    def is_connected(self) -> bool:
        """Pings the server to check liveness."""
        if not self._server:
            return False
        try:
            status = self._server.noop()
            return status[0] == 250
        except Exception:
            return False

    def _reconnect_if_needed(self) -> None:
        if not self.is_connected():
            log_info("SMTP connection lost — reconnecting…")
            self.connect()

    # ── Message construction ──────────────────────────────────────────────────

    @staticmethod
    def _build_message(
        payload: dict,
        resume_path: Optional[str],
    ) -> MIMEMultipart:
        """
        Constructs a MIME message from an email payload dict.
        """
        msg = MIMEMultipart("mixed")
        msg["From"]    = f"{settings.SENDER_NAME} <{settings.SENDER_EMAIL}>"
        msg["To"]      = payload["to"]
        msg["Subject"] = payload["subject"]
        msg["X-Mailer"] = "EmailAutomation/1.0"

        # Multipart/alternative for plain + HTML
        alt_part = MIMEMultipart("alternative")
        alt_part.attach(MIMEText(payload["body"], "plain", "utf-8"))
        alt_part.attach(MIMEText(payload["html"],  "html",  "utf-8"))
        msg.attach(alt_part)

        # Resume attachment
        if resume_path:
            resume_path = Path(resume_path)
            if not resume_path.exists():
                log_error("Resume file not found: %s — skipping attachment", resume_path)
            else:
                with open(resume_path, "rb") as f:
                    part = MIMEApplication(f.read(), _subtype="pdf")
                part.add_header(
                    "Content-Disposition",
                    "attachment",
                    filename=resume_path.name,
                )
                msg.attach(part)

        return msg

    # ── Sending with retry ────────────────────────────────────────────────────

    def send(
        self,
        payload: dict,
        resume_path: Optional[str] = None,
        retries: int = settings.MAX_RETRIES,
    ) -> bool:
        """
        Sends one email. Returns True on success, False on permanent failure.
        Retries up to `retries` times with exponential backoff.
        """
        msg = self._build_message(payload, resume_path)

        for attempt in range(1, retries + 1):
            try:
                self._reconnect_if_needed()
                self._server.sendmail(
                    settings.SENDER_EMAIL,
                    payload["to"],
                    msg.as_string(),
                )
                return True

            except smtplib.SMTPRecipientsRefused as exc:
                # Permanent failure — no point retrying
                log_failed(
                    payload["to"],
                    f"Recipient refused (permanent): {exc.recipients}"
                )
                return False

            except (smtplib.SMTPServerDisconnected,
                    smtplib.SMTPSenderRefused,
                    smtplib.SMTPDataError,
                    ConnectionResetError,
                    OSError) as exc:
                log_error(
                    "Send attempt %d/%d failed for %s: %s",
                    attempt, retries, payload["to"], exc
                )
                if attempt < retries:
                    backoff = settings.RETRY_DELAY_SECONDS * attempt
                    log_info("Retrying in %ds…", backoff)
                    self._server = None   # force reconnect on next attempt
                    time.sleep(backoff)
                else:
                    log_failed(payload["to"], str(exc))
                    return False

            except Exception as exc:
                log_failed(payload["to"], f"Unexpected error: {exc}")
                return False

        return False

    # ── Context manager ───────────────────────────────────────────────────────

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.disconnect()
