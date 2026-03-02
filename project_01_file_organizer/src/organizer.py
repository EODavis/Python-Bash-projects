"""
organizer.py
============
Project 01: File Organizer Bot
--------------------------------
Watches a target folder and sorts files into categorised subfolders
by extension. Supports:
  - Dry-run mode (preview only, no moves)
  - Live mode  (actually moves files)
  - Move log   (CSV with timestamp, source, destination, status)
  - Summary report (printed + saved to output/)

Usage:
    python src/organizer.py --source test_data --dry-run
    python src/organizer.py --source test_data
    python src/organizer.py --source test_data --log-dir logs
"""

import os
import shutil
import argparse
import csv
import json
from pathlib import Path
from datetime import datetime

# ─── EXTENSION → CATEGORY MAP ────────────────────────────────────────────────

EXTENSION_MAP = {
    # Documents
    ".pdf":  "documents/pdf",
    ".docx": "documents/word",
    ".doc":  "documents/word",
    ".txt":  "documents/text",
    ".md":   "documents/markdown",
    ".rtf":  "documents/text",
    # Spreadsheets
    ".csv":  "spreadsheets",
    ".xlsx": "spreadsheets",
    ".xls":  "spreadsheets",
    # Images
    ".jpg":  "images",
    ".jpeg": "images",
    ".png":  "images",
    ".gif":  "images",
    ".bmp":  "images",
    ".svg":  "images",
    ".webp": "images",
    # Audio
    ".mp3":  "audio",
    ".wav":  "audio",
    ".flac": "audio",
    ".aac":  "audio",
    # Video
    ".mp4":  "video",
    ".mov":  "video",
    ".avi":  "video",
    ".mkv":  "video",
    # Code
    ".py":   "code/python",
    ".sh":   "code/shell",
    ".js":   "code/javascript",
    ".ts":   "code/typescript",
    ".html": "code/web",
    ".css":  "code/web",
    ".sql":  "code/sql",
    ".json": "code/config",
    ".yaml": "code/config",
    ".yml":  "code/config",
    ".toml": "code/config",
    ".env":  "code/config",
    # Archives
    ".zip":  "archives",
    ".gz":   "archives",
    ".tar":  "archives",
    ".rar":  "archives",
    ".7z":   "archives",
}


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def get_category(filepath: Path) -> str:
    """Return the destination subfolder for a given file."""
    ext = filepath.suffix.lower()
    return EXTENSION_MAP.get(ext, "uncategorised")


def sanitise_filename(filepath: Path) -> Path:
    """Strip leading/trailing whitespace from filenames."""
    clean_name = filepath.name.strip()
    if clean_name != filepath.name:
        new_path = filepath.parent / clean_name
        filepath.rename(new_path)
        return new_path
    return filepath


def build_destination(source_dir: Path, category: str, filename: str) -> Path:
    """Build the full destination path, handling filename collisions."""
    dest_folder = source_dir.parent / "organised" / category
    dest_path   = dest_folder / filename

    # Collision handling: append _1, _2, ...
    if dest_path.exists():
        stem   = Path(filename).stem
        suffix = Path(filename).suffix
        counter = 1
        while dest_path.exists():
            dest_path = dest_folder / f"{stem}_{counter}{suffix}"
            counter += 1

    return dest_path


# ─── CORE ENGINE ─────────────────────────────────────────────────────────────

def organise(source_dir: Path, dry_run: bool = True, log_dir: Path = None):
    """
    Main organiser function.

    Args:
        source_dir : Path to the messy folder to organise.
        dry_run    : If True, only preview — no files are moved.
        log_dir    : Where to write the CSV move-log.

    Returns:
        summary dict with counts and log entries.
    """
    source_dir = source_dir.resolve()
    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory not found: {source_dir}")

    run_time   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entries = []
    stats = {
        "total_scanned": 0,
        "moved":         0,
        "skipped":       0,
        "errors":        0,
        "dry_run":       dry_run,
        "run_time":      run_time,
        "categories":    {},
    }

    mode_label = "🔍 DRY RUN" if dry_run else "🚀 LIVE RUN"
    print(f"\n{'='*60}")
    print(f"  File Organizer Bot  |  {mode_label}")
    print(f"  Source : {source_dir}")
    print(f"  Time   : {run_time}")
    print(f"{'='*60}\n")

    # Scan only top-level files (non-recursive) — intentional for Project 01
    files = [f for f in source_dir.iterdir() if f.is_file()]
    stats["total_scanned"] = len(files)

    for filepath in sorted(files):
        # Sanitise whitespace in filename
        filepath = sanitise_filename(filepath)

        category    = get_category(filepath)
        destination = build_destination(source_dir, category, filepath.name)
        status      = ""

        try:
            if not dry_run:
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(filepath), str(destination))
                status = "MOVED"
                stats["moved"] += 1
            else:
                status = "WOULD_MOVE"
                stats["skipped"] += 1

            # Track category counts
            stats["categories"][category] = stats["categories"].get(category, 0) + 1

            action_icon = "→" if not dry_run else "~"
            print(f"  {action_icon}  [{category:<25}]  {filepath.name}")

        except Exception as e:
            status = f"ERROR: {e}"
            stats["errors"] += 1
            print(f"  ✗  ERROR moving {filepath.name}: {e}")

        log_entries.append({
            "timestamp":   run_time,
            "filename":    filepath.name,
            "source":      str(filepath),
            "destination": str(destination),
            "category":    category,
            "status":      status,
            "dry_run":     dry_run,
        })

    # ── SUMMARY ──────────────────────────────────────────────────────────────
    print(f"\n{'─'*60}")
    print(f"  📊 SUMMARY")
    print(f"{'─'*60}")
    print(f"  Files scanned : {stats['total_scanned']}")
    print(f"  {'Moved' if not dry_run else 'Would move':<14}: {stats['moved'] if not dry_run else stats['skipped']}")
    print(f"  Errors        : {stats['errors']}")
    print(f"\n  Categories breakdown:")
    for cat, count in sorted(stats["categories"].items(), key=lambda x: -x[1]):
        print(f"    {cat:<30} {count:>3} file(s)")
    print(f"{'='*60}\n")

    # ── WRITE LOG ────────────────────────────────────────────────────────────
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        timestamp_slug = datetime.now().strftime("%Y%m%d_%H%M%S")
        mode_slug      = "dryrun" if dry_run else "live"
        log_path       = log_dir / f"move_log_{mode_slug}_{timestamp_slug}.csv"

        with open(log_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=log_entries[0].keys())
            writer.writeheader()
            writer.writerows(log_entries)

        print(f"  📄 Log saved → {log_path}\n")
        stats["log_path"] = str(log_path)

    return stats


# ─── CLI ─────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="File Organizer Bot — sorts files into categorised subfolders."
    )
    parser.add_argument(
        "--source",  required=True,
        help="Path to the messy folder to organise."
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Preview moves without actually moving any files."
    )
    parser.add_argument(
        "--log-dir", default="logs",
        help="Directory to write the CSV move-log (default: logs/)."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args   = parse_args()
    source = Path(args.source)
    stats  = organise(
        source_dir=source,
        dry_run=args.dry_run,
        log_dir=Path(args.log_dir),
    )
