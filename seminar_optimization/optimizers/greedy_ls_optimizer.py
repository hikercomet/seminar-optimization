import random
import time
import threading
from typing import Dict, List, Any, Callable, Optional, Tuple

# BaseOptimizerとOptimizationResultをutilsからインポート
from seminar_optimization.seminar_optimization.utils import BaseOptimizer, OptimizationResult # <-- 修正: 相対インポート
# ロギングは logger_config.py で一元的に設定されるため、ここではロガーの取得のみ
from seminar_optimization.seminar_optimization.logger_config import logger # <-- 修正: 相対インポート

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

    def _initial_assignment(self) -> Dict[str, str]:
        """
        学生の希望に基づいて初期割り当てを生成する（貪欲法）。
        各学生は、まだ定員に空きがある中で最も希望順位の高いセミナーに割り当てられる。
        """
        logger.debug("GreedyLSOptimizer: 初期割り当て（貪欲法）を開始します。")
        assignment: Dict[str, str] = {}
        seminar_current_counts = {s_id: 0 for s_id in self.seminar_ids}

        # 学生をランダムな順序で処理することで、異なる初期解を生成する可能性を高める
        shuffled_students = list(self.student_ids)
        random.shuffle(shuffled_students)

        for student_id in shuffled_students:
            preferences = self.student_preferences.get(student_id, [])
            assigned = False
            for preferred_seminar_id in preferences:
                capacity = self.seminar_capacities.get(preferred_seminar_id)
                if capacity is not None and seminar_current_counts[preferred_seminar_id] < capacity:
                    assignment[student_id] = preferred_seminar_id
                    seminar_current_counts[preferred_seminar_id] += 1
                    assigned = True
                    logger.debug(f"学生 {student_id} をセミナー {preferred_seminar_id} に初期割り当てしました。")
                    break
            if not assigned:
                logger.debug(f"学生 {student_id} は初期割り当てで希望するセミナーに割り当てられませんでした。")
        
        logger.info(f"GreedyLSOptimizer: 初期割り当てが完了しました。割り当てられた学生数: {len(assignment)}")
        return assignment

    def _local_search(self, initial_assignment: Dict[str, str], cancel_event: Optional[threading.Event] = None) -> Tuple[Dict[str, str], float]:
        """
        局所探索（Local Search）を実行し、割り当てを改善する。
        現在の割り当てから近傍解を生成し、スコアが改善すれば更新する。
        """
        logger.debug("GreedyLSOptimizer: 局所探索を開始します。")
        current_assignment = initial_assignment.copy()
        current_score = self._calculate_score(current_assignment)
        best_assignment = current_assignment.copy()
        best_score = current_score
        
        no_improvement_count = 0

        self._log(f"Greedy_LS: 局所探索開始。初期スコア: {current_score:.2f}")

        for i in range(self.iterations):
            if cancel_event and cancel_event.is_set():
                self._log(f"Greedy_LS: 局所探索がイテレーション {i} でキャンセルされました。")
                break

            # 進捗報告 (例: 10000イテレーションごとに)
            if (i + 1) % 10000 == 0:
                self._log(f"Greedy_LS: 局所探索イテレーション {i+1}/{self.iterations}。現在のベストスコア: {best_score:.2f}")

            # 1. 未割り当て学生の割り当てを試みる
            unassigned_students = self._get_unassigned_students(current_assignment)
            if unassigned_students:
                student_to_assign = random.choice(unassigned_students)
                preferences = self.student_preferences.get(student_to_assign, [])
                random.shuffle(preferences) # 希望順をランダムに試す
                
                found_slot = False
                for seminar_id in preferences:
                    if seminar_id in self.seminar_capacities and \
                       list(current_assignment.values()).count(seminar_id) < self.seminar_capacities[seminar_id]:
                        
                        new_assignment = current_assignment.copy()
                        new_assignment[student_to_assign] = seminar_id
                        
                        if self._is_feasible_assignment(new_assignment):
                            new_score = self._calculate_score(new_assignment)
                            if new_score > current_score:
                                current_assignment = new_assignment
                                current_score = new_score
                                if current_score > best_score:
                                    best_score = current_score
                                    best_assignment = current_assignment.copy()
                                    no_improvement_count = 0
                                    logger.debug(f"GreedyLSOptimizer: 未割り当て学生 {student_to_assign} を割り当て、スコア改善: {best_score:.2f}")
                                found_slot = True
                                break # この学生の割り当て成功
                if found_slot:
                    continue # 次のイテレーションへ

            # 2. 既存の割り当てを交換または再割り当てを試みる
            if current_assignment:
                student_id = random.choice(list(current_assignment.keys()))
                original_seminar = current_assignment[student_id]
                
                # 選択肢: 別のセミナーに移動するか、未割り当てにする
                possible_seminars = list(self.seminar_ids)
                if len(possible_seminars) > 1: # 少なくとも2つセミナーがないと交換できない
                    # 元のセミナーを除外し、別のセミナーを選択
                    possible_seminars.remove(original_seminar) 
                    target_seminar = random.choice(possible_seminars)
                else: # セミナーが1つしかない場合は、未割り当てを試みる
                    target_seminar = None # 未割り当てを意味する

                new_assignment = current_assignment.copy()
                del new_assignment[student_id] # 一旦学生を未割り当てにする

                if target_seminar:
                    # 新しいセミナーに割り当てを試みる
                    if list(new_assignment.values()).count(target_seminar) < self.seminar_capacities[target_seminar]:
                        new_assignment[student_id] = target_seminar
                        
                        if self._is_feasible_assignment(new_assignment):
                            new_score = self._calculate_score(new_assignment)
                            if new_score > current_score:
                                current_assignment = new_assignment
                                current_score = new_score
                                if current_score > best_score:
                                    best_score = current_score
                                    best_assignment = current_assignment.copy()
                                    no_improvement_count = 0
                                    logger.debug(f"GreedyLSOptimizer: 学生 {student_id} を {original_seminar} から {target_seminar} へ移動し、スコア改善: {best_score:.2f}")
                                continue # 改善があったので次のイテレーションへ
                
                # 移動で改善がなかった、または移動先がない場合、元の割り当てに戻すか、未割り当てのままにする
                # ここでは、改善がなければ元の割り当てに戻す
                if student_id not in new_assignment: # 移動が試行されなかったか、失敗した場合
                    new_assignment[student_id] = original_seminar # 元に戻す
                
                # 元に戻した割り当てのスコアを再計算（これは通常不要だが、念のため）
                # current_score = self._calculate_score(current_assignment)

            # 改善がなかった場合
            no_improvement_count += 1
            if no_improvement_count >= self.early_stop_no_improvement_limit:
                self._log(f"Greedy_LS: {self.early_stop_no_improvement_limit} イテレーションの間改善がなかったため、早期停止します。")
                break

        logger.info(f"GreedyLSOptimizer: 局所探索が完了しました。最終ベストスコア: {best_score:.2f}")
        return best_assignment, best_score

    def optimize(self, cancel_event: Optional[threading.Event] = None) -> OptimizationResult:
        """
        最適化プロセスを実行する。
        """
        start_time = time.time()
        self._log("Greedy_LS 最適化を開始します...")

        # 初期割り当ての生成
        initial_assignment = self._initial_assignment()
        self._log(f"Greedy_LS: 初期割り当て生成完了。割り当て数: {len(initial_assignment)}")

        # 局所探索による改善
        final_assignment, final_score = self._local_search(initial_assignment, cancel_event)
        
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
                final_score = -float('inf') # 不可能な解はスコアを最低にする

        if cancel_event and cancel_event.is_set():
            status = "CANCELLED"
            message = "最適化がユーザーによってキャンセルされました。"
            final_score = -float('inf') # キャンセルされた場合はスコアを無効にする
            unassigned_students = self.student_ids # 全員未割り当てとみなす

        return OptimizationResult(
            status=status,
            message=message,
            best_score=final_score,
            best_assignment=final_assignment,
            seminar_capacities=self.seminar_capacities,
            unassigned_students=unassigned_students,
            optimization_strategy="Greedy_LS"
        )
