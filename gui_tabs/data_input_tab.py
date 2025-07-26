import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import json
import logging
from typing import Dict, List, Any, Optional, Callable, Tuple

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
    def __init__(self, notebook: ttk.Notebook, parent_app: Any): # parent_app は MainApplication インスタンス
        self.notebook = notebook
        self.parent_app = parent_app # MainApplicationインスタンスへの参照を保持
        self.frame = ttk.Frame(notebook, padding="10")
        logger.debug("DataInputTab: 初期化を開始します。")
        
        # Tkinter変数 - DataInputTabで管理する設定のみ
        # 初期値はparent_appから取得
        self.data_input_method_var = tk.StringVar(value=self.parent_app.initial_data_input_method)
        self.seminar_ids_var = tk.StringVar(value="") # セミナーIDは動的にセットされるため初期値は空
        self.num_seminars_var = tk.IntVar(value=self.parent_app.initial_num_seminars)
        self.num_students_var = tk.IntVar(value=self.parent_app.initial_num_students)
        self.min_capacity_var = tk.IntVar(value=self.parent_app.initial_min_capacity)
        self.max_capacity_var = tk.IntVar(value=self.parent_app.initial_max_capacity)
        self.preference_distribution_var = tk.StringVar(value=self.parent_app.initial_preference_distribution)
        self.random_seed_var = tk.IntVar(value=self.parent_app.initial_random_seed)
        self.q_boost_probability_var = tk.DoubleVar(value=self.parent_app.initial_q_boost_probability)
        self.num_preferences_to_consider_var = tk.IntVar(value=self.parent_app.initial_num_preferences_to_consider) # UI上の「考慮する希望数（最大）」
        self.min_preferences_var = tk.IntVar(value=self.parent_app.initial_min_preferences) # 最小希望数
        
        # ファイルパスもDataInputTabで管理
        self.config_file_path_var = tk.StringVar(value=self.parent_app.initial_config_file_path) # config.jsonのパス
        self.students_file_path_var = tk.StringVar(value=self.parent_app.initial_students_file_path)
        self.seminars_file_path_var = tk.StringVar(value=self.parent_app.initial_seminars_file_path)

        # 実際のデータ保持用
        self.seminars_data: List[Dict[str, Any]] = []
        self.students_data: List[Dict[str, Any]] = []

        self._create_widgets()
        self._load_initial_settings_to_ui() # UIに初期値を反映

        logger.debug("DataInputTab: 初期化が完了しました。")

    def _create_widgets(self):
        """
        「データ入力」タブのウィジェットを作成する。
        """
        logger.debug("DataInputTab: ウィジェットの作成を開始します。")
        # 入力方法選択フレーム
        input_method_frame = ttk.LabelFrame(self.frame, text="データ入力方法", padding="10")
        input_method_frame.pack(fill=tk.X, pady=5)
        
        ttk.Radiobutton(input_method_frame, text="既存ファイルをロード", variable=self.data_input_method_var, value="load_file", command=self._toggle_input_fields).pack(anchor=tk.W)
        ttk.Radiobutton(input_method_frame, text="ランダムに自動生成", variable=self.data_input_method_var, value="auto_generate", command=self._toggle_input_fields).pack(anchor=tk.W)
        ttk.Radiobutton(input_method_frame, text="config.jsonからロード", variable=self.data_input_method_var, value="load_config", command=self._toggle_input_fields).pack(anchor=tk.W)

        # ファイルロード設定フレーム
        self.file_load_frame = ttk.LabelFrame(self.frame, text="ファイルロード設定", padding="10")
        self.file_load_frame.pack(fill=tk.X, pady=5)

        ttk.Label(self.file_load_frame, text="セミナーファイル (.json/.csv):").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.file_load_frame, textvariable=self.seminars_file_path_var, width=50).grid(row=0, column=1, padx=5, pady=2)
        ttk.Button(self.file_load_frame, text="参照", command=lambda: self._browse_file(self.seminars_file_path_var, [("JSON files", "*.json"), ("CSV files", "*.csv")])).grid(row=0, column=2, padx=5, pady=2)
        ttk.Button(self.file_load_frame, text="ロード", command=self._load_seminar_data).grid(row=0, column=3, padx=5, pady=2)

        ttk.Label(self.file_load_frame, text="学生ファイル (.json/.csv):").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.file_load_frame, textvariable=self.students_file_path_var, width=50).grid(row=1, column=1, padx=5, pady=2)
        ttk.Button(self.file_load_frame, text="参照", command=lambda: self._browse_file(self.students_file_path_var, [("JSON files", "*.json"), ("CSV files", "*.csv")])).grid(row=1, column=2, padx=5, pady=2)
        ttk.Button(self.file_load_frame, text="ロード", command=self._load_student_data).grid(row=1, column=3, padx=5, pady=2)

        ttk.Label(self.file_load_frame, text="Configファイル (.json):").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.file_load_frame, textvariable=self.config_file_path_var, width=50).grid(row=2, column=1, padx=5, pady=2)
        ttk.Button(self.file_load_frame, text="参照", command=lambda: self._browse_file(self.config_file_path_var, [("JSON files", "*.json")])).grid(row=2, column=2, padx=5, pady=2)
        ttk.Button(self.file_load_frame, text="Configロード", command=self._load_config_file).grid(row=2, column=3, padx=5, pady=2)


        # 自動生成設定フレーム
        self.auto_generate_frame = ttk.LabelFrame(self.frame, text="自動生成設定", padding="10")
        self.auto_generate_frame.pack(fill=tk.X, pady=5)

        ttk.Label(self.auto_generate_frame, text="セミナー数:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.auto_generate_frame, textvariable=self.num_seminars_var, width=10).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(self.auto_generate_frame, text="学生数:").grid(row=1, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.auto_generate_frame, textvariable=self.num_students_var, width=10).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(self.auto_generate_frame, text="セミナー最小定員:").grid(row=2, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.auto_generate_frame, textvariable=self.min_capacity_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(self.auto_generate_frame, text="セミナー最大定員:").grid(row=3, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.auto_generate_frame, textvariable=self.max_capacity_var, width=10).grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(self.auto_generate_frame, text="希望分布:").grid(row=4, column=0, sticky=tk.W, pady=2)
        ttk.Combobox(self.auto_generate_frame, textvariable=self.preference_distribution_var,
                     values=["uniform", "biased_towards_popular", "diverse"]).grid(row=4, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(self.auto_generate_frame, text="ランダムシード:").grid(row=5, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.auto_generate_frame, textvariable=self.random_seed_var, width=10).grid(row=5, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(self.auto_generate_frame, text="Qブースト確率:").grid(row=6, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.auto_generate_frame, textvariable=self.q_boost_probability_var, width=10).grid(row=6, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(self.auto_generate_frame, text="考慮する希望数 (最大):").grid(row=7, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.auto_generate_frame, textvariable=self.num_preferences_to_consider_var, width=10).grid(row=7, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(self.auto_generate_frame, text="考慮する希望数 (最小):").grid(row=8, column=0, sticky=tk.W, pady=2)
        ttk.Entry(self.auto_generate_frame, textvariable=self.min_preferences_var, width=10).grid(row=8, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Button(self.auto_generate_frame, text="データ生成", command=self._generate_data).grid(row=9, column=0, columnspan=2, pady=10)

        # データ概要表示エリア
        self.data_summary_text = tk.Text(self.frame, height=8, state='disabled', wrap=tk.WORD)
        self.data_summary_text.pack(fill=tk.X, pady=5)
        logger.debug("DataInputTab: ウィジェットの作成が完了しました。")
        
        # 初期状態の表示を更新
        self._toggle_input_fields()


    def _load_initial_settings_to_ui(self):
        """
        MainApplicationから初期値をロードしてUIに反映する。
        """
        logger.debug("DataInputTab: UIに初期設定をロードします。")
        self.data_input_method_var.set(self.parent_app.initial_data_input_method)
        self.num_seminars_var.set(self.parent_app.initial_num_seminars)
        self.num_students_var.set(self.parent_app.initial_num_students)
        self.min_capacity_var.set(self.parent_app.initial_min_capacity)
        self.max_capacity_var.set(self.parent_app.initial_max_capacity)
        self.preference_distribution_var.set(self.parent_app.initial_preference_distribution)
        self.random_seed_var.set(self.parent_app.initial_random_seed)
        self.q_boost_probability_var.set(self.parent_app.initial_q_boost_probability)
        # num_preferences_to_consider_varはmax_preferencesに相当
        self.num_preferences_to_consider_var.set(self.parent_app.initial_max_preferences) 
        self.min_preferences_var.set(self.parent_app.initial_min_preferences)
        self.students_file_path_var.set(self.parent_app.initial_students_file_path)
        self.seminars_file_path_var.set(self.parent_app.initial_seminars_file_path)
        self.config_file_path_var.set(self.parent_app.initial_config_file_path) # config.jsonのパスもUIに反映

        self._toggle_input_fields() # ロードされた入力方法に基づいてフィールドの表示を切り替える

    def _toggle_input_fields(self):
        """
        選択されたデータ入力方法に基づいて、関連する入力フィールドの表示を切り替える。
        """
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
            # config.jsonのパス入力だけを有効にし、他のファイルパス入力は無効にする
            self.seminars_file_path_var.set("")
            self.students_file_path_var.set("")
            # エントリーウィジェットを直接操作する必要があるため、_create_widgetsで参照を保持するか、再構築が必要になる可能性あり
            # 現状は、config.jsonロード時に他のパスをクリアするのみとする
        logger.debug(f"DataInputTab: 入力フィールドの表示を '{method}' に切り替えました。")

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
            logger.info(f"DataInputTab: ファイルパスを設定しました: {file_path}")

    def _load_seminar_data(self):
        """
        指定されたセミナーファイルからデータをロードする。
        """
        file_path = self.seminars_file_path_var.get()
        if not file_path:
            messagebox.showwarning("ファイル未指定", "セミナーファイルを指定してください。")
            return
        
        try:
            generator = DataGenerator(config={}) # configはここではダミー
            self.seminars_data = generator.load_data_from_file(file_path, data_type="seminars")
            self._update_data_summary()
            messagebox.showinfo("ロード完了", f"セミナーデータ {len(self.seminars_data)} 件をロードしました。")
            logger.info(f"DataInputTab: セミナーデータをロードしました: {file_path}")
        except Exception as e:
            messagebox.showerror("ロードエラー", f"セミナーデータのロード中にエラーが発生しました: {e}")
            logger.exception(f"DataInputTab: セミナーデータのロード中にエラーが発生しました: {file_path}")

    def _load_student_data(self):
        """
        指定された学生ファイルからデータをロードする。
        """
        file_path = self.students_file_path_var.get()
        if not file_path:
            messagebox.showwarning("ファイル未指定", "学生ファイルを指定してください。")
            return
        
        try:
            generator = DataGenerator(config={}) # configはここではダミー
            self.students_data = generator.load_data_from_file(file_path, data_type="students")
            self._update_data_summary()
            messagebox.showinfo("ロード完了", f"学生データ {len(self.students_data)} 件をロードしました。")
            logger.info(f"DataInputTab: 学生データをロードしました: {file_path}")
        except Exception as e:
            messagebox.showerror("ロードエラー", f"学生データのロード中にエラーが発生しました: {e}")
            logger.exception(f"DataInputTab: 学生データのロード中にエラーが発生しました: {file_path}")

    def _load_config_file(self):
        """
        config.jsonファイルから設定をロードし、UIに反映する。
        """
        file_path = self.config_file_path_var.get()
        if not file_path:
            messagebox.showwarning("ファイル未指定", "config.jsonファイルを指定してください。")
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # スキーマ検証
            jsonschema.validate(instance=config_data, schema=CONFIG_SCHEMA)
            logger.debug(f"DataInputTab: config.jsonのスキーマ検証に成功しました: {file_path}")

            # DataInputTabが管理する設定をconfig_dataから取得してUIに反映
            self.num_seminars_var.set(config_data.get("num_seminars", self.num_seminars_var.get()))
            self.num_students_var.set(config_data.get("num_students", self.num_students_var.get()))
            self.min_capacity_var.set(config_data.get("min_capacity", self.min_capacity_var.get()))
            self.max_capacity_var.set(config_data.get("max_capacity", self.max_capacity_var.get()))
            self.preference_distribution_var.set(config_data.get("preference_distribution", self.preference_distribution_var.get()))
            self.random_seed_var.set(config_data.get("random_seed", self.random_seed_var.get()))
            self.q_boost_probability_var.set(config_data.get("q_boost_probability", self.q_boost_probability_var.get()))
            self.num_preferences_to_consider_var.set(config_data.get("max_preferences", self.num_preferences_to_consider_var.get())) # max_preferencesを反映
            self.min_preferences_var.set(config_data.get("min_preferences", self.min_preferences_var.get())) # min_preferencesを反映
            
            # MainApplicationの属性も更新する（SettingTabの設定も含む）
            # これはMainApplicationのsave_current_settingsが最終的に行うべき処理だが、
            # config.jsonロード時に即座にUIと内部状態を同期させるためにここで呼び出す
            self.parent_app.initial_num_seminars = self.num_seminars_var.get()
            self.parent_app.initial_num_students = self.num_students_var.get()
            self.parent_app.initial_min_capacity = self.min_capacity_var.get()
            self.parent_app.initial_max_capacity = self.max_capacity_var.get()
            self.parent_app.initial_preference_distribution = self.preference_distribution_var.get()
            self.parent_app.initial_random_seed = self.random_seed_var.get()
            self.parent_app.initial_q_boost_probability = self.q_boost_probability_var.get()
            self.parent_app.initial_num_preferences_to_consider = self.num_preferences_to_consider_var.get()
            self.parent_app.initial_min_preferences = self.min_preferences_var.get()
            self.parent_app.initial_max_preferences = self.num_preferences_to_consider_var.get() # max_preferencesも更新
            
            # SettingTabの設定もconfig.jsonからロードしてMainApplicationの属性を更新
            # SettingTabのインスタンスを通じて更新をトリガー
            self.parent_app.setting_tab.load_settings_from_config(config_data)

            messagebox.showinfo("Configロード完了", "config.jsonから設定をロードし、UIに反映しました。")
            logger.info(f"DataInputTab: config.jsonをロードしました: {file_path}")

        except json.JSONDecodeError as e:
            messagebox.showerror("Configロードエラー", f"config.jsonの形式が不正です: {e}")
            logger.exception(f"DataInputTab: config.jsonのJSONデコードエラー: {file_path}")
        except jsonschema.exceptions.ValidationError as e:
            messagebox.showerror("Config検証エラー", f"config.jsonがスキーマに準拠していません: {e.message} (パス: {'.'.join(map(str, e.path))})")
            logger.exception(f"DataInputTab: config.jsonのスキーマ検証エラー: {file_path}")
        except Exception as e:
            messagebox.showerror("Configロードエラー", f"config.jsonのロード中に予期せぬエラーが発生しました: {e}")
            logger.exception(f"DataInputTab: config.jsonのロード中に予期せぬエラーが発生しました: {e}")

    def _generate_data(self):
        """
        設定されたパラメータに基づいてセミナーと学生データを自動生成する。
        """
        try:
            # GUIからパラメータを取得
            num_seminars = self.num_seminars_var.get()
            num_students = self.num_students_var.get()
            min_capacity = self.min_capacity_var.get()
            max_capacity = self.max_capacity_var.get()
            preference_distribution = self.preference_distribution_var.get()
            random_seed = self.random_seed_var.get()
            q_boost_probability = self.q_boost_probability_var.get()
            max_preferences = self.num_preferences_to_consider_var.get() # UIの考慮する希望数（最大）
            min_preferences = self.min_preferences_var.get() # UIの考慮する希望数（最小）

            # データ生成用のconfig辞書を構築
            generation_config = {
                "num_seminars": num_seminars,
                "num_students": num_students,
                "min_capacity": min_capacity,
                "max_capacity": max_capacity,
                "preference_distribution": preference_distribution,
                "random_seed": random_seed,
                "q_boost_probability": q_boost_probability,
                "min_preferences": min_preferences,
                "max_preferences": max_preferences,
            }
            
            generator = DataGenerator(config=generation_config)
            self.seminars_data, self.students_data = generator.generate_data(
                num_seminars=num_seminars,
                min_capacity=min_capacity,
                max_capacity=max_capacity,
                num_students=num_students,
                min_preferences=min_preferences,
                max_preferences=max_preferences,
                preference_distribution=preference_distribution
            )
            self._update_data_summary()
            messagebox.showinfo("データ生成完了", f"セミナーデータ {len(self.seminars_data)} 件、学生データ {len(self.students_data)} 件を生成しました。")
            logger.info(f"DataInputTab: データを自動生成しました。セミナー数: {len(self.seminars_data)}, 学生数: {len(self.students_data)}")
        except Exception as e:
            messagebox.showerror("データ生成エラー", f"データの自動生成中にエラーが発生しました: {e}")
            logger.exception("DataInputTab: データの自動生成中にエラーが発生しました。")

    def _update_data_summary(self):
        """
        ロードまたは生成されたデータの概要をテキストエリアに表示する。
        """
        self.data_summary_text.config(state='normal')
        self.data_summary_text.delete(1.0, tk.END)
        
        summary = "--- データ概要 ---\n"
        summary += f"セミナー数: {len(self.seminars_data)}\n"
        if self.seminars_data:
            summary += "  セミナーID例: " + ", ".join([s['id'] for s in self.seminars_data[:3]]) + ("..." if len(self.seminars_data) > 3 else "") + "\n"
        
        summary += f"学生数: {len(self.students_data)}\n"
        if self.students_data:
            summary += "  学生ID例: " + ", ".join([s['id'] for s in self.students_data[:3]]) + ("..." if len(self.students_data) > 3 else "") + "\n"

        # セミナーIDリストを更新
        if self.seminars_data:
            seminar_ids = [s['id'] for s in self.seminars_data]
            self.seminar_ids_var.set(",".join(seminar_ids))
            summary += "  全セミナーID: " + self.seminar_ids_var.get() + "\n"
        else:
            self.seminar_ids_var.set("")

        self.data_summary_text.insert(tk.END, summary)
        self.data_summary_text.config(state='disabled')
        logger.debug("DataInputTab: データ概要を更新しました。")

    def get_current_settings_for_main_app(self) -> Dict[str, Any]:
        """
        MainApplicationに保存するためのDataInputTabの現在の設定値を取得します。
        """
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
            "max_preferences": self.num_preferences_to_consider_var.get(), # max_preferencesとして返す
            "min_preferences": self.min_preferences_var.get(),
            "students_file_path": self.students_file_path_var.get(),
            "seminars_file_path": self.seminars_file_path_var.get(),
            "config_file_path": self.config_file_path_var.get(), # config.jsonのパスも保存対象に含める
        }

    def get_seminars_data(self) -> List[Dict[str, Any]]:
        """
        現在ロードまたは生成されているセミナーデータを返す。
        """
        return self.seminars_data

    def get_students_data(self) -> List[Dict[str, Any]]:
        """
        現在ロードまたは生成されている学生データを返す。
        """
        return self.students_data
