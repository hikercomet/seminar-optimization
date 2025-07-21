import random
import logging
import copy
import threading
import time
from typing import Dict, List, Any, Callable, Optional, Tuple

# BaseOptimizerとOptimizationResultをutilsからインポート
from utils import BaseOptimizer, OptimizationResult 

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # DEBUGレベルのメッセージも出力

class GeneticAlgorithmOptimizer(BaseOptimizer): # BaseOptimizerを継承
    """
    遺伝的アルゴリズムと局所探索を組み合わせた最適化アルゴリズム。
    """
    def __init__(self, 
                 seminars: List[Dict[str, Any]], 
                 students: List[Dict[str, Any]], 
                 config: Dict[str, Any],\
                 progress_callback: Optional[Callable[[str], None]] = None # progress_callbackを追加
                 ):
        # BaseOptimizerの__init__を呼び出す
        super().__init__(seminars, students, config, progress_callback) 
        logger.debug("GeneticAlgorithmOptimizer: 初期化を開始します。")
        
        # 固有のパラメータはconfigから取得
        self.population_size = config.get("ga_population_size", 100)
        self.generations = config.get("ga_generations", 200)
        self.mutation_rate = config.get("ga_mutation_rate", 0.05)
        self.crossover_rate = config.get("ga_crossover_rate", 0.8)
        self.local_search_iterations = config.get("local_search_iterations", 500) # GA内の局所探索用
        self.no_improvement_limit = config.get("ga_no_improvement_limit", 50) # 改善が見られない世代数で早期停止
        logger.debug(f"GAOptimizer: 個体群サイズ: {self.population_size}, 世代数: {self.generations}, 変異率: {self.mutation_rate}, 交叉率: {self.crossover_rate}, 局所探索イテレーション: {self.local_search_iterations}, 改善なし停止リミット: {self.no_improvement_limit}")

    def _generate_individual(self) -> Dict[str, str]:
        """
        ランダムな個体（学生割り当て）を生成する。
        定員制約を考慮しつつ、可能な限り希望に沿うように割り当てる。
        """
        assignment: Dict[str, str] = {}
        seminar_current_counts: Dict[str, int] = {s_id: 0 for s_id in self.seminar_ids}
        
        shuffled_student_ids = list(self.student_ids)
        random.shuffle(shuffled_student_ids)
        logger.debug("_generate_individual: 新しい個体を生成中...")

        for student_id in shuffled_student_ids:
            student_preferences = self.student_preferences.get(student_id, [])
            assigned = False
            
            # まず希望するセミナーに割り当てを試みる
            for preferred_seminar_id in student_preferences:
                capacity = self.seminar_capacities.get(preferred_seminar_id, 0)
                if seminar_current_counts.get(preferred_seminar_id, 0) < capacity:
                    assignment[student_id] = preferred_seminar_id
                    seminar_current_counts[preferred_seminar_id] += 1
                    assigned = True
                    logger.debug(f"学生 {student_id} を希望セミナー {preferred_seminar_id} に割り当て。")
                    break
            
            # 希望するセミナーに割り当てられなかった場合、ランダムな空きセミナーに割り当てる
            if not assigned:
                available_seminars = [s_id for s_id in self.seminar_ids if seminar_current_counts.get(s_id, 0) < self.seminar_capacities.get(s_id, 0)]
                if available_seminars:
                    chosen_seminar = random.choice(available_seminars)
                    assignment[student_id] = chosen_seminar
                    seminar_current_counts[chosen_seminar] += 1
                    assigned = True
                    logger.debug(f"学生 {student_id} を空きセミナー {chosen_seminar} に割り当て。")
                else:
                    logger.debug(f"学生 {student_id} は割り当てられませんでした（空きセミナーなし）。")

        logger.debug(f"_generate_individual: 生成された個体の割り当て学生数: {len(assignment)}")
        return assignment

    def _repair_assignment(self, assignment: Dict[str, str]) -> Dict[str, str]:
        """
        定員超過を修正し、実行可能な割り当てにする。
        超過しているセミナーからランダムに学生を外し、未割り当てにするか、空きのあるセミナーに再割り当てを試みる。
        """
        repaired_assignment = assignment.copy()
        seminar_counts: Dict[str, int] = {s_id: 0 for s_id in self.seminar_ids}
        
        # まず現在のカウントを計算
        for student_id, seminar_id in repaired_assignment.items():
            seminar_counts[seminar_id] = seminar_counts.get(seminar_id, 0) + 1
        
        logger.debug("_repair_assignment: 割り当ての修復を開始します。")
        
        # 定員超過しているセミナーから学生をランダムに外す
        over_capacity_seminars = [s_id for s_id, count in seminar_counts.items() if count > self.seminar_capacities.get(s_id, 0)]
        for seminar_id in over_capacity_seminars:
            capacity = self.seminar_capacities.get(seminar_id, 0)
            num_to_remove = seminar_counts[seminar_id] - capacity
            
            students_in_seminar = [s_id for s_id, sem_id in repaired_assignment.items() if sem_id == seminar_id]
            random.shuffle(students_in_seminar) # ランダムに学生を選ぶ
            
            for i in range(num_to_remove):
                if students_in_seminar:
                    student_to_unassign = students_in_seminar.pop()
                    del repaired_assignment[student_to_unassign]
                    logger.debug(f"セミナー {seminar_id} の定員超過を修正: 学生 {student_to_unassign} を割り当てから外しました。")
                else:
                    logger.warning(f"セミナー {seminar_id} から外す学生がいませんでしたが、まだ定員超過しています。")
                    break # これ以上外す学生がいない

        # 未割り当てになった学生を再割り当て試行
        unassigned_students = self._get_unassigned_students(repaired_assignment)
        random.shuffle(unassigned_students)
        logger.debug(f"_repair_assignment: 修復後、未割り当て学生: {len(unassigned_students)}")

        for student_id in unassigned_students:
            student_preferences = self.student_preferences.get(student_id, [])
            
            # まず希望するセミナーに割り当てを試みる
            assigned = False
            for preferred_seminar_id in student_preferences:
                capacity = self.seminar_capacities.get(preferred_seminar_id, 0)
                current_count = repaired_assignment.values().count(preferred_seminar_id) # 再計算
                if current_count < capacity:
                    repaired_assignment[student_id] = preferred_seminar_id
                    assigned = True
                    logger.debug(f"修復中に学生 {student_id} を希望セミナー {preferred_seminar_id} に再割り当てしました。")
                    break
            
            # 希望に沿えなければ、ランダムな空きセミナーに割り当てる
            if not assigned:
                available_seminars = [s_id for s_id in self.seminar_ids if repaired_assignment.values().count(s_id) < self.seminar_capacities.get(s_id, 0)]
                if available_seminars:
                    chosen_seminar = random.choice(available_seminars)
                    repaired_assignment[student_id] = chosen_seminar
                    logger.debug(f"修復中に学生 {student_id} を空きセミナー {chosen_seminar} に再割り当てしました。")
                else:
                    logger.debug(f"修復中に学生 {student_id} を再割り当てできませんでした（空きセミナーなし）。")

        logger.info(f"_repair_assignment: 修復完了。実行可能性: {self._is_feasible_assignment(repaired_assignment)}")
        return repaired_assignment

    def _crossover(self, parent1: Dict[str, str], parent2: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        2つの親から2つの子を生成する交叉操作。
        ここでは、各学生の割り当てをランダムに親から継承する。
        """
        child1 = {}
        child2 = {}
        logger.debug("_crossover: 交叉操作を実行中。")

        for student_id in self.student_ids:
            if random.random() < 0.5: # 50%の確率で親1から、50%の確率で親2から継承
                child1[student_id] = parent1.get(student_id)
                child2[student_id] = parent2.get(student_id)
            else:
                child1[student_id] = parent2.get(student_id)
                child2[student_id] = parent1.get(student_id)
            logger.debug(f"学生 {student_id}: 親1から {parent1.get(student_id)}, 親2から {parent2.get(student_id)} を継承。")
        
        # None が含まれる可能性があるため、後で修復が必要
        child1_filtered = {k: v for k, v in child1.items() if v is not None}
        child2_filtered = {k: v for k, v in child2.items() if v is not None}

        logger.debug("_crossover: 交叉完了。子の割り当てを修復します。")
        return self._repair_assignment(child1_filtered), self._repair_assignment(child2_filtered)

    def _mutate(self, individual: Dict[str, str]) -> Dict[str, str]:
        """
        個体に変異を導入する。
        ランダムな学生の割り当てをランダムなセミナーに変更する。
        """
        mutated_individual = individual.copy()
        logger.debug("_mutate: 変異操作を実行中。")

        for student_id in self.student_ids:
            if random.random() < self.mutation_rate:
                # ランダムなセミナーに割り当てる (未割り当ての可能性も含む)
                new_seminar_id = random.choice(self.seminar_ids + [None]) 
                if new_seminar_id is None:
                    if student_id in mutated_individual:
                        del mutated_individual[student_id]
                        logger.debug(f"学生 {student_id} を未割り当てにしました。")
                else:
                    mutated_individual[student_id] = new_seminar_id
                    logger.debug(f"学生 {student_id} の割り当てを {new_seminar_id} に変異させました。")
        
        # 変異後も実行可能な割り当てを保証するために修復
        logger.debug("_mutate: 変異後の個体を修復します。")
        return self._repair_assignment(mutated_individual)

    def _local_search_for_ga(self, assignment: Dict[str, str]) -> Dict[str, str]:
        """
        GAの各個体に適用される局所探索。
        Greedy_LSの局所探索と似ているが、イテレーション数が少ない。
        """
        current_assignment = assignment.copy()
        current_score = self._calculate_score(current_assignment)
        logger.debug(f"_local_search_for_ga: GAのための局所探索を開始。初期スコア: {current_score:.2f}")

        for _ in range(self.local_search_iterations):
            temp_assignment = current_assignment.copy()
            
            # ランダムな学生を選び、現在の割り当てから削除
            if not temp_assignment: # 割り当てが空の場合の例外処理
                student_to_move_id = random.choice(self.student_ids)
                original_seminar_id = None
            else:
                student_to_move_id = random.choice(list(temp_assignment.keys()))
                original_seminar_id = temp_assignment.pop(student_to_move_id)

            # その学生をランダムなセミナーに割り当てる (または未割り当てのままにする)
            possible_seminars = list(self.seminar_ids) + [None] # Noneは未割り当てを意味する
            random.shuffle(possible_seminars)

            found_better_move = False
            for new_seminar_id in possible_seminars:
                neighbor_assignment = temp_assignment.copy()
                if new_seminar_id is not None:
                    neighbor_assignment[student_to_move_id] = new_seminar_id
                
                # 新しい割り当てが実行可能かチェック
                if self._is_feasible_assignment(neighbor_assignment):
                    neighbor_score = self._calculate_score(neighbor_assignment)
                    if neighbor_score > current_score:
                        current_score = neighbor_score
                        current_assignment = neighbor_assignment.copy()
                        found_better_move = True
                        logger.debug(f"GA局所探索: 改善が見られました。学生 {student_to_move_id} を {original_seminar_id} から {new_seminar_id} へ。新スコア: {current_score:.2f}")
                        break # より良い解が見つかったので、この学生の移動はこれで確定
            
            if not found_better_move:
                # 改善が見られなかった場合は元の割り当てに戻すか、そのまま次のイテレーションへ
                if original_seminar_id is not None:
                    current_assignment[student_to_move_id] = original_seminar_id # 元に戻す
                logger.debug(f"GA局所探索: 学生 {student_to_move_id} の移動で改善なし。")

        logger.debug(f"_local_search_for_ga: GAのための局所探索完了。最終スコア: {current_score:.2f}")
        return current_assignment

    def optimize(self) -> OptimizationResult:
        """
        遺伝的アルゴリズムの最適化を実行する。
        """
        self._log("GA_LS 最適化を開始します。")
        start_time = time.time()
        logger.debug("GeneticAlgorithmOptimizer: optimize メソッド呼び出し。")

        population: List[Dict[str, str]] = []
        for _ in range(self.population_size):
            individual = self._generate_individual()
            population.append(self._repair_assignment(individual)) # 初期個体も修復
        logger.info(f"GA_LS: 初期個体群 ({self.population_size}個体) を生成しました。")

        best_overall_assignment: Dict[str, str] = {}
        best_overall_score = -float('inf')
        no_improvement_generations = 0

        for generation in range(self.generations):
            self._log(f"GA_LS: 世代 {generation+1}/{self.generations} を実行中...")
            logger.debug(f"GA_LS: 現在の個体群サイズ: {len(population)}")

            # 1. 評価 (Fitness Evaluation)
            # 各個体のスコアを計算し、実行可能でない場合はペナルティを与えるか、修復する
            # ここでは、生成時に修復しているので、スコア計算のみ
            fitness_scores: List[Tuple[float, Dict[str, str]]] = []
            for individual in population:
                score = self._calculate_score(individual)
                fitness_scores.append((score, individual))
            
            fitness_scores.sort(key=lambda x: x[0], reverse=True) # スコアの高い順にソート
            current_best_score = fitness_scores[0][0]
            current_best_assignment = fitness_scores[0][1]
            logger.debug(f"世代 {generation+1}: 現在の世代のベストスコア: {current_best_score:.2f}")

            if current_best_score > best_overall_score:
                best_overall_score = current_best_score
                best_overall_assignment = current_best_assignment.copy()
                no_improvement_generations = 0
                self._log(f"GA_LS: 新しい全体ベストスコアが見つかりました: {best_overall_score:.2f} (世代 {generation+1})")
            else:
                no_improvement_generations += 1
                logger.debug(f"世代 {generation+1}: 改善なし。連続改善なし世代数: {no_improvement_generations}")
            
            if no_improvement_generations >= self.no_improvement_limit:
                self._log(f"GA_LS: {self.no_improvement_limit}世代改善が見られなかったため、早期終了します。")
                break

            # 2. 選択 (Selection) - トーナメント選択
            # スコアの高い個体が選ばれやすいようにする
            new_population: List[Dict[str, str]] = []
            for _ in range(self.population_size):
                # ランダムに2つの個体を選び、スコアが高い方を次世代に残す
                ind1 = random.choice(population)
                ind2 = random.choice(population)
                if self._calculate_score(ind1) > self._calculate_score(ind2):
                    new_population.append(ind1)
                else:
                    new_population.append(ind2)
            logger.debug(f"世代 {generation+1}: 選択操作完了。")

            # 3. 交叉 (Crossover)
            offspring_population: List[Dict[str, str]] = []
            for i in range(0, self.population_size, 2):
                parent1 = new_population[i]
                parent2 = new_population[i+1] if i+1 < self.population_size else random.choice(new_population) # 奇数サイズ対応
                
                if random.random() < self.crossover_rate:
                    child1, child2 = self._crossover(parent1, parent2)
                    offspring_population.extend([child1, child2])
                else:
                    offspring_population.extend([parent1, parent2])
            logger.debug(f"世代 {generation+1}: 交叉操作完了。生成された子孫数: {len(offspring_population)}")

            # 4. 変異 (Mutation)
            mutated_population: List[Dict[str, str]] = []
            for individual in offspring_population:
                mutated_population.append(self._mutate(individual))
            logger.debug(f"世代 {generation+1}: 変異操作完了。")

            # 5. 局所探索 (Local Search) - 各個体に適用
            # 実行可能解を維持しつつ、個々の解の質を向上させる
            next_generation_population = []
            for individual in mutated_population:
                ls_improved_individual = self._local_search_for_ga(individual)
                next_generation_population.append(self._repair_assignment(ls_improved_individual)) # 局所探索後も修復
            logger.debug(f"世代 {generation+1}: 局所探索適用完了。")

            population = next_generation_population
            logger.debug(f"世代 {generation+1}: 次の世代の個体群が設定されました。")

        end_time = time.time()
        duration = end_time - start_time
        self._log(f"GA_LS 最適化完了。実行時間: {duration:.2f}秒")
        logger.info(f"GA_LS: 最終ベストスコア: {best_overall_score:.2f}")

        status_str = "NO_SOLUTION_FOUND"
        message_str = "GA最適化で有効な解が見つかりませんでした。"
        unassigned_students: List[str] = []

        if best_overall_assignment:
            if self._is_feasible_assignment(best_overall_assignment):
                status_str = "OPTIMAL" # GAは厳密な最適解を保証しないが、ここではベストとみなす
                message_str = "GA最適化が成功しました。"
                unassigned_students = self._get_unassigned_students(best_overall_assignment)
                logger.info(f"GA_LS: 最終割り当ては実行可能です。未割り当て学生数: {len(unassigned_students)}")
            else:
                status_str = "INFEASIBLE"
                message_str = "GA最適化は実行不可能な解を返しました。定員制約を満たしていません。"
                logger.error(f"GA_LS: 最終割り当てが実行不可能です。割り当て: {best_overall_assignment}")
                unassigned_students = self.student_ids # 全員未割り当てとみなす
                best_overall_assignment = {} # 無効な割り当てはクリア

        return OptimizationResult(
            status=status_str,
            message=message_str,
            best_score=best_overall_score,
            best_assignment=best_overall_assignment,
            seminar_capacities=self.seminar_capacities,
            unassigned_students=unassigned_students,
            optimization_strategy="GA_LS"
        )

