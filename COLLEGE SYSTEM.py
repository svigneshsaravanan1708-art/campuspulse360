"""
CAMPUSPULSE 360 — Standalone Windows Desktop Prototype  (Sky-blue & white theme)
Python: 3.10+ recommended | Libraries: Tkinter + SQLite (both included with Python)

Run:
    python CampusPulse360.py

First run:
    The program asks you to create the administrator username and password.
    Use that account to sign in afterwards. There is no built-in demo login.

Pictures:
    The campus illustration (building, trees, drifting clouds, moving campus bus)
    is drawn by the program itself, so no image files are needed.

This is a college-project prototype:
use fictional/sample data until your institution authorizes real data collection.
"""
import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
import hashlib
import math
import os
from datetime import datetime

APP_NAME = "CAMPUSPULSE 360"
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "campuspulse360.db")

# ---- Sky-blue & white palette ------------------------------------------------
BG = "#F3F9FE"        # page background (soft white-blue)
PANEL = "#FFFFFF"     # cards
PANEL2 = "#E8F4FD"    # light sky tint
FIELD = "#EEF7FD"     # input fields
BLUE = "#1E9BEA"      # sky blue (primary)
CYAN = "#0B6FB8"      # deeper blue for headings
TEAL = "#12A8B8"
TEXT = "#12304A"
MUTED = "#5E7D96"
GREEN = "#17A765"
ORANGE = "#F08C1E"
RED = "#E5484D"
BORDER = "#CFE5F5"
SIDEBAR = "#1A93E0"
SIDE_HOVER = "#3AA8EE"
SIDE_SUB = "#D7EFFD"
SIDE_LINE = "#62B8F0"
SKY_TOP = "#6CC3F5"
SKY_BOTTOM = "#E4F4FE"
DARK = "#0B3558"
SUB = "#245D8A"
BADGE_COLORS = [BLUE, GREEN, ORANGE, "#8B6CF0", TEAL, "#E5649A", "#5B7CFA", "#F0B429"]

MODULES = {
    "Overview": ["Overview"],
    "Students": ["Student ID", "Name", "Department", "Year", "Email", "Phone"],
    "Faculty": ["Faculty ID", "Name", "Department", "Designation", "Email"],
    "Attendance": ["Student ID", "Name", "Department", "Date", "Status"],
    "Academics": ["Student ID", "Name", "Subject", "Internal Mark", "Semester"],
    "Transport": ["Vehicle ID", "Route", "Driver", "Capacity", "Status"],
    "Campus Assets": ["Asset ID", "Asset Name", "Location", "Condition", "Last Service"],
    "Maintenance": ["Ticket ID", "Asset", "Location", "Issue", "Priority", "Status"],
    "Announcements": ["Title", "Audience", "Message", "Date"],
}
MODULE_BLURB = {
    "Students": "Profiles & contacts", "Faculty": "Staff directory",
    "Attendance": "Daily presence logs", "Academics": "Marks & semesters",
    "Transport": "Vehicles & routes", "Campus Assets": "Buildings & equipment",
    "Maintenance": "Tickets & repairs", "Announcements": "Notices & updates",
}
ROLE_ACCESS = {
    "Principal": list(MODULES.keys()),
    "Admin": list(MODULES.keys()),
    "HOD": ["Overview", "Students", "Faculty", "Attendance", "Academics", "Announcements"],
    "Faculty": ["Overview", "Students", "Attendance", "Academics", "Announcements"],
    "Transport Admin": ["Overview", "Transport", "Maintenance", "Announcements"],
    "Campus Admin": ["Overview", "Campus Assets", "Maintenance", "Announcements"],
    "Student": ["Overview", "Academics", "Announcements"],
}

# ---- Department separation -------------------------------------------------
# Edit this list to match your college's departments.
DEPARTMENTS = ["Computer Science", "Information Technology", "Electronics & Communication",
               "Electrical & Electronics", "Mechanical", "Civil",
               "Artificial Intelligence & Data Science", "Management Studies"]
ALL_DEPT = "All"                   # stored value = not tied to one department
ALL_DEPT_LABEL = "All Departments"  # shown in the screen
UNASSIGNED = "(unassigned)"
# These roles see every department. HOD / Faculty / Student see only their own.
GLOBAL_ROLES = {"Principal", "Admin", "Transport Admin", "Campus Admin"}
# Modules whose records belong to a department.
DEPT_MODULES = {"Students", "Faculty", "Attendance", "Academics", "Announcements"}

def match_department(text):
    text = (text or "").strip()
    for d in DEPARTMENTS:
        if d.lower() == text.lower():
            return d
    return text or ALL_DEPT

