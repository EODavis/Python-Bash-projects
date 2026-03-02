"""
renamer.py
==========
Project 03: Bulk File Renamer
------------------------------
Renames files in a folder using composable, chainable strategies:

  Strategies (apply in any combination via --rules):
    slugify     → "My File Name!.txt"    → "my_file_name.txt"
    snake_case  → "camelCaseFile.py"     → "camel_case_file.py"
    date_prefix → adds YYYY-MM-DD_ prefix using file modification time
    sequential  → adds zero-padded numeric prefix (001_, 002_, ...)
    strip_ver   → removes common version suffixes (_v1, _FINAL, _old, _copy)
    dedupe_words→ removes repeated words ("copy of copy of..." → "copy_of...")
    sanitise    → collapses spaces, removes special chars (&, #, !, @, (), etc.)

Modes:
    --dry-run   Preview only (default safety net — always run this first!)
    (no flag)   Live rename

Outputs:
    - Console preview table
    - CSV rename log (logs/)

Usage:
    python src/renamer.py --source test_data --dry-run
    python src/renamer.py --source test_data --dry-run --rules slugify date_prefix
    python src/renamer.py --source test_data --rules slugify sequential
    python src/renamer.py --source test_data --rules slugify strip_ver dedupe_words
"""

import re
import csv
import argparse
from pathlib import Path
from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════════
#  STRATEGY FUNCTIONS  (each takes a stem string, returns a cleaned stem string)
# ═══════════════════════════════════════════════════════════════════════════════

def strategy_sanitise(stem: str) -> str:
    """
    Step 1 — always runs first internally.
    - Collapse multiple spaces/underscores
    - Remove chars that are dangerous in filenames: & # ! @ ( ) [ ] { } , ; ' "
    - Normalize separators to single space
    """
    # Remove special chars
    stem = re.sub(r"[&#!@()\[\]{},;'\"]+", " ", stem)
    # Collapse dashes used as separators ("notes - meeting - jan" → "notes meeting jan")
    stem = re.sub(r"\s*-\s*", " ", stem)
    # Collapse multiple spaces/underscores
    stem = re.sub(r"[\s_]+", " ", stem).strip()
    return stem


def strategy_slugify(stem: str) -> str:
    """
    Lowercase everything, replace spaces with underscores.
    'Monthly Revenue Report' → 'monthly_revenue_report'
    """
    stem = stem.lower()
    stem = re.sub(r"\s+", "_", stem)
    stem = re.sub(r"_+", "_", stem).strip("_")
    return stem


def strategy_snake_case(stem: str) -> str:
    """
    Convert camelCase or PascalCase to snake_case.
    'dataAnalysisScript' → 'data_analysis_script'
    Also slugifies the result.
    """
    # Insert underscore before uppercase letters preceded by lowercase
    stem = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", stem)
    # Insert underscore before uppercase runs followed by lowercase
    stem = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", stem)
    return strategy_slugify(stem)


def strategy_strip_version(stem: str) -> str:
    """
    Remove common version & status suffixes (case-insensitive):
    _v1, _v2, _v3, _FINAL, _final, _old, _copy, _use_this_one, _backup
    Applied repeatedly until stable.
    """
    patterns = [
        r"[_ ]+v\d+(\.\d+)?$",           # _v1, _v2, _v3, _v1.2
        r"[_ ]+final(?:_final)*$",        # _final, _FINAL, _final_FINAL
        r"[_ ]+old$",                      # _old
        r"[_ ]+copy$",                     # _copy
        r"[_ ]+backup$",                   # _backup
        r"[_ ]+use[_ ]this([_ ]one)?$",   # _use_this_one
        r"[_ ]+draft$",                    # _draft (optional — aggressive)
        r"[_ ]+revised$",                  # _revised
        r"\(\d+\)$",                       # (1), (2) — untitled(1)
    ]
    prev = None
    stem_lower = stem  # work on lowercase copy for matching
    while prev != stem_lower:
        prev = stem_lower
        for pat in patterns:
            stem_lower = re.sub(pat, "", stem_lower, flags=re.IGNORECASE).strip()
    return stem_lower


