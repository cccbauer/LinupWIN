import flet as ft
from collections import deque
import sqlite3
import os
import math
import random
from datetime import datetime
import asyncio
import tempfile

# --- GROUP CONFIGURATION ---
ROJOS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
GRUPOS_MAESTROS = {
    '34': {1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34},
    '35': {2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35},
    '36': {3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36},
    '1a': set(range(1, 13)), '2a': set(range(13, 25)), '3a': set(range(25, 37)),
    'Z0': {0, 3, 12, 15, 26, 32, 35},
    'ZG': {2, 4, 7, 18, 21, 19, 22, 25, 28, 29},
    'ZP': {5, 8, 10, 11, 13, 16, 23, 24, 27, 30, 33, 36},
    'H':  {1, 6, 9, 14, 17, 20, 31, 34},
    'T1': {2, 4, 6, 13, 15, 17, 19, 21, 25, 27, 32, 34},
    'T2': {1, 5, 8, 10, 11, 16, 20, 23, 24, 30, 33, 36},
    'T3': {0, 3, 7, 9, 12, 14, 18, 22, 26, 28, 29, 31, 35},
    # Wave zones — wheel position relative to 0
    # W1 Lip:    0 + 6 each side  → 13 numbers
    'W1': {0, 2, 3, 4, 7, 12, 15, 19, 21, 26, 28, 32, 35},
    # W2 Curls:  next 6 each side → 12 numbers
    'W2': {6, 9, 13, 14, 17, 18, 22, 25, 27, 29, 31, 34},
    # W3 Through: remaining       → 12 numbers
    'W3': {1, 5, 8, 10, 11, 16, 20, 23, 24, 30, 33, 36},
}
PROG_FIBO = [1, 1, 2, 3, 5, 8, 13, 21, 34, 55]
C_COL, C_DOC, C_SEC, C_SET, C_WAV = '#00d2ff', '#2ecc71', '#e67e22', '#9b59b6', '#e91e63'
NUM_COLS = 20

# ── Wheel neighbours (European single-zero wheel order) ──────────────
WHEEL_ORDER = [0,32,15,19,4,21,2,25,17,34,6,27,13,36,11,30,8,23,10,5,24,16,33,1,20,14,31,9,22,18,29,7,28,12,35,3,26]
WHEEL_NEIGHBORS = {
    n: {WHEEL_ORDER[(i - 1) % 37], WHEEL_ORDER[(i + 1) % 37]}
    for i, n in enumerate(WHEEL_ORDER)
}
# Live dozen groups: each dozen + direct wheel neighbours of every member
def _live_grp(base):
    return base | set().union(*(WHEEL_NEIGHBORS[n] for n in base))

LIVE_FILTER_SETS = {
    'R':     ROJOS,
    'B':     set(range(1, 37)) - ROJOS,
    '1-18':  set(range(1, 19)),
    'Even':  {n for n in range(2, 37, 2)},
    'Odd':   {n for n in range(1, 37, 2)},
    '19-36': set(range(19, 37)),
}
# Suffix maps for building group keys from filter
_DOC_SFX = {None: '_L', 'R': '_LR', 'B': '_LB',
            '1-18': '_L18', 'Even': '_LE', 'Odd': '_LO', '19-36': '_L36'}
_COL_SFX = {None: '', 'R': '_R', 'B': '_B',
            '1-18': '_18', 'Even': '_E', 'Odd': '_O', '19-36': '_36'}

for _d in ('1a', '2a', '3a'):
    GRUPOS_MAESTROS[f'{_d}_L']   = _live_grp(GRUPOS_MAESTROS[_d])
    GRUPOS_MAESTROS[f'{_d}_LR']  = GRUPOS_MAESTROS[f'{_d}_L'] & ROJOS
    GRUPOS_MAESTROS[f'{_d}_LB']  = GRUPOS_MAESTROS[f'{_d}_L'] - ROJOS - {0}
    GRUPOS_MAESTROS[f'{_d}_L18'] = GRUPOS_MAESTROS[f'{_d}_L'] & LIVE_FILTER_SETS['1-18']
    GRUPOS_MAESTROS[f'{_d}_LE']  = GRUPOS_MAESTROS[f'{_d}_L'] & LIVE_FILTER_SETS['Even']
    GRUPOS_MAESTROS[f'{_d}_LO']  = GRUPOS_MAESTROS[f'{_d}_L'] & LIVE_FILTER_SETS['Odd']
    GRUPOS_MAESTROS[f'{_d}_L36'] = GRUPOS_MAESTROS[f'{_d}_L'] & LIVE_FILTER_SETS['19-36']
# 0 is a wheel neighbour of 3a numbers (26, 32) → include it in every 3a filtered group
for _sfx in ('_LR', '_LB', '_L18', '_LE', '_LO', '_L36'):
    GRUPOS_MAESTROS[f'3a{_sfx}'] |= {0}
for _c in ('34', '35', '36'):
    GRUPOS_MAESTROS[f'{_c}_R']  = GRUPOS_MAESTROS[_c] & ROJOS
    GRUPOS_MAESTROS[f'{_c}_B']  = GRUPOS_MAESTROS[_c] - ROJOS - {0}
    GRUPOS_MAESTROS[f'{_c}_18'] = GRUPOS_MAESTROS[_c] & LIVE_FILTER_SETS['1-18']
    GRUPOS_MAESTROS[f'{_c}_E']  = GRUPOS_MAESTROS[_c] & LIVE_FILTER_SETS['Even']
    GRUPOS_MAESTROS[f'{_c}_O']  = GRUPOS_MAESTROS[_c] & LIVE_FILTER_SETS['Odd']
    GRUPOS_MAESTROS[f'{_c}_36'] = GRUPOS_MAESTROS[_c] & LIVE_FILTER_SETS['19-36']
# All live / filtered groups are inside bets (one chip per number)
GRUPOS_LIVE_INSIDE: set = set()
for _d in ('1a', '2a', '3a'):
    for _sfx in _DOC_SFX.values():
        GRUPOS_LIVE_INSIDE.add(f'{_d}{_sfx}')
for _c in ('34', '35', '36'):
    for _sfx in _COL_SFX.values():
        if _sfx:   # empty suffix = standard column (stays as outside)
            GRUPOS_LIVE_INSIDE.add(f'{_c}{_sfx}')


