"""
duplicate_finder.py
===================
Project 02: Duplicate File Finder
-----------------------------------
Recursively scans a directory, hashes every file (SHA-256),
groups files by identical hash, and produces:
  - A console report with grouped duplicates
  - A CSV report saved to output/
  - An optional --delete flag (with confirmation prompt)

Usage:
    python src/duplicate_finder.py --source test_data
    python src/duplicate_finder.py --source test_data --output output
    python src/duplicate_finder.py --source test_data --delete
"""

import os
import csv
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict


# ─── HASHING ─────────────────────────────────────────────────────────────────

def hash_file(filepath: Path, chunk_size: int = 65536) -> str:
    """
    Compute SHA-256 hash of a file in chunks.
    Using chunks keeps memory usage flat even for large files.
    """
    sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (PermissionError, OSError) as e:
        return f"ERROR:{e}"


# ─── SCANNER ─────────────────────────────────────────────────────────────────

def scan_directory(source_dir: Path) -> dict:
    """
    Walk source_dir recursively, hash every file.

    Returns:
        hash_map : { sha256_hash: [Path, Path, ...] }
    """
    hash_map = defaultdict(list)
    total = 0
    errors = 0

    print(f"\n  🔍 Scanning: {source_dir}")

    for filepath in sorted(source_dir.rglob("*")):
        if not filepath.is_file():
            continue
        total += 1
        file_hash = hash_file(filepath)
        if file_hash.startswith("ERROR:"):
            errors += 1
            print(f"  ✗  Could not hash: {filepath}  ({file_hash})")
        else:
            hash_map[file_hash].append(filepath)

    print(f"  📂 Files scanned: {total}  |  Errors: {errors}")
    return dict(hash_map)


# ─── ANALYSIS ────────────────────────────────────────────────────────────────

def find_duplicates(hash_map: dict) -> dict:
    """Filter hash_map to only groups with 2+ files (actual duplicates)."""
    return {h: paths for h, paths in hash_map.items() if len(paths) > 1}


def compute_wasted_space(duplicates: dict) -> int:
    """
    For each duplicate group, wasted space = (n-1) × file_size.
    (You need 1 copy; the rest are waste.)
    """
    wasted = 0
    for paths in duplicates.values():
        try:
            size = paths[0].stat().st_size
            wasted += size * (len(paths) - 1)
        except OSError:
            pass
    return wasted


def format_bytes(size: int) -> str:
    """Human-readable file size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


# ─── REPORTER ────────────────────────────────────────────────────────────────

def print_report(duplicates: dict, source_dir: Path):
    """Pretty-print the duplicate groups to the console."""
    wasted = compute_wasted_space(duplicates)
    total_dup_files = sum(len(v) for v in duplicates.values())

    print(f"\n{'='*65}")
    print(f"  Duplicate File Finder  |  Report")
    print(f"  Scanned  : {source_dir}")
    print(f"  Run Time : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*65}")
    print(f"  Duplicate groups  : {len(duplicates)}")
    print(f"  Duplicate files   : {total_dup_files}")
    print(f"  Wasted space      : {format_bytes(wasted)}")
    print(f"{'─'*65}\n")

    for group_num, (file_hash, paths) in enumerate(duplicates.items(), start=1):
        try:
            size = paths[0].stat().st_size
        except OSError:
            size = 0

        print(f"  📋 Group {group_num}  [{format_bytes(size)} each  ×{len(paths)} copies]")
        print(f"     Hash: {file_hash[:16]}...")
        for path in paths:
            # Show relative path for cleaner output
            try:
                rel = path.relative_to(source_dir)
            except ValueError:
                rel = path
            print(f"       • {rel}")
        print()

    print(f"{'='*65}\n")


def write_csv_report(duplicates: dict, source_dir: Path, output_dir: Path) -> Path:
    """Write a detailed CSV report of all duplicate groups."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path  = output_dir / f"duplicates_report_{timestamp}.csv"

    rows = []
    for group_num, (file_hash, paths) in enumerate(duplicates.items(), start=1):
        for rank, path in enumerate(paths):
            try:
                size  = path.stat().st_size
                mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            except OSError:
                size, mtime = 0, "unknown"

            rows.append({
                "group":       group_num,
                "hash":        file_hash,
                "rank":        rank + 1,          # 1 = keep (oldest/first), 2+ = potential delete
                "filename":    path.name,
                "full_path":   str(path),
                "size_bytes":  size,
                "size_human":  format_bytes(size),
                "modified":    mtime,
                "suggestion":  "KEEP" if rank == 0 else "REVIEW",
            })

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"  📄 CSV report saved → {csv_path}\n")
    return csv_path


# ─── DELETER (OPTIONAL) ──────────────────────────────────────────────────────

def interactive_delete(duplicates: dict):
    """
    For each duplicate group, keep the first file and prompt to delete the rest.
    Requires explicit confirmation per group.
    """
    print("\n  ⚠️  DELETE MODE — you will be prompted per group.")
    print("  Strategy: KEEP the first file, offer to DELETE the rest.\n")

    deleted_count = 0
    saved_bytes   = 0

    for group_num, (file_hash, paths) in enumerate(duplicates.items(), start=1):
        keeper = paths[0]
        to_delete = paths[1:]

        print(f"  Group {group_num}: keeping → {keeper.name}")
        for dup in to_delete:
            try:
                size = dup.stat().st_size
            except OSError:
                size = 0
            confirm = input(f"    Delete '{dup}' ({format_bytes(size)})? [y/N]: ").strip().lower()
            if confirm == "y":
                dup.unlink()
                deleted_count += 1
                saved_bytes   += size
                print(f"    🗑  Deleted.")
            else:
                print(f"    ⏭  Skipped.")

    print(f"\n  ✅ Done. Deleted {deleted_count} files. Freed {format_bytes(saved_bytes)}.\n")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="Duplicate File Finder — finds and reports duplicate files by SHA-256 hash."
    )
    parser.add_argument(
        "--source",  required=True,
        help="Directory to scan recursively."
    )
    parser.add_argument(
        "--output",  default="output",
        help="Directory to save CSV report (default: output/)."
    )
    parser.add_argument(
        "--delete",  action="store_true", default=False,
        help="Interactively prompt to delete duplicates (keeps first in each group)."
    )
    return parser.parse_args()


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    args       = parse_args()
    source_dir = Path(args.source).resolve()
    output_dir = Path(args.output)

    if not source_dir.exists():
        print(f"  ✗  Source not found: {source_dir}")
        return

    # 1. Scan & hash
    hash_map   = scan_directory(source_dir)

    # 2. Find duplicates
    duplicates = find_duplicates(hash_map)

    if not duplicates:
        print("\n  ✅ No duplicates found. Your folder is clean!\n")
        return

    # 3. Print report
    print_report(duplicates, source_dir)

    # 4. Write CSV
    write_csv_report(duplicates, source_dir, output_dir)

    # 5. Optional delete
    if args.delete:
        interactive_delete(duplicates)


if __name__ == "__main__":
    main()
