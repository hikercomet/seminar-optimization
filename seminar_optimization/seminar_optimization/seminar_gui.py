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

# logging設定をここで一元化
# 他のモジュールがbasicConfigを呼ばないように注意
if not logging.root.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) # loggerの定義をここへ移動

# sys.pathにプロジェクトのルートディレクトリを追加し、
# seminar_optimization パッケージを見つけられるようにする。
# 想定される一般的なプロジェクト構造:
# some_parent_directory/
# ├── seminar_optimization/  <- このディレクトリがPythonパッケージのルート (__init__.py, optimizers/, utils/ を含む)
# │   ├── __init__.py
# │   ├── optimizers/
# │   │   └── optimizer_service.py
# │   ├── utils.py
# │   └── seminar_gui.py     <- seminar_gui.py がここにある場合
# └── (その他のファイルやフォルダ)

# 現在のスクリプト (seminar_gui.py) のディレクトリを取得
script_dir = os.path.dirname(os.path.abspath(__file__))

# プロジェクトルートを、seminar_gui.py の場所から2つ上のディレクトリとして直接設定します。
# 例: C:/Users/hiker/seminar_optimization/seminar_optimization/seminar_optimization/seminar_gui.py から見て、
# プロジェクトルートは C:/Users/hiker/seminar_optimization になります。
project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))

if project_root not in sys.path:
    sys.path.insert(0, project_root)
    logger.info(f"'{project_root}' を sys.path に追加しました。")
else:
    logger.info(f"'{project_root}' は既に sys.path に存在します。")


# optimizer_serviceとDataLoaderをインポート
try:
    # プロジェクトルートがsys.pathに追加されたので、絶対インポートで optimizers.optimizer_service を参照
    from seminar_optimization.optimizers.optimizer_service import run_optimization_service, DataLoader
    # utils.pyがseminar_optimizationパッケージ内に移動されたため、絶対インポートに変更
    from seminar_optimization.utils import OptimizationResult # utils.OptimizationResult をインポート
except ImportError as e:
    messagebox.showerror("エラー", f"モジュールのインポートに失敗しました: {e}\n\n考えられる原因:\n1. Pythonのパス設定が正しくない。\n2. 'seminar_optimization' パッケージの構造が想定と異なる。\n3. 特に 'utils.py' が 'seminar_optimization' パッケージ内にない可能性があります。\n\nプロジェクトのルートディレクトリ ('{project_root}') と、各モジュールのファイルパスを確認してください。")
    sys.exit(1)

# DPI設定 (Windowsのみ)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except AttributeError:
    pass # Not on Windows or old Windows version


class InputValidator:
    """
    GUIの入力値の検証を行うクラス。
    """
    @staticmethod
    def validate_settings(gui_instance) -> bool:
        """
        設定タブの入力値検証ロジック。
        スピンボックスの範囲チェックなどをここで行う。
        """
        try:
            # 各変数の値を取得し、必要に応じて型変換や範囲チェックを行う
            if not (1 <= gui_instance.num_seminars_var.get() <= 1000):
                messagebox.showerror("入力エラー", "セミナー数は1から1000の範囲で入力してください。")
                return False
            if not (1 <= gui_instance.min_capacity_var.get() <= 100):
                messagebox.showerror("入力エラー", "最小定員は1から100の範囲で入力してください。")
                return False
            if not (gui_instance.min_capacity_var.get() <= gui_instance.max_capacity_var.get()):
                messagebox.showerror("入力エラー", "最小定員は最大定員以下である必要があります。")
                return False
            if not (1 <= gui_instance.num_students_var.get() <= 10000):
                messagebox.showerror("入力エラー", "学生数は1から10000の範囲で入力してください。")
                return False
            if not (1 <= gui_instance.min_preferences_var.get() <= 10):
                messagebox.showerror("入力エラー", "最小希望数は1から10の範囲で入力してください。")
                return False
            if not (gui_instance.min_preferences_var.get() <= gui_instance.max_preferences_var.get()):
                messagebox.showerror("入力エラー", "最小希望数は最大希望数以下である必要があります。")
                return False

            return True # すべての検証が成功

        except tk.TclError as e: # Spinboxなどの入力エラーをキャッチ
            messagebox.showerror("入力エラー", f"数値入力が不正です: {e}")
            return False
        except Exception as e:
            messagebox.showerror("検証エラー", f"設定検証中にエラーが発生しました: {e}")
            return False

class ConfigManager:
    """
    GUI固有の設定をiniファイルで管理するクラス。
    """
    def __init__(self):
        self.config_file = "gui_settings.ini"
        self.config = configparser.ConfigParser()

    def load_gui_settings(self):
        """GUI設定をファイルから読み込む。"""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
            if 'GUI' in self.config:
                return self.config['GUI']
        return {}

    def save_gui_settings(self, settings: Dict[str, str]):
        """GUI設定をファイルに保存する。"""
        if 'GUI' not in self.config:
            self.config['GUI'] = {}
        for key, value in settings.items():
            self.config['GUI'][key] = str(value)
        with open(self.config_file, 'w') as f:
            self.config.write(f)

