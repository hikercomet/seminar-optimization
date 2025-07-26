import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
from datetime import datetime
import configparser
import json
import os
import sys
import logging
import random
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable, Tuple
import ctypes
from dataclasses import dataclass, field
from enum import Enum

# DPI設定（Windows用）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(True)
except:
    pass


class OptimizationStatus(Enum):
    """最適化ステータス"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class AppConfig:
    """アプリケーション設定を管理するデータクラス"""
    # データ入力関連
    seminars_file_path: str = ""
    students_file_path: str = ""
    data_input_method: str = "auto_generate"
    num_seminars: int = 5
    num_students: int = 50
    min_capacity: int = 5
    max_capacity: int = 15
    preference_distribution: str = "uniform"
    random_seed: int = 42
    q_boost_probability: float = 0.2
    num_preferences_to_consider: int = 5
    min_preferences: int = 1
    max_preferences: int = 5

    # 最適化関連
    optimization_strategy: str = "Greedy_LS"
    ga_population_size: int = 100
    ga_generations: int = 200
    ga_mutation_rate: float = 0.05
    ga_crossover_rate: float = 0.8
    ga_no_improvement_limit: int = 10
    max_workers: int = 4
    ilp_time_limit: int = 300
    cp_time_limit: int = 300
    multilevel_clusters: int = 5
    greedy_ls_iterations: int = 200000
    local_search_iterations: int = 500
    initial_temperature: float = 1.0
    cooling_rate: float = 0.995
    score_weights: Dict[str, float] = field(default_factory=lambda: {
        "1st_choice": 5.0, "2nd_choice": 2.0, "3rd_choice": 1.0, "other": 0.5
    })
    early_stop_threshold: float = 0.001
    early_stop_no_improvement_limit: int = 1000
    adaptive_history_size: int = 10
    adaptive_exploration_epsilon: float = 0.1
    adaptive_score_weight: float = 10.0
    adaptive_unassigned_weight: float = 2.0
    adaptive_time_weight: float = 0.1
    max_time_for_normalization: float = 60.0
    adaptive_learning_rate: float = 0.01
    # 出力関連
    generate_pdf_report: bool = True
    generate_csv_report: bool = True
    output_directory: Path = field(default_factory=lambda: Path.cwd() / "output")
    pdf_font_path: str = "fonts/ipaexg.ttf"

    # システム関連
    debug_mode: bool = False
    log_enabled: bool = True
    save_intermediate: bool = False
    theme: str = "clam"
    config_file_path: str = r"C:\Users\hiker\seminar_optimization\config\config.json"


    def to_dict(self) -> Dict[str, Any]:
        """設定を辞書形式で返す"""
        result = {}
        for key, value in self.__dict__.items():
            if isinstance(value, Path):
                result[key] = str(value)
            else:
                result[key] = value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """辞書から設定を復元する"""
        # Pathオブジェクトの復元
        if 'output_directory' in data and isinstance(data['output_directory'], str):
            data['output_directory'] = Path(data['output_directory'])
        
        # 存在しないキーを除外
        valid_keys = {field.name for field in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        
        return cls(**filtered_data)


def get_project_root() -> Path:
    """プロジェクトルートディレクトリを特定する"""
    current_file_path = Path(__file__).resolve()
    marker_files = ["pyproject.toml", "setup.py", "README.md", ".git", "seminar_optimization.code-workspace"]

    for parent in current_file_path.parents:
        for marker in marker_files:
            if (parent / marker).exists():
                return parent
        if parent.name == "seminar_optimization" and (parent / "seminar_optimization").is_dir():
            return parent

    print("プロジェクトルートマーカーが見つかりませんでした。現在のスクリプトの親ディレクトリをルートとみなします。")
    return current_file_path.parent


class MainApplication(tk.Tk):
    """セミナー割当最適化ツールのメインアプリケーションクラス"""

    def __init__(self, project_root: Optional[Path] = None):
        super().__init__()
        
        # プロジェクトルートの設定
        self.project_root = project_root or get_project_root()
        self._setup_imports()
        
        # 基本設定
        self._setup_basic_config()
        
        # 設定の初期化
        self.config = AppConfig()
        self._load_settings()
        
        # GUI関連の初期値設定（タブで使用される）
        self._setup_gui_attributes()
        
        # ロギング設定
        self._setup_logging()
        
        # UI初期化
        self._setup_ui()
        
        # 最適化関連の初期化
        self._setup_optimization()
        
        # 終了処理の設定
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        
        self.logger.info("MainApplication: 初期化が完了しました。")

    def _setup_gui_attributes(self):
        """GUI関連の属性を初期化"""
        # DataInputTabで参照される属性
        self.initial_data_input_method = self.config.data_input_method
        self.initial_seminars_file_path = self.config.seminars_file_path
        self.initial_students_file_path = self.config.students_file_path
        self.initial_num_seminars = self.config.num_seminars
        self.initial_num_students = self.config.num_students
        self.initial_min_capacity = self.config.min_capacity
        self.initial_max_capacity = self.config.max_capacity
        self.initial_preference_distribution = self.config.preference_distribution
        self.initial_random_seed = self.config.random_seed
        self.initial_q_boost_probability = self.config.q_boost_probability
        self.initial_num_preferences_to_consider = self.config.num_preferences_to_consider
        self.initial_min_preferences = self.config.min_preferences
        self.initial_max_preferences = self.config.max_preferences
        
        # SettingTabで参照される属性
        self.initial_optimization_strategy = self.config.optimization_strategy
        self.initial_ga_population_size = self.config.ga_population_size
        self.initial_ga_generations = self.config.ga_generations
        self.initial_ga_mutation_rate = self.config.ga_mutation_rate
        self.initial_ga_crossover_rate = self.config.ga_crossover_rate
        self.initial_ga_no_improvement_limit = self.config.ga_no_improvement_limit
        self.initial_max_workers = self.config.max_workers
        self.initial_ilp_time_limit = self.config.ilp_time_limit
        self.initial_cp_time_limit = self.config.cp_time_limit
        self.initial_multilevel_clusters = self.config.multilevel_clusters
        self.initial_greedy_ls_iterations = self.config.greedy_ls_iterations
        self.initial_local_search_iterations = self.config.local_search_iterations
        self.initial_temperature = self.config.initial_temperature
        self.initial_cooling_rate = self.config.cooling_rate
        self.initial_score_weights = self.config.score_weights.copy()
        self.initial_early_stop_threshold = self.config.early_stop_threshold
        self.initial_early_stop_no_improvement_limit = self.config.early_stop_no_improvement_limit
        self.initial_adaptive_history_size = self.config.adaptive_history_size
        self.initial_adaptive_exploration_epsilon = self.config.adaptive_exploration_epsilon
        self.initial_adaptive_score_weight = self.config.adaptive_score_weight
        self.initial_adaptive_unassigned_weight = self.config.adaptive_unassigned_weight
        self.initial_adaptive_time_weight = self.config.adaptive_time_weight
        self.initial_max_time_for_normalization = self.config.max_time_for_normalization
        self.initial_adaptive_learning_rate = self.config.adaptive_learning_rate
        # 出力関連の属性
        self.initial_generate_pdf_report = self.config.generate_pdf_report
        self.initial_generate_csv_report = self.config.generate_csv_report
        self.initial_output_directory = str(self.config.output_directory)
        self.initial_pdf_font_path = self.config.pdf_font_path
        
        # システム関連の属性
        self.initial_debug_mode = self.config.debug_mode
        self.initial_log_enabled = self.config.log_enabled
        self.initial_save_intermediate = self.config.save_intermediate
        self.initial_theme = self.config.theme
        self.initial_config_file_path = self.config.config_file_path

    def _setup_imports(self):
        """必要なモジュールのインポート設定"""
        if str(self.project_root) not in sys.path:
            sys.path.insert(0, str(self.project_root))
        
        try:
            # 必要なモジュールをインポート
            from seminar_optimization.logger_config import setup_logging
            from seminar_optimization.data_generator import DataGenerator
            from seminar_optimization.schemas import CONFIG_SCHEMA
            from seminar_optimization.output_generator import save_pdf_report, save_csv_results
            from optimizers.optimizer_service import OptimizerService, OPTIMIZER_MAP
            from setting_manager import SettingsManager
            from gui_tabs.data_input_tab import DataInputTab
            from gui_tabs.results_tab import ResultsTab
            from gui_tabs.log_tab import LogTab
            from gui_tabs.setting_tab import SettingTab
            from gui_components.progress_dialog import ProgressDialog
            
            # クラス属性として保存
            self._setup_logging_func = setup_logging
            self.DataGenerator = DataGenerator
            self.OptimizerService = OptimizerService
            self.SettingsManager = SettingsManager
            self.DataInputTab = DataInputTab
            self.ResultsTab = ResultsTab
            self.LogTab = LogTab
            self.SettingTab = SettingTab
            self.ProgressDialog = ProgressDialog
            
        except ImportError as e:
            print(f"必要なモジュールのインポートに失敗しました: {e}")
            sys.exit(1)

    def _setup_basic_config(self):
        """基本設定のセットアップ"""
        self.title("セミナー割当最適化ツール")
        self.geometry("1200x800")
        self.minsize(800, 600)
        
        # 出力ディレクトリの確保
        output_dir = self.project_root / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # ログディレクトリの確保
        logs_dir = self.project_root / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)

    def _load_settings(self):
        """設定をファイルから読み込む"""
        try:
            self.settings_manager = self.SettingsManager(self.project_root)
            loaded_settings = self.settings_manager.load_gui_settings(self)
            
            # AppConfigに設定を適用
            if loaded_settings:
                self.config = AppConfig.from_dict(loaded_settings)
                
        except Exception as e:
            print(f"設定の読み込みに失敗しました。デフォルト設定を使用します: {e}")
            self.config = AppConfig()

    def _setup_logging(self):
        """ロギング設定のセットアップ"""
        try:
            log_file = str(self.project_root / "logs" / "seminar_optimization.log") if self.config.log_enabled else None
            log_level = "DEBUG" if self.config.debug_mode else "INFO"
            
            self.logger = self._setup_logging_func(log_level=log_level, log_file=log_file)
            if self.logger is None:
                # フォールバック用の簡単なロガー
                logging.basicConfig(level=logging.INFO)
                self.logger = logging.getLogger(__name__)
                
            self.logger.info("MainApplication: ロギングが設定されました。")
            
        except Exception as e:
            print(f"ロギング設定に失敗しました: {e}")
            # フォールバック用の簡単なロガー
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger(__name__)

    def _setup_ui(self):
        """UI要素のセットアップ"""
        try:
            # スタイル設定
            self.style = ttk.Style()
            available_themes = list(self.style.theme_names())
            if self.config.theme in available_themes:
                self.style.theme_use(self.config.theme)
            else:
                self.logger.warning(f"テーマ '{self.config.theme}' が利用できません。デフォルトを使用します。")
            
            self._create_widgets()
            self._create_main_buttons()
            
        except Exception as e:
            self.logger.error(f"UI設定中にエラーが発生しました: {e}")
            raise

    def _setup_optimization(self):
        """最適化関連の初期化"""
        try:
            self.optimization_status = OptimizationStatus.IDLE
            self.optimization_thread: Optional[threading.Thread] = None
            self.cancel_optimization_event = threading.Event()
            
            # プログレスダイアログ
            self.progress_dialog = self.ProgressDialog(self, self._cancel_optimization)
            
            # 最適化サービス
            self.optimizer_service = self.OptimizerService(
                progress_callback=self._update_progress_message,
                logger_instance=self.logger
            )
            
            self.logger.debug("MainApplication: 最適化システムが初期化されました。")
            
        except Exception as e:
            self.logger.error(f"最適化システムの初期化に失敗しました: {e}")
            raise

    def _create_widgets(self):
        """メインウィジェットの作成"""
        self.logger.debug("MainApplication: メインウィジェットの作成を開始します。")
        
        try:
            # メインのPanedWindow
            self.paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
            self.paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

            # 左側（コントロールパネル）
            self.control_frame = ttk.Frame(self.paned_window, width=400)
            self.paned_window.add(self.control_frame, weight=1)

            # タブノートブック
            self.notebook = ttk.Notebook(self.control_frame)
            self.notebook.pack(fill=tk.BOTH, expand=True)

            # 各タブの作成
            self._create_tabs()

            # 右側（表示エリア）
            self.display_frame = ttk.Frame(self.paned_window, width=800) 
            self.paned_window.add(self.display_frame, weight=2)

            # 表示エリアの初期内容
            welcome_label = ttk.Label(
                self.display_frame, 
                text="セミナー割当最適化ツール", 
                font=("Inter", 18, "bold")
            )
            welcome_label.pack(pady=50)
            
            description_label = ttk.Label(
                self.display_frame,
                text="左側のパネルからデータを入力し、設定を行った後、\n最適化を実行してください。",
                font=("Inter", 12),
                justify=tk.CENTER
            )
            description_label.pack(pady=20)
            
            self.logger.debug("MainApplication: メインウィジェットの作成が完了しました。")
            
        except Exception as e:
            self.logger.error(f"メインウィジェット作成中にエラー: {e}")
            raise

    def _create_tabs(self):
        """各タブの作成"""
        try:
            # 各タブのインスタンス作成
            self.data_input_tab = self.DataInputTab(self.notebook, self)
            self.setting_tab = self.SettingTab(self.notebook, self)
            self.results_tab = self.ResultsTab(self.notebook)
            self.log_tab = self.LogTab(self.notebook)

            # ノートブックにタブを追加
            self.notebook.add(self.data_input_tab.frame, text="データ入力")
            self.notebook.add(self.setting_tab.frame, text="設定")
            self.notebook.add(self.results_tab.frame, text="最適化結果")
            self.notebook.add(self.log_tab.frame, text="ログ")
            
            self.logger.debug("MainApplication: タブの作成が完了しました。")
            
        except Exception as e:
            self.logger.error(f"タブ作成中にエラー: {e}")
            raise

    def _create_main_buttons(self):
        """メイン操作ボタンの作成"""
        self.logger.debug("MainApplication: メインボタンの作成を開始します。")
        
        try:
            button_frame = ttk.Frame(self)
            button_frame.pack(pady=10)

            # 最適化実行ボタン
            self.start_button = ttk.Button(
                button_frame, 
                text="最適化実行", 
                command=self._start_optimization,
                style="Accent.TButton"
            )
            self.start_button.pack(side=tk.LEFT, padx=5)

            # 設定保存ボタン
            self.save_settings_button = ttk.Button(
                button_frame, 
                text="設定保存", 
                command=self.save_current_settings
            )
            self.save_settings_button.pack(side=tk.LEFT, padx=5)

            # 設定リセットボタン
            self.reset_settings_button = ttk.Button(
                button_frame,
                text="設定リセット",
                command=self._reset_settings
            )
            self.reset_settings_button.pack(side=tk.LEFT, padx=5)

            # 終了ボタン
            self.exit_button = ttk.Button(
                button_frame, 
                text="終了", 
                command=self._on_closing
            )
            self.exit_button.pack(side=tk.LEFT, padx=5)
            
            self.logger.debug("MainApplication: メインボタンの作成が完了しました。")
            
        except Exception as e:
            self.logger.error(f"メインボタン作成中にエラー: {e}")
            raise

    def save_current_settings(self):
        """現在の設定をファイルに保存"""
        try:
            self.logger.info("MainApplication: 設定の保存を開始します。")
            
            # 各タブから設定を取得
            settings_to_save = {}
            
            if hasattr(self, 'data_input_tab'):
                data_input_settings = self.data_input_tab.get_current_settings_for_main_app()
                settings_to_save.update(data_input_settings)
            
            if hasattr(self, 'setting_tab'):
                general_settings = self.setting_tab.get_current_settings_for_main_app()
                settings_to_save.update(general_settings)

            # 設定を保存
            if settings_to_save:
                # AppConfigを更新
                self.config = AppConfig.from_dict(settings_to_save)
                
                # GUI属性も更新
                self._setup_gui_attributes()
                
                # ファイルに保存
                final_settings = {k: str(v) if isinstance(v, Path) else v for k, v in settings_to_save.items()}
                self.settings_manager.save_gui_settings(final_settings)
                
                messagebox.showinfo("設定保存", "現在の設定が保存されました！")
                self.logger.info("MainApplication: 設定の保存が完了しました。")
            else:
                messagebox.showwarning("設定保存", "保存する設定がありません。")
                
        except Exception as e:
            self.logger.error(f"設定保存中にエラー: {e}")
            messagebox.showerror("エラー", f"設定の保存に失敗しました: {e}")

    def _reset_settings(self):
        """設定をデフォルト値にリセット"""
        try:
            if messagebox.askyesno("設定リセット", "すべての設定をデフォルト値にリセットしますか？"):
                self.config = AppConfig()
                self._setup_gui_attributes()
                
                # 各タブの設定もリセット
                if hasattr(self, 'data_input_tab') and hasattr(self.data_input_tab, 'reset_to_defaults'):
                    self.data_input_tab.reset_to_defaults()
                
                if hasattr(self, 'setting_tab') and hasattr(self.setting_tab, 'reset_to_defaults'):
                    self.setting_tab.reset_to_defaults()
                
                messagebox.showinfo("設定リセット", "設定をデフォルト値にリセットしました。")
                self.logger.info("MainApplication: 設定をリセットしました。")
                
        except Exception as e:
            self.logger.error(f"設定リセット中にエラー: {e}")
            messagebox.showerror("エラー", f"設定のリセットに失敗しました: {e}")

    def _start_optimization(self):
        """最適化処理の開始"""
        try:
            self.logger.info("MainApplication: 最適化処理を開始します。")
            
            # 既に実行中かチェック
            if self.optimization_status == OptimizationStatus.RUNNING:
                messagebox.showwarning("最適化実行中", "既に最適化が実行中です。")
                return

            # データの検証
            if not self._validate_optimization_data():
                return

            # 設定を保存
            self.save_current_settings()

            # データを取得
            seminars_data = self.data_input_tab.get_seminars_data()
            students_data = self.data_input_tab.get_students_data()

            if not seminars_data or not students_data:
                messagebox.showerror("データエラー", "セミナーデータまたは学生データがロードされていません。")
                return

            # 最適化設定を準備
            optimization_config = self._prepare_optimization_config()

            # 最適化開始
            self._execute_optimization(seminars_data, students_data, optimization_config)
            
        except Exception as e:
            self.logger.error(f"最適化開始中にエラー: {e}")
            messagebox.showerror("エラー", f"最適化の開始に失敗しました: {e}")

    def _validate_optimization_data(self) -> bool:
        """最適化データの検証"""
        try:
            # 基本的な検証ロジック
            if not hasattr(self, 'data_input_tab'):
                messagebox.showerror("エラー", "データ入力タブが初期化されていません。")
                return False
            
            # 設定の検証
            if hasattr(self, 'setting_tab') and hasattr(self.setting_tab, 'validate_settings'):
                is_valid, errors = self.setting_tab.validate_settings()
                if not is_valid:
                    messagebox.showerror("設定エラー", "\n".join(errors))
                    return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"データ検証中にエラー: {e}")
            messagebox.showerror("エラー", f"データの検証に失敗しました: {e}")
            return False

    def _prepare_optimization_config(self) -> Dict[str, Any]:
        """最適化用設定の準備"""
        config_dict = self.config.to_dict()
        config_dict["data_directory"] = str(self.project_root / "data")
        return config_dict

    def _execute_optimization(self, seminars_data: List[Dict], students_data: List[Dict], config: Dict[str, Any]):
        """最適化の実行"""
        try:
            self.optimization_status = OptimizationStatus.RUNNING
            self.cancel_optimization_event.clear()
            self.progress_dialog.show()
            
            # UIボタンの状態更新
            self.start_button.config(state='disabled')
            
            # スレッドで実行
            self.optimization_thread = threading.Thread(
                target=self._run_optimization_in_thread,
                args=(seminars_data, students_data, config),
                daemon=True
            )
            self.optimization_thread.start()
            
            self.logger.info("MainApplication: 最適化スレッドを開始しました。")
            
        except Exception as e:
            self.logger.error(f"最適化実行中にエラー: {e}")
            self._reset_optimization_state()
            raise

    def _run_optimization_in_thread(self, seminars_data: List[Dict], students_data: List[Dict], config: Dict[str, Any]):
        """スレッド内での最適化処理"""
        try:
            self.logger.info("MainApplication: 最適化処理スレッドが開始されました。")
            
            result = self.optimizer_service.optimize(
                seminars=seminars_data,
                students=students_data,
                config=config,
                cancel_event=self.cancel_optimization_event
            )
            
            # メインスレッドでUI更新
            self.after(0, lambda: self._handle_optimization_result(result, config))
            
        except Exception as e:
            self.logger.exception("MainApplication: 最適化処理中に予期せぬエラーが発生しました。")
            self.after(0, lambda: self._handle_optimization_error(e))
        finally:
            self.after(0, self._reset_optimization_state)

    def _handle_optimization_result(self, result: Any, config: Dict[str, Any]):
        """最適化結果の処理"""
        try:
            self.logger.info(f"MainApplication: 最適化結果を処理します。ステータス: {result.status}")
            
            # 結果をタブに表示
            self.results_tab.display_results(result)
            self.notebook.select(self.results_tab.frame)

            # ステータス別処理
            if result.status == "CANCELLED":
                self.optimization_status = OptimizationStatus.CANCELLED
                messagebox.showinfo("最適化キャンセル", "最適化がキャンセルされました。")
            elif result.status in ["OPTIMAL", "FEASIBLE"]:
                self.optimization_status = OptimizationStatus.COMPLETED
                messagebox.showinfo("最適化完了", "最適化が成功しました！")
            else:
                self.optimization_status = OptimizationStatus.ERROR
                messagebox.showwarning("最適化警告", f"最適化が完了しましたが、問題が発生しました: {result.message}")

        except Exception as e:
            self.logger.error(f"最適化結果処理中にエラー: {e}")
            messagebox.showerror("エラー", f"結果の処理に失敗しました: {e}")

    def _handle_optimization_error(self, error: Exception):
        """最適化エラーの処理"""
        self.optimization_status = OptimizationStatus.ERROR
        messagebox.showerror("最適化エラー", f"最適化中にエラーが発生しました: {error}")

    def _reset_optimization_state(self):
        """最適化状態のリセット"""
        self.optimization_status = OptimizationStatus.IDLE
        self.progress_dialog.hide()
        self.start_button.config(state='normal')

    def _update_progress_message(self, message: str):
        """プログレスメッセージの更新"""
        self.after(0, self.progress_dialog.update_message, message)

    def _cancel_optimization(self):
        """最適化のキャンセル"""
        try:
            self.logger.info("MainApplication: 最適化キャンセルリクエストを受信しました。")
            
            if self.optimization_status == OptimizationStatus.RUNNING:
                self.cancel_optimization_event.set()
                self.progress_dialog.update_message("最適化をキャンセルしています...")
                self.logger.info("MainApplication: キャンセルイベントを設定しました。")
            else:
                self.progress_dialog.hide()
                
        except Exception as e:
            self.logger.error(f"キャンセル処理中にエラー: {e}")

    def _on_closing(self):
        """アプリケーション終了処理"""
        try:
            self.logger.info("MainApplication: アプリケーションを終了します。")
            
            if self.optimization_status == OptimizationStatus.RUNNING:
                if messagebox.askyesno("終了確認", "最適化が実行中です。本当に終了しますか？"):
                    self.cancel_optimization_event.set()
                    
                    # スレッドの終了を待つ
                    if self.optimization_thread and self.optimization_thread.is_alive():
                        self.optimization_thread.join(timeout=5)
                        if self.optimization_thread.is_alive():
                            self.logger.warning("MainApplication: 最適化スレッドがタイムアウト内に終了しませんでした。")
                    
                    self.destroy()
                else:
                    self.logger.info("MainApplication: 終了がキャンセルされました。")
                    return
            
            # 設定を保存してから終了
            try:
                self.save_current_settings()
            except Exception as e:
                self.logger.warning(f"終了時の設定保存に失敗: {e}")
            
            self.destroy()
            
        except Exception as e:
            self.logger.error(f"終了処理中にエラー: {e}")
            self.destroy()

    def get_config(self) -> AppConfig:
        """現在の設定を取得"""
        return self.config

    def update_config(self, **kwargs):
        """設定を更新"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
            else:
                self.logger.warning(f"不明な設定キー: {key}")


def main():
    """アプリケーションのエントリーポイント"""
    try:
        # プロジェクトルートの取得
        project_root = get_project_root()
        
        # アプリケーションの起動
        app = MainApplication(project_root)
        app.mainloop()
        
    except Exception as e:
        print(f"アプリケーションの起動に失敗しました: {e}")
        logging.exception("アプリケーション起動エラー")
        sys.exit(1)


if __name__ == "__main__":
    main()