import logging
import random
import time
from typing import Dict, List, Any, Callable, Optional, Tuple

# BaseOptimizerとOptimizationResultをutilsからインポート
from utils import BaseOptimizer, OptimizationResult

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # DEBUGレベルのメッセージも出力

class GreedyLSOptimizer(BaseOptimizer): # BaseOptimizerを継承
    """
    貪欲法と局所探索を組み合わせた最適化アルゴリズム。
    """
    def __init__(self,
                 seminars: List[Dict[str, Any]],
                 students: List[Dict[str, Any]],
                 config: Dict[str, Any],
                 progress_callback: Optional[Callable[[str], None]] = None): # progress_callbackを追加
        # BaseOptimizerの__init__を呼び出す
        super().__init__(seminars, students, config, progress_callback)
        logger.debug("GreedyLSOptimizer: 初期化を開始します。")

        # 固有のパラメータはconfigから取得
        self.iterations = config.get("greedy_ls_iterations", 200000)
        self.early_stop_no_improvement_limit = config.get("early_stop_no_improvement_limit", 5000)
        logger.debug(f"GreedyLSOptimizer: イテレーション数: {self.iterations}, 早期停止リミット: {self.early_stop_no_improvement_limit}")

    def _generate_initial_assignment(self) -> Dict[str, str]:
        """
        貪欲法で初期割り当てを生成する。
        学生をランダムな順序で処理し、希望するセミナーに可能な限り割り当てる。
        """
        self._log("Greedy_LS: 初期割り当てを貪欲法で生成中...")
        assignment: Dict[str, str] = {}
        seminar_current_counts: Dict[str, int] = {s_id: 0 for s_id in self.seminar_ids}
        
        # 学生をランダムな順序で処理することで、初期解の多様性を確保
        shuffled_student_ids = list(self.student_ids)
        random.shuffle(shuffled_student_ids)
        logger.debug(f"_generate_initial_assignment: シャッフルされた学生ID: {shuffled_student_ids[:5]}...") # 最初の5つだけ表示

        for student_id in shuffled_student_ids:
            student_preferences = self.student_preferences.get(student_id, [])
            assigned = False
            logger.debug(f"学生 {student_id} の割り当てを試行中。希望: {student_preferences}")

            for preferred_seminar_id in student_preferences:
                capacity = self.seminar_capacities.get(preferred_seminar_id, 0)
                current_count = seminar_current_counts.get(preferred_seminar_id, 0)

                if current_count < capacity:
                    assignment[student_id] = preferred_seminar_id
                    seminar_current_counts[preferred_seminar_id] += 1
                    assigned = True
                    logger.debug(f"学生 {student_id} をセミナー {preferred_seminar_id} に割り当てました。現在の定員: {current_count+1}/{capacity}")
                    break # この学生は割り当てられたので次の学生へ
                else:
                    logger.debug(f"セミナー {preferred_seminar_id} は満員です ({current_count}/{capacity})。")
            
            if not assigned:
                logger.debug(f"学生 {student_id} は初期割り当てで未割り当てのままです。")

        self._log(f"Greedy_LS: 初期割り当て生成完了。割り当て学生数: {len(assignment)}")
        logger.debug(f"_generate_initial_assignment: 初期割り当ての実行可能性チェック: {self._is_feasible_assignment(assignment)}")
        return assignment

    def _local_search(self, initial_assignment: Dict[str, str]) -> Tuple[Dict[str, str], float]:
        """
        局所探索で解を改善する。
        現在の割り当てから近傍解を生成し、スコアが改善すれば更新する。
        """
        self._log("Greedy_LS: 局所探索で解を改善中...")
        current_assignment = initial_assignment.copy()
        current_score = self._calculate_score(current_assignment)
        best_assignment = current_assignment.copy()
        best_score = current_score
        
        no_improvement_count = 0
        logger.info(f"Greedy_LS: 局所探索開始時のスコア: {best_score:.2f}")

        for i in range(self.iterations):
            if i % 10000 == 0: # 10000イテレーションごとに進捗を報告
                self._log(f"Greedy_LS: 局所探索イテレーション {i}/{self.iterations} (現在のベストスコア: {best_score:.2f})")
                logger.debug(f"Greedy_LS: 現在の割り当ての実行可能性チェック: {self._is_feasible_assignment(current_assignment)}")

            # 近傍解の生成戦略 (ここでは、ランダムな学生を別のセミナーに移動)
            # 1. ランダムな学生を選び、現在の割り当てから削除
            student_to_move_id = random.choice(list(current_assignment.keys()) + self.student_ids) # 割り当て済み or 未割り当てから選択
            
            temp_assignment = current_assignment.copy()
            original_seminar_id = temp_assignment.pop(student_to_move_id, None) # 割り当てられていなければNone

            # 2. その学生をランダムなセミナーに割り当てる (または未割り当てのままにする)
            possible_seminars = list(self.seminar_ids) + [None] # Noneは未割り当てを意味する
            random.shuffle(possible_seminars) # ランダムな順序でセミナーを試す

            found_better_neighbor = False
            for new_seminar_id in possible_seminars:
                neighbor_assignment = temp_assignment.copy()
                if new_seminar_id is not None:
                    neighbor_assignment[student_to_move_id] = new_seminar_id
                
                # 新しい割り当てが実行可能かチェック
                if self._is_feasible_assignment(neighbor_assignment):
                    neighbor_score = self._calculate_score(neighbor_assignment)
                    logger.debug(f"イテレーション {i}: 学生 {student_to_move_id} を {original_seminar_id} から {new_seminar_id} へ移動を試行。スコア: {neighbor_score:.2f}")

                    if neighbor_score > best_score:
                        best_score = neighbor_score
                        best_assignment = neighbor_assignment.copy()
                        no_improvement_count = 0 # 改善が見られたのでカウントをリセット
                        found_better_neighbor = True
                        logger.info(f"Greedy_LS: スコアが改善しました！新しいベストスコア: {best_score:.2f} (イテレーション {i})")
                        break # より良い解が見つかったので、この学生の移動はこれで確定
            
            if not found_better_neighbor:
                no_improvement_count += 1
                logger.debug(f"イテレーション {i}: 改善が見られませんでした。連続改善なしカウント: {no_improvement_count}")

            if no_improvement_count >= self.early_stop_no_improvement_limit:
                self._log(f"Greedy_LS: {self.early_stop_no_improvement_limit}回改善が見られなかったため、早期終了します。")
                logger.info(f"Greedy_LS: 早期終了時のベストスコア: {best_score:.2f}")
                break
            
            # 現在の割り当てを更新 (ここでは、常にベストなものに更新する戦略)
            current_assignment = best_assignment.copy()
            current_score = best_score


        self._log(f"Greedy_LS: 局所探索完了。最終ベストスコア: {best_score:.2f}")
        logger.debug(f"Greedy_LS: 最終割り当ての実行可能性チェック: {self._is_feasible_assignment(best_assignment)}")
        return best_assignment, best_score

    def optimize(self) -> OptimizationResult: # 返り値をOptimizationResultに
        """
        貪欲法と局所探索を組み合わせた最適化を実行する。
        """
        self._log("Greedy_LS 最適化を開始します。")
        start_time = time.time()
        logger.debug("Greedy_LS: optimize メソッド呼び出し。")

        # ステップ1: 貪欲法で初期解を生成
        initial_assignment = self._generate_initial_assignment()
        self._log(f"Greedy_LS: 初期割り当てを生成しました。割り当て学生数: {len(initial_assignment)}")
        logger.debug(f"Greedy_LS: 初期割り当てのスコア: {self._calculate_score(initial_assignment):.2f}")

        # ステップ2: 局所探索で解を改善
        final_assignment, final_score = self._local_search(initial_assignment)
        
        end_time = time.time()
        duration = end_time - start_time
        self._log(f"Greedy_LS 最適化完了。実行時間: {duration:.2f}秒")
        logger.info(f"Greedy_LS: 最終スコア: {final_score:.2f}")

        status = "NO_SOLUTION_FOUND"
        message = "Greedy_LSで有効な解が見つかりませんでした。"
        unassigned_students: List[str] = []

        if final_assignment:
            # 最終的な割り当てが実行可能か再確認
            if self._is_feasible_assignment(final_assignment):
                status = "OPTIMAL" # または FEASIBLE (厳密な最適性を保証しないため)
                message = "Greedy_LS最適化が成功しました。"
                unassigned_students = self._get_unassigned_students(final_assignment)
                logger.info(f"Greedy_LS: 最終割り当ては実行可能です。未割り当て学生数: {len(unassigned_students)}")
            else:
                status = "INFEASIBLE"
                message = "Greedy_LS最適化は実行不可能な解を返しました。定員制約を満たしていません。"
                logger.error(f"Greedy_LS: 最終割り当てが実行不可能です。割り当て: {final_assignment}")
                unassigned_students = self.student_ids # 全員未割り当てとみなす
                final_assignment = {} # 無効な割り当てはクリア

        return OptimizationResult(
            status=status,
            message=message,
            best_score=final_score,
            best_assignment=final_assignment,
            seminar_capacities=self.seminar_capacities,
            unassigned_students=unassigned_students,
            optimization_strategy="Greedy_LS"
        )

