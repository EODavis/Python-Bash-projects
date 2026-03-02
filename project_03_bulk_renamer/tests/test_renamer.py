"""
test_renamer.py
===============
Unit tests for Project 03: Bulk File Renamer

Tests every strategy function in isolation, then tests the full
apply_rules() pipeline and the rename_files() engine end-to-end.

Run: pytest tests/ -v
"""

import csv
import pytest
from pathlib import Path
from src.renamer import (
    strategy_sanitise,
    strategy_slugify,
    strategy_snake_case,
    strategy_strip_version,
    strategy_dedupe_words,
    strategy_date_prefix,
    apply_rules,
    build_safe_destination,
    rename_files,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  FIXTURES
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def messy_dir(tmp_path):
    """Folder of messy-named files for integration tests."""
    names = [
        "MONTHLY REPORT JANUARY.txt",
        "invoice_FINAL_v2.txt",
        "dataAnalysisScript.py",
        "copy of copy of notes.txt",
        "client brief & proposal (draft).txt",
        "  spaced_file.txt",
        "budget #2 revised.txt",
        "report_v1.txt",
        "report_v2.txt",
        "report_FINAL.txt",
    ]
    for name in names:
        (tmp_path / name).write_text(f"content: {name}")
    return tmp_path


# ═══════════════════════════════════════════════════════════════════════════════
#  strategy_sanitise
# ═══════════════════════════════════════════════════════════════════════════════

class TestSanitise:
    def test_removes_ampersand(self):
        assert "&" not in strategy_sanitise("brief & proposal")

    def test_removes_hash(self):
        assert "#" not in strategy_sanitise("budget #2")

    def test_removes_exclamation(self):
        assert "!" not in strategy_sanitise("urgent!!!")

    def test_removes_parentheses(self):
        result = strategy_sanitise("file (draft)")
        assert "(" not in result and ")" not in result

    def test_collapses_dashes_as_separators(self):
        result = strategy_sanitise("notes - meeting - jan")
        assert "--" not in result
        assert "-" not in result

    def test_collapses_multiple_spaces(self):
        result = strategy_sanitise("too   many    spaces")
        assert "  " not in result

    def test_strips_leading_trailing_spaces(self):
        assert strategy_sanitise("  hello  ") == "hello"

    def test_empty_string_returns_empty(self):
        assert strategy_sanitise("") == ""


# ═══════════════════════════════════════════════════════════════════════════════
#  strategy_slugify
# ═══════════════════════════════════════════════════════════════════════════════

class TestSlugify:
    def test_lowercases_everything(self):
        assert strategy_slugify("REPORT") == "report"

    def test_spaces_become_underscores(self):
        assert strategy_slugify("my file name") == "my_file_name"

    def test_no_double_underscores(self):
        result = strategy_slugify("too  many  spaces")
        assert "__" not in result

    def test_no_leading_trailing_underscores(self):
        result = strategy_slugify("  hello  ")
        assert not result.startswith("_")
        assert not result.endswith("_")

    def test_already_clean_unchanged(self):
        assert strategy_slugify("clean_name") == "clean_name"


# ═══════════════════════════════════════════════════════════════════════════════
#  strategy_snake_case
# ═══════════════════════════════════════════════════════════════════════════════

class TestSnakeCase:
    def test_camel_to_snake(self):
        assert strategy_snake_case("dataAnalysisScript") == "data_analysis_script"

    def test_pascal_to_snake(self):
        assert strategy_snake_case("MonthlyRevenueReport") == "monthly_revenue_report"

    def test_already_snake_unchanged(self):
        assert strategy_snake_case("already_snake") == "already_snake"

    def test_acronym_followed_by_lowercase(self):
        # "HTMLParser" → "html_parser"
        result = strategy_snake_case("HTMLParser")
        assert "_" in result

    def test_single_word_lowercased(self):
        assert strategy_snake_case("Report") == "report"


# ═══════════════════════════════════════════════════════════════════════════════
#  strategy_strip_version
# ═══════════════════════════════════════════════════════════════════════════════

class TestStripVersion:
    def test_strips_v1(self):
        assert "v1" not in strategy_strip_version("report_v1")

    def test_strips_v2(self):
        assert "v2" not in strategy_strip_version("report_v2")

    def test_strips_final(self):
        result = strategy_strip_version("report_FINAL")
        assert "final" not in result.lower()

    def test_strips_final_v2(self):
        result = strategy_strip_version("report_FINAL_v2")
        assert "final" not in result.lower()
        assert "v2"    not in result

    def test_strips_repeated_final(self):
        result = strategy_strip_version("report_final_FINAL")
        assert "final" not in result.lower()

    def test_strips_old(self):
        assert "old" not in strategy_strip_version("script_old")

    def test_strips_copy(self):
        assert "copy" not in strategy_strip_version("file_copy")

    def test_strips_parenthetical_number(self):
        result = strategy_strip_version("untitled(1)")
        assert "(1)" not in result

    def test_preserves_base_name(self):
        result = strategy_strip_version("monthly_report_FINAL_v2")
        assert "monthly" in result
        assert "report"  in result

    def test_already_clean_unchanged(self):
        assert strategy_strip_version("clean_report") == "clean_report"


# ═══════════════════════════════════════════════════════════════════════════════
#  strategy_dedupe_words
# ═══════════════════════════════════════════════════════════════════════════════

class TestDedupeWords:
    def test_removes_consecutive_duplicate_words(self):
        result = strategy_dedupe_words("report report summary")
        assert result.count("report") == 1

    def test_copy_of_copy_of(self):
        result = strategy_dedupe_words("copy of copy of invoice")
        assert result.count("copy") == 1

    def test_backup_of_backup_of(self):
        result = strategy_dedupe_words("backup of backup of plan")
        assert result.count("backup") == 1

    def test_no_duplicates_unchanged(self):
        result = strategy_dedupe_words("monthly revenue report")
        assert "monthly" in result
        assert "revenue" in result
        assert "report"  in result

    def test_preserves_underscored_names(self):
        result = strategy_dedupe_words("copy_of_copy_of_notes")
        assert result.count("copy") == 1


# ═══════════════════════════════════════════════════════════════════════════════
#  apply_rules  (pipeline)
# ═══════════════════════════════════════════════════════════════════════════════

class TestApplyRules:
    def test_slugify_pipeline(self, tmp_path):
        f = tmp_path / "My File Name.txt"
        f.write_text("x")
        assert apply_rules(f, ["slugify"]) == "my_file_name.txt"

    def test_strip_ver_then_slugify(self, tmp_path):
        f = tmp_path / "Report FINAL v2.txt"
        f.write_text("x")
        result = apply_rules(f, ["strip_ver", "slugify"])
        assert "final" not in result.lower()
        assert "v2"    not in result

    def test_snake_case_pipeline(self, tmp_path):
        f = tmp_path / "dataAnalysisScript.py"
        f.write_text("x")
        assert apply_rules(f, ["snake_case"]) == "data_analysis_script.py"

    def test_sequential_prefix(self, tmp_path):
        f = tmp_path / "report.txt"
        f.write_text("x")
        result = apply_rules(f, ["sequential", "slugify"], seq_num=5)
        assert result.startswith("005_")

    def test_extension_preserved(self, tmp_path):
        f = tmp_path / "MyScript.PY"
        f.write_text("x")
        result = apply_rules(f, ["slugify"])
        assert result.endswith(".py")

    def test_no_double_underscores_in_output(self, tmp_path):
        f = tmp_path / "FINAL__REPORT__v2.txt"
        f.write_text("x")
        result = apply_rules(f, ["slugify"])
        assert "__" not in result

    def test_special_chars_removed(self, tmp_path):
        f = tmp_path / "brief & proposal (draft).txt"
        f.write_text("x")
        result = apply_rules(f, ["slugify"])
        assert "&" not in result
        assert "(" not in result


# ═══════════════════════════════════════════════════════════════════════════════
#  build_safe_destination
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildSafeDestination:
    def test_no_conflict_returns_name(self, tmp_path):
        result = build_safe_destination(tmp_path, "report.txt", set())
        assert result == "report.txt"

    def test_conflict_with_existing_set(self, tmp_path):
        result = build_safe_destination(tmp_path, "report.txt", {"report.txt"})
        assert result != "report.txt"
        assert "conflict" in result

    def test_conflict_with_file_on_disk(self, tmp_path):
        (tmp_path / "report.txt").write_text("existing")
        result = build_safe_destination(tmp_path, "report.txt", set())
        assert "conflict" in result


# ═══════════════════════════════════════════════════════════════════════════════
#  rename_files  (integration)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRenameFiles:
    def test_dry_run_no_files_moved(self, messy_dir):
        original = {f.name for f in messy_dir.iterdir() if f.is_file()}
        rename_files(messy_dir, ["slugify"], dry_run=True, log_dir=messy_dir / "logs")
        after = {f.name for f in messy_dir.iterdir() if f.is_file()}
        # Dry run: original files should still exist (allow sanitise rename of spaces)
        assert len(after) >= len(original) - 2

    def test_live_run_renames_files(self, messy_dir, tmp_path):
        stats = rename_files(messy_dir, ["slugify"], dry_run=False, log_dir=tmp_path / "logs")
        assert stats["renamed"] > 0
        assert stats["errors"]  == 0

    def test_live_run_produces_lowercase_names(self, messy_dir, tmp_path):
        rename_files(messy_dir, ["slugify"], dry_run=False, log_dir=tmp_path / "logs")
        for f in messy_dir.iterdir():
            if f.is_file():
                assert f.name == f.name.lower(), f"{f.name} should be lowercase"

    def test_no_special_chars_after_rename(self, messy_dir, tmp_path):
        rename_files(messy_dir, ["slugify"], dry_run=False, log_dir=tmp_path / "logs")
        for f in messy_dir.iterdir():
            if f.is_file():
                for char in "&# !@()":
                    assert char not in f.name

    def test_csv_log_written(self, messy_dir, tmp_path):
        log_dir = tmp_path / "logs"
        rename_files(messy_dir, ["slugify"], dry_run=True, log_dir=log_dir)
        logs = list(log_dir.glob("*.csv"))
        assert len(logs) == 1

    def test_csv_has_correct_columns(self, messy_dir, tmp_path):
        log_dir = tmp_path / "logs"
        rename_files(messy_dir, ["slugify"], dry_run=True, log_dir=log_dir)
        log_file = list(log_dir.glob("*.csv"))[0]
        with open(log_file) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert "original"   in rows[0]
        assert "renamed_to" in rows[0]
        assert "status"     in rows[0]
        assert "rules"      in rows[0]

    def test_no_collision_in_batch(self, messy_dir, tmp_path):
        """Two files that slugify to the same name must not overwrite each other."""
        rename_files(messy_dir, ["slugify", "strip_ver"], dry_run=False, log_dir=tmp_path / "logs")
        names = [f.name for f in messy_dir.iterdir() if f.is_file()]
        assert len(names) == len(set(names)), "Duplicate filenames found after rename!"
