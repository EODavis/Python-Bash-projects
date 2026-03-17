"""
bulk_sender.py
==============
Project 15: Bulk Email Sender with Personalisation  — Theme B: Email Automation
---------------------------------------------------------------------------------
Reads a contacts CSV, renders a personalised email per recipient using
{{variable}} templates, and sends via SMTP with rate limiting and a
full delivery report.

Features:
  - Contacts CSV      : any columns become template variables automatically
  - Template engine   : {{first_name}}, {{company}}, any custom column
  - HTML + plain-text : dual-part MIME email for all clients
  - Attachment support: one optional shared attachment for all recipients
  - Per-row attachment: optional column pointing to a file path per contact
  - Rate limiter      : configurable delay between sends (default 1s)
  - Dry-run mode      : renders all emails, saves previews, sends nothing
  - Delivery report   : CSV — recipient, status, timestamp, error message
  - Resume support    : skips already-sent recipients (from previous report)
  - Preview mode      : render + save first N emails without sending

Usage:
    # Dry run — render all, save previews to output/previews/
    python src/bulk_sender.py --contacts test_data/contacts.csv \\
        --template templates/outreach.txt --dry-run

    # Send live
    python src/bulk_sender.py --contacts test_data/contacts.csv \\
        --template templates/outreach.txt \\
        --from sender@gmail.com --password "app_pass" --delay 2

    # Preview first 3 only
    python src/bulk_sender.py --contacts test_data/contacts.csv \\
        --template templates/outreach.txt --preview 3

    # With shared attachment
    python src/bulk_sender.py --contacts test_data/contacts.csv \\
        --template templates/outreach.txt --attachment report.pdf --dry-run
"""

import csv
import email.mime.application
import email.mime.multipart
import email.mime.text
import json
import os
import re
import smtplib
import sys
import time
import argparse
from datetime import datetime
from email.utils import formatdate, make_msgid
from pathlib import Path


# ─── CONSTANTS ───────────────────────────────────────────────────────────────

GMAIL_SMTP_HOST  = "smtp.gmail.com"
GMAIL_SMTP_PORT  = 587
REPORT_FILENAME  = "delivery_report.csv"
REPORT_FIELDS    = ["email", "first_name", "last_name", "status",
                    "timestamp", "error", "subject"]
PREVIEW_DIR      = "previews"


# ─── CONTACTS LOADER ─────────────────────────────────────────────────────────

