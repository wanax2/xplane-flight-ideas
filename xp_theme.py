"""
xp_theme.py - the look of the app.

One place for colours, fonts and spacing, with a light and a dark palette.
Call  theme = init(root, "light"|"dark")  once, then  theme.set_mode("dark")
to switch. Plain Tk widgets (Listbox, Text, Canvas) aren't styled by ttk, so
register them with  theme.track(widget, "text")  and they'll be recoloured too.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

LIGHT = {
    "name":      "light",
    "bg":        "#eef1f5",   # window behind the panels
    "card":      "#ffffff",   # panels, fields, tables
    "card2":     "#f5f7fa",   # buttons, table headings, striping
    "border":    "#d3dae2",
    "text":      "#1c2430",
    "muted":     "#66727f",
    "accent":    "#1f6fd1",
    "accent_fg": "#ffffff",
    "accent_lo": "#e4eefb",   # selection / hover wash
    "ok":        "#127a4b",
    "warn":      "#a4600a",
    "bad":       "#c0332b",
    "lifr":      "#8b3fb8",
    "field":     "#ffffff",
    "paper":     "#ffffff",   # behind the drawings
}

DARK = {
    "name":      "dark",
    "bg":        "#171b21",
    "card":      "#212730",
    "card2":     "#2a313b",
    "border":    "#39424e",
    "text":      "#e6eaf0",
    "muted":     "#98a3b1",
    "accent":    "#5599e8",
    "accent_fg": "#0d1117",
    "accent_lo": "#2d3d52",
    "ok":        "#3cc98b",
    "warn":      "#e0a33c",
    "bad":       "#f0685d",
    "lifr":      "#c07ae8",
    "field":     "#1a1f27",
    "paper":     "#e9ecf0",
}


class Theme:
    def __init__(self, root, mode="light"):
        self.root = root
        self.style = ttk.Style(root)
        self.tracked = []            # (widget, role)
        self.listeners = []          # callables run after a mode change
        self.c = dict(LIGHT)
        self._fonts()
        self.set_mode(mode, first=True)

    # ------------------------------------------------------------------ fonts
    def _fonts(self):
        fam = "Segoe UI"
        have = set(tkfont.families(self.root))
        for cand in ("Segoe UI", "Inter", "Ubuntu", "DejaVu Sans", "Helvetica Neue", "Arial"):
            if cand in have:
                fam = cand
                break
        mono = "Consolas"
        for cand in ("Cascadia Mono", "Consolas", "DejaVu Sans Mono", "Menlo", "Courier New"):
            if cand in have:
                mono = cand
                break
        self.family, self.mono_family = fam, mono
        self.ui = (fam, 10)
        self.ui_sm = (fam, 9)
        self.ui_bold = (fam, 10, "bold")
        self.head = (fam, 11, "bold")
        self.title = (fam, 13, "bold")
        self.mono = (mono, 10)
        self.line_h = 18
        for name, spec in (("TkDefaultFont", self.ui), ("TkTextFont", self.ui), ("TkMenuFont", self.ui),
                           ("TkHeadingFont", self.ui_bold), ("TkTooltipFont", self.ui_sm)):
            try:
                f = tkfont.nametofont(name)
                f.configure(family=spec[0], size=spec[1],
                            weight="bold" if len(spec) > 2 else "normal")
            except tk.TclError:
                pass
        self.line_h = self.measure_line()

    def measure_line(self):
        """How tall one line of the UI font really is, at whatever DPI this screen uses."""
        try:
            f = tkfont.Font(root=self.root, family=self.family, size=self.ui[1])
            return max(14, int(f.metrics("linespace")))
        except tk.TclError:
            return 18

    @property
    def row_h(self):
        """Table row height: never smaller than the text, or rows overlap."""
        return self.line_h + 8

    @property
    def scale(self):
        """How much bigger this screen's text is than the 96-dpi baseline."""
        return max(1.0, self.line_h / 18.0)

    def px(self, n):
        """A pixel size from the design, scaled for this screen."""
        return int(round(n * self.scale))

    def fit_columns(self, tv, minimum=40):
        """Widen a table's columns for high-dpi screens so headings aren't cut off."""
        if self.scale <= 1.01:
            return tv
        try:
            for col in tv["columns"]:
                w = int(tv.column(col, "width"))
                tv.column(col, width=max(minimum, self.px(w)))
        except tk.TclError:
            pass
        return tv

    # ------------------------------------------------------------------ modes
    def set_mode(self, mode, first=False):
        self.c = dict(DARK if mode == "dark" else LIGHT)
        self.apply()
        if not first:
            self.tracked = [(w, r) for w, r in self.tracked if self._alive(w)]
            for w, role in list(self.tracked):
                self.paint(w, role)
            for fn in list(self.listeners):
                try:
                    fn()
                except tk.TclError:
                    pass

    def toggle(self):
        self.set_mode("light" if self.c["name"] == "dark" else "dark")
        return self.c["name"]

    @property
    def dark(self):
        return self.c["name"] == "dark"

    def on_change(self, fn):
        self.listeners.append(fn)

    # --------------------------------------------------------------- ttk styles
    def apply(self):
        c, s = self.c, self.style
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        self.root.configure(background=c["bg"])

        s.configure(".", background=c["card"], foreground=c["text"], fieldbackground=c["field"],
                    bordercolor=c["border"], darkcolor=c["card"], lightcolor=c["card"],
                    troughcolor=c["card2"], focuscolor=c["accent"], font=self.ui)
        s.configure("TFrame", background=c["card"])
        s.configure("Bg.TFrame", background=c["bg"])
        s.configure("Card.TFrame", background=c["card"], relief="solid", borderwidth=1)
        s.configure("TLabel", background=c["card"], foreground=c["text"])
        s.configure("Bg.TLabel", background=c["bg"], foreground=c["text"])
        s.configure("Head.TLabel", font=self.head, foreground=c["text"], background=c["bg"])
        s.configure("Title.TLabel", font=self.title, foreground=c["text"], background=c["bg"])
        s.configure("Muted.TLabel", foreground=c["muted"], background=c["card"])
        s.configure("MutedBg.TLabel", foreground=c["muted"], background=c["bg"])
        s.configure("Ok.TLabel", foreground=c["ok"], background=c["card"])
        s.configure("Warn.TLabel", foreground=c["warn"], background=c["card"])
        s.configure("Bad.TLabel", foreground=c["bad"], background=c["card"])
        s.configure("Status.TLabel", background=c["bg"], foreground=c["muted"], font=self.ui_sm)

        # group boxes
        s.configure("TLabelframe", background=c["card"], bordercolor=c["border"],
                    relief="solid", borderwidth=1, padding=8)
        s.configure("TLabelframe.Label", background=c["card"], foreground=c["muted"], font=self.ui_bold)

        # buttons
        s.configure("TButton", background=c["card2"], foreground=c["text"], bordercolor=c["border"],
                    relief="flat", padding=(12, 5), font=self.ui, anchor="center", width=0)
        s.map("TButton",
              background=[("disabled", c["card2"]), ("pressed", c["accent_lo"]), ("active", c["accent_lo"])],
              foreground=[("disabled", c["muted"]), ("active", c["accent"])],
              bordercolor=[("active", c["accent"])])
        s.configure("Big.TButton", background=c["accent"], foreground=c["accent_fg"], font=self.ui_bold,
                    padding=(16, 7), bordercolor=c["accent"], width=0)
        s.map("Big.TButton",
              background=[("disabled", c["card2"]), ("pressed", c["accent"]), ("active", c["accent"])],
              foreground=[("disabled", c["muted"]), ("active", c["accent_fg"])])
        s.configure("Quiet.TButton", background=c["card"], foreground=c["muted"], padding=(10, 4), width=0)
        s.map("Quiet.TButton", background=[("active", c["accent_lo"])], foreground=[("active", c["accent"])])
        s.configure("Toolbutton", background=c["card"], padding=(8, 4), relief="flat")
        s.map("Toolbutton", background=[("selected", c["accent_lo"]), ("active", c["accent_lo"])],
              foreground=[("selected", c["accent"])])

        # entries, combos, spinboxes
        for st in ("TEntry", "TCombobox", "TSpinbox"):
            s.configure(st, fieldbackground=c["field"], background=c["card2"], foreground=c["text"],
                        bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"],
                        arrowcolor=c["muted"], insertcolor=c["text"], padding=4, relief="flat")
            s.map(st, bordercolor=[("focus", c["accent"]), ("hover", c["accent"])],
                  fieldbackground=[("readonly", c["card2"]), ("disabled", c["card2"])],
                  foreground=[("disabled", c["muted"])],
                  arrowcolor=[("active", c["accent"])])
        self.root.option_add("*TCombobox*Listbox.background", c["card"])
        self.root.option_add("*TCombobox*Listbox.foreground", c["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", c["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", c["accent_fg"])

        # ticks and radios (clam draws the mark with indicatorforeground on indicatorbackground)
        for st in ("TCheckbutton", "TRadiobutton"):
            s.configure(st, background=c["card"], foreground=c["text"], focuscolor=c["accent"],
                        indicatorbackground=c["field"], indicatorforeground=c["accent"],
                        upperbordercolor=c["border"], lowerbordercolor=c["border"],
                        bordercolor=c["border"], padding=3)
            s.map(st,
                  indicatorbackground=[("disabled", c["card2"]), ("selected", "!disabled", c["field"]),
                                       ("active", c["accent_lo"])],
                  indicatorforeground=[("disabled", c["muted"]), ("selected", c["accent"])],
                  upperbordercolor=[("selected", c["accent"]), ("active", c["accent"])],
                  lowerbordercolor=[("selected", c["accent"]), ("active", c["accent"])],
                  foreground=[("disabled", c["muted"]), ("active", c["accent"])],
                  background=[("active", c["card"])])

        # notebook
        s.configure("TNotebook", background=c["bg"], bordercolor=c["border"], tabmargins=(2, 4, 2, 0))
        s.configure("TNotebook.Tab", background=c["bg"], foreground=c["muted"],
                    padding=(14, 7), font=self.ui, bordercolor=c["border"])
        s.map("TNotebook.Tab",
              background=[("selected", c["card"]), ("active", c["accent_lo"])],
              foreground=[("selected", c["accent"]), ("active", c["text"])],
              font=[("selected", self.ui_bold)])

        # tables
        s.configure("Treeview", background=c["card"], fieldbackground=c["card"], foreground=c["text"],
                    bordercolor=c["border"], rowheight=self.row_h, relief="flat")
        s.map("Treeview", background=[("selected", c["accent_lo"])], foreground=[("selected", c["text"])])
        s.configure("Treeview.Heading", background=c["card2"], foreground=c["muted"], font=self.ui_sm,
                    relief="flat", padding=(6, 5), bordercolor=c["border"])
        s.map("Treeview.Heading", background=[("active", c["accent_lo"])], foreground=[("active", c["accent"])])

        # bars and sliders
        s.configure("TScrollbar", background=c["card2"], troughcolor=c["bg"], bordercolor=c["bg"],
                    arrowcolor=c["muted"], relief="flat", width=12)
        s.map("TScrollbar", background=[("active", c["accent_lo"])])
        s.configure("TScale", background=c["card"], troughcolor=c["card2"], bordercolor=c["border"])
        s.configure("TProgressbar", background=c["accent"], troughcolor=c["card2"], bordercolor=c["border"])
        s.configure("TPanedwindow", background=c["bg"])
        s.configure("Sash", sashthickness=6, gripcount=0, background=c["bg"])
        s.configure("TSeparator", background=c["border"])

    # ------------------------------------------------------- plain tk widgets
    def track(self, widget, role="text"):
        """Keep a plain Tk widget in step with the theme. role: text|list|canvas|window."""
        self.tracked.append((widget, role))
        self.paint(widget, role)
        return widget

    @staticmethod
    def _alive(w):
        try:
            return bool(w.winfo_exists())
        except tk.TclError:
            return False

    def paint(self, w, role):
        c = self.c
        try:
            if role == "text":
                w.configure(background=c["card"], foreground=c["text"], insertbackground=c["text"],
                            selectbackground=c["accent_lo"], selectforeground=c["text"],
                            highlightthickness=1, highlightbackground=c["border"],
                            highlightcolor=c["border"], relief="flat", borderwidth=0, padx=8, pady=6)
            elif role == "list":
                w.configure(background=c["card"], foreground=c["text"],
                            selectbackground=c["accent_lo"], selectforeground=c["text"],
                            highlightthickness=1, highlightbackground=c["border"],
                            highlightcolor=c["border"], relief="flat", borderwidth=0,
                            activestyle="none", font=self.ui)
            elif role == "canvas":
                w.configure(background=c["paper"], highlightthickness=1,
                            highlightbackground=c["border"], relief="flat", borderwidth=0)
            elif role == "window":
                w.configure(background=c["bg"])
        except tk.TclError:
            pass

    def forget(self, widget):
        self.tracked = [(w, r) for w, r in self.tracked if w is not widget]

    # ---------------------------------------------------------------- helpers
    def rules_colour(self, rules):
        return {"VFR": self.c["ok"], "MVFR": self.c["accent"],
                "IFR": self.c["bad"], "LIFR": self.c["lifr"]}.get(rules, self.c["muted"])


def init(root, mode="light"):
    return Theme(root, mode)
