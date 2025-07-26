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
# プロジェクトルートをsys.pathに追加して、絶対インポートを可能にする
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# seminar_optimization パッケージ内のモジュールをインポート
from seminar_optimization.logger_config import setup_logging, logger
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

class MainApplication(tk.Tk):
    """
    セミナー割当最適化ツールのメインアプリケーションクラス。
    GUIの構築、設定の管理、最適化処理の実行を統括する。
    """
    def __init__(self, project_root: Path):
        super().__init__()
        # self.project_root は必ず最初に設定する
        self.project_root = project_root 
        self.title("セミナー割当最適化ツール")
        self.geometry("1200x800") # ウィンドウの初期サイズを設定

        # ロギング設定の初期化
        # gui_settings.iniから読み込む前に、一時的にデフォルトのログレベルを設定
        setup_logging(log_level="INFO", log_file=str(self.project_root / "logs" / "seminar_optimization.log"))

        # GUI設定の初期値 (SettingsManagerからロードされる値を保持する属性を定義)
        # DataInputTabが管理する設定
        self.initial_seminars_file_path: str = ""
        self.initial_students_file_path: str = ""
        self.initial_data_input_method: str = "auto_generate"
        self.initial_num_seminars: int = 5
        self.initial_num_students: int = 50
        self.initial_min_capacity: int = 5
        self.initial_max_capacity: int = 15
        self.initial_preference_distribution: str = "uniform"
        self.initial_random_seed: int = 42
        self.initial_q_boost_probability: float = 0.2
        self.initial_num_preferences_to_consider: int = 5 # UI上の「考慮する希望数（最大）」
        self.initial_min_preferences: int = 1 # 最小希望数の初期値
        self.initial_max_preferences: int = 5 # 最大希望数の初期値 (num_preferences_to_considerと同じ値で初期化)

        # SettingTabが管理する設定
        self.initial_optimization_strategy: str = "Greedy_LS"
        self.initial_ga_population_size: int = 100
        self.initial_ga_generations: int = 200
        self.initial_ga_mutation_rate: float = 0.05
        self.initial_ga_crossover_rate: float = 0.8
        self.initial_ga_no_improvement_limit: int = 10
        self.initial_ilp_time_limit: int = 300
        self.initial_cp_time_limit: int = 300
        self.initial_multilevel_clusters: int = 5
        self.initial_greedy_ls_iterations: int = 200000
        self.initial_local_search_iterations: int = 500
        self.initial_initial_temperature: float = 1.0
        self.initial_cooling_rate: float = 0.995
        self.initial_score_weights: Dict[str, float] = {"1st_choice": 5.0, "2nd_choice": 2.0, "3rd_choice": 1.0, "other": 0.5}
        self.initial_early_stop_threshold: float = 0.001
        # 修正: early_stop_no_improvement_limit に名前を変更
        self.initial_early_stop_no_improvement_limit: int = 1000 
        self.initial_generate_pdf_report: bool = True
        self.initial_generate_csv_report: bool = True
        self.initial_output_directory: Path = self.project_root / "output"
        self.initial_pdf_font_path: str = ""
        self.initial_debug_mode: bool = False
        self.initial_log_enabled: bool = True
        self.initial_save_intermediate: bool = False
        self.initial_theme: str = "clam"
        self.initial_config_file_path: str = ""

        # SettingsManagerから設定をロードし、initial_属性を更新
        self.settings_manager = SettingsManager(self.project_root)
        loaded_settings = self.settings_manager.load_gui_settings(self)
        for key, value in loaded_settings.items():
            full_key = 'initial_' + key
            if hasattr(self, full_key):
                setattr(self, full_key, value)
            else:
                logger.warning(f"MainApplication: 未知の初期設定 '{key}' がgui_settings.iniに存在します。")
        
        # ロギング設定をgui_settings.iniから読み込んだ値で再設定
        setup_logging(
            log_level="DEBUG" if self.initial_debug_mode else "INFO",
            log_file=str(self.project_root / "logs" / "seminar_optimization.log") if self.initial_log_enabled else None
        )
        logger.info("MainApplication: アプリケーションの初期化を開始します。")

        # 出力ディレクトリが存在しない場合は作成
        self.initial_output_directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"MainApplication: 出力ディレクトリを確認/作成しました: {self.initial_output_directory}")

        # スタイル設定
        self.style = ttk.Style()
        self.style.theme_use(self.initial_theme)
        logger.debug(f"MainApplication: GUIテーマを '{self.initial_theme}' に設定しました。")

        self._create_widgets()
        self._create_main_buttons()

        self.optimization_thread: Optional[threading.Thread] = None
        self.cancel_optimization_event = threading.Event()
        self.progress_dialog = ProgressDialog(self, self._cancel_optimization)

        # 最適化サービスを初期化
        self.optimizer_service = OptimizerService(
            progress_callback=self._update_progress_message,
            logger_instance=logger
        )
        logger.debug("MainApplication: OptimizerServiceを初期化しました。")

        # アプリケーション終了時の処理を設定
        self.protocol("WM_DELETE_WINDOW", self._on_closing)
        logger.info("MainApplication: 初期化が完了しました。")

    def _create_widgets(self):
        """
        メインウィンドウのウィジェットを作成する。
        """
        logger.debug("MainApplication: メインウィジェットの作成を開始します。")
        # 左右に分割するPanedWindow
        self.paned_window = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 左側のフレーム（コントロールパネル）
        self.control_frame = ttk.Frame(self.paned_window, width=400)
        self.paned_window.add(self.control_frame, weight=1)

        # コントロールフレーム内にノートブック（タブ）を作成
        self.notebook = ttk.Notebook(self.control_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # 各タブのインスタンスを作成し、ノートブックに追加
        # 各タブにMainApplicationインスタンス自身を渡すことで、設定値にアクセスできるようにする
        self.data_input_tab = DataInputTab(self.notebook, self)
        self.setting_tab = SettingTab(self.notebook, self)
        self.results_tab = ResultsTab(self.notebook)
        self.log_tab = LogTab(self.notebook)

        self.notebook.add(self.data_input_tab.frame, text="データ入力")
        self.notebook.add(self.setting_tab.frame, text="設定")
        self.notebook.add(self.results_tab.frame, text="最適化結果")
        self.notebook.add(self.log_tab.frame, text="ログ")

        # 右側のフレーム（将来的なグラフ表示など）
        self.display_frame = ttk.Frame(self.paned_window, width=800)
        self.paned_window.add(self.display_frame, weight=2)
        
        # 仮の表示内容
        ttk.Label(self.display_frame, text="最適化結果のグラフや詳細表示エリア", font=("Inter", 16)).pack(pady=50)
        logger.debug("MainApplication: メインウィジェットの作成が完了しました。")


    def _create_main_buttons(self):
        """
        メイン操作ボタンを作成する。
        """
        logger.debug("MainApplication: メインボタンの作成を開始します。")
        button_frame = ttk.Frame(self)
        button_frame.pack(pady=10)

        self.start_button = ttk.Button(button_frame, text="最適化実行", command=self._start_optimization)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.save_settings_button = ttk.Button(button_frame, text="設定保存", command=self.save_current_settings)
        self.save_settings_button.pack(side=tk.LEFT, padx=5)

        self.exit_button = ttk.Button(button_frame, text="終了", command=self._on_closing)
        self.exit_button.pack(side=tk.LEFT, padx=5)
        logger.debug("MainApplication: メインボタンの作成が完了しました。")

    def save_current_settings(self):
        """
        GUIの現在の設定値をgui_settings.iniに保存する。
        各タブから最新の設定値を取得し、MainApplicationの属性に反映させてから保存する。
        """
        logger.info("MainApplication: 現在の設定の保存を開始します。")
        settings_to_save = {}

        # DataInputTabからデータを取得
        data_input_settings = self.data_input_tab.get_current_settings_for_main_app()
        settings_to_save.update(data_input_settings)

        # SettingTabからデータを取得
        general_settings = self.setting_tab.get_current_settings_for_main_app()
        settings_to_save.update(general_settings)

        # MainApplicationのinitial_属性を更新（オプション、だが一貫性のため推奨）
        for key, value in settings_to_save.items():
            full_key = 'initial_' + key 
            if hasattr(self, full_key):
                setattr(self, full_key, value)
            else:
                logger.warning(f"MainApplication.save_current_settings: Unknown key for MainApplication attribute: {full_key}")
        
        # settings_managerに渡す辞書は、'initial_' プレフィックスなしのキーで構成
        # Pathオブジェクトは文字列に変換して保存
        final_settings_for_save = {k: str(v) if isinstance(v, Path) else v for k, v in settings_to_save.items()}
        self.settings_manager.save_gui_settings(final_settings_for_save)
        messagebox.showinfo("設定保存", "現在の設定が保存されました！")
        logger.info("MainApplication: 設定の保存が完了しました。")

    def _start_optimization(self):
        """
        最適化処理を新しいスレッドで開始する。
        """
        logger.info("MainApplication: 最適化処理を開始します。")
        if self.optimization_thread and self.optimization_thread.is_alive():
            messagebox.showwarning("最適化実行中", "既に最適化が実行中です。")
            logger.warning("MainApplication: 最適化が既に実行中のため、開始をスキップしました。")
            return

        # 最新の設定をMainApplicationの属性に反映 (GUIで変更された値を反映)
        self.save_current_settings()

        # DataInputTabからデータを取得
        seminars_data = self.data_input_tab.get_seminars_data()
        students_data = self.data_input_tab.get_students_data()

        if not seminars_data or not students_data:
            messagebox.showerror("データエラー", "セミナーデータまたは学生データがロードされていません。")
            logger.error("MainApplication: セミナーまたは学生データが不足しているため、最適化を開始できませんでした。")
            return

        # configはMainApplicationのinitial_属性から構築
        config = {
            # DataInputTabが管理する設定
            "num_seminars": self.initial_num_seminars,
            "num_students": self.initial_num_students,
            "min_capacity": self.initial_min_capacity,
            "max_capacity": self.initial_max_capacity,
            "preference_distribution": self.initial_preference_distribution,
            "random_seed": self.initial_random_seed,
            "q_boost_probability": self.initial_q_boost_probability,
            "min_preferences": self.initial_min_preferences,
            "max_preferences": self.initial_max_preferences, # max_preferencesとして渡す
            "seminars_file": self.initial_seminars_file_path,
            "students_file": self.initial_students_file_path,

            # SettingTabが管理する設定
            "optimization_strategy": self.initial_optimization_strategy,
            "ga_population_size": self.initial_ga_population_size,
            "ga_generations": self.initial_ga_generations,
            "ga_mutation_rate": self.initial_ga_mutation_rate,
            "ga_crossover_rate": self.initial_ga_crossover_rate,
            "ga_no_improvement_limit": self.initial_ga_no_improvement_limit,
            "ilp_time_limit": self.initial_ilp_time_limit,
            "cp_time_limit": self.initial_cp_time_limit,
            "multilevel_clusters": self.initial_multilevel_clusters,
            "greedy_ls_iterations": self.initial_greedy_ls_iterations,
            "local_search_iterations": self.initial_local_search_iterations,
            "initial_temperature": self.initial_initial_temperature,
            "cooling_rate": self.initial_cooling_rate,
            "score_weights": self.initial_score_weights,
            "early_stop_threshold": self.initial_early_stop_threshold,
            # 修正: early_stop_no_improvement_limit を config に追加
            "early_stop_no_improvement_limit": self.initial_early_stop_no_improvement_limit,
            "generate_pdf_report": self.initial_generate_pdf_report,
            "generate_csv_report": self.initial_generate_csv_report,
            "output_directory": str(self.initial_output_directory),
            "pdf_font_path": self.initial_pdf_font_path,
            "debug_mode": self.initial_debug_mode,
            "log_enabled": self.initial_log_enabled,
            "save_intermediate": self.initial_save_intermediate,
            "data_directory": str(self.project_root / "data")
        }

        self.cancel_optimization_event.clear()
        self.progress_dialog.show()

        # 最適化を別スレッドで実行
        self.optimization_thread = threading.Thread(
            target=self._run_optimization_in_thread,
            args=(seminars_data, students_data, config, self.cancel_optimization_event)
        )
        self.optimization_thread.start()
        logger.info("MainApplication: 最適化スレッドを開始しました。")

    def _run_optimization_in_thread(self, seminars_data: List[Dict[str, Any]], students_data: List[Dict[str, Any]], config: Dict[str, Any], cancel_event: threading.Event):
        """
        最適化処理をスレッド内で実行する。
        """
        try:
            logger.info("MainApplication: 最適化処理スレッドが開始されました。")
            result = self.optimizer_service.optimize(
                seminars=seminars_data,
                students=students_data,
                config=config,
                cancel_event=cancel_event
            )
            # メインスレッドでUIを更新
            self.after(0, lambda: self._handle_optimization_result(result, config))
        except Exception as e:
            logger.exception("MainApplication: 最適化処理中に予期せぬエラーが発生しました。")
            self.after(0, lambda: messagebox.showerror("最適化エラー", f"最適化中にエラーが発生しました: {e}"))
        finally:
            self.after(0, self.progress_dialog.hide)
            logger.info("MainApplication: 最適化処理スレッドが終了しました。")

    def _handle_optimization_result(self, result: Any, config: Dict[str, Any]):
        """
        最適化結果を処理し、UIを更新する。
        """
        logger.info(f"MainApplication: 最適化結果を処理します。ステータス: {result.status}")
        self.results_tab.display_results(result)
        self.notebook.select(self.results_tab.frame)

        if result.status == "CANCELLED":
            messagebox.showinfo("最適化キャンセル", "最適化がキャンセルされました。")
            logger.info("MainApplication: 最適化がユーザーによってキャンセルされました。")
        elif result.status == "OPTIMAL" or result.status == "FEASIBLE":
            messagebox.showinfo("最適化完了", "最適化が成功しました！")
            logger.info("MainApplication: 最適化が成功しました。")
        else:
            messagebox.showwarning("最適化失敗", f"最適化が完了しましたが、問題が発生しました: {result.message}")
            logger.warning(f"MainApplication: 最適化が完了しましたが、問題が発生しました: {result.message}")

        logger.debug("MainApplication: 最適化結果の処理が完了しました。")

    def _update_progress_message(self, message: str):
        """
        プログレスダイアログのメッセージを更新する。
        """
        self.after(0, self.progress_dialog.update_message, message)

    def _cancel_optimization(self):
        """
        最適化処理をキャンセルする。
        """
        logger.info("MainApplication: 最適化キャンセルリクエストを受信しました。")
        if self.optimization_thread and self.optimization_thread.is_alive():
            self.cancel_optimization_event.set()
            self.progress_dialog.update_message("最適化をキャンセルしています...")
            logger.info("MainApplication: キャンセルイベントを設定しました。")
        else:
            self.progress_dialog.hide()
            logger.info("MainApplication: 最適化スレッドが実行中でないため、キャンセル不要です。")


    def _on_closing(self):
        """
        アプリケーション終了時の処理。
        """
        logger.info("MainApplication: アプリケーションを終了します。")
        if self.optimization_thread and self.optimization_thread.is_alive():
            if messagebox.askyesno("終了確認", "最適化が実行中です。本当に終了しますか？"):
                self.cancel_optimization_event.set()
                self.optimization_thread.join(timeout=5)
                if self.optimization_thread.is_alive():
                    logger.warning("MainApplication: 最適化スレッドがタイムアウト内に終了しませんでした。")
                self.destroy()
            else:
                logger.info("MainApplication: 終了がキャンセルされました。")
        else:
            self.destroy()

# アプリケーションのエントリーポイント
if __name__ == "__main__":
    app = MainApplication(PROJECT_ROOT)
    app.mainloop()
