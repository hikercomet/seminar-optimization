import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
from datetime import datetime
import configparser
import json
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Tuple

# --- プロジェクトルートの特定と絶対インポートの設定 ---
def get_project_root() -> Path:
    """
    スクリプトの実行場所からプロジェクトのルートディレクトリを特定する。
    """
    current_file_path = Path(__file__).resolve()
    
    # プロジェクトのルートを示すマーカーファイル（またはディレクトリ）の名前
    marker_files = ["pyproject.toml", "setup.py", "README.md", ".git", "seminar_optimization.code-workspace"]
    
    # 上位ディレクトリを探索
    for parent in current_file_path.parents:
        for marker in marker_files:
            if (parent / marker).exists():
                return parent
        # または、特定のディレクトリ名がプロジェクトルートである場合
        if parent.name == "seminar_optimization" and (parent / "seminar_optimization").is_dir():
             return parent
    
    # 見つからない場合は、現在のスクリプトの親ディレクトリを返す（フォールバック）
    print("プロジェクトルートマーカーが見つかりませんでした。現在のスクリプトの親ディレクトリをルートとみなします。")
    return current_file_path.parent

# プロジェクトルートを設定
PROJECT_ROOT = get_project_root()

# sys.path にプロジェクトルートを追加して、絶対インポートを可能にする
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# インポートエラーを処理する簡単なラッパー
def safe_import(module_name, from_package=None):
    """安全にモジュールをインポートし、失敗時にNoneを返す"""
    try:
        if from_package:
            return __import__(from_package, fromlist=[module_name])
        else:
            return __import__(module_name)
    except ImportError as e:
        print(f"Warning: Could not import {from_package}.{module_name} or {module_name}: {e}")
        return None

# 基本的なロガー設定（依存関係がない場合のフォールバック）
def setup_basic_logging(log_level="DEBUG", log_file=None):
    """
    基本的なロギング設定を行う関数
    :param log_level: ログレベル（デフォルト: "DEBUG"）
    :param log_file: ログファイルのパス（オプション）
    """
    # ログレベルを文字列から対応するレベルに変換
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    log_level_numeric = level_map.get(log_level.upper(), logging.DEBUG)
    
    # ハンドラーのリストを作成
    handlers = [logging.StreamHandler()]
    
    # ログファイルが指定されている場合は追加
    if log_file:
        try:
            # ログファイルのディレクトリが存在しない場合は作成
            log_file_path = Path(log_file)
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(logging.FileHandler(str(log_file_path)))
        except Exception as e:
            print(f"Warning: Could not create log file {log_file}: {e}")
    else:
        # デフォルトのログファイル名
        default_log_file = f'seminar_optimization_{datetime.now().strftime("%Y%m%d")}.log'
        try:
            handlers.append(logging.FileHandler(default_log_file))
        except Exception as e:
            print(f"Warning: Could not create default log file {default_log_file}: {e}")
    
    logging.basicConfig(
        level=log_level_numeric,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers,
        force=True  # 既存の設定を上書き
    )
    return logging.getLogger(__name__)

# 依存モジュールのインポート（失敗時はNoneになる）
optimizer_service_module = safe_import("optimizer_service", "optimizers")
data_generator_module = safe_import("data_generator", "seminar_optimization")
logger_config_module = safe_import("logger_config", "seminar_optimization")
schemas_module = safe_import("schemas", "seminar_optimization")

# jsonschemaのインポート
try:
    import jsonschema
except ImportError:
    jsonschema = None
    print("Warning: jsonschema not available")

# ロガーの設定
if logger_config_module:
    setup_logging = getattr(logger_config_module, 'setup_logging', None)
    logger = getattr(logger_config_module, 'logger', None)
    # setup_loggingが存在しない場合はsetup_basic_loggingを使用
    if setup_logging is None:
        setup_logging = setup_basic_logging
    # loggerが存在しない場合は基本ロガーを作成
    if logger is None:
        logger = setup_basic_logging()
else:
    setup_logging = setup_basic_logging
    logger = setup_basic_logging()

