import tkinter as tk
from tkinter import ttk
from typing import Optional, Callable
import logging

logger = logging.getLogger(__name__)

class ProgressDialog:
    def __init__(self, parent: tk.Tk, cancel_command: Optional[Callable] = None):
        self.parent = parent
        self.dialog: Optional[tk.Toplevel] = None
        self.progress_label: Optional[ttk.Label] = None
        self.progress_bar: Optional[ttk.Progressbar] = None
        self.cancel_command = cancel_command

    def show(self):
        """プログレスダイアログを表示する。"""
        logger.debug("ProgressDialog: ダイアログを表示します。")
        if self.dialog is None or not self.dialog.winfo_exists():
            self.dialog = tk.Toplevel(self.parent)
            self.dialog.title("最適化の進捗")
            self.dialog.geometry("400x150")
            self.dialog.transient(self.parent) # 親ウィンドウの上に表示
            self.dialog.grab_set() # 他のウィンドウ操作をブロック

            self.progress_label = ttk.Label(self.dialog, text="最適化を開始しています...", wraplength=350)
            self.progress_label.pack(pady=20)

            self.progress_bar = ttk.Progressbar(self.dialog, mode='indeterminate', length=300)
            self.progress_bar.pack(pady=10)
            self.progress_bar.start(5) # 5msごとに更新

            if self.cancel_command:
                ttk.Button(self.dialog, text="キャンセル", command=self.cancel_command).pack(pady=5)
            
            # ウィンドウが閉じられたときの処理
            self.dialog.protocol("WM_DELETE_WINDOW", self.cancel_command if self.cancel_command else self.hide)
        else:
            self.dialog.deiconify() # 既に存在する場合は再表示
        logger.debug("ProgressDialog: ダイアログが表示されました。")

    def update_message(self, message: str):
        """プログレスダイアログのメッセージを更新する。"""
        if self.progress_dialog and self.progress_label:
            self.progress_label.config(text=message)
            self.dialog.update_idletasks() # UIを即座に更新

    def hide(self):
        """プログレスダイアログを非表示にする。"""
        logger.debug("ProgressDialog: ダイアログを非表示にします。")
        if self.dialog and self.dialog.winfo_exists():
            if self.progress_bar:
                self.progress_bar.stop()
            self.dialog.grab_release() # ブロックを解除
            self.dialog.destroy()
            self.dialog = None
            self.progress_label = None
            self.progress_bar = None
        logger.debug("ProgressDialog: ダイアログが非表示になりました。")
