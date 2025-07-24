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
    marker_files = ["pyproject.toml", "setup.py", "README.md", ".git"]
    
    # 上位ディレクトリを探索
    for parent in current_file_path.parents:
        for marker in marker_files:
            if (parent / marker).exists():
                return parent
        # または、特定のディレクトリ名がプロジェクトルートである場合
        if parent.name == "seminar_optimization":
            # seminar_optimization/seminar_optimization/gui.py のような構造を想定し、
            # その親がプロジェクトルートである可能性をチェック
            if (parent.parent / "config").is_dir() and (parent.parent / "data").is_dir():
                return parent.parent
            return parent # 直接 seminar_optimization がルートの場合

    # 見つからない場合は、スクリプトからの相対パスをフォールバックとして返す
    # gui.py が seminar_optimization/seminar_optimization/gui.py にある場合、
    # 3つ上の階層がプロジェクトルート
    fallback_root = current_file_path.parent.parent.parent
    return fallback_root

# プロジェクトルートを特定し、sys.path に追加
PROJECT_ROOT = get_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# --- ロギング設定 ---
# seminar_optimization.seminar_optimization.logger_config からインポート
try:
    from seminar_optimization.seminar_optimization.logger_config import setup_logging, logger
except ImportError as e:
    print(f"logger_configのインポートエラー: {e}")
    print("デフォルトのロギング設定を使用します。")
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

# --- アプリケーション固有のモジュールを絶対インポート ---
try:
    from seminar_optimization.optimizers.optimizer_service import run_optimization_service
    from seminar_optimization.seminar_optimization.data_generator import DataGenerator
    from seminar_optimization.seminar_optimization.utils import OptimizationResult
    from seminar_optimization.seminar_optimization.output_generator import save_csv_results, save_pdf_report
    from seminar_optimization.seminar_optimization.schemas import CONFIG_SCHEMA
    import jsonschema
except ImportError as e:
    logger.critical(f"Application specific module import error: {e}", exc_info=True)
    messagebox.showerror("Startup Error", f"Required modules not found. Application will exit.\nError: {e}")
    sys.exit(1)

# DPIスケーリングを有効にする（Windowsの場合）
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except AttributeError:
    pass # Windows以外では無視

# ログをScrolledTextにリダイレクトするためのカスタムハンドラ
class TextHandler(logging.Handler):
    """
    Handler to redirect log messages to a Tkinter ScrolledText widget.
    Supports color coding based on log level.
    """
    def __init__(self, text_widget, root_tk_instance):
        super().__init__()
        self.text_widget = text_widget
        self.root = root_tk_instance
        self.text_widget.config(state=tk.DISABLED)
        logger.debug("TextHandler: Initialized log handler for ScrolledText.")

        # Configure tags for log levels
        self.text_widget.tag_configure("DEBUG", foreground="gray")
        self.text_widget.tag_configure("INFO", foreground="black")
        self.text_widget.tag_configure("WARNING", foreground="orange")
        self.text_widget.tag_configure("ERROR", foreground="red")
        self.text_widget.tag_configure("CRITICAL", foreground="purple", font=("", 10, "bold"))

    def emit(self, record):
        msg = self.format(record)
        log_level_name = record.levelname # Get log level name

        if self.root.winfo_exists():
            # Tkinter GUI updates must be done in the main thread, so use root.after()
            self.root.after(0, self._insert_text, msg + "\n", log_level_name)
        else:
            print(msg) # Print to console if GUI is closed

    def _insert_text(self, msg, tag_name):
        # This method runs in the main thread
        if self.text_widget.winfo_exists():
            self.text_widget.config(state=tk.NORMAL)
            self.text_widget.insert(tk.END, msg, tag_name) # Apply tag
            self.text_widget.see(tk.END)
            self.text_widget.config(state=tk.DISABLED)

class InputValidator:
    """
    Class for validating GUI input values.
    """
    @staticmethod
    def validate_settings(gui_instance) -> bool:
        """
        Input validation logic for the settings tab.
        Performs range checks for spinbox values.
        """
        logger.debug("InputValidator: Starting validation of settings.")
        try:
            # Get values of each variable and perform type conversion and range checks as needed
            if not (1 <= gui_instance.num_seminars_var.get() <= 1000):
                messagebox.showerror("Input Error", "Number of seminars must be between 1 and 1000.")
                logger.warning(f"InputValidator: Number of seminars ({gui_instance.num_seminars_var.get()}) is out of range.")
                return False
            if not (1 <= gui_instance.min_capacity_var.get() <= 100):
                messagebox.showerror("Input Error", "Minimum capacity must be between 1 and 100.")
                logger.warning(f"InputValidator: Minimum capacity ({gui_instance.min_capacity_var.get()}) is out of range.")
                return False
            if not (gui_instance.min_capacity_var.get() <= gui_instance.max_capacity_var.get()):
                messagebox.showerror("Input Error", "Minimum capacity must be less than or equal to maximum capacity.")
                logger.warning(f"InputValidator: Minimum capacity ({gui_instance.min_capacity_var.get()}) is greater than maximum capacity ({gui_instance.max_capacity_var.get()}).")
                return False
            if not (1 <= gui_instance.num_students_var.get() <= 10000):
                messagebox.showerror("Input Error", "Number of students must be between 1 and 10000.")
                logger.warning(f"InputValidator: Number of students ({gui_instance.num_students_var.get()}) is out of range.")
                return False
            if not (1 <= gui_instance.min_preferences_var.get() <= 10):
                messagebox.showerror("Input Error", "Minimum number of preferences must be between 1 and 10.")
                logger.warning(f"InputValidator: Minimum preferences ({gui_instance.min_preferences_var.get()}) is out of range.")
                return False
            if not (gui_instance.min_preferences_var.get() <= gui_instance.max_preferences_var.get()):
                messagebox.showerror("Input Error", "Minimum preferences must be less than or equal to maximum preferences.")
                logger.warning(f"InputValidator: Minimum preferences ({gui_instance.min_preferences_var.get()}) is greater than maximum preferences ({gui_instance.max_preferences_var.get()}).")
                return False

            logger.info("InputValidator: All settings values are valid.")
            return True

        except tk.TclError as e:
            messagebox.showerror("Input Error", f"Invalid numeric input: {e}")
            logger.error(f"InputValidator: Numeric input error: {e}", exc_info=True)
            return False
        except Exception as e:
            messagebox.showerror("Validation Error", f"An unexpected error occurred during settings validation: {e}")
            logger.error(f"InputValidator: Unexpected error during settings validation: {e}", exc_info=True)
            return False

class ConfigManager:
    """
    Class to manage GUI-specific settings in an ini file.
    """
    def __init__(self):
        self.config_file = "gui_settings.ini"
        self.config = configparser.ConfigParser()
        logger.debug(f"ConfigManager: Initialized. Config file: {self.config_file}")

    def load_gui_settings(self):
        """Loads GUI settings from the file."""
        logger.debug(f"ConfigManager: Attempting to load GUI settings: {self.config_file}")
        if os.path.exists(self.config_file):
            self.config.read(self.config_file, encoding="utf-8")
            if 'GUI' in self.config:
                logger.info(f"ConfigManager: GUI settings loaded.")
                return self.config['GUI']
        logger.info("ConfigManager: GUI settings file not found or section missing. Using empty settings.")
        return {}

    def save_gui_settings(self, settings: Dict[str, str]):
        """Saves GUI settings to the file."""
        logger.debug(f"ConfigManager: Attempting to save GUI settings: {self.config_file}")
        if 'GUI' not in self.config:
            self.config['GUI'] = {}
            logger.debug("ConfigManager: Created 'GUI' section.")
        for key, value in settings.items():
            self.config['GUI'][key] = str(value)
            logger.debug(f"ConfigManager: Added/updated setting '{key}' = '{value}'.")
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                self.config.write(f)
            logger.info(f"ConfigManager: GUI settings successfully saved: {self.config_file}")
        except Exception as e:
            logger.error(f"ConfigManager: Error saving GUI settings: {e}", exc_info=True)


class ProgressDialog:
    """
    Dialog to display optimization progress as a circular graph.
    """
    def __init__(self, parent):
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Processing...")
        self.dialog.geometry("400x250")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_closing)
        logger.debug("ProgressDialog: Initialized progress dialog.")

        self.canvas = tk.Canvas(self.dialog, width=200, height=200, bg="white", highlightthickness=0)
        self.canvas.pack(pady=10)

        self.progress_text_id = self.canvas.create_text(100, 90, text="0%", font=("Yu Gothic UI", 24, "bold"), fill="black")
        self.process_text_id = self.canvas.create_text(100, 120, text="Preparing...", font=("Yu Gothic UI", 10), fill="black", wraplength=180)
        
        self.cancel_button = ttk.Button(self.dialog, text="Cancel", command=self._on_cancel)
        self.cancel_button.pack(pady=5)
        self.cancel_callback: Optional[Callable[[], None]] = None
        logger.debug("ProgressDialog: Placed UI elements.")

        self.progress_value = 0
        self.current_process_message = "Preparing..."

    def _on_closing(self):
        """Prevents the dialog from closing when the user clicks the close button."""
        logger.debug("ProgressDialog: Close button clicked.")
        messagebox.showinfo("Information", "Please wait until the process is complete.")
        logger.info("ProgressDialog: Displayed message to wait for process completion.")

    def _on_cancel(self):
        """Handles the cancel button click."""
        logger.debug("ProgressDialog: Cancel button clicked.")
        if messagebox.askyesno("Confirmation", "Do you want to cancel the optimization process?"):
            if self.cancel_callback:
                self.cancel_callback()
                logger.info("ProgressDialog: Called cancel callback.")
            self.update_progress_value(self.progress_value, "Sending cancel request...")
            self.cancel_button.config(state=tk.DISABLED, text="Cancelling...")
            logger.debug("ProgressDialog: Sent cancel request and disabled button.")
        else:
            logger.debug("ProgressDialog: Cancel denied by user.")

    def _draw_progress_circle(self):
        """Draws the circular graph on the Canvas."""
        self.canvas.delete("progress_arc") # Delete existing arc
        
        # Background circle
        self.canvas.create_oval(10, 10, 190, 190, outline="lightgray", width=5, tags="progress_arc")
        
        # Progress arc
        angle = int(self.progress_value * 3.6) # Convert 0-100% to 0-360 degrees
        self.canvas.create_arc(10, 10, 190, 190,
                               start=90, extent=-angle, # 0 degrees at top, draw clockwise
                               fill="#4CAF50", outline="#4CAF50", width=5, style=tk.ARC, tags="progress_arc")
        
        # Update text
        self.canvas.itemconfig(self.progress_text_id, text=f"{self.progress_value}%")
        self.canvas.itemconfig(self.process_text_id, text=self.current_process_message)
        logger.debug(f"ProgressDialog: Circular graph updated. Progress: {self.progress_value}%, Message: '{self.current_process_message}'")


    def start_progress_bar(self, initial_message: str = "Preparing..."):
        """Starts the progress dialog and sets the initial message."""
        self.progress_value = 0
        self.current_process_message = initial_message
        self.parent.after(0, self._draw_progress_circle) # Initial draw
        logger.info(f"ProgressDialog: Progress dialog started. Initial message: '{initial_message}'")

    def update_progress_value(self, value: int, message: str):
        """Updates the progress value and message, and redraws the Canvas."""
        self.progress_value = max(0, min(100, value)) # Clamp to 0-100%
        self.current_process_message = message
        self.parent.after(0, self._draw_progress_circle)
        logger.debug(f"ProgressDialog: Progress updated. Value: {value}%, Message: '{message}'")

    def close(self):
        """Closes the progress dialog."""
        logger.debug("ProgressDialog: Closing progress dialog.")
        if self.dialog.winfo_exists():
            self.parent.after(0, self.dialog.destroy)
            self.parent.after(0, self.parent.grab_release)
            logger.info("ProgressDialog: Progress dialog closed successfully.")
        else:
            logger.debug("ProgressDialog: Progress dialog is already closed.")

