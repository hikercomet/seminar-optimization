import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.scrolledtext as scrolledtext
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
import logging # ロギングを追加

# logging設定をここで一元化
# 他のモジュールがbasicConfigを呼ばないように注意
if not logging.root.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # loggerの定義をここへ移動
logger.setLevel(logging.DEBUG) # DEBUGレベルのメッセージも出力

# sys.pathにプロジェクトのトップレベルパッケージディレクトリを追加
# seminar_gui.py が C:/Users/hiker/seminar_optimization/seminar_optimization/seminar_optimization/seminar_gui.py にある場合、
# トップレベルパッケージは C:/Users/hiker/seminar_optimization/seminar_optimization/ になります。
script_dir = os.path.dirname(os.path.abspath(__file__))
# script_dir から一つ上のディレクトリが、目的のパッケージルート
package_root_to_add = os.path.abspath(os.path.join(script_dir, '..'))

if package_root_to_add not in sys.path:
    sys.path.insert(0, package_root_to_add)
    logger.info(f"'{package_root_to_add}' を sys.path に追加しました。")
else:
    logger.info(f"'{package_root_to_add}' は既に sys.path に存在します。")

# パッケージの存在と __init__.py ファイルのチェック
# 想定されるパッケージ構造に基づいて、必要な __init__.py ファイルの存在を確認します。
missing_init_files = []

# トップレベルパッケージのルート (例: C:/Users/hiker/seminar_optimization/seminar_optimization/)
if not os.path.exists(os.path.join(package_root_to_add, '__init__.py')):
    missing_init_files.append(os.path.join(package_root_to_add, '__init__.py'))

# optimizers サブパッケージ
optimizers_path = os.path.join(package_root_to_add, 'optimizers')
if not os.path.exists(os.path.join(optimizers_path, '__init__.py')):
    missing_init_files.append(os.path.join(optimizers_path, '__init__.py'))
    
# config サブパッケージ
config_path = os.path.join(package_root_to_add, 'config')
if not os.path.exists(os.path.join(config_path, '__init__.py')):
    missing_init_files.append(os.path.join(config_path, '__init__.py'))

# data サブパッケージ
data_path = os.path.join(package_root_to_add, 'data')
if not os.path.exists(os.path.join(data_path, '__init__.py')):
    missing_init_files.append(os.path.join(data_path, '__init__.py'))

# seminar_gui.py が存在する内側の seminar_optimization サブパッケージ
# (例: C:/Users/hiker/seminar_optimization/seminar_optimization/seminar_optimization/)
inner_seminar_optimization_path = os.path.join(package_root_to_add, 'seminar_optimization')
if not os.path.exists(os.path.join(inner_seminar_optimization_path, '__init__.py')):
    missing_init_files.append(os.path.join(inner_seminar_optimization_path, '__init__.py'))

# data_generator.py の存在チェック (inner_seminar_optimization_path 内にあると仮定)
data_generator_path = os.path.join(inner_seminar_optimization_path, 'data_generator.py')
if not os.path.exists(data_generator_path):
    missing_init_files.append(data_generator_path) # Treat as missing init for simplicity of message

# utils.py の存在チェック (inner_seminar_optimization_path 内にあると仮定)
utils_path = os.path.join(inner_seminar_optimization_path, 'utils.py')
if not os.path.exists(utils_path):
    missing_init_files.append(utils_path)

# output_generator.py の存在チェック (inner_seminar_optimization_path 内にあると仮定)
output_generator_path = os.path.join(inner_seminar_optimization_path, 'output_generator.py')
if not os.path.exists(output_generator_path):
    missing_init_files.append(output_generator_path)


if missing_init_files:
    error_message = "Pythonパッケージの初期化ファイルまたは必要なモジュールファイルが見つかりません。以下のファイルが存在することを確認してください:\n"
    for f in missing_init_files:
        error_message += f"- {f}\n"
    error_message += "\nこれらのファイルがないと、Pythonはモジュールを正しくインポートできません。"
    logger.critical(f"seminar_gui.py: パッケージ初期化ファイルまたはモジュールが見つかりません: {missing_init_files}")
    messagebox.showerror("エラー: パッケージ構造", error_message)
    sys.exit(1)


# アプリケーション固有のモジュールをインポート
try:
    # optimizers.optimizer_service は package_root_to_add/optimizers/optimizer_service.py にあると仮定
    from ..optimizers.optimizer_service import OptimizerService, run_optimization_service
    # data_generator, utils, output_generator は seminar_gui.py と同じディレクトリにあると仮定
    from data_generator import DataGenerator # <-- ここを修正
    from utils import OptimizationResult
    from output_generator import save_csv_results, save_pdf_report
    logger.debug("seminar_gui.py: 必要なモジュールのインポートに成功しました。")
except ImportError as e:
    logger.critical(f"seminar_gui.py: モジュールのインポートに致命的な失敗: {e}", exc_info=True)
    messagebox.showerror("エラー", f"モジュールのインポートに失敗しました: {e}\n\n考えられる原因:\n1. Pythonのパス設定が正しくない。\n2. 'seminar_optimization' パッケージの構造が想定と異なる。\n\nプロジェクトのルートディレクトリ ('{package_root_to_add}') と、各モジュールのファイルパスを再確認してください。")
    sys.exit(1)

# ReportLab のインポートチェック (PDF生成機能が有効な場合のみ使用)
# output_generatorでインポートしているのでここでは不要だが、念のため
try:
    from reportlab.lib.pagesizes import A4 # 存在チェック
except ImportError:
    logger.warning("ReportLabがインストールされていません。PDFレポート生成は無効になります。")

# DPIスケーリングを有効にする（Windowsの場合）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except AttributeError:
    pass # Windows以外では無視

# ログをScrolledTextにリダイレクトするためのカスタムハンドラ
class TextHandler(logging.Handler):
    """
    ログメッセージをTkinterのScrolledTextウィジェットにリダイレクトするハンドラ。
    """
    def __init__(self, text_widget, root_tk_instance): # root_tk_instance を追加
        super().__init__()
        self.text_widget = text_widget
        self.root = root_tk_instance # rootインスタンスを保存
        # 初期状態はDISABLEDにして、ログ追加時のみNORMALにする
        self.text_widget.config(state=tk.DISABLED) 
        logger.debug("TextHandler: ScrolledTextへのログハンドラを初期化しました。")

    def emit(self, record):
        msg = self.format(record)
        # TkinterのGUI更新はメインスレッドで行う必要があるため、root.after()を使用
        # rootがまだ存在するか確認
        if self.root.winfo_exists(): # ウィンドウが存在するかチェック
            self.root.after(0, self._insert_text, msg + "\n") # 改行も追加
        else:
            # GUIがすでに閉じられている場合は、通常のコンソール出力に戻す
            print(msg)


    def _insert_text(self, msg):
        # このメソッドはメインスレッドで実行される
        # ウィジェットが破棄されていないことを再度確認
        if self.text_widget.winfo_exists():
            self.text_widget.config(state=tk.NORMAL) # ログ追加時に一時的に有効化
            self.text_widget.insert(tk.END, msg)
            self.text_widget.see(tk.END) # 最新のログを表示
            self.text_widget.config(state=tk.DISABLED) # ログ追加後に無効化
        # else: ウィジェットが破棄されている場合は何もしない

class InputValidator:
    """
    GUIの入力値の検証を行うクラス。
    """
    @staticmethod
    def validate_settings(gui_instance) -> bool:
        """
        設定タブの入力値検証ロジック。
        スピンボックスの範囲チェックなどをここで行う。
        """
        logger.debug("InputValidator: 設定値の検証を開始します。")
        try:
            # 各変数の値を取得し、必要に応じて型変換や範囲チェックを行う
            if not (1 <= gui_instance.num_seminars_var.get() <= 1000):
                messagebox.showerror("入力エラー", "セミナー数は1から1000の範囲で入力してください。")
                logger.warning(f"InputValidator: セミナー数 ({gui_instance.num_seminars_var.get()}) が範囲外です。")
                return False
            if not (1 <= gui_instance.min_capacity_var.get() <= 100):
                messagebox.showerror("入力エラー", "最小定員は1から100の範囲で入力してください。")
                logger.warning(f"InputValidator: 最小定員 ({gui_instance.min_capacity_var.get()}) が範囲外です。")
                return False
            if not (gui_instance.min_capacity_var.get() <= gui_instance.max_capacity_var.get()):
                messagebox.showerror("入力エラー", "最小定員は最大定員以下である必要があります。")
                logger.warning(f"InputValidator: 最小定員 ({gui_instance.min_capacity_var.get()}) が最大定員 ({gui_instance.max_capacity_var.get()}) より大きいです。")
                return False
            if not (1 <= gui_instance.num_students_var.get() <= 10000):
                messagebox.showerror("入力エラー", "学生数は1から10000の範囲で入力してください。")
                logger.warning(f"InputValidator: 学生数 ({gui_instance.num_students_var.get()}) が範囲外です。")
                return False
            if not (1 <= gui_instance.min_preferences_var.get() <= 10):
                messagebox.showerror("入力エラー", "最小希望数は1から10の範囲で入力してください。")
                logger.warning(f"InputValidator: 最小希望数 ({gui_instance.min_preferences_var.get()}) が範囲外です。")
                return False
            if not (gui_instance.min_preferences_var.get() <= gui_instance.max_preferences_var.get()):
                messagebox.showerror("入力エラー", "最小希望数は最大希望数以下である必要があります。")
                logger.warning(f"InputValidator: 最小希望数 ({gui_instance.min_preferences_var.get()}) が最大希望数 ({gui_instance.max_preferences_var.get()}) より大きいです。")
                return False

            logger.info("InputValidator: すべての設定値が有効です。")
            return True # すべての検証が成功

        except tk.TclError as e: # Spinboxなどの入力エラーをキャッチ
            messagebox.showerror("入力エラー", f"数値入力が不正です: {e}")
            logger.error(f"InputValidator: 数値入力エラー: {e}", exc_info=True)
            return False
        except Exception as e:
            messagebox.showerror("検証エラー", f"設定検証中に予期せぬエラーが発生しました: {e}")
            logger.error(f"InputValidator: 設定検証中に予期せぬエラー: {e}", exc_info=True)
            return False

