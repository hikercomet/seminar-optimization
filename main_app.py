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
    この関数は、marker_file_name (例: 'pyproject.toml', 'setup.py', '.git')
    または特定のディレクトリ名 (例: 'seminar_optimization') を探すことで
    プロジェクトのルートを判断します。
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
    logger.warning("プロジェクトルートマーカーが見つかりませんでした。現在のスクリプトの親ディレクトリをルートとみなします。")
    return current_file_path.parent

# プロジェクトルートを設定
PROJECT_ROOT = get_project_root()

# sys.path にプロジェクトルートを追加して、絶対インポートを可能にする
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# seminar_optimization パッケージ内のモジュールを絶対パスでインポート
try:
    from optimizers.optimizer_service import OptimizerService
    from seminar_optimization.data_generator import DataGenerator
    from seminar_optimization.logger_config import setup_logging, logger
    from seminar_optimization.schemas import CONFIG_SCHEMA # スキーマをインポート
    import jsonschema # jsonschemaをインポート
except ImportError as e:
    # ロガーがまだ設定されていない可能性があるので、printも使用
    print(f"ImportError: {e}. 'seminar_optimization' パッケージのインポートに失敗しました。")
    print("プロジェクトのルートディレクトリが正しく設定されているか、または 'seminar_optimization' パッケージがPythonのパスにあるか確認してください。")
    print(f"現在のPROJECT_ROOT: {PROJECT_ROOT}")
    print(f"sys.path: {sys.path}")
    messagebox.showerror("インポートエラー", f"必要なモジュールをロードできませんでした: {e}\n\nプロジェクトの構造とPythonのパス設定を確認してください。")
    sys.exit(1)

# 分割したGUIコンポーネントのインポート
try:
    from gui_tabs.data_input_tab import DataInputTab
    from gui_tabs.results_tab import ResultsTab
    from gui_tabs.log_tab import LogTab
    from gui_components.progress_dialog import ProgressDialog
    from settings_manager import SettingsManager
except ImportError as e:
    print(f"ImportError: {e}. GUIコンポーネントのインポートに失敗しました。")
    messagebox.showerror("インポートエラー", f"必要なGUIコンポーネントをロードできませんでした: {e}\n\nファイル構造とPythonのパス設定を確認してください。")
    sys.exit(1)


