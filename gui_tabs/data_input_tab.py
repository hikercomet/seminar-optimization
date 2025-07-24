import tkinter as tk
from tkinter import ttk, filedialog
import os
import json
import logging
from typing import Dict, List, Any, Optional, Callable, Tuple

logger = logging.getLogger(__name__)

class DataInputTab:
    def __init__(self, notebook: ttk.Notebook, parent_app: Any): # parent_app は MainApplication インスタンス
        self.notebook = notebook
        self.parent_app = parent_app # MainApplicationインスタンスへの参照を保持
        self.frame = ttk.Frame(notebook, padding="10")
        
        # Tkinter変数 (ここで定義することで、MainApplicationの初期化時にアクセス可能になる)
        self.data_input_method_var = tk.StringVar()
        self.seminar_ids_var = tk.StringVar()
        self.num_students_var = tk.IntVar()
        self.min_capacity_var = tk.IntVar()
        self.max_capacity_var = tk.IntVar()
        self.preference_distribution_var = tk.StringVar()
        self.random_seed_var = tk.IntVar()
        self.q_boost_probability_var = tk.DoubleVar()
        self.num_preferences_to_consider_var = tk.IntVar()
        self.config_file_path_var = tk.StringVar()
        self.students_file_path_var = tk.StringVar()
        self.seminars_file_path_var = tk.StringVar()
        self.optimization_strategy_var = tk.StringVar()
        self.ga_population_size_var = tk.IntVar()
        self.ga_generations_var = tk.IntVar()
        self.ga_mutation_rate_var = tk.DoubleVar()
        self.ga_crossover_rate_var = tk.DoubleVar()
        self.ga_no_improvement_limit_var = tk.IntVar()
        self.ilp_time_limit_var = tk.IntVar()
        self.cp_time_limit_var = tk.IntVar()
        self.multilevel_clusters_var = tk.IntVar()
        self.greedy_ls_iterations_var = tk.IntVar()
        self.local_search_iterations_var = tk.IntVar()
        self.initial_temperature_var = tk.DoubleVar()
        self.cooling_rate_var = tk.DoubleVar()
        self.pref_weight_1st_var = tk.DoubleVar()
        self.pref_weight_2nd_var = tk.DoubleVar()
        self.pref_weight_3rd_var = tk.DoubleVar()
        self.pref_weight_other_var = tk.DoubleVar()
        self.early_stop_threshold_var = tk.DoubleVar()
        self.no_improvement_limit_var = tk.IntVar()
        self.generate_pdf_report_var = tk.BooleanVar()
        self.generate_csv_report_var = tk.BooleanVar()
        self.log_enabled_var = tk.BooleanVar() # MainApplicationで管理されるが、GUI要素として必要
        self.save_intermediate_var = tk.BooleanVar() # MainApplicationで管理されるが、GUI要素として必要
        self.output_directory_var = tk.StringVar() # MainApplicationで管理されるが、GUI要素として必要
        self.max_adaptive_iterations_var = tk.IntVar()
        self.strategy_time_limit_var = tk.IntVar()
        self.adaptive_history_size_var = tk.IntVar()
        self.adaptive_exploration_epsilon_var = tk.DoubleVar()
        self.adaptive_learning_rate_var = tk.DoubleVar()
        self.adaptive_score_weight_var = tk.DoubleVar()
        self.adaptive_unassigned_weight_var = tk.DoubleVar()
        self.adaptive_time_weight_var = tk.DoubleVar()
        self.max_time_for_normalization_var = tk.DoubleVar()
        self.debug_mode_var = tk.BooleanVar() # 新しく追加
        self.max_workers_var = tk.IntVar() # DataInputTab自身が管理するmax_workers_var

        self.magnification_entries: Dict[str, tk.DoubleVar] = {} # 倍率エントリーの管理

        self._create_widgets()

    def _create_widgets(self):
        """
        「データ入力と設定」タブのウィジェットを作成する。
        """
        logger.debug("DataInputTab: ウィジェットの作成を開始します。")

        # データ生成/ロード方法の選択
        data_method_frame = ttk.LabelFrame(self.frame, text="データ入力方法", padding="10")
        data_method_frame.pack(fill=tk.X, pady=10)
        ttk.Radiobutton(data_method_frame, text="自動生成", variable=self.data_input_method_var, value="auto", command=self._update_data_input_method_fields).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(data_method_frame, text="JSONファイル", variable=self.data_input_method_var, value="json", command=self._update_data_input_method_fields).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(data_method_frame, text="CSVファイル", variable=self.data_input_method_var, value="csv", command=self._update_data_input_method_fields).pack(side=tk.LEFT, padx=5)
        logger.debug("DataInputTab: データ入力方法の選択が完了しました。")

        # 自動生成設定フレーム
        self.auto_gen_frame = ttk.LabelFrame(self.frame, text="自動生成設定", padding="10")
        self.auto_gen_frame.pack(fill=tk.X, pady=5)
        self._create_auto_generate_fields(self.auto_gen_frame)
        logger.debug("DataInputTab: 自動生成設定フレームの作成が完了しました。")

        # ファイル入力設定フレーム
        self.file_input_frame = ttk.LabelFrame(self.frame, text="ファイル入力設定", padding="10")
        self.file_input_frame.pack(fill=tk.X, pady=5)
        self._create_file_input_fields(self.file_input_frame)
        logger.debug("DataInputTab: ファイル入力設定フレームの作成が完了しました。")

        # 最適化アルゴリズム設定フレーム
        optimization_settings_frame = ttk.LabelFrame(self.frame, text="最適化アルゴリズム設定", padding="10")
        optimization_settings_frame.pack(fill=tk.X, pady=5)
        self._create_optimization_algorithm_fields(optimization_settings_frame)
        logger.debug("DataInputTab: 最適化アルゴリズム設定フレームの作成が完了しました。")

        # レポートとログ設定フレーム
        report_log_frame = ttk.LabelFrame(self.frame, text="レポートとログ設定", padding="10")
        report_log_frame.pack(fill=tk.X, pady=5)
        self._create_report_log_fields(report_log_frame)
        logger.debug("DataInputTab: レポートとログ設定フレームの作成が完了しました。")

        logger.debug("DataInputTab: ウィジェットの作成が完了しました。")


    def _create_auto_generate_fields(self, parent_frame: ttk.LabelFrame):
        """自動生成設定の入力フィールドを作成する。"""
        logger.debug("DataInputTab: 自動生成固有のフィールドの作成を開始します。")
        
        top_input_frame = ttk.Frame(parent_frame)
        top_input_frame.pack(fill=tk.X, pady=5)

        ttk.Label(top_input_frame, text="セミナーID (カンマ区切り):").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.seminar_ids_entry = ttk.Entry(top_input_frame, textvariable=self.seminar_ids_var, width=40)
        self.seminar_ids_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        self.seminar_ids_entry.bind("<FocusOut>", self._update_magnification_entries)
        self.seminar_ids_entry.bind("<Return>", lambda event: self._update_magnification_entries())

        ttk.Label(top_input_frame, text="学生数:").grid(row=0, column=2, sticky=tk.W, pady=2, padx=5)
        self.num_students_entry = ttk.Entry(top_input_frame, textvariable=self.num_students_var, width=15)
        self.num_students_entry.grid(row=0, column=3, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(top_input_frame, text="最小定員:").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        self.min_size_entry = ttk.Entry(top_input_frame, textvariable=self.min_capacity_var, width=15)
        self.min_size_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(top_input_frame, text="最大定員:").grid(row=1, column=2, sticky=tk.W, pady=2, padx=5)
        self.max_size_entry = ttk.Entry(top_input_frame, textvariable=self.max_capacity_var, width=15)
        self.max_size_entry.grid(row=1, column=3, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(top_input_frame, text="優先度分布:").grid(row=2, column=0, sticky=tk.W, pady=2, padx=5)
        self.preference_distribution_menu = ttk.Combobox(top_input_frame, textvariable=self.preference_distribution_var, values=["random", "uniform", "biased"], state="readonly")
        self.preference_distribution_menu.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(top_input_frame, text="乱数シード:").grid(row=2, column=2, sticky=tk.W, pady=2, padx=5)
        self.random_seed_entry = ttk.Entry(top_input_frame, textvariable=self.random_seed_var, width=15)
        self.random_seed_entry.grid(row=2, column=3, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(top_input_frame, text="Qブースト確率:").grid(row=3, column=0, sticky=tk.W, pady=2, padx=5)
        self.q_boost_probability_entry = ttk.Entry(top_input_frame, textvariable=self.q_boost_probability_var, width=15)
        self.q_boost_probability_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(top_input_frame, text="考慮する希望数:").grid(row=3, column=2, sticky=tk.W, pady=2, padx=5)
        self.num_preferences_to_consider_entry = ttk.Entry(top_input_frame, textvariable=self.num_preferences_to_consider_var, width=15)
        self.num_preferences_to_consider_entry.grid(row=3, column=3, sticky=(tk.W, tk.E), pady=2, padx=5)
        
        # num_patterns は現在使用されていないが、将来のために残す
        # ttk.Label(top_input_frame, text="パターン数:").grid(row=4, column=0, sticky=tk.W, pady=2, padx=5)
        # self.num_patterns_entry = ttk.Entry(top_input_frame, textvariable=self.num_patterns_var, width=15)
        # self.num_patterns_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)


        top_input_frame.columnconfigure(1, weight=1)
        top_input_frame.columnconfigure(3, weight=1)

        self.magnification_frame = ttk.LabelFrame(parent_frame, text="セミナー倍率設定", padding="10")
        self.magnification_frame.pack(fill=tk.X, pady=5)
        self._update_magnification_entries() # 初期表示のために呼び出す
        logger.debug("DataInputTab: 自動生成固有のフィールドの作成が完了しました。")


    def _update_magnification_entries(self, event=None):
        """セミナーIDに基づいて倍率入力フィールドを動的に更新する。"""
        logger.debug("DataInputTab: 倍率エントリーの更新を開始します。")
        for widget in self.magnification_frame.winfo_children():
            widget.destroy()
        self.magnification_entries.clear()

        seminar_ids_str = self.seminar_ids_var.get()
        seminar_ids = [s.strip() for s in seminar_ids_str.split(',') if s.strip()]

        if not seminar_ids:
            ttk.Label(self.magnification_frame, text="セミナーIDを入力してください。").pack(pady=5)
            logger.debug("DataInputTab: セミナーIDが空のため、倍率エントリーを更新しませんでした。")
            return

        for i, sem_id in enumerate(seminar_ids):
            row = i // 4
            col = (i % 4) * 2
            
            label = ttk.Label(self.magnification_frame, text=f"{sem_id} 倍率:")
            label.grid(row=row, column=col, sticky=tk.W, padx=5, pady=2)
            
            # MainApplicationから初期倍率を取得
            initial_mag = self.parent_app.initial_magnification.get(sem_id, 1.0)
            entry_var = tk.DoubleVar(value=initial_mag)
            entry = ttk.Entry(self.magnification_frame, textvariable=entry_var, width=10)
            entry.grid(row=row, column=col+1, sticky=(tk.W, tk.E), padx=5, pady=2)
            self.magnification_entries[sem_id] = entry_var
        
        for i in range(8):
            self.magnification_frame.columnconfigure(i, weight=1)
        logger.debug("DataInputTab: 倍率エントリーの更新が完了しました。")


    def _create_file_input_fields(self, parent_frame: ttk.LabelFrame):
        """ファイル入力設定の入力フィールドを作成する。"""
        logger.debug("DataInputTab: ファイル入力固有のフィールドの作成を開始します。")
        ttk.Label(parent_frame, text="設定ファイル (config.json):").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.config_file_path_entry = ttk.Entry(parent_frame, textvariable=self.config_file_path_var, width=50)
        self.config_file_path_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        ttk.Button(parent_frame, text="参照", command=lambda: self._browse_file(self.config_file_path_var, [("JSON files", "*.json")])).grid(row=0, column=2, padx=5)

        ttk.Label(parent_frame, text="学生ファイル:").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        self.students_file_path_entry = ttk.Entry(parent_frame, textvariable=self.students_file_path_var, width=50)
        self.students_file_path_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        ttk.Button(parent_frame, text="参照", command=lambda: self._browse_file(self.students_file_path_var, [("JSON files", "*.json"), ("CSV files", "*.csv")])).grid(row=1, column=2, padx=5)

        ttk.Label(parent_frame, text="セミナーファイル:").grid(row=2, column=0, sticky=tk.W, pady=2, padx=5)
        self.seminars_file_path_entry = ttk.Entry(parent_frame, textvariable=self.seminars_file_path_var, width=50)
        self.seminars_file_path_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        ttk.Button(parent_frame, text="参照", command=lambda: self._browse_file(self.seminars_file_path_var, [("JSON files", "*.json"), ("CSV files", "*.csv")])).grid(row=2, column=2, padx=5)
        logger.debug("DataInputTab: ファイル入力固有のフィールドの作成が完了しました。")


    def _create_optimization_algorithm_fields(self, parent_frame: ttk.LabelFrame):
        """最適化アルゴリズム設定の入力フィールドを作成する。"""
        logger.debug("DataInputTab: 最適化アルゴリズム固有のフィールドの作成を開始します。")
        ttk.Label(parent_frame, text="最適化戦略:").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        strategies = ["Greedy_LS", "GA_LS", "ILP", "CP", "Multilevel", "Adaptive"]
        self.optimization_strategy_menu = ttk.Combobox(parent_frame, textvariable=self.optimization_strategy_var, values=strategies, state="readonly")
        self.optimization_strategy_menu.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)
        self.optimization_strategy_menu.bind("<<ComboboxSelected>>", self._update_algorithm_fields)

        self.algo_params_frame = ttk.Frame(parent_frame, padding="5")
        self.algo_params_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E))

        self._create_greedy_ls_fields(self.algo_params_frame)
        self._create_ga_ls_fields(self.algo_params_frame)
        self._create_ilp_fields(self.algo_params_frame)
        self._create_cp_fields(self.algo_params_frame)
        self._create_multilevel_fields(self.algo_params_frame)
        self._create_adaptive_fields(self.algo_params_frame)

        self._update_algorithm_fields() # 初期表示のために呼び出す
        logger.debug("DataInputTab: 最適化アルゴリズム固有のフィールドの作成が完了しました。")


    def _create_greedy_ls_fields(self, parent_frame: ttk.Frame):
        """Greedy_LSアルゴリズムのパラメータフィールドを作成する。"""
        self.greedy_ls_frame = ttk.LabelFrame(parent_frame, text="Greedy_LS パラメータ", padding="10")
        
        ttk.Label(self.greedy_ls_frame, text="イテレーション数:").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.greedy_ls_iterations_entry = ttk.Entry(self.greedy_ls_frame, textvariable=self.greedy_ls_iterations_var, width=15)
        self.greedy_ls_iterations_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.greedy_ls_frame, text="改善なし停止制限:").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        self.no_improvement_limit_entry = ttk.Entry(self.greedy_ls_frame, textvariable=self.no_improvement_limit_var, width=15)
        self.no_improvement_limit_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.greedy_ls_frame, text="早期停止閾値:").grid(row=2, column=0, sticky=tk.W, pady=2, padx=5)
        self.early_stop_threshold_entry = ttk.Entry(self.greedy_ls_frame, textvariable=self.early_stop_threshold_var, width=15)
        self.early_stop_threshold_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.greedy_ls_frame, text="初期温度:").grid(row=3, column=0, sticky=tk.W, pady=2, padx=5)
        self.initial_temperature_entry = ttk.Entry(self.greedy_ls_frame, textvariable=self.initial_temperature_var, width=15)
        self.initial_temperature_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.greedy_ls_frame, text="冷却率:").grid(row=4, column=0, sticky=tk.W, pady=2, padx=5)
        self.cooling_rate_entry = ttk.Entry(self.greedy_ls_frame, textvariable=self.cooling_rate_var, width=15)
        self.cooling_rate_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.greedy_ls_frame, text="最大ワーカー数:").grid(row=5, column=0, sticky=tk.W, pady=2, padx=5)
        # 修正: max_workers_var は DataInputTab 自身が持つべき変数
        self.max_workers_entry = ttk.Entry(self.greedy_ls_frame, textvariable=self.max_workers_var, width=15) 
        self.max_workers_entry.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.greedy_ls_frame, text="局所探索イテレーション:").grid(row=6, column=0, sticky=tk.W, pady=2, padx=5)
        self.local_search_iterations_entry = ttk.Entry(self.greedy_ls_frame, textvariable=self.local_search_iterations_var, width=15)
        self.local_search_iterations_entry.grid(row=6, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)


    def _create_ga_ls_fields(self, parent_frame: ttk.Frame):
        """GA_LSアルゴリズムのパラメータフィールドを作成する。"""
        self.ga_ls_frame = ttk.LabelFrame(parent_frame, text="GA_LS パラメータ", padding="10")
        
        ttk.Label(self.ga_ls_frame, text="個体群サイズ:").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.ga_population_size_entry = ttk.Entry(self.ga_ls_frame, textvariable=self.ga_population_size_var, width=15)
        self.ga_population_size_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.ga_ls_frame, text="世代数:").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        self.ga_generations_entry = ttk.Entry(self.ga_ls_frame, textvariable=self.ga_generations_var, width=15)
        self.ga_generations_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.ga_ls_frame, text="突然変異率:").grid(row=2, column=0, sticky=tk.W, pady=2, padx=5)
        self.ga_mutation_rate_entry = ttk.Entry(self.ga_ls_frame, textvariable=self.ga_mutation_rate_var, width=15)
        self.ga_mutation_rate_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.ga_ls_frame, text="交叉率:").grid(row=3, column=0, sticky=tk.W, pady=2, padx=5)
        self.ga_crossover_rate_entry = ttk.Entry(self.ga_ls_frame, textvariable=self.ga_crossover_rate_var, width=15)
        self.ga_crossover_rate_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.ga_ls_frame, text="改善なし停止制限:").grid(row=4, column=0, sticky=tk.W, pady=2, padx=5)
        self.ga_no_improvement_limit_entry = ttk.Entry(self.ga_ls_frame, textvariable=self.ga_no_improvement_limit_var, width=15)
        self.ga_no_improvement_limit_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)


    def _create_ilp_fields(self, parent_frame: ttk.Frame):
        """ILPアルゴリズムのパラメータフィールドを作成する。"""
        self.ilp_frame = ttk.LabelFrame(parent_frame, text="ILP パラメータ", padding="10")
        
        ttk.Label(self.ilp_frame, text="時間制限 (秒):").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.ilp_time_limit_entry = ttk.Entry(self.ilp_frame, textvariable=self.ilp_time_limit_var, width=15)
        self.ilp_time_limit_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)


    def _create_cp_fields(self, parent_frame: ttk.Frame):
        """CP-SATアルゴリズムのパラメータフィールドを作成する。"""
        self.cp_frame = ttk.LabelFrame(parent_frame, text="CP-SAT パラメータ", padding="10")
        
        ttk.Label(self.cp_frame, text="時間制限 (秒):").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.cp_time_limit_entry = ttk.Entry(self.cp_frame, textvariable=self.cp_time_limit_var, width=15)
        self.cp_time_limit_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)


    def _create_multilevel_fields(self, parent_frame: ttk.Frame):
        """Multilevelアルゴリズムのパラメータフィールドを作成する。"""
        self.multilevel_frame = ttk.LabelFrame(parent_frame, text="Multilevel パラメータ", padding="10")
        
        ttk.Label(self.multilevel_frame, text="クラスタ数:").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.multilevel_clusters_entry = ttk.Entry(self.multilevel_frame, textvariable=self.multilevel_clusters_var, width=15)
        self.multilevel_clusters_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.multilevel_frame, text="局所探索イテレーション:").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        # local_search_iterations_var は DataInputTab 自身が持つべき変数
        self.multilevel_local_search_iterations_var = tk.IntVar() # Multilevel固有の変数として定義
        self.multilevel_local_search_iterations_entry = ttk.Entry(self.multilevel_frame, textvariable=self.local_search_iterations_var, width=15)
        self.multilevel_local_search_iterations_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)


    def _create_adaptive_fields(self, parent_frame: ttk.Frame):
        """適応型最適化アルゴリズムのパラメータフィールドを作成する。"""
        self.adaptive_frame = ttk.LabelFrame(parent_frame, text="Adaptive パラメータ", padding="10")

        ttk.Label(self.adaptive_frame, text="最大適応イテレーション:").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        self.max_adaptive_iterations_entry = ttk.Entry(self.adaptive_frame, textvariable=self.max_adaptive_iterations_var, width=15)
        self.max_adaptive_iterations_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.adaptive_frame, text="戦略ごとの時間制限 (秒):").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        self.strategy_time_limit_entry = ttk.Entry(self.adaptive_frame, textvariable=self.strategy_time_limit_var, width=15)
        self.strategy_time_limit_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.adaptive_frame, text="履歴サイズ:").grid(row=2, column=0, sticky=tk.W, pady=2, padx=5)
        self.adaptive_history_size_entry = ttk.Entry(self.adaptive_frame, textvariable=self.adaptive_history_size_var, width=15)
        self.adaptive_history_size_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.adaptive_frame, text="探索率 (epsilon):").grid(row=3, column=0, sticky=tk.W, pady=2, padx=5)
        self.adaptive_exploration_epsilon_entry = ttk.Entry(self.adaptive_frame, textvariable=self.adaptive_exploration_epsilon_var, width=15)
        self.adaptive_exploration_epsilon_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.adaptive_frame, text="学習率:").grid(row=4, column=0, sticky=tk.W, pady=2, padx=5)
        self.adaptive_learning_rate_entry = ttk.Entry(self.adaptive_frame, textvariable=self.adaptive_learning_rate_var, width=15)
        self.adaptive_learning_rate_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.adaptive_frame, text="スコア重み:").grid(row=5, column=0, sticky=tk.W, pady=2, padx=5)
        self.adaptive_score_weight_entry = ttk.Entry(self.adaptive_frame, textvariable=self.adaptive_score_weight_var, width=15)
        self.adaptive_score_weight_entry.grid(row=5, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.adaptive_frame, text="未割り当て重み:").grid(row=6, column=0, sticky=tk.W, pady=2, padx=5)
        self.adaptive_unassigned_weight_entry = ttk.Entry(self.adaptive_frame, textvariable=self.adaptive_unassigned_weight_var, width=15)
        self.adaptive_unassigned_weight_entry.grid(row=6, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.adaptive_frame, text="時間重み:").grid(row=7, column=0, sticky=tk.W, pady=2, padx=5)
        self.adaptive_time_weight_entry = ttk.Entry(self.adaptive_frame, textvariable=self.adaptive_time_weight_var, width=15)
        self.adaptive_time_weight_entry.grid(row=7, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(self.adaptive_frame, text="正規化最大時間 (秒):").grid(row=8, column=0, sticky=tk.W, pady=2, padx=5)
        self.max_time_for_normalization_entry = ttk.Entry(self.adaptive_frame, textvariable=self.max_time_for_normalization_var, width=15)
        self.max_time_for_normalization_entry.grid(row=8, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)


    def _update_algorithm_fields(self, event=None):
        """選択された最適化戦略に応じてパラメータフィールドを表示/非表示にする。"""
        logger.debug("DataInputTab: アルゴリズムフィールドの更新を開始します。")
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
        logger.debug(f"DataInputTab: 選択された戦略 '{selected_strategy}' に基づいてフィールドを更新しました。")


    def _create_report_log_fields(self, parent_frame: ttk.LabelFrame):
        """レポートとログ設定の入力フィールドを作成する。"""
        logger.debug("DataInputTab: レポートとログ固有のフィールドの作成を開始します。")
        # スコア重み
        score_weights_frame = ttk.LabelFrame(parent_frame, text="スコア重み", padding="10")
        score_weights_frame.pack(fill=tk.X, pady=5)

        ttk.Label(score_weights_frame, text="第1希望:").grid(row=0, column=0, sticky=tk.W, pady=2, padx=5)
        ttk.Entry(score_weights_frame, textvariable=self.pref_weight_1st_var, width=10).grid(row=0, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(score_weights_frame, text="第2希望:").grid(row=1, column=0, sticky=tk.W, pady=2, padx=5)
        ttk.Entry(score_weights_frame, textvariable=self.pref_weight_2nd_var, width=10).grid(row=1, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(score_weights_frame, text="第3希望:").grid(row=2, column=0, sticky=tk.W, pady=2, padx=5)
        ttk.Entry(score_weights_frame, textvariable=self.pref_weight_3rd_var, width=10).grid(row=2, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)

        ttk.Label(score_weights_frame, text="その他希望:").grid(row=3, column=0, sticky=tk.W, pady=2, padx=5)
        ttk.Entry(score_weights_frame, textvariable=self.pref_weight_other_var, width=10).grid(row=3, column=1, sticky=(tk.W, tk.E), pady=2, padx=5)


        # レポート生成オプション
        self.generate_pdf_report_checkbox = ttk.Checkbutton(parent_frame, text="PDFレポートを生成", variable=self.generate_pdf_report_var)
        self.generate_pdf_report_checkbox.pack(anchor=tk.W, pady=2, padx=5)

        self.generate_csv_report_checkbox = ttk.Checkbutton(parent_frame, text="CSVレポートを生成", variable=self.generate_csv_report_var)
        self.generate_csv_report_checkbox.pack(anchor=tk.W, pady=2, padx=5)

        # ログ有効化オプション (MainApplicationのメソッドを呼び出す)
        self.log_enabled_checkbox = ttk.Checkbutton(parent_frame, text="ログを有効にする", variable=self.log_enabled_var, command=self.parent_app._toggle_logging)
        self.log_enabled_checkbox.pack(anchor=tk.W, pady=2, padx=5)

        # 中間結果保存オプション
        self.save_intermediate_checkbox = ttk.Checkbutton(parent_frame, text="中間結果を保存", variable=self.save_intermediate_var)
        self.save_intermediate_checkbox.pack(anchor=tk.W, pady=2, padx=5)

        # 出力ディレクトリ
        ttk.Label(parent_frame, text="出力ディレクトリ:").pack(anchor=tk.W, pady=2, padx=5)
        self.output_directory_entry = ttk.Entry(parent_frame, textvariable=self.output_directory_var, width=50)
        self.output_directory_entry.pack(fill=tk.X, pady=2, padx=5)
        ttk.Button(parent_frame, text="参照", command=lambda: self._browse_directory(self.output_directory_var)).pack(pady=5)
        
        # デバッグモード (新しく追加)
        self.debug_mode_checkbox = ttk.Checkbutton(parent_frame, text="デバッグモードを有効にする", variable=self.debug_mode_var)
        self.debug_mode_checkbox.pack(anchor=tk.W, pady=2, padx=5)

        logger.debug("DataInputTab: レポートとログ固有のフィールドの作成が完了しました。")


    def _update_data_input_method_fields(self):
        """データ入力方法の選択に応じて関連フィールドの表示を切り替える。"""
        logger.debug("DataInputTab: データ入力方法のフィールドを更新します。")
        selected_method = self.data_input_method_var.get()

        if selected_method == "auto":
            self.auto_gen_frame.pack(fill=tk.X, pady=5)
            self.file_input_frame.pack_forget()
        else: # "json" or "csv"
            self.auto_gen_frame.pack_forget()
            self.file_input_frame.pack(fill=tk.X, pady=5)
        logger.debug(f"DataInputTab: データ入力方法を '{selected_method}' に切り替えました。")

    def _browse_file(self, tk_string_var: tk.StringVar, filetypes: List[Tuple[str, str]]):
        """ファイル参照ダイアログを開き、選択されたパスをStringVarに設定する。"""
        logger.debug("DataInputTab: ファイル参照ダイアログを開きます。")
        filepath = filedialog.askopenfilename(filetypes=filetypes)
        if filepath:
            tk_string_var.set(filepath)
            self.parent_app._update_status_bar(f"ファイル選択: {os.path.basename(filepath)}", "info")
            logger.info(f"ファイルが選択されました: {filepath}")

    def _browse_directory(self, tk_string_var: tk.StringVar):
        """ディレクトリ参照ダイアログを開き、選択されたパスをStringVarに設定する。"""
        logger.debug("DataInputTab: ディレクトリ参照ダイアログを開きます。")
        directorypath = filedialog.askdirectory()
        if directorypath:
            tk_string_var.set(directorypath)
            self.parent_app._update_status_bar(f"ディレクトリ選択: {os.path.basename(directorypath)}", "info")
            logger.info(f"ディレクトリが選択されました: {directorypath}")

    def initialize_fields(self, **initial_values):
        """
        MainApplicationから渡された初期値でUIフィールドを設定する。
        """
        logger.debug("DataInputTab: UIフィールドの初期化を開始します。")
        self.seminar_ids_var.set(initial_values.get('initial_seminars_str', ''))
        self.num_students_var.set(initial_values.get('initial_num_students', 0))
        self.min_capacity_var.set(initial_values.get('initial_min_size', 0))
        self.max_capacity_var.set(initial_values.get('initial_max_size', 0))
        self.q_boost_probability_var.set(initial_values.get('initial_q_boost_probability', 0.0))
        self.num_preferences_to_consider_var.set(initial_values.get('initial_num_preferences_to_consider', 0))
        # self.num_patterns_var.set(initial_values.get('initial_num_patterns', 0)) # 現在使用されていない
        self.max_workers_var.set(initial_values.get('initial_max_workers', 0)) # DataInputTabのmax_workers_varを初期化
        self.local_search_iterations_var.set(initial_values.get('initial_local_search_iterations', 0))
        self.initial_temperature_var.set(initial_values.get('initial_initial_temperature', 0.0))
        self.cooling_rate_var.set(initial_values.get('initial_cooling_rate', 0.0))
        self.early_stop_threshold_var.set(initial_values.get('initial_early_stop_threshold', 0.0))
        self.no_improvement_limit_var.set(initial_values.get('initial_no_improvement_limit', 0))
        self.data_input_method_var.set(initial_values.get('initial_data_input_method', 'auto'))
        self.config_file_path_var.set(initial_values.get('initial_config_file_path', ''))
        self.students_file_path_var.set(initial_values.get('initial_student_file_path', ''))
        self.ga_population_size_var.set(initial_values.get('initial_ga_population_size', 0))
        self.ga_crossover_rate_var.set(initial_values.get('initial_ga_crossover_rate', 0.0))
        self.ga_mutation_rate_var.set(initial_values.get('initial_ga_mutation_rate', 0.0))
        self.ga_generations_var.set(initial_values.get('initial_ga_generations', 0))
        self.ga_no_improvement_limit_var.set(initial_values.get('initial_ga_no_improvement_limit', 0))
        self.optimization_strategy_var.set(initial_values.get('initial_optimization_strategy', 'Greedy_LS'))
        self.seminars_file_path_var.set(initial_values.get('initial_seminars_file_path', ''))
        self.min_preferences_var.set(initial_values.get('initial_min_preferences', 0))
        self.max_preferences_var.set(initial_values.get('initial_max_preferences', 0))
        self.preference_distribution_var.set(initial_values.get('initial_preference_distribution', 'random'))
        self.random_seed_var.set(initial_values.get('initial_random_seed', 0))
        self.ilp_time_limit_var.set(initial_values.get('initial_ilp_time_limit', 0))
        self.cp_time_limit_var.set(initial_values.get('initial_cp_time_limit', 0))
        self.multilevel_clusters_var.set(initial_values.get('initial_multilevel_clusters', 0))
        self.generate_pdf_report_var.set(initial_values.get('initial_generate_pdf_report', False))
        self.generate_csv_report_var.set(initial_values.get('initial_generate_csv_report', False))
        self.max_adaptive_iterations_var.set(initial_values.get('initial_max_adaptive_iterations', 0))
        self.strategy_time_limit_var.set(initial_values.get('initial_strategy_time_limit', 0))
        self.adaptive_history_size_var.set(initial_values.get('initial_adaptive_history_size', 0))
        self.adaptive_exploration_epsilon_var.set(initial_values.get('initial_adaptive_exploration_epsilon', 0.0))
        self.adaptive_learning_rate_var.set(initial_values.get('initial_adaptive_learning_rate', 0.0))
        self.adaptive_score_weight_var.set(initial_values.get('initial_adaptive_score_weight', 0.0))
        self.adaptive_unassigned_weight_var.set(initial_values.get('initial_adaptive_unassigned_weight', 0.0))
        self.adaptive_time_weight_var.set(initial_values.get('initial_adaptive_time_weight', 0.0))
        self.max_time_for_normalization_var.set(initial_values.get('initial_max_time_for_normalization', 0.0))
        self.greedy_ls_iterations_var.set(initial_values.get('initial_greedy_ls_iterations', 0))
        self.output_directory_var.set(initial_values.get('initial_output_directory', ''))
        self.debug_mode_var.set(initial_values.get('initial_debug_mode', False))

        # スコア重み
        pref_weights = initial_values.get('initial_preference_weights', {})
        self.pref_weight_1st_var.set(pref_weights.get("1st_choice", 5.0))
        self.pref_weight_2nd_var.set(pref_weights.get("2nd_choice", 2.0))
        self.pref_weight_3rd_var.set(pref_weights.get("3rd_choice", 1.0))
        self.pref_weight_other_var.set(pref_weights.get("other_preference", 0.5))

        # 動的な更新が必要なフィールドを呼び出す
        self._update_magnification_entries()
        self._update_algorithm_fields()
        self._update_data_input_method_fields()
        
        # MainApplicationのログと中間結果保存のチェックボックスの状態を同期
        self.log_enabled_var.set(initial_values.get('initial_log_enabled', True))
        self.save_intermediate_var.set(initial_values.get('initial_save_intermediate', False))
        self.output_directory_var.set(initial_values.get('initial_output_directory', 'results'))

        logger.debug("DataInputTab: UIフィールドの初期化が完了しました。")


    def get_current_config(self) -> Dict[str, Any]:
        """
        現在のUI入力から最適化設定を構築して返す。
        """
        logger.debug("DataInputTab: 現在のUI設定からconfigを構築します。")
        config = {}

        # データ生成/ファイル入力の設定
        config["data_input_method"] = self.data_input_method_var.get()
        
        if config["data_input_method"] == "auto":
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

            current_magnification = {}
            seminar_ids_str = self.seminar_ids_var.get()
            seminar_ids = [s.strip() for s in seminar_ids_str.split(',') if s.strip()]
            for sem_id in seminar_ids:
                if sem_id in self.magnification_entries:
                    try:
                        current_magnification[sem_id] = self.magnification_entries[sem_id].get()
                    except tk.TclError:
                        logger.warning(f"DataInputTab: セミナー '{sem_id}' の倍率が無効な値です。デフォルト値を使用します。")
                        current_magnification[sem_id] = 1.0
            config["seminar_specific_magnifications"] = current_magnification
            config["seminars"] = [{"id": s_id, "capacity": 0, "magnification": current_magnification.get(s_id, 1.0)} for s_id in seminar_ids]
            config["students"] = []

        else: # "json" or "csv"
            config["seminars_file"] = self.seminars_file_path_var.get()
            config["students_file"] = self.students_file_path_var.get()
            config["config_file_path"] = self.config_file_path_var.get()

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
        config["early_stop_no_improvement_limit"] = self.no_improvement_limit_var.get()
        config["initial_temperature"] = self.initial_temperature_var.get()
        config["cooling_rate"] = self.cooling_rate_var.get()
        config["max_workers"] = self.max_workers_var.get() # DataInputTabのmax_workers_varから取得

        # スコア重み
        config["score_weights"] = {
            "1st_choice": self.pref_weight_1st_var.get(),
            "2nd_choice": self.pref_weight_2nd_var.get(),
            "3rd_choice": self.pref_weight_3rd_var.get(),
            "other_preference": self.pref_weight_other_var.get()
        }

        # レポートとログ設定 (一部はMainApplicationで管理)
        config["generate_pdf_report"] = self.generate_pdf_report_var.get()
        config["generate_csv_report"] = self.generate_csv_report_var.get()
        config["log_enabled"] = self.log_enabled_var.get()
        config["output_directory"] = self.output_directory_var.get()
        config["save_intermediate"] = self.save_intermediate_var.get()
        config["debug_mode"] = self.debug_mode_var.get()

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

        logger.debug(f"DataInputTab: 構築されたconfig: {config}")
        return config

    def get_current_settings_for_save(self) -> Dict[str, Any]:
        """
        SettingsManagerに保存するための現在のGUI設定を辞書として返す。
        """
        settings = {}
        settings['seminars'] = self.seminar_ids_var.get()
        settings['num_students'] = self.num_students_var.get()
        
        current_magnification_values = {
            sem_id: self.magnification_entries[sem_id].get()
            for sem_id in [s.strip() for s in self.seminar_ids_var.get().split(',') if s.strip()]
            if sem_id in self.magnification_entries
        }
        settings['magnification'] = current_magnification_values

        settings['min_size'] = self.min_capacity_var.get()
        settings['max_size'] = self.max_capacity_var.get()
        settings['q_boost_probability'] = self.q_boost_probability_var.get()
        settings['num_preferences_to_consider'] = self.num_preferences_to_consider_var.get()
        # settings['num_patterns'] = self.num_patterns_var.get() # 現在使用されていない
        settings['max_workers'] = self.max_workers_var.get() # DataInputTabのmax_workers_varから取得
        settings['local_search_iterations'] = self.local_search_iterations_var.get()
        settings['initial_temperature'] = self.initial_temperature_var.get()
        settings['cooling_rate'] = self.cooling_rate_var.get()
        
        settings['preference_weights_1st'] = self.pref_weight_1st_var.get()
        settings['preference_weights_2nd'] = self.pref_weight_2nd_var.get()
        settings['preference_weights_3rd'] = self.pref_weight_3rd_var.get()
        settings['preference_weights_other'] = self.pref_weight_other_var.get()

        settings['early_stop_threshold'] = self.early_stop_threshold_var.get()
        settings['no_improvement_limit'] = self.no_improvement_limit_var.get()
        settings['data_source'] = self.data_input_method_var.get() # data_source は data_input_method と同じ
        settings['log_enabled'] = self.log_enabled_var.get()
        settings['save_intermediate'] = self.save_intermediate_var.get()
        settings['config_file_path'] = self.config_file_path_var.get()
        settings['student_file_path'] = self.students_file_path_var.get()
        settings['ga_population_size'] = self.ga_population_size_var.get()
        settings['ga_crossover_rate'] = self.ga_crossover_rate_var.get()
        settings['ga_mutation_rate'] = self.ga_mutation_rate_var.get()
        settings['ga_generations'] = self.ga_generations_var.get() 
        settings['ga_no_improvement_limit'] = self.ga_no_improvement_limit_var.get() 
        settings['optimization_strategy'] = self.optimization_strategy_var.get()
        settings['seminars_file_path'] = self.seminars_file_path_var.get()
        settings['students_file_path'] = self.students_file_path_var.get()
        settings['data_input_method'] = self.data_input_method_var.get()
        settings['num_seminars'] = self.num_seminars_var.get()
        settings['min_preferences'] = self.min_preferences_var.get()
        settings['max_preferences'] = self.max_preferences_var.get()
        settings['preference_distribution'] = self.preference_distribution_var.get()
        settings['random_seed'] = self.random_seed_var.get()
        settings['ilp_time_limit'] = self.ilp_time_limit_var.get()
        settings['cp_time_limit'] = self.cp_time_limit_var.get()
        settings['multilevel_clusters'] = self.multilevel_clusters_var.get()
        settings['generate_pdf_report'] = self.generate_pdf_report_var.get()
        settings['generate_csv_report'] = self.generate_csv_report_var.get()
        settings['max_adaptive_iterations'] = self.max_adaptive_iterations_var.get()
        settings['strategy_time_limit'] = self.strategy_time_limit_var.get()
        settings['adaptive_history_size'] = self.adaptive_history_size_var.get()
        settings['adaptive_exploration_epsilon'] = self.adaptive_exploration_epsilon_var.get()
        settings['adaptive_learning_rate'] = self.adaptive_learning_rate_var.get()
        settings['adaptive_score_weight'] = self.adaptive_score_weight_var.get()
        settings['adaptive_unassigned_weight'] = self.adaptive_unassigned_weight_var.get()
        settings['adaptive_time_weight'] = self.adaptive_time_weight_var.get()
        settings['max_time_for_normalization'] = self.max_time_for_normalization_var.get()
        settings['greedy_ls_iterations'] = self.greedy_ls_iterations_var.get()
        settings['output_directory'] = self.output_directory_var.get()
        settings['debug_mode'] = self.debug_mode_var.get()

        return settings
