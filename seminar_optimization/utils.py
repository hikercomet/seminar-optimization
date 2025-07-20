import logging
from typing import Dict, List, Any, Callable, Optional, Tuple, Literal
import time

logger = logging.getLogger(__name__)

class OptimizationResult:
    """
    最適化結果を格納するためのデータクラス。
    """
    def __init__(self,
                 status: Literal["OPTIMAL", "FEASIBLE", "INFEASIBLE", "NO_SOLUTION_FOUND", "MODEL_INVALID", "CANCELLED", "FAILED", "RUNNING"],
                 message: str,
                 best_score: float,
                 best_assignment: Dict[str, str],
                 seminar_capacities: Dict[str, int],
                 unassigned_students: List[str],
                 optimization_strategy: str):
        self.status = status
        self.message = message
        self.best_score = best_score
        self.best_assignment = best_assignment
        self.seminar_capacities = seminar_capacities
        self.unassigned_students = unassigned_students
        self.optimization_strategy = optimization_strategy

    def to_dict(self) -> Dict[str, Any]:
        """結果を辞書形式で返す"""
        return {
            "status": self.status,
            "message": self.message,
            "best_score": self.best_score,
            "best_assignment": self.best_assignment,
            "seminar_capacities": self.seminar_capacities,
            "unassigned_students": self.unassigned_students,
            "optimization_strategy": self.optimization_strategy
        }

class BaseOptimizer:
    """
    すべての最適化アルゴリズムの基底クラス。
    共通の初期化ロジック、スコア計算、制約チェックなどを提供する。
    """
    def __init__(self,
                 seminars: List[Dict[str, Any]],
                 students: List[Dict[str, Any]],
                 config: Dict[str, Any],
                 progress_callback: Optional[Callable[[str], None]] = None):
        self.seminars = seminars
        self.students = students
        self.config = config
        self.progress_callback = progress_callback
        
        self.seminar_capacities = {s['id']: s['capacity'] for s in seminars}
        self.seminar_magnifications = {s['id']: s.get('magnification', 1.0) for s in seminars} # 倍率を考慮
        self.seminar_ids = [s['id'] for s in seminars]
        self.student_ids = [s['id'] for s in students]
        self.student_preferences = {s['id']: s['preferences'] for s in students}
        self.preference_weights = config.get("preference_weights", {"1st": 5.0, "2nd": 2.0, "3rd": 1.0})
        self.log_enabled = config.get("log_enabled", True)

    def _log(self, message: str, level: int = logging.INFO):
        """
        ロギングメッセージを出力し、GUIにプログレスを通知する。
        """
        if self.log_enabled:
            if level == logging.DEBUG:
                logger.debug(message)
            elif level == logging.INFO:
                logger.info(message)
            elif level == logging.WARNING:
                logger.warning(message)
            elif level == logging.ERROR:
                logger.error(message)
            elif level == logging.CRITICAL:
                logger.critical(message)
            else:
                logger.info(message) # デフォルト

        if self.progress_callback:
            # プログレスバーの更新やメッセージ表示のためにGUIにコールバック
            self.progress_callback(message)

    def _calculate_score(self, assignment: Dict[str, str]) -> float:
        """
        現在の割り当てのスコアを計算する。
        """
        score = 0.0
        for student_id, assigned_seminar_id in assignment.items():
            if student_id not in self.student_preferences:
                continue # 学生データが見つからない場合はスキップ

            preferences = self.student_preferences[student_id]
            
            try:
                rank = preferences.index(assigned_seminar_id)
                # 倍率を考慮した重み付け
                magnification = self.seminar_magnifications.get(assigned_seminar_id, 1.0)
                
                if rank == 0: # 1st choice
                    score += self.preference_weights.get("1st", 5.0) * magnification
                elif rank == 1: # 2nd choice
                    score += self.preference_weights.get("2nd", 2.0) * magnification
                elif rank == 2: # 3rd choice
                    score += self.preference_weights.get("3rd", 1.0) * magnification
                # 4位以下は0点
            except ValueError:
                # 希望リストにないセミナーに割り当てられた場合
                pass
        return score

    def _is_feasible_assignment(self, assignment: Dict[str, str]) -> bool:
        """
        与えられた割り当てが定員制約を満たしているかチェックする。
        """
        seminar_counts: Dict[str, int] = {s_id: 0 for s_id in self.seminar_ids}
        for student_id, seminar_id in assignment.items():
            if seminar_id in seminar_counts:
                seminar_counts[seminar_id] += 1
            else:
                # 存在しないセミナーIDへの割り当ては不正
                return False

        for seminar_id, count in seminar_counts.items():
            if count > self.seminar_capacities.get(seminar_id, 0):
                self._log(f"制約違反: セミナー '{seminar_id}' の定員 ({self.seminar_capacities.get(seminar_id, 0)}) を超えています ({count}人)", level=logging.DEBUG)
                return False
        return True

    def _get_unassigned_students(self, assignment: Dict[str, str]) -> List[str]:
        """
        割り当てられていない学生のリストを返す。
        """
        assigned_student_ids = set(assignment.keys())
        all_student_ids = set(self.student_ids)
        unassigned = list(all_student_ids - assigned_student_ids)
        return unassigned

    def optimize(self) -> OptimizationResult:
        """
        各最適化アルゴリズムはこのメソッドを実装する必要がある。
        """
        raise NotImplementedError("optimize method must be implemented by subclasses")