def strategy_dedupe_words(stem: str) -> str:
    """
    Remove consecutively repeated words or phrases.
    'copy of copy of copy of invoice' → 'copy of invoice'
    'backup of backup of project plan' → 'backup of project plan'
    Works on space-separated or underscore-separated tokens.
    """
    separator = "_" if "_" in stem else " "
    words = stem.replace("_", " ").split()

    # Remove consecutive duplicate single words
    deduped = []
    for word in words:
        if not deduped or word.lower() != deduped[-1].lower():
            deduped.append(word)
    result = separator.join(deduped)

    # Remove repeated 2-word phrases
    for _ in range(3):  # multiple passes
        result = re.sub(
            r"\b(\w+(?:[ _]\w+)?)\b([ _]\1\b)+",
            r"\1", result, flags=re.IGNORECASE
        )
    return result.strip()


def strategy_date_prefix(stem: str, filepath: Path) -> str:
    """
    Prepend the file's modification date as YYYY-MM-DD_.
    'invoice_nov2024' → '2024-11-01_invoice_nov2024'
    Note: uses actual file mtime, not parsed date from name.
    """
    mtime  = filepath.stat().st_mtime
    date_s = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")
    return f"{date_s}_{stem}"


# ═══════════════════════════════════════════════════════════════════════════════
#  STRATEGY REGISTRY
# ═══════════════════════════════════════════════════════════════════════════════

STRATEGIES = {
    "sanitise":    strategy_sanitise,
    "slugify":     strategy_slugify,
    "snake_case":  strategy_snake_case,
    "strip_ver":   strategy_strip_version,
    "dedupe_words":strategy_dedupe_words,
    # date_prefix handled separately (needs filepath)
}

STRATEGY_HELP = """
Available rename strategies (applied left to right):
  sanitise      Remove special chars, collapse spaces        (always auto-applied first)
  slugify       Lowercase + underscores                      e.g. "My File" → "my_file"
  snake_case    camelCase → snake_case + slugify             e.g. "myFile" → "my_file"
  strip_ver     Remove _v1 _FINAL _old _copy suffixes        e.g. "report_FINAL_v2" → "report"
  dedupe_words  Remove repeated words/phrases                e.g. "copy of copy of x" → "copy_of_x"
  date_prefix   Prepend file mod date as YYYY-MM-DD_         e.g. "report" → "2025-01-15_report"
  sequential    Prepend zero-padded counter 001_ 002_ ...    e.g. "report" → "001_report"
"""


# ═══════════════════════════════════════════════════════════════════════════════
#  RENAME ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def apply_rules(filepath: Path, rules: list, seq_num: int = None) -> str:
    """
    Apply the chosen strategy chain to a filepath's stem.
    Returns the full new filename (stem + original extension).
    """
    stem = filepath.stem
    ext  = filepath.suffix.lower()  # also normalise extension case

    # Step 0: always sanitise first
    stem = strategy_sanitise(stem)

    # Step 1+: apply user-chosen rules in order
    for rule in rules:
        if rule == "sanitise":
            continue  # already done above
        elif rule == "date_prefix":
            stem = strategy_date_prefix(stem, filepath)
        elif rule == "sequential":
            if seq_num is not None:
                stem = f"{seq_num:03d}_{stem}"
        elif rule in STRATEGIES:
            stem = STRATEGIES[rule](stem)

    # Final cleanup: no double underscores, no leading/trailing underscores
    stem = re.sub(r"_+", "_", stem).strip("_")

    # Rebuild filename
    return stem + ext


def build_safe_destination(dest_dir: Path, new_name: str, existing_names: set) -> str:
    """
    If new_name already exists in dest_dir or in the current rename batch,
    append _conflict_N to avoid collisions.
    """
    if new_name not in existing_names and not (dest_dir / new_name).exists():
        return new_name

    stem = Path(new_name).stem
    ext  = Path(new_name).suffix
    counter = 1
    candidate = f"{stem}_conflict_{counter}{ext}"
    while candidate in existing_names or (dest_dir / candidate).exists():
        counter += 1
        candidate = f"{stem}_conflict_{counter}{ext}"
    return candidate


