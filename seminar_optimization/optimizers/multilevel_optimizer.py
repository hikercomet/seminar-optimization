import random
import logging
from collections import defaultdict
from typing import Dict, List, Tuple, Callable, Optional

# 外部モジュールからのインポート
from models import Config, Student
from optimizers.greedy_ls_optimizer import LocalSearchOptimizer # LocalSearchOptimizerをインポート

logger = logging.getLogger(__name__)

class MultilevelOptimizer:
    """
    多段階最適化 (Multilevel Optimization) を用いてセミナー割り当てを最適化するクラスです。
    このアプローチでは、複数のフェーズを経て解を洗練させます。
    フェーズ1: 階層的な初期割り当て (学生の希望順位を考慮)
    フェーズ2: 全体的な局所探索による洗練
    """
    def __init__(self, config_dict: dict, students: list[Student], target_sizes: dict[str, int]):
        self.config = Config(**config_dict)
        self.students = students
        self.target_sizes = target_sizes
        self.students_dict = {s.id: s for s in students}
        self.seminar_names = self.config.seminars

        self.local_search_optimizer = LocalSearchOptimizer(
            config_dict,
            num_iterations=self.config.multilevel_refinement_iterations, # Multilevel専用の反復回数
            initial_temperature=self.config.initial_temperature,
            cooling_rate=self.config.cooling_rate
        )

    def _hierarchical_initial_assignment(self, students: list[Student], target_sizes: dict[str, int]) -> tuple[float, dict[str, list[tuple[int, float]]]]:
        """
        学生の希望順位を考慮した階層的な初期割り当てを行います。
        1. 第1希望のセミナーに優先的に割り当てる。
        2. 第1希望が叶わなかった学生を第2希望のセミナーに割り当てる。
        3. 第2希望が叶わなかった学生を第3希望のセミナーに割り当てる。
        4. それでも割り当てられなかった学生を、空きのあるセミナーにランダムに割り当てる。
        """
        current_assignments = {sem: [] for sem in self.seminar_names}
        seminar_current_counts = defaultdict(int)
        
        # 学生をランダムな順序で処理
        shuffled_students = list(students)
        random.shuffle(shuffled_students)

        total_score = 0.0
        
        # 希望順位ごとに学生を処理
        # 0: 1st choice, 1: 2nd choice, 2: 3rd choice, -1: others
        for rank_priority in range(self.config.num_preferences_to_consider): # 0, 1, 2
            students_for_this_rank = [s for s in shuffled_students if s.assigned_seminar is None] # まだ割り当てられていない学生
            
            for student in students_for_this_rank:
                preferred_seminar_at_rank = None
                if len(student.preferences) > rank_priority:
                    preferred_seminar_at_rank = student.preferences[rank_priority]
                
                if preferred_seminar_at_rank and preferred_seminar_at_rank in self.seminar_names:
                    # 目標定員内であれば割り当て
                    if seminar_current_counts[preferred_seminar_at_rank] < target_sizes[preferred_seminar_at_rank]:
                        score = student.calculate_score(preferred_seminar_at_rank, self.config.magnification, self.config.preference_weights)
                        current_assignments[preferred_seminar_at_rank].append((student.id, score))
                        seminar_current_counts[preferred_seminar_at_rank] += 1
                        total_score += score
                        student.assigned_seminar = preferred_seminar_at_rank # 学生オブジェクトに割り当てを記録
        
        # 残りの学生を最大定員内で割り当てる
        unassigned_students = [s for s in shuffled_students if s.assigned_seminar is None]
        for student in unassigned_students:
            found_slot = False
            # 空きのあるセミナーをランダムに試す
            available_seminars = [sem for sem in self.seminar_names if seminar_current_counts[sem] < self.config.max_size]
            random.shuffle(available_seminars)

            for sem in available_seminars:
                score = student.calculate_score(sem, self.config.magnification, self.config.preference_weights)
                current_assignments[sem].append((student.id, score))
                seminar_current_counts[sem] += 1
                total_score += score
                student.assigned_seminar = sem
                found_slot = True
                break
            
            if not found_slot:
                logger.warning(f"Student {student.id} could not be assigned to any seminar in hierarchical assignment (max capacity reached).")
        
        # 最終チェックとして、全ての学生が割り当てられているか確認
        # もし割り当てられていない学生が残っていたら、強制的に割り当てる（定員無視の可能性あり）
        final_unassigned_students = [s for s in shuffled_students if s.assigned_seminar is None]
        for student in final_unassigned_students:
            # 最も空きがあるセミナーに割り当てる
            sorted_seminars_by_capacity = sorted(self.seminar_names, key=lambda sem: seminar_current_counts[sem])
            assigned_to_any = False
            for sem in sorted_seminars_by_capacity:
                if seminar_current_counts[sem] < self.config.max_size: # 最大定員まで許容
                    score = student.calculate_score(sem, self.config.magnification, self.config.preference_weights)
                    current_assignments[sem].append((student.id, score))
                    seminar_current_counts[sem] += 1
                    total_score += score
                    student.assigned_seminar = sem
                    assigned_to_any = True
                    break
            if not assigned_to_any:
                # 最終手段：どこかのセミナーに割り当てる（定員超過を許容）
                chosen_sem = random.choice(self.seminar_names)
                score = student.calculate_score(chosen_sem, self.config.magnification, self.config.preference_weights)
                current_assignments[chosen_sem].append((student.id, score))
                seminar_current_counts[chosen_sem] += 1
                total_score += score
                student.assigned_seminar = chosen_sem
                logger.warning(f"Student {student.id} forced into {chosen_sem} (may exceed max capacity).")

        return total_score, current_assignments

    def run_multilevel(self, progress_callback: Callable[[str], None]) -> tuple[float, dict[str, list[tuple[int, float]]]]:
        """
        多段階最適化のメインループを実行します。
        """
        logger.info("多段階最適化を開始します。")
        progress_callback("多段階最適化: フェーズ1 (初期割り当て) 開始...")

        best_score = 0.0
        best_assignments = None

        # フェーズ1: 複数の階層的初期割り当てを生成し、最も良いものを選択
        for i in range(self.config.multilevel_initial_greedy_runs):
            if progress_callback:
                progress_callback(f"  初期割り当てパターン生成中: {i+1}/{self.config.multilevel_initial_greedy_runs}")
            
            # 各学生オブジェクトのassigned_seminarをリセットして再利用
            for s in self.students:
                s.assigned_seminar = None

            current_score, current_assignments = self._hierarchical_initial_assignment(self.students, self.target_sizes)
            
            if current_score > best_score:
                best_score = current_score
                best_assignments = current_assignments
                logger.info(f"[Multilevel Phase 1 New Best] パターン {i+1}: スコア {best_score:.2f}")
        
        if best_assignments is None:
            logger.error("多段階最適化: 初期割り当てで有効な結果が得られませんでした。")
            progress_callback("エラー: 多段階最適化の初期割り当てに失敗しました。")
            return 0.0, {sem: [] for sem in self.seminar_names}

        progress_callback("多段階最適化: フェーズ2 (局所探索による洗練) 開始...")
        # フェーズ2: 最も良い初期割り当てに対して局所探索を適用
        final_score, final_assignments = self.local_search_optimizer.improve_assignment(
            self.students, best_assignments, self.target_sizes, progress_callback=progress_callback
        )

        logger.info(f"多段階最適化が完了しました。最終スコア: {final_score:.2f}")
        progress_callback("多段階最適化が完了しました。")
        return final_score, final_assignments

