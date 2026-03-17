"""
test_task_converter.py — Project 16 unit tests (stdlib unittest, fully offline)
Run: python -m unittest tests.test_task_converter -v
"""
import csv
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.task_converter import (
    extract_due_date,
    score_priority,
    extract_tasks_from_text,
    next_weekday,
    decode_hdr,
    format_task_md,
    append_to_markdown,
    init_csv, append_csv, CSV_FIELDS,
    load_processed, save_processed,
    PRIORITY_EMOJI,
)

TODAY = date(2026, 3, 9)   # Monday


# ─── DATE EXTRACTION ─────────────────────────────────────────────────────────

class TestExtractDueDate(unittest.TestCase):
    def test_iso_date(self):
        self.assertEqual(extract_due_date("Due by 2026-03-15", TODAY), "2026-03-15")

    def test_slash_date(self):
        self.assertEqual(extract_due_date("complete by 15/03/2026", TODAY), "2026-03-15")

    def test_month_day(self):
        self.assertEqual(extract_due_date("due March 15", TODAY), "2026-03-15")

    def test_day_month(self):
        self.assertEqual(extract_due_date("submit by 15 March", TODAY), "2026-03-15")

    def test_relative_today(self):
        self.assertEqual(extract_due_date("please do today", TODAY), str(TODAY))

    def test_relative_tomorrow(self):
        self.assertEqual(extract_due_date("send it tomorrow", TODAY),
                         str(TODAY + timedelta(days=1)))

    def test_relative_eod(self):
        self.assertEqual(extract_due_date("finish by EOD", TODAY),
                         str(TODAY + timedelta(days=1)))

    def test_weekday_friday(self):
        result = extract_due_date("by Friday", TODAY)
        self.assertEqual(date.fromisoformat(result).weekday(), 4)

    def test_weekday_in_future(self):
        result = extract_due_date("send by Wednesday", TODAY)
        d = date.fromisoformat(result)
        self.assertEqual(d.weekday(), 2)
        self.assertGreater(d, TODAY)

    def test_no_date_returns_empty(self):
        self.assertEqual(extract_due_date("please review this document", TODAY), "")

    def test_eow_is_friday(self):
        result = extract_due_date("done by EOW", TODAY)
        self.assertEqual(date.fromisoformat(result).weekday(), 4)

    def test_next_week(self):
        result = extract_due_date("complete next week", TODAY)
        d = date.fromisoformat(result)
        self.assertGreater(d, TODAY)


class TestNextWeekday(unittest.TestCase):
    def test_next_monday_from_monday(self):
        monday = date(2026, 3, 9)
        result = next_weekday(monday, 0)
        self.assertEqual(result.weekday(), 0)
        self.assertGreater(result, monday)

    def test_next_friday_from_monday(self):
        monday = date(2026, 3, 9)
        result = next_weekday(monday, 4)
        self.assertEqual(result, date(2026, 3, 13))


# ─── PRIORITY SCORING ────────────────────────────────────────────────────────

class TestScorePriority(unittest.TestCase):
    def test_critical(self):
        self.assertEqual(score_priority("this is URGENT please fix"), "critical")

    def test_critical_asap(self):
        self.assertEqual(score_priority("Fix ASAP"), "critical")

    def test_high(self):
        self.assertEqual(score_priority("This is important and must be done"), "high")

    def test_medium_please(self):
        self.assertEqual(score_priority("Please send the report"), "medium")

    def test_medium_followup(self):
        self.assertEqual(score_priority("Follow up on this"), "medium")

    def test_low_default(self):
        self.assertEqual(score_priority("TODO update the readme"), "low")


# ─── TASK EXTRACTION ─────────────────────────────────────────────────────────

