"""
sender/email_builder.py
-----------------------
Personalization & email construction layer.

Two modes:
  1. Template mode  — simple {{placeholder}} substitution (always available)
  2. AI mode        — OpenAI rewrites the body for unique variation per recruiter
                      (activated when USE_AI_PERSONALIZATION=true + OPENAI_API_KEY set)
"""

import re
import random
from pathlib import Path
from typing import Optional

from config import settings
from utils.logger import log_info, log_error


# ── Placeholder variations for non-AI mode ────────────────────────────────────
# These are swapped in randomly to avoid identical emails triggering spam filters.
_OPENERS = [
    "I hope this message finds you well.",
    "I hope you're having a great week.",
    "I trust this email finds you in good health.",
    "I hope your week is going well.",
]

_CTA_PHRASES = [
    "I'd love the opportunity to connect and explore potential openings.",
    "I'd be grateful for the chance to discuss any relevant opportunities.",
    "I would appreciate a few minutes of your time to explore this further.",
    "I'd be thrilled to have a quick conversation about any fitting roles.",
]

_CLOSINGS = [
    "Thank you for your time and consideration.",
    "I appreciate you taking the time to read this.",
    "Thank you so much for considering my application.",
    "I sincerely appreciate your time and look forward to hearing from you.",
]


def _load_template(path: str) -> str:
    """Reads the email template file."""
    p = Path(path)
    if not p.exists():
        log_error("Template file not found: %s", path)
        raise FileNotFoundError(f"Template file not found: {path}")
    return p.read_text(encoding="utf-8")


def _resolve_placeholders(text: str, recruiter: dict) -> str:
    """Replaces {{name}}, {{company}}, and variation tokens."""
    replacements = {
        "{{name}}":         recruiter.get("recruiter_name", "Hiring Manager"),
        "{{company}}":      recruiter.get("organization_name", "your company"),
        "{{role}}":  recruiter.get("role", "Software Engineer"),
        "{{opener}}":       random.choice(_OPENERS),
        "{{cta}}":          random.choice(_CTA_PHRASES),
        "{{closing}}":      random.choice(_CLOSINGS),
        "{{sender_name}}":  settings.SENDER_NAME,
        "{{sender_email}}": settings.SENDER_EMAIL,
    }
    for token, value in replacements.items():
        text = text.replace(token, value)

    # Catch any remaining {{unknown}} tokens and warn
    unresolved = re.findall(r"\{\{[^}]+\}\}", text)
    if unresolved:
        log_error("Unresolved template tokens: %s", unresolved)

    return text


def _resolve_subject(recruiter: dict) -> str:
    subject = settings.EMAIL_SUBJECT

    replacements = {
        "{{name}}": recruiter.get("recruiter_name", ""),
        "{{company}}": recruiter.get("organization_name", ""),
        "{{role}}": recruiter.get("role", "Software Engineer"),  # fallback
    }

    for token, value in replacements.items():
        subject = subject.replace(token, value)

    return subject.strip()


# ── AI personalization ────────────────────────────────────────────────────────

def _ai_personalize(base_body: str, recruiter: dict) -> str:
    """
    Calls OpenAI to rephrase the email body uniquely for this recruiter.
    Falls back to base_body on any error so the run is never blocked.
    """
    try:
        import openai  # lazy import — only required when AI mode is on
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)

        system_prompt = (
            "You are an expert career coach helping a software engineer write "
            "personalized cold outreach emails to tech recruiters. "
            "Rewrite the following email body slightly — change wording, vary sentence "
            "structure, and make it feel uniquely written for this specific person. "
            "Keep the same meaning, professional tone, and all factual claims. "
            "Return ONLY the rewritten email body — no subject, no explanations."
        )

        user_prompt = (
            f"Recruiter name: {recruiter['recruiter_name']}\n"
            f"Company: {recruiter['organization_name']}\n\n"
            f"Original email body:\n{base_body}"
        )

        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=800,
            temperature=0.75,
        )
        return response.choices[0].message.content.strip()

    except Exception as exc:
        log_error(
            "AI personalization failed for %s — falling back to template. Error: %s",
            recruiter.get("recruiter_email"), exc
        )
        return base_body


# ── Tracking pixel (optional) ─────────────────────────────────────────────────

def _inject_tracking_pixel(html_body: str, email: str) -> str:
    """
    Appends a 1×1 transparent tracking pixel to an HTML email body.
    Only used when TRACKING_PIXEL_URL is configured.
    The pixel URL should accept a query param: ?email=<address>
    """
    if not settings.TRACKING_PIXEL_URL:
        return html_body
    import urllib.parse
    encoded = urllib.parse.quote_plus(email)
    pixel = (
        f'<img src="{settings.TRACKING_PIXEL_URL}?email={encoded}" '
        f'width="1" height="1" style="display:none;" alt="" />'
    )
    # Insert before </body> if present, otherwise append
    if "</body>" in html_body.lower():
        html_body = re.sub(r"</body>", f"{pixel}\n</body>", html_body, flags=re.IGNORECASE)
    else:
        html_body += f"\n{pixel}"
    return html_body


# ── Public API ─────────────────────────────────────────────────────────────────

def build_email(recruiter: dict) -> dict:
    """
    Builds a complete email payload for one recruiter.

    Returns:
        {
            'to':      str,
            'subject': str,
            'body':    str,    # plain-text version
            'html':    str,    # HTML version (body wrapped in <p> tags)
        }
    """
    template_text = _load_template(settings.TEMPLATE_FILE)
    body = _resolve_placeholders(template_text, recruiter)

    # Optional AI rewrite
    if settings.USE_AI_PERSONALIZATION and settings.OPENAI_API_KEY:
        log_info("AI personalizing email for %s", recruiter["recruiter_email"])
        body = _ai_personalize(body, recruiter)

    subject = _resolve_subject(recruiter)

    # Build a simple HTML version (paragraphs per blank-line-separated block)
    paragraphs = [p.strip() for p in body.strip().split("\n\n") if p.strip()]
    html_body = "\n".join(f"<p>{p.replace(chr(10), '<br>')}</p>" for p in paragraphs)
    html_body = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;font-size:14px;line-height:1.5;color:#222;">
{html_body}
</body></html>"""

    # Optional open-tracking pixel
    html_body = _inject_tracking_pixel(html_body, recruiter["recruiter_email"])

    return {
        "to":      recruiter["recruiter_email"],
        "subject": subject,
        "body":    body,
        "html":    html_body,
    }
