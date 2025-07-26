import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional
import logging


def setup_logging(log_level: str, log_file: Optional[str] = None):
    """ロギング設定のセットアップ"""
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    
    # 既存のハンドラーをクリア
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # フォーマッターを設定
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (OSError, IOError) as e:
            print(f"ログファイルの作成に失敗しました: {e}")
    
    # コンソールハンドラーも追加
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


logger = logging.getLogger(__name__)


class SettingTab:
    """
    アプリケーションの各種設定を管理するタブ。
    ファイルパス、数値パラメータ、ブール値などを設定できます。
    """
    
    # クラス定数として定義
    OPTIMIZATION_STRATEGIES = ["Greedy_LS", "GA_LS", "ILP", "CP", "Multilevel", "Adaptive", "TSL"]
    
    OBJECTIVE_PRESETS = {
        "希望優先": {
            "adaptive_score_weight": 10.0,
            "adaptive_unassigned_weight": 2.0,
            "adaptive_time_weight": 0.1
        },
        "未割当回避": {
            "adaptive_score_weight": 1.0,
            "adaptive_unassigned_weight": 100.0,
            "adaptive_time_weight": 1.0
        },
        "スピード優先": {
            "adaptive_score_weight": 0.5,
            "adaptive_unassigned_weight": 5.0,
            "adaptive_time_weight": 50.0
        },
        "バランス型": {
            "adaptive_score_weight": 5.0,
            "adaptive_unassigned_weight": 10.0,
            "adaptive_time_weight": 5.0
        },
    }

    def __init__(self, notebook: ttk.Notebook, main_app: Any):
        """
        SettingTabのコンストラクタ。
        
        Args:
            notebook (ttk.Notebook): このタブが追加される親のノートブックウィジェット。
            main_app (Any): MainApplicationのインスタンスへの参照。
        """
        self.frame = ttk.Frame(notebook, padding="10")
        self.main_app = main_app
        logger.debug("SettingTab: 初期化を開始します。")

        # 設定変数の初期化
        self._initialize_variables()
        
        # UIの作成
        self._create_widgets()
        
        # 初期値の読み込み
        self._load_initial_settings_to_ui()

        logger.debug("SettingTab: 初期化が完了しました。")

    def _initialize_variables(self):
        """設定変数を初期化する"""
        # ファイルパス関連
        self.output_directory_var = tk.StringVar(
            value=str(getattr(self.main_app, 'initial_output_directory', Path.cwd()))
        )
        self.pdf_font_path_var = tk.StringVar(
            value=getattr(self.main_app, 'initial_pdf_font_path', '')
        )

        # 最適化アルゴリズム関連
        self.optimization_strategy_var = tk.StringVar(
            value=getattr(self.main_app, 'initial_optimization_strategy', 'Greedy_LS')
        )
        
        # GA設定
        self.ga_population_size_var = tk.IntVar(
            value=getattr(self.main_app, 'initial_ga_population_size', 100)
        )
        self.ga_generations_var = tk.IntVar(
            value=getattr(self.main_app, 'initial_ga_generations', 200)
        )
        self.ga_mutation_rate_var = tk.DoubleVar(
            value=getattr(self.main_app, 'initial_ga_mutation_rate', 0.1)
        )
        self.ga_crossover_rate_var = tk.DoubleVar(
            value=getattr(self.main_app, 'initial_ga_crossover_rate', 0.8)
        )
        self.ga_no_improvement_limit_var = tk.IntVar(
            value=getattr(self.main_app, 'initial_ga_no_improvement_limit', 50)
        )

        # ILP/CP設定
        self.ilp_time_limit_var = tk.IntVar(
            value=getattr(self.main_app, 'initial_ilp_time_limit', 300)
        )
        self.cp_time_limit_var = tk.IntVar(
            value=getattr(self.main_app, 'initial_cp_time_limit', 300)
        )

        # Multilevel設定
        self.multilevel_clusters_var = tk.IntVar(
            value=getattr(self.main_app, 'initial_multilevel_clusters', 5)
        )

        # Greedy LS設定
        self.greedy_ls_iterations_var = tk.IntVar(
            value=getattr(self.main_app, 'initial_greedy_ls_iterations', 1000)
        )
        self.local_search_iterations_var = tk.IntVar(
            value=getattr(self.main_app, 'initial_local_search_iterations', 100)
        )
        self.initial_temperature_var = tk.DoubleVar(
            value=getattr(self.main_app, 'initial_initial_temperature', 100.0)
        )
        self.cooling_rate_var = tk.DoubleVar(
            value=getattr(self.main_app, 'initial_cooling_rate', 0.95)
        )

        # Adaptive設定
        self.adaptive_history_size_var = tk.IntVar(
            value=getattr(self.main_app, 'initial_adaptive_history_size', 10)
        )
        self.adaptive_exploration_epsilon_var = tk.DoubleVar(
            value=getattr(self.main_app, 'initial_adaptive_exploration_epsilon', 0.1)
        )
        self.adaptive_learning_rate_var = tk.DoubleVar(
            value=getattr(self.main_app, 'initial_adaptive_learning_rate', 0.1)
        )       
        self.adaptive_score_weight_var = tk.DoubleVar(value=5.0)
        self.adaptive_unassigned_weight_var = tk.DoubleVar(value=10.0)
        self.adaptive_time_weight_var = tk.DoubleVar(value=5.0)

        # スコア重み関連
        initial_score_weights = getattr(self.main_app, 'initial_score_weights', {})
        self.score_weight_1st_choice_var = tk.DoubleVar(
            value=initial_score_weights.get("1st_choice", 5.0)
        )
        self.score_weight_2nd_choice_var = tk.DoubleVar(
            value=initial_score_weights.get("2nd_choice", 2.0)
        )
        self.score_weight_3rd_choice_var = tk.DoubleVar(
            value=initial_score_weights.get("3rd_choice", 1.0)
        )
        self.score_weight_other_var = tk.DoubleVar(
            value=initial_score_weights.get("other", 0.5)
        )

        # その他詳細設定
        self.max_workers_var = tk.IntVar(
            value=getattr(self.main_app, 'initial_max_workers', 4)
        )
        self.early_stop_threshold_var = tk.DoubleVar(
            value=getattr(self.main_app, 'initial_early_stop_threshold', 0.01)
        )
        self.early_stop_no_improvement_limit_var = tk.IntVar(
            value=getattr(self.main_app, 'initial_early_stop_no_improvement_limit', 50)
        )
        self.debug_mode_var = tk.BooleanVar(
            value=getattr(self.main_app, 'initial_debug_mode', False)
        )
        self.log_enabled_var = tk.BooleanVar(
            value=getattr(self.main_app, 'initial_log_enabled', True)
        )
        self.save_intermediate_var = tk.BooleanVar(
            value=getattr(self.main_app, 'initial_save_intermediate', False)
        )
        self.theme_var = tk.StringVar(
            value=getattr(self.main_app, 'initial_theme', 'default')
        )

        # レポート生成関連
        self.generate_pdf_report_var = tk.BooleanVar(
            value=getattr(self.main_app, 'initial_generate_pdf_report', True)
        )
        self.generate_csv_report_var = tk.BooleanVar(
            value=getattr(self.main_app, 'initial_generate_csv_report', True)
        )

        # プリセット選択用
        self.preset_var = tk.StringVar(value="バランス型")

    def _create_widgets(self):
        """UIウィジェットを作成する"""
        logger.debug("SettingTab: ウィジェットの作成を開始します。")

        # スクロール可能なフレームの設定
        self._setup_scrollable_frame()

        # 各設定セクションの作成
        self._create_output_settings()
        self._create_optimization_settings()
        self._create_score_weights_settings()
        self._create_misc_settings()

        logger.debug("SettingTab: ウィジェットの作成が完了しました。")

    def _setup_scrollable_frame(self):
        """スクロール可能なフレームをセットアップする"""
        self.canvas = tk.Canvas(self.frame)
        self.scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # マウスホイールイベントをバインド
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel)
        self.canvas.bind_all("<Button-5>", self._on_mousewheel)

    def _create_output_settings(self):
        """出力設定セクションを作成する"""
        output_frame = ttk.LabelFrame(self.scrollable_frame, text="出力設定", padding="10")
        output_frame.pack(fill=tk.X, pady=5)

        # 出力ディレクトリ
        self._create_labeled_entry_with_browse(
            output_frame, "出力ディレクトリ:", self.output_directory_var, 0,
            browse_type="directory"
        )

        # PDFフォントパス
        self._create_labeled_entry_with_browse(
            output_frame, "PDFフォントパス:", self.pdf_font_path_var, 1,
            browse_type="file", filetypes=[("TTF files", "*.ttf")]
        )

        # レポート生成設定
        ttk.Checkbutton(
            output_frame, text="PDFレポート生成", 
            variable=self.generate_pdf_report_var
        ).grid(row=2, column=0, sticky=tk.W, pady=2)
        
        ttk.Checkbutton(
            output_frame, text="CSVレポート生成", 
            variable=self.generate_csv_report_var
        ).grid(row=3, column=0, sticky=tk.W, pady=2)

    def _create_optimization_settings(self):
        """最適化アルゴリズム設定セクションを作成する"""
        opt_algo_frame = ttk.LabelFrame(
            self.scrollable_frame, text="最適化アルゴリズム設定", padding="10"
        )
        opt_algo_frame.pack(fill=tk.X, pady=5)

        # 最適化戦略選択
        ttk.Label(opt_algo_frame, text="最適化戦略:").grid(row=0, column=0, sticky=tk.W, pady=2)
        strategy_combo = ttk.Combobox(
            opt_algo_frame, textvariable=self.optimization_strategy_var,
            values=self.OPTIMIZATION_STRATEGIES, state="readonly"
        )
        strategy_combo.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        # 各アルゴリズム固有の設定
        self._create_ga_settings(opt_algo_frame)
        self._create_ilp_cp_settings(opt_algo_frame)
        self._create_multilevel_settings(opt_algo_frame)
        self._create_greedy_ls_settings(opt_algo_frame)
        self._create_adaptive_settings(opt_algo_frame)

    def _create_ga_settings(self, parent):
        """遺伝的アルゴリズム設定を作成する"""
        ga_frame = ttk.LabelFrame(parent, text="遺伝的アルゴリズム (GA) 設定", padding="10")
        ga_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5)

        settings = [
            ("個体数:", self.ga_population_size_var),
            ("世代数:", self.ga_generations_var),
            ("突然変異率:", self.ga_mutation_rate_var),
            ("交叉率:", self.ga_crossover_rate_var),
            ("改善なし制限:", self.ga_no_improvement_limit_var)
        ]

        for i, (label, var) in enumerate(settings):
            self._create_labeled_entry(ga_frame, label, var, i)

    def _create_ilp_cp_settings(self, parent):
        """ILP/CP設定を作成する"""
        ilp_cp_frame = ttk.LabelFrame(parent, text="ILP/CP-SAT 設定", padding="10")
        ilp_cp_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5)

        self._create_labeled_entry(ilp_cp_frame, "ILPタイムリミット (秒):", self.ilp_time_limit_var, 0)
        self._create_labeled_entry(ilp_cp_frame, "CP-SATタイムリミット (秒):", self.cp_time_limit_var, 1)

    def _create_multilevel_settings(self, parent):
        """多段階最適化設定を作成する"""
        multilevel_frame = ttk.LabelFrame(parent, text="多段階最適化設定", padding="10")
        multilevel_frame.grid(row=3, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5)

        self._create_labeled_entry(multilevel_frame, "クラスタ数:", self.multilevel_clusters_var, 0)

    def _create_greedy_ls_settings(self, parent):
        """Greedy LS設定を作成する"""
        greedy_ls_frame = ttk.LabelFrame(parent, text="Greedy LS 設定", padding="10")
        greedy_ls_frame.grid(row=4, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5)

        settings = [
            ("イテレーション数:", self.greedy_ls_iterations_var),
            ("局所探索イテレーション数:", self.local_search_iterations_var),
            ("初期温度:", self.initial_temperature_var),
            ("冷却率:", self.cooling_rate_var)
        ]

        for i, (label, var) in enumerate(settings):
            self._create_labeled_entry(greedy_ls_frame, label, var, i)

    def _create_adaptive_settings(self, parent):
        """適応型最適化設定を作成する"""
        adaptive_frame = ttk.LabelFrame(parent, text="適応型最適化設定", padding="10")
        adaptive_frame.grid(row=5, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5)

        # プリセット選択
        ttk.Label(adaptive_frame, text="プリセット:").grid(row=0, column=0, sticky=tk.W, pady=2)
        preset_combo = ttk.Combobox(
            adaptive_frame, textvariable=self.preset_var, 
            values=list(self.OBJECTIVE_PRESETS.keys()), state="readonly"
        )
        preset_combo.grid(row=0, column=1, padx=5, pady=2, sticky="ew")
        preset_combo.bind("<<ComboboxSelected>>", self.apply_preset)

        # 個別設定
        settings = [
            ("履歴サイズ:", self.adaptive_history_size_var),
            ("探索率 (epsilon):", self.adaptive_exploration_epsilon_var),
            ("スコア重み:", self.adaptive_score_weight_var),
            ("未割当重み:", self.adaptive_unassigned_weight_var),
            ("時間重み:", self.adaptive_time_weight_var)
        ]

        for i, (label, var) in enumerate(settings, 1):
            self._create_labeled_entry(adaptive_frame, label, var, i)

    def _create_score_weights_settings(self):
        """スコア重み設定セクションを作成する"""
        score_weights_frame = ttk.LabelFrame(
            self.scrollable_frame, text="希望順位スコア重み", padding="10"
        )
        score_weights_frame.pack(fill=tk.X, pady=5)

        settings = [
            ("1位希望:", self.score_weight_1st_choice_var),
            ("2位希望:", self.score_weight_2nd_choice_var),
            ("3位希望:", self.score_weight_3rd_choice_var),
            ("その他:", self.score_weight_other_var)
        ]

        for i, (label, var) in enumerate(settings):
            self._create_labeled_entry(score_weights_frame, label, var, i)

    def _create_misc_settings(self):
        """その他詳細設定セクションを作成する"""
        misc_settings_frame = ttk.LabelFrame(
            self.scrollable_frame, text="その他詳細設定", padding="10"
        )
        misc_settings_frame.pack(fill=tk.X, pady=5)

        # 数値設定
        numeric_settings = [
            ("コア数:", self.max_workers_var),
            ("早期停止閾値:", self.early_stop_threshold_var),
            ("改善なし停止制限:", self.early_stop_no_improvement_limit_var)
        ]

        for i, (label, var) in enumerate(numeric_settings):
            self._create_labeled_entry(misc_settings_frame, label, var, i)

        # チェックボックス設定
        checkbox_settings = [
            ("デバッグモード", self.debug_mode_var),
            ("ログ有効化", self.log_enabled_var),
            ("中間結果保存", self.save_intermediate_var)
        ]

        for i, (label, var) in enumerate(checkbox_settings, 3):
            ttk.Checkbutton(misc_settings_frame, text=label, variable=var).grid(
                row=i, column=0, sticky=tk.W, pady=2
            )

        # テーマ設定
        ttk.Label(misc_settings_frame, text="GUIテーマ:").grid(
            row=6, column=0, sticky=tk.W, pady=2
        )
        self.theme_combobox = ttk.Combobox(
            misc_settings_frame, textvariable=self.theme_var,
            values=self._get_available_themes(), state="readonly"
        )
        self.theme_combobox.grid(row=6, column=1, sticky=tk.W, padx=5, pady=2)
        self.theme_combobox.bind("<<ComboboxSelected>>", self._apply_theme)

    def _create_labeled_entry(self, parent, label_text: str, variable, row: int, width: int = 10):
        """ラベル付きエントリーウィジェットを作成する"""
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky=tk.W, pady=2)
        entry = ttk.Entry(parent, textvariable=variable, width=width)
        entry.grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)
        return entry

    def _create_labeled_entry_with_browse(
        self, parent, label_text: str, variable, row: int, 
        browse_type: str = "file", filetypes: Optional[List[Tuple[str, str]]] = None
    ):
        """ブラウズボタン付きのラベル付きエントリーウィジェットを作成する"""
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(parent, textvariable=variable, width=50).grid(
            row=row, column=1, padx=5, pady=2
        )
        
        if browse_type == "directory":
            command = lambda: self._browse_directory(variable)
        else:
            command = lambda: self._browse_file(variable, filetypes or [])
            
        ttk.Button(parent, text="参照", command=command).grid(
            row=row, column=2, padx=5, pady=2
        )

    def apply_preset(self, event=None):
        """選択されたプリセットに基づいて適応型最適化の重みを適用する"""
        try:
            preset_name = self.preset_var.get()
            if preset_name in self.OBJECTIVE_PRESETS:
                preset_values = self.OBJECTIVE_PRESETS[preset_name]
                self.adaptive_score_weight_var.set(preset_values["adaptive_score_weight"])
                self.adaptive_unassigned_weight_var.set(preset_values["adaptive_unassigned_weight"])
                self.adaptive_time_weight_var.set(preset_values["adaptive_time_weight"])
                logger.info(f"プリセット '{preset_name}' を適用しました。")
                self._update_main_app_settings_from_ui()
        except Exception as e:
            logger.error(f"プリセット適用中にエラーが発生しました: {e}")
            messagebox.showerror("エラー", f"プリセットの適用に失敗しました: {e}")

    def _on_mousewheel(self, event):
        """マウスホイールイベントを処理してCanvasをスクロールさせる"""
        try:
            if event.delta:  # Windows/macOS
                self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
            elif event.num == 4:  # Linux (スクロールアップ)
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:  # Linux (スクロールダウン)
                self.canvas.yview_scroll(1, "units")
        except Exception as e:
            logger.debug(f"マウスホイール処理中にエラー: {e}")

    def _load_initial_settings_to_ui(self):
        """MainApplicationから初期値をロードしてUIに反映する"""
        logger.debug("UIに初期設定をロードします。")
        try:
            # 各変数は既に __init__ で初期化されているので、追加の処理は不要
            logger.debug("初期設定のロードが完了しました。")
        except Exception as e:
            logger.error(f"初期設定のロード中にエラーが発生しました: {e}")

    def load_settings_from_config(self, config_data: Dict[str, Any]):
        """config.jsonからロードされた設定をUIに反映する"""
        logger.debug("config.jsonから設定をロードし、UIに反映します。")
        
        try:
            # 設定値の安全な更新
            safe_updates = [
                ("optimization_strategy", self.optimization_strategy_var, str),
                ("ga_population_size", self.ga_population_size_var, int),
                ("ga_generations", self.ga_generations_var, int),
                ("ga_mutation_rate", self.ga_mutation_rate_var, float),
                ("ga_crossover_rate", self.ga_crossover_rate_var, float),
                ("ga_no_improvement_limit", self.ga_no_improvement_limit_var, int),
                ("ilp_time_limit", self.ilp_time_limit_var, int),
                ("cp_time_limit", self.cp_time_limit_var, int),
                ("multilevel_clusters", self.multilevel_clusters_var, int),
                ("greedy_ls_iterations", self.greedy_ls_iterations_var, int),
                ("local_search_iterations", self.local_search_iterations_var, int),
                ("initial_temperature", self.initial_temperature_var, float),
                ("cooling_rate", self.cooling_rate_var, float),
                ("adaptive_history_size", self.adaptive_history_size_var, int),
                ("adaptive_exploration_epsilon", self.adaptive_exploration_epsilon_var, float),
                ("adaptive_score_weight", self.adaptive_score_weight_var, float),
                ("adaptive_unassigned_weight", self.adaptive_unassigned_weight_var, float),
                ("adaptive_time_weight", self.adaptive_time_weight_var, float),
                ("early_stop_threshold", self.early_stop_threshold_var, float),
                ("early_stop_no_improvement_limit", self.early_stop_no_improvement_limit_var, int),
                ("max_workers", self.max_workers_var, int),
                ("debug_mode", self.debug_mode_var, bool),
                ("log_enabled", self.log_enabled_var, bool),
                ("save_intermediate", self.save_intermediate_var, bool),
                ("generate_pdf_report", self.generate_pdf_report_var, bool),
                ("generate_csv_report", self.generate_csv_report_var, bool),
                ("output_directory", self.output_directory_var, str),
                ("pdf_font_path", self.pdf_font_path_var, str),
                ("theme", self.theme_var, str),
            ]

            for config_key, tk_var, expected_type in safe_updates:
                if config_key in config_data:
                    try:
                        value = config_data[config_key]
                        if expected_type == bool:
                            tk_var.set(bool(value))
                        else:
                            tk_var.set(expected_type(value))
                    except (ValueError, TypeError) as e:
                        logger.warning(f"設定値 {config_key} の変換に失敗: {e}")

            # スコア重みの特別処理
            if "score_weights" in config_data:
                score_weights = config_data["score_weights"]
                if isinstance(score_weights, dict):
                    self.score_weight_1st_choice_var.set(
                        float(score_weights.get("1st_choice", self.score_weight_1st_choice_var.get()))
                    )
                    self.score_weight_2nd_choice_var.set(
                        float(score_weights.get("2nd_choice", self.score_weight_2nd_choice_var.get()))
                    )
                    self.score_weight_3rd_choice_var.set(
                        float(score_weights.get("3rd_choice", self.score_weight_3rd_choice_var.get()))
                    )
                    self.score_weight_other_var.set(
                        float(score_weights.get("other", self.score_weight_other_var.get()))
                    )

            self._update_main_app_settings_from_ui()
            logger.info("設定ファイルからの読み込みが完了しました。")
            
        except Exception as e:
            logger.error(f"設定ファイルの読み込み中にエラーが発生しました: {e}")
            messagebox.showerror("エラー", f"設定ファイルの読み込みに失敗しました: {e}")

    def get_current_settings_for_main_app(self) -> Dict[str, Any]:
        """MainApplicationに保存するための現在の設定値を取得する"""
        logger.debug("現在の設定値を取得します。")
        
        try:
            score_weights = {
                "1st_choice": self.score_weight_1st_choice_var.get(),
                "2nd_choice": self.score_weight_2nd_choice_var.get(),
                "3rd_choice": self.score_weight_3rd_choice_var.get(),
                "other": self.score_weight_other_var.get(),
            }

            return {
                "output_directory": Path(self.output_directory_var.get()),
                "pdf_font_path": self.pdf_font_path_var.get(),
                "optimization_strategy": self.optimization_strategy_var.get(),
                "ga_population_size": self.ga_population_size_var.get(),
                "ga_generations": self.ga_generations_var.get(),
                "ga_mutation_rate": self.ga_mutation_rate_var.get(),
                "ga_crossover_rate": self.ga_crossover_rate_var.get(),
                "ga_no_improvement_limit": self.ga_no_improvement_limit_var.get(),
                "ilp_time_limit": self.ilp_time_limit_var.get(),
                "cp_time_limit": self.cp_time_limit_var.get(),
                "multilevel_clusters": self.multilevel_clusters_var.get(),
                "greedy_ls_iterations": self.greedy_ls_iterations_var.get(),
                "local_search_iterations": self.local_search_iterations_var.get(),
                "initial_temperature": self.initial_temperature_var.get(),
                "cooling_rate": self.cooling_rate_var.get(),
                "adaptive_history_size": self.adaptive_history_size_var.get(),
                "adaptive_exploration_epsilon": self.adaptive_exploration_epsilon_var.get(),
                "adaptive_score_weight": self.adaptive_score_weight_var.get(),
                "adaptive_unassigned_weight": self.adaptive_unassigned_weight_var.get(),
                "adaptive_time_weight": self.adaptive_time_weight_var.get(),
                "max_workers": self.max_workers_var.get(),
                "score_weights": score_weights,
                "early_stop_threshold": self.early_stop_threshold_var.get(),
                "early_stop_no_improvement_limit": self.early_stop_no_improvement_limit_var.get(),
                "debug_mode": self.debug_mode_var.get(),
                "log_enabled": self.log_enabled_var.get(),
                "save_intermediate": self.save_intermediate_var.get(),
                "generate_pdf_report": self.generate_pdf_report_var.get(),
                "generate_csv_report": self.generate_csv_report_var.get(),
                "theme": self.theme_var.get(),
            }
        except Exception as e:
            logger.error(f"設定値の取得中にエラーが発生しました: {e}")
            return {}

    def _update_main_app_settings_from_ui(self):
        """UIの現在の設定値をMainApplicationの属性に反映する"""
        try:
            current_settings = self.get_current_settings_for_main_app()
            if not current_settings:
                logger.warning("設定値の取得に失敗したため、MainApplicationの更新をスキップします。")
                return

            for key, value in current_settings.items():
                full_key = 'initial_' + key
                try:
                    if key == "score_weights":
                        # 辞書の場合は特別処理
                        if hasattr(self.main_app, full_key):
                            getattr(self.main_app, full_key).update(value)
                        else:
                            setattr(self.main_app, full_key, value)
                    else:
                        setattr(self.main_app, full_key, value)
                except AttributeError:
                    logger.debug(f"MainApplication属性 {full_key} が存在しません。新規作成します。")
                    setattr(self.main_app, full_key, value)
                except Exception as e:
                    logger.warning(f"MainApplication属性 {full_key} の更新に失敗: {e}")

            # テーマ変更を即座に適用
            self._apply_theme_to_app()

            # ログ設定も即座に適用
            self._apply_logging_settings()

            logger.debug("MainApplicationの設定を更新しました。")
            
        except Exception as e:
            logger.error(f"MainApplicationの設定更新中にエラーが発生しました: {e}")

    def _apply_theme_to_app(self):
        """選択されたテーマをアプリケーションに適用する"""
        try:
            if hasattr(self.main_app, 'style'):
                theme_name = self.theme_var.get()
                available_themes = list(self.main_app.style.theme_names())
                
                if theme_name in available_themes:
                    self.main_app.style.theme_use(theme_name)
                    logger.info(f"GUIテーマを '{theme_name}' に変更しました。")
                else:
                    logger.warning(f"テーマ '{theme_name}' は利用できません。利用可能: {available_themes}")
        except Exception as e:
            logger.error(f"テーマの適用に失敗しました: {e}")

    def _apply_logging_settings(self):
        """現在のログ設定を適用する"""
        try:
            if self.log_enabled_var.get():
                project_root = getattr(self.main_app, 'project_root', Path.cwd())
                logs_dir = project_root / "logs"
                logs_dir.mkdir(parents=True, exist_ok=True)
                log_file_path = str(logs_dir / "seminar_optimization.log")
            else:
                log_file_path = None

            log_level = "DEBUG" if self.debug_mode_var.get() else "INFO"
            setup_logging(log_level, log_file_path)
            logger.info("ロギング設定を更新しました。")
            
        except Exception as e:
            logger.error(f"ロギング設定の適用に失敗しました: {e}")

    def _browse_directory(self, tk_var: tk.StringVar):
        """ディレクトリ参照ダイアログを開く"""
        try:
            initial_dir = tk_var.get() if tk_var.get() and Path(tk_var.get()).exists() else os.getcwd()
            dir_path = filedialog.askdirectory(
                initialdir=initial_dir, 
                title="ディレクトリを選択"
            )
            if dir_path:
                tk_var.set(dir_path)
                logger.info(f"出力ディレクトリを設定しました: {dir_path}")
                self._update_main_app_settings_from_ui()
        except Exception as e:
            logger.error(f"ディレクトリ選択中にエラーが発生しました: {e}")
            messagebox.showerror("エラー", f"ディレクトリの選択に失敗しました: {e}")

    def _browse_file(self, tk_var: tk.StringVar, filetypes: List[Tuple[str, str]]):
        """ファイル参照ダイアログを開く"""
        try:
            current_path = tk_var.get()
            if current_path and Path(current_path).exists():
                initial_dir = str(Path(current_path).parent)
            else:
                initial_dir = os.getcwd()
            
            file_path = filedialog.askopenfilename(
                initialdir=initial_dir,
                title="ファイルを選択",
                filetypes=filetypes
            )
            if file_path:
                tk_var.set(file_path)
                logger.info(f"ファイルパスを設定しました: {file_path}")
                self._update_main_app_settings_from_ui()
        except Exception as e:
            logger.error(f"ファイル選択中にエラーが発生しました: {e}")
            messagebox.showerror("エラー", f"ファイルの選択に失敗しました: {e}")

    def _get_available_themes(self) -> List[str]:
        """利用可能なttkスタイルテーマのリストを返す"""
        try:
            if hasattr(self.main_app, 'style'):
                return list(self.main_app.style.theme_names())
            else:
                # デフォルトのテーマリスト
                return ['default', 'clam', 'alt', 'classic']
        except Exception as e:
            logger.error(f"テーマリストの取得に失敗しました: {e}")
            return ['default']

    def _apply_theme(self, event=None):
        """コンボボックスでのテーマ選択時に呼ばれる"""
        try:
            self._apply_theme_to_app()
            self._update_main_app_settings_from_ui()
        except Exception as e:
            logger.error(f"テーマ適用中にエラーが発生しました: {e}")
            messagebox.showerror("テーマエラー", f"テーマの適用に失敗しました: {e}")

    def validate_settings(self) -> Tuple[bool, List[str]]:
        """現在の設定値を検証する"""
        errors = []
        
        try:
            # 数値範囲の検証
            if self.ga_population_size_var.get() <= 0:
                errors.append("GA個体数は正の値である必要があります")
            
            if self.ga_generations_var.get() <= 0:
                errors.append("GA世代数は正の値である必要があります")
            
            if not (0.0 <= self.ga_mutation_rate_var.get() <= 1.0):
                errors.append("GA突然変異率は0.0から1.0の間である必要があります")
            
            if not (0.0 <= self.ga_crossover_rate_var.get() <= 1.0):
                errors.append("GA交叉率は0.0から1.0の間である必要があります")
            
            if self.ilp_time_limit_var.get() <= 0:
                errors.append("ILPタイムリミットは正の値である必要があります")
            
            if self.cp_time_limit_var.get() <= 0:
                errors.append("CP-SATタイムリミットは正の値である必要があります")
            
            if self.max_workers_var.get() <= 0:
                errors.append("コア数は正の値である必要があります")
            
            # パスの検証
            output_dir = self.output_directory_var.get()
            if output_dir:
                output_path = Path(output_dir)
                if not output_path.parent.exists():
                    errors.append(f"出力ディレクトリの親ディレクトリが存在しません: {output_path.parent}")
            
            font_path = self.pdf_font_path_var.get()
            if font_path and not Path(font_path).exists():
                errors.append(f"PDFフォントファイルが存在しません: {font_path}")

        except Exception as e:
            errors.append(f"設定値の検証中にエラーが発生しました: {e}")
            logger.error(f"設定検証中にエラー: {e}")

        return len(errors) == 0, errors

    def save_settings_to_dict(self) -> Dict[str, Any]:
        """現在の設定を辞書形式で保存用に取得する"""
        try:
            settings = self.get_current_settings_for_main_app()
            # Path オブジェクトを文字列に変換
            if 'output_directory' in settings:
                settings['output_directory'] = str(settings['output_directory'])
            return settings
        except Exception as e:
            logger.error(f"設定の保存用辞書作成中にエラー: {e}")
            return {}

    def reset_to_defaults(self):
        """設定をデフォルト値にリセットする"""
        try:
            # 確認ダイアログ
            if not messagebox.askyesno("設定リセット", "すべての設定をデフォルト値にリセットしますか？"):
                return

            # デフォルト値のマッピング
            defaults = {
                self.optimization_strategy_var: "Greedy_LS",
                self.ga_population_size_var: 100,
                self.ga_generations_var: 200,
                self.ga_mutation_rate_var: 0.1,
                self.ga_crossover_rate_var: 0.8,
                self.ga_no_improvement_limit_var: 50,
                self.ilp_time_limit_var: 300,
                self.cp_time_limit_var: 300,
                self.multilevel_clusters_var: 5,
                self.greedy_ls_iterations_var: 1000,
                self.local_search_iterations_var: 100,
                self.initial_temperature_var: 100.0,
                self.cooling_rate_var: 0.95,
                self.adaptive_history_size_var: 10,
                self.adaptive_exploration_epsilon_var: 0.1,
                self.adaptive_score_weight_var: 5.0,
                self.adaptive_unassigned_weight_var: 10.0,
                self.adaptive_time_weight_var: 5.0,
                self.score_weight_1st_choice_var: 5.0,
                self.score_weight_2nd_choice_var: 2.0,
                self.score_weight_3rd_choice_var: 1.0,
                self.score_weight_other_var: 0.5,
                self.max_workers_var: 4,
                self.early_stop_threshold_var: 0.01,
                self.early_stop_no_improvement_limit_var: 50,
                self.debug_mode_var: False,
                self.log_enabled_var: True,
                self.save_intermediate_var: False,
                self.generate_pdf_report_var: True,
                self.generate_csv_report_var: True,
                self.theme_var: "default",
                self.preset_var: "バランス型"
            }

            # デフォルト値を設定
            for var, default_value in defaults.items():
                var.set(default_value)

            # パス設定はクリア
            self.output_directory_var.set(str(Path.cwd()))
            self.pdf_font_path_var.set("")

            self._update_main_app_settings_from_ui()
            logger.info("設定をデフォルト値にリセットしました。")
            messagebox.showinfo("完了", "設定をデフォルト値にリセットしました。")

        except Exception as e:
            logger.error(f"設定リセット中にエラー: {e}")
            messagebox.showerror("エラー", f"設定のリセットに失敗しました: {e}")