class TestExtractTasksFromText(unittest.TestCase):
    def test_detects_todo(self):
        tasks = extract_tasks_from_text("TODO: update the config file", TODAY)
        self.assertEqual(len(tasks), 1)
        self.assertIn("update the config", tasks[0]["task_text"])

    def test_detects_action_required(self):
        tasks = extract_tasks_from_text(
            "Action Required: submit your report by Friday", TODAY)
        self.assertEqual(len(tasks), 1)

    def test_detects_follow_up(self):
        tasks = extract_tasks_from_text("Follow up with the client next week", TODAY)
        self.assertEqual(len(tasks), 1)

    def test_detects_please(self):
        tasks = extract_tasks_from_text("Please review the attached document", TODAY)
        self.assertEqual(len(tasks), 1)

    def test_no_signal_no_task(self):
        tasks = extract_tasks_from_text(
            "The weather in Lagos is warm today", TODAY)
        self.assertEqual(tasks, [])

    def test_multiple_lines(self):
        text = (
            "Hi there,\n"
            "TODO: send invoice\n"
            "No action needed here.\n"
            "ACTION REQUIRED: sign the contract by March 20\n"
        )
        tasks = extract_tasks_from_text(text, TODAY)
        self.assertEqual(len(tasks), 2)

    def test_due_date_extracted(self):
        tasks = extract_tasks_from_text(
            "TODO: finish report by 2026-03-20", TODAY)
        self.assertEqual(tasks[0]["due_date"], "2026-03-20")

    def test_priority_in_task(self):
        tasks = extract_tasks_from_text("URGENT TODO: fix the bug", TODAY)
        self.assertEqual(tasks[0]["priority"], "critical")

    def test_short_line_skipped(self):
        tasks = extract_tasks_from_text("TODO", TODAY)
        self.assertEqual(tasks, [])

    def test_task_text_capped(self):
        long_line = "TODO: " + "x " * 200
        tasks = extract_tasks_from_text(long_line, TODAY)
        self.assertLessEqual(len(tasks[0]["task_text"]), 301)

    def test_empty_text(self):
        self.assertEqual(extract_tasks_from_text("", TODAY), [])

    def test_deadline_keyword(self):
        tasks = extract_tasks_from_text(
            "Deadline: submit proposal by Friday 2026-03-13", TODAY)
        self.assertGreater(len(tasks), 0)


# ─── FORMAT MARKDOWN ─────────────────────────────────────────────────────────

class TestFormatTaskMd(unittest.TestCase):
    def _task(self, priority="medium", due="2026-03-15"):
        return {
            "task_text":   "Please send the quarterly report",
            "priority":    priority,
            "due_date":    due,
            "source_line": "Please send the quarterly report by March 15",
        }

    def test_contains_checkbox(self):
        md = format_task_md(self._task(), "alice@test.com", "Q1 Report", TODAY)
        self.assertIn("- [ ]", md)

    def test_contains_priority_label(self):
        md = format_task_md(self._task(priority="high"), "a@b.com", "Subj", TODAY)
        self.assertIn("[HIGH]", md)

    def test_contains_due_date(self):
        md = format_task_md(self._task(), "a@b.com", "Subj", TODAY)
        self.assertIn("2026-03-15", md)

    def test_no_due_date_omitted(self):
        md = format_task_md(self._task(due=""), "a@b.com", "Subj", TODAY)
        self.assertNotIn("📅", md)

    def test_contains_sender(self):
        md = format_task_md(self._task(), "alice@test.com", "Subj", TODAY)
        self.assertIn("alice@test.com", md)

    def test_priority_emoji_present(self):
        for priority, emoji in PRIORITY_EMOJI.items():
            md = format_task_md(self._task(priority=priority), "a@b.com", "S", TODAY)
            self.assertIn(emoji, md)


# ─── MARKDOWN APPEND ─────────────────────────────────────────────────────────

class TestAppendToMarkdown(unittest.TestCase):
    def _item(self):
        return {
            "task": {
                "task_text": "Review the document",
                "priority":  "medium",
                "due_date":  "2026-03-15",
                "source_line": "Please review",
            },
            "sender":     "alice@test.com",
            "subject":    "Review needed",
            "email_date": TODAY,
        }

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tasks.md"
            append_to_markdown([self._item()], path)
            self.assertTrue(path.exists())

    def test_contains_header_on_first_write(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tasks.md"
            append_to_markdown([self._item()], path)
            content = path.read_text()
            self.assertIn("Email Task Inbox", content)

    def test_task_text_in_file(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tasks.md"
            append_to_markdown([self._item()], path)
            self.assertIn("Review the document", path.read_text())

    def test_appends_on_second_call(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "tasks.md"
            append_to_markdown([self._item()], path)
            item2 = self._item()
            item2["task"]["task_text"] = "Second task"
            append_to_markdown([item2], path)
            content = path.read_text()
            self.assertIn("Review the document", content)
            self.assertIn("Second task", content)


# ─── CSV ────────────────────────────────────────────────────────────────────

class TestCsv(unittest.TestCase):
    def test_init_creates_headers(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "tasks.csv"
            init_csv(p)
            with open(p) as f:
                header = f.readline()
            for field in CSV_FIELDS:
                self.assertIn(field, header)

    def test_append_rows(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "tasks.csv"
            init_csv(p)
            append_csv(p, [{k: f"v{k}" for k in CSV_FIELDS}])
            with open(p) as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)


# ─── PROCESSED STORE ────────────────────────────────────────────────────────

class TestProcessedStore(unittest.TestCase):
    def test_load_empty(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "store.json"
            self.assertEqual(load_processed(p), set())

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "store.json"
            ids = {"<id1>", "<id2>"}
            save_processed(ids, p)
            self.assertEqual(load_processed(p), ids)

    def test_corrupt_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "store.json"
            p.write_text("not valid json")
            self.assertEqual(load_processed(p), set())


if __name__ == "__main__":
    unittest.main(verbosity=2)
