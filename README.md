# 📧 Email Automation — Cold Recruiter Outreach

> Production-ready automated cold email system with deduplication, rate limiting,
> resume attachment, AI personalization, and Antigravity agent compatibility.

---

## 📁 Project Structure

```
email-automation/
├── main.py                  ← CLI entry point + Antigravity task functions
├── antigravity.json         ← Antigravity agent manifest
├── requirements.txt
├── .env.example             ← Copy → .env and fill in credentials
│
├── config/
│   ├── __init__.py
│   └── settings.py          ← All config, loaded from .env
│
├── sender/
│   ├── __init__.py
│   ├── email_builder.py     ← Template engine + optional AI personalization
│   └── smtp_client.py       ← SMTP sender with retry logic + PDF attachment
│
├── templates/
│   └── cold_email.txt       ← Email template with {{placeholders}}
│
├── data/
│   ├── recruiters.csv       ← Sample CSV input
│   └── sent_emails.db       ← SQLite dedup store (auto-created)
│
├── logs/
│   ├── sent_emails.log      ← All sent emails (auto-created)
│   └── failed_emails.log    ← All failures (auto-created)
│
├── utils/
│   ├── __init__.py
│   ├── csv_parser.py        ← Safe CSV ingestion with validation
│   ├── dedup.py             ← SQLite deduplication store
│   ├── logger.py            ← Dual-file structured logger
│   └── validator.py         ← Email + row validation
│
└── tests/
    └── test_suite.py        ← Unit tests (pytest)
```

---

## ⚡ Quick Start

### 1. Install dependencies
```bash
cd email-automation
pip install -r requirements.txt
```

### 2. Configure credentials
```bash
cp .env.example .env
# Edit .env with your real Gmail credentials
```

> **Gmail Setup**: Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords),
> enable 2FA if not already, then generate a 16-character **App Password**.
> Use that as `SMTP_PASSWORD` — NOT your regular Gmail password.

### 3. Prepare your files
```bash
# Place your CSV in data/
# recruiters.csv columns: recruiter_name, recruiter_email, organization_name

# Place your resume PDF at project root (or any path)
cp /path/to/your/resume.pdf resume.pdf
```

### 4. Dry run first (ALWAYS do this)
```bash
python main.py --csv data/recruiters.csv --resume resume.pdf --dry-run
```

### 5. Send for real
```bash
python main.py --csv data/recruiters.csv --resume resume.pdf
```

---

## 🔧 CLI Reference

```bash
# Basic send
python main.py --csv data/recruiters.csv --resume resume.pdf

# Preview without sending
python main.py --csv data/recruiters.csv --resume resume.pdf --dry-run

# Limit to 10 emails this run
python main.py --csv data/recruiters.csv --resume resume.pdf --limit 10

# Use a custom template
python main.py --csv data/recruiters.csv --resume resume.pdf --template templates/followup.txt

# Check who has been contacted so far
python main.py --status

# DANGER: reset the dedup database (will allow re-sending to everyone)
python main.py --reset
```

---

## 📋 CSV Format

```csv
recruiter_name,recruiter_email,organization_name
Priya Sharma,priya@razorpay.com,Razorpay
Arjun Mehta,arjun@groww.in,Groww
```

- Column names are **case-insensitive**
- Invalid rows (bad email, blank fields) are **skipped and logged**
- Duplicate emails in the CSV are **automatically deduplicated**

---

## ✏️ Template Placeholders

| Placeholder       | Replaced with                          |
|-------------------|----------------------------------------|
| `{{name}}`        | Recruiter's name                       |
| `{{company}}`     | Organization name                      |
| `{{opener}}`      | Random professional opener sentence    |
| `{{cta}}`         | Random call-to-action phrase           |
| `{{closing}}`     | Random closing sentence                |
| `{{sender_name}}` | Your name (from `.env`)                |
| `{{sender_email}}`| Your email (from `.env`)               |

---

## 🤖 AI Personalization (Optional)

When enabled, OpenAI rewrites each email body uniquely for every recruiter —
different sentence structure, word choices, and flow — so every email feels
handcrafted. The same factual claims are preserved.

```env
USE_AI_PERSONALIZATION=true
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
```

**Cost**: ~$0.001 per email with `gpt-4o-mini`. 50 emails ≈ $0.05.

---

## 🔌 Antigravity Integration

The project is fully compatible with the Antigravity agentic framework.

### Option A — Import and call task functions directly
```python
from main import run_agent_task

result = run_agent_task(
    csv_path="data/recruiters.csv",
    resume_path="resume.pdf",
    dry_run=False,
    limit=20,
)
print(result)
# {'sent': 18, 'skipped': 2, 'failed': 0, 'total': 20}
```

