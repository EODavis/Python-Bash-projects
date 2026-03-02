# 📁 Project 01 — File Organizer Bot

> **Tier:** 🟢 Foundations | **Theme:** Local File Manipulation  
> **Stack:** Python 3 · argparse · shutil · csv · pathlib

---

## What It Does

Drops a messy folder full of files into categories automatically:

```
test_data/                        organised/
├── invoice_nov2024.txt    →      documents/text/
├── photo_lagos.jpg        →      images/
├── data_cleaner.py        →      code/python/
├── transactions.csv       →      spreadsheets/
├── backup.sh              →      code/shell/
└── old_project.zip        →      archives/
```

Outputs a timestamped **CSV move-log** with source, destination, category, and status.

---

## Project Structure

```
project_01_file_organizer/
├── src/
│   └── organizer.py        # Core bot
├── tests/
│   └── test_organizer.py   # 12 unit tests
├── logs/                   # Auto-generated move logs (CSV)
├── output/                 # Summary reports
├── test_data/              # Synthetic messy files
└── README.md
```

---

## How to Run

```bash
# 1. Preview only (no files moved)
python src/organizer.py --source test_data --dry-run --log-dir logs

# 2. Live run (moves files for real)
python src/organizer.py --source test_data --log-dir logs

# 3. Run tests
pytest tests/ -v
```

---

## Sample Output

```
============================================================
  File Organizer Bot  |  🔍 DRY RUN
  Source : /projects/project_01/test_data
  Time   : 2025-02-26 10:42:01
============================================================

  ~  [documents/text            ]  invoice_nov2024.txt
  ~  [images                    ]  photo_lagos_trip.jpg
  ~  [code/python               ]  data_cleaner.py
  ~  [spreadsheets              ]  transactions_q1.csv
  ~  [archives                  ]  old_project_backup.zip
  ~  [uncategorised             ]  unnamed_file

────────────────────────────────────────────────────────────
  📊 SUMMARY
────────────────────────────────────────────────────────────
  Files scanned :  30
  Would move    :  30
  Errors        :   0

  Categories breakdown:
    documents/text                  8 file(s)
    images                          4 file(s)
    code/python                     3 file(s)
    ...
```

---

## Skills Learned

- `pathlib` for cross-platform file handling
- `shutil.move()` for safe file operations
- Dry-run pattern (preview before commit)
- CSV logging with `csv.DictWriter`
- Collision-safe destination naming
- `argparse` for CLI interfaces
- `pytest` fixtures and unit testing