class ConfigManager:
    """
    GUI固有の設定をiniファイルで管理するクラス。
    """
    def __init__(self):
        self.config_file = "gui_settings.ini"
        self.config = configparser.ConfigParser()
        logger.debug(f"ConfigManager: 初期化。設定ファイル: {self.config_file}")

    def load_gui_settings(self):
        """GUI設定をファイルから読み込む。"""
        logger.debug(f"ConfigManager: GUI設定のロードを試行中: {self.config_file}")
        if os.path.exists(self.config_file):
            # エンコーディングを明示的に指定
            self.config.read(self.config_file, encoding="utf-8")
            if 'GUI' in self.config:
                logger.info(f"ConfigManager: GUI設定をロードしました。")
                return self.config['GUI']
        logger.info("ConfigManager: GUI設定ファイルが見つからないか、セクションがありません。空の設定を使用します。")
        return {}

    def save_gui_settings(self, settings: Dict[str, str]):
        """GUI設定をファイルに保存する。"""
        logger.debug(f"ConfigManager: GUI設定の保存を試行中: {self.config_file}")
        if 'GUI' not in self.config:
            self.config['GUI'] = {}
            logger.debug("ConfigManager: 'GUI' セクションを作成しました。")
        for key, value in settings.items():
            self.config['GUI'][key] = str(value)
            logger.debug(f"ConfigManager: 設定 '{key}' = '{value}' を追加/更新しました。")
        with open(self.config_file, 'w') as f:
            self.config.write(f)
        logger.info(f"ConfigManager: GUI設定を正常に保存しました: {self.config_file}")

class ProgressDialog:
    """
    最適化処理の進捗を表示するダイアログ。
    """
    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("処理中...")
        self.dialog.geometry("400x150")
        self.dialog.transient(parent) # 親ウィンドウの前面に表示
        self.dialog.grab_set() # 他のウィンドウを操作できなくする
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_closing) # 閉じるボタンの無効化
        logger.debug("ProgressDialog: プログレスダイアログを初期化しました。")

        self.label = ttk.Label(self.dialog, text="最適化を開始しています...", wraplength=350)
        self.label.pack(pady=20)

        self.progress_bar = ttk.Progressbar(self.dialog, orient="horizontal", length=300, mode="indeterminate")
        self.progress_bar.pack(pady=10)

        # キャンセルボタン
        self.cancel_button = ttk.Button(self.dialog, text="キャンセル", command=self._on_cancel)
        self.cancel_button.pack(pady=5)
        self.cancel_callback: Optional[Callable[[], None]] = None
        logger.debug("ProgressDialog: UI要素を配置しました。")

    def _on_closing(self):
        """ユーザーが閉じるボタンを押しても閉じないようにする。"""
        logger.debug("ProgressDialog: 閉じるボタンが押されました。")
        messagebox.showinfo("情報", "処理が完了するまでお待ちください。")
        logger.info("ProgressDialog: 処理完了を待つメッセージを表示しました。")

    def _on_cancel(self):
        """キャンセルボタンが押されたときの処理。"""
        logger.debug("ProgressDialog: キャンセルボタンが押されました。")
        if messagebox.askyesno("確認", "最適化処理をキャンセルしますか？"):
            if self.cancel_callback:
                self.cancel_callback()
                logger.info("ProgressDialog: キャンセルコールバックを呼び出しました。")
            self.update_progress_message("キャンセル要求を送信しました...")
            self.cancel_button.config(state=tk.DISABLED, text="キャンセル中...")
            logger.debug("ProgressDialog: キャンセル要求を送信し、ボタンを無効化しました。")
        else:
            logger.debug("ProgressDialog: キャンセルがユーザーによって拒否されました。")


    def start_progress_bar(self, initial_message: str = "処理中..."):
        """プログレスバーを開始し、初期メッセージを設定する。"""
        self.label.config(text=initial_message)
        self.progress_bar.start()
        self.dialog.update_idletasks() # UIを更新
        logger.info(f"ProgressDialog: プログレスバーを開始しました。初期メッセージ: '{initial_message}'")

    def update_progress_message(self, message: str):
        """プログレスメッセージを更新する。"""
        self.label.config(text=message)
        self.dialog.update_idletasks() # UIを更新
        logger.debug(f"ProgressDialog: プログレスメッセージを更新: '{message}'")

    def close(self):
        """プログレスダイアログを閉じる。"""
        logger.debug("ProgressDialog: プログレスダイアログを閉じます。")
        if self.progress_bar.winfo_exists(): # ウィジェットが存在するか確認
            self.progress_bar.stop()
            self.dialog.destroy()
            self.parent.grab_release() # grabを解除
            logger.info("ProgressDialog: プログレスダイアログを正常に閉じました。")
        else:
            logger.debug("ProgressDialog: プログレスダイアログは既に閉じられています。")

