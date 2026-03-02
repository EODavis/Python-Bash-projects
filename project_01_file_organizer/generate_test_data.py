"""
generate_test_data.py
=====================
Drops synthetic messy files into test_data/ folders for:
  - Project 01: File Organizer Bot
  - Project 02: Duplicate File Finder

Run: python generate_test_data.py
"""

import os
import random
import shutil
import hashlib
from pathlib import Path
from datetime import datetime, timedelta

# ─── CONFIG ───────────────────────────────────────────────────────────────────
P01_DIR = Path("project_01_file_organizer/test_data")
P02_DIR = Path("project_02_duplicate_finder/test_data")

RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# ─── SYNTHETIC CONTENT POOLS ─────────────────────────────────────────────────

INVOICE_CONTENT = [
    "Invoice #1042\nVendor: TechNova Ltd\nAmount: ₦85,000\nDate: 2024-11-12\nStatus: Unpaid",
    "Invoice #2091\nVendor: DataHub Inc\nAmount: ₦120,500\nDate: 2025-01-03\nStatus: Paid",
    "Invoice #3017\nVendor: CloudServe NG\nAmount: ₦47,200\nDate: 2025-02-18\nStatus: Pending",
]

REPORT_CONTENT = [
    "Q3 Sales Report\n===============\nTotal Revenue: ₦4,200,000\nUnits Sold: 312\nTop Region: Lagos\nGrowth: +14%",
    "Monthly Analytics\n=================\nActive Users: 8,421\nNew Signups: 1,203\nChurn Rate: 2.1%\nNPS Score: 67",
    "Performance Review\n==================\nProject: DSN Pipeline\nStatus: On Track\nDeliverables: 7/10\nNext Milestone: March 2025",
]

CODE_CONTENT = [
    "# data_cleaner.py\nimport pandas as pd\n\ndef clean(df):\n    return df.dropna().reset_index(drop=True)\n",
    "#!/bin/bash\n# backup.sh\nDATE=$(date +%Y%m%d)\ntar -czf backup_$DATE.tar.gz ./data\necho 'Backup done'",
    "# model.py\nfrom sklearn.linear_model import LogisticRegression\nclf = LogisticRegression()\n# TODO: fit model\n",
]

NOTE_CONTENT = [
    "Meeting Notes - 2025-01-15\nAttendees: Davis, Tunde, Amaka\nAction Items:\n- Finish ETL pipeline by Friday\n- Review PR #24\n- Send weekly report",
    "Ideas Dump\n==========\n- Build language corpus for Igbo\n- Automate soccer fixture alerts\n- Portfolio OS system design",
    "TODO:\n[ ] Set up Docker container\n[ ] Write unit tests for parser\n[ ] Push to GitHub\n[x] Design DB schema",
]

IMAGE_PLACEHOLDER = "<<SYNTHETIC_IMAGE_BINARY_PLACEHOLDER>>\nFile: photo_{}\nCamera: Synthetic Cam 3000\nResolution: 1920x1080\nDate: {}"
MUSIC_PLACEHOLDER  = "<<SYNTHETIC_AUDIO_PLACEHOLDER>>\nTrack: {}\nArtist: Synthetic Artist\nDuration: 3:42\nBitrate: 320kbps"
VIDEO_PLACEHOLDER  = "<<SYNTHETIC_VIDEO_PLACEHOLDER>>\nTitle: {}\nResolution: 1080p\nDuration: 00:04:22"

# ─── FILE SPEC: (filename, content) ──────────────────────────────────────────