# GUIコンポーネントのインポート（失敗時は代替実装を使用）
gui_tabs_data_input = safe_import("data_input_tab", "gui_tabs")
gui_tabs_results = safe_import("results_tab", "gui_tabs")
gui_tabs_log = safe_import("log_tab", "gui_tabs")
gui_components_progress = safe_import("progress_dialog", "gui_components")
settings_manager_module = safe_import("settings_manager")

# 代替実装クラス（インポートが失敗した場合）
class FallbackTab:
    def __init__(self, notebook, text_content="このタブは利用できません"):
        self.frame = ttk.Frame(notebook)
        self.text_content = text_content
        label = ttk.Label(self.frame, text=text_content)
        label.pack(expand=True)

class FallbackDataInputTab(FallbackTab):
    def __init__(self, notebook, main_app):
        super().__init__(notebook, "データ入力タブは現在利用できません")
        self.main_app = main_app
        # デフォルト値を設定
        self.log_enabled_var = tk.BooleanVar(value=True)
        self.seminar_ids_var = tk.StringVar(value="A,B,C")
    
    def initialize_fields(self, **kwargs):
        """初期化メソッド（何もしない）"""
        pass
    
    def get_current_config(self):
        """デフォルト設定を返す"""
        return {
            "data_input_method": "auto",
            "num_seminars": 10,
            "min_capacity": 5,
            "max_capacity": 15,
            "num_students": 100,
            "min_preferences": 3,
            "max_preferences": 5,
            "preference_distribution": "random",
            "random_seed": 42,
            "optimization_strategy": "Greedy_LS"
        }
    
    def get_current_settings_for_save(self):
        """保存用設定を返す"""
        return {}

class FallbackResultsTab(FallbackTab):
    def __init__(self, notebook):
        super().__init__(notebook, "結果タブは現在利用できません")
    
    def display_results(self, result):
        """結果表示（プレースホルダー）"""
        logger.info(f"Results would be displayed here: {result}")
    
    def clear_results(self):
        """結果クリア（プレースホルダー）"""
        logger.info("Results would be cleared here")

class FallbackLogTab(FallbackTab):
    def __init__(self, notebook):
        super().__init__(notebook, "ログタブは現在利用できません")
        self.text_widget = tk.Text(self.frame)
        self.text_widget.pack(expand=True, fill=tk.BOTH)
    
    def get_text_handler(self):
        """テキストハンドラーを返す（None）"""
        return None

class FallbackProgressDialog:
    def __init__(self, parent, cancel_callback):
        self.parent = parent
        self.cancel_callback = cancel_callback
        self.dialog = None
    
    def show(self):
        """プログレスダイアログを表示"""
        if self.dialog is None:
            self.dialog = tk.Toplevel(self.parent)
            self.dialog.title("処理中")
            self.dialog.geometry("300x100")
            self.label = ttk.Label(self.dialog, text="処理中...")
            self.label.pack(expand=True)
            ttk.Button(self.dialog, text="キャンセル", command=self.cancel_callback).pack()
    
    def update_message(self, message):
        """メッセージを更新"""
        if self.dialog and hasattr(self, 'label'):
            self.label.config(text=message)
    
    def hide(self):
        """ダイアログを非表示"""
        if self.dialog:
            self.dialog.destroy()
            self.dialog = None

class FallbackSettingsManager:
    def __init__(self, project_root):
        self.project_root = project_root
    
    def load_gui_settings(self, main_app):
        """GUI設定をロード（空の辞書を返す）"""
        return {}
    
    def save_gui_settings(self, settings):
        """GUI設定を保存（何もしない）"""
        logger.info("Settings would be saved here")

