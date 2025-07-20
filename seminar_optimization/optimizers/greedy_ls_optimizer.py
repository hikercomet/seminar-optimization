import logging
import random
import time
from typing import Dict, List, Any, Callable, Optional, Tuple

# BaseOptimizerとOptimizationResultをutilsからインポート
from utils import BaseOptimizer, OptimizationResult

logger = logging.getLogger(__name__)

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

        # 固有のパラメータはconfigから取得
        self.iterations = config.get("greedy_ls_iterations", 200000)
        self.early_stop_no_improvement_limit = config.get("early_stop_no_improvement_limit", 5000)

    # _calculate_score, _is_feasible_assignment, _get_unassigned_students はBaseOptimizerから継承されるため削除

    def _generate_initial_assignment(self) -> Dict[str, str]:
        """
        貪欲法で初期割り当てを生成する。
        学生をランダムな順序で処理し、希望するセミナーに空きがあれば割り当てる。
        """
        initial_assignment: Dict[str, str] = {}
        seminar_current_counts = {s_id: 0 for s_id in self.seminar_ids}
        
        shuffled_students = list(self.students)
        random.shuffle(shuffled_students) # 学生の処理順序をランダム化

        for student in shuffled_students:
            student_id = student['id']
            assigned = False
            preferences = student.get('preferences', [])
            
            for preferred_seminar_id in preferences:
                if preferred_seminar_id in self.seminar_capacities and \
                   seminar_current_counts[preferred_seminar_id] < self.seminar_capacities[preferred_seminar_id]:
                    initial_assignment[student_id] = preferred_seminar_id
                    seminar_current_counts[preferred_seminar_id] += 1
                    assigned = True
                    break
            
            # 希望するセミナーに割り当てられなかった場合、未割り当てのままにする
            # または、ランダムに空きのあるセミナーに割り当てるロジックを追加することも可能
            # ここではシンプルに未割り当てのまま

        return initial_assignment

    def _local_search(self, initial_assignment: Dict[str, str]) -> Tuple[Dict[str, str], float]:
        """
        局所探索（焼きなまし法）で割り当てを改善する。
        """
        current_assignment = initial_assignment.copy()
        current_score = self._calculate_score(current_assignment) # BaseOptimizerから継承

        best_assignment = current_assignment.copy()
        best_score = current_score

        no_improvement_count = 0

        for i in range(self.iterations):
            if i % 1000 == 0:
                self._log(f"Greedy_LS 局所探索イテレーション {i}/{self.iterations}, 現在のスコア: {current_score:.2f}", level=logging.DEBUG)

            # 変更操作: 2人の学生のセミナーを交換してみる
            if len(current_assignment) < 2:
                break # 交換できる学生がいない

            student_ids = list(current_assignment.keys())
            s1_id, s2_id = random.sample(student_ids, 2)
            
            s1_seminar = current_assignment[s1_id]
            s2_seminar = current_assignment[s2_id]

            # 新しい割り当てを作成
            new_assignment = current_assignment.copy()
            new_assignment[s1_id] = s2_seminar
            new_assignment[s2_id] = s1_seminar

            # 新しい割り当てが実行可能かチェック
            if self._is_feasible_assignment(new_assignment): # BaseOptimizerから継承
                new_score = self._calculate_score(new_assignment) # BaseOptimizerから継承

                if new_score > current_score:
                    # 改善があれば常に採用
                    current_assignment = new_assignment
                    current_score = new_score
                    no_improvement_count = 0 # 改善があったのでカウントをリセット

                    if new_score > best_score:
                        best_score = new_score
                        best_assignment = current_assignment.copy()
                        self._log(f"Greedy_LS: ベストスコア更新: {best_score:.2f}", level=logging.DEBUG)
                else:
                    no_improvement_count += 1
            else:
                no_improvement_count += 1 # 制約違反も改善なしとみなす

            if no_improvement_count >= self.early_stop_no_improvement_limit:
                self._log(f"Greedy_LS: {self.early_stop_no_improvement_limit}回改善が見られなかったため、早期終了します。")
                break

        return best_assignment, best_score

    def optimize(self) -> OptimizationResult: # 返り値をOptimizationResultに
        """
        貪欲法と局所探索を組み合わせた最適化を実行する。
        """
        self._log("Greedy_LS 最適化を開始します。")
        start_time = time.time()

        # ステップ1: 貪欲法で初期解を生成
        initial_assignment = self._generate_initial_assignment()
        self._log(f"Greedy_LS: 初期割り当てを生成しました。割り当て学生数: {len(initial_assignment)}")

        # ステップ2: 局所探索で解を改善
        final_assignment, final_score = self._local_search(initial_assignment)
        
        end_time = time.time()
        duration = end_time - start_time
        self._log(f"Greedy_LS 最適化完了。実行時間: {duration:.2f}秒")

        status = "NO_SOLUTION_FOUND"
        message = "Greedy_LSで有効な解が見つかりませんでした。"
        unassigned_students: List[str] = []

        if final_assignment:
            status = "OPTIMAL" # または FEASIBLE
            message = "Greedy_LS最適化が成功しました。"
            unassigned_students = self._get_unassigned_students(final_assignment) # BaseOptimizerから継承

        return OptimizationResult(
            status=status,
            message=message,
            best_score=final_score,
            best_assignment=final_assignment,
            seminar_capacities=self.seminar_capacities,
            unassigned_students=unassigned_students,
            optimization_strategy="Greedy_LS"
        )

