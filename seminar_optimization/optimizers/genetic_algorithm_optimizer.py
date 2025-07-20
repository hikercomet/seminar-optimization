import random
import logging
import copy
import threading
import time
from typing import Dict, List, Any, Callable, Optional, Tuple

# BaseOptimizerとOptimizationResultをutilsからインポート
from utils import BaseOptimizer, OptimizationResult 

logger = logging.getLogger(__name__)

class GeneticAlgorithmOptimizer(BaseOptimizer): # BaseOptimizerを継承
    """
    遺伝的アルゴリズムと局所探索を組み合わせた最適化アルゴリズム。
    """
    def __init__(self, 
                 seminars: List[Dict[str, Any]], 
                 students: List[Dict[str, Any]], 
                 config: Dict[str, Any],
                 progress_callback: Optional[Callable[[str], None]] = None # progress_callbackを追加
                 ):
        # BaseOptimizerの__init__を呼び出す
        super().__init__(seminars, students, config, progress_callback) 
        
        # 固有のパラメータはconfigから取得
        self.population_size = config.get("ga_population_size", 100)
        self.generations = config.get("ga_generations", 200)
        self.mutation_rate = config.get("ga_mutation_rate", 0.05)
        self.crossover_rate = config.get("ga_crossover_rate", 0.8)
        self.local_search_iterations = config.get("local_search_iterations", 500) # GA内の局所探索用
        self.no_improvement_limit = config.get("early_stop_no_improvement_limit", 50) # 早期停止条件

    # _calculate_score, _is_feasible_assignment, _get_unassigned_students はBaseOptimizerから継承されるため削除

    def _generate_individual(self) -> Dict[str, str]:
        """
        ランダムな個体（学生-セミナー割り当て）を生成する。
        定員制約を考慮しつつ、可能な限り希望に沿うように試みる。
        """
        assignment: Dict[str, str] = {}
        seminar_current_counts = {s_id: 0 for s_id in self.seminar_ids}
        
        # 学生をランダムな順序で処理
        shuffled_students = list(self.students)
        random.shuffle(shuffled_students)

        for student in shuffled_students:
            student_id = student['id']
            assigned = False
            preferences = student.get('preferences', [])
            
            # 優先順位の高い希望から割り当てを試みる
            for preferred_seminar_id in preferences:
                if preferred_seminar_id in self.seminar_capacities and \
                   seminar_current_counts[preferred_seminar_id] < self.seminar_capacities[preferred_seminar_id]:
                    assignment[student_id] = preferred_seminar_id
                    seminar_current_counts[preferred_seminar_id] += 1
                    assigned = True
                    break
            
            if not assigned:
                # 希望するセミナーに割り当てられなかった場合、空きのあるランダムなセミナーに割り当てる
                # または、未割り当てのままにする (ここでは未割り当てのまま)
                pass
        
        # 生成された割り当てが実行可能か確認し、必要なら修復
        if not self._is_feasible_assignment(assignment):
            assignment = self._repair_assignment(assignment)
        
        return assignment

    def _crossover(self, parent1: Dict[str, str], parent2: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        2つの親個体から2つの子個体を生成する（一点交叉）。
        """
        child1 = {}
        child2 = {}
        
        # 学生IDのリストを取得
        student_ids = list(self.student_ids)
        if not student_ids:
            return {}, {}

        # 交叉点をランダムに選択
        crossover_point = random.randint(1, len(student_ids) - 1)

        for i, student_id in enumerate(student_ids):
            if i < crossover_point:
                child1[student_id] = parent1.get(student_id)
                child2[student_id] = parent2.get(student_id)
            else:
                child1[student_id] = parent2.get(student_id)
                child2[student_id] = parent1.get(student_id)
        
        # None値を取り除く（未割り当て学生はそのまま）
        child1 = {k: v for k, v in child1.items() if v is not None}
        child2 = {k: v for k, v in child2.items() if v is not None}

        # 生成された子が実行可能か確認し、必要なら修復
        if not self._is_feasible_assignment(child1):
            child1 = self._repair_assignment(child1)
        if not self._is_feasible_assignment(child2):
            child2 = self._repair_assignment(child2)

        return child1, child2

    def _mutate(self, individual: Dict[str, str]) -> Dict[str, str]:
        """
        個体に変異を適用する。
        ランダムな学生を別のランダムなセミナーに割り当てる。
        """
        mutated_individual = individual.copy()
        
        if random.random() < self.mutation_rate and len(mutated_individual) > 0:
            student_id_to_mutate = random.choice(list(mutated_individual.keys()))
            
            # 別のセミナーをランダムに選択
            available_seminars = list(self.seminar_ids)
            if available_seminars:
                new_seminar_id = random.choice(available_seminars)
                mutated_individual[student_id_to_mutate] = new_seminar_id
        
        # 変異後に実行可能か確認し、必要なら修復
        if not self._is_feasible_assignment(mutated_individual):
            mutated_individual = self._repair_assignment(mutated_individual)

        return mutated_individual

    def _repair_assignment(self, assignment: Dict[str, str]) -> Dict[str, str]:
        """
        定員超過の割り当てを修復する。
        超過しているセミナーからランダムな学生を未割り当てにするか、別のセミナーに再割り当てする。
        ここではシンプルに超過分を未割り当てにする。
        """
        repaired_assignment = assignment.copy()
        seminar_counts = {s_id: 0 for s_id in self.seminar_ids}
        
        # まず現在の割り当てをカウント
        for student_id, seminar_id in assignment.items():
            seminar_counts[seminar_id] += 1

        # 定員超過しているセミナーを特定し、学生を削除
        for seminar_id, count in seminar_counts.items():
            capacity = self.seminar_capacities.get(seminar_id, 0)
            if count > capacity:
                students_in_overfilled_seminar = [s_id for s_id, sem_id in repaired_assignment.items() if sem_id == seminar_id]
                # 超過している学生をランダムに選び、割り当てを解除
                num_to_remove = count - capacity
                students_to_unassign = random.sample(students_in_overfilled_seminar, num_to_remove)
                for s_id in students_to_unassign:
                    del repaired_assignment[s_id]
                self._log(f"修復: セミナー {seminar_id} から {num_to_remove} 人の学生を削除しました。", level=logging.DEBUG)

        # 割り当てが解除された学生を再割り当て試行（希望を優先）
        unassigned_after_repair = self._get_unassigned_students(repaired_assignment)
        for student_id in unassigned_after_repair:
            student_info = next((s for s in self.students if s['id'] == student_id), None)
            if student_info:
                preferences = student_info.get('preferences', [])
                assigned = False
                for preferred_seminar_id in preferences:
                    if preferred_seminar_id in self.seminar_capacities:
                        # 仮割り当てを試みる
                        temp_assignment = repaired_assignment.copy()
                        temp_assignment[student_id] = preferred_seminar_id
                        # ここで_is_feasible_assignmentを呼び出すと、他のセミナーの定員もチェックされる
                        # そのため、ここではそのセミナーの現在のカウントのみをチェックする
                        current_count_for_seminar = sum(1 for sid, assigned_sem in temp_assignment.items() if assigned_sem == preferred_seminar_id)
                        if current_count_for_seminar <= self.seminar_capacities[preferred_seminar_id]:
                            repaired_assignment[student_id] = preferred_seminar_id
                            assigned = True
                            break
                if not assigned:
                    # まだ割り当てられなければ、ランダムな空きセミナーを探す
                    available_seminars_for_reassign = [
                        s_id for s_id in self.seminar_ids
                        if sum(1 for sid, assigned_sem in repaired_assignment.items() if assigned_sem == s_id) < self.seminar_capacities[s_id]
                    ]
                    if available_seminars_for_reassign:
                        repaired_assignment[student_id] = random.choice(available_seminars_for_reassign)
        
        return repaired_assignment

    def _local_search_for_ga(self, individual: Dict[str, str]) -> Dict[str, str]:
        """
        GAの各個体に適用する局所探索（焼きなまし法を簡易化）。
        """
        current_assignment = individual.copy()
        current_score = self._calculate_score(current_assignment) # BaseOptimizerから継承

        best_assignment = current_assignment.copy()
        best_score = current_score

        for _ in range(self.local_search_iterations):
            # 変更操作: 2人の学生のセミナーを交換してみる
            if len(current_assignment) < 2:
                break 

            student_ids = list(current_assignment.keys())
            s1_id, s2_id = random.sample(student_ids, 2)
            
            s1_seminar = current_assignment[s1_id]
            s2_seminar = current_assignment[s2_id]

            new_assignment = current_assignment.copy()
            new_assignment[s1_id] = s2_seminar
            new_assignment[s2_id] = s1_seminar

            if self._is_feasible_assignment(new_assignment): # BaseOptimizerから継承
                new_score = self._calculate_score(new_assignment) # BaseOptimizerから継承
                if new_score > current_score:
                    current_assignment = new_assignment
                    current_score = new_score
                    if new_score > best_score:
                        best_score = new_score
                        best_assignment = current_assignment.copy()
            
        return best_assignment

    def optimize(self) -> OptimizationResult: # 返り値をOptimizationResultに
        """
        遺伝的アルゴリズム最適化を実行する。
        """
        self._log("GA_LS 最適化を開始します。")
        start_time = time.time()

        population: List[Dict[str, str]] = []
        for _ in range(self.population_size):
            population.append(self._generate_individual())
        
        best_overall_assignment: Dict[str, str] = {}
        best_overall_score = -float('inf')
        no_improvement_count = 0

        for generation in range(self.generations):
            if generation % 10 == 0:
                self._log(f"GA世代 {generation+1}/{self.generations} を実行中...", level=logging.INFO)

            # 評価
            # スコアと個体をペアにする (スコア, 個体)
            scored_population = [(self._calculate_score(ind), ind) for ind in population]
            scored_population.sort(key=lambda x: x[0], reverse=True) # スコアの高い順にソート

            current_best_score_in_generation = scored_population[0][0]
            current_best_in_generation = scored_population[0][1]

            if current_best_score_in_generation > best_overall_score:
                self._log(f"GA世代 {generation+1}: スコアが改善しました: {best_overall_score:.2f} -> {current_best_score_in_generation:.2f}")
                best_overall_score = current_best_score_in_generation
                best_overall_assignment = current_best_in_generation.copy()
                no_improvement_count = 0
            else:
                no_improvement_count += 1
                if no_improvement_count >= self.no_improvement_limit:
                    self._log(f"GA: {self.no_improvement_limit}世代改善が見られなかったため、早期終了します。")
                    break

            # 選択 (エリート選択 + ルーレット選択)
            new_population = []
            # エリート主義: 最も良い個体を次世代に直接コピー
            new_population.append(scored_population[0][1]) 

            # ルーレット選択
            total_fitness = sum(max(0, score) for score, _ in scored_population) # スコアが負の場合は0として扱う
            if total_fitness == 0: # 全てのスコアが0以下の場合、ランダムに選択
                weights = [1] * len(scored_population)
            else:
                weights = [max(0, score) / total_fitness for score, _ in scored_population]

            for _ in range(self.population_size - 1): # エリートを除いた残りの個体数
                # 確率的に親を選択
                selected_parents = random.choices([ind for _, ind in scored_population], weights=weights, k=2)
                parent1, parent2 = selected_parents[0], selected_parents[1]

                # 交叉
                if random.random() < self.crossover_rate:
                    child1, child2 = self._crossover(parent1, parent2)
                else:
                    child1, child2 = parent1.copy(), parent2.copy()
                
                # 変異
                child1 = self._mutate(child1)
                child2 = self._mutate(child2)

                # 局所探索を適用
                child1 = self._local_search_for_ga(child1)
                child2 = self._local_search_for_ga(child2)

                new_population.append(child1)
                if len(new_population) < self.population_size: # 念のためサイズチェック
                    new_population.append(child2)
            
            population = new_population

        end_time = time.time()
        duration = end_time - start_time
        self._log(f"GA_LS 最適化完了。実行時間: {duration:.2f}秒")

        if not best_overall_assignment:
            self._log("GAで有効な解が見つかりませんでした。", level=logging.ERROR)
            return OptimizationResult(
                status="NO_SOLUTION_FOUND",
                message="GAで有効な解が見つかりませんでした。",
                best_score=-float('inf'),
                best_assignment={},
                seminar_capacities=self.seminar_capacities,
                unassigned_students=self.student_ids,
                optimization_strategy="GA_LS"
            )

        # 最終的な割り当てが定員制約を満たしているか再確認
        if not self._is_feasible_assignment(best_overall_assignment):
            self._log("最終的な割り当てが定員制約を満たしていません。修復を試みます。", level=logging.WARNING)
            best_overall_assignment = self._repair_assignment(best_overall_assignment)
            if not self._is_feasible_assignment(best_overall_assignment):
                self._log("修復後も割り当てが実行不可能です。", level=logging.ERROR)
                status_str = "INFEASIBLE"
                message_str = "GA最適化は実行不可能な解を返しました。"
            else:
                status_str = "FEASIBLE"
                message_str = "GA最適化が実行可能解を見つけました (修復済み)。"
        else:
            status_str = "OPTIMAL" # GAは厳密な最適解を保証しないが、ここではベストとみなす
            message_str = "GA最適化が成功しました。"

        unassigned_students = self._get_unassigned_students(best_overall_assignment)

        return OptimizationResult(
            status=status_str,
            message=message_str,
            best_score=best_overall_score,
            best_assignment=best_overall_assignment,
            seminar_capacities=self.seminar_capacities,
            unassigned_students=unassigned_students,
            optimization_strategy="GA_LS"
        )

