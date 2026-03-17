# 📸 Smart Folder Snapshot

![Python](https://img.shields.io/badge/Python-3.8+-blue?logo=python&logoColor=white)
![CLI](https://img.shields.io/badge/Interface-CLI-lightgrey)
![Tier](https://img.shields.io/badge/Portfolio-Tier%201%20%F0%9F%9F%A2-brightgreen)
![Status](https://img.shields.io/badge/Status-Complete-success)

> **Project 04 of 120** — Python × Shell × GitHub Portfolio
> Takes cryptographic snapshots of a directory tree to JSON, then diffs any two snapshots to detect exactly what changed: files added, deleted, modified, or moved. Includes per-file history tracking.

---

## 🎯 What It Solves

Git tracks code. This tracks *everything* — data folders, config directories, shared drives, any folder you can't or don't want to put in version control. Take a snapshot before a big change, take one after, and know exactly what moved.

```
  📸 Smart Folder Snapshot — Diff Report
  Snapshot A  : 2025-02-26T10:18:49  (17 files)
  Snapshot B  : 2025-02-26T10:18:57  (19 files)
  ─────────────────────────────────────────────
  ➕ Added     :   3   🗑  Deleted  :   1
  ✏️  Modified  :   2   ↩️  Moved    :   1
  ·  Unchanged :  13
  ─────────────────────────────────────────────
  ➕  ADDED       data/raw/orders.csv
  ➕  ADDED       src/model.py
  🗑  DELETED     data/processed/clean.csv
  ✏️  MODIFIED    config/settings.yaml
  ↩️  MOVED       docs/CHANGELOG.md  →  docs/HISTORY.md
```

---

## 🚀 Quick Start

```bash
git clone https://github.com/EODavis/py-folder-snapshot.git
cd py-folder-snapshot

# 1. Create a synthetic workspace to track
python test_data/generate_test_data.py

# 2. Take initial snapshot
python src/snapshot.py --source test_data/workspace --save

# 3. Simulate changes (add, edit, delete, rename files)
python test_data/generate_test_data.py --mutate

# 4. Take second snapshot
python src/snapshot.py --source test_data/workspace --save

# 5. See exactly what changed
python src/snapshot.py --diff

# 6. Track one file's history across all snapshots
python src/snapshot.py --history src/pipeline.py

# 7. List all saved snapshots
python src/snapshot.py --list
```

---

## 🔧 Commands

| Flag | Description |
|---|---|
| `--save` | Take and save a new snapshot |
| `--diff` | Diff the two most recent snapshots |
| `--diff-files A B` | Diff two specific snapshot JSON files |
| `--list` | List all saved snapshots with metadata |
| `--history FILE` | Show a file's status across every snapshot |

---

## 🧪 Tests

```bash
python -m pytest tests/ -v   # 29 tests
```

Covers: hashing, snapshot structure, save/load round-trip, all 5 diff statuses (ADDED/DELETED/MODIFIED/MOVED/UNCHANGED), complex multi-change diffs, MOVE not double-counted as ADD+DELETE.

---

## 🧠 Skills Demonstrated

`SHA-256` content hashing · recursive `rglob()` · JSON serialisation · snapshot diff algorithm · MOVE detection via reverse hash maps · file history across time series · `argparse` subcommand-style CLI

---

## 🗺️ Part of the 120-Project Python Portfolio by [EODavis](https://github.com/EODavis)