class SeminarGUI:
    """
    セミナー割り当て最適化ツールのメインGUIクラス。
    """
    def __init__(self, root):
        self.root = root
        self.root.title("セミナー割り当て最適化ツール")
        self.root.geometry("1200x800") # ウィンドウサイズを少し大きく設定
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing) # 閉じるボタンの挙動を制御
        logger.debug("SeminarGUI: GUIウィンドウを初期化しました。")

        self.config_manager = ConfigManager()
        self.gui_settings = self.config_manager.load_gui_settings()
        self.optimization_config = self._load_default_optimization_config() # config.jsonから読み込む
        
        self.optimization_thread: Optional[threading.Thread] = None
        self.cancel_event = threading.Event()
        self.progress_dialog: Optional[ProgressDialog] = None
        self.is_optimizing = False # 最適化が実行中かどうかを示すフラグ

        self.log_text: Optional[scrolledtext.ScrolledText] = None # TextHandlerに渡す前に初期化
        self.text_handler: Optional[TextHandler] = None # TextHandlerインスタンスを保持

        self._initialize_defaults() # GUIのデフォルト値を設定
        self._setup_ui() # UIのセットアップ

        self._load_saved_settings() # 保存されたGUI設定をロード (UIセットアップ後に行う)

        logger.info("SeminarGUI: 初期化が完了しました。")
        messagebox.showinfo("起動完了", "アプリケーションが起動しました。")


    def _load_default_optimization_config(self):
        """config.jsonから最適化のデフォルト設定を読み込む。"""
        # config.json は package_root_to_add/config/config.json にあると仮定
        config_path = os.path.join(package_root_to_add, 'config', 'config.json')
        logger.debug(f"SeminarGUI: config.json のロードを試行中: {config_path}")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                logger.info(f"SeminarGUI: config.json を正常にロードしました。")
                return config_data
        except FileNotFoundError:
            logger.warning(f"SeminarGUI: config.jsonが見つかりません: {config_path}。空の設定を使用します。")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"SeminarGUI: config.jsonのデコードエラー: {e}。空の設定を使用します。", exc_info=True)
            return {}
        except Exception as e:
            logger.error(f"SeminarGUI: config.jsonのロード中に予期せぬエラーが発生しました: {e}", exc_info=True)
            return {}

    def _initialize_defaults(self):
        """GUIの入力フィールドのデフォルト値を設定。config.jsonの値を初期値として使用。"""
        logger.debug("SeminarGUI: GUI入力フィールドのデフォルト値を初期化します。")
        self.num_seminars_var = tk.IntVar(value=self.optimization_config.get("num_seminars", 10))
        self.min_capacity_var = tk.IntVar(value=self.optimization_config.get("min_capacity", 5))
        self.max_capacity_var = tk.IntVar(value=self.optimization_config.get("max_capacity", 10))
        self.num_students_var = tk.IntVar(value=self.optimization_config.get("num_students", 50))
        self.min_preferences_var = tk.IntVar(value=self.optimization_config.get("min_preferences", 3))
        self.max_preferences_var = tk.IntVar(value=self.optimization_config.get("max_preferences", 5))
        self.preference_dist_var = tk.StringVar(value=self.optimization_config.get("preference_distribution", "random")) # 新しいデータ生成オプション

        self.optimization_strategy_var = tk.StringVar(value=self.optimization_config.get("optimization_strategy", "Greedy_LS"))
        self.ga_population_size_var = tk.IntVar(value=self.optimization_config.get("ga_population_size", 100))
        self.ga_generations_var = tk.IntVar(value=self.optimization_config.get("ga_generations", 200))
        self.ilp_time_limit_var = tk.IntVar(value=self.optimization_config.get("ilp_time_limit", 300))
        self.cp_time_limit_var = tk.IntVar(value=self.optimization_config.get("cp_time_limit", 300))
        self.multilevel_clusters_var = tk.IntVar(value=self.optimization_config.get("multilevel_clusters", 5))
        self.greedy_ls_iterations_var = tk.IntVar(value=self.optimization_config.get("greedy_ls_iterations", 200000))
        self.local_search_iterations_var = tk.IntVar(value=self.optimization_config.get("local_search_iterations", 500))
        self.initial_temperature_var = tk.DoubleVar(value=self.optimization_config.get("initial_temperature", 1.0))
        self.cooling_rate_var = tk.DoubleVar(value=self.optimization_config.get("cooling_rate", 0.995))

        self.generate_pdf_report_var = tk.BooleanVar(value=self.optimization_config.get("generate_pdf_report", True))
        self.generate_csv_report_var = tk.BooleanVar(value=self.optimization_config.get("generate_csv_report", True))
        self.debug_mode_var = tk.BooleanVar(value=self.optimization_config.get("debug_mode", False))
        self.log_enabled_var = tk.BooleanVar(value=self.optimization_config.get("log_enabled", True))
        self.random_seed_var = tk.IntVar(value=self.optimization_config.get("random_seed", 42)) # デフォルト値は42
        
        # データ入力方法の変数
        self.data_input_method_var = tk.StringVar(value=self.gui_settings.get("data_input_method", "generate")) # gui_settingsから初期値をロード
        
        # config.jsonからデフォルトのファイルパスを設定
        # dataディレクトリは package_root_to_add/data にあると仮定
        default_data_dir = os.path.join(package_root_to_add, 'data') 
        self.seminars_file_path_var = tk.StringVar(value=self.gui_settings.get('seminars_file_path', os.path.join(default_data_dir, self.optimization_config.get('seminars_file', 'seminars.json'))))
        self.students_file_path_var = tk.StringVar(value=self.gui_settings.get('students_file_path', os.path.join(default_data_dir, self.optimization_config.get('students_file', 'students.json'))))
        logger.debug(f"SeminarGUI: デフォルトのデータファイルパス: セミナー='{self.seminars_file_path_var.get()}', 学生='{self.students_file_path_var.get()}'")

        # 手動入力用データ格納
        self.manual_seminar_data: List[Dict[str, Any]] = []
        self.manual_student_data: List[Dict[str, Any]] = []
        self.manual_seminar_tree: Optional[ttk.Treeview] = None
        self.manual_student_tree: Optional[ttk.Treeview] = None
        logger.debug("SeminarGUI: 手動入力用データ構造を初期化しました。")

        # レポート表示用のオリジナルデータ保持
        self.seminars_data_for_report: List[Dict[str, Any]] = []
        self.students_data_for_report: List[Dict[str, Any]] = []


    def _setup_ui(self):
        """UIの主要な要素をセットアップする。"""
        logger.debug("SeminarGUI: UIのセットアップを開始します。")

        # スタイル設定
        self.style = ttk.Style()
        self.style.theme_use('clam') # 'clam', 'alt', 'default', 'classic' など
        self.style.configure("TFrame", background="#f0f0f0")
        self.style.configure("TLabel", background="#f0f0f0", font=('Yu Gothic UI', 10))
        self.style.configure("TButton", font=('Yu Gothic UI', 10, 'bold'), padding=5)
        self.style.configure("TLabelframe.Label", font=('Yu Gothic UI', 10, 'bold'))
        self.style.configure("TCheckbutton", background="#f0f0f0", font=('Yu Gothic UI', 10))
        self.style.configure("TRadiobutton", background="#f0f0f0", font=('Yu Gothic UI', 10))

        # メインフレームにCanvas + Scrollbar を作る
        outer_frame = ttk.Frame(self.root)
        outer_frame.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer_frame)
        scrollbar = ttk.Scrollbar(outer_frame, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Canvasの中にFrameを作る
        self.main_frame = ttk.Frame(canvas)
        self.main_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        self.canvas_window = canvas.create_window((0, 0), window=self.main_frame, anchor="nw")

        # Notebookをmain_frame内に作成する
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(padx=10, pady=10, fill="both", expand=True)

        # ログタブを最初に作成し、TextHandlerを設定
        self._create_logs_tab() # <-- ログタブを最初に作成

        self._create_data_input_tab()
        self._create_settings_tab()
        self._create_results_tab()
        
        # 最適化実行ボタン
        control_frame = ttk.Frame(self.main_frame, padding="10")
        control_frame.pack(fill="x")
        self.optimize_button = ttk.Button(control_frame, text="最適化を実行", command=self._run_optimization)
        self.optimize_button.pack(side="left", padx=5, pady=5)
        self.cancel_button = ttk.Button(control_frame, text="キャンセル", command=self._cancel_optimization, state=tk.DISABLED)
        self.cancel_button.pack(side="right", padx=5, pady=5)

        canvas.bind('<Configure>', lambda e: canvas.itemconfig(self.canvas_window, width=e.width))
        logger.info("SeminarGUI: UIのセットアップが完了しました。")


    def _create_data_input_tab(self):
        """データ入力タブを作成する。"""
        logger.debug("SeminarGUI: データ入力タブを作成します。")
        data_input_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(data_input_frame, text="データ入力")

        # データ入力方法の選択
        input_method_frame = ttk.LabelFrame(data_input_frame, text="データ入力方法の選択", padding="10")
        input_method_frame.pack(pady=10, fill="x")

        json_radio = ttk.Radiobutton(input_method_frame, text="JSONファイルから読み込む", variable=self.data_input_method_var, value="json", command=self._on_input_method_changed)
        json_radio.pack(anchor="w", pady=2)
        csv_radio = ttk.Radiobutton(input_method_frame, text="CSVファイルから読み込む", variable=self.data_input_method_var, value="csv", command=self._on_input_method_changed)
        csv_radio.pack(anchor="w", pady=2)
        generate_radio = ttk.Radiobutton(input_method_frame, text="自動生成する", variable=self.data_input_method_var, value="generate", command=self._on_input_method_changed)
        generate_radio.pack(anchor="w", pady=2)
        manual_radio = ttk.Radiobutton(input_method_frame, text="手動入力する", variable=self.data_input_method_var, value="manual", command=self._on_input_method_changed)
        manual_radio.pack(anchor="w", pady=2)
        logger.debug("SeminarGUI: データ入力方法のラジオボタンを配置しました。")

        # 各入力方法に対応するフレーム
        self.file_input_frame = ttk.Frame(data_input_frame)
        self.generate_input_frame = ttk.Frame(data_input_frame)
        self.manual_input_frame = ttk.Frame(data_input_frame)

        self._create_file_input_section(self.file_input_frame)
        self._create_generate_input_section(self.generate_input_frame)
        self._create_manual_input_section(self.manual_input_frame)

        self._on_input_method_changed() # 初期表示
        logger.debug("SeminarGUI: データ入力タブの作成が完了しました。")


    def _on_input_method_changed(self):
        """データ入力方法のラジオボタンが変更されたときに、対応するUIを表示/非表示する。"""
        logger.debug("SeminarGUI: 入力方法の変更イベントを処理中。")
        # 全ての入力フレームを非表示にする
        self.file_input_frame.pack_forget()
        self.generate_input_frame.pack_forget()
        self.manual_input_frame.pack_forget()
        logger.debug("SeminarGUI: 全ての入力フレームを非表示にしました。")

        # 選択された入力方法に対応するフレームを表示
        selected_method = self.data_input_method_var.get()
        if selected_method == "json" or selected_method == "csv":
            self.file_input_frame.pack(pady=10, fill="x", expand=True)
            logger.info(f"SeminarGUI: ファイル入力フレームを表示しました (方法: {selected_method})。")
        elif selected_method == "generate":
            self.generate_input_frame.pack(pady=10, fill="x", expand=True)
            logger.info("SeminarGUI: 自動生成入力フレームを表示しました。")
        elif selected_method == "manual":
            self.manual_input_frame.pack(pady=10, fill="both", expand=True) # expand=True for manual table
            logger.info("SeminarGUI: 手動入力フレームを表示しました。")
        logger.debug(f"SeminarGUI: 選択された入力方法: {selected_method} に対応するフレームを表示しました。")

    def _create_file_input_section(self, parent_frame):
        """ファイル入力セクション (JSON/CSV共通) を作成する。"""
        logger.debug("SeminarGUI: ファイル入力セクションを作成します。")
        file_frame = ttk.LabelFrame(parent_frame, text="ファイルパス", padding="10")
        file_frame.pack(fill="x", expand=True)

        ttk.Label(file_frame, text="セミナーファイル:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        seminars_entry = ttk.Entry(file_frame, textvariable=self.seminars_file_path_var, width=50)
        seminars_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(file_frame, text="参照...", command=lambda: self._browse_file(self.seminars_file_path_var, "seminars")).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(file_frame, text="学生ファイル:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        students_entry = ttk.Entry(file_frame, textvariable=self.students_file_path_var, width=50)
        students_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(file_frame, text="参照...", command=lambda: self._browse_file(self.students_file_path_var, "students")).grid(row=1, column=2, padx=5, pady=5)

        # 修正: grid_column_configure の代わりに columnconfigure を使用
        file_frame.columnconfigure(1, weight=1)
        logger.debug("SeminarGUI: ファイル入力セクションの作成が完了しました。")
    
    def _browse_file(self, var: tk.StringVar, file_type: str):
        """ファイル参照ダイアログを開き、選択されたファイルパスを変数に設定する。"""
        logger.debug(f"SeminarGUI: ファイル参照ダイアログを開きます (タイプ: {file_type})。")
        filetypes = []
        selected_method = self.data_input_method_var.get()
        if selected_method == "json":
            filetypes = [("JSON files", "*.json"), ("All files", "*.*")]
        elif selected_method == "csv":
            filetypes = [("CSV files", "*.csv"), ("All files", "*.*")]
        
        initial_dir = os.path.dirname(var.get()) if var.get() else os.path.join(package_root_to_add, 'data')
        logger.debug(f"SeminarGUI: ファイル参照の初期ディレクトリ: {initial_dir}")
        
        filepath = filedialog.askopenfilename(
            title=f"{file_type}ファイルを指定してください",
            initialdir=initial_dir,
            filetypes=filetypes
        )
        if filepath:
            var.set(filepath)
            logger.info(f"SeminarGUI: ファイルパスが設定されました: {filepath}")
        else:
            logger.debug("SeminarGUI: ファイル選択がキャンセルされました。")

    def _create_generate_input_section(self, parent_frame):
        """データ自動生成セクションを作成する。"""
        logger.debug("SeminarGUI: データ自動生成セクションを作成します。")
        generate_frame = ttk.LabelFrame(parent_frame, text="データ自動生成設定", padding="10")
        generate_frame.pack(fill="x", expand=True)

        row = 0
        ttk.Label(generate_frame, text="セミナー数:").grid(row=row, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=1000, textvariable=self.num_seminars_var, width=10).grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        row += 1

        ttk.Label(generate_frame, text="最小定員:").grid(row=row, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=100, textvariable=self.min_capacity_var, width=10).grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        row += 1

        ttk.Label(generate_frame, text="最大定員:").grid(row=row, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=100, textvariable=self.max_capacity_var, width=10).grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        row += 1

        ttk.Label(generate_frame, text="学生数:").grid(row=row, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=10000, textvariable=self.num_students_var, width=10).grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        row += 1

        ttk.Label(generate_frame, text="最小希望数:").grid(row=row, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=10, textvariable=self.min_preferences_var, width=10).grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        row += 1

        ttk.Label(generate_frame, text="最大希望数:").grid(row=row, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=10, textvariable=self.max_preferences_var, width=10).grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        row += 1

        ttk.Label(generate_frame, text="希望分布:").grid(row=row, column=0, padx=5, pady=2, sticky="w")
        dist_options = ["random", "uniform", "biased"]
        ttk.Combobox(generate_frame, textvariable=self.preference_dist_var, values=dist_options, state="readonly", width=10).grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        row += 1

        generate_frame.grid_columnconfigure(1, weight=1)
        logger.debug("SeminarGUI: データ自動生成セクションの作成が完了しました。")

    def _create_manual_input_section(self, parent_frame):
        """手動入力セクションを作成する。"""
        logger.debug("SeminarGUI: 手動入力セクションを作成します。")
        manual_frame = ttk.LabelFrame(parent_frame, text="データ手動入力", padding="10")
        manual_frame.pack(fill="both", expand=True)

        self.manual_notebook = ttk.Notebook(manual_frame)
        self.manual_notebook.pack(padx=5, pady=5, fill="both", expand=True)

        # セミナー手動入力タブ
        seminar_manual_frame = ttk.Frame(self.manual_notebook, padding="10")
        self.manual_notebook.add(seminar_manual_frame, text="セミナー")
        self._create_manual_seminar_input(seminar_manual_frame)

        # 学生手動入力タブ
        student_manual_frame = ttk.Frame(self.manual_notebook, padding="10")
        self.manual_notebook.add(student_manual_frame, text="学生")
        self._create_manual_student_input(student_manual_frame)
        logger.debug("SeminarGUI: 手動入力セクションの作成が完了しました。")

    def _create_manual_seminar_input(self, parent_frame):
        """セミナーデータの手動入力UIを作成する。"""
        logger.debug("SeminarGUI: 手動セミナー入力UIを作成します。")
        # セミナーデータ表示/入力ツリービュー
        seminar_tree_frame = ttk.Frame(parent_frame)
        seminar_tree_frame.pack(fill="both", expand=True)

        columns = ("ID", "定員")
        self.manual_seminar_tree = ttk.Treeview(seminar_tree_frame, columns=columns, show="headings")
        self.manual_seminar_tree.heading("ID", text="セミナーID")
        self.manual_seminar_tree.heading("定員", text="定員")
        self.manual_seminar_tree.column("ID", width=100)
        self.manual_seminar_tree.column("定員", width=80)
        self.manual_seminar_tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(seminar_tree_frame, orient="vertical", command=self.manual_seminar_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.manual_seminar_tree.configure(yscrollcommand=scrollbar.set)
        logger.debug("SeminarGUI: セミナーツリービューを作成しました。")

        # 入力フォーム
        input_frame = ttk.Frame(parent_frame)
        input_frame.pack(fill="x", pady=10)

        ttk.Label(input_frame, text="ID:").grid(row=0, column=0, padx=5)
        self.seminar_id_entry = ttk.Entry(input_frame, width=15)
        self.seminar_id_entry.grid(row=0, column=1, padx=5)

        ttk.Label(input_frame, text="定員:").grid(row=0, column=2, padx=5)
        self.seminar_capacity_entry = ttk.Spinbox(input_frame, from_=1, to=1000, width=10)
        self.seminar_capacity_entry.grid(row=0, column=3, padx=5)

        add_button = ttk.Button(input_frame, text="追加/更新", command=self._add_or_update_seminar)
        add_button.grid(row=0, column=4, padx=5)
        remove_button = ttk.Button(input_frame, text="削除", command=self._remove_seminar)
        remove_button.grid(row=0, column=5, padx=5)
        logger.debug("SeminarGUI: セミナー入力フォームを作成しました。")

        self._populate_manual_seminar_tree()
        logger.debug("SeminarGUI: 手動セミナー入力UIの作成が完了しました。")

    def _populate_manual_seminar_tree(self):
        """手動入力セミナーツリービューを更新する。"""
        logger.debug("SeminarGUI: 手動セミナーツリービューを更新中。")
        for item in self.manual_seminar_tree.get_children():
            self.manual_seminar_tree.delete(item)
        for seminar in self.manual_seminar_data:
            self.manual_seminar_tree.insert("", "end", values=(seminar['id'], seminar['capacity']))
        logger.debug(f"SeminarGUI: 手動セミナーツリービューに {len(self.manual_seminar_data)} 件のデータを挿入しました。")

    def _add_or_update_seminar(self):
        """手動入力セミナーを追加または更新する。"""
        logger.debug("SeminarGUI: セミナーの追加/更新を処理中。")
        seminar_id = self.seminar_id_entry.get().strip()
        capacity_str = self.seminar_capacity_entry.get().strip()
        if not seminar_id or not capacity_str:
            messagebox.showwarning("入力エラー", "セミナーIDと定員を入力してください。")
            logger.warning("SeminarGUI: セミナーIDまたは定員が空のため、追加/更新を拒否しました。")
            return
        try:
            capacity = int(capacity_str)
            if capacity <= 0:
                messagebox.showwarning("入力エラー", "定員は正の整数である必要があります。")
                logger.warning(f"SeminarGUI: 定員 ({capacity}) が正の整数ではないため、追加/更新を拒否しました。")
                return
        except ValueError:
            messagebox.showwarning("入力エラー", "定員は数値で入力してください。")
            logger.warning("SeminarGUI: 定員が数値ではないため、追加/更新を拒否しました。")
            return

        # 既存のセミナーを更新するか、新規追加する
        found = False
        for seminar in self.manual_seminar_data:
            if seminar['id'] == seminar_id:
                seminar['capacity'] = capacity
                found = True
                logger.info(f"SeminarGUI: セミナー '{seminar_id}' を更新しました。新定員: {capacity}")
                break
        if not found:
            self.manual_seminar_data.append({'id': seminar_id, 'capacity': capacity})
            logger.info(f"SeminarGUI: 新しいセミナー '{seminar_id}' (定員: {capacity}) を追加しました。")
        
        self._populate_manual_seminar_tree()
        self.seminar_id_entry.delete(0, tk.END)
        self.seminar_capacity_entry.delete(0, tk.END)
        self.seminar_capacity_entry.insert(0, "10") # デフォルト値に戻す
        logger.debug("SeminarGUI: セミナー入力フォームをクリアしました。")

    def _remove_seminar(self):
        """手動入力セミナーを削除する。"""
        logger.debug("SeminarGUI: セミナーの削除を処理中。")
        selected_items = self.manual_seminar_tree.selection()
        if not selected_items:
            messagebox.showwarning("選択エラー", "削除するセミナーを選択してください。")
            logger.warning("SeminarGUI: 削除するセミナーが選択されていません。")
            return
        
        for item in selected_items:
            seminar_id_to_remove = self.manual_seminar_tree.item(item, "values")[0]
            self.manual_seminar_data = [s for s in self.manual_seminar_data if s['id'] != seminar_id_to_remove]
            logger.info(f"SeminarGUI: セミナー '{seminar_id_to_remove}' を削除しました。")
        self._populate_manual_seminar_tree()
        logger.debug("SeminarGUI: セミナー削除後のツリービューを更新しました。")

    def _create_manual_student_input(self, parent_frame):
        """学生データの手動入力UIを作成する。"""
        logger.debug("SeminarGUI: 手動学生入力UIを作成します。")
        # 学生データ表示/入力ツリービュー
        student_tree_frame = ttk.Frame(parent_frame)
        student_tree_frame.pack(fill="both", expand=True)

        columns = ("ID", "希望セミナー")
        self.manual_student_tree = ttk.Treeview(student_tree_frame, columns=columns, show="headings")
        self.manual_student_tree.heading("ID", text="学生ID")
        self.manual_student_tree.heading("希望セミナー", text="希望セミナー（カンマ区切り）")
        self.manual_student_tree.column("ID", width=100)
        self.manual_student_tree.column("希望セミナー", width=300)
        self.manual_student_tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(student_tree_frame, orient="vertical", command=self.manual_student_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.manual_student_tree.configure(yscrollcommand=scrollbar.set)
        logger.debug("SeminarGUI: 学生ツリービューを作成しました。")

        # 入力フォーム
        input_frame = ttk.Frame(parent_frame)
        input_frame.pack(fill="x", pady=10)

        ttk.Label(input_frame, text="ID:").grid(row=0, column=0, padx=5)
        self.student_id_entry = ttk.Entry(input_frame, width=15)
        self.student_id_entry.grid(row=0, column=1, padx=5)

        ttk.Label(input_frame, text="希望:").grid(row=0, column=2, padx=5)
        self.student_preferences_entry = ttk.Entry(input_frame, width=40)
        self.student_preferences_entry.grid(row=0, column=3, padx=5)
        ttk.Label(input_frame, text="(例: S001,S002,S003)").grid(row=0, column=4, padx=5, sticky="w")


        add_button = ttk.Button(input_frame, text="追加/更新", command=self._add_or_update_student)
        add_button.grid(row=1, column=0, columnspan=2, pady=5)
        remove_button = ttk.Button(input_frame, text="削除", command=self._remove_student)
        remove_button.grid(row=1, column=2, columnspan=2, pady=5)
        logger.debug("SeminarGUI: 学生入力フォームを作成しました。")
        
        self._populate_manual_student_tree()
        logger.debug("SeminarGUI: 手動学生入力UIの作成が完了しました。")

    def _populate_manual_student_tree(self):
        """手動入力学生ツリービューを更新する。"""
        logger.debug("SeminarGUI: 手動学生ツリービューを更新中。")
        for item in self.manual_student_tree.get_children():
            self.manual_student_tree.delete(item)
        for student in self.manual_student_data:
            self.manual_student_tree.insert("", "end", values=(student['id'], ", ".join(student['preferences'])))
        logger.debug(f"SeminarGUI: 手動学生ツリービューに {len(self.manual_student_data)} 件のデータを挿入しました。")

    def _add_or_update_student(self):
        """手動入力学生を追加または更新する。"""
        logger.debug("SeminarGUI: 学生の追加/更新を処理中。")
        student_id = self.student_id_entry.get().strip()
        preferences_str = self.student_preferences_entry.get().strip()
        if not student_id:
            messagebox.showwarning("入力エラー", "学生IDを入力してください。")
            logger.warning("SeminarGUI: 学生IDが空のため、追加/更新を拒否しました。")
            return
        
        preferences = [p.strip() for p in preferences_str.split(',') if p.strip()]
        
        if not preferences:
            messagebox.showwarning("入力エラー", "希望セミナーを入力してください。")
            logger.warning("SeminarGUI: 希望セミナーが空のため、追加/更新を拒否しました。")
            return

        # 既存の学生を更新するか、新規追加する
        found = False
        for student in self.manual_student_data:
            if student['id'] == student_id:
                student['preferences'] = preferences
                found = True
                logger.info(f"SeminarGUI: 学生 '{student_id}' を更新しました。新希望: {preferences}")
                break
        if not found:
            self.manual_student_data.append({'id': student_id, 'preferences': preferences})
            logger.info(f"SeminarGUI: 新しい学生 '{student_id}' (希望: {preferences}) を追加しました。")
        
        self._populate_manual_student_tree()
        self.student_id_entry.delete(0, tk.END)
        self.student_preferences_entry.delete(0, tk.END)
        logger.debug("SeminarGUI: 学生入力フォームをクリアしました。")

    def _remove_student(self):
        """手動入力学生を削除する。"""
        logger.debug("SeminarGUI: 学生の削除を処理中。")
        selected_items = self.manual_student_tree.selection()
        if not selected_items:
            messagebox.showwarning("選択エラー", "削除する学生を選択してください。")
            logger.warning("SeminarGUI: 削除する学生が選択されていません。")
            return
        
        for item in selected_items:
            student_id_to_remove = self.manual_student_tree.item(item, "values")[0]
            self.manual_student_data = [s for s in self.manual_student_data if s['id'] != student_id_to_remove]
            logger.info(f"SeminarGUI: 学生 '{student_id_to_remove}' を削除しました。")
        self._populate_manual_student_tree()
        logger.debug("SeminarGUI: 学生削除後のツリービューを更新しました。")

    def _create_settings_tab(self):
        """設定タブを作成する。"""
        logger.debug("SeminarGUI: 設定タブを作成します。")
        settings_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(settings_frame, text="設定")

        # 各最適化戦略の設定をグループ化
        strategy_frame = ttk.LabelFrame(settings_frame, text="最適化戦略の選択", padding="10")
        strategy_frame.pack(pady=10, fill="x")

        strategy_options = ["Greedy_LS", "GA_LS", "ILP", "CP", "Multilevel", "Adaptive"]
        strategy_menu = ttk.OptionMenu(strategy_frame, self.optimization_strategy_var, self.optimization_strategy_var.get(), *strategy_options)
        strategy_menu.pack(padx=5, pady=5, anchor="w")
        logger.debug(f"SeminarGUI: 最適化戦略の選択メニューを作成しました。初期値: {self.optimization_strategy_var.get()}")

        # GA_LS設定
        ga_frame = ttk.LabelFrame(settings_frame, text="遺伝的アルゴリズム (GA_LS) 設定", padding="10")
        ga_frame.pack(pady=10, fill="x")
        self._create_setting_row(ga_frame, "個体群サイズ:", self.ga_population_size_var, 0, min_val=10, max_val=1000)
        self._create_setting_row(ga_frame, "世代数:", self.ga_generations_var, 1, min_val=10, max_val=1000)
        logger.debug("SeminarGUI: GA_LS設定フレームを作成しました。")

        # ILP/CP設定
        ilp_cp_frame = ttk.LabelFrame(settings_frame, text="ILP/CP 設定", padding="10")
        ilp_cp_frame.pack(pady=10, fill="x")
        self._create_setting_row(ilp_cp_frame, "ILPタイムリミット (秒):", self.ilp_time_limit_var, 0, min_val=1, max_val=3600)
        self._create_setting_row(ilp_cp_frame, "CPタイムリミット (秒):", self.cp_time_limit_var, 1, min_val=1, max_val=3600)
        logger.debug("SeminarGUI: ILP/CP設定フレームを作成しました。")

        # 多段階最適化設定
        multilevel_frame = ttk.LabelFrame(settings_frame, text="多段階最適化 設定", padding="10")
        multilevel_frame.pack(pady=10, fill="x")
        self._create_setting_row(multilevel_frame, "クラスタ数:", self.multilevel_clusters_var, 0, min_val=1, max_val=20)
        logger.debug("SeminarGUI: 多段階最適化設定フレームを作成しました。")

        # 共通の局所探索設定
        ls_frame = ttk.LabelFrame(settings_frame, text="局所探索設定", padding="10")
        ls_frame.pack(pady=10, fill="x")
        self._create_setting_row(ls_frame, "Greedy LS イテレーション:", self.greedy_ls_iterations_var, 0, min_val=100, max_val=1000000, step=100)
        self._create_setting_row(ls_frame, "局所探索イテレーション:", self.local_search_iterations_var, 1, min_val=10, max_val=10000)
        self._create_setting_row(ls_frame, "初期温度 (焼きなまし):", self.initial_temperature_var, 2, is_double=True, min_val=0.01, max_val=100.0)
        self._create_setting_row(ls_frame, "冷却率 (焼きなまし):", self.cooling_rate_var, 3, is_double=True, min_val=0.001, max_val=0.9999)
        logger.debug("SeminarGUI: 局所探索設定フレームを作成しました。")

        # レポート設定
        report_frame = ttk.LabelFrame(settings_frame, text="レポート設定", padding="10")
        report_frame.pack(pady=10, fill="x")
        ttk.Checkbutton(report_frame, text="PDFレポートを生成", variable=self.generate_pdf_report_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(report_frame, text="CSVレポートを生成", variable=self.generate_csv_report_var).pack(anchor="w", pady=2)
        logger.debug("SeminarGUI: レポート設定フレームを作成しました。")

        # デバッグ/ロギング設定
        debug_frame = ttk.LabelFrame(settings_frame, text="デバッグ/ロギング", padding="10")
        debug_frame.pack(pady=10, fill="x")
        
        # Checkbuttonをgrid()に変更
        debug_row = 0
        ttk.Checkbutton(debug_frame, text="デバッグモード", variable=self.debug_mode_var).grid(row=debug_row, column=0, columnspan=2, padx=5, pady=2, sticky="w")
        debug_row += 1
        ttk.Checkbutton(debug_frame, text="ログ出力", variable=self.log_enabled_var).grid(row=debug_row, column=0, columnspan=2, padx=5, pady=2, sticky="w")
        debug_row += 1
        
        # 乱数シードの入力フィールドを追加
        self._create_setting_row(debug_frame, "乱数シード:", self.random_seed_var, debug_row, min_val=0, max_val=99999999)
        
        debug_frame.columnconfigure(1, weight=1) # Ensure column 1 expands for entries
        logger.debug("SeminarGUI: デバッグ/ロギング設定フレームを作成しました。")

        logger.debug("SeminarGUI: 設定タブの作成が完了しました。")


    def _create_setting_row(self, parent_frame, label_text, tk_var, row, min_val=None, max_val=None, step=1, is_double=False):
        """設定項目の行をGUIに作成するヘルパー関数。"""
        logger.debug(f"SeminarGUI: 設定行を作成中: '{label_text}' (row: {row})")
        ttk.Label(parent_frame, text=label_text).grid(row=row, column=0, padx=5, pady=2, sticky="w")
        if is_double:
            entry = ttk.Spinbox(parent_frame, from_=min_val, to=max_val, increment=step, textvariable=tk_var, width=15, format="%.3f")
        else:
            entry = ttk.Spinbox(parent_frame, from_=min_val, to=max_val, increment=step, textvariable=tk_var, width=15)
        entry.grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        # 修正: grid_column_configure の代わりに columnconfigure を使用
        parent_frame.columnconfigure(1, weight=1) 
        logger.debug(f"SeminarGUI: 設定行 '{label_text}' の配置が完了しました。")

    def _create_results_tab(self):
        """結果表示タブを作成する。"""
        logger.debug("SeminarGUI: 結果表示タブを作成します。")
        results_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(results_frame, text="結果")

        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD, state=tk.DISABLED, width=80, height=20)
        self.results_text.pack(padx=5, pady=5, fill="both", expand=True)
        logger.debug("SeminarGUI: 結果表示タブの作成が完了しました。")

    def _create_logs_tab(self):
        """ログ表示タブを作成し、TextHandlerを設定する。"""
        logger.debug("SeminarGUI: ログ表示タブを作成します。")
        logs_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(logs_frame, text="ログ")

        self.log_text = scrolledtext.ScrolledText(logs_frame, wrap=tk.WORD, state=tk.DISABLED, width=80, height=20)
        self.log_text.pack(padx=5, pady=5, fill="both", expand=True)

        # カスタムハンドラを設定して、ログメッセージをScrolledTextにリダイレクト
        # TextHandlerはここで一度だけ初期化される
        self.text_handler = TextHandler(self.log_text, self.root) # self.root を渡す
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.text_handler.setFormatter(formatter)
        logging.getLogger().addHandler(self.text_handler) # ルートロガーに追加
        logger.debug("SeminarGUI: ログ表示タブの作成とカスタムロギングハンドラの設定が完了しました。")


    def _load_saved_settings(self):
        """保存されたGUI設定をロードし、UIに適用する。"""
        logger.debug("SeminarGUI: 保存された設定のロードを開始します。")
        # 現在はファイルパスのみ
        if 'seminars_file_path' in self.gui_settings:
            self.seminars_file_path_var.set(self.gui_settings['seminars_file_path'])
            logger.debug(f"SeminarGUI: セミナーファイルパスをロード: {self.gui_settings['seminars_file_path']}")
        if 'students_file_path' in self.gui_settings:
            self.students_file_path_var.set(self.gui_settings['students_file_path'])
            logger.debug(f"SeminarGUI: 学生ファイルパスをロード: {self.gui_settings['students_file_path']}")
        if 'data_input_method' in self.gui_settings:
            self.data_input_method_var.set(self.gui_settings['data_input_method'])
            logger.debug(f"SeminarGUI: データ入力方法をロード: {self.gui_settings['data_input_method']}")
            self._on_input_method_changed() # UIを更新
        
        # その他の設定もロード (config.jsonからのデフォルト値は_initialize_defaultsで設定済み)
        # gui_settings.ini に保存する設定を追加する場合はここにも記述
        if 'num_seminars' in self.gui_settings:
            self.num_seminars_var.set(self.config_manager.config.getint('GUI', 'num_seminars'))
        if 'num_students' in self.gui_settings:
            self.num_students_var.set(self.config_manager.config.getint('GUI', 'num_students'))
        if 'selected_optimizer' in self.gui_settings:
            self.optimization_strategy_var.set(self.gui_settings['selected_optimizer'])
        if 'generate_pdf_report' in self.gui_settings:
            self.generate_pdf_report_var.set(self.config_manager.config.getboolean('GUI', 'generate_pdf_report'))
        if 'generate_csv_report' in self.gui_settings:
            self.generate_csv_report_var.set(self.config_manager.config.getboolean('GUI', 'generate_csv_report'))
        
        # 新しく追加されたGUI設定変数のロード
        if 'min_capacity' in self.gui_settings:
            self.min_capacity_var.set(self.config_manager.config.getint('GUI', 'min_capacity'))
        if 'max_capacity' in self.gui_settings:
            self.max_capacity_var.set(self.config_manager.config.getint('GUI', 'max_capacity'))
        if 'min_preferences' in self.gui_settings:
            self.min_preferences_var.set(self.config_manager.config.getint('GUI', 'min_preferences'))
        if 'max_preferences' in self.gui_settings:
            self.max_preferences_var.set(self.config_manager.config.getint('GUI', 'max_preferences'))
        if 'preference_distribution' in self.gui_settings:
            self.preference_dist_var.set(self.gui_settings['preference_distribution'])
        if 'ga_population_size' in self.gui_settings:
            self.ga_population_size_var.set(self.config_manager.config.getint('GUI', 'ga_population_size'))
        if 'ga_generations' in self.gui_settings:
            self.ga_generations_var.set(self.config_manager.config.getint('GUI', 'ga_generations'))
        if 'ilp_time_limit' in self.gui_settings:
            self.ilp_time_limit_var.set(self.config_manager.config.getint('GUI', 'ilp_time_limit'))
        if 'cp_time_limit' in self.gui_settings:
            self.cp_time_limit_var.set(self.config_manager.config.getint('GUI', 'cp_time_limit'))
        if 'multilevel_clusters' in self.gui_settings:
            self.multilevel_clusters_var.set(self.config_manager.config.getint('GUI', 'multilevel_clusters'))
        if 'greedy_ls_iterations' in self.gui_settings:
            self.greedy_ls_iterations_var.set(self.config_manager.config.getint('GUI', 'greedy_ls_iterations'))
        if 'local_search_iterations' in self.gui_settings:
            self.local_search_iterations_var.set(self.config_manager.config.getint('GUI', 'local_search_iterations'))
        if 'initial_temperature' in self.gui_settings:
            self.initial_temperature_var.set(self.config_manager.config.getfloat('GUI', 'initial_temperature'))
        if 'cooling_rate' in self.gui_settings:
            self.cooling_rate_var.set(self.config_manager.config.getfloat('GUI', 'cooling_rate'))
        if 'debug_mode' in self.gui_settings:
            self.debug_mode_var.set(self.config_manager.config.getboolean('GUI', 'debug_mode'))
        if 'log_enabled' in self.gui_settings:
            self.log_enabled_var.set(self.config_manager.config.getboolean('GUI', 'log_enabled'))
        if 'random_seed' in self.gui_settings:
            self.random_seed_var.set(self.config_manager.config.getint('GUI', 'random_seed'))


        logger.info("SeminarGUI: 保存された設定のロードが完了しました。")

    def _save_current_settings(self):
        """現在のGUI設定を保存する。"""
        logger.debug("SeminarGUI: 現在の設定の保存を開始します。")
        settings_to_save = {
            'seminars_file_path': self.seminars_file_path_var.get(),
            'students_file_path': self.students_file_path_var.get(),
            'data_input_method': self.data_input_method_var.get(),
            'num_seminars': str(self.num_seminars_var.get()),
            'num_students': str(self.num_students_var.get()),
            'selected_optimizer': self.optimization_strategy_var.get(),
            'generate_pdf_report': str(self.generate_pdf_report_var.get()),
            'generate_csv_report': str(self.generate_csv_report_var.get()),
            # その他の設定変数もここに追加
            'min_capacity': str(self.min_capacity_var.get()),
            'max_capacity': str(self.max_capacity_var.get()),
            'min_preferences': str(self.min_preferences_var.get()),
            'max_preferences': str(self.max_preferences_var.get()),
            'preference_distribution': self.preference_dist_var.get(),
            'ga_population_size': str(self.ga_population_size_var.get()),
            'ga_generations': str(self.ga_generations_var.get()),
            'ilp_time_limit': str(self.ilp_time_limit_var.get()),
            'cp_time_limit': str(self.cp_time_limit_var.get()),
            'multilevel_clusters': str(self.multilevel_clusters_var.get()),
            'greedy_ls_iterations': str(self.greedy_ls_iterations_var.get()),
            'local_search_iterations': str(self.local_search_iterations_var.get()),
            'initial_temperature': str(self.initial_temperature_var.get()),
            'cooling_rate': str(self.cooling_rate_var.get()),
            'debug_mode': str(self.debug_mode_var.get()),
            'log_enabled': str(self.log_enabled_var.get()),
            'random_seed': str(self.random_seed_var.get()),
        }
        self.config_manager.save_gui_settings(settings_to_save)
        logger.info("SeminarGUI: 現在の設定の保存が完了しました。")


    def _run_optimization(self):
        """最適化処理を開始する。"""
        logger.info("SeminarGUI: 最適化処理の開始をリクエストされました。")
        if self.is_optimizing: # self.optimization_thread.is_alive() の代わりにフラグを使用
            messagebox.showinfo("情報", "最適化処理が既に実行中です。")
            logger.warning("SeminarGUI: 最適化処理が既に実行中のため、新規開始を拒否しました。")
            return

        # GUIの設定値バリデーション
        if not InputValidator.validate_settings(self):
            logger.warning("SeminarGUI: 設定値の検証に失敗したため、最適化を中止しました。")
            return

        # 進捗ダイアログを閉じる (もし開いている場合)
        if self.progress_dialog and self.progress_dialog.dialog.winfo_exists():
            self.progress_dialog.close()
            logger.debug("SeminarGUI: 既存のプログレスダイアログを閉じました。")

        self.progress_dialog = ProgressDialog(self.root)
        self.progress_dialog.cancel_callback = self._cancel_optimization # キャンセルボタンにコールバックを設定
        self.cancel_event.clear() # イベントをリセット
        self.is_optimizing = True # 最適化開始フラグを設定
        self.optimize_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        logger.debug("SeminarGUI: 新しいプログレスダイアログを初期化し、キャンセルイベントをリセットしました。")

        selected_method = self.data_input_method_var.get()
        seminars_data: List[Dict[str, Any]] = []
        students_data: List[Dict[str, Any]] = []
        
        # DataGeneratorのインスタンス化時にconfigとロガーを渡す
        data_generator = DataGenerator(self.optimization_config, logger) 
        logger.debug(f"SeminarGUI: データ入力方法: '{selected_method}'")

        try:
            if selected_method == "json":
                seminars_file = self.seminars_file_path_var.get()
                students_file = self.students_file_path_var.get()
                if not seminars_file or not students_file:
                    raise ValueError("JSONファイルパスが指定されていません。")
                seminars_data, students_data = data_generator.load_from_json(seminars_file, students_file)
                logger.info("SeminarGUI: JSONファイルからデータをロードしました。")
            elif selected_method == "csv":
                seminars_file = self.seminars_file_path_var.get()
                students_file = self.students_file_path_var.get()
                if not seminars_file or not students_file:
                    raise ValueError("CSVファイルパスが指定されていません。")
                seminars_data, students_data = data_generator.load_from_csv(seminars_file, students_file)
                logger.info("SeminarGUI: CSVファイルからデータをロードしました。")
            elif selected_method == "generate":
                seminars_data, students_data = data_generator.generate_data(
                    num_seminars=self.num_seminars_var.get(),
                    min_capacity=self.min_capacity_var.get(),
                    max_capacity=self.max_capacity_var.get(),
                    num_students=self.num_students_var.get(),
                    min_preferences=self.min_preferences_var.get(),
                    max_preferences=self.max_preferences_var.get(),
                    preference_distribution=self.preference_dist_var.get()
                )
                logger.info("SeminarGUI: ランダムデータを生成しました。")
            elif selected_method == "manual":
                seminars_data = self.manual_seminar_data
                students_data = self.manual_student_data
                if not seminars_data or not students_data:
                    raise ValueError("手動入力データが不足しています。セミナーと学生のデータを入力してください。")
                # 手動入力データもDataGeneratorのスキーマで検証
                data_generator._validate_data(seminars_data, students_data) # DataGeneratorの検証メソッドを呼び出す
                logger.info("SeminarGUI: 手動入力データを使用します。")
            
            # レポート表示用にオリジナルデータを保持
            self.seminars_data_for_report = seminars_data
            self.students_data_for_report = students_data

            # データが正常に準備されたら、configを構築して最適化を開始
            self._update_optimization_config_from_gui() # GUIからconfigを更新
            logger.debug("SeminarGUI: 最適化設定をGUIから更新しました。")
            
            self.optimization_thread = threading.Thread(
                target=self._run_optimization_thread,
                args=(seminars_data, students_data, self.optimization_config, self.cancel_event, self._update_progress)
            )
            self.optimization_thread.start()
            self.progress_dialog.start_progress_bar(f"最適化開始中: {self.optimization_strategy_var.get()}")
            self.root.after(100, self._check_optimization_thread)
            logger.info("SeminarGUI: 最適化スレッドを開始しました。")

        except Exception as e:
            messagebox.showerror("データ準備エラー", f"データの準備中にエラーが発生しました: {e}")
            logger.exception("SeminarGUI: データの準備中に予期せぬエラーが発生しました。")
            if self.progress_dialog:
                self.progress_dialog.close()
                logger.debug("SeminarGUI: データ準備エラーのためプログレスダイアログを閉じました。")
            self._reset_gui_state() # エラー時もGUI状態をリセット

    def _cancel_optimization(self):
        """最適化処理をキャンセルする。"""
        logger.info("SeminarGUI: ユーザーによって最適化のキャンセルが要求されました。")
        self.cancel_event.set() # キャンセルイベントを設定
        if self.progress_dialog:
            self.progress_dialog.update_progress_message("キャンセル中です。しばらくお待ちください...")
            logger.debug("SeminarGUI: プログレスダイアログにキャンセルメッセージを表示しました。")

    def _update_optimization_config_from_gui(self):
        """GUIの現在の設定をself.optimization_configに反映する"""
        logger.debug("SeminarGUI: GUI設定を最適化コンフィグに反映中。")
        self.optimization_config["optimization_strategy"] = self.optimization_strategy_var.get()
        self.optimization_config["ga_population_size"] = self.ga_population_size_var.get()
        self.optimization_config["ga_generations"] = self.ga_generations_var.get()
        self.optimization_config["ilp_time_limit"] = self.ilp_time_limit_var.get()
        self.optimization_config["cp_time_limit"] = self.cp_time_limit_var.get()
        self.optimization_config["multilevel_clusters"] = self.multilevel_clusters_var.get()
        self.optimization_config["greedy_ls_iterations"] = self.greedy_ls_iterations_var.get()
        self.optimization_config["local_search_iterations"] = self.local_search_iterations_var.get()
        self.optimization_config["initial_temperature"] = self.initial_temperature_var.get()
        self.optimization_config["cooling_rate"] = self.cooling_rate_var.get()
        self.optimization_config["generate_pdf_report"] = self.generate_pdf_report_var.get()
        self.optimization_config["generate_csv_report"] = self.generate_csv_report_var.get()
        self.optimization_config["debug_mode"] = self.debug_mode_var.get()
        self.optimization_config["log_enabled"] = self.log_enabled_var.get()
        # 乱数シードをconfigに含める
        self.optimization_config["random_seed"] = self.random_seed_var.get()
        
        # データ生成関連のパラメータもconfigに含める
        self.optimization_config["num_seminars"] = self.num_seminars_var.get()
        self.optimization_config["min_capacity"] = self.min_capacity_var.get()
        self.optimization_config["max_capacity"] = self.max_capacity_var.get()
        self.optimization_config["num_students"] = self.num_students_var.get()
        self.optimization_config["min_preferences"] = self.min_preferences_var.get()
        self.optimization_config["max_preferences"] = self.max_preferences_var.get()
        self.optimization_config["preference_distribution"] = self.preference_dist_var.get()
        logger.debug("SeminarGUI: 最適化コンフィグの更新が完了しました。")

    def _run_optimization_thread(self, seminars_data, students_data, config, cancel_event, progress_callback):
        """
        最適化サービスを別スレッドで実行する。
        """
        logger.info(f"SeminarGUI: 最適化スレッド開始: データ数 (セミナー: {len(seminars_data)}, 学生: {len(students_data)})")
        try:
            results = run_optimization_service(
                seminars=seminars_data,
                students=students_data,
                config=config,
                cancel_event=cancel_event,
                progress_callback=progress_callback
            )
            logger.info("SeminarGUI: 最適化サービスが完了しました。")
            # GUI更新はメインスレッドで行う
            self.root.after(0, self._handle_optimization_completion, results, seminars_data, students_data) # seminars_data, students_data も渡す
        except Exception as e:
            logger.exception("SeminarGUI: 最適化スレッド内で予期せぬエラーが発生しました。")
            error_results = OptimizationResult(
                status="ERROR",
                message=f"最適化スレッドエラー: {e}",
                best_score=-1,
                best_assignment={},
                seminar_capacities={s['id']: s['capacity'] for s in seminars_data} if seminars_data else {},
                unassigned_students=[s['id'] for s in students_data] if students_data else [],
                optimization_strategy=config.get("optimization_strategy", "Unknown")
            )
            self.root.after(0, self._handle_optimization_completion, error_results, seminars_data, students_data) # エラー時もデータは渡す
        finally:
            if self.progress_dialog:
                self.root.after(0, self.progress_dialog.close)
                logger.debug("SeminarGUI: 最適化スレッド終了時にプログレスダイアログを閉じました。")


    def _check_optimization_thread(self):
        """最適化スレッドの終了を定期的にチェックする。"""
        logger.debug("SeminarGUI: 最適化スレッドの終了をチェック中。")
        if self.optimization_thread and self.optimization_thread.is_alive():
            self.root.after(100, self._check_optimization_thread)
        else:
            logger.info("SeminarGUI: 最適化スレッドが終了しました。")
            # スレッドが終了した後の処理は _handle_optimization_completion で行われる


    def _update_progress(self, message: str):
        """プログレスバーとログにメッセージを更新するコールバック関数。"""
        # この関数は別スレッドから呼び出されるため、直接GUIを操作せず、root.after()を使用する
        # TextHandlerが既にロギングシステムにアタッチされているため、logger.info()を呼び出すだけでGUIに表示される
        logger.info(message)


    def _handle_optimization_completion(self, results: OptimizationResult, seminars_data: List[Dict[str, Any]], students_data: List[Dict[str, Any]]):
        """最適化完了後の処理（メインスレッドで実行）。"""
        logger.info(f"SeminarGUI: 最適化完了処理を開始します。ステータス: {results.status}")
        if self.progress_dialog:
            self.progress_dialog.close() # プログレスダイアログを閉じる
            logger.debug("SeminarGUI: 最適化完了時にプログレスダイアログを閉じました。")

        if results.status == "CANCELLED":
            messagebox.showinfo("最適化結果", results.message)
            logger.info("SeminarGUI: 最適化がキャンセルされました。")
        elif results.status == "ERROR" or results.status == "FAILED" or results.status == "NO_SOLUTION_FOUND":
            messagebox.showerror("最適化エラー", results.message)
            logger.error(f"SeminarGUI: 最適化エラーが発生しました: {results.message}")
        else:
            messagebox.showinfo("最適化完了", results.message)
            logger.info("SeminarGUI: 最適化が成功しました。")
        
        # 結果表示ロジック
        self._display_results(results, seminars_data, students_data) # seminars_data, students_data を渡す
        self._reset_gui_state() # GUI状態をリセット
        logger.debug("SeminarGUI: 最適化完了処理が終了しました。")

    def _display_results(self, results: OptimizationResult, seminars_data: List[Dict[str, Any]], students_data: List[Dict[str, Any]]):
        """
        最適化結果を結果タブのテキストエリアに表示する。
        """
        logger.info("SeminarGUI: 最適化結果を表示します。")
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END) # クリア

        self.results_text.insert(tk.END, "--- 最適化結果 ---\n")
        self.results_text.insert(tk.END, f"ステータス: {results.status}\n")
        self.results_text.insert(tk.END, f"メッセージ: {results.message}\n")
        self.results_text.insert(tk.END, f"ベストスコア: {results.best_score:.2f}\n")
        self.results_text.insert(tk.END, f"最適化戦略: {results.optimization_strategy}\n")
        self.results_text.insert(tk.END, f"未割り当て学生数: {len(results.unassigned_students)}\n")
        if results.unassigned_students:
            self.results_text.insert(tk.END, f"  未割り当て学生: {', '.join(results.unassigned_students)}\n")
        
        self.results_text.insert(tk.END, "\n--- 割り当て概要 ---\n")
        seminar_counts: Dict[str, int] = {s_id: 0 for s_id in results.seminar_capacities.keys()}
        for student_id, seminar_id in results.best_assignment.items():
            seminar_counts[seminar_id] = seminar_counts.get(seminar_id, 0) + 1

        for seminar_id, capacity in results.seminar_capacities.items():
            assigned_count = seminar_counts.get(seminar_id, 0)
            remaining_capacity = capacity - assigned_count
            self.results_text.insert(tk.END, f"セミナー {seminar_id}: 割り当て数 {assigned_count} / 定員 {capacity} (残り: {remaining_capacity})\n")

        self.results_text.insert(tk.END, "\n--- 個別割り当て (上位20件のみ) ---\n")
        # 大量データの場合にGUIが重くならないように制限
        display_limit = 20
        count = 0
        
        # 学生データマップを作成して、希望順位を効率的に検索できるようにする
        students_data_map = {s['id']: s for s in students_data}

        for student_id, assigned_seminar in results.best_assignment.items():
            if count >= display_limit:
                self.results_text.insert(tk.END, f"...\n(残りの割り当てはCSV/PDFレポートを参照してください)\n")
                break
            
            # 学生の希望順位を特定
            student_info = students_data_map.get(student_id)
            preferences = student_info.get('preferences', []) if student_info else []
            
            rank_str = "希望外"
            if assigned_seminar in preferences:
                try:
                    rank = preferences.index(assigned_seminar) + 1
                    rank_str = f"第{rank}希望"
                except ValueError:
                    # これは発生しないはずだが、念のため
                    pass
            
            self.results_text.insert(tk.END, f"学生 {student_id}: {assigned_seminar} ({rank_str})\n")
            count += 1

        self.results_text.config(state=tk.DISABLED)
        self.notebook.select(self.notebook.index("end") - 1) # 結果タブに切り替える (ログタブの1つ前)
        logger.debug("SeminarGUI: 最適化結果の表示が完了しました。")


    def clear_results(self):
        """結果表示エリアをクリアする"""
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        self.results_text.config(state=tk.DISABLED)
        logger.debug("SeminarGUI: 結果表示エリアをクリアしました。")


    def _reset_gui_state(self):
        """
        最適化終了後にGUIの状態をリセットする（メインスレッドで実行）。
        """
        self.optimize_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        self.cancel_button.config(text="キャンセル") # テキストを元に戻す
        self.is_optimizing = False
        logger.info("GUIの状態がリセットされました。")

    def _on_closing(self):
        """
        ウィンドウが閉じられようとしたときの処理。
        実行中の最適化があれば確認ダイアログを表示。
        """
        logger.debug("SeminarGUI: ウィンドウを閉じようとしています。")
        if self.is_optimizing:
            logger.info("SeminarGUI: 最適化処理が実行中のため、終了確認ダイアログを表示します。")
            if messagebox.askyesno("確認", "最適化処理が実行中です。強制終了しますか？"):
                self.cancel_event.set() # キャンセルイベントを設定
                if self.progress_dialog and self.progress_dialog.dialog.winfo_exists():
                    self.progress_dialog.close()
                if self.optimization_thread and self.optimization_thread.is_alive():
                    self.optimization_thread.join(timeout=1.0) # スレッドが終了するのを待つ（短い時間）
                
                # GUIハンドラを削除してからGUIを破棄
                if self.text_handler in logging.getLogger().handlers:
                    logging.getLogger().removeHandler(self.text_handler)
                    logger.debug("SeminarGUI: TextHandlerをロギングシステムから削除しました。")
                self.root.destroy()
                logger.info("SeminarGUI: 最適化を強制終了し、アプリケーションを閉じました。")
            else:
                logger.debug("SeminarGUI: アプリケーションの終了がキャンセルされました。")
                return # ウィンドウを閉じない
        else:
            self._save_current_settings() # 終了時に設定を保存
            # GUIハンドラを削除してからGUIを破棄
            if self.text_handler in logging.getLogger().handlers:
                logging.getLogger().removeHandler(self.text_handler)
                logger.debug("SeminarGUI: TextHandlerをロギングシステムから削除しました。")
            self.root.destroy()
            logger.info("SeminarGUI: アプリケーションを正常に閉じました。")

    def run(self):
        """GUIのメインループを開始する。"""
        logger.info("SeminarGUI: GUIメインループを開始します。")
        self.root.mainloop()
        # メインループ終了後にもログが出力される可能性があるため、ここでもハンドラを削除
        if self.text_handler in logging.getLogger().handlers:
            logging.getLogger().removeHandler(self.text_handler)
            logger.debug("SeminarGUI: GUIメインループ終了後にTextHandlerを削除しました。")
        logger.info("SeminarGUI: GUIメインループが終了しました。")

# アプリケーションのエントリポイント
if __name__ == "__main__":
    root = tk.Tk()
    app = SeminarGUI(root)
    app.run()