# Helper class to report progress from the optimization worker to the GUI
class ProgressReporter:
    def __init__(self, root_tk_instance: tk.Tk, progress_dialog: ProgressDialog, status_bar_callback: Callable[[str, str], None]):
        self.root = root_tk_instance
        self.progress_dialog = progress_dialog
        self.status_bar_callback = status_bar_callback
        logger.debug("ProgressReporter: Initialized.")

    def report_progress(self, percentage: int, message: str):
        """Reports progress to the ProgressDialog and status bar."""
        if self.progress_dialog and self.progress_dialog.dialog.winfo_exists():
            self.root.after(0, self.progress_dialog.update_progress_value, percentage, message)
        self.status_bar_callback(message, "info")
        logger.debug(f"Progress reported: {percentage}% - {message}")


class SeminarGUI:
    """
    Main GUI class for the seminar assignment optimization tool.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Seminar Assignment Optimization Tool")
        self.root.geometry("1200x800")
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        logger.debug("SeminarGUI: Initialized GUI window.")

        self.config_manager = ConfigManager()
        self.gui_settings = self.config_manager.load_gui_settings()
        self.optimization_config = self._load_default_optimization_config()
        
        self.optimization_thread: Optional[threading.Thread] = None
        self.cancel_event = threading.Event()
        self.progress_dialog: Optional[ProgressDialog] = None
        self.is_optimizing = False

        self.log_text: Optional[scrolledtext.ScrolledText] = None
        self.text_handler: Optional[TextHandler] = None
        self.status_bar_label: Optional[ttk.Label] = None # Status bar label

        # --- Theme settings ---
        self.theme_var = tk.StringVar(value=self.gui_settings.get("theme", "Default Light"))
        self.themes = {
            "Default Light": {
                "bg": "#f0f0f0", "fg": "black", "btn_bg": "#e0e0e0", "btn_fg": "black",
                "frame_bg": "#f0f0f0", "tree_bg": "white", "tree_fg": "black", "tree_select_bg": "#0078d7", "tree_select_fg": "white",
                "tree_alt_row_bg": "#f9f9f9", "tree_heading_bg": "#e0e0e0", "tree_heading_fg": "black",
                "status_bg_info": "#e0e0e0", "status_fg_info": "black",
                "status_bg_error": "#ffcccc", "status_fg_error": "red",
                "status_bg_warning": "#fffacd", "status_fg_warning": "orange"
            },
            "Dark Mode": {
                "bg": "#2e2e2e", "fg": "white", "btn_bg": "#4a4a4a", "btn_fg": "white",
                "frame_bg": "#3c3c3c", "tree_bg": "#3c3c3c", "tree_fg": "white", "tree_select_bg": "#0056b3", "tree_select_fg": "white",
                "tree_alt_row_bg": "#4a4a4a", "tree_heading_bg": "#4a4a4a", "tree_heading_fg": "white",
                "status_bg_info": "#4a4a4a", "status_fg_info": "white",
                "status_bg_error": "#8b0000", "status_fg_error": "white",
                "status_bg_warning": "#8b8b00", "status_fg_warning": "white"
            },
            "Ocean Blue": {
                "bg": "#e0f2f7", "fg": "#003366", "btn_bg": "#a7d9ed", "btn_fg": "#003366",
                "frame_bg": "#e0f2f7", "tree_bg": "#ffffff", "tree_fg": "#003366", "tree_select_bg": "#007bb6", "tree_select_fg": "white",
                "tree_alt_row_bg": "#f0f8ff", "tree_heading_bg": "#a7d9ed", "tree_heading_fg": "#003366",
                "status_bg_info": "#a7d9ed", "status_fg_info": "#003366",
                "status_bg_error": "#ff6347", "status_fg_error": "white",
                "status_bg_warning": "#ffd700", "status_fg_warning": "#003366"
            },
            "Forest Green": {
                "bg": "#e8f5e9", "fg": "#1b5e20", "btn_bg": "#a5d6a7", "btn_fg": "#1b5e20",
                "frame_bg": "#e8f5e9", "tree_bg": "#ffffff", "tree_fg": "#1b5e20", "tree_select_bg": "#4caf50", "tree_select_fg": "white",
                "tree_alt_row_bg": "#f1f8e9", "tree_heading_bg": "#a5d6a7", "tree_heading_fg": "#1b5e20",
                "status_bg_info": "#a5d6a7", "status_fg_info": "#1b5e20",
                "status_bg_error": "#dc143c", "status_fg_error": "white",
                "status_bg_warning": "#ff8c00", "status_fg_warning": "white"
            },
            "Warm Gray": {
                "bg": "#f5f5f5", "fg": "#424242", "btn_bg": "#e0e0e0", "btn_fg": "#424242",
                "frame_bg": "#f5f5f5", "tree_bg": "#ffffff", "tree_fg": "#424242", "tree_select_bg": "#757575", "tree_select_fg": "white",
                "tree_alt_row_bg": "#eeeeee", "tree_heading_bg": "#e0e0e0", "tree_heading_fg": "#424242",
                "status_bg_info": "#e0e0e0", "status_fg_info": "#424242",
                "status_bg_error": "#c0392b", "status_fg_error": "white",
                "status_bg_warning": "#f39c12", "status_fg_warning": "white"
            }
        }

        # Treeview sorting state
        self.seminar_sort_column: str = "ID"
        self.seminar_sort_direction: bool = True # True for ascending, False for descending
        self.student_sort_column: str = "ID"
        self.student_sort_direction: bool = True

        self._initialize_defaults()
        self._setup_ui()
        self._load_saved_settings()
        self._apply_theme() # Apply initial theme

        logger.info("SeminarGUI: Initialization complete.")
        self._update_status_bar("Application started. Ready for input.", "info")
        messagebox.showinfo("Startup Complete", "Application has started.")

    def _load_default_optimization_config(self):
        """Loads default optimization settings from config.json and validates schema."""
        config_path = PROJECT_ROOT / 'config' / 'config.json'
        logger.debug(f"SeminarGUI: Attempting to load config.json: {config_path}")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
                jsonschema.validate(instance=config_data, schema=CONFIG_SCHEMA)
                logger.info(f"SeminarGUI: config.json loaded and schema validated successfully.")
                return config_data
        except FileNotFoundError:
            logger.warning(f"SeminarGUI: config.json not found: {config_path}. Using empty settings.", exc_info=True)
            messagebox.showwarning("Config File Error", f"Config file '{config_path}' not found. Using default settings.")
            self._update_status_bar(f"Error: Config file '{config_path}' not found.", "error")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"SeminarGUI: config.json decode error: {e}. Using empty settings.", exc_info=True)
            messagebox.showerror("Config File Error", f"Config file '{config_path}' has invalid format: {e}. Using default settings.")
            self._update_status_bar(f"Error: Config file '{config_path}' has invalid format.", "error")
            return {}
        except jsonschema.exceptions.ValidationError as e:
            logger.error(f"SeminarGUI: config.json schema validation error: {e.message} (path: {'.'.join(map(str, e.path))}). Using empty settings.", exc_info=True)
            messagebox.showerror("Config File Error", f"Config file '{config_path}' content does not conform to schema: {e.message} (path: {'.'.join(map(str, e.path))}). Using default settings.")
            self._update_status_bar(f"Error: Config file '{config_path}' schema validation failed.", "error")
            return {}
        except Exception as e:
            logger.error(f"SeminarGUI: Unexpected error loading config.json: {e}", exc_info=True)
            messagebox.showerror("Config File Error", f"An unexpected error occurred while loading the config file: {e}. Using default settings.")
            self._update_status_bar(f"Error: Unexpected error loading config file.", "error")
            return {}

    def _initialize_defaults(self):
        """Sets default values for GUI input fields, using values from config.json as initial values."""
        logger.debug("SeminarGUI: Initializing default values for GUI input fields.")
        self.num_seminars_var = tk.IntVar(value=self.optimization_config.get("num_seminars", 10))
        self.min_capacity_var = tk.IntVar(value=self.optimization_config.get("min_capacity", 5))
        self.max_capacity_var = tk.IntVar(value=self.optimization_config.get("max_capacity", 10))
        self.num_students_var = tk.IntVar(value=self.optimization_config.get("num_students", 50))
        self.min_preferences_var = tk.IntVar(value=self.optimization_config.get("min_preferences", 3))
        self.max_preferences_var = tk.IntVar(value=self.optimization_config.get("max_preferences", 5))
        self.preference_dist_var = tk.StringVar(value=self.optimization_config.get("preference_distribution", "random"))

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
        self.random_seed_var = tk.IntVar(value=self.optimization_config.get("random_seed", 42))
        
        self.data_input_method_var = tk.StringVar(value=self.gui_settings.get("data_input_method", "generate_or_manual"))

        default_data_dir = PROJECT_ROOT / 'data'
        
        self.seminars_file_path_var = tk.StringVar(value=self.gui_settings.get('seminars_file_path', str(default_data_dir / self.optimization_config.get('seminars_file', 'seminars.json'))))
        self.students_file_path_var = tk.StringVar(value=self.gui_settings.get('students_file_path', str(default_data_dir / self.optimization_config.get('students_file', 'students.json'))))
        logger.debug(f"SeminarGUI: Default data file paths: Seminars='{self.seminars_file_path_var.get()}', Students='{self.students_file_path_var.get()}'")

        self.manual_seminar_data: List[Dict[str, Any]] = []
        self.manual_student_data: List[Dict[str, Any]] = []
        self.manual_seminar_tree: Optional[ttk.Treeview] = None
        self.manual_student_tree: Optional[ttk.Treeview] = None
        logger.debug("SeminarGUI: Initialized manual input data structures.")

        self.seminars_data_for_report: List[Dict[str, Any]] = []
        self.students_data_for_report: List[Dict[str, Any]] = []

    def _setup_ui(self):
        """Sets up the main UI elements."""
        logger.debug("SeminarGUI: Starting UI setup.")

        self.style = ttk.Style()
        self.style.theme_use('clam')

        # Main frame with Canvas + Scrollbar
        outer_frame = ttk.Frame(self.root)
        outer_frame.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(outer_frame, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(outer_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        # Create a Frame inside the Canvas
        self.main_frame = ttk.Frame(self.canvas)
        self.main_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        self.canvas.bind('<Configure>', self._on_canvas_configure)
        
        self.canvas_window = self.canvas.create_window((0, 0), window=self.main_frame, anchor="nw")

        # Bind mouse wheel for scrolling
        self.root.bind_all("<MouseWheel>", self._on_mousewheel) # Windows/macOS
        self.root.bind_all("<Button-4>", self._on_mousewheel)   # Linux (scroll up)
        self.root.bind_all("<Button-5>", self._on_mousewheel)   # Linux (scroll down)


        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(padx=10, pady=10, fill="both", expand=True)

        self._create_logs_tab()
        self._create_data_input_tab()
        self._create_settings_tab()
        self._create_results_tab()
        
        control_frame = ttk.Frame(self.main_frame, padding="10")
        control_frame.pack(fill="x")
        self.optimize_button = ttk.Button(control_frame, text="Run Optimization", command=self._run_optimization)
        self.optimize_button.pack(side="left", padx=5, pady=5)
        self.cancel_button = ttk.Button(control_frame, text="Cancel", command=self._cancel_optimization, state=tk.DISABLED)
        self.cancel_button.pack(side="right", padx=5, pady=5)

        # Status Bar
        self.status_bar_label = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor="w", font=('Yu Gothic UI', 9))
        self.status_bar_label.pack(side="bottom", fill="x")

        logger.info("SeminarGUI: UI setup complete.")

    def _on_canvas_configure(self, event):
        """Adjusts the width of the inner frame when the Canvas size changes."""
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        """Handles mouse wheel scrolling."""
        if sys.platform.startswith('win') or sys.platform == 'darwin': # Windows or macOS
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        elif sys.platform.startswith('linux'): # Linux
            if event.num == 4: # Scroll up
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5: # Scroll down
                self.canvas.yview_scroll(1, "units")

    def _apply_theme(self):
        """Applies the selected theme to the entire GUI."""
        theme_name = self.theme_var.get()
        theme_colors = self.themes.get(theme_name, self.themes["Default Light"])
        logger.debug(f"Applying theme: {theme_name}, Colors: {theme_colors}")

        # Tkinter Style settings (for ttk widgets)
        self.style.configure("TFrame", background=theme_colors["frame_bg"])
        self.style.configure("TLabel", background=theme_colors["frame_bg"], foreground=theme_colors["fg"])
        self.style.configure("TButton", background=theme_colors["btn_bg"], foreground=theme_colors["btn_fg"])
        self.style.map("TButton",
                       background=[('active', theme_colors["btn_bg"]), ('!disabled', theme_colors["btn_bg"])],
                       foreground=[('active', theme_colors["btn_fg"]), ('!disabled', theme_colors["btn_fg"])])
        self.style.configure("TLabelframe", background=theme_colors["frame_bg"])
        self.style.configure("TLabelframe.Label", background=theme_colors["frame_bg"], foreground=theme_colors["fg"])
        self.style.configure("TCheckbutton", background=theme_colors["frame_bg"], foreground=theme_colors["fg"])
        self.style.configure("TRadiobutton", background=theme_colors["frame_bg"], foreground=theme_colors["fg"])
        self.style.configure("TCombobox", fieldbackground=theme_colors["tree_bg"], foreground=theme_colors["fg"])
        self.style.map("TCombobox", fieldbackground=[('readonly', theme_colors["tree_bg"])])
        self.style.configure("TEntry", fieldbackground=theme_colors["tree_bg"], foreground=theme_colors["fg"])
        
        # Treeview style settings
        self.style.configure("Treeview",
                             background=theme_colors["tree_bg"],
                             foreground=theme_colors["tree_fg"],
                             fieldbackground=theme_colors["tree_bg"])
        self.style.map("Treeview",
                       background=[('selected', theme_colors["tree_select_bg"])],
                       foreground=[('selected', theme_colors["tree_select_fg"])])
        self.style.configure("Treeview.Heading",
                             background=theme_colors["tree_heading_bg"],
                             foreground=theme_colors["tree_heading_fg"])
        self.style.map("Treeview.Heading",
                       background=[('active', theme_colors["tree_heading_bg"])])

        # Tkinter widget background colors (not controllable by ttk.Style)
        self.root.config(bg=theme_colors["bg"])
        self.canvas.config(bg=theme_colors["bg"])
        self.main_frame.config(bg=theme_colors["bg"])
        self.notebook.config(bg=theme_colors["bg"])

        # Update ScrolledText background and foreground colors
        if self.log_text:
            self.log_text.config(bg=theme_colors["tree_bg"], fg=theme_colors["tree_fg"])
        if hasattr(self, 'results_text') and self.results_text:
            self.results_text.config(bg=theme_colors["tree_bg"], fg=theme_colors["tree_fg"])

        # Update ProgressDialog Canvas background color
        if self.progress_dialog and self.progress_dialog.canvas.winfo_exists():
            self.progress_dialog.canvas.config(bg=theme_colors["tree_bg"])
            self.progress_dialog.canvas.itemconfig(self.progress_dialog.progress_text_id, fill=theme_colors["fg"])
            self.progress_dialog.canvas.itemconfig(self.progress_dialog.process_text_id, fill=theme_colors["fg"])

        # Update notebook tab frames background color
        for tab_id in self.notebook.tabs():
            tab_frame = self.notebook.nametowidget(tab_id)
            if isinstance(tab_frame, ttk.Frame):
                tab_frame.config(background=theme_colors["frame_bg"])
        
        # Update status bar colors
        if self.status_bar_label:
            self.status_bar_label.config(background=theme_colors["status_bg_info"], foreground=theme_colors["status_fg_info"])

        logger.info(f"GUI theme changed to '{theme_name}'.")


    def _create_logs_tab(self):
        """Creates the log tab and sets up the logger handler."""
        logger.debug("SeminarGUI: Creating log tab.")
        logs_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(logs_frame, text="Logs")

        self.log_text = scrolledtext.ScrolledText(logs_frame, wrap=tk.WORD, state=tk.DISABLED, height=15, font=('Consolas', 9))
        self.log_text.pack(expand=True, fill="both")

        if not self.text_handler:
            self.text_handler = TextHandler(self.log_text, self.root)
            self.text_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logging.getLogger().addHandler(self.text_handler)
            logging.getLogger().setLevel(logging.DEBUG)
            logger.info("SeminarGUI: TextHandler configured for logger.")
        else:
            logger.debug("SeminarGUI: TextHandler is already configured.")

    def _create_data_input_tab(self):
        """Creates the data input tab."""
        logger.debug("SeminarGUI: Creating data input tab.")
        data_input_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(data_input_frame, text="Data Input")

        # Data input method selection
        input_method_frame = ttk.LabelFrame(data_input_frame, text="Select Data Input Method", padding="10")
        input_method_frame.pack(pady=10, fill="x")

        json_radio = ttk.Radiobutton(input_method_frame, text="Load from JSON file", variable=self.data_input_method_var, value="json_file", command=self._toggle_input_frames)
        json_radio.pack(anchor="w", padx=5, pady=2)
        
        generate_manual_radio = ttk.Radiobutton(input_method_frame, text="Manual Input / Generate Data", variable=self.data_input_method_var, value="generate_or_manual", command=self._toggle_input_frames)
        generate_manual_radio.pack(anchor="w", padx=5, pady=2)

        # Frames for each input method
        self.json_input_frame = ttk.LabelFrame(data_input_frame, text="JSON File Input", padding="10")
        self.manual_generate_frame = ttk.LabelFrame(data_input_frame, text="Data Generation / Manual Input", padding="10")

        self._setup_json_input_frame()
        self._setup_manual_input_frame()

        # Toggle display based on initial state
        self._toggle_input_frames()
        logger.info("SeminarGUI: Data input tab UI setup complete.")

    def _toggle_input_frames(self):
        """Toggles the visibility of input frames based on the selected data input method."""
        selected_method = self.data_input_method_var.get()
        logger.debug(f"Input method changed to: {selected_method}")

        if selected_method == "json_file":
            self.json_input_frame.pack(pady=10, fill="x", expand=True)
            self.manual_generate_frame.pack_forget()
            logger.debug("Displaying JSON file input frame.")
        elif selected_method == "generate_or_manual":
            self.manual_generate_frame.pack(pady=10, fill="x", expand=True)
            self.json_input_frame.pack_forget()
            logger.debug("Displaying data generation/manual input frame.")
        
        self._apply_theme() # Re-apply theme to ensure new frames have correct background colors

    def _setup_json_input_frame(self):
        """Sets up the UI for the JSON file input frame."""
        logger.debug("SeminarGUI: Setting up JSON file input frame UI.")
        # Seminar file path
        seminar_file_frame = ttk.Frame(self.json_input_frame)
        seminar_file_frame.pack(fill="x", pady=5)
        ttk.Label(seminar_file_frame, text="Seminar Data File:").pack(side="left", padx=5)
        self.seminar_file_entry = ttk.Entry(seminar_file_frame, textvariable=self.seminars_file_path_var, width=50)
        self.seminar_file_entry.pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(seminar_file_frame, text="Browse...", command=lambda: self._browse_file(self.seminars_file_path_var, [("JSON files", "*.json")])).pack(side="left", padx=5)

        # Student file path
        student_file_frame = ttk.Frame(self.json_input_frame)
        student_file_frame.pack(fill="x", pady=5)
        ttk.Label(student_file_frame, text="Student Data File:").pack(side="left", padx=5)
        self.student_file_entry = ttk.Entry(student_file_frame, textvariable=self.students_file_path_var, width=50)
        self.student_file_entry.pack(side="left", fill="x", expand=True, padx=5)
        ttk.Button(student_file_frame, text="Browse...", command=lambda: self._browse_file(self.students_file_path_var, [("JSON files", "*.json")])).pack(side="left", padx=5)
        logger.debug("JSON file input frame UI setup complete.")

    def _browse_file(self, path_var: tk.StringVar, filetypes: List[Tuple[str, str]]):
        """Opens a file dialog and sets the selected file path to the StringVar."""
        logger.debug("Opening file browse dialog.")
        filepath = filedialog.askopenfilename(filetypes=filetypes)
        if filepath:
            path_var.set(filepath)
            logger.info(f"File selected: {filepath}")
            self._update_status_bar(f"File selected: {os.path.basename(filepath)}", "info")
        else:
            logger.debug("File selection cancelled.")
            self._update_status_bar("File selection cancelled.", "info")

    def _setup_manual_input_frame(self):
        """Sets up the UI for the data generation/manual input frame."""
        logger.debug("SeminarGUI: Setting up data generation/manual input frame UI.")

        # Data generation settings
        generate_frame = ttk.LabelFrame(self.manual_generate_frame, text="Data Generation Settings", padding="10")
        generate_frame.pack(fill="x", pady=5)

        ttk.Label(generate_frame, text="Number of Seminars:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=1000, textvariable=self.num_seminars_var, width=8).grid(row=0, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(generate_frame, text="Min Capacity:").grid(row=0, column=2, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=100, textvariable=self.min_capacity_var, width=8).grid(row=0, column=3, padx=5, pady=2, sticky="w")
        ttk.Label(generate_frame, text="Max Capacity:").grid(row=0, column=4, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=100, textvariable=self.max_capacity_var, width=8).grid(row=0, column=5, padx=5, pady=2, sticky="w")

        ttk.Label(generate_frame, text="Number of Students:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=10000, textvariable=self.num_students_var, width=8).grid(row=1, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(generate_frame, text="Min Preferences:").grid(row=1, column=2, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=10, textvariable=self.min_preferences_var, width=8).grid(row=1, column=3, padx=5, pady=2, sticky="w")
        ttk.Label(generate_frame, text="Max Preferences:").grid(row=1, column=4, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=1, to=10, textvariable=self.max_preferences_var, width=8).grid(row=1, column=5, padx=5, pady=2, sticky="w")

        ttk.Label(generate_frame, text="Preference Distribution:").grid(row=2, column=0, padx=5, pady=2, sticky="w")
        ttk.Combobox(generate_frame, textvariable=self.preference_dist_var, values=["random", "skewed"], state="readonly").grid(row=2, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(generate_frame, text="Random Seed:").grid(row=2, column=2, padx=5, pady=2, sticky="w")
        ttk.Spinbox(generate_frame, from_=0, to=99999, textvariable=self.random_seed_var, width=8).grid(row=2, column=3, padx=5, pady=2, sticky="w")

        generate_buttons_frame = ttk.Frame(generate_frame)
        generate_buttons_frame.grid(row=3, column=0, columnspan=6, pady=5, sticky="ew")
        ttk.Button(generate_buttons_frame, text="Generate Data", command=self._generate_and_display_data).pack(side="left", padx=5)
        ttk.Button(generate_buttons_frame, text="Clear Data", command=self._clear_manual_data).pack(side="left", padx=5)


        # Seminar data manual input / display
        seminar_manual_frame = ttk.LabelFrame(self.manual_generate_frame, text="Seminar Data (Manual Input / Generated Results)", padding="10")
        seminar_manual_frame.pack(fill="both", expand=True, pady=10)

        seminar_tree_frame = ttk.Frame(seminar_manual_frame)
        seminar_tree_frame.pack(fill="both", expand=True)

        self.manual_seminar_tree = ttk.Treeview(seminar_tree_frame, columns=("ID", "Capacity"), show="headings", height=5)
        self.manual_seminar_tree.heading("ID", text="Seminar ID", command=lambda: self._sort_treeview("seminar", "ID"))
        self.manual_seminar_tree.heading("Capacity", text="Capacity", command=lambda: self._sort_treeview("seminar", "Capacity"))
        self.manual_seminar_tree.column("ID", width=100, anchor="center")
        self.manual_seminar_tree.column("Capacity", width=100, anchor="center")
        self.manual_seminar_tree.pack(side="left", fill="both", expand=True)

        seminar_scrollbar = ttk.Scrollbar(seminar_tree_frame, orient="vertical", command=self.manual_seminar_tree.yview)
        seminar_scrollbar.pack(side="right", fill="y")
        self.manual_seminar_tree.config(yscrollcommand=seminar_scrollbar.set)

        seminar_buttons_frame = ttk.Frame(seminar_manual_frame)
        seminar_buttons_frame.pack(pady=5)
        ttk.Button(seminar_buttons_frame, text="Add", command=lambda: self._open_edit_dialog("seminar")).pack(side="left", padx=2)
        ttk.Button(seminar_buttons_frame, text="Edit", command=lambda: self._open_edit_dialog("seminar", True)).pack(side="left", padx=2)
        ttk.Button(seminar_buttons_frame, text="Delete", command=lambda: self._delete_item("seminar")).pack(side="left", padx=2)
        ttk.Button(seminar_buttons_frame, text="Load CSV", command=lambda: self._load_seminar_csv()).pack(side="left", padx=2)
        ttk.Button(seminar_buttons_frame, text="Save CSV", command=lambda: self._save_seminar_csv()).pack(side="left", padx=2)

        # Student data manual input / display
        student_manual_frame = ttk.LabelFrame(self.manual_generate_frame, text="Student Data (Manual Input / Generated Results)", padding="10")
        student_manual_frame.pack(fill="both", expand=True, pady=10)

        student_tree_frame = ttk.Frame(student_manual_frame)
        student_tree_frame.pack(fill="both", expand=True)

        self.manual_student_tree = ttk.Treeview(student_tree_frame, columns=("ID", "Preferred Seminars"), show="headings", height=5)
        self.manual_student_tree.heading("ID", text="Student ID", command=lambda: self._sort_treeview("student", "ID"))
        self.manual_student_tree.heading("Preferred Seminars", text="Preferred Seminars (comma-separated)", command=lambda: self._sort_treeview("student", "Preferred Seminars"))
        self.manual_student_tree.column("ID", width=100, anchor="center")
        self.manual_student_tree.column("Preferred Seminars", width=300, anchor="w")
        self.manual_student_tree.pack(side="left", fill="both", expand=True)

        student_scrollbar = ttk.Scrollbar(student_tree_frame, orient="vertical", command=self.manual_student_tree.yview)
        student_scrollbar.pack(side="right", fill="y")
        self.manual_student_tree.config(yscrollcommand=student_scrollbar.set)

        student_buttons_frame = ttk.Frame(student_manual_frame)
        student_buttons_frame.pack(pady=5)
        ttk.Button(student_buttons_frame, text="Add", command=lambda: self._open_edit_dialog("student")).pack(side="left", padx=2)
        ttk.Button(student_buttons_frame, text="Edit", command=lambda: self._open_edit_dialog("student", True)).pack(side="left", padx=2)
        ttk.Button(student_buttons_frame, text="Delete", command=lambda: self._delete_item("student")).pack(side="left", padx=2)
        ttk.Button(student_buttons_frame, text="Load CSV", command=lambda: self._load_student_csv()).pack(side="left", padx=2)
        ttk.Button(student_buttons_frame, text="Save CSV", command=lambda: self._save_student_csv()).pack(side="left", padx=2)

        logger.debug("Data generation/manual input frame UI setup complete.")

    def _sort_treeview(self, data_type: str, column: str):
        """Sorts the Treeview by the specified column."""
        logger.debug(f"Sorting Treeview: Type={data_type}, Column={column}")
        if data_type == "seminar":
            data_list = self.manual_seminar_data
            tree = self.manual_seminar_tree
            current_sort_column = self.seminar_sort_column
            current_sort_direction = self.seminar_sort_direction
        elif data_type == "student":
            data_list = self.manual_student_data
            tree = self.manual_student_tree
            current_sort_column = self.student_sort_column
            current_sort_direction = self.student_sort_direction
        else:
            return

        # Determine new sort direction
        if column == current_sort_column:
            new_sort_direction = not current_sort_direction
        else:
            new_sort_direction = True # Default to ascending for new column

        # Update sort state
        if data_type == "seminar":
            self.seminar_sort_column = column
            self.seminar_sort_direction = new_sort_direction
        elif data_type == "student":
            self.student_sort_column = column
            self.student_sort_direction = new_sort_direction

        # Sort the data list
        if column == "ID":
            # Sort by ID (e.g., S001, S002, U0001, U0002)
            data_list.sort(key=lambda x: (x['id'][0], int(x['id'][1:])), reverse=not new_sort_direction)
        elif column == "Capacity": # For seminars
            data_list.sort(key=lambda x: x['capacity'], reverse=not new_sort_direction)
        elif column == "Preferred Seminars": # For students, sort by number of preferences or first preference
            data_list.sort(key=lambda x: len(x['preferences']), reverse=not new_sort_direction)
        
        # Update Treeview headings to show sort indicator
        for col_id in tree["columns"]:
            text = tree.heading(col_id, "text")
            # Remove existing sort indicator
            text = text.replace(" ▲", "").replace(" ▼", "")
            if col_id == column:
                text += " ▲" if new_sort_direction else " ▼"
            tree.heading(col_id, text=text)

        self._update_treeview(tree, data_list, data_type)
        logger.info(f"Treeview ({data_type}) sorted by '{column}' in {'ascending' if new_sort_direction else 'descending'} order.")


    def _open_edit_dialog(self, data_type: str, is_edit: bool = False):
        """Opens a dialog to add/edit seminar or student data."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Edit Data" if is_edit else "Add Data")
        dialog.transient(self.root)
        dialog.grab_set()
        
        # Set dialog background color to match theme
        dialog.config(bg=self.themes[self.theme_var.get()]["bg"])

        selected_item = None
        current_data = {}
        if is_edit:
            if data_type == "seminar":
                selected_item = self.manual_seminar_tree.focus()
                if not selected_item:
                    messagebox.showwarning("No Selection", "Please select a seminar to edit.")
                    dialog.destroy()
                    return
                current_values = self.manual_seminar_tree.item(selected_item, "values")
                current_data = {"id": current_values[0], "capacity": int(current_values[1])}
            elif data_type == "student":
                selected_item = self.manual_student_tree.focus()
                if not selected_item:
                    messagebox.showwarning("No Selection", "Please select a student to edit.")
                    dialog.destroy()
                    return
                current_values = self.manual_student_tree.item(selected_item, "values")
                current_data = {"id": current_values[0], "preferences": current_values[1]}
            logger.debug(f"Edit mode: {data_type} data '{current_data.get('id', '')}'")

        fields: List[Tuple[str, tk.StringVar, Any]] = []

        if is_edit:
            ttk.Label(dialog, text="ID:", background=dialog.cget("bg"), foreground=self.themes[self.theme_var.get()]["fg"]).grid(row=0, column=0, padx=5, pady=5, sticky="w")
            id_var = tk.StringVar(value=str(current_data.get('id', '')))
            ttk.Entry(dialog, textvariable=id_var, state="readonly", background=self.themes[self.theme_var.get()]["tree_bg"], foreground=self.themes[self.theme_var.get()]["fg"]).grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        else:
            id_var = tk.StringVar()
            pass

        if data_type == "seminar":
            ttk.Label(dialog, text="Capacity:", background=dialog.cget("bg"), foreground=self.themes[self.theme_var.get()]["fg"]).grid(row=1, column=0, padx=5, pady=5, sticky="w")
            capacity_var = tk.IntVar(value=current_data.get('capacity', 0))
            ttk.Entry(dialog, textvariable=capacity_var, background=self.themes[self.theme_var.get()]["tree_bg"], foreground=self.themes[self.theme_var.get()]["fg"]).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
            fields.append(("capacity", capacity_var, int))
        elif data_type == "student":
            ttk.Label(dialog, text="Preferred Seminars (comma-separated IDs):", background=dialog.cget("bg"), foreground=self.themes[self.theme_var.get()]["fg"]).grid(row=1, column=0, padx=5, pady=5, sticky="w")
            preferences_var = tk.StringVar(value=current_data.get('preferences', ''))
            ttk.Entry(dialog, textvariable=preferences_var, background=self.themes[self.theme_var.get()]["tree_bg"], foreground=self.themes[self.theme_var.get()]["fg"]).grid(row=1, column=1, padx=5, pady=5, sticky="ew")
            fields.append(("preferences", preferences_var, str))

        def save_item():
            try:
                if data_type == "seminar":
                    capacity = fields[0][1].get()
                    if not capacity.isdigit() or int(capacity) <= 0:
                        messagebox.showerror("Input Error", "Capacity must be a positive integer.")
                        return
                    new_capacity = int(capacity)
                    
                    if is_edit:
                        seminar_id = current_data['id']
                        for i, s in enumerate(self.manual_seminar_data):
                            if s['id'] == seminar_id:
                                self.manual_seminar_data[i]['capacity'] = new_capacity
                                self._update_treeview(self.manual_seminar_tree, self.manual_seminar_data, "seminar")
                                logger.info(f"Updated seminar data '{seminar_id}'.")
                                self._update_status_bar(f"Updated seminar: {seminar_id}", "info")
                                break
                    else:
                        existing_ids = {s['id'] for s in self.manual_seminar_data}
                        new_id_num = 1
                        while f"S{new_id_num:03d}" in existing_ids:
                            new_id_num += 1
                        new_id = f"S{new_id_num:03d}"
                        self.manual_seminar_data.append({"id": new_id, "capacity": new_capacity})
                        self._update_treeview(self.manual_seminar_tree, self.manual_seminar_data, "seminar")
                        logger.info(f"Added new seminar data '{new_id}'.")
                        self._update_status_bar(f"Added new seminar: {new_id}", "info")
                elif data_type == "student":
                    preferences_str = fields[0][1].get()
                    new_preferences = [s.strip() for s in preferences_str.split(',') if s.strip()]
                    
                    if is_edit:
                        student_id = current_data['id']
                        for i, st in enumerate(self.manual_student_data):
                            if st['id'] == student_id:
                                self.manual_student_data[i]['preferences'] = new_preferences
                                self._update_treeview(self.manual_student_tree, self.manual_student_data, "student")
                                logger.info(f"Updated student data '{student_id}'.")
                                self._update_status_bar(f"Updated student: {student_id}", "info")
                                break
                    else:
                        existing_ids = {st['id'] for st in self.manual_student_data}
                        new_id_num = 1
                        while f"U{new_id_num:04d}" in existing_ids:
                            new_id_num += 1
                        new_id = f"U{new_id_num:04d}"
                        self.manual_student_data.append({"id": new_id, "preferences": new_preferences})
                        self._update_treeview(self.manual_student_tree, self.manual_student_data, "student")
                        logger.info(f"Added new student data '{new_id}'.")
                        self._update_status_bar(f"Added new student: {new_id}", "info")
                dialog.destroy()
            except Exception as e:
                messagebox.showerror("Save Error", f"An error occurred while saving data: {e}")
                logger.error(f"Data save error ({data_type}): {e}", exc_info=True)
                self._update_status_bar(f"Error saving {data_type} data.", "error")

        button_frame = ttk.Frame(dialog, background=dialog.cget("bg"))
        button_frame.grid(row=len(fields) + 1, column=0, columnspan=2, pady=10)
        ttk.Button(button_frame, text="Save", command=save_item).pack(side="left", padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side="left", padx=5)
        
        dialog.columnconfigure(1, weight=1)

    def _delete_item(self, data_type: str):
        """Deletes selected items from the Treeview."""
        if data_type == "seminar":
            selected_items = self.manual_seminar_tree.selection()
            tree = self.manual_seminar_tree
            data_list = self.manual_seminar_data
        elif data_type == "student":
            selected_items = self.manual_student_tree.selection()
            tree = self.manual_student_tree
            data_list = self.manual_student_data
        else:
            return

        if not selected_items:
            messagebox.showwarning("No Selection", "Please select items to delete.")
            logger.warning(f"Delete operation: No {data_type} items selected.")
            self._update_status_bar(f"No {data_type} items selected for deletion.", "warning")
            return

        if messagebox.askyesno("Confirmation", f"Are you sure you want to delete {len(selected_items)} selected items?"):
            deleted_count = 0
            for item in selected_items:
                item_id = tree.item(item, "values")[0]
                # Remove from data list
                data_list[:] = [d for d in data_list if d['id'] != item_id]
                tree.delete(item)
                logger.info(f"Deleted {data_type} data '{item_id}'.")
                deleted_count += 1
            
            # Re-sort and update treeview after deletion
            if data_type == "seminar":
                self._update_treeview(self.manual_seminar_tree, self.manual_seminar_data, "seminar")
            elif data_type == "student":
                self._update_treeview(self.manual_student_tree, self.manual_student_data, "student")

            messagebox.showinfo("Deletion Complete", f"{deleted_count} items deleted.")
            self._update_status_bar(f"{deleted_count} {data_type} items deleted.", "info")
        else:
            logger.debug(f"Delete operation ({data_type}): Cancelled by user.")
            self._update_status_bar(f"Deletion of {data_type} items cancelled.", "info")

    def _update_treeview(self, tree: ttk.Treeview, data_list: List[Dict[str, Any]], data_type: str):
        """Helper function to update the Treeview display."""
        # Clear existing items
        for item in tree.get_children():
            tree.delete(item)
        
        # Insert new items
        for item_data in data_list:
            if data_type == "seminar":
                tree.insert("", "end", values=(item_data["id"], item_data["capacity"]))
            elif data_type == "student":
                # Convert list of preferences to comma-separated string for display
                preferences_str = ", ".join(item_data["preferences"])
                tree.insert("", "end", values=(item_data["id"], preferences_str))
        logger.debug(f"Treeview ({data_type}) updated. Item count: {len(data_list)}")


    def _load_seminar_csv(self):
        """Loads seminar data from a CSV file and displays it in the Treeview."""
        filepath = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not filepath:
            logger.debug("Seminar CSV load: No file selected.")
            self._update_status_bar("Seminar CSV load cancelled.", "info")
            return
        
        try:
            new_data = []
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                required_headers = ["id", "capacity"]
                if not all(header in reader.fieldnames for header in required_headers):
                    messagebox.showerror("CSV Error", f"Required headers ({', '.join(required_headers)}) not found in CSV file.")
                    logger.error(f"Seminar CSV load error: Missing headers. File: {filepath}")
                    self._update_status_bar("Error: Seminar CSV missing required headers.", "error")
                    return

                for row in reader:
                    seminar_id = row["id"].strip()
                    capacity = int(row["capacity"].strip())
                    if not seminar_id or capacity <= 0:
                        raise ValueError(f"Invalid data format: id='{seminar_id}', capacity='{row['capacity']}'")
                    new_data.append({"id": seminar_id, "capacity": capacity})
            
            self.manual_seminar_data = new_data
            self._update_treeview(self.manual_seminar_tree, self.manual_seminar_data, "seminar")
            messagebox.showinfo("Load Complete", f"{len(new_data)} seminar data items loaded from CSV.")
            logger.info(f"Loaded seminar data from CSV: {filepath}, Item count: {len(new_data)}")
            self._update_status_bar(f"Loaded {len(new_data)} seminar items from CSV.", "info")
        except FileNotFoundError:
            messagebox.showerror("Error", "File not found.")
            logger.error(f"Seminar CSV load error: File not found. Path: {filepath}", exc_info=True)
            self._update_status_bar("Error: Seminar CSV file not found.", "error")
        except ValueError as e:
            messagebox.showerror("CSV Error", f"Invalid data format in CSV file: {e}")
            logger.error(f"Seminar CSV load error: Invalid data format. Error: {e}", exc_info=True)
            self._update_status_bar("Error: Invalid data format in seminar CSV.", "error")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while loading the CSV file: {e}")
            logger.error(f"Unexpected error loading seminar CSV: {e}", exc_info=True)
            self._update_status_bar("Error: Unexpected error loading seminar CSV.", "error")

    def _save_seminar_csv(self):
        """Saves seminar data to a CSV file."""
        if not self.manual_seminar_data:
            messagebox.showwarning("No Data", "No seminar data to save.")
            logger.warning("Seminar CSV save: No data to save.")
            self._update_status_bar("No seminar data to save.", "warning")
            return

        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not filepath:
            logger.debug("Seminar CSV save: File name not specified.")
            self._update_status_bar("Seminar CSV save cancelled.", "info")
            return
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["id", "capacity"])
                writer.writeheader()
                writer.writerows(self.manual_seminar_data)
            messagebox.showinfo("Save Complete", f"{len(self.manual_seminar_data)} seminar data items saved to CSV.")
            logger.info(f"Saved seminar data to CSV: {filepath}, Item count: {len(self.manual_seminar_data)}")
            self._update_status_bar(f"Saved {len(self.manual_seminar_data)} seminar items to CSV.", "info")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while saving the CSV file: {e}")
            logger.error(f"Unexpected error saving seminar CSV: {e}", exc_info=True)
            self._update_status_bar("Error: Unexpected error saving seminar CSV.", "error")

    def _load_student_csv(self):
        """Loads student data from a CSV file and displays it in the Treeview."""
        filepath = filedialog.askopenfilename(filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not filepath:
            logger.debug("Student CSV load: No file selected.")
            self._update_status_bar("Student CSV load cancelled.", "info")
            return
        
        try:
            new_data = []
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                required_headers = ["id", "preferences"]
                if not all(header in reader.fieldnames for header in required_headers):
                    messagebox.showerror("CSV Error", f"Required headers ({', '.join(required_headers)}) not found in CSV file.")
                    logger.error(f"Student CSV load error: Missing headers. File: {filepath}")
                    self._update_status_bar("Error: Student CSV missing required headers.", "error")
                    return

                for row in reader:
                    student_id = row["id"].strip()
                    # Convert comma-separated string to list of preferences
                    preferences = [s.strip() for s in row["preferences"].split(',') if s.strip()]
                    if not student_id:
                        raise ValueError(f"Invalid data format: id='{student_id}'")
                    new_data.append({"id": student_id, "preferences": preferences})
            
            self.manual_student_data = new_data
            self._update_treeview(self.manual_student_tree, self.manual_student_data, "student")
            messagebox.showinfo("Load Complete", f"{len(new_data)} student data items loaded from CSV.")
            logger.info(f"Loaded student data from CSV: {filepath}, Item count: {len(new_data)}")
            self._update_status_bar(f"Loaded {len(new_data)} student items from CSV.", "info")
        except FileNotFoundError:
            messagebox.showerror("Error", "File not found.")
            logger.error(f"Student CSV load error: File not found. Path: {filepath}", exc_info=True)
            self._update_status_bar("Error: Student CSV file not found.", "error")
        except ValueError as e:
            messagebox.showerror("CSV Error", f"Invalid data format in CSV file: {e}")
            logger.error(f"Student CSV load error: Invalid data format. Error: {e}", exc_info=True)
            self._update_status_bar("Error: Invalid data format in student CSV.", "error")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while loading the CSV file: {e}")
            logger.error(f"Unexpected error loading student CSV: {e}", exc_info=True)
            self._update_status_bar("Error: Unexpected error loading student CSV.", "error")

    def _save_student_csv(self):
        """Saves student data to a CSV file."""
        if not self.manual_student_data:
            messagebox.showwarning("No Data", "No student data to save.")
            logger.warning("Student CSV save: No data to save.")
            self._update_status_bar("No student data to save.", "warning")
            return

        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")])
        if not filepath:
            logger.debug("Student CSV save: File name not specified.")
            self._update_status_bar("Student CSV save cancelled.", "info")
            return
        
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=["id", "preferences"])
                writer.writeheader()
                # Convert preferences list to comma-separated string for saving
                rows_to_write = [{"id": d["id"], "preferences": ", ".join(d["preferences"])} for d in self.manual_student_data]
                writer.writerows(rows_to_write)
            messagebox.showinfo("Save Complete", f"{len(self.manual_student_data)} student data items saved to CSV.")
            logger.info(f"Saved student data to CSV: {filepath}, Item count: {len(self.manual_student_data)}")
            self._update_status_bar(f"Saved {len(self.manual_student_data)} student items to CSV.", "info")
        except Exception as e:
            messagebox.showerror("Error", f"An error occurred while saving the CSV file: {e}")
            logger.error(f"Unexpected error saving student CSV: {e}", exc_info=True)
            self._update_status_bar("Error: Unexpected error saving student CSV.", "error")

    def _generate_and_display_data(self):
        """Generates data based on settings and displays it in the manual input Treeview."""
        logger.debug("Generating and displaying data.")
        self._update_status_bar("Generating data...", "info")
        if not InputValidator.validate_settings(self):
            logger.warning("Data generation: Settings invalid, generation aborted.")
            self._update_status_bar("Data generation aborted due to invalid settings.", "warning")
            return

        try:
            num_seminars = self.num_seminars_var.get()
            min_capacity = self.min_capacity_var.get()
            max_capacity = self.max_capacity_var.get()
            num_students = self.num_students_var.get()
            min_preferences = self.min_preferences_var.get()
            max_preferences = self.max_preferences_var.get()
            preference_dist = self.preference_dist_var.get()
            random_seed = self.random_seed_var.get()

            data_generator = DataGenerator(
                num_seminars=num_seminars,
                min_capacity=min_capacity,
                max_capacity=max_capacity,
                num_students=num_students,
                min_preferences=min_preferences,
                max_preferences=max_preferences,
                preference_distribution=preference_dist,
                random_seed=random_seed
            )

            seminars, students = data_generator.generate_data()
            self.manual_seminar_data = seminars
            self.manual_student_data = students

            self._update_treeview(self.manual_seminar_tree, self.manual_seminar_data, "seminar")
            self._update_treeview(self.manual_student_tree, self.manual_student_data, "student")
            
            messagebox.showinfo("Data Generation Complete", f"Generated {len(seminars)} seminars and {len(students)} students.")
            logger.info(f"Data generation complete: {len(seminars)} seminars, {len(students)} students.")
            self._update_status_bar(f"Generated {len(seminars)} seminars and {len(students)} students.", "info")
            
            self.seminars_data_for_report = seminars
            self.students_data_for_report = students

        except Exception as e:
            messagebox.showerror("Data Generation Error", f"An error occurred while generating data: {e}")
            logger.error(f"Data generation error: {e}", exc_info=True)
            self._update_status_bar("Error generating data.", "error")

    def _clear_manual_data(self):
        """Clears the manual input Treeview and data."""
        if messagebox.askyesno("Confirmation", "Are you sure you want to clear all manually entered/generated data?"):
            self.manual_seminar_data = []
            self.manual_student_data = []
            self._update_treeview(self.manual_seminar_tree, [], "seminar")
            self._update_treeview(self.manual_student_tree, [], "student")
            messagebox.showinfo("Clear Complete", "Manual input data cleared.")
            logger.info("Manual input data cleared.")
            self._update_status_bar("Manual input data cleared.", "info")
        else:
            logger.debug("Data clear cancelled by user.")
            self._update_status_bar("Data clear cancelled.", "info")

    def _create_settings_tab(self):
        """Creates the settings tab."""
        logger.debug("SeminarGUI: Creating settings tab.")
        settings_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(settings_frame, text="Optimization Settings")

        # GUI Theme settings
        theme_frame = ttk.LabelFrame(settings_frame, text="GUI Theme", padding="10")
        theme_frame.pack(pady=10, fill="x")
        ttk.Label(theme_frame, text="Select Theme:").pack(side="left", padx=5)
        theme_options = list(self.themes.keys())
        self.theme_combobox = ttk.Combobox(theme_frame, textvariable=self.theme_var, values=theme_options, state="readonly", width=20)
        self.theme_combobox.pack(side="left", padx=5)
        self.theme_combobox.bind("<<ComboboxSelected>>", lambda e: self._apply_theme())


        # Optimization strategy settings
        strategy_frame = ttk.LabelFrame(settings_frame, text="Optimization Strategy", padding="10")
        strategy_frame.pack(pady=10, fill="x")
        ttk.Label(strategy_frame, text="Select Strategy:").pack(side="left", padx=5)
        strategy_options = ["Greedy_LS", "GeneticAlgorithm", "ILP_CBC", "Multilevel", "SimulatedAnnealing", "LocalSearch"]
        self.strategy_combobox = ttk.Combobox(strategy_frame, textvariable=self.optimization_strategy_var, values=strategy_options, state="readonly", width=20)
        self.strategy_combobox.pack(side="left", padx=5)
        self.strategy_combobox.bind("<<ComboboxSelected>>", self._on_strategy_selected)

        # Settings frames for each strategy
        self.strategy_settings_frames: Dict[str, ttk.Frame] = {}

        self.ga_frame = ttk.Frame(settings_frame)
        ttk.Label(self.ga_frame, text="Population Size:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(self.ga_frame, from_=10, to=1000, textvariable=self.ga_population_size_var, width=10).grid(row=0, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(self.ga_frame, text="Generations:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(self.ga_frame, from_=10, to=2000, textvariable=self.ga_generations_var, width=10).grid(row=1, column=1, padx=5, pady=2, sticky="w")
        self.strategy_settings_frames["GeneticAlgorithm"] = self.ga_frame; self.ga_frame.columnconfigure(1, weight=1)

        self.ilp_frame = ttk.Frame(settings_frame)
        ttk.Label(self.ilp_frame, text="Time Limit (seconds):").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(self.ilp_frame, from_=10, to=3600, textvariable=self.ilp_time_limit_var, width=10).grid(row=0, column=1, padx=5, pady=2, sticky="w")
        self.strategy_settings_frames["ILP_CBC"] = self.ilp_frame; self.ilp_frame.columnconfigure(1, weight=1)

        self.multilevel_frame = ttk.Frame(settings_frame)
        ttk.Label(self.multilevel_frame, text="Number of Clusters:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(self.multilevel_frame, from_=1, to=100, textvariable=self.multilevel_clusters_var, width=10).grid(row=0, column=1, padx=5, pady=2, sticky="w")
        self.strategy_settings_frames["Multilevel"] = self.multilevel_frame; self.multilevel_frame.columnconfigure(1, weight=1)
        
        self.greedy_ls_frame = ttk.Frame(settings_frame)
        ttk.Label(self.greedy_ls_frame, text="Iterations:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(self.greedy_ls_frame, from_=1000, to=1000000, textvariable=self.greedy_ls_iterations_var, width=15).grid(row=0, column=1, padx=5, pady=2, sticky="w")
        self.strategy_settings_frames["Greedy_LS"] = self.greedy_ls_frame; self.greedy_ls_frame.columnconfigure(1, weight=1)

        self.local_search_frame = ttk.Frame(settings_frame)
        ttk.Label(self.local_search_frame, text="Iterations:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(self.local_search_frame, from_=10, to=100000, textvariable=self.local_search_iterations_var, width=15).grid(row=0, column=1, padx=5, pady=2, sticky="w")
        self.strategy_settings_frames["LocalSearch"] = self.local_search_frame; self.local_search_frame.columnconfigure(1, weight=1)
        
        self.sa_frame = ttk.Frame(settings_frame)
        ttk.Label(self.sa_frame, text="Initial Temperature:").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(self.sa_frame, from_=0.01, to=10.0, increment=0.01, textvariable=self.initial_temperature_var, width=10, format="%.2f").grid(row=0, column=1, padx=5, pady=2, sticky="w")
        ttk.Label(self.sa_frame, text="Cooling Rate:").grid(row=1, column=0, padx=5, pady=2, sticky="w")
        ttk.Spinbox(self.sa_frame, from_=0.9, to=0.9999, increment=0.0001, textvariable=self.cooling_rate_var, width=10, format="%.4f").grid(row=1, column=1, padx=5, pady=2, sticky="w")
        self.strategy_settings_frames["SimulatedAnnealing"] = self.sa_frame; self.sa_frame.columnconfigure(1, weight=1)


        # Report output settings
        report_frame = ttk.LabelFrame(settings_frame, text="Report Output Settings", padding="10")
        report_frame.pack(pady=10, fill="x")
        ttk.Checkbutton(report_frame, text="Generate PDF Report", variable=self.generate_pdf_report_var).pack(anchor="w", padx=5, pady=2)
        ttk.Checkbutton(report_frame, text="Generate CSV Report", variable=self.generate_csv_report_var).pack(anchor="w", padx=5, pady=2)
        
        # Other settings
        other_settings_frame = ttk.LabelFrame(settings_frame, text="Other", padding="10")
        other_settings_frame.pack(pady=10, fill="x")
        ttk.Checkbutton(other_settings_frame, text="Enable Debug Mode", variable=self.debug_mode_var).pack(anchor="w", padx=5, pady=2)
        ttk.Checkbutton(other_settings_frame, text="Enable Log Output (GUI/File)", variable=self.log_enabled_var).pack(anchor="w", padx=5, pady=2)


        self._on_strategy_selected() # Call to display initial strategy settings
        logger.info("SeminarGUI: Settings tab UI setup complete.")

    def _on_strategy_selected(self, event=None):
        """Toggles the display of settings frames based on the selected optimization strategy."""
        selected_strategy = self.optimization_strategy_var.get()
        logger.debug(f"Optimization strategy changed to: {selected_strategy}")

        # Hide all frames
        for frame in self.strategy_settings_frames.values():
            frame.pack_forget()

        # Display the frame for the selected strategy
        if selected_strategy in self.strategy_settings_frames:
            self.strategy_settings_frames[selected_strategy].pack(pady=5, fill="x")
            logger.debug(f"Displayed settings frame for strategy '{selected_strategy}'.")
        else:
            logger.warning(f"Unknown optimization strategy selected: {selected_strategy}")
        
        self._apply_theme() # Re-apply theme to ensure new frames have correct background colors

    def _create_results_tab(self):
        """Creates the results display tab."""
        logger.debug("SeminarGUI: Creating results tab.")
        results_frame = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(results_frame, text="Results")

        self.results_text = scrolledtext.ScrolledText(results_frame, wrap=tk.WORD, state=tk.DISABLED, height=20, font=('Consolas', 9))
        self.results_text.pack(expand=True, fill="both")
        
        # Clear results button
        clear_results_button = ttk.Button(results_frame, text="Clear Results", command=self._clear_results)
        clear_results_button.pack(pady=5)
        logger.info("SeminarGUI: Results tab UI setup complete.")

    def _clear_results(self):
        """Clears the results display area."""
        if self.results_text:
            self.results_text.config(state=tk.NORMAL)
            self.results_text.delete(1.0, tk.END)
            self.results_text.config(state=tk.DISABLED)
            logger.info("Results display area cleared.")
            self._update_status_bar("Results display cleared.", "info")

    def _load_saved_settings(self):
        """Loads saved GUI settings and applies them to the GUI."""
        logger.debug("SeminarGUI: Attempting to load saved GUI settings.")
        if self.gui_settings:
            method = self.gui_settings.get("data_input_method", "generate_or_manual")
            self.data_input_method_var.set(method)
            self._toggle_input_frames()

            seminars_path = self.gui_settings.get("seminars_file_path")
            if seminars_path and os.path.exists(seminars_path):
                self.seminars_file_path_var.set(seminars_path)
            
            students_path = self.gui_settings.get("students_file_path")
            if students_path and os.path.exists(students_path):
                self.students_file_path_var.set(students_path)

            log_enabled_str = self.gui_settings.get("log_enabled", "True")
            self.log_enabled_var.set(log_enabled_str.lower() == 'true')
            if self.log_enabled_var.get():
                logging.getLogger().setLevel(logging.DEBUG)
                logger.info("GUI Settings: Log output enabled.")
            else:
                logging.getLogger().setLevel(logging.CRITICAL + 1)
                logger.info("GUI Settings: Log output disabled.")
            
            theme_name = self.gui_settings.get("theme", "Default Light")
            self.theme_var.set(theme_name)
            self._apply_theme() # Apply loaded theme

            logger.info("SeminarGUI: Saved GUI settings loaded.")
        else:
            logger.info("SeminarGUI: No saved GUI settings found. Using default values.")

    def _save_current_gui_settings(self):
        """Saves current GUI settings."""
        logger.debug("SeminarGUI: Attempting to save current GUI settings.")
        settings_to_save = {
            "data_input_method": self.data_input_method_var.get(),
            "seminars_file_path": self.seminars_file_path_var.get(),
            "students_file_path": self.students_file_path_var.get(),
            "log_enabled": str(self.log_enabled_var.get()),
            "theme": self.theme_var.get(), # Save theme setting
        }
        self.config_manager.save_gui_settings(settings_to_save)
        logger.info("SeminarGUI: Current GUI settings saved.")
        self._update_status_bar("GUI settings saved.", "info")


    def _update_status_bar(self, message: str, level: str = "info"):
        """Updates the status bar with a message and optionally changes its color."""
        if self.status_bar_label:
            theme_colors = self.themes.get(self.theme_var.get(), self.themes["Default Light"])
            bg_color = theme_colors.get(f"status_bg_{level}", theme_colors["status_bg_info"])
            fg_color = theme_colors.get(f"status_fg_{level}", theme_colors["status_fg_info"])
            
            self.status_bar_label.config(text=message, background=bg_color, foreground=fg_color)
            self.root.update_idletasks() # Ensure immediate update

    def _run_optimization(self):
        """Executes the optimization process in a separate thread."""
        logger.info("Run Optimization button clicked.")
        self._update_status_bar("Starting optimization process...", "info")
        if self.is_optimizing:
            messagebox.showwarning("Running", "Optimization process is already running.")
            logger.warning("Optimization already running, blocking new execution.")
            self._update_status_bar("Optimization already running.", "warning")
            return

        # Input validation
        if not InputValidator.validate_settings(self):
            logger.warning("Settings validation failed. Optimization aborted.")
            self._update_status_bar("Optimization aborted: Invalid settings.", "error")
            return

        # Prepare data
        seminars: List[Dict[str, Any]] = []
        students: List[Dict[str, Any]] = []
        input_method = self.data_input_method_var.get()

        if input_method == "json_file":
            seminars_filepath = self.seminars_file_path_var.get()
            students_filepath = self.students_file_path_var.get()
            if not seminars_filepath or not students_filepath:
                messagebox.showerror("Input Error", "JSON files not selected.")
                logger.error("JSON file input mode, but file paths not specified.")
                self._update_status_bar("Error: JSON files not selected.", "error")
                return
            try:
                with open(seminars_filepath, 'r', encoding='utf-8') as f:
                    seminars = json.load(f)
                with open(students_filepath, 'r', encoding='utf-8') as f:
                    students = json.load(f)
                logger.info(f"Data loaded from JSON files: Seminars='{seminars_filepath}', Students='{students_filepath}'")
                self._update_status_bar("Data loaded from JSON files.", "info")
            except FileNotFoundError as e:
                messagebox.showerror("File Error", f"Specified file not found: {e}")
                logger.error(f"File load error: {e}", exc_info=True)
                self._update_status_bar("Error: Data file not found.", "error")
                return
            except json.JSONDecodeError as e:
                messagebox.showerror("JSON Error", f"Invalid JSON file format: {e}")
                logger.error(f"JSON decode error: {e}", exc_info=True)
                self._update_status_bar("Error: Invalid JSON file format.", "error")
                return
            except Exception as e:
                messagebox.showerror("Data Load Error", f"An unexpected error occurred while loading data: {e}")
                logger.error(f"Unexpected error loading data: {e}", exc_info=True)
                self._update_status_bar("Error: Unexpected error loading data.", "error")
                return
        elif input_method == "generate_or_manual":
            if not self.manual_seminar_data or not self.manual_student_data:
                messagebox.showwarning("Insufficient Data", "No manually entered or generated seminar and student data. Please prepare data first.")
                logger.warning("Data generation/manual input mode, but data is empty.")
                self._update_status_bar("Error: No manual/generated data found.", "warning")
                return
            seminars = self.manual_seminar_data
            students = self.manual_student_data
            logger.info(f"Using manually entered/generated data. Seminars: {len(seminars)}, Students: {len(students)}")
            self._update_status_bar("Using manual/generated data.", "info")
        
        self.seminars_data_for_report = seminars
        self.students_data_for_report = students

        # Collect optimization parameters
        optimization_params: Dict[str, Any] = {
            "strategy": self.optimization_strategy_var.get(),
            "ga_population_size": self.ga_population_size_var.get(),
            "ga_generations": self.ga_generations_var.get(),
            "ilp_time_limit": self.ilp_time_limit_var.get(),
            "multilevel_clusters": self.multilevel_clusters_var.get(),
            "greedy_ls_iterations": self.greedy_ls_iterations_var.get(),
            "local_search_iterations": self.local_search_iterations_var.get(),
            "initial_temperature": self.initial_temperature_var.get(),
            "cooling_rate": self.cooling_rate_var.get(),
            "debug_mode": self.debug_mode_var.get(),
            "random_seed": self.random_seed_var.get(),
        }
        
        # Set optimization flag
        self.is_optimizing = True
        self.optimize_button.config(state=tk.DISABLED)
        self.cancel_button.config(state=tk.NORMAL)
        self.cancel_event.clear() # Clear cancel event

        self.progress_dialog = ProgressDialog(self.root)
        self.progress_dialog.cancel_callback = self.cancel_event.set # Set event when cancel button is pressed
        self.progress_dialog.start_progress_bar("Preparing data...")
        
        self.optimization_thread = threading.Thread(
            target=self._optimization_worker,
            args=(seminars, students, optimization_params, self.cancel_event)
        )
        self.optimization_thread.daemon = True # Exit with main thread
        self.optimization_thread.start()
        logger.info("Optimization thread started.")
        self._update_status_bar("Optimization in progress...", "info")

    def _optimization_worker(self, seminars: List[Dict[str, Any]], students: List[Dict[str, Any]],
                              optimization_params: Dict[str, Any], cancel_event: threading.Event):
        """Worker function to execute the optimization process in a separate thread.
        Reports progress to ProgressDialog.
        """
        progress_reporter = ProgressReporter(self.root, self.progress_dialog, self._update_status_bar)

        try:
            logger.info(f"Optimization worker started. Strategy: {optimization_params['strategy']}")

            # Phase 1: Data Preparation (0-10%)
            progress_reporter.report_progress(5, "Data preparation complete")
            time.sleep(0.5)
            if cancel_event.is_set(): return # Check for cancellation

            # Phase 2: Optimization Execution (10-90%)
            # Simulate more granular progress within the optimization phase
            total_optimization_steps = 10 # Example: 10 sub-steps for optimization
            for i in range(total_optimization_steps):
                if cancel_event.is_set(): return # Check for cancellation
                current_progress_percentage = 10 + int((i / total_optimization_steps) * 75) # 10% to 85%
                progress_message = f"Executing optimization: Step {i+1}/{total_optimization_steps}"
                progress_reporter.report_progress(current_progress_percentage, progress_message)
                time.sleep(0.5) # Simulate work

            progress_reporter.report_progress(85, "Optimization core complete")
            time.sleep(0.5)
            if cancel_event.is_set(): return # Check for cancellation

            optimization_result: Optional[OptimizationResult] = None
            try:
                # This is where the actual run_optimization_service would be called.
                # In a real scenario, run_optimization_service would accept progress_reporter
                # and call its methods internally.
                optimization_result = run_optimization_service(
                    seminars, students, optimization_params, cancel_event # Pass cancel_event to backend
                )
            except Exception as e:
                logger.error(f"Error during run_optimization_service execution: {e}", exc_info=True)
                self.root.after(0, lambda: messagebox.showerror("Optimization Error", f"An error occurred during optimization service execution: {e}"))
                self.root.after(0, lambda: self._update_status_bar("Error during optimization execution.", "error"))
                return # Abort further processing on error

            if cancel_event.is_set():
                logger.info("Optimization process cancelled by user.")
                self.root.after(0, lambda: messagebox.showinfo("Cancelled", "Optimization process cancelled."))
                self.root.after(0, lambda: self._update_results_text("Optimization process cancelled by user.\n"))
                self.root.after(0, lambda: self._update_status_bar("Optimization cancelled.", "warning"))
                return

            # Phase 3: Report Generation (85-100%)
            progress_reporter.report_progress(90, "Finalizing results...")
            time.sleep(0.5)
            if cancel_event.is_set(): return # Check for cancellation

            if optimization_result:
                self.root.after(0, lambda: self._generate_reports(optimization_result))
            progress_reporter.report_progress(100, "Done")
            time.sleep(0.5)

            if optimization_result:
                self.root.after(0, self._display_results, optimization_result)
                logger.info("Optimization process completed successfully.")
            else:
                self.root.after(0, lambda: messagebox.showerror("Optimization Error", "No optimization results obtained."))
                self.root.after(0, lambda: self._update_results_text("An unexpected error occurred during optimization or no results were obtained.\n"))
                logger.error("Optimization process returned no results.")
                self.root.after(0, lambda: self._update_status_bar("Error: No optimization results.", "error"))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Optimization Error", f"An error occurred during optimization: {e}"))
            self.root.after(0, lambda: self._update_results_text(f"An error occurred during optimization: {e}\n"))
            logger.critical(f"Fatal error in optimization worker: {e}", exc_info=True)
            self.root.after(0, lambda: self._update_status_bar("Fatal error during optimization.", "error"))
        finally:
            self.root.after(0, self._reset_optimization_state)
            self.root.after(0, self.progress_dialog.close)
            logger.info("Optimization worker finished.")

    def _cancel_optimization(self):
        """Requests cancellation of the optimization process."""
        logger.info("Cancel button clicked.")
        if self.is_optimizing and self.optimization_thread and self.optimization_thread.is_alive():
            self.progress_dialog._on_cancel() # Call the cancel logic in ProgressDialog
            self._update_status_bar("Cancellation requested...", "warning")
        else:
            messagebox.showinfo("Information", "Optimization process is not running.")
            logger.debug("Optimization not running, cancel request ignored.")
            self._update_status_bar("Optimization not running.", "info")

    def _reset_optimization_state(self):
        """Resets the optimization state."""
        self.is_optimizing = False
        self.optimize_button.config(state=tk.NORMAL)
        self.cancel_button.config(state=tk.DISABLED)
        self.cancel_event.clear()
        self.optimization_thread = None
        self.progress_dialog = None
        logger.debug("Optimization state reset.")
        self._update_status_bar("Ready.", "info")

    def _display_results(self, result: OptimizationResult):
        """Displays optimization results in the results tab."""
        logger.debug("Starting display of optimization results.")
        self.notebook.select(self.notebook.index("Results")) # Switch to results tab
        
        self.results_text.config(state=tk.NORMAL)
        self.results_text.delete(1.0, tk.END) # Clear existing results

        self.results_text.insert(tk.END, f"--- Optimization Results ---\n")
        self.results_text.insert(tk.END, f"Optimization Strategy: {result.strategy_name}\n")
        self.results_text.insert(tk.END, f"Execution Time: {result.runtime_seconds:.2f} seconds\n")
        self.results_text.insert(tk.END, f"Total Satisfaction: {result.total_satisfaction}\n")
        self.results_text.insert(tk.END, f"Unassigned Students: {result.unassigned_students}\n")
        self.results_text.insert(tk.END, f"Over-capacity Seminars: {result.over_capacity_seminars}\n")
        self.results_text.insert(tk.END, f"Total Over-capacity Count: {result.over_capacity_count}\n")
        self.results_text.insert(tk.END, f"Assignment Output File: {result.output_filepath}\n")
        
        self.results_text.insert(tk.END, "\n--- Student Assignment Details ---\n")
        if result.assignments:
            for student_id, seminar_id in result.assignments.items():
                self.results_text.insert(tk.END, f"Student {student_id}: Seminar {seminar_id}\n")
        else:
            self.results_text.insert(tk.END, "No assignment data.\n")

        self.results_text.config(state=tk.DISABLED)
        logger.info("Optimization results displayed in GUI.")
        self._update_status_bar("Optimization results displayed.", "info")

    def _update_results_text(self, message: str):
        """Helper to add messages to the results display text area."""
        if self.results_text:
            self.results_text.config(state=tk.NORMAL)
            self.results_text.insert(tk.END, message)
            self.results_text.see(tk.END)
            self.results_text.config(state=tk.DISABLED)

    def _generate_reports(self, result: OptimizationResult):
        """Generates reports from optimization results."""
        logger.debug("Starting report generation.")
        output_dir = PROJECT_ROOT / "output"
        output_dir.mkdir(parents=True, exist_ok=True) # Ensure output directory exists
        logger.debug(f"Report output directory: {output_dir}")
        self._update_status_bar("Generating reports...", "info")

        base_filename = f"seminar_assignment_{result.strategy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        if self.generate_csv_report_var.get():
            try:
                csv_filepath = output_dir / f"{base_filename}.csv"
                save_csv_results(result, str(csv_filepath))
                messagebox.showinfo("Report Generation", f"CSV report generated:\n{csv_filepath}")
                logger.info(f"CSV report generated: {csv_filepath}")
                self._update_status_bar(f"CSV report generated: {csv_filepath.name}", "info")
            except Exception as e:
                messagebox.showerror("Report Error", f"An error occurred while generating the CSV report: {e}")
                logger.error(f"CSV report generation error: {e}", exc_info=True)
                self._update_status_bar("Error generating CSV report.", "error")
        else:
            logger.info("CSV report generation is disabled.")

        if self.generate_pdf_report_var.get():
            try:
                pdf_filepath = output_dir / f"{base_filename}.pdf"
                # Pass original data for report generation
                save_pdf_report(result, self.seminars_data_for_report, self.students_data_for_report, str(pdf_filepath))
                messagebox.showinfo("Report Generation", f"PDF report generated:\n{pdf_filepath}")
                logger.info(f"PDF report generated: {pdf_filepath}")
                self._update_status_bar(f"PDF report generated: {pdf_filepath.name}", "info")
            except ImportError:
                messagebox.showwarning("Report Generation", "ReportLab is not installed. PDF report cannot be generated. Please run `pip install reportlab`.")
                logger.warning("ReportLab not installed, PDF report could not be generated.")
                self._update_status_bar("Warning: ReportLab not installed, PDF report skipped.", "warning")
            except Exception as e:
                messagebox.showerror("Report Error", f"An error occurred while generating the PDF report: {e}")
                logger.error(f"PDF report generation error: {e}", exc_info=True)
                self._update_status_bar("Error generating PDF report.", "error")
        else:
            logger.info("PDF report generation is disabled.")

    def _on_closing(self):
        """Handles closing the window: saves settings and exits the application."""
        logger.info("Exiting application.")
        self._update_status_bar("Exiting application...", "info")
        if self.is_optimizing:
            if not messagebox.askyesno("Confirmation", "Optimization process is running. Exiting will interrupt it. Do you want to proceed?"):
                logger.debug("Exit process cancelled by user.")
                self._update_status_bar("Exit cancelled.", "info")
                return
            self.cancel_event.set() # Notify running thread to cancel
            if self.optimization_thread and self.optimization_thread.is_alive():
                self.optimization_thread.join(timeout=5) # Wait for thread to finish
                if self.optimization_thread.is_alive():
                    logger.warning("Optimization thread did not terminate within timeout. Forcing exit.")
                    self._update_status_bar("Warning: Optimization thread did not terminate.", "warning")
        
        # Save GUI settings
        self._save_current_gui_settings()

        # Close progress dialog if open
        if self.progress_dialog:
            self.progress_dialog.close()

        # Remove TextHandler from logger
        if self.text_handler:
            logging.getLogger().removeHandler(self.text_handler)
            logger.debug("TextHandler removed from logger.")
            self.text_handler.close() # Release handler resources

        self.root.destroy()
        logger.info("Application exited successfully.")


if __name__ == "__main__":
    logger.info("Starting application.")
    root = tk.Tk()
    app = SeminarGUI(root)
    root.mainloop()
    logger.info("Main loop exited.")