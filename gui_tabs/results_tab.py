import tkinter as tk
from tkinter import ttk
import tkinter.scrolledtext as scrolledtext
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class ResultsTab:
    def __init__(self, notebook: ttk.Notebook):
        self.notebook = notebook
        self.frame = ttk.Frame(notebook, padding="10")
        self._create_widgets()
    def _on_mousewheel(self, event):
        # Windows/macOSではevent.deltaが使用され、Linuxではevent.num (Button-4/5) が使用される
        if event.delta: # Windows/macOS
            self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        elif event.num == 4: # Linux (スクロールアップ)
            self.canvas.yview_scroll(-1, "units")
        elif event.num == 5: # Linux (スクロールダウン)
            self.canvas.yview_scroll(1, "units")

    def _create_widgets(self):
        """
        「最適化結果」タブのウィジェットを作成する。
        """
        logger.debug("ResultsTab: ウィジェットの作成を開始します。")
        # 結果表示エリア
        self.results_text = scrolledtext.ScrolledText(self.frame, wrap=tk.WORD, state='disabled', height=10)
        self.results_text.pack(fill=tk.BOTH, expand=True, pady=10)

        # 最適化詳細表示エリア (ツリービューなど)
        self.results_tree = ttk.Treeview(self.frame, columns=("Parameter", "Value"), show="headings")
        self.results_tree.heading("Parameter", text="パラメータ")
        self.results_tree.heading("Value", text="値")
        self.results_tree.column("Parameter", width=150, anchor=tk.W)
        self.results_tree.column("Value", width=250, anchor=tk.W)
        self.results_tree.pack(fill=tk.BOTH, expand=True, pady=10)
        logger.debug("ResultsTab: ウィジェットの作成が完了しました。")

    def display_results(self, result: Any):
        """
        最適化結果をUIに表示する。
        """
        logger.info("ResultsTab: 最適化結果をUIに表示します。")
        self.results_text.config(state='normal')
        self.results_text.delete(1.0, tk.END)

        if result:
            self.results_text.insert(tk.END, f"最適化ステータス: {result.status}\n")
            self.results_text.insert(tk.END, f"メッセージ: {result.message}\n")
            self.results_text.insert(tk.END, f"最適化戦略: {result.optimization_strategy}\n")
            self.results_text.insert(tk.END, f"ベストスコア: {result.best_score:.2f}\n")
            self.results_text.insert(tk.END, f"未割り当て学生数: {len(result.unassigned_students)}\n\n")

            self.results_text.insert(tk.END, "--- 割り当て結果 ---\n")
            if result.best_assignment:
                for student_id, seminar_id in result.best_assignment.items():
                    self.results_text.insert(tk.END, f"学生 {student_id}: {seminar_id}\n")
            else:
                self.results_text.insert(tk.END, "割り当てられた学生はいません。\n")

            self.results_text.insert(tk.END, "\n--- 未割り当て学生 ---\n")
            if result.unassigned_students:
                for student_id in result.unassigned_students:
                    self.results_text.insert(tk.END, f"学生 {student_id}\n")
            else:
                self.results_text.insert(tk.END, "未割り当て学生はいません。\n")

            # ツリービューに詳細を表示
            self.results_tree.delete(*self.results_tree.get_children()) # 既存の項目をクリア
            self.results_tree.insert("", "end", values=("最適化ステータス", result.status))
            self.results_tree.insert("", "end", values=("最適化戦略", result.optimization_strategy))
            self.results_tree.insert("", "end", values=("ベストスコア", f"{result.best_score:.2f}"))
            self.results_tree.insert("", "end", values=("未割り当て学生数", len(result.unassigned_students)))

            # セミナーごとの割り当て数を計算して表示
            seminar_counts: Dict[str, int] = {sem_id: 0 for sem_id in result.seminar_capacities.keys()}
            for assigned_seminar_id in result.best_assignment.values():
                if assigned_seminar_id in seminar_counts:
                    seminar_counts[assigned_seminar_id] += 1
            
            self.results_tree.insert("", "end", values=("", "")) # 区切り
            self.results_tree.insert("", "end", values=("セミナー割り当て概要", ""))
            for sem_id, count in seminar_counts.items():
                capacity = result.seminar_capacities.get(sem_id, "N/A")
                self.results_tree.insert("", "end", values=(f"  {sem_id} (定員 {capacity})", f"{count}人"))
        else:
            self.results_text.insert(tk.END, "最適化結果がありません。\n")

        self.results_text.config(state='disabled')
        logger.info("ResultsTab: 最適化結果のUI表示が完了しました。")

    def clear_results(self):
        """結果表示エリアをクリアする。"""
        logger.info("ResultsTab: 結果表示エリアをクリアします。")
        self.results_text.config(state='normal')
        self.results_text.delete(1.0, tk.END)
        self.results_text.config(state='disabled')
        self.results_tree.delete(*self.results_tree.get_children())
