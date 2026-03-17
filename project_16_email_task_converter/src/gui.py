"""
gui.py
======
Project 16: Email-to-Task Converter — Tkinter GUI
--------------------------------------------------
A minimal desktop GUI that wraps task_converter.py.
Build to .exe with:  pyinstaller --onefile --noconsole gui.py

Layout:
  ┌─────────────────────────────────────┐
  │  📧 Email-to-Task Converter         │
  ├─────────────────────────────────────┤
  │  Gmail address  [____________]      │
  │  App Password   [____________]      │
  │  Since date     [____________]      │
  │  Output file    [____________] [..] │
  ├─────────────────────────────────────┤
  │  [  🔍 Dry Run  ]  [  ✅ Extract  ] │
  ├─────────────────────────────────────┤
  │  Log output...                      │
  │  (scrollable text area)             │
  └─────────────────────────────────────┘
"""

import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
from pathlib import Path
from datetime import date
from io import StringIO

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.task_converter import extract_tasks_from_text, append_to_markdown
sys.stdout.reconfigure(encoding="utf-8")

class TaskConverterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("📧 Email-to-Task Converter")
        self.geometry("620x520")
        self.resizable(True, True)
        self.configure(bg="#f0f0f0")
        self._build_ui()

    def _build_ui(self):
        PAD = {"padx": 10, "pady": 4}

        # ── Header ──────────────────────────────────────────────────────────
        hdr = tk.Frame(self, bg="#1e3a5f")
        hdr.pack(fill="x")
        tk.Label(hdr, text="📧  Email-to-Task Converter",
                 bg="#1e3a5f", fg="white",
                 font=("Segoe UI", 13, "bold"),
                 pady=10).pack(side="left", padx=14)

        # ── Form ────────────────────────────────────────────────────────────
        frm = tk.LabelFrame(self, text=" Connection ", bg="#f0f0f0",
                            font=("Segoe UI", 9))
        frm.pack(fill="x", **PAD)

        self._field(frm, "Gmail address:",  "email_var")
        self._field(frm, "App Password:",   "pass_var",  show="*")
        self._field(frm, "Since date:",     "since_var", placeholder="YYYY-MM-DD (optional)")

        # Output path row
        out_row = tk.Frame(frm, bg="#f0f0f0")
        out_row.pack(fill="x", pady=2)
        tk.Label(out_row, text="Output .md:", bg="#f0f0f0",
                 width=14, anchor="e").pack(side="left")
        self.output_var = tk.StringVar(value="output/tasks.md")
        tk.Entry(out_row, textvariable=self.output_var, width=36).pack(side="left", padx=4)
        tk.Button(out_row, text="…", width=3,
                  command=self._browse_output).pack(side="left")

        # ── Buttons ─────────────────────────────────────────────────────────
        btn_row = tk.Frame(self, bg="#f0f0f0")
        btn_row.pack(pady=8)
        tk.Button(btn_row, text="🔍  Dry Run",  width=14, bg="#3b82f6", fg="white",
                  font=("Segoe UI", 9, "bold"),
                  command=lambda: self._run(dry_run=True)).pack(side="left", padx=6)
        tk.Button(btn_row, text="✅  Extract",  width=14, bg="#16a34a", fg="white",
                  font=("Segoe UI", 9, "bold"),
                  command=lambda: self._run(dry_run=False)).pack(side="left", padx=6)
        tk.Button(btn_row, text="🧹  Clear Log", width=12,
                  command=self._clear_log).pack(side="left", padx=6)

        # ── Log area ────────────────────────────────────────────────────────
        log_frame = tk.LabelFrame(self, text=" Output Log ", bg="#f0f0f0",
                                  font=("Segoe UI", 9))
        log_frame.pack(fill="both", expand=True, **PAD)
        self.log = scrolledtext.ScrolledText(
            log_frame, height=12, state="disabled",
            font=("Courier New", 9), bg="#1e1e1e", fg="#d4d4d4",
            insertbackground="white"
        )
        self.log.pack(fill="both", expand=True, padx=4, pady=4)

        # Status bar
        self.status_var = tk.StringVar(value="Ready.")
        tk.Label(self, textvariable=self.status_var, bg="#e5e7eb",
                 anchor="w", font=("Segoe UI", 8)).pack(fill="x")

    def _field(self, parent, label, var_name, show="", placeholder=""):
        row = tk.Frame(parent, bg="#f0f0f0")
        row.pack(fill="x", pady=2)
        tk.Label(row, text=label, bg="#f0f0f0",
                 width=14, anchor="e").pack(side="left")
        var = tk.StringVar(value=placeholder if placeholder else "")
        setattr(self, var_name, var)
        entry = tk.Entry(row, textvariable=var, width=40, show=show)
        entry.pack(side="left", padx=4)
        if placeholder:
            entry.config(fg="grey")
            def on_focus_in(e, v=var, ph=placeholder, w=entry):
                if v.get() == ph:
                    v.set("")
                    w.config(fg="black")
            def on_focus_out(e, v=var, ph=placeholder, w=entry):
                if not v.get():
                    v.set(ph)
                    w.config(fg="grey")
            entry.bind("<FocusIn>",  on_focus_in)
            entry.bind("<FocusOut>", on_focus_out)

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("All files", "*.*")],
            initialfile="tasks.md"
        )
        if path:
            self.output_var.set(path)

    def _log(self, text: str):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    def _clear_log(self):
        self.log.config(state="normal")
        self.log.delete("1.0", "end")
        self.log.config(state="disabled")

    def _run(self, dry_run: bool):
        user     = self.email_var.get().strip()
        password = self.pass_var.get().strip()

        if not user or not password:
            messagebox.showwarning("Missing fields",
                                   "Gmail address and App Password are required.")
            return

        since_raw = self.since_var.get().strip()
        since     = "" if since_raw in ("YYYY-MM-DD (optional)", "") else since_raw
        output_md = Path(self.output_var.get().strip() or "output/tasks.md")

        mode = "DRY RUN" if dry_run else "LIVE EXTRACT"
        self._log(f"\n── {mode} ──────────────────────")
        self.status_var.set(f"Running {mode}…")
        self.update()

        def worker():
            try:
                # Import here to keep GUI responsive
                from src.task_converter import run_converter

                # Redirect stdout to log widget
                import builtins
                original_print = builtins.print

                def gui_print(*args, **kwargs):
                    text = " ".join(str(a) for a in args)
                    self.after(0, self._log, text)

                builtins.print = gui_print
                result = run_converter(
                    user       = user,
                    password   = password,
                    output_md  = output_md,
                    output_dir = output_md.parent,
                    since      = since,
                    dry_run    = dry_run,
                )
                builtins.print = original_print

                summary = (f"Done — {result['tasks_extracted']} tasks from "
                           f"{result['with_tasks']} emails")
                self.after(0, self.status_var.set, summary)

                if not dry_run and result["tasks_extracted"] > 0:
                    self.after(0, messagebox.showinfo, "Complete",
                               f"{result['tasks_extracted']} tasks written to:\n{output_md}")

            except Exception as e:
                self.after(0, self._log, f"  ✗ Error: {e}")
                self.after(0, self.status_var.set, "Error — check log.")

        threading.Thread(target=worker, daemon=True).start()


def main():
    app = TaskConverterApp()
    app.mainloop()


if __name__ == "__main__":
    main()
