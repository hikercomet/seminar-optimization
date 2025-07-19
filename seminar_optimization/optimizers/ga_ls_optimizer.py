import random
import numpy as np
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Callable, Optional

# 外部モジュールからのインポート
from models import Config, Student
from optimizers.greedy_ls_optimizer import LocalSearchOptimizer # LocalSearchOptimizerをインポート

logger = logging.getLogger(__name__)

class GeneticAlgorithmOptimizer:
    """
    遺伝的アルゴリズム (Genetic Algorithm) を用いてセミナー割り当てを最適化するクラスです。
    Lamarckian GAとして、各個体の評価前に局所探索（Local Search）を適用します。
    """
    def __init__(self, config_dict: dict, students: list[Student], target_sizes: dict[str, int]):
        self.config = Config(**config_dict)
        self.students = students
        self.target_sizes = target_sizes
        self.students_dict = {s.id: s for s in students} # 学生IDから学生オブジェクトへのマッピング
        self.seminar_names = self.config.seminars # セミナー名のリスト

        self.population_size = self.config.ga_population_size
        self.crossover_rate = self.config.ga_crossover_rate
        self.mutation_rate = self.config.ga_mutation_rate
        self.num_generations = self.config.num_patterns # GAではnum_patternsを世代数として使用

        self.local_search_optimizer = LocalSearchOptimizer(
            config_dict,
            num_iterations=self.config.local_search_iterations,
            initial_temperature=self.config.initial_temperature,
            cooling_rate=self.config.cooling_rate
        )

    def _initial_assignment_random(self) -> dict[str, list[tuple[int, float]]]:
        """
        ランダムな初期割り当てを生成します。
        各学生をランダムなセミナーに割り当てます。
        """
        initial_assignments = {sem: [] for sem in self.seminar_names}
        student_ids = [s.id for s in self.students]
        random.shuffle(student_ids)

        for student_id in student_ids:
            seminar_name = random.choice(self.seminar_names)
            student_obj = self.students_dict[student_id]
            score = student_obj.calculate_score(seminar_name, self.config.magnification, self.config.preference_weights)
            initial_assignments[seminar_name].append((student_id, score)) 
        
        # 初期割り当てに対して簡易的な修復を適用
        self._repair_assignment(initial_assignments)
        return initial_assignments

    def _initialize_population(self, progress_callback: Callable[[str], None]) -> list[tuple[dict[str, list[tuple[int, float]]], float]]:
        """
        初期個体群を生成し、Lamarckian GAとして局所探索を適用します。
        """
        population = []
        for i in range(self.population_size):
            if progress_callback:
                progress_callback(f"  初期個体生成中: {i+1}/{self.population_size}")
            
            initial_individual = self._initial_assignment_random()
            
            # Lamarckian GAの初期化ステップ: 初期個体に局所探索を適用
            score, improved_assignment = self.local_search_optimizer.improve_assignment(
                self.students, initial_individual, self.target_sizes, progress_callback=None # 内部局所探索の進捗は表示しない
            )
            population.append((improved_assignment, score))
        
        return population

    def _selection(self, population_with_fitness: list[tuple[dict[str, list[tuple[int, float]]], float]]) -> tuple[dict[str, list[tuple[int, float]]], dict[str, list[tuple[int, float]]]]:
        """
        親個体を選択します（トーナメント選択）。
        """
        # トーナメントサイズ
        tournament_size = max(2, self.population_size // 10) 
        
        selected_parents = []
        for _ in range(2): # 2人の親を選択
            tournament_candidates = random.sample(population_with_fitness, tournament_size)
            # 最も適応度の高い個体を選択
            winner = max(tournament_candidates, key=lambda x: x[1])[0]
            selected_parents.append(winner)
        return selected_parents[0], selected_parents[1]

    def _crossover(self, parent1: dict[str, list[tuple[int, float]]], parent2: dict[str, list[tuple[int, float]]]) -> tuple[dict[str, list[tuple[int, float]]], dict[str, list[tuple[int, float]]]]:
        """
        2つの親個体から新しい子個体を生成します（均一交叉）。
        学生IDに基づいて割り当てセミナーを交換します。
        """
        # 割り当てを学生IDをキーとする辞書に変換
        parent1_flat = {s_id: sem_name for sem_name, students_in_sem in parent1.items() for s_id, _ in students_in_sem}
        parent2_flat = {s_id: sem_name for sem_name, students_in_sem in parent2.items() for s_id, _ in students_in_sem}

        child1_flat = {}
        child2_flat = {}
        
        # 学生IDのリストを取得し、シャッフル
        all_student_ids = list(self.students_dict.keys())

        for student_id in all_student_ids:
            if random.random() < 0.5: # 50%の確率で親1から、50%の確率で親2から引き継ぐ
                child1_flat[student_id] = parent1_flat.get(student_id, random.choice(self.seminar_names))
                child2_flat[student_id] = parent2_flat.get(student_id, random.choice(self.seminar_names))
            else:
                child1_flat[student_id] = parent2_flat.get(student_id, random.choice(self.seminar_names))
                child2_flat[student_id] = parent1_flat.get(student_id, random.choice(self.seminar_names))
        
        # フラットな割り当てを元の辞書形式に戻す
        child1_assignments = {sem: [] for sem in self.seminar_names}
        child2_assignments = {sem: [] for sem in self.seminar_names}

        for s_id, sem_name in child1_flat.items():
            student_obj = self.students_dict[s_id]
            score = student_obj.calculate_score(sem_name, self.config.magnification, self.config.preference_weights)
            child1_assignments[sem_name].append((s_id, score))
        
        for s_id, sem_name in child2_flat.items():
            student_obj = self.students_dict[s_id]
            score = student_obj.calculate_score(sem_name, self.config.magnification, self.config.preference_weights)
            child2_assignments[sem_name].append((s_id, score))

        # 定員制約を緩やかに満たすように調整 (簡易的な修復)
        self._repair_assignment(child1_assignments)
        self._repair_assignment(child2_assignments)

        return child1_assignments, child2_assignments

    def _mutate(self, assignment: dict[str, list[tuple[int, float]]]) -> dict[str, list[tuple[int, float]]]:
        """
        個体に突然変異を適用します。
        ランダムに選ばれた学生の割り当てセミナーを変更します。
        """
        mutated_assignment = {sem: list(students) for sem, students in assignment.items()}
        
        # 全ての割り当て済み学生のリストを作成
        all_assigned_students = []
        for sem_name, students_in_sem in mutated_assignment.items():
            for student_id, score in students_in_sem:
                all_assigned_students.append((student_id, sem_name))

        if not all_assigned_students:
            return mutated_assignment # 割り当てがない場合は何もしない

        if random.random() < self.mutation_rate:
            # ランダムに学生を選び、別のセミナーに割り当てる
            student_to_mutate_info = random.choice(all_assigned_students)
            student_id, old_seminar_name = student_to_mutate_info
            
            # 新しいセミナーをランダムに選択 (元のセミナー以外)
            available_seminars = [s for s in self.seminar_names if s != old_seminar_name]
            if available_seminars:
                new_seminar_name = random.choice(available_seminars)
                
                # 古いセミナーから学生を削除
                mutated_assignment[old_seminar_name] = [
                    (s_id, score) for s_id, score in mutated_assignment[old_seminar_name] if s_id != student_id
                ]
                
                # 新しいセミナーに学生を追加し、スコアを再計算
                student_obj = self.students_dict[student_id]
                new_score = student_obj.calculate_score(new_seminar_name, self.config.magnification, self.config.preference_weights)
                mutated_assignment[new_seminar_name].append((student_id, new_score))
                
                # 定員制約を緩やかに満たすように調整
                self._repair_assignment(mutated_assignment)

        return mutated_assignment

    def _repair_assignment(self, assignment: dict[str, list[tuple[int, float]]]):
        """
        割り当てが定員制約を大きく逸脱しないように簡易的に修復します。
        これは厳密な制約充足ではなく、GAの探索をガイドするものです。
        """
        current_counts = {sem: len(students) for sem, students in assignment.items()}
        
        # 超過しているセミナーから学生を移動
        for sem_name in self.seminar_names:
            while current_counts[sem_name] > self.config.max_size:
                if not assignment[sem_name]: break # 学生がいなければ終了
                
                # ランダムに学生を選び、移動させる
                student_to_move_idx = random.randrange(len(assignment[sem_name]))
                student_id, _ = assignment[sem_name].pop(student_to_move_idx)
                student_obj = self.students_dict[student_id]
                current_counts[sem_name] -= 1

                # 移動先のセミナーを探す
                # まだmax_sizeに達していないセミナーを優先
                available_to_move_to = [s for s in self.seminar_names if current_counts[s] < self.config.max_size]
                if not available_to_move_to: # 全てのセミナーが最大定員に達している場合
                    # 全てのセミナーからランダムに選ぶ（この場合、他のセミナーも超過する可能性あり）
                    available_to_move_to = list(self.seminar_names) 
                
                target_sem = random.choice(available_to_move_to)
                
                score = student_obj.calculate_score(target_sem, self.config.magnification, self.config.preference_weights)
                assignment[target_sem].append((student_id, score))
                current_counts[target_sem] += 1
        
        # 不足しているセミナーに学生を割り当てる（もし未割り当てがいれば）
        # GAでは全ての学生が割り当てられていることを前提とするため、このステップは主に初期化や交叉・突然変異後の補助
        all_assigned_ids = set()
        for sem_name, students_in_sem in assignment.items():
            for s_id, _ in students_in_sem:
                all_assigned_ids.add(s_id)
        
        # 全ての学生が割り当てられているか確認
        if len(all_assigned_ids) < len(self.students):
            unassigned_students_in_repair = [s for s in self.students if s.id not in all_assigned_ids]
            
            for student_obj in unassigned_students_in_repair:
                found_slot = False
                # 最も空きがあるセミナーを優先して割り当てる
                sorted_seminars_by_capacity = sorted(self.seminar_names, key=lambda sem: current_counts[sem])
                for sem_name in sorted_seminars_by_capacity:
                    if current_counts[sem_name] < self.config.max_size: # 最大定員まで許容
                        score = student_obj.calculate_score(sem_name, self.config.magnification, self.config.preference_weights)
                        assignment[sem_name].append((student_obj.id, score))
                        current_counts[sem_name] += 1
                        found_slot = True
                        break
                if not found_slot:
                    logger.warning(f"Repair: Student {student_obj.id} could not be reassigned to any seminar. This might lead to unassigned students.")
        
        # 最終チェック：全ての学生が割り当てられているか
        final_assigned_count = sum(len(students_in_sem) for students_in_sem in assignment.values())
        if final_assigned_count != len(self.students):
            logger.error(f"Repair failed: Total assigned students ({final_assigned_count}) != total students ({len(self.students)}).")


    def run_ga(self, progress_callback: Callable[[str], None]) -> tuple[float, dict[str, list[tuple[int, float]]]]:
        """
        遺伝的アルゴリズムのメインループを実行します。
        """
        logger.info("遺伝的アルゴリズムを開始します。")
        progress_callback("遺伝的アルゴリズムを開始しています...")

        # 初期個体群を生成 (Lamarckian GA: 初期個体にも局所探索適用済み)
        population_with_fitness = self._initialize_population(progress_callback)
        
        # 初期個体群からベストスコアを抽出
        best_overall_assignment, best_overall_score = max(population_with_fitness, key=lambda x: x[1])
        logger.info(f"[GA Initial Best] スコア {best_overall_score:.2f}")

        for generation in range(self.num_generations):
            if progress_callback:
                progress_callback(f"GA世代 {generation+1}/{self.num_generations} を処理中... (現在のベスト: {best_overall_score:.2f})")

            new_population_with_fitness = []

            # エリート選択 (最も良い個体を次世代に引き継ぐ)
            population_with_fitness.sort(key=lambda x: x[1], reverse=True)
            elites_count = max(1, self.population_size // 10) # 10%をエリートとする
            new_population_with_fitness.extend(population_with_fitness[:elites_count])

            # 選択、交叉、突然変異で残りの個体を生成
            while len(new_population_with_fitness) < self.population_size:
                parent1_assignment, _ = self._selection(population_with_fitness)
                parent2_assignment, _ = self._selection(population_with_fitness)
                
                child1_assignment, child2_assignment = parent1_assignment, parent2_assignment # デフォルトは親をそのまま引き継ぐ

                if random.random() < self.crossover_rate:
                    child1_assignment, child2_assignment = self._crossover(parent1_assignment, parent2_assignment)

                child1_assignment = self._mutate(child1_assignment)
                child2_assignment = self._mutate(child2_assignment)
                
                # Lamarckian GA: 子個体にも局所探索を適用し、改善された個体とスコアを保存
                score1, improved_child1 = self.local_search_optimizer.improve_assignment(
                    self.students, child1_assignment, self.target_sizes, progress_callback=None
                )
                new_population_with_fitness.append((improved_child1, score1))

                if len(new_population_with_fitness) < self.population_size:
                    score2, improved_child2 = self.local_search_optimizer.improve_assignment(
                        self.students, child2_assignment, self.target_sizes, progress_callback=None
                    )
                    new_population_with_fitness.append((improved_child2, score2))
            
            population_with_fitness = new_population_with_fitness

            # 世代のベストスコアを更新
            current_generation_best_assignment, current_generation_best_score = max(population_with_fitness, key=lambda x: x[1])
            if current_generation_best_score > best_overall_score:
                best_overall_score = current_generation_best_score
                best_overall_assignment = current_generation_best_assignment
                logger.info(f"[GA New Record] 世代 {generation+1}: スコア {best_overall_score:.2f}")
            
            if self.config.log_enabled and generation % (self.num_generations // 10 or 1) == 0:
                logger.info(f"GA世代 {generation+1} 完了。現在のベストスコア: {best_overall_score:.2f}")

        logger.info("遺伝的アルゴリズムが完了しました。")
        progress_callback("遺伝的アルゴリズムが完了しました。")
        return best_overall_score, best_overall_assignment

