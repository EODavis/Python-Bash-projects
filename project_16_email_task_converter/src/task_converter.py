"""
task_converter.py
=================
Project 16: Email-to-Task Converter  — Theme B: Email Automation
-----------------------------------------------------------------
Connects to an IMAP inbox, scans emails for action signals, extracts
structured tasks, and appends them to a local Markdown task file.

Features:
  - Task detector   : keyword patterns (TODO, ACTION, TASK, DEADLINE, FOLLOW UP…)
  - Date extractor  : pulls due dates from natural language ("by Friday", "before March 15")
  - Priority scorer : urgency keywords → critical / high / medium / low
  - Dedup guard     : tracks processed message IDs — never double-extracts
  - Markdown writer : appends tasks to a .md file with checkboxes, priority, source
  - CSV export      : parallel CSV of all extracted tasks
  - Dry-run mode    : prints tasks without writing files
  - Stats summary   : emails scanned, tasks extracted, dates found

Task signal patterns (any triggers extraction):
    TODO, TO DO, ACTION REQUIRED, ACTION ITEM, FOLLOW UP, FOLLOW-UP,
    PLEASE, KINDLY, TASK, DEADLINE, BY [DATE], BEFORE [DATE], DUE [DATE]

Usage:
    python src/task_converter.py --dry-run \\
        --user you@gmail.com --password "app_pass"

    python src/task_converter.py \\
        --user you@gmail.com --password "app_pass" \\
        --output output/tasks.md --since 2026-03-01
"""

import csv
import email
import email.header
import imaplib
import json
import os
import re
import sys
import argparse
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path


# ─── CONSTANTS ───────────────────────────────────────────────────────────────

GMAIL_IMAP_HOST = "imap.gmail.com"
GMAIL_IMAP_PORT = 993
PROCESSED_STORE = ".processed_ids.json"
TASK_CSV        = "tasks.csv"
CSV_FIELDS      = ["extracted_at", "msg_id", "email_date", "sender",
                   "subject", "task_text", "priority", "due_date", "source_line"]

# Task signal keywords
TASK_SIGNALS = re.compile(
    r"\b(todo|to[\s\-]do|action\s+required|action\s+item|follow[\s\-]up|"
    r"please\s+\w+|kindly\s+\w+|task:|deadline|by\s+(monday|tuesday|wednesday|"
    r"thursday|friday|saturday|sunday|eod|eow|tomorrow|next\s+week)|"
    r"due\s+(date|by|on)|before\s+(monday|tuesday|wednesday|thursday|friday|"
    r"saturday|sunday|tomorrow)|urgent|asap|high\s+priority)\b",
    re.IGNORECASE
)

# Priority keywords
PRIORITY_MAP = [
    (re.compile(r"\b(critical|asap|immediately|urgent|emergency)\b", re.I), "critical"),
    (re.compile(r"\b(high\s+priority|important|crucial|must)\b",    re.I), "high"),
    (re.compile(r"\b(please|kindly|follow[\s\-]up|action\s+required)\b", re.I), "medium"),
]

# Date patterns in natural language
DATE_PATTERNS = [
    # Explicit: March 15, 15 March, 2026-03-15, 15/03/2026
    (re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b"),          "dmy_slash"),
    (re.compile(r"\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b"),          "iso"),
    (re.compile(
        r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
        r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?"
        r"(?:[,\s]+(\d{4}))?",
        re.IGNORECASE
    ), "month_day"),
    (re.compile(
        r"\b(\d{1,2})(?:st|nd|rd|th)?\s+"
        r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|"
        r"jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|"
        r"nov(?:ember)?|dec(?:ember)?)(?:[,\s]+(\d{4}))?",
        re.IGNORECASE
    ), "day_month"),
    # Relative
    (re.compile(r"\b(today)\b",       re.I), "relative"),
    (re.compile(r"\b(tomorrow)\b",    re.I), "relative"),
    (re.compile(r"\b(eod)\b",         re.I), "relative"),
    (re.compile(r"\b(eow)\b",         re.I), "relative"),
    (re.compile(r"\b(next\s+week)\b", re.I), "relative"),
    (re.compile(r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
                re.I), "weekday"),
]

MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}

WEEKDAY_MAP = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


# ─── DATE EXTRACTION ─────────────────────────────────────────────────────────

def next_weekday(today: date, weekday: int) -> date:
    days_ahead = weekday - today.weekday()
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


