"""
test_duplicate_finder.py
========================
Unit tests for Project 02: Duplicate File Finder

Run: pytest tests/ -v
"""

import pytest
import csv
from pathlib import Path
from src.duplicate_finder import (
    hash_file,
    scan_directory,
    find_duplicates,
    compute_wasted_space,
    format_bytes,
    write_csv_report,
)


# ─── FIXTURES ────────────────────────────────────────────────────────────────

@pytest.fixture
def clean_dir(tmp_path):
    """Directory with all unique files — no duplicates."""
    (tmp_path / "file_a.txt").write_text("content alpha")
    (tmp_path / "file_b.txt").write_text("content beta")
    (tmp_path / "file_c.py").write_text("print('gamma')")
    return tmp_path


@pytest.fixture
def dup_dir(tmp_path):
    """Directory with known duplicates for testing."""
    identical = "This content is identical in all three files."
    (tmp_path / "original.txt").write_text(identical)
    (tmp_path / "copy_one.txt").write_text(identical)
    (tmp_path / "copy_two.txt").write_text(identical)
    (tmp_path / "unique.txt").write_text("Completely different content here.")
    sub = tmp_path / "subfolder"
    sub.mkdir()
    (sub / "nested_dup.txt").write_text(identical)   # cross-folder duplicate
    return tmp_path


# ─── HASH TESTS ──────────────────────────────────────────────────────────────

class TestHashFile:
    def test_same_content_same_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello world")
        f2.write_text("hello world")
        assert hash_file(f1) == hash_file(f2)

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("content one")
        f2.write_text("content two")
        assert hash_file(f1) != hash_file(f2)

    def test_hash_is_64_char_hex(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("test content")
        result = hash_file(f)
        assert len(result) == 64
        assert all(c in "0123456789abcdef" for c in result)

    def test_empty_file_has_stable_hash(self, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("")
        h = hash_file(f)
        assert len(h) == 64  # SHA-256 of empty string is deterministic


# ─── SCANNER TESTS ───────────────────────────────────────────────────────────

class TestScanDirectory:
    def test_returns_dict(self, clean_dir):
        result = scan_directory(clean_dir)
        assert isinstance(result, dict)

    def test_unique_files_each_have_own_hash(self, clean_dir):
        result = scan_directory(clean_dir)
        # All hashes should map to exactly 1 file
        assert all(len(v) == 1 for v in result.values())

    def test_duplicate_files_share_hash(self, dup_dir):
        result = scan_directory(dup_dir)
        # The identical content should appear under one hash with 4 paths
        dup_groups = [v for v in result.values() if len(v) >= 4]
        assert len(dup_groups) == 1

    def test_recursive_scan_catches_subfolders(self, dup_dir):
        result = scan_directory(dup_dir)
        all_paths = [str(p) for paths in result.values() for p in paths]
        assert any("subfolder" in p for p in all_paths)


# ─── DUPLICATE DETECTION TESTS ───────────────────────────────────────────────

class TestFindDuplicates:
    def test_no_duplicates_returns_empty(self, clean_dir):
        hash_map = scan_directory(clean_dir)
        dups = find_duplicates(hash_map)
        assert dups == {}

    def test_detects_duplicate_group(self, dup_dir):
        hash_map = scan_directory(dup_dir)
        dups = find_duplicates(hash_map)
        assert len(dups) == 1  # one group of identical files

    def test_duplicate_group_has_correct_count(self, dup_dir):
        hash_map = scan_directory(dup_dir)
        dups = find_duplicates(hash_map)
        counts = [len(v) for v in dups.values()]
        assert 4 in counts  # original + copy_one + copy_two + nested_dup


# ─── WASTED SPACE TESTS ──────────────────────────────────────────────────────

class TestComputeWastedSpace:
    def test_wasted_space_is_positive(self, dup_dir):
        hash_map = scan_directory(dup_dir)
        dups = find_duplicates(hash_map)
        wasted = compute_wasted_space(dups)
        assert wasted > 0

    def test_no_duplicates_zero_waste(self, clean_dir):
        hash_map = scan_directory(clean_dir)
        dups = find_duplicates(hash_map)
        assert compute_wasted_space(dups) == 0


# ─── FORMAT BYTES TESTS ──────────────────────────────────────────────────────

class TestFormatBytes:
    def test_bytes(self):
        assert "B" in format_bytes(500)

    def test_kilobytes(self):
        assert "KB" in format_bytes(2048)

    def test_megabytes(self):
        assert "MB" in format_bytes(2 * 1024 * 1024)

    def test_zero(self):
        assert "0.0 B" == format_bytes(0)


# ─── CSV REPORT TESTS ────────────────────────────────────────────────────────

class TestWriteCsvReport:
    def test_csv_created(self, dup_dir, tmp_path):
        hash_map = scan_directory(dup_dir)
        dups = find_duplicates(hash_map)
        csv_path = write_csv_report(dups, dup_dir, tmp_path / "output")
        assert csv_path.exists()

    def test_csv_has_correct_columns(self, dup_dir, tmp_path):
        hash_map = scan_directory(dup_dir)
        dups = find_duplicates(hash_map)
        csv_path = write_csv_report(dups, dup_dir, tmp_path / "output")
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert "group" in rows[0]
        assert "hash"  in rows[0]
        assert "suggestion" in rows[0]

    def test_first_in_group_marked_keep(self, dup_dir, tmp_path):
        hash_map = scan_directory(dup_dir)
        dups = find_duplicates(hash_map)
        csv_path = write_csv_report(dups, dup_dir, tmp_path / "output")
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        keep_rows = [r for r in rows if r["suggestion"] == "KEEP"]
        assert len(keep_rows) == len(dups)  # one KEEP per group
