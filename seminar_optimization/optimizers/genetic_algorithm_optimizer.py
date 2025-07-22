import random
import copy
import threading
import time
from typing import Dict, List, Any, Callable, Optional, Tuple

# BaseOptimizerとOptimizationResultをutilsからインポート
from seminar_optimization.utils import BaseOptimizer, OptimizationResult 
# ロギングは logger_config.py で一元的に設定されるため、ここではロガーの取得のみ
from seminar_optimization.logger_config import logger

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
        logger.debug("GeneticAlgorithmOptimizer: 初期化を開始します。")
        
        # 固有のパラメータはconfigから取得
        self.population_size = config.get("ga_population_size", 100)
        self.generations = config.get("ga_generations", 200)
        self.mutation_rate = config.get("ga_mutation_rate", 0.05)
        self.crossover_rate = config.get("ga_crossover_rate", 0.8)
        self.no_improvement_limit = config.get("ga_no_improvement_limit", 50) # 改善がない場合に早期停止する世代数
        logger.debug(f"GA_LS: 個体群サイズ={self.population_size}, 世代数={self.generations}, 変異率={self.mutation_rate}, 交叉率={self.crossover_rate}, 改善停止世代={self.no_improvement_limit}")

    def _generate_initial_population(self) -> List[Dict[str, str]]:
        """
        初期個体群を生成する。
        各個体は、学生の希望に基づいたランダムな割り当て（定員制約を考慮）となる。
        """
        logger.debug("GeneticAlgorithmOptimizer: 初期個体群の生成を開始します。")
        population = []
        for _ in range(self.population_size):
            assignment: Dict[str, str] = {}
            seminar_current_counts = {s_id: 0 for s_id in self.seminar_ids}
            
            # 学生をランダムな順序で処理
            shuffled_students = list(self.student_ids)
            random.shuffle(shuffled_students)

            for student_id in shuffled_students:
                preferences = self.student_preferences.get(student_id, [])
                assigned = False
                # 希望順に割り当てを試みる
                for preferred_seminar_id in preferences:
                    capacity = self.seminar_capacities.get(preferred_seminar_id)
                    if capacity is not None and seminar_current_counts[preferred_seminar_id] < capacity:
                        assignment[student_id] = preferred_seminar_id
                        seminar_current_counts[preferred_seminar_id] += 1
                        assigned = True
                        break
                # 希望するセミナーに割り当てられなかった場合、ランダムな空きセミナーに割り当てる
                # または未割り当てのままにする（ここでは未割り当てのまま）
                if not assigned:
                    pass # 未割り当てのままにする
            population.append(assignment)
        logger.info(f"GeneticAlgorithmOptimizer: {len(population)} 個の初期個体群を生成しました。")
        return population

    def _evaluate_fitness(self, assignment: Dict[str, str]) -> float:
        """
        割り当ての適応度（スコア）を計算する。
        定員制約を満たさない場合はペナルティを与える。
        """
        score = self._calculate_score(assignment)
        if not self._is_feasible_assignment(assignment):
            # 定員オーバーのセミナーがある場合、大きなペナルティ
            # 未割り当て学生がいる場合もペナルティ
            penalty = 0.0
            seminar_counts = {s_id: 0 for s_id in self.seminar_ids}
            for assigned_seminar_id in assignment.values():
                seminar_counts[assigned_seminar_id] = seminar_counts.get(assigned_seminar_id, 0) + 1
            
            for seminar_id, count in seminar_counts.items():
                capacity = self.seminar_capacities.get(seminar_id, 0)
                if count > capacity:
                    penalty += (count - capacity) * 100.0 # 定員オーバー1人あたり100点のペナルティ
            
            unassigned_students_count = len(self._get_unassigned_students(assignment))
            penalty += unassigned_students_count * 50.0 # 未割り当て1人あたり50点のペナルティ

            score -= penalty
            logger.debug(f"GA_LS: 不適合な割り当てにペナルティ {penalty:.2f} を適用しました。調整後スコア: {score:.2f}")
        return score

    def _selection(self, population: List[Dict[str, str]], fitnesses: List[float]) -> List[Dict[str, str]]:
        """
        ルーレット選択により次世代の親を選択する。
        """
        logger.debug("GeneticAlgorithmOptimizer: 親の選択を開始します。")
        selected_parents = []
        # 適応度が負の値になる可能性を考慮し、最小値を0にシフト
        min_fitness = min(fitnesses)
        adjusted_fitnesses = [f - min_fitness + 1 for f in fitnesses] # 全て正の値にする
        total_adjusted_fitness = sum(adjusted_fitnesses)

        if total_adjusted_fitness == 0: # 全ての個体が同じ（低い）適応度の場合
            logger.warning("GA_LS: 全ての個体の適応度が同じか非常に低いため、ランダム選択にフォールバックします。")
            return random.sample(population, self.population_size)

        for _ in range(self.population_size):
            pick = random.uniform(0, total_adjusted_fitness)
            current = 0
            for i, individual in enumerate(population):
                current += adjusted_fitnesses[i]
                if current > pick:
                    selected_parents.append(individual)
                    break
        logger.debug(f"GeneticAlgorithmOptimizer: {len(selected_parents)} 個の親を選択しました。")
        return selected_parents

    def _crossover(self, parent1: Dict[str, str], parent2: Dict[str, str]) -> Tuple[Dict[str, str], Dict[str, str]]:
        """
        2つの親から2つの子を生成する（一点交叉）。
        学生の割り当てをランダムな点で分割し、組み合わせる。
        """
        logger.debug("GeneticAlgorithmOptimizer: 交叉を開始します。")
        child1 = {}
        child2 = {}
        
        student_ids = list(self.student_ids)
        if not student_ids: # 学生がいない場合は空の割り当てを返す
            return {}, {}

        crossover_point = random.randint(1, len(student_ids) - 1)

        for i, student_id in enumerate(student_ids):
            if i < crossover_point:
                child1[student_id] = parent1.get(student_id)
                child2[student_id] = parent2.get(student_id)
            else:
                child1[student_id] = parent2.get(student_id)
                child2[student_id] = parent1.get(student_id)
        
        # None値を持つ割り当てを削除（未割り当てとして扱う）
        child1 = {k: v for k, v in child1.items() if v is not None}
        child2 = {k: v for k, v in child2.items() if v is not None}

        logger.debug("GeneticAlgorithmOptimizer: 交叉が完了しました。")
        return child1, child2

    def _mutate(self, assignment: Dict[str, str]) -> Dict[str, str]:
        """
        割り当てに突然変異を導入する。
        ランダムな学生の割り当てを変更するか、未割り当てにする。
        """
        logger.debug("GeneticAlgorithmOptimizer: 突然変異を適用します。")
        mutated_assignment = assignment.copy()
        for student_id in self.student_ids:
            if random.random() < self.mutation_rate:
                # 突然変異の種類を選択:
                # 1. 未割り当ての学生を割り当てる
                # 2. 割り当て済みの学生のセミナーを変更する
                # 3. 割り当て済みの学生を未割り当てにする
                
                if student_id not in mutated_assignment: # 未割り当ての場合
                    preferences = self.student_preferences.get(student_id, [])
                    if preferences:
                        # 希望の中からランダムに選択し、定員に空きがあれば割り当てる
                        random.shuffle(preferences)
                        for preferred_seminar_id in preferences:
                            if preferred_seminar_id in self.seminar_capacities and \
                               list(mutated_assignment.values()).count(preferred_seminar_id) < self.seminar_capacities[preferred_seminar_id]:
                                mutated_assignment[student_id] = preferred_seminar_id
                                logger.debug(f"GA_LS: 学生 {student_id} を未割り当てから {preferred_seminar_id} に変異させました。")
                                break
                else: # 割り当て済みの場合
                    current_seminar = mutated_assignment[student_id]
                    # 50%の確率で別のセミナーへ移動、50%の確率で未割り当てにする
                    if random.random() < 0.5 and len(self.seminar_ids) > 1:
                        available_seminars = [s for s in self.seminar_ids if s != current_seminar]
                        if available_seminars:
                            new_seminar = random.choice(available_seminars)
                            if list(mutated_assignment.values()).count(new_seminar) < self.seminar_capacities[new_seminar]:
                                mutated_assignment[student_id] = new_seminar
                                logger.debug(f"GA_LS: 学生 {student_id} を {current_seminar} から {new_seminar} に変異させました。")
                            else: # 新しいセミナーの定員が満杯なら未割り当てにする
                                del mutated_assignment[student_id]
                                logger.debug(f"GA_LS: 学生 {student_id} を {current_seminar} から未割り当てに変異させました (移動失敗)。")
                        else: # 他にセミナーがない場合、未割り当てにする
                            del mutated_assignment[student_id]
                            logger.debug(f"GA_LS: 学生 {student_id} を {current_seminar} から未割り当てに変異させました (移動先なし)。")
                    else:
                        del mutated_assignment[student_id] # 未割り当てにする
                        logger.debug(f"GA_LS: 学生 {student_id} を {current_seminar} から未割り当てに変異させました。")
        return mutated_assignment

    def _apply_local_search(self, assignment: Dict[str, str], iterations: int = 100) -> Dict[str, str]:
        """
        個体に局所探索を適用して、さらに改善を試みる。
        これは GreedyLSOptimizer の _local_search の簡易版。
        """
        logger.debug("GeneticAlgorithmOptimizer: 局所探索を個体に適用します。")
        current_assignment = assignment.copy()
        current_score = self._evaluate_fitness(current_assignment)

        for _ in range(iterations):
            if not current_assignment:
                break # 割り当てがない場合は終了

            student_id = random.choice(list(current_assignment.keys()))
            original_seminar = current_assignment[student_id]

            # 別のセミナーに移動を試みる
            possible_moves = []
            # 未割り当てにするオプション
            temp_assignment_unassigned = current_assignment.copy()
            del temp_assignment_unassigned[student_id]
            if self._is_feasible_assignment(temp_assignment_unassigned):
                possible_moves.append((temp_assignment_unassigned, self._evaluate_fitness(temp_assignment_unassigned)))

            # 別のセミナーへの移動オプション
            for target_seminar in self.seminar_ids:
                if target_seminar == original_seminar:
                    continue
                temp_assignment_move = current_assignment.copy()
                # 元のセミナーの定員を一旦解放
                temp_assignment_move[student_id] = target_seminar # 新しいセミナーに割り当て

                if self._is_feasible_assignment(temp_assignment_move):
                    possible_moves.append((temp_assignment_move, self._evaluate_fitness(temp_assignment_move)))
            
            if possible_moves:
                best_move_assignment, best_move_score = max(possible_moves, key=lambda x: x[1])
                if best_move_score > current_score:
                    current_assignment = best_move_assignment
                    current_score = best_move_score
                    logger.debug(f"GA_LS: 個体への局所探索でスコア改善: {current_score:.2f}")
            
        return current_assignment

    def optimize(self, cancel_event: Optional[threading.Event] = None) -> OptimizationResult:
        """
        最適化プロセスを実行する。
        """
        start_time = time.time()
        self._log("GA_LS 最適化を開始します...")

        population = self._generate_initial_population()
        best_overall_assignment: Dict[str, str] = {}
        best_overall_score = -float('inf')
        no_improvement_count = 0

        for generation in range(self.generations):
            if cancel_event and cancel_event.is_set():
                self._log(f"GA_LS: 最適化が世代 {generation} でキャンセルされました。")
                break

            self._log(f"GA_LS: 世代 {generation+1}/{self.generations} を処理中...")

            # 適応度の評価
            fitnesses = [self._evaluate_fitness(individual) for individual in population]

            # 現在の世代のベスト個体を追跡
            current_best_idx = fitnesses.index(max(fitnesses))
            current_best_assignment = population[current_best_idx]
            current_best_score = fitnesses[current_best_idx]

            if current_best_score > best_overall_score:
                best_overall_score = current_best_score
                best_overall_assignment = current_best_assignment.copy()
                no_improvement_count = 0
                self._log(f"GA_LS: 世代 {generation+1} でベストスコアを更新: {best_overall_score:.2f}")
            else:
                no_improvement_count += 1
                self._log(f"GA_LS: 世代 {generation+1} で改善なし。連続改善なし: {no_improvement_count} 世代。")

            if no_improvement_count >= self.no_improvement_limit:
                self._log(f"GA_LS: {self.no_improvement_limit} 世代の間改善がなかったため、早期停止します。")
                break

            # 選択
            parents = self._selection(population, fitnesses)

            # 交叉と突然変異
            next_population = []
            # エリート選択: 最も良い個体を次世代にそのまま引き継ぐ
            if best_overall_assignment:
                next_population.append(best_overall_assignment)

            while len(next_population) < self.population_size:
                parent1 = random.choice(parents)
                parent2 = random.choice(parents)

                if random.random() < self.crossover_rate:
                    child1, child2 = self._crossover(parent1, parent2)
                else:
                    child1, child2 = parent1.copy(), parent2.copy() # 交叉しない場合は親をそのままコピー

                mutated_child1 = self._mutate(child1)
                mutated_child2 = self._mutate(child2)

                # 局所探索を適用して個体を強化
                next_population.append(self._apply_local_search(mutated_child1, iterations=self.config.get("local_search_iterations", 100)))
                if len(next_population) < self.population_size:
                    next_population.append(self._apply_local_search(mutated_child2, iterations=self.config.get("local_search_iterations", 100)))
            
            population = next_population[:self.population_size] # サイズ調整
            logger.debug(f"GA_LS: 世代 {generation+1}: 次の世代の個体群が設定されました。")

        end_time = time.time()
        duration = end_time - start_time
        self._log(f"GA_LS 最適化完了。実行時間: {duration:.2f}秒")
        logger.info(f"GA_LS: 最終ベストスコア: {best_overall_score:.2f}")

        status_str = "NO_SOLUTION_FOUND"
        message_str = "GA最適化で有効な解が見つかりませんでした。"
        unassigned_students: List[str] = []

        if best_overall_assignment:
            # 最終的なベスト割り当てが実行可能か再確認
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
                best_overall_score = -float('inf') # 不可能な解はスコアを最低にする

        if cancel_event and cancel_event.is_set():
            status_str = "CANCELLED"
            message_str = "最適化がユーザーによってキャンセルされました。"
            best_overall_score = -float('inf') # キャンセルされた場合はスコアを無効にする
            unassigned_students = self.student_ids # 全員未割り当てとみなす

        return OptimizationResult(
            status=status_str,
            message=message_str,
            best_score=best_overall_score,
            best_assignment=best_overall_assignment,
            seminar_capacities=self.seminar_capacities,
            unassigned_students=unassigned_students,
            optimization_strategy="GA_LS"
        )
