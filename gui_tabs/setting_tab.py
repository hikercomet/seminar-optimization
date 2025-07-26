import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, Any, List
import logging
from typing import Callable, Tuple
import os
import json # config.jsonから読み込むために追加
from pathlib import Path # Pathオブジェクトを扱うために追加

# ロギングは logger_config.py で一元的に設定されるため、ここではロガーの取得のみ
from seminar_optimization.logger_config import logger, setup_logging

class SettingTab:
    """
    アプリケーションの各種設定を管理するタブ。
    ファイルパス、数値パラメータ、ブール値などを設定できます。
    """
    def __init__(self, notebook: ttk.Notebook, main_app: Any):
        """
        SettingTabのコンストラクタ。
        Args:
            notebook (ttk.Notebook): このタブが追加される親のノートブックウィジェット。
            main_app (Any): MainApplicationのインスタンスへの参照。
        """
        self.frame = ttk.Frame(notebook, padding="10")
        self.main_app = main_app # MainApplicationのインスタンスへの参照を保持
        logger.debug("SettingTab: 初期化を開始します。")

        # --- 設定変数の定義 ---
        # ファイルパス関連 (SettingTabで管理する出力関連パスのみ)
        self.output_directory_var = tk.StringVar(value=str(main_app.initial_output_directory)) # Pathを文字列に変換
        self.pdf_font_path_var = tk.StringVar(value=main_app.initial_pdf_font_path)

        # 最適化アルゴリズム関連
        self.optimization_strategy_var = tk.StringVar(value=main_app.initial_optimization_strategy)
        self.ga_population_size_var = tk.IntVar(value=main_app.initial_ga_population_size)
        self.ga_generations_var = tk.IntVar(value=main_app.initial_ga_generations)
        self.ga_mutation_rate_var = tk.DoubleVar(value=main_app.initial_ga_mutation_rate)
        self.ga_crossover_rate_var = tk.DoubleVar(value=main_app.initial_ga_crossover_rate)
        self.ga_no_improvement_limit_var = tk.IntVar(value=main_app.initial_ga_no_improvement_limit)
        self.ilp_time_limit_var = tk.IntVar(value=main_app.initial_ilp_time_limit)
        self.cp_time_limit_var = tk.IntVar(value=main_app.initial_cp_time_limit)
        self.multilevel_clusters_var = tk.IntVar(value=main_app.initial_multilevel_clusters)
        self.greedy_ls_iterations_var = tk.IntVar(value=main_app.initial_greedy_ls_iterations)
        self.local_search_iterations_var = tk.IntVar(value=main_app.initial_local_search_iterations)
        self.initial_temperature_var = tk.DoubleVar(value=main_app.initial_initial_temperature)
        self.cooling_rate_var = tk.DoubleVar(value=main_app.initial_cooling_rate)

        # スコア重み関連
        self.score_weight_1st_choice_var = tk.DoubleVar(value=main_app.initial_score_weights.get("1st_choice", 5.0))
        self.score_weight_2nd_choice_var = tk.DoubleVar(value=main_app.initial_score_weights.get("2nd_choice", 2.0))
        self.score_weight_3rd_choice_var = tk.DoubleVar(value=main_app.initial_score_weights.get("3rd_choice", 1.0))
        self.score_weight_other_var = tk.DoubleVar(value=main_app.initial_score_weights.get("other", 0.5))

        # その他詳細設定
        self.early_stop_threshold_var = tk.DoubleVar(value=main_app.initial_early_stop_threshold)
        # 修正: no_improvement_limit_var を early_stop_no_improvement_limit_var に変更
        self.early_stop_no_improvement_limit_var = tk.IntVar(value=main_app.initial_early_stop_no_improvement_limit)
        self.debug_mode_var = tk.BooleanVar(value=main_app.initial_debug_mode)
        self.log_enabled_var = tk.BooleanVar(value=main_app.initial_log_enabled)
        self.save_intermediate_var = tk.BooleanVar(value=main_app.initial_save_intermediate)
        self.theme_var = tk.StringVar(value=main_app.initial_theme) # テーマ設定もここに移動

        # レポート生成関連
        self.generate_pdf_report_var = tk.BooleanVar(value=main_app.initial_generate_pdf_report)
        self.generate_csv_report_var = tk.BooleanVar(value=main_app.initial_generate_csv_report)

        self._create_widgets()
        self._load_initial_settings_to_ui() # UIに初期値を反映

        logger.debug("SettingTab: 初期化が完了しました。")

    def _create_widgets(self):
        """
        「設定」タブのウィジェットを作成する。
        スクロール機能を追加するため、CanvasとScrollbarを使用する。
        """
        logger.debug("SettingTab: ウィジェットの作成を開始します。")

        # Canvasを作成し、スクロールバーを関連付ける
        self.canvas = tk.Canvas(self.frame)
        self.scrollbar = ttk.Scrollbar(self.frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas) # このフレーム内にすべての設定ウィジェットを配置する

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(
                scrollregion=self.canvas.bbox("all")
            )
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        # マウスホイールイベントをバインド
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind_all("<Button-4>", self._on_mousewheel) # Linuxの場合
        self.canvas.bind_all("<Button-5>", self._on_mousewheel) # Linuxの場合

        # ここから、既存のウィジェットを self.scrollable_frame に配置していく
        # 出力設定フレーム
        output_frame = ttk.LabelFrame(self.scrollable_frame, text="出力設定", padding="10")
        output_frame.pack(fill=tk.X, pady=5)

        ttk.Label(output_frame, text="出力ディレクトリ:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(output_frame, textvariable=self.output_directory_var, width=50).grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(output_frame, text="参照", command=lambda: self._browse_directory(self.output_directory_var)).grid(row=0, column=2, padx=5, pady=2)

        ttk.Label(output_frame, text="PDFフォントパス:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(output_frame, textvariable=self.pdf_font_path_var, width=50).grid(row=1, column=1, padx=5, pady=2)
        ttk.Button(output_frame, text="参照", command=lambda: self._browse_file(self.pdf_font_path_var, [("TTF files", "*.ttf")])).grid(row=1, column=2, padx=5, pady=2)

        ttk.Checkbutton(output_frame, text="PDFレポート生成", variable=self.generate_pdf_report_var).grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Checkbutton(output_frame, text="CSVレポート生成", variable=self.generate_csv_report_var).grid(row=3, column=0, sticky=tk.W, pady=2)


        # 最適化アルゴリズム設定フレーム
        opt_algo_frame = ttk.LabelFrame(self.scrollable_frame, text="最適化アルゴリズム設定", padding="10")
        opt_algo_frame.pack(fill=tk.X, pady=5)

        ttk.Label(opt_algo_frame, text="最適化戦略:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Combobox(opt_algo_frame, textvariable=self.optimization_strategy_var,
                     values=["Greedy_LS", "GA_LS", "ILP", "CP", "Multilevel", "Adaptive", "TSL"]).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        
        # GA設定
        ga_frame = ttk.LabelFrame(opt_algo_frame, text="遺伝的アルゴリズム (GA) 設定", padding="10")
        ga_frame.grid(row=1, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5)
        ttk.Label(ga_frame, text="個体数:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(ga_frame, textvariable=self.ga_population_size_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(ga_frame, text="世代数:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(ga_frame, textvariable=self.ga_generations_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(ga_frame, text="突然変異率:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(ga_frame, textvariable=self.ga_mutation_rate_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(ga_frame, text="交叉率:").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(ga_frame, textvariable=self.ga_crossover_rate_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(ga_frame, text="GA改善なし制限:").grid(row=4, column=0, sticky=tk.W, pady=2) # ラベルを修正
        ttk.Entry(ga_frame, textvariable=self.ga_no_improvement_limit_var, width=10).grid(row=4, column=1, sticky=tk.W, padx=5, pady=2)

        # ILP/CP設定
        ilp_cp_frame = ttk.LabelFrame(opt_algo_frame, text="ILP/CP-SAT 設定", padding="10")
        ilp_cp_frame.grid(row=2, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5)
        ttk.Label(ilp_cp_frame, text="ILPタイムリミット (秒):").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(ilp_cp_frame, textvariable=self.ilp_time_limit_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(ilp_cp_frame, text="CP-SATタイムリミット (秒):").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(ilp_cp_frame, textvariable=self.cp_time_limit_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        # Multilevel設定
        multilevel_frame = ttk.LabelFrame(opt_algo_frame, text="多段階最適化設定", padding="10")
        multilevel_frame.grid(row=3, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5)
        ttk.Label(multilevel_frame, text="クラスタ数:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(multilevel_frame, textvariable=self.multilevel_clusters_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        # Greedy LS 設定
        greedy_ls_frame = ttk.LabelFrame(opt_algo_frame, text="Greedy LS 設定", padding="10")
        greedy_ls_frame.grid(row=4, column=0, columnspan=2, sticky=tk.W+tk.E, pady=5)
        ttk.Label(greedy_ls_frame, text="イテレーション数:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(greedy_ls_frame, textvariable=self.greedy_ls_iterations_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(greedy_ls_frame, text="局所探索イテレーション数:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(greedy_ls_frame, textvariable=self.local_search_iterations_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(greedy_ls_frame, text="初期温度:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(greedy_ls_frame, textvariable=self.initial_temperature_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(greedy_ls_frame, text="冷却率:").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(greedy_ls_frame, textvariable=self.cooling_rate_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)


        # スコア重み設定フレーム
        score_weights_frame = ttk.LabelFrame(self.scrollable_frame, text="希望順位スコア重み", padding="10")
        score_weights_frame.pack(fill=tk.X, pady=5)

        ttk.Label(score_weights_frame, text="1位希望:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(score_weights_frame, textvariable=self.score_weight_1st_choice_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(score_weights_frame, text="2位希望:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(score_weights_frame, textvariable=self.score_weight_2nd_choice_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(score_weights_frame, text="3位希望:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(score_weights_frame, textvariable=self.score_weight_3rd_choice_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(score_weights_frame, text="その他:").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(score_weights_frame, textvariable=self.score_weight_other_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)


        # その他詳細設定フレーム
        misc_settings_frame = ttk.LabelFrame(self.scrollable_frame, text="その他詳細設定", padding="10")
        misc_settings_frame.pack(fill=tk.X, pady=5)

        ttk.Label(misc_settings_frame, text="早期停止閾値:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(misc_settings_frame, textvariable=self.early_stop_threshold_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Label(misc_settings_frame, text="改善なし停止制限:").grid(row=1, column=0, sticky=tk.W, pady=2) # ラベルを修正
        # 修正: early_stop_no_improvement_limit_var を使用
        ttk.Entry(misc_settings_frame, textvariable=self.early_stop_no_improvement_limit_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)
        ttk.Checkbutton(misc_settings_frame, text="デバッグモード", variable=self.debug_mode_var).grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Checkbutton(misc_settings_frame, text="ログ有効化", variable=self.log_enabled_var).grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Checkbutton(misc_settings_frame, text="中間結果保存", variable=self.save_intermediate_var).grid(row=4, column=0, sticky=tk.W, pady=2)
        
        ttk.Label(misc_settings_frame, text="GUIテーマ:").grid(row=5, column=0, sticky=tk.W, pady=2)
        self.theme_combobox = ttk.Combobox(misc_settings_frame, textvariable=self.theme_var,
                                           values=self.style_themes())
        self.theme_combobox.grid(row=5, column=1, sticky=tk.W, padx=5, pady=2)
        self.theme_combobox.bind("<<ComboboxSelected>>", self._apply_theme)

        logger.debug("SettingTab: ウィジェットの作成が完了しました。")

    def _on_mousewheel(self, event):
        """
        マウスホイールイベントを処理し、Canvasをスクロールさせる。
        """
        if event.delta: # Windows/macOS
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        elif event.num == 4: # Linux (スクロールアップ)
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5: # Linux (スクロールダウン)
            self.canvas.yview_scroll(1, "units")

    def _load_initial_settings_to_ui(self):
        """
        MainApplicationから初期値をロードしてUIに反映する。
        """
        logger.debug("SettingTab: UIに初期設定をロードします。")
        self.output_directory_var.set(str(self.main_app.initial_output_directory))
        self.pdf_font_path_var.set(self.main_app.initial_pdf_font_path)
        self.optimization_strategy_var.set(self.main_app.initial_optimization_strategy)
        self.ga_population_size_var.set(self.main_app.initial_ga_population_size)
        self.ga_generations_var.set(self.main_app.initial_ga_generations)
        self.ga_mutation_rate_var.set(self.main_app.initial_ga_mutation_rate)
        self.ga_crossover_rate_var.set(self.main_app.initial_ga_crossover_rate)
        self.ga_no_improvement_limit_var.set(self.main_app.initial_ga_no_improvement_limit)
        self.ilp_time_limit_var.set(self.main_app.initial_ilp_time_limit)
        self.cp_time_limit_var.set(self.main_app.initial_cp_time_limit)
        self.multilevel_clusters_var.set(self.main_app.initial_multilevel_clusters)
        self.greedy_ls_iterations_var.set(self.main_app.initial_greedy_ls_iterations)
        self.local_search_iterations_var.set(self.main_app.initial_local_search_iterations)
        self.initial_temperature_var.set(self.main_app.initial_initial_temperature)
        self.cooling_rate_var.set(self.main_app.initial_cooling_rate)
        
        # スコア重みは辞書なので、個別に設定
        self.score_weight_1st_choice_var.set(self.main_app.initial_score_weights.get("1st_choice", 5.0))
        self.score_weight_2nd_choice_var.set(self.main_app.initial_score_weights.get("2nd_choice", 2.0))
        self.score_weight_3rd_choice_var.set(self.main_app.initial_score_weights.get("3rd_choice", 1.0))
        self.score_weight_other_var.set(self.main_app.initial_score_weights.get("other", 0.5))

        self.early_stop_threshold_var.set(self.main_app.initial_early_stop_threshold)
        # 修正: early_stop_no_improvement_limit_var を使用
        self.early_stop_no_improvement_limit_var.set(self.main_app.initial_early_stop_no_improvement_limit)
        self.debug_mode_var.set(self.main_app.initial_debug_mode)
        self.log_enabled_var.set(self.main_app.initial_log_enabled)
        self.save_intermediate_var.set(self.main_app.initial_save_intermediate)
        self.generate_pdf_report_var.set(self.main_app.initial_generate_pdf_report)
        self.generate_csv_report_var.set(self.main_app.initial_generate_csv_report)
        self.theme_var.set(self.main_app.initial_theme) # テーマもUIに反映

    def load_settings_from_config(self, config_data: Dict[str, Any]):
        """
        config.jsonからロードされた設定をSettingTabのUIとmain_appの属性に反映する。
        """
        logger.debug("SettingTab: config.jsonから設定をロードし、UIに反映します。")
        # SettingTabが管理する設定をconfig_dataから取得してUIに反映
        self.optimization_strategy_var.set(config_data.get("optimization_strategy", self.optimization_strategy_var.get()))
        self.ga_population_size_var.set(config_data.get("ga_population_size", self.ga_population_size_var.get()))
        self.ga_generations_var.set(config_data.get("ga_generations", self.ga_generations_var.get()))
        self.ga_mutation_rate_var.set(config_data.get("ga_mutation_rate", self.ga_mutation_rate_var.get()))
        self.ga_crossover_rate_var.set(config_data.get("ga_crossover_rate", self.ga_crossover_rate_var.get()))
        self.ga_no_improvement_limit_var.set(config_data.get("ga_no_improvement_limit", self.ga_no_improvement_limit_var.get()))
        self.ilp_time_limit_var.set(config_data.get("ilp_time_limit", self.ilp_time_limit_var.get()))
        self.cp_time_limit_var.set(config_data.get("cp_time_limit", self.cp_time_limit_var.get()))
        self.multilevel_clusters_var.set(config_data.get("multilevel_clusters", self.multilevel_clusters_var.get()))
        self.greedy_ls_iterations_var.set(config_data.get("greedy_ls_iterations", self.greedy_ls_iterations_var.get()))
        self.local_search_iterations_var.set(config_data.get("local_search_iterations", self.local_search_iterations_var.get()))
        self.initial_temperature_var.set(config_data.get("initial_temperature", self.initial_temperature_var.get()))
        self.cooling_rate_var.set(config_data.get("cooling_rate", self.cooling_rate_var.get()))

        # スコア重みはネストされた辞書なので特別処理
        loaded_score_weights = config_data.get("score_weights", {})
        self.score_weight_1st_choice_var.set(loaded_score_weights.get("1st_choice", self.score_weight_1st_choice_var.get()))
        self.score_weight_2nd_choice_var.set(loaded_score_weights.get("2nd_choice", self.score_weight_2nd_choice_var.get()))
        self.score_weight_3rd_choice_var.set(loaded_score_weights.get("3rd_choice", self.score_weight_3rd_choice_var.get()))
        self.score_weight_other_var.set(loaded_score_weights.get("other", self.score_weight_other_var.get()))

        self.early_stop_threshold_var.set(config_data.get("early_stop_threshold", self.early_stop_threshold_var.get()))
        # 修正: early_stop_no_improvement_limit_var を使用
        self.early_stop_no_improvement_limit_var.set(config_data.get("early_stop_no_improvement_limit", self.early_stop_no_improvement_limit_var.get()))
        self.debug_mode_var.set(config_data.get("debug_mode", self.debug_mode_var.get()))
        self.log_enabled_var.set(config_data.get("log_enabled", self.log_enabled_var.get()))
        self.save_intermediate_var.set(config_data.get("save_intermediate", self.save_intermediate_var.get()))
        self.generate_pdf_report_var.set(config_data.get("generate_pdf_report", self.generate_pdf_report_var.get()))
        self.generate_csv_report_var.set(config_data.get("generate_csv_report", self.generate_csv_report_var.get()))
        
        # output_directory は Path オブジェクトとして扱うため、文字列から変換
        output_dir_str = config_data.get("output_directory", str(self.main_app.initial_output_directory))
        self.output_directory_var.set(output_dir_str)
        self.pdf_font_path_var.set(config_data.get("pdf_font_path", self.pdf_font_path_var.get()))

        # MainApplicationの属性を直接更新
        self._update_main_app_settings_from_ui() # UIの現在の値をMainApplicationに反映

    def get_current_settings_for_main_app(self) -> Dict[str, Any]:
        """
        MainApplicationに保存するためのSettingTabの現在の設定値を取得します。
        """
        logger.debug("SettingTab: 現在の設定値を取得します。")
        score_weights = {
            "1st_choice": self.score_weight_1st_choice_var.get(),
            "2nd_choice": self.score_weight_2nd_choice_var.get(),
            "3rd_choice": self.score_weight_3rd_choice_var.get(),
            "other": self.score_weight_other_var.get(),
        }
        return {
            "output_directory": Path(self.output_directory_var.get()), # Pathオブジェクトとして返す
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
            "score_weights": score_weights,
            "early_stop_threshold": self.early_stop_threshold_var.get(),
            "early_stop_no_improvement_limit": self.early_stop_no_improvement_limit_var.get(), # 修正: 正しいキー名で返す
            "debug_mode": self.debug_mode_var.get(),
            "log_enabled": self.log_enabled_var.get(),
            "save_intermediate": self.save_intermediate_var.get(),
            "generate_pdf_report": self.generate_pdf_report_var.get(),
            "generate_csv_report": self.generate_csv_report_var.get(),
            "theme": self.theme_var.get(), # テーマ設定も返す
        }

    def _update_main_app_settings_from_ui(self):
        """
        UIの現在の設定値をMainApplicationの属性に反映する。
        これはconfig.jsonロード時や、SettingTab内での変更時にMainApplicationの内部状態を同期するために使用。
        """
        current_settings = self.get_current_settings_for_main_app()
        for key, value in current_settings.items():
            full_key = 'initial_' + key
            if hasattr(self.main_app, full_key):
                setattr(self.main_app, full_key, value)
            else:
                logger.warning(f"SettingTab._update_main_app_settings_from_ui: Unknown key for MainApplication attribute: {full_key}")
        
        # テーマ変更を即座に適用
        self.main_app.style.theme_use(self.theme_var.get())
        logger.info(f"SettingTab: GUIテーマを '{self.theme_var.get()}' に変更しました。")
        # ログ設定も即座に適用
        setup_logging(
            log_level="DEBUG" if self.debug_mode_var.get() else "INFO",
            log_file=str(self.main_app.project_root / "logs" / "seminar_optimization.log") if self.log_enabled_var.get() else None
        )
        logger.info("SettingTab: ロギング設定を更新しました。")


    def _browse_directory(self, tk_var: tk.StringVar):
        """
        ディレクトリ参照ダイアログを開き、選択されたディレクトリパスをTkinter変数に設定する。
        """
        dir_path = filedialog.askdirectory(initialdir=os.getcwd(), title="ディレクトリを選択")
        if dir_path:
            tk_var.set(dir_path)
            logger.info(f"SettingTab: 出力ディレクトリを設定しました: {dir_path}")

    def _browse_file(self, tk_var: tk.StringVar, filetypes: List[Tuple[str, str]]):
        """
        ファイル参照ダイアログを開き、選択されたファイルパスをTkinter変数に設定する。
        """
        file_path = filedialog.askopenfilename(
            initialdir=os.getcwd(),
            title="ファイルを選択",
            filetypes=filetypes
        )
        if file_path:
            tk_var.set(file_path)
            logger.info(f"SettingTab: フォントファイルパスを設定しました: {file_path}")

    def style_themes(self) -> List[str]:
        """
        利用可能なttkスタイルテーマのリストを返す。
        修正: main_appのスタイルオブジェクトを使用
        """
        return list(self.main_app.style.theme_names())

    def _apply_theme(self, event=None):
        """
        選択されたテーマをGUIに適用する。
        """
        selected_theme = self.theme_var.get()
        try:
            self.main_app.style.theme_use(selected_theme)
            logger.info(f"SettingTab: GUIテーマを '{selected_theme}' に変更しました。")
        except tk.TclError as e:
            messagebox.showerror("テーマエラー", f"テーマ '{selected_theme}' の適用に失敗しました: {e}")
            logger.error(f"SettingTab: テーマ '{selected_theme}' の適用に失敗しました。", exc_info=True)