# 使用例とテスト用のクラス
class MockMainApp:
    """テスト用のMainApplicationモック"""
    def __init__(self):
        self.initial_output_directory = Path.cwd() / "output"
        self.initial_pdf_font_path = ""
        self.initial_optimization_strategy = "Greedy_LS"
        self.initial_ga_population_size = 100
        self.initial_ga_generations = 200
        self.initial_ga_mutation_rate = 0.1
        self.initial_ga_crossover_rate = 0.8
        self.initial_ga_no_improvement_limit = 50
        self.initial_ilp_time_limit = 300
        self.initial_cp_time_limit = 300
        self.initial_multilevel_clusters = 5
        self.initial_greedy_ls_iterations = 1000
        self.initial_local_search_iterations = 100
        self.initial_initial_temperature = 100.0
        self.initial_cooling_rate = 0.95
        self.initial_adaptive_history_size = 10
        self.initial_adaptive_exploration_epsilon = 0.1
        self.initial_score_weights = {
            "1st_choice": 5.0,
            "2nd_choice": 2.0,
            "3rd_choice": 1.0,
            "other": 0.5
        }
        self.initial_max_workers = 4
        self.initial_early_stop_threshold = 0.01
        self.initial_early_stop_no_improvement_limit = 50
        self.initial_debug_mode = False
        self.initial_log_enabled = True
        self.initial_save_intermediate = False
        self.initial_generate_pdf_report = True
        self.initial_generate_csv_report = True
        self.initial_theme = "default"
        self.project_root = Path.cwd()
        
        # ttkスタイルのモック
        try:
            import tkinter.ttk as ttk
            self.style = ttk.Style()
        except:
            self.style = None


