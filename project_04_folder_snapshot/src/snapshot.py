"""
snapshot.py
===========
Project 04: Smart Folder Snapshot
-----------------------------------
Takes a cryptographic snapshot of a directory tree to JSON,
then diffs any two snapshots to detect exactly what changed:
  - ADDED    : new files
  - DELETED  : removed files
  - MODIFIED : content changed (hash differs)
  - MOVED    : same content, different path (hash match across paths)
  - UNCHANGED: identical

Modes:
  --save          Take a fresh snapshot and save to snapshots/
  --diff          Compare latest two snapshots and show delta
  --diff A B      Compare two specific snapshot files
  --list          List all saved snapshots
  --history FILE  Show the full change history of a specific file

Usage:
  python src/snapshot.py --source test_data/workspace --save
  python src/snapshot.py --source test_data/workspace --diff
  python src/snapshot.py --source test_data/workspace --history src/pipeline.py
  python src/snapshot.py --list --snapshot-dir snapshots
"""

import os
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict


# ═══════════════════════════════════════════════════════════════════════════════
#  SNAPSHOT ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def hash_file(filepath: Path, chunk_size: int = 65536) -> str:
    """SHA-256 hash a file in chunks — same approach as Project 02."""
    sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while chunk := f.read(chunk_size):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (PermissionError, OSError) as e:
        return f"ERROR:{e}"


def take_snapshot(source_dir: Path) -> dict:
    """
    Walk source_dir recursively and build a snapshot dict.

    Returns:
        {
            "meta": {
                "source":    "/abs/path/to/dir",
                "taken_at":  "2025-02-26T10:42:01",
                "file_count": 17,
                "total_bytes": 4821,
            },
            "files": {
                "src/pipeline.py": {
                    "hash":         "abc123...",
                    "size_bytes":   312,
                    "modified_at":  "2025-02-26T10:40:00",
                },
                ...
            }
        }
    """
    source_dir  = source_dir.resolve()
    files_data  = {}
    total_bytes = 0

    for filepath in sorted(source_dir.rglob("*")):
        if not filepath.is_file():
            continue

        rel_path = str(filepath.relative_to(source_dir))
        # Normalise to forward slashes for cross-platform consistency
        rel_path = rel_path.replace("\\", "/")

        try:
            stat        = filepath.stat()
            size        = stat.st_size
            modified_at = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
            file_hash   = hash_file(filepath)
            total_bytes += size

            files_data[rel_path] = {
                "hash":        file_hash,
                "size_bytes":  size,
                "modified_at": modified_at,
            }
        except OSError as e:
            files_data[rel_path] = {
                "hash":        f"ERROR:{e}",
                "size_bytes":  0,
                "modified_at": "unknown",
            }

    return {
        "meta": {
            "source":      str(source_dir),
            "taken_at":    datetime.now().isoformat(timespec="seconds"),
            "file_count":  len(files_data),
            "total_bytes": total_bytes,
        },
        "files": files_data,
    }


def save_snapshot(snapshot: dict, snapshot_dir: Path) -> Path:
    """Save snapshot JSON to snapshot_dir with a timestamp filename."""
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = snapshot_dir / f"snapshot_{ts}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, indent=2)
    return out_path