def digest(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def mix(a, b, t):
    """Blend colour a towards colour b (t = 0..1). Used for gradients and smooth hover fades."""
    t = max(0.0, min(1.0, t))
    return "#%02x%02x%02x" % tuple(int(round(x + (y - x) * t)) for x, y in zip(_rgb(a), _rgb(b)))

class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE)
        self.conn.row_factory = sqlite3.Row
        self.create()

    def create(self):
        cur = self.conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, role TEXT NOT NULL, display_name TEXT NOT NULL)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS records(
            id INTEGER PRIMARY KEY AUTOINCREMENT, module TEXT NOT NULL,
            data TEXT NOT NULL, created_at TEXT NOT NULL)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS audit(
            id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, action TEXT,
            detail TEXT, created_at TEXT)""")
        # Department columns (added safely to databases created by the older version)
        self.add_column("users", "department", "TEXT NOT NULL DEFAULT 'All'")
        if self.add_column("records", "department", "TEXT NOT NULL DEFAULT 'All'"):
            self.backfill_record_departments()
        self.conn.commit()

    def needs_setup(self):
        """True on first run, or while the old built-in admin/admin123 demo account still exists."""
        if self.conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
            return True
        return self.has_demo_account()

    def has_demo_account(self):
        return self.conn.execute("SELECT 1 FROM users WHERE username='admin' AND password_hash=?",
                                 (digest("admin123"),)).fetchone() is not None

    def remove_demo_account(self):
        self.conn.execute("DELETE FROM users WHERE username='admin' AND password_hash=?",
                          (digest("admin123"),))
        self.conn.commit()

    def add_column(self, table, column, definition):
        cols = [r["name"] for r in self.conn.execute("PRAGMA table_info(" + table + ")")]
        if column in cols:
            return False
        self.conn.execute("ALTER TABLE " + table + " ADD COLUMN " + column + " " + definition)
        self.conn.commit()
        return True

    def backfill_record_departments(self):
        """One-time: tag existing records with a department using their own data."""
        student_dept = {}
        for r in self.conn.execute("SELECT data FROM records WHERE module='Students'").fetchall():
            v = r["data"].split("|||")
            if len(v) > 2:
                student_dept[v[0].strip().lower()] = match_department(v[2])
        for r in self.conn.execute("SELECT id,module,data FROM records").fetchall():
            v = r["data"].split("|||")
            dept = ALL_DEPT
            if r["module"] in ("Students", "Faculty", "Attendance") and len(v) > 2:
                dept = match_department(v[2])
            elif r["module"] == "Academics" and v:
                dept = student_dept.get(v[0].strip().lower(), ALL_DEPT)
            if dept != ALL_DEPT:
                self.conn.execute("UPDATE records SET department=? WHERE id=?", (dept, r["id"]))
        self.conn.commit()

    def log(self, username, action, detail=""):
        self.conn.execute("INSERT INTO audit(username,action,detail,created_at) VALUES(?,?,?,?)",
                          (username, action, detail, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.conn.commit()

    def recent_activity(self, username=None, limit=5):
        if username:
            return self.conn.execute("SELECT * FROM audit WHERE username=? ORDER BY id DESC LIMIT ?",
                                     (username, limit)).fetchall()
        return self.conn.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()

    def authenticate(self, username, password):
        return self.conn.execute("SELECT * FROM users WHERE username=? AND password_hash=?",
                                 (username.strip(), digest(password))).fetchone()

    def add_user(self, username, password, role, display_name, department=ALL_DEPT):
        self.conn.execute("INSERT INTO users(username,password_hash,role,display_name,department) VALUES(?,?,?,?,?)",
                          (username.strip(), digest(password), role, display_name.strip(), department))
        self.conn.commit()

    def users(self):
        return self.conn.execute("SELECT username,role,display_name,department FROM users ORDER BY username").fetchall()

    def set_user_department(self, username, department):
        self.conn.execute("UPDATE users SET department=? WHERE username=?", (department, username))
        self.conn.commit()

    def _dept_clause(self, module, department):
        # department=None means "no restriction". Records marked 'All' (e.g. college-wide
        # announcements) stay visible to everyone.
        if department and module in DEPT_MODULES:
            return " AND (department=? OR department='All')", [department]
        return "", []

    def rows(self, module, department=None):
        extra, params = self._dept_clause(module, department)
        return self.conn.execute("SELECT * FROM records WHERE module=?" + extra + " ORDER BY id DESC",
                                 [module] + params).fetchall()

    def add_record(self, module, values, department=ALL_DEPT):
        self.conn.execute("INSERT INTO records(module,data,created_at,department) VALUES(?,?,?,?)",
                          (module, "|||".join(values), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), department))
        self.conn.commit()

    def delete_record(self, record_id, department=None):
        if department:
            self.conn.execute("DELETE FROM records WHERE id=? AND department=?", (record_id, department))
        else:
            self.conn.execute("DELETE FROM records WHERE id=?", (record_id,))
        self.conn.commit()

    def count(self, module, department=None):
        extra, params = self._dept_clause(module, department)
        return self.conn.execute("SELECT COUNT(*) FROM records WHERE module=?" + extra,
                                 [module] + params).fetchone()[0]

class ScrollFrame(tk.Frame):
    """A frame with a vertical scrollbar on its right side. Put widgets in `.inner`.
    When the content is shorter than the window it stretches to fill it, so
    expanding tables still work; when it is taller, the scrollbar appears in use."""
    def __init__(self, parent, bg, bar=True):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0, yscrollincrement=24)
        self.canvas.scroll_target = True
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)
        if bar:
            self.vbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", self._fit)
        self.canvas.bind("<Configure>", self._fit)

    def _fit(self, event=None):
        w, h = self.canvas.winfo_width(), self.canvas.winfo_height()
        self.canvas.itemconfigure(self.win, width=w, height=max(h, self.inner.winfo_reqheight()))
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def to_top(self):
        self.canvas.yview_moveto(0)

class CampusScene(tk.Canvas):
    """Campus illustration drawn with code: sky gradient, sun, birds, drifting clouds, hills,
    the main hall with dome and clock, trees, a floating graduation cap and a moving campus bus.
    No image files needed."""
    CLOUDS = [(0.08, 0.20, 1.0, 0.40), (0.42, 0.12, 0.7, 0.25),
              (0.72, 0.34, 1.2, 0.32), (0.26, 0.50, 0.6, 0.20)]

    def __init__(self, parent, height=230, cx_ratio=0.7, texts=(), ecg_y=None):
        super().__init__(parent, height=height, bg=SKY_BOTTOM, highlightthickness=0, bd=0)
        self.cx_ratio = cx_ratio
        self.texts = texts
        self.ecg_y = ecg_y
        self.cloud_x = []
        self.bus_x = None
        self.phase = 0.0
        self.bind("<Configure>", self.draw)
        self.after(60, self.tick)

    def draw(self, event=None):
        w = max(self.winfo_width(), 200)
        h = max(self.winfo_height(), 120)
        self.delete("all")
        s = min(h / 230.0, w / 900.0)
        gy = h - max(34, int(h * 0.13))          # ground line
        cx = int(w * self.cx_ratio)               # centre of the main hall
        S = lambda v: v * s

        # sky gradient
        band = 3
        for y in range(0, gy + band, band):
            self.create_rectangle(0, y, w, y + band, outline="",
                                  fill=mix(SKY_TOP, SKY_BOTTOM, y / max(gy, 1)))
        # sun with soft glow
        sx, sy = int(w * 0.90), int(gy * 0.32)
        for r, col in ((54, "#EAF7FF"), (42, "#FFF5CF"), (30, "#FFE58F")):
            self.create_oval(sx - S(r), sy - S(r), sx + S(r), sy + S(r), fill=col, outline="")
        # birds
        for bx, by in ((0.80, 0.18), (0.84, 0.26), (0.77, 0.27)):
            x, y = bx * w, by * gy
            self.create_line(x - 7, y, x - 3.5, y - 4, x, y, x + 3.5, y - 4, x + 7, y,
                             fill="#5F8FB0", width=2, smooth=True)
        # clouds (animated)
        self.cloud_x = []
        for i, (xr, yr, sc, _sp) in enumerate(self.CLOUDS):
            x, y, k = xr * w, yr * gy, sc * max(s, 0.6)
            for dx, dy, rx, ry in ((0, 0, 42, 14), (-26, 6, 26, 10), (24, 5, 30, 11), (-4, -10, 24, 12)):
                self.create_oval(x + (dx - rx) * k, y + (dy - ry) * k, x + (dx + rx) * k, y + (dy + ry) * k,
                                 fill="#FFFFFF", outline="", tags=("cloud%d" % i,))
            self.cloud_x.append(x)
        # rolling hills
        for amp, off, col, base in ((18, 0.0, "#A9D8F5", 38), (12, 1.7, "#D2EBFB", 20)):
            pts = [0, gy]
            for x in range(0, w + 20, 20):
                pts += [x, gy - S(base) - S(amp) * math.sin(x / S(110) + off)]
            pts += [w, gy]
            self.create_polygon(pts, fill=col, outline="")
        # ground
        self.create_rectangle(0, gy, w, h, fill="#E4F2FC", outline="")
        self.create_line(0, gy, w, gy, fill="#C4DFF1", width=2)

        # trees
        def tree(x, k):
            self.create_rectangle(x - S(3) * k, gy - S(24) * k, x + S(3) * k, gy, fill="#7FA9C5", outline="")
            self.create_oval(x - S(17) * k, gy - S(56) * k, x + S(17) * k, gy - S(18) * k, fill="#5CC59A", outline="")
            self.create_oval(x - S(10) * k, gy - S(60) * k, x + S(14) * k, gy - S(34) * k, fill="#7ED9B3", outline="")
        for tx, k in ((-228, 1.0), (-268, 0.8), (226, 1.0), (266, 0.8)):
            tree(cx + S(tx), k)

        # main hall
        edge = "#9CC9E6"
        for side in (-1, 1):                      # wings
            x1, x2 = sorted((cx + side * S(110), cx + side * S(190)))
            self.create_rectangle(x1, gy - S(50), x2, gy, fill="#F7FBFF", outline=edge)
            for wx in (0.2, 0.5, 0.8):
                px = x1 + (x2 - x1) * wx
                self.create_rectangle(px - S(6), gy - S(38), px + S(6), gy - S(22), fill="#8FD0F5", outline=edge)
        self.create_rectangle(cx - S(110), gy - S(80), cx + S(110), gy, fill="#FFFFFF", outline=edge)
        self.create_polygon(cx - S(88), gy - S(80), cx, gy - S(118), cx + S(88), gy - S(80),
                            fill="#DDEFFB", outline=edge)
        for k in range(5):                        # columns
            x = cx - S(64) + k * S(32)
            self.create_rectangle(x - S(5), gy - S(80), x + S(5), gy, fill="#FFFFFF", outline=edge)
        self.create_rectangle(cx - S(96), gy - S(6), cx + S(96), gy, fill="#EAF4FB", outline=edge)
        self.create_rectangle(cx - S(11), gy - S(36), cx + S(11), gy - S(6), fill="#7CC4EF", outline=edge)
        # dome + flag + clock
        self.create_rectangle(cx - S(26), gy - S(138), cx + S(26), gy - S(116), fill="#FFFFFF", outline=edge)
        self.create_arc(cx - S(26), gy - S(168), cx + S(26), gy - S(112), start=0, extent=180,
                        fill=BLUE, outline=CYAN, style="pieslice")
        self.create_line(cx, gy - S(168), cx, gy - S(190), fill=CYAN, width=2)
        self.create_polygon(cx, gy - S(190), cx + S(16), gy - S(185), cx, gy - S(179), fill=ORANGE, outline="")
        self.create_oval(cx - S(10), gy - S(106), cx + S(10), gy - S(86), fill="#FFFFFF", outline=BLUE, width=2)
        self.create_line(cx, gy - S(96), cx, gy - S(103), fill=CYAN, width=2)
        self.create_line(cx, gy - S(96), cx + S(5), gy - S(93), fill=CYAN, width=2)

        # floating graduation cap
        gx, gcy = cx - S(150), gy - S(150)
        tags = ("cap",)
        self.create_polygon(gx, gcy - S(11), gx + S(24), gcy, gx, gcy + S(11), gx - S(24), gcy,
                            fill=CYAN, outline="", tags=tags)
        self.create_polygon(gx - S(13), gcy + S(5), gx - S(13), gcy + S(15), gx, gcy + S(21),
                            gx + S(13), gcy + S(15), gx + S(13), gcy + S(5), gx, gcy + S(11),
                            fill=BLUE, outline="", tags=tags)
        self.create_line(gx + S(24), gcy, gx + S(24), gcy + S(16), fill=ORANGE, width=2, tags=tags)

        # campus bus (drives across the ground)
        if self.bus_x is None:
            self.bus_x = w * 0.18
        x0 = self.bus_x
        by = min(h - 4, gy + S(28))
        bt = ("bus",)
        self.create_rectangle(x0, by - S(26), x0 + S(76), by - S(4), fill="#FFC24B", outline="#C98A1A", tags=bt)
        for k in range(4):
            self.create_rectangle(x0 + S(6) + k * S(15), by - S(22), x0 + S(17) + k * S(15), by - S(13),
                                  fill="#EAF7FF", outline="", tags=bt)
        self.create_rectangle(x0 + S(65), by - S(22), x0 + S(73), by - S(11), fill="#EAF7FF", outline="", tags=bt)
        self.create_rectangle(x0, by - S(10), x0 + S(76), by - S(7), fill=BLUE, outline="", tags=bt)
        for wx in (16, 58):
            self.create_oval(x0 + S(wx - 6), by - S(10), x0 + S(wx + 6), by + S(2), fill=DARK, outline="", tags=bt)
            self.create_oval(x0 + S(wx - 2), by - S(6), x0 + S(wx + 2), by - S(2), fill="#FFFFFF", outline="", tags=bt)

        # heartbeat line + headline text
        if self.ecg_y is not None:
            base = [(0, 0), (46, 0), (58, -10), (70, 14), (86, -36), (100, 28), (112, 0),
                    (170, 0), (182, -8), (194, 0), (300, 0)]
            pts = []
            for px, py in base:
                pts += [40 + px, self.ecg_y + py]
            self.create_line(pts, fill=BLUE, width=3, capstyle="round", joinstyle="round")
        for text, size, weight, color, y in self.texts:
            self.create_text(40, y, text=text, anchor="w", fill=color, font=("Segoe UI", size, weight))

    def tick(self):
        try:
            if not self.winfo_exists():
                return
            w = max(self.winfo_width(), 200)
            for i, (_x, _y, _k, speed) in enumerate(self.CLOUDS):
                if i < len(self.cloud_x):
                    tag = "cloud%d" % i
                    self.move(tag, speed, 0)
                    self.cloud_x[i] += speed
                    if self.cloud_x[i] > w + 90:
                        self.move(tag, -(w + 220), 0)
                        self.cloud_x[i] -= (w + 220)
            if self.bus_x is not None:
                self.move("bus", 1.4, 0)
                self.bus_x += 1.4
                if self.bus_x > w + 20:
                    self.move("bus", -(w + 160), 0)
                    self.bus_x -= (w + 160)
            self.phase += 0.1
            self.move("cap", 0, math.sin(self.phase) * 0.45)
            self.after(40, self.tick)
        except tk.TclError:
            pass

def draw_icon(canvas, kind, color):
    """Small flat icons for the dashboard cards."""
    soft = mix(color, "#FFFFFF", 0.82)
    canvas.create_oval(0, 0, 46, 46, fill=soft, outline="")
    if kind == "students":
        canvas.create_polygon(23, 12, 38, 19, 23, 26, 8, 19, fill=color, outline="")
        canvas.create_polygon(15, 23, 15, 30, 23, 34, 31, 30, 31, 23, 23, 27, fill=mix(color, "#FFFFFF", 0.25), outline="")
        canvas.create_line(38, 19, 38, 29, fill=color, width=2)
    elif kind == "faculty":
        canvas.create_rectangle(10, 14, 22, 33, fill=color, outline="")
        canvas.create_rectangle(24, 14, 36, 33, fill=mix(color, "#FFFFFF", 0.35), outline="")
    elif kind == "attendance":
        canvas.create_oval(11, 11, 35, 35, outline=color, width=3)
        canvas.create_line(17, 24, 22, 29, 30, 18, fill=color, width=3)
    else:
        for dx, dy in ((0, -11), (0, 11), (-11, 0), (11, 0)):
            canvas.create_rectangle(23 + dx - 3, 23 + dy - 3, 23 + dx + 3, 23 + dy + 3, fill=color, outline="")
        canvas.create_oval(13, 13, 33, 33, fill=color, outline="")
        canvas.create_oval(19, 19, 27, 27, fill=soft, outline="")

class CampusPulse(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME + " | Intelligent Campus Operations")
        self.geometry("1360x820")
        self.minsize(1100, 700)
        self.configure(bg=BG)
        self.db = Database()
        self.user = None
        self.current_module = "Overview"
        self.nav_buttons = {}
        self._cover = None
        self.protocol("WM_DELETE_WINDOW", self.close_app)
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, self.on_mousewheel)
        self.style()
        self.set_alpha(0.0)
        self.show_login()
        self.fade(0.0, 1.0, 10)

    # ---- smooth-motion helpers ------------------------------------------------
    def set_alpha(self, a):
        try:
            self.attributes("-alpha", a)
        except tk.TclError:
            pass

    def fade(self, start, end, steps=8, done=None):
        def step(i=0):
            self.set_alpha(start + (end - start) * (i / steps))
            if i < steps:
                self.after(16, step, i + 1)
            elif done:
                done()
        step()

    def fade_to(self, build):
        """Fade the whole window down, switch screen, fade back up."""
        def switched():
            build()
            self.fade(0.35, 1.0, 8)
        self.fade(1.0, 0.35, 6, switched)

    def tween_bg(self, widgets, end, steps=6):
        """Smoothly blend the background of the given widgets from its current colour to `end`."""
        root = widgets[0]
        try:
            job = getattr(root, "_tw", None)
            if job:
                root.after_cancel(job)
            start = root.cget("bg")
        except tk.TclError:
            return
        def step(i=1):
            try:
                c = mix(start, end, i / steps)
                for w in widgets:
                    w.configure(bg=c)
                if i < steps:
                    root._tw = root.after(16, step, i + 1)
            except tk.TclError:
                pass
        step()

    def count_up(self, lbl, target, steps=18):
        def step(i=0):
            try:
                t = 1 - (1 - i / steps) ** 3
                lbl.configure(text=str(int(round(target * t))))
                if i < steps:
                    self.after(22, step, i + 1)
            except tk.TclError:
                pass
        step()

    def reveal(self, cover, steps=14):
        """Wipe the cover upwards so the new page is revealed smoothly."""
        def step(i=1):
            try:
                if not cover.winfo_exists():
                    return
                if i >= steps:
                    cover.destroy()
                    return
                t = 1 - (1 - i / steps) ** 3
                cover.place_configure(relheight=1 - t)
                self.after(16, step, i + 1)
            except tk.TclError:
                pass
        self.after(10, step)

    # ---- styling ---------------------------------------------------------------
    def style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=PANEL, foreground=TEXT, fieldbackground=PANEL,
                        rowheight=36, borderwidth=0, font=("Segoe UI", 10))
        style.configure("Treeview.Heading", background="#DCEFFB", foreground=CYAN, relief="flat",
                        font=("Segoe UI", 10, "bold"), padding=(6, 8))
        style.map("Treeview.Heading", background=[("active", "#CBE6F8")])
        style.map("Treeview", background=[("selected", "#BFE3FA")], foreground=[("selected", TEXT)])
        style.configure("TCombobox", fieldbackground=FIELD, background=PANEL2, foreground=TEXT,
                        arrowcolor=CYAN, bordercolor=BORDER, lightcolor=FIELD, darkcolor=FIELD)
        style.map("TCombobox", fieldbackground=[("readonly", FIELD), ("disabled", "#E3EEF6")],
                  foreground=[("readonly", TEXT), ("disabled", MUTED)],
                  selectbackground=[("readonly", FIELD)], selectforeground=[("readonly", TEXT)])
        self.option_add("*TCombobox*Listbox.background", PANEL)
        self.option_add("*TCombobox*Listbox.foreground", TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", "#BFE3FA")
        self.option_add("*TCombobox*Listbox.selectForeground", TEXT)
        self.option_add("*TCombobox*Listbox.font", ("Segoe UI", 10))
        for orient in ("Vertical", "Horizontal"):
            style.configure(orient + ".TScrollbar", background="#B9DDF5", troughcolor="#EAF4FB",
                            bordercolor=BORDER, arrowcolor=CYAN, lightcolor="#B9DDF5", darkcolor="#B9DDF5")
            style.map(orient + ".TScrollbar", background=[("active", BLUE)])

    def on_mousewheel(self, event):
        """Mouse wheel scrolls the table under the pointer, else the sidebar / page under it."""
        try:
            w = self.winfo_containing(event.x_root, event.y_root)
        except Exception:
            return
        if event.num == 4:
            step = -1
        elif event.num == 5:
            step = 1
        else:
            step = -1 if event.delta > 0 else 1
        while w is not None:
            if isinstance(w, ttk.Treeview):
                w.yview_scroll(step, "units")
                return
            if getattr(w, "scroll_target", False):
                w.yview_scroll(step * 2, "units")
                return
            w = getattr(w, "master", None)

    def scope(self):
        """None = sees all departments; otherwise the department name this user is limited to."""
        if self.user["role"] in GLOBAL_ROLES:
            return None
        dept = self.user.get("department")
        return dept if dept and dept != ALL_DEPT else UNASSIGNED

    def clear(self):
        for w in self.winfo_children():
            w.destroy()

    def label(self, parent, text, size=11, color=TEXT, weight="normal"):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                        font=("Segoe UI", size, weight))

    def entry(self, parent, **kw):
        opts = dict(bg=FIELD, fg=TEXT, insertbackground=TEXT, relief="flat", font=("Segoe UI", 11),
                    highlightthickness=1, highlightbackground=BORDER, highlightcolor=BLUE)
        opts.update(kw)
        return tk.Entry(parent, **opts)

    def style_button(self, b, bg, hover, fg):
        b.rest_bg, b.hover_bg = bg, hover
        b.configure(bg=bg, fg=fg, activebackground=hover, activeforeground=fg)

    def button(self, parent, text, command, primary=False):
        b = tk.Button(parent, text=text, command=command, relief="flat", bd=0, padx=16, pady=10,
                      cursor="hand2", font=("Segoe UI", 10, "bold"))
        if primary:
            self.style_button(b, BLUE, "#0F82CF", "#FFFFFF")
        else:
            self.style_button(b, PANEL2, "#D2EAFA", TEXT)
        b.bind("<Enter>", lambda e: self.tween_bg([b], b.hover_bg))
        b.bind("<Leave>", lambda e: self.tween_bg([b], b.rest_bg))
        return b

    # ---- sign-in / setup screens ----------------------------------------------
    def auth_layout(self, texts, ecg_y):
        """Illustration on the left, white card on the right. Returns the card."""
        self.clear()
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="both", expand=True)
        right = tk.Frame(wrap, bg=BG, width=540)
        right.pack(side="right", fill="y")
        right.pack_propagate(False)
        scene = CampusScene(wrap, height=600, cx_ratio=0.5, texts=texts, ecg_y=ecg_y)
        scene.pack(side="left", fill="both", expand=True)
        card = tk.Frame(right, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        card.pack(expand=True, ipadx=35, ipady=25)
        return card

    def show_setup(self):
        """First-run screen: the owner creates their own administrator account."""
        card = self.auth_layout([
            ("CAMPUSPULSE", 34, "bold", DARK, 80),
            ("360", 64, "bold", CYAN, 150),
            ("Welcome. Let's set up your administrator account.", 14, "normal", DARK, 228),
            ("You will use this username and password to sign in.", 10, "normal", SUB, 258),
        ], ecg_y=320)
        self.label(card, "CREATE ADMIN ACCOUNT", 19, CYAN, "bold").pack(anchor="w", padx=30, pady=(20, 18))
        entries = {}
        for name, hidden in [("FULL NAME", False), ("USERNAME", False),
                             ("PASSWORD (min 6 characters)", True), ("CONFIRM PASSWORD", True)]:
            self.label(card, name, 9, MUTED, "bold").pack(anchor="w", padx=30)
            ent = self.entry(card, show="•" if hidden else "", font=("Segoe UI", 12), width=30)
            ent.pack(padx=30, pady=(6, 14), ipady=9)
            entries[name] = ent
        names = list(entries.values())
        def create():
            full, user, pw, pw2 = [e.get().strip() if i < 2 else e.get() for i, e in enumerate(names)]
            if not full or not user or not pw:
                messagebox.showwarning("Missing information", "Please fill in every field.")
                return
            if len(pw) < 6:
                messagebox.showwarning("Weak password", "Password must be at least 6 characters.")
                return
            if pw != pw2:
                messagebox.showwarning("Passwords differ", "The two passwords do not match.")
                return
            try:
                self.db.remove_demo_account()
                self.db.add_user(user, pw, "Admin", full, ALL_DEPT)
            except sqlite3.IntegrityError:
                messagebox.showerror("Username exists", "Choose a different username.")
                return
            self.db.log(user, "SETUP", "Administrator account created")
            messagebox.showinfo("Account created", "Your account is ready. Please sign in.")
            self.fade_to(self.show_login)
        self.button(card, "CREATE ACCOUNT  →", create, True).pack(fill="x", padx=30, pady=10)
        names[-1].bind("<Return>", lambda e: create())
        names[0].focus_set()

    def show_login(self):
        if self.db.needs_setup():
            self.show_setup()
            return
        card = self.auth_layout([
            ("CAMPUSPULSE", 34, "bold", DARK, 80),
            ("360", 64, "bold", CYAN, 150),
            ("INTELLIGENT CAMPUS OPERATIONS PLATFORM", 11, "bold", SUB, 215),
            ("One command centre. Every campus signal.", 15, "normal", DARK, 322),
            ("Students  •  Faculty  •  Academics  •  Infrastructure  •  Mobility", 10, "normal", SUB, 352),
        ], ecg_y=262)
        self.label(card, "SECURE ACCESS", 19, CYAN, "bold").pack(anchor="w", padx=30, pady=(20, 5))
        self.label(card, "Sign in to your campus workspace", 10, MUTED).pack(anchor="w", padx=30, pady=(0, 25))
        self.label(card, "USERNAME", 9, MUTED, "bold").pack(anchor="w", padx=30)
        self.username = self.entry(card, font=("Segoe UI", 12), width=30)
        self.username.pack(padx=30, pady=(6, 18), ipady=10)
        self.label(card, "PASSWORD", 9, MUTED, "bold").pack(anchor="w", padx=30)
        self.password = self.entry(card, show="•", font=("Segoe UI", 12), width=30)
        self.password.pack(padx=30, pady=(6, 20), ipady=10)
        self.button(card, "SIGN IN  →", self.login, True).pack(fill="x", padx=30, pady=5)
        self.password.bind("<Return>", lambda e: self.login())
        self.username.focus_set()

    def login(self):
        user = self.db.authenticate(self.username.get(), self.password.get())
        if not user:
            messagebox.showerror("Access denied", "Username or password is incorrect.")
            return
        self.user = dict(user)
        self.db.log(self.user["username"], "LOGIN", "Successful sign in")
        self.fade_to(self.show_dashboard)

    # ---- dashboard shell -------------------------------------------------------
    def show_dashboard(self):
        self.clear()
        self.nav_buttons = {}
        shell = tk.Frame(self, bg=BG)
        shell.pack(fill="both", expand=True)
        side = tk.Frame(shell, bg=SIDEBAR, width=240)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        logo = tk.Frame(side, bg=SIDEBAR)
        logo.pack(anchor="w", padx=20, pady=(24, 0))
        lg = tk.Canvas(logo, width=38, height=38, bg=SIDEBAR, highlightthickness=0)
        lg.create_oval(2, 2, 36, 36, fill="#FFFFFF", outline="")
        lg.create_line(8, 20, 14, 20, 18, 11, 23, 29, 27, 20, 31, 20, fill=BLUE, width=2)
        lg.pack(side="left")
        txt = tk.Frame(logo, bg=SIDEBAR)
        txt.pack(side="left", padx=10)
        self.label(txt, "CAMPUSPULSE", 14, "#FFFFFF", "bold").pack(anchor="w")
        self.label(txt, "360  /  CONTROL HUB", 8, SIDE_SUB, "bold").pack(anchor="w")
        tk.Frame(side, bg=SIDE_LINE, height=1).pack(fill="x", padx=18, pady=(18, 6))
        # Bottom block is packed first so it is always visible (Sign out never gets pushed off screen)
        bottom = tk.Frame(side, bg=SIDEBAR)
        bottom.pack(side="bottom", fill="x", pady=(0, 10))
        tk.Frame(bottom, bg=SIDE_LINE, height=1).pack(fill="x", padx=18, pady=(8, 10))
        self.label(bottom, self.user["display_name"], 10, "#FFFFFF", "bold").pack(anchor="w", padx=20)
        self.label(bottom, self.user["role"].upper(), 8, "#C9F7DF", "bold").pack(anchor="w", padx=20, pady=(3, 0))
        self.label(bottom, (self.scope() or ALL_DEPT_LABEL).upper(), 8, SIDE_SUB, "bold").pack(anchor="w", padx=20, pady=(0, 10))
        if self.user["role"] in ("Admin", "Principal"):
            for text, cmd in (("＋  Create user", self.create_user), ("⚙  Assign department", self.assign_department)):
                b = self.button(bottom, text, cmd)
                self.style_button(b, "#FFFFFF", "#E1F2FD", CYAN)
                b.pack(fill="x", padx=15, pady=3)
        signout = self.button(bottom, "↪  Sign out", self.confirm_logout)
        self.style_button(signout, RED, "#F0666B", "#FFFFFF")
        signout.pack(fill="x", padx=15, pady=3)

        # Module list scrolls when the window is short
        nav = ScrollFrame(side, SIDEBAR, bar=False)
        nav.pack(fill="both", expand=True)
        for module in ROLE_ACCESS.get(self.user["role"], ["Overview"]):
            self.nav_button(nav.inner, module)

        # Main page scrolls when a module's content is taller than the window
        self.page = ScrollFrame(shell, BG)
        self.page.pack(side="left", fill="both", expand=True)
        self.content = self.page.inner
        self.show_module("Overview")

    def nav_button(self, parent, name):
        b = tk.Button(parent, text="   " + name, anchor="w", command=lambda n=name: self.show_module(n),
                      relief="flat", bd=0, padx=14, pady=11, font=("Segoe UI", 10, "bold"), cursor="hand2")
        self.style_button(b, SIDEBAR, SIDE_HOVER, "#FFFFFF")
        b.bind("<Enter>", lambda e: self.tween_bg([b], b.hover_bg))
        b.bind("<Leave>", lambda e: self.tween_bg([b], b.rest_bg))
        b.pack(fill="x", padx=10, pady=1)
        self.nav_buttons[name] = b

    def set_active_nav(self, module):
        for name, b in self.nav_buttons.items():
            try:
                if name == module:
                    b.rest_bg, b.hover_bg = "#FFFFFF", "#FFFFFF"
                    b.configure(fg=CYAN, activeforeground=CYAN, activebackground="#FFFFFF")
                else:
                    b.rest_bg, b.hover_bg = SIDEBAR, SIDE_HOVER
                    b.configure(fg="#FFFFFF", activeforeground="#FFFFFF", activebackground=SIDE_HOVER)
                self.tween_bg([b], b.rest_bg)
            except tk.TclError:
                pass

    def header(self, title, subtitle):
        top = tk.Frame(self.content, bg=BG)
        top.pack(fill="x", padx=30, pady=(25, 18))
        # Log out button: top-right of every page, for every role (Admin, Principal, HOD, ...)
        right = tk.Frame(top, bg=BG)
        right.pack(side="right", anchor="n")
        logout_btn = self.button(right, "↪  Log out", self.confirm_logout)
        self.style_button(logout_btn, RED, "#F0666B", "#FFFFFF")
        logout_btn.pack(anchor="e")
        self.label(right, datetime.now().strftime("%d %b %Y  |  %I:%M %p"), 9, CYAN).pack(anchor="e", pady=(8, 0))
        left = tk.Frame(top, bg=BG)
        left.pack(side="left", anchor="w")
        self.label(left, title, 23, TEXT, "bold").pack(anchor="w")
        self.label(left, subtitle, 10, MUTED).pack(anchor="w", pady=(4, 0))

    def show_module(self, module):
        self.current_module = module
        self.set_active_nav(module)
        try:
            if self._cover is not None and self._cover.winfo_exists():
                self._cover.destroy()
        except tk.TclError:
            pass
        for w in self.content.winfo_children():
            w.destroy()
        if hasattr(self, "page") and self.page.winfo_exists():
            self.page.to_top()
        # curtain that wipes upward once the new page is built (smooth page transition)
        cover = tk.Frame(self.page, bg=BG)
        cover.place(relx=0, rely=1, relwidth=1, relheight=1, anchor="sw")
        cover.lift()
        self._cover = cover
        if module == "Overview":
            self.show_overview()
        else:
            self.show_records(module)
        self.update_idletasks()
        self.reveal(cover)

    # ---- overview --------------------------------------------------------------
    def show_overview(self):
        self.header("Command centre", "Live snapshot of campus operations • Local database")
        hero = CampusScene(self.content, height=230, cx_ratio=0.70, ecg_y=160, texts=[
            ("Smart campus. Calm operations.", 24, "bold", DARK, 66),
            ("Students  •  Faculty  •  Academics  •  Transport  •  Infrastructure", 11, "normal", SUB, 104)])
        hero.pack(fill="x", padx=30, pady=(0, 14))

        cards = tk.Frame(self.content, bg=BG)
        cards.pack(fill="x", padx=25)
        dept = self.scope()
        stats = [("STUDENTS", self.db.count("Students", dept), BLUE, "students"),
                 ("FACULTY", self.db.count("Faculty", dept), TEAL, "faculty"),
                 ("ATTENDANCE LOGS", self.db.count("Attendance", dept), GREEN, "attendance"),
                 ("OPEN MAINTENANCE", self.db.count("Maintenance"), ORANGE, "maintenance")]
        for title, value, color, icon in stats:
            box = tk.Frame(cards, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
            box.pack(side="left", fill="both", expand=True, padx=6, pady=6, ipady=10)
            ic = tk.Canvas(box, width=46, height=46, bg=PANEL, highlightthickness=0)
            draw_icon(ic, icon, color)
            ic.pack(side="right", anchor="n", padx=16, pady=14)
            self.label(box, title, 9, MUTED, "bold").pack(anchor="w", padx=16, pady=(14, 4))
            num = self.label(box, "0", 27, color, "bold")
            num.pack(anchor="w", padx=16)
            self.label(box, "DATABASE RECORDS", 8, MUTED).pack(anchor="w", padx=16, pady=(2, 10))
            self.count_up(num, value)

        lower = tk.Frame(self.content, bg=BG)
        lower.pack(fill="both", expand=True, padx=31, pady=18)
        left = tk.Frame(lower, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))
        self.label(left, "CAMPUS MODULES", 12, CYAN, "bold").pack(anchor="w", padx=20, pady=(18, 8))
        grid = tk.Frame(left, bg=PANEL)
        grid.pack(fill="both", expand=True, padx=14, pady=(0, 16))
        grid.grid_columnconfigure(0, weight=1, uniform="tile")
        grid.grid_columnconfigure(1, weight=1, uniform="tile")
        mods = [m for m in ROLE_ACCESS.get(self.user["role"], []) if m != "Overview"]
        for idx, m in enumerate(mods):
            self.module_tile(grid, m, idx).grid(row=idx // 2, column=idx % 2, sticky="ew", padx=6, pady=6)

        right = tk.Frame(lower, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        right.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.label(right, "SYSTEM STATUS", 12, CYAN, "bold").pack(anchor="w", padx=20, pady=(18, 8))
        for line, color in [("●  Local SQLite database connected", GREEN),
                            ("●  Role-based access enabled", GREEN),
                            ("●  Offline desktop mode", GREEN),
                            ("●  Analytics: sample-data dependent", ORANGE)]:
            self.label(right, line, 10, color).pack(anchor="w", padx=22, pady=5)
        tk.Frame(right, bg=BORDER, height=1).pack(fill="x", padx=20, pady=(14, 10))
        self.label(right, "RECENT ACTIVITY", 12, CYAN, "bold").pack(anchor="w", padx=20, pady=(0, 6))
        who = None if self.user["role"] in ("Admin", "Principal") else self.user["username"]
        acts = self.db.recent_activity(who, 5)
        if not acts:
            self.label(right, "No activity yet.", 9, MUTED).pack(anchor="w", padx=22, pady=3)
        for a in acts:
            line = "%s   %s · %s %s" % ((a["created_at"] or "")[11:16], a["username"], a["action"], a["detail"] or "")
            self.label(right, line.strip(), 9, MUTED).pack(anchor="w", padx=22, pady=2)
        self.label(right, "Tip: click a module tile or use the menu on the left.", 9, MUTED).pack(anchor="w", padx=22, pady=(14, 18))

    def module_tile(self, parent, name, idx):
        color = BADGE_COLORS[idx % len(BADGE_COLORS)]
        tile = tk.Frame(parent, bg=PANEL2, cursor="hand2")
        badge = tk.Canvas(tile, width=40, height=40, bg=PANEL2, highlightthickness=0, cursor="hand2")
        badge.create_oval(2, 2, 38, 38, fill=color, outline="")
        badge.create_text(20, 20, text=name[0], fill="#FFFFFF", font=("Segoe UI", 13, "bold"))
        badge.pack(side="left", padx=(12, 10), pady=12)
        box = tk.Frame(tile, bg=PANEL2, cursor="hand2")
        box.pack(side="left", fill="x", expand=True)
        t1 = self.label(box, name, 11, TEXT, "bold")
        t1.configure(cursor="hand2")
        t1.pack(anchor="w")
        t2 = self.label(box, MODULE_BLURB.get(name, ""), 9, MUTED)
        t2.configure(cursor="hand2")
        t2.pack(anchor="w")
        widgets = [tile, badge, box, t1, t2]
        for w in widgets:
            w.bind("<Enter>", lambda e, ws=widgets: self.tween_bg(ws, "#D2EAFA"))
            w.bind("<Leave>", lambda e, ws=widgets: self.tween_bg(ws, PANEL2))
            w.bind("<Button-1>", lambda e, n=name: self.show_module(n))
        return tile

    # ---- record pages ----------------------------------------------------------
    def show_records(self, module):
        fields = MODULES[module]
        subtitle = "Create, search and manage " + module.lower() + " records"
        if module in DEPT_MODULES and self.scope():
            subtitle += "  •  Department: " + self.scope()
        self.header(module, subtitle)
        toolbar = tk.Frame(self.content, bg=BG)
        toolbar.pack(fill="x", padx=30, pady=(0, 12))
        self.button(toolbar, "＋  Add record", lambda: self.add_record(module), True).pack(side="left")
        self.button(toolbar, "Delete selected", lambda: self.delete_selected(module)).pack(side="left", padx=8)
        self.button(toolbar, "Refresh", lambda: self.refresh_table(module)).pack(side="left")
        self.dept_filter = tk.StringVar(value=ALL_DEPT_LABEL)
        if module in DEPT_MODULES and self.scope() is None:
            self.label(toolbar, "   DEPARTMENT  ", 9, MUTED, "bold").pack(side="left")
            box = ttk.Combobox(toolbar, textvariable=self.dept_filter, state="readonly", width=30,
                               values=[ALL_DEPT_LABEL] + DEPARTMENTS)
            box.pack(side="left", ipady=4)
            box.bind("<<ComboboxSelected>>", lambda e: self.refresh_table(module))
        self.search_var = tk.StringVar()
        search = self.entry(toolbar, textvariable=self.search_var, font=("Segoe UI", 10), width=28)
        search.pack(side="right", ipady=9)
        self.label(toolbar, "SEARCH  ", 9, MUTED, "bold").pack(side="right")
        search.bind("<KeyRelease>", lambda e: self.refresh_table(module))
        frame = tk.Frame(self.content, bg=PANEL, highlightbackground=BORDER, highlightthickness=1)
        frame.pack(fill="both", expand=True, padx=30, pady=(0, 25))
        cols = ["ID"] + fields + ["Created"]
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        self.tree.tag_configure("odd", background="#F3F9FE")
        for c in cols:
            self.tree.heading(c, text=c.upper())
            self.tree.column(c, width=130, minwidth=90, anchor="w")
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(10, 0), pady=(10, 0))
        yscroll.grid(row=0, column=1, sticky="ns", padx=(0, 4), pady=(10, 0))
        xscroll.grid(row=1, column=0, sticky="ew", padx=(10, 0), pady=(0, 4))
        self.refresh_table(module)

    def refresh_table(self, module):
        if not hasattr(self, "tree") or not self.tree.winfo_exists():
            return
        for item in self.tree.get_children():
            self.tree.delete(item)
        term = self.search_var.get().lower() if hasattr(self, "search_var") else ""
        dept = self.scope()
        if dept is None and module in DEPT_MODULES and hasattr(self, "dept_filter"):
            chosen = self.dept_filter.get()
            dept = None if chosen == ALL_DEPT_LABEL else chosen
        n = 0
        for row in self.db.rows(module, dept):
            values = row["data"].split("|||")
            if term and term not in " ".join(values).lower():
                continue
            self.tree.insert("", "end", iid=str(row["id"]), tags=("odd",) if n % 2 else (),
                             values=[row["id"]] + values + [row["created_at"]])
            n += 1

    def add_record(self, module):
        fields = MODULES[module]
        scope = self.scope()
        if scope == UNASSIGNED and module in DEPT_MODULES:
            messagebox.showwarning("No department", "Your account has no department yet. "
                                   "Ask the administrator to assign one.")
            return
        has_dept_field = "Department" in fields
        extra_dept = module in DEPT_MODULES and not has_dept_field
        choices = [scope] if scope else ([ALL_DEPT_LABEL] if module == "Announcements" else []) + DEPARTMENTS
        win = tk.Toplevel(self)
        win.title("Add " + module + " record")
        win.configure(bg=BG)
        height = min(190 + (len(fields) + extra_dept) * 76 + 90, self.winfo_screenheight() - 120)
        win.geometry("500x" + str(height))
        win.minsize(420, 360)
        win.transient(self)
        # Save / Cancel bar is packed first at the bottom, so it is ALWAYS visible
        bar = tk.Frame(win, bg=BG)
        bar.pack(side="bottom", fill="x", padx=25, pady=15)
        tk.Label(win, text="NEW " + module.upper() + " RECORD", bg=BG, fg=CYAN,
                 font=("Segoe UI", 15, "bold")).pack(side="top", anchor="w", padx=25, pady=(20, 10))
        scroller = ScrollFrame(win, BG)   # fields scroll if the window is short
        scroller.pack(fill="both", expand=True)
        form = scroller.inner
        def dept_combo():
            box = ttk.Combobox(form, values=choices, state="disabled" if scope else "readonly",
                               font=("Segoe UI", 11))
            box.set(choices[0] if scope or len(choices) == 1 else "")
            box.pack(fill="x", padx=25, pady=(4, 12), ipady=6)
            return box
        dept_box = None
        if extra_dept:
            tk.Label(form, text="Department", bg=BG, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=25)
            dept_box = dept_combo()
        entries = []
        for field in fields:
            tk.Label(form, text=field, bg=BG, fg=MUTED, font=("Segoe UI", 9, "bold")).pack(anchor="w", padx=25)
            if field == "Department":
                ent = dept_box = dept_combo()
            else:
                ent = self.entry(form)
                ent.pack(fill="x", padx=25, pady=(4, 12), ipady=8)
            entries.append(ent)
        def save():
            values = [e.get().strip() for e in entries]
            if not all(values) or (dept_box is not None and not dept_box.get().strip()):
                messagebox.showwarning("Missing information", "Please fill in every field.", parent=win)
                return
            record_dept = ALL_DEPT
            if dept_box is not None:
                record_dept = ALL_DEPT if dept_box.get() == ALL_DEPT_LABEL else dept_box.get()
            self.db.add_record(module, values, record_dept)
            self.db.log(self.user["username"], "ADD", module)
            win.destroy()
            self.refresh_table(module)
        self.button(bar, "SAVE RECORD", save, True).pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.button(bar, "Cancel", win.destroy).pack(side="left", padx=(6, 0))
        win.bind("<Return>", lambda e: save())
        win.bind("<Escape>", lambda e: win.destroy())
        for e in entries:
            if isinstance(e, tk.Entry):
                e.focus_set()
                break

    def delete_selected(self, module):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo("Select a record", "Choose a row first.")
            return
        if messagebox.askyesno("Confirm deletion", "Delete the selected record permanently?"):
            for item in selected:
                self.db.delete_record(int(item), self.scope())
            self.db.log(self.user["username"], "DELETE", module)
            self.refresh_table(module)

    def create_user(self):
        win = tk.Toplevel(self)
        win.title("Create user")
        win.configure(bg=BG)
        win.geometry("430x" + str(min(680, self.winfo_screenheight() - 120)))
        win.minsize(400, 420)
        fields = {}
        for name in ["Username", "Display name", "Password"]:
            tk.Label(win, text=name, bg=BG, fg=MUTED).pack(anchor="w", padx=25, pady=(16, 3))
            ent = self.entry(win, show="•" if name == "Password" else "")
            ent.pack(fill="x", padx=25, ipady=9)
            fields[name] = ent
        tk.Label(win, text="Role", bg=BG, fg=MUTED).pack(anchor="w", padx=25, pady=(16, 3))
        role = ttk.Combobox(win, values=list(ROLE_ACCESS.keys()), state="readonly")
        role.set("Faculty")
        role.pack(fill="x", padx=25, ipady=5)
        tk.Label(win, text="Department (HOD / Faculty / Student)", bg=BG, fg=MUTED).pack(anchor="w", padx=25, pady=(16, 3))
        dept = ttk.Combobox(win, values=DEPARTMENTS, state="readonly")
        dept.pack(fill="x", padx=25, ipady=5)
        def role_changed(event=None):
            if role.get() in GLOBAL_ROLES:
                dept.set("")
                dept.configure(state="disabled")
            else:
                dept.configure(state="readonly")
        role.bind("<<ComboboxSelected>>", role_changed)
        def save():
            if role.get() not in GLOBAL_ROLES and not dept.get():
                messagebox.showwarning("Department required", "Please choose a department for this user.", parent=win)
                return
            try:
                self.db.add_user(fields["Username"].get(), fields["Password"].get(),
                                 role.get(), fields["Display name"].get(),
                                 ALL_DEPT if role.get() in GLOBAL_ROLES else dept.get())
                self.db.log(self.user["username"], "CREATE USER", fields["Username"].get())
                messagebox.showinfo("Created", "User account created.", parent=win)
                win.destroy()
            except sqlite3.IntegrityError:
                messagebox.showerror("Username exists", "Choose a different username.", parent=win)
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=win)
        self.button(win, "CREATE ACCOUNT", save, True).pack(fill="x", padx=25, pady=25, side="bottom")

    def assign_department(self):
        """Give (or change) the department of an existing HOD / Faculty / Student account."""
        users = [u for u in self.db.users() if u["role"] not in GLOBAL_ROLES]
        if not users:
            messagebox.showinfo("No users", "There are no HOD, Faculty or Student accounts yet.")
            return
        win = tk.Toplevel(self)
        win.title("Assign department")
        win.configure(bg=BG)
        win.geometry("460x320")
        win.transient(self)
        tk.Label(win, text="User", bg=BG, fg=MUTED).pack(anchor="w", padx=25, pady=(20, 3))
        user_box = ttk.Combobox(win, state="readonly", values=[
            u["username"] + "  (" + u["role"] + ")  -  " + (u["department"] if u["department"] != ALL_DEPT else "no department")
            for u in users])
        user_box.pack(fill="x", padx=25, ipady=5)
        tk.Label(win, text="Department", bg=BG, fg=MUTED).pack(anchor="w", padx=25, pady=(16, 3))
        dept = ttk.Combobox(win, values=DEPARTMENTS, state="readonly")
        dept.pack(fill="x", padx=25, ipady=5)
        def save():
            if user_box.current() < 0 or not dept.get():
                messagebox.showwarning("Missing information", "Choose a user and a department.", parent=win)
                return
            username = users[user_box.current()]["username"]
            self.db.set_user_department(username, dept.get())
            self.db.log(self.user["username"], "ASSIGN DEPARTMENT", username + " -> " + dept.get())
            messagebox.showinfo("Saved", "Department updated. It applies at the user's next sign in.", parent=win)
            win.destroy()
        self.button(win, "SAVE", save, True).pack(fill="x", padx=25, pady=25)

    def confirm_logout(self):
        if messagebox.askyesno("Log out", "Do you want to log out?"):
            self.logout()

    def logout(self):
        if self.user:
            self.db.log(self.user["username"], "LOGOUT", "Signed out")
        self.user = None
        self.fade_to(self.show_login)

    def close_app(self):
        try:
            self.db.conn.close()
        finally:
            self.destroy()

if __name__ == "__main__":
    app = CampusPulse()
    app.mainloop()
