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
from pathlib import Path # Pathlibを使用してパス操作を堅牢にする

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


class TextHandler(logging.Handler):
    """
    TkinterのScrolledTextウィジェットにログメッセージをリダイレクトするためのハンドラ。
    """
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.text_widget.config(state='disabled') # 読み取り専用にする
        self.queue = []
        self.lock = threading.Lock()
        self.text_widget.after(100, self.check_queue) # 100msごとにキューをチェック

    def emit(self, record):
        msg = self.format(record)
        with self.lock:
            self.queue.append(msg)

    def check_queue(self):
        with self.lock:
            if self.queue:
                self.text_widget.config(state='normal')
                for msg in self.queue:
                    self.text_widget.insert(tk.END, msg + '\n')
                self.text_widget.see(tk.END) # スクロールを一番下にする
                self.text_widget.config(state='disabled')
                self.queue.clear()
        self.text_widget.after(100, self.check_queue) # 再度スケジュール

class SeminarGUI:
    def __init__(self, root: tk.Tk):
        logger.debug("SeminarGUI: 初期化を開始します。")
        self.root = root
        self._set_dpi_awareness()
        self.root.title("セミナー割り当て最適化ツール")
        self.root.geometry("1200x800")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.cancel_event = threading.Event()
        self.optimization_thread: Optional[threading.Thread] = None
        self.progress_dialog: Optional[tk.Toplevel] = None
        self.text_handler: Optional[TextHandler] = None
        self.magnification_entries: Dict[str, tk.DoubleVar] = {}

        # スタイルオブジェクトをここで初期化
        self.style = ttk.Style()

        # --- すべての initial_* 属性を絶対的なデフォルト値で初期化 ---
        # これらのデフォルト値は、gui_settings.iniのロードが失敗した場合や、
        # 特定のキーが存在しない/不正な場合にフォールバックとして使用されます。
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
        # Greedy_LS固有のイテレーション数を初期化
        self.initial_greedy_ls_iterations = 200000 # ここで初期値を設定
        # --- initial_* 属性のデフォルト値設定終了 ---

        self._load_gui_settings() # ここでgui_settings.iniから値を読み込み、上記のデフォルトを上書きします。

        # GUIウィジェットを先に作成することで、status_bar_labelが初期化されるようにする
        self._create_widgets()

        # configをロード
        self.optimization_config = self._load_default_optimization_config()

        # DataGeneratorとOptimizerServiceのインスタンスを初期化
        # configがロードされた後に初期化する必要がある
        self.data_generator = DataGenerator(self.optimization_config, logger)
        self.optimizer_service = OptimizerService(self.optimization_config, logger)

        # UI要素の状態を初期化
        self._initialize_ui_elements()

        logger.info("SeminarGUI: 初期化が完了しました。")

    def _set_dpi_awareness(self):
        """Windowsで高DPIスケーリングを有効にする。"""
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
            logger.debug("DPI認識が設定されました。")
        except AttributeError:
            logger.debug("DPI認識設定はWindowsでのみ利用可能です。")

    def _get_setting(self, section: str, option: str, default: Any, type_func: Callable[[str], Any]) -> Any:
        """
        gui_settingsから設定値を取得するヘルパーメソッド。
        値がない場合や変換エラーが発生した場合はデフォルト値を返し、警告をログに記録する。
        """
        try:
            value = self.gui_settings.get(section, option)
            if value == '': # 空文字列の場合はデフォルト値を適用
                logger.warning(f"SeminarGUI: '{option}' の値が空です。デフォルト値 '{default}' を使用します。")
                return default
            return type_func(value)
        except (configparser.NoOptionError, ValueError) as e:
            logger.warning(f"SeminarGUI: Failed to load '{option}': {e}. Using current default.")
            return default

    def _load_gui_settings(self):
        """
        gui_settings.iniからGUI設定をロードする。
        各設定は個別にロードし、エラーが発生しても他の設定のロードを続行する。
        """
        self.gui_settings = configparser.ConfigParser()
        gui_settings_path = PROJECT_ROOT / "gui_settings.ini"
        logger.debug(f"SeminarGUI: gui_settings.iniのロードを開始します: {gui_settings_path}")

        if gui_settings_path.exists():
            try:
                self.gui_settings.read(gui_settings_path, encoding='utf-8')
                logger.info(f"SeminarGUI: gui_settings.iniをロードしました: {gui_settings_path}")
                
                # 各設定を個別にロードし、エラーハンドリング
                # fallbackには__init__で設定された現在の値を使用します。
                self.initial_seminars_str = self._get_setting('GUI', 'seminars', self.initial_seminars_str, str)
                self.initial_num_students = self._get_setting('GUI', 'num_students', self.initial_num_students, int)
                
                # magnification のロードは複雑なので、既存のtry-exceptを維持
                magnification_str = self.gui_settings.get('GUI', 'magnification', fallback=json.dumps(self.initial_magnification))
                try:
                    self.initial_magnification = json.loads(magnification_str.replace("'", "\""))
                except (json.JSONDecodeError, AttributeError) as e:
                    logger.warning(f"SeminarGUI: magnification設定の解析に失敗しました: {magnification_str}, エラー: {e}。現在のデフォルト値を使用します。")
                    # initial_magnification は __init__ で既に設定されているので、何もしない

                self.initial_min_size = self._get_setting('GUI', 'min_size', self.initial_min_size, int)
                self.initial_max_size = self._get_setting('GUI', 'max_size', self.initial_max_size, int)
                self.initial_q_boost_probability = self._get_setting('GUI', 'q_boost_probability', self.initial_q_boost_probability, float)
                self.initial_num_preferences_to_consider = self._get_setting('GUI', 'num_preferences_to_consider', self.initial_num_preferences_to_consider, int)
                self.initial_num_patterns = self._get_setting('GUI', 'num_patterns', self.initial_num_patterns, int)
                self.initial_max_workers = self._get_setting('GUI', 'max_workers', self.initial_max_workers, int)
                self.initial_local_search_iterations = self._get_setting('GUI', 'local_search_iterations', self.initial_local_search_iterations, int)
                self.initial_initial_temperature = self._get_setting('GUI', 'initial_temperature', self.initial_initial_temperature, float)
                self.initial_cooling_rate = self._get_setting('GUI', 'cooling_rate', self.initial_cooling_rate, float)
                
                # preference_weights のロード
                try:
                    pref_weights_1st = self._get_setting('GUI', 'preference_weights_1st', self.initial_preference_weights["1st_choice"], float)
                    pref_weights_2nd = self._get_setting('GUI', 'preference_weights_2nd', self.initial_preference_weights["2nd_choice"], float)
                    pref_weights_3rd = self._get_setting('GUI', 'preference_weights_3rd', self.initial_preference_weights["3rd_choice"], float)
                    pref_weights_other = self._get_setting('GUI', 'preference_weights_other', self.initial_preference_weights["other_preference"], float)
                    self.initial_preference_weights = {
                        "1st_choice": pref_weights_1st,
                        "2nd_choice": pref_weights_2nd,
                        "3rd_choice": pref_weights_3rd,
                        "other_preference": pref_weights_other
                    }
                except Exception as e:
                    logger.warning(f"Failed to load 'preference_weights': {e}. Using current default.")

                self.initial_early_stop_threshold = self._get_setting('GUI', 'early_stop_threshold', self.initial_early_stop_threshold, float)
                self.initial_no_improvement_limit = self._get_setting('GUI', 'no_improvement_limit', self.initial_no_improvement_limit, int)
                self.initial_data_source = self._get_setting('GUI', 'data_source', self.initial_data_source, str)
                self.initial_log_enabled = self._get_setting('GUI', 'log_enabled', self.initial_log_enabled, bool)
                self.initial_save_intermediate = self._get_setting('GUI', 'save_intermediate', self.initial_save_intermediate, bool)

                # テーマのロードと検証
                loaded_theme = self._get_setting('GUI', 'theme', self.initial_theme, str)
                if loaded_theme in self.style.theme_names():
                    self.initial_theme = loaded_theme
                else:
                    logger.warning(f"SeminarGUI: 無効なテーマ '{loaded_theme}' がgui_settings.iniに設定されています。デフォルトテーマ '{self.initial_theme}' を使用します。")
                    # self.initial_theme は既に有効なデフォルト値('clam')に設定されているため、変更不要

                self.initial_config_file_path = self._get_setting('GUI', 'config_file_path', self.initial_config_file_path, str)
                self.initial_student_file_path = self._get_setting('GUI', 'student_file_path', self.initial_student_file_path, str)
                self.initial_ga_population_size = self._get_setting('GUI', 'ga_population_size', self.initial_ga_population_size, int)
                self.initial_ga_crossover_rate = self._get_setting('GUI', 'ga_crossover_rate', self.initial_ga_crossover_rate, float)
                self.initial_ga_mutation_rate = self._get_setting('GUI', 'ga_mutation_rate', self.initial_ga_mutation_rate, float)
                self.initial_optimization_strategy = self._get_setting('GUI', 'optimization_strategy', self.initial_optimization_strategy, str)
                self.initial_seminars_file_path = self._get_setting('GUI', 'seminars_file_path', self.initial_seminars_file_path, str)
                self.initial_students_file_path = self._get_setting('GUI', 'students_file_path', self.initial_students_file_path, str)
                self.initial_data_input_method = self._get_setting('GUI', 'data_input_method', self.initial_data_input_method, str)
                self.initial_num_seminars = self._get_setting('GUI', 'num_seminars', self.initial_num_seminars, int)
                self.initial_min_preferences = self._get_setting('GUI', 'min_preferences', self.initial_min_preferences, int)
                self.initial_max_preferences = self._get_setting('GUI', 'max_preferences', self.initial_max_preferences, int)
                self.initial_preference_distribution = self._get_setting('GUI', 'preference_distribution', self.initial_preference_distribution, str)
                self.initial_random_seed = self._get_setting('GUI', 'random_seed', self.initial_random_seed, int)
                self.initial_ilp_time_limit = self._get_setting('GUI', 'ilp_time_limit', self.initial_ilp_time_limit, int)
                self.initial_cp_time_limit = self._get_setting('GUI', 'cp_time_limit', self.initial_cp_time_limit, int)
                self.initial_multilevel_clusters = self._get_setting('GUI', 'multilevel_clusters', self.initial_multilevel_clusters, int)
                self.initial_generate_pdf_report = self._get_setting('GUI', 'generate_pdf_report', self.initial_generate_pdf_report, bool)
                self.initial_generate_csv_report = self._get_setting('GUI', 'generate_csv_report', self.initial_generate_csv_report, bool)
                self.initial_max_adaptive_iterations = self._get_setting('GUI', 'max_adaptive_iterations', self.initial_max_adaptive_iterations, int)
                self.initial_strategy_time_limit = self._get_setting('GUI', 'strategy_time_limit', self.initial_strategy_time_limit, int)
                self.initial_adaptive_history_size = self._get_setting('GUI', 'adaptive_history_size', self.initial_adaptive_history_size, int)
                self.initial_adaptive_exploration_epsilon = self._get_setting('GUI', 'adaptive_exploration_epsilon', self.initial_adaptive_exploration_epsilon, float)
                self.initial_adaptive_learning_rate = self._get_setting('GUI', 'adaptive_learning_rate', self.initial_adaptive_learning_rate, float)
                self.initial_adaptive_score_weight = self._get_setting('GUI', 'adaptive_score_weight', self.initial_adaptive_score_weight, float)
                self.initial_adaptive_unassigned_weight = self._get_setting('GUI', 'adaptive_unassigned_weight', self.initial_adaptive_unassigned_weight, float)
                self.initial_adaptive_time_weight = self._get_setting('GUI', 'adaptive_time_weight', self.initial_adaptive_time_weight, float)
                self.initial_max_time_for_normalization = self._get_setting('GUI', 'max_time_for_normalization', self.initial_max_time_for_normalization, float)
                self.initial_greedy_ls_iterations = self._get_setting('GUI', 'greedy_ls_iterations', self.initial_greedy_ls_iterations, int) # 追加: Greedy_LSイテレーション

            except Exception as e: # この外側のexceptは、gui_settings.read()自体のエラーを捕捉します。
                logger.error(f"SeminarGUI: gui_settings.iniの読み込み中に予期せぬエラーが発生しました: {e}", exc_info=True)
                self._update_status_bar(f"エラー: GUI設定ファイルの読み込み中にエラーが発生しました。\n{e}", "error")
                # __init__で既にデフォルト値が設定されているため、ここでは特別な処理は不要です。
        else:
            logger.info("SeminarGUI: gui_settings.iniが見つかりませんでした。__init__で設定されたデフォルト値を使用します。")
            self._update_status_bar(f"警告: 設定ファイル '{gui_settings_path}' が見つかりません。デフォルト設定を使用します。", "warning")

    def _set_default_optimization_config(self) -> Dict[str, Any]:
        """
        最適化設定のデフォルト値を返す。
        このメソッドは、config.jsonのロードが失敗した場合のフォールバックとして使用されます。
        """
        logger.debug("SeminarGUI: デフォルトの最適化設定を生成します。")
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

    def _sync_gui_settings_with_config(self, config_data: Dict[str, Any]):
        """
        config.jsonからロードした値でGUI設定を上書きする。
        """
        logger.debug("SeminarGUI: GUI設定をconfig.jsonの値と同期します。")
        # config.jsonから読み込んだ値で、__init__で設定された初期値を上書きします。
        # ここでも個別のgetとtry-exceptを使用して堅牢性を高めます。
        self.initial_num_seminars = config_data.get("num_seminars", self.initial_num_seminars)
        self.initial_min_size = config_data.get("min_capacity", self.initial_min_size)
        self.initial_max_size = config_data.get("max_capacity", self.initial_max_size)
        self.initial_num_students = config_data.get("num_students", self.initial_num_students)
        self.initial_min_preferences = config_data.get("min_preferences", self.initial_min_preferences)
        self.initial_max_preferences = config_data.get("max_preferences", self.initial_max_preferences)
        self.initial_preference_distribution = config_data.get("preference_distribution", self.initial_preference_distribution)
        self.initial_random_seed = config_data.get("random_seed", self.initial_random_seed)
        self.initial_optimization_strategy = config_data.get("optimization_strategy", self.initial_optimization_strategy)
        self.initial_ga_population_size = config_data.get("ga_population_size", self.initial_ga_population_size)
        self.initial_ga_generations = config_data.get("ga_generations", self.initial_ga_generations)
        self.initial_ga_mutation_rate = config_data.get("ga_mutation_rate", self.initial_ga_mutation_rate)
        self.initial_ga_crossover_rate = config_data.get("ga_crossover_rate", self.initial_ga_crossover_rate)
        self.initial_ga_no_improvement_limit = config_data.get("ga_no_improvement_limit", self.initial_ga_no_improvement_limit)
        self.initial_ilp_time_limit = config_data.get("ilp_time_limit", self.initial_ilp_time_limit)
        self.initial_cp_time_limit = config_data.get("cp_time_limit", self.initial_cp_time_limit)
        self.initial_max_workers = config_data.get("max_workers", self.initial_max_workers)
        self.initial_multilevel_clusters = config_data.get("multilevel_clusters", self.initial_multilevel_clusters)
        self.initial_greedy_ls_iterations = config_data.get("greedy_ls_iterations", self.initial_greedy_ls_iterations)
        self.initial_local_search_iterations = config_data.get("local_search_iterations", self.initial_local_search_iterations)
        self.initial_early_stop_no_improvement_limit = config_data.get("early_stop_no_improvement_limit", self.initial_early_stop_no_improvement_limit)
        self.initial_initial_temperature = config_data.get("initial_temperature", self.initial_initial_temperature)
        self.initial_cooling_rate = config_data.get("cooling_rate", self.initial_cooling_rate)
        
        # score_weightsの同期
        if "score_weights" in config_data and isinstance(config_data["score_weights"], dict):
            self.initial_preference_weights = config_data["score_weights"]

        self.initial_generate_pdf_report = config_data.get("generate_pdf_report", self.initial_generate_pdf_report)
        self.initial_generate_csv_report = config_data.get("generate_csv_report", self.initial_generate_csv_report)
        self.initial_debug_mode = config_data.get("debug_mode", False)
        self.initial_log_enabled = config_data.get("log_enabled", True)
        self.initial_output_directory = config_data.get("output_directory", "results")
        self.initial_seminars_file_path = config_data.get("seminars_file", self.initial_seminars_file_path)
        self.initial_students_file_path = config_data.get("students_file", self.initial_students_file_path)
        self.initial_q_boost_probability = config_data.get("q_boost_probability", self.initial_q_boost_probability)
        self.initial_num_preferences_to_consider = config_data.get("num_preferences_to_consider", self.initial_num_preferences_to_consider)
        self.initial_max_adaptive_iterations = config_data.get("max_adaptive_iterations", self.initial_max_adaptive_iterations)
        self.initial_strategy_time_limit = config_data.get("strategy_time_limit", self.initial_strategy_time_limit)
        self.initial_adaptive_history_size = config_data.get("adaptive_history_size", self.initial_adaptive_history_size)
        self.initial_adaptive_exploration_epsilon = config_data.get("adaptive_exploration_epsilon", self.initial_adaptive_exploration_epsilon)
        self.initial_adaptive_learning_rate = config_data.get("adaptive_learning_rate", self.initial_adaptive_learning_rate)
        self.initial_adaptive_score_weight = config_data.get("adaptive_score_weight", self.initial_adaptive_score_weight)
        self.initial_adaptive_unassigned_weight = config_data.get("adaptive_unassigned_weight", self.initial_adaptive_unassigned_weight)
        self.initial_adaptive_time_weight = config_data.get("adaptive_time_weight", self.initial_adaptive_time_weight)
        self.initial_max_time_for_normalization = config_data.get("max_time_for_normalization", self.initial_max_time_for_normalization)
        logger.debug("SeminarGUI: GUI設定とconfig.jsonの同期が完了しました。")


    def _initialize_ui_elements(self):
        """
        GUI要素の初期値を設定する。
        _create_widgets() の後に呼び出されることを想定。
        """
        logger.debug("SeminarGUI: UI要素の初期化を開始します。")
        # データ入力と設定タブ
        self.num_seminars_var.set(self.initial_num_seminars)
        self.min_capacity_var.set(self.initial_min_size)
        self.max_capacity_var.set(self.initial_max_size)
        self.num_students_var.set(self.initial_num_students)
        self.min_preferences_var.set(self.initial_min_preferences)
        self.max_preferences_var.set(self.initial_max_preferences)
        self.preference_distribution_var.set(self.initial_preference_distribution)
        self.random_seed_var.set(self.initial_random_seed)
        
        # 最適化アルゴリズム設定
        self.optimization_strategy_var.set(self.initial_optimization_strategy)
        self.ga_population_size_var.set(self.initial_ga_population_size)
        self.ga_generations_var.set(self.initial_ga_generations)
        self.ga_mutation_rate_var.set(self.initial_ga_mutation_rate)
        self.ga_crossover_rate_var.set(self.initial_ga_crossover_rate)
        self.ga_no_improvement_limit_var.set(self.initial_ga_no_improvement_limit)
        self.ilp_time_limit_var.set(self.initial_ilp_time_limit)
        self.cp_time_limit_var.set(self.initial_cp_time_limit)
        self.multilevel_clusters_var.set(self.initial_multilevel_clusters)
        self.greedy_ls_iterations_var.set(self.initial_greedy_ls_iterations)
        self.local_search_iterations_var.set(self.initial_local_search_iterations)
        self.initial_temperature_var.set(self.initial_initial_temperature)
        self.cooling_rate_var.set(self.initial_cooling_rate)

        # スコア重み
        self.pref_weight_1st_var.set(self.initial_preference_weights.get("1st_choice", 5.0))
        self.pref_weight_2nd_var.set(self.initial_preference_weights.get("2nd_choice", 2.0))
        self.pref_weight_3rd_var.set(self.initial_preference_weights.get("3rd_choice", 1.0))
        self.pref_weight_other_var.set(self.initial_preference_weights.get("other_preference", 0.5))

        # レポート設定
        self.generate_pdf_report_var.set(self.initial_generate_pdf_report)
        self.generate_csv_report_var.set(self.initial_generate_csv_report)
        self.log_enabled_var.set(self.initial_log_enabled)
        self.output_directory_var.set(self.initial_output_directory)
        self.seminars_file_path_var.set(self.initial_seminars_file_path)
        self.students_file_path_var.set(self.initial_students_file_path)
        self.data_input_method_var.set(self.initial_data_input_method)

        # 適応型最適化設定
        self.max_adaptive_iterations_var.set(self.initial_max_adaptive_iterations)
        self.strategy_time_limit_var.set(self.initial_strategy_time_limit)
        self.adaptive_history_size_var.set(self.initial_adaptive_history_size)
        self.adaptive_exploration_epsilon_var.set(self.initial_adaptive_exploration_epsilon)
        self.adaptive_learning_rate_var.set(self.initial_adaptive_learning_rate)
        self.adaptive_score_weight_var.set(self.initial_adaptive_score_weight)
        self.adaptive_unassigned_weight_var.set(self.initial_adaptive_unassigned_weight)
        self.adaptive_time_weight_var.set(self.initial_adaptive_time_weight)
        self.max_time_for_normalization_var.set(self.initial_max_time_for_normalization)

        # その他のUI要素
        self.seminar_ids_entry.delete(0, tk.END)
        self.seminar_ids_entry.insert(0, self.initial_seminars_str)
        self.num_students_entry.delete(0, tk.END)
        self.num_students_entry.insert(0, str(self.initial_num_students))
        
        # magnification の初期値を設定
        self._update_magnification_entries()

        self.min_size_entry.delete(0, tk.END)
        self.min_size_entry.insert(0, str(self.initial_min_size))
        self.max_size_entry.delete(0, tk.END)
        self.max_size_entry.insert(0, str(self.initial_max_size))
        self.q_boost_probability_entry.delete(0, tk.END)
        self.q_boost_probability_entry.insert(0, str(self.initial_q_boost_probability))
        self.num_preferences_to_consider_entry.delete(0, tk.END)
        self.num_preferences_to_consider_entry.insert(0, str(self.initial_num_preferences_to_consider))
        self.num_patterns_entry.delete(0, tk.END)
        self.num_patterns_entry.insert(0, str(self.initial_num_patterns))
        self.max_workers_entry.delete(0, tk.END)
        self.max_workers_entry.insert(0, str(self.initial_max_workers))
        self.local_search_iterations_entry.delete(0, tk.END)
        self.local_search_iterations_entry.insert(0, str(self.initial_local_search_iterations))
        self.initial_temperature_entry.delete(0, tk.END)
        self.initial_temperature_entry.insert(0, str(self.initial_initial_temperature))
        self.cooling_rate_entry.delete(0, tk.END)
        self.cooling_rate_entry.insert(0, str(self.initial_cooling_rate))
        self.early_stop_threshold_entry.delete(0, tk.END)
        self.early_stop_threshold_entry.insert(0, str(self.initial_early_stop_threshold))
        self.no_improvement_limit_entry.delete(0, tk.END)
        self.no_improvement_limit_entry.insert(0, str(self.initial_no_improvement_limit))
        self.data_source_var.set(self.initial_data_source)
        self.log_enabled_checkbox.select() if self.initial_log_enabled else self.log_enabled_checkbox.deselect()
        self.save_intermediate_checkbox.select() if self.initial_save_intermediate else self.save_intermediate_checkbox.deselect()
        self.theme_var.set(self.initial_theme)
        self.config_file_path_entry.delete(0, tk.END)
        self.config_file_path_entry.insert(0, self.initial_config_file_path)
        self.student_file_path_entry.delete(0, tk.END)
        self.student_file_path_entry.insert(0, self.initial_student_file_path)
        
        # GA設定のUI要素を更新
        self.ga_population_size_entry.delete(0, tk.END)
        self.ga_population_size_entry.insert(0, str(self.initial_ga_population_size))
        self.ga_generations_entry.delete(0, tk.END)
        self.ga_generations_entry.insert(0, str(self.initial_ga_generations))
        self.ga_mutation_rate_entry.delete(0, tk.END)
        self.ga_mutation_rate_entry.insert(0, str(self.initial_ga_mutation_rate))
        self.ga_crossover_rate_entry.delete(0, tk.END)
        self.ga_crossover_rate_entry.insert(0, str(self.initial_ga_crossover_rate))

        # ILP/CP設定のUI要素を更新
        self.ilp_time_limit_entry.delete(0, tk.END)
        self.ilp_time_limit_entry.insert(0, str(self.initial_ilp_time_limit))
        self.cp_time_limit_entry.delete(0, tk.END)
        self.cp_time_limit_entry.insert(0, str(self.initial_cp_time_limit))

        # Multilevel設定のUI要素を更新
        self.multilevel_clusters_entry.delete(0, tk.END)
        self.multilevel_clusters_entry.insert(0, str(self.initial_multilevel_clusters))

        # 適応型最適化設定のUI要素を更新
        self.max_adaptive_iterations_entry.delete(0, tk.END)
        self.max_adaptive_iterations_entry.insert(0, str(self.initial_max_adaptive_iterations))
        self.strategy_time_limit_entry.delete(0, tk.END)
        self.strategy_time_limit_entry.insert(0, str(self.initial_strategy_time_limit))
        self.adaptive_history_size_entry.delete(0, tk.END)
        self.adaptive_history_size_entry.insert(0, str(self.initial_adaptive_history_size))
        self.adaptive_exploration_epsilon_entry.delete(0, tk.END)
        self.adaptive_exploration_epsilon_entry.insert(0, str(self.initial_adaptive_exploration_epsilon))
        self.adaptive_learning_rate_entry.delete(0, tk.END)
        self.adaptive_learning_rate_entry.insert(0, str(self.initial_adaptive_learning_rate))
        self.adaptive_score_weight_entry.delete(0, tk.END)
        self.adaptive_score_weight_entry.insert(0, str(self.initial_adaptive_score_weight))
        self.adaptive_unassigned_weight_entry.delete(0, tk.END)
        self.adaptive_unassigned_weight_entry.insert(0, str(self.initial_adaptive_unassigned_weight))
        self.adaptive_time_weight_entry.delete(0, tk.END)
        self.adaptive_time_weight_entry.insert(0, str(self.initial_adaptive_time_weight))
        self.max_time_for_normalization_entry.delete(0, tk.END)
        self.max_time_for_normalization_entry.insert(0, str(self.initial_max_time_for_normalization))

        # レポート生成チェックボックスの更新
        self.generate_pdf_report_checkbox.select() if self.initial_generate_pdf_report else self.generate_pdf_report_checkbox.deselect()
        self.generate_csv_report_checkbox.select() if self.initial_generate_csv_report else self.generate_csv_report_checkbox.deselect()

        # データ入力方法のラジオボタンを更新
        self._update_data_input_method_fields()
        logger.debug("SeminarGUI: UI要素の初期化が完了しました。")


    def _create_widgets(self):
        """
        GUIのウィジェットを作成し、配置する。
        画像のUI配置を参考に、PanedWindowを使ってレイアウトを改善。
        """
        logger.debug("SeminarGUI: GUIウィジェットの作成を開始します。")
        # スタイル設定
        # self.style は __init__ で既に初期化済み
        self.style.theme_use(self.initial_theme) # gui_settings.iniからロードした有効なテーマを適用

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

        # --- 「データ入力と設定」タブ ---
        self._create_data_input_tab()
        # --- 「最適化結果」タブ ---
        self._create_results_tab()
        # --- 「ログ」タブ ---
        self._create_log_tab()

        # メインボタンをコンテンツフレームの下部に配置
        self._create_main_buttons(self.content_frame)

        # ステータスバーをルートウィンドウの最下部に配置
        self.status_bar_label = ttk.Label(self.root, text="準備完了", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar_label.pack(side=tk.BOTTOM, fill=tk.X)
        logger.debug("SeminarGUI: GUIウィジェットの作成が完了しました。")


    def _create_navigation_buttons(self, parent_frame: ttk.Frame):
        """左側のナビゲーションボタンを作成する。"""
        logger.debug("SeminarGUI: ナビゲーションボタンを作成中...")
        # 仮のボタン。実際の機能に応じてコマンドを追加
        button_texts = ["インフォメーション", "登録", "照会", "リクエスト", "終了"]
        for text in button_texts:
            btn = ttk.Button(parent_frame, text=text, command=lambda t=text: self._on_nav_button_click(t))
            btn.pack(fill=tk.X, pady=5, padx=5)
        logger.debug("SeminarGUI: ナビゲーションボタンの作成が完了しました。")

    def _on_nav_button_click(self, button_text: str):
        """ナビゲーションボタンがクリックされたときの処理。"""
        self._update_status_bar(f"「{button_text}」ボタンがクリックされました。", "info")
        logger.info(f"SeminarGUI: ナビゲーションボタンクリック: {button_text}")
        # ここに各ボタンに応じた処理を追加
        if button_text == "終了":
            self._on_closing()
        # 他のタブへの切り替えなど
        # 例: if button_text == "登録": self.notebook.select(0)


    def _create_data_input_tab(self):
        """
        「データ入力と設定」タブを作成する。
        画像のレイアウトを参考に、入力フィールドの配置を調整。
        """
        logger.debug("SeminarGUI: 「データ入力と設定」タブの作成を開始します。")
        data_input_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(data_input_frame, text="データ入力と設定")

        # データ生成/ロード方法の選択
        data_method_frame = ttk.LabelFrame(data_input_frame, text="データ入力方法", padding="10")
        data_method_frame.pack(fill=tk.X, pady=10)
        self.data_input_method_var = tk.StringVar(value=self.initial_data_input_method)
        ttk.Radiobutton(data_method_frame, text="自動生成", variable=self.data_input_method_var, value="auto", command=self._update_data_input_method_fields).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(data_method_frame, text="JSONファイル", variable=self.data_input_method_var, value="json", command=self._update_data_input_method_fields).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(data_method_frame, text="CSVファイル", variable=self.data_input_method_var, value="csv", command=self._update_data_input_method_fields).pack(side=tk.LEFT, padx=5)
        logger.debug("SeminarGUI: データ入力方法の選択が完了しました。")

        # 自動生成設定フレーム
        self.auto_gen_frame = ttk.LabelFrame(data_input_frame, text="自動生成設定", padding="10")
        self.auto_gen_frame.pack(fill=tk.X, pady=5)
        self._create_auto_generate_fields(self.auto_gen_frame)
        logger.debug("SeminarGUI: 自動生成設定フレームの作成が完了しました。")

        # ファイル入力設定フレーム
        self.file_input_frame = ttk.LabelFrame(data_input_frame, text="ファイル入力設定", padding="10")
        self.file_input_frame.pack(fill=tk.X, pady=5)
        self._create_file_input_fields(self.file_input_frame)
        logger.debug("SeminarGUI: ファイル入力設定フレームの作成が完了しました。")

        # 最適化アルゴリズム設定フレーム
        optimization_settings_frame = ttk.LabelFrame(data_input_frame, text="最適化アルゴリズム設定", padding="10")
        optimization_settings_frame.pack(fill=tk.X, pady=5)
        self._create_optimization_algorithm_fields(optimization_settings_frame)
        logger.debug("SeminarGUI: 最適化アルゴリズム設定フレームの作成が完了しました。")

        # レポートとログ設定フレーム
        report_log_frame = ttk.LabelFrame(data_input_frame, text="レポートとログ設定", padding="10")
        report_log_frame.pack(fill=tk.X, pady=5)
        self._create_report_log_fields(report_log_frame)
        logger.debug("SeminarGUI: レポートとログ設定フレームの作成が完了しました。")

        logger.debug("SeminarGUI: 「データ入力と設定」タブの作成が完了しました。")


    def _create_auto_generate_fields(self, parent_frame: ttk.LabelFrame):
        """自動生成設定の入力フィールドを作成する。画像のレイアウトを参考に調整。"""
        logger.debug("SeminarGUI: 自動生成固有のフィールドの作成を開始します。")
        
        # 上部の入力フィールド群
        top_input_frame = ttk.Frame(parent_frame)
        top_input_frame.pack(fill=tk.X, pady=5)

        # 利用番号 / 提出期間のようなレイアウトを再現
        # 1行目
        ttk.Label(top_input_frame, text="セミナーID (カンマ区切り):").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.seminar_ids_entry = ttk.Entry(top_input_frame, width=40)
        self.seminar_ids_entry.insert(0, self.initial_seminars_str)
        self.seminar_ids_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        self.seminar_ids_entry.bind("<FocusOut>", self._update_magnification_entries)
        self.seminar_ids_entry.bind("<Return>", lambda event: self._update_magnification_entries())

        ttk.Label(top_input_frame, text="学生数:").grid(row=0, column=2, sticky=tk.W, pady=2, padx=5)
        self.num_students_var = tk.IntVar(value=self.initial_num_students)
        self.num_students_entry = ttk.Entry(top_input_frame, textvariable=self.num_students_var, width=15)
        self.num_students_entry.grid(row=0, column=3, sticky=(tk.W, tk.E), pady=2, padx=5)

        # 2行目
        ttk.Label(top_input_frame, text="最小定員:").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        self.min_capacity_var = tk.IntVar(value=self.initial_min_size)
        self.min_size_entry = ttk.Entry(top_input_frame, textvariable=self.min_capacity_var, width=15)
        self.min_size_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(top_input_frame, text="最大定員:").grid(row=1, column=2, sticky=tk.W, pady=2, padx=5)
        self.max_capacity_var = tk.IntVar(value=self.initial_max_size)
        self.max_size_entry = ttk.Entry(top_input_frame, textvariable=self.max_capacity_var, width=15)
        self.max_size_entry.grid(row=1, column=3, sticky=(tk.W, tk.E), pady=2, padx=5)

        # 3行目
        ttk.Label(top_input_frame, text="優先度分布:").grid(row=2, column=0, sticky=tk.W, pady=2, padx=5)
        self.preference_distribution_var = tk.StringVar(value=self.initial_preference_distribution)
        self.preference_distribution_menu = ttk.Combobox(top_input_frame, textvariable=self.preference_distribution_var, values=["random", "uniform", "biased"], state="readonly")
        self.preference_distribution_menu.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(top_input_frame, text="乱数シード:").grid(row=2, column=2, sticky=tk.W, pady=2, padx=5)
        self.random_seed_var = tk.IntVar(value=self.initial_random_seed)
        self.random_seed_entry = ttk.Entry(top_input_frame, textvariable=self.random_seed_var, width=15)
        self.random_seed_entry.grid(row=2, column=3, sticky=(tk.W, tk.E), pady=2, padx=5)

        # 4行目
        ttk.Label(top_input_frame, text="Qブースト確率:").grid(row=3, column=0, sticky=tk.W, pady=2, padx=5)
        self.q_boost_probability_var = tk.DoubleVar(value=self.initial_q_boost_probability)
        self.q_boost_probability_entry = ttk.Entry(top_input_frame, textvariable=self.q_boost_probability_var, width=15)
        self.q_boost_probability_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(top_input_frame, text="考慮する希望数:").grid(row=3, column=2, sticky=tk.W, pady=2, padx=5)
        self.num_preferences_to_consider_var = tk.IntVar(value=self.initial_num_preferences_to_consider)
        self.num_preferences_to_consider_entry = ttk.Entry(top_input_frame, textvariable=self.num_preferences_to_consider_var, width=15)
        self.num_preferences_to_consider_entry.grid(row=3, column=3, sticky=(tk.W, tk.E), pady=2, padx=5)

        top_input_frame.columnconfigure(1, weight=1)
        top_input_frame.columnconfigure(3, weight=1)

        # 倍率設定の動的フィールドは下部に配置
        self.magnification_frame = ttk.LabelFrame(parent_frame, text="セミナー倍率設定", padding="10")
        self.magnification_frame.pack(fill=tk.X, pady=5)
        self._update_magnification_entries() # 初期表示のために呼び出す
        logger.debug("SeminarGUI: 自動生成固有のフィールドの作成が完了しました。")


    def _update_magnification_entries(self, event=None):
        """セミナーIDに基づいて倍率入力フィールドを動的に更新する。"""
        logger.debug("SeminarGUI: 倍率エントリーの更新を開始します。")
        # 既存の倍率エントリーをクリア
        for widget in self.magnification_frame.winfo_children():
            widget.destroy()
        # self.magnification_entries は __init__ で初期化されているので、ここではクリアのみ
        self.magnification_entries.clear()

        seminar_ids_str = self.seminar_ids_entry.get()
        seminar_ids = [s.strip() for s in seminar_ids_str.split(',') if s.strip()]

        if not seminar_ids:
            ttk.Label(self.magnification_frame, text="セミナーIDを入力してください。").pack(pady=5)
            logger.debug("SeminarGUI: セミナーIDが空のため、倍率エントリーを更新しませんでした。")
            return

        # 倍率フィールドをグリッドで配置して、より整列させる
        for i, sem_id in enumerate(seminar_ids):
            row = i // 4 # 1行に4つまで表示
            col = (i % 4) * 2 # ラベルとエントリーで2列使う
            
            label = ttk.Label(self.magnification_frame, text=f"{sem_id} 倍率:")
            label.grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            
            # 既存の倍率があればそれを、なければデフォルト値を使用
            initial_mag = self.initial_magnification.get(sem_id, 1.0)
            entry_var = tk.DoubleVar(value=initial_mag)
            entry = ttk.Entry(self.magnification_frame, textvariable=entry_var, width=10)
            entry.grid(row=row, column=col+1, sticky=(tk.W, tk.E), padx=5, pady=2)
            self.magnification_entries[sem_id] = entry_var # StringVarではなくDoubleVarを保存
        
        # 列の伸縮設定
        for i in range(8): # 最大4つのペア (ラベル+エントリー) なので8列
            self.magnification_frame.columnconfigure(i, weight=1)
        logger.debug("SeminarGUI: 倍率エントリーの更新が完了しました。")


    def _create_file_input_fields(self, parent_frame: ttk.LabelFrame):
        """ファイル入力設定の入力フィールドを作成する。"""
        logger.debug("SeminarGUI: ファイル入力固有のフィールドの作成を開始します。")
        # config.jsonパス
        ttk.Label(parent_frame, text="設定ファイル (config.json):").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.config_file_path_var = tk.StringVar(value=self.initial_config_file_path)
        self.config_file_path_entry = ttk.Entry(parent_frame, textvariable=self.config_file_path_var, width=50)
        self.config_file_path_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        ttk.Button(parent_frame, text="参照", command=lambda: self._browse_file(self.config_file_path_var, [("JSON files", "*.json")])).grid(row=0, column=2, padx=5)

        # 学生ファイルパス
        ttk.Label(parent_frame, text="学生ファイル:").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        self.students_file_path_var = tk.StringVar(value=self.initial_student_file_path) # gui_settings.iniからロードした値を使用
        self.students_file_path_entry = ttk.Entry(parent_frame, textvariable=self.students_file_path_var, width=50)
        self.students_file_path_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        ttk.Button(parent_frame, text="参照", command=lambda: self._browse_file(self.students_file_path_var, [("JSON files", "*.json"), ("CSV files", "*.csv")])).grid(row=1, column=2, padx=5)

        # セミナーファイルパス
        ttk.Label(parent_frame, text="セミナーファイル:").grid(row=2, column=0, sticky=tk.W, pady=2, padx=5)
        self.seminars_file_path_var = tk.StringVar(value=self.initial_seminars_file_path) # gui_settings.iniからロードした値を使用
        self.seminars_file_path_entry = ttk.Entry(parent_frame, textvariable=self.seminars_file_path_var, width=50)
        self.seminars_file_path_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        ttk.Button(parent_frame, text="参照", command=lambda: self._browse_file(self.seminars_file_path_var, [("JSON files", "*.json"), ("CSV files", "*.csv")])).grid(row=2, column=2, padx=5)
        logger.debug("SeminarGUI: ファイル入力固有のフィールドの作成が完了しました。")


    def _create_optimization_algorithm_fields(self, parent_frame: ttk.LabelFrame):
        """最適化アルゴリズム設定の入力フィールドを作成する。"""
        logger.debug("SeminarGUI: 最適化アルゴリズム固有のフィールドの作成を開始します。")
        # 最適化戦略の選択
        ttk.Label(parent_frame, text="最適化戦略:").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.optimization_strategy_var = tk.StringVar(value=self.initial_optimization_strategy)
        strategies = ["Greedy_LS", "GA_LS", "ILP", "CP", "Multilevel", "Adaptive"]
        self.optimization_strategy_menu = ttk.Combobox(parent_frame, textvariable=self.optimization_strategy_var, values=strategies, state="readonly")
        self.optimization_strategy_menu.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        self.optimization_strategy_menu.bind("<<ComboboxSelected>>", self._update_algorithm_fields)

        # 各アルゴリズムのパラメータフレーム
        self.algo_params_frame = ttk.Frame(parent_frame, padding="5")
        self.algo_params_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))

        self._create_greedy_ls_fields(self.algo_params_frame)
        self._create_ga_ls_fields(self.algo_params_frame)
        self._create_ilp_fields(self.algo_params_frame)
        self._create_cp_fields(self.algo_params_frame)
        self._create_multilevel_fields(self.algo_params_frame)
        self._create_adaptive_fields(self.algo_params_frame) # 適応型最適化のフィールドを追加

        self._update_algorithm_fields() # 初期表示のために呼び出す
        logger.debug("SeminarGUI: 最適化アルゴリズム固有のフィールドの作成が完了しました。")


    def _create_greedy_ls_fields(self, parent_frame: ttk.Frame):
        """Greedy_LSアルゴリズムのパラメータフィールドを作成する。"""
        self.greedy_ls_frame = ttk.LabelFrame(parent_frame, text="Greedy_LS パラメータ", padding="10")
        
        ttk.Label(self.greedy_ls_frame, text="イテレーション数:").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.greedy_ls_iterations_var = tk.IntVar(value=self.initial_greedy_ls_iterations)
        self.greedy_ls_iterations_entry = ttk.Entry(self.greedy_ls_frame, textvariable=self.greedy_ls_iterations_var, width=15)
        self.greedy_ls_iterations_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.greedy_ls_frame, text="改善なし停止制限:").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        self.no_improvement_limit_var = tk.IntVar(value=self.initial_no_improvement_limit)
        self.no_improvement_limit_entry = ttk.Entry(self.greedy_ls_frame, textvariable=self.no_improvement_limit_var, width=15)
        self.no_improvement_limit_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.greedy_ls_frame, text="早期停止閾値:").grid(row=2, column=0, sticky=tk.W, pady=2, padx=5)
        self.early_stop_threshold_var = tk.DoubleVar(value=self.initial_early_stop_threshold)
        self.early_stop_threshold_entry = ttk.Entry(self.greedy_ls_frame, textvariable=self.early_stop_threshold_var, width=15)
        self.early_stop_threshold_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.greedy_ls_frame, text="初期温度:").grid(row=3, column=0, sticky=tk.W, pady=2, padx=5)
        self.initial_temperature_var = tk.DoubleVar(value=self.initial_initial_temperature)
        self.initial_temperature_entry = ttk.Entry(self.greedy_ls_frame, textvariable=self.initial_temperature_var, width=15)
        self.initial_temperature_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.greedy_ls_frame, text="冷却率:").grid(row=4, column=0, sticky=tk.W, pady=2, padx=5)
        self.cooling_rate_var = tk.DoubleVar(value=self.initial_cooling_rate)
        self.cooling_rate_entry = ttk.Entry(self.greedy_ls_frame, textvariable=self.cooling_rate_var, width=15)
        self.cooling_rate_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.greedy_ls_frame, text="最大ワーカー数:").grid(row=5, column=0, sticky=tk.W, pady=2, padx=5)
        self.max_workers_var = tk.IntVar(value=self.initial_max_workers)
        self.max_workers_entry = ttk.Entry(self.greedy_ls_frame, textvariable=self.max_workers_var, width=15)
        self.max_workers_entry.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.greedy_ls_frame, text="局所探索イテレーション:").grid(row=6, column=0, sticky=tk.W, pady=2, padx=5)
        self.local_search_iterations_var = tk.IntVar(value=self.initial_local_search_iterations)
        self.local_search_iterations_entry = ttk.Entry(self.greedy_ls_frame, textvariable=self.local_search_iterations_var, width=15)
        self.local_search_iterations_entry.grid(row=6, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)


    def _create_ga_ls_fields(self, parent_frame: ttk.Frame):
        """GA_LSアルゴリズムのパラメータフィールドを作成する。"""
        self.ga_ls_frame = ttk.LabelFrame(parent_frame, text="GA_LS パラメータ", padding="10")
        
        ttk.Label(self.ga_ls_frame, text="個体群サイズ:").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.ga_population_size_var = tk.IntVar(value=self.initial_ga_population_size)
        self.ga_population_size_entry = ttk.Entry(self.ga_ls_frame, textvariable=self.ga_population_size_var, width=15)
        self.ga_population_size_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.ga_ls_frame, text="世代数:").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        self.ga_generations_var = tk.IntVar(value=self.initial_ga_generations)
        self.ga_generations_entry = ttk.Entry(self.ga_ls_frame, textvariable=self.ga_generations_var, width=15)
        self.ga_generations_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.ga_ls_frame, text="突然変異率:").grid(row=2, column=0, sticky=tk.W, pady=2, padx=5)
        self.ga_mutation_rate_var = tk.DoubleVar(value=self.initial_ga_mutation_rate)
        self.ga_mutation_rate_entry = ttk.Entry(self.ga_ls_frame, textvariable=self.ga_mutation_rate_var, width=15)
        self.ga_mutation_rate_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.ga_ls_frame, text="交叉率:").grid(row=3, column=0, sticky=tk.W, pady=2, padx=5)
        self.ga_crossover_rate_var = tk.DoubleVar(value=self.initial_ga_crossover_rate)
        self.ga_crossover_rate_entry = ttk.Entry(self.ga_ls_frame, textvariable=self.ga_crossover_rate_var, width=15)
        self.ga_crossover_rate_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.ga_ls_frame, text="改善なし停止制限:").grid(row=4, column=0, sticky=tk.W, pady=2, padx=5)
        self.ga_no_improvement_limit_var = tk.IntVar(value=self.initial_ga_no_improvement_limit)
        self.ga_no_improvement_limit_entry = ttk.Entry(self.ga_ls_frame, textvariable=self.ga_no_improvement_limit_var, width=15)
        self.ga_no_improvement_limit_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)


    def _create_ilp_fields(self, parent_frame: ttk.Frame):
        """ILPアルゴリズムのパラメータフィールドを作成する。"""
        self.ilp_frame = ttk.LabelFrame(parent_frame, text="ILP パラメータ", padding="10")
        
        ttk.Label(self.ilp_frame, text="時間制限 (秒):").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.ilp_time_limit_var = tk.IntVar(value=self.initial_ilp_time_limit)
        self.ilp_time_limit_entry = ttk.Entry(self.ilp_frame, textvariable=self.ilp_time_limit_var, width=15)
        self.ilp_time_limit_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)


    def _create_cp_fields(self, parent_frame: ttk.Frame):
        """CP-SATアルゴリズムのパラメータフィールドを作成する。"""
        self.cp_frame = ttk.LabelFrame(parent_frame, text="CP-SAT パラメータ", padding="10")
        
        ttk.Label(self.cp_frame, text="時間制限 (秒):").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.cp_time_limit_var = tk.IntVar(value=self.initial_cp_time_limit)
        self.cp_time_limit_entry = ttk.Entry(self.cp_frame, textvariable=self.cp_time_limit_var, width=15)
        self.cp_time_limit_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)


    def _create_multilevel_fields(self, parent_frame: ttk.Frame):
        """Multilevelアルゴリズムのパラメータフィールドを作成する。"""
        self.multilevel_frame = ttk.LabelFrame(parent_frame, text="Multilevel パラメータ", padding="10")
        
        ttk.Label(self.multilevel_frame, text="クラスタ数:").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.multilevel_clusters_var = tk.IntVar(value=self.initial_multilevel_clusters)
        self.multilevel_clusters_entry = ttk.Entry(self.multilevel_frame, textvariable=self.multilevel_clusters_var, width=15)
        self.multilevel_clusters_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.multilevel_frame, text="局所探索イテレーション:").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        self.multilevel_local_search_iterations_var = tk.IntVar(value=self.initial_local_search_iterations) # Greedy_LSと共通
        self.multilevel_local_search_iterations_entry = ttk.Entry(self.multilevel_frame, textvariable=self.multilevel_local_search_iterations_var, width=15)
        self.multilevel_local_search_iterations_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)


    def _create_adaptive_fields(self, parent_frame: ttk.Frame):
        """適応型最適化アルゴリズムのパラメータフィールドを作成する。"""
        self.adaptive_frame = ttk.LabelFrame(parent_frame, text="Adaptive パラメータ", padding="10")

        ttk.Label(self.adaptive_frame, text="最大適応イテレーション:").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.max_adaptive_iterations_var = tk.IntVar(value=self.initial_max_adaptive_iterations)
        self.max_adaptive_iterations_entry = ttk.Entry(self.adaptive_frame, textvariable=self.max_adaptive_iterations_var, width=15)
        self.max_adaptive_iterations_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.adaptive_frame, text="戦略ごとの時間制限 (秒):").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        self.strategy_time_limit_var = tk.IntVar(value=self.initial_strategy_time_limit)
        self.strategy_time_limit_entry = ttk.Entry(self.adaptive_frame, textvariable=self.strategy_time_limit_var, width=15)
        self.strategy_time_limit_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.adaptive_frame, text="履歴サイズ:").grid(row=2, column=0, sticky=tk.W, pady=2, padx=5)
        self.adaptive_history_size_var = tk.IntVar(value=self.initial_adaptive_history_size)
        self.adaptive_history_size_entry = ttk.Entry(self.adaptive_frame, textvariable=self.adaptive_history_size_var, width=15)
        self.adaptive_history_size_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.adaptive_frame, text="探索率 (epsilon):").grid(row=3, column=0, sticky=tk.W, pady=2, padx=5)
        self.adaptive_exploration_epsilon_var = tk.DoubleVar(value=self.initial_adaptive_exploration_epsilon)
        self.adaptive_exploration_epsilon_entry = ttk.Entry(self.adaptive_frame, textvariable=self.adaptive_exploration_epsilon_var, width=15)
        self.adaptive_exploration_epsilon_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.adaptive_frame, text="学習率:").grid(row=4, column=0, sticky=tk.W, pady=2, padx=5)
        self.adaptive_learning_rate_var = tk.DoubleVar(value=self.initial_adaptive_learning_rate)
        self.adaptive_learning_rate_entry = ttk.Entry(self.adaptive_frame, textvariable=self.adaptive_learning_rate_var, width=15)
        self.adaptive_learning_rate_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.adaptive_frame, text="スコア重み:").grid(row=5, column=0, sticky=tk.W, pady=2, padx=5)
        self.adaptive_score_weight_var = tk.DoubleVar(value=self.initial_adaptive_score_weight)
        self.adaptive_score_weight_entry = ttk.Entry(self.adaptive_frame, textvariable=self.adaptive_score_weight_var, width=15)
        self.adaptive_score_weight_entry.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.adaptive_frame, text="未割り当て重み:").grid(row=6, column=0, sticky=tk.W, pady=2, padx=5)
        self.adaptive_unassigned_weight_var = tk.DoubleVar(value=self.initial_adaptive_unassigned_weight)
        self.adaptive_unassigned_weight_entry = ttk.Entry(self.adaptive_frame, textvariable=self.adaptive_unassigned_weight_var, width=15)
        self.adaptive_unassigned_weight_entry.grid(row=6, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.adaptive_frame, text="時間重み:").grid(row=7, column=0, sticky=tk.W, pady=2, padx=5)
        self.adaptive_time_weight_var = tk.DoubleVar(value=self.initial_adaptive_time_weight)
        self.adaptive_time_weight_entry = ttk.Entry(self.adaptive_frame, textvariable=self.adaptive_time_weight_var, width=15)
        self.adaptive_time_weight_entry.grid(row=7, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.adaptive_frame, text="正規化最大時間 (秒):").grid(row=8, column=0, sticky=tk.W, pady=2, padx=5)
        self.max_time_for_normalization_var = tk.DoubleVar(value=self.initial_max_time_for_normalization)
        self.max_time_for_normalization_entry = ttk.Entry(self.adaptive_frame, textvariable=self.max_time_for_normalization_var, width=15)
        self.max_time_for_normalization_entry.grid(row=8, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)


    def _update_algorithm_fields(self, event=None):
        """選択された最適化戦略に応じてパラメータフィールドを表示/非表示にする。"""
        logger.debug("SeminarGUI: アルゴリズムフィールドの更新を開始します。")
        # すべてのフレームを非表示にする
        for frame in [self.greedy_ls_frame, self.ga_ls_frame, self.ilp_frame, self.cp_frame, self.multilevel_frame, self.adaptive_frame]:
            frame.pack_forget()

        selected_strategy = self.optimization_strategy_var.get()
        if selected_strategy == "Greedy_LS":
            self.greedy_ls_frame.pack(fill=tk.X, pady=5)
        elif selected_strategy == "GA_LS":
            self.ga_ls_frame.pack(fill=tk.X, pady=5)
        elif selected_strategy == "ILP":
            self.ilp_frame.pack(fill=tk.X, pady=5)
        elif selected_strategy == "CP":
            self.cp_frame.pack(fill=tk.X, pady=5)
        elif selected_strategy == "Multilevel":
            self.multilevel_frame.pack(fill=tk.X, pady=5)
        elif selected_strategy == "Adaptive":
            self.adaptive_frame.pack(fill=tk.X, pady=5)
        logger.debug(f"SeminarGUI: 選択された戦略 '{selected_strategy}' に基づいてフィールドを更新しました。")


    def _create_report_log_fields(self, parent_frame: ttk.LabelFrame):
        """レポートとログ設定の入力フィールドを作成する。"""
        logger.debug("SeminarGUI: レポートとログ固有のフィールドの作成を開始します。")
        # スコア重み
        score_weights_frame = ttk.LabelFrame(parent_frame, text="スコア重み", padding="10")
        score_weights_frame.pack(fill=tk.X, pady=5)

        ttk.Label(score_weights_frame, text="第1希望:").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.pref_weight_1st_var = tk.DoubleVar(value=self.initial_preference_weights.get("1st_choice", 5.0))
        ttk.Entry(score_weights_frame, textvariable=self.pref_weight_1st_var, width=10).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(score_weights_frame, text="第2希望:").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        self.pref_weight_2nd_var = tk.DoubleVar(value=self.initial_preference_weights.get("2nd_choice", 2.0))
        ttk.Entry(score_weights_frame, textvariable=self.pref_weight_2nd_var, width=10).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(score_weights_frame, text="第3希望:").grid(row=2, column=0, sticky=tk.W, pady=2, padx=5)
        self.pref_weight_3rd_var = tk.DoubleVar(value=self.initial_preference_weights.get("3rd_choice", 1.0))
        ttk.Entry(score_weights_frame, textvariable=self.pref_weight_3rd_var, width=10).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(score_weights_frame, text="その他希望:").grid(row=3, column=0, sticky=tk.W, pady=2, padx=5)
        self.pref_weight_other_var = tk.DoubleVar(value=self.initial_preference_weights.get("other_preference", 0.5))
        ttk.Entry(score_weights_frame, textvariable=self.pref_weight_other_var, width=10).grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)


        # レポート生成オプション
        self.generate_pdf_report_var = tk.BooleanVar(value=self.initial_generate_pdf_report)
        self.generate_pdf_report_checkbox = ttk.Checkbutton(parent_frame, text="PDFレポートを生成", variable=self.generate_pdf_report_var)
        self.generate_pdf_report_checkbox.pack(anchor=tk.W, pady=2, padx=5)

        self.generate_csv_report_var = tk.BooleanVar(value=self.initial_generate_csv_report)
        self.generate_csv_report_checkbox = ttk.Checkbutton(parent_frame, text="CSVレポートを生成", variable=self.generate_csv_report_var)
        self.generate_csv_report_checkbox.pack(anchor=tk.W, pady=2, padx=5)

        # ログ有効化オプション
        self.log_enabled_var = tk.BooleanVar(value=self.initial_log_enabled)
        self.log_enabled_checkbox = ttk.Checkbutton(parent_frame, text="ログを有効にする", variable=self.log_enabled_var, command=self._toggle_logging)
        self.log_enabled_checkbox.pack(anchor=tk.W, pady=2, padx=5)

        # 中間結果保存オプション
        self.save_intermediate_var = tk.BooleanVar(value=self.initial_save_intermediate)
        self.save_intermediate_checkbox = ttk.Checkbutton(parent_frame, text="中間結果を保存", variable=self.save_intermediate_var)
        self.save_intermediate_checkbox.pack(anchor=tk.W, pady=2, padx=5)

        # 出力ディレクトリ
        ttk.Label(parent_frame, text="出力ディレクトリ:").pack(anchor=tk.W, pady=2, padx=5)
        self.output_directory_var = tk.StringVar(value=self.initial_output_directory)
        self.output_directory_entry = ttk.Entry(parent_frame, textvariable=self.output_directory_var, width=50)
        self.output_directory_entry.pack(fill=tk.X, pady=2, padx=5)
        ttk.Button(parent_frame, text="参照", command=lambda: self._browse_directory(self.output_directory_var)).pack(pady=5)
        logger.debug("SeminarGUI: レポートとログ固有のフィールドの作成が完了しました。")


    def _update_data_input_method_fields(self):
        """データ入力方法の選択に応じて関連フィールドの表示を切り替える。"""
        logger.debug("SeminarGUI: データ入力方法のフィールドを更新します。")
        selected_method = self.data_input_method_var.get()

        if selected_method == "auto":
            self.auto_gen_frame.pack(fill=tk.X, pady=5)
            self.file_input_frame.pack_forget()
        else: # "json" or "csv"
            self.auto_gen_frame.pack_forget()
            self.file_input_frame.pack(fill=tk.X, pady=5)
        logger.debug(f"SeminarGUI: データ入力方法を '{selected_method}' に切り替えました。")


    def _create_results_tab(self):
        """
        「最適化結果」タブを作成する。
        """
        logger.debug("SeminarGUI: 「最適化結果」タブを作成中...")
        results_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(results_frame, text="最適化結果")

        # 結果表示エリア
        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD, state='disabled', height=10) # 高さを調整
        self.results_text.pack(fill=tk.BOTH, expand=True, pady=10)

        # 最適化詳細表示エリア (ツリービューなど)
        self.results_tree = ttk.Treeview(results_frame, columns=("Parameter", "Value"), show="headings")
        self.results_tree.heading("Parameter", text="パラメータ")
        self.results_tree.heading("Value", text="値")
        self.results_tree.column("Parameter", width=150, anchor=tk.W)
        self.results_tree.column("Value", width=250, anchor=tk.W)
        self.results_tree.pack(fill=tk.BOTH, expand=True, pady=10)
        logger.debug("SeminarGUI: 「最適化結果」タブの作成が完了しました。")


    def _create_log_tab(self):
        """
        「ログ」タブを作成する。
        """
        logger.debug("SeminarGUI: 「ログ」タブを作成中...")
        log_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(log_frame, text="ログ")

        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state='disabled')
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=10)

        # TextHandlerを設定
        self.text_handler = TextHandler(self.log_text)
        self.text_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(self.text_handler)
        logging.getLogger().setLevel(logging.DEBUG) # 全てのログレベルをTextHandlerに送る
        logger.debug("SeminarGUI: 「ログ」タブの作成が完了しました。")


    def _create_main_buttons(self, parent_frame: ttk.Frame):
        """
        メインの操作ボタンを作成する。
        """
        logger.debug("SeminarGUI: メインボタンを作成中...")
        button_frame = ttk.Frame(parent_frame, padding="10")
        button_frame.pack(fill=tk.X, pady=10)

        ttk.Button(button_frame, text="最適化開始", command=self._start_optimization).pack(side=tk.LEFT, padx=5, expand=True)
        ttk.Button(button_frame, text="最適化停止", command=self._cancel_optimization).pack(side=tk.LEFT, padx=5, expand=True)
        ttk.Button(button_frame, text="結果クリア", command=self._clear_results).pack(side=tk.LEFT, padx=5, expand=True)
        ttk.Button(button_frame, text="設定保存", command=self._save_current_gui_settings).pack(side=tk.LEFT, padx=5, expand=True)
        # 終了ボタンはナビゲーションに移動したが、念のためここにも残しておく
        # ttk.Button(button_frame, text="終了", command=self._on_closing).pack(side=tk.LEFT, padx=5, expand=True)
        logger.debug("SeminarGUI: メインボタンの作成が完了しました。")


    def _browse_file(self, tk_string_var: tk.StringVar, filetypes: List[Tuple[str, str]]):
        """ファイル参照ダイアログを開き、選択されたパスをStringVarに設定する。"""
        logger.debug("SeminarGUI: ファイル参照ダイアログを開きます。")
        filepath = filedialog.askopenfilename(filetypes=filetypes)
        if filepath:
            tk_string_var.set(filepath)
            logger.info(f"ファイルが選択されました: {filepath}")
            self._update_status_bar(f"ファイル選択: {os.path.basename(filepath)}", "info")


    def _browse_directory(self, tk_string_var: tk.StringVar):
        """ディレクトリ参照ダイアログを開き、選択されたパスをStringVarに設定する。"""
        logger.debug("SeminarGUI: ディレクトリ参照ダイアログを開きます。")
        directorypath = filedialog.askdirectory()
        if directorypath:
            tk_string_var.set(directorypath)
            logger.info(f"ディレクトリが選択されました: {directorypath}")
            self._update_status_bar(f"ディレクトリ選択: {os.path.basename(directorypath)}", "info")


    def _toggle_logging(self):
        """ログの有効/無効を切り替える。"""
        if self.log_enabled_var.get():
            setup_logging(log_level="DEBUG", log_file=str(PROJECT_ROOT / "seminar_optimization_log.txt"))
            self._update_status_bar("ログが有効になりました。", "info")
        else:
            # ロギングを無効にする（既存のハンドラを削除）
            for handler in logging.root.handlers[:]:
                if isinstance(handler, logging.FileHandler) or isinstance(handler, TextHandler):
                    handler.close()
                    logging.root.removeHandler(handler)
            self._update_status_bar("ログが無効になりました。", "info")
        logger.debug(f"SeminarGUI: ログの状態が {self.log_enabled_var.get()} に切り替わりました。")


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


    def _start_optimization(self):
        """最適化プロセスを開始する。"""
        logger.info("最適化開始ボタンが押されました。")
        if self.optimization_thread and self.optimization_thread.is_alive():
            self._update_status_bar("最適化がすでに実行中です。", "warning")
            logger.warning("SeminarGUI: 最適化がすでに実行中のため、開始要求を無視します。")
            return

        # 結果表示エリアをクリア
        self._clear_results()
        self._update_status_bar("最適化を開始しています...", "info")
        self.cancel_event.clear() # キャンセルイベントをリセット

        # 現在のGUI設定からconfigを構築
        current_config = self._get_current_config_from_gui()
        
        # config.jsonのスキーマで検証
        try:
            jsonschema.validate(instance=current_config, schema=CONFIG_SCHEMA)
            logger.info("SeminarGUI: 現在のGUI設定から構築したconfigがスキーマ検証に成功しました。")
        except jsonschema.exceptions.ValidationError as e:
            error_message = f"入力設定のスキーマ検証エラー: {e.message} (パス: {'.'.join(map(str, e.path))})"
            logger.error(f"SeminarGUI: {error_message}", exc_info=True)
            self._update_status_bar(f"エラー: {error_message}", "error")
            messagebox.showerror("設定エラー", error_message)
            return

        self.optimization_thread = threading.Thread(
            target=self._run_optimization,
            args=(current_config, self.cancel_event)
        )
        self.optimization_thread.start()
        self._show_progress_dialog()
        logger.info("SeminarGUI: 最適化スレッドが開始されました。")


    def _get_current_config_from_gui(self) -> Dict[str, Any]:
        """
        現在のGUI入力から最適化設定を構築する。
        """
        logger.debug("SeminarGUI: 現在のGUI設定からconfigを構築します。")
        config = self.optimization_config.copy() # デフォルト設定をベースにする

        # データ生成/ファイル入力の設定
        data_input_method = self.data_input_method_var.get()
        config["data_input_method"] = data_input_method
        
        if data_input_method == "auto":
            config["num_seminars"] = self.num_seminars_var.get()
            config["min_capacity"] = self.min_capacity_var.get()
            config["max_capacity"] = self.max_capacity_var.get()
            config["num_students"] = self.num_students_var.get()
            config["min_preferences"] = self.min_preferences_var.get()
            config["max_preferences"] = self.max_preferences_var.get()
            config["preference_distribution"] = self.preference_distribution_var.get()
            config["random_seed"] = self.random_seed_var.get()
            config["q_boost_probability"] = self.q_boost_probability_var.get()
            config["num_preferences_to_consider"] = self.num_preferences_to_consider_var.get()

            # 動的に生成された倍率を収集
            current_magnification = {}
            seminar_ids_str = self.seminar_ids_entry.get()
            seminar_ids = [s.strip() for s in seminar_ids_str.split(',') if s.strip()]
            for sem_id in seminar_ids:
                if sem_id in self.magnification_entries:
                    try:
                        current_magnification[sem_id] = self.magnification_entries[sem_id].get()
                    except tk.TclError:
                        logger.warning(f"SeminarGUI: セミナー '{sem_id}' の倍率が無効な値です。デフォルト値を使用します。")
                        current_magnification[sem_id] = 1.0 # 無効な場合はデフォルト値
            config["seminar_specific_magnifications"] = current_magnification # 新しいキー名で保存
            config["seminars"] = [{"id": s_id, "capacity": 0, "magnification": current_magnification.get(s_id, 1.0)} for s_id in seminar_ids] # ダミーのセミナーリスト
            config["students"] = [] # ダミーの学生リスト

        else: # "json" or "csv"
            config["seminars_file"] = self.seminars_file_path_var.get()
            config["students_file"] = self.students_file_path_var.get()
            config["config_file_path"] = self.config_file_path_var.get() # ここはGUIの設定ファイルパスなので、config.jsonには不要だが、念のため

        # 最適化アルゴリズム設定
        config["optimization_strategy"] = self.optimization_strategy_var.get()
        config["ga_population_size"] = self.ga_population_size_var.get()
        config["ga_generations"] = self.ga_generations_var.get()
        config["ga_mutation_rate"] = self.ga_mutation_rate_var.get()
        config["ga_crossover_rate"] = self.ga_crossover_rate_var.get()
        config["ga_no_improvement_limit"] = self.ga_no_improvement_limit_var.get()
        config["ilp_time_limit"] = self.ilp_time_limit_var.get()
        config["cp_time_limit"] = self.cp_time_limit_var.get()
        config["multilevel_clusters"] = self.multilevel_clusters_var.get()
        config["greedy_ls_iterations"] = self.greedy_ls_iterations_var.get()
        config["local_search_iterations"] = self.local_search_iterations_var.get()
        config["early_stop_no_improvement_limit"] = self.no_improvement_limit_var.get() # GUIのno_improvement_limitを使用
        config["initial_temperature"] = self.initial_temperature_var.get()
        config["cooling_rate"] = self.cooling_rate_var.get()
        config["max_workers"] = self.max_workers_var.get()

        # スコア重み
        config["score_weights"] = {
            "1st_choice": self.pref_weight_1st_var.get(),
            "2nd_choice": self.pref_weight_2nd_var.get(),
            "3rd_choice": self.pref_weight_3rd_var.get(),
            "other_preference": self.pref_weight_other_var.get()
        }

        # レポートとログ設定
        config["generate_pdf_report"] = self.generate_pdf_report_var.get()
        config["generate_csv_report"] = self.generate_csv_report_var.get()
        config["log_enabled"] = self.log_enabled_var.get()
        config["output_directory"] = self.output_directory_var.get()
        config["save_intermediate"] = self.save_intermediate_var.get() # 中間結果保存のオプションを追加

        # 適応型最適化設定
        config["max_adaptive_iterations"] = self.max_adaptive_iterations_var.get()
        config["strategy_time_limit"] = self.strategy_time_limit_var.get()
        config["adaptive_history_size"] = self.adaptive_history_size_var.get()
        config["adaptive_exploration_epsilon"] = self.adaptive_exploration_epsilon_var.get()
        config["adaptive_learning_rate"] = self.adaptive_learning_rate_var.get()
        config["adaptive_score_weight"] = self.adaptive_score_weight_var.get()
        config["adaptive_unassigned_weight"] = self.adaptive_unassigned_weight_var.get()
        config["adaptive_time_weight"] = self.adaptive_time_weight_var.get()
        config["max_time_for_normalization"] = self.max_time_for_normalization_var.get()

        logger.debug(f"SeminarGUI: 構築されたconfig: {config}")
        return config


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
                seminars_ids_list = [s.strip() for s in self.seminar_ids_entry.get().split(',') if s.strip()]
                
                # 自動生成の場合、configからセミナーと学生の数を取得
                num_seminars = current_config.get("num_seminars")
                min_capacity = current_config.get("min_capacity")
                max_capacity = current_config.get("max_capacity")
                num_students = current_config.get("num_students")
                min_preferences = current_config.get("min_preferences")
                max_preferences = current_config.get("max_preferences")
                preference_distribution = current_config.get("preference_distribution")
                random_seed = current_config.get("random_seed")
                
                # DataGeneratorのインスタンスを更新
                self.data_generator.config = current_config
                
                seminars_data, students_data = self.data_generator.generate_data(
                    num_seminars=num_seminars,
                    min_capacity=min_capacity,
                    max_capacity=max_capacity,
                    num_students=num_students,
                    min_preferences=min_preferences,
                    max_preferences=max_preferences,
                    preference_distribution=preference_distribution,
                    random_seed=random_seed,
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
        logger.debug("SeminarGUI: プログレスダイアログを表示します。")
        if self.progress_dialog is None:
            self.progress_dialog = tk.Toplevel(self.root)
            self.progress_dialog.title("最適化の進捗")
            self.progress_dialog.geometry("400x150")
            self.progress_dialog.transient(self.root) # 親ウィンドウの上に表示
            self.progress_dialog.grab_set() # 他のウィンドウ操作をブロック

            self.progress_label = ttk.Label(self.progress_dialog, text="最適化を開始しています...", wraplength=350)
            self.progress_label.pack(pady=20)

            self.progress_bar = ttk.Progressbar(self.progress_dialog, mode='indeterminate', length=300)
            self.progress_bar.pack(pady=10)
            self.progress_bar.start(10) # 10msごとに更新

            # キャンセルボタン
            ttk.Button(self.progress_dialog, text="キャンセル", command=self._cancel_optimization).pack(pady=5)
            
            # ウィンドウが閉じられたときの処理
            self.progress_dialog.protocol("WM_DELETE_WINDOW", self._cancel_optimization)
        else:
            self.progress_dialog.deiconify() # 既に存在する場合は再表示
        logger.debug("SeminarGUI: プログレスダイアログが表示されました。")


    def _update_progress_dialog(self, message: str):
        """プログレスダイアログのメッセージを更新する。"""
        if self.progress_dialog and self.progress_label:
            self.progress_label.config(text=message)
            self.root.update_idletasks() # UIを即座に更新


    def _hide_progress_dialog(self):
        """プログレスダイアログを非表示にする。"""
        logger.debug("SeminarGUI: プログレスダイアログを非表示にします。")
        if self.progress_dialog:
            if self.progress_bar:
                self.progress_bar.stop()
            self.progress_dialog.grab_release() # ブロックを解除
            self.progress_dialog.destroy()
            self.progress_dialog = None
            self.progress_label = None
            self.progress_bar = None
        logger.debug("SeminarGUI: プログレスダイアログが非表示になりました。")


    def _cancel_optimization(self):
        """最適化プロセスをキャンセルする。"""
        logger.info("最適化停止ボタンが押されました。")
        if self.optimization_thread and self.optimization_thread.is_alive():
            self.cancel_event.set() # キャンセルイベントを設定
            self._update_status_bar("最適化をキャンセルしています...", "warning")
            logger.warning("SeminarGUI: 最適化のキャンセル要求が送信されました。")
        else:
            self._update_status_bar("実行中の最適化はありません。", "info")
            logger.info("SeminarGUI: 実行中の最適化がないため、キャンセル要求を無視します。")
        # プログレスダイアログはスレッド終了時に自動的に閉じられるはずだが、念のためここでも非表示を試みる
        self._hide_progress_dialog()


    def _display_results(self, result: Any):
        """
        最適化結果をUIに表示する。
        """
        logger.info("最適化結果をUIに表示します。")
        self.results_text.config(state='normal')
        self.results_text.delete(1.0, tk.END)

        if result:
            self.results_text.insert(tk.END, f"最適化ステータス: {result.status}\n")
            self.results_text.insert(tk.END, f"メッセージ: {result.message}\n")
            self.results_text.insert(tk.END, f"最適化戦略: {result.optimization_strategy}\n")
            self.results_text.insert(tk.END, f"ベストスコア: {result.best_score:.2f}\n")
            self.results_text.insert(tk.END, f"未割り当て学生数: {len(result.unassigned_students)}\n\n")

            self.results_text.insert(tk.END, "--- 割り当て結果 ---\n")
            if result.best_assignment:
                for student_id, seminar_id in result.best_assignment.items():
                    self.results_text.insert(tk.END, f"学生 {student_id}: {seminar_id}\n")
            else:
                self.results_text.insert(tk.END, "割り当てられた学生はいません。\n")

            self.results_text.insert(tk.END, "\n--- 未割り当て学生 ---\n")
            if result.unassigned_students:
                for student_id in result.unassigned_students:
                    self.results_text.insert(tk.END, f"学生 {student_id}\n")
            else:
                self.results_text.insert(tk.END, "未割り当て学生はいません。\n")

            # ツリービューに詳細を表示
            self.results_tree.delete(*self.results_tree.get_children()) # 既存の項目をクリア
            self.results_tree.insert("", "end", values=("最適化ステータス", result.status))
            self.results_tree.insert("", "end", values=("最適化戦略", result.optimization_strategy))
            self.results_tree.insert("", "end", values=("ベストスコア", f"{result.best_score:.2f}"))
            self.results_tree.insert("", "end", values=("未割り当て学生数", len(result.unassigned_students)))

            # セミナーごとの割り当て数を計算して表示
            seminar_counts: Dict[str, int] = {sem_id: 0 for sem_id in result.seminar_capacities.keys()}
            for assigned_seminar_id in result.best_assignment.values():
                if assigned_seminar_id in seminar_counts:
                    seminar_counts[assigned_seminar_id] += 1
            
            self.results_tree.insert("", "end", values=("", "")) # 区切り
            self.results_tree.insert("", "end", values=("セミナー割り当て概要", ""))
            for sem_id, count in seminar_counts.items():
                capacity = result.seminar_capacities.get(sem_id, "N/A")
                self.results_tree.insert("", "end", values=(f"  {sem_id} (定員 {capacity})", f"{count}人"))

            self._update_status_bar(f"最適化完了: {result.status}", "info")
            self.notebook.select(self.notebook.tabs()[1]) # 結果タブに切り替える
        else:
            self.results_text.insert(tk.END, "最適化結果がありません。\n")
            self._update_status_bar("最適化が結果を返しませんでした。", "warning")

        self.results_text.config(state='disabled')
        logger.info("最適化結果のUI表示が完了しました。")


    def _clear_results(self):
        """結果表示エリアをクリアする。"""
        logger.info("結果クリアボタンが押されました。")
        self.results_text.config(state='normal')
        self.results_text.delete(1.0, tk.END)
        self.results_text.config(state='disabled')
        self.results_tree.delete(*self.results_tree.get_children())
        self._update_status_bar("結果表示をクリアしました。", "info")


    def _save_current_gui_settings(self):
        """現在のGUI設定をgui_settings.iniに保存する。"""
        logger.info("設定保存ボタンが押されました。")
        if not self.gui_settings.has_section('GUI'):
            self.gui_settings.add_section('GUI')

        # GUIの現在の値を取得して保存
        self.gui_settings.set('GUI', 'seminars', self.seminar_ids_entry.get())
        self.gui_settings.set('GUI', 'num_students', str(self.num_students_var.get()))
        
        # 倍率設定を辞書として保存
        current_magnification_values = {
            sem_id: self.magnification_entries[sem_id].get()
            for sem_id in [s.strip() for s in self.seminar_ids_entry.get().split(',') if s.strip()]
            if sem_id in self.magnification_entries
        }
        self.gui_settings.set('GUI', 'magnification', json.dumps(current_magnification_values))

        self.gui_settings.set('GUI', 'min_size', str(self.min_capacity_var.get()))
        self.gui_settings.set('GUI', 'max_size', str(self.max_capacity_var.get()))
        self.gui_settings.set('GUI', 'q_boost_probability', str(self.q_boost_probability_var.get()))
        self.gui_settings.set('GUI', 'num_preferences_to_consider', str(self.num_preferences_to_consider_var.get()))
        self.gui_settings.set('GUI', 'num_patterns', str(self.num_patterns_entry.get()))
        self.gui_settings.set('GUI', 'max_workers', str(self.max_workers_var.get()))
        self.gui_settings.set('GUI', 'local_search_iterations', str(self.local_search_iterations_var.get()))
        self.gui_settings.set('GUI', 'initial_temperature', str(self.initial_temperature_var.get()))
        self.gui_settings.set('GUI', 'cooling_rate', str(self.cooling_rate_var.get()))
        
        # preference_weights を個別に保存
        self.gui_settings.set('GUI', 'preference_weights_1st', str(self.pref_weight_1st_var.get()))
        self.gui_settings.set('GUI', 'preference_weights_2nd', str(self.pref_weight_2nd_var.get()))
        self.gui_settings.set('GUI', 'preference_weights_3rd', str(self.pref_weight_3rd_var.get()))
        self.gui_settings.set('GUI', 'preference_weights_other', str(self.pref_weight_other_var.get()))


        self.gui_settings.set('GUI', 'early_stop_threshold', str(self.early_stop_threshold_var.get()))
        self.gui_settings.set('GUI', 'no_improvement_limit', str(self.no_improvement_limit_var.get()))
        self.gui_settings.set('GUI', 'data_source', self.data_source_var.get())
        self.gui_settings.set('GUI', 'log_enabled', str(self.log_enabled_var.get()))
        self.gui_settings.set('GUI', 'save_intermediate', str(self.save_intermediate_var.get()))
        self.gui_settings.set('GUI', 'theme', self.style.theme_use()) # 現在のテーマを保存
        self.gui_settings.set('GUI', 'config_file_path', self.config_file_path_var.get())
        self.gui_settings.set('GUI', 'student_file_path', self.student_file_path_var.get())
        self.gui_settings.set('GUI', 'ga_population_size', str(self.ga_population_size_var.get()))
        self.gui_settings.set('GUI', 'ga_crossover_rate', str(self.ga_crossover_rate_var.get()))
        self.gui_settings.set('GUI', 'ga_mutation_rate', str(self.ga_mutation_rate_var.get()))
        self.gui_settings.set('GUI', 'optimization_strategy', self.optimization_strategy_var.get())
        self.gui_settings.set('GUI', 'seminars_file_path', self.seminars_file_path_var.get())
        self.gui_settings.set('GUI', 'students_file_path', self.students_file_path_var.get())
        self.gui_settings.set('GUI', 'data_input_method', self.data_input_method_var.get())
        self.gui_settings.set('GUI', 'num_seminars', str(self.num_seminars_var.get()))
        self.gui_settings.set('GUI', 'min_preferences', str(self.min_preferences_var.get()))
        self.gui_settings.set('GUI', 'max_preferences', str(self.max_preferences_var.get()))
        self.gui_settings.set('GUI', 'preference_distribution', self.preference_distribution_var.get())
        self.gui_settings.set('GUI', 'random_seed', str(self.random_seed_var.get()))
        self.gui_settings.set('GUI', 'ilp_time_limit', str(self.ilp_time_limit_var.get()))
        self.gui_settings.set('GUI', 'cp_time_limit', str(self.cp_time_limit_var.get()))
        self.gui_settings.set('GUI', 'multilevel_clusters', str(self.multilevel_clusters_var.get()))
        self.gui_settings.set('GUI', 'generate_pdf_report', str(self.generate_pdf_report_var.get()))
        self.gui_settings.set('GUI', 'generate_csv_report', str(self.generate_csv_report_var.get()))
        self.gui_settings.set('GUI', 'max_adaptive_iterations', str(self.max_adaptive_iterations_var.get()))
        self.gui_settings.set('GUI', 'strategy_time_limit', str(self.strategy_time_limit_var.get()))
        self.gui_settings.set('GUI', 'adaptive_history_size', str(self.adaptive_history_size_var.get()))
        self.gui_settings.set('GUI', 'adaptive_exploration_epsilon', str(self.adaptive_exploration_epsilon_var.get()))
        self.gui_settings.set('GUI', 'adaptive_learning_rate', str(self.adaptive_learning_rate_var.get()))
        self.gui_settings.set('GUI', 'adaptive_score_weight', str(self.adaptive_score_weight_var.get()))
        self.gui_settings.set('GUI', 'adaptive_unassigned_weight', str(self.adaptive_unassigned_weight_var.get()))
        self.gui_settings.set('GUI', 'adaptive_time_weight', str(self.adaptive_time_weight_var.get()))
        self.gui_settings.set('GUI', 'max_time_for_normalization', str(self.max_time_for_normalization_var.get()))
        self.gui_settings.set('GUI', 'greedy_ls_iterations', str(self.greedy_ls_iterations_var.get())) # 追加: Greedy_LSイテレーション


        gui_settings_path = PROJECT_ROOT / "gui_settings.ini"
        try:
            with open(gui_settings_path, 'w', encoding='utf-8') as configfile:
                self.gui_settings.write(configfile)
            logger.info(f"SeminarGUI: GUI設定を '{gui_settings_path}' に保存しました。")
            self._update_status_bar("GUI設定を保存しました。", "info")
        except Exception as e:
            logger.error(f"SeminarGUI: GUI設定の保存中にエラーが発生しました: {e}", exc_info=True)
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
        if self.progress_dialog:
            self.progress_dialog.destroy()
            self.progress_dialog = None

        # TextHandlerをロガーから削除
        if self.text_handler:
            logging.getLogger().removeHandler(self.text_handler)
            logger.debug("TextHandler removed from logger.")
            self.text_handler.close() # ハンドラの解放

        self.root.destroy()
        logger.info("アプリケーションが正常に終了しました。")


if __name__ == "__main__":
    # ロギングの初期設定 (ファイル出力はGUI設定で制御)
    setup_logging(log_level="DEBUG", log_file=str(PROJECT_ROOT / "logs" / f"seminar_optimization_{datetime.now().strftime('%Y%m%d')}.log"))
    logger.info("main: アプリケーションのロギングが初期化されました。")
    
    root = tk.Tk()
    app = SeminarGUI(root)
    root.mainloop()
    logger.info("Main loop exited.")
