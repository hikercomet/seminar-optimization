import logging
from typing import List, Dict, Any, Tuple

from models import Config, Student # ConfigとStudentモデルをインポート

logger = logging.getLogger(__name__)

def calculate_satisfaction_stats(config: Config, students: List[Student], final_assignments: Dict[str, List[Tuple[int, float]]]) -> Dict[str, int]:
    """
    学生の満足度統計を計算します。
    割り当てられた学生の希望順位ごとの人数、希望外、未割り当てをカウントします。
    """
    satisfaction_counts = {
        "1st_choice": 0,
        "2nd_choice": 0,
        "3rd_choice": 0,
        "other_preference": 0, # 3位以降の希望
        "no_preference_met": 0, # 希望が全く叶わなかった（希望リストにないセミナーに割り当て）
        "unassigned": 0 # 未割り当て
    }
    
    # 割り当てを学生IDからセミナー名へのマップに変換
    student_to_seminar_map = {}
    for sem_name, assigned_list in final_assignments.items():
        for student_id, _ in assigned_list:
            student_to_seminar_map[student_id] = sem_name

    # 全ての学生をループして満足度を評価
    for student in students:
        assigned_seminar = student_to_seminar_map.get(student.id)

        if assigned_seminar is None:
            # 未割り当ての学生
            satisfaction_counts["unassigned"] += 1
        else:
            # 割り当てられた学生の希望順位をチェック
            rank = -1 # 希望リストにない場合は-1
            try:
                rank = student.preferences.index(assigned_seminar) # 0-indexed
            except ValueError:
                pass # 希望リストにない場合

            if rank == 0:
                satisfaction_counts["1st_choice"] += 1
            elif rank == 1:
                satisfaction_counts["2nd_choice"] += 1
            elif rank == 2:
                satisfaction_counts["3rd_choice"] += 1
            elif rank != -1: # 3位以降の希望が叶った場合
                satisfaction_counts["other_preference"] += 1
            else: # 希望リストになく、かつ割り当てられた場合
                satisfaction_counts["no_preference_met"] += 1
            
    return satisfaction_counts

def validate_assignment(config: Config, final_assignments: Dict[str, List[Tuple[int, float]]], target_sizes: Dict[str, int]) -> bool:
    """
    最終割り当ての妥当性を検証します。
    - 全ての学生が割り当てられているか (Config.num_students と比較)
    - 各セミナーの定員が守られているか (min_size, max_size)
    """
    is_valid = True
    
    # 1. 全ての学生が割り当てられているか
    assigned_student_ids = set()
    for sem_name, assigned_list in final_assignments.items():
        for student_id, _ in assigned_list:
            assigned_student_ids.add(student_id)
    
    total_assigned_students = len(assigned_student_ids)
    if total_assigned_students != config.num_students:
        logger.error(f"検証エラー: 割り当てられた学生数 ({total_assigned_students}) が総学生数 ({config.num_students}) と一致しません。")
        is_valid = False

    # 2. 各セミナーの定員が守られているか
    for sem_name in config.seminars:
        current_count = len(final_assignments.get(sem_name, []))
        target_size = target_sizes.get(sem_name, 0) # 目標定員が設定されていない場合は0とする
        
        # 最小定員チェック (警告レベル)
        if current_count < config.min_size:
            logger.warning(f"検証警告: セミナー {sem_name} の割り当て数 ({current_count}) が最小定員 ({config.min_size}) を下回っています。")
            # この警告は is_valid を False にしない（問題の性質による）
        
        # 最大定員チェック (エラーレベル)
        if current_count > config.max_size:
            logger.error(f"検証エラー: セミナー {sem_name} の割り当て数 ({current_count}) が最大定員 ({config.max_size}) を超過しています。")
            is_valid = False
        
        # 目標定員との乖離もログに出力（エラーではないが、最適化の質を示す）
        if current_count != target_size:
            logger.info(f"セミナー {sem_name}: 目標定員 {target_size}, 実際の割り当て {current_count} (差異: {current_count - target_size})")

    return is_valid

