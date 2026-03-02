# 🔍 Project 02 — Duplicate File Finder

> **Tier:** 🟢 Foundations | **Theme:** Local File Manipulation  
> **Stack:** Python 3 · hashlib · pathlib · csv

## What It Does
Recursively scans any directory, hashes every file with SHA-256,
groups identical files, and reports wasted disk space.
Cross-folder duplicates are caught automatically.

## How to Run
```bash
# Scan and report
python src/duplicate_finder.py --source test_data --output output

# Scan and interactively delete
python src/duplicate_finder.py --source test_data --delete
```

## Skills Learned
- SHA-256 file hashing with chunked reads
- Recursive directory walking with `rglob`
- `defaultdict` grouping pattern
- Wasted space calculation
- CSV report generation
- Interactive CLI confirmation prompts
