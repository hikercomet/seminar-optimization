import random
import numpy as np
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Callable, Optional

# 外部モジュールからのインポート
from models import Config, Student

logger = logging.getLogger(__name__)

class GreedyAssigner:
    """貪欲法による初期割当を行うクラス"""
    def __init__(self, config_dict: dict):
        self.config = Config(**config_dict)

    def assign_students_greedily(self, students: list[Student], target_sizes: dict[str, int]) -> tuple[float, dict[str, list[tuple[int, float]]]]:
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
            # 希望セミナーのリストをコピーして、割り当て可能なセミナーから順に試す
            student_preferred_seminars = list(student.preferences)
            random.shuffle(student_preferred_seminars) # 希望順位内でもランダム性を導入

            for preferred_seminar in student_preferred_seminars:
                # Student.calculate_score に preference_weights を渡す
                score = student.calculate_score(preferred_seminar, self.config.magnification, self.config.preference_weights)
                
                # 目標定員内であれば優先
                if seminar_current_counts[preferred_seminar] < target_sizes[preferred_seminar]:
                    if score > best_score_for_student:
                        best_score_for_student = score
                        best_seminar = preferred_seminar
                        # 目標定員内の割り当てが見つかったら、それ以上の希望は探さない（貪欲性）
                        break 
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
                # ただし、最大定員を超えないようにする
                available_seminars = [sem for sem in self.config.seminars if seminar_current_counts[sem] < self.config.max_size]
                if available_seminars:
                    chosen_seminar = random.choice(available_seminars)
                    # Student.calculate_score に preference_weights を渡す
                    score = student.calculate_score(chosen_seminar, self.config.magnification, self.config.preference_weights)
                    current_assignments[chosen_seminar].append((student.id, score))
                    seminar_current_counts[chosen_seminar] += 1
                    total_score += score
                    assigned_student_ids.add(student.id)
                else:
                    logger.warning(f"Student {student.id} could not be assigned to any seminar due to full capacity. This might indicate an issue with seminar capacities or student preferences.")
        
        # 未割り当ての学生がいたら、残りの空きに強制的に割り当てる（もしあれば）
        # このフェーズは、厳密な定員制約を破る可能性もあるが、全学生を割り当てることを優先する
        unassigned_students = [s for s in students if s.id not in assigned_student_ids]
        for student in unassigned_students:
            found_slot = False
            # 最も空きがあるセミナーを優先して割り当てる
            sorted_seminars_by_capacity = sorted(self.config.seminars, key=lambda sem: seminar_current_counts[sem])
            for sem in sorted_seminars_by_capacity:
                if seminar_current_counts[sem] < self.config.max_size: # 最大定員まで許容
                    # Student.calculate_score に preference_weights を渡す
                    score = student.calculate_score(sem, self.config.magnification, self.config.preference_weights)
                    current_assignments[sem].append((student.id, score))
                    seminar_current_counts[sem] += 1
                    total_score += score
                    found_slot = True
                    assigned_student_ids.add(student.id) # 割り当て済みとしてマーク
                    break
            if not found_slot:
                logger.error(f"Critical: Student {student.id} could not be assigned even after greedy pass and forced assignment attempt. Total students might exceed total max capacity or all seminars are at max capacity.")
                
        return total_score, current_assignments

