import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import logging
from typing import Dict, List, Any, Optional, Callable, Tuple
import ctypes

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(True)
except:
    pass

# ロギングは logger_config.py で一元的に設定されるため、ここではロガーの取得のみ
from seminar_optimization.logger_config import logger
from seminar_optimization.data_generator import DataGenerator
from seminar_optimization.schemas import SEMINARS_SCHEMA, STUDENTS_SCHEMA, CONFIG_SCHEMA
import jsonschema


class DataInputTab:
    """
    「データ入力」タブのUIとロジックを管理するクラス。
    セミナーと学生データのロード、生成、および関連する設定を扱う。
    """
    
    def __init__(self, notebook: ttk.Notebook, parent_app: Any):
        """
        DataInputTabを初期化する。
        
        Args:
            notebook: 親のNotebookウィジェット
            parent_app: MainApplicationインスタンス
        """
        self.notebook = notebook
        self.parent_app = parent_app
        self.frame = ttk.Frame(notebook, padding="10")
        logger.debug("DataInputTab: 初期化を開始します。")
        
        # データ保持用
        self.seminars_data: List[Dict[str, Any]] = []
        self.students_data: List[Dict[str, Any]] = []
        
        # UI要素の参照を保持
        self.file_load_frame = None
        self.auto_generate_frame = None
        self.data_summary_text = None
        
        # Tkinter変数の初期化
        self._initialize_variables()
        
        # UIコンポーネントの作成
        self._create_widgets()
        
        # 初期設定の読み込み
        self._load_initial_settings_to_ui()
        
        logger.debug("DataInputTab: 初期化が完了しました。")

    def _initialize_variables(self):
        """Tkinter変数を初期化する。"""
        # 初期値はparent_appから取得
        self.data_input_method_var = tk.StringVar(value=self.parent_app.initial_data_input_method)
        self.seminar_ids_var = tk.StringVar(value="")
        self.num_seminars_var = tk.IntVar(value=self.parent_app.initial_num_seminars)
        self.num_students_var = tk.IntVar(value=self.parent_app.initial_num_students)
        self.min_capacity_var = tk.IntVar(value=self.parent_app.initial_min_capacity)
        self.max_capacity_var = tk.IntVar(value=self.parent_app.initial_max_capacity)
        self.preference_distribution_var = tk.StringVar(value=self.parent_app.initial_preference_distribution)
        self.random_seed_var = tk.IntVar(value=self.parent_app.initial_random_seed)
        self.q_boost_probability_var = tk.DoubleVar(value=self.parent_app.initial_q_boost_probability)
        self.num_preferences_to_consider_var = tk.IntVar(value=self.parent_app.initial_num_preferences_to_consider)
        self.min_preferences_var = tk.IntVar(value=self.parent_app.initial_min_preferences)
        
        # ファイルパス変数
        self.config_file_path_var = tk.StringVar(value=self.parent_app.initial_config_file_path)
        self.students_file_path_var = tk.StringVar(value=self.parent_app.initial_students_file_path)
        self.seminars_file_path_var = tk.StringVar(value=self.parent_app.initial_seminars_file_path)

    def _create_widgets(self):
        """「データ入力」タブのウィジェットを作成する。"""
        logger.debug("DataInputTab: ウィジェットの作成を開始します。")
        
        self._create_input_method_widgets()
        self._create_file_load_widgets()
        self._create_auto_generate_widgets()
        self._create_summary_widgets()
        
        # 初期状態の表示を更新
        self._toggle_input_fields()
        
        logger.debug("DataInputTab: ウィジェットの作成が完了しました。")

    def _create_input_method_widgets(self):
        """入力方法選択ウィジェットを作成する。"""
        input_method_frame = ttk.LabelFrame(self.frame, text="データ入力方法", padding="10")
        input_method_frame.pack(fill=tk.X, pady=5)
        
        methods = [
            ("既存ファイルをロード", "load_file"),
            ("ランダムに自動生成", "auto_generate"),
            ("config.jsonからロード", "load_config")
        ]
        
        for text, value in methods:
            ttk.Radiobutton(
                input_method_frame, 
                text=text, 
                variable=self.data_input_method_var, 
                value=value, 
                command=self._toggle_input_fields
            ).pack(anchor=tk.W)

    def _create_file_load_widgets(self):
        """ファイルロード設定ウィジェットを作成する。"""
        self.file_load_frame = ttk.LabelFrame(self.frame, text="ファイルロード設定", padding="10")
        self.file_load_frame.pack(fill=tk.X, pady=5)

        # セミナーファイル行
        self._create_file_input_row(
            self.file_load_frame, 0, "セミナーファイル (.json/.csv):",
            self.seminars_file_path_var,
            [("JSON files", "*.json"), ("CSV files", "*.csv")],
            self._load_seminar_data
        )
        
        # 学生ファイル行
        self._create_file_input_row(
            self.file_load_frame, 1, "学生ファイル (.json/.csv):",
            self.students_file_path_var,
            [("JSON files", "*.json"), ("CSV files", "*.csv")],
            self._load_student_data
        )
        
        # Configファイル行
        self._create_file_input_row(
            self.file_load_frame, 2, "Configファイル (.json):",
            self.config_file_path_var,
            [("JSON files", "*.json")],
            self._load_config_file,
            load_button_text="Configロード"
        )

    def _create_file_input_row(self, parent, row, label_text, path_var, filetypes, load_command, load_button_text="ロード"):
        """ファイル入力行を作成するヘルパーメソッド。"""
        ttk.Label(parent, text=label_text).grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Entry(parent, textvariable=path_var, width=50).grid(row=row, column=1, padx=5, pady=2)
        ttk.Button(
            parent, text="参照", 
            command=lambda: self._browse_file(path_var, filetypes)
        ).grid(row=row, column=2, padx=5, pady=2)
        ttk.Button(
            parent, text=load_button_text, 
            command=load_command
        ).grid(row=row, column=3, padx=5, pady=2)

    def _create_auto_generate_widgets(self):
        """自動生成設定ウィジェットを作成する。"""
        self.auto_generate_frame = ttk.LabelFrame(self.frame, text="自動生成設定", padding="10")
        self.auto_generate_frame.pack(fill=tk.X, pady=5)

        # 設定項目のリスト
        settings = [
            ("セミナー数:", self.num_seminars_var, 10),
            ("学生数:", self.num_students_var, 10),
            ("セミナー最小定員:", self.min_capacity_var, 10),
            ("セミナー最大定員:", self.max_capacity_var, 10),
            ("ランダムシード:", self.random_seed_var, 10),
            ("Qブースト確率:", self.q_boost_probability_var, 10),
            ("考慮する希望数 (最大):", self.num_preferences_to_consider_var, 10),
            ("考慮する希望数 (最小):", self.min_preferences_var, 10),
        ]

        # 通常の入力フィールド
        for i, (label_text, var, width) in enumerate(settings):
            ttk.Label(self.auto_generate_frame, text=label_text).grid(row=i, column=0, sticky=tk.W, pady=2)
            ttk.Entry(self.auto_generate_frame, textvariable=var, width=width).grid(row=i, column=1, sticky=tk.W, padx=5, pady=2)

        # 希望分布のコンボボックス
        row = len(settings)
        ttk.Label(self.auto_generate_frame, text="希望分布:").grid(row=row, column=0, sticky=tk.W, pady=2)
        ttk.Combobox(
            self.auto_generate_frame, 
            textvariable=self.preference_distribution_var,
            values=["uniform", "biased_towards_popular", "diverse"],
            state="readonly"
        ).grid(row=row, column=1, sticky=tk.W, padx=5, pady=2)

        # データ生成ボタン
        ttk.Button(
            self.auto_generate_frame, 
            text="データ生成", 
            command=self._generate_data
        ).grid(row=row+1, column=0, columnspan=2, pady=10)

    def _create_summary_widgets(self):
        """データ概要表示ウィジェットを作成する。"""
        # データ概要表示エリア
        summary_frame = ttk.LabelFrame(self.frame, text="データ概要", padding="10")
        summary_frame.pack(fill=tk.X, pady=5)
        
        self.data_summary_text = tk.Text(summary_frame, height=8, state='disabled', wrap=tk.WORD)
        
        # スクロールバーを追加
        scrollbar = ttk.Scrollbar(summary_frame, orient="vertical", command=self.data_summary_text.yview)
        self.data_summary_text.configure(yscrollcommand=scrollbar.set)
        
        self.data_summary_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _load_initial_settings_to_ui(self):
        """MainApplicationから初期値をロードしてUIに反映する。"""
        logger.debug("DataInputTab: UIに初期設定をロードします。")
        
        # 設定値の辞書
        settings = {
            self.data_input_method_var: self.parent_app.initial_data_input_method,
            self.num_seminars_var: self.parent_app.initial_num_seminars,
            self.num_students_var: self.parent_app.initial_num_students,
            self.min_capacity_var: self.parent_app.initial_min_capacity,
            self.max_capacity_var: self.parent_app.initial_max_capacity,
            self.preference_distribution_var: self.parent_app.initial_preference_distribution,
            self.random_seed_var: self.parent_app.initial_random_seed,
            self.q_boost_probability_var: self.parent_app.initial_q_boost_probability,
            self.num_preferences_to_consider_var: self.parent_app.initial_max_preferences,
            self.min_preferences_var: self.parent_app.initial_min_preferences,
            self.students_file_path_var: self.parent_app.initial_students_file_path,
            self.seminars_file_path_var: self.parent_app.initial_seminars_file_path,
            self.config_file_path_var: self.parent_app.initial_config_file_path,
        }
        
        # 一括設定
        for var, value in settings.items():
            var.set(value)

        self._toggle_input_fields()

    def _toggle_input_fields(self):
        """選択されたデータ入力方法に基づいて、関連する入力フィールドの表示を切り替える。"""
        method = self.data_input_method_var.get()
        
        if method == "load_file":
            self.file_load_frame.pack(fill=tk.X, pady=5)
            self.auto_generate_frame.pack_forget()
        elif method == "auto_generate":
            self.file_load_frame.pack_forget()
            self.auto_generate_frame.pack(fill=tk.X, pady=5)
        elif method == "load_config":
            self.file_load_frame.pack(fill=tk.X, pady=5)
            self.auto_generate_frame.pack_forget()
            # config.jsonロード時に他のパスをクリア
            self.seminars_file_path_var.set("")
            self.students_file_path_var.set("")
            
        logger.debug(f"DataInputTab: 入力フィールドの表示を '{method}' に切り替えました。")

    def _browse_file(self, tk_var: tk.StringVar, filetypes: List[Tuple[str, str]]):
        """ファイル参照ダイアログを開き、選択されたファイルパスをTkinter変数に設定する。"""
        file_path = filedialog.askopenfilename(
            initialdir=os.getcwd(),
            title="ファイルを選択",
            filetypes=filetypes
        )
        if file_path:
            tk_var.set(file_path)
            logger.info(f"DataInputTab: ファイルパスを設定しました: {file_path}")

    def _load_data_from_file(self, file_path: str, data_type: str) -> List[Dict[str, Any]]:
        """
        ファイルからデータをロードする共通メソッド。
        
        Args:
            file_path: ファイルパス
            data_type: データタイプ（"seminars" または "students"）
            
        Returns:
            ロードされたデータのリスト
            
        Raises:
            Exception: ロード中にエラーが発生した場合
        """
        if not file_path:
            raise ValueError(f"{data_type}ファイルが指定されていません。")
        
        generator = DataGenerator(config={})
        return generator.load_data_from_file(file_path, data_type=data_type)

    def _load_seminar_data(self):
        """指定されたセミナーファイルからデータをロードする。"""
        try:
            file_path = self.seminars_file_path_var.get()
            self.seminars_data = self._load_data_from_file(file_path, "seminars")
            self._update_data_summary()
            messagebox.showinfo("ロード完了", f"セミナーデータ {len(self.seminars_data)} 件をロードしました。")
            logger.info(f"DataInputTab: セミナーデータをロードしました: {file_path}")
        except Exception as e:
            messagebox.showerror("ロードエラー", f"セミナーデータのロード中にエラーが発生しました: {e}")
            logger.exception("DataInputTab: セミナーデータのロード中にエラーが発生しました。")

    def _load_student_data(self):
        """指定された学生ファイルからデータをロードする。"""
        try:
            file_path = self.students_file_path_var.get()
            self.students_data = self._load_data_from_file(file_path, "students")
            self._update_data_summary()
            messagebox.showinfo("ロード完了", f"学生データ {len(self.students_data)} 件をロードしました。")
            logger.info(f"DataInputTab: 学生データをロードしました: {file_path}")
        except Exception as e:
            messagebox.showerror("ロードエラー", f"学生データのロード中にエラーが発生しました: {e}")
            logger.exception("DataInputTab: 学生データのロード中にエラーが発生しました。")

    def _load_config_file(self):
        """config.jsonファイルから設定をロードし、UIに反映する。"""
        file_path = self.config_file_path_var.get()
        if not file_path:
            messagebox.showwarning("ファイル未指定", "config.jsonファイルを指定してください。")
            return

        try:
            config_data = self._load_and_validate_config(file_path)
            self._apply_config_to_ui(config_data)
            self._update_parent_app_settings(config_data)
            
            # SettingTabの設定もconfig.jsonからロード
            self.parent_app.setting_tab.load_settings_from_config(config_data)

            messagebox.showinfo("Configロード完了", "config.jsonから設定をロードし、UIに反映しました。")
            logger.info(f"DataInputTab: config.jsonをロードしました: {file_path}")

        except json.JSONDecodeError as e:
            messagebox.showerror("Configロードエラー", f"config.jsonの形式が不正です: {e}")
            logger.exception(f"DataInputTab: config.jsonのJSONデコードエラー: {file_path}")
        except jsonschema.exceptions.ValidationError as e:
            messagebox.showerror("Config検証エラー", 
                               f"config.jsonがスキーマに準拠していません: {e.message} (パス: {'.'.join(map(str, e.path))})")
            logger.exception(f"DataInputTab: config.jsonのスキーマ検証エラー: {file_path}")
        except Exception as e:
            messagebox.showerror("Configロードエラー", f"config.jsonのロード中に予期せぬエラーが発生しました: {e}")
            logger.exception("DataInputTab: config.jsonのロード中に予期せぬエラーが発生しました。")

    def _load_and_validate_config(self, file_path: str) -> Dict[str, Any]:
        """config.jsonファイルをロードして検証する。"""
        with open(file_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)
        
        # スキーマ検証
        jsonschema.validate(instance=config_data, schema=CONFIG_SCHEMA)
        logger.debug(f"DataInputTab: config.jsonのスキーマ検証に成功しました: {file_path}")
        
        return config_data

    def _apply_config_to_ui(self, config_data: Dict[str, Any]):
        """config.jsonの設定をUIに適用する。"""
        # 設定項目のマッピング
        config_mappings = {
            "num_seminars": self.num_seminars_var,
            "num_students": self.num_students_var,
            "min_capacity": self.min_capacity_var,
            "max_capacity": self.max_capacity_var,
            "preference_distribution": self.preference_distribution_var,
            "random_seed": self.random_seed_var,
            "q_boost_probability": self.q_boost_probability_var,
            "max_preferences": self.num_preferences_to_consider_var,
            "min_preferences": self.min_preferences_var,
        }
        
        for config_key, var in config_mappings.items():
            if config_key in config_data:
                var.set(config_data[config_key])

    def _update_parent_app_settings(self, config_data: Dict[str, Any]):
        """MainApplicationの設定属性をconfig.jsonから更新する。"""
        # MainApplicationの属性マッピング
        app_mappings = {
            "num_seminars": "initial_num_seminars",
            "num_students": "initial_num_students",
            "min_capacity": "initial_min_capacity",
            "max_capacity": "initial_max_capacity",
            "preference_distribution": "initial_preference_distribution",
            "random_seed": "initial_random_seed",
            "q_boost_probability": "initial_q_boost_probability",
            "max_preferences": "initial_max_preferences",
            "min_preferences": "initial_min_preferences",
        }
        
        for config_key, app_attr in app_mappings.items():
            if config_key in config_data:
                setattr(self.parent_app, app_attr, config_data[config_key])

    def _generate_data(self):
        """設定されたパラメータに基づいてセミナーと学生データを自動生成する。"""
        try:
            generation_config = self._build_generation_config()
            generator = DataGenerator(config=generation_config)
            
            self.seminars_data, self.students_data = generator.generate_data(
                num_seminars=generation_config["num_seminars"],
                min_capacity=generation_config["min_capacity"],
                max_capacity=generation_config["max_capacity"],
                num_students=generation_config["num_students"],
                min_preferences=generation_config["min_preferences"],
                max_preferences=generation_config["max_preferences"],
                preference_distribution=generation_config["preference_distribution"]
            )
            
            self._update_data_summary()
            messagebox.showinfo("データ生成完了", 
                              f"セミナーデータ {len(self.seminars_data)} 件、学生データ {len(self.students_data)} 件を生成しました。")
            logger.info(f"DataInputTab: データを自動生成しました。セミナー数: {len(self.seminars_data)}, 学生数: {len(self.students_data)}")
            
        except Exception as e:
            messagebox.showerror("データ生成エラー", f"データの自動生成中にエラーが発生しました: {e}")
            logger.exception("DataInputTab: データの自動生成中にエラーが発生しました。")

    def _build_generation_config(self) -> Dict[str, Any]:
        """データ生成用の設定辞書を構築する。"""
        return {
            "num_seminars": self.num_seminars_var.get(),
            "num_students": self.num_students_var.get(),
            "min_capacity": self.min_capacity_var.get(),
            "max_capacity": self.max_capacity_var.get(),
            "preference_distribution": self.preference_distribution_var.get(),
            "random_seed": self.random_seed_var.get(),
            "q_boost_probability": self.q_boost_probability_var.get(),
            "min_preferences": self.min_preferences_var.get(),
            "max_preferences": self.num_preferences_to_consider_var.get(),
        }

    def _update_data_summary(self):
        """ロードまたは生成されたデータの概要をテキストエリアに表示する。"""
        self.data_summary_text.config(state='normal')
        self.data_summary_text.delete(1.0, tk.END)
        
        summary = self._build_data_summary()
        self.data_summary_text.insert(tk.END, summary)
        self.data_summary_text.config(state='disabled')
        
        logger.debug("DataInputTab: データ概要を更新しました。")

    def _build_data_summary(self) -> str:
        """データ概要の文字列を構築する。"""
        summary = "--- データ概要 ---\n"
        
        # セミナー情報
        summary += f"セミナー数: {len(self.seminars_data)}\n"
        if self.seminars_data:
            seminar_ids = [s['id'] for s in self.seminars_data]
            sample_ids = seminar_ids[:3]
            if len(self.seminars_data) > 3:
                sample_ids.append("...")
            summary += "  セミナーID例: " + ", ".join(sample_ids) + "\n"
            
            # セミナーIDリストを更新
            self.seminar_ids_var.set(",".join(seminar_ids))
            summary += "  全セミナーID: " + self.seminar_ids_var.get() + "\n"
        else:
            self.seminar_ids_var.set("")
        
        # 学生情報
        summary += f"学生数: {len(self.students_data)}\n"
        if self.students_data:
            student_ids = [s['id'] for s in self.students_data]
            sample_ids = student_ids[:3]
            if len(self.students_data) > 3:
                sample_ids.append("...")
            summary += "  学生ID例: " + ", ".join(sample_ids) + "\n"
        
        return summary

    def get_current_settings_for_main_app(self) -> Dict[str, Any]:
        """MainApplicationに保存するためのDataInputTabの現在の設定値を取得する。"""
        logger.debug("DataInputTab: 現在の設定値を取得します。")
        return {
            "data_input_method": self.data_input_method_var.get(),
            "num_seminars": self.num_seminars_var.get(),
            "num_students": self.num_students_var.get(),
            "min_capacity": self.min_capacity_var.get(),
            "max_capacity": self.max_capacity_var.get(),
            "preference_distribution": self.preference_distribution_var.get(),
            "random_seed": self.random_seed_var.get(),
            "q_boost_probability": self.q_boost_probability_var.get(),
            "max_preferences": self.num_preferences_to_consider_var.get(),
            "min_preferences": self.min_preferences_var.get(),
            "students_file_path": self.students_file_path_var.get(),
            "seminars_file_path": self.seminars_file_path_var.get(),
            "config_file_path": self.config_file_path_var.get(),
        }

    def get_seminars_data(self) -> List[Dict[str, Any]]:
        """現在ロードまたは生成されているセミナーデータを返す。"""
        return self.seminars_data

    def get_students_data(self) -> List[Dict[str, Any]]:
        """現在ロードまたは生成されている学生データを返す。"""
        return self.students_data