class MainApplication:
    def __init__(self, root: tk.Tk):
        logger.debug("MainApplication: 初期化を開始します。")
        self.root = root
        self._set_dpi_awareness()
        
        # スタイルオブジェクトをここで初期化
        self.style = ttk.Style()

        # SettingsManagerのインスタンスを作成
        self.settings_manager = SettingsManager(PROJECT_ROOT)

        # --- すべての initial_* 属性を絶対的なデフォルト値で初期化 ---
        # これらのデフォルト値は、gui_settings.iniのロードが失敗した場合や、
        # 特定のキーが存在しない/不正な場合にフォールバックとして使用されます。
        # _load_gui_settings() がこれらの属性にアクセスする前に定義されている必要がある。
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
        self.initial_theme = 'clam' # デフォルトテーマを有効なものに設定
        self.initial_config_file_path = ''
        self.initial_student_file_path = ''
        self.initial_ga_population_size = 100
        self.initial_ga_crossover_rate = 0.8
        self.initial_ga_mutation_rate = 0.05
        self.initial_ga_generations = 200 
        self.initial_ga_no_improvement_limit = 10 
        self.initial_optimization_strategy = 'Greedy_LS'
        self.initial_seminars_file_path = ''
        self.initial_students_file_path = ''
        self.initial_data_input_method = 'json'
        self.initial_num_seminars = 10
        self.initial_min_preferences = 3
        self.initial_max_preferences = 5
        self.initial_preference_distribution = 'random'
        self.initial_random_seed = 42
        self.initial_ilp_time_limit = 300
        self.initial_cp_time_limit = 300
        self.initial_multilevel_clusters = 5
        self.initial_generate_pdf_report = True
        self.initial_generate_csv_report = True
        self.initial_max_adaptive_iterations = 5
        self.initial_strategy_time_limit = 60
        self.initial_adaptive_history_size = 5
        self.initial_adaptive_exploration_epsilon = 0.1
        self.initial_adaptive_learning_rate = 0.5
        self.initial_adaptive_score_weight = 0.6
        self.initial_adaptive_unassigned_weight = 0.3
        self.initial_adaptive_time_weight = 0.1
        self.initial_max_time_for_normalization = 300.0
        self.initial_greedy_ls_iterations = 200000 
        self.initial_output_directory = "results" 
        self.initial_debug_mode = False 
        # --- initial_* 属性のデフォルト値設定終了 ---

        # gui_settings.iniからGUI設定をロードし、initial_*属性を更新
        # SettingsManagerを使用
        loaded_settings = self.settings_manager.load_gui_settings(self)
        for key, value in loaded_settings.items():
            if hasattr(self, key):
                setattr(self, key, value)
        
        # ロードされたテーマを適用
        self.style.theme_use(self.initial_theme) 

        self.root.title("セミナー割り当て最適化ツール")
        self.root.geometry("1200x800")
        
        # ウィンドウが生成された直後に表示状態を強制
        self.root.deiconify() 
        self.root.state('normal')
        self.root.lift()
        self.root.focus_force()
        logger.debug("MainApplication: GUIウィンドウの初期表示設定を適用しました。")

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.cancel_event = threading.Event()
        self.optimization_thread: Optional[threading.Thread] = None
        self.progress_dialog_instance: Optional[ProgressDialog] = None
        self.text_handler: Optional[logging.Handler] = None # TextHandlerはLogTab内で管理される

        # GUIウィジェットを作成
        self._create_widgets()

        # configをロード (デフォルトの最適化設定)
        self.optimization_config = self._set_default_optimization_config()
        # DataGeneratorとOptimizerServiceのインスタンスを初期化
        self.data_generator = DataGenerator(self.optimization_config, logger)
        self.optimizer_service = OptimizerService(self.optimization_config, logger)

        # UI要素の状態を初期化 (各タブに委譲)
        self._initialize_ui_elements()

        logger.info("MainApplication: 初期化が完了しました。")


    def _set_dpi_awareness(self):
        """Windowsで高DPIスケーリングを有効にする。"""
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            logger.debug("DPI認識が設定されました。")
        except (AttributeError, ImportError):
            logger.debug("DPI認識設定はWindowsでのみ利用可能です。")

    def _set_default_optimization_config(self) -> Dict[str, Any]:
        """
        最適化設定のデフォルト値を返す。
        このメソッドは、config.jsonのロードが失敗した場合のフォールバックとして使用されます。
        """
        logger.debug("MainApplication: デフォルトの最適化設定を生成します。")
        return {
            "data_directory": "data",
            "seminars_file": "seminars.json",
            "students_file": "students.json",
            "results_file": "optimization_results.json",
            "num_seminars": 10,
            "min_capacity": 5,
            "max_capacity": 10,
            "seminar_specific_capacities": [],
            "num_students": 50,
            "min_preferences": 3,
            "max_preferences": 5,
            "preference_distribution": "random", # デフォルト値
            "ga_population_size": 100,
            "ga_generations": 200,
            "ga_mutation_rate": 0.05,
            "ga_crossover_rate": 0.8,
            "ga_no_improvement_limit": 10, # デフォルト値
            "k_means_clusters": 5,
            "debug_mode": True,
            "ilp_time_limit": 300,
            "cp_time_limit": 300,
            "multilevel_clusters": 5,
            "greedy_ls_iterations": 200000,
            "local_search_iterations": 500,
            "initial_temperature": 1.0,
            "cooling_rate": 0.995,
            "score_weights": { # キー名を修正
                "1st_choice": 5.0,
                "2nd_choice": 2.0,
                "3rd_choice": 1.0,
                "other_preference": 0.5 # 追加
            },
            "early_stop_no_improvement_limit": 50,
            "generate_pdf_report": True,
            "generate_csv_report": True,
            "log_enabled": True,
            "optimization_strategy": "Greedy_LS",
            "q_boost_probability": 0.2,
            "num_preferences_to_consider": 3,
            "max_adaptive_iterations": 5,
            "strategy_time_limit": 60,
            "random_seed": 42,
            "max_workers": 8, # デフォルト値
            "pdf_font_path": "fonts/ipaexg.ttf", # デフォルト値
            "output_directory": "results"
        }

    def _initialize_ui_elements(self):
        """
        GUI要素の初期値を設定する。
        各タブの初期化メソッドを呼び出す。
        """
        logger.debug("MainApplication: UI要素の初期化を開始します。")
        # DataInputTabの初期化
        self.data_input_tab_handler.initialize_fields(
            initial_seminars_str=self.initial_seminars_str,
            initial_num_students=self.initial_num_students,
            initial_magnification=self.initial_magnification,
            initial_min_size=self.initial_min_size,
            initial_max_size=self.initial_max_size,
            initial_q_boost_probability=self.initial_q_boost_probability,
            initial_num_preferences_to_consider=self.initial_num_preferences_to_consider,
            initial_num_patterns=self.initial_num_patterns,
            initial_max_workers=self.initial_max_workers,
            initial_local_search_iterations=self.initial_local_search_iterations,
            initial_initial_temperature=self.initial_initial_temperature,
            initial_cooling_rate=self.initial_cooling_rate,
            initial_preference_weights=self.initial_preference_weights,
            initial_early_stop_threshold=self.initial_early_stop_threshold,
            initial_no_improvement_limit=self.initial_no_improvement_limit,
            initial_data_source=self.initial_data_source,
            initial_log_enabled=self.initial_log_enabled,
            initial_save_intermediate=self.initial_save_intermediate,
            initial_config_file_path=self.initial_config_file_path,
            initial_student_file_path=self.initial_student_file_path,
            initial_ga_population_size=self.initial_ga_population_size,
            initial_ga_crossover_rate=self.initial_ga_crossover_rate,
            initial_ga_mutation_rate=self.initial_ga_mutation_rate,
            initial_ga_generations=self.initial_ga_generations,
            initial_ga_no_improvement_limit=self.initial_ga_no_improvement_limit,
            initial_optimization_strategy=self.initial_optimization_strategy,
            initial_seminars_file_path=self.initial_seminars_file_path,
            initial_students_file_path=self.initial_students_file_path,
            initial_data_input_method=self.initial_data_input_method,
            initial_num_seminars=self.initial_num_seminars,
            initial_min_preferences=self.initial_min_preferences,
            initial_max_preferences=self.initial_max_preferences,
            initial_preference_distribution=self.initial_preference_distribution,
            initial_random_seed=self.initial_random_seed,
            initial_ilp_time_limit=self.initial_ilp_time_limit,
            initial_cp_time_limit=self.initial_cp_time_limit,
            initial_multilevel_clusters=self.initial_multilevel_clusters,
            initial_generate_pdf_report=self.initial_generate_pdf_report,
            initial_generate_csv_report=self.initial_generate_csv_report,
            initial_max_adaptive_iterations=self.initial_max_adaptive_iterations,
            initial_strategy_time_limit=self.initial_strategy_time_limit,
            initial_adaptive_history_size=self.initial_adaptive_history_size,
            initial_adaptive_exploration_epsilon=self.initial_adaptive_exploration_epsilon,
            initial_adaptive_learning_rate=self.initial_adaptive_learning_rate,
            initial_adaptive_score_weight=self.initial_adaptive_score_weight,
            initial_adaptive_unassigned_weight=self.initial_adaptive_unassigned_weight,
            initial_adaptive_time_weight=self.initial_adaptive_time_weight,
            initial_max_time_for_normalization=self.initial_max_time_for_normalization,
            initial_greedy_ls_iterations=self.initial_greedy_ls_iterations,
            initial_output_directory=self.initial_output_directory,
            initial_debug_mode=self.initial_debug_mode
        )
        # 他のタブの初期化メソッドがあればここに呼び出しを追加
        logger.debug("MainApplication: UI要素の初期化が完了しました。")


    def _create_widgets(self):
        """
        GUIのウィジェットを作成し、配置する。
        PanedWindowを使ってレイアウトを改善。
        """
        logger.debug("MainApplication: GUIウィジェットの作成を開始します。")

        # メインフレーム
        main_frame = ttk.Frame(self.root, padding="10") 
        main_frame.pack(fill=tk.BOTH, expand=True)

        # PanedWindowで左側のナビゲーションと中央のコンテンツを分割
        self.main_pane = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.main_pane.pack(fill=tk.BOTH, expand=True)

        # 左側のナビゲーションフレーム
        self.nav_frame = ttk.Frame(self.main_pane, width=150, relief=tk.RAISED, borderwidth=1)
        self.main_pane.add(self.nav_frame, weight=0) # weight=0でサイズ固定

        # 中央のコンテンツフレーム
        self.content_frame = ttk.Frame(self.main_pane)
        self.main_pane.add(self.content_frame, weight=1) # weight=1で残りのスペースを占有

        # ナビゲーションボタンの作成
        self._create_navigation_buttons(self.nav_frame)

        # ノートブック（タブ）をコンテンツフレーム内に配置
        self.notebook = ttk.Notebook(self.content_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5) # パディングを追加

        # 各タブのインスタンスを作成し、ノートブックに追加
        self.data_input_tab_handler = DataInputTab(self.notebook, self)
        self.results_tab_handler = ResultsTab(self.notebook)
        self.log_tab_handler = LogTab(self.notebook)

        self.notebook.add(self.data_input_tab_handler.frame, text="データ入力と設定")
        self.notebook.add(self.results_tab_handler.frame, text="最適化結果")
        self.notebook.add(self.log_tab_handler.frame, text="ログ")

        # TextHandlerをLogTabから取得し、ロギングシステムに追加
        self.text_handler = self.log_tab_handler.get_text_handler()
        if self.text_handler:
            logging.getLogger().addHandler(self.text_handler)
            logging.getLogger().setLevel(logging.DEBUG) # 全てのログレベルをTextHandlerに送る

        # メインボタンをコンテンツフレームの下部に配置
        self._create_main_buttons(self.content_frame)

        # ステータスバーをルートウィンドウの最下部に配置
        self.status_bar_label = ttk.Label(self.root, text="準備完了", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar_label.pack(side=tk.BOTTOM, fill=tk.X)
        logger.debug("MainApplication: GUIウィジェットの作成が完了しました。")


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
        # 他のタブへの切り替えなど
        # 例: if button_text == "登録": self.notebook.select(0)


    def _create_main_buttons(self, parent_frame: ttk.Frame):
        """
        メインの操作ボタンを作成する。
        """
        logger.debug("MainApplication: メインボタンを作成中...")
        button_frame = ttk.Frame(parent_frame, padding="10")
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="最適化開始", command=self._start_optimization).pack(side=tk.LEFT, padx=5, expand=True)
        ttk.Button(button_frame, text="最適化停止", command=self._cancel_optimization).pack(side=tk.LEFT, padx=5, expand=True)
        ttk.Button(button_frame, text="結果クリア", command=self._clear_results).pack(side=tk.LEFT, padx=5, expand=True)
        ttk.Button(button_frame, text="設定保存", command=self._save_current_gui_settings).pack(side=tk.LEFT, padx=5, expand=True)
        logger.debug("MainApplication: メインボタンの作成が完了しました。")


    def _update_status_bar(self, message: str, message_type: str = "info"):
        """
        ステータスバーを更新する。
        :param message: 表示するメッセージ
        :param message_type: 'info', 'warning', 'error' で色を変える
        """
        logger.debug(f"ステータスバー更新: タイプ={message_type}, メッセージ='{message}'")
        if self.status_bar_label: # status_bar_labelがNoneでないことを確認
            self.status_bar_label.config(text=message)
            if message_type == "info":
                self.status_bar_label.config(background="SystemButtonFace", foreground="black")
            elif message_type == "warning":
                self.status_bar_label.config(background="yellow", foreground="black")
            elif message_type == "error":
                self.status_bar_label.config(background="red", foreground="white")
            self.root.update_idletasks() # UIを即座に更新

    def _toggle_logging(self):
        """ログの有効/無効を切り替える。"""
        # DataInputTabのlog_enabled_varの状態を取得
        if self.data_input_tab_handler.log_enabled_var.get():
            setup_logging(log_level="DEBUG", log_file=str(PROJECT_ROOT / "logs" / f"seminar_optimization_{datetime.now().strftime('%Y%m%d')}.log"))
            self._update_status_bar("ログが有効になりました。", "info")
            logger.info("MainApplication: ログが有効になりました。")
        else:
            # ロギングを無効にする（既存のファイルハンドラを削除）
            for handler in logging.root.handlers[:]:
                if isinstance(handler, logging.FileHandler):
                    handler.close()
                    logging.root.removeHandler(handler)
            self._update_status_bar("ログが無効になりました。", "info")
            logger.info("MainApplication: ログが無効になりました。")
        logger.debug(f"MainApplication: ログの状態が {self.data_input_tab_handler.log_enabled_var.get()} に切り替わりました。")


    def _start_optimization(self):
        """最適化プロセスを開始する。"""
        logger.info("最適化開始ボタンが押されました。")
        if self.optimization_thread and self.optimization_thread.is_alive():
            self._update_status_bar("最適化がすでに実行中です。", "warning")
            logger.warning("MainApplication: 最適化がすでに実行中のため、開始要求を無視します。")
            return

        # 結果表示エリアをクリア
        self._clear_results()
        self._update_status_bar("最適化を開始しています...", "info")
        self.cancel_event.clear() # キャンセルイベントをリセット

        # 現在のGUI設定からconfigを構築 (DataInputTabから値を取得)
        current_config = self.data_input_tab_handler.get_current_config()
        
        # config.jsonのスキーマで検証
        try:
            jsonschema.validate(instance=current_config, schema=CONFIG_SCHEMA)
            logger.info("MainApplication: 現在のGUI設定から構築したconfigがスキーマ検証に成功しました。")
        except jsonschema.exceptions.ValidationError as e:
            error_message = f"入力設定のスキーマ検証エラー: {e.message} (パス: {'.'.join(map(str, e.path))})"
            logger.error(f"MainApplication: {error_message}", exc_info=True)
            self._update_status_bar(f"エラー: {error_message}", "error")
            messagebox.showerror("設定エラー", error_message)
            return

        self.optimization_thread = threading.Thread(
            target=self._run_optimization,
            args=(current_config, self.cancel_event)
        )
        self.optimization_thread.start()
        self._show_progress_dialog()
        logger.info("MainApplication: 最適化スレッドが開始されました。")


    def _run_optimization(self, current_config: Dict[str, Any], cancel_event: threading.Event):
        """
        最適化プロセスを実行し、結果をUIに表示する。
        このメソッドは別スレッドで実行される。
        """
        logger.info("最適化プロセスを開始します。")
        self.root.after(0, self._update_status_bar, "最適化を実行中...", "info")
        
        try:
            # データソースに基づいてデータをロードまたは生成
            data_input_method = current_config.get("data_input_method", "auto")
            seminars_data = []
            students_data = []

            if data_input_method == "auto":
                logger.info("自動生成モードでデータを準備します。")
                seminars_ids_list = [s.strip() for s in self.data_input_tab_handler.seminar_ids_var.get().split(',') if s.strip()]
                
                # DataGeneratorのインスタンスを更新
                self.data_generator.config = current_config
                
                seminars_data, students_data = self.data_generator.generate_data(
                    num_seminars=current_config.get("num_seminars"),
                    min_capacity=current_config.get("min_capacity"),
                    max_capacity=current_config.get("max_capacity"),
                    num_students=current_config.get("num_students"),
                    min_preferences=current_config.get("min_preferences"),
                    max_preferences=current_config.get("max_preferences"),
                    preference_distribution=current_config.get("preference_distribution"),
                    random_seed=current_config.get("random_seed"),
                    seminar_ids_list=seminars_ids_list, # 明示的に渡す
                    seminar_specific_capacities=current_config.get("seminar_specific_capacities", []),
                    seminar_specific_magnifications=current_config.get("seminar_specific_magnifications", {})
                )
                logger.info("データが正常に自動生成されました。")
            else: # "json" or "csv"
                logger.info(f"ファイル入力モード '{data_input_method}' でデータを準備します。")
                seminars_file = current_config.get("seminars_file")
                students_file = current_config.get("students_file")

                # DataGeneratorのインスタンスを更新
                self.data_generator.config = current_config

                if data_input_method == "json":
                    seminars_data, students_data = self.data_generator.load_data_from_json(
                        seminars_file=seminars_file,
                        students_file=students_file
                    )
                elif data_input_method == "csv":
                    seminars_data, students_data = self.data_generator.load_data_from_csv(
                        seminars_file=seminars_file,
                        students_file=students_file
                    )
                logger.info("データが正常にファイルからロードされました。")

            # OptimizerServiceに最新のデータを設定
            self.optimizer_service.update_data(seminars_data, students_data, current_config)

            # 最適化を実行
            result = self.optimizer_service.run_optimization(cancel_event, self._progress_callback)
            
            # 結果をUIに表示
            self.root.after(0, self._display_results, result)

        except Exception as e:
            logger.error(f"最適化中にエラーが発生しました: {e}", exc_info=True)
            self.root.after(0, self._update_status_bar, f"エラー: {e}", "error")
            self.root.after(0, messagebox.showerror, "最適化エラー", f"最適化中にエラーが発生しました。\n詳細: {e}")
        finally:
            self.root.after(0, self._hide_progress_dialog)
            logger.info("最適化プロセスが終了しました。")


    def _progress_callback(self, message: str):
        """
        最適化の進捗をプログレスダイアログに表示するコールバック関数。
        """
        # メインスレッドでUIを更新するためにafterを使用
        self.root.after(0, self._update_progress_dialog, message)


    def _show_progress_dialog(self):
        """プログレスダイアログを表示する。"""
        logger.debug("MainApplication: プログレスダイアログを表示します。")
        if self.progress_dialog_instance is None:
            self.progress_dialog_instance = ProgressDialog(self.root, self._cancel_optimization)
        self.progress_dialog_instance.show()
        logger.debug("MainApplication: プログレスダイアログが表示されました。")


    def _update_progress_dialog(self, message: str):
        """プログレスダイアログのメッセージを更新する。"""
        if self.progress_dialog_instance:
            self.progress_dialog_instance.update_message(message)
            self.root.update_idletasks() # UIを即座に更新


    def _hide_progress_dialog(self):
        """プログレスダイアログを非表示にする。"""
        logger.debug("MainApplication: プログレスダイアログを非表示にします。")
        if self.progress_dialog_instance:
            self.progress_dialog_instance.hide()
            self.progress_dialog_instance = None
        logger.debug("MainApplication: プログレスダイアログが非表示になりました。")


    def _cancel_optimization(self):
        """最適化プロセスをキャンセルする。"""
        logger.info("最適化停止ボタンが押されました。")
        if self.optimization_thread and self.optimization_thread.is_alive():
            self.cancel_event.set() # キャンセルイベントを設定
            self._update_status_bar("最適化をキャンセルしています...", "warning")
            logger.warning("MainApplication: 最適化のキャンセル要求が送信されました。")
        else:
            self._update_status_bar("実行中の最適化はありません。", "info")
            logger.info("MainApplication: 実行中の最適化がないため、キャンセル要求を無視します。")
        # プログレスダイアログはスレッド終了時に自動的に閉じられるはずだが、念のためここでも非表示を試みる
        self._hide_progress_dialog()


    def _display_results(self, result: Any):
        """
        最適化結果をUIに表示する。ResultsTabに処理を委譲。
        """
        logger.info("最適化結果をUIに表示します。")
        self.results_tab_handler.display_results(result)
        self._update_status_bar(f"最適化完了: {result.status}", "info")
        self.notebook.select(self.notebook.tabs()[1]) # 結果タブに切り替える
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
        current_settings['theme'] = self.style.theme_use()
        # log_enabled, save_intermediate, output_directoryはDataInputTabで管理されているので、そちらから取得
        # current_settings['log_enabled'] = self.data_input_tab_handler.log_enabled_var.get()
        # current_settings['save_intermediate'] = self.data_input_tab_handler.save_intermediate_var.get()
        # current_settings['output_directory'] = self.data_input_tab_handler.output_directory_var.get()
        
        # preference_weights は DataInputTab で管理されているため、そこから取得
        # current_settings['preference_weights_1st'] = self.data_input_tab_handler.pref_weight_1st_var.get()
        # current_settings['preference_weights_2nd'] = self.data_input_tab_handler.pref_weight_2nd_var.get()
        # current_settings['preference_weights_3rd'] = self.data_input_tab_handler.pref_weight_3rd_var.get()
        # current_settings['preference_weights_other'] = self.data_input_tab_handler.pref_weight_other_var.get()

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
                self.cancel_event.set() # 実行中のスレッドにキャンセルを通知
                if self.optimization_thread and self.optimization_thread.is_alive():
                    self.optimization_thread.join(timeout=5) # スレッドが終了するまで待機
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
            # self.text_handler.close() # TextHandlerのcloseはLogTabで管理されるべき

        self.root.destroy()
        logger.info("アプリケーションが正常に終了しました。")


if __name__ == "__main__":
    # ロギングの初期設定 (ファイル出力はGUI設定で制御)
    setup_logging(log_level="DEBUG", log_file=str(PROJECT_ROOT / "logs" / f"seminar_optimization_{datetime.now().strftime('%Y%m%d')}.log"))
    logger.info("main: アプリケーションのロギングが初期化されました。")
    
    root = tk.Tk()
    app = MainApplication(root)
    root.mainloop()
    logger.info("Main loop exited.")
