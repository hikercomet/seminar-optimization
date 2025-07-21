import logging
from ortools.sat.python import cp_model
import time
import threading
from typing import Dict, List, Any, Callable, Optional, Tuple

# BaseOptimizerとOptimizationResultをutilsからインポート
from utils import BaseOptimizer, OptimizationResult

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # DEBUGレベルのメッセージも出力

class CPSATOptimizer(BaseOptimizer): # BaseOptimizerを継承
    """
    制約プログラミング (CP-SAT) を用いたセミナー割り当て最適化アルゴリズム。
    Google OR-Tools の CP-SAT ソルバーを使用する。
    """
    def __init__(self,
                 seminars: List[Dict[str, Any]],
                 students: List[Dict[str, Any]],
                 config: Dict[str, Any],\
                 progress_callback: Optional[Callable[[str], None]] = None): # progress_callbackを追加
        # BaseOptimizerの__init__を呼び出す
        super().__init__(seminars, students, config, progress_callback)
        logger.debug("CPSATOptimizer: 初期化を開始シマス。")

        # 固有のパラメータはconfigから取得
        self.time_limit = config.get("cp_time_limit", 300) # 秒
        self.solver = cp_model.CpSolver()
        self.solver.parameters.max_time_in_seconds = self.time_limit
        self.solver.parameters.num_workers = config.get("max_workers", 8) # 並列ワーカー数
        logger.info(f"CPSATOptimizer: タイムリミット: {self.time_limit}秒, ワーカー数: {self.solver.parameters.num_workers}")

    def optimize(self, cancel_event: Optional[threading.Event] = None) -> OptimizationResult:
        """
        CP-SAT最適化を実行する。
        """
        self._log("CP-SAT 最適化を開始シマス。")
        start_time = time.time()
        logger.debug("CPSATOptimizer: optimize メソッド呼び出し。")

        model = cp_model.CpModel()
        logger.debug("CPSATOptimizer: CP-SATモデルを初期化しました。")

        # 変数: student_seminar_vars[学生ID][セミナーID] = 1 (割り当てられた場合) / 0 (それ以外)
        # 各学生は1つのセミナーにのみ割り当てられる
        student_seminar_vars: Dict[str, Dict[str, cp_model.IntVar]] = {}
        for student_id in self.student_ids:
            student_seminar_vars[student_id] = {}
            for seminar_id in self.seminar_ids:
                student_seminar_vars[student_id][seminar_id] = model.NewBoolVar(f'x_{student_id}_{seminar_id}')
            logger.debug(f"CPSATOptimizer: 学生 {student_id} の割り当て変数を生成しました。")

        # 制約1: 各学生はちょうど1つのセミナーに割り当てられる
        for student_id in self.student_ids:
            model.Add(sum(student_seminar_vars[student_id][seminar_id] for seminar_id in self.seminar_ids) == 1)
            logger.debug(f"CPSATOptimizer: 学生 {student_id} が1つのセミナーに割り当てられる制約を追加しました。")

        # 制約2: 各セミナーの定員制約
        for seminar_id in self.seminar_ids:
            capacity = self.seminar_capacities.get(seminar_id, 0)
            model.Add(sum(student_seminar_vars[student_id][seminar_id] for student_id in self.student_ids) <= capacity)
            logger.debug(f"CPSATOptimizer: セミナー {seminar_id} の定員制約 ({capacity}) を追加しました。")

        # 目的関数: 学生の希望順位とセミナーの倍率に基づいてスコアを最大化
        objective_expr = []
        for student_id in self.student_ids:
            preferences = self.student_preferences.get(student_id, [])
            magnification_factor = 1.0 # デフォルトの倍率

            # スコア計算の重み付けをconfigから取得、デフォルト値を設定
            score_weights = self.config.get("score_weights", {
                "1st_choice": 3.0,
                "2nd_choice": 2.0,
                "3rd_choice": 1.0,
                "other_preference": 0.5
            })
            logger.debug(f"CPSATOptimizer: 学生 {student_id} の目的関数項を構築中。スコア重み: {score_weights}")

            for seminar_id in self.seminar_ids:
                # この割り当てが学生の希望リストにあるか確認
                if seminar_id in preferences:
                    rank = preferences.index(seminar_id) + 1
                    seminar_magnification = self.seminar_magnifications.get(seminar_id, 1.0)
                    
                    score_value = 0.0
                    if rank == 1:
                        score_value = score_weights["1st_choice"]
                    elif rank == 2:
                        score_value = score_weights["2nd_choice"]
                    elif rank == 3:
                        score_value = score_weights["3rd_choice"]
                    else:
                        score_value = score_weights["other_preference"]
                    
                    # 倍率を適用
                    weighted_score = score_value * seminar_magnification
                    objective_expr.append(student_seminar_vars[student_id][seminar_id] * weighted_score)
                    logger.debug(f"CPSATOptimizer: 学生 {student_id} -> セミナー {seminar_id} (第{rank}希望, 倍率 {seminar_magnification:.2f}): スコア係数 {weighted_score:.2f} を追加。")
                else:
                    # 希望リストにないセミナーへの割り当ては0点
                    objective_expr.append(student_seminar_vars[student_id][seminar_id] * 0)
                    logger.debug(f"CPSATOptimizer: 学生 {student_id} -> セミナー {seminar_id} (希望外): スコア係数 0 を追加。")
        
        model.Maximize(sum(objective_expr))
        self._log("CP-SAT: モデル構築完了。ソルバーを実行シマス。")
        logger.debug("CPSATOptimizer: 目的関数を最大化するように設定しました。")

        # 最適化の実行
        status = self.solver.Solve(model)
        logger.debug(f"CPSATOptimizer: ソルバー実行ステータス: {self.solver.StatusName(status)}")

        final_assignment: Dict[str, str] = {}
        final_score: float = -float('inf')
        status_str: str = "NO_SOLUTION_FOUND"
        message: str = "CP-SATソルバーで解が見つかりませんでした。"
        unassigned_students: List[str] = []

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            status_str = self.solver.StatusName(status) # OPTIMAL or FEASIBLE
            message = "CP-SAT最適化が成功しました。"
            for student_id in self.student_ids:
                for seminar_id in self.seminar_ids:
                    if self.solver.Value(student_seminar_vars[student_id][seminar_id]) == 1:
                        final_assignment[student_id] = seminar_id
                        logger.debug(f"CPSATOptimizer: ソルバー結果: 学生 {student_id} はセミナー {seminar_id} に割り当てられました。")
                        break # 各学生は1つのセミナーに割り当てられるため
            final_score = self.solver.ObjectiveValue()
            unassigned_students = self._get_unassigned_students(final_assignment) # BaseOptimizerから継承
            self._log(f"CP-SAT: 最適解が見つかりました。スコア: {final_score:.2f}, 未割り当て学生数: {len(unassigned_students)}")

        elif status == cp_model.INFEASIBLE:
            status_str = "INFEASIBLE"
            message = "CP-SATモデルは実行不可能です。制約を見直してください。"
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

        return OptimizationResult(
            status=status_str,
            message=message,
            best_score=final_score,
            best_assignment=final_assignment,
            seminar_capacities=self.seminar_capacities,
            unassigned_students=unassigned_students,
            optimization_strategy="CP"
        )

