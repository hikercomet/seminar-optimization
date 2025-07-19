import random
import numpy as np
import logging
from collections import defaultdict
# 修正: Dict, List, Tuple は Python 3.9+ で不要なため削除 (または小文字に修正)
# from typing import Dict, List, Tuple

# 外部モジュールからのインポート
from models import Config, Student
from utils import PreferenceGenerator, TargetSizeOptimizer 

logger = logging.getLogger(__name__)

class GreedyAssigner:
    """貪欲法による初期割当を行うクラス"""
    def __init__(self, config_dict: dict): # 修正: dictを使用
        self.config = Config(**config_dict)

    def assign_students_greedily(self, students: list[Student], target_sizes: dict[str, int]) -> tuple[float, dict[str, list[tuple[int, float]]]]: # 修正: list, dict, tupleを使用
        """
        学生を貪欲法でセミナーに初期割当します。
        各学生について、最もスコアが高く、かつ現在のセミナー定員が目標定員を超えないセミナーに割り当てます。
        目標定員に達している場合は、最大定員まで許容します。
        """
        current_assignments = {sem: [] for sem in self.config.seminars}
        seminar_current_counts = defaultdict(int)
        
        # 学生をランダムな順序で処理することで、同じ希望を持つ学生間の公平性を高める
        shuffled_students = list(students)
        random.shuffle(shuffled_students)

        total_score = 0.0
        assigned_student_ids = set()

        # 優先順位に基づいて学生を割り当てる
        for student in shuffled_students:
            best_seminar = None
            best_score_for_student = -1.0 
            
            # 学生の希望順位に基づいてセミナーを評価
            for preferred_seminar in student.preferences:
                score = student.calculate_score(preferred_seminar, self.config.magnification, self.config.preference_weights)
                
                # 目標定員内であれば優先
                if seminar_current_counts[preferred_seminar] < target_sizes[preferred_seminar]:
                    if score > best_score_for_student:
                        best_score_for_student = score
                        best_seminar = preferred_seminar
                # 目標定員を超えていても、最大定員内であれば考慮
                elif seminar_current_counts[preferred_seminar] < self.config.max_size:
                    if score > best_score_for_student:
                        best_score_for_student = score
                        best_seminar = preferred_seminar
            
            # 最適なセミナーが見つかった場合
            if best_seminar:
                current_assignments[best_seminar].append((student.id, best_score_for_student))
                seminar_current_counts[best_seminar] += 1
                total_score += best_score_for_student
                assigned_student_ids.add(student.id)
            else:
                # どの希望セミナーも割り当てられない場合、空きのあるセミナーにランダムに割り当てる
                available_seminars = [sem for sem in self.config.seminars if seminar_current_counts[sem] < self.config.max_size]
                if available_seminars:
                    chosen_seminar = random.choice(available_seminars)
                    score = student.calculate_score(chosen_seminar, self.config.magnification, self.config.preference_weights)
                    current_assignments[chosen_seminar].append((student.id, score))
                    seminar_current_counts[chosen_seminar] += 1
                    total_score += score
                    assigned_student_ids.add(student.id)
                else:
                    logger.warning(f"Student {student.id} could not be assigned to any seminar due to full capacity.")
        
        # 未割り当ての学生がいたら、残りの空きに強制的に割り当てる（もしあれば）
        unassigned_students = [s for s in students if s.id not in assigned_student_ids]
        for student in unassigned_students:
            found_slot = False
            for sem in self.config.seminars:
                if seminar_current_counts[sem] < self.config.max_size:
                    score = student.calculate_score(sem, self.config.magnification, self.config.preference_weights)
                    current_assignments[sem].append((student.id, score))
                    seminar_current_counts[sem] += 1
                    total_score += score
                    found_slot = True
                    break
            if not found_slot:
                logger.error(f"Critical: Student {student.id} could not be assigned even after greedy pass and forced assignment attempt. Total students might exceed total max capacity.")
                
        return total_score, current_assignments