if __name__ == "__main__":
    # テスト用のアプリケーション
    import tkinter as tk
    from tkinter import ttk
    
    root = tk.Tk()
    root.title("SettingTab テスト")
    root.geometry("800x600")
    
    # ノートブックを作成
    notebook = ttk.Notebook(root)
    notebook.pack(fill="both", expand=True, padx=10, pady=10)
    
    # モックのMainApplicationを作成
    mock_app = MockMainApp()
    
    # SettingTabを作成
    setting_tab = SettingTab(notebook, mock_app)
    notebook.add(setting_tab.frame, text="設定")
    
    # テスト用のボタンを追加
    button_frame = ttk.Frame(root)
    button_frame.pack(fill="x", padx=10, pady=5)
    
    def test_validate():
        is_valid, errors = setting_tab.validate_settings()
        if is_valid:
            messagebox.showinfo("検証結果", "すべての設定が有効です。")
        else:
            messagebox.showerror("検証エラー", "\n".join(errors))
    
    def test_save():
        settings = setting_tab.save_settings_to_dict()
        print("現在の設定:", settings)
        messagebox.showinfo("保存テスト", "設定をコンソールに出力しました。")
    
    ttk.Button(button_frame, text="設定検証", command=test_validate).pack(side="left", padx=5)
    ttk.Button(button_frame, text="設定保存テスト", command=test_save).pack(side="left", padx=5)
    ttk.Button(button_frame, text="デフォルトリセット", command=setting_tab.reset_to_defaults).pack(side="left", padx=5)
    
    root.mainloop()