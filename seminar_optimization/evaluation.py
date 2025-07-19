import logging
from collections import defaultdict
from typing import Dict, List, Tuple # Optionalは使わないので削除

# 外部モジュールからのインポート
from models import Config, Student
from utils import PreferenceGenerator 

logger = logging.getLogger(__name__)

def validate_assignment(config: Config, assignments: dict[str, list[tuple[int, float]]], # 修正: dict, list, tupleを使用
                        target_sizes: dict[str, int]) -> bool: # 修正: dictを使用
    """割当結果を検証します"""
    total_assigned = sum(len(assignments[sem]) for sem in config.seminars)
    if total_assigned != config.num_students:
        logger.error(f"Total assigned students {total_assigned} does not match total students {config.num_students}.")
        return False
    
    all_students = set()
    for sem in config.seminars:
        for student_id, _ in assignments[sem]:
            if student_id in all_students:
                logger.error(f"Student {student_id} is assigned to multiple seminars.")
                return False
            all_students.add(student_id)
    
    for sem in config.seminars:
        actual_size = len(assignments[sem])
        target_size = target_sizes[sem]
        if not (target_size - 1 <= actual_size <= target_size + 1):
            logger.warning(f"Actual size {actual_size} for Seminar {sem} significantly deviates from target size {target_size}. This might indicate capacity adjustments for optimal score due to the nature of greedy assignment and local search.")
    
    return True

def calculate_satisfaction_stats(config: Config, assignments: dict[str, list[tuple[int, float]]], pattern_id: int) -> dict[str, float]: # 修正: dict, list, tupleを使用
    """満足度統計を計算します"""
    total_students = config.num_students
    first_pref_count = 0
    second_pref_count = 0
    third_pref_count = 0
    not_preferred_count = 0

    temp_pref_gen = PreferenceGenerator(config.__dict__) 
    students_for_stats = temp_pref_gen.generate_realistic_preferences(42 + pattern_id)
    students_dict_for_stats = {s.id: s for s in students_for_stats}

    for sem_name, assigned_students in assignments.items():
        for student_id, _ in assigned_students:
            student_obj = students_dict_for_stats.get(student_id)
            if student_obj:
                rank = student_obj.get_preference_rank(sem_name)
                if rank == 0:
                    first_pref_count += 1
                elif rank == 1:
                    second_pref_count += 1
                elif rank == 2:
                    third_pref_count += 1
                else:
                    not_preferred_count += 1
            else:
                logger.warning(f"Student ID {student_id} not found when calculating satisfaction stats. This indicates a potential data mismatch.")
                not_preferred_count += 1

    stats = {
        'first': (first_pref_count / total_students) * 100 if total_students > 0 else 0,
        'second': (second_pref_count / total_students) * 100 if total_students > 0 else 0,
        'third': (third_pref_count / total_students) * 100 if total_students > 0 else 0,
        'none': (not_preferred_count / total_students) * 100 if total_students > 0 else 0,
    }
    return stats