def make_p01_files():
    """Messy, unsorted pile — all extensions jumbled in one folder."""
    files = [
        # Documents
        ("invoice_nov2024.txt",        INVOICE_CONTENT[0]),
        ("invoice_jan2025.txt",        INVOICE_CONTENT[1]),
        ("invoice_feb2025.txt",        INVOICE_CONTENT[2]),
        ("q3_sales_report.txt",        REPORT_CONTENT[0]),
        ("monthly_analytics.txt",      REPORT_CONTENT[1]),
        ("performance_review.txt",     REPORT_CONTENT[2]),
        ("meeting_notes_jan15.txt",    NOTE_CONTENT[0]),
        ("ideas_dump.md",              NOTE_CONTENT[1]),
        ("todo_list.md",               NOTE_CONTENT[2]),
        # Code
        ("data_cleaner.py",            CODE_CONTENT[0]),
        ("backup.sh",                  CODE_CONTENT[1]),
        ("model_draft.py",             CODE_CONTENT[2]),
        # Images (placeholder)
        ("photo_lagos_trip.jpg",       IMAGE_PLACEHOLDER.format("lagos_trip", "2024-12-25")),
        ("screenshot_dashboard.png",   IMAGE_PLACEHOLDER.format("dashboard",  "2025-01-10")),
        ("profile_pic_v2.jpg",         IMAGE_PLACEHOLDER.format("profile",    "2025-02-01")),
        ("logo_draft.png",             IMAGE_PLACEHOLDER.format("logo",       "2025-01-28")),
        # Audio (placeholder)
        ("afrobeats_mix.mp3",          MUSIC_PLACEHOLDER.format("Afrobeats Mix Vol.3")),
        ("podcast_ep12.mp3",           MUSIC_PLACEHOLDER.format("Data Science Podcast Ep.12")),
        # Video (placeholder)
        ("demo_walkthrough.mp4",       VIDEO_PLACEHOLDER.format("Product Demo Walkthrough")),
        ("intro_animation.mp4",        VIDEO_PLACEHOLDER.format("Intro Animation v1")),
        # Spreadsheets
        ("transactions_q1.csv",        "date,description,amount_ngn,category\n2025-01-05,Airtime,500,Utilities\n2025-01-07,Groceries,12000,Food\n2025-01-10,Uber,3200,Transport"),
        ("contacts_export.csv",        "name,email,phone\nAmaka Obi,amaka@example.com,+2348012345678\nTunde Bello,tunde@example.com,+2348098765432"),
        # Archives
        ("old_project_backup.zip",     "<<ZIP_PLACEHOLDER>>\nContents: 47 files\nOriginal Size: 14MB\nDate: 2024-10-01"),
        ("assets_bundle.tar.gz",       "<<TAR_PLACEHOLDER>>\nContents: images/, fonts/, icons/\nDate: 2024-11-15"),
        # Misc
        ("random_notes.txt",           "Random thoughts at 2am.\nCheck the pipeline logs.\nAsk about the Hausa corpus."),
        ("unnamed_file",               "This file has no extension. Classic chaos."),
        ("   spaced out name.txt",     "This filename has leading spaces. A nightmare."),
        ("DUPLICATE_TEST.txt",         "This content is identical to another file."),
        ("duplicate_test_copy.txt",    "This content is identical to another file."),  # intentional duplicate
        ("old_report_2023.txt",        REPORT_CONTENT[0]),  # same content as q3_sales_report.txt
    ]
    return files


def make_p02_files():
    """Files with intentional duplicates — same content, different names/locations."""
    base_content_a = "Account Summary\nHolder: Davis A.\nBalance: ₦1,240,000\nLast Transaction: 2025-02-20"
    base_content_b = "Project Plan v1\nSprint 1: Data ingestion\nSprint 2: Feature engineering\nSprint 3: Model training"
    base_content_c = CODE_CONTENT[0]
    image_dup      = IMAGE_PLACEHOLDER.format("beach_vacation", "2025-01-01")

    files = [
        # Group A: exact duplicates
        ("account_summary.txt",         base_content_a),
        ("account_summary_copy.txt",    base_content_a),           # dup of above
        ("account_backup_jan.txt",      base_content_a),           # dup of above
        # Group B: exact duplicates
        ("project_plan.txt",            base_content_b),
        ("project_plan_v1_final.txt",   base_content_b),           # dup
        ("project_plan_BACKUP.txt",     base_content_b),           # dup
        # Group C: code duplicates
        ("data_cleaner.py",             base_content_c),
        ("data_cleaner_old.py",         base_content_c),           # dup
        # Group D: image duplicates
        ("beach_photo.jpg",             image_dup),
        ("beach_photo_copy.jpg",        image_dup),                # dup
        ("IMG_00492.jpg",               image_dup),                # dup
        # Unique files (no duplicates)
        ("unique_report.txt",           REPORT_CONTENT[2]),
        ("unique_notes.md",             NOTE_CONTENT[1]),
        ("unique_script.sh",            CODE_CONTENT[1]),
        ("transactions.csv",            "date,amount\n2025-01-01,5000\n2025-01-02,8200"),
    ]

    # Add subfolder duplicates (cross-folder detection challenge)
    subfolders = {
        "subfolder_a": [
            ("report_draft.txt",  REPORT_CONTENT[1]),
            ("notes.txt",         NOTE_CONTENT[0]),
        ],
        "subfolder_b": [
            ("report_draft.txt",  REPORT_CONTENT[1]),   # cross-folder dup
            ("extra_notes.txt",   NOTE_CONTENT[0]),     # cross-folder dup
        ],
    }
    return files, subfolders


# ─── WRITER ──────────────────────────────────────────────────────────────────

def write_files(directory: Path, files: list):
    directory.mkdir(parents=True, exist_ok=True)
    count = 0
    for filename, content in files:
        filepath = directory / filename
        filepath.write_text(content, encoding="utf-8")
        count += 1
    return count


def write_p02(directory: Path):
    files, subfolders = make_p02_files()
    count = write_files(directory, files)
    for subfolder_name, sub_files in subfolders.items():
        count += write_files(directory / subfolder_name, sub_files)
    return count


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    base = Path(__file__).parent
    p01 = base / P01_DIR
    p02 = base / P02_DIR

    print("🔧 Generating synthetic test data...\n")

    n1 = write_files(p01, make_p01_files())
    print(f"  ✅ Project 01 — {n1} files written to: {p01}")

    n2 = write_p02(p02)
    print(f"  ✅ Project 02 — {n2} files written to: {p02}")

    print(f"\n🎉 Done! Total files generated: {n1 + n2}")
    print("   Run the organizer and duplicate finder on these now.\n")


if __name__ == "__main__":
    main()