### Option B — Compose individual tasks
```python
from main import task_load_recruiters, task_filter_unsent, task_send_campaign

recruiters = task_load_recruiters("data/recruiters.csv")
to_send, already_sent = task_filter_unsent(recruiters)
summary = task_send_campaign(to_send, resume_path="resume.pdf", limit=10)
```

### Option C — Antigravity manifest
Point Antigravity at `antigravity.json`. It declares all tasks, inputs,
outputs, scheduling, and required environment variables.

---

## ⚙️ Configuration Reference

| Variable                | Default                     | Description                             |
|-------------------------|-----------------------------|-----------------------------------------|
| `SMTP_HOST`             | `smtp.gmail.com`            | SMTP server hostname                    |
| `SMTP_PORT`             | `587`                       | SMTP port (587=STARTTLS, 465=SSL)        |
| `SMTP_USERNAME`         | —                           | Gmail address (required)                |
| `SMTP_PASSWORD`         | —                           | Gmail App Password (required)           |
| `SENDER_NAME`           | —                           | Your display name                       |
| `SENDER_EMAIL`          | Same as `SMTP_USERNAME`     | From address                            |
| `EMAIL_SUBJECT`         | See `.env.example`          | Subject with optional `{{company}}`     |
| `DELAY_MIN_SECONDS`     | `10`                        | Min delay between emails                |
| `DELAY_MAX_SECONDS`     | `30`                        | Max delay between emails                |
| `MAX_EMAILS_PER_RUN`    | `50`                        | Hard cap per execution                  |
| `MAX_RETRIES`           | `3`                         | SMTP retry attempts per email           |
| `RETRY_DELAY_SECONDS`   | `60`                        | Base delay before retry (multiplied)    |
| `USE_AI_PERSONALIZATION`| `false`                     | Enable OpenAI rewriting                 |
| `OPENAI_API_KEY`        | —                           | OpenAI key (if AI mode enabled)         |
| `TRACKING_PIXEL_URL`    | —                           | URL for open-tracking pixel             |

---

## 🔒 Deduplication — How It Works

1. Every successfully sent email is written to `data/sent_emails.db` (SQLite).
2. On each run, **before building or sending** any email, the system checks this DB.
3. If an email address already exists → **skip**, log it, move on.
4. The check is thread-safe (WAL mode + mutex lock).
5. The DB persists across runs, machines, and code deploys — as long as the file exists.

This means you can run the script multiple times on the same CSV safely.

---

## 📬 Avoiding Spam Filters — Best Practices

| Practice                        | How this tool helps                              |
|---------------------------------|--------------------------------------------------|
| **Varied wording**              | `{{opener}}`, `{{cta}}`, `{{closing}}` tokens    |
| **AI uniqueness**               | Optional OpenAI rewrite per email                |
| **Rate limiting**               | 10–30s random delay between sends                |
| **Volume cap**                  | 50 emails/day max (configurable)                 |
| **Plain text fallback**         | Multipart/alternative (plain + HTML)             |
| **No purchased lists**          | Only send to people who match your profile       |
| **Professional from address**   | Use your real name + Gmail address               |
| **SPF/DKIM**                    | Gmail handles this automatically for @gmail.com  |

**Additional tips (manual)**:
- Warm up a new Gmail account gradually (start with 10/day, scale up)
- Don't use link shorteners in cold emails
- Avoid ALL CAPS in subject lines
- Personalise the opening line if possible

---

## 📈 Scaling

For >500 emails/day, switch from Gmail SMTP to a transactional email provider:

1. **SendGrid** — free tier: 100/day, paid: unlimited
   - Change `SMTP_HOST=smtp.sendgrid.net`, `SMTP_PORT=587`
   - `SMTP_USERNAME=apikey`, `SMTP_PASSWORD=<your_sendgrid_api_key>`

2. **Amazon SES** — ~$0.10/1,000 emails, very high deliverability

3. **Mailgun** — developer-friendly, good EU options

The codebase needs **zero changes** — just update the `.env` variables.

---

## 🧪 Running Tests

```bash
pytest tests/ -v
```

Tests cover: email validation, row validation, CSV header validation,
deduplication store (mark/check/count/idempotency/case-insensitivity),
and CSV parser (invalid rows, duplicates, missing files).

---

## 🚨 Troubleshooting

| Error                             | Fix                                                       |
|-----------------------------------|-----------------------------------------------------------|
| `SMTPAuthenticationError`         | Generate a fresh Gmail App Password; enable 2FA first     |
| `Template file not found`         | Check `TEMPLATE_FILE` in `.env` points to the right path  |
| `Resume file not found`           | Pass the correct `--resume` path                          |
| `CSV is missing required columns` | Ensure CSV headers match exactly (or close to) the spec   |
| Emails landing in spam            | See anti-spam tips above; warm up slowly                  |
| All emails skipped                | Run `python main.py --status` to inspect the dedup DB     |

---

## 📄 License

MIT — free to use, modify, and distribute.
