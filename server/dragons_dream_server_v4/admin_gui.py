#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dragon's Dream Revival Server v4 — Administration GUI
Tkinter-based server operator panel for managing all aspects of the game server.

Usage: python -m dragons_dream_server_v4.admin_gui
   or: python admin_gui.py
"""
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog, simpledialog
import subprocess
import threading
import sqlite3
import struct
import os
import sys
import json
import time
import logging
from datetime import datetime

# ============================================================
# Resolve paths
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVER_DIR = os.path.dirname(SCRIPT_DIR)
DEFAULT_DB = os.path.join(SERVER_DIR, "dd_world.db")
DEFAULT_PORT = 8020
LOG_DIR = os.path.join(SERVER_DIR, "logs")
CONFIG_FILE = os.path.join(SERVER_DIR, "dd_admin_config.json")

# Ensure log dir exists
os.makedirs(LOG_DIR, exist_ok=True)

# Admin GUI log
ADMIN_LOG_FILE = os.path.join(LOG_DIR, f"dd_admin_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
admin_log = logging.getLogger("DD-Admin")
admin_log.setLevel(logging.DEBUG)
_fh = logging.FileHandler(ADMIN_LOG_FILE, encoding='utf-8')
_fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
admin_log.addHandler(_fh)


def load_config():
    """Load admin configuration."""
    defaults = {
        "host": "0.0.0.0",
        "port": DEFAULT_PORT,
        "db_path": DEFAULT_DB,
        "client_mode": "auto",
        "auto_start": False,
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                cfg = json.load(f)
                defaults.update(cfg)
        except Exception:
            pass
    return defaults


def save_config(cfg):
    """Save admin configuration."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(cfg, f, indent=2)


# ============================================================
# Game Data Editor — in-memory copy of game_data tables
# ============================================================
# We import and allow live editing of these tables
try:
    from . import game_data as gd
    from .config import (EXP_THRESHOLDS, STAT_GROWTH, DEFAULT_BASE_STATS,
                         CLASS_NAMES, MAX_LEVEL)
except ImportError:
    # Running standalone
    sys.path.insert(0, os.path.dirname(SCRIPT_DIR))
    from dragons_dream_server_v4 import game_data as gd
    from dragons_dream_server_v4.config import (EXP_THRESHOLDS, STAT_GROWTH,
                                                 DEFAULT_BASE_STATS, CLASS_NAMES, MAX_LEVEL)


class AdminGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Dragon's Dream Revival Server v4 — Admin Panel")
        self.root.geometry("1200x800")
        self.root.minsize(900, 600)

        self.config = load_config()
        self.server_process = None
        self.server_running = False
        self.log_tail_thread = None
        self.db_conn = None

        self._build_ui()
        self._load_state()

        admin_log.info("Admin GUI started. Log: %s", ADMIN_LOG_FILE)
        self.log_admin(f"Admin GUI started. Log file: {ADMIN_LOG_FILE}")

    def _build_ui(self):
        """Build the main UI."""
        # Menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Open Database...", command=self._open_db_dialog)
        file_menu.add_command(label="View Server Logs...", command=self._open_log_viewer)
        file_menu.add_separator()
        file_menu.add_command(label="Export Config", command=self._export_config)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        # Status bar
        self.status_var = tk.StringVar(value="Server: STOPPED")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self._build_server_tab()
        self._build_characters_tab()
        self._build_items_tab()
        self._build_monsters_tab()
        self._build_skills_tab()
        self._build_zones_tab()
        self._build_shops_tab()
        self._build_balance_tab()
        self._build_log_tab()

    # ============================================================
    # TAB 1: Server Control
    # ============================================================
    def _build_server_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Server Control")

        # Connection settings
        settings_frame = ttk.LabelFrame(tab, text="Server Settings")
        settings_frame.pack(fill=tk.X, padx=10, pady=5)

        row = ttk.Frame(settings_frame)
        row.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(row, text="Host:").pack(side=tk.LEFT)
        self.host_var = tk.StringVar(value=self.config.get("host", "0.0.0.0"))
        ttk.Entry(row, textvariable=self.host_var, width=20).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="Port:").pack(side=tk.LEFT)
        self.port_var = tk.IntVar(value=self.config.get("port", DEFAULT_PORT))
        ttk.Entry(row, textvariable=self.port_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Label(row, text="Client mode:").pack(side=tk.LEFT, padx=(15, 0))
        self.client_mode_var = tk.StringVar(value=self.config.get("client_mode", "auto"))
        client_mode = ttk.Combobox(
            row,
            textvariable=self.client_mode_var,
            values=("auto", "saturn", "windows"),
            width=10,
            state="readonly",
        )
        client_mode.pack(side=tk.LEFT, padx=5)

        row2 = ttk.Frame(settings_frame)
        row2.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(row2, text="Database:").pack(side=tk.LEFT)
        self.db_var = tk.StringVar(value=self.config.get("db_path", DEFAULT_DB))
        ttk.Entry(row2, textvariable=self.db_var, width=60).pack(side=tk.LEFT, padx=5)
        ttk.Button(row2, text="Browse", command=self._browse_db).pack(side=tk.LEFT)

        # Control buttons
        ctrl_frame = ttk.Frame(tab)
        ctrl_frame.pack(fill=tk.X, padx=10, pady=10)

        self.start_btn = ttk.Button(ctrl_frame, text="START SERVER",
                                     command=self._start_server)
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = ttk.Button(ctrl_frame, text="STOP SERVER",
                                    command=self._stop_server, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(ctrl_frame, text="Save Settings",
                    command=self._save_settings).pack(side=tk.LEFT, padx=5)

        ttk.Button(ctrl_frame, text="Refresh DB",
                    command=self._refresh_db).pack(side=tk.LEFT, padx=5)

        # Server output
        output_frame = ttk.LabelFrame(tab, text="Server Output (Live)")
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.server_output = scrolledtext.ScrolledText(output_frame, height=20,
                                                        font=("Consolas", 9),
                                                        state=tk.DISABLED, wrap=tk.WORD)
        self.server_output.pack(fill=tk.BOTH, expand=True)

    # ============================================================
    # TAB 2: Characters
    # ============================================================
    def _build_characters_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Characters")

        # Toolbar
        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(toolbar, text="Refresh", command=self._refresh_characters).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Edit Selected", command=self._edit_character).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Delete Selected", command=self._delete_character).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Create New", command=self._create_character).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Reset Stats", command=self._reset_char_stats).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Set Gold", command=self._set_char_gold).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Set Level", command=self._set_char_level).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Set EXP", command=self._set_char_exp).pack(side=tk.LEFT, padx=2)

        # Character list
        cols = ("ID", "Name", "Class", "Level", "EXP", "Gold", "Zone", "Map",
                "HP", "MP", "STR", "VIT", "INT", "MND", "AGI", "DEX")
        self.char_tree = ttk.Treeview(tab, columns=cols, show='headings', height=20)
        for c in cols:
            self.char_tree.heading(c, text=c)
            w = 50 if c not in ("Name", "ID") else 80
            if c == "Name":
                w = 120
            self.char_tree.column(c, width=w, minwidth=40)

        vsb = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=self.char_tree.yview)
        self.char_tree.configure(yscrollcommand=vsb.set)
        self.char_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        vsb.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

    # ============================================================
    # TAB 3: Items
    # ============================================================
    def _build_items_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Items")

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(toolbar, text="Refresh", command=self._refresh_items).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Edit Selected", command=self._edit_item).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Add New Item", command=self._add_item).pack(side=tk.LEFT, padx=2)

        cols = ("ID", "Name", "Type", "SubType", "Slot", "Price",
                "ATK", "DEF", "INT", "MND", "AGI", "DEX", "LUK", "CHA")
        self.item_tree = ttk.Treeview(tab, columns=cols, show='headings', height=20)
        for c in cols:
            self.item_tree.heading(c, text=c)
            w = 50 if c != "Name" else 120
            self.item_tree.column(c, width=w, minwidth=40)
        self.item_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # ============================================================
    # TAB 4: Monsters
    # ============================================================
    def _build_monsters_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Monsters")

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(toolbar, text="Refresh", command=self._refresh_monsters).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Edit Selected", command=self._edit_monster).pack(side=tk.LEFT, padx=2)

        cols = ("ID", "Name", "Level", "HP", "MP", "ATK", "DEF", "AGI",
                "EXP Reward", "Gold Reward", "Drops")
        self.monster_tree = ttk.Treeview(tab, columns=cols, show='headings', height=20)
        for c in cols:
            self.monster_tree.heading(c, text=c)
            w = 70 if c != "Name" else 120
            if c == "Drops":
                w = 150
            self.monster_tree.column(c, width=w, minwidth=40)
        self.monster_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # ============================================================
    # TAB 5: Skills
    # ============================================================
    def _build_skills_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Skills")

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(toolbar, text="Refresh", command=self._refresh_skills).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Edit Selected", command=self._edit_skill).pack(side=tk.LEFT, padx=2)

        cols = ("ID", "Name", "MP Cost", "Power", "Element", "Target",
                "Learn Cost", "Classes")
        self.skill_tree = ttk.Treeview(tab, columns=cols, show='headings', height=20)
        for c in cols:
            self.skill_tree.heading(c, text=c)
            w = 70 if c not in ("Name", "Classes") else 120
            self.skill_tree.column(c, width=w, minwidth=40)
        self.skill_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # ============================================================
    # TAB 6: Zones
    # ============================================================
    def _build_zones_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Zones")

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(toolbar, text="Refresh", command=self._refresh_zones).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Edit Selected", command=self._edit_zone).pack(side=tk.LEFT, padx=2)

        cols = ("ID", "Name", "Map", "Size", "Encounter Rate", "Monster Pool",
                "NPCs", "Shops", "Connections")
        self.zone_tree = ttk.Treeview(tab, columns=cols, show='headings', height=20)
        for c in cols:
            self.zone_tree.heading(c, text=c)
            w = 80 if c not in ("Name", "Monster Pool", "Connections") else 130
            self.zone_tree.column(c, width=w, minwidth=40)
        self.zone_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # ============================================================
    # TAB 7: Shops
    # ============================================================
    def _build_shops_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Shops")

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(toolbar, text="Refresh", command=self._refresh_shops).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Edit Selected", command=self._edit_shop).pack(side=tk.LEFT, padx=2)

        cols = ("ID", "Name", "Items (IDs)", "Item Names")
        self.shop_tree = ttk.Treeview(tab, columns=cols, show='headings', height=20)
        for c in cols:
            self.shop_tree.heading(c, text=c)
            w = 60 if c == "ID" else 200
            self.shop_tree.column(c, width=w, minwidth=40)
        self.shop_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # ============================================================
    # TAB 8: Balance / Game Rules
    # ============================================================
    def _build_balance_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Balance & Rules")

        canvas = tk.Canvas(tab)
        scrollbar = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # EXP Thresholds
        exp_frame = ttk.LabelFrame(scroll_frame, text="EXP Thresholds (level^2 * 100)")
        exp_frame.pack(fill=tk.X, padx=5, pady=5)
        self.exp_vars = {}
        for level in range(1, MAX_LEVEL + 1):
            row = ttk.Frame(exp_frame)
            row.pack(fill=tk.X, padx=5)
            ttk.Label(row, text=f"Level {level}:", width=10).pack(side=tk.LEFT)
            var = tk.IntVar(value=EXP_THRESHOLDS[level])
            self.exp_vars[level] = var
            ttk.Entry(row, textvariable=var, width=10).pack(side=tk.LEFT, padx=5)

        # Class base stats
        stats_frame = ttk.LabelFrame(scroll_frame, text="Class Base Stats (HP,MP,STR,VIT,INT,MND,AGI,DEX,LUK,CHA)")
        stats_frame.pack(fill=tk.X, padx=5, pady=5)
        self.class_stat_vars = {}
        stat_names = ["HP", "MP", "STR", "VIT", "INT", "MND", "AGI", "DEX", "LUK", "CHA"]
        for cls_id, cls_name in enumerate(CLASS_NAMES):
            row = ttk.Frame(stats_frame)
            row.pack(fill=tk.X, padx=5, pady=1)
            ttk.Label(row, text=f"{cls_name}:", width=10).pack(side=tk.LEFT)
            self.class_stat_vars[cls_id] = {}
            for i, sn in enumerate(stat_names):
                val = DEFAULT_BASE_STATS[cls_id][i]
                var = tk.IntVar(value=val)
                self.class_stat_vars[cls_id][sn] = var
                ttk.Label(row, text=sn, width=4).pack(side=tk.LEFT)
                ttk.Entry(row, textvariable=var, width=5).pack(side=tk.LEFT)

        # Stat growth per level
        growth_frame = ttk.LabelFrame(scroll_frame, text="Stat Growth Per Level")
        growth_frame.pack(fill=tk.X, padx=5, pady=5)
        self.growth_vars = {}
        for cls_id, cls_name in enumerate(CLASS_NAMES):
            row = ttk.Frame(growth_frame)
            row.pack(fill=tk.X, padx=5, pady=1)
            ttk.Label(row, text=f"{cls_name}:", width=10).pack(side=tk.LEFT)
            self.growth_vars[cls_id] = {}
            for i, sn in enumerate(stat_names):
                val = STAT_GROWTH[cls_id][i]
                var = tk.IntVar(value=val)
                self.growth_vars[cls_id][sn] = var
                ttk.Label(row, text=sn, width=4).pack(side=tk.LEFT)
                ttk.Entry(row, textvariable=var, width=4).pack(side=tk.LEFT)

        # Combat formulas
        combat_frame = ttk.LabelFrame(scroll_frame, text="Combat Formulas")
        combat_frame.pack(fill=tk.X, padx=5, pady=5)
        formulas = [
            ("Physical Damage", "base = ATK*2 - DEF, variance +/-15%, min 1"),
            ("Skill Damage", "base_power * (1 + level/10) - DEF/2, variance +/-10%"),
            ("Flee Chance", "50% base + (player_AGI - avg_monster_AGI) * 5%"),
            ("Encounter Rate", "Per-step roll vs zone.encounter_rate (0.0-1.0)"),
            ("Sell Price", "Buy price / 2"),
        ]
        for name, formula in formulas:
            row = ttk.Frame(combat_frame)
            row.pack(fill=tk.X, padx=5, pady=1)
            ttk.Label(row, text=f"{name}:", width=20, anchor='w').pack(side=tk.LEFT)
            ttk.Label(row, text=formula, anchor='w', foreground='blue').pack(side=tk.LEFT)

        # Apply button
        ttk.Button(scroll_frame, text="Apply Balance Changes (Runtime Only)",
                    command=self._apply_balance).pack(padx=5, pady=10)

    # ============================================================
    # TAB 9: Admin Log
    # ============================================================
    def _build_log_tab(self):
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Admin Log")

        toolbar = ttk.Frame(tab)
        toolbar.pack(fill=tk.X, padx=5, pady=2)
        ttk.Button(toolbar, text="Clear", command=self._clear_admin_log).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Save Log As...", command=self._save_admin_log).pack(side=tk.LEFT, padx=2)
        ttk.Label(toolbar, text=f"Log file: {ADMIN_LOG_FILE}",
                   foreground='gray').pack(side=tk.LEFT, padx=10)

        self.admin_log_text = scrolledtext.ScrolledText(tab, height=30,
                                                         font=("Consolas", 9),
                                                         state=tk.DISABLED, wrap=tk.WORD)
        self.admin_log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # ============================================================
    # Server Control Logic
    # ============================================================
    def _start_server(self):
        if self.server_running:
            return

        host = self.host_var.get()
        port = self.port_var.get()
        db_path = self.db_var.get()
        client_mode = self.client_mode_var.get()

        self._save_settings()

        cmd = [sys.executable, "-m", "dragons_dream_server_v4",
               "--host", host, "--port", str(port), "--db", db_path,
               "--client-mode", client_mode]

        try:
            self.server_process = subprocess.Popen(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                cwd=SERVER_DIR, text=True, bufsize=1
            )
            self.server_running = True
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.status_var.set(f"Server: RUNNING on {host}:{port} ({client_mode})")
            self.log_admin(f"Server started: {host}:{port} mode={client_mode} DB={db_path}")
            admin_log.info("Server started: %s:%d mode=%s DB=%s", host, port, client_mode, db_path)

            # Start log tail thread
            self.log_tail_thread = threading.Thread(target=self._tail_server_output, daemon=True)
            self.log_tail_thread.start()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to start server:\n{e}")
            self.log_admin(f"ERROR starting server: {e}")
            admin_log.error("Failed to start server: %s", e)

    def _stop_server(self):
        if not self.server_running or not self.server_process:
            return
        try:
            self.server_process.terminate()
            self.server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.server_process.kill()
        except Exception:
            pass

        self.server_running = False
        self.server_process = None
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.status_var.set("Server: STOPPED")
        self.log_admin("Server stopped")
        admin_log.info("Server stopped")

    def _tail_server_output(self):
        """Read server stdout in a background thread."""
        try:
            for line in iter(self.server_process.stdout.readline, ''):
                if not self.server_running:
                    break
                self.root.after(0, self._append_server_output, line)
        except Exception:
            pass
        finally:
            self.root.after(0, self._on_server_exit)

    def _append_server_output(self, text):
        self.server_output.config(state=tk.NORMAL)
        self.server_output.insert(tk.END, text)
        self.server_output.see(tk.END)
        self.server_output.config(state=tk.DISABLED)

    def _on_server_exit(self):
        if self.server_running:
            self.server_running = False
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.status_var.set("Server: STOPPED (exited)")
            self.log_admin("Server process exited")

    # ============================================================
    # Database Access
    # ============================================================
    def _get_db(self):
        """Get or open a database connection."""
        db_path = self.db_var.get()
        if not os.path.exists(db_path):
            messagebox.showwarning("Database", f"Database not found: {db_path}\n"
                                   "Start the server once to create it.")
            return None
        try:
            if self.db_conn:
                self.db_conn.close()
            self.db_conn = sqlite3.connect(db_path)
            self.db_conn.row_factory = sqlite3.Row
            return self.db_conn
        except Exception as e:
            messagebox.showerror("Database Error", str(e))
            return None

    def _refresh_db(self):
        """Refresh all DB-backed tabs."""
        self._refresh_characters()
        self.log_admin("Database refreshed")

    # ============================================================
    # Character Management
    # ============================================================
    def _refresh_characters(self):
        db = self._get_db()
        if not db:
            return
        for row in self.char_tree.get_children():
            self.char_tree.delete(row)

        try:
            rows = db.execute("SELECT * FROM characters ORDER BY char_id").fetchall()
            for r in rows:
                name_bytes = bytes(r['char_name'])
                try:
                    name = name_bytes.rstrip(b'\x00').decode('shift_jis', errors='replace')
                except Exception:
                    name = name_bytes.hex()

                base = bytes(r['base_stats'])
                stats = []
                for i in range(min(8, len(base) // 2)):
                    stats.append(struct.unpack_from('>H', base, i * 2)[0])
                while len(stats) < 8:
                    stats.append(0)

                cls_name = CLASS_NAMES[r['char_class']] if r['char_class'] < len(CLASS_NAMES) else str(r['char_class'])

                self.char_tree.insert('', tk.END, values=(
                    r['char_id'], name, cls_name, r['char_level'],
                    r['experience'], r['gold'], r['zone_id'], r['map_id'],
                    stats[0], stats[1], stats[2], stats[3],
                    stats[4], stats[5], stats[6], stats[7]
                ))
            self.log_admin(f"Loaded {len(rows)} characters from DB")
        except Exception as e:
            self.log_admin(f"Error loading characters: {e}")

    def _edit_character(self):
        sel = self.char_tree.selection()
        if not sel:
            messagebox.showinfo("Edit", "Select a character first")
            return
        values = self.char_tree.item(sel[0])['values']
        char_id = values[0]

        db = self._get_db()
        if not db:
            return
        row = db.execute("SELECT * FROM characters WHERE char_id=?", (char_id,)).fetchone()
        if not row:
            return

        # Open edit dialog
        dlg = tk.Toplevel(self.root)
        dlg.title(f"Edit Character #{char_id}")
        dlg.geometry("400x500")

        fields = {}
        editable = [("char_class", "Class (0-5)"), ("char_level", "Level (1-16)"),
                     ("experience", "Experience"), ("gold", "Gold"),
                     ("zone_id", "Zone ID"), ("map_id", "Map ID"),
                     ("pos_x", "Pos X"), ("pos_y", "Pos Y"),
                     ("facing", "Facing (1-4)"), ("move_mode", "Move Mode (1-3)")]
        for key, label in editable:
            frame = ttk.Frame(dlg)
            frame.pack(fill=tk.X, padx=10, pady=2)
            ttk.Label(frame, text=label, width=18).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(row[key]))
            fields[key] = var
            ttk.Entry(frame, textvariable=var, width=20).pack(side=tk.LEFT)

        def save():
            try:
                updates = {k: int(v.get()) for k, v in fields.items()}
                sql = "UPDATE characters SET " + ", ".join(f"{k}=?" for k in updates) + " WHERE char_id=?"
                db.execute(sql, list(updates.values()) + [char_id])
                db.commit()
                self.log_admin(f"Updated character #{char_id}: {updates}")
                admin_log.info("Updated character #%d: %s", char_id, updates)
                dlg.destroy()
                self._refresh_characters()
            except Exception as e:
                messagebox.showerror("Error", str(e))

        ttk.Button(dlg, text="Save", command=save).pack(pady=10)

    def _delete_character(self):
        sel = self.char_tree.selection()
        if not sel:
            return
        char_id = self.char_tree.item(sel[0])['values'][0]
        if not messagebox.askyesno("Confirm", f"Delete character #{char_id}?"):
            return
        db = self._get_db()
        if db:
            db.execute("DELETE FROM inventory WHERE char_id=?", (char_id,))
            db.execute("DELETE FROM skills WHERE char_id=?", (char_id,))
            db.execute("DELETE FROM characters WHERE char_id=?", (char_id,))
            db.commit()
            self.log_admin(f"Deleted character #{char_id}")
            admin_log.info("Deleted character #%d", char_id)
            self._refresh_characters()

    def _create_character(self):
        name = simpledialog.askstring("New Character", "Character name:")
        if not name:
            return
        cls = simpledialog.askinteger("New Character", "Class (0=War,1=Mage,2=Priest,3=Thief,4=Ranger,5=Bard):",
                                       initialvalue=0, minvalue=0, maxvalue=5)
        if cls is None:
            return

        db = self._get_db()
        if not db:
            return

        try:
            from .db import Database as DB
            temp_db = DB.__new__(DB)
            temp_db.conn = db
            char_id = temp_db.create_character(name.encode('shift_jis', errors='replace'), cls)
            self.log_admin(f"Created character '{name}' (class={cls}) -> ID={char_id}")
            admin_log.info("Created character '%s' class=%d id=%d", name, cls, char_id)
            self._refresh_characters()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def _set_char_gold(self):
        sel = self.char_tree.selection()
        if not sel:
            return
        char_id = self.char_tree.item(sel[0])['values'][0]
        gold = simpledialog.askinteger("Set Gold", "New gold amount:", initialvalue=1000, minvalue=0)
        if gold is None:
            return
        db = self._get_db()
        if db:
            db.execute("UPDATE characters SET gold=? WHERE char_id=?", (gold, char_id))
            db.commit()
            self.log_admin(f"Set character #{char_id} gold={gold}")
            self._refresh_characters()

    def _set_char_level(self):
        sel = self.char_tree.selection()
        if not sel:
            return
        char_id = self.char_tree.item(sel[0])['values'][0]
        level = simpledialog.askinteger("Set Level", "New level:", initialvalue=1, minvalue=1, maxvalue=16)
        if level is None:
            return
        db = self._get_db()
        if db:
            db.execute("UPDATE characters SET char_level=? WHERE char_id=?", (level, char_id))
            db.commit()
            self.log_admin(f"Set character #{char_id} level={level}")
            self._refresh_characters()

    def _set_char_exp(self):
        sel = self.char_tree.selection()
        if not sel:
            return
        char_id = self.char_tree.item(sel[0])['values'][0]
        exp = simpledialog.askinteger("Set EXP", "New experience:", initialvalue=0, minvalue=0)
        if exp is None:
            return
        db = self._get_db()
        if db:
            db.execute("UPDATE characters SET experience=? WHERE char_id=?", (exp, char_id))
            db.commit()
            self.log_admin(f"Set character #{char_id} exp={exp}")
            self._refresh_characters()

    def _reset_char_stats(self):
        sel = self.char_tree.selection()
        if not sel:
            return
        char_id = self.char_tree.item(sel[0])['values'][0]
        if not messagebox.askyesno("Reset Stats", f"Reset character #{char_id} stats to class defaults?"):
            return
        db = self._get_db()
        if not db:
            return
        row = db.execute("SELECT char_class, char_level FROM characters WHERE char_id=?",
                          (char_id,)).fetchone()
        if not row:
            return
        cls = row['char_class']
        base = DEFAULT_BASE_STATS.get(cls, DEFAULT_BASE_STATS[0])
        growth = STAT_GROWTH.get(cls, STAT_GROWTH[0])
        # Recalculate for current level
        stats = list(base)
        for lvl in range(1, row['char_level']):
            for i in range(19):
                stats[i] += growth[i]
        blob = bytearray(38)
        for i in range(19):
            struct.pack_into('>H', blob, i * 2, min(stats[i], 65535))
        db.execute("UPDATE characters SET base_stats=?, current_stats=? WHERE char_id=?",
                    (bytes(blob), bytes(blob), char_id))
        db.commit()
        self.log_admin(f"Reset character #{char_id} stats to class {cls} level {row['char_level']} defaults")
        self._refresh_characters()

    # ============================================================
    # Items Management (runtime game_data)
    # ============================================================
    def _refresh_items(self):
        for row in self.item_tree.get_children():
            self.item_tree.delete(row)
        type_names = {0: "Weapon", 1: "Armor", 2: "Shield", 3: "Helm",
                      4: "Accessory", 5: "Consumable", 6: "Key"}
        for item_id, item in sorted(gd.ITEMS.items()):
            name = item.name.rstrip(b'\x00').decode('ascii', errors='replace')
            mods = item.stat_modifiers + [0] * (8 - len(item.stat_modifiers))
            self.item_tree.insert('', tk.END, values=(
                item_id, name, type_names.get(item.type_a, str(item.type_a)),
                item.type_b, item.equip_slot, item.price,
                mods[0], mods[1], mods[2], mods[3], mods[4], mods[5], mods[6], mods[7]
            ))

    def _edit_item(self):
        sel = self.item_tree.selection()
        if not sel:
            return
        item_id = int(self.item_tree.item(sel[0])['values'][0])
        item = gd.ITEMS.get(item_id)
        if not item:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Edit Item #{item_id}")
        dlg.geometry("350x400")

        fields = {}
        name_str = item.name.rstrip(b'\x00').decode('ascii', errors='replace')
        for label, key, val in [
            ("Name", "name", name_str),
            ("Type A", "type_a", item.type_a),
            ("Type B", "type_b", item.type_b),
            ("Equip Slot", "equip_slot", item.equip_slot),
            ("Price", "price", item.price),
        ]:
            row = ttk.Frame(dlg)
            row.pack(fill=tk.X, padx=10, pady=2)
            ttk.Label(row, text=label, width=12).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(val))
            fields[key] = var
            ttk.Entry(row, textvariable=var, width=20).pack(side=tk.LEFT)

        stat_names = ["ATK", "DEF", "INT", "MND", "AGI", "DEX", "LUK", "CHA"]
        stat_vars = []
        for i, sn in enumerate(stat_names):
            row = ttk.Frame(dlg)
            row.pack(fill=tk.X, padx=10, pady=1)
            ttk.Label(row, text=f"Mod {sn}", width=12).pack(side=tk.LEFT)
            val = item.stat_modifiers[i] if i < len(item.stat_modifiers) else 0
            var = tk.IntVar(value=val)
            stat_vars.append(var)
            ttk.Entry(row, textvariable=var, width=10).pack(side=tk.LEFT)

        def save():
            from .protocol import sjis_pad
            item.name = sjis_pad(fields['name'].get(), 16)
            item.type_a = int(fields['type_a'].get())
            item.type_b = int(fields['type_b'].get())
            item.equip_slot = int(fields['equip_slot'].get())
            item.price = int(fields['price'].get())
            item.stat_modifiers = [v.get() for v in stat_vars]
            self.log_admin(f"Updated item #{item_id}: {fields['name'].get()} price={item.price}")
            admin_log.info("Updated item #%d", item_id)
            dlg.destroy()
            self._refresh_items()

        ttk.Button(dlg, text="Save", command=save).pack(pady=10)

    def _add_item(self):
        next_id = max(gd.ITEMS.keys()) + 1 if gd.ITEMS else 1
        from .models import ItemDef
        from .protocol import sjis_pad
        name = simpledialog.askstring("New Item", "Item name:")
        if not name:
            return
        gd.ITEMS[next_id] = ItemDef(next_id, sjis_pad(name, 16), 0, 0, 0, 100, [0]*8)
        self.log_admin(f"Added item #{next_id}: {name}")
        self._refresh_items()

    # ============================================================
    # Monsters Management
    # ============================================================
    def _refresh_monsters(self):
        for row in self.monster_tree.get_children():
            self.monster_tree.delete(row)
        for mid, m in sorted(gd.MONSTERS.items()):
            name = m.name.rstrip(b'\x00').decode('ascii', errors='replace')
            drops = ", ".join(f"#{d[0]}({d[1]}%)" for d in m.drop_table)
            self.monster_tree.insert('', tk.END, values=(
                mid, name, m.level, m.hp, m.mp, m.atk, m.defense, m.agi,
                m.exp_reward, m.gold_reward, drops or "None"
            ))

    def _edit_monster(self):
        sel = self.monster_tree.selection()
        if not sel:
            return
        mid = int(self.monster_tree.item(sel[0])['values'][0])
        m = gd.MONSTERS.get(mid)
        if not m:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Edit Monster #{mid}")
        dlg.geometry("380x450")

        fields = {}
        name_str = m.name.rstrip(b'\x00').decode('ascii', errors='replace')
        for label, key, val in [
            ("Name", "name", name_str), ("Level", "level", m.level),
            ("HP", "hp", m.hp), ("MP", "mp", m.mp),
            ("ATK", "atk", m.atk), ("DEF", "defense", m.defense),
            ("AGI", "agi", m.agi), ("EXP Reward", "exp_reward", m.exp_reward),
            ("Gold Reward", "gold_reward", m.gold_reward),
            ("Drops (id:chance,...)", "drops", ",".join(f"{d[0]}:{d[1]}" for d in m.drop_table)),
        ]:
            row = ttk.Frame(dlg)
            row.pack(fill=tk.X, padx=10, pady=2)
            ttk.Label(row, text=label, width=16).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(val))
            fields[key] = var
            ttk.Entry(row, textvariable=var, width=20).pack(side=tk.LEFT)

        def save():
            from .protocol import sjis_pad
            m.name = sjis_pad(fields['name'].get(), 16)
            for k in ['level', 'hp', 'mp', 'atk', 'defense', 'agi', 'exp_reward', 'gold_reward']:
                setattr(m, k, int(fields[k].get()))
            drops_str = fields['drops'].get().strip()
            if drops_str:
                m.drop_table = []
                for pair in drops_str.split(','):
                    parts = pair.strip().split(':')
                    if len(parts) == 2:
                        m.drop_table.append((int(parts[0]), int(parts[1])))
            else:
                m.drop_table = []
            self.log_admin(f"Updated monster #{mid}: {fields['name'].get()}")
            admin_log.info("Updated monster #%d", mid)
            dlg.destroy()
            self._refresh_monsters()

        ttk.Button(dlg, text="Save", command=save).pack(pady=10)

    # ============================================================
    # Skills Management
    # ============================================================
    def _refresh_skills(self):
        for row in self.skill_tree.get_children():
            self.skill_tree.delete(row)
        elem_names = {0: "None", 1: "Fire", 2: "Ice", 3: "Thunder", 4: "Holy", 5: "Dark"}
        target_names = {0: "1 Enemy", 1: "All Enemy", 2: "1 Ally", 3: "All Ally", 4: "Self"}
        for sid, s in sorted(gd.SKILLS.items()):
            name = s.name.rstrip(b'\x00').decode('ascii', errors='replace')
            classes = ",".join(CLASS_NAMES[c] if c < len(CLASS_NAMES) else str(c)
                              for c in s.class_req)
            self.skill_tree.insert('', tk.END, values=(
                sid, name, s.mp_cost, s.base_power,
                elem_names.get(s.element, str(s.element)),
                target_names.get(s.target_type, str(s.target_type)),
                s.learn_cost, classes
            ))

    def _edit_skill(self):
        sel = self.skill_tree.selection()
        if not sel:
            return
        sid = int(self.skill_tree.item(sel[0])['values'][0])
        s = gd.SKILLS.get(sid)
        if not s:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Edit Skill #{sid}")
        dlg.geometry("380x380")

        fields = {}
        name_str = s.name.rstrip(b'\x00').decode('ascii', errors='replace')
        for label, key, val in [
            ("Name", "name", name_str), ("MP Cost", "mp_cost", s.mp_cost),
            ("Power", "base_power", s.base_power), ("Element (0-5)", "element", s.element),
            ("Target (0-4)", "target_type", s.target_type),
            ("Learn Cost", "learn_cost", s.learn_cost),
            ("Class IDs (comma)", "class_req", ",".join(str(c) for c in s.class_req)),
        ]:
            row = ttk.Frame(dlg)
            row.pack(fill=tk.X, padx=10, pady=2)
            ttk.Label(row, text=label, width=16).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(val))
            fields[key] = var
            ttk.Entry(row, textvariable=var, width=20).pack(side=tk.LEFT)

        def save():
            from .protocol import sjis_pad
            s.name = sjis_pad(fields['name'].get(), 16)
            s.mp_cost = int(fields['mp_cost'].get())
            s.base_power = int(fields['base_power'].get())
            s.element = int(fields['element'].get())
            s.target_type = int(fields['target_type'].get())
            s.learn_cost = int(fields['learn_cost'].get())
            s.class_req = [int(c.strip()) for c in fields['class_req'].get().split(',') if c.strip()]
            self.log_admin(f"Updated skill #{sid}: {fields['name'].get()}")
            dlg.destroy()
            self._refresh_skills()

        ttk.Button(dlg, text="Save", command=save).pack(pady=10)

    # ============================================================
    # Zones Management
    # ============================================================
    def _refresh_zones(self):
        for row in self.zone_tree.get_children():
            self.zone_tree.delete(row)
        for zid, z in sorted(gd.ZONES.items()):
            monsters = ",".join(str(m) for m in z.monster_pool) or "None"
            npcs = str(len(z.npc_list))
            shops = ",".join(str(s) for s in z.shop_ids) or "None"
            conns = ",".join(str(c) for c in gd.ZONE_CONNECTIONS.get(zid, []))
            self.zone_tree.insert('', tk.END, values=(
                zid, z.name, z.map_id, f"{z.width}x{z.height}",
                f"{z.encounter_rate:.2f}", monsters, npcs, shops, conns
            ))

    def _edit_zone(self):
        sel = self.zone_tree.selection()
        if not sel:
            return
        zid = int(self.zone_tree.item(sel[0])['values'][0])
        z = gd.ZONES.get(zid)
        if not z:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Edit Zone #{zid}")
        dlg.geometry("400x350")

        fields = {}
        for label, key, val in [
            ("Name", "name", z.name),
            ("Encounter Rate", "encounter_rate", z.encounter_rate),
            ("Monster Pool (IDs)", "monsters", ",".join(str(m) for m in z.monster_pool)),
            ("Shop IDs", "shops", ",".join(str(s) for s in z.shop_ids)),
            ("Connections", "conns", ",".join(str(c) for c in gd.ZONE_CONNECTIONS.get(zid, []))),
        ]:
            row = ttk.Frame(dlg)
            row.pack(fill=tk.X, padx=10, pady=2)
            ttk.Label(row, text=label, width=16).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(val))
            fields[key] = var
            ttk.Entry(row, textvariable=var, width=25).pack(side=tk.LEFT)

        def save():
            z.name = fields['name'].get()
            z.encounter_rate = float(fields['encounter_rate'].get())
            mp = fields['monsters'].get().strip()
            z.monster_pool = [int(m.strip()) for m in mp.split(',') if m.strip()] if mp else []
            sp = fields['shops'].get().strip()
            z.shop_ids = [int(s.strip()) for s in sp.split(',') if s.strip()] if sp else []
            cp = fields['conns'].get().strip()
            gd.ZONE_CONNECTIONS[zid] = [int(c.strip()) for c in cp.split(',') if c.strip()] if cp else []
            self.log_admin(f"Updated zone #{zid}: {z.name} enc_rate={z.encounter_rate}")
            dlg.destroy()
            self._refresh_zones()

        ttk.Button(dlg, text="Save", command=save).pack(pady=10)

    # ============================================================
    # Shops Management
    # ============================================================
    def _refresh_shops(self):
        for row in self.shop_tree.get_children():
            self.shop_tree.delete(row)
        for sid, s in sorted(gd.SHOPS.items()):
            item_names = []
            for iid in s.item_ids:
                item = gd.ITEMS.get(iid)
                if item:
                    item_names.append(item.name.rstrip(b'\x00').decode('ascii', errors='replace'))
                else:
                    item_names.append(f"?{iid}")
            self.shop_tree.insert('', tk.END, values=(
                sid, s.name, ",".join(str(i) for i in s.item_ids),
                ", ".join(item_names)
            ))

    def _edit_shop(self):
        sel = self.shop_tree.selection()
        if not sel:
            return
        sid = int(self.shop_tree.item(sel[0])['values'][0])
        s = gd.SHOPS.get(sid)
        if not s:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Edit Shop #{sid}")
        dlg.geometry("400x200")

        fields = {}
        for label, key, val in [
            ("Name", "name", s.name),
            ("Item IDs (comma)", "items", ",".join(str(i) for i in s.item_ids)),
        ]:
            row = ttk.Frame(dlg)
            row.pack(fill=tk.X, padx=10, pady=5)
            ttk.Label(row, text=label, width=14).pack(side=tk.LEFT)
            var = tk.StringVar(value=str(val))
            fields[key] = var
            ttk.Entry(row, textvariable=var, width=30).pack(side=tk.LEFT)

        def save():
            s.name = fields['name'].get()
            ip = fields['items'].get().strip()
            s.item_ids = [int(i.strip()) for i in ip.split(',') if i.strip()] if ip else []
            self.log_admin(f"Updated shop #{sid}: {s.name} items={s.item_ids}")
            dlg.destroy()
            self._refresh_shops()

        ttk.Button(dlg, text="Save", command=save).pack(pady=10)

    # ============================================================
    # Balance
    # ============================================================
    def _apply_balance(self):
        """Apply balance changes to runtime game data (NOT persisted to .py files)."""
        # EXP thresholds
        for level, var in self.exp_vars.items():
            EXP_THRESHOLDS[level] = var.get()

        # Class base stats
        for cls_id, stat_dict in self.class_stat_vars.items():
            stat_names = ["HP", "MP", "STR", "VIT", "INT", "MND", "AGI", "DEX", "LUK", "CHA"]
            for i, sn in enumerate(stat_names):
                DEFAULT_BASE_STATS[cls_id][i] = stat_dict[sn].get()

        # Stat growth
        for cls_id, stat_dict in self.growth_vars.items():
            stat_names = ["HP", "MP", "STR", "VIT", "INT", "MND", "AGI", "DEX", "LUK", "CHA"]
            for i, sn in enumerate(stat_names):
                STAT_GROWTH[cls_id][i] = stat_dict[sn].get()

        self.log_admin("Applied balance changes (runtime only — restart will reset)")
        messagebox.showinfo("Balance", "Balance changes applied to running server.\n"
                           "Changes are runtime only and will reset on restart.\n"
                           "Edit config.py to make permanent changes.")

    # ============================================================
    # Logging
    # ============================================================
    def log_admin(self, msg):
        """Write to the admin log tab and file."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        text = f"[{timestamp}] {msg}\n"
        self.admin_log_text.config(state=tk.NORMAL)
        self.admin_log_text.insert(tk.END, text)
        self.admin_log_text.see(tk.END)
        self.admin_log_text.config(state=tk.DISABLED)
        admin_log.info(msg)

    def _clear_admin_log(self):
        self.admin_log_text.config(state=tk.NORMAL)
        self.admin_log_text.delete(1.0, tk.END)
        self.admin_log_text.config(state=tk.DISABLED)

    def _save_admin_log(self):
        path = filedialog.asksaveasfilename(defaultextension=".log",
                                             filetypes=[("Log files", "*.log"), ("All", "*.*")])
        if path:
            self.admin_log_text.config(state=tk.NORMAL)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(self.admin_log_text.get(1.0, tk.END))
            self.admin_log_text.config(state=tk.DISABLED)
            self.log_admin(f"Log saved to {path}")

    # ============================================================
    # Misc
    # ============================================================
    def _browse_db(self):
        path = filedialog.askopenfilename(filetypes=[("SQLite DB", "*.db"), ("All", "*.*")])
        if path:
            self.db_var.set(path)

    def _open_db_dialog(self):
        self._browse_db()
        self._refresh_db()

    def _open_log_viewer(self):
        """Open a file browser to select and view a log file."""
        path = filedialog.askopenfilename(initialdir=LOG_DIR,
                                           filetypes=[("Log files", "*.log"), ("All", "*.*")])
        if not path:
            return

        dlg = tk.Toplevel(self.root)
        dlg.title(f"Log Viewer: {os.path.basename(path)}")
        dlg.geometry("900x600")

        text = scrolledtext.ScrolledText(dlg, font=("Consolas", 9), wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                text.insert(tk.END, f.read())
        except Exception as e:
            text.insert(tk.END, f"Error reading file: {e}")

    def _export_config(self):
        """Export current game data as JSON for backup/sharing."""
        path = filedialog.asksaveasfilename(defaultextension=".json",
                                             filetypes=[("JSON", "*.json")])
        if not path:
            return

        export = {
            "items": {},
            "monsters": {},
            "skills": {},
            "zones": {},
            "shops": {},
            "exp_thresholds": list(EXP_THRESHOLDS),
        }
        for iid, item in gd.ITEMS.items():
            export["items"][str(iid)] = {
                "name": item.name.rstrip(b'\x00').decode('ascii', errors='replace'),
                "type_a": item.type_a, "type_b": item.type_b,
                "equip_slot": item.equip_slot, "price": item.price,
                "stat_modifiers": item.stat_modifiers,
            }
        for mid, m in gd.MONSTERS.items():
            export["monsters"][str(mid)] = {
                "name": m.name.rstrip(b'\x00').decode('ascii', errors='replace'),
                "level": m.level, "hp": m.hp, "mp": m.mp,
                "atk": m.atk, "defense": m.defense, "agi": m.agi,
                "exp_reward": m.exp_reward, "gold_reward": m.gold_reward,
                "drop_table": m.drop_table,
            }
        for sid, s in gd.SKILLS.items():
            export["skills"][str(sid)] = {
                "name": s.name.rstrip(b'\x00').decode('ascii', errors='replace'),
                "mp_cost": s.mp_cost, "base_power": s.base_power,
                "element": s.element, "target_type": s.target_type,
                "learn_cost": s.learn_cost, "class_req": s.class_req,
            }
        for zid, z in gd.ZONES.items():
            export["zones"][str(zid)] = {
                "name": z.name, "encounter_rate": z.encounter_rate,
                "monster_pool": z.monster_pool, "shop_ids": z.shop_ids,
                "connections": gd.ZONE_CONNECTIONS.get(zid, []),
            }
        for sid, s in gd.SHOPS.items():
            export["shops"][str(sid)] = {"name": s.name, "item_ids": s.item_ids}

        with open(path, 'w') as f:
            json.dump(export, f, indent=2)
        self.log_admin(f"Config exported to {path}")

    def _save_settings(self):
        self.config["host"] = self.host_var.get()
        self.config["port"] = self.port_var.get()
        self.config["db_path"] = self.db_var.get()
        self.config["client_mode"] = self.client_mode_var.get()
        save_config(self.config)
        self.log_admin("Settings saved")

    def _load_state(self):
        """Initial load of all tabs."""
        self._refresh_items()
        self._refresh_monsters()
        self._refresh_skills()
        self._refresh_zones()
        self._refresh_shops()
        # Characters loaded on-demand (requires DB)

    def _on_close(self):
        if self.server_running:
            if messagebox.askyesno("Quit", "Server is running. Stop and quit?"):
                self._stop_server()
            else:
                return
        if self.db_conn:
            try:
                self.db_conn.close()
            except Exception:
                pass
        self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.mainloop()


def main():
    app = AdminGUI()
    app.run()


if __name__ == '__main__':
    main()