def load_contacts(filepath: Path) -> list[dict]:
    """
    Load contacts CSV. Every column becomes a template variable.
    Required: 'email' column. All others are optional.
    Strips whitespace from all values.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Contacts file not found: {filepath}")

    with open(filepath, encoding="utf-8", newline="") as f:
        reader   = csv.DictReader(f)
        contacts = []
        for i, row in enumerate(reader, start=2):   # row 1 = header
            contact = {k.strip().lower(): v.strip() for k, v in row.items()}
            if not contact.get("email"):
                print(f"  ⚠️  Row {i}: missing email — skipped")
                continue
            if not _valid_email(contact["email"]):
                print(f"  ⚠️  Row {i}: invalid email '{contact['email']}' — skipped")
                continue
            contacts.append(contact)
    return contacts


def _valid_email(addr: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", addr))


# ─── TEMPLATE ENGINE ─────────────────────────────────────────────────────────

def load_template(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Template not found: {path}")
    return path.read_text(encoding="utf-8")


def extract_subject(template_text: str) -> tuple[str, str]:
    """
    If template begins with 'Subject: ...\n\n', splits it off.
    Returns (subject, body).
    """
    lines = template_text.splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip()
        body    = "\n".join(lines[2:]) if len(lines) > 2 else ""
        return subject, body
    return "(no subject)", template_text


def render(template_text: str, context: dict) -> str:
    """Replace {{key}} with context[key]. Unknown keys left as-is."""
    def replacer(m):
        key = m.group(1).strip().lower()
        return str(context.get(key, m.group(0)))
    return re.sub(r"\{\{(.+?)\}\}", replacer, template_text)


def build_context(contact: dict) -> dict:
    """
    Merge contact dict into a context, adding derived helpers.
    All keys lowercased for consistent template access.
    """
    ctx = dict(contact)

    # Derive first_name / last_name if not explicit
    if "first_name" not in ctx and "name" in ctx:
        parts = ctx["name"].split()
        ctx["first_name"] = parts[0] if parts else ""
        ctx["last_name"]  = " ".join(parts[1:]) if len(parts) > 1 else ""

    ctx.setdefault("first_name", ctx.get("email", "").split("@")[0])
    ctx.setdefault("last_name",  "")
    ctx.setdefault("full_name",  f"{ctx['first_name']} {ctx['last_name']}".strip())
    ctx["reply_date"] = datetime.now().strftime("%d %B %Y")
    ctx["year"]       = str(datetime.now().year)

    return ctx


# ─── EMAIL BUILDER ────────────────────────────────────────────────────────────

def build_html_body(plain_body: str) -> str:
    """Wrap plain text in minimal HTML for HTML part of MIME."""
    paragraphs = "".join(
        f"<p style='margin:0 0 10px;line-height:1.6'>{line}</p>"
        if line.strip() else "<br>"
        for line in plain_body.splitlines()
    )
    return f"""<!DOCTYPE html><html><body
      style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;
             font-size:14px;color:#222;max-width:600px;margin:0 auto;padding:20px'>
      {paragraphs}
    </body></html>"""


def build_message(subject: str, plain_body: str,
                  from_addr: str, to_addr: str,
                  attachment_path: Path | None = None) -> email.mime.multipart.MIMEMultipart:
    """Build a dual-part MIME email with optional attachment."""
    msg = email.mime.multipart.MIMEMultipart("mixed")
    msg["From"]       = from_addr
    msg["To"]         = to_addr
    msg["Subject"]    = subject
    msg["Date"]       = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()

    # Text + HTML alternative parts
    alt = email.mime.multipart.MIMEMultipart("alternative")
    alt.attach(email.mime.text.MIMEText(plain_body,          "plain", "utf-8"))
    alt.attach(email.mime.text.MIMEText(build_html_body(plain_body), "html",  "utf-8"))
    msg.attach(alt)

    # Attachment
    if attachment_path and attachment_path.exists():
        data = attachment_path.read_bytes()
        part = email.mime.application.MIMEApplication(data,
                                                       Name=attachment_path.name)
        part["Content-Disposition"] = f'attachment; filename="{attachment_path.name}"'
        msg.attach(part)

    return msg


# ─── SMTP ─────────────────────────────────────────────────────────────────────

def smtp_connect(from_addr: str, password: str,
                 host: str = GMAIL_SMTP_HOST,
                 port: int = GMAIL_SMTP_PORT) -> smtplib.SMTP:
    server = smtplib.SMTP(host, port, timeout=15)
    server.ehlo()
    server.starttls()
    server.login(from_addr, password)
    return server


def send_one(server: smtplib.SMTP,
             msg: email.mime.multipart.MIMEMultipart,
             from_addr: str, to_addr: str) -> tuple[bool, str]:
    """Send one message. Returns (success, error_message)."""
    try:
        server.sendmail(from_addr, [to_addr], msg.as_string())
        return True, ""
    except smtplib.SMTPRecipientsRefused:
        return False, "Recipient refused"
    except smtplib.SMTPException as e:
        return False, str(e)


# ─── DELIVERY REPORT ─────────────────────────────────────────────────────────

def init_report(path: Path):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=REPORT_FIELDS).writeheader()


def append_report(path: Path, row: dict):
    with open(path, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=REPORT_FIELDS,
                       extrasaction="ignore").writerow(row)


def load_already_sent(report_path: Path) -> set[str]:
    """Return set of emails already marked 'sent' in report."""
    sent = set()
    if not report_path.exists():
        return sent
    with open(report_path, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("status") == "sent":
                sent.add(row["email"].lower())
    return sent


# ─── PREVIEW SAVER ────────────────────────────────────────────────────────────

def save_preview(output_dir: Path, contact: dict,
                 subject: str, body: str, index: int):
    preview_dir = output_dir / PREVIEW_DIR
    preview_dir.mkdir(parents=True, exist_ok=True)
    slug  = re.sub(r"[^a-z0-9]", "_", contact["email"].lower())[:30]
    path  = preview_dir / f"{index:03d}_{slug}.txt"
    path.write_text(
        f"TO: {contact['email']}\nSUBJECT: {subject}\n\n{body}",
        encoding="utf-8"
    )
    return path


# ─── MAIN PIPELINE ────────────────────────────────────────────────────────────

def run_bulk_sender(contacts_path: Path,
                    template_path: Path,
                    from_addr: str      = "",
                    password: str       = "",
                    output_dir: Path    = Path("output"),
                    attachment: Path | None = None,
                    dry_run: bool       = True,
                    preview_n: int      = 0,
                    delay_sec: float    = 1.0,
                    smtp_host: str      = GMAIL_SMTP_HOST,
                    smtp_port: int      = GMAIL_SMTP_PORT,
                    resume: bool        = True) -> dict:

    stats = {"total": 0, "sent": 0, "skipped": 0, "failed": 0, "previewed": 0}

    contacts     = load_contacts(contacts_path)
    template_raw = load_template(template_path)
    subject_tpl, body_tpl = extract_subject(template_raw)

    report_path  = output_dir / REPORT_FILENAME
    output_dir.mkdir(parents=True, exist_ok=True)

    already_sent: set[str] = set()
    if resume and not dry_run:
        already_sent = load_already_sent(report_path)
        if already_sent:
            print(f"  ↩️  Resuming — {len(already_sent)} already sent, skipping.\n")

    if not dry_run:
        init_report(report_path)

    mode = "DRY-RUN" if dry_run else ("PREVIEW" if preview_n else "LIVE")
    print(f"\n  📧 Bulk Sender — {mode}")
    print(f"  Contacts : {len(contacts)}")
    print(f"  Template : {template_path.name}\n")

    server = None
    if not dry_run and not preview_n and from_addr and password:
        try:
            server = smtp_connect(from_addr, password, smtp_host, smtp_port)
            print(f"  ✓  SMTP connected as {from_addr}\n")
        except Exception as e:
            print(f"  ✗  SMTP connection failed: {e}")
            return stats

    stats["total"] = len(contacts)

    for i, contact in enumerate(contacts, start=1):
        email_addr = contact["email"].lower()

        # Resume skip
        if email_addr in already_sent:
            stats["skipped"] += 1
            continue

        ctx     = build_context(contact)
        subject = render(subject_tpl, ctx)
        body    = render(body_tpl, ctx)

        # Per-row attachment override
        row_attachment = attachment
        if contact.get("attachment_path"):
            p = Path(contact["attachment_path"])
            if p.exists():
                row_attachment = p

        print(f"  [{i:>3}/{len(contacts)}] {email_addr:<35} {subject[:35]}")

        # Preview mode
        if preview_n and i <= preview_n:
            path = save_preview(output_dir, contact, subject, body, i)
            print(f"           💾 Preview → {path}")
            stats["previewed"] += 1
            if i == preview_n:
                print(f"\n  Previewed {preview_n} emails. Stopping.\n")
                break
            continue

        if dry_run:
            save_preview(output_dir, contact, subject, body, i)
            stats["sent"] += 1   # count as "would send"
            continue

        # Live send
        if server is None:
            stats["failed"] += 1
            continue
        msg     = build_message(subject, body, from_addr, email_addr, row_attachment)
        success, error = send_one(server, msg, from_addr, email_addr)

        status = "sent" if success else "failed"
        if success:
            stats["sent"] += 1
        else:
            stats["failed"] += 1
            print(f"           ✗ Failed: {error}")

        append_report(report_path, {
            "email":      email_addr,
            "first_name": ctx.get("first_name", ""),
            "last_name":  ctx.get("last_name",  ""),
            "status":     status,
            "timestamp":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error":      error,
            "subject":    subject,
        })

        if delay_sec > 0 and i < len(contacts):
            time.sleep(delay_sec)

    if server:
        server.quit()

    print(f"\n  {'='*50}")
    print(f"  📊 Summary [{mode}]")
    print(f"     Total contacts  : {stats['total']}")
    if dry_run:
        print(f"     Would send      : {stats['sent']}")
    else:
        print(f"     Sent            : {stats['sent']}")
        print(f"     Failed          : {stats['failed']}")
        print(f"     Skipped         : {stats['skipped']}")
        print(f"     Report          : {report_path}")
    print(f"  {'='*50}\n")
    return stats


# ─── CLI ─────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(
        description="Bulk Email Sender with Personalisation"
    )
    p.add_argument("--contacts",   required=True,  help="Contacts CSV path.")
    p.add_argument("--template",   required=True,  help="Email template .txt path.")
    p.add_argument("--from",       dest="sender",  default="", help="Sender Gmail.")
    p.add_argument("--password",   default="",     help="Gmail App Password.")
    p.add_argument("--attachment", default="",     help="Optional shared attachment path.")
    p.add_argument("--output",     default="output")
    p.add_argument("--dry-run",    action="store_true", default=False)
    p.add_argument("--preview",    type=int, default=0,
                   help="Render + save first N emails only.")
    p.add_argument("--delay",      type=float, default=1.0,
                   help="Seconds between sends (default: 1.0).")
    p.add_argument("--no-resume",  action="store_true", default=False,
                   help="Disable resume — resend to all contacts.")
    return p.parse_args()


def main():
    args     = parse_args()
    password = args.password or os.environ.get("SMTP_PASSWORD", "")

    attachment = Path(args.attachment) if args.attachment else None

    run_bulk_sender(
        contacts_path = Path(args.contacts),
        template_path = Path(args.template),
        from_addr     = args.sender,
        password      = password,
        output_dir    = Path(args.output),
        attachment    = attachment,
        dry_run       = args.dry_run,
        preview_n     = args.preview,
        delay_sec     = args.delay,
        resume        = not args.no_resume,
    )


if __name__ == "__main__":
    main()