def extract_due_date(text: str, today: date = None) -> str:
    """
    Attempt to extract a due date from natural language text.
    Returns ISO date string or "" if none found.
    """
    today = today or date.today()

    for pattern, ptype in DATE_PATTERNS:
        m = pattern.search(text)
        if not m:
            continue
        try:
            if ptype == "iso":
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return str(date(y, mo, d))
            if ptype == "dmy_slash":
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
                return str(date(y, mo, d))
            if ptype == "month_day":
                month = MONTH_MAP.get(m.group(1)[:3].lower(), 0)
                day   = int(m.group(2))
                year  = int(m.group(3)) if m.group(3) else today.year
                if month:
                    return str(date(year, month, day))
            if ptype == "day_month":
                day   = int(m.group(1))
                month = MONTH_MAP.get(m.group(2)[:3].lower(), 0)
                year  = int(m.group(3)) if m.group(3) else today.year
                if month:
                    return str(date(year, month, day))
            if ptype == "relative":
                word = m.group(1).lower()
                if word in ("today",):
                    return str(today)
                if word in ("tomorrow", "eod"):
                    return str(today + timedelta(days=1))
                if word == "eow":
                    return str(next_weekday(today, 4))   # Friday
                if word == "next week":
                    return str(today + timedelta(weeks=1))
            if ptype == "weekday":
                wd = WEEKDAY_MAP.get(m.group(1).lower())
                if wd is not None:
                    return str(next_weekday(today, wd))
        except (ValueError, TypeError):
            continue
    return ""


# ─── PRIORITY SCORING ────────────────────────────────────────────────────────

def score_priority(text: str) -> str:
    for pattern, level in PRIORITY_MAP:
        if pattern.search(text):
            return level
    return "low"


# ─── TASK EXTRACTION ─────────────────────────────────────────────────────────

def extract_tasks_from_text(text: str, today: date = None) -> list[dict]:
    """
    Scan each line of text. If a line contains a task signal,
    extract it as a task dict.
    """
    today  = today or date.today()
    tasks  = []
    lines  = text.splitlines()

    for line in lines:
        line_stripped = line.strip()
        if len(line_stripped) < 5:
            continue
        if not TASK_SIGNALS.search(line_stripped):
            continue

        due      = extract_due_date(line_stripped, today)
        priority = score_priority(line_stripped)

        # Clean up the task text
        task_text = re.sub(r"\s+", " ", line_stripped).strip()
        task_text = task_text[:300]   # cap length

        tasks.append({
            "task_text":   task_text,
            "priority":    priority,
            "due_date":    due,
            "source_line": line_stripped[:120],
        })

    return tasks


# ─── EMAIL UTILS ─────────────────────────────────────────────────────────────

def decode_hdr(raw) -> str:
    if raw is None:
        return ""
    parts = email.header.decode_header(raw)
    out   = []
    for chunk, charset in parts:
        if isinstance(chunk, bytes):
            out.append(chunk.decode(charset or "utf-8", errors="replace"))
        else:
            out.append(str(chunk))
    return "".join(out)


def get_plain_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    return payload.decode(
                        part.get_content_charset() or "utf-8", errors="replace"
                    )
        return ""
    payload = msg.get_payload(decode=True)
    return payload.decode(
        msg.get_content_charset() or "utf-8", errors="replace"
    ) if payload else ""


def get_email_date(msg) -> date:
    try:
        return parsedate_to_datetime(msg.get("Date", "")).date()
    except Exception:
        return date.today()


# ─── PROCESSED STORE ─────────────────────────────────────────────────────────

def load_processed(path: Path) -> set:
    if path.exists():
        try:
            return set(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            return set()
    return set()


def save_processed(ids: set, path: Path):
    path.write_text(json.dumps(sorted(ids), indent=2), encoding="utf-8")


# ─── MARKDOWN WRITER ─────────────────────────────────────────────────────────

PRIORITY_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}


def format_task_md(task: dict, sender: str, subject: str, email_date) -> str:
    emoji    = PRIORITY_EMOJI.get(task["priority"], "⚪")
    due_str  = f" · 📅 {task['due_date']}" if task["due_date"] else ""
    src_str  = f" · 📧 {sender[:40]}"
    return (
        f"- [ ] {emoji} **[{task['priority'].upper()}]** {task['task_text']}"
        f"{due_str}{src_str}\n"
        f"  > *Subject: {subject[:80]} · {email_date}*\n"
    )


def append_to_markdown(tasks_with_meta: list[dict], md_path: Path):
    """Append extracted tasks to the markdown file."""
    md_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not md_path.exists()

    with open(md_path, "a", encoding="utf-8") as f:
        if is_new:
            f.write("# 📋 Email Task Inbox\n\n")
            f.write("*Auto-generated by task_converter.py*\n\n---\n\n")

        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        f.write(f"\n## Extracted {now}\n\n")
        for item in tasks_with_meta:
            f.write(format_task_md(
                item["task"], item["sender"],
                item["subject"], item["email_date"]
            ))
        f.write("\n")


# ─── CSV WRITER ──────────────────────────────────────────────────────────────

def init_csv(path: Path):
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=CSV_FIELDS).writeheader()


def append_csv(path: Path, rows: list[dict]):
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writerows(rows)


# ─── MAIN PIPELINE ───────────────────────────────────────────────────────────

