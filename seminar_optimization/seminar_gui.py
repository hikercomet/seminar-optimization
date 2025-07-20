import tkinter as tk
from tkinter import ttk, messagebox, filedialog, scrolledtext
import json
import os
import sys
import threading
from datetime import datetime
import configparser
from typing import Dict, List, Any, Optional, Callable, Tuple
import ctypes # DPI設定用
import tkinter.font # Tkinterのフォントをチェックするためにインポート
import csv # CSV読み込み用
import time # シミュレーションの進捗表示のために追加

# sys.pathに現在のディレクトリ（プロジェクトルート）を追加し、
# seminar_optimizationパッケージを見つけられるようにする
# このスクリプトが SEMINAR_OPTIMIZATION/seminar_gui.py にある場合、
# プロジェクトルートは現在のディレクトリ。
# seminar_optimization/optimizer_service.py はそのサブディレクトリにある。
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

# optimizer_serviceをインポート
try:
    # 実際の環境に合わせてパスを調整してください。
    # 例: from .seminar_optimization.optimizer_service import run_optimization_service
    # または、optimizer_service.py が直接 seminar_gui.py と同じディレクトリにある場合
    # from optimizer_service import run_optimization_service

    # ここでは、提供されたパス構造を尊重し、seminar_optimizationパッケージ内にあると仮定します。
    # この行は、実際のプロジェクト構造に合わせて調整が必要です。
    # 例: from seminar_optimization.optimizer_service import run_optimization_service
    # デモンストレーションのため、仮の関数を定義します。
    # 実際の環境では、optimizer_service.py からインポートしてください。
    # from seminar_optimization.optimizer_service import run_optimization_service
    
    # デモンストレーション用のダミー関数
    def run_optimization_service(params, progress_callback=None, cancel_event=None):
        """
        最適化サービスをシミュレートするダミー関数。
        実際のアプリケーションでは、optimizer_service.py の実際の関数に置き換えます。
        """
        print(f"最適化サービス実行開始 (ダミー): {params}")
        total_steps = 100
        for i in range(total_steps):
            if cancel_event and cancel_event.is_set():
                print("最適化サービスがキャンセルされました (ダミー)。")
                return {"status": "cancelled", "message": "最適化がキャンセルされました。"}
            
            progress_message = f"処理中... {i+1}/{total_steps} ステップ"
            if progress_callback:
                progress_callback(progress_message)
            time.sleep(0.05) # シミュレーションのための短い遅延
        
        # ダミーの結果を返す
        return {
            "status": "success",
            "message": "最適化が完了しました！ (ダミー)",
            "best_score": 98.76,
            "best_assignment": {
                "学生A": "セミナーX",
                "学生B": "セミナーY",
                "学生C": "セミナーZ"
            },
            "seminar_capacities": {
                "セミナーX": 10,
                "セミナーY": 12,
                "セミナーZ": 8
            },
            "unassigned_students": []
        }

except ImportError as e:
    messagebox.showerror("エラー", f"最適化サービスモジュールのインポートに失敗しました。seminar_optimization/optimizer_service.py が存在し、パスが正しいことを確認してください。\n詳細: {e}")
    sys.exit(1)

# --- 既存のユーティリティクラス ---
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