class ProgressDialog:
    """
    最適化処理の進捗を表示するダイアログ。
    """
    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("処理中...")
        self.dialog.geometry("400x150")
        self.dialog.transient(parent) # 親ウィンドウの前面に表示
        self.dialog.grab_set() # 他のウィンドウを操作できなくする
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_closing) # 閉じるボタンの無効化

        self.label = ttk.Label(self.dialog, text="最適化を開始しています...", wraplength=350)
        self.label.pack(pady=20)

        self.progress_bar = ttk.Progressbar(self.dialog, orient="horizontal", length=300, mode="indeterminate")
        self.progress_bar.pack(pady=10)

        # キャンセルボタン
        self.cancel_button = ttk.Button(self.dialog, text="キャンセル", command=self._on_cancel)
        self.cancel_button.pack(pady=5)
        self.cancel_callback: Optional[Callable[[], None]] = None

    def _on_closing(self):
        """ユーザーが閉じるボタンを押しても閉じないようにする。"""
        messagebox.showinfo("情報", "処理が完了するまでお待ちください。")

    def _on_cancel(self):
        """キャンセルボタンが押されたときの処理。"""
        if messagebox.askyesno("確認", "最適化処理をキャンセルしますか？"):
            if self.cancel_callback:
                self.cancel_callback()
            self.update_progress_message("キャンセル要求を送信しました...")
            self.cancel_button.config(state=tk.DISABLED, text="キャンセル中...")


    def start_progress_bar(self, initial_message: str = "処理中..."):
        """プログレスバーを開始し、初期メッセージを設定する。"""
        self.label.config(text=initial_message)
        self.progress_bar.start()
        self.dialog.update_idletasks() # UIを更新

    def update_progress_message(self, message: str):
        """プログレスメッセージを更新する。"""
        self.label.config(text=message)
        self.dialog.update_idletasks() # UIを更新

    def close(self):
        """プログレスダイアログを閉じる。"""
        if self.progress_bar.winfo_exists(): # ウィジェットが存在するか確認
            self.progress_bar.stop()
            self.dialog.destroy()
            self.parent.grab_release() # grabを解除