def run_converter(user: str, password: str,
                  output_md: Path,
                  output_dir: Path  = Path("output"),
                  folder: str       = "INBOX",
                  since: str        = "",
                  dry_run: bool     = True,
                  max_emails: int   = 100,
                  imap_host: str    = GMAIL_IMAP_HOST,
                  imap_port: int    = GMAIL_IMAP_PORT) -> dict:

    stats = {"scanned": 0, "with_tasks": 0, "tasks_extracted": 0, "errors": []}

    store_path  = output_dir / PROCESSED_STORE
    csv_path    = output_dir / TASK_CSV
    processed   = load_processed(store_path)

    print(f"\n  📬 Email→Task Converter — {'DRY RUN' if dry_run else 'LIVE'}\n")

    try:
        conn = imaplib.IMAP4_SSL(imap_host, imap_port)
        conn.login(user, password)
    except Exception as e:
        print(f"  ✗  Connection failed: {e}")
        return stats

    conn.select(f'"INBOX"')
    criteria = "ALL"
    if since:
        try:
            d = datetime.strptime(since, "%Y-%m-%d")
            criteria = f'SINCE "{d.strftime("%d-%b-%Y")}"'
        except ValueError:
            pass

    _, data = conn.search(None, criteria)
    msg_ids = data[0].split()[-max_emails:] if data[0] else []
    print(f"  📨 {len(msg_ids)} emails to scan\n")

    if not dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        init_csv(csv_path)

    all_tasks_with_meta = []

    for msg_id in msg_ids:
        stats["scanned"] += 1
        try:
            _, raw = conn.fetch(msg_id, "(RFC822)")
            if not raw or raw[0] is None:
                continue
            msg = email.message_from_bytes(raw[0][1])

            msg_id_str  = msg.get("Message-ID", msg_id.decode())
            if msg_id_str in processed:
                continue

            sender      = decode_hdr(msg.get("From", ""))
            subject     = decode_hdr(msg.get("Subject", ""))
            email_date  = get_email_date(msg)
            body        = get_plain_body(msg)
            full_text   = f"{subject}\n{body}"

            tasks = extract_tasks_from_text(full_text, today=email_date)
            if not tasks:
                continue

            stats["with_tasks"]      += 1
            stats["tasks_extracted"] += len(tasks)

            print(f"  ✉️  {sender[:45]}")
            print(f"     Subject : {subject[:60]}")
            print(f"     Tasks   : {len(tasks)}")
            for t in tasks:
                due   = f"  due {t['due_date']}" if t["due_date"] else ""
                print(f"     {PRIORITY_EMOJI[t['priority']]} [{t['priority'].upper()}]{due}")
                print(f"       {t['task_text'][:80]}")
            print()

            meta_tasks = [
                {"task": t, "sender": sender, "subject": subject,
                 "email_date": email_date, "msg_id": msg_id_str}
                for t in tasks
            ]
            all_tasks_with_meta.extend(meta_tasks)

            if not dry_run:
                processed.add(msg_id_str)
                csv_rows = [{
                    "extracted_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "msg_id":       msg_id_str,
                    "email_date":   str(email_date),
                    "sender":       sender,
                    "subject":      subject,
                    "task_text":    t["task_text"],
                    "priority":     t["priority"],
                    "due_date":     t["due_date"],
                    "source_line":  t["source_line"],
                } for t in tasks]
                append_csv(csv_path, csv_rows)

        except Exception as e:
            stats["errors"].append(str(e))

    conn.logout()

    if all_tasks_with_meta and not dry_run:
        append_to_markdown(all_tasks_with_meta, output_md)
        save_processed(processed, store_path)
        print(f"  📄 Markdown → {output_md}")
        print(f"  📊 CSV      → {csv_path}\n")

    print(f"  {'='*50}")
    print(f"  📊 Summary")
    print(f"     Emails scanned   : {stats['scanned']}")
    print(f"     Emails with tasks: {stats['with_tasks']}")
    print(f"     Tasks extracted  : {stats['tasks_extracted']}")
    print(f"  {'='*50}\n")
    return stats


# ─── CLI ─────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Email-to-Task Converter")
    p.add_argument("--user",     required=True)
    p.add_argument("--password", default="")
    p.add_argument("--output",   default="output/tasks.md",
                   help="Markdown output file (default: output/tasks.md)")
    p.add_argument("--since",    default="", help="Start date YYYY-MM-DD")
    p.add_argument("--folder",   default="INBOX")
    p.add_argument("--dry-run",  action="store_true", default=False)
    p.add_argument("--max",      type=int, default=100)
    return p.parse_args()


def main():
    args     = parse_args()
    password = args.password or os.environ.get("IMAP_PASSWORD", "")
    if not password:
        print("  ✗  No password. Use --password or IMAP_PASSWORD env.")
        sys.exit(1)

    output_md  = Path(args.output)
    output_dir = output_md.parent

    run_converter(
        user       = args.user,
        password   = password,
        output_md  = output_md,
        output_dir = output_dir,
        folder     = args.folder,
        since      = args.since,
        dry_run    = args.dry_run,
        max_emails = args.max,
    )


if __name__ == "__main__":
    main()
