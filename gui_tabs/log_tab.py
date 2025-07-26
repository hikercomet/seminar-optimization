import tkinter as tk
from tkinter import ttk
import tkinter.scrolledtext as scrolledtext
import logging
import threading
from typing import Optional
import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(True)
except:
    pass

logger = logging.getLogger(__name__)

class TextHandler(logging.Handler):
    def _on_mousewheel(self, event):
        # Windows/macOSではevent.deltaが使用され、Linuxではevent.num (Button-4/5) が使用される
        if event.delta: # Windows/macOS
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        elif event.num == 4: # Linux (スクロールアップ)
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5: # Linux (スクロールダウン)
            self.canvas.yview_scroll(1, "units")
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
        logger.debug("ResultsTab:Canvasとスクロールバーのウェジットをさくせいしました。")


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

class LogTab:
    def __init__(self, notebook: ttk.Notebook):
        self.notebook = notebook
        self.frame = ttk.Frame(notebook, padding="10")
        self.text_handler: Optional[TextHandler] = None # TextHandlerのインスタンスを保持
        self._create_widgets()

    def _create_widgets(self):
        """
        「ログ」タブのウィジェットを作成する。
        """
        logger.debug("LogTab: ウィジェットの作成を開始します。")
        self.log_text = scrolledtext.ScrolledText(self.frame, wrap=tk.WORD, state='disabled')
        self.log_text.pack(fill=tk.BOTH, expand=True, pady=10)

        # TextHandlerを設定
        self.text_handler = TextHandler(self.log_text)
        self.text_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
        # ここではロガーには追加しない。MainApplicationが取得して追加する。
        logger.debug("LogTab: ウィジェットの作成が完了しました。")

    def get_text_handler(self) -> TextHandler:
        """このタブのTextHandlerインスタンスを返す。"""
        return self.text_handler
