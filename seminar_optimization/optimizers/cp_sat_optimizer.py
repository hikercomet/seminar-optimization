import logging
from ortools.sat.python import cp_model
import time
import threading
from typing import Dict, List, Any, Callable, Optional, Tuple

# BaseOptimizerとOptimizationResultをutilsからインポート
from utils import BaseOptimizer, OptimizationResult

logger = logging.getLogger(__name__)

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

        # 固有のパラメータはconfigから取得
        self.time_limit = config.get("cp_time_limit", 300) # 秒
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = self.time_limit
        self.solver.parameters.num_workers = config.get("max_workers", 8) # 並列ワーカー数

    # _calculate_score はBaseOptimizerから継承されるため削除

    def optimize(self) -> OptimizationResult: # 返り値をOptimizationResultに
        """
        CP-SATモデルを構築し、最適化を実行する。
        """
        self._log("CP-SAT 最適化を開始します。")
        start_time = time.time()

        model = cp_model.CpModel()

        # 変数: x[(学生ID, セミナーID)] = 1 なら割り当て、0 なら割り当てなし
        x = {}
        for student in self.students:
            for seminar in self.seminars:
                x[(student['id'], seminar['id'])] = model.NewBoolVar(f'x_{student["id"]}_{seminar["id"]}')

        # 制約1: 各学生は1つのセミナーに割り当てられる
        for student in self.students:
            model.Add(sum(x[(student['id'], s['id'])] for s in self.seminars) == 1)

        # 制約2: 各セミナーの定員を超えない
        for seminar in self.seminars:
            model.Add(sum(x[(student['id'], seminar['id'])] for student in self.students) <= seminar['capacity'])

        # 目的関数: 希望順位に応じたスコアの最大化
        objective_terms = []
        for student in self.students:
            student_id = student['id']
            preferences = student['preferences']
            for rank, preferred_seminar_id in enumerate(preferences):
                # 希望リストにないセミナーは考慮しない
                if preferred_seminar_id in self.seminar_ids:
                    weight = 0.0
                    if rank == 0: weight = self.preference_weights.get("1st", 5.0)
                    elif rank == 1: weight = self.preference_weights.get("2nd", 2.0)
                    elif rank == 2: weight = self.preference_weights.get("3rd", 1.0)
                    
                    # x変数が存在するか確認してから追加
                    if (student_id, preferred_seminar_id) in x:
                        objective_terms.append(x[(student_id, preferred_seminar_id)] * weight)
        
        model.Maximize(sum(objective_terms))

        self._log("CP-SAT ソルバーを実行中...")
        status = self.solver.Solve(model)

        final_assignment: Dict[str, str] = {}
        final_score = -float('inf')
        status_str = "NO_SOLUTION_FOUND"
        message = "CP-SATソルバーで解が見つかりませんでした。"
        unassigned_students: List[str] = []

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            if status == cp_model.OPTIMAL:
                status_str = "OPTIMAL"
                message = f"CP-SAT最適解が見つかりました。スコア: {self.solver.ObjectiveValue():.2f}"
                self._log(message)
            else: # FEASIBLE
                status_str = "FEASIBLE"
                message = f"CP-SAT実行可能解が見つかりました (時間切れなど)。スコア: {self.solver.ObjectiveValue():.2f}"
                self._log(message, level=logging.WARNING)

            for student in self.students:
                for seminar in self.seminars:
                    if self.solver.Value(x[(student['id'], seminar['id'])]) == 1:
                        final_assignment[student['id']] = seminar['id']
                        break # 各学生は1つのセミナーに割り当てられるため
            final_score = self.solver.ObjectiveValue()
            unassigned_students = self._get_unassigned_students(final_assignment) # BaseOptimizerから継承

        elif status == cp_model.INFEASIBLE:
            status_str = "INFEASIBLE"
            message = "CP-SATモデルは実行不可能です。制約を見直してください。"
            self._log(message, level=logging.ERROR)
        elif status == cp_model.MODEL_INVALID:
            status_str = "MODEL_INVALID"
            message = "CP-SATモデルが無効です。"
            self._log(message, level=logging.ERROR)
        elif status == cp_model.CANCELLED:
            status_str = "CANCELLED"
            message = "CP-SATソルバーがキャンセルされました。"
            self._log(message)
        else:
            status_str = "NO_SOLUTION_FOUND"
            message = f"CP-SATソルバーで解が見つかりませんでした。ステータス: {self.solver.StatusName(status)}"
            self._log(message, level=logging.WARNING)

        end_time = time.time()
        duration = end_time - start_time
        self._log(f"CP-SAT 最適化完了。実行時間: {duration:.2f}秒")

        return OptimizationResult(
            status=status_str,
            message=message,
            best_score=final_score,
            best_assignment=final_assignment,
            seminar_capacities=self.seminar_capacities,
            unassigned_students=unassigned_students,
            optimization_strategy="CP"
        )