class SeminarGUI:
    """
    セミナー割り当て最適化ツールのメインGUIクラス。
    """
    def __init__(self, root):
        self.root = root
        self.root.title("セミナー割り当て最適化ツール")
        self.root.geometry("1000x800")

        self.config_manager = ConfigManager()
        self.gui_settings = self.config_manager.load_gui_settings()
        self.optimization_config = self._load_default_optimization_config() # config.jsonから読み込む
        
        self.optimization_thread: Optional[threading.Thread] = None
        self.cancel_event = threading.Event()
        self.progress_dialog: Optional[ProgressDialog] = None

        self._initialize_defaults() # GUIのデフォルト値を設定
        self._setup_ui()
        self._load_saved_settings() # 保存されたGUI設定をロード

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _load_default_optimization_config(self):
        """config.jsonから最適化のデフォルト設定を読み込む。"""
        # config.json は project_root/seminar_optimization/config/config.json にあると仮定
        config_path = os.path.join(project_root, 'seminar_optimization', 'config', 'config.json')
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"config.jsonが見つかりません: {config_path}。空の設定を使用します。")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"config.jsonのデコードエラー: {e}。空の設定を使用します。")
            return {}

    def _initialize_defaults(self):
        """GUIの入力フィールドのデフォルト値を設定。config.jsonの値を初期値として使用。"""
        self.num_seminars_var = tk.IntVar(value=self.optimization_config.get("num_seminars", 10))
        self.min_capacity_var = tk.IntVar(value=self.optimization_config.get("min_capacity", 5))
        self.max_capacity_var = tk.IntVar(value=self.optimization_config.get("max_capacity", 10))
        self.num_students_var = tk.IntVar(value=self.optimization_config.get("num_students", 50))
        self.min_preferences_var = tk.IntVar(value=self.optimization_config.get("min_preferences", 3))
        self.max_preferences_var = tk.IntVar(value=self.optimization_config.get("max_preferences", 5))
        self.preference_dist_var = tk.StringVar(value="random") # 新しいデータ生成オプション

        self.optimization_strategy_var = tk.StringVar(value=self.optimization_config.get("optimization_strategy", "Greedy_LS"))
        self.ga_population_size_var = tk.IntVar(value=self.optimization_config.get("ga_population_size", 100))
        self.ga_generations_var = tk.IntVar(value=self.optimization_config.get("ga_generations", 200))
        self.ilp_time_limit_var = tk.IntVar(value=self.optimization_config.get("ilp_time_limit", 300))
        self.cp_time_limit_var = tk.IntVar(value=self.optimization_config.get("cp_time_limit", 300))
        self.multilevel_clusters_var = tk.IntVar(value=self.optimization_config.get("multilevel_clusters", 5))
        self.greedy_ls_iterations_var = tk.IntVar(value=self.optimization_config.get("greedy_ls_iterations", 200000))
        self.local_search_iterations_var = tk.IntVar(value=self.optimization_config.get("local_search_iterations", 500))
        self.initial_temperature_var = tk.DoubleVar(value=self.optimization_config.get("initial_temperature", 1.0))
        self.cooling_rate_var = tk.DoubleVar(value=self.optimization_config.get("cooling_rate", 0.995))

        self.generate_pdf_report_var = tk.BooleanVar(value=self.optimization_config.get("generate_pdf_report", True))
        self.generate_csv_report_var = tk.BooleanVar(value=self.optimization_config.get("generate_csv_report", True))
        self.debug_mode_var = tk.BooleanVar(value=self.optimization_config.get("debug_mode", False))
        self.log_enabled_var = tk.BooleanVar(value=self.optimization_config.get("log_enabled", True))
        
        # データ入力方法の変数
        self.data_input_method_var = tk.StringVar(value="json") # "json", "csv", "generate", "manual"
        
        # config.jsonからデフォルトのファイルパスを設定
        # dataディレクトリは project_root/seminar_optimization/data にあると仮定
        default_data_dir = os.path.join(project_root, 'seminar_optimization', self.optimization_config.get('data_directory', 'data'))
        self.seminars_file_path_var = tk.StringVar(value=os.path.join(default_data_dir, self.optimization_config.get('seminars_file', 'seminars.json')))
        self.students_file_path_var = tk.StringVar(value=os.path.join(default_data_dir, self.optimization_config.get('students_file', 'students.json')))

        # 手動入力用データ格納
        self.manual_seminar_data: List[Dict[str, Any]] = []
        self.manual_student_data: List[Dict[str, Any]] = []
        self.manual_seminar_tree: Optional[ttk.Treeview] = None
        self.manual_student_tree: Optional[ttk.Treeview] = None

    def _setup_ui(self):
        """UIの主要な要素をセットアップする。"""
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(padx=10, pady=10, fill="both", expand=True)

        self._create_data_input_tab() # データ入力タブを一番最初に配置
        self._create_settings_tab()
        self._create_results_tab()
        self._create_logs_tab()

        # 最適化実行ボタンをNotebookの外に配置して常に表示させる
        control_frame = ttk.Frame(self.root, padding="10")
        control_frame.pack(fill="x")
        ttk.Button(control_frame, text="最適化を実行", command=self._run_optimization).pack(side="left", padx=5, pady=5)
        ttk.Button(control_frame, text="キャンセル", command=self._cancel_optimization).pack(side="right", padx=5, pady=5)


    def _create_data_input_tab(self):
        """データ入力タブを作成する。"""
        data_input_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(data_input_frame, text="データ入力")

        # データ入力方法の選択
        input_method_frame = ttk.LabelFrame(data_input_frame, text="データ入力方法の選択", padding="10")
        input_method_frame.pack(pady=10, fill="x")

        json_radio = ttk.Radiobutton(input_method_frame, text="JSONファイルから読み込む", variable=self.data_input_method_var, value="json", command=self._on_input_method_changed)
        json_radio.pack(anchor="w", pady=2)
        csv_radio = ttk.Radiobutton(input_method_frame, text="CSVファイルから読み込む", variable=self.data_input_method_var, value="csv", command=self._on_input_method_changed)
        csv_radio.pack(anchor="w", pady=2)
        generate_radio = ttk.Radiobutton(input_method_frame, text="自動生成する", variable=self.data_input_method_var, value="generate", command=self._on_input_method_changed)
        generate_radio.pack(anchor="w", pady=2)
        manual_radio = ttk.Radiobutton(input_method_frame, text="手動入力する", variable=self.data_input_method_var, value="manual", command=self._on_input_method_changed)
        manual_radio.pack(anchor="w", pady=2)

        # 各入力方法に対応するフレーム
        self.file_input_frame = ttk.Frame(data_input_frame)
        self.generate_input_frame = ttk.Frame(data_input_frame)
        self.manual_input_frame = ttk.Frame(data_input_frame)

        self._create_file_input_section(self.file_input_frame)
        self._create_generate_input_section(self.generate_input_frame)
        self._create_manual_input_section(self.manual_input_frame)

        self._on_input_method_changed() # 初期表示


    def _on_input_method_changed(self):
        """データ入力方法のラジオボタンが変更されたときに、対応するUIを表示/非表示する。"""
        # 全ての入力フレームを非表示にする
        self.file_input_frame.pack_forget()
        self.generate_input_frame.pack_forget()
        self.manual_input_frame.pack_forget()

        # 選択された入力方法に対応するフレームを表示
        selected_method = self.data_input_method_var.get()
        if selected_method == "json" or selected_method == "csv":
            self.file_input_frame.pack(pady=10, fill="x", expand=True)
        elif selected_method == "generate":
            self.generate_input_frame.pack(pady=10, fill="x", expand=True)
        elif selected_method == "manual":
            self.manual_input_frame.pack(pady=10, fill="both", expand=True) # expand=True for manual table

    def _create_file_input_section(self, parent_frame):
        """ファイル入力セクション (JSON/CSV共通) を作成する。"""
        file_frame = ttk.LabelFrame(parent_frame, text="ファイルパス", padding="10")
        file_frame.pack(fill="x", expand=True)

        ttk.Label(file_frame, text="セミナーファイル:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        seminars_entry = ttk.Entry(file_frame, textvariable=self.seminars_file_path_var, width=50)
        seminars_entry.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(file_frame, text="参照...", command=lambda: self._browse_file(self.seminars_file_path_var, "seminars")).grid(row=0, column=2, padx=5, pady=5)

        ttk.Label(file_frame, text="学生ファイル:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        students_entry = ttk.Entry(file_frame, textvariable=self.students_file_path_var, width=50)
        students_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")
        ttk.Button(file_frame, text="参照...", command=lambda: self._browse_file(self.students_file_path_var, "students")).grid(row=1, column=2, padx=5, pady=5)

        file_frame.grid_columnconfigure(1, weight=1)
    
    def _browse_file(self, var: tk.StringVar, file_type: str):
        """ファイル参照ダイアログを開き、選択されたファイルパスを変数に設定する。"""
        filetypes = []
        selected_method = self.data_input_method_var.get()
        if selected_method == "json":
            filetypes = [("JSON files", "*.json"), ("All files", "*.*")]
        elif selected_method == "csv":
            filetypes = [("CSV files", "*.csv"), ("All files", "*.*")]
        
        initial_dir = os.path.dirname(var.get()) if var.get() else os.path.join(project_root, 'seminar_optimization', 'data')
        
        filepath = filedialog.askopenfilename(
            title=f"{file_type}ファイルを指定してください",
            initialdir=initial_dir,
            filetypes=filetypes
        )
        if filepath:
            var.set(filepath)

    def _create_generate_input_section(self, parent_frame):
        """データ自動生成セクションを作成する。"""
        generate_frame = ttk.LabelFrame(parent_frame, text="データ自動生成設定", padding="10")
        generate_frame.pack(fill="x", expand=True)

        row = 0
        ttk.Label(generate_frame, text="セミナー数:").grid(row=row, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=1000, textvariable=self.num_seminars_var, width=10).grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        row += 1

        ttk.Label(generate_frame, text="最小定員:").grid(row=row, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=100, textvariable=self.min_capacity_var, width=10).grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        row += 1

        ttk.Label(generate_frame, text="最大定員:").grid(row=row, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=100, textvariable=self.max_capacity_var, width=10).grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        row += 1

        ttk.Label(generate_frame, text="学生数:").grid(row=row, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=10000, textvariable=self.num_students_var, width=10).grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        row += 1

        ttk.Label(generate_frame, text="最小希望数:").grid(row=row, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=10, textvariable=self.min_preferences_var, width=10).grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        row += 1

        ttk.Label(generate_frame, text="最大希望数:").grid(row=row, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=10, textvariable=self.max_preferences_var, width=10).grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        row += 1

        ttk.Label(generate_frame, text="希望分布:").grid(row=row, column=0, padx=5, pady=2, sticky="w")
        dist_options = ["random", "uniform", "biased"]
        ttk.Combobox(generate_frame, textvariable=self.preference_dist_var, values=dist_options, state="readonly", width=10).grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        row += 1

        generate_frame.grid_columnconfigure(1, weight=1)

    def _create_manual_input_section(self, parent_frame):
        """手動入力セクションを作成する。"""
        manual_frame = ttk.LabelFrame(parent_frame, text="データ手動入力", padding="10")
        manual_frame.pack(fill="both", expand=True)

        self.manual_notebook = ttk.Notebook(manual_frame)
        self.manual_notebook.pack(padx=5, pady=5, fill="both", expand=True)

        # セミナー手動入力タブ
        seminar_manual_frame = ttk.Frame(self.manual_notebook, padding="10")
        self.manual_notebook.add(seminar_manual_frame, text="セミナー")
        self._create_manual_seminar_input(seminar_manual_frame)

        # 学生手動入力タブ
        student_manual_frame = ttk.Frame(self.manual_notebook, padding="10")
        self.manual_notebook.add(student_manual_frame, text="学生")
        self._create_manual_student_input(student_manual_frame)

    def _create_manual_seminar_input(self, parent_frame):
        """セミナーデータの手動入力UIを作成する。"""
        # セミナーデータ表示/入力ツリービュー
        seminar_tree_frame = ttk.Frame(parent_frame)
        seminar_tree_frame.pack(fill="both", expand=True)

        columns = ("ID", "定員")
        self.manual_seminar_tree = ttk.Treeview(seminar_tree_frame, columns=columns, show="headings")
        self.manual_seminar_tree.heading("ID", text="セミナーID")
        self.manual_seminar_tree.heading("定員", text="定員")
        self.manual_seminar_tree.column("ID", width=100)
        self.manual_seminar_tree.column("定員", width=80)
        self.manual_seminar_tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(seminar_tree_frame, orient="vertical", command=self.manual_seminar_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.manual_seminar_tree.configure(yscrollcommand=scrollbar.set)

        # 入力フォーム
        input_frame = ttk.Frame(parent_frame)
        input_frame.pack(fill="x", pady=10)

        ttk.Label(input_frame, text="ID:").grid(row=0, column=0, padx=5)
        self.seminar_id_entry = ttk.Entry(input_frame, width=15)
        self.seminar_id_entry.grid(row=0, column=1, padx=5)

        ttk.Label(input_frame, text="定員:").grid(row=0, column=2, padx=5)
        self.seminar_capacity_entry = ttk.Spinbox(input_frame, from_=1, to=1000, width=10)
        self.seminar_capacity_entry.grid(row=0, column=3, padx=5)

        add_button = ttk.Button(input_frame, text="追加/更新", command=self._add_or_update_seminar)
        add_button.grid(row=0, column=4, padx=5)
        remove_button = ttk.Button(input_frame, text="削除", command=self._remove_seminar)
        remove_button.grid(row=0, column=5, padx=5)

        self._populate_manual_seminar_tree()

    def _populate_manual_seminar_tree(self):
        """手動入力セミナーツリービューを更新する。"""
        for item in self.manual_seminar_tree.get_children():
            self.manual_seminar_tree.delete(item)
        for seminar in self.manual_seminar_data:
            self.manual_seminar_tree.insert("", "end", values=(seminar['id'], seminar['capacity']))

    def _add_or_update_seminar(self):
        """手動入力セミナーを追加または更新する。"""
        seminar_id = self.seminar_id_entry.get().strip()
        capacity_str = self.seminar_capacity_entry.get().strip()
        if not seminar_id or not capacity_str:
            messagebox.showwarning("入力エラー", "セミナーIDと定員を入力してください。")
            return
        try:
            capacity = int(capacity_str)
            if capacity <= 0:
                messagebox.showwarning("入力エラー", "定員は正の整数である必要があります。")
                return
        except ValueError:
            messagebox.showwarning("入力エラー", "定員は数値で入力してください。")
            return

        # 既存のセミナーを更新するか、新規追加する
        found = False
        for seminar in self.manual_seminar_data:
            if seminar['id'] == seminar_id:
                seminar['capacity'] = capacity
                found = True
                break
        if not found:
            self.manual_seminar_data.append({'id': seminar_id, 'capacity': capacity})
        
        self._populate_manual_seminar_tree()
        self.seminar_id_entry.delete(0, tk.END)
        self.seminar_capacity_entry.delete(0, tk.END)
        self.seminar_capacity_entry.insert(0, "10") # デフォルト値に戻す

    def _remove_seminar(self):
        """手動入力セミナーを削除する。"""
        selected_items = self.manual_seminar_tree.selection()
        if not selected_items:
            messagebox.showwarning("選択エラー", "削除するセミナーを選択してください。")
            return
        
        for item in selected_items:
            seminar_id_to_remove = self.manual_seminar_tree.item(item, "values")[0]
            self.manual_seminar_data = [s for s in self.manual_seminar_data if s['id'] != seminar_id_to_remove]
        self._populate_manual_seminar_tree()

    def _create_manual_student_input(self, parent_frame):
        """学生データの手動入力UIを作成する。"""
        # 学生データ表示/入力ツリービュー
        student_tree_frame = ttk.Frame(parent_frame)
        student_tree_frame.pack(fill="both", expand=True)

        columns = ("ID", "希望セミナー")
        self.manual_student_tree = ttk.Treeview(student_tree_frame, columns=columns, show="headings")
        self.manual_student_tree.heading("ID", text="学生ID")
        self.manual_student_tree.heading("希望セミナー", text="希望セミナー（カンマ区切り）")
        self.manual_student_tree.column("ID", width=100)
        self.manual_student_tree.column("希望セミナー", width=300)
        self.manual_student_tree.pack(side="left", fill="both", expand=True)

        scrollbar = ttk.Scrollbar(student_tree_frame, orient="vertical", command=self.manual_student_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.manual_student_tree.configure(yscrollcommand=scrollbar.set)

        # 入力フォーム
        input_frame = ttk.Frame(parent_frame)
        input_frame.pack(fill="x", pady=10)

        ttk.Label(input_frame, text="ID:").grid(row=0, column=0, padx=5)
        self.student_id_entry = ttk.Entry(input_frame, width=15)
        self.student_id_entry.grid(row=0, column=1, padx=5)

        ttk.Label(input_frame, text="希望:").grid(row=0, column=2, padx=5)
        self.student_preferences_entry = ttk.Entry(input_frame, width=40)
        self.student_preferences_entry.grid(row=0, column=3, padx=5)
        ttk.Label(input_frame, text="(例: S001,S002,S003)").grid(row=0, column=4, padx=5, sticky="w")


        add_button = ttk.Button(input_frame, text="追加/更新", command=self._add_or_update_student)
        add_button.grid(row=1, column=0, columnspan=2, pady=5)
        remove_button = ttk.Button(input_frame, text="削除", command=self._remove_student)
        remove_button.grid(row=1, column=2, columnspan=2, pady=5)
        
        self._populate_manual_student_tree()

    def _populate_manual_student_tree(self):
        """手動入力学生ツリービューを更新する。"""
        for item in self.manual_student_tree.get_children():
            self.manual_student_tree.delete(item)
        for student in self.manual_student_data:
            self.manual_student_tree.insert("", "end", values=(student['id'], ", ".join(student['preferences'])))

    def _add_or_update_student(self):
        """手動入力学生を追加または更新する。"""
        student_id = self.student_id_entry.get().strip()
        preferences_str = self.student_preferences_entry.get().strip()
        if not student_id:
            messagebox.showwarning("入力エラー", "学生IDを入力してください。")
            return
        
        preferences = [p.strip() for p in preferences_str.split(',') if p.strip()]
        
        if not preferences:
            messagebox.showwarning("入力エラー", "希望セミナーを入力してください。")
            return

        # 既存の学生を更新するか、新規追加する
        found = False
        for student in self.manual_student_data:
            if student['id'] == student_id:
                student['preferences'] = preferences
                found = True
                break
        if not found:
            self.manual_student_data.append({'id': student_id, 'preferences': preferences})
        
        self._populate_manual_student_tree()
        self.student_id_entry.delete(0, tk.END)
        self.student_preferences_entry.delete(0, tk.END)

    def _remove_student(self):
        """手動入力学生を削除する。"""
        selected_items = self.manual_student_tree.selection()
        if not selected_items:
            messagebox.showwarning("選択エラー", "削除する学生を選択してください。")
            return
        
        for item in selected_items:
            student_id_to_remove = self.manual_student_tree.item(item, "values")[0]
            self.manual_student_data = [s for s in self.manual_student_data if s['id'] != student_id_to_remove]
        self._populate_manual_student_tree()

    def _create_settings_tab(self):
        """設定タブを作成する。"""
        settings_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(settings_frame, text="設定")

        # 各最適化戦略の設定をグループ化
        strategy_frame = ttk.LabelFrame(settings_frame, text="最適化戦略の選択", padding="10")
        strategy_frame.pack(pady=10, fill="x")

        strategy_options = ["Greedy_LS", "GA_LS", "ILP", "CP", "Multilevel", "Adaptive"]
        strategy_menu = ttk.OptionMenu(strategy_frame, self.optimization_strategy_var, self.optimization_strategy_var.get(), *strategy_options)
        strategy_menu.pack(padx=5, pady=5, anchor="w")

        # GA_LS設定
        ga_frame = ttk.LabelFrame(settings_frame, text="遺伝的アルゴリズム (GA_LS) 設定", padding="10")
        ga_frame.pack(pady=10, fill="x")
        self._create_setting_row(ga_frame, "個体群サイズ:", self.ga_population_size_var, 0, min_val=10, max_val=1000)
        self._create_setting_row(ga_frame, "世代数:", self.ga_generations_var, 1, min_val=10, max_val=1000)

        # ILP/CP設定
        ilp_cp_frame = ttk.LabelFrame(settings_frame, text="ILP/CP 設定", padding="10")
        ilp_cp_frame.pack(pady=10, fill="x")
        self._create_setting_row(ilp_cp_frame, "ILPタイムリミット (秒):", self.ilp_time_limit_var, 0, min_val=1, max_val=3600)
        self._create_setting_row(ilp_cp_frame, "CPタイムリミット (秒):", self.cp_time_limit_var, 1, min_val=1, max_val=3600)

        # 多段階最適化設定
        multilevel_frame = ttk.LabelFrame(settings_frame, text="多段階最適化 設定", padding="10")
        multilevel_frame.pack(pady=10, fill="x")
        self._create_setting_row(multilevel_frame, "クラスタ数:", self.multilevel_clusters_var, 0, min_val=1, max_val=20)

        # 共通の局所探索設定
        ls_frame = ttk.LabelFrame(settings_frame, text="局所探索設定", padding="10")
        ls_frame.pack(pady=10, fill="x")
        self._create_setting_row(ls_frame, "Greedy LS イテレーション:", self.greedy_ls_iterations_var, 0, min_val=100, max_val=1000000, step=100)
        self._create_setting_row(ls_frame, "局所探索イテレーション:", self.local_search_iterations_var, 1, min_val=10, max_val=10000)
        self._create_setting_row(ls_frame, "初期温度 (焼きなまし):", self.initial_temperature_var, 2, is_double=True, min_val=0.01, max_val=100.0)
        self._create_setting_row(ls_frame, "冷却率 (焼きなまし):", self.cooling_rate_var, 3, is_double=True, min_val=0.001, max_val=0.9999)

        # レポート設定
        report_frame = ttk.LabelFrame(settings_frame, text="レポート設定", padding="10")
        report_frame.pack(pady=10, fill="x")
        ttk.Checkbutton(report_frame, text="PDFレポートを生成", variable=self.generate_pdf_report_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(report_frame, text="CSVレポートを生成", variable=self.generate_csv_report_var).pack(anchor="w", pady=2)

        # デバッグ/ロギング設定
        debug_frame = ttk.LabelFrame(settings_frame, text="デバッグ/ロギング", padding="10")
        debug_frame.pack(pady=10, fill="x")
        ttk.Checkbutton(debug_frame, text="デバッグモード", variable=self.debug_mode_var).pack(anchor="w", pady=2)
        ttk.Checkbutton(debug_frame, text="ログ出力", variable=self.log_enabled_var).pack(anchor="w", pady=2)


    def _create_setting_row(self, parent_frame, label_text, tk_var, row, min_val=None, max_val=None, step=1, is_double=False):
        """設定項目の行をGUIに作成するヘルパー関数。"""
        ttk.Label(parent_frame, text=label_text).grid(row=row, column=0, padx=5, pady=2, sticky="w")
        if is_double:
            entry = ttk.Spinbox(parent_frame, from_=min_val, to=max_val, increment=step, textvariable=tk_var, width=15, format="%.3f")
        else:
            entry = ttk.Spinbox(parent_frame, from_=min_val, to=max_val, increment=step, textvariable=tk_var, width=15)
        entry.grid(row=row, column=1, padx=5, pady=2, sticky="ew")
        parent_frame.grid_column_configure(1, weight=1)

    def _create_results_tab(self):
        """結果表示タブを作成する。"""
        results_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(results_frame, text="結果")

        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD, state=tk.DISABLED, width=80, height=20)
        self.results_text.pack(padx=5, pady=5, fill="both", expand=True)

    def _create_logs_tab(self):
        """ログ表示タブを作成する。"""
        logs_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(logs_frame, text="ログ")

        self.log_text = scrolledtext.ScrolledText(logs_frame, wrap=tk.WORD, state=tk.DISABLED, width=80, height=20)
        self.log_text.pack(padx=5, pady=5, fill="both", expand=True)

        # カスタムハンドラを設定して、ログメッセージをScrolledTextにリダイレクト
        log_handler = TextHandler(self.log_text)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        log_handler.setFormatter(formatter)
        logging.getLogger().addHandler(log_handler) # ルートロガーに追加


    def _load_saved_settings(self):
        """保存されたGUI設定をロードし、UIに適用する。"""
        # 現在はファイルパスのみ
        if 'seminars_file_path' in self.gui_settings:
            self.seminars_file_path_var.set(self.gui_settings['seminars_file_path'])
        if 'students_file_path' in self.gui_settings:
            self.students_file_path_var.set(self.gui_settings['students_file_path'])
        if 'data_input_method' in self.gui_settings:
            self.data_input_method_var.set(self.gui_settings['data_input_method'])
            self._on_input_method_changed() # UIを更新

    def _save_current_settings(self):
        """現在のGUI設定を保存する。"""
        settings_to_save = {
            'seminars_file_path': self.seminars_file_path_var.get(),
            'students_file_path': self.students_file_path_var.get(),
            'data_input_method': self.data_input_method_var.get(),
            # 他のGUI設定変数があればここに追加
        }
        self.config_manager.save_gui_settings(settings_to_save)


    def _run_optimization(self):
        """最適化処理を開始する。"""
        if self.optimization_thread and self.optimization_thread.is_alive():
            messagebox.showinfo("情報", "最適化処理が既に実行中です。")
            return

        # GUIの設定値バリデーション
        if not InputValidator.validate_settings(self):
            return

        # 進捗ダイアログを閉じる (もし開いている場合)
        if self.progress_dialog and self.progress_dialog.dialog.winfo_exists():
            self.progress_dialog.close()

        self.progress_dialog = ProgressDialog(self.root)
        self.progress_dialog.cancel_callback = self._cancel_optimization # キャンセルボタンにコールバックを設定
        self.cancel_event.clear() # イベントをリセット

        selected_method = self.data_input_method_var.get()
        seminars_data: List[Dict[str, Any]] = []
        students_data: List[Dict[str, Any]] = []
        data_loader = DataLoader(self.optimization_config) # データローダーインスタンス化

        try:
            if selected_method == "json":
                seminars_file = self.seminars_file_path_var.get()
                students_file = self.students_file_path_var.get()
                if not seminars_file or not students_file:
                    raise ValueError("JSONファイルパスが指定されていません。")
                seminars_data, students_data = data_loader.load_from_json(seminars_file, students_file)
            elif selected_method == "csv":
                seminars_file = self.seminars_file_path_var.get()
                students_file = self.students_file_path_var.get()
                if not seminars_file or not students_file:
                    raise ValueError("CSVファイルパスが指定されていません。")
                seminars_data, students_data = data_loader.load_from_csv(seminars_file, students_file)
            elif selected_method == "generate":
                seminars_data, students_data = data_loader.generate_data(
                    num_seminars=self.num_seminars_var.get(),
                    min_capacity=self.min_capacity_var.get(),
                    max_capacity=self.max_capacity_var.get(),
                    num_students=self.num_students_var.get(),
                    min_preferences=self.min_preferences_var.get(),
                    max_preferences=self.max_preferences_var.get(),
                    preference_distribution=self.preference_dist_var.get()
                )
            elif selected_method == "manual":
                seminars_data = self.manual_seminar_data
                students_data = self.manual_student_data
                if not seminars_data or not students_data:
                    raise ValueError("手動入力データが不足しています。セミナーと学生のデータを入力してください。")
                # 手動入力データもDataLoaderのスキーマで検証
                data_loader._validate_data(seminars_data, students_data)
            
            # データが正常に準備されたら、configを構築して最適化を開始
            self._update_optimization_config_from_gui() # GUIからconfigを更新
            
            self.optimization_thread = threading.Thread(
                target=self._run_optimization_thread,
                args=(seminars_data, students_data, self.optimization_config, self.cancel_event, self._update_progress)
            )
            self.optimization_thread.start()
            self.progress_dialog.start_progress_bar(f"最適化開始中: {self.optimization_strategy_var.get()}")
            self.root.after(100, self._check_optimization_thread)

        except Exception as e:
            messagebox.showerror("データ準備エラー", f"データの準備中にエラーが発生しました: {e}")
            logger.exception("データの準備中にエラーが発生しました。")
            if self.progress_dialog:
                self.progress_dialog.close()

    def _cancel_optimization(self):
        """最適化処理をキャンセルする。"""
        self.cancel_event.set() # キャンセルイベントを設定
        logger.info("ユーザーによって最適化がキャンセルされました。")
        if self.progress_dialog:
            self.progress_dialog.update_progress_message("キャンセル中です。しばらくお待ちください...")

    def _update_optimization_config_from_gui(self):
        """GUIの現在の設定をself.optimization_configに反映する"""
        self.optimization_config["optimization_strategy"] = self.optimization_strategy_var.get()
        self.optimization_config["ga_population_size"] = self.ga_population_size_var.get()
        self.optimization_config["ga_generations"] = self.ga_generations_var.get()
        self.optimization_config["ilp_time_limit"] = self.ilp_time_limit_var.get()
        self.optimization_config["cp_time_limit"] = self.cp_time_limit_var.get()
        self.optimization_config["multilevel_clusters"] = self.multilevel_clusters_var.get()
        self.optimization_config["greedy_ls_iterations"] = self.greedy_ls_iterations_var.get()
        self.optimization_config["local_search_iterations"] = self.local_search_iterations_var.get()
        self.optimization_config["initial_temperature"] = self.initial_temperature_var.get()
        self.optimization_config["cooling_rate"] = self.cooling_rate_var.get()
        self.optimization_config["generate_pdf_report"] = self.generate_pdf_report_var.get()
        self.optimization_config["generate_csv_report"] = self.generate_csv_report_var.get()
        self.optimization_config["debug_mode"] = self.debug_mode_var.get()
        self.optimization_config["log_enabled"] = self.log_enabled_var.get()
        
        # データ生成関連のパラメータもconfigに含める
        self.optimization_config["num_seminars"] = self.num_seminars_var.get()
        self.optimization_config["min_capacity"] = self.min_capacity_var.get()
        self.optimization_config["max_capacity"] = self.max_capacity_var.get()
        self.optimization_config["num_students"] = self.num_students_var.get()
        self.optimization_config["min_preferences"] = self.min_preferences_var.get()
        self.optimization_config["max_preferences"] = self.max_preferences_var.get()
        # preference_weightsは通常config.jsonで固定されるが、GUIで設定可能にするならここに追加

    def _run_optimization_thread(self, seminars_data, students_data, config, cancel_event, progress_callback):
        """
        最適化サービスを別スレッドで実行する。
        """
        logger.info(f"最適化スレッド開始: データ数 (セミナー: {len(seminars_data)}, 学生: {len(students_data)})")
        try:
            results = run_optimization_service(
                seminars=seminars_data,
                students=students_data,
                config=config,
                cancel_event=cancel_event,
                progress_callback=progress_callback
            )
            # GUI更新はメインスレッドで行う
            self.root.after(0, self._handle_optimization_completion, results)
        except Exception as e:
            logger.exception("最適化スレッド内で予期せぬエラーが発生しました。")
            error_results = OptimizationResult( # utils.OptimizationResult を直接使用
                status="ERROR",
                message=f"最適化スレッドエラー: {e}",
                best_score=-1,
                best_assignment={},
                seminar_capacities={s['id']: s['capacity'] for s in seminars_data},
                unassigned_students=[],
                optimization_strategy=config.get("optimization_strategy", "Unknown")
            )
            self.root.after(0, self._handle_optimization_completion, error_results)
        finally:
            if self.progress_dialog:
                self.root.after(0, self.progress_dialog.close)


    def _check_optimization_thread(self):
        """最適化スレッドの終了を定期的にチェックする。"""
        if self.optimization_thread and self.optimization_thread.is_alive():
            self.root.after(100, self._check_optimization_thread)
        else:
            logger.info("最適化スレッドが終了しました。")
            # スレッドが終了した後の処理は _handle_optimization_completion で行われる


    def _update_progress(self, message: str):
        """プログレスバーとログにメッセージを更新するコールバック関数。"""
        if self.progress_dialog:
            self.root.after(0, lambda: self.progress_dialog.update_progress_message(message))
        self.root.after(0, lambda: self.log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n"))
        self.root.after(0, lambda: self.log_text.see(tk.END))

    def _handle_optimization_completion(self, results: OptimizationResult): # utils.OptimizationResult を直接使用
        """最適化完了後の処理（メインスレッドで実行）。"""
        if self.progress_dialog:
            self.progress_dialog.close() # プログレスダイアログを閉じる

        if results.status == "CANCELLED":
            messagebox.showinfo("最適化結果", results.message)
        elif results.status == "ERROR" or results.status == "FAILED" or results.status == "NO_SOLUTION_FOUND":
            messagebox.showerror("最適化エラー", results.message)
        else:
            messagebox.showinfo("最適化完了", results.message)
        
        self._display_results(results) # 結果タブに詳細を表示

    def _display_results(self, results: OptimizationResult): # utils.OptimizationResult を直接使用
        """最適化結果を結果タブに表示する。"""
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END)
        
        self.results_text.insert(tk.END, f"最適化結果\n")
        self.results_text.insert(tk.END, f"--------------------------\n")
        self.results_text.insert(tk.END, f"ステータス: {results.status}\n")
        self.results_text.insert(tk.END, f"メッセージ: {results.message}\n")
        self.results_text.insert(tk.END, f"最適化戦略: {results.optimization_strategy}\n")
        self.results_text.insert(tk.END, f"ベストスコア: {results.best_score:.2f}\n")
        
        # students_dataがGUIにロードされている場合にのみ正確な総学生数を表示
        total_students = len(self.manual_student_data) if self.data_input_method_var.get() == "manual" else self.num_students_var.get()
        self.results_text.insert(tk.END, f"割り当てられた学生数: {len(results.best_assignment)} / {total_students}\n")
        self.results_text.insert(tk.END, f"未割り当て学生数: {len(results.unassigned_students)}\n")
        
        if results.unassigned_students:
            self.results_text.insert(tk.END, f"未割り当て学生: {', '.join(results.unassigned_students)}\n")
        
        self.results_text.insert(tk.END, "\n--- 最適割り当て結果 ---\n")
        if results.best_assignment:
            for student_id, seminar_id in results.best_assignment.items():
                self.results_text.insert(tk.END, f"学生 {student_id}: セミナー {seminar_id}\n")
        else:
            self.results_text.insert(tk.END, "割り当て結果はありません。\n")

        self.results_text.config(state=tk.DISABLED)
        self.notebook.select(self.results_text.winfo_parent()) # 結果タブに切り替える


    def _on_closing(self):
        """ウィンドウを閉じるときの処理。最適化が実行中の場合は確認する。"""
        if self.optimization_thread and self.optimization_thread.is_alive():
            if messagebox.askyesno("確認", "最適化処理が実行中です。強制終了しますか？"):
                self.cancel_event.set() # キャンセルイベントを設定
                if self.progress_dialog and self.progress_dialog.dialog.winfo_exists():
                    self.progress_dialog.close()
                self.optimization_thread.join(timeout=1.0) # スレッドが終了するのを待つ（短い時間）
                self.root.destroy()
            else:
                return # ウィンドウを閉じない
        else:
            self._save_current_settings() # 終了時に設定を保存
            self.root.destroy()

    def run(self):
        """GUIのメインループを開始する。"""
        self.root.mainloop()

# ログをScrolledTextにリダイレクトするためのカスタムハンドラ
class TextHandler(logging.Handler):
    """
    ログメッセージをTkinterのScrolledTextウィジェットにリダイレクトするハンドラ。
    """
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget
        self.text_widget.config(state=tk.NORMAL) # ログ追加時に一時的に有効化

    def emit(self, record):
        """ログレコードを処理し、ウィジェットに挿入する。"""
        msg = self.format(record)
        self.text_widget.insert(tk.END, msg + "\n")
        self.text_widget.see(tk.END) # 最新のログが見えるようにスクロール
        self.text_widget.config(state=tk.DISABLED) # 再度無効化 (読み取り専用)

if __name__ == "__main__":
    # Ensure logging is configured only once at startup
    root = tk.Tk()
    app = SeminarGUI(root)
    app.run()