class LocalSearchOptimizer:
    """局所探索法 (簡易焼きなまし法を含む) による改善"""
    
    def __init__(self, config_dict: dict, num_iterations: int, initial_temperature: float, cooling_rate: float):
        self.config = Config(**config_dict) 
        self.num_iterations = num_iterations
        self.initial_temperature = initial_temperature
        self.cooling_rate = cooling_rate
    
    def improve_assignment(self, students: list[Student], assignments: dict[str, list[tuple[int, float]]], 
                             target_sizes: dict[str, int], progress_callback: Optional[Callable[[str], None]] = None) -> tuple[float, dict[str, list[tuple[int, float]]]]:
        """
        局所探索法を用いて割当を改善します。
        割り当てられた学生のリストとスコアを保持し、変更時に更新します。
        """
        
        current_assignments = {sem: list(assignments[sem]) for sem in assignments} # 割り当てをコピー
        current_score = sum(score for sem in current_assignments for _, score in current_assignments[sem])
        
        students_dict = {s.id: s for s in students}
        seminar_names = self.config.seminars
        
        temperature = self.initial_temperature
        
        for iteration in range(self.num_iterations): 
            improved_in_this_iter = False
            
            # 2-optスタイルの交換 (2つのランダムなセミナー間で学生を交換)
            # 各イテレーションで試行する交換回数を学生数に比例させる
            num_exchanges = max(1, len(students) // 10) 
            for _ in range(num_exchanges): 
                # 学生が割り当てられているセミナーのみを対象にする
                active_seminars = [sem for sem in seminar_names if current_assignments[sem]]
                if len(active_seminars) < 2: # 交換できるセミナーが2つ未満ならスキップ
                    continue

                sem1_name = random.choice(active_seminars)
                sem2_name = random.choice([s for s in active_seminars if s != sem1_name])

                if not current_assignments[sem1_name] or not current_assignments[sem2_name]:
                    continue
                
                student1_idx_in_sem1 = random.randrange(len(current_assignments[sem1_name]))
                student2_idx_in_sem2 = random.randrange(len(current_assignments[sem2_name]))

                student1_id, _ = current_assignments[sem1_name][student1_idx_in_sem1]
                student2_id, _ = current_assignments[sem2_name][student2_idx_in_sem2]
                
                student1_obj = students_dict[student1_id]
                student2_obj = students_dict[student2_id]
                
                # 交換後のスコアを計算
                # Student.calculate_score に preference_weights を渡す
                old_score1 = student1_obj.calculate_score(sem1_name, self.config.magnification, self.config.preference_weights)
                old_score2 = student2_obj.calculate_score(sem2_name, self.config.magnification, self.config.preference_weights)
                new_score1 = student1_obj.calculate_score(sem2_name, self.config.magnification, self.config.preference_weights)
                new_score2 = student2_obj.calculate_score(sem1_name, self.config.magnification, self.config.preference_weights) 
                
                score_diff = (new_score1 + new_score2) - (old_score1 + old_score2)
                
                # 焼きなまし法の受容基準
                if score_diff > 0.001 or (score_diff <= 0 and temperature > 0 and random.random() < np.exp(score_diff / temperature)):
                    # 割り当てを更新
                    current_assignments[sem1_name][student1_idx_in_sem1] = (student2_id, new_score2)
                    current_assignments[sem2_name][student2_idx_in_sem2] = (student1_id, new_score1)
                    current_score += score_diff
                    improved_in_this_iter = True
            
            # 学生の単一移動 (近傍探索)
            num_moves = max(1, len(students) // 20) 
            for _ in range(num_moves): 
                active_seminars = [sem for sem in seminar_names if current_assignments[sem]]
                if not active_seminars: continue

                seminar_from_name = random.choice(active_seminars)
                if not current_assignments[seminar_from_name]:
                    continue
                
                student_idx_in_from_sem = random.randrange(len(current_assignments[seminar_from_name]))
                student_id_to_move, old_score = current_assignments[seminar_from_name][student_idx_in_from_sem]
                student_to_move_obj = students_dict[student_id_to_move]
                
                # 移動先のセミナーをランダムに選択 (元のセミナー以外)
                seminar_to_name = random.choice([s for s in seminar_names if s != seminar_from_name])
                
                # 移動先のセミナーが最大定員を超過しないかチェック (厳密な制約ではないが、探索をガイド)
                if len(current_assignments[seminar_to_name]) >= self.config.max_size: 
                    continue

                # 移動後のスコアを計算
                # Student.calculate_score に preference_weights を渡す
                new_score = student_to_move_obj.calculate_score(seminar_to_name, self.config.magnification, self.config.preference_weights)
                score_diff_move = new_score - old_score
                
                # 焼きなまし法の受容基準
                if score_diff_move > 0.001 or (score_diff_move <= 0 and temperature > 0 and random.random() < np.exp(score_diff_move / temperature)):
                    current_assignments[seminar_from_name].pop(student_idx_in_from_sem)
                    current_assignments[seminar_to_name].append((student_id_to_move, new_score))
                    current_score += score_diff_move
                    improved_in_this_iter = True
            
            # 温度を冷却
            temperature *= self.cooling_rate 
            
            # 進捗コールバック
            if progress_callback and iteration % (self.num_iterations // 50 or 1) == 0:
                progress_callback(f"  局所探索中: {iteration+1}/{self.num_iterations} (スコア: {current_score:.2f}, 温度: {temperature:.4f})")
            
            # 改善がなければ早期終了 (ヒルクライミング的な要素)
            if not improved_in_this_iter and temperature < 0.001: # 温度が十分に下がってから
                if self.config.log_enabled:
                    logger.debug(f"Local search converged at iteration {iteration}.")
                break
        
        return current_score, current_assignments

def optimize_greedy_ls_single_assignment(config_dict: dict, students: list[Student], initial_assignments: dict[str, list[tuple[int, float]]], target_sizes: dict[str, int]) -> tuple[float, dict[str, list[tuple[int, float]]]]:
    """
    与えられた初期割り当てに対して局所探索（Simulated Annealing風）を実行し、改善されたスコアと割り当てを返します。
    これは、Greedy+LS戦略での並列実行に使用されます。
    """
    current_config = Config(**config_dict)
    local_optimizer = LocalSearchOptimizer(
        config_dict,
        num_iterations=current_config.local_search_iterations,
        initial_temperature=current_config.initial_temperature,
        cooling_rate=current_config.cooling_rate
    )
    
    improved_score, improved_assignments = local_optimizer.improve_assignment(
        students, initial_assignments, target_sizes, progress_callback=None # 並列処理なので進捗は表示しない
    )
    return improved_score, improved_assignments

