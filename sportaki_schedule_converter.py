#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import re
import tkinter as tk
from tkinter import filedialog, messagebox

# Matches { ... } blocks
BLOCK_RE = re.compile(r"\{([^{}]*)\}", re.DOTALL)

# Extract key:value pairs inside a { ... } block.
PAIR_RE = re.compile(
    r"""
    (?P<key>[a-zA-Z_][a-zA-Z0-9_]*)
    \s*:\s*
    (?P<val>
        '(?:\\'|[^'])*'          |   # single-quoted
        "(?:\\"|[^"])*"          |   # double-quoted
        -?\d+(?:\.\d+)?          |   # number
        \([^)]+\)                |   # (ANAMONH LINK) etc
        [^,}]+                       # fallback token until comma/}
    )
    \s*(?:,|$)
    """,
    re.VERBOSE,
)

def strip_quotes(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and ((s[0] == s[-1] == "'") or (s[0] == s[-1] == '"')):
        return s[1:-1]
    return s

def php_escape(s: str) -> str:
    # PHP single-quote safety
    return s.replace("\\", "\\\\").replace("'", "\\'")

def parse_block(block_text: str) -> dict:
    d = {}
    for m in PAIR_RE.finditer(block_text):
        key = m.group("key").strip()
        val_raw = m.group("val").strip()
        d[key] = strip_quotes(val_raw)
    return d

def to_php_line(ev: dict) -> str:
    # Fallback: competition from comp
    competition = ev.get("competition") or ev.get("comp") or ""

    # Duration as int if possible
    duration_raw = ev.get("duration", "")
    try:
        duration_num = int(float(duration_raw))
        dur_part = f"'duration'=>{duration_num}"
    except Exception:
        dur_part = f"'duration'=>'{php_escape(str(duration_raw))}'"

    date = php_escape(ev.get("date", ""))
    start = php_escape(ev.get("start", ""))
    title = php_escape(ev.get("title", ""))
    sport = php_escape(ev.get("sport", ""))
    competition = php_escape(competition)
    url = php_escape(ev.get("url", ""))

    return (
        f"['date'=>'{date}','start'=>'{start}',{dur_part},"
        f"'title'=>'{title}','sport'=>'{sport}','competition'=>'{competition}','url'=>'{url}'],"
    )

def convert(text: str):
    blocks = BLOCK_RE.findall(text)
    events = []
    pending = []

    for b in blocks:
        ev = parse_block(b)
        if not ev:
            continue
        if "date" not in ev and "title" not in ev:
            continue

        # Pending detection
        url = (ev.get("url") or "").strip()
        if "ANAMONH" in url.upper():
            pending.append({
                "date": ev.get("date",""),
                "start": ev.get("start",""),
                "title": ev.get("title",""),
                "url": url
            })

        # Normalize comp->competition for output logic
        if "competition" not in ev and "comp" in ev:
            ev["competition"] = ev.get("comp","")

        events.append(ev)

    # Sort by date then start (string sort works with YYYY-MM-DD, HH:MM)
    events.sort(key=lambda e: (e.get("date",""), e.get("start","")))

    # Build output with blank line per date
    out_lines = []
    last_date = None
    for ev in events:
        d = ev.get("date","")
        if last_date is not None and d != last_date:
            out_lines.append("")  # blank line between dates
        out_lines.append(to_php_line(ev))
        last_date = d

    return "\n".join(out_lines), pending

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sportaki Schedule Converter")
        self.geometry("1100x700")

        top = tk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)

        tk.Button(top, text="Άνοιγμα input.txt", command=self.open_file).pack(side="left")
        tk.Button(top, text="Convert", command=self.do_convert).pack(side="left", padx=8)
        tk.Button(top, text="Αποθήκευση output.txt", command=self.save_output).pack(side="left")

        tk.Label(top, text="(Paste ή άνοιγμα αρχείου → Convert → Save)").pack(side="left", padx=12)

        mid = tk.PanedWindow(self, orient="horizontal")
        mid.pack(fill="both", expand=True, padx=10, pady=10)

        left_frame = tk.Frame(mid)
        right_frame = tk.Frame(mid)
        mid.add(left_frame, stretch="always")
        mid.add(right_frame, stretch="always")

        tk.Label(left_frame, text="INPUT (paste το schedule εδώ)").pack(anchor="w")
        self.input_text = tk.Text(left_frame, wrap="none", undo=True)
        self.input_text.pack(fill="both", expand=True)

        tk.Label(right_frame, text="OUTPUT (PHP array lines)").pack(anchor="w")
        self.output_text = tk.Text(right_frame, wrap="none", undo=True)
        self.output_text.pack(fill="both", expand=True)

        bottom = tk.Frame(self)
        bottom.pack(fill="both", padx=10, pady=(0,10))

        tk.Label(bottom, text="Εκκρεμότητες (ANAMONH LINK)").pack(anchor="w")
        self.pending_text = tk.Text(bottom, height=8, wrap="none")
        self.pending_text.pack(fill="both", expand=False)

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Διάλεξε input αρχείο",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                data = f.read()
            self.input_text.delete("1.0", "end")
            self.input_text.insert("1.0", data)
        except Exception as e:
            messagebox.showerror("Σφάλμα", str(e))

    def do_convert(self):
        inp = self.input_text.get("1.0", "end").strip()
        if not inp:
            messagebox.showwarning("Κενό", "Δεν υπάρχει input.")
            return
        out, pending = convert(inp)

        if not out.strip():
            messagebox.showwarning("Δεν βρέθηκαν blocks", "Δεν βρέθηκαν entries της μορφής { ... }.")
            return

        self.output_text.delete("1.0", "end")
        self.output_text.insert("1.0", out)

        self.pending_text.delete("1.0", "end")
        if pending:
            lines = []
            for p in pending:
                lines.append(f"- {p['date']} {p['start']} | {p['title']} | {p['url']}")
            self.pending_text.insert("1.0", "\n".join(lines))
        else:
            self.pending_text.insert("1.0", "— Καμία εκκρεμότητα —")

    def save_output(self):
        data = self.output_text.get("1.0", "end").strip()
        if not data:
            messagebox.showwarning("Κενό", "Δεν υπάρχει output για αποθήκευση.")
            return
        path = filedialog.asksaveasfilename(
            title="Αποθήκευση output",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(data + "\n")
            messagebox.showinfo("ΟΚ", f"Αποθηκεύτηκε:\n{path}")
        except Exception as e:
            messagebox.showerror("Σφάλμα", str(e))

if __name__ == "__main__":
    App().mainloop()