def load_snapshot(path: Path) -> dict:
    """Load a snapshot JSON from disk."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def list_snapshots(snapshot_dir: Path) -> list:
    """Return all snapshot files sorted by creation time (oldest first)."""
    snapshots = sorted(snapshot_dir.glob("snapshot_*.json"))
    return snapshots


# ═══════════════════════════════════════════════════════════════════════════════
#  DIFF ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def diff_snapshots(snap_a: dict, snap_b: dict) -> dict:
    """
    Compare two snapshots and return a structured diff.

    Change types (in priority order):
      MOVED     — hash exists in both, but path changed
      ADDED     — path in B but not A
      DELETED   — path in A but not B
      MODIFIED  — path in both A and B, but hash differs
      UNCHANGED — path in both A and B, hash identical

    Returns:
        {
            "summary": { "added": N, "deleted": N, "modified": N, "moved": N, "unchanged": N },
            "changes": [
                { "status": "ADDED", "path": "src/model.py", "path_b": None, ... },
                ...
            ]
        }
    """
    files_a = snap_a["files"]
    files_b = snap_b["files"]

    paths_a  = set(files_a.keys())
    paths_b  = set(files_b.keys())

    # Build reverse hash maps: hash → [paths]
    hash_to_paths_a = defaultdict(list)
    hash_to_paths_b = defaultdict(list)
    for path, info in files_a.items():
        hash_to_paths_a[info["hash"]].append(path)
    for path, info in files_b.items():
        hash_to_paths_b[info["hash"]].append(path)

    changes      = []
    accounted_a  = set()  # paths in A already explained
    accounted_b  = set()  # paths in B already explained

    # ── STEP 1: Detect MOVED files (same hash, different path) ────────────
    for h, paths_in_b in hash_to_paths_b.items():
        if h.startswith("ERROR"):
            continue
        paths_in_a_for_hash = hash_to_paths_a.get(h, [])
        # A hash that appears in A under a different path = MOVE
        for pb in paths_in_b:
            if pb not in paths_a:  # new path — not in A
                for pa in paths_in_a_for_hash:
                    if pa not in paths_b and pa not in accounted_a:
                        changes.append({
                            "status":       "MOVED",
                            "path":         pa,
                            "path_b":       pb,
                            "hash":         h,
                            "size_bytes":   files_b[pb]["size_bytes"],
                        })
                        accounted_a.add(pa)
                        accounted_b.add(pb)
                        break

    # ── STEP 2: Detect ADDED, DELETED, MODIFIED, UNCHANGED ───────────────
    all_paths = paths_a | paths_b

    for path in sorted(all_paths):
        if path in accounted_a or path in accounted_b:
            continue

        in_a = path in paths_a
        in_b = path in paths_b

        if in_b and not in_a:
            changes.append({
                "status":      "ADDED",
                "path":        path,
                "path_b":      None,
                "hash":        files_b[path]["hash"],
                "size_bytes":  files_b[path]["size_bytes"],
            })

        elif in_a and not in_b:
            changes.append({
                "status":      "DELETED",
                "path":        path,
                "path_b":      None,
                "hash":        files_a[path]["hash"],
                "size_bytes":  files_a[path]["size_bytes"],
            })

        elif in_a and in_b:
            ha = files_a[path]["hash"]
            hb = files_b[path]["hash"]
            if ha == hb:
                changes.append({
                    "status":      "UNCHANGED",
                    "path":        path,
                    "path_b":      None,
                    "hash":        hb,
                    "size_bytes":  files_b[path]["size_bytes"],
                })
            else:
                changes.append({
                    "status":      "MODIFIED",
                    "path":        path,
                    "path_b":      None,
                    "hash_before": ha,
                    "hash_after":  hb,
                    "size_bytes":  files_b[path]["size_bytes"],
                })

    # ── SUMMARY ──────────────────────────────────────────────────────────
    summary = {"added": 0, "deleted": 0, "modified": 0, "moved": 0, "unchanged": 0}
    for c in changes:
        summary[c["status"].lower()] += 1

    return {"summary": summary, "changes": changes}


# ═══════════════════════════════════════════════════════════════════════════════
#  REPORTERS
# ═══════════════════════════════════════════════════════════════════════════════

STATUS_ICONS = {
    "ADDED":     "➕",
    "DELETED":   "🗑 ",
    "MODIFIED":  "✏️ ",
    "MOVED":     "↩️ ",
    "UNCHANGED": "·  ",
}

STATUS_ORDER = ["ADDED", "DELETED", "MODIFIED", "MOVED", "UNCHANGED"]


def print_diff(diff: dict, snap_a: dict, snap_b: dict):
    """Pretty-print a diff to the console."""
    s   = diff["summary"]
    ta  = snap_a["meta"]["taken_at"]
    tb  = snap_b["meta"]["taken_at"]

    print(f"\n{'='*65}")
    print(f"  📸 Smart Folder Snapshot — Diff Report")
    print(f"{'='*65}")
    print(f"  Snapshot A  : {ta}  ({snap_a['meta']['file_count']} files)")
    print(f"  Snapshot B  : {tb}  ({snap_b['meta']['file_count']} files)")
    print(f"{'─'*65}")
    print(f"  ➕ Added     : {s['added']:>3}   🗑  Deleted  : {s['deleted']:>3}")
    print(f"  ✏️  Modified  : {s['modified']:>3}   ↩️  Moved    : {s['moved']:>3}")
    print(f"  ·  Unchanged : {s['unchanged']:>3}")
    print(f"{'─'*65}\n")

    # Group by status for cleaner display
    by_status = defaultdict(list)
    for c in diff["changes"]:
        by_status[c["status"]].append(c)

    for status in STATUS_ORDER:
        items = by_status.get(status, [])
        if not items or status == "UNCHANGED":
            continue
        icon = STATUS_ICONS[status]
        for item in items:
            if status == "MOVED":
                print(f"  {icon}  {status:<10}  {item['path']}  →  {item['path_b']}")
            else:
                print(f"  {icon}  {status:<10}  {item['path']}")

    # Show unchanged count but not each file
    unchanged = s["unchanged"]
    if unchanged:
        print(f"\n  ·  {unchanged} file(s) unchanged")

    print(f"\n{'='*65}\n")


def print_file_history(file_path: str, snapshot_dir: Path):
    """
    Show the change history of a single file across all snapshots.
    """
    snapshots = list_snapshots(snapshot_dir)
    if len(snapshots) < 1:
        print("  No snapshots found.")
        return

    print(f"\n{'='*65}")
    print(f"  📜 File History: {file_path}")
    print(f"{'='*65}\n")
    print(f"  {'SNAPSHOT':<22}  {'STATUS':<12}  {'HASH (first 12)':<14}  SIZE")
    print(f"  {'─'*21}  {'─'*11}  {'─'*13}  ────")

    prev_hash = None
    for snap_path in snapshots:
        snap = load_snapshot(snap_path)
        taken = snap["meta"]["taken_at"]
        files = snap["files"]

        if file_path in files:
            info    = files[file_path]
            h       = info["hash"]
            size    = info["size_bytes"]
            if prev_hash is None:
                status = "INITIAL"
            elif h != prev_hash:
                status = "MODIFIED"
            else:
                status = "UNCHANGED"
            prev_hash = h
            print(f"  {taken:<22}  {status:<12}  {h[:12]}...      {size} B")
        else:
            if prev_hash is not None:
                print(f"  {taken:<22}  {'DELETED':<12}  {'—':<14}  —")
                prev_hash = None
            else:
                print(f"  {taken:<22}  {'NOT YET':<12}  {'—':<14}  —")

    print()


# ═══════════════════════════════════════════════════════════════════════════════
#  CLI
# ═══════════════════════════════════════════════════════════════════════════════

def parse_args():
    parser = argparse.ArgumentParser(
        description="Smart Folder Snapshot — track directory changes over time."
    )
    parser.add_argument("--source",       help="Directory to snapshot.")
    parser.add_argument("--save",         action="store_true", help="Take and save a new snapshot.")
    parser.add_argument("--diff",         action="store_true", help="Diff the two most recent snapshots.")
    parser.add_argument("--diff-files",   nargs=2, metavar=("SNAP_A", "SNAP_B"),
                                          help="Diff two specific snapshot JSON files.")
    parser.add_argument("--list",         action="store_true", help="List all saved snapshots.")
    parser.add_argument("--history",      metavar="FILE",
                                          help="Show change history of a file across all snapshots.")
    parser.add_argument("--snapshot-dir", default="snapshots",
                                          help="Directory to store snapshots (default: snapshots/).")
    return parser.parse_args()


def main():
    args         = parse_args()
    snapshot_dir = Path(args.snapshot_dir)

    # ── LIST ──────────────────────────────────────────────────────────────
    if args.list:
        snaps = list_snapshots(snapshot_dir)
        print(f"\n  📚 Snapshots in {snapshot_dir}/ ({len(snaps)} total)\n")
        for i, s in enumerate(snaps, 1):
            snap = load_snapshot(s)
            m    = snap["meta"]
            print(f"  {i:>2}.  {s.name}  |  {m['file_count']} files  |  taken {m['taken_at']}")
        print()
        return

    # ── SAVE ──────────────────────────────────────────────────────────────
    if args.save:
        if not args.source:
            print("  ✗  --source required with --save")
            return
        source = Path(args.source)
        print(f"\n  📸 Taking snapshot of {source} ...")
        snap     = take_snapshot(source)
        out_path = save_snapshot(snap, snapshot_dir)
        m        = snap["meta"]
        print(f"  ✅ Snapshot saved → {out_path}")
        print(f"     Files : {m['file_count']}   Total size : {m['total_bytes']} B\n")
        return

    # ── DIFF (specific files) ─────────────────────────────────────────────
    if args.diff_files:
        snap_a = load_snapshot(Path(args.diff_files[0]))
        snap_b = load_snapshot(Path(args.diff_files[1]))
        diff   = diff_snapshots(snap_a, snap_b)
        print_diff(diff, snap_a, snap_b)
        return

    # ── DIFF (latest two) ─────────────────────────────────────────────────
    if args.diff:
        snaps = list_snapshots(snapshot_dir)
        if len(snaps) < 2:
            print(f"\n  ✗  Need at least 2 snapshots to diff. Found: {len(snaps)}\n")
            return
        snap_a = load_snapshot(snaps[-2])
        snap_b = load_snapshot(snaps[-1])
        diff   = diff_snapshots(snap_a, snap_b)
        print_diff(diff, snap_a, snap_b)
        return

    # ── HISTORY ───────────────────────────────────────────────────────────
    if args.history:
        print_file_history(args.history, snapshot_dir)
        return

    print("  Run with --help to see usage.")


if __name__ == "__main__":
    main()
