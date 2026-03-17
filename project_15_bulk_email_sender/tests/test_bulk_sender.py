"""
test_bulk_sender.py — Project 15 unit tests (stdlib unittest, fully offline)
Run: python -m unittest tests.test_bulk_sender -v
"""
import csv
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

from src.bulk_sender import (
    load_contacts, _valid_email,
    load_template, extract_subject, render, build_context,
    build_html_body, build_message,
    init_report, append_report, load_already_sent,
    save_preview,
    run_bulk_sender,
    REPORT_FIELDS,
)


# ─── HELPERS ─────────────────────────────────────────────────────────────────

def write_contacts(tmp, rows, fields=None):
    fields = fields or ["email","first_name","last_name","company","role","city"]
    p = Path(tmp) / "contacts.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return p


def write_template(tmp, content, name="tpl.txt"):
    p = Path(tmp) / name
    p.write_text(content, encoding="utf-8")
    return p


SAMPLE_CONTACTS = [
    {"email": "alice@test.com", "first_name": "Alice", "last_name": "Smith",
     "company": "ACME", "role": "Engineer", "city": "London"},
    {"email": "bob@test.com",   "first_name": "Bob",   "last_name": "Jones",
     "company": "Beta", "role": "Manager",  "city": "Lagos"},
]


# ─── LOAD CONTACTS ───────────────────────────────────────────────────────────

