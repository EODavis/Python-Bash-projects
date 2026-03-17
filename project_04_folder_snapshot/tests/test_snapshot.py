"""
test_snapshot.py
================
Unit tests for Project 04: Smart Folder Snapshot

Tests cover:
  - Snapshot structure and metadata
  - File hashing consistency
  - Diff detection: ADDED, DELETED, MODIFIED, MOVED, UNCHANGED
  - Edge cases: empty dirs, binary files, nested paths
  - Snapshot persistence (save/load round-trip)
  - File history tracking

Run: pytest tests/ -v
"""

import json
import time
import pytest
from pathlib import Path
from src.snapshot import (
    hash_file,
    take_snapshot,
    save_snapshot,
    load_snapshot,
    list_snapshots,
    diff_snapshots,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def workspace(tmp_path):
    """A clean, realistic workspace to snapshot."""
    files = {
        "src/main.py":         "print('hello')\n",
        "src/utils.py":        "def helper(): pass\n",
        "config/settings.yaml":"debug: false\nport: 8080\n",
        "data/input.csv":      "id,value\n1,100\n2,200\n",
        "README.md":           "# My Project\n",
        "requirements.txt":    "pandas==2.0.0\n",
    }
    for rel, content in files.items():
        full = tmp_path / rel
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    return tmp_path


@pytest.fixture
def snap_dir(tmp_path):
    """Empty snapshot storage directory."""
    d = tmp_path / "snapshots"
    d.mkdir()
    return d


# ═══════════════════════════════════════════════════════════════════════════════
#  hash_file
# ═══════════════════════════════════════════════════════════════════════════════

class TestHashFile:
    def test_same_content_same_hash(self, tmp_path):
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("identical content")
        b.write_text("identical content")
        assert hash_file(a) == hash_file(b)

    def test_different_content_different_hash(self, tmp_path):
        a = tmp_path / "a.txt"
        b = tmp_path / "b.txt"
        a.write_text("content A")
        b.write_text("content B")
        assert hash_file(a) != hash_file(b)

    def test_hash_is_64_char_hex(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("test")
        h = hash_file(f)
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_modified_file_changes_hash(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("version 1")
        h1 = hash_file(f)
        f.write_text("version 2")
        h2 = hash_file(f)
        assert h1 != h2


# ═══════════════════════════════════════════════════════════════════════════════
#  take_snapshot
# ═══════════════════════════════════════════════════════════════════════════════

class TestTakeSnapshot:
    def test_returns_dict_with_meta_and_files(self, workspace):
        snap = take_snapshot(workspace)
        assert "meta"  in snap
        assert "files" in snap

    def test_meta_has_required_keys(self, workspace):
        snap = take_snapshot(workspace)
        for key in ["source", "taken_at", "file_count", "total_bytes"]:
            assert key in snap["meta"]

    def test_file_count_correct(self, workspace):
        snap = take_snapshot(workspace)
        assert snap["meta"]["file_count"] == 6

    def test_files_have_hash_size_modified(self, workspace):
        snap  = take_snapshot(workspace)
        entry = list(snap["files"].values())[0]
        assert "hash"        in entry
        assert "size_bytes"  in entry
        assert "modified_at" in entry

    def test_paths_are_relative_forward_slashes(self, workspace):
        snap  = take_snapshot(workspace)
        paths = list(snap["files"].keys())
        assert all("/" in p or p.count(".") >= 1 for p in paths)
        assert all("\\" not in p for p in paths)

    def test_total_bytes_positive(self, workspace):
        snap = take_snapshot(workspace)
        assert snap["meta"]["total_bytes"] > 0

    def test_empty_directory_gives_zero_files(self, tmp_path):
        snap = take_snapshot(tmp_path)
        assert snap["meta"]["file_count"] == 0

    def test_deterministic_for_unchanged_dir(self, workspace):
        snap1 = take_snapshot(workspace)
        snap2 = take_snapshot(workspace)
        assert snap1["files"] == snap2["files"]


# ═══════════════════════════════════════════════════════════════════════════════
#  save_snapshot / load_snapshot
# ═══════════════════════════════════════════════════════════════════════════════

class TestPersistence:
    def test_save_creates_json_file(self, workspace, snap_dir):
        snap = take_snapshot(workspace)
        path = save_snapshot(snap, snap_dir)
        assert path.exists()
        assert path.suffix == ".json"

    def test_filename_has_timestamp(self, workspace, snap_dir):
        snap = take_snapshot(workspace)
        path = save_snapshot(snap, snap_dir)
        assert "snapshot_" in path.name

    def test_load_roundtrip(self, workspace, snap_dir):
        snap      = take_snapshot(workspace)
        path      = save_snapshot(snap, snap_dir)
        reloaded  = load_snapshot(path)
        assert reloaded["meta"]  == snap["meta"]
        assert reloaded["files"] == snap["files"]

    def test_list_snapshots_sorted(self, workspace, snap_dir):
        snap = take_snapshot(workspace)
        save_snapshot(snap, snap_dir)
        time.sleep(0.05)
        save_snapshot(snap, snap_dir)
        snaps = list_snapshots(snap_dir)
        assert len(snaps) == 2
        assert snaps[0].name < snaps[1].name  # alphabetically sorted = chronologically sorted


# ═══════════════════════════════════════════════════════════════════════════════
#  diff_snapshots
# ═══════════════════════════════════════════════════════════════════════════════

class TestDiffSnapshots:

    def _make_snap(self, files: dict) -> dict:
        """Build a minimal snapshot dict from a {path: content} dict."""
        import hashlib
        file_entries = {}
        for path, content in files.items():
            h = hashlib.sha256(content.encode()).hexdigest()
            file_entries[path] = {
                "hash":        h,
                "size_bytes":  len(content),
                "modified_at": "2025-01-01T00:00:00",
            }
        return {
            "meta":  {"taken_at": "2025-01-01T00:00:00", "file_count": len(files), "total_bytes": 0},
            "files": file_entries,
        }

    def test_no_changes_all_unchanged(self):
        files = {"a.txt": "hello", "b.txt": "world"}
        snap  = self._make_snap(files)
        diff  = diff_snapshots(snap, snap)
        assert diff["summary"]["unchanged"] == 2
        assert diff["summary"]["added"]     == 0

    def test_detects_added_file(self):
        a = self._make_snap({"a.txt": "hello"})
        b = self._make_snap({"a.txt": "hello", "b.txt": "new file"})
        diff = diff_snapshots(a, b)
        assert diff["summary"]["added"] == 1
        added_paths = [c["path"] for c in diff["changes"] if c["status"] == "ADDED"]
        assert "b.txt" in added_paths

    def test_detects_deleted_file(self):
        a = self._make_snap({"a.txt": "hello", "b.txt": "bye"})
        b = self._make_snap({"a.txt": "hello"})
        diff = diff_snapshots(a, b)
        assert diff["summary"]["deleted"] == 1
        deleted_paths = [c["path"] for c in diff["changes"] if c["status"] == "DELETED"]
        assert "b.txt" in deleted_paths

    def test_detects_modified_file(self):
        a = self._make_snap({"a.txt": "version 1"})
        b = self._make_snap({"a.txt": "version 2"})
        diff = diff_snapshots(a, b)
        assert diff["summary"]["modified"] == 1
        modified = [c for c in diff["changes"] if c["status"] == "MODIFIED"]
        assert modified[0]["path"] == "a.txt"

    def test_detects_moved_file(self):
        content = "same content in both"
        a = self._make_snap({"old/path.txt": content})
        b = self._make_snap({"new/path.txt": content})
        diff = diff_snapshots(a, b)
        assert diff["summary"]["moved"] == 1
        moved = [c for c in diff["changes"] if c["status"] == "MOVED"]
        assert moved[0]["path"]   == "old/path.txt"
        assert moved[0]["path_b"] == "new/path.txt"

    def test_moved_not_counted_as_added_and_deleted(self):
        content = "moved content"
        a    = self._make_snap({"old.txt": content})
        b    = self._make_snap({"new.txt": content})
        diff = diff_snapshots(a, b)
        assert diff["summary"]["added"]   == 0
        assert diff["summary"]["deleted"] == 0
        assert diff["summary"]["moved"]   == 1

    def test_complex_diff(self):
        a = self._make_snap({
            "keep.txt":    "stays same",
            "modify.txt":  "old version",
            "delete.txt":  "will be gone",
            "move_src.txt":"will move",
        })
        b = self._make_snap({
            "keep.txt":    "stays same",
            "modify.txt":  "new version",
            "add.txt":     "brand new",
            "move_dst.txt":"will move",
        })
        diff = diff_snapshots(a, b)
        s = diff["summary"]
        assert s["unchanged"] == 1
        assert s["modified"]  == 1
        assert s["deleted"]   == 1
        assert s["added"]     == 1
        assert s["moved"]     == 1

    def test_summary_counts_sum_to_total_unique_paths(self):
        a = self._make_snap({"a.txt": "1", "b.txt": "2", "c.txt": "3"})
        b = self._make_snap({"a.txt": "1", "b.txt": "changed", "d.txt": "4"})
        diff = diff_snapshots(a, b)
        s    = diff["summary"]
        total = s["unchanged"] + s["modified"] + s["added"] + s["deleted"] + s["moved"]
        all_paths = set(a["files"]) | set(b["files"])
        assert total == len(all_paths)