def rename_files(source_dir: Path, rules: list, dry_run: bool, log_dir: Path) -> dict:
    """
    Main rename loop.

    Args:
        source_dir : folder of files to rename
        rules      : ordered list of strategy names to apply
        dry_run    : True = preview only, False = actually rename
        log_dir    : where to write CSV log

    Returns:
        stats dict
    """
    source_dir = source_dir.resolve()
    files = sorted([f for f in source_dir.iterdir() if f.is_file()])

    if not files:
        print("  ⚠️  No files found in source directory.")
        return {}

    run_time   = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    mode_label = "🔍 DRY RUN" if dry_run else "🚀 LIVE RENAME"

    print(f"\n{'='*75}")
    print(f"  Bulk File Renamer  |  {mode_label}")
    print(f"  Source  : {source_dir}")
    print(f"  Rules   : {' → '.join(['sanitise'] + rules)}")
    print(f"  Time    : {run_time}")
    print(f"{'='*75}\n")
    print(f"  {'ORIGINAL NAME':<42} {'NEW NAME':<30}")
    print(f"  {'─'*41} {'─'*30}")

    log_entries    = []
    renamed_count  = 0
    skipped_count  = 0
    error_count    = 0
    used_names     = set()  # track names in this batch to avoid collisions

    for seq_num, filepath in enumerate(files, start=1):
        original_name = filepath.name
        try:
            new_name  = apply_rules(filepath, rules, seq_num if "sequential" in rules else None)
            new_name  = build_safe_destination(source_dir, new_name, used_names)
            used_names.add(new_name)

            changed   = (new_name != original_name)
            status    = ""

            if not changed:
                status  = "UNCHANGED"
                skipped_count += 1
                icon    = "·"
            elif dry_run:
                status  = "WOULD_RENAME"
                renamed_count += 1
                icon    = "~"
            else:
                filepath.rename(source_dir / new_name)
                status  = "RENAMED"
                renamed_count += 1
                icon    = "→"

            # Truncate long names for console display
            orig_disp = (original_name[:39] + "…") if len(original_name) > 40 else original_name
            new_disp  = (new_name[:28]  + "…") if len(new_name)  > 29 else new_name
            print(f"  {icon}  {orig_disp:<42} {new_disp:<30}")

        except Exception as e:
            status       = f"ERROR: {e}"
            error_count += 1
            new_name     = original_name
            print(f"  ✗  ERROR on '{original_name}': {e}")

        log_entries.append({
            "seq":          seq_num,
            "timestamp":    run_time,
            "original":     original_name,
            "renamed_to":   new_name,
            "changed":      new_name != original_name,
            "status":       status,
            "rules":        "+".join(["sanitise"] + rules),
            "dry_run":      dry_run,
        })

    # ── SUMMARY ──────────────────────────────────────────────────────────────
    print(f"\n{'─'*75}")
    print(f"  📊 SUMMARY")
    print(f"{'─'*75}")
    print(f"  Total files  : {len(files)}")
    action = "Would rename" if dry_run else "Renamed"
    print(f"  {action:<13}: {renamed_count}")
    print(f"  Unchanged    : {skipped_count}")
    print(f"  Errors       : {error_count}")
    print(f"{'='*75}\n")

    # ── WRITE LOG ────────────────────────────────────────────────────────────
    log_dir.mkdir(parents=True, exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode_s   = "dryrun" if dry_run else "live"
    rules_s  = "_".join(rules) if rules else "default"
    log_path = log_dir / f"rename_log_{mode_s}_{rules_s}_{ts}.csv"

    with open(log_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=log_entries[0].keys())
        writer.writeheader()
        writer.writerows(log_entries)

    print(f"  📄 Log saved → {log_path}\n")

    return {
        "total":    len(files),
        "renamed":  renamed_count,
        "skipped":  skipped_count,
        "errors":   error_count,
        "log_path": str(log_path),
        "dry_run":  dry_run,
    }


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="Bulk File Renamer — apply composable rename strategies to a folder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=STRATEGY_HELP,
    )
    parser.add_argument(
        "--source", required=True,
        help="Directory containing files to rename."
    )
    parser.add_argument(
        "--rules", nargs="+", default=["slugify"],
        choices=["sanitise", "slugify", "snake_case", "strip_ver",
                 "dedupe_words", "date_prefix", "sequential"],
        help="Ordered list of rename strategies to apply (default: slugify)."
    )
    parser.add_argument(
        "--dry-run", action="store_true", default=False,
        help="Preview renames without touching any files."
    )
    parser.add_argument(
        "--log-dir", default="logs",
        help="Where to save the CSV rename log (default: logs/)."
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    rename_files(
        source_dir = Path(args.source),
        rules      = args.rules,
        dry_run    = args.dry_run,
        log_dir    = Path(args.log_dir),
    )
