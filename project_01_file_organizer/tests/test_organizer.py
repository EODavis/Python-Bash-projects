"""
test_organizer.py
=================
Unit tests for Project 01: File Organizer Bot

Run: pytest tests/ -v
"""

import pytest
import shutil
from pathlib import Path
from src.organizer import get_category, sanitise_filename, build_destination, organise

# ─── FIXTURES ────────────────────────────────────────────────────────────────

@pytest.fixture
def temp_source(tmp_path):
    """Creates a small temporary messy folder for testing."""
    files = {
        "report.txt":    "Some report content",
        "photo.jpg":     "<<IMAGE>>",
        "script.py":     "print('hello')",
        "data.csv":      "col1,col2\n1,2",
        "archive.zip":   "<<ZIP>>",
        "unknownfile":   "no extension",
        "  spaced.txt":  "has leading space",
        "dup_a.txt":     "identical content",
        "dup_b.txt":     "identical content",
    }
    for name, content in files.items():
        (tmp_path / name).write_text(content)
    return tmp_path


# ─── UNIT TESTS ──────────────────────────────────────────────────────────────

class TestGetCategory:
    def test_txt_goes_to_documents_text(self):
        assert get_category(Path("report.txt")) == "documents/text"

    def test_jpg_goes_to_images(self):
        assert get_category(Path("photo.jpg")) == "images"

    def test_py_goes_to_code_python(self):
        assert get_category(Path("script.py")) == "code/python"

    def test_sh_goes_to_code_shell(self):
        assert get_category(Path("backup.sh")) == "code/shell"

    def test_csv_goes_to_spreadsheets(self):
        assert get_category(Path("data.csv")) == "spreadsheets"

    def test_zip_goes_to_archives(self):
        assert get_category(Path("bundle.zip")) == "archives"

    def test_unknown_extension_goes_to_uncategorised(self):
        assert get_category(Path("weirdfile.xyz")) == "uncategorised"

    def test_no_extension_goes_to_uncategorised(self):
        assert get_category(Path("noextension")) == "uncategorised"

    def test_uppercase_extension_handled(self):
        assert get_category(Path("PHOTO.JPG")) == "images"

    def test_md_goes_to_documents_markdown(self):
        assert get_category(Path("readme.md")) == "documents/markdown"


class TestSanitiseFilename:
    def test_strips_leading_spaces(self, tmp_path):
        spaced = tmp_path / "  spaced.txt"
        spaced.write_text("content")
        result = sanitise_filename(spaced)
        assert result.name == "spaced.txt"
        assert result.exists()

    def test_clean_filename_unchanged(self, tmp_path):
        clean = tmp_path / "clean.txt"
        clean.write_text("content")
        result = sanitise_filename(clean)
        assert result.name == "clean.txt"


class TestBuildDestination:
    def test_basic_destination(self, tmp_path):
        dest = build_destination(tmp_path / "source", "images", "photo.jpg")
        assert dest.parent.name == "images"
        assert dest.name == "photo.jpg"

    def test_collision_appends_counter(self, tmp_path):
        organised = tmp_path / "organised" / "images"
        organised.mkdir(parents=True)
        (organised / "photo.jpg").write_text("existing")
        dest = build_destination(tmp_path / "source", "images", "photo.jpg")
        assert dest.name == "photo_1.jpg"


class TestOrganise:
    def test_dry_run_moves_nothing(self, temp_source):
        original_files = set(p.name for p in temp_source.iterdir() if p.is_file())
        organise(temp_source, dry_run=True)
        after_files = set(p.name.strip() for p in temp_source.iterdir() if p.is_file())
        # All original files (stripped) should still exist
        assert len(after_files) >= len(original_files) - 1  # allow sanitise rename

    def test_live_run_moves_files(self, temp_source):
        stats = organise(temp_source, dry_run=False)
        assert stats["moved"] > 0
        assert stats["errors"] == 0

    def test_organised_folder_created(self, temp_source):
        organise(temp_source, dry_run=False)
        organised = temp_source.parent / "organised"
        assert organised.exists()

    def test_categories_populated(self, temp_source):
        stats = organise(temp_source, dry_run=False)
        assert len(stats["categories"]) > 0

    def test_log_written_when_log_dir_given(self, temp_source, tmp_path):
        log_dir = tmp_path / "logs"
        organise(temp_source, dry_run=True, log_dir=log_dir)
        logs = list(log_dir.glob("*.csv"))
        assert len(logs) == 1

    def test_log_contains_correct_columns(self, temp_source, tmp_path):
        import csv
        log_dir = tmp_path / "logs"
        organise(temp_source, dry_run=True, log_dir=log_dir)
        log_file = list(log_dir.glob("*.csv"))[0]
        with open(log_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert "filename" in rows[0]
        assert "category" in rows[0]
        assert "status"   in rows[0]

    def test_source_not_found_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            organise(tmp_path / "nonexistent_folder", dry_run=True)