class LocalSearchOptimizer:
    """局所探索法 (簡易焼きなまし法を含む) による改善"""
    
    def __init__(self, config_dict: dict, num_iterations: int, initial_temperature: float, cooling_rate: float): # 修正: dictを使用
        self.config = Config(**config_dict) 
        self.num_iterations = num_iterations
        self.initial_temperature = initial_temperature
        self.cooling_rate = cooling_rate
    
    def improve_assignment(self, students: list[Student], assignments: dict[str, list[tuple[int, float]]], 
                             target_sizes: dict[str, int]) -> tuple[float, dict[str, list[tuple[int, float]]]]: # 修正: list, dict, tupleを使用
        """局所探索法を用いて割当を改善します"""
        
        current_assignments = {sem: list(assignments[sem]) for sem in assignments}
        current_score = sum(score for sem in current_assignments for _, score in current_assignments[sem])
        
        students_dict = {s.id: s for s in students}
        
        temperature = self.initial_temperature
        
        for iteration in range(self.num_iterations): 
            improved_in_this_iter = False
            
            # 2-optスタイルの交換 (2つのランダムなセミナー間で学生を交換)
            num_exchanges = self.config.num_students // 4 
            for _ in range(num_exchanges): 
                sem1 = random.choice(self.config.seminars)
                sem2 = random.choice(self.config.seminars)

                if sem1 == sem2 or not current_assignments[sem1] or not current_assignments[sem2]:
                    continue
                
                student1_idx_in_sem1 = random.randrange(len(current_assignments[sem1]))
                student2_idx_in_sem2 = random.randrange(len(current_assignments[sem2]))

                student1_id, _ = current_assignments[sem1][student1_idx_in_sem1]
                student2_id, _ = current_assignments[sem2][student2_idx_in_sem2]
                
                student1 = students_dict[student1_id]
                student2 = students_dict[student2_id]
                
                # Student.calculate_score に preference_weights を渡す
                old_score1 = student1.calculate_score(sem1, self.config.magnification, self.config.preference_weights)
                old_score2 = student2.calculate_score(sem2, self.config.magnification, self.config.preference_weights)
                new_score1 = student1.calculate_score(sem2, self.config.magnification, self.config.preference_weights)
                new_score2 = student2.calculate_score(sem1, self.config.magnification, self.config.preference_weights) 
                
                score_diff = (new_score1 + new_score2) - (old_score1 + old_score2)
                
                if score_diff > 0.01 or (score_diff <= 0 and random.random() < np.exp(score_diff / temperature)):
                    current_assignments[sem1][student1_idx_in_sem1] = (student2_id, new_score2)
                    current_assignments[sem2][student2_idx_in_sem2] = (student1_id, new_score1)
                    current_score += score_diff
                    improved_in_this_iter = True
            
            # 学生の単一移動 (近傍探索)
            num_moves = self.config.num_students // 5 
            for _ in range(num_moves): 
                seminar_from_name = random.choice(self.config.seminars)
                if not current_assignments[seminar_from_name]:
                    continue
                
                student_idx_in_from_sem = random.randrange(len(current_assignments[seminar_from_name]))
                student_id_to_move, old_score = current_assignments[seminar_from_name][student_idx_in_from_sem]
                student_to_move = students_dict[student_id_to_move]
                
                seminar_to_name = random.choice([s for s in self.config.seminars if s != seminar_from_name])
                
                if len(current_assignments[seminar_to_name]) >= target_sizes[seminar_to_name] * 1.1: 
                    continue

                # Student.calculate_score に preference_weights を渡す
                new_score = student_to_move.calculate_score(seminar_to_name, self.config.magnification, self.config.preference_weights)
                score_diff_move = new_score - old_score
                
                if score_diff_move > 0.01 or (score_diff_move <= 0 and random.random() < np.exp(score_diff_move / temperature)):
                    current_assignments[seminar_from_name].pop(student_idx_in_from_sem)
                    current_assignments[seminar_to_name].append((student_id_to_move, new_score))
                    current_score += score_diff_move
                    improved_in_this_iter = True
            
            # 温度を冷却
            temperature *= self.cooling_rate 
            
            if not improved_in_this_iter and temperature < 0.001:
                break
        
        return current_score, current_assignments

# トップレベル関数として定義
# 修正: Dict, List, Tuple を dict, list, tuple に変更
def _optimize_single_pattern_task(config_dict: dict, pattern_id: int, all_students: list[Student]) -> tuple[float, dict[str, list[tuple[int, float]]], dict[str, int]]:
    """
    並列処理のための単一パターン最適化タスク。
    この関数はプロセス間で安全にpickle化できるようトップレベルに配置されています。
    """
    try:
        current_config = Config(**config_dict) 

        target_optimizer = TargetSizeOptimizer(config_dict)
        greedy_assigner = GreedyAssigner(config_dict) 
        
        local_optimizer = LocalSearchOptimizer(
            config_dict,
            num_iterations=current_config.local_search_iterations,
            initial_temperature=current_config.initial_temperature,
            cooling_rate=current_config.cooling_rate
        )
        
        students = all_students 

        target_sizes = target_optimizer.generate_balanced_sizes(students, pattern_id)
        
        score, assignments = greedy_assigner.assign_students_greedily(students, target_sizes)
        
        improved_score, improved_assignments = local_optimizer.improve_assignment(
            students, assignments, target_sizes
        )
        
        return improved_score, improved_assignments, target_sizes
            
    except Exception as e:
        logger.error(f"Pattern {pattern_id} optimization failed: {e}")
        return 0.0, {sem: [] for sem in Config(**config_dict).seminars}, {}

