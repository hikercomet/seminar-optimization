import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
from typing import Dict, List, Any, Optional, Callable, Tuple
import ctypes
import tkinter.font
import os
from datetime import datetime
import configparser

# ---- 設定管理 ----

class ConfigManager:
    """設定をINIファイルで管理するクラスです。"""
    def __init__(self, config_file: str = "gui_settings.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load_config()

    def load_config(self):
        """設定ファイルを読み込みます。"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file, encoding='utf-8')

    def save_config(self, settings: Dict[str, Any]):
        """設定をファイルに保存します。"""
        if 'GUI' not in self.config:
            self.config.add_section('GUI')
        for key, value in settings.items():
            # dictやlistはJSONとして保存します
            self.config['GUI'][key] = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            self.config.write(f)

    def get_setting(self, key: str, default: Any = None) -> Any:
        """指定されたキーの設定値を取得します。"""
        try:
            val = self.config['GUI'][key]
            # JSON形式の文字列の場合はパースします
            if val.strip().startswith('{') or val.strip().startswith('['):
                return json.loads(val)
            return val
        except:
            return default

# ---- 入力バリデーションヘルパー ----

class InputValidator:
    """GUI入力のバリデーションを行うヘルパークラスです。"""
    @staticmethod
    def validate_positive_int(value_str: str, field_name: str) -> Tuple[bool, str]:
        """正の整数であることを検証します。"""
        try:
            value = int(value_str)
            if value <= 0:
                return False, f"{field_name}は正の整数である必要があります。"
            return True, ""
        except ValueError:
            return False, f"{field_name}は有効な整数である必要があります。"

    @staticmethod
    def validate_positive_float(value_str: str, field_name: str) -> Tuple[bool, str]:
        """正の浮動小数点数であることを検証します。"""
        try:
            value = float(value_str)
            if value <= 0:
                return False, f"{field_name}は正の数値である必要があります。"
            return True, ""
        except ValueError:
            return False, f"{field_name}は有効な数値である必要があります。"

    @staticmethod
    def validate_range_float(value_str: str, field_name: str, min_val: float, max_val: float) -> Tuple[bool, str]:
        """指定された範囲内の浮動小数点数であることを検証します。"""
        try:
            value = float(value_str)
            if not (min_val < value < max_val): # 厳密にmin_valとmax_valを含まないようにします
                return False, f"{field_name}は{min_val}より大きく{max_val}未満である必要があります。"
            return True, ""
        except ValueError:
            return False, f"{field_name}は有効な数値である必要があります。"

    @staticmethod
    def validate_json_dict(value_str: str, field_name: str) -> Tuple[bool, str]:
        """有効なJSON辞書形式であることを検証します。"""
        try:
            data = json.loads(value_str)
            if not isinstance(data, dict):
                return False, f"{field_name}は有効なJSON辞書形式である必要があります。"
            for k, v in data.items():
                if not isinstance(k, str) or not isinstance(v, (int, float)) or v < 0:
                    return False, f"{field_name}のキーは文字列、値は0以上の数値である必要があります。"
            return True, ""
        except json.JSONDecodeError:
            return False, f"{field_name}は有効なJSON形式 (例: {{\"a\": 2.0, \"d\": 3.0}}) である必要があります。"

# ---- カスタム入力フレーム ----

class CustomEntryFrame(ttk.Frame):
    """ラベル、エントリー、ツールチップを含むカスタム入力ウィジェットです。"""
    def __init__(self, parent, label_text: str, default_value: str, width: int, tooltip: str = "", validator: Optional[Callable[[str, str], Tuple[bool, str]]] = None):
        super().__init__(parent, padding=(5, 2))
        self.label_text = label_text
        self.validator = validator
        self.entry_var = tk.StringVar(value=default_value)

        # ラベル
        ttk.Label(self, text=label_text, style='TLabel').pack(anchor='w')
        
        # エントリー
        self.entry = ttk.Entry(self, textvariable=self.entry_var, width=width, style='TEntry')
        self.entry.pack(fill='x', pady=(0, 2))

        # ツールチップ
        if tooltip:
            self.tooltip = Tooltip(self.entry, text=tooltip)

    def get_value(self) -> str:
        """エントリーの現在の値を取得します。"""
        return self.entry_var.get()

    def set_value(self, value: Any):
        """エントリーの値を設定します。"""
        self.entry_var.set(str(value))

    def validate(self) -> Tuple[bool, str]:
        """エントリーの値をバリデーションします。"""
        if self.validator:
            return self.validator(self.get_value(), self.label_text)
        return True, ""

class Tooltip:
    """ウィジェットにツールチップを追加するクラスです。"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        """ツールチップを表示します。"""
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 20

        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True) # ウィンドウの装飾をなくします
        self.tooltip_window.wm_geometry(f"+{x}+{y}")

        label = tk.Label(self.tooltip_window, text=self.text, background="#FFFFEA", relief="solid", borderwidth=1,
                         font=("IPAexGothic", 9), wraplength=200) # 日本語フォントと折り返し設定
        label.pack(ipadx=1)

    def hide_tooltip(self, event=None):
        """ツールチップを非表示にします。"""
        if self.tooltip_window:
            self.tooltip_window.destroy()
        self.tooltip_window = None

# ---- GUIクラス ----

class SeminarOptimizationGUI:
    # 定数定義 (初期値として使用し、リサイズ時に動的に調整します)
    INITIAL_WINDOW_WIDTH = 450
    INITIAL_WINDOW_HEIGHT = 600
    
    # テーマ設定
    THEMES = {
        "デフォルト": "clam",
        "モダン": "vista",
        # "ダーク": "equilux" # ttkthemesが必要なため、ここではコメントアウトします
    }
    
    def __init__(self):
        self.config_manager = ConfigManager()
        self.root = tk.Tk()
        
        # デフォルト値
        self.default_seminars = ['A', 'B', 'C']
        self.default_magnification = {'A': 1.5, 'B': 1.0, 'C': 0.8}
        self.default_preference_weights = {"1st": 5.0, "2nd": 2.0, "3rd": 1.0}
        
        # 設定用辞書
        self.entries: Dict[str, CustomEntryFrame] = {} # CustomEntryFrameのインスタンスを格納します
        self.defaults = self._initialize_defaults()
        
        self.result_settings: Optional[Dict[str, Any]] = None # 実行ボタンが押された結果を格納します
        
        self._setup_window()
        self._apply_dpi_awareness()
        
        # フォントの初期設定 (リサイズ時に更新されます)
        self.DEFAULT_FONT_FAMILY = self._get_preferred_font_family()
        self.DEFAULT_FONT = (self.DEFAULT_FONT_FAMILY, 11) # 初期ベースサイズ
        self.BOLD_FONT = (self.DEFAULT_FONT_FAMILY, 13, "bold") # 初期タブサイズ
        self.TITLE_FONT = (self.DEFAULT_FONT_FAMILY, 14, "bold") # 初期タイトルサイズ

        self._configure_ttk_styles()
        self._create_menu()
        self._create_widgets()
        self._load_saved_settings()

        # ウィンドウリサイズイベントをバインドします
        self.root.bind("<Configure>", self._on_window_resize)
    
    def _initialize_defaults(self) -> Dict[str, Any]:
        """デフォルト値の初期化を行います。"""
        return {
            "seminars": ",".join(self.default_seminars),
            "num_students": 112,
            "magnification": json.dumps(self.default_magnification, ensure_ascii=False),
            "min_size": 5,
            "max_size": 10,
            "q_boost_probability": 0.2,
            "num_preferences_to_consider": 3,
            "num_patterns": 200000,
            "max_workers": 8,
            "local_search_iterations": 500,
            "initial_temperature": 1.0,
            "cooling_rate": 0.995,
            "preference_weights_1st": self.default_preference_weights.get("1st", 5.0),
            "preference_weights_2nd": self.default_preference_weights.get("2nd", 2.0),
            "preference_weights_3rd": self.default_preference_weights.get("3rd", 1.0),
            "early_stop_threshold": 0.001,
            "no_improvement_limit": 1000,
            # 新しい設定項目
            "log_enabled": True,
            "save_intermediate": False,
            "theme": "デフォルト",
            "config_file_path": "", # 手動データ選択時の設定ファイルパス
            "student_file_path": "" # 手動データ選択時の学生ファイルパス
        }
    
    def _setup_window(self):
        """ウィンドウの基本設定を行います。"""
        self.root.title("セミナー割当最適化ツール - 設定 v2.0")
        self.root.geometry(f"{self.INITIAL_WINDOW_WIDTH}x{self.INITIAL_WINDOW_HEIGHT}")
        self.root.minsize(400, 500) # 最小サイズを設定します
        self.root.resizable(True, True) # ウィンドウのリサイズを許可します
        
        # アイコン設定（存在する場合）
        try:
            if os.path.exists("icon.ico"):
                self.root.iconbitmap("icon.ico")
        except:
            pass
        
        # 中央に配置します
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - self.INITIAL_WINDOW_WIDTH) // 2
        y = (self.root.winfo_screenheight() - self.INITIAL_WINDOW_HEIGHT) // 2
        self.root.geometry(f"{self.INITIAL_WINDOW_WIDTH}x{self.INITIAL_WINDOW_HEIGHT}+{x}+{y}")
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _apply_dpi_awareness(self):
        """DPIスケーリングを適用します。"""
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass

    def _get_preferred_font_family(self) -> str:
        """利用可能な日本語フォントを優先順位に基づいて取得します。"""
        available_fonts = tkinter.font.families()
        font_priority = ["Meiryo UI", "Meiryo", "Yu Gothic UI", "Yu Gothic", "IPAexGothic", "Arial"]
        
        for font in font_priority:
            if font in available_fonts:
                return font
        return "Arial" # デフォルトのフォールバック
    
    def _configure_ttk_styles(self):
        """スタイルの設定を行います。"""
        self.style = ttk.Style()
        
        # 利用可能なテーマの確認
        available_themes = self.style.theme_names()
        # 保存されたテーマを読み込み、利用可能であれば適用します。なければclam、それもなければ最初のテーマを適用します
        saved_theme = self.config_manager.get_setting("theme", "デフォルト")
        if saved_theme in self.THEMES and self.THEMES[saved_theme] in available_themes:
            self.style.theme_use(self.THEMES[saved_theme])
        elif 'clam' in available_themes:
            self.style.theme_use('clam')
        else:
            self.style.theme_use(available_themes[0])
        
        # スタイル適用 (現在のself.DEFAULT_FONT, BOLD_FONT, TITLE_FONTを使用)
        self.style.configure('TNotebook.Tab', font=self.BOLD_FONT)
        self.style.configure('TButton', font=self.BOLD_FONT)
        self.style.configure('TLabel', font=self.DEFAULT_FONT)
        self.style.configure('Title.TLabel', font=self.TITLE_FONT) # カスタムタイトルスタイル
        self.style.configure('TRadiobutton', font=self.DEFAULT_FONT)
        self.style.configure('TCheckbutton', font=self.DEFAULT_FONT)
        self.style.configure('TEntry', font=self.DEFAULT_FONT)
        self.style.configure('TLabelframe.Label', font=self.BOLD_FONT)

        # Title.TLabelのレイアウトをTLabelからコピーします
        self.style.layout('Title.TLabel', self.style.layout('TLabel'))
    
    def _on_window_resize(self, event):
        """ウィンドウサイズ変更時に呼び出されます。"""
        # ウィンドウの幅と高さが0になるのを防ぎます（初期化時や最小化時などに発生することがあります）
        if event.width == 0 or event.height == 0:
            return

        # 幅と高さの比率を考慮してフォントサイズを調整します
        # 最小サイズと最大サイズを設定して、極端な変化を防ぎます
        min_font_size = 8
        max_font_size = 16
        
        # ウィンドウの幅と高さに基づいて新しいベースフォントサイズを計算します
        # 基準となる初期サイズからの比率で計算することもできます
        width_ratio = event.width / self.INITIAL_WINDOW_WIDTH
        height_ratio = event.height / self.INITIAL_WINDOW_HEIGHT
        
        # 最小の比率を使って、フォントサイズがウィンドウの最も制約の厳しい次元に合わせるようにします
        scale_factor = min(width_ratio, height_ratio)
        
        # 初期フォントサイズを基準にスケーリングします
        initial_base_font_size = 11 # _initialize_defaultsで設定したDEFAULT_FONTの初期サイズ
        new_base_font_size = int(initial_base_font_size * scale_factor)
        
        # 最小・最大フォントサイズでクリップします
        new_base_font_size = max(min_font_size, min(max_font_size, new_base_font_size))
        
        # 各フォントのサイズを更新します
        self.DEFAULT_FONT = (self.DEFAULT_FONT_FAMILY, new_base_font_size)
        self.BOLD_FONT = (self.DEFAULT_FONT_FAMILY, int(new_base_font_size * 1.2) + 1, "bold") # タブのフォント (少し大きめに)
        self.TITLE_FONT = (self.DEFAULT_FONT_FAMILY, int(new_base_font_size * 1.4) + 2, "bold") # タイトルのフォント (さらに大きめに)

        # スタイルを再設定して、変更をUIに反映させます
        self._configure_ttk_styles()

        # ウィジェットの再描画を強制します
        self.root.update_idletasks()

    def _create_menu(self):
        """メニューバーを作成します。"""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # ファイルメニュー
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="ファイル", menu=file_menu)
        file_menu.add_command(label="設定をインポート", command=self._import_settings)
        file_menu.add_command(label="設定をエクスポート", command=self._export_settings)
        file_menu.add_separator()
        file_menu.add_command(label="デフォルト値に戻す", command=self._reset_to_defaults)
        file_menu.add_separator()
        file_menu.add_command(label="終了", command=self._on_closing)
        
        # ヘルプメニュー
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="ヘルプ", menu=help_menu)
        help_menu.add_command(label="使用方法", command=self._show_help)
        help_menu.add_command(label="このアプリについて", command=self._show_about)
    
    def _create_widgets(self):
        """ウィジェットを作成します。"""
        # メインフレーム
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)
        
        # ノートブック
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill="both", expand=True)
        
        self._create_data_source_tab()
        self._create_auto_gen_tab()
        self._create_optimization_tab()
        self._create_advanced_tab()
        
        # ボタンフレーム
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill="x", pady=10)
        
        # プリセット読み込みボタン
        ttk.Button(button_frame, text="プリセット読み込み", 
                   command=self._load_preset).pack(side="left", padx=5)
        
        # プリセット保存ボタン
        ttk.Button(button_frame, text="プリセット保存", 
                   command=self._save_preset).pack(side="left", padx=5)
        
        # 実行ボタン
        self.run_button = ttk.Button(button_frame, text="最適化を実行", 
                                     command=self._on_run_button_click)
        self.run_button.pack(side="right", padx=5)
        
        # キャンセルボタン
        ttk.Button(button_frame, text="終了", 
                   command=self._on_closing).pack(side="right", padx=5)
    
    def _create_data_source_tab(self):
        """データソースタブを作成します。"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="データソース")
        
        ttk.Label(frame, text="データ入力方法", style="Title.TLabel").pack(pady=10)
        
        self.data_source_var = tk.StringVar(value=self.config_manager.get_setting("data_source", "auto"))
        
        radio_frame = ttk.LabelFrame(frame, text="選択してください", padding=10)
        radio_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Radiobutton(radio_frame, text="手動データを使用 (seminar_config.json, students_preferences.csv)", 
                        variable=self.data_source_var, value="manual").pack(anchor="w", pady=2)
        
        ttk.Radiobutton(radio_frame, text="自動生成データを使用", 
                        variable=self.data_source_var, value="auto").pack(anchor="w", pady=2)
        
        # ファイル選択フレーム
        file_frame = ttk.LabelFrame(frame, text="ファイル選択 (手動データ使用時)", padding=10)
        file_frame.pack(fill="x", padx=10, pady=5)
        
        self.config_file_path_var = tk.StringVar(value=self.config_manager.get_setting("config_file_path", ""))
        self.student_file_path_var = tk.StringVar(value=self.config_manager.get_setting("student_file_path", ""))

        ttk.Label(file_frame, text="設定ファイル:").pack(anchor="w", padx=5)
        ttk.Entry(file_frame, textvariable=self.config_file_path_var, state="readonly", width=40).pack(fill="x", pady=2, padx=5)
        ttk.Button(file_frame, text="選択...", 
                   command=self._select_config_file).pack(fill="x", pady=2, padx=5)
        
        ttk.Label(file_frame, text="学生データファイル:").pack(anchor="w", padx=5, pady=(10,0))
        ttk.Entry(file_frame, textvariable=self.student_file_path_var, state="readonly", width=40).pack(fill="x", pady=2, padx=5)
        ttk.Button(file_frame, text="選択...", 
                   command=self._select_student_file).pack(fill="x", pady=2, padx=5)
    
    def _create_auto_gen_tab(self):
        """自動生成設定タブを作成します。"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="自動生成設定")
        
        # スクロール可能フレーム
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # マウスホイール対応
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 各種設定項目
        self._add_auto_gen_entries(scrollable_frame)
    
    def _add_auto_gen_entries(self, parent):
        """自動生成設定項目を追加します。"""
        ttk.Label(parent, text="基本設定", style="Title.TLabel").pack(pady=10)
        
        # セミナー名
        self.entries["seminars"] = CustomEntryFrame(
            parent, "セミナー名 (カンマ区切り)", 
            self.defaults["seminars"], width=40,
            tooltip="例: a,b,c,d,e"
        )
        self.entries["seminars"].pack(fill="x", padx=10, pady=2)
        
        # 学生数
        self.entries["num_students"] = CustomEntryFrame(
            parent, "学生数", 
            str(self.defaults["num_students"]), width=15,
            tooltip="シミュレーションする学生の総数",
            validator=lambda x, name: InputValidator.validate_positive_int(x, name)
        )
        self.entries["num_students"].pack(fill="x", padx=10, pady=2)
        
        # 倍率設定
        self.entries["magnification"] = CustomEntryFrame(
            parent, "各セミナーの倍率 (JSON形式)", 
            self.defaults["magnification"], width=40,
            tooltip='例: {"a": 2.0, "d": 3.0}',
            validator=lambda x, name: InputValidator.validate_json_dict(x, name)
        )
        self.entries["magnification"].pack(fill="x", padx=10, pady=2)
        
        # 定員設定
        capacity_frame = ttk.LabelFrame(parent, text="定員設定", padding=5)
        capacity_frame.pack(fill="x", padx=10, pady=5)
        
        self.entries["min_size"] = CustomEntryFrame(
            capacity_frame, "最小定員", 
            str(self.defaults["min_size"]), width=10,
            validator=lambda x, name: InputValidator.validate_positive_int(x, name)
        )
        self.entries["min_size"].pack(fill="x", pady=2)
        
        self.entries["max_size"] = CustomEntryFrame(
            capacity_frame, "最大定員", 
            str(self.defaults["max_size"]), width=10,
            validator=lambda x, name: InputValidator.validate_positive_int(x, name)
        )
        self.entries["max_size"].pack(fill="x", pady=2)
        
        # q_boost_probability
        self.entries["q_boost_probability"] = CustomEntryFrame(
            parent, "'q'セミナーの希望ブースト確率 (0.0～1.0)",
            str(self.defaults["q_boost_probability"]), width=10,
            tooltip="Qセミナーを第一希望にする確率を高めます",
            validator=lambda x, name: InputValidator.validate_range_float(x, name, 0.0, 1.0)
        )
        self.entries["q_boost_probability"].pack(fill="x", padx=10, pady=2)

        # num_preferences_to_consider
        self.entries["num_preferences_to_consider"] = CustomEntryFrame(
            parent, "第何希望まで考慮するか",
            str(self.defaults["num_preferences_to_consider"]), width=10,
            tooltip="スコア計算で考慮する希望順位の深さ",
            validator=lambda x, name: InputValidator.validate_positive_int(x, name)
        )
        self.entries["num_preferences_to_consider"].pack(fill="x", padx=10, pady=2)
    
    def _create_optimization_tab(self):
        """最適化設定タブを作成します。"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="最適化設定")
        
        # スクロール可能フレーム
        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self._add_optimization_entries(scrollable_frame)
    
    def _add_optimization_entries(self, parent):
        """最適化設定項目を追加します。"""
        ttk.Label(parent, text="アルゴリズム設定", style="Title.TLabel").pack(pady=10)
        
        # 基本パラメータ
        basic_frame = ttk.LabelFrame(parent, text="基本パラメータ", padding=5)
        basic_frame.pack(fill="x", padx=10, pady=5)
        
        self.entries["num_patterns"] = CustomEntryFrame(
            basic_frame, "試行回数", 
            str(self.defaults["num_patterns"]), width=15,
            tooltip="最適化の試行回数（多いほど良い解が見つかりやすいです）",
            validator=lambda x, name: InputValidator.validate_positive_int(x, name)
        )
        self.entries["num_patterns"].pack(fill="x", pady=2)
        
        self.entries["max_workers"] = CustomEntryFrame(
            basic_frame, "並列処理数", 
            str(self.defaults["max_workers"]), width=10,
            tooltip="同時に実行する処理数（CPUコア数以下推奨です）",
            validator=lambda x, name: InputValidator.validate_positive_int(x, name)
        )
        self.entries["max_workers"].pack(fill="x", pady=2)
        
        # 焼きなまし法設定
        sa_frame = ttk.LabelFrame(parent, text="焼きなまし法設定", padding=5)
        sa_frame.pack(fill="x", padx=10, pady=5)

        self.entries["local_search_iterations"] = CustomEntryFrame(
            sa_frame, "局所探索反復回数",
            str(self.defaults["local_search_iterations"]), width=10,
            tooltip="各パターンにおける局所探索の反復回数です",
            validator=lambda x, name: InputValidator.validate_positive_int(x, name)
        )
        self.entries["local_search_iterations"].pack(fill="x", pady=2)
        
        self.entries["initial_temperature"] = CustomEntryFrame(
            sa_frame, "初期温度", 
            str(self.defaults["initial_temperature"]), width=10,
            tooltip="焼きなまし法の初期温度です",
            validator=lambda x, name: InputValidator.validate_positive_float(x, name)
        )
        self.entries["initial_temperature"].pack(fill="x", pady=2)
        
        self.entries["cooling_rate"] = CustomEntryFrame(
            sa_frame, "冷却率", 
            str(self.defaults["cooling_rate"]), width=10,
            tooltip="温度の冷却率 (0.0より大きく1.0未満推奨です)",
            validator=lambda x, name: InputValidator.validate_range_float(x, name, 0.0, 1.0)
        )
        self.entries["cooling_rate"].pack(fill="x", pady=2)
        
        # スコア重み設定
        weight_frame = ttk.LabelFrame(parent, text="希望順位の重み", padding=5)
        weight_frame.pack(fill="x", padx=10, pady=5)
        
        for rank, key in [("1位希望", "preference_weights_1st"), 
                          ("2位希望", "preference_weights_2nd"), 
                          ("3位希望", "preference_weights_3rd")]:
            self.entries[key] = CustomEntryFrame(
                weight_frame, f"{rank}の重み", 
                str(self.defaults[key]), width=10,
                validator=lambda x, name: InputValidator.validate_positive_float(x, name)
            )
            self.entries[key].pack(fill="x", pady=2)
    
    def _create_advanced_tab(self):
        """高度な設定タブを作成します。"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="高度な設定")
        
        ttk.Label(frame, text="高度な設定", style="Title.TLabel").pack(pady=10)
        
        # ログ設定
        log_frame = ttk.LabelFrame(frame, text="ログ設定", padding=5)
        log_frame.pack(fill="x", padx=10, pady=5)
        
        self.log_enabled = tk.BooleanVar(value=self.config_manager.get_setting("log_enabled", True))
        ttk.Checkbutton(log_frame, text="詳細ログを出力します", 
                        variable=self.log_enabled).pack(anchor="w")
        
        self.save_intermediate = tk.BooleanVar(value=self.config_manager.get_setting("save_intermediate", False))
        ttk.Checkbutton(log_frame, text="中間結果を保存します", 
                        variable=self.save_intermediate).pack(anchor="w")
        
        # テーマ設定
        theme_frame = ttk.LabelFrame(frame, text="テーマ設定", padding=5)
        theme_frame.pack(fill="x", padx=10, pady=5)
        
        self.theme_var = tk.StringVar(value=self.config_manager.get_setting("theme", "デフォルト"))
        for theme_name in self.THEMES.keys():
            ttk.Radiobutton(theme_frame, text=theme_name, 
                            variable=self.theme_var, value=theme_name,
                            command=self._change_theme).pack(anchor="w")
        
        # 早期終了設定
        early_stop_frame = ttk.LabelFrame(frame, text="早期終了設定 (現在未使用)", padding=5)
        early_stop_frame.pack(fill="x", padx=10, pady=5)

        self.entries["early_stop_threshold"] = CustomEntryFrame(
            early_stop_frame, "早期終了閾値",
            str(self.defaults["early_stop_threshold"]), width=10,
            tooltip="スコア改善がこの閾値以下の場合に早期終了します",
            validator=lambda x, name: InputValidator.validate_positive_float(x, name)
        )
        self.entries["early_stop_threshold"].pack(fill="x", pady=2)

        self.entries["no_improvement_limit"] = CustomEntryFrame(
            early_stop_frame, "改善なし制限",
            str(self.defaults["no_improvement_limit"]), width=10,
            tooltip="この回数だけ改善がない場合に早期終了します",
            validator=lambda x, name: InputValidator.validate_positive_int(x, name)
        )
        self.entries["no_improvement_limit"].pack(fill="x", pady=2)
    
    def _load_saved_settings(self):
        """保存された設定をGUIに読み込みます。"""
        for key, entry_frame in self.entries.items():
            saved_value = self.config_manager.get_setting(key, None)
            if saved_value is not None:
                entry_frame.set_value(saved_value)
            else:
                # configファイルにない場合はデフォルト値を設定
                entry_frame.set_value(self.defaults[key])
        
        # BooleanVar, StringVarなどの特殊なウィジェットの読み込み
        self.data_source_var.set(self.config_manager.get_setting("data_source", "auto"))
        self.log_enabled.set(self.config_manager.get_setting("log_enabled", True))
        self.save_intermediate.set(self.config_manager.get_setting("save_intermediate", False))
        self.theme_var.set(self.config_manager.get_setting("theme", "デフォルト"))
        self.config_file_path_var.set(self.config_manager.get_setting("config_file_path", ""))
        self.student_file_path_var.set(self.config_manager.get_setting("student_file_path", ""))

        self._change_theme() # テーマの変更を反映します

    def _save_current_settings(self) -> bool:
        """現在のGUI設定をConfigManagerに保存します。"""
        current_settings = {}
        for key, entry_frame in self.entries.items():
            is_valid, message = entry_frame.validate()
            if not is_valid:
                messagebox.showerror("入力エラー", message)
                return False
            
            # 特殊な型の変換（JSON文字列など）
            value = entry_frame.get_value()
            if key in ["magnification"]:
                try:
                    current_settings[key] = json.loads(value)
                except json.JSONDecodeError:
                    messagebox.showerror("入力エラー", f"{entry_frame.label_text}の形式が不正です。")
                    return False
            elif key in ["seminars"]:
                current_settings[key] = [s.strip() for s in value.split(',') if s.strip()]
            elif key.startswith("preference_weights_"):
                current_settings[key] = float(value)
            else:
                current_settings[key] = value # その他の値は文字列として保存

        # BooleanVar, StringVarなどの特殊なウィジェットの値を取得
        current_settings["data_source"] = self.data_source_var.get()
        current_settings["log_enabled"] = self.log_enabled.get()
        current_settings["save_intermediate"] = self.save_intermediate.get()
        current_settings["theme"] = self.theme_var.get()
        current_settings["config_file_path"] = self.config_file_path_var.get()
        current_settings["student_file_path"] = self.student_file_path_var.get()

        try:
            # min_sizeとmax_sizeの論理的なバリデーション
            min_s = int(self.entries["min_size"].get_value())
            max_s = int(self.entries["max_size"].get_value())
            if min_s > max_s:
                messagebox.showerror("入力エラー", "最小定員は最大定員以下である必要があります。")
                return False
            
            self.config_manager.save_config(current_settings)
            return True
        except Exception as e:
            messagebox.showerror("保存エラー", f"設定の保存中にエラーが発生しました: {e}")
            return False

    def _on_run_button_click(self):
        """「最適化を実行」ボタンがクリックされたときの処理です。"""
        if not self._save_current_settings(): # 設定保存が失敗したら処理を中断します
            return

        # GUIから現在の設定を収集します
        collected_params = {}
        for key, entry_frame in self.entries.items():
            value = entry_frame.get_value()
            if key == "seminars":
                collected_params[key] = [s.strip() for s in value.split(',') if s.strip()]
            elif key == "magnification":
                collected_params[key] = json.loads(value)
            elif key.startswith("preference_weights_"):
                collected_params[key] = float(value)
            elif key in ["num_students", "min_size", "max_size", "num_patterns", "max_workers", 
                         "local_search_iterations", "no_improvement_limit", "num_preferences_to_consider"]:
                collected_params[key] = int(value)
            elif key in ["q_boost_probability", "initial_temperature", "cooling_rate", "early_stop_threshold"]:
                collected_params[key] = float(value)
            else:
                collected_params[key] = value
        
        collected_params["data_source"] = self.data_source_var.get()
        collected_params["log_enabled"] = self.log_enabled.get()
        collected_params["save_intermediate"] = self.save_intermediate.get()
        collected_params["theme"] = self.theme_var.get()
        collected_params["config_file_path"] = self.config_file_path_var.get()
        collected_params["student_file_path"] = self.student_file_path_var.get()

        self.result_settings = collected_params # 結果を設定として保存します
        self.root.destroy() # ウィンドウを閉じます

    def _on_closing(self):
        """ウィンドウを閉じる際の処理です。設定を保存し、ウィンドウを破棄します。"""
        self._save_current_settings() # 終了時にも設定を保存します
        self.result_settings = None # キャンセルとしてNoneを設定します
        self.root.destroy()

    def _select_config_file(self):
        """設定ファイルを選択します。"""
        filepath = filedialog.askopenfilename(
            title="セミナー設定ファイルを選択してください",
            filetypes=[("JSONファイル", "*.json"), ("全てのファイル", "*.*")]
        )
        if filepath:
            self.config_file_path_var.set(filepath)

    def _select_student_file(self):
        """学生データファイルを選択します。"""
        filepath = filedialog.askopenfilename(
            title="学生希望データファイルを選択してください",
            filetypes=[("CSVファイル", "*.csv"), ("全てのファイル", "*.*")]
        )
        if filepath:
            self.student_file_path_var.set(filepath)

    def _import_settings(self):
        """設定をファイルからインポートします。"""
        filepath = filedialog.askopenfilename(
            title="設定ファイルをインポート",
            filetypes=[("INIファイル", "*.ini"), ("全てのファイル", "*.*")]
        )
        if filepath:
            try:
                temp_config_manager = ConfigManager(filepath)
                temp_config_manager.load_config()
                
                # インポートした設定をGUIに適用します
                for key, entry_frame in self.entries.items():
                    imported_value = temp_config_manager.get_setting(key)
                    if imported_value is not None:
                        entry_frame.set_value(imported_value)
                
                self.data_source_var.set(temp_config_manager.get_setting("data_source", "auto"))
                self.log_enabled.set(temp_config_manager.get_setting("log_enabled", True))
                self.save_intermediate.set(temp_config_manager.get_setting("save_intermediate", False))
                self.theme_var.set(temp_config_manager.get_setting("theme", "デフォルト"))
                self.config_file_path_var.set(temp_config_manager.get_setting("config_file_path", ""))
                self.student_file_path_var.set(temp_config_manager.get_setting("student_file_path", ""))

                self._change_theme() # テーマの変更を反映します
                messagebox.showinfo("インポート完了", "設定を正常にインポートしました。")
            except Exception as e:
                messagebox.showerror("インポートエラー", f"設定のインポート中にエラーが発生しました: {e}")

    def _export_settings(self):
        """現在の設定をファイルにエクスポートします。"""
        if not self._save_current_settings(): # まず現在の設定を保存します
            return
        
        filepath = filedialog.asksaveasfilename(
            title="設定をエクスポート",
            defaultextension=".ini",
            filetypes=[("INIファイル", "*.ini"), ("全てのファイル", "*.*")]
        )
        if filepath:
            try:
                # 現在のConfigManagerの内容を新しいパスに書き出します
                with open(filepath, 'w', encoding='utf-8') as f:
                    self.config_manager.config.write(f)
                messagebox.showinfo("エクスポート完了", f"設定を正常にエクスポートしました:\n{filepath}")
            except Exception as e:
                messagebox.showerror("エクスポートエラー", f"設定のエクスポート中にエラーが発生しました: {e}")

    def _reset_to_defaults(self):
        """全てのGUI設定をデフォルト値に戻します。"""
        if messagebox.askyesno("確認", "全ての設定をデフォルト値に戻しますか？"):
            for key, entry_frame in self.entries.items():
                entry_frame.set_value(self.defaults[key])
            
            # BooleanVar, StringVarなどの特殊なウィジェットもデフォルトに戻します
            self.data_source_var.set(self.defaults["data_source"])
            self.log_enabled.set(self.defaults["log_enabled"])
            self.save_intermediate.set(self.defaults["save_intermediate"])
            self.theme_var.set(self.defaults["theme"])
            self.config_file_path_var.set(self.defaults["config_file_path"])
            self.student_file_path_var.set(self.defaults["student_file_path"])

            self._change_theme() # テーマの変更を反映します
            messagebox.showinfo("リセット完了", "設定をデフォルト値に戻しました。")

    def _change_theme(self):
        """GUIのテーマを変更します。"""
        selected_theme_name = self.theme_var.get()
        ttk_theme_name = self.THEMES.get(selected_theme_name)
        
        if ttk_theme_name and ttk_theme_name in self.style.theme_names():
            self.style.theme_use(ttk_theme_name)
        else:
            messagebox.showwarning("テーマエラー", f"テーマ '{selected_theme_name}' は利用できません。デフォルトテーマを使用します。")
            self.style.theme_use('clam') # フォールバック

    def _load_preset(self):
        """プリセット設定を読み込みます。"""
        # 簡易的なプリセットの例
        presets = {
            "小規模セミナー (30人)": {
                "seminars": "A,B,C", "num_students": 30, "min_size": 5, "max_size": 10,
                "num_patterns": 10000, "max_workers": 4, "local_search_iterations": 100
            },
            "大規模セミナー (100人)": {
                "seminars": "A,B,C,D,E,F,G,H,I,J", "num_students": 100, "min_size": 8, "max_size": 15,
                "num_patterns": 50000, "max_workers": 8, "local_search_iterations": 300
            }
        }
        
        preset_names = list(presets.keys())
        
        # プリセット選択ダイアログを表示します
        preset_dialog = tk.Toplevel(self.root)
        preset_dialog.title("プリセットを選択")
        preset_dialog.transient(self.root) # 親ウィンドウの上に表示します
        preset_dialog.grab_set() # 親ウィンドウを無効にします
        
        tk.Label(preset_dialog, text="読み込むプリセットを選択してください:", font=self.DEFAULT_FONT).pack(pady=10)
        
        listbox_frame = ttk.Frame(preset_dialog)
        listbox_frame.pack(padx=10, pady=5)
        
        listbox = tk.Listbox(listbox_frame, height=len(preset_names), font=self.DEFAULT_FONT)
        for name in preset_names:
            listbox.insert(tk.END, name)
        listbox.pack(side="left", fill="both", expand=True)
        
        scrollbar = ttk.Scrollbar(listbox_frame, orient="vertical", command=listbox.yview)
        scrollbar.pack(side="right", fill="y")
        listbox.config(yscrollcommand=scrollbar.set)
        
        def apply_selected_preset():
            selected_index = listbox.curselection()
            if selected_index:
                selected_preset_name = preset_names[selected_index[0]]
                selected_preset_settings = presets[selected_preset_name]
                
                # GUIに設定を適用します
                for key, value in selected_preset_settings.items():
                    if key in self.entries:
                        self.entries[key].set_value(value)
                    elif key == "theme" and key in self.THEMES:
                        self.theme_var.set(value)
                        self._change_theme()
                messagebox.showinfo("プリセット読み込み", f"プリセット '{selected_preset_name}' を読み込みました。")
                preset_dialog.destroy()
            else:
                messagebox.showwarning("選択なし", "プリセットを選択してください。")

        btn_frame = ttk.Frame(preset_dialog)
        btn_frame.pack(pady=10)
        ttk.Button(btn_frame, text="適用", command=apply_selected_preset).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="キャンセル", command=preset_dialog.destroy).pack(side="left", padx=5)
        
        self.root.wait_window(preset_dialog) # ダイアログが閉じるまで待機します

    def _save_preset(self):
        """現在の設定をプリセットとして保存します。"""
        if not self._save_current_settings(): # まず現在の設定を保存します
            return
        
        preset_name = tk.simpledialog.askstring("プリセット名", "保存するプリセットの名前を入力してください:")
        if preset_name:
            # ここでは簡易的にファイルに保存するのではなく、メッセージを表示するだけです。
            # 実際のプリセット管理は、ConfigManagerにプリセットセクションを追加するなど、より複雑になります。
            messagebox.showinfo("プリセット保存", f"現在の設定を '{preset_name}' として保存しました (機能は未実装)。")
        
    def _show_help(self):
        """ヘルプ情報を表示します。"""
        messagebox.showinfo("使用方法", "このツールはセミナーの学生割り当てを最適化します。\n\n"
                                        "データソースタブで手動データか自動生成データかを選択してください。\n"
                                        "各タブで必要な設定を入力し、「最適化を実行」ボタンを押してください。\n"
                                        "結果はポップアップで表示されます。")

    def _show_about(self):
        """アプリ情報を表示します。"""
        messagebox.showinfo("このアプリについて", "セミナー割当最適化ツール v2.0\n\n"
                                               "開発者: Gemini\n"
                                               f"最終更新日: {datetime.now().strftime('%Y/%m/%d')}\n\n"
                                               "このツールは、学生の希望とセミナーの定員を考慮して、\n"
                                               "最適な割り当てを見つけることを目的としています。")

    def get_user_settings(self) -> Optional[Dict[str, Any]]:
        """GUIを表示し、ユーザーの設定を取得します。"""
        self.root.mainloop() # GUIループを開始します
        return self.result_settings # 実行ボタンが押された場合のみ設定を返します

# main.pyから呼び出される公開関数
def launch_gui_and_get_settings() -> Optional[Dict[str, Any]]:
    """GUIを起動し、ユーザーが設定した内容を辞書として返します。"""
    gui = SeminarOptimizationGUI()
    return gui.get_user_settings()

if __name__ == '__main__':
    # このファイルを直接実行してGUIをテストします
    print("GUIをテスト起動します。")
    settings = launch_gui_and_get_settings()
    if settings:
        print("\nGUIから取得した設定:")
        import pprint
        pprint.pprint(settings)
    else:
        print("設定がキャンセルされました。")