class TestLoadContacts(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp()

    def test_loads_valid_rows(self):
        p = write_contacts(self.tmp, SAMPLE_CONTACTS)
        contacts = load_contacts(p)
        self.assertEqual(len(contacts), 2)

    def test_skips_missing_email(self):
        rows = [{"email": "", "first_name": "X", "last_name": "",
                 "company": "", "role": "", "city": ""}]
        p = write_contacts(self.tmp, rows)
        self.assertEqual(load_contacts(p), [])

    def test_skips_invalid_email(self):
        rows = [{"email": "not-an-email", "first_name": "X",
                 "last_name": "", "company": "", "role": "", "city": ""}]
        p = write_contacts(self.tmp, rows)
        self.assertEqual(load_contacts(p), [])

    def test_keys_lowercased(self):
        p = write_contacts(self.tmp, SAMPLE_CONTACTS)
        contacts = load_contacts(p)
        self.assertIn("email", contacts[0])
        self.assertIn("first_name", contacts[0])

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_contacts(Path(self.tmp) / "ghost.csv")

    def test_values_stripped(self):
        rows = [{"email": "  alice@test.com  ", "first_name": " Alice ",
                 "last_name": "", "company": "", "role": "", "city": ""}]
        p = write_contacts(self.tmp, rows)
        contacts = load_contacts(p)
        self.assertEqual(contacts[0]["email"], "alice@test.com")
        self.assertEqual(contacts[0]["first_name"], "Alice")


# ─── EMAIL VALIDATION ────────────────────────────────────────────────────────

class TestValidEmail(unittest.TestCase):
    def test_valid(self):
        for addr in ("a@b.com", "user.name+tag@sub.domain.io", "x@y.ng"):
            self.assertTrue(_valid_email(addr), addr)

    def test_invalid(self):
        for addr in ("", "nope", "@nope.com", "nope@", "no spaces@x.com"):
            self.assertFalse(_valid_email(addr), addr)


# ─── TEMPLATE LOADING ────────────────────────────────────────────────────────

class TestLoadTemplate(unittest.TestCase):
    def test_loads_content(self):
        with tempfile.TemporaryDirectory() as td:
            p = write_template(td, "Hello {{name}}")
            self.assertEqual(load_template(p), "Hello {{name}}")

    def test_missing_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_template(Path("/ghost/template.txt"))


# ─── EXTRACT SUBJECT ─────────────────────────────────────────────────────────

class TestExtractSubject(unittest.TestCase):
    def test_extracts_subject_line(self):
        s, b = extract_subject("Subject: Hello World\n\nBody here")
        self.assertEqual(s, "Hello World")
        self.assertIn("Body here", b)

    def test_no_subject_uses_default(self):
        s, b = extract_subject("Just a body")
        self.assertEqual(s, "(no subject)")
        self.assertIn("Just a body", b)

    def test_case_insensitive(self):
        s, b = extract_subject("SUBJECT: Test\n\nbody")
        self.assertEqual(s, "Test")

    def test_subject_with_template_var(self):
        s, b = extract_subject("Subject: Hi {{first_name}}\n\nBody")
        self.assertIn("{{first_name}}", s)


# ─── RENDER ──────────────────────────────────────────────────────────────────

class TestRender(unittest.TestCase):
    def test_replaces_single_var(self):
        self.assertEqual(render("Hi {{name}}", {"name": "Alice"}), "Hi Alice")

    def test_replaces_multiple_vars(self):
        result = render("{{a}} and {{b}}", {"a": "X", "b": "Y"})
        self.assertEqual(result, "X and Y")

    def test_unknown_var_preserved(self):
        result = render("Hi {{ghost}}", {})
        self.assertIn("{{ghost}}", result)

    def test_repeated_var(self):
        result = render("{{x}} {{x}}", {"x": "yes"})
        self.assertEqual(result, "yes yes")

    def test_empty_template(self):
        self.assertEqual(render("", {"a": "b"}), "")


# ─── BUILD CONTEXT ───────────────────────────────────────────────────────────

class TestBuildContext(unittest.TestCase):
    def test_preserves_contact_fields(self):
        ctx = build_context({"email": "a@b.com", "first_name": "Alice",
                             "company": "ACME", "role": "Eng", "city": "X",
                             "last_name": "Smith"})
        self.assertEqual(ctx["company"], "ACME")
        self.assertEqual(ctx["role"], "Eng")

    def test_derives_first_name_from_name(self):
        ctx = build_context({"email": "a@b.com", "name": "Alice Smith",
                             "last_name": ""})
        self.assertEqual(ctx["first_name"], "Alice")
        self.assertEqual(ctx["last_name"],  "Smith")

    def test_fallback_first_name_from_email(self):
        ctx = build_context({"email": "charlie@test.com"})
        self.assertEqual(ctx["first_name"], "charlie")

    def test_full_name_derived(self):
        ctx = build_context({"email": "a@b.com", "first_name": "Alice",
                             "last_name": "Smith"})
        self.assertEqual(ctx["full_name"], "Alice Smith")

    def test_year_present(self):
        from datetime import datetime
        ctx = build_context({"email": "a@b.com"})
        self.assertEqual(ctx["year"], str(datetime.now().year))


# ─── HTML BODY ───────────────────────────────────────────────────────────────

class TestBuildHtmlBody(unittest.TestCase):
    def test_returns_html_string(self):
        html = build_html_body("Hello world")
        self.assertIn("<html>", html)
        self.assertIn("Hello world", html)

    def test_empty_lines_become_br(self):
        html = build_html_body("Line one\n\nLine two")
        self.assertIn("<br>", html)


# ─── BUILD MESSAGE ───────────────────────────────────────────────────────────

class TestBuildMessage(unittest.TestCase):
    def test_basic_fields(self):
        msg = build_message("Subject", "Body", "from@x.com", "to@x.com")
        self.assertEqual(msg["Subject"], "Subject")
        self.assertEqual(msg["From"],    "from@x.com")
        self.assertEqual(msg["To"],      "to@x.com")

    def test_has_alternative_part(self):
        msg = build_message("S", "B", "f@x.com", "t@x.com")
        types = [p.get_content_type() for p in msg.walk()]
        self.assertIn("text/plain", types)
        self.assertIn("text/html",  types)

    def test_attachment_added(self):
        with tempfile.TemporaryDirectory() as td:
            att = Path(td) / "file.txt"
            att.write_text("data")
            msg = build_message("S", "B", "f@x.com", "t@x.com", att)
            names = [p.get_filename() for p in msg.walk()]
            self.assertIn("file.txt", names)

    def test_missing_attachment_ignored(self):
        msg = build_message("S", "B", "f@x.com", "t@x.com",
                            Path("/nonexistent/file.pdf"))
        # Should not raise; no attachment added
        names = [p.get_filename() for p in msg.walk() if p.get_filename()]
        self.assertEqual(names, [])


# ─── REPORT ──────────────────────────────────────────────────────────────────

class TestReport(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp()

    def _path(self): return Path(self.tmp) / "report.csv"

    def test_init_creates_headers(self):
        init_report(self._path())
        with open(self._path()) as f:
            header = f.readline()
        for field in REPORT_FIELDS:
            self.assertIn(field, header)

    def test_append_row(self):
        p = self._path()
        init_report(p)
        append_report(p, {k: f"v_{k}" for k in REPORT_FIELDS})
        with open(p) as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)

    def test_load_already_sent(self):
        p = self._path()
        init_report(p)
        append_report(p, {**{k: "" for k in REPORT_FIELDS},
                          "email": "alice@test.com", "status": "sent"})
        append_report(p, {**{k: "" for k in REPORT_FIELDS},
                          "email": "bob@test.com",   "status": "failed"})
        sent = load_already_sent(p)
        self.assertIn("alice@test.com", sent)
        self.assertNotIn("bob@test.com", sent)

    def test_init_idempotent(self):
        p = self._path()
        init_report(p)
        init_report(p)
        with open(p) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)


