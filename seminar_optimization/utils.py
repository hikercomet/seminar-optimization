import logging
from typing import Dict, List, Any, Callable, Optional, Tuple, Literal
import time
import random
import threading
import numpy as np

# ロガーの設定を強化
# ロギングは logger_config.py で一元的に設定されるため、ここではロガーの取得のみ
from seminar_optimization.logger_config import logger # <-- 修正: 相対インポート


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
        logger.debug(f"OptimizationResult: 新しい結果オブジェクトが作成されました。ステータス: {status}, スコア: {best_score:.2f}")
        self.status = status
        self.message = message
        self.best_score = best_score
        self.best_assignment = best_assignment
        self.seminar_capacities = seminar_capacities
        self.unassigned_students = unassigned_students
        self.optimization_strategy = optimization_strategy
        logger.debug(f"OptimizationResult: 未割り当て学生数: {len(self.unassigned_students)}")

    def to_dict(self) -> Dict[str, Any]:
        """結果を辞書形式で返す"""
        logger.debug("OptimizationResult: 結果を辞書形式に変換しています。")
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
    共通のロジック（スコア計算、制約チェックなど）を提供する。
    """
    def __init__(self,
                 seminars: List[Dict[str, Any]],
                 students: List[Dict[str, Any]],
                 config: Dict[str, Any],
                 progress_callback: Optional[Callable[[str], None]] = None):
        logger.debug("BaseOptimizer: 初期化を開始シマス。")
        self.seminars = seminars
        self.students = students
        self.config = config
        self.progress_callback = progress_callback

        # 乱数シードを初期化
        random_seed = config.get("random_seed")
        if random_seed is not None:
            random.seed(random_seed)
            np.random.seed(random_seed)
            logger.info(f"BaseOptimizer: 乱数シードを {random_seed} に設定しました。")
        else:
            logger.info("BaseOptimizer: 乱数シードが設定されていません。")


        self.seminar_capacities: Dict[str, int] = {s['id']: s['capacity'] for s in seminars}
        self.seminar_magnifications: Dict[str, float] = {s['id']: s.get('magnification', 1.0) for s in seminars} # 倍率を初期化
        self.student_preferences: Dict[str, List[str]] = {s['id']: s['preferences'] for s in students}
        self.student_ids: List[str] = [s['id'] for s in students]
        self.seminar_ids: List[str] = [s['id'] for s in seminars]

        logger.info(f"BaseOptimizer: 学生数={len(self.student_ids)}, セミナー数={len(self.seminar_ids)} で初期化されました。")
        logger.debug(f"BaseOptimizer: セミナー定員: {self.seminar_capacities}")
        logger.debug(f"BaseOptimizer: セミナー倍率: {self.seminar_magnifications}")
        logger.debug(f"BaseOptimizer: 設定: {self.config}")

    def _log(self, message: str, level: int = logging.INFO):
        """
        ログメッセージを出力し、進捗コールバックがあれば呼び出す。
        """
        logger.log(level, message)
        if self.progress_callback:
            self.progress_callback(message)
        logger.debug(f"_log: メッセージ '{message}' (レベル: {logging.getLevelName(level)}) が処理されました。")

    def _calculate_score(self, assignment: Dict[str, str]) -> float:
        """
        与えられた割り当ての合計スコアを計算する。

        各学生の希望順位に基づいてスコアを付与し、セミナーの倍率を考慮する。
        スコアの重みは `self.config` の "score_weights" から取得される。
        デフォルトの重みは以下の通り:
        - 第1希望: 3.0点
        - 第2希望: 2.0点
        - 第3希望: 1.0点
        - その他の希望: 0.5点
        - 希望リストにないセミナーへの割り当て、または未割り当て: 0点

        Args:
            assignment (Dict[str, str]): 学生IDをキー、割り当てられたセミナーIDを値とする辞書。

        Returns:
            float: 計算された合計スコア。
        """
        score = 0.0
        logger.debug(f"_calculate_score: 割り当てのスコア計算を開始シマス。割り当て数: {len(assignment)}")
        
        # スコア計算の重み付けをconfigから取得、デフォルト値を設定
        score_weights = self.config.get("score_weights", {
            "1st_choice": 3.0,
            "2nd_choice": 2.0,
            "3rd_choice": 1.0,
            "other_preference": 0.5
        })
        logger.debug(f"_calculate_score: スコア重み: {score_weights}")

        for student_id, assigned_seminar_id in assignment.items():
            if student_id not in self.student_preferences:
                logger.warning(f"_calculate_score: 学生ID '{student_id}' の希望が見つかりませんでした。スキップシマス。")
                continue

            preferences = self.student_preferences[student_id]
            magnification = self.seminar_magnifications.get(assigned_seminar_id, 1.0) # 倍率を取得、デフォルトは1.0
            
            student_score_added = 0.0 # この学生に加算されるスコア

            try:
                rank = preferences.index(assigned_seminar_id) + 1 # 0-indexed to 1-indexed
                if rank == 1:
                    student_score_added = score_weights["1st_choice"] * magnification
                elif rank == 2:
                    student_score_added = score_weights["2nd_choice"] * magnification
                elif rank == 3:
                    student_score_added = score_weights["3rd_choice"] * magnification
                else:
                    # 4位以下の場合も希望リストに含まれていれば0.5点
                    student_score_added = score_weights["other_preference"] * magnification
                
                score += student_score_added
                logger.debug(f"学生 {student_id}: セミナー {assigned_seminar_id} (第{rank}希望) に割り当て。スコア +{student_score_added:.2f} (合計: {score:.2f})")

            except ValueError:
                # 希望リストにないセミナーに割り当てられた場合（または未割り当て）
                # スコアは加算されない（初期値0のまま）
                logger.debug(f"学生 {student_id}: 希望外のセミナー ({assigned_seminar_id}) に割り当てられたか、未割り当てです。スコア変更なし。")
                pass # スコアは0点のまま

        logger.info(f"_calculate_score: 合計スコア: {score:.2f}")
        return score

    def _is_feasible_assignment(self, assignment: Dict[str, str]) -> bool:
        """
        与えられた割り当てが定員制約を満たしているかチェックする。
        """
        logger.debug(f"_is_feasible_assignment: 定員制約チェックを開始シマス。割り当て数: {len(assignment)}")
        seminar_counts: Dict[str, int] = {s_id: 0 for s_id in self.seminar_ids}
        
        # 割り当てられた学生数をカウント
        for student_id, seminar_id in assignment.items():
            if seminar_id in seminar_counts:
                seminar_counts[seminar_id] += 1
                logger.debug(f"学生 {student_id} がセミナー {seminar_id} に割り当てられました。現在のカウント: {seminar_counts[seminar_id]}")
            else:
                logger.warning(f"_is_feasible_assignment: 不正なセミナーID '{seminar_id}' が割り当てに存在シマス。無効な割り当てです。")
                return False # 存在しないセミナーIDへの割り当ては不正

        # 定員と比較
        for seminar_id, count in seminar_counts.items():
            capacity = self.seminar_capacities.get(seminar_id, 0)
            if count > capacity:
                logger.warning(f"_is_feasible_assignment: 制約違反: セミナー '{seminar_id}' の定員 ({capacity}) を超えています ({count}人割り当て)。")
                return False
            else:
                logger.debug(f"セミナー '{seminar_id}': 割り当て数 {count} / 定員 {capacity} (OK)")
        logger.info("_is_feasible_assignment: すべての定員制約を満たしています。割り当ては実行可能です。")
        return True

    def _get_unassigned_students(self, assignment: Dict[str, str]) -> List[str]:
        """
        割り当てられていない学生のリストを返す。
        """
        logger.debug("_get_unassigned_students: 未割り当て学生のリストを生成シマス。")
        assigned_student_ids = set(assignment.keys())
        all_student_ids = set(self.student_ids)
        unassigned = list(all_student_ids - assigned_student_ids)
        logger.info(f"_get_unassigned_students: 未割り当て学生数: {len(unassigned)}")
        if unassigned:
            logger.debug(f"_get_unassigned_students: 未割り当て学生リスト: {unassigned}")
        return unassigned

    def optimize(self, cancel_event: Optional[threading.Event] = None) -> OptimizationResult:
        """
        このメソッドは各サブクラスで実装されるべき抽象メソッド。
        最適化を実行し、結果を OptimizationResult オブジェクトとして返します。
        cancel_event を受け取り、最適化の途中でキャンセルできるようにします。
        """
        logger.error("BaseOptimizer: optimize メソッドはサブクラスで実装されていません。")
        raise NotImplementedError("Subclasses must implement the optimize method.")

