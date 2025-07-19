import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
from typing import Dict, List, Any, Optional, Callable, Tuple
import ctypes # DPI設定用
import tkinter.font # Tkinterのフォントをチェックするためにインポート
import os
import threading # 最適化処理を別スレッドで実行するために使用
from datetime import datetime
import configparser # 設定ファイルの読み書きに利用
from dataclasses import asdict # 追加: asdictをインポート

# ConfigManager, ValidationError, InputValidator, ProgressDialog クラスは変更なし
class ConfigManager:
    """設定の保存・読み込みを管理するクラス"""
    
    def __init__(self, config_file: str = "gui_settings.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()
        self.load_config()
    
    def load_config(self):
        """設定ファイルから設定を読み込み"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file, encoding='utf-8')
    
    def save_config(self, settings: Dict[str, Any]):
        """設定をファイルに保存"""
        if 'GUI' not in self.config:
            self.config.add_section('GUI')
        
        # 設定値を文字列として保存
        for key, value in settings.items():
            if isinstance(value, dict):
                self.config['GUI'][key] = json.dumps(value, ensure_ascii=False)
            else:
                self.config['GUI'][key] = str(value)
        
        with open(self.config_file, 'w', encoding='utf-8') as f:
            self.config.write(f)
    
    def get_setting(self, key: str, default_value: Any = None) -> Any:
        """設定値を取得"""
        if 'GUI' not in self.config or key not in self.config['GUI']:
            return default_value
        
        value = self.config['GUI'][key]
        
        # 型に応じて変換
        if isinstance(default_value, dict):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return default_value
        elif isinstance(default_value, int):
            try:
                return int(value)
            except ValueError:
                return default_value
        elif isinstance(default_value, float):
            try:
                return float(value)
            except ValueError:
                return default_value
        elif isinstance(default_value, bool):
            return value.lower() in ['true', '1', 'yes', 'on']
        else:
            return value

class ValidationError(Exception):
    """バリデーションエラー用の例外クラス"""
    pass

class InputValidator:
    """入力値の検証を行うクラス"""
    
    @staticmethod
    def validate_positive_int(value: str, field_name: str) -> int:
        """正の整数の検証"""
        try:
            int_value = int(value)
            if int_value <= 0:
                raise ValidationError(f"{field_name}は正の整数である必要があります")
            return int_value
        except ValueError:
            raise ValidationError(f"{field_name}は有効な整数を入力してください")
    
    @staticmethod
    def validate_positive_float(value: str, field_name: str) -> float:
        """正の浮動小数点数の検証"""
        try:
            float_value = float(value)
            if float_value <= 0:
                raise ValidationError(f"{field_name}は正の数値である必要があります")
            return float_value
        except ValueError:
            raise ValidationError(f"{field_name}は有効な数値を入力してください")
    
    @staticmethod
    def validate_range_float(value: str, field_name: str, min_val: float, max_val: float) -> float:
        """範囲指定の浮動小数点数の検証"""
        try:
            float_value = float(value)
            if not (min_val <= float_value <= max_val):
                raise ValidationError(f"{field_name}は{min_val}から{max_val}の間で入力してください")
            return float_value
        except ValueError:
            raise ValidationError(f"{field_name}は有効な数値を入力してください")
    
    @staticmethod
    def validate_json_dict(value: str, field_name: str) -> dict:
        """JSON辞書形式の検証"""
        try:
            parsed = json.loads(value)
            if not isinstance(parsed, dict):
                raise ValidationError(f"{field_name}は辞書形式で入力してください")
            return parsed
        except json.JSONDecodeError:
            raise ValidationError(f"{field_name}は有効なJSON形式で入力してください")

class ProgressDialog:
    """進捗表示ダイアログ"""
    
    def __init__(self, parent, title="処理中..."):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("300x100")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent) # 親ウィンドウの上に表示
        self.dialog.grab_set() # 親ウィンドウの操作を無効化
        
        # 中央に配置
        self.dialog.update_idletasks() # ウィンドウ情報を更新
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.dialog.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.dialog.winfo_height() // 2)
        self.dialog.geometry(f"+{x}+{y}")
        
        self.progress_var = tk.StringVar(value="処理を開始しています...")
        ttk.Label(self.dialog, textvariable=self.progress_var, font=("IPAexGothic", 10)).pack(pady=20)
        
        self.progress_bar = ttk.Progressbar(self.dialog, mode='indeterminate')
        self.progress_bar.pack(pady=10, padx=20, fill='x')
        self.progress_bar.start()
        
        self.cancel_button = ttk.Button(self.dialog, text="キャンセル", command=self.cancel, font=("IPAexGothic", 9))
        self.cancel_button.pack(pady=5)
        
        self.cancelled = False
    
    def update_message(self, message: str):
        """進捗メッセージを更新"""
        self.progress_var.set(message)
        self.dialog.update_idletasks() # 即座にUIを更新
    
    def cancel(self):
        """キャンセル処理"""
        self.cancelled = True
        self.close()
    
    def close(self):
        """ダイアログを閉じる"""
        self.progress_bar.stop()
        self.dialog.destroy()

class CustomEntryFrame(ttk.Frame):
    """ラベル付きエントリーウィジェットのカスタムフレーム"""
    
    def __init__(self, parent, label_text: str, default_value: str = "", 
                 width: int = 20, tooltip: str = "", validator: Callable = None,
                 entry_state: str = "normal"): # 新しい引数: エントリーの状態
        super().__init__(parent)
        
        self.validator = validator
        self.tooltip_text = tooltip
        
        # ラベル
        self.label = ttk.Label(self, text=label_text)
        self.label.pack(anchor="w")
        
        # エントリーフレーム
        entry_frame = ttk.Frame(self)
        entry_frame.pack(fill="x", pady=2)
        
        # エントリー
        self.entry = ttk.Entry(entry_frame, width=width, state=entry_state) # stateを設定
        self.entry.insert(0, default_value)
        self.entry.pack(side="left", fill="x", expand=True)
        
        # バリデーション結果表示
        self.validation_label = ttk.Label(entry_frame, text="", foreground="red")
        self.validation_label.pack(side="right", padx=5)
        
        # リアルタイムバリデーション
        self.entry.bind('<FocusOut>', self._validate)
        self.entry.bind('<KeyRelease>', self._validate_delayed)
        
        # ツールチップ
        if tooltip:
            self._create_tooltip()
        
        self.validation_job = None
    
    def _validate_delayed(self, event=None):
        """遅延バリデーション（入力中の頻繁な検証を避ける）"""
        if self.validation_job:
            self.after_cancel(self.validation_job)
        self.validation_job = self.after(500, self._validate)
    
    def _validate(self, event=None):
        """入力値の検証"""
        if not self.validator:
            self.validation_label.config(text="") # バリデーターがない場合は表示をクリア
            return True
        
        try:
            value = self.entry.get()
            if value.strip():  # 空でない場合のみ検証
                self.validator(value)
            self.validation_label.config(text="✓", foreground="green")
            return True
        except (ValueError, ValidationError) as e:
            self.validation_label.config(text="✗", foreground="red")
            return False
    
    def _create_tooltip(self):
        """ツールチップの作成"""
        def show_tooltip(event):
            tooltip = tk.Toplevel(self.master) # 親ウィジェットをmasterに設定
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
            label = ttk.Label(tooltip, text=self.tooltip_text, 
                              background="lightyellow", relief="solid", borderwidth=1, font=("IPAexGothic", 8))
            label.pack()
            
            def hide_tooltip():
                tooltip.destroy()
            
            tooltip.after(3000, hide_tooltip)  # 3秒後に自動で消去
        
        self.label.bind("<Enter>", show_tooltip)
    
    def get(self) -> str:
        """エントリーの値を取得"""
        return self.entry.get()
    
    def set(self, value: str):
        """エントリーの値を設定"""
        self.entry.delete(0, tk.END)
        self.entry.insert(0, value)

    def configure_state(self, state: str):
        """エントリーの状態を変更します (normal, disabled, readonly)"""
        self.entry.config(state=state)

class SeminarOptimizationGUI:
    """改善されたセミナー最適化GUI"""
    
    # 定数定義
    WINDOW_WIDTH = 450
    WINDOW_HEIGHT = 600
    
    # テーマ設定
    THEMES = {
        "デフォルト": "clam",
        "モダン": "vista",
        # "ダーク": "equilux" # ttkthemesが必要なため、ここではコメントアウト
    }
    
    def __init__(self, default_seminars: List[str], default_magnification: Dict[str, float], 
                 default_preference_weights: Dict[str, float]):
        self.settings = {}
        self.config_manager = ConfigManager()
        self.root = tk.Tk()
        
        # デフォルト値
        self.default_seminars = default_seminars
        self.default_magnification = default_magnification
        self.default_preference_weights = default_preference_weights
        
        # 設定用辞書
        self.entries = {} # CustomEntryFrameのインスタンスを格納
        self.defaults = self._initialize_defaults()
        
        self._setup_window()
        self._apply_dpi_awareness()
        self._configure_ttk_styles()
        self._create_menu()
        self._create_widgets()
        self._load_saved_settings()

        # 最適化戦略の選択に応じてGAパラメータの表示/非表示を切り替える
        self.optimization_strategy_var.trace_add("write", self._toggle_strategy_parameters)
        self._toggle_strategy_parameters() # 初期状態を設定
    
    def _initialize_defaults(self) -> Dict[str, Any]:
        """デフォルト値の初期化"""
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
            "student_file_path": "", # 手動データ選択時の学生ファイルパス
            "optimization_strategy": "Greedy_LS", # デフォルトの最適化戦略
            "ga_population_size": 100, # GAパラメータ
            "ga_crossover_rate": 0.8, # GAパラメータ
            "ga_mutation_rate": 0.05, # GAパラメータ
            # ILP/CP/Multilevelのパラメータは現時点ではGUIに表示しないが、将来的な拡張のために残す
            "ilp_time_limit": 300, # 秒
            "cp_time_limit": 300, # 秒
            "multilevel_clusters": 5 # 多段階最適化のクラスタ数
        }
    
    def _setup_window(self):
        """ウィンドウの基本設定"""
        self.root.title("セミナー割当最適化ツール - 設定 v2.0")
        self.root.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")
        self.root.minsize(400, 500)
        
        # アイコン設定（存在する場合）
        try:
            if os.path.exists("icon.ico"):
                self.root.iconbitmap("icon.ico")
        except:
            pass
        
        # 中央に配置
        self.root.update_idletasks()
        x = (self.root.winfo_screenwidth() - self.WINDOW_WIDTH) // 2
        y = (self.root.winfo_screenheight() - self.WINDOW_HEIGHT) // 2
        self.root.geometry(f"+{x}+{y}")
        
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _apply_dpi_awareness(self):
        """DPIスケーリングの適用"""
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            pass
    
    def _configure_ttk_styles(self):
        """スタイルの設定"""
        self.style = ttk.Style()
        
        # 利用可能なテーマの確認
        available_themes = self.style.theme_names()
        # 保存されたテーマを読み込み、利用可能であれば適用。なければclam、それもなければ最初のテーマ
        saved_theme = self.config_manager.get_setting("theme", "デフォルト")
        if saved_theme in self.THEMES and self.THEMES[saved_theme] in available_themes:
            self.style.theme_use(self.THEMES[saved_theme])
        elif 'clam' in available_themes:
            self.style.theme_use('clam')
        else:
            self.style.theme_use(available_themes[0])
        
        # フォント設定
        available_fonts = tkinter.font.families()
        font_priority = ["Meiryo UI", "Meiryo", "Yu Gothic UI", "Yu Gothic", "IPAexGothic", "Arial"]
        
        selected_font = "Arial" # デフォルトのフォールバック
        for font in font_priority:
            if font in available_fonts:
                selected_font = font
                break
        
        # フォントサイズを大きく調整
        self.DEFAULT_FONT = (selected_font, 10)
        self.BOLD_FONT = (selected_font, 11, "bold")
        self.TITLE_FONT = (selected_font, 12, "bold")
        
        # スタイル適用
        self.style.configure('TNotebook.Tab', font=self.BOLD_FONT)
        self.style.configure('TButton', font=self.BOLD_FONT)
        self.style.configure('TLabel', font=self.DEFAULT_FONT)
        self.style.configure('Title.TLabel', font=self.TITLE_FONT) # カスタムタイトルスタイル
        self.style.configure('TRadiobutton', font=self.DEFAULT_FONT)
        self.style.configure('TCheckbutton', font=self.DEFAULT_FONT) # チェックボタンのフォントも設定
        self.style.configure('TEntry', font=self.DEFAULT_FONT) # エントリーのフォントも設定
        self.style.configure('TLabelframe.Label', font=self.BOLD_FONT) # ラベルフレームのタイトル
    
    def _create_menu(self):
        """メニューバーの作成"""
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
        """ウィジェットの作成"""
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
        ttk.Button(button_frame, text="終了", # キャンセルではなく「終了」に
                   command=self._on_closing).pack(side="right", padx=5)
    
    def _create_data_source_tab(self):
        """データソースタブの作成"""
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
        """自動生成設定タブの作成"""
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
        """自動生成設定項目の追加"""
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
            validator=lambda x: InputValidator.validate_positive_int(x, "学生数")
        )
        self.entries["num_students"].pack(fill="x", padx=10, pady=2)
        
        # 倍率設定
        self.entries["magnification"] = CustomEntryFrame(
            parent, "各セミナーの倍率 (JSON形式)", 
            self.defaults["magnification"], width=40,
            tooltip='例: {"a": 2.0, "d": 3.0}',
            validator=lambda x: InputValidator.validate_json_dict(x, "倍率")
        )
        self.entries["magnification"].pack(fill="x", padx=10, pady=2)
        
        # 定員設定
        capacity_frame = ttk.LabelFrame(parent, text="定員設定", padding=5)
        capacity_frame.pack(fill="x", padx=10, pady=5)
        
        self.entries["min_size"] = CustomEntryFrame(
            capacity_frame, "最小定員", 
            str(self.defaults["min_size"]), width=10,
            validator=lambda x: InputValidator.validate_positive_int(x, "最小定員")
        )
        self.entries["min_size"].pack(fill="x", pady=2)
        
        self.entries["max_size"] = CustomEntryFrame(
            capacity_frame, "最大定員", 
            str(self.defaults["max_size"]), width=10,
            validator=lambda x: InputValidator.validate_positive_int(x, "最大定員")
        )
        self.entries["max_size"].pack(fill="x", pady=2)
        
        # q_boost_probability
        self.entries["q_boost_probability"] = CustomEntryFrame(
            parent, "'q'セミナーの希望ブースト確率 (0.0～1.0)",
            str(self.defaults["q_boost_probability"]), width=10,
            tooltip="Qセミナーを第一希望にする確率を高めます",
            validator=lambda x: InputValidator.validate_range_float(x, "ブースト確率", 0.0, 1.0)
        )
        self.entries["q_boost_probability"].pack(fill="x", padx=10, pady=2)

        # num_preferences_to_consider
        self.entries["num_preferences_to_consider"] = CustomEntryFrame(
            parent, "第何希望まで考慮するか",
            str(self.defaults["num_preferences_to_consider"]), width=10,
            tooltip="スコア計算で考慮する希望順位の深さ",
            validator=lambda x: InputValidator.validate_positive_int(x, "希望考慮数")
        )
        self.entries["num_preferences_to_consider"].pack(fill="x", padx=10, pady=2)
    
    def _create_optimization_tab(self):
        """最適化設定タブの作成"""
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
        """最適化設定項目の追加"""
        ttk.Label(parent, text="アルゴリズム設定", style="Title.TLabel").pack(pady=10)
        
        # 最適化戦略の選択
        strategy_frame = ttk.LabelFrame(parent, text="最適化戦略", padding=5)
        strategy_frame.pack(fill="x", padx=10, pady=5)
        
        self.optimization_strategy_var = tk.StringVar(value=self.config_manager.get_setting("optimization_strategy", "Greedy_LS"))
        
        ttk.Radiobutton(strategy_frame, text="貪欲法＋局所探索 (Greedy + Local Search)", 
                        variable=self.optimization_strategy_var, value="Greedy_LS").pack(anchor="w", pady=2)
        ttk.Radiobutton(strategy_frame, text="遺伝的アルゴリズム＋局所探索 (Genetic Algorithm + Local Search)", 
                        variable=self.optimization_strategy_var, value="GA_LS").pack(anchor="w", pady=2)
        ttk.Radiobutton(strategy_frame, text="整数線形計画法 (ILP) - 開発中", 
                        variable=self.optimization_strategy_var, value="ILP").pack(anchor="w", pady=2)
        ttk.Radiobutton(strategy_frame, text="制約プログラミング (CP-SAT) - 開発中", 
                        variable=self.optimization_strategy_var, value="CP").pack(anchor="w", pady=2)
        ttk.Radiobutton(strategy_frame, text="多段階最適化 - 開発中", 
                        variable=self.optimization_strategy_var, value="Multilevel").pack(anchor="w", pady=2)

        # 基本パラメータ
        basic_frame = ttk.LabelFrame(parent, text="基本パラメータ", padding=5)
        basic_frame.pack(fill="x", padx=10, pady=5)
        
        self.entries["num_patterns"] = CustomEntryFrame(
            basic_frame, "試行回数 / 世代数", # テキストを更新
            str(self.defaults["num_patterns"]), width=15,
            tooltip="Greedy+LS: 試行する割当パターンの数\nGA+LS: 遺伝的アルゴリズムの世代数"
        )
        self.entries["num_patterns"].pack(fill="x", pady=2)
        
        self.entries["max_workers"] = CustomEntryFrame(
            basic_frame, "並列処理数", 
            str(self.defaults["max_workers"]), width=10,
            tooltip="同時に実行する処理数（CPUコア数以下推奨）",
            validator=lambda x: InputValidator.validate_positive_int(x, "並列処理数")
        )
        self.entries["max_workers"].pack(fill="x", pady=2)
        
        # 焼きなまし法設定 (局所探索用)
        self.sa_frame = ttk.LabelFrame(parent, text="局所探索 (焼きなまし法) 設定", padding=5) # テキストを更新
        self.sa_frame.pack(fill="x", padx=10, pady=5)

        self.entries["local_search_iterations"] = CustomEntryFrame(
            self.sa_frame, "局所探索反復回数",
            str(self.defaults["local_search_iterations"]), width=10,
            tooltip="各パターンまたはGA個体における局所探索の反復回数",
            validator=lambda x: InputValidator.validate_positive_int(x, "局所探索反復回数")
        )
        self.entries["local_search_iterations"].pack(fill="x", pady=2)
        
        self.entries["initial_temperature"] = CustomEntryFrame(
            self.sa_frame, "初期温度", 
            str(self.defaults["initial_temperature"]), width=10,
            tooltip="焼きなまし法の初期温度",
            validator=lambda x: InputValidator.validate_positive_float(x, "初期温度")
        )
        self.entries["initial_temperature"].pack(fill="x", pady=2)
        
        self.entries["cooling_rate"] = CustomEntryFrame(
            self.sa_frame, "冷却率", 
            str(self.defaults["cooling_rate"]), width=10,
            tooltip="温度の冷却率 (0.0より大きく1.0未満推奨)",
            validator=lambda x: InputValidator.validate_range_float(x, "冷却率", 0.00001, 0.99999)
        )
        self.entries["cooling_rate"].pack(fill="x", pady=2)

        # 遺伝的アルゴリズム (GA) 設定
        self.ga_frame = ttk.LabelFrame(parent, text="遺伝的アルゴリズム (GA) 設定", padding=5)
        # self.ga_frame.pack(fill="x", padx=10, pady=5) # 初期状態では非表示にするため、ここではpackしない

        self.entries["ga_population_size"] = CustomEntryFrame(
            self.ga_frame, "個体数",
            str(self.defaults["ga_population_size"]), width=10,
            tooltip="GAの個体群のサイズ",
            validator=lambda x: InputValidator.validate_positive_int(x, "個体数"),
            entry_state="disabled" # 初期状態は無効
        )
        self.entries["ga_population_size"].pack(fill="x", pady=2)

        self.entries["ga_crossover_rate"] = CustomEntryFrame(
            self.ga_frame, "交叉率 (0.0～1.0)",
            str(self.defaults["ga_crossover_rate"]), width=10,
            tooltip="交叉が発生する確率",
            validator=lambda x: InputValidator.validate_range_float(x, "交叉率", 0.0, 1.0),
            entry_state="disabled" # 初期状態は無効
        )
        self.entries["ga_crossover_rate"].pack(fill="x", pady=2)

        self.entries["ga_mutation_rate"] = CustomEntryFrame(
            self.ga_frame, "突然変異率 (0.0～1.0)",
            str(self.defaults["ga_mutation_rate"]), width=10,
            tooltip="突然変異が発生する確率",
            validator=lambda x: InputValidator.validate_range_float(x, "突然変異率", 0.0, 1.0),
            entry_state="disabled" # 初期状態は無効
        )
        self.entries["ga_mutation_rate"].pack(fill="x", pady=2)
        
        # スコア重み設定
        weight_frame = ttk.LabelFrame(parent, text="希望順位の重み", padding=5)
        weight_frame.pack(fill="x", padx=10, pady=5)
        
        for rank, key in [("1位希望", "preference_weights_1st"), 
                          ("2位希望", "preference_weights_2nd"), 
                          ("3位希望", "preference_weights_3rd")]:
            self.entries[key] = CustomEntryFrame(
                weight_frame, f"{rank}の重み", 
                str(self.defaults[key]), width=10,
                validator=lambda x: InputValidator.validate_positive_float(x, f"{rank}重み")
            )
            self.entries[key].pack(fill="x", pady=2)
    
    def _create_advanced_tab(self):
        """高度な設定タブの作成"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="高度な設定")
        
        ttk.Label(frame, text="高度な設定", style="Title.TLabel").pack(pady=10)
        
        # ログ設定
        log_frame = ttk.LabelFrame(frame, text="ログ設定", padding=5)
        log_frame.pack(fill="x", padx=10, pady=5)
        
        self.log_enabled = tk.BooleanVar(value=self.config_manager.get_setting("log_enabled", True))
        ttk.Checkbutton(log_frame, text="詳細ログを出力", 
                        variable=self.log_enabled).pack(anchor="w")
        
        self.save_intermediate = tk.BooleanVar(value=self.config_manager.get_setting("save_intermediate", False))
        ttk.Checkbutton(log_frame, text="中間結果を保存", 
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
            tooltip="スコア改善がこの閾値以下の場合に早期終了",
            validator=lambda x: InputValidator.validate_positive_float(x, "早期終了閾値")
        )
        self.entries["early_stop_threshold"].pack(fill="x", pady=2)

        self.entries["no_improvement_limit"] = CustomEntryFrame(
            early_stop_frame, "改善なし制限",
            str(self.defaults["no_improvement_limit"]), width=10,
            tooltip="この回数だけ改善がない場合に早期終了",
            validator=lambda x: InputValidator.validate_positive_int(x, "改善なし制限")
        )
        self.entries["no_improvement_limit"].pack(fill="x", pady=2)

    def _toggle_strategy_parameters(self, *args):
        """最適化戦略に応じてパラメータの表示/非表示、有効/無効を切り替えます。"""
        selected_strategy = self.optimization_strategy_var.get()
        
        # GAパラメータの表示/非表示と有効/無効
        if selected_strategy == "GA_LS":
            self.ga_frame.pack(fill="x", padx=10, pady=5)
            for key in ["ga_population_size", "ga_crossover_rate", "ga_mutation_rate"]:
                self.entries[key].configure_state("normal")
            # GA選択時は焼きなまし法の設定も有効
            self.sa_frame.pack(fill="x", padx=10, pady=5)
            for key in ["local_search_iterations", "initial_temperature", "cooling_rate"]:
                self.entries[key].configure_state("normal")
        else:
            self.ga_frame.pack_forget() # フレームを非表示にする
            for key in ["ga_population_size", "ga_crossover_rate", "ga_mutation_rate"]:
                self.entries[key].configure_state("disabled") # 無効にする
            
            # Greedy_LSの場合は焼きなまし法の設定を有効にする
            if selected_strategy == "Greedy_LS":
                self.sa_frame.pack(fill="x", padx=10, pady=5)
                for key in ["local_search_iterations", "initial_temperature", "cooling_rate"]:
                    self.entries[key].configure_state("normal")
            else: # ILP, CP, Multilevelの場合は焼きなまし法の設定を無効にする
                self.sa_frame.pack_forget()
                for key in ["local_search_iterations", "initial_temperature", "cooling_rate"]:
                    self.entries[key].configure_state("disabled")

    def _change_theme(self):
        """テーマの変更"""
        theme_name = self.theme_var.get()
        if theme_name in self.THEMES:
            try:
                self.style.theme_use(self.THEMES[theme_name])
            except tk.TclError:
                messagebox.showwarning("テーマエラー", f"テーマ '{theme_name}' は利用できません")
    
    def _load_saved_settings(self):
        """保存された設定の読み込み"""
        # CustomEntryFrameの値を更新
        for key, entry_widget in self.entries.items():
            if hasattr(entry_widget, 'set'):  # CustomEntryFrameの場合
                # ConfigManagerから設定を読み込み、デフォルト値も考慮
                saved_value = self.config_manager.get_setting(key, self.defaults.get(key))
                if saved_value is not None:
                    # JSON文字列の場合はそのまま、辞書の場合はJSON文字列に変換して設定
                    if key == "magnification" and isinstance(saved_value, dict):
                        entry_widget.set(json.dumps(saved_value, ensure_ascii=False))
                    else:
                        entry_widget.set(str(saved_value))
                # 読み込み後にバリデーションをトリガーして表示を更新
                entry_widget._validate() 
        
        # BooleanVarとStringVarの値を更新
        self.log_enabled.set(self.config_manager.get_setting("log_enabled", self.defaults["log_enabled"]))
        self.save_intermediate.set(self.config_manager.get_setting("save_intermediate", self.defaults["save_intermediate"]))
        self.theme_var.set(self.config_manager.get_setting("theme", self.defaults["theme"]))
        self.data_source_var.set(self.config_manager.get_setting("data_source", "auto"))
        self.config_file_path_var.set(self.config_manager.get_setting("config_file_path", ""))
        self.student_file_path_var.set(self.config_manager.get_setting("student_file_path", ""))
        self.optimization_strategy_var.set(self.config_manager.get_setting("optimization_strategy", "Greedy_LS"))


        # テーマを再適用してUIを更新
        self._change_theme()
        self._toggle_strategy_parameters() # GAパラメータの表示状態を再設定

    def _save_current_settings(self):
        """現在の設定を保存"""
        current_settings = {}
        for key, entry_widget in self.entries.items():
            if hasattr(entry_widget, 'get'):
                current_settings[key] = entry_widget.get()
        
        current_settings['log_enabled'] = self.log_enabled.get()
        current_settings['save_intermediate'] = self.save_intermediate.get()
        current_settings['theme'] = self.theme_var.get()
        current_settings['data_source'] = self.data_source_var.get()
        current_settings['config_file_path'] = self.config_file_path_var.get()
        current_settings['student_file_path'] = self.student_file_path_var.get()
        current_settings['optimization_strategy'] = self.optimization_strategy_var.get() # 新しい戦略設定

        self.config_manager.save_config(current_settings)
    
    def _import_settings(self):
        """設定ファイルをインポート"""
        file_path = filedialog.askopenfilename(
            title="設定ファイルを選択",
            filetypes=[("INIファイル", "*.ini")]
        )
        if file_path:
            self.config_manager = ConfigManager(file_path)
            self._load_saved_settings()
            messagebox.showinfo("インポート完了", "設定をインポートしました。")
    
    def _export_settings(self):
        """設定ファイルをエクスポート"""
        file_path = filedialog.asksaveasfilename(
            title="設定ファイルを保存",
            defaultextension=".ini",
            filetypes=[("INIファイル", "*.ini")]
        )
        if file_path:
            # 現在の設定を一時的に保存マネージャーに設定
            temp_config_manager = ConfigManager(file_path)
            current_settings = {}
            for key, entry_widget in self.entries.items():
                if hasattr(entry_widget, 'get'):
                    current_settings[key] = entry_widget.get()
            current_settings['log_enabled'] = self.log_enabled.get()
            current_settings['save_intermediate'] = self.save_intermediate.get()
            current_settings['theme'] = self.theme_var.get()
            current_settings['data_source'] = self.data_source_var.get()
            current_settings['config_file_path'] = self.config_file_path_var.get()
            current_settings['student_file_path'] = self.student_file_path_var.get()
            current_settings['optimization_strategy'] = self.optimization_strategy_var.get() # 新しい戦略設定
            
            temp_config_manager.save_config(current_settings)
            
            messagebox.showinfo("エクスポート完了", "設定をエクスポートしました。")
    
    def _reset_to_defaults(self):
        """デフォルト値にリセット"""
        if not messagebox.askyesno("確認", "全ての設定をデフォルト値に戻しますか？"):
            return

        for key, entry_widget in self.entries.items():
            if hasattr(entry_widget, 'set'):
                default_value = self.defaults.get(key)
                # JSON文字列の場合は変換して設定
                if key == "magnification" and isinstance(default_value, dict):
                    entry_widget.set(json.dumps(default_value, ensure_ascii=False))
                else:
                    entry_widget.set(str(default_value))
                entry_widget._validate() # バリデーション表示を更新
        
        self.log_enabled.set(self.defaults["log_enabled"])
        self.save_intermediate.set(self.defaults["save_intermediate"])
        self.theme_var.set(self.defaults["theme"])
        self.data_source_var.set(self.defaults["data_source"])
        self.config_file_path_var.set(self.defaults["config_file_path"])
        self.student_file_path_var.set(self.defaults["student_file_path"])
        self.optimization_strategy_var.set(self.defaults["optimization_strategy"])

        self._change_theme()
        self._toggle_strategy_parameters() # GAパラメータの表示状態を再設定
        messagebox.showinfo("リセット完了", "設定をデフォルト値に戻しました。")
    
    def _show_help(self):
        """ヘルプを表示"""
        help_text = (
            "【使い方】\n"
            "・「データソース」タブで使用するデータ（自動生成/手動）を選択します。\n"
            "・「自動生成設定」タブで、学生数やセミナー情報などのパラメータを設定します。\n"
            "・「最適化設定」タブで、アルゴリズムの動作に関するパラメータを調整します。\n"
            "  - 「最適化戦略」で「貪欲法＋局所探索」または「遺伝的アルゴリズム＋局所探索」を選択できます。\n"
            "  - 選択した戦略に応じて、関連するパラメータが表示されます。\n"
            "・「高度な設定」タブで、ログ出力やテーマなどを設定できます。\n"
            "・画面下部の「最適化を実行」ボタンで処理を開始します。\n"
            "・メニューバーの「ファイル」から設定のインポート/エクスポートが可能です。\n"
            "\n"
            "より詳しい情報は、同梱のREADMEファイルをご覧ください。"
        )
        messagebox.showinfo("使用方法", help_text)
    
    def _show_about(self):
        """アプリ情報を表示"""
        about_text = (
            "セミナー割当最適化ツール v2.0\n"
            "このツールは、学生の希望とセミナーの定員を考慮し、\n"
            "最適なセミナー割当を探索するためのものです。\n"
            "開発者: あなたの名前\n" # ここにあなたの名前を入れてください
            f"最終更新: {datetime.now().strftime('%Y年%m月%d日')}\n"
            "© 2025"
        )
        messagebox.showinfo("このアプリについて", about_text)
    
    def _select_config_file(self):
        """設定ファイル選択"""
        file_path = filedialog.askopenfilename(
            title="設定ファイルを選択",
            filetypes=[("JSONファイル", "*.json"), ("全てのファイル", "*.*")]
        )
        if file_path:
            self.config_file_path_var.set(file_path)
    
    def _select_student_file(self):
        """学生データファイル選択"""
        file_path = filedialog.askopenfilename(
            title="学生データファイルを選択",
            filetypes=[("CSVファイル", "*.csv"), ("全てのファイル", "*.*")]
        )
        if file_path:
            self.student_file_path_var.set(file_path)
    
    def _load_preset(self):
        """プリセットの読み込み"""
        file_path = filedialog.askopenfilename(
            title="プリセットファイルを選択",
            filetypes=[("JSONファイル", "*.json")]
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    preset_data = json.load(f)
                
                for key, value in preset_data.items():
                    if key in self.entries and hasattr(self.entries[key], 'set'):
                        # JSON文字列の場合はそのまま、辞書の場合はJSON文字列に変換して設定
                        if key == "magnification" and isinstance(value, dict):
                            self.entries[key].set(json.dumps(value, ensure_ascii=False))
                        else:
                            self.entries[key].set(str(value))
                        self.entries[key]._validate()
                    elif key == "log_enabled":
                        self.log_enabled.set(bool(value))
                    elif key == "save_intermediate":
                        self.save_intermediate.set(bool(value))
                    elif key == "theme":
                        self.theme_var.set(str(value))
                        self._change_theme()
                    elif key == "data_source":
                        self.data_source_var.set(str(value))
                    elif key == "config_file_path":
                        self.config_file_path_var.set(str(value))
                    elif key == "student_file_path":
                        self.student_file_path_var.set(str(value))
                    elif key == "optimization_strategy": # 新しい戦略設定
                        self.optimization_strategy_var.set(str(value))
                
                self._toggle_strategy_parameters() # GAパラメータの表示状態を更新
                messagebox.showinfo("プリセット", "プリセットを読み込みました。")
            except Exception as e:
                messagebox.showerror("エラー", f"プリセットの読み込みに失敗しました: {e}")
    
    def _save_preset(self):
        """プリセットの保存"""
        preset_data = {}
        for key, entry in self.entries.items():
            # JSON文字列に変換して保存
            if key == "magnification":
                try:
                    preset_data[key] = json.loads(entry.get())
                except json.JSONDecodeError:
                    preset_data[key] = entry.get() # 無効なJSONの場合はそのまま文字列として保存
            else:
                preset_data[key] = entry.get()
        
        preset_data['log_enabled'] = self.log_enabled.get()
        preset_data['save_intermediate'] = self.save_intermediate.get()
        preset_data['theme'] = self.theme_var.get()
        preset_data['data_source'] = self.data_source_var.get()
        preset_data['config_file_path'] = self.config_file_path_var.get()
        preset_data['student_file_path'] = self.student_file_path_var.get()
        preset_data['optimization_strategy'] = self.optimization_strategy_var.get() # 新しい戦略設定

        file_path = filedialog.asksaveasfilename(
            title="プリセットを保存",
            defaultextension=".json",
            filetypes=[("JSONファイル", "*.json")]
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(preset_data, f, ensure_ascii=False, indent=4)
                messagebox.showinfo("プリセット", "プリセットを保存しました。")
            except Exception as e:
                messagebox.showerror("エラー", f"プリセットの保存に失敗しました: {e}")
    
    def _on_run_button_click(self):
        """最適化実行"""
        # 全てのCustomEntryFrameのバリデーションを強制的に実行
        all_valid = True
        for key, entry_widget in self.entries.items():
            # 無効なエントリーはバリデーションをスキップ
            if entry_widget.entry.cget("state") == "disabled":
                continue

            if hasattr(entry_widget, '_validate'):
                if not entry_widget._validate():
                    all_valid = False
                    # エラーのあるタブに切り替える
                    if key in ["seminars", "num_students", "magnification", "min_size", "max_size", "q_boost_probability", "num_preferences_to_consider"]:
                        self.notebook.select(0) # データソースタブ
                    elif key in ["num_patterns", "max_workers", "local_search_iterations", "initial_temperature", "cooling_rate", "preference_weights_1st", "preference_weights_2nd", "preference_weights_3rd", "ga_population_size", "ga_crossover_rate", "ga_mutation_rate"]:
                        self.notebook.select(2) # 最適化設定タブ
                    elif key in ["early_stop_threshold", "no_improvement_limit"]:
                        self.notebook.select(3) # 高度な設定タブ
                    break # 最初に見つかったエラーで中断

        if not all_valid:
            messagebox.showerror("入力エラー", "入力値にエラーがあります。赤色の✗マークを確認してください。")
            return

        try:
            # 手動データ選択時のファイルパスの存在チェック
            if self.data_source_var.get() == "manual":
                config_file = self.config_file_path_var.get()
                student_file = self.student_file_path_var.get()
                if not os.path.exists(config_file):
                    messagebox.showerror("ファイルエラー", f"設定ファイルが見つかりません: {config_file}")
                    return
                if not os.path.exists(student_file):
                    messagebox.showerror("ファイルエラー", f"学生データファイルが見つかりません: {student_file}")
                    return

            self._save_current_settings() # 実行前に現在の設定を保存
            
            # ここに実際の最適化処理を呼び出す
            self.progress_dialog = ProgressDialog(self.root, "最適化処理中...")
            
            # 全ての設定を辞書として取得
            all_settings = {}
            for key, entry_widget in self.entries.items():
                # 無効なエントリーの値は取得しない
                if entry_widget.entry.cget("state") == "disabled":
                    continue

                if hasattr(entry_widget, 'get'):
                    value = entry_widget.get()
                    if key == "magnification":
                        all_settings[key] = json.loads(value) # JSON文字列を辞書に変換
                    elif key == "seminars":
                        all_settings[key] = [s.strip() for s in value.split(',') if s.strip()]
                    elif key.startswith("preference_weights_"):
                        all_settings[key] = float(value)
                    elif key in ["num_students", "min_size", "max_size", "num_patterns", "max_workers", 
                                 "local_search_iterations", "no_improvement_limit", "num_preferences_to_consider",
                                 "ga_population_size"]:
                        all_settings[key] = int(value)
                    elif key in ["q_boost_probability", "initial_temperature", "cooling_rate", "early_stop_threshold",
                                 "ga_crossover_rate", "ga_mutation_rate"]:
                        all_settings[key] = float(value)
                    else:
                        all_settings[key] = value
            
            all_settings['log_enabled'] = self.log_enabled.get()
            all_settings['save_intermediate'] = self.save_intermediate.get()
            all_settings['theme'] = self.theme_var.get()
            all_settings['data_source'] = self.data_source_var.get()
            all_settings['config_file_path'] = self.config_file_path_var.get()
            all_settings['student_file_path'] = self.student_file_path_var.get()
            all_settings['optimization_strategy'] = self.optimization_strategy_var.get()

            # 最適化処理を実行するスレッドを開始
            threading.Thread(target=self._start_optimization_thread, args=(all_settings,)).start()

            # ここでダイアログが表示されるので、メッセージボックスは不要
            # messagebox.showinfo("最適化開始", "最適化処理を開始します。\n別ウィンドウで進捗を表示します。\n処理が完了するまでお待ちください。")
            
        except ValidationError as e:
            messagebox.showerror("入力エラー", str(e))
        except json.JSONDecodeError as e:
            messagebox.showerror("入力エラー", f"JSON形式が不正です: {e}")
        except Exception as e:
            messagebox.showerror("予期せぬエラー", f"予期せぬエラーが発生しました: {e}")
            if hasattr(self, 'progress_dialog') and self.progress_dialog.dialog.winfo_exists():
                self.progress_dialog.close()

    def _start_optimization_thread(self, settings: Dict[str, Any]):
        """最適化処理を別スレッドで実行するためのラッパー"""
        try:
            # main.pyのSeminarOptimizerとConfigを動的にインポート
            # これにより、循環参照を回避しつつ、GUIからメインロジックを呼び出せる
            from main import SeminarOptimizer, Config
            from utils import PreferenceGenerator

            # Configオブジェクトを再構築
            initial_config = Config(
                seminars=settings.get('seminars', []),
                magnification=settings.get('magnification', {}),
                min_size=settings.get('min_size', 5),
                max_size=settings.get('max_size', 10),
                num_students=settings.get('num_students', 112),
                q_boost_probability=settings.get('q_boost_probability', 0.2),
                num_patterns=settings.get('num_patterns', 200000),
                max_workers=settings.get('max_workers', 8),
                local_search_iterations=settings.get('local_search_iterations', 500),
                initial_temperature=float(settings.get('initial_temperature', 1.0)),
                cooling_rate=float(settings.get('cooling_rate', 0.995)),
                preference_weights=settings.get('preference_weights', {}),
                optimization_strategy=settings.get('optimization_strategy', "Greedy_LS"),
                ga_population_size=settings.get('ga_population_size', 100),
                ga_crossover_rate=float(settings.get('ga_crossover_rate', 0.8)),
                ga_mutation_rate=float(settings.get('ga_mutation_rate', 0.05)),
                # ILP/CP/MultilevelのパラメータもConfigに渡す
                ilp_time_limit=settings.get('ilp_time_limit', 300),
                cp_time_limit=settings.get('cp_time_limit', 300),
                multilevel_clusters=settings.get('multilevel_clusters', 5)
            )

            all_students = []
            data_source_choice = settings.get("data_source", "auto")

            if data_source_choice == 'manual':
                config_file_path = settings.get('config_file_path')
                students_file_path = settings.get('student_file_path')

                try:
                    # seminar_config.json の内容を読み込み、Configオブジェクトを更新
                    with open(config_file_path, 'r', encoding='utf-8') as f:
                        seminar_settings_from_file = json.load(f)
                    
                    # ファイルからの設定でConfigを上書き（GUI設定より優先）
                    initial_config.seminars = seminar_settings_from_file.get('seminars', initial_config.seminars)
                    initial_config.magnification = seminar_settings_from_file.get('magnification', initial_config.magnification)
                    initial_config.min_size = seminar_settings_from_file.get('min_size', initial_config.min_size)
                    initial_config.max_size = seminar_settings_from_file.get('max_size', initial_config.max_size)
                    initial_config.q_boost_probability = seminar_settings_from_file.get('q_boost_probability', initial_config.q_boost_probability)
                    initial_config.num_patterns = seminar_settings_from_file.get('num_patterns', initial_config.num_patterns)
                    initial_config.max_workers = seminar_settings_from_file.get('max_workers', initial_config.max_workers)
                    initial_config.local_search_iterations = seminar_settings_from_file.get('local_search_iterations', initial_config.local_search_iterations)
                    initial_config.initial_temperature = seminar_settings_from_file.get('initial_temperature', initial_config.initial_temperature)
                    initial_config.cooling_rate = seminar_settings_from_file.get('cooling_rate', initial_config.cooling_rate)
                    initial_config.preference_weights = seminar_settings_from_file.get('preference_weights', initial_config.preference_weights)
                    initial_config.optimization_strategy = seminar_settings_from_file.get('optimization_strategy', initial_config.optimization_strategy)
                    initial_config.ga_population_size = seminar_settings_from_file.get('ga_population_size', initial_config.ga_population_size)
                    initial_config.ga_crossover_rate = seminar_settings_from_file.get('ga_crossover_rate', initial_config.ga_crossover_rate)
                    initial_config.ga_mutation_rate = seminar_settings_from_file.get('ga_mutation_rate', initial_config.ga_mutation_rate)
                    initial_config.ilp_time_limit = seminar_settings_from_file.get('ilp_time_limit', initial_config.ilp_time_limit)
                    initial_config.cp_time_limit = seminar_settings_from_file.get('cp_time_limit', initial_config.cp_time_limit)
                    initial_config.multilevel_clusters = seminar_settings_from_file.get('multilevel_clusters', initial_config.multilevel_clusters)

                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror("ファイル読み込みエラー", f"設定ファイルの読み込みに失敗しました: {e}"))
                    self.root.after(0, self.progress_dialog.close)
                    return
                
                preference_generator = PreferenceGenerator(asdict(initial_config)) 
                try:
                    all_students = preference_generator.load_preferences_from_csv(students_file_path)
                    initial_config.num_students = len(all_students) # CSVから読み込んだ学生数で更新
                except Exception as e:
                    self.root.after(0, lambda: messagebox.showerror("ファイル読み込みエラー", f"学生データファイルの読み込みに失敗しました: {e}"))
                    self.root.after(0, self.progress_dialog.close)
                    return

            elif data_source_choice == 'auto':
                preference_generator = PreferenceGenerator(asdict(initial_config))
                all_students = preference_generator.generate_realistic_preferences(42)
                initial_config.num_students = len(all_students)

            # SeminarOptimizerをインスタンス化し、進捗コールバックを渡す
            optimizer = SeminarOptimizer(initial_config, all_students, self.progress_dialog.update_message)
            
            # 最適化を実行
            best_pattern_sizes, overall_best_score, final_assignments = optimizer.run_optimization()

            # 結果をGUIスレッドで表示
            self.root.after(0, lambda: self._show_optimization_results(best_pattern_sizes, overall_best_score, final_assignments))
            
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("最適化エラー", f"最適化中にエラーが発生しました: {e}"))
        finally:
            # 処理が完了したらダイアログを閉じる
            if hasattr(self, 'progress_dialog') and self.progress_dialog.dialog.winfo_exists():
                self.root.after(0, self.progress_dialog.close)

    def _show_optimization_results(self, best_pattern_sizes: Dict[str, int], overall_best_score: float, final_assignments: Dict[str, List[Tuple[int, float]]]):
        """最適化結果をメッセージボックスで表示します。"""
        if not best_pattern_sizes or not final_assignments:
            messagebox.showinfo("最適化結果", "最適化は完了しましたが、有効な結果が得られませんでした。ログを確認してください。")
            return

        result_message = f"最適化が完了しました！\n\n"
        result_message += f"最終スコア: {overall_best_score:.2f}\n\n"
        result_message += "各セミナーの目標定員:\n"
        for sem, size in best_pattern_sizes.items():
            result_message += f"  セミナー {sem.upper()}: {size}人\n"
        
        # 割り当て詳細を簡潔に表示
        result_message += "\n最終割り当ての概要:\n"
        for sem_name, assigned_students in final_assignments.items():
            result_message += f"  セミナー {sem_name.upper()}: {len(assigned_students)}人\n"
        
        messagebox.showinfo("最適化結果", result_message)

    def _on_closing(self):
        """ウィンドウを閉じる際の処理"""
        self._save_current_settings()
        if hasattr(self, 'progress_dialog') and self.progress_dialog.dialog.winfo_exists():
            self.progress_dialog.cancel() # 実行中の最適化があればキャンセル
        self.root.destroy()

def launch_gui_and_get_settings(default_seminars: List[str], default_magnification: Dict[str, float], 
                                default_preference_weights: Dict[str, float]) -> Optional[Dict[str, Any]]:
    """GUIを起動し、ユーザーが設定した内容を辞書として返します。"""
    gui = SeminarOptimizationGUI(default_seminars, default_magnification, default_preference_weights)
    gui.root.mainloop() # GUIループを開始
    # GUIが閉じられた後、gui.settingsに保存された値が返される
    # _on_run_button_click で self.settings を更新するように変更する必要がある
    # または、_on_run_button_click で直接 self.root.destroy() を呼び出し、
    # result_settings をインスタンス変数として保持し、それを返すようにする
    return gui.settings # GUIが閉じられたときに設定を返す