# ─── SAVE PREVIEW ────────────────────────────────────────────────────────────

class TestSavePreview(unittest.TestCase):
    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as td:
            contact = {"email": "alice@test.com", "first_name": "Alice"}
            path = save_preview(Path(td), contact, "Test Subject", "Hello Alice", 1)
            self.assertTrue(path.exists())

    def test_content_correct(self):
        with tempfile.TemporaryDirectory() as td:
            contact = {"email": "alice@test.com", "first_name": "Alice"}
            path = save_preview(Path(td), contact, "My Subject", "Body text", 1)
            content = path.read_text()
            self.assertIn("alice@test.com", content)
            self.assertIn("My Subject",     content)
            self.assertIn("Body text",      content)


# ─── RUN BULK SENDER (INTEGRATION) ──────────────────────────────────────────

class TestRunBulkSender(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp()

    def test_dry_run_counts_all(self):
        cp = write_contacts(self.tmp, SAMPLE_CONTACTS)
        tp = write_template(self.tmp,
            "Subject: Hi {{first_name}}\n\nHello {{first_name}}, welcome to {{company}}!")
        result = run_bulk_sender(cp, tp, output_dir=Path(self.tmp), dry_run=True)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["sent"],  2)

    def test_skips_already_sent(self):
        cp = write_contacts(self.tmp, SAMPLE_CONTACTS)
        tp = write_template(self.tmp, "Subject: Hi\n\nHello {{first_name}}")
        # Pre-populate report with alice already sent
        report = Path(self.tmp) / "delivery_report.csv"
        init_report(report)
        append_report(report, {**{k: "" for k in REPORT_FIELDS},
                               "email": "alice@test.com", "status": "sent"})
        result = run_bulk_sender(cp, tp, output_dir=Path(self.tmp),
                                 dry_run=False, from_addr="", password="",
                                 resume=True)
        self.assertEqual(result["skipped"], 1)

    def test_preview_mode_stops_early(self):
        contacts = SAMPLE_CONTACTS + [
            {"email": "charlie@test.com", "first_name": "Charlie",
             "last_name": "", "company": "X", "role": "Dev", "city": "X"},
        ]
        cp = write_contacts(self.tmp, contacts)
        tp = write_template(self.tmp, "Subject: Hi\n\nHello {{first_name}}")
        result = run_bulk_sender(cp, tp, output_dir=Path(self.tmp),
                                 dry_run=False, preview_n=2)
        self.assertEqual(result["previewed"], 2)

    def test_invalid_contacts_filtered(self):
        rows = SAMPLE_CONTACTS + [
            {"email": "", "first_name": "Ghost",
             "last_name": "", "company": "", "role": "", "city": ""},
        ]
        cp = write_contacts(self.tmp, rows)
        tp = write_template(self.tmp, "Subject: Hi\n\nHi {{first_name}}")
        result = run_bulk_sender(cp, tp, output_dir=Path(self.tmp), dry_run=True)
        self.assertEqual(result["total"], 2)   # ghost filtered out


if __name__ == "__main__":
    unittest.main(verbosity=2)