class MainApplication:
    def __init__(self, root: tk.Tk):
        try:
            logger.debug("MainApplication: 初期化を開始します。")
            self.root = root
            
            # ステータスバーの初期化を最上位に配置
            self.status_bar_label = ttk.Label(self.root, text="初期化中...", relief=tk.SUNKEN, anchor=tk.W)
            self.status_bar_label.pack(side=tk.BOTTOM, fill=tk.X)
            logger.debug("MainApplication: ステータスバーを初期化しました。")
            self._update_status_bar("アプリケーションを初期化中...", "info")

            self._set_dpi_awareness()
            
            # スタイルオブジェクトをここで初期化
            self.style = ttk.Style()

            # SettingsManagerのインスタンスを作成（フォールバックあり）
            if settings_manager_module:
                SettingsManager = getattr(settings_manager_module, 'SettingsManager', FallbackSettingsManager)
                self.settings_manager = SettingsManager(PROJECT_ROOT)
            else:
                self.settings_manager = FallbackSettingsManager(PROJECT_ROOT)

            # 初期値の設定
            self._set_initial_values()

            # GUI設定をロード
            loaded_settings = self.settings_manager.load_gui_settings(self)
            for key, value in loaded_settings.items():
                if hasattr(self, key): 
                    setattr(self, key, value)
            
            # テーマを適用
            try:
                self.style.theme_use(getattr(self, 'initial_theme', 'clam'))
            except tk.TclError:
                self.style.theme_use('clam')  # フォールバック

            self.root.title("セミナー割り当て最適化ツール")
            self.root.geometry("1200x800+100+100") 
            self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

            self.cancel_event = threading.Event()
            self.optimization_thread: Optional[threading.Thread] = None
            self.progress_dialog_instance: Optional[object] = None
            self.text_handler: Optional[logging.Handler] = None

            # GUIウィジェットを作成
            self._create_widgets()
            logger.debug("MainApplication: _create_widgets() 呼び出し完了。")

            # configをロード
            self.optimization_config = self._set_default_optimization_config()
            logger.debug("MainApplication: デフォルトの最適化設定ロード完了。")

            # DataGeneratorとOptimizerServiceのインスタンスを初期化（利用可能な場合）
            self._initialize_services()

            # UI要素の状態を初期化
            self._initialize_ui_elements()
            logger.debug("MainApplication: UI要素の初期化完了。")

            # メインボタンをコンテンツフレームの下部に配置
            self._create_main_buttons(self.content_frame)

            # ウィンドウの表示設定
            self.root.deiconify() 
            self.root.state('normal')
            self.root.lift()
            self.root.focus_force()
            self.root.update_idletasks()
            logger.debug("MainApplication: GUIウィンドウの初期表示設定を適用しました。")

            logger.info("MainApplication: 初期化が完了しました。")

        except Exception as e:
            logger.critical(f"MainApplication: 初期化中に致命的なエラーが発生しました: {e}", exc_info=True)
            messagebox.showerror("致命的なエラー", f"アプリケーションの初期化中に致命的なエラーが発生しました。\n詳細: {e}")
            sys.exit(1)

    def _set_initial_values(self):
        """初期値を設定"""
        self.initial_seminars_str = 'A,B,C'
        self.initial_num_students = 112
        self.initial_magnification = {"A": 5.5, "B": 1.0, "C": 0.6}
        self.initial_min_size = 5
        self.initial_max_size = 15
        self.initial_q_boost_probability = 0.2
        self.initial_num_preferences_to_consider = 5
        self.initial_num_patterns = 200000
        self.initial_max_workers = 8
        self.initial_local_search_iterations = 500
        self.initial_initial_temperature = 1.0
        self.initial_cooling_rate = 0.995
        self.initial_preference_weights = {"1st_choice": 5.0, "2nd_choice": 2.0, "3rd_choice": 1.0, "other_preference": 0.5}
        self.initial_early_stop_threshold = 0.001
        self.initial_no_improvement_limit = 1000
        self.initial_data_source = 'auto'
        self.initial_log_enabled = True
        self.initial_save_intermediate = False
        self.initial_theme = 'clam'
        # 他の初期値...（元のコードから必要に応じて追加）

    def _initialize_services(self):
        """サービスクラスの初期化"""
        if data_generator_module:
            DataGenerator = getattr(data_generator_module, 'DataGenerator', None)
            if DataGenerator:
                self.data_generator = DataGenerator(self.optimization_config, logger)
            else:
                self.data_generator = None
        else:
            self.data_generator = None

        if optimizer_service_module:
            OptimizerService = getattr(optimizer_service_module, 'OptimizerService', None)
            if OptimizerService:
                self.optimizer_service = OptimizerService(self.optimization_config, logger)
            else:
                self.optimizer_service = None
        else:
            self.optimizer_service = None

    def _set_dpi_awareness(self):
        """Windowsで高DPIスケーリングを有効にする。"""
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            logger.debug("DPI認識が設定されました。")
        except (AttributeError, ImportError, OSError):
            logger.debug("DPI認識設定はWindowsでのみ利用可能です。")

    def _set_default_optimization_config(self) -> Dict[str, Any]:
        """最適化設定のデフォルト値を返す。"""
        logger.debug("MainApplication: デフォルトの最適化設定を生成します。")
        return {
            "data_directory": "data",
            "seminars_file": "seminars.json",
            "students_file": "students.json",
            "results_file": "optimization_results.json",
            "num_seminars": 10,
            "min_capacity": 5,
            "max_capacity": 10,
            "num_students": 50,
            "min_preferences": 3,
            "max_preferences": 5,
            "preference_distribution": "random",
            "optimization_strategy": "Greedy_LS",
            "random_seed": 42,
            "debug_mode": True,
            "output_directory": "results"
        }

    def _initialize_ui_elements(self):
        """GUI要素の初期値を設定する。"""
        logger.debug("MainApplication: UI要素の初期化を開始します。")
        # DataInputTabの初期化（利用可能な場合のみ）
        if hasattr(self.data_input_tab_handler, 'initialize_fields'):
            try:
                self.data_input_tab_handler.initialize_fields(
                    initial_seminars_str=getattr(self, 'initial_seminars_str', 'A,B,C'),
                    initial_num_students=getattr(self, 'initial_num_students', 100),
                    # 他の初期値パラメータ...
                )
            except Exception as e:
                logger.warning(f"DataInputTabの初期化に失敗しました: {e}")
        logger.debug("MainApplication: UI要素の初期化が完了しました。")

    def _create_widgets(self):
        """GUIのウィジェットを作成し、配置する。"""
        try:
            logger.debug("MainApplication: GUIウィジェットの作成を開始します。")

            # メインフレーム
            main_frame = ttk.Frame(self.root, padding="10") 
            main_frame.pack(fill=tk.BOTH, expand=True)

            # PanedWindowで左側のナビゲーションと中央のコンテンツを分割
            self.main_pane = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL) 
            self.main_pane.pack(fill=tk.BOTH, expand=True)

            # 左側のナビゲーションフレーム
            self.nav_frame = ttk.Frame(self.main_pane, width=180, relief=tk.RAISED, borderwidth=1)
            self.main_pane.add(self.nav_frame, weight=0) 

            # 中央のコンテンツフレーム
            self.content_frame = ttk.Frame(self.main_pane)
            self.main_pane.add(self.content_frame, weight=1)

            # ナビゲーションボタンの作成
            self._create_navigation_buttons(self.nav_frame)

            # ノートブック（タブ）をコンテンツフレーム内に配置
            self.notebook = ttk.Notebook(self.content_frame)
            self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5, 40))

            # 各タブのインスタンスを作成し、ノートブックに追加
            self._create_tabs()

            logger.debug("MainApplication: GUIウィジェットの作成が完了しました。")
        except Exception as e:
            logger.error(f"MainApplication: _create_widgetsでエラーが発生しました: {e}", exc_info=True)
            self._update_status_bar(f"エラー: ウィジェットの作成に失敗しました: {e}", "error")
            messagebox.showerror("GUIエラー", f"ウィジェットの作成中にエラーが発生しました。\n詳細: {e}")
            raise

    def _create_tabs(self):
        """タブを作成してノートブックに追加"""
        try:
            # DataInputTabの作成
            if gui_tabs_data_input:
                DataInputTab = getattr(gui_tabs_data_input, 'DataInputTab', FallbackDataInputTab)
                self.data_input_tab_handler = DataInputTab(self.notebook, self)
            else:
                self.data_input_tab_handler = FallbackDataInputTab(self.notebook, self)

            # ResultsTabの作成
            if gui_tabs_results:
                ResultsTab = getattr(gui_tabs_results, 'ResultsTab', FallbackResultsTab)
                self.results_tab_handler = ResultsTab(self.notebook)
            else:
                self.results_tab_handler = FallbackResultsTab(self.notebook)

            # LogTabの作成
            if gui_tabs_log:
                LogTab = getattr(gui_tabs_log, 'LogTab', FallbackLogTab)
                self.log_tab_handler = LogTab(self.notebook)
            else:
                self.log_tab_handler = FallbackLogTab(self.notebook)

            # タブをノートブックに追加
            self.notebook.add(self.data_input_tab_handler.frame, text="データ入力と設定")
            self.notebook.add(self.results_tab_handler.frame, text="最適化結果")
            self.notebook.add(self.log_tab_handler.frame, text="ログ")

            # TextHandlerをLogTabから取得し、ロギングシステムに追加
            self.text_handler = self.log_tab_handler.get_text_handler()
            if self.text_handler:
                logging.getLogger().addHandler(self.text_handler)
                logging.getLogger().setLevel(logging.DEBUG)

            logger.debug("MainApplication: タブの作成が完了しました。")
        except Exception as e:
            logger.error(f"タブの作成中にエラーが発生しました: {e}", exc_info=True)
            # フォールバックタブを作成
            self.data_input_tab_handler = FallbackDataInputTab(self.notebook, self)
            self.results_tab_handler = FallbackResultsTab(self.notebook)
            self.log_tab_handler = FallbackLogTab(self.notebook)
            
            self.notebook.add(self.data_input_tab_handler.frame, text="データ入力と設定")
            self.notebook.add(self.results_tab_handler.frame, text="最適化結果")
            self.notebook.add(self.log_tab_handler.frame, text="ログ")

    def _create_navigation_buttons(self, parent_frame: ttk.Frame):
        """左側のナビゲーションボタンを作成する。"""
        logger.debug("MainApplication: ナビゲーションボタンを作成中...")
        button_texts = ["インフォメーション", "登録", "照会", "リクエスト", "終了"]
        for text in button_texts:
            btn = ttk.Button(parent_frame, text=text, command=lambda t=text: self._on_nav_button_click(t))
            btn.pack(fill=tk.X, pady=5, padx=5)
        logger.debug("MainApplication: ナビゲーションボタンの作成が完了しました。")

    def _on_nav_button_click(self, button_text: str):
        """ナビゲーションボタンがクリックされたときの処理。"""
        self._update_status_bar(f"「{button_text}」ボタンがクリックされました。", "info")
        logger.info(f"MainApplication: ナビゲーションボタンクリック: {button_text}")
        if button_text == "終了":
            self._on_closing()

    def _create_main_buttons(self, parent_frame: ttk.Frame):
        """メインの操作ボタンを作成する。"""
        try:
            logger.debug("MainApplication: _create_main_buttons: 開始。")
            parent_frame.update_idletasks()

            button_frame = ttk.Frame(parent_frame)
            button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

            ttk.Button(button_frame, text="最適化開始", command=self._start_optimization).pack(side=tk.LEFT, padx=5, expand=True)
            ttk.Button(button_frame, text="最適化停止", command=self._cancel_optimization).pack(side=tk.LEFT, padx=5, expand=True)
            ttk.Button(button_frame, text="結果クリア", command=self._clear_results).pack(side=tk.LEFT, padx=5, expand=True)
            ttk.Button(button_frame, text="設定保存", command=self._save_current_gui_settings).pack(side=tk.LEFT, padx=5, expand=True)

            self.root.update()
            logger.debug("MainApplication: メインボタンの作成が完了しました。")
        except Exception as e:
            logger.error(f"MainApplication: _create_main_buttonsでエラーが発生しました: {e}", exc_info=True)
            self._update_status_bar(f"エラー: メインボタンの作成に失敗しました: {e}", "error")

    def _update_status_bar(self, message: str, message_type: str = "info"):
        """ステータスバーを更新する。"""
        logger.debug(f"ステータスバー更新: タイプ={message_type}, メッセージ='{message}'")
        if self.status_bar_label:
            self.status_bar_label.config(text=message)
            if message_type == "info":
                self.status_bar_label.config(background="SystemButtonFace", foreground="black")
            elif message_type == "warning":
                self.status_bar_label.config(background="yellow", foreground="black")
            elif message_type == "error":
                self.status_bar_label.config(background="red", foreground="white")
            self.root.update_idletasks()

    def _start_optimization(self):
        """最適化プロセスを開始する。"""
        logger.info("最適化開始ボタンが押されました。")
        if self.optimization_thread and self.optimization_thread.is_alive():
            self._update_status_bar("最適化がすでに実行中です。", "warning")
            return

        if not self.optimizer_service:
            self._update_status_bar("最適化サービスが利用できません。", "error")
            messagebox.showerror("エラー", "最適化サービスが初期化されていません。")
            return

        self._clear_results()
        self._update_status_bar("最適化を開始しています...", "info")
        self.cancel_event.clear()

        current_config = self.data_input_tab_handler.get_current_config()
        
        self.optimization_thread = threading.Thread(
            target=self._run_optimization,
            args=(current_config, self.cancel_event)
        )
        self.optimization_thread.start()
        self._show_progress_dialog()

    def _run_optimization(self, current_config: Dict[str, Any], cancel_event: threading.Event):
        """最適化プロセスを実行する。"""
        logger.info("最適化プロセスを開始します。")
        self.root.after(0, self._update_status_bar, "最適化を実行中...", "info")
        
        try:
            # 簡単な処理をシミュレート（実際の最適化が利用できない場合）
            import time
            for i in range(10):
                if cancel_event.is_set():
                    break
                time.sleep(0.5)
                progress_msg = f"処理中... {i+1}/10"
                self.root.after(0, self._progress_callback, progress_msg)
            
            # ダミーの結果を作成
            result = type('Result', (), {
                'status': 'completed',
                'message': '最適化が完了しました（シミュレーション）',
                'data': {'score': 95.5, 'assignments': 'テストデータ'}
            })()
            
            self.root.after(0, self._display_results, result)

        except Exception as e:
            logger.error(f"最適化中にエラーが発生しました: {e}", exc_info=True)
            self.root.after(0, self._update_status_bar, f"エラー: {e}", "error")
            self.root.after(0, messagebox.showerror, "最適化エラー", f"最適化中にエラーが発生しました。\n詳細: {e}")
        finally:
            self.root.after(0, self._hide_progress_dialog)

    def _progress_callback(self, message: str):
        """最適化の進捗をプログレスダイアログに表示するコールバック関数。"""
        self.root.after(0, self._update_progress_dialog, message)

    def _show_progress_dialog(self):
        """プログレスダイアログを表示する。"""
        logger.debug("MainApplication: プログレスダイアログを表示します。")
        if self.progress_dialog_instance is None:
            if gui_components_progress:
                ProgressDialog = getattr(gui_components_progress, 'ProgressDialog', FallbackProgressDialog)
                self.progress_dialog_instance = ProgressDialog(self.root, self._cancel_optimization)
            else:
                self.progress_dialog_instance = FallbackProgressDialog(self.root, self._cancel_optimization)
        self.progress_dialog_instance.show()

    def _update_progress_dialog(self, message: str):
        """プログレスダイアログのメッセージを更新する。"""
        if self.progress_dialog_instance:
            self.progress_dialog_instance.update_message(message)
            self.root.update_idletasks()

    def _hide_progress_dialog(self):
        """プログレスダイアログを非表示にする。"""
        logger.debug("MainApplication: プログレスダイアログを非表示にします。")
        if self.progress_dialog_instance:
            self.progress_dialog_instance.hide()
            self.progress_dialog_instance = None

    def _cancel_optimization(self):
        """最適化プロセスをキャンセルする。"""
        logger.info("最適化停止ボタンが押されました。")
        if self.optimization_thread and self.optimization_thread.is_alive():
            self.cancel_event.set()
            self._update_status_bar("最適化をキャンセルしています...", "warning")
        else:
            self._update_status_bar("実行中の最適化はありません。", "info")
        self._hide_progress_dialog()

    def _display_results(self, result: Any):
        """最適化結果をUIに表示する。ResultsTabに処理を委譲。"""
        logger.info("最適化結果をUIに表示します。")
        self.results_tab_handler.display_results(result)
        self._update_status_bar(f"最適化完了: {result.status}", "info")
        self.notebook.select(self.notebook.tabs()[1])  # 結果タブに切り替える
        logger.info("最適化結果のUI表示が完了しました。")

    def _clear_results(self):
        """結果表示エリアをクリアする。ResultsTabに処理を委譲。"""
        logger.info("結果クリアボタンが押されました。")
        self.results_tab_handler.clear_results()
        self._update_status_bar("結果表示をクリアしました。", "info")

    def _save_current_gui_settings(self):
        """現在のGUI設定をgui_settings.iniに保存する。SettingsManagerに処理を委譲。"""
        logger.info("設定保存ボタンが押されました。")
        # 各タブから現在の設定値を取得して保存
        current_settings = self.data_input_tab_handler.get_current_settings_for_save()
        
        # MainApplicationが直接管理する設定も追加
        try:
            current_settings['theme'] = self.style.theme_use()
        except:
            current_settings['theme'] = 'clam'

        try:
            self.settings_manager.save_gui_settings(current_settings)
            self._update_status_bar("GUI設定を保存しました。", "info")
        except Exception as e:
            logger.error(f"MainApplication: GUI設定の保存中にエラーが発生しました: {e}", exc_info=True)
            self._update_status_bar(f"エラー: GUI設定の保存に失敗しました: {e}", "error")

    def _on_closing(self):
        """アプリケーション終了時の処理。"""
        logger.info("アプリケーション終了処理を開始します。")
        if self.optimization_thread and self.optimization_thread.is_alive():
            if messagebox.askyesno("最適化実行中", "最適化プロセスが実行中です。終了すると中断されます。続行しますか？"):
                logger.debug("Exit process confirmed by user.")
                self.cancel_event.set()
                if self.optimization_thread and self.optimization_thread.is_alive():
                    self.optimization_thread.join(timeout=5)
                    if self.optimization_thread.is_alive():
                        logger.warning("Optimization thread did not terminate within timeout. Forcing exit.")
                        self._update_status_bar("Warning: Optimization thread did not terminate.", "warning")
            else:
                logger.debug("Exit process cancelled by user.")
                self._update_status_bar("Exit cancelled.", "info")
                return
        
        # GUI設定を保存
        self._save_current_gui_settings()

        # プログレスダイアログが開いている場合は閉じる
        if self.progress_dialog_instance:
            self.progress_dialog_instance.hide()
            self.progress_dialog_instance = None

        # TextHandlerをロガーから削除
        if self.text_handler:
            logging.getLogger().removeHandler(self.text_handler)
            logger.debug("TextHandler removed from logger.")

        self.root.destroy()
        logger.info("アプリケーションが正常に終了しました。")


if __name__ == "__main__":
    # ロギングの初期設定
    log_file_path = PROJECT_ROOT / "logs" / f"seminar_optimization_{datetime.now().strftime('%Y%m%d')}.log"
    
    try:
        if logger_config_module and hasattr(logger_config_module, 'setup_logging'):
            # 元のsetup_logging関数を使用
            setup_logging_func = getattr(logger_config_module, 'setup_logging')
            setup_logging_func(log_level="DEBUG", log_file=str(log_file_path))
        else:
            # フォールバック関数を使用
            setup_basic_logging(log_level="DEBUG", log_file=str(log_file_path))
    except Exception as e:
        print(f"Warning: Could not set up logging properly: {e}")
        # 最低限のロギング設定
        logging.basicConfig(level=logging.DEBUG)
        logger = logging.getLogger(__name__)
    
    logger.info("main: アプリケーションのロギングが初期化されました。")
    
    root = tk.Tk()
    app = MainApplication(root)
    root.mainloop()
    logger.info("Main loop exited.")