class LinupApp:
    def __init__(self, page: ft.Page):
        self.page = page

        self.mixer_btns: dict = {}
        self.lbl_bank = None
        self.lbl_inv  = None
        self.lbl_pl   = None
        self.sug_row  = None
        self.btn_inv  = None
        self.reg_rows_box   = None
        self.reg_header_row = None
        self._on_game_screen = False
        self.current_investment_id = None
        self.lbl_inv_pl = None

        self.page.title      = "Linup v12.0"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.bgcolor    = '#1a1a1a'
        self.page.padding    = 0
        self.page.scroll     = None
        self.page.on_resized = self._on_resize

        # window settings
        self.page.window.width      = 420
        self.page.window.height     = 860
        self.page.window.min_width  = 380
        self.page.window.min_height = 700

        self.root = ft.Container(expand=True, bgcolor='#1a1a1a')
        self.page.add(self.root)
        self.page.update()

        self.show_splash()
        self.init_db()
        self.reset_variables()
        self.page.run_task(self._after_splash)

    async def _after_splash(self):
        await asyncio.sleep(2.0)
        self.show_main_menu()

    # ──────────────────────────────────────────────────────────────────
    # TEXT HELPER
    # ──────────────────────────────────────────────────────────────────
    def _txt(self, label, size=15, bold=True):
        return ft.Text(
            label, size=size,
            weight=ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL,
            text_align=ft.TextAlign.CENTER,
        )

    # ──────────────────────────────────────────────────────────────────
    # RESPONSIVE COLUMN WIDTH
    # ──────────────────────────────────────────────────────────────────
    def _col_width(self):
        w  = self.page.width or 360
        vc = getattr(self, 'visible_cats', {k: True for k in ['basic','cols','docs','secs','thirds','wave']})
        n  = (1
              + (6 if vc.get('basic',  True) else 0)
              + (3 if vc.get('cols',   True) else 0)
              + (3 if vc.get('docs',   True) else 0)
              + (4 if vc.get('secs',   True) else 0)
              + (3 if vc.get('thirds', True) else 0)
              + (3 if vc.get('wave',   True) else 0))
        return max(11, int((w - 4) / max(n, 1)))

    def _on_resize(self, e):
        if self._on_game_screen and self.reg_rows_box is not None:
            self.update_registration_table()

    # ──────────────────────────────────────────────────────────────────
    # DATABASE
    # ──────────────────────────────────────────────────────────────────
    def init_db(self):
        self.db_error = None
        candidates = []
        asp = getattr(self.page, 'app_support_path', None)
        if asp:
            candidates.append(os.path.join(str(asp), "linup_data"))
        candidates += [
            os.path.join(os.path.expanduser("~"), "linup_data"),
            os.path.join(os.getcwd(), "linup_data"),
            os.path.join(tempfile.gettempdir(), "linup_data"),
        ]
        self.db_path = None
        for data_dir in candidates:
            try:
                os.makedirs(data_dir, exist_ok=True)
                db_path = os.path.join(data_dir, "linup_data.db")
                conn = sqlite3.connect(db_path)
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS sesiones "
                    "(id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    " mesa TEXT, fecha TEXT, profit REAL, "
                    " banca_inicial REAL, banca_final REAL)"
                )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS table_stats "
                    "(investment_id INTEGER NOT NULL DEFAULT 0, mesa TEXT NOT NULL, "
                    " wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, "
                    " last_bank REAL DEFAULT 0, "
                    " PRIMARY KEY (investment_id, mesa))"
                )
                # Migration: if old schema had mesa as sole PK, rebuild with investment_id
                try:
                    cols = [r[1] for r in conn.execute(
                        "PRAGMA table_info(table_stats)").fetchall()]
                    if 'investment_id' not in cols:
                        conn.execute(
                            "ALTER TABLE table_stats RENAME TO table_stats_old")
                        conn.execute(
                            "CREATE TABLE table_stats "
                            "(investment_id INTEGER NOT NULL DEFAULT 0, mesa TEXT NOT NULL, "
                            " wins INTEGER DEFAULT 0, losses INTEGER DEFAULT 0, "
                            " last_bank REAL DEFAULT 0, "
                            " PRIMARY KEY (investment_id, mesa))")
                        conn.execute(
                            "INSERT INTO table_stats "
                            "(investment_id, mesa, wins, losses, last_bank) "
                            "SELECT 0, mesa, wins, losses, last_bank FROM table_stats_old")
                        conn.execute("DROP TABLE table_stats_old")
                        conn.commit()
                except Exception:
                    pass
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS investments "
                    "(id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    " name TEXT, capital REAL, created_at TEXT)"
                )
                conn.execute(
                    "CREATE TABLE IF NOT EXISTS investment_tables "
                    "(id INTEGER PRIMARY KEY AUTOINCREMENT, "
                    " investment_id INTEGER, mesa_name TEXT, init_bank REAL)"
                )
                conn.commit()
                try:
                    conn.execute("ALTER TABLE sesiones ADD COLUMN banca_inicial REAL")
                    conn.commit()
                except Exception:
                    pass  # column already exists
                conn.close()
                self.db_path = db_path
                break
            except Exception as ex:
                self.db_error = str(ex)
                continue
        if not self.db_path:
            self.db_error = f"All paths failed. Last: {self.db_error}"

    def _get_conn(self):
        if not self.db_path:
            return None
        try:
            return sqlite3.connect(self.db_path)
        except Exception:
            return None

    def _guardar_sesion(self):
        """Save or update session. Returns (True, None) or (False, error_msg)."""
        try:
            if not self.db_path:
                init_err = getattr(self, "db_error", "unknown")
                raise Exception(f"DB unavailable. Error: {init_err}")
            conn = sqlite3.connect(self.db_path)
            try:
                profit = round(float(self.banca_actual - self.banca_inicial), 2)
                fecha  = datetime.now().strftime("%d/%m %H:%M")
                if self.session_id is not None:
                    conn.execute(
                        "UPDATE sesiones SET profit=?, banca_final=?, fecha=? WHERE id=?",
                        (profit, round(float(self.banca_actual), 2), fecha, self.session_id)
                    )
                else:
                    cursor = conn.execute(
                        "INSERT INTO sesiones (mesa, fecha, profit, banca_inicial, banca_final) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (str(self.nombre_mesa), fecha, profit,
                         round(float(self.banca_inicial), 2),
                         round(float(self.banca_actual), 2))
                    )
                    self.session_id = cursor.lastrowid
                conn.commit()
                return True, None
            finally:
                conn.close()
        except Exception as ex:
            return False, str(ex)

    def _update_table_stats(self, is_win: bool):
        """Increment win or loss counter and update last_bank for this table.
        A break-even session (0% P/L) is not counted as W or L."""
        profit = round(self.banca_actual - self.banca_inicial, 2)
        conn = self._get_conn()
        if not conn:
            return
        try:
            w    = 0 if profit == 0 else (1 if is_win else 0)
            l    = 0 if profit == 0 else (0 if is_win else 1)
            bk   = round(float(self.banca_actual), 2)
            inv  = self.current_investment_id or 0
            conn.execute(
                "INSERT INTO table_stats (investment_id, mesa, wins, losses, last_bank) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(investment_id, mesa) DO UPDATE SET "
                "wins=wins+?, losses=losses+?, last_bank=?",
                (inv, self.nombre_mesa, w, l, bk, w, l, bk)
            )
            conn.commit()
        except Exception:
            pass
        finally:
            conn.close()

    # ──────────────────────────────────────────────────────────────────
    # STATE
    # ──────────────────────────────────────────────────────────────────
    def reset_variables(self):
        self.banca_inicial        = 100.0
        self.banca_actual         = 100.0
        self.idx_fibo_out         = 0
        self.nivel_martingala_out = 0
        self.idx_fibo_in          = 0
        self.nivel_martingala_in  = 0
        self.last_bet_outside     = None
        self.last_prog_state      = True   # was progression on when last bet resolved
        self.last_bank_delta      = 0.0
        self.stop_loss_triggered  = False
        self.activa               = False
        self.free_spin_mode       = False
        self.live_table_mode      = False
        self.live_filter          = None   # None, 'R', 'B'
        self.prog_on              = True   # progression on/off
        self.fixed_multi          = 1      # 1-5 when progression is off
        self.grupos_activos       = []
        self.history_nums         = []
        self.sliding_window       = deque(maxlen=6)
        self.val_fin              = 0.10
        self.val_fout             = 0.30
        self.nombre_mesa          = "TABLE 1"
        self.session_id           = None
        self.inv_name             = ""
        self.inv_capital          = 0.0
        self.inv_other_pl         = 0.0
        # Which column categories are shown in the registration table / mixer
        if not hasattr(self, 'visible_cats'):
            self.visible_cats = {
                'basic':  True,   # R N P I B A
                'cols':   True,   # 34 35 36
                'docs':   True,   # 1a 2a 3a
                'secs':   True,   # Z0 ZG ZP H
                'thirds': True,   # T1 T2 T3
                'wave':   True,   # W1 W2 W3
            }

    # ──────────────────────────────────────────────────────────────────
    # NAVIGATION
    # ──────────────────────────────────────────────────────────────────
    def _close_dlg(self, dlg: ft.AlertDialog):
        """Close a dialog, sync to client, then remove from overlay."""
        try:
            dlg.open = False
            self.page.update()          # client sees dialog close while it's still in overlay
            self.page.overlay.remove(dlg)  # Python-side cleanup — no extra update needed
        except Exception:
            pass

    def _set_view(self, content: ft.Control):
        # Clear any stale dialogs left over from the previous screen
        self.page.overlay.clear()
        self.root.content = content
        self.page.update()

    def _go_home(self, e=None):
        """Return to investment dashboard if inside one, otherwise main menu."""
        if self.current_investment_id is not None:
            inv_id = self.current_investment_id
            self.show_investment_dashboard(inv_id)
        else:
            self.show_main_menu()

    # ──────────────────────────────────────────────────────────────────
    # SPLASH SCREEN
    # ──────────────────────────────────────────────────────────────────
    def show_splash(self):
        self._set_view(
            ft.Container(
                bgcolor='#1a1a1a', expand=True,
                content=ft.Column(
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text("Linup", color='#3498db', size=64,
                                weight=ft.FontWeight.BOLD),
                        ft.Container(height=8),
                        ft.Text("v12.0", color='#7f8c8d', size=18),
                        ft.Container(height=48),
                        ft.ProgressRing(color='#3498db', width=36, height=36,
                                        stroke_width=3),
                    ],
                ),
            )
        )

    # ──────────────────────────────────────────────────────────────────
    # MAIN MENU
    # ──────────────────────────────────────────────────────────────────
    def show_main_menu(self, e=None):
        self._on_game_screen = False
        self.current_investment_id = None
        self._set_view(
            ft.Container(
                bgcolor='#1a1a1a', expand=True, padding=20,
                content=ft.Column(
                    expand=True,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[
                        ft.Text("Linup", color='#3498db', size=42,
                                weight=ft.FontWeight.BOLD),
                        ft.Container(height=40),
                        ft.ElevatedButton(
                            "NEW INVESTMENT",
                            on_click=self.show_new_investment_form,
                            width=280, height=60,
                            style=ft.ButtonStyle(bgcolor='#27ae60',
                                                 color=ft.Colors.WHITE),
                        ),
                        ft.Container(height=12),
                        ft.ElevatedButton(
                            "LOAD INVESTMENT",
                            on_click=self.show_load_investments,
                            width=280, height=60,
                            style=ft.ButtonStyle(bgcolor='#2980b9',
                                                 color=ft.Colors.WHITE),
                        ),
                    ],
                ),
            )
        )

    # ──────────────────────────────────────────────────────────────────
    # NEW INVESTMENT — Step 1: name + capital
    # ──────────────────────────────────────────────────────────────────
    def show_new_investment_form(self, e=None):
        inv_name_field = ft.TextField(
            label="Investment Name", value="",
            bgcolor=ft.Colors.WHITE, color=ft.Colors.BLACK, height=50,
        )
        capital_field = ft.TextField(
            label="Capital ($)", value="",
            bgcolor=ft.Colors.WHITE, color=ft.Colors.BLACK, height=50,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        def on_next(ev):
            try:
                inv_name = inv_name_field.value.strip().upper() or "INVESTMENT 1"
                capital  = float(capital_field.value or 0)
            except Exception:
                return
            self._show_num_tables_form(inv_name, capital)

        self._set_view(
            ft.Container(
                bgcolor='#1a1a1a', expand=True, padding=20,
                content=ft.ListView(
                    expand=True,
                    controls=[
                        ft.ElevatedButton(
                            "CANCEL", on_click=self.show_main_menu,
                            style=ft.ButtonStyle(bgcolor='#c0392b',
                                                 color=ft.Colors.WHITE),
                        ),
                        ft.Container(height=16),
                        ft.Text("NEW INVESTMENT", color='#3498db', size=20,
                                weight=ft.FontWeight.BOLD),
                        ft.Container(height=12),
                        inv_name_field,
                        ft.Container(height=8),
                        capital_field,
                        ft.Container(height=20),
                        ft.ElevatedButton(
                            "NEXT  →", on_click=on_next,
                            height=60, expand=True,
                            style=ft.ButtonStyle(bgcolor='#2980b9',
                                                 color=ft.Colors.WHITE),
                        ),
                    ],
                ),
            )
        )

    # NEW INVESTMENT — Step 2: number of tables
    # ──────────────────────────────────────────────────────────────────
    def _show_num_tables_form(self, inv_name: str, capital: float):
        num_tables_field = ft.TextField(
            label="Number of Tables", value="1",
            bgcolor=ft.Colors.WHITE, color=ft.Colors.BLACK, height=50,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        def on_next(ev):
            try:
                num_tables = max(1, min(10, int(num_tables_field.value or 1)))
            except Exception:
                return
            self._show_table_setup(inv_name, capital, num_tables)

        self._set_view(
            ft.Container(
                bgcolor='#1a1a1a', expand=True, padding=20,
                content=ft.ListView(
                    expand=True,
                    controls=[
                        ft.ElevatedButton(
                            "←  BACK", on_click=self.show_new_investment_form,
                            style=ft.ButtonStyle(bgcolor='#c0392b',
                                                 color=ft.Colors.WHITE),
                        ),
                        ft.Container(height=16),
                        ft.Text(inv_name, color='#3498db', size=20,
                                weight=ft.FontWeight.BOLD),
                        ft.Text(f"Capital: ${capital:,.2f}", color='#7f8c8d', size=14),
                        ft.Container(height=12),
                        num_tables_field,
                        ft.Container(height=20),
                        ft.ElevatedButton(
                            "NEXT  →", on_click=on_next,
                            height=60, expand=True,
                            style=ft.ButtonStyle(bgcolor='#2980b9',
                                                 color=ft.Colors.WHITE),
                        ),
                    ],
                ),
            )
        )

    # ──────────────────────────────────────────────────────────────────
    # NEW INVESTMENT — Step 2: table names and banks
    # ──────────────────────────────────────────────────────────────────
    def _show_table_setup(self, inv_name: str, capital: float, num_tables: int):
        bank_per_table = round(capital * 0.03, 2)
        name_fields = []
        bank_fields = []
        rows = []
        for i in range(num_tables):
            nf = ft.TextField(
                value=f"TABLE {i + 1}",
                bgcolor=ft.Colors.WHITE, color=ft.Colors.BLACK, height=45,
                expand=2,
            )
            bf = ft.TextField(
                value=str(bank_per_table),
                bgcolor=ft.Colors.WHITE, color=ft.Colors.BLACK, height=45,
                keyboard_type=ft.KeyboardType.NUMBER,
                expand=1,
            )
            name_fields.append(nf)
            bank_fields.append(bf)
            rows.append(ft.Row(controls=[nf, bf], spacing=6))

        def on_create(ev):
            tables_data = []
            for nf, bf in zip(name_fields, bank_fields):
                t_name = nf.value.strip().upper() or f"TABLE {len(tables_data) + 1}"
                try:
                    t_bank = float(bf.value or bank_per_table)
                except Exception:
                    t_bank = bank_per_table
                tables_data.append((t_name, t_bank))
            self._create_investment(inv_name, capital, tables_data)

        controls = [
            ft.ElevatedButton(
                "←  BACK", on_click=self.show_new_investment_form,
                style=ft.ButtonStyle(bgcolor='#c0392b', color=ft.Colors.WHITE),
            ),
            ft.Container(height=12),
            ft.Text(f"{inv_name}  |  Capital: ${capital:.2f}", color='#3498db',
                    size=16, weight=ft.FontWeight.BOLD),
            ft.Container(height=4),
            ft.Row(controls=[
                ft.Text("TABLE NAME", color='#7f8c8d', size=12, expand=2),
                ft.Text("BANK", color='#7f8c8d', size=12, expand=1),
            ]),
            ft.Container(height=4),
        ] + rows + [
            ft.Container(height=20),
            ft.ElevatedButton(
                "CREATE INVESTMENT", on_click=on_create,
                height=60, expand=True,
                style=ft.ButtonStyle(bgcolor='#27ae60', color=ft.Colors.WHITE),
            ),
        ]

        self._set_view(
            ft.Container(
                bgcolor='#1a1a1a', expand=True, padding=20,
                content=ft.ListView(expand=True, controls=controls),
            )
        )

    # ──────────────────────────────────────────────────────────────────
    # SAVE INVESTMENT TO DB
    # ──────────────────────────────────────────────────────────────────
    def _create_investment(self, inv_name: str, capital: float, tables_data: list):
        conn = self._get_conn()
        inv_id = None
        if conn:
            try:
                fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
                cursor = conn.execute(
                    "INSERT INTO investments (name, capital, created_at) VALUES (?, ?, ?)",
                    (inv_name, round(capital, 2), fecha)
                )
                inv_id = cursor.lastrowid
                for mesa_name, init_bank in tables_data:
                    conn.execute(
                        "INSERT INTO investment_tables "
                        "(investment_id, mesa_name, init_bank) VALUES (?, ?, ?)",
                        (inv_id, mesa_name, round(init_bank, 2))
                    )
                conn.commit()
            except Exception:
                pass
            finally:
                conn.close()
        if inv_id:
            self.show_investment_dashboard(inv_id)
        else:
            self.show_main_menu()

    # ──────────────────────────────────────────────────────────────────
    # INVESTMENT DASHBOARD
    # ──────────────────────────────────────────────────────────────────
    def show_investment_dashboard(self, investment_id):
        self._on_game_screen = False
        self.current_investment_id = investment_id
        inv_name    = "Investment"
        inv_capital = 0.0
        table_rows  = []
        conn = self._get_conn()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name, capital FROM investments WHERE id=?",
                    (investment_id,)
                )
                row = cursor.fetchone()
                if row:
                    inv_name, inv_capital = row

                cursor.execute(
                    "SELECT mesa_name, init_bank FROM investment_tables "
                    "WHERE investment_id=? ORDER BY id",
                    (investment_id,)
                )
                inv_tables = cursor.fetchall()

                # Collect all table data first so we can compute per-table other_pl
                all_tdata = []  # (mesa_name, init_bank, wins, losses, last_bank)
                for mesa_name, init_bank in inv_tables:
                    cursor.execute(
                        "SELECT wins, losses, last_bank FROM table_stats "
                        "WHERE investment_id=? AND mesa=?",
                        (investment_id, mesa_name)
                    )
                    stats = cursor.fetchone()
                    if stats and (stats[0] or stats[1]):
                        w = stats[0] or 0
                        l = stats[1] or 0
                        bk = stats[2] or float(init_bank)
                    else:
                        w, l, bk = 0, 0, float(init_bank)
                    all_tdata.append((mesa_name, float(init_bank), w, l, bk))

                total_wins   = sum(d[2] for d in all_tdata)
                total_losses = sum(d[3] for d in all_tdata)

                for i, (mesa_name, init_bank, wins, losses, last_bank) in enumerate(all_tdata):
                    # P/L from all OTHER tables (used in game screen bar)
                    other_pl = sum((d[4] - d[1]) for j, d in enumerate(all_tdata) if j != i)

                    total = wins + losses
                    eff   = (wins / total * 100) if total > 0 else 0.0
                    color = '#2ecc71' if (total == 0 or eff >= 50) else '#ff4444'
                    if total == 0:
                        txt = f"{mesa_name}  |  ${last_bank:.2f}  |  New"
                    else:
                        txt = (f"{mesa_name}  |  ${last_bank:.2f}"
                               f"  |  W:{wins} L:{losses}  |  {eff:.0f}%")

                    def make_loader(m, bk, has_hist, opl):
                        def loader(ev):
                            self.reset_variables()
                            self.current_investment_id = investment_id
                            self.inv_name      = inv_name
                            self.inv_capital   = float(inv_capital)
                            self.inv_other_pl  = opl
                            self.nombre_mesa   = str(m)
                            self.banca_inicial = float(bk)
                            self.banca_actual  = float(bk)
                            self.render_setup_form(has_hist)
                        return loader

                    table_rows.append(
                        ft.ElevatedButton(
                            txt,
                            on_click=make_loader(mesa_name, last_bank, total > 0, other_pl),
                            width=340, height=60,
                            style=ft.ButtonStyle(bgcolor='#222222', color=color),
                        )
                    )

                total_pl   = sum(d[4] - d[1] for d in all_tdata)
                total_bank = sum(d[4] for d in all_tdata)
                if table_rows:
                    # Efficiency = avg per-table W/L ratio across tables that have played
                    played = [(d[2], d[3]) for d in all_tdata if d[2] + d[3] > 0]
                    te     = (sum(w / (w + l) * 100 for w, l in played) / len(played)) if played else 0.0
                    tc     = '#2ecc71' if total_pl >= 0 else '#ff4444'
                    pl_sign  = "+" if total_pl >= 0 else ""
                    pl_pct   = (total_pl / float(inv_capital) * 100) if inv_capital else 0.0
                    eff_txt  = f"EFF: {te:.0f}%  W:{total_wins} L:{total_losses}\n" if played else ""
                    table_rows.insert(0, ft.Container(
                        bgcolor='#1e2d1e' if total_pl >= 0 else '#2d1e1e',
                        padding=10, margin=ft.margin.only(bottom=4),
                        content=ft.Text(
                            f"{eff_txt}${total_bank:.2f}  |  P/L: {pl_sign}${total_pl:.2f} ({pl_sign}{pl_pct:.1f}%)",
                            color=tc, size=13, weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER,
                        ),
                    ))

                # ── Compound interest section ──────────────────────────
                num_sessions = total_wins + total_losses
                per_session_rate = (
                    (total_pl / float(inv_capital) / num_sessions)
                    if (num_sessions > 0 and float(inv_capital) > 0) else 0.0
                )
                table_rows.append(ft.Container(height=16))
                table_rows.append(
                    self._build_compound_widget(7, float(inv_capital), per_session_rate, te)
                )
                table_rows.append(ft.Container(height=6))

                def _open_custom(ev, r=per_session_rate, c=float(inv_capital),
                                 n=inv_name, iid=investment_id, e=te):
                    self.show_compound_custom_view(iid, n, c, r, e)

                table_rows.append(
                    ft.ElevatedButton(
                        "CUSTOM PERIOD",
                        on_click=_open_custom,
                        height=45, expand=True,
                        style=ft.ButtonStyle(bgcolor='#2980b9', color=ft.Colors.WHITE),
                    )
                )
            except Exception as ex:
                table_rows.append(ft.Text(f"Error: {ex}", color='#ff4444'))
            finally:
                conn.close()

        if not table_rows:
            table_rows.append(ft.Text("No tables found.", color='#7f8c8d'))

        self._set_view(
            ft.Container(
                bgcolor='#1a1a1a', expand=True,
                content=ft.Column(
                    expand=True,
                    controls=[
                        ft.Container(
                            bgcolor='#2c3e50',
                            padding=ft.padding.only(left=8, right=8, top=36, bottom=8),
                            content=ft.Row(
                                controls=[
                                    ft.ElevatedButton(
                                        "MENU",
                                        on_click=self.show_main_menu,
                                        style=ft.ButtonStyle(bgcolor='#34495e',
                                                             color=ft.Colors.WHITE),
                                    ),
                                    ft.Text(
                                        f"{inv_name}  |  ${inv_capital:.2f}",
                                        color=ft.Colors.WHITE, size=13,
                                        weight=ft.FontWeight.BOLD, expand=True,
                                        text_align=ft.TextAlign.RIGHT,
                                    ),
                                ],
                            ),
                        ),
                        ft.ListView(controls=table_rows, expand=True,
                                    spacing=4, padding=10),
                    ],
                ),
            )
        )

    # ──────────────────────────────────────────────────────────────────
    # COMPOUND INTEREST WIDGET
    # ──────────────────────────────────────────────────────────────────
    def _build_compound_widget(self, periods: int, start_capital: float,
                               rate: float, efficiency: float = 0.0):
        # efficiency: 0–100 (e.g. 70 → 70 % win rate)
        eff      = max(0.0, min(100.0, efficiency)) / 100.0
        denom    = 2 * eff - 1
        # Derive symmetric win/loss rate so that the weighted average == rate
        r        = (rate / denom) if abs(denom) > 0.01 else abs(rate)
        r        = abs(r)

        # Random W/L sequence matching the efficiency ratio
        wins_n   = round(periods * eff)
        losses_n = periods - wins_n
        wl_seq   = ['W'] * wins_n + ['L'] * losses_n
        random.shuffle(wl_seq)

        rate_txt = f"{rate * 100:+.2f}% / session  ·  EFF {efficiency:.0f}%"

        def _cell(text, color, expand, bold=False, size=13):
            return ft.Container(
                expand=expand,
                content=ft.Text(
                    text, color=color, size=size,
                    text_align=ft.TextAlign.CENTER,
                    weight=ft.FontWeight.BOLD if bold else ft.FontWeight.NORMAL,
                ),
            )

        def _red_cell(text, expand):
            return ft.Container(
                expand=expand,
                bgcolor='#3d0000', border_radius=4,
                padding=ft.padding.symmetric(vertical=1),
                content=ft.Text(
                    text, color='#ff4444', size=13,
                    text_align=ft.TextAlign.CENTER,
                    weight=ft.FontWeight.BOLD,
                ),
            )

        def _badge(label, win):
            return ft.Container(
                expand=1,
                bgcolor='#1a3d1a' if win else '#3d0000',
                border_radius=4,
                padding=ft.padding.symmetric(vertical=1),
                content=ft.Text(
                    label,
                    color='#2ecc71' if win else '#ff4444',
                    size=12, weight=ft.FontWeight.BOLD,
                    text_align=ft.TextAlign.CENTER,
                ),
            )

        header = ft.Row([
            _cell("DAY",  '#7f8c8d', 1, bold=True),
            _cell("RES",  '#7f8c8d', 1, bold=True),
            _cell("CAPITAL", '#7f8c8d', 2, bold=True),
            _cell("GAIN",    '#7f8c8d', 2, bold=True),
            _cell("TOT%",    '#7f8c8d', 1, bold=True),
        ], spacing=3)

        # Day 0 — starting capital
        data_rows = [ft.Row([
            _cell("0",                     '#7f8c8d', 1),
            _cell("—",                     '#7f8c8d', 1),
            _cell(f"${start_capital:.2f}", ft.Colors.WHITE, 2),
            _cell("—",                     '#7f8c8d', 2),
            _cell("0.0%",                  '#7f8c8d', 1),
        ], spacing=3)]

        cap = start_capital
        for i, result in enumerate(wl_seq, start=1):
            win     = (result == 'W')
            new_cap = cap * (1 + r) if win else cap * (1 - r)
            gain    = new_cap - cap
            total_gain = new_cap - start_capital
            total_pct  = (total_gain / start_capital * 100) if start_capital > 0 else 0.0
            cap     = new_cap

            gain_txt = f"{'+' if gain >= 0 else ''}{gain:.2f}"
            pct_txt  = f"{'+' if total_pct >= 0 else ''}{total_pct:.1f}%"

            gain_cell = _cell(gain_txt, '#2ecc71', 2) if win else _red_cell(gain_txt, 2)
            pct_cell  = _cell(pct_txt,  '#2ecc71', 1) if win else _red_cell(pct_txt,  1)

            data_rows.append(ft.Row([
                _cell(str(i),            ft.Colors.WHITE, 1),
                _badge(result, win),
                _cell(f"${new_cap:.2f}", ft.Colors.WHITE, 2),
                gain_cell,
                pct_cell,
            ], spacing=3))

        return ft.Container(
            bgcolor='#1a2535', padding=10, border_radius=8,
            content=ft.Column(
                [
                    ft.Text(
                        "COMPOUND GROWTH",
                        color='#3498db', size=14, weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Text(
                        rate_txt,
                        color='#5dade2', size=12,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Container(height=4),
                    header,
                    ft.Divider(color='#333333', height=1),
                ] + data_rows,
                spacing=4, tight=True,
            ),
        )

    # ──────────────────────────────────────────────────────────────────
    # COMPOUND INTEREST — CUSTOM PERIOD VIEW
    # ──────────────────────────────────────────────────────────────────
    def show_compound_custom_view(self, investment_id, inv_name: str,
                                  inv_capital: float, rate: float, efficiency: float = 0.0):
        periods_field = ft.TextField(
            value="30",
            bgcolor=ft.Colors.WHITE, color=ft.Colors.BLACK, height=45,
            keyboard_type=ft.KeyboardType.NUMBER,
            expand=True,
        )
        result_col = ft.Column([], tight=True)

        def generate(ev=None):
            try:
                p = max(1, min(730, int(periods_field.value or 30)))
            except Exception:
                p = 30
            result_col.controls = [self._build_compound_widget(p, inv_capital, rate, efficiency)]
            result_col.update()

        def go_back(ev):
            self.show_investment_dashboard(investment_id)

        self._set_view(
            ft.Container(
                bgcolor='#1a1a1a', expand=True, padding=20,
                content=ft.ListView(
                    expand=True,
                    controls=[
                        ft.ElevatedButton(
                            "←  BACK", on_click=go_back,
                            style=ft.ButtonStyle(bgcolor='#c0392b',
                                                 color=ft.Colors.WHITE),
                        ),
                        ft.Container(height=12),
                        ft.Text(
                            f"{inv_name}  —  CUSTOM COMPOUND PERIOD",
                            color='#3498db', size=14, weight=ft.FontWeight.BOLD,
                        ),
                        ft.Text(
                            f"Base: ${inv_capital:.2f}  |  Rate: {rate * 100:+.2f}% / session",
                            color='#7f8c8d', size=12,
                        ),
                        ft.Container(height=10),
                        ft.Row([
                            ft.Text("PERIODS:", color=ft.Colors.WHITE),
                            periods_field,
                            ft.ElevatedButton(
                                "GENERATE", on_click=generate,
                                style=ft.ButtonStyle(bgcolor='#27ae60',
                                                     color=ft.Colors.WHITE),
                            ),
                        ], spacing=8),
                        ft.Container(height=10),
                        result_col,
                    ],
                ),
            )
        )
        generate()   # auto-generate on open

    # ──────────────────────────────────────────────────────────────────
    # LOAD INVESTMENT
    # ──────────────────────────────────────────────────────────────────
    def show_load_investments(self, e=None):
        rows = []
        conn = self._get_conn()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, name, capital FROM investments ORDER BY id DESC"
                )
                for inv_id, name, capital in cursor.fetchall():
                    cursor2 = conn.cursor()
                    cursor2.execute(
                        "SELECT mesa_name FROM investment_tables WHERE investment_id=?",
                        (inv_id,)
                    )
                    mesa_names = [r[0] for r in cursor2.fetchall()]
                    wins = losses = 0
                    for mn in mesa_names:
                        cursor2.execute(
                            "SELECT wins, losses FROM table_stats "
                            "WHERE investment_id=? AND mesa=?", (inv_id, mn)
                        )
                        s = cursor2.fetchone()
                        if s:
                            wins   += s[0] or 0
                            losses += s[1] or 0
                    total    = wins + losses
                    eff      = (wins / total * 100) if total > 0 else 0.0
                    color    = '#2ecc71' if (total == 0 or eff >= 50) else '#ff4444'
                    n_tables = len(mesa_names)
                    if total > 0:
                        txt = (f"{name}  |  ${capital:.2f}"
                               f"  |  {n_tables} tables  |  EFF:{eff:.0f}%")
                    else:
                        txt = f"{name}  |  ${capital:.2f}  |  {n_tables} tables"

                    def make_loader(iid):
                        def loader(ev):
                            self.show_investment_dashboard(iid)
                        return loader

                    def make_editor(iid):
                        def editor(ev):
                            self.show_edit_investment(iid)
                        return editor

                    rows.append(
                        ft.Row(
                            controls=[
                                ft.ElevatedButton(
                                    txt, on_click=make_loader(inv_id),
                                    expand=True, height=60,
                                    style=ft.ButtonStyle(bgcolor='#222222', color=color),
                                ),
                                ft.ElevatedButton(
                                    "EDIT", on_click=make_editor(inv_id),
                                    width=60, height=60,
                                    style=ft.ButtonStyle(bgcolor='#34495e',
                                                         color=ft.Colors.WHITE),
                                ),
                            ],
                            spacing=4,
                        )
                    )
            except Exception as ex:
                rows.append(ft.Text(f"Error: {ex}", color='#ff4444'))
            finally:
                conn.close()

        if not rows:
            rows.append(ft.Text("No investments saved.", color='#7f8c8d'))

        self._set_view(
            ft.Container(
                bgcolor='#1a1a1a', expand=True,
                content=ft.Column(
                    expand=True,
                    controls=[
                        ft.Container(
                            bgcolor='#2c3e50',
                            padding=ft.padding.only(left=8, right=8, top=36, bottom=8),
                            content=ft.ElevatedButton(
                                "BACK", on_click=self.show_main_menu,
                                style=ft.ButtonStyle(bgcolor='#34495e',
                                                     color=ft.Colors.WHITE),
                            ),
                        ),
                        ft.ListView(controls=rows, expand=True, spacing=4, padding=10),
                    ],
                ),
            )
        )

    # ──────────────────────────────────────────────────────────────────
    # EDIT / DELETE INVESTMENT
    # ──────────────────────────────────────────────────────────────────
    def show_edit_investment(self, inv_id):
        inv_name    = ""
        inv_capital = 0.0
        tables_data = []  # list of (table_id, mesa_name, init_bank)
        conn = self._get_conn()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name, capital FROM investments WHERE id=?", (inv_id,)
                )
                row = cursor.fetchone()
                if row:
                    inv_name, inv_capital = row
                cursor.execute(
                    "SELECT id, mesa_name, init_bank FROM investment_tables "
                    "WHERE investment_id=? ORDER BY id",
                    (inv_id,)
                )
                tables_data = cursor.fetchall()
            except Exception:
                pass
            finally:
                conn.close()

        name_field = ft.TextField(
            label="Investment Name", value=inv_name,
            bgcolor=ft.Colors.WHITE, color=ft.Colors.BLACK, height=50,
        )
        capital_field = ft.TextField(
            label="Capital ($)", value=str(inv_capital),
            bgcolor=ft.Colors.WHITE, color=ft.Colors.BLACK, height=50,
            keyboard_type=ft.KeyboardType.NUMBER,
        )

        # Table edit rows: (table_id, name_field, bank_field)
        table_rows_ui = []
        table_fields  = []
        for tid, mname, mbank in tables_data:
            nf = ft.TextField(
                value=mname,
                bgcolor=ft.Colors.WHITE, color=ft.Colors.BLACK, height=45,
                expand=2,
            )
            bf = ft.TextField(
                value=str(mbank),
                bgcolor=ft.Colors.WHITE, color=ft.Colors.BLACK, height=45,
                keyboard_type=ft.KeyboardType.NUMBER, expand=1,
            )
            table_fields.append((tid, nf, bf))
            table_rows_ui.append(ft.Row(controls=[nf, bf], spacing=6))

        def on_save(ev):
            conn2 = self._get_conn()
            if not conn2:
                return
            try:
                new_name    = name_field.value.strip().upper() or inv_name
                new_capital = float(capital_field.value or inv_capital)
                conn2.execute(
                    "UPDATE investments SET name=?, capital=? WHERE id=?",
                    (new_name, round(new_capital, 2), inv_id)
                )
                for tid, nf, bf in table_fields:
                    t_name = nf.value.strip().upper()
                    try:
                        t_bank = float(bf.value)
                    except Exception:
                        t_bank = 0.0
                    conn2.execute(
                        "UPDATE investment_tables SET mesa_name=?, init_bank=? WHERE id=?",
                        (t_name, round(t_bank, 2), tid)
                    )
                conn2.commit()
            except Exception:
                pass
            finally:
                conn2.close()
            self.show_load_investments()

        def on_delete(ev):
            dlg = ft.AlertDialog(modal=True, bgcolor='#1e1e1e')

            def confirm_delete(ev2):
                self._close_dlg(dlg)
                self.page.update()
                conn3 = self._get_conn()
                if conn3:
                    try:
                        conn3.execute(
                            "DELETE FROM investment_tables WHERE investment_id=?", (inv_id,)
                        )
                        conn3.execute(
                            "DELETE FROM investments WHERE id=?", (inv_id,)
                        )
                        conn3.commit()
                    except Exception:
                        pass
                    finally:
                        conn3.close()
                self.show_load_investments()

            def cancel_delete(ev2):
                self._close_dlg(dlg)
                self.page.update()

            dlg.title = ft.Text("DELETE INVESTMENT", color='#ff4444',
                                size=16, weight=ft.FontWeight.BOLD,
                                text_align=ft.TextAlign.CENTER)
            dlg.content = ft.Text(
                f"Delete '{inv_name}'?\nThis cannot be undone.",
                color=ft.Colors.WHITE, size=14,
                text_align=ft.TextAlign.CENTER,
            )
            dlg.actions = [
                ft.ElevatedButton(
                    "CANCEL", on_click=cancel_delete, expand=1,
                    style=ft.ButtonStyle(bgcolor='#555555', color=ft.Colors.WHITE),
                ),
                ft.ElevatedButton(
                    "DELETE", on_click=confirm_delete, expand=1,
                    style=ft.ButtonStyle(bgcolor='#ff4444', color=ft.Colors.WHITE),
                ),
            ]
            dlg.actions_alignment = ft.MainAxisAlignment.CENTER
            self.page.overlay.append(dlg)
            dlg.open = True
            self.page.update()

        table_section = []
        if table_rows_ui:
            table_section = [
                ft.Container(height=12),
                ft.Text("TABLES", color='#7f8c8d', size=12, weight=ft.FontWeight.BOLD),
                ft.Row(controls=[
                    ft.Text("TABLE NAME", color='#7f8c8d', size=11, expand=2),
                    ft.Text("BANK", color='#7f8c8d', size=11, expand=1),
                ]),
            ] + table_rows_ui

        controls = [
            ft.ElevatedButton(
                "BACK", on_click=self.show_load_investments,
                style=ft.ButtonStyle(bgcolor='#34495e', color=ft.Colors.WHITE),
            ),
            ft.Container(height=12),
            ft.Text("EDIT INVESTMENT", color='#3498db', size=18,
                    weight=ft.FontWeight.BOLD),
            ft.Container(height=10),
            name_field,
            ft.Container(height=8),
            capital_field,
        ] + table_section + [
            ft.Container(height=20),
            ft.ElevatedButton(
                "SAVE CHANGES", on_click=on_save,
                height=60, expand=True,
                style=ft.ButtonStyle(bgcolor='#27ae60', color=ft.Colors.WHITE),
            ),
            ft.Container(height=10),
            ft.ElevatedButton(
                "DELETE INVESTMENT", on_click=on_delete,
                height=50, expand=True,
                style=ft.ButtonStyle(bgcolor='#c0392b', color=ft.Colors.WHITE),
            ),
        ]

        self._set_view(
            ft.Container(
                bgcolor='#1a1a1a', expand=True, padding=20,
                content=ft.ListView(expand=True, controls=controls),
            )
        )

    # ──────────────────────────────────────────────────────────────────
    # SESSION SETUP FORM
    # ──────────────────────────────────────────────────────────────────
    def render_setup_form(self, is_continue: bool):
        self.table_input = ft.TextField(
            value=str(self.nombre_mesa),
            bgcolor=ft.Colors.WHITE, color=ft.Colors.BLACK, height=45,
            read_only=True,
        )
        sug_bank     = self.banca_actual
        sug_max_loss = 33.0    # default: 3 losses = 33% bank
        sug_fin      = round(sug_bank * (sug_max_loss / 100) / 225, 6)
        sug_fout     = round(sug_bank * (sug_max_loss / 100) / 26,  4)

        def _f(val):
            try:
                return float(val)
            except Exception:
                return 0.0

        def _chips_from(bk, loss_pct):
            """Return (fin, fout) given bank and max-loss %."""
            factor = bk * max(loss_pct, 0) / 100
            return round(factor / 225, 6), round(factor / 26, 4)

        def _chip_label_text(chip_val, bank, multiplier_sum, max_loss_pct):
            """chip_val × multiplier_sum = total 3-loss cost; % relative to bank"""
            try:
                pct      = (chip_val / bank * 100) if bank > 0 else 0
                loss     = chip_val * multiplier_sum
                loss_pct = (loss / bank * 100) if bank > 0 else 0
                return (f"({pct:.4f}% bank · 3 losses = ${loss:.2f}"
                        f" = {loss_pct:.1f}% / {max_loss_pct:.0f}% bank)")
            except Exception:
                return ""

        self.fin_label  = ft.Text(
            f"CHIP IN {_chip_label_text(sug_fin,  sug_bank, 225, sug_max_loss)}:",
            color=ft.Colors.WHITE,
        )
        self.fout_label = ft.Text(
            f"CHIP OUT {_chip_label_text(sug_fout, sug_bank, 26,  sug_max_loss)}:",
            color=ft.Colors.WHITE,
        )

        def _refresh_labels(bank, fin_val, fout_val):
            ml = _f(self.max_loss_input.value)
            self.fin_label.value  = f"CHIP IN {_chip_label_text(fin_val,  bank, 225, ml)}:"
            self.fout_label.value = f"CHIP OUT {_chip_label_text(fout_val, bank, 26,  ml)}:"
            try:
                self.fin_label.update()
                self.fout_label.update()
            except Exception:
                pass

        def _recalc(e=None):
            try:
                bk  = _f(self.banca_input.value)
                ml  = _f(self.max_loss_input.value)
                fin_val, fout_val = _chips_from(bk, ml)
                self.fin_input.value  = str(fin_val)
                self.fout_input.value = str(fout_val)
                self.fin_input.update()
                self.fout_input.update()
                _refresh_labels(bk, fin_val, fout_val)
            except Exception:
                pass

        def _on_bank_change(e):
            _recalc()

        self.max_loss_input = ft.TextField(
            value=str(sug_max_loss),
            bgcolor=ft.Colors.WHITE, color=ft.Colors.BLACK, height=45,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=lambda e: _recalc(),
        )

        self.fin_input = ft.TextField(
            value=str(sug_fin),
            bgcolor=ft.Colors.WHITE, color=ft.Colors.BLACK, height=45,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=lambda _e: _refresh_labels(
                _f(self.banca_input.value),
                _f(self.fin_input.value),
                _f(self.fout_input.value),
            ),
        )
        self.fout_input = ft.TextField(
            value=str(sug_fout),
            bgcolor=ft.Colors.WHITE, color=ft.Colors.BLACK, height=45,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=lambda _e: _refresh_labels(
                _f(self.banca_input.value),
                _f(self.fin_input.value),
                _f(self.fout_input.value),
            ),
        )
        self.banca_input = ft.TextField(
            value=str(sug_bank),
            bgcolor=ft.Colors.WHITE, color=ft.Colors.BLACK, height=45,
            keyboard_type=ft.KeyboardType.NUMBER,
            on_change=_on_bank_change,
        )
        self.free_spin_mode = False
        _fs_lbl = ft.Text("FREE SPIN: OFF", color=ft.Colors.WHITE,
                          weight=ft.FontWeight.BOLD)
        _fs_ref = [None]   # forward ref so toggle can update the button

        def _toggle_free_spin(e):
            self.free_spin_mode = not self.free_spin_mode
            on = self.free_spin_mode
            _fs_lbl.value       = "FREE SPIN: ON" if on else "FREE SPIN: OFF"
            _fs_ref[0].style    = ft.ButtonStyle(
                bgcolor='#e67e22' if on else '#555555',
                color=ft.Colors.WHITE,
            )
            _fs_lbl.update()
            _fs_ref[0].update()

        free_spin_btn = ft.ElevatedButton(
            content=_fs_lbl,
            height=50, expand=True,
            style=ft.ButtonStyle(bgcolor='#555555', color=ft.Colors.WHITE),
            on_click=_toggle_free_spin,
        )
        _fs_ref[0] = free_spin_btn

        self.live_table_mode = False
        _lt_lbl = ft.Text("LIVE TABLE: OFF", color=ft.Colors.WHITE,
                          weight=ft.FontWeight.BOLD)
        _lt_ref = [None]

        def _toggle_live_table(e):
            self.live_table_mode = not self.live_table_mode
            on = self.live_table_mode
            _lt_lbl.value    = "LIVE TABLE: ON" if on else "LIVE TABLE: OFF"
            _lt_ref[0].style = ft.ButtonStyle(
                bgcolor='#3498db' if on else '#555555',
                color=ft.Colors.WHITE,
            )
            if on and hasattr(self, 'cb_basic'):
                self.cb_basic.value = True
                self.cb_basic.update()
            _lt_lbl.update()
            _lt_ref[0].update()

        live_table_btn = ft.ElevatedButton(
            content=_lt_lbl,
            height=50, expand=True,
            style=ft.ButtonStyle(bgcolor='#555555', color=ft.Colors.WHITE),
            on_click=_toggle_live_table,
        )
        _lt_ref[0] = live_table_btn

        vc = self.visible_cats
        self.cb_basic  = ft.Checkbox(label="Basic  (R N P I B A)", value=vc['basic'],
                                     fill_color='#555555', check_color=ft.Colors.WHITE,
                                     label_style=ft.TextStyle(color=ft.Colors.WHITE, size=13))
        self.cb_cols   = ft.Checkbox(label="Columns  (34 35 36)",  value=vc['cols'],
                                     fill_color=C_COL, check_color=ft.Colors.WHITE,
                                     label_style=ft.TextStyle(color=ft.Colors.WHITE, size=13))
        self.cb_docs   = ft.Checkbox(label="Dozens  (1a 2a 3a)",   value=vc['docs'],
                                     fill_color=C_DOC, check_color=ft.Colors.WHITE,
                                     label_style=ft.TextStyle(color=ft.Colors.WHITE, size=13))
        self.cb_secs   = ft.Checkbox(label="Sectors  (Z0 ZG ZP H)", value=vc['secs'],
                                     fill_color=C_SEC, check_color=ft.Colors.WHITE,
                                     label_style=ft.TextStyle(color=ft.Colors.WHITE, size=13))
        self.cb_thirds = ft.Checkbox(label="Thirds  (T1 T2 T3)",   value=vc['thirds'],
                                     fill_color=C_SET, check_color=ft.Colors.WHITE,
                                     label_style=ft.TextStyle(color=ft.Colors.WHITE, size=13))
        self.cb_wave   = ft.Checkbox(label="Wave  (W1 Lip · W2 Curls · W3 Through)",
                                     value=vc['wave'],
                                     fill_color=C_WAV, check_color=ft.Colors.WHITE,
                                     label_style=ft.TextStyle(color=ft.Colors.WHITE, size=13))

        btn_txt = "RESUME TABLE" if is_continue else "OPEN TABLE"
        self._set_view(
            ft.Container(
                bgcolor='#1a1a1a', expand=True, padding=20,
                content=ft.ListView(
                    expand=True,
                    controls=[
                        ft.ElevatedButton(
                            "CANCEL", on_click=self._go_home,
                            style=ft.ButtonStyle(bgcolor='#c0392b',
                                                 color=ft.Colors.WHITE),
                        ),
                        ft.Container(height=10),
                        ft.Text("TABLE:", color=ft.Colors.WHITE),
                        self.table_input,
                        ft.Text("BANK:", color=ft.Colors.WHITE),
                        self.banca_input,
                        ft.Text("MAX LOSS %:", color=ft.Colors.WHITE),
                        self.max_loss_input,
                        self.fin_label,
                        self.fin_input,
                        self.fout_label,
                        self.fout_input,
                        ft.Container(height=10),
                        free_spin_btn,
                        ft.Container(height=6),
                        live_table_btn,
                        ft.Container(height=10),
                        ft.Text("TABLE COLUMNS:", color='#7f8c8d', size=12,
                                weight=ft.FontWeight.BOLD),
                        self.cb_basic,
                        self.cb_cols,
                        self.cb_docs,
                        self.cb_secs,
                        self.cb_thirds,
                        self.cb_wave,
                        ft.Container(height=6),
                        ft.ElevatedButton(
                            btn_txt, on_click=self.iniciar_ciclo,
                            height=70, expand=True,
                            style=ft.ButtonStyle(bgcolor='#27ae60',
                                                 color=ft.Colors.WHITE),
                        ),
                    ],
                ),
            )
        )

    # ──────────────────────────────────────────────────────────────────
    # START SESSION
    # ──────────────────────────────────────────────────────────────────
    def iniciar_ciclo(self, e=None):
        try:
            self.nombre_mesa   = str(self.table_input.value).upper() or "TABLE 1"
            self.banca_inicial = float(self.banca_input.value or 100)
            self.banca_actual  = self.banca_inicial
            self.val_fin       = float(self.fin_input.value)  if self.fin_input.value  else round(self.banca_inicial / 225, 6)
            self.val_fout      = float(self.fout_input.value) if self.fout_input.value else round(self.banca_inicial / 26, 4)
        except Exception:
            pass
        # Read column visibility checkboxes
        try:
            self.visible_cats = {
                'basic':  bool(self.cb_basic.value),
                'cols':   bool(self.cb_cols.value),
                'docs':   bool(self.cb_docs.value),
                'secs':   bool(self.cb_secs.value),
                'thirds': bool(self.cb_thirds.value),
                'wave':   bool(self.cb_wave.value),
            }
        except Exception:
            pass
        self.show_game_screen()

    # ─────────────────────────────────────────────────────────────────
    # STOP LOSS — triggers at 45% loss of initial bank
    # ─────────────────────────────────────────────────────────────────
    def _check_stop_loss(self):
        if self.stop_loss_triggered:
            return
        if self.banca_inicial <= 0:
            return
        loss_pct = (self.banca_inicial - self.banca_actual) / self.banca_inicial
        if loss_pct < 0.45:
            return

        self.stop_loss_triggered = True
        self.activa = False

        profit = round(self.banca_actual - self.banca_inicial, 2)
        pl_pct = (profit / self.banca_inicial * 100) if self.banca_inicial != 0 else 0

        ok, err_msg    = self._guardar_sesion()
        self._update_table_stats(False)
        guardado_txt   = "Saved to history" if ok else f"Error: {err_msg}"
        guardado_color = '#2ecc71' if ok else '#ff4444'

        dlg = ft.AlertDialog(modal=True, bgcolor='#1e1e1e')

        def cerrar(ev):
            self._close_dlg(dlg)
            self.page.update()
            self._go_home()

        dlg.title = ft.Text(
            "STOP LOSS",
            color='#ff4444', size=18, weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )
        dlg.content = ft.Column(
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Divider(color='#444444'),
                ft.Text("45% loss limit reached.", color='#ff4444',
                        size=13, text_align=ft.TextAlign.CENTER),
                ft.Container(height=6),
                ft.Text(f"Initial bank:  ${self.banca_inicial:.2f}",
                        color=ft.Colors.WHITE, size=14),
                ft.Text(f"Final bank:    ${self.banca_actual:.2f}",
                        color=ft.Colors.WHITE, size=14),
                ft.Container(height=8),
                ft.Text(
                    f"P/L:  ${profit:.2f}   ({pl_pct:.1f}%)",
                    color='#ff4444', size=20, weight=ft.FontWeight.BOLD,
                ),
                ft.Container(height=10),
                ft.Text(guardado_txt, color=guardado_color, size=13),
            ],
        )
        dlg.actions = [
            ft.ElevatedButton(
                content=ft.Text("CLOSE TABLE", size=15, weight=ft.FontWeight.BOLD),
                on_click=cerrar,
                expand=True,
                style=ft.ButtonStyle(bgcolor='#ff4444', color=ft.Colors.WHITE),
            )
        ]
        dlg.actions_alignment = ft.MainAxisAlignment.CENTER

        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    # ─────────────────────────────────────────────────────────────────
    # FINALIZE SESSION
    # ─────────────────────────────────────────────────────────────────
    def finalizar_sesion(self, e=None):
        profit   = round(self.banca_actual - self.banca_inicial, 2)
        pl_pct   = (profit / self.banca_inicial * 100) if self.banca_inicial != 0 else 0
        positivo = profit >= 0
        color    = '#2ecc71' if positivo else '#ff4444'
        signo    = "+" if positivo else ""

        ok, err_msg    = self._guardar_sesion()
        self._update_table_stats(profit >= 0)
        guardado_txt   = "Saved to history" if ok else f"Error: {err_msg}"
        guardado_color = '#2ecc71' if ok else '#ff4444'

        dlg = ft.AlertDialog(modal=True, bgcolor='#1e1e1e')

        def cerrar(ev):
            self._close_dlg(dlg)
            self.page.update()
            self._go_home()

        dlg.title = ft.Text(
            f"SUMMARY  {self.nombre_mesa}",
            color='#3498db', size=16, weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )
        dlg.content = ft.Column(
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Divider(color='#444444'),
                ft.Text(f"Initial bank:  ${self.banca_inicial:.2f}",
                        color=ft.Colors.WHITE, size=14),
                ft.Text(f"Final bank:    ${self.banca_actual:.2f}",
                        color=ft.Colors.WHITE, size=14),
                ft.Container(height=8),
                ft.Text(
                    f"P/L:  {signo}${profit:.2f}   ({signo}{pl_pct:.1f}%)",
                    color=color, size=20, weight=ft.FontWeight.BOLD,
                ),
                ft.Container(height=10),
                ft.Text(guardado_txt, color=guardado_color, size=13),
            ],
        )
        dlg.actions = [
            ft.ElevatedButton(
                content=ft.Text("OK", size=15, weight=ft.FontWeight.BOLD),
                on_click=cerrar,
                expand=True,
                style=ft.ButtonStyle(bgcolor=color, color=ft.Colors.WHITE),
            )
        ]
        dlg.actions_alignment = ft.MainAxisAlignment.CENTER

        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    # ──────────────────────────────────────────────────────────────────
    # GAME SCREEN
    # ──────────────────────────────────────────────────────────────────
    def show_game_screen(self):
        self._on_game_screen = True

        # ── Investment bar (shown only when inside an investment) ───
        inv_bar_controls = []
        if self.current_investment_id and self.inv_name:
            init_pl = self.inv_other_pl + (self.banca_actual - self.banca_inicial)
            self.lbl_inv_pl = ft.Text(
                f"P/L: {init_pl:+.2f}",
                color='#2ecc71' if init_pl >= 0 else '#ff4444',
                weight=ft.FontWeight.BOLD, size=16,
                text_align=ft.TextAlign.RIGHT,
            )
            inv_bar_controls = [ft.Container(
                bgcolor='#0a0a0a',
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                content=ft.Row(controls=[
                    ft.Text(
                        self.inv_name,
                        color='#3498db', size=14, weight=ft.FontWeight.BOLD,
                        expand=True,
                    ),
                    self.lbl_inv_pl,
                ]),
            )]
        else:
            self.lbl_inv_pl = None

        self.lbl_bank = ft.Text(
            f"{self.nombre_mesa}  |  ${self.banca_actual:.2f}",
            color='#2ecc71', weight=ft.FontWeight.BOLD, size=13, expand=True,
        )
        self.lbl_inv = ft.Text(
            "BET: $0.00",
            color='#f1c40f', weight=ft.FontWeight.BOLD, size=11, expand=True,
            text_align=ft.TextAlign.CENTER,
            no_wrap=True,
        )
        self.lbl_pl = ft.Text(
            "P/L: 0.0%",
            color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, size=13, expand=True,
            text_align=ft.TextAlign.RIGHT,
        )
        stats_bar = ft.Container(
            bgcolor='#1e1e1e', padding=5,
            content=ft.Row(controls=[self.lbl_bank, self.lbl_inv, self.lbl_pl]),
        )

        # ── Progression ON/OFF + fixed multiplier bar ─────────────────────
        self.prog_on     = True
        self.fixed_multi = 1

        _PROG_ON_COLOR  = '#2ecc71'
        _PROG_OFF_COLOR = '#e67e22'
        _MULTI_ACT      = '#f39c12'
        _MULTI_INACT    = '#3a3a3a'

        _prog_lbl  = ft.Text("PROG: ON", color=ft.Colors.WHITE,
                              weight=ft.FontWeight.BOLD, size=11)
        _prog_ref  = [None]
        _multi_refs: dict = {}   # multiplier int → button ref

        def _refresh_prog_ui():
            on = self.prog_on
            m  = self.fixed_multi
            _prog_lbl.value = "PROG: ON" if on else "PROG: OFF"
            _prog_ref[0].style = ft.ButtonStyle(
                bgcolor=_PROG_ON_COLOR if on else _PROG_OFF_COLOR,
                color=ft.Colors.WHITE,
            )
            _prog_ref[0].update()
            _prog_lbl.update()
            for mx, btn in _multi_refs.items():
                btn.visible = not on
                btn.style = ft.ButtonStyle(
                    bgcolor=_MULTI_ACT if mx == m else _MULTI_INACT,
                    color=ft.Colors.WHITE,
                )
                btn.update()
            self.update_inv_label()
            if self.lbl_inv:
                self.lbl_inv.update()

        def _toggle_prog(_e):
            self.prog_on = not self.prog_on
            _refresh_prog_ui()

        def _make_multi_handler(mx):
            def handler(_e):
                self.fixed_multi = mx
                _refresh_prog_ui()
            return handler

        _prog_btn = ft.ElevatedButton(
            content=_prog_lbl, height=30, expand=2,
            style=ft.ButtonStyle(bgcolor=_PROG_ON_COLOR, color=ft.Colors.WHITE),
            on_click=_toggle_prog,
        )
        _prog_ref[0] = _prog_btn

        _multi_btn_list = []
        for _mx in (1, 2, 3, 4, 5):
            _mb = ft.ElevatedButton(
                content=ft.Text(f"{_mx}x", size=10,
                                weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                height=30, expand=1, visible=False,
                style=ft.ButtonStyle(
                    bgcolor=_MULTI_ACT if _mx == 1 else _MULTI_INACT,
                    color=ft.Colors.WHITE,
                ),
                on_click=_make_multi_handler(_mx),
            )
            _multi_refs[_mx] = _mb
            _multi_btn_list.append(_mb)

        prog_bar = ft.Container(
            bgcolor='#161616', padding=ft.padding.symmetric(horizontal=4, vertical=3),
            content=ft.Row(controls=[_prog_btn] + _multi_btn_list, spacing=3),
        )
        # ──────────────────────────────────────────────────────────────────

        self.sug_row = ft.Row(
            controls=[
                ft.ElevatedButton(
                    content=self._txt("---", size=12),
                    expand=True, height=35,
                    style=ft.ButtonStyle(bgcolor='#34495e', color=ft.Colors.WHITE),
                )
                for _ in range(4)
            ],
            spacing=2,
        )
        sug_bar = ft.Container(
            bgcolor='#2c3e50', padding=4, height=50,
            content=self.sug_row,
        )

        # ── Live Table filter panel (only when live_table_mode is ON) ──────
        self.live_filter = None
        rb_bar = None
        if self.live_table_mode:
            _INACTIVE = '#3a3a3a'
            _ACTIVE_COLOR = {
                'R': '#c0392b', 'B': '#222222',
                '1-18': '#555577', 'Even': '#446644',
                'Odd': '#664444', '19-36': '#445566',
            }
            # All buttons stored as (opt, btn) pairs so R/B can appear in both rows
            _all_filter_btns: list = []   # list of (opt, btn)

            def _apply_filter(new_f):
                self.live_filter = new_f
                # Re-map any already-selected live groups to the new filter variant
                updated = []
                for g in self.grupos_activos:
                    base = self._to_display_name(g)
                    if base in ('1a', '2a', '3a'):
                        updated.append(f'{base}{_DOC_SFX.get(new_f, "_L")}')
                    elif base in ('34', '35', '36'):
                        sfx = _COL_SFX.get(new_f, '')
                        updated.append(f'{base}{sfx}' if sfx else base)
                    else:
                        updated.append(g)
                self.grupos_activos = updated
                for opt, btn in _all_filter_btns:
                    btn.style = ft.ButtonStyle(
                        bgcolor=_ACTIVE_COLOR[opt] if opt == new_f else _INACTIVE,
                        color=ft.Colors.WHITE,
                    )
                    btn.update()
                self._refresh_mixer_colors()
                self.update_inv_label()
                if self.lbl_inv:
                    self.lbl_inv.update()
                self.actualizar_sugerencias()

            def _filter_btn(opt, label, height=34, size=11):
                def _click(e, o=opt):
                    _apply_filter(None if self.live_filter == o else o)
                btn = ft.ElevatedButton(
                    content=self._txt(label, size=size),
                    expand=True, height=height,
                    style=ft.ButtonStyle(bgcolor=_INACTIVE, color=ft.Colors.WHITE),
                    on_click=_click,
                )
                _all_filter_btns.append((opt, btn))
                return btn

            row1 = ft.Row(controls=[
                _filter_btn('R', '■  RED',   height=38, size=12),
                _filter_btn('B', '■  BLACK', height=38, size=12),
            ], spacing=4)
            row2 = ft.Row(controls=[
                _filter_btn('1-18',  '1-18',  height=28, size=9),
                _filter_btn('Even',  'Even',  height=28, size=9),
                _filter_btn('R',     'RED',   height=28, size=9),
                _filter_btn('B',     'BLACK', height=28, size=9),
                _filter_btn('Odd',   'Odd',   height=28, size=9),
                _filter_btn('19-36', '19-36', height=28, size=9),
            ], spacing=2, tight=True)
            rb_bar = ft.Container(
                bgcolor='#1a2a3a',
                padding=ft.padding.symmetric(horizontal=6, vertical=4),
                content=ft.Column(controls=[row1, row2], spacing=3),
            )

        self.mixer_btns = {}
        vc = self.visible_cats
        all_cats = [
            ('cols',   ['34', '35', '36'],      C_COL),
            ('docs',   ['1a', '2a', '3a'],      C_DOC),
            ('secs',   ['Z0', 'ZG', 'ZP', 'H'], C_SEC),
            ('thirds', ['T1', 'T2', 'T3'],      C_SET),
            ('wave',   ['W1', 'W2', 'W3'],      C_WAV),
        ]
        cats = [(grps, col) for key, grps, col in all_cats if vc.get(key, True)]
        mixer_rows = []
        for grps, col in cats:
            row_btns = []
            for g in grps:
                btn = ft.ElevatedButton(
                    content=self._txt(g),
                    data={'name': g, 'color': col},
                    on_click=self.seleccionar_mixer,
                    expand=True, height=40,
                    style=ft.ButtonStyle(
                        bgcolor=col, color=ft.Colors.WHITE,
                        animation_duration=400,
                        overlay_color={
                            ft.ControlState.PRESSED: ft.Colors.with_opacity(0.4, ft.Colors.WHITE),
                        },
                    ),
                )
                self.mixer_btns[g] = btn
                row_btns.append(btn)
            mixer_rows.append(ft.Row(controls=row_btns, spacing=2))

        mixer_box = ft.Container(
            padding=ft.padding.symmetric(horizontal=2),
            content=ft.Column(controls=mixer_rows, spacing=2),
        )

        self.btn_inv = ft.ElevatedButton(
            content=self._txt("INVEST"),
            on_click=self.confirmar_manual,
            expand=2, height=45,
            style=ft.ButtonStyle(bgcolor='#2ecc71', color=ft.Colors.WHITE,
                                 animation_duration=400),
        )
        btn_corr = ft.ElevatedButton(
            content=self._txt("UNDO"),
            on_click=self.corregir_ultimo,
            expand=1, height=45,
            style=ft.ButtonStyle(bgcolor='#f39c12', color=ft.Colors.WHITE,
                                 animation_duration=400),
        )
        btn_fin = ft.ElevatedButton(
            content=self._txt("FINISH"),
            on_click=self.finalizar_sesion,
            expand=1, height=45,
            style=ft.ButtonStyle(bgcolor='#ff4444', color=ft.Colors.WHITE,
                                 animation_duration=400),
        )
        ctrl_bar = ft.Container(
            padding=ft.padding.symmetric(horizontal=4, vertical=4),
            content=ft.Row(controls=[self.btn_inv, btn_corr, btn_fin], spacing=4),
        )

        teclado_controls = [
            ft.Row(controls=[
                ft.ElevatedButton(
                    content=self._txt("0"),
                    data=0, on_click=self.process_number,
                    height=45, expand=True,
                    style=ft.ButtonStyle(
                        bgcolor='#27ae60', color=ft.Colors.WHITE,
                        animation_duration=400,
                        overlay_color={
                            ft.ControlState.PRESSED: ft.Colors.with_opacity(0.4, ft.Colors.WHITE),
                        },
                    ),
                )
            ])
        ]
        for i in range(12):
            row_btns = []
            for j in range(1, 4):
                n = (i * 3) + j
                row_btns.append(
                    ft.ElevatedButton(
                        content=self._txt(str(n)),
                        data=n, on_click=self.process_number,
                        expand=True, height=40,
                        style=ft.ButtonStyle(
                            bgcolor='#cc0000' if n in ROJOS else '#222222',
                            color=ft.Colors.WHITE,
                            animation_duration=400,
                            overlay_color={
                                ft.ControlState.PRESSED: ft.Colors.with_opacity(0.5, ft.Colors.WHITE),
                            },
                        ),
                    )
                )
            teclado_controls.append(ft.Row(controls=row_btns, spacing=2))

        teclado = ft.Container(
            bgcolor='#0e3d24', padding=5, height=620,
            content=ft.Column(controls=teclado_controls, spacing=2),
        )

        self.reg_header_row = ft.Row(controls=[], spacing=0)
        self.reg_rows_box   = ft.Column(controls=[], spacing=0)
        self._rebuild_table_header()

        bitacora = ft.Container(
            height=170, bgcolor='#0d0d0d',
            content=ft.Row(
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Column(
                        controls=[self.reg_header_row, self.reg_rows_box],
                        spacing=0, tight=True,
                    )
                ],
            ),
        )

        self._set_view(
            ft.Container(
                bgcolor='#121212', expand=True,
                content=ft.Column(
                    expand=True, spacing=0,
                    controls=inv_bar_controls + [
                        stats_bar, prog_bar, sug_bar,
                    ] + ([rb_bar] if rb_bar else []) + [
                        mixer_box, ctrl_bar,
                        ft.Container(
                            expand=True,
                            content=ft.ListView(expand=True, controls=[teclado]),
                        ),
                        bitacora,
                    ],
                ),
            )
        )

        self.actualizar_sugerencias()

    # ──────────────────────────────────────────────────────────────────
    # LOG TABLE
    # ──────────────────────────────────────────────────────────────────
    def _table_specs(self):
        """Return list of (header, color) pairs based on visible_cats."""
        vc = getattr(self, 'visible_cats', {k: True for k in ['basic','cols','docs','secs','thirds','wave']})
        W  = ft.Colors.WHITE
        specs = [("N", '#f1c40f')]
        if vc.get('basic',  True): specs += [("R",'#ff4d4d'),("N",W),("P",'#3498db'),("I",'#f39c12'),("B",W),("A",W)]
        if vc.get('cols',   True): specs += [("34",C_COL),("35",C_COL),("36",C_COL)]
        if vc.get('docs',   True): specs += [("1a",C_DOC),("2a",C_DOC),("3a",C_DOC)]
        if vc.get('secs',   True): specs += [("Z0",C_SEC),("ZG",C_SEC),("ZP",C_SEC),("H",C_SEC)]
        if vc.get('thirds', True): specs += [("T1",C_SET),("T2",C_SET),("T3",C_SET)]
        if vc.get('wave',   True): specs += [("W1",C_WAV),("W2",C_WAV),("W3",C_WAV)]
        return specs

    def _rebuild_table_header(self):
        cw    = self._col_width()
        specs = self._table_specs()
        self.reg_header_row.controls = [
            ft.Text(h, width=cw, color=c,
                    text_align=ft.TextAlign.CENTER,
                    size=7, weight=ft.FontWeight.BOLD)
            for h, c in specs
        ]

    def update_registration_table(self):
        if self.reg_rows_box is None:
            return
        cw = self._col_width()
        self._rebuild_table_header()
        self.reg_rows_box.controls.clear()
        vc = getattr(self, 'visible_cats', {k: True for k in ['basic','cols','docs','secs','thirds','wave']})
        s  = "■"
        W  = ft.Colors.WHITE
        for n in self.history_nums[-8:]:
            cells = [(str(n), '#f1c40f')]
            if vc.get('basic', True):
                cells += [
                    (s if n in ROJOS else "",                '#ff4d4d'),
                    (s if (n != 0 and n not in ROJOS) else "", W),
                    (s if (n != 0 and n % 2 == 0) else "",  '#3498db'),
                    (s if (n % 2 != 0) else "",              '#f39c12'),
                    (s if (1 <= n <= 18) else "",            W),
                    (s if (19 <= n <= 36) else "",           W),
                ]
            live = getattr(self, 'live_table_mode', False)
            for key, grps, col in [
                ('cols',   ['34','35','36'],       C_COL),
                ('docs',   ['1a','2a','3a'],        C_DOC),
                ('secs',   ['Z0','ZG','ZP','H'],   C_SEC),
                ('thirds', ['T1','T2','T3'],        C_SET),
                ('wave',   ['W1','W2','W3'],        C_WAV),
            ]:
                if vc.get(key, True):
                    if live and key == 'docs':
                        # In live mode show ■ in every dozen whose live set contains n
                        cells += [(s if n in GRUPOS_MAESTROS[f'{g}_L'] else "", col) for g in grps]
                    else:
                        cells += [(s if n in GRUPOS_MAESTROS[g] else "", col) for g in grps]
            self.reg_rows_box.controls.append(
                ft.Row(
                    controls=[
                        ft.Text(txt, width=cw, color=col,
                                text_align=ft.TextAlign.CENTER,
                                size=8, weight=ft.FontWeight.BOLD)
                        for txt, col in cells
                    ],
                    spacing=0,
                )
            )
        self.reg_header_row.update()
        self.reg_rows_box.update()

    # ──────────────────────────────────────────────────────────────────
    # VISUAL FEEDBACK
    # ──────────────────────────────────────────────────────────────────
    def _darken_color(self, hex_color, factor=0.7):
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            r, g, b = (int(hex_color[i:i+2], 16) for i in (0, 2, 4))
            return f'#{int(r*factor):02x}{int(g*factor):02x}{int(b*factor):02x}'
        return hex_color

    def _flash_button(self, btn, original_color, duration_ms=300):
        flash_color = self._darken_color(original_color, 0.6)
        async def _animate():
            btn.style.bgcolor = flash_color
            self.page.update()
            await asyncio.sleep(duration_ms / 1000)
            btn.style.bgcolor = original_color
            self.page.update()
        asyncio.create_task(_animate())

    # ──────────────────────────────────────────────────────────────────
    # GAME LOGIC
    # ──────────────────────────────────────────────────────────────────

    GRUPOS_STRAIGHT = {'Z0', 'ZG', 'ZP', 'H', 'T1', 'T2', 'T3', 'W1', 'W2', 'W3'}
    PROG_2_OUT = [2, 6, 18, 54]          # 2 lines/dozens: 1,3,9,27 per line (4 attempts)
    PROG_2_IN  = [1, 3, 5, 9, 17]        # 2 sectors/zones progression

    def _is_outside(self):
        return all(g not in self.GRUPOS_STRAIGHT and g not in GRUPOS_LIVE_INSIDE
                   for g in self.grupos_activos)

    def _group_cost(self, g):
        if g in self.GRUPOS_STRAIGHT or g in GRUPOS_LIVE_INSIDE:
            return self.val_fin * len(GRUPOS_MAESTROS[g])
        return self.val_fout

    def _current_multi(self, is_out: bool) -> int:
        """Return the active multiplier for outside or inside bets."""
        if not self.prog_on:
            return self.fixed_multi
        n = len(self.grupos_activos)
        if is_out:
            if n == 1:
                return PROG_FIBO[self.idx_fibo_out]
            return self.PROG_2_OUT[min(self.nivel_martingala_out, len(self.PROG_2_OUT) - 1)]
        if n == 1:
            return PROG_FIBO[self.idx_fibo_in]
        return self.PROG_2_IN[min(self.nivel_martingala_in, len(self.PROG_2_IN) - 1)]

    def _compute_bet(self):
        n = len(self.grupos_activos)
        if n == 0:
            return 0.0, 0.0

        is_out = self._is_outside()
        multi  = self._current_multi(is_out)
        if is_out:
            if n == 1:
                total      = self.val_fout * multi
                win_payout = total * 3
            else:
                total      = self.val_fout * multi
                win_payout = (total / n) * 3
        else:
            total      = sum(self._group_cost(g) * multi for g in self.grupos_activos)
            win_payout = self.val_fin * 36 * multi

        return total, win_payout

    def process_number(self, e):
        try:
            btn = e.control
            try:
                self._flash_button(btn, btn.style.bgcolor, 300)
            except Exception:
                pass

            num = int(e.control.data)
            if self.activa:
                n                     = len(self.grupos_activos)
                is_out                = self._is_outside()
                self.last_bet_outside = is_out
                self.last_prog_state  = self.prog_on   # save for undo
                total_cost, win_py    = self._compute_bet()
                self.banca_actual    -= total_cost

                if any(num in GRUPOS_MAESTROS[g] for g in self.grupos_activos):
                    self.banca_actual += win_py
                    self.last_bank_delta = win_py - total_cost
                    # Only reset progression counters when progression is active
                    if self.prog_on:
                        if is_out:
                            self.idx_fibo_out         = 0
                            self.nivel_martingala_out = 0
                        else:
                            self.idx_fibo_in         = 0
                            self.nivel_martingala_in = 0
                else:
                    self.last_bank_delta = -total_cost
                    # Only advance progression counters when progression is active
                    if self.prog_on:
                        if n == 1:
                            if is_out:
                                if self.idx_fibo_out < len(PROG_FIBO) - 1:
                                    self.idx_fibo_out += 1
                            else:
                                if self.idx_fibo_in < len(PROG_FIBO) - 1:
                                    self.idx_fibo_in += 1
                        else:
                            if is_out:
                                self.nivel_martingala_out += 1
                            else:
                                self.nivel_martingala_in += 1
                self.activa         = False
                self.grupos_activos = []
                self.limpiar_seleccion_visual()
            else:
                if self.free_spin_mode:
                    # Red + Black: net 0 unless 0 falls (lose both)
                    delta = -2 * self.val_fin if num == 0 else 0.0
                else:
                    delta = self.val_fin * (1 if num in ROJOS else -1)
                self.banca_actual      += delta
                self.last_bank_delta    = delta
                self.last_bet_outside   = None

            self.history_nums.append(num)
            self.sliding_window.append(num)
            self.update_registration_table()   # buffers row/header updates
            self.actualizar_sugerencias()       # buffers sug_row update
            self.update_ui()                    # single page.update() flushes all
        except Exception as _err:
            import traceback
            with open(os.path.join(tempfile.gettempdir(), "linup_error.log"), "a") as _f:
                _f.write(f"[process_number] {type(_err).__name__}: {_err}\n")
                traceback.print_exc(file=_f)

    @staticmethod
    def _to_display_name(g):
        """Strip live/filter suffixes to get the mixer button key."""
        for sfx in ('_LR', '_LB', '_L', '_R', '_B'):
            if g.endswith(sfx):
                return g[:-len(sfx)]
        return g

    def _refresh_mixer_colors(self):
        has_sel = bool(self.grupos_activos)
        active_display = {self._to_display_name(g) for g in self.grupos_activos}
        for g, btn in self.mixer_btns.items():
            base_color = btn.data['color']
            if g in active_display:
                btn.style = ft.ButtonStyle(
                    bgcolor=base_color, color='#f1c40f',
                    animation_duration=400,
                    overlay_color={ft.ControlState.PRESSED: ft.Colors.with_opacity(0.4, ft.Colors.WHITE)},
                )
            elif has_sel:
                btn.style = ft.ButtonStyle(
                    bgcolor='#2a2a2a', color='#444444',
                    animation_duration=400,
                )
            else:
                btn.style = ft.ButtonStyle(
                    bgcolor=base_color, color=ft.Colors.WHITE,
                    animation_duration=400,
                    overlay_color={ft.ControlState.PRESSED: ft.Colors.with_opacity(0.4, ft.Colors.WHITE)},
                )
            btn.update()

    def seleccionar_mixer(self, e):
        SECTORS = {'Z0', 'ZG', 'ZP', 'H'}
        g = e.control.data['name']
        # In Live Table mode, map dozens/columns to their live/filtered variants
        actual_g = g
        if self.live_table_mode:
            f = self.live_filter
            if g in ('1a', '2a', '3a'):
                actual_g = f'{g}{_DOC_SFX.get(f, "_L")}'
            elif g in ('34', '35', '36') and f:
                actual_g = f'{g}{_COL_SFX.get(f, "")}'
        # Toggle: check by display name to handle live variants
        if g in {self._to_display_name(x) for x in self.grupos_activos}:
            self.grupos_activos = [x for x in self.grupos_activos
                                   if self._to_display_name(x) != g]
        else:
            all_sectors = all(x in SECTORS for x in self.grupos_activos) and g in SECTORS
            limit = 3 if all_sectors else 2
            if len(self.grupos_activos) < limit:
                self.grupos_activos.append(actual_g)
        self._refresh_mixer_colors()
        self.update_inv_label()
        self.lbl_inv.update()

    def _show_roulette_chip_popup(self, on_ready_cb):
        """Show vertical roulette chip placement popup for all active straight groups.
        Calls on_ready_cb() when the user dismisses with READY."""
        multi        = self._current_multi(is_out=False)
        chip_per_num = self.val_fin * multi
        total_cost, _ = self._compute_bet()   # exact amount that will hit the bank

        # Merge all nums from active straight groups (including live inside groups)
        straight_groups = [g for g in self.grupos_activos
                           if g in self.GRUPOS_STRAIGHT or g in GRUPOS_LIVE_INSIDE]
        all_nums: set = set()
        for g in straight_groups:
            all_nums |= GRUPOS_MAESTROS[g]

        # Color: use first group's color, or blended label if two
        def grp_color(g):
            if g in {'Z0', 'ZG', 'ZP', 'H'}:                   return C_SEC
            if g in {'W1', 'W2', 'W3'}:                         return C_WAV
            if self._to_display_name(g) in ('1a', '2a', '3a'):  return C_DOC
            if self._to_display_name(g) in ('34', '35', '36'):  return C_COL
            return C_SET

        def grp_label(g):
            """Human-readable label for chip popup header."""
            for sfx, tag in [('_LR','·R'),('_LB','·B'),('_L18','·1-18'),
                              ('_LE','·Even'),('_LO','·Odd'),('_L36','·19-36'),
                              ('_L',''), ('_R','·R'),('_B','·B'),('_18','·1-18'),
                              ('_E','·Even'),('_O','·Odd'),('_36','·19-36')]:
                if g.endswith(sfx):
                    return self._to_display_name(g) + tag
            return g

        title_chips = [
            ft.Container(
                bgcolor=grp_color(g), border_radius=5,
                padding=ft.padding.symmetric(horizontal=8, vertical=2),
                content=ft.Text(grp_label(g), color=ft.Colors.WHITE, size=14,
                                weight=ft.FontWeight.BOLD),
            )
            for g in straight_groups
        ]

        CELL = 25   # zero cell size
        CN   = 50   # number cell size (double, -10%)
        GAP  = 2

        def num_bg(num):
            return '#27ae60' if num == 0 else ('#c0392b' if num in ROJOS else '#2c3e50')

        def make_cell(num):
            lit = num in all_nums
            return ft.Container(
                width=CN, height=CN,
                bgcolor=num_bg(num),
                border=ft.Border.all(3 if lit else 0.5,
                                     '#f1c40f' if lit else '#444'),
                border_radius=6,
                content=ft.Column(
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    controls=[ft.Text(str(num), size=14, color=ft.Colors.WHITE,
                                      weight=ft.FontWeight.BOLD,
                                      text_align=ft.TextAlign.CENTER)],
                ),
            )


        ROW_W = CN * 3 + GAP * 2   # exact pixel width of a number row

        zero_row = ft.Container(
            width=ROW_W, height=CELL * 2,
            bgcolor='#27ae60',
            border=ft.Border.all(3 if 0 in all_nums else 0.5,
                                 '#f1c40f' if 0 in all_nums else '#444'),
            border_radius=6,
            alignment=ft.Alignment(0, 0),
            content=ft.Text("0", size=14, color=ft.Colors.WHITE,
                            weight=ft.FontWeight.BOLD,
                            text_align=ft.TextAlign.CENTER),
        )

        num_rows = []
        for i in range(12):
            base = i * 3
            a, b, c = base + 1, base + 2, base + 3
            num_rows.append(
                ft.Row([make_cell(a), make_cell(b), make_cell(c)],
                       spacing=GAP, tight=True)
            )

        grid = ft.Container(
            width=ROW_W,
            content=ft.Column(
                controls=[zero_row] + num_rows,
                spacing=GAP,
                tight=True,
            ),
        )


        dlg = ft.AlertDialog(modal=True, bgcolor='#1e1e1e')

        def on_cancel(_ev):
            self._close_dlg(dlg)
            self.page.update()

        def cerrar(_ev):
            self._close_dlg(dlg)
            self.page.update()
            on_ready_cb()

        dlg.title = ft.Column(
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.CENTER,
                    controls=title_chips + [ft.Container(width=6)] + [
                        ft.Text(f"${chip_per_num:.2f}/num",
                                color='#f1c40f', size=13,
                                weight=ft.FontWeight.BOLD),
                    ],
                ),
            ],
        )
        _total_lbl = ft.Text(
            f"Total: ${total_cost:.2f}  ({len(all_nums)} × ${chip_per_num:.2f})",
            color='#ecf0f1', size=12, weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )
        _chip_lbl = dlg.title.controls[0].controls[-1]  # the $/num text in title row

        # When progression is OFF, show live multiplier picker inside the popup
        popup_extra: list = []
        if not self.prog_on:
            _pmx_refs: dict = {}

            def _make_pmx(mx):
                def handler(_ev):
                    self.fixed_multi = mx
                    _c  = self.val_fin * mx
                    _t  = len(all_nums) * _c
                    _chip_lbl.value  = f"${_c:.2f}/num"
                    _total_lbl.value = f"Total: ${_t:.2f}  ({len(all_nums)} × ${_c:.2f})"
                    for k, b in _pmx_refs.items():
                        b.style = ft.ButtonStyle(
                            bgcolor='#f39c12' if k == mx else '#3a3a3a',
                            color=ft.Colors.WHITE,
                        )
                        b.update()
                    _chip_lbl.update()
                    _total_lbl.update()
                    self.update_inv_label()
                    if self.lbl_inv:
                        self.lbl_inv.update()
                return handler

            mx_row = ft.Row(spacing=3, tight=True)
            for _mx in (1, 2, 3, 4, 5):
                _mb = ft.ElevatedButton(
                    content=ft.Text(f"{_mx}x", size=11,
                                    weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    expand=True, height=34,
                    style=ft.ButtonStyle(
                        bgcolor='#f39c12' if _mx == self.fixed_multi else '#3a3a3a',
                        color=ft.Colors.WHITE,
                    ),
                    on_click=_make_pmx(_mx),
                )
                _pmx_refs[_mx] = _mb
                mx_row.controls.append(_mb)

            popup_extra = [
                ft.Container(height=6),
                ft.Text("MULTIPLIER", color='#aaaaaa', size=10,
                        text_align=ft.TextAlign.CENTER),
                mx_row,
            ]

        dlg.content = ft.Column(
            tight=True,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Container(height=4),
                grid,
                ft.Container(height=8),
                _total_lbl,
            ] + popup_extra,
        )
        dlg.actions = [
            ft.ElevatedButton(
                content=ft.Text("CANCEL", size=13, weight=ft.FontWeight.BOLD),
                on_click=on_cancel, expand=1,
                style=ft.ButtonStyle(bgcolor='#c0392b', color=ft.Colors.WHITE),
            ),
            ft.ElevatedButton(
                content=ft.Text("READY", size=13, weight=ft.FontWeight.BOLD),
                on_click=cerrar, expand=1,
                style=ft.ButtonStyle(bgcolor='#27ae60', color=ft.Colors.WHITE),
            ),
        ]
        dlg.actions_alignment = ft.MainAxisAlignment.CENTER
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _activate_bet(self):
        self.activa = True
        self.btn_inv.style = ft.ButtonStyle(bgcolor='#3498db', color=ft.Colors.WHITE,
                                            animation_duration=400)
        self.btn_inv.update()
        self.update_inv_label()
        self.lbl_inv.update()
        self.update_ui()   # immediately reflect pending bet in P/L

    def _check_pre_bet_warning(self, on_confirm):
        """Show warning if losing this bet would breach 45% stop loss."""
        if self.stop_loss_triggered or self.banca_inicial <= 0:
            on_confirm()
            return
        total_cost, _ = self._compute_bet()
        potential_bank = self.banca_actual - total_cost
        loss_pct = (self.banca_inicial - potential_bank) / self.banca_inicial
        if loss_pct < 0.3:
            on_confirm()
            return

        dlg = ft.AlertDialog(modal=True, bgcolor='#1e1e1e')

        def continuar(ev):
            self._close_dlg(dlg)
            self.page.update()
            on_confirm()

        def volver(ev):
            self._close_dlg(dlg)
            self.page.update()

        dlg.title = ft.Text(
            "WARNING",
            color='#f39c12', size=16, weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
        )
        dlg.content = ft.Column(
            tight=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Divider(color='#444444'),
                ft.Text("If you lose this bet:", color=ft.Colors.WHITE, size=13),
                ft.Container(height=4),
                ft.Text(f"Bank: ${potential_bank:.2f}", color='#ff4444',
                        size=18, weight=ft.FontWeight.BOLD),
                ft.Text(f"Loss: {loss_pct*100:.1f}%  (limit 45%)",
                        color='#ff4444', size=13),
            ],
        )
        dlg.actions = [
            ft.ElevatedButton(
                content=ft.Text("BACK", size=14, weight=ft.FontWeight.BOLD),
                on_click=volver, expand=1,
                style=ft.ButtonStyle(bgcolor='#555555', color=ft.Colors.WHITE),
            ),
            ft.ElevatedButton(
                content=ft.Text("CONTINUE", size=14, weight=ft.FontWeight.BOLD),
                on_click=continuar, expand=1,
                style=ft.ButtonStyle(bgcolor='#e67e22', color=ft.Colors.WHITE),
            ),
        ]
        dlg.actions_alignment = ft.MainAxisAlignment.CENTER
        self.page.overlay.append(dlg)
        dlg.open = True
        self.page.update()

    def _has_straight(self):
        return any(g in self.GRUPOS_STRAIGHT or g in GRUPOS_LIVE_INSIDE
                   for g in self.grupos_activos)

    def _proceed_bet(self):
        self._check_pre_bet_warning(self._activate_bet)

    def confirmar_manual(self, e=None):
        if not self.grupos_activos:
            return
        if self._has_straight():
            self._show_roulette_chip_popup(self._proceed_bet)
        else:
            self._proceed_bet()

    def auto_invertir_sug(self, grupos):
        self.limpiar_seleccion_visual()
        self.grupos_activos = list(grupos)
        self._refresh_mixer_colors()
        if self._has_straight():
            self._show_roulette_chip_popup(self._proceed_bet)
        else:
            self._proceed_bet()

    # ──────────────────────────────────────────────────────────────────
    # SUGGESTIONS
    # ──────────────────────────────────────────────────────────────────
    def _make_sug_handler(self, g_par):
        def handler(ev):
            if getattr(self, 'live_table_mode', False):
                # Live mode: just select the group — user presses INVEST to confirm
                self.limpiar_seleccion_visual()
                self.grupos_activos = list(g_par)
                self._refresh_mixer_colors()
                self.update_inv_label()
                if self.lbl_inv:
                    self.lbl_inv.update()
            else:
                self.auto_invertir_sug(g_par)
        return handler

    def actualizar_sugerencias(self):
        vc = getattr(self, 'visible_cats', {k: True for k in ['cols','docs','secs','thirds','wave']})
        all_cats = [
            ('cols',   ['34', '35', '36'],       C_COL),
            ('docs',   ['1a', '2a', '3a'],        C_DOC),
            ('secs',   ['Z0', 'ZG', 'ZP', 'H'],  C_SEC),
            ('thirds', ['T1', 'T2', 'T3'],        C_SET),
            ('wave',   ['W1', 'W2', 'W3'],        C_WAV),
        ]
        cats = [(key, grps, col) for key, grps, col in all_cats if vc.get(key, True)]
        n_cats = max(len(cats), 1)

        if len(self.sliding_window) < 6:
            self.sug_row.controls = [
                ft.ElevatedButton(
                    content=self._txt("×", size=16),
                    expand=True, height=40,
                    style=ft.ButtonStyle(bgcolor='#34495e', color='#7f8c8d'),
                )
                for _ in range(n_cats)
            ]
            self.sug_row.update()
            return

        def _sug_content(label):
            if '+' in label:
                a, b = label.split('+', 1)
                return ft.Column(
                    [ft.Text(a, size=11, weight=ft.FontWeight.BOLD,
                             color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER),
                     ft.Text(b, size=11, weight=ft.FontWeight.BOLD,
                             color=ft.Colors.WHITE, text_align=ft.TextAlign.CENTER)],
                    spacing=0, tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                )
            return self._txt(label, size=12)

        live = getattr(self, 'live_table_mode', False)
        lf   = getattr(self, 'live_filter', None)   # e.g. None, 'R', 'B', '1-18', …

        _FILTER_LABELS = {
            'R': 'R', 'B': 'B', '1-18': '1-18',
            'Even': 'Ev', 'Odd': 'Od', '19-36': '19-36',
        }

        new_btns = []
        PAIR_BLOQUEADO = {'ZG', 'ZP'}
        for key, grupos, color in cats:
            # In live mode, dozens frequency is measured against expanded live sets
            stats = sorted(
                [{'g': g,
                  'p': sum(1 for n in self.sliding_window
                           if n in GRUPOS_MAESTROS[f'{g}_L' if (live and key == 'docs') else g]) / 6}
                 for g in grupos],
                key=lambda x: x['p'], reverse=True,
            )

            if live and key == 'docs':
                # Single most-frequent dozen using live (wheel-expanded) group + active filter
                top      = stats[0]['g']
                actual_g = f'{top}{_DOC_SFX.get(lf, "_L")}'
                ftag     = _FILTER_LABELS[lf] if lf else ''
                label    = f'{top}+{ftag}' if ftag else top
                bg       = color if stats[0]['p'] > 0 else '#34495e'
                click    = self._make_sug_handler([actual_g])
                new_btns.append(
                    ft.ElevatedButton(
                        content=_sug_content(label),
                        expand=True, height=40,
                        on_click=click,
                        style=ft.ButtonStyle(bgcolor=bg, color=ft.Colors.WHITE),
                    )
                )
                continue

            if live and key == 'cols' and lf:
                # Column pair with active filter applied
                if stats[1]['p'] > stats[2 if len(stats) > 2 else 1]['p']:
                    g_par  = [stats[0]['g'], stats[1]['g']]
                    col_sfx = _COL_SFX.get(lf, '')
                    actual  = [f'{g}{col_sfx}' if col_sfx else g for g in g_par]
                    ftag    = _FILTER_LABELS[lf]
                    label   = f'{g_par[0]}·{ftag}+{g_par[1]}·{ftag}'
                    bg      = color
                    click   = self._make_sug_handler(actual)
                else:
                    label = "---"
                    bg    = '#34495e'
                    click = None
                new_btns.append(
                    ft.ElevatedButton(
                        content=_sug_content(label),
                        expand=True, height=40,
                        on_click=click,
                        style=ft.ButtonStyle(bgcolor=bg, color=ft.Colors.WHITE),
                    )
                )
                continue

            # Standard suggestion logic (pair)
            g_par_candidato = {stats[0]['g'], stats[1]['g']}
            es_par_bloqueado = g_par_candidato == PAIR_BLOQUEADO

            if stats[1]['p'] > stats[2 if len(stats) > 2 else 1]['p'] and not es_par_bloqueado:
                g_par = [stats[0]['g'], stats[1]['g']]
                label = f"{g_par[0]}+{g_par[1]}"
                bg    = color
                click = self._make_sug_handler(g_par)
            else:
                label = "---"
                bg    = '#34495e'
                click = None

            new_btns.append(
                ft.ElevatedButton(
                    content=_sug_content(label),
                    expand=True, height=40,
                    on_click=click,
                    style=ft.ButtonStyle(bgcolor=bg, color=ft.Colors.WHITE),
                )
            )

        self.sug_row.controls = new_btns
        self.sug_row.update()

    # ──────────────────────────────────────────────────────────────────

    def limpiar_seleccion_visual(self):
        if self.btn_inv:
            self.btn_inv.style = ft.ButtonStyle(bgcolor='#2ecc71', color=ft.Colors.WHITE,
                                                animation_duration=400)
            self.btn_inv.update()
        self.grupos_activos = []
        self._refresh_mixer_colors()
        self.update_inv_label()
        if self.lbl_inv:
            self.lbl_inv.update()

    def update_inv_label(self):
        if not self.lbl_inv:
            return
        if self.activa or self.grupos_activos:
            total, _ = self._compute_bet()
            is_out = self._is_outside()
            multi  = self._current_multi(is_out)
            if is_out:
                chip_val  = self.val_fout
                num_chips = multi
            else:
                chip_val  = self.val_fin
                num_chips = sum(len(GRUPOS_MAESTROS[g]) for g in self.grupos_activos) * multi
            prog_tag = "" if self.prog_on else f" [{multi}x]"
            self.lbl_inv.value = f"BET: ${total:.2f} ({num_chips}x${chip_val:.4g}){prog_tag}"
        else:
            self.lbl_inv.value = "BET: $0.00"

    def update_ui(self):
        if not self.lbl_bank:
            return
        pl = self.banca_actual - self.banca_inicial
        # When a bet is active, immediately reflect the pending cost in bank + P/L
        displayed_bank = self.banca_actual
        if self.activa:
            pending_cost, _ = self._compute_bet()
            pl -= pending_cost
            displayed_bank -= pending_cost
        pl_pct = (pl / self.banca_inicial * 100) if self.banca_inicial != 0 else 0
        self.lbl_bank.value = f"{self.nombre_mesa}  |  ${displayed_bank:.2f}"
        self.lbl_pl.value   = f"P/L: {pl_pct:+.1f}%"
        self.lbl_pl.color   = '#2ecc71' if pl >= 0 else '#ff4444'
        self.update_inv_label()
        if self.lbl_inv_pl:
            total_pl = self.inv_other_pl + pl
            self.lbl_inv_pl.value = f"P/L: {total_pl:+.2f}"
            self.lbl_inv_pl.color = '#2ecc71' if total_pl >= 0 else '#ff4444'
        self.page.update()
        self._check_stop_loss()

    def corregir_ultimo(self, e=None):
        # First press while bet is active: cancel the pending bet, restore display
        if self.activa:
            self.activa = False
            self.limpiar_seleccion_visual()
            self.update_ui()
            return
        if self.history_nums:
            self.history_nums.pop()
            if self.sliding_window:
                self.sliding_window.pop()
            # Reverse bank
            self.banca_actual -= self.last_bank_delta
            self.last_bank_delta = 0.0
            # Reverse progression only if that bet was running with progression on
            if getattr(self, 'last_prog_state', True):
                if self.last_bet_outside is True:
                    if self.idx_fibo_out > 0:
                        self.idx_fibo_out -= 1
                    if self.nivel_martingala_out > 0:
                        self.nivel_martingala_out -= 1
                elif self.last_bet_outside is False:
                    if self.idx_fibo_in > 0:
                        self.idx_fibo_in -= 1
                    if self.nivel_martingala_in > 0:
                        self.nivel_martingala_in -= 1
            self.last_bet_outside = None
            self.last_prog_state  = True
            self.update_registration_table()
            self.update_ui()


# ──────────────────────────────────────────────────────────────────────
# ENTRY POINT
# ──────────────────────────────────────────────────────────────────────
def main(page: ft.Page):
    LinupApp(page)


ft.app(main)