# --- セミナー最適化GUIクラス ---
class SeminarOptimizerGUI:
    """統合されたセミナー最適化GUI"""
    
    # 定数定義
    WINDOW_WIDTH = 750 # ウィンドウ幅を拡大
    WINDOW_HEIGHT = 700 # ウィンドウ高さを拡大
    
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
        self.data_source_var.trace_add("write", self._toggle_data_source_fields)
        
        self._toggle_strategy_parameters() # 初期状態を設定
        self._toggle_data_source_fields() # 初期状態を設定

        self.optimization_thread = None # 最適化スレッドを保持する変数
        self.cancel_event = threading.Event() # 最適化をキャンセルするためのイベント
    
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
        self.root.minsize(500, 600) # 最小サイズを調整
        
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
        self._create_result_tab() # 結果タブを追加
        
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
        
        # 終了ボタン
        ttk.Button(button_frame, text="終了", 
                   command=self._on_closing).pack(side="right", padx=5)
    
    def _create_data_source_tab(self):
        """データソースタブの作成"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="データソース")
        
        ttk.Label(frame, text="データ入力方法", style="Title.TLabel").pack(pady=10)
        
        self.data_source_var = tk.StringVar(value=self.config_manager.get_setting("data_source", "auto"))
        
        radio_frame = ttk.LabelFrame(frame, text="選択してください", padding=10)
        radio_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Radiobutton(radio_frame, text="手動データを使用 (seminar_config.json & students_preferences.csv)", 
                        variable=self.data_source_var, value="manual").pack(anchor="w", pady=2)
        
        ttk.Radiobutton(radio_frame, text="自動生成データを使用", 
                        variable=self.data_source_var, value="auto").pack(anchor="w", pady=2)
        
        # ファイル選択フレーム
        self.file_selection_frame = ttk.LabelFrame(frame, text="ファイル選択 (手動データ使用時)", padding=10)
        self.file_selection_frame.pack(fill="x", padx=10, pady=5)
        
        self.config_file_path_var = tk.StringVar(value=self.config_manager.get_setting("config_file_path", ""))
        self.student_file_path_var = tk.StringVar(value=self.config_manager.get_setting("student_file_path", ""))

        ttk.Label(self.file_selection_frame, text="セミナー設定ファイル (JSON):").pack(anchor="w", padx=5)
        ttk.Entry(self.file_selection_frame, textvariable=self.config_file_path_var, state="readonly", width=60).pack(fill="x", pady=2, padx=5)
        ttk.Button(self.file_selection_frame, text="選択...", 
                   command=self._select_config_file).pack(fill="x", pady=2, padx=5)
        
        ttk.Label(self.file_selection_frame, text="学生希望データファイル (CSV):").pack(anchor="w", padx=5, pady=(10,0))
        ttk.Entry(self.file_selection_frame, textvariable=self.student_file_path_var, state="readonly", width=60).pack(fill="x", pady=2, padx=5)
        ttk.Button(self.file_selection_frame, text="選択...", 
                   command=self._select_student_file).pack(fill="x", pady=2, padx=5)
    
    def _toggle_data_source_fields(self, *args):
        """データソース選択に応じてファイル選択フィールドの表示/非表示を切り替える"""
        selected_source = self.data_source_var.get()
        if selected_source == "manual":
            self.file_selection_frame.pack(fill="x", padx=10, pady=5)
            # 自動生成タブを無効化 (notebookのタブは0から始まるインデックスで、データソース、自動生成、最適化、高度、結果の順)
            # 自動生成タブはインデックス1 (2番目)
            self.notebook.tab(1, state="disabled") 
        else: # "auto"の場合
            self.file_selection_frame.pack_forget()
            # 自動生成タブを有効化
            self.notebook.tab(1, state="normal") 

    def _select_config_file(self):
        """セミナー設定ファイルのパスを選択"""
        filepath = filedialog.askopenfilename(
            initialdir=os.getcwd(),
            title="セミナー設定JSONファイルを選択",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filepath:
            self.config_file_path_var.set(filepath)

    def _select_student_file(self):
        """学生希望データファイルのパスを選択"""
        filepath = filedialog.askopenfilename(
            initialdir=os.getcwd(),
            title="学生希望データCSVファイルを選択",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filepath:
            self.student_file_path_var.set(filepath)

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
                        variable=self.optimization_strategy_var, value="ILP", state="disabled").pack(anchor="w", pady=2)
        ttk.Radiobutton(strategy_frame, text="制約プログラミング (CP-SAT) - 開発中", 
                        variable=self.optimization_strategy_var, value="CP", state="disabled").pack(anchor="w", pady=2)
        ttk.Radiobutton(strategy_frame, text="多段階最適化 - 開発中", 
                        variable=self.optimization_strategy_var, value="Multilevel", state="disabled").pack(anchor="w", pady=2)

        # 基本パラメータ
        basic_frame = ttk.LabelFrame(parent, text="基本パラメータ", padding=5)
        basic_frame.pack(fill="x", padx=10, pady=5)
        
        self.entries["num_patterns"] = CustomEntryFrame(
            basic_frame, "試行回数 / 世代数", # テキストを更新
            str(self.defaults["num_patterns"]), width=15,
            tooltip="Greedy+LS: 試行する割当パターンの数\nGA+LS: 遺伝的アルゴリズムの世代数",
            validator=lambda x: InputValidator.validate_positive_int(x, "試行回数/世代数")
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
        ttk.Checkbutton(log_frame, text="中間結果を保存 (大規模データでは非推奨)",
                        variable=self.save_intermediate).pack(anchor="w")

        # 早期終了設定
        early_stop_frame = ttk.LabelFrame(frame, text="早期終了設定 (GA/Greedy+LS)", padding=5)
        early_stop_frame.pack(fill="x", padx=10, pady=5)

        self.entries["early_stop_threshold"] = CustomEntryFrame(
            early_stop_frame, "改善しきい値",
            str(self.defaults["early_stop_threshold"]), width=10,
            tooltip="スコア改善がこの値以下になった場合に早期終了を検討",
            validator=lambda x: InputValidator.validate_range_float(x, "改善しきい値", 0.0, 1.0)
        )
        self.entries["early_stop_threshold"].pack(fill="x", pady=2)

        self.entries["no_improvement_limit"] = CustomEntryFrame(
            early_stop_frame, "改善なしの許容世代数/回数",
            str(self.defaults["no_improvement_limit"]), width=10,
            tooltip="スコアが改善しない世代/試行がこの回数続いた場合に早期終了",
            validator=lambda x: InputValidator.validate_positive_int(x, "改善なしの許容回数")
        )
        self.entries["no_improvement_limit"].pack(fill="x", pady=2)

        # テーマ設定
        theme_frame = ttk.LabelFrame(frame, text="GUIテーマ", padding=5)
        theme_frame.pack(fill="x", padx=10, pady=5)

        self.theme_var = tk.StringVar(value=self.config_manager.get_setting("theme", "デフォルト"))
        theme_options = list(self.THEMES.keys())
        theme_dropdown = ttk.OptionMenu(theme_frame, self.theme_var, self.theme_var.get(), *theme_options, command=self._apply_theme)
        theme_dropdown.pack(fill="x", pady=5)

    def _create_result_tab(self):
        """結果表示タブの作成"""
        frame = ttk.Frame(self.notebook)
        self.notebook.add(frame, text="結果")

        ttk.Label(frame, text="最適化結果", style="Title.TLabel").pack(pady=10)

        # 結果表示用のScrolledText
        self.result_text = scrolledtext.ScrolledText(frame, wrap=tk.WORD, width=80, height=20, font=self.DEFAULT_FONT)
        self.result_text.pack(fill="both", expand=True, padx=10, pady=5)
        self.result_text.config(state="disabled") # 読み取り専用に設定

        # 結果保存ボタン
        ttk.Button(frame, text="結果を保存", command=self._save_results).pack(pady=5)

    def _apply_theme(self, selected_theme_name: str):
        """選択されたテーマを適用"""
        theme_to_use = self.THEMES.get(selected_theme_name)
        if theme_to_use and theme_to_use in self.style.theme_names():
            self.style.theme_use(theme_to_use)
            # フォント設定を再適用して、新しいテーマに合わせた見た目を維持
            self._configure_ttk_styles()
        else:
            messagebox.showwarning("テーマエラー", f"テーマ '{selected_theme_name}' は利用できません。")
    
    def _load_saved_settings(self):
        """保存された設定をGUIに読み込み"""
        for key, entry_frame in self.entries.items():
            saved_value = self.config_manager.get_setting(key, self.defaults[key])
            if key == "magnification": # magnificationはJSON文字列として保存されているため、辞書に変換
                if isinstance(saved_value, dict):
                    entry_frame.set(json.dumps(saved_value, ensure_ascii=False))
                else:
                    entry_frame.set(str(saved_value))
            else:
                entry_frame.set(str(saved_value))
        
        # BooleanVarの値を設定
        self.log_enabled.set(self.config_manager.get_setting("log_enabled", self.defaults["log_enabled"]))
        self.save_intermediate.set(self.config_manager.get_setting("save_intermediate", self.defaults["save_intermediate"]))
        self.data_source_var.set(self.config_manager.get_setting("data_source", self.defaults["optimization_strategy"]))
        self.optimization_strategy_var.set(self.config_manager.get_setting("optimization_strategy", self.defaults["optimization_strategy"]))
        self.config_file_path_var.set(self.config_manager.get_setting("config_file_path", self.defaults["config_file_path"]))
        self.student_file_path_var.set(self.config_manager.get_setting("student_file_path", self.defaults["student_file_path"]))
        self.theme_var.set(self.config_manager.get_setting("theme", self.defaults["theme"]))

        # ロード後に各トグル関数を呼び出してUIの状態を同期
        self._toggle_strategy_parameters()
        self._toggle_data_source_fields()

    def _save_current_settings(self):
        """現在のGUI設定を保存"""
        current_settings = {}
        for key, entry_frame in self.entries.items():
            value = entry_frame.get()
            # 倍率設定はJSON文字列として保存
            if key == "magnification":
                try:
                    current_settings[key] = json.loads(value)
                except json.JSONDecodeError:
                    current_settings[key] = self.defaults[key] # 無効な場合はデフォルトに戻す
            else:
                current_settings[key] = value
        
        current_settings["log_enabled"] = self.log_enabled.get()
        current_settings["save_intermediate"] = self.save_intermediate.get()
        current_settings["data_source"] = self.data_source_var.get()
        current_settings["optimization_strategy"] = self.optimization_strategy_var.get()
        current_settings["config_file_path"] = self.config_file_path_var.get()
        current_settings["student_file_path"] = self.student_file_path_var.get()
        current_settings["theme"] = self.theme_var.get()

        self.config_manager.save_config(current_settings)
        messagebox.showinfo("設定保存", "現在の設定が保存されました。")

    def _import_settings(self):
        """設定ファイルをインポート"""
        filepath = filedialog.askopenfilename(
            initialdir=os.getcwd(),
            title="設定ファイルをインポート",
            filetypes=[("INI files", "*.ini"), ("All files", "*.*")]
        )
        if filepath:
            try:
                temp_config = configparser.ConfigParser()
                temp_config.read(filepath, encoding='utf-8')
                if 'GUI' in temp_config:
                    for key, value in temp_config['GUI'].items():
                        # ConfigManagerのget_settingロジックを模倣して型変換
                        default_val = self.defaults.get(key)
                        if isinstance(default_val, dict):
                            self.entries[key].set(value) # JSON文字列のままセット
                        elif key in self.entries:
                            self.entries[key].set(value)
                        elif key == "log_enabled":
                            self.log_enabled.set(value.lower() in ['true', '1', 'yes', 'on'])
                        elif key == "save_intermediate":
                            self.save_intermediate.set(value.lower() in ['true', '1', 'yes', 'on'])
                        elif key == "data_source":
                            self.data_source_var.set(value)
                        elif key == "optimization_strategy":
                            self.optimization_strategy_var.set(value)
                        elif key == "config_file_path":
                            self.config_file_path_var.set(value)
                        elif key == "student_file_path":
                            self.student_file_path_var.set(value)
                        elif key == "theme":
                            self.theme_var.set(value)
                    messagebox.showinfo("インポート完了", "設定が正常にインポートされました。")
                    self._apply_theme(self.theme_var.get()) # テーマを再適用
                    self._toggle_strategy_parameters() # UI状態を更新
                    self._toggle_data_source_fields() # UI状態を更新
                else:
                    messagebox.showerror("インポートエラー", "選択されたファイルに有効なGUI設定セクションが見つかりません。")
            except Exception as e:
                messagebox.showerror("インポートエラー", f"設定ファイルの読み込み中にエラーが発生しました: {e}")

    def _export_settings(self):
        """現在の設定をファイルにエクスポート"""
        filepath = filedialog.asksaveasfilename(
            initialdir=os.getcwd(),
            title="設定ファイルをエクスポート",
            defaultextension=".ini",
            filetypes=[("INI files", "*.ini"), ("All files", "*.*")]
        )
        if filepath:
            try:
                current_settings = {}
                for key, entry_frame in self.entries.items():
                    value = entry_frame.get()
                    # 倍率設定はJSON文字列として保存
                    if key == "magnification":
                        try:
                            current_settings[key] = json.dumps(json.loads(value), ensure_ascii=False)
                        except json.JSONDecodeError:
                            current_settings[key] = json.dumps(self.defaults[key], ensure_ascii=False)
                    else:
                        current_settings[key] = value
                
                current_settings["log_enabled"] = str(self.log_enabled.get())
                current_settings["save_intermediate"] = str(self.save_intermediate.get())
                current_settings["data_source"] = self.data_source_var.get()
                current_settings["optimization_strategy"] = self.optimization_strategy_var.get()
                current_settings["config_file_path"] = self.config_file_path_var.get()
                current_settings["student_file_path"] = self.student_file_path_var.get()
                current_settings["theme"] = self.theme_var.get()

                temp_config = configparser.ConfigParser()
                temp_config['GUI'] = current_settings
                with open(filepath, 'w', encoding='utf-8') as f:
                    temp_config.write(f)
                messagebox.showinfo("エクスポート完了", f"設定が '{filepath}' にエクスポートされました。")
            except Exception as e:
                messagebox.showerror("エクスポートエラー", f"設定ファイルのエクスポート中にエラーが発生しました: {e}")

    def _reset_to_defaults(self):
        """設定をデフォルト値に戻す"""
        if messagebox.askyesno("確認", "全ての設定をデフォルト値に戻しますか？"):
            for key, entry_frame in self.entries.items():
                entry_frame.set(str(self.defaults[key]))
            
            self.log_enabled.set(self.defaults["log_enabled"])
            self.save_intermediate.set(self.defaults["save_intermediate"])
            self.data_source_var.set(self.defaults["optimization_strategy"]) # デフォルトはauto
            self.optimization_strategy_var.set(self.defaults["optimization_strategy"])
            self.config_file_path_var.set(self.defaults["config_file_path"])
            self.student_file_path_var.set(self.defaults["student_file_path"])
            self.theme_var.set(self.defaults["theme"])

            self._apply_theme(self.theme_var.get()) # テーマを再適用
            self._toggle_strategy_parameters() # UI状態を更新
            self._toggle_data_source_fields() # UI状態を更新
            messagebox.showinfo("リセット完了", "設定がデフォルト値に戻されました。")

    def _show_help(self):
        """ヘルプダイアログを表示"""
        messagebox.showinfo("使用方法", 
                            "このツールは、セミナー割当を最適化するためのGUIです。\n\n"
                            "1. 「データソース」タブでデータの入力方法を選択します。\n"
                            "   - 手動データ: seminar_config.json と students_preferences.csv を選択します。\n"
                            "   - 自動生成データ: 「自動生成設定」タブでパラメータを設定します。\n"
                            "2. 「最適化設定」タブで、使用するアルゴリズムとパラメータを設定します。\n"
                            "3. 「高度な設定」タブで、ログ出力や早期終了などの詳細設定を行います。\n"
                            "4. 「最適化を実行」ボタンをクリックして処理を開始します。\n"
                            "5. 「結果」タブで最適化結果を確認できます。")

    def _show_about(self):
        """このアプリについてダイアログを表示"""
        messagebox.showinfo("このアプリについて", 
                            "セミナー割当最適化ツール v2.0\n\n"
                            "開発者: [あなたの名前/組織名]\n"
                            "このアプリケーションは、学生の希望とセミナーの定員を考慮し、"
                            "最適なセミナー割当を探索するためのツールです。\n"
                            "PythonとTkinterを使用して開発されました。")
    
    def _toggle_strategy_parameters(self, *args):
        """最適化戦略に応じてGAパラメータの表示/非表示を切り替える"""
        selected_strategy = self.optimization_strategy_var.get()
        
        # GAフレームの表示/非表示
        if selected_strategy == "GA_LS":
            self.ga_frame.pack(fill="x", padx=10, pady=5)
            ga_state = "normal"
            sa_state = "normal" # GA_LSの場合も局所探索は利用
        else:
            self.ga_frame.pack_forget()
            ga_state = "disabled"
            sa_state = "normal" if selected_strategy == "Greedy_LS" else "disabled" # Greedy_LSのみSAがnormal

        # GA関連エントリーの状態を設定
        self.entries["ga_population_size"].configure_state(ga_state)
        self.entries["ga_crossover_rate"].configure_state(ga_state)
        self.entries["ga_mutation_rate"].configure_state(ga_state)

        # SA関連エントリーの状態を設定
        self.entries["local_search_iterations"].configure_state(sa_state)
        self.entries["initial_temperature"].configure_state(sa_state)
        self.entries["cooling_rate"].configure_state(sa_state)
        
        # ILP/CP/Multilevelが選択された場合、SAフレームも非表示にする
        if selected_strategy in ["ILP", "CP", "Multilevel"]:
            self.sa_frame.pack_forget()
        else:
            self.sa_frame.pack(fill="x", padx=10, pady=5) # 再表示

    def _get_all_settings(self) -> Dict[str, Any]:
        """GUIから全ての入力設定を取得し、検証する"""
        settings = {}
        errors = []

        # データソース設定
        settings["data_source"] = self.data_source_var.get()
        if settings["data_source"] == "manual":
            settings["config_file_path"] = self.config_file_path_var.get()
            settings["student_file_path"] = self.student_file_path_var.get()
            if not os.path.exists(settings["config_file_path"]):
                errors.append("セミナー設定ファイルが存在しません。")
            if not os.path.exists(settings["student_file_path"]):
                errors.append("学生希望データファイルが存在しません。")
        
        # 自動生成データ設定 (手動データ選択時は検証しない)
        if settings["data_source"] == "auto":
            try:
                settings["seminars"] = [s.strip() for s in self.entries["seminars"].get().split(',') if s.strip()]
                if not settings["seminars"]:
                    errors.append("セミナー名が入力されていません。")
            except Exception:
                errors.append("セミナー名の形式が不正です。カンマ区切りで入力してください。")

            try:
                settings["num_students"] = InputValidator.validate_positive_int(self.entries["num_students"].get(), "学生数")
            except ValidationError as e:
                errors.append(str(e))

            try:
                settings["magnification"] = InputValidator.validate_json_dict(self.entries["magnification"].get(), "倍率")
                # 倍率のキーがセミナー名と一致しているか確認（簡易チェック）
                if settings["seminars"]:
                    for seminar in settings["magnification"].keys():
                        if seminar not in settings["seminars"]:
                            errors.append(f"倍率設定に存在しないセミナー名 '{seminar}' が含まれています。")
            except ValidationError as e:
                errors.append(str(e))

            try:
                settings["min_size"] = InputValidator.validate_positive_int(self.entries["min_size"].get(), "最小定員")
            except ValidationError as e:
                errors.append(str(e))
            try:
                settings["max_size"] = InputValidator.validate_positive_int(self.entries["max_size"].get(), "最大定員")
            except ValidationError as e:
                errors.append(str(e))
            if "min_size" in settings and "max_size" in settings and settings["min_size"] > settings["max_size"]:
                errors.append("最小定員は最大定員以下である必要があります。")
            
            try:
                settings["q_boost_probability"] = InputValidator.validate_range_float(self.entries["q_boost_probability"].get(), "ブースト確率", 0.0, 1.0)
            except ValidationError as e:
                errors.append(str(e))
            
            try:
                settings["num_preferences_to_consider"] = InputValidator.validate_positive_int(self.entries["num_preferences_to_consider"].get(), "希望考慮数")
            except ValidationError as e:
                errors.append(str(e))

        # 最適化設定
        settings["optimization_strategy"] = self.optimization_strategy_var.get()
        
        try:
            settings["num_patterns"] = InputValidator.validate_positive_int(self.entries["num_patterns"].get(), "試行回数/世代数")
        except ValidationError as e:
            errors.append(str(e))
        
        try:
            settings["max_workers"] = InputValidator.validate_positive_int(self.entries["max_workers"].get(), "並列処理数")
        except ValidationError as e:
            errors.append(str(e))

        # 焼きなまし法 (SA) 設定
        if settings["optimization_strategy"] in ["Greedy_LS", "GA_LS"]:
            try:
                settings["local_search_iterations"] = InputValidator.validate_positive_int(self.entries["local_search_iterations"].get(), "局所探索反復回数")
            except ValidationError as e:
                errors.append(str(e))
            try:
                settings["initial_temperature"] = InputValidator.validate_positive_float(self.entries["initial_temperature"].get(), "初期温度")
            except ValidationError as e:
                errors.append(str(e))
            try:
                settings["cooling_rate"] = InputValidator.validate_range_float(self.entries["cooling_rate"].get(), "冷却率", 0.00001, 0.99999)
            except ValidationError as e:
                errors.append(str(e))

        # 遺伝的アルゴリズム (GA) 設定
        if settings["optimization_strategy"] == "GA_LS":
            try:
                settings["ga_population_size"] = InputValidator.validate_positive_int(self.entries["ga_population_size"].get(), "個体数")
            except ValidationError as e:
                errors.append(str(e))
            try:
                settings["ga_crossover_rate"] = InputValidator.validate_range_float(self.entries["ga_crossover_rate"].get(), "交叉率", 0.0, 1.0)
            except ValidationError as e:
                errors.append(str(e))
            try:
                settings["ga_mutation_rate"] = InputValidator.validate_range_float(self.entries["ga_mutation_rate"].get(), "突然変異率", 0.0, 1.0)
            except ValidationError as e:
                errors.append(str(e))

        # 希望順位の重み
        for rank_key in ["preference_weights_1st", "preference_weights_2nd", "preference_weights_3rd"]:
            try:
                settings[rank_key] = InputValidator.validate_positive_float(self.entries[rank_key].get(), rank_key)
            except ValidationError as e:
                errors.append(str(e))
        
        # 高度な設定
        settings["log_enabled"] = self.log_enabled.get()
        settings["save_intermediate"] = self.save_intermediate.get()
        try:
            settings["early_stop_threshold"] = InputValidator.validate_range_float(self.entries["early_stop_threshold"].get(), "改善しきい値", 0.0, 1.0)
        except ValidationError as e:
            errors.append(str(e))
        try:
            settings["no_improvement_limit"] = InputValidator.validate_positive_int(self.entries["no_improvement_limit"].get(), "改善なしの許容回数")
        except ValidationError as e:
            errors.append(str(e))
        settings["theme"] = self.theme_var.get()

        if errors:
            messagebox.showerror("入力エラー", "\n".join(errors))
            return None
        return settings

    def _on_run_button_click(self):
        """最適化実行ボタンがクリックされた時の処理"""
        settings = self._get_all_settings()
        if settings is None:
            return # バリデーションエラーがある場合は処理を中断

        # 実行ボタンを無効化し、キャンセルボタンを有効化
        self.run_button.config(state="disabled")
        self.cancel_event.clear() # キャンセルイベントをクリア

        self.progress_dialog = ProgressDialog(self.root)
        
        # 別スレッドで最適化を実行
        self.optimization_thread = threading.Thread(
            target=self._run_optimization_in_thread, 
            args=(settings, self.progress_dialog.update_message, self.cancel_event)
        )
        self.optimization_thread.start()

        # 進捗ダイアログが閉じられたらボタンを有効化
        self.root.wait_window(self.progress_dialog.dialog)
        self.run_button.config(state="normal")
        
    def _run_optimization_in_thread(self, settings: Dict[str, Any], progress_callback: Callable, cancel_event: threading.Event):
        """
        最適化処理を別スレッドで実行する。
        """
        try:
            # ここで実際の最適化サービスを呼び出す
            # run_optimization_serviceは、progress_callbackとcancel_eventを引数に取ることを想定
            result = run_optimization_service(settings, progress_callback, cancel_event)
            
            self.root.after(0, self._display_results, result) # メインスレッドで結果を表示
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("最適化エラー", f"最適化中にエラーが発生しました: {e}"))
        finally:
            self.root.after(0, self.progress_dialog.close) # 処理完了後にダイアログを閉じる

    def _display_results(self, result: Dict[str, Any]):
        """最適化結果を結果タブに表示する"""
        self.result_text.config(state="normal") # 書き込み可能にする
        self.result_text.delete(1.0, tk.END) # 既存の内容をクリア

        if result.get("status") == "cancelled":
            self.result_text.insert(tk.END, "--- 最適化がキャンセルされました ---\n\n")
            self.result_text.insert(tk.END, f"メッセージ: {result.get('message', '不明なキャンセル')}\n")
        elif result.get("status") == "success":
            self.result_text.insert(tk.END, "--- 最適化完了 ---\n\n")
            self.result_text.insert(tk.END, f"メッセージ: {result.get('message', '成功')}\n")
            self.result_text.insert(tk.END, f"最適スコア: {result.get('best_score', 'N/A'):.2f}\n\n")
            
            self.result_text.insert(tk.END, "--- 最適な割当 ---\n")
            best_assignment = result.get("best_assignment", {})
            if best_assignment:
                for student, seminar in best_assignment.items():
                    self.result_text.insert(tk.END, f"{student}: {seminar}\n")
            else:
                self.result_text.insert(tk.END, "割当データがありません。\n")
            self.result_text.insert(tk.END, "\n")

            self.result_text.insert(tk.END, "--- 各セミナーの定員 ---\n")
            seminar_capacities = result.get("seminar_capacities", {})
            if seminar_capacities:
                for seminar, capacity in seminar_capacities.items():
                    self.result_text.insert(tk.END, f"{seminar}: {capacity}\n")
            else:
                self.result_text.insert(tk.END, "定員データがありません。\n")
            self.result_text.insert(tk.END, "\n")

            unassigned_students = result.get("unassigned_students", [])
            if unassigned_students:
                self.result_text.insert(tk.END, "--- 未割当学生 ---\n")
                for student in unassigned_students:
                    self.result_text.insert(tk.END, f"- {student}\n")
                self.result_text.insert(tk.END, "\n")
            
        else:
            self.result_text.insert(tk.END, "--- 最適化失敗または不明な結果 ---\n")
            self.result_text.insert(tk.END, f"ステータス: {result.get('status', '不明')}\n")
            self.result_text.insert(tk.END, f"メッセージ: {result.get('message', '詳細なし')}\n")

        self.result_text.config(state="disabled") # 読み取り専用に戻す
        self.notebook.select(self.notebook.index("end") - 1) # 結果タブに切り替える

    def _save_results(self):
        """結果をファイルに保存"""
        if self.result_text.get(1.0, tk.END).strip() == "":
            messagebox.showwarning("警告", "保存する結果がありません。")
            return

        filepath = filedialog.asksaveasfilename(
            initialdir=os.getcwd(),
            title="最適化結果を保存",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(self.result_text.get(1.0, tk.END))
                messagebox.showinfo("保存完了", f"結果が '{filepath}' に保存されました。")
            except Exception as e:
                messagebox.showerror("保存エラー", f"結果の保存中にエラーが発生しました: {e}")

    def _load_preset(self):
        """プリセットを読み込む"""
        filepath = filedialog.askopenfilename(
            initialdir=os.getcwd(),
            title="プリセットファイルを読み込む",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    preset_data = json.load(f)
                
                # 読み込んだプリセットデータをGUIに適用
                for key, value in preset_data.items():
                    if key in self.entries:
                        # magnificationのような辞書はJSON文字列として保存されている場合があるので注意
                        if key == "magnification" and isinstance(value, dict):
                            self.entries[key].set(json.dumps(value, ensure_ascii=False))
                        else:
                            self.entries[key].set(str(value))
                    elif key == "log_enabled":
                        self.log_enabled.set(bool(value))
                    elif key == "save_intermediate":
                        self.save_intermediate.set(bool(value))
                    elif key == "data_source":
                        self.data_source_var.set(value)
                    elif key == "optimization_strategy":
                        self.optimization_strategy_var.set(value)
                    elif key == "config_file_path":
                        self.config_file_path_var.set(value)
                    elif key == "student_file_path":
                        self.student_file_path_var.set(value)
                    elif key == "theme":
                        self.theme_var.set(value)
                
                messagebox.showinfo("プリセット読み込み", "プリセットが正常に読み込まれました。")
                self._apply_theme(self.theme_var.get()) # テーマを再適用
                self._toggle_strategy_parameters() # UI状態を更新
                self._toggle_data_source_fields() # UI状態を更新
            except Exception as e:
                messagebox.showerror("プリセット読み込みエラー", f"プリセットファイルの読み込み中にエラーが発生しました: {e}")

    def _save_preset(self):
        """現在の設定をプリセットとして保存する"""
        settings_to_save = self._get_all_settings() # 現在の検証済み設定を取得
        if settings_to_save is None:
            return # エラーがあれば保存しない

        filepath = filedialog.asksaveasfilename(
            initialdir=os.getcwd(),
            title="プリセットファイルを保存",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if filepath:
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(settings_to_save, f, ensure_ascii=False, indent=4)
                messagebox.showinfo("プリセット保存", f"現在の設定が '{filepath}' にプリセットとして保存されました。")
            except Exception as e:
                messagebox.showerror("プリセット保存エラー", f"プリセットファイルの保存中にエラーが発生しました: {e}")

    def _on_closing(self):
        """ウィンドウを閉じる際の処理"""
        if messagebox.askokcancel("終了", "アプリケーションを終了しますか？\n現在の設定は自動的に保存されます。"):
            self._save_current_settings() # 終了時に設定を自動保存
            self.root.destroy()

# --- アプリケーションのエントリポイント ---
if __name__ == "__main__":
    # デフォルトのセミナー、倍率、希望順位の重みを定義
    # これらは、アプリケーション起動時の初期値として使用されます。
    default_seminars = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
    default_magnification = {
        "A": 1.5, "B": 1.2, "C": 1.0, "D": 1.0, "E": 1.0,
        "F": 0.8, "G": 0.9, "H": 1.1, "I": 1.3, "J": 0.7
    }
    default_preference_weights = {"1st": 5.0, "2nd": 2.0, "3rd": 1.0}

    # GUIのインスタンスを作成
    app = SeminarOptimizerGUI(default_seminars, default_magnification, default_preference_weights)
    
    # Tkinterイベントループを開始
    # これにより、GUIウィンドウが表示され、ユーザーとのインタラクションが可能になります。
    app.root.mainloop()
