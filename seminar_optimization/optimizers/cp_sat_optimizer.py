from ortools.sat.python import cp_model
import time
import threading
import logging # ロギングを追加
from typing import Dict, List, Any, Callable, Optional, Tuple

# BaseOptimizerとOptimizationResultをutilsからインポート
from seminar_optimization.seminar_optimization.utils import BaseOptimizer, OptimizationResult # <-- 修正: 相対インポート
# ロギングは logger_config.py で一元的に設定されるため、ここではロガーの取得のみ
from seminar_optimization.seminar_optimization.logger_config import logger # <-- 修正: 相対インポート

class CPSATOptimizer(BaseOptimizer): # BaseOptimizerを継承
    """
    制約プログラミング (CP-SAT) を用いたセミナー割り当て最適化アルゴリズム。
    Google OR-Tools の CP-SAT ソルバーを使用する。
    """
    def __init__(self,
                 seminars: List[Dict[str, Any]],
                 students: List[Dict[str, Any]],
                 config: Dict[str, Any],
                 progress_callback: Optional[Callable[[str], None]] = None): # progress_callbackを追加
        # BaseOptimizerの__init__を呼び出す
        super().__init__(seminars, students, config, progress_callback)
        logger.debug("CPSATOptimizer: 初期化を開始シマス。")

        # 固有のパラメータはconfigから取得
        self.time_limit = config.get("cp_time_limit", 300) # 秒
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = self.time_limit
        self.solver.parameters.num_workers = config.get("max_workers", 8) # 並列処理ワーカー数
        logger.debug(f"CPSATOptimizer: タイムリミット: {self.time_limit}秒, ワーカー数: {self.solver.parameters.num_workers}")

    def optimize(self, cancel_event: Optional[threading.Event] = None) -> OptimizationResult:
        """
        CP-SATモデルを構築し、ソルバーで最適化を実行する。
        """
        start_time = time.time()
        self._log("CP-SAT 最適化を開始します...")

        model = cp_model.CpModel()

        # 変数の定義: x[s][j] = 1 なら学生jがセミナーsに割り当てられる
        x = {}
        for student_id in self.student_ids:
            for seminar_id in self.seminar_ids:
                x[(student_id, seminar_id)] = model.NewBoolVar(f'x_{student_id}_{seminar_id}')
        logger.debug("CPSATOptimizer: 割り当て変数を定義しました。")

        # 制約1: 各学生は最大で1つのセミナーに割り当てられる
        for student_id in self.student_ids:
            model.AddAtMostOne([x[(student_id, seminar_id)] for seminar_id in self.seminar_ids])
        logger.debug("CPSATOptimizer: 各学生は最大1つのセミナーに割り当てられる制約を追加しました。")

        # 制約2: 各セミナーの定員制約
        for seminar_id in self.seminar_ids:
            capacity = self.seminar_capacities[seminar_id]
            model.Add(sum(x[(student_id, seminar_id)] for student_id in self.student_ids) <= capacity)
        logger.debug("CPSATOptimizer: 各セミナーの定員制約を追加しました。")

        # 目的関数の定義: 希望順位に基づいてスコアを最大化
        obj_terms = []
        score_weights = self.config.get("score_weights", {
            "1st_choice": 3.0, "2nd_choice": 2.0, "3rd_choice": 1.0, "other_preference": 0.5
        })
        
        for student_id in self.student_ids:
            preferences = self.student_preferences.get(student_id, [])
            for i, preferred_seminar_id in enumerate(preferences):
                if preferred_seminar_id not in self.seminar_ids:
                    logger.warning(f"CPSATOptimizer: 学生 {student_id} の希望セミナー '{preferred_seminar_id}' が存在しません。スキップします。")
                    continue # 存在しないセミナーはスキップ

                weight = 0.0
                if i == 0: # 1st choice
                    weight = score_weights["1st_choice"]
                elif i == 1: # 2nd choice
                    weight = score_weights["2nd_choice"]
                elif i == 2: # 3rd choice
                    weight = score_weights["3rd_choice"]
                else: # Other preferences
                    weight = score_weights["other_preference"]
                
                magnification = self.seminar_magnifications.get(preferred_seminar_id, 1.0)
                obj_terms.append(x[(student_id, preferred_seminar_id)] * weight * magnification)
        
        model.Maximize(sum(obj_terms))
        self._log("CPSATOptimizer: 目的関数を定義しました。")

        # キャンセルイベントが設定された場合、ソルバーを停止するコールバック
        class SolutionCallback(cp_model.CpSolverSolutionCallback):
            def __init__(self, cancel_event: threading.Event, progress_callback: Callable[[str], None], solver_instance):
                cp_model.CpSolverSolutionCallback.__init__(self)
                self._cancel_event = cancel_event
                self._progress_callback = progress_callback
                self._solver = solver_instance
                self._start_time = time.time()
                self._last_log_time = time.time()
                logger.debug("CPSATOptimizer: SolutionCallback を初期化しました。")

            def on_solution_callback(self):
                if self._cancel_event.is_set():
                    logger.info("CPSATOptimizer: キャンセルイベントが検出されました。ソルバーを停止します。")
                    self.StopSearch()
                    return
                
                current_time = time.time()
                if current_time - self._last_log_time > 5: # 5秒ごとに進捗を報告
                    self._progress_callback(f"CP-SAT: 実行中... 経過時間: {current_time - self._start_time:.1f}秒, 現在のベストスコア: {self.ObjectiveValue():.2f}")
                    self._last_log_time = current_time

        # ソルバーの実行
        solution_callback = SolutionCallback(cancel_event, self.progress_callback, self.solver)
        status = self.solver.Solve(model, solution_callback)
        self._log(f"CP-SAT: ソルバーのステータス: {self.solver.StatusName(status)}")

        final_assignment: Dict[str, str] = {}
        final_score = -float('inf')
        status_str = "FAILED"
        message = "CP-SAT最適化が失敗しました。"

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            final_score = self.solver.ObjectiveValue()
            for student_id in self.student_ids:
                for seminar_id in self.seminar_ids:
                    if self.solver.Value(x[(student_id, seminar_id)]) == 1:
                        final_assignment[student_id] = seminar_id
            
            if self._is_feasible_assignment(final_assignment):
                status_str = "OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE"
                message = "CP-SAT最適化が成功しました。"
                self._log(f"CPSATOptimizer: 最適解または実行可能解が見つかりました。スコア: {final_score:.2f}")
            else:
                status_str = "INFEASIBLE"
                message = "CP-SATソルバーが実行不可能な解を返しました。定員制約を満たしていません。"
                final_assignment = {} # 無効な割り当てはクリア
                final_score = -float('inf')
                self._log(f"CPSATOptimizer: ソルバーが返した解が実行不可能です。")

        elif status == cp_model.INFEASIBLE:
            status_str = "INFEASIBLE"
            message = "CP-SATモデルが実行不可能です。制約が厳しすぎる可能性があります。"
            self._log(message, level=logging.ERROR)
            logger.error("CPSATOptimizer: モデルが実行不可能です。制約が厳しすぎる可能性があります。")
        elif status == cp_model.MODEL_INVALID:
            status_str = "MODEL_INVALID"
            message = "CP-SATモデルが無効です。"
            self._log(message, level=logging.ERROR)
            logger.error("CPSATOptimizer: モデルの構築が無効です。変数の定義や制約に誤りがないか確認してください。")
        elif status == cp_model.CANCELLED:
            status_str = "CANCELLED"
            message = "CP-SATソルバーがキャンセルされました。"
            self._log(message)
            logger.info("CPSATOptimizer: ソルバーが外部からキャンセルされました。")
        else:
            status_str = "NO_SOLUTION_FOUND"
            message = f"CP-SATソルバーで解が見つかりませんでした。ステータス: {self.solver.StatusName(status)}"
            self._log(message, level=logging.WARNING)
            logger.warning(f"CPSATOptimizer: 解が見つからないステータスです: {self.solver.StatusName(status)}")

        end_time = time.time()
        duration = end_time - start_time
        self._log(f"CP-SAT 最適化完了。実行時間: {duration:.2f}秒")
        logger.debug(f"CPSATOptimizer: 最終割り当ての実行可能性チェック: {self._is_feasible_assignment(final_assignment)}")

        unassigned_students = self._get_unassigned_students(final_assignment)

        return OptimizationResult(
            status=status_str,
            message=message,
            best_score=final_score,
            best_assignment=final_assignment,
            seminar_capacities=self.seminar_capacities,
            unassigned_students=unassigned_students,
            optimization_strategy="CP"
        )
