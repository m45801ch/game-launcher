import tkinter as tk
try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False
try:
    from tkinterweb import HtmlFrame
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False
from tkinter import ttk, filedialog, messagebox
import json
import os
import subprocess
import threading
import requests
import re
from bs4 import BeautifulSoup
from PIL import Image, ImageTk
from io import BytesIO
from datetime import datetime
import webbrowser  # 新增：用於開啟瀏覽器
import hashlib  # 新增：用於產生圖片快取檔名
import winsound # 新增：用於播放系統音效
import sys
import ctypes

def get_app_dir():
    """程式所在目錄（PyInstaller 打包後以 exe 位置為準）"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))

# 資料路徑以「程式所在目錄」為基準（PyInstaller 打包後即 exe 所在目錄）
# 這樣從任何目錄啟動 exe 都能讀到同一份 games.json / config.json
_APP_DIR = get_app_dir()
DATA_FILE = os.path.join(_APP_DIR, "games.json")
CACHE_DIR = os.path.join(_APP_DIR, "img_cache") # 新增：圖片快取資料夾
CONFIG_FILE = os.path.join(_APP_DIR, "config.json") # 新增：設定檔

# 版本號
APP_VERSION = "v1.0"

class GameLauncherApp:
    def __init__(self, root):
        self.root = root
        self.root.title(f"我的本地遊戲啟動器 {APP_VERSION}")
        self.root.geometry("1280x850") 
        self.root.configure(bg="#121212")
        
        # 啟動時最大化視窗 (Windows)
        try:
            self.root.state('zoomed')
        except:
            pass

        # 初始化資料
        self.games = self.load_games()
        self.current_selected_index = None
        
        # 圖片與卡片快取
        self.image_cache = {} 
        self.thumbnail_cache = {}
        
        # 載入設定（路徑以 exe 所在目錄為基準）
        self.config_file = CONFIG_FILE
        self.config = self.load_config()
        # 載入設定（路徑以 exe 所在目錄為基準）
        self.config_file = CONFIG_FILE
        self.config = self.load_config()
        self.is_privacy_mode = False
        self.is_vhost_mode = False
        self.is_favorite_mode = False
        self.is_move_mode = False
        self.batch_selection = [] # 儲存勾選的遊戲 index

        self.card_widgets = [] 
        
        # Grid 排版設定        # 工具欄內容
        self.grid_columns = tk.IntVar(value=7)  # 預設 7 個

        # 建立快取資料夾
        os.makedirs(CACHE_DIR, exist_ok=True)

        # 載入設定
        self.config = self.load_config()

        # 設定樣式
        self.setup_styles()
        
        # 建立 UI
        self.create_widgets()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        bg_color = "#121212"
        fg_color = "#eeeeee"
        accent_color = "#007acc"
        
        style.configure("TFrame", background=bg_color)
        style.configure("TLabel", background=bg_color, foreground=fg_color, font=("微軟正黑體", 10))
        style.configure("Header.TLabel", font=("微軟正黑體", 20, "bold"))
        style.configure("TButton", font=("微軟正黑體", 10), background="#2d2d30", foreground="#ffffff", borderwidth=0)
        style.map("TButton", background=[("active", accent_color)])
        
        style.configure("Action.TButton", font=("微軟正黑體", 12, "bold"), background="#ff6600", foreground="white")
        style.configure("Update.TButton", font=("微軟正黑體", 10), background="#6c5ce7")
        # 最愛按鈕樣式
        style.configure("Fav.TButton", font=("微軟正黑體", 11), background="#e91e63", foreground="white")
        # Steam 按鈕樣式 (深藍色)
        style.configure("Steam.TButton", font=("微軟正黑體", 11), background="#171a21", foreground="white")

    def create_widgets(self):
        # 使用 PanedWindow
        self.paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True)

        # --- 左側：海報牆區域 ---
        self.left_frame = ttk.Frame(self.paned)
        self.paned.add(self.left_frame, weight=8)

        # 頂部工具列
        toolbar = tk.Frame(self.left_frame, bg="#1e1e1e", height=50)
        toolbar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # 容器
        ltb = tk.Frame(toolbar, bg="#1e1e1e")
        ltb.pack(side=tk.LEFT, fill=tk.Y)
        rtb = tk.Frame(toolbar, bg="#1e1e1e")
        rtb.pack(side=tk.RIGHT, fill=tk.Y)

        def create_tool_btn(text, cmd, color=None, parent=ltb):
            container = tk.Frame(parent, bg="#1e1e1e", padx=3, pady=3)
            container.pack(side=tk.LEFT, padx=2)
            btn = tk.Button(container, text=text, command=cmd, bg="#2d2d30" if not color else color, 
                          fg="white", font=("微軟正黑體", 12, "bold"), relief="flat", padx=15, pady=5)
            btn.pack()
            btn.container = container 
            return btn

        # 功能區 (左)
        create_tool_btn("+ 新增", self.open_add_game_window)
        create_tool_btn("🔍 批量", self.open_bulk_import_window)
        create_tool_btn("☁️ 智能更新", self.auto_update_game_info, "#6c5ce7")
        create_tool_btn("🛠️ 庫管", self.open_library_manager)
        self.privacy_mgr_btn = create_tool_btn("📝 名單", self.open_privacy_manager, "#888") 
        create_tool_btn("📦 備份", self.backup_database)
        create_tool_btn("✎ 編輯", self.edit_game)
        create_tool_btn("- 移除", self.delete_game)

        # 模式與排版區 (右)
        # 排版與搜尋放在 rtb 的最右邊
        setting_frame = tk.Frame(rtb, bg="#1e1e1e")
        setting_frame.pack(side=tk.RIGHT, padx=10)
        
        # 空間按鈕在 rtb 中靠右排列
        self.btn_move = create_tool_btn("📦 批量移動", self.switch_to_move, "#f39c12", parent=rtb)
        self.btn_vhost = create_tool_btn("🖥️ 虛擬", self.switch_to_vhost, "#5a1212", parent=rtb)
        self.btn_privacy = create_tool_btn("🔐 隱私", self.switch_to_privacy, "#555", parent=rtb)
        self.btn_favorite = create_tool_btn("❤ 收藏", self.switch_to_favorite, "#555", parent=rtb)
        self.btn_general = create_tool_btn("🏠 一般", self.switch_to_general, "#007acc", parent=rtb)
        
        # 拖曳狀態
        self.drag_data = {"start_index": None, "current_index": None, "x": 0, "y": 0, "dragging": False}

        # 排序選單
        tk.Label(setting_frame, text="排序:", bg="#1e1e1e", fg="#aaa").pack(side=tk.LEFT, padx=2)
        self.sort_var = tk.StringVar(value="自訂排序")
        self.sort_combo = ttk.Combobox(setting_frame, textvariable=self.sort_var, 
                                       values=["自訂排序", "預設 (最愛)", "🕒 最近遊玩"], 
                                       state="readonly", width=12, font=("微軟正黑體", 9))
        self.sort_combo.pack(side=tk.LEFT, padx=5)
        self.sort_combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_list())

        # 版本號（工具列最右）
        self.version_label = tk.Label(setting_frame, text=APP_VERSION, bg="#1e1e1e", fg="#555",
                                      font=("微軟正黑體", 10, "bold"))
        self.version_label.pack(side=tk.RIGHT, padx=(0, 10))

        tk.Label(setting_frame, text="排列:", bg="#1e1e1e", fg="#aaa").pack(side=tk.LEFT, padx=2)
        scale = tk.Scale(setting_frame, from_=2, to=8, orient=tk.HORIZONTAL, 
                         variable=self.grid_columns, bg="#1e1e1e", fg="white", 
                         highlightthickness=0, length=80, command=lambda v: self.refresh_list())
        scale.pack(side=tk.LEFT)
        
        tk.Button(setting_frame, text="↻", command=self.refresh_list, bg="#1e1e1e", fg="white", relief="flat", font=("Arial", 12)).pack(side=tk.LEFT, padx=5)

        # 捲動區域 (Canvas)
        self.canvas = tk.Canvas(self.left_frame, bg="#121212", highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.left_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg="#121212") # 改用 tk.Frame 以支援 bg 變更

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        
        self.canvas.bind("<Configure>", self.on_canvas_configure)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # --- 右側：詳細資訊 ---
        self.right_panel = ttk.Frame(self.paned, width=512)
        self.paned.add(self.right_panel, weight=2)  # 改為 2，配合左側 weight=8 形成 8:2 比例

        self.right_bg = tk.Frame(self.right_panel, bg="#000000")
        self.right_bg.pack(fill=tk.BOTH, expand=True)

        self.cover_label = tk.Label(self.right_bg, text="選擇遊戲", bg="#000000", fg="#555", font=("微軟正黑體", 12))
        self.cover_label.pack(pady=(30, 10), fill=tk.X, padx=20)

        self.title_label = tk.Label(self.right_bg, text="", bg="#000000", fg="white", font=("微軟正黑體", 22, "bold"), wraplength=350)
        self.title_label.pack(pady=5, fill=tk.X, padx=20)
        
        self.subtitle_label = tk.Label(self.right_bg, text="", bg="#000000", fg="#aaaaaa", font=("Arial", 14), wraplength=350)
        self.subtitle_label.pack(pady=0, fill=tk.X, padx=20)

        # 上次遊玩時間顯示
        self.last_played_label = tk.Label(self.right_bg, text="", bg="#000000", fg="#4caf50", font=("微軟正黑體", 10))
        self.last_played_label.pack(pady=(5,0), fill=tk.X, padx=20)

        # 按鈕區 (啟動 + 最愛 + Steam)
        action_frame = tk.Frame(self.right_bg, bg="#000000")
        action_frame.pack(pady=20, fill=tk.X, padx=20)

        self.launch_btn = ttk.Button(action_frame, text="立即啟動", style="Action.TButton", command=self.launch_game, state=tk.DISABLED)
        self.launch_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=10, padx=(0, 5))

        self.fav_btn = ttk.Button(action_frame, text="🤍", style="Fav.TButton", command=self.toggle_favorite, state=tk.DISABLED, width=12)
        self.fav_btn.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        # Steam 按鈕
        self.steam_btn = ttk.Button(action_frame, text="Steam 商店", style="Steam.TButton", state=tk.DISABLED, width=10)
        self.steam_btn.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        # 新增：單一遊戲更新按鈕
        self.update_info_btn = ttk.Button(self.right_bg, text="✨ 更新資料 (從 Steam)", style="Update.TButton", command=self.update_selected_game_info, state=tk.DISABLED)
        self.update_info_btn.pack(pady=(10, 0), fill=tk.X, padx=20)

        tk.Frame(self.right_bg, height=1, bg="#333").pack(fill=tk.X, padx=20, pady=10)

        tk.Label(self.right_bg, text="遊戲簡介", bg="#000000", fg="#888", anchor="w").pack(fill=tk.X, padx=20)
        
        self.desc_text = tk.Text(
            self.right_bg, 
            bg="#000000", 
            fg="#cccccc", 
            font=("微軟正黑體", 20), 
            wrap=tk.WORD, 
            bd=0, 
            highlightthickness=0,
            state=tk.DISABLED,
            height=15
        )
        self.desc_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # --- 影片預覽區 ---
        self.video_frame_outer = tk.Frame(self.right_bg, bg="#000000")
        self.video_frame_outer.pack(fill=tk.X, padx=20, pady=(0, 5))
        self.video_frame_outer.pack_forget()  # 預設隱藏

        tk.Label(self.video_frame_outer, text="🎬 遊戲影片", bg="#000000", fg="#888", anchor="w").pack(fill=tk.X)

        # 影片縮圖 + 點擊播放
        self.video_thumb_label = tk.Label(
            self.video_frame_outer, text="",
            bg="#000", fg="#ccc", cursor="hand2",
            font=("微軟正黑體", 10)
        )

        self.video_open_btn = tk.Button(
            self.video_frame_outer, text="▶  在瀏覽器中播放影片",
            bg="#c0392b", fg="white", relief="flat",
            font=("微軟正黑體", 10), cursor="hand2"
        )
        self.video_open_btn.pack_forget()

        # Steam 實時資訊區
        self.steam_info_frame = tk.Frame(self.right_bg, bg="#000000")
        self.steam_info_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        def create_info_row(label_text):
            row = tk.Frame(self.steam_info_frame, bg="#000000")
            row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=label_text, bg="#000000", fg="#888", font=("微軟正黑體", 9), width=8, anchor="w").pack(side=tk.LEFT)
            val_label = tk.Label(row, text="", bg="#000000", fg="#ccc", font=("微軟正黑體", 9), wraplength=220, anchor="w", justify=tk.LEFT)
            val_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
            return val_label

        self.info_labels = {
            "reviews": create_info_row("所有評論:"),
            "date": create_info_row("發行日期:"),
            "dev": create_info_row("開發人員:"),
            "pub": create_info_row("發行商:")
        }

        self.refresh_list()
        
        # 綁定視窗關閉事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 恢復上次的視窗比例（使用比例而非絕對位置）
        if 'sash_ratio' in self.config:
            self.restore_attempts = 0
            def try_restore_sash():
                try:
                    self.restore_attempts += 1
                    window_width = self.paned.winfo_width()
                    # 只有當寬度有效且大於 200 時才嘗試恢復
                    if window_width > 200:
                        saved_ratio = self.config['sash_ratio']
                        if 0.2 <= saved_ratio <= 0.9:
                            sash_pos = int(window_width * saved_ratio)
                            self.paned.sashpos(0, sash_pos)
                    elif self.restore_attempts < 10:
                        # 若視窗尚未準備好，延遲後重試
                        self.root.after(200, try_restore_sash)
                except:
                    pass
            
            # 延遲啟動嘗試
            self.root.after(500, try_restore_sash)

        # 啟用拖曳 EXE 新增遊戲
        if HAS_DND:
            self.canvas.drop_target_register(DND_FILES)
            self.canvas.dnd_bind('<<Drop>>', self.on_exe_drop)
            self.scrollable_frame.drop_target_register(DND_FILES)
            self.scrollable_frame.dnd_bind('<<Drop>>', self.on_exe_drop)

    def on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)
        if hasattr(self, '_resize_job'):
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(200, self.refresh_list)

    def get_local_image_path(self, url):
        if not url: return None
        # 使用 URL 的 MD5 作為檔名
        ext = os.path.splitext(url)[1]
        if '?' in ext: ext = ext.split('?')[0] # 處理網址參數
        if not ext or len(ext) > 5: ext = ".jpg" # 預設副檔名
        
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()
        return os.path.join(CACHE_DIR, f"{url_hash}{ext}")

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def load_config(self):
        """載入設定檔"""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_config(self):
        """儲存設定檔"""
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
        except:
            pass
    
    def on_closing(self):
        """視窗關閉時儲存設定"""
        try:
            # 儲存 sash 比例而非絕對位置
            sash_pos = self.paned.sashpos(0)
            window_width = self.root.winfo_width()
            if window_width > 0:
                ratio = sash_pos / window_width
                # 只儲存合理的比例 (0.2 ~ 0.9)
                if 0.2 <= ratio <= 0.9:
                    self.config['sash_ratio'] = ratio
                    self.save_config()
        except:
            pass
        self.root.destroy()
    def load_config(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_config(self):
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=4)

    def resolve_ts_script(self, config_key, filename):
        """解析 Test Signing 批次檔：自訂路徑 → 程式目錄 → 工作目錄"""
        candidates = [
            self.config.get(config_key),
            os.path.join(get_app_dir(), filename),
            os.path.join(os.getcwd(), filename),
        ]
        for p in candidates:
            if p and os.path.isfile(p):
                return os.path.abspath(p)
        return None

    def run_as_admin(self, path):
        """以管理員權限執行批次檔（觸發 UAC），保留主控台視窗顯示結果"""
        path = os.path.abspath(path)
        workdir = os.path.dirname(path) or get_app_dir()
        cmd_exe = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "cmd.exe")
        rc = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", cmd_exe, f'/c ""{path}""', workdir, 1)
        if rc <= 32:
            raise OSError(f"無法取得管理員權限（代碼 {rc}，可能是取消 UAC 提示）")

    def update_space_buttons(self):
        vhost_inactive = "#5a1212" # 深紅色
        vhost_active = "#ff0000"   # 亮紅色
        fav_active = "#e91e63"     # 收藏粉紅色
        active_border = "yellow"
        inactive_border = "#1e1e1e"
        
        # 預設全部灰色
        self.btn_general.config(bg="#555")
        self.btn_general.container.config(bg=inactive_border)
        self.btn_favorite.config(bg="#555")
        self.btn_favorite.container.config(bg=inactive_border)
        self.btn_privacy.config(bg="#555", text="🔐 隱私")
        self.btn_privacy.container.config(bg=inactive_border)
        self.btn_vhost.config(bg=vhost_inactive)
        self.btn_vhost.container.config(bg=inactive_border)
        self.btn_move.config(bg="#555")
        self.btn_move.container.config(bg=inactive_border)

        # 根據模式點亮
        if self.is_privacy_mode:
            self.btn_privacy.config(bg="#FF69B4", text="🔒 隱私 (開啟)")
            self.btn_privacy.container.config(bg=active_border)
        elif self.is_vhost_mode:
            self.btn_vhost.config(bg=vhost_active) 
            self.btn_vhost.container.config(bg=active_border)
        elif self.is_favorite_mode:
            self.btn_favorite.config(bg=fav_active)
            self.btn_favorite.container.config(bg=active_border)
        elif self.is_move_mode:
            self.btn_move.config(bg="#f39c12")
            self.btn_move.container.config(bg=active_border)
        else:
            self.btn_general.config(bg="#007acc")
            self.btn_general.container.config(bg=active_border)

    def switch_to_general(self):
        self.is_privacy_mode = False
        self.is_vhost_mode = False
        self.is_favorite_mode = False
        self.is_move_mode = False
        self.update_space_buttons()
        self.refresh_list()
    
    def switch_to_favorite(self):
        self.is_favorite_mode = True
        self.is_privacy_mode = False
        self.is_vhost_mode = False
        self.is_move_mode = False
        self.update_space_buttons()
        self.refresh_list()

    def switch_to_move(self):
        self.is_move_mode = not self.is_move_mode
        if self.is_move_mode:
            self.batch_selection = []
        self.update_space_buttons()
        self.refresh_list()

    def switch_to_privacy(self):
        if self.is_privacy_mode:
            return
        
        # 防止重複開啟視窗
        if hasattr(self, "login_win") and self.login_win.winfo_exists():
            self.login_win.focus_force()
            return
        if hasattr(self, "setup_win") and self.setup_win.winfo_exists():
            self.setup_win.focus_force()
            return
            
        self.is_vhost_mode = False
        self.is_favorite_mode = False
        
        # Check if password is set
        if "privacy_password_hash" not in self.config:
            self.ask_setup_password()
        else:
            self.ask_login_password()
    
    def switch_to_vhost(self):
        self.is_vhost_mode = True
        self.is_privacy_mode = False
        self.is_favorite_mode = False
        self.update_space_buttons()
        self.refresh_list()
    
    def ask_setup_password(self):
        self.setup_win = tk.Toplevel(self.root)
        self.setup_win.title("設定隱私密碼")
        self.setup_win.geometry("300x250")
        self.setup_win.configure(bg="#2d2d30")
        self.setup_win.attributes('-topmost', True)
        
        tk.Label(self.setup_win, text="設定新密碼:", bg="#2d2d30", fg="white").pack(pady=(20, 5))
        pw_entry = tk.Entry(self.setup_win, show="*", bg="#3e3e42", fg="white")
        pw_entry.pack(pady=5)
        
        tk.Label(self.setup_win, text="確認密碼:", bg="#2d2d30", fg="white").pack(pady=5)
        confirm_entry = tk.Entry(self.setup_win, show="*", bg="#3e3e42", fg="white")
        confirm_entry.pack(pady=5)

        tk.Label(self.setup_win, text="密碼提示語 (選填):", bg="#2d2d30", fg="white").pack(pady=5)
        hint_entry = tk.Entry(self.setup_win, bg="#3e3e42", fg="white")
        hint_entry.pack(pady=5)
        
        def commit():
            p1 = pw_entry.get()
            p2 = confirm_entry.get()
            hint = hint_entry.get()
            
            if not p1:
                messagebox.showerror("錯誤", "密碼不能為空", parent=self.setup_win)
                return
            if p1 != p2:
                messagebox.showerror("錯誤", "兩次密碼輸入不一致", parent=self.setup_win)
                return
            
            # Save hash
            hashed = hashlib.sha256(p1.encode()).hexdigest()
            self.config["privacy_password_hash"] = hashed
            self.config["password_hint"] = hint
            self.save_config()
            
            messagebox.showinfo("成功", "密碼設定成功！現在進入隱私模式。", parent=self.setup_win)
            self.setup_win.destroy()
            
            # Auto login
            self.is_privacy_mode = True
            self.update_space_buttons()
            self.refresh_list()
            
        tk.Button(self.setup_win, text="確定", command=commit, bg="#007acc", fg="white").pack(pady=20)

    def ask_login_password(self):
        self.login_win = tk.Toplevel(self.root)
        self.login_win.title("輸入隱私密碼")
        self.login_win.geometry("300x200")
        self.login_win.configure(bg="#2d2d30")
        self.login_win.attributes('-topmost', True)
        self.login_win.focus_force()
        
        tk.Label(self.login_win, text="請輸入密碼:", bg="#2d2d30", fg="white").pack(pady=(30, 10))
        pw_entry = tk.Entry(self.login_win, show="*", bg="#3e3e42", fg="white")
        pw_entry.pack(pady=5)
        pw_entry.focus_set()
        
        def check_pw(event=None):
            pw = pw_entry.get()
            hashed = hashlib.sha256(pw.encode()).hexdigest()
            
            # Check against stored hash or master password
            stored_hash = self.config.get("privacy_password_hash")
            
            if hashed == stored_hash or pw == "Aa88888888":
                self.is_privacy_mode = True
                self.update_space_buttons()
                self.refresh_list()
                self.login_win.destroy()
            else:
                messagebox.showerror("錯誤", "密碼錯誤！", parent=self.login_win)
                pw_entry.delete(0, tk.END)
        
        def show_hint():
            hint = self.config.get("password_hint", "未設定提示語")
            if not hint: hint = "未設定提示語"
            messagebox.showinfo("密碼提示", f"您的提示語是：\n{hint}", parent=self.login_win)

        tk.Button(self.login_win, text="登入", command=check_pw, bg="#007acc", fg="white").pack(pady=(10, 5))
        tk.Button(self.login_win, text="顯示提示", command=show_hint, bg="#2d2d30", fg="#888", relief="flat").pack(pady=5)
        
        pw_entry.bind("<Return>", check_pw)

    def execute_batch_move(self, target):
        if not self.batch_selection:
            messagebox.showwarning("提示", "請先勾選要移動的遊戲！")
            return
            
        count = len(self.batch_selection)
        for idx in self.batch_selection:
            game = self.games[idx]
            if target == "general":
                game["is_private"] = False
                game["is_vhost"] = False
                game["favorite"] = False
            elif target == "favorite":
                game["favorite"] = True
                game["is_private"] = False
                game["is_vhost"] = False
            elif target == "privacy":
                game["is_private"] = True
                game["is_vhost"] = False
            elif target == "vhost":
                game["is_vhost"] = True
                game["is_private"] = False
        
        self.save_games()
        self.batch_selection = []
        messagebox.showinfo("成功", f"已成功將 {count} 個遊戲移動至新標籤！")
        self.refresh_list()

    def load_games(self):
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for g in data:
                        if "name_zh" not in g: g["name_zh"] = g.get("name", "未命名")
                        if "name_en" not in g: 
                            base = os.path.splitext(os.path.basename(g.get("path", "")))[0]
                            g["name_en"] = re.sub(r'[-_]?(Shipping|Win64|Release)', '', base, flags=re.IGNORECASE)
                        if "favorite" not in g: g["favorite"] = False
                        if "last_played" not in g: g["last_played"] = ""
                        if "steam_url" not in g: g["steam_url"] = "" # 新增欄位
                    return data
            except:
                return []
        return []

    def save_games(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.games, f, ensure_ascii=False, indent=4)

    def refresh_list(self):
        # 根據模式過濾
        if self.is_privacy_mode:
            display_games = [g for g in self.games if g.get("is_private", False)]
            bg_color = "#2d1b2e"
        elif self.is_vhost_mode:
            display_games = [g for g in self.games if g.get("is_vhost", False)]
            bg_color = "#4a1212"
        elif self.is_favorite_mode:
            display_games = [g for g in self.games if g.get("favorite", False)]
            bg_color = "#1a1a2e"
        else:
            display_games = [g for g in self.games if not g.get("is_private", False) and not g.get("is_vhost", False)]
            bg_color = "#121212"

        self.canvas.config(bg=bg_color)
        self.scrollable_frame.config(bg=bg_color)

        sort_mode = self.sort_var.get()
        if "自訂" not in sort_mode:
            if "最近" in sort_mode:
                display_games.sort(key=lambda x: x.get("last_played", ""), reverse=True)
            else:
                display_games.sort(key=lambda x: x.get("favorite", False), reverse=True)

        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.card_widgets = []

        # 批量操作面板
        if self.is_move_mode:
            batch_bar = tk.Frame(self.scrollable_frame, bg="#000000", pady=10)
            batch_bar.pack(fill=tk.X, padx=10, pady=(0, 10))
            
            self.batch_status_label = tk.Label(batch_bar, text=f"已選取 {len(self.batch_selection)} 個項目", 
                                             bg="#000000", fg="#f39c12", font=("微軟正黑體", 11, "bold"))
            self.batch_status_label.pack(side=tk.LEFT, padx=15)
            
            def move_to(t): self.execute_batch_move(t)
            
            # 全選與取消
            def select_all():
                self.batch_selection = [self.games.index(g) for g in display_games]
                self.refresh_list()
            
            tk.Button(batch_bar, text="☑ 全選", command=select_all, bg="#444", fg="white", relief="flat", padx=10).pack(side=tk.LEFT, padx=5)
            tk.Button(batch_bar, text="☒ 取消", command=lambda: (setattr(self, 'batch_selection', []), self.refresh_list()), bg="#444", fg="white", relief="flat", padx=10).pack(side=tk.LEFT, padx=5)

            tk.Label(batch_bar, text="| 批次移動至:", bg="#000000", fg="#888").pack(side=tk.LEFT, padx=10)
            
            tk.Button(batch_bar, text="🏠 一般", command=lambda: move_to("general"), bg="#007acc", fg="white", relief="flat", padx=12, pady=2).pack(side=tk.LEFT, padx=2)
            tk.Button(batch_bar, text="❤ 收藏", command=lambda: move_to("favorite"), bg="#e91e63", fg="white", relief="flat", padx=12, pady=2).pack(side=tk.LEFT, padx=2)
            tk.Button(batch_bar, text="🔐 隱私", command=lambda: move_to("privacy"), bg="#FF69B4", fg="white", relief="flat", padx=12, pady=2).pack(side=tk.LEFT, padx=2)
            tk.Button(batch_bar, text="🖥️ 虛擬", command=lambda: move_to("vhost"), bg="#ff0000", fg="white", relief="flat", padx=12, pady=2).pack(side=tk.LEFT, padx=2)

        # 清除舊的固定說明欄位（如果存在）
        if hasattr(self, "vhost_fixed_frame") and self.vhost_fixed_frame:
            self.vhost_fixed_frame.destroy()
            self.vhost_fixed_frame = None

        # 虛擬頁面：Test Signing 開／關（VBS.cmd 在本機無法使用）
        if self.is_vhost_mode:
            vhost_info = (
                "【使用方式：Test Signing（VBS 模式在本機無法使用，已改為 Test Signing）】\n"
                "1. 玩遊戲前：按「① 開 Test Signing」執行 TS_On.bat（跳出 UAC 時以管理員執行）\n"
                "2. 重新開機 → 桌面出現「測試模式 / Test Mode」浮水印屬正常現象 → 再啟動遊戲\n"
                "3. 玩完遊戲後：按「② 關 Test Signing」執行 TS_Off.bat（管理員）\n"
                "4. 重新開機 → 恢復正常模式，浮水印消失\n"
                "※ 開／關都必須重開機才會生效；按鈕左鍵執行、右鍵可更換批次檔路徑"
            )
            # 建立固定容器，放置在 left_frame 中，canvas 之前
            self.vhost_fixed_frame = tk.Frame(self.left_frame, bg="#000000", pady=15, padx=20, 
                                            highlightthickness=2, highlightbackground="#ff0000")
            self.vhost_fixed_frame.pack(fill=tk.X, pady=(0, 10), padx=10, before=self.canvas)
            
            tk.Label(self.vhost_fixed_frame, text=vhost_info, bg="#000000", fg="#ffffff", 
                     font=("微軟正黑體", 13, "bold"), justify=tk.LEFT, anchor="w").pack(fill=tk.X)
            
            btn_row = tk.Frame(self.vhost_fixed_frame, bg="#000000")
            btn_row.pack(fill=tk.X, pady=(15, 0))

            def select_ts(key, filename, event=None):
                path = filedialog.askopenfilename(title=f"選擇 {filename}",
                                                  filetypes=[("批次檔", "*.bat;*.cmd"), ("所有檔案", "*.*")])
                if path:
                    self.config[key] = path
                    self.save_config()
                    messagebox.showinfo("成功", f"已設定路徑：\n{path}")
                    return True
                return False

            def run_ts(key, filename, title):
                path = self.resolve_ts_script(key, filename)
                if not path:
                    messagebox.showwarning("找不到檔案", f"找不到 {filename}，請手動選擇檔案位置。")
                    if not select_ts(key, filename):
                        return
                    path = self.resolve_ts_script(key, filename)
                if not path:
                    return
                try:
                    self.run_as_admin(path)
                except Exception as e:
                    messagebox.showerror("錯誤", f"無法執行 {title}：{e}")

            ts_specs = [
                ("ts_on_path", "TS_On.bat", "① 開 Test Signing（TS_On.bat）", "#27ae60"),
                ("ts_off_path", "TS_Off.bat", "② 關 Test Signing（TS_Off.bat）", "#c0392b"),
            ]
            for key, filename, label, color in ts_specs:
                btn = tk.Button(btn_row, text=label,
                                command=lambda k=key, f=filename, t=label: run_ts(k, f, t),
                                bg=color, fg="white", font=("微軟正黑體", 11, "bold"),
                                relief="flat", cursor="hand2", padx=20, pady=5)
                btn.pack(side=tk.LEFT, padx=(15, 0))
                btn.bind("<Button-3>", lambda e, k=key, f=filename: select_ts(k, f, e))
            tk.Label(btn_row, text="(左鍵執行 / 右鍵更換路徑)", bg="#000000", fg="#888",
                     font=("微軟正黑體", 9)).pack(side=tk.LEFT, padx=10)

        if not display_games:
            msg = "🔒 這裡是隱私空間，目前沒有遊戲。" if self.is_privacy_mode else "👋 歡迎！請點擊上方「批量掃描」或「新增」來加入遊戲。"
            tk.Label(self.scrollable_frame, text=msg, 
                     bg=bg_color, fg="#888", font=("微軟正黑體", 14)).pack(pady=100)
            return

        canvas_width = self.canvas.winfo_width()
        if canvas_width < 100: canvas_width = 800
        cols = self.grid_columns.get()
        padding_x = 10 
        total_padding = (cols + 1) * padding_x
        card_width = max(120, int((canvas_width - total_padding) / cols))
        img_height = int(card_width * (215 / 460))
        card_height = img_height + 65

        gallery_frame = tk.Frame(self.scrollable_frame, bg=bg_color)
        gallery_frame.pack(fill=tk.BOTH, expand=True)

        for i, game in enumerate(display_games):
            real_index = self.games.index(game)
            row, col = i // cols, i % cols
            self.create_game_card(gallery_frame, game, real_index, row, col, card_width, img_height, card_height, padding_x)

    def create_game_card(self, parent, game, index, row, col, w, h_img, h_card, pad):
        card_bg = "#000000"
        hover_bg = "#1e1e1e"
        is_selected = index in self.batch_selection
        
        # 批量模式下選中的邊框顏色
        border_color = "#f39c12" if (self.is_move_mode and is_selected) else card_bg
        
        card = tk.Frame(parent, bg=card_bg, width=w, height=h_card, 
                        highlightthickness=3, highlightbackground=border_color)
        card.real_index = index
        card.grid(row=row, column=col, padx=pad/2, pady=pad/2)
        card.grid_propagate(False)
        self.card_widgets.append(card)

        # 圖片容器
        img_container = tk.Label(card, text="No Image", bg="#000", fg="#333")
        img_container.place(x=0, y=0, width=w, height=h_img)

        if game.get("image_url"):
            threading.Thread(target=self.load_thumbnail_async, args=(game["image_url"], img_container, w, h_img), daemon=True).start()
        else:
            img_container.config(text=game.get("name_zh", "")[:1], font=("Arial", int(w/4)))
        
        # 英文名稱
        en_name = game.get("name_en", "")
        en_label = tk.Label(card, text=en_name, bg=card_bg, fg="#aaaaaa", 
                           font=("Arial", 10), anchor="w")
        en_label.place(x=5, y=h_img + 2, width=w-10, height=20)

        # 中文名稱
        zh_name = game.get("name_zh", game.get("name", "未命名"))
        zh_label = tk.Label(card, text=zh_name, bg=card_bg, fg="#ffffff", 
                            font=("微軟正黑體", 13, "bold"), anchor="w")
        zh_label.place(x=5, y=h_img + 22, width=w-10, height=30)

        # 批量選取勾選框
        cb = None
        if self.is_move_mode:
            check_bg = "#f39c12" if is_selected else "#444"
            check_fg = "white" if is_selected else "#888"
            check_text = "✔" if is_selected else ""
            cb = tk.Label(card, text=check_text, bg=check_bg, fg=check_fg, font=("Arial", 12, "bold"))
            cb.place(x=5, y=5, width=25, height=25)

        def toggle_selection(e=None):
            if self.is_move_mode:
                if index in self.batch_selection:
                    self.batch_selection.remove(index)
                    # 局部更新為未選中
                    card.config(highlightbackground="#000000")
                    if cb: cb.config(text="", bg="#444", fg="#888")
                else:
                    self.batch_selection.append(index)
                    # 局部更新為選中
                    card.config(highlightbackground="#f39c12")
                    if cb: cb.config(text="✔", bg="#f39c12", fg="white")
                
                # 更新狀態文字
                if hasattr(self, "batch_status_label"):
                    self.batch_status_label.config(text=f"已選取 {len(self.batch_selection)} 個項目")
            else:
                self.on_game_select(index)

        # 懸停效果
        def on_enter(e): 
            card.config(bg=hover_bg)
            zh_label.config(bg=hover_bg)
            en_label.config(bg=hover_bg)
        def on_leave(e): 
            card.config(bg=card_bg)
            zh_label.config(bg=card_bg)
            en_label.config(bg=card_bg)

        card.bind("<Enter>", on_enter)
        card.bind("<Leave>", on_leave)

        # 拖曳事件綁定
        def on_drag_start(event):
            if self.is_move_mode: return
            self.drag_data["start_index"] = index
            self.drag_data["x"] = event.x_root
            self.drag_data["y"] = event.y_root
            self.drag_data["dragging"] = False
            
        def on_drag_motion(event):
            if self.is_move_mode: return
            if not self.drag_data["start_index"] is None:
                if abs(event.x_root - self.drag_data["x"]) > 5 or abs(event.y_root - self.drag_data["y"]) > 5:
                    self.drag_data["dragging"] = True
                    card.config(cursor="fleur")
                    if self.sort_var.get() != "自訂排序":
                        self.sort_var.set("自訂排序")

        def on_drag_stop(event):
            start_idx = self.drag_data["start_index"]
            self.drag_data["start_index"] = None
            card.config(cursor="")
            
            if self.drag_data["dragging"]:
                x, y = event.x_root, event.y_root
                item = self.games[start_idx]
                
                # --- 偵測是否落在標籤按鈕上 ---
                def is_over(widget):
                    if not widget: return False
                    try:
                        wx, wy = widget.winfo_rootx(), widget.winfo_rooty()
                        ww, wh = widget.winfo_width(), widget.winfo_height()
                        return wx <= x <= wx + ww and wy <= y <= wy + wh
                    except: return False

                if is_over(self.btn_general):
                    item["is_private"] = False
                    item["is_vhost"] = False
                    item["favorite"] = False
                elif is_over(self.btn_favorite):
                    item["favorite"] = True
                    item["is_private"] = False
                    item["is_vhost"] = False
                elif is_over(self.btn_privacy):
                    item["is_private"] = True
                    item["is_vhost"] = False
                elif is_over(self.btn_vhost):
                    item["is_vhost"] = True
                    item["is_private"] = False
                else:
                    # 原本的卡片間排序邏輯
                    target_idx = None
                    found = False
                    for i, w_card in enumerate(self.card_widgets):
                        try:
                            wx, wy = w_card.winfo_rootx(), w_card.winfo_rooty()
                            ww, wh = w_card.winfo_width(), w_card.winfo_height()
                            if wx <= x <= wx + ww and wy <= y <= wy + wh:
                                if hasattr(w_card, "real_index"):
                                    target_idx = w_card.real_index
                                    found = True
                                break
                        except: continue
                    
                    if found and target_idx != start_idx:
                        # 移動項目
                        self.games.pop(start_idx)
                        self.games.insert(target_idx, item)

                self.save_games()
                self.refresh_list()
                try:
                    new_idx = self.games.index(item)
                    self.on_game_select(new_idx)
                except: pass
                self.drag_data["dragging"] = False
            else:
                toggle_selection()

        # 綁定事件到所有可交互子元件
        for widget in [card, zh_label, en_label, img_container]:
            widget.bind("<Button-1>", on_drag_start)
            widget.bind("<B1-Motion>", on_drag_motion)
            widget.bind("<ButtonRelease-1>", on_drag_stop)
        
        # 最愛按鈕 (放在最上層，不參與拖曳)
        if game.get("favorite"):
            star_label = tk.Label(card, text="★", bg="gold", fg="#b8860b", font=("Arial", 16, "bold"))
            star_label.place(x=w-30, y=0, width=30, height=30)
            star_label.bind("<Button-1>", lambda e: self.on_game_select(index)) 
        
        # 右鍵選單綁定
        def on_right_click(event):
            self.show_context_menu(event, index)
            
        def on_double_click(event):
            self.launch_game(index)

        for widget in [card, zh_label, en_label, img_container]:
             widget.bind("<Button-3>", on_right_click)
             widget.bind("<Double-Button-1>", on_double_click)

    def show_context_menu(self, event, index):
        menu = tk.Menu(self.root, tearoff=0)
        game = self.games[index]
        is_private = game.get("is_private", False)
        
        # 隱私切換
        label = "🔓 移出隱私模式" if is_private else "🔒 加入隱私模式"
        menu.add_command(label=label, command=lambda: self.toggle_game_privacy(index))
        
        menu.add_separator()
        menu.add_command(label="✎ 編輯", command=lambda: self.edit_game(index))
        menu.add_command(label="- 移除", command=lambda: self.delete_game(index))
        # 執行
        menu.add_command(label="🚀 啟動", command=lambda: self.launch_game(index))
        
        menu.post(event.x_root, event.y_root)

    def toggle_game_privacy(self, index):
        if 0 <= index < len(self.games):
            self.games[index]["is_private"] = not self.games[index].get("is_private", False)
            self.save_games()
            self.refresh_list()

    def load_thumbnail_async(self, url, label_widget, target_w, target_h):
        cache_key = f"{url}_{target_w}x{target_h}"
        if cache_key in self.thumbnail_cache:
            def update_cached():
                if label_widget.winfo_exists():
                    label_widget.config(image=self.thumbnail_cache[cache_key], text="")
            self.root.after(0, update_cached)
            return
            
        local_path = self.get_local_image_path(url)
        
        try:
            pil_image = None
            if local_path and os.path.exists(local_path):
                try: pil_image = Image.open(local_path)
                except: pil_image = None
            
            if not pil_image:
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(url, headers=headers, timeout=5)
                image_data = BytesIO(response.content)
                pil_image = Image.open(image_data)
                if local_path:
                    try:
                        with open(local_path, "wb") as f: f.write(response.content)
                    except: pass
            
            img_ratio = pil_image.width / pil_image.height
            target_ratio = target_w / target_h
            if img_ratio > target_ratio:
                new_h, new_w = target_h, int(target_h * img_ratio)
            else:
                new_w, new_h = target_w, int(target_w / img_ratio)
                
            pil_image = pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS)
            left, top = (new_w - target_w) / 2, (new_h - target_h) / 2
            pil_image = pil_image.crop((left, top, left + target_w, top + target_h))
            
            photo = ImageTk.PhotoImage(pil_image)
            self.thumbnail_cache[cache_key] = photo
            
            def update_ui():
                if label_widget.winfo_exists():
                    label_widget.config(image=photo, text="")
            self.root.after(0, update_ui)
        except: pass

    def on_game_select(self, index):
        self.current_selected_index = index
        game = self.games[index]

        # 更新卡片邊框效果 (高反差)
        for i, card in enumerate(self.card_widgets):
            # 必須使用 card.real_index 來比對，因為 card_widgets 順序可能跟 self.games index 不同 (如隱私過濾後)
            if hasattr(card, "real_index") and card.real_index == index:
                card.config(highlightbackground="#ff6600") # 橙色高亮
            else:
                card.config(highlightbackground="#1e1e1e") # 恢復背景色

        zh_name = game.get("name_zh", game.get("name", "未命名"))
        en_name = game.get("name_en", "")

        self.title_label.config(text=zh_name)
        self.subtitle_label.config(text=en_name)

        # 先清空圖片，避免顯示上一個遊戲的圖片
        self.cover_label.config(image='', text='無封面圖片')

        desc = game.get("description", "無介紹")
        self.desc_text.config(state=tk.NORMAL)
        self.desc_text.delete(1.0, tk.END)
        self.desc_text.insert(tk.END, desc)
        self.desc_text.config(state=tk.DISABLED)

        steam_url = game.get("steam_url", "")
        if steam_url:
            self.steam_btn.config(state=tk.NORMAL, command=lambda: webbrowser.open(steam_url))
        else:
            self.steam_btn.config(state=tk.DISABLED)

        last_played = game.get("last_played", "")
        self.last_played_label.config(text=f"上次遊玩: {last_played if last_played else '尚未遊玩'}")
        self.launch_btn.config(state=tk.NORMAL)
        self.fav_btn.config(state=tk.NORMAL)

        if game.get("favorite"):
            self.fav_btn.config(text="❤ 已收藏")
        else:
            self.fav_btn.config(text="🤍 加入最愛")

        # 設定 Steam 按鈕
        steam_url = game.get("steam_url", "")
        if steam_url:
            self.steam_btn.config(state=tk.NORMAL, command=lambda: webbrowser.open(steam_url))
            self.update_info_btn.config(state=tk.NORMAL)
        else:
            self.steam_btn.config(state=tk.DISABLED)
            self.update_info_btn.config(state=tk.DISABLED)

        if game.get("image_url"):
            threading.Thread(target=self.load_big_image, args=(game["image_url"],), daemon=True).start()
        else:
            self.cover_label.config(image='', text="[無圖片]")

        # --- 影片顯示 ---
        video_url = game.get("video_url", "").strip()
        self._show_video_panel(video_url)

        # 清除舊的 Steam 資訊並開始更新
        for lbl in self.info_labels.values(): lbl.config(text="讀取中...")
        if steam_url:
            threading.Thread(target=self.update_steam_extra_info_async, args=(steam_url,), daemon=True).start()
        else:
            for lbl in self.info_labels.values(): lbl.config(text="--")

    def _get_embed_url(self, url):
        """將各種影片 URL 轉為可嵌入的 embed URL"""
        import re as _re
        if not url:
            return None
        # YouTube 標準格式
        yt = _re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})', url)
        if yt:
            vid = yt.group(1)
            return f"https://www.youtube.com/embed/{vid}?autoplay=1&mute=1&loop=1&playlist={vid}"
        # YouTube embed 格式（直接用）
        if 'youtube.com/embed/' in url:
            sep = '&' if '?' in url else '?'
            return url + sep + 'autoplay=1&mute=1'
        # Steam 影片 (mp4)
        if url.endswith('.mp4') or 'steamstatic.com' in url or 'steamcdn' in url:
            return url  # 用 <video> tag
        return url

    def _load_video_thumb(self, thumb_url):
        """背景載入影片縮圖（YouTube hqdefault）"""
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(thumb_url, headers=headers, timeout=5)
            from io import BytesIO as _BytesIO
            pil_img = Image.open(_BytesIO(response.content))
            # 縮放到合適寬度
            target_w = self.video_thumb_label.winfo_width() or 280
            ratio = target_w / pil_img.width
            new_h = int(pil_img.height * ratio)
            pil_img = pil_img.resize((target_w, new_h), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(pil_img)
            self._video_thumb_photo = photo  # 防止 GC
            self.root.after(0, lambda: self.video_thumb_label.config(
                image=photo, text="", compound=tk.TOP
            ))
        except:
            pass

    def _show_video_panel(self, video_url):
        """顯示或隱藏右側影片面板"""
        self.video_thumb_label.pack_forget()
        self.video_open_btn.pack_forget()

        if not video_url:
            self.video_frame_outer.pack_forget()
            return

        self.video_frame_outer.pack(fill=tk.X, padx=20, pady=(0, 5),
                                    before=self.steam_info_frame)

        # 顯示縮圖 + 播放按鈕
        self.video_thumb_label.config(image='', text="⏳ 載入影片縮圖中...")
        self.video_thumb_label.pack(fill=tk.X, ipady=5)
        self.video_open_btn.pack(fill=tk.X, ipady=6)
        self.video_open_btn.config(command=lambda u=video_url: webbrowser.open(u))
        self.video_thumb_label.bind("<Button-1>", lambda e, u=video_url: webbrowser.open(u))

        # 決定縮圖 URL
        thumb_url = None
        import re as _re

        # YouTube
        yt_m = _re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]{11})', video_url)
        if yt_m:
            thumb_url = f"https://img.youtube.com/vi/{yt_m.group(1)}/hqdefault.jpg"

        # Steam mp4 — 從 URL 提取 movie_id 構建縮圖
        if not thumb_url:
            steam_m = _re.search(r'store_trailers/(\d+)/movie', video_url)
            if steam_m:
                movie_id = steam_m.group(1)
                thumb_url = f"https://shared.akamai.steamstatic.com/store_item_assets/steam/apps/{movie_id}/movie.293x165.jpg"

        if thumb_url:
            threading.Thread(
                target=self._load_video_thumb, args=(thumb_url,), daemon=True
            ).start()
        else:
            self.video_thumb_label.config(image='', text="🎬 點擊下方按鈕播放影片")

    def toggle_favorite(self):
        if self.current_selected_index is None: return
        current_game = self.games[self.current_selected_index]
        current_game["favorite"] = not current_game.get("favorite", False)
        self.save_games()
        self.refresh_list()
        try:
            new_index = self.games.index(current_game)
            self.on_game_select(new_index)
        except ValueError:
            self.current_selected_index = None

    def load_big_image(self, url):
        local_path = self.get_local_image_path(url)
        try:
            pil_image = None
            if local_path and os.path.exists(local_path):
                try:
                    pil_image = Image.open(local_path)
                except:
                    pil_image = None
            
            if not pil_image:
                headers = {'User-Agent': 'Mozilla/5.0'}
                response = requests.get(url, headers=headers, timeout=5)
                pil_image = Image.open(BytesIO(response.content))
                
                if local_path:
                    try:
                        with open(local_path, "wb") as f:
                            f.write(response.content)
                    except:
                        pass

            base_width = 300
            w_percent = (base_width / float(pil_image.size[0]))
            h_size = int((float(pil_image.size[1]) * float(w_percent)))
            if h_size > 450:
                h_size = 450
                w_percent = (h_size / float(pil_image.size[1]))
                base_width = int((float(pil_image.size[0]) * float(w_percent)))

            pil_image = pil_image.resize((base_width, h_size), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(pil_image)
            
            self.root.after(0, lambda: self.cover_label.config(image=photo, text=""))
            self.image_cache['current_big'] = photo
        except:
            pass

    def launch_game(self, index=None):
        target_index = index if index is not None else self.current_selected_index
        if target_index is None: return
        game = self.games[target_index]
        exe_path = game["path"]
        
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        game["last_played"] = now_str
        self.save_games()
        
        self.last_played_label.config(text=f"上次遊玩: {now_str}", fg="#4caf50")
        
        if "最近" in self.sort_var.get():
            self.refresh_list()
            try:
                new_idx = self.games.index(game)
                self.on_game_select(new_idx)
            except: pass

        if not os.path.exists(exe_path):
            messagebox.showerror("錯誤", f"找不到執行檔：\n{exe_path}")
            return
        try:
            game_dir = os.path.dirname(exe_path)
            subprocess.Popen(f'"{exe_path}"', cwd=game_dir, shell=True)
        except Exception as e:
            messagebox.showerror("錯誤", f"無法啟動遊戲：\n{e}")

    def delete_game(self, index=None):
        target_index = index if index is not None else self.current_selected_index
        if target_index is None:
            messagebox.showwarning("提示", "請先點擊選擇一款遊戲")
            return
        game = self.games[target_index]
        name = game.get("name_zh", game.get("name"))
        if not messagebox.askyesno("確認", f"確定要移除 {name} 嗎？"):
            return
        
        # 刪除快取圖片
        image_url = game.get("image_url")
        if image_url:
            local_path = self.get_local_image_path(image_url)
            if local_path and os.path.exists(local_path):
                try:
                    os.remove(local_path)
                except:
                    pass
        
        del self.games[target_index]
        self.save_games()
        if self.current_selected_index == target_index:
            self.current_selected_index = None
        self.refresh_list()

    def on_exe_drop(self, event):
        """處理拖曳 EXE 檔案進入視窗，自動新增遊戲"""
        raw = event.data
        # tkinterdnd2 回傳的路徑可能被 {} 包圍（含空格時），也可能是空格分隔多個
        import re as _re
        paths = _re.findall(r'\{([^}]+)\}|([^\s]+)', raw)
        exe_paths = []
        for a, b in paths:
            p = (a or b).strip()
            if p.lower().endswith('.exe') and os.path.isfile(p):
                exe_paths.append(p)

        if not exe_paths:
            messagebox.showwarning("提示", "請拖曳 .exe 執行檔")
            return

        added = []
        for exe_path in exe_paths:
            # 檢查是否已存在
            if any(g.get('path', '').lower() == exe_path.lower() for g in self.games):
                continue

            # 從路徑取得名稱（去除常見後綴）
            base = os.path.splitext(os.path.basename(exe_path))[0]
            name = re.sub(r'[-_]?(Shipping|Win64|Win32|Release|x64|x86)', '', base, flags=re.IGNORECASE).strip('_- ')
            if not name:
                name = base

            new_game = {
                "name_zh": name,
                "name_en": name,
                "path": exe_path,
                "image_url": "",
                "steam_url": "",
                "description": "",
                "is_private": self.is_privacy_mode,
                "is_vhost": self.is_vhost_mode,
                "favorite": False,
                "last_played": ""
            }
            if self.is_privacy_mode:
                self.games.append(new_game)
            else:
                self.games.insert(0, new_game)
            added.append(name)

        if added:
            self.save_games()
            self.refresh_list()
            # 選中第一個新增的遊戲
            new_idx = next((i for i, g in enumerate(self.games) if g.get('path', '').lower() == exe_paths[0].lower()), None)
            if new_idx is not None:
                self.on_game_select(new_idx)
            names_str = '\n'.join(added)
            messagebox.showinfo("新增成功", f"已新增 {len(added)} 款遊戲：\n{names_str}\n\n💡 可以點選遊戲後使用「更新資料」從 Steam 補全資訊")
        else:
            messagebox.showinfo("提示", "所選遊戲已存在於清單中")

    def backup_database(self):
        if not os.path.exists(DATA_FILE):
            messagebox.showwarning("提示", "目前沒有資料庫可供備份")
            return
        try:
            import shutil
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"games_backup_{ts}.json"
            shutil.copy2(DATA_FILE, backup_name)
            messagebox.showinfo("成功", f"資料庫已備份至：\n{backup_name}")
        except Exception as e:
            messagebox.showerror("錯誤", f"備份失敗：\n{e}")

    def update_selected_game_info(self):
        if self.current_selected_index is None: return
        game = self.games[self.current_selected_index]
        
        # 取得兩個名稱欄位
        name_en = game.get("name_en", "").strip()
        name_zh = game.get("name_zh", game.get("name", "")).strip()
        
        # 禁用按鈕防止重複點擊
        self.update_info_btn.config(state=tk.DISABLED, text="更新中...")
        
        def run_update():
            try:
                info = None
                
                # 優先使用英文欄位搜尋（不論內容是英文還是中文）
                if name_en:
                    info = self.fetch_game_info_from_steam(name_en)
                
                # 如果第一次搜尋失敗且中文欄位不同，則用中文欄位再試
                if not info and name_zh and name_zh != name_en:
                    info = self.fetch_game_info_from_steam(name_zh)
                
                if info:
                    game["name_zh"] = info.get("name_zh", game.get("name_zh", ""))
                    game["name_en"] = info.get("name_en", game.get("name_en", ""))
                    game["image_url"] = info.get("image_url", game.get("image_url", ""))
                    game["description"] = info.get("description", game.get("description", ""))
                    if info["name_zh"]: game["name_zh"] = info["name_zh"]
                    if info["steam_url"]: game["steam_url"] = info["steam_url"]
                    if info.get("video_url"): game["video_url"] = info["video_url"]
                    self.save_games()
                    self.root.after(0, lambda: self.on_game_select(self.current_selected_index))
                    self.root.after(0, self.refresh_list)
                    self.root.after(0, lambda: messagebox.showinfo("成功", f"「{game['name_zh']}」資料已更新！"))
                else:
                    self.root.after(0, lambda: messagebox.showwarning("提示", "找不到對應的 Steam 資料。"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("錯誤", f"更新過程中發生錯誤：\n{e}"))
            finally:
                self.root.after(0, lambda: self.update_info_btn.config(state=tk.NORMAL, text="✨ 更新資料 (從 Steam)"))

        threading.Thread(target=run_update, daemon=True).start()

    def auto_update_game_info(self):
        msg = "是否重新掃描所有遊戲資料？\n\n注意：這將嘗試抓取 Steam 的「橫式封面」，\n並更新名稱與 Steam 連結。"
        ans = messagebox.askyesno("智能更新", msg)
        if not ans: return

        progress_win = tk.Toplevel(self.root)
        progress_win.title("更新中")
        progress_win.geometry("350x150")
        progress_win.configure(bg="#2d2d30")
        
        lbl = tk.Label(progress_win, text="準備中...", bg="#2d2d30", fg="white", pady=20)
        lbl.pack()
        pbar = ttk.Progressbar(progress_win, length=300, mode='determinate')
        pbar.pack()
        pbar["maximum"] = len(self.games)

        threading.Thread(target=self.run_full_update, args=(progress_win, lbl, pbar), daemon=True).start()

    def run_full_update(self, win, label, pbar):
        for i, game in enumerate(self.games):
            query = game.get("name_en") if game.get("name_en") else game.get("name_zh", game.get("name"))
            self.root.after(0, lambda n=query: label.config(text=f"搜尋: {n}"))
            try:
                info = self.fetch_game_info_from_steam(query)
                if info:
                    if info["image_url"]: game["image_url"] = info["image_url"]
                    if info["description"]: game["description"] = info["description"]
                    if info["name_zh"]: game["name_zh"] = info["name_zh"]
                    if info["steam_url"]: game["steam_url"] = info["steam_url"]
                    if info.get("video_url"): game["video_url"] = info["video_url"]
            except Exception as e: 
                print(e)
            
            self.root.after(0, lambda v=i+1: pbar.configure(value=v))
        
        self.save_games()
        self.root.after(0, self.refresh_list)
        self.root.after(0, win.destroy)
        self.root.after(0, lambda: messagebox.showinfo("完成", "更新完畢！"))

    def update_steam_extra_info_async(self, steam_url):
        try:
            cookies = {'birthtime': '0', 'lastagecheckage': '1-January-1990', 'Steam_Language': 'tchinese'}
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(steam_url, headers=headers, cookies=cookies, timeout=5)
            soup = BeautifulSoup(res.text, 'html.parser')
            
            # 抓取評論
            reviews = "未知"
            review_tag = soup.select_one('.user_reviews_summary_row .game_review_summary')
            if review_tag:
                reviews = review_tag.text.strip()
                count_tag = soup.select_one('.user_reviews_summary_row .responsive_review_type_selector')
                if count_tag:
                    count_text = count_tag.text.strip().replace("(", "").replace(")", "").replace(",", "")
                    reviews += f" ({count_text})"
            
            # 抓取發行日期
            date = "未知"
            date_tag = soup.select_one('.release_date .date')
            if date_tag: date = date_tag.text.strip()
            
            # 抓取開發人員
            devs = "未知"
            dev_tags = soup.select('#developers_list a')
            if dev_tags: devs = ", ".join([a.text.strip() for a in dev_tags])
            
            # 抓取發行商
            pubs = "未知"
            pub_divs = soup.select('.dev_row')
            for div in pub_divs:
                subtitle = div.find('div', class_='subtitle')
                if subtitle and '發行商' in subtitle.text:
                    pub_links = div.select('.summary.column a')
                    if pub_links:
                        pubs = ", ".join([a.text.strip() for a in pub_links])
                        break

            # 更新 UI
            self.root.after(0, lambda: self.info_labels["reviews"].config(text=reviews))
            self.root.after(0, lambda: self.info_labels["date"].config(text=date))
            self.root.after(0, lambda: self.info_labels["dev"].config(text=devs))
            self.root.after(0, lambda: self.info_labels["pub"].config(text=pubs))
            
        except Exception as e:
            print(f"Error updating steam extra info: {e}")
            self.root.after(0, lambda: [lbl.config(text="抓取失敗") for lbl in self.info_labels.values()])

    def open_privacy_manager(self):
        # 批量隱私管理視窗
        mgr_win = tk.Toplevel(self.root)
        mgr_win.title("批量隱私管理")
        mgr_win.geometry("600x700")
        mgr_win.configure(bg="#2d1b2e") # 深紫色背景
        mgr_win.attributes('-topmost', True)
        
        # 標題
        tk.Label(mgr_win, text="隱私模式遊戲管理", bg="#2d1b2e", fg="white", font=("微軟正黑體", 16, "bold")).pack(pady=10)
        tk.Label(mgr_win, text="勾選的遊戲將被設為隱私模式，僅在驗證密碼後顯示。", bg="#2d1b2e", fg="#aaa").pack(pady=(0, 10))
        
        # 列表容器
        list_frame = tk.Frame(mgr_win, bg="#2d1b2e")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        
        canvas = tk.Canvas(list_frame, bg="#000000", highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = tk.Frame(canvas, bg="#000000")
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 變數列表
        self.privacy_vars = []
        
        for i, game in enumerate(self.games):
            var = tk.BooleanVar(value=game.get("is_private", False))
            self.privacy_vars.append(var)
            
            # 項目 Frame
            item_frame = tk.Frame(scrollable_frame, bg="#000000", pady=2)
            item_frame.pack(fill=tk.X, anchor="w")
            
            chk = tk.Checkbutton(item_frame, text=game.get("name_zh", "未命名"), variable=var, 
                                 bg="#000000", fg="white", selectcolor="#2d1b2e", 
                                 activebackground="#1e1e1e", activeforeground="white",
                                 font=("微軟正黑體", 12, "bold"))
            chk.pack(side=tk.LEFT, padx=10)
            
            # 使用滑鼠滾輪
            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            
            item_frame.bind("<MouseWheel>", _on_mousewheel)
            chk.bind("<MouseWheel>", _on_mousewheel)

        canvas.bind_all("<MouseWheel>", lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))
        
        # 底部按鈕區
        btn_frame = tk.Frame(mgr_win, bg="#2d1b2e", pady=10)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        def save_privacy():
            changed = False
            for i, var in enumerate(self.privacy_vars):
                new_val = var.get()
                if self.games[i].get("is_private", False) != new_val:
                    self.games[i]["is_private"] = new_val
                    changed = True
            
            if changed:
                self.save_games()
                self.refresh_list()
                messagebox.showinfo("成功", "隱私設定已更新！", parent=mgr_win)
            mgr_win.destroy()
            
        def select_all():
            for var in self.privacy_vars: var.set(True)
            
        def select_none():
            for var in self.privacy_vars: var.set(False)

        btn_style = {"fg": "white", "relief": "flat", "width": 12, "font": ("微軟正黑體", 10, "bold")}
        
        tk.Button(btn_frame, text="全選", command=select_all, bg="#555", **btn_style).pack(side=tk.LEFT, padx=20)
        tk.Button(btn_frame, text="全不選", command=select_none, bg="#555", **btn_style).pack(side=tk.LEFT)
        tk.Button(btn_frame, text="儲存變更", command=save_privacy, bg="#00b894", **btn_style).pack(side=tk.RIGHT, padx=20)

    def fetch_game_info_from_steam(self, query_name):
        try:
            # 第一步：搜尋（使用繁體中文）
            search_url = f"https://store.steampowered.com/search/?term={query_name}&l=tchinese&cc=tw"
            cookies = {'birthtime': '0', 'lastagecheckage': '1-January-1990', 'Steam_Language': 'tchinese'}
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(search_url, headers=headers, cookies=cookies, timeout=5)
            soup = BeautifulSoup(res.text, 'html.parser')
            row = soup.find('a', class_='search_result_row')
            
            if not row: return None
            
            store_url = row.get('href', '')
            if not store_url: return None
            
            # 第二步：抓取中文商店頁面資訊
            res_store = requests.get(store_url, headers=headers, cookies=cookies, timeout=5)
            soup_store = BeautifulSoup(res_store.text, 'html.parser')
            
            # 優先抓取商店頁面的大圖
            img_url = ""
            img_tag = soup_store.select_one('.game_header_image_full')
            if img_tag:
                img_url = img_tag.get('src', '')
            
            # 如果沒抓到大圖，嘗試備選
            if not img_url:
                app_id_match = re.search(r'/app/(\d+)', store_url)
                if app_id_match:
                    app_id = app_id_match.group(1)
                    img_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg"
                else:
                    img_tag_res = row.find('img')
                    if img_tag_res: img_url = img_tag_res.get('src', '')
                    
            if not img_url or img_url.endswith('header.jpg'):
                # 如果還是抓不到，或者抓到的是可能 404 的舊版 CDN 網址，自動開啟 steamgriddb
                import urllib.parse
                safe_query = urllib.parse.quote(query_name)
                import webbrowser
                webbrowser.open(f"https://www.steamgriddb.com/search/grids?term={safe_query}")
            
            name_zh = query_name
            name_tag = soup_store.find('div', class_='apphub_AppName')
            if name_tag: name_zh = name_tag.text.strip()
            
            desc = "無介紹"
            desc_tag = soup_store.find('div', class_='game_description_snippet')
            if desc_tag: desc = desc_tag.text.strip()
            
            # 第三步：抓取英文名稱（使用英文語系再請求一次商店頁面）
            name_en = ""
            try:
                cookies_en = {'birthtime': '0', 'lastagecheckage': '1-January-1990', 'Steam_Language': 'english'}
                res_store_en = requests.get(store_url, headers=headers, cookies=cookies_en, timeout=5)
                soup_store_en = BeautifulSoup(res_store_en.text, 'html.parser')
                name_tag_en = soup_store_en.find('div', class_='apphub_AppName')
                if name_tag_en: name_en = name_tag_en.text.strip()
            except:
                pass
            
            # 如果抓不到英文名稱，或者英文名稱跟中文一樣，嘗試看看是否為純英文
            # (有些遊戲在中英文介面顯示名稱一樣，如果是純英文就填入英文欄位)
            if not name_en:
                if all(ord(c) < 128 for c in name_zh): # 簡單判斷是否為 ASCII
                    name_en = name_zh

            # 第四步：抓取遊戲預告片影片網址
            video_url = ""
            try:
                # 嘗試從 Steam API 取得影片 (mp4 直連)
                if app_id_match:
                    api_url = f"https://store.steampowered.com/api/appdetails?appids={app_id_match.group(1)}&l=tchinese"
                    api_res = requests.get(api_url, headers=headers, timeout=5)
                    api_data = api_res.json()
                    movies = api_data.get(app_id_match.group(1), {}).get("data", {}).get("movies", [])
                    if movies:
                        movie_id = movies[0].get("id", "")
                        if movie_id:
                            video_url = f"https://video.akamai.steamstatic.com/store_trailers/{movie_id}/movie_max.mp4"
            except:
                pass

            # 若 API 拿不到，嘗試從頁面抓 YouTube 連結
            if not video_url:
                try:
                    yt_tag = soup_store.find('a', href=lambda h: h and 'youtube.com' in h)
                    if yt_tag:
                        video_url = yt_tag['href']
                except:
                    pass

            return {
                "name_zh": name_zh,
                "name_en": name_en,
                "image_url": img_url,
                "description": desc,
                "steam_url": store_url,
                "video_url": video_url
            }
        except: return None

    def edit_game(self, index=None):
        target_index = index if index is not None else self.current_selected_index
        if target_index is None:
            messagebox.showwarning("提示", "請先點擊選擇一款遊戲")
            return
        AddGameWindow(self.root, self, game_data=self.games[target_index], index=target_index)

    def open_add_game_window(self):
        AddGameWindow(self.root, self)

    def open_bulk_import_window(self):
        BulkImportWindow(self.root, self)

    def open_library_manager(self):
        LibraryManagerWindow(self.root, self)

# --- 批量匯入視窗 ---
class BulkImportWindow:
    def __init__(self, parent, app):
        self.top = tk.Toplevel(parent)
        self.app = app
        self.found = []
        self.top.title("批量掃描")
        self.top.geometry("600x600")
        self.top.configure(bg="#2d2d30")
        
        frame = tk.Frame(self.top, bg="#2d2d30")
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(frame, text="請選擇資料夾進行掃描 (例如 D:\\Games)", bg="#2d2d30", fg="white").pack(anchor="w")
        tk.Button(frame, text="📁 選擇資料夾開始掃描", command=self.start_scan_thread, bg="#007acc", fg="white", font=("微軟正黑體", 10)).pack(fill=tk.X, pady=5)
        
        self.status_lbl = tk.Label(frame, text="準備就緒", bg="#2d2d30", fg="#aaa")
        self.status_lbl.pack(anchor="w")

        # 使用 Treeview 替代 Listbox
        self.tree = ttk.Treeview(frame, columns=("path"), selectmode="extended")
        self.tree.heading("#0", text="名稱 (資料夾 / 檔案)")
        self.tree.heading("path", text="完整路徑")
        self.tree.column("path", width=300)
        
        # 捲軸
        vsb = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.tree.pack(fill=tk.BOTH, expand=True, pady=5)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # 設定樣式標籤 (高對比色彩)
        self.tree.tag_configure("main_folder", foreground="#f1c40f", font=("微軟正黑體", 10, "bold"))
        self.tree.tag_configure("folder", foreground="#ecf0f1")
        self.tree.tag_configure("file", foreground="#bdc3c7")
        
        # 用於存儲路徑節點的字典
        self.nodes = {}
        # 用於存儲 exe 資料的字典 (以 tree id 為索引)
        self.exe_data = {}
        # 儲存勾選狀態
        self.checked_ids = set()
        
        self.tree.bind("<Button-1>", self.on_click)
        
        tk.Button(frame, text="✅ 匯入勾選項目", command=self.imp, bg="#28a745", fg="white", font=("微軟正黑體", 11)).pack(fill=tk.X, pady=5)

    def on_click(self, event):
        item_id = self.tree.identify_row(event.y)
        if not item_id: return
        
        # 取得點擊所在的列
        column = self.tree.identify_column(event.x)
        
        # 如果點擊的是第一欄 (樹狀欄位) 或是整列，切換勾選狀態
        # 為了使用者方便，點擊整列都切換勾選
        self.toggle_check(item_id)

    def toggle_check(self, item_id):
        if item_id in self.checked_ids:
            self.set_check_state(item_id, False)
        else:
            self.set_check_state(item_id, True)

    def set_check_state(self, item_id, state):
        if state:
            self.checked_ids.add(item_id)
        else:
            self.checked_ids.discard(item_id)
            
        # 更新顯示
        self.update_item_text(item_id)
        
        # 遞迴處理子項目 (資料夾連動)
        for child in self.tree.get_children(item_id):
            self.set_check_state(child, state)

    def update_item_text(self, item_id):
        current_text = self.tree.item(item_id, "text")
        # 移除舊的勾選號
        clean_text = re.sub(r'^[☐☑] ', '', current_text)
        
        prefix = "☑ " if item_id in self.checked_ids else "☐ "
        self.tree.item(item_id, text=prefix + clean_text)

    def start_scan_thread(self):
        d = filedialog.askdirectory()
        if not d: return
        self.status_lbl.config(text=f"掃描中: {d} ... (請稍候)")
        
        # 清空
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.nodes = {}
        self.exe_data = {}
        self.checked_ids = set()
        self.found = []
        
        threading.Thread(target=self.scan_logic, args=(d,), daemon=True).start()

    def scan_logic(self, directory):
        ignore = [
            "uninstall", "unins", "uninst", "setup", "install", 
            "unitycrashhandler", "crashpad", "errorreport", "dxwebsetup", "vcredist",
            "redist", "vc_redist", "helper", "webhelper", "launcher", "config",
            "setting", "tool", "fixer", "updater", "patcher", "socialclub",
            "easyanticheat", "eac", "battle-eye", "overlay"
        ]
        count = 0
        try:
            for root, dirs, files in os.walk(directory):
                for f in files:
                    if f.lower().endswith(".exe"):
                        if any(x in f.lower() for x in ignore): continue
                        
                        full_path = os.path.join(root, f)
                        # 在 GUI 排隊處理內容插入
                        self.top.after(0, self.add_to_tree, directory, root, f, full_path)
                        count += 1
        except Exception as e:
            print(f"Scan error: {e}")
            
        self.top.after(0, lambda: self.finish_scan(count))

    def finish_scan(self, count):
        self.status_lbl.config(text=f"掃描完成，找到 {count} 個項目。")
        self.adjust_window_size()

    def adjust_window_size(self):
        # 統計 Treeview 中的總項目數
        total_items = len(self.tree.get_children(""))
        for item in self.tree.get_children(""):
            total_items += len(self.tree.get_children(item))
            
        # 計算預期高度: 標題(120) + 列表內容 + 按鈕/狀態欄(80)
        # 每行約 25px
        item_h = total_items * 25
        h = 200 + item_h
        
        # 限制範圍
        screen_h = self.top.winfo_screenheight()
        max_h = int(screen_h * 0.8)
        final_h = min(max(400, h), max_h)
        final_w = 750 # 加寬一點顯示路徑
        
        self.top.geometry(f"{final_w}x{final_h}")
        self.top.update_idletasks()

    def add_to_tree(self, base_dir, root_path, filename, full_path):
        # 構建資料夾樹
        rel_path = os.path.relpath(root_path, base_dir)
        parts = [] if rel_path == "." else rel_path.split(os.sep)
        
        parent = ""
        current_path = base_dir
        
        for part in parts:
            prev_parent = parent
            current_path = os.path.join(current_path, part)
            if current_path not in self.nodes:
                # 如果是第一層 (prev_parent 為空)，套用 main_folder 標籤
                tag = "main_folder" if prev_parent == "" else "folder"
                self.nodes[current_path] = self.tree.insert(prev_parent, "end", text=f"☐ 📁 {part}", open=True, tags=(tag,))
            parent = self.nodes[current_path]
            
        # 插入檔案
        # 決定中文名稱 (邏輯同之前)
        folder_name = os.path.basename(root_path)
        if folder_name.lower() in ["bin", "bin64", "release", "system"]:
            game_name = os.path.basename(os.path.dirname(root_path))
        else:
            game_name = folder_name
            
        en_name = os.path.splitext(filename)[0]
        en_name = re.sub(r'[-_]?(Shipping|Win64|Release)', '', en_name, flags=re.IGNORECASE)
        
        item_id = self.tree.insert(parent, "end", text=f"☐ 🎮 {filename}", values=(full_path,))
        self.exe_data[item_id] = {
            "name_zh": game_name,
            "name_en": en_name,
            "path": full_path
        }

        # 智慧判定：如果是 Shipping.exe 或檔名與資料夾名稱相近，自動勾選
        is_primary = False
        if "shipping" in filename.lower():
            is_primary = True
        elif filename.lower().startswith(game_name.lower()):
            is_primary = True
        elif game_name.lower() in filename.lower():
            is_primary = True
            
        if is_primary:
            self.set_check_state(item_id, True)

    def imp(self):
        if not self.checked_ids:
            messagebox.showwarning("提示", "請先勾選要匯入的遊戲檔案")
            return
            
        added = 0
        for item_id in self.checked_ids:
            if item_id not in self.exe_data: continue # 跳過資料夾
            
            g = self.exe_data[item_id]
            if not any(x["path"] == g["path"] for x in self.app.games):
                self.app.games.append({
                    "name_zh": g["name_zh"], 
                    "name_en": g["name_en"],
                    "path": g["path"], 
                    "image_url": "", 
                    "steam_url": "",
                    "description": "批量匯入",
                    "is_private": self.app.is_privacy_mode,
                    "is_vhost": self.app.is_vhost_mode,
                    "favorite": False,
                    "last_played": ""
                })
                added += 1
        self.app.save_games()
        self.app.refresh_list()
        messagebox.showinfo("完成", f"已匯入 {added} 個遊戲。")
        self.top.destroy()

# --- 新增/編輯視窗 ---
class AddGameWindow:
    def __init__(self, parent, app, game_data=None, index=None):
        self.top = tk.Toplevel(parent)
        self.app = app
        self.edit_data = game_data
        self.edit_index = index
        self.top.title("編輯遊戲資料" if game_data else "新增遊戲")
        self.top.geometry("1200x650") 
        self.top.configure(bg="#2d2d30")
        self.top.attributes('-topmost', True)
        self.top.focus_force()

        self.path_var = tk.StringVar(value=game_data["path"] if game_data else "")
        nm_zh = game_data.get("name_zh", game_data.get("name", "")) if game_data else ""
        nm_en = game_data.get("name_en", "") if game_data else ""

        self.name_zh_var = tk.StringVar(value=nm_zh)
        self.name_en_var = tk.StringVar(value=nm_en)
        self.url_var = tk.StringVar(value=game_data.get("image_url", "") if game_data else "")
        self.steam_url_var = tk.StringVar(value=game_data.get("steam_url", "") if game_data else "")
        self.video_url_var = tk.StringVar(value=game_data.get("video_url", "") if game_data else "")
        self.is_private_var = tk.BooleanVar(value=game_data.get("is_private", False) if game_data else False)
        self.is_vhost_var = tk.BooleanVar(value=game_data.get("is_vhost", False) if game_data else False)
        self.sgdb_search_var = tk.StringVar(value=nm_en if nm_en else nm_zh)

        self.preview_img = None
        self.create_ui()
        self.url_var.trace_add("write", lambda *args: self.update_preview_async())
        
        if game_data and "description" in game_data:
            self.desc_entry.insert(tk.END, game_data["description"])
        if self.url_var.get():
            self.update_preview_async()

    def create_ui(self):
        bg, fg = "#2d2d30", "white"
        p = {'padx': 15, 'pady': 5}
        
        # 強制對稱容器
        main_container = tk.Frame(self.top, bg=bg)
        main_container.pack(fill=tk.BOTH, expand=True, padx=30, pady=15)
        # 使用 uniform="group1" 強制兩欄絕對相等
        main_container.columnconfigure(0, weight=1, uniform="group1")
        main_container.columnconfigure(1, weight=1, uniform="group1")
        
        left_col = tk.Frame(main_container, bg=bg)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        
        right_col = tk.Frame(main_container, bg=bg)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(20, 0))

        # --- 左側：文件資料 ---
        tk.Label(left_col, text="📂 執行檔路徑:", bg=bg, fg="#aaaaaa").pack(anchor="w", padx=15, pady=(5,0))
        f_path = tk.Frame(left_col, bg=bg); f_path.pack(fill=tk.X, **p)
        tk.Entry(f_path, textvariable=self.path_var, bg="#3e3e42", fg="white", relief="flat", width=40).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        tk.Button(f_path, text="瀏覽", command=self.browse, bg="#555", fg="white", width=6).pack(side=tk.RIGHT, padx=(5,0))
        
        tk.Label(left_col, text="📝 英文名稱 (搜尋關鍵字):", bg=bg, fg="#aaaaaa").pack(anchor="w", padx=15)
        f_en = tk.Frame(left_col, bg=bg); f_en.pack(fill=tk.X, **p)
        tk.Entry(f_en, textvariable=self.name_en_var, bg="#3e3e42", fg="white", relief="flat", width=40).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self.search_btn = tk.Button(f_en, text="🔍 搜尋資料", command=self.fetch_by_name, bg="#00b894", fg="white", relief="flat", padx=10)
        self.search_btn.pack(side=tk.RIGHT, padx=(5,0))

        tk.Label(left_col, text="🏷️ 中文名稱 (啟動器顯示):", bg=bg, fg="#aaaaaa").pack(anchor="w", padx=15)
        tk.Entry(left_col, textvariable=self.name_zh_var, bg="#3e3e42", fg="white", relief="flat", width=40).pack(fill=tk.X, **p, ipady=4)
        
        tk.Label(left_col, text="🔗 Steam 商店網址:", bg=bg, fg="#aaaaaa").pack(anchor="w", padx=15)
        f_steam = tk.Frame(left_col, bg=bg); f_steam.pack(fill=tk.X, **p)
        self.steam_entry = tk.Entry(f_steam, textvariable=self.steam_url_var, bg="#3e3e42", fg="white", relief="flat", width=40)
        self.steam_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        self.fetch_btn = tk.Button(f_steam, text="自動抓取", command=self.fetch_from_steam_url, bg="#6c5ce7", fg="white", relief="flat", padx=10)
        self.fetch_btn.pack(side=tk.RIGHT, padx=(5,0))

        tk.Label(left_col, text="🌐 SteamGridDB 備用搜尋:", bg=bg, fg="#aaaaaa").pack(anchor="w", padx=15)
        f_sgdb = tk.Frame(left_col, bg=bg); f_sgdb.pack(fill=tk.X, **p)
        tk.Entry(f_sgdb, textvariable=self.sgdb_search_var, bg="#3e3e42", fg="white", relief="flat", width=40).pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4)
        tk.Button(f_sgdb, text="🔍 搜尋網頁", command=self.open_sgdb, bg="#2980b9", fg="white", relief="flat", padx=10).pack(side=tk.RIGHT, padx=(5,0))

        tk.Label(left_col, text="🎬 遊戲影片網址:", bg=bg, fg="#aaaaaa").pack(anchor="w", padx=15)
        tk.Entry(left_col, textvariable=self.video_url_var, bg="#3e3e42", fg="white", relief="flat", width=40).pack(fill=tk.X, **p, ipady=4)

        # --- 右側：封面媒體 ---
        tk.Label(right_col, text="🖼️ 封面圖網址 (建議 460x215):", bg=bg, fg="#aaaaaa").pack(anchor="w", padx=15)
        tk.Entry(right_col, textvariable=self.url_var, bg="#3e3e42", fg="white", relief="flat", width=40).pack(fill=tk.X, **p, ipady=4)

        self.preview_label = tk.Label(right_col, bg="#1e1e1e", pady=5)
        self.preview_label.pack(fill=tk.X, padx=15, pady=5)

        tk.Label(right_col, text="📖 遊戲介紹:", bg=bg, fg="#aaaaaa").pack(anchor="w", padx=15)
        self.desc_entry = tk.Text(right_col, height=4, bg="#3e3e42", fg="white", relief="flat", font=("微軟正黑體", 10))
        self.desc_entry.pack(fill=tk.X, **p)

        opt_frame = tk.Frame(right_col, bg=bg)
        opt_frame.pack(fill=tk.X, padx=15, pady=2)
        tk.Checkbutton(opt_frame, text="🔒 隱私模式", variable=self.is_private_var, 
                       bg=bg, fg="#ff5252", selectcolor="#3e3e42", activebackground=bg, activeforeground="#ff5252").pack(side=tk.LEFT)
        tk.Checkbutton(opt_frame, text="🖥️ 虛擬主機", variable=self.is_vhost_var, 
                       bg=bg, fg="#ff7675", selectcolor="#3e3e42", activebackground=bg, activeforeground="#ff7675").pack(side=tk.LEFT, padx=(20, 0))
        
        tk.Button(right_col, text="💾 儲存並關閉", command=self.save, bg="#007acc", fg="white", font=("微軟正黑體", 12, "bold"), relief="flat", height=2).pack(fill=tk.X, padx=15, pady=(8, 0))

    def browse(self):
        initial_dir = "/"
        current_path = self.path_var.get().strip()
        if current_path and os.path.exists(os.path.dirname(current_path)):
            initial_dir = os.path.dirname(current_path)
            
        f = filedialog.askopenfilename(initialdir=initial_dir, filetypes=[("Exe", "*.exe"), ("All Files", "*.*")])
        if f: 
            self.path_var.set(f)
            if not self.name_en_var.get(): 
                base = os.path.splitext(os.path.basename(f))[0]
                en_name = re.sub(r'[-_]?(Shipping|Win64|Release)', '', base, flags=re.IGNORECASE)
                self.name_en_var.set(en_name)
                self.sgdb_search_var.set(en_name)

    def open_sgdb(self):
        query = self.sgdb_search_var.get().strip()
        if not query:
            query = self.name_en_var.get().strip()
        if not query:
            query = self.name_zh_var.get().strip()
            
        if query:
            import urllib.parse
            safe_query = urllib.parse.quote(query)
            import webbrowser
            webbrowser.open(f"https://www.steamgriddb.com/search/grids?term={safe_query}")
        else:
            messagebox.showwarning("提示", "請先輸入遊戲名稱再進行搜尋")

    def update_preview_async(self):
        url = self.url_var.get().strip()
        if not url:
            self.preview_label.config(image="", text="無網址", bg="#1e1e1e")
            return
        threading.Thread(target=self._load_preview, args=(url,), daemon=True).start()

    def _load_preview(self, url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(url, headers=headers, timeout=5)
            from io import BytesIO
            img_data = BytesIO(res.content)
            img = Image.open(img_data)
            
            # 縮放到大尺寸 (460x215)
            img.thumbnail((460, 215))
            
            from PIL import ImageTk
            photo = ImageTk.PhotoImage(img)
            
            def set_img():
                if self.top.winfo_exists():
                    self.preview_img = photo # 保持引用防止回收
                    self.preview_label.config(image=photo, text="", bg="#2d2d30")
            
            self.top.after(0, set_img)
        except:
            def set_error():
                if self.top.winfo_exists():
                    self.preview_label.config(image="", text="圖片載入失敗", bg="#1e1e1e")
            self.top.after(0, set_error)

    def fetch_from_steam_url(self):
        url = self.steam_url_var.get().strip()
        if "store.steampowered.com/app/" not in url:
            messagebox.showwarning("提示", "請輸入有效的 Steam 商店網址")
            return
        threading.Thread(target=self.run_fetch_url, args=(url,), daemon=True).start()

    def fetch_by_name(self):
        threading.Thread(target=self.run_fetch_by_name, daemon=True).start()

    def extract_folder_name_from_path(self, path):
        if not path: return None
        try:
            path = os.path.normpath(path)
            parts = path.split(os.sep)
            exe_index = len(parts) - 1
            if exe_index >= 1:
                folder_1 = parts[exe_index - 1]
                if folder_1.lower() in ['game', 'games'] and exe_index >= 2:
                    return parts[exe_index - 2]
                else:
                    return folder_1
        except: pass
        return None

    def run_fetch_by_name(self):
        self.top.after(0, lambda: self.search_btn.config(text="搜尋中...", state=tk.DISABLED, bg="#555", fg="#aaaaaa"))
        try:
            info = None
            name_en = self.name_en_var.get().strip()
            name_zh = self.name_zh_var.get().strip()
            
            if name_en and name_en.lower() not in ['game', 'games']:
                info = self.app.fetch_game_info_from_steam(name_en)
            if not info and name_zh and name_zh != name_en and name_zh.lower() not in ['game', 'games']:
                info = self.app.fetch_game_info_from_steam(name_zh)
            if not info:
                folder_name = self.extract_folder_name_from_path(self.path_var.get())
                if folder_name: info = self.app.fetch_game_info_from_steam(folder_name)
            
            if info:
                def on_success():
                    winsound.MessageBeep(winsound.MB_OK)
                    self.apply_fetch_results(info)
                    # 高對比度成功色與延長至 3 秒
                    self.search_btn.config(text="✅ 搜尋成功", bg="#2ecc71", fg="white")
                    self.top.after(3000, lambda: self.search_btn.config(text="🔍 搜尋資料", bg="#00b894", fg="white"))
                self.top.after(0, on_success)
            else:
                def on_fail():
                    winsound.MessageBeep(winsound.MB_ICONHAND)
                    messagebox.showerror("❌ 搜尋失敗", "Steam 搜尋不到該遊戲！", parent=self.top)
                self.top.after(0, on_fail)
        except Exception as e:
            self.top.after(0, lambda: messagebox.showerror("❌ 發生錯誤", f"搜尋過程中發生錯誤:\n{e}", parent=self.top))
        finally:
            self.top.after(0, lambda: self.search_btn.config(state=tk.NORMAL))

    def apply_fetch_results(self, info):
        if info.get("name_zh"): self.name_zh_var.set(info["name_zh"])
        if info.get("name_en"): self.name_en_var.set(info["name_en"])
        if info.get("image_url"): self.url_var.set(info["image_url"])
        if info.get("steam_url"): self.steam_url_var.set(info["steam_url"])
        if info.get("video_url"): self.video_url_var.set(info["video_url"])
        if info.get("description"):
            self.desc_entry.delete(1.0, tk.END)
            self.desc_entry.insert(tk.END, info["description"])
        # 同步更新備用搜尋框
        self.sgdb_search_var.set(info.get("name_zh") or info.get("name_en", ""))

    def run_fetch_url(self, url):
        self.top.after(0, lambda: self.fetch_btn.config(text="搜尋中...", state=tk.DISABLED, bg="#555", fg="#aaaaaa"))
        try:
            cookies = {'birthtime': '0', 'lastagecheckage': '1-January-1990', 'Steam_Language': 'tchinese'}
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(url, headers=headers, cookies=cookies, timeout=5)
            soup = BeautifulSoup(res.text, 'html.parser')

            name = ""
            name_tag = soup.find('div', class_='apphub_AppName')
            if name_tag: name = name_tag.text.strip()

            desc = ""
            desc_tag = soup.find('div', class_='game_description_snippet')
            if desc_tag: desc = desc_tag.text.strip()

            img_url = ""
            img_tag = soup.select_one('.game_header_image_full')
            if img_tag: img_url = img_tag.get('src', '')

            app_id_match = re.search(r'/app/(\d+)', url)
            video_url = ""
            if app_id_match:
                app_id = app_id_match.group(1)
                if not img_url: img_url = f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg"
                try:
                    api_res = requests.get(f"https://store.steampowered.com/api/appdetails?appids={app_id}&l=tchinese", timeout=5)
                    api_data = api_res.json()
                    movies = api_data.get(app_id, {}).get("data", {}).get("movies", [])
                    if movies:
                        movie_id = movies[0].get("id", "")
                        if movie_id: video_url = f"https://video.akamai.steamstatic.com/store_trailers/{movie_id}/movie_max.mp4"
                except: pass

            if not img_url or img_url.endswith('header.jpg'):
                import urllib.parse
                safe_query = urllib.parse.quote(name if name else "遊戲")
                import webbrowser
                webbrowser.open(f"https://www.steamgriddb.com/search/grids?term={safe_query}")

            self.top.after(0, lambda: self.fill_fetched_data(name, desc))
            if video_url: self.top.after(0, lambda: self.video_url_var.set(video_url))
            if img_url: self.top.after(0, lambda: self.url_var.set(img_url))
            
            # 高對比度成功色與延長至 3 秒
            def fetch_success():
                self.fetch_btn.config(text="✅ 抓取成功", bg="#2ecc71", fg="white", state=tk.NORMAL)
                self.top.after(3000, lambda: self.fetch_btn.config(text="自動抓取", bg="#6c5ce7", fg="white"))
            self.top.after(0, fetch_success)

        except Exception as e:
            self.top.after(0, lambda: messagebox.showerror("錯誤", f"抓取失敗: {e}", parent=self.top))
        finally:
            self.top.after(0, lambda: self.fetch_btn.config(state=tk.NORMAL))




    def fill_fetched_data(self, name, desc):
        if name: 
            self.name_zh_var.set(name)
            self.sgdb_search_var.set(name)
        if desc:
            self.desc_entry.delete(1.0, tk.END)
            self.desc_entry.insert(tk.END, desc)

    def save(self):
        new = {
            "name_zh": self.name_zh_var.get(),
            "name_en": self.name_en_var.get(),
            "path": self.path_var.get(),
            "image_url": self.url_var.get(),
            "steam_url": self.steam_url_var.get(),
            "video_url": self.video_url_var.get(),
            "description": self.desc_entry.get(1.0, tk.END).strip(),
            "is_private": self.is_private_var.get(),
            "is_vhost": self.is_vhost_var.get(),
            "favorite": self.edit_data.get("favorite", False) if self.edit_data else False,
            "last_played": self.edit_data.get("last_played", "") if self.edit_data else ""
        }
        if self.edit_index is not None: self.app.games[self.edit_index] = new
        else: self.app.games.append(new)
        self.app.save_games()
        self.app.refresh_list()
        self.top.destroy()

# --- 遊戲庫管理視窗 ---
class LibraryManagerWindow:
    def __init__(self, parent, app):
        self.top = tk.Toplevel(parent)
        self.app = app
        self.top.title("🛠️ 遊戲庫管理與檢查")
        self.top.geometry("900x600")
        self.top.configure(bg="#121212")
        self.top.attributes('-topmost', True)
        self.top.focus_force()
        
        # 標題與說明
        header_frame = tk.Frame(self.top, bg="#1e1e1e", pady=20)
        header_frame.pack(fill=tk.X)
        tk.Label(header_frame, text="遊戲路徑有效性檢查", bg="#1e1e1e", fg="white", font=("微軟正黑體", 16, "bold")).pack()
        tk.Label(header_frame, text="掃描所有遊戲執行檔路徑，找出標記為紅色（檔案已不存在）的項目並清理。", bg="#1e1e1e", fg="#888").pack()

        # 表格區域
        table_frame = tk.Frame(self.top, bg="#121212")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        columns = ("status", "path")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="extended")
        
        self.tree.heading("status", text="狀態")
        self.tree.heading("path", text="完整檔案路徑")
        
        self.tree.column("status", width=120, anchor="center")
        self.tree.column("path", width=650)

        # 捲軸
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # 標籤樣式
        self.tree.tag_configure("missing", foreground="#ff4757")
        self.tree.tag_configure("ok", foreground="#2ed573")

        # 底部按鈕
        btn_frame = tk.Frame(self.top, bg="#1e1e1e", pady=15)
        btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Button(btn_frame, text="🔄 重新掃描", command=self.scan, bg="#2f3542", fg="white", 
                  relief="flat", padx=20, pady=5, font=("微軟正黑體", 10)).pack(side=tk.LEFT, padx=20)
        
        self.clean_btn = tk.Button(btn_frame, text="🗑️ 移除所有失效連結", command=self.remove_invalid, 
                                   bg="#ff4757", fg="white", relief="flat", padx=25, pady=5, 
                                   font=("微軟正黑體", 11, "bold"))
        self.clean_btn.pack(side=tk.RIGHT, padx=20)

        self.missing_indices = []
        self.scan()

    def scan(self):
        # 清空舊資料
        for i in self.tree.get_children():
            self.tree.delete(i)
        
        self.missing_indices = []
        
        # 開始檢查
        for i, game in enumerate(self.app.games):
            path = game.get("path", "")
            exists = os.path.exists(path)
            
            name = game.get("name_zh", game.get("name", "未命名"))
            status_text = "🔴 已失效" if not exists else "🟢 正常"
            tag = "missing" if not exists else "ok"
            
            item_id = self.tree.insert("", "end", values=(status_text, path), tags=(tag,))
            # 由於 Treeview 只能存 values，我們要在 Treeview 中額外處理名稱
            # 這裡我們把名稱跟狀態放一起或是修改欄位
            self.tree.item(item_id, text=name) # 如果 show="tree headings"
            
            if not exists:
                self.missing_indices.append(i)
        
        # 若需要顯示名稱，調整 Treeview
        self.tree.config(show="tree headings")
        self.tree.heading("#0", text="遊戲名稱")
        self.tree.column("#0", width=180)

        # 更新清理按鈕狀態
        if not self.missing_indices:
            self.clean_btn.config(state=tk.DISABLED, bg="#57606f")
        else:
            self.clean_btn.config(state=tk.NORMAL, bg="#ff4757")

    def remove_invalid(self):
        if not self.missing_indices:
            return
            
        count = len(self.missing_indices)
        msg = f"確定要從清單中移除這 {count} 個失效的遊戲連結嗎？\n\n這不會刪除您的硬碟檔案，僅會從啟動器清單中移除。"
        if not messagebox.askyesno("清理確認", msg, parent=self.top):
            return
            
        # 從後往前刪除，索引才不會跑掉
        for i in sorted(self.missing_indices, reverse=True):
            # 刪除對應的快取圖片（選擇性）
            game = self.app.games[i]
            if game.get("image_url"):
                cache_path = self.app.get_local_image_path(game["image_url"])
                if cache_path and os.path.exists(cache_path):
                    try: os.remove(cache_path)
                    except: pass
            
            del self.app.games[i]
            
        self.app.save_games()
        self.app.refresh_list()
        messagebox.showinfo("完成", f"已成功移除 {count} 個失效連結！", parent=self.top)
        self.scan()

if __name__ == "__main__":
    if HAS_DND:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
    app = GameLauncherApp(root)
    root.mainloop()