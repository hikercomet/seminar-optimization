import random
import csv
import os
import pandas as pd 
import numpy as np
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set
import heapq
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import logging
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.fonts import addMapping

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 設定クラス
@dataclass
class Config:
    seminars: List[str] = None
    magnification: Dict[str, float] = None
    min_size: int = 5
    max_size: int = 10
    num_students: int = 112
    num_patterns: int = 50000  # より効率的なアルゴリズムなので削減
    early_stop_threshold: float = 0.001
    no_improvement_limit: int = 1000
    output_dir: str = "results"
    pdf_file: str = None
    q_boost_probability: float = 0.2
    max_workers: int = 4  # 並列処理用
    
    def __post_init__(self):
        if self.seminars is None:
            self.seminars = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q']
        if self.magnification is None:
            self.magnification = {'a': 2.0, 'd': 3.0, 'm': 0.5, 'o': 0.25}
        if self.pdf_file is None:
            self.pdf_file = os.path.join(self.output_dir, "seminar_results_advanced.pdf")
        os.makedirs(self.output_dir, exist_ok=True)

# フォント設定
addMapping('Helvetica', 0, 0, 'Helvetica')
addMapping('Helvetica', 1, 1, 'Helvetica-Bold')

class Student:
    def __init__(self, student_id: int, preferences: List[str]):
        self.id = student_id
        self.preferences = preferences
        self.assigned_seminar = None
        self.satisfaction_score = 0.0
    
    def get_preference_rank(self, seminar: str) -> int:
        """セミナーに対する希望順位を返す (1位=0, 2位=1, 3位=2, その他=-1)"""
        try:
            return self.preferences.index(seminar)
        except ValueError:
            return -1
    
    def calculate_score(self, seminar: str, magnification: Dict[str, float]) -> float:
        """特定のセミナーに対するスコアを計算"""
        rank = self.get_preference_rank(seminar)
        if rank == 0:  # 第1希望
            base_score = 3.0
        elif rank == 1:  # 第2希望
            base_score = 2.0
        elif rank == 2:  # 第3希望
            base_score = 1.0
        else:  # 希望外
            base_score = 0.0
        
        return base_score * magnification.get(seminar, 1.0)

class Seminar:
    def __init__(self, name: str, target_size: int, min_size: int = 5, max_size: int = 10):
        self.name = name
        self.target_size = target_size
        self.min_size = min_size
        self.max_size = max_size
        self.assigned_students: List[Student] = []
        self.total_score = 0.0
    
    def can_accept_more(self) -> bool:
        return len(self.assigned_students) < self.target_size
    
    def is_overfull(self) -> bool:
        return len(self.assigned_students) > self.target_size
    
    def add_student(self, student: Student, score: float):
        self.assigned_students.append(student)
        student.assigned_seminar = self.name
        student.satisfaction_score = score
        self.total_score += score
    
    def remove_student(self, student: Student):
        if student in self.assigned_students:
            self.assigned_students.remove(student)
            self.total_score -= student.satisfaction_score
            student.assigned_seminar = None
            student.satisfaction_score = 0.0

class PreferenceGenerator:
    def __init__(self, config: Config):
        self.config = config
    
    def generate_realistic_preferences(self, seed: int) -> List[Student]:
        """よりリアルな希望分布を生成"""
        random.seed(seed)
        students = []
        
        # セミナーの人気度を設定
        popularity_weights = {sem: 1.0 for sem in self.config.seminars}
        popularity_weights.update({
            'a': 1.5,  # 人気
            'd': 1.8,  # 非常に人気
            'q': 1.2,  # やや人気
            'm': 0.7,  # やや不人気
            'o': 0.5  # 不人気
        })
        
        for student_id in range(1, self.config.num_students + 1):
            # 重み付き選択で第1希望を決定
            if random.random() < self.config.q_boost_probability:
                first_choice = 'q'
            else:
                seminars_list = list(self.config.seminars)
                weights = [popularity_weights[sem] for sem in seminars_list]
                first_choice = random.choices(seminars_list, weights=weights)[0]
            
            # 第2、第3希望を決定（相関を持たせる）
            remaining_seminars = [s for s in self.config.seminars if s != first_choice]
            
            # 第1希望に関連する傾向を持たせる
            second_weights = []
            for sem in remaining_seminars:
                base_weight = popularity_weights[sem]
                # 同じ系統のセミナーは選ばれやすくする簡易ロジック
                if abs(ord(first_choice) - ord(sem)) <= 2:
                    base_weight *= 1.3
                second_weights.append(base_weight)
            
            second_choice = random.choices(remaining_seminars, weights=second_weights)[0]
            
            final_remaining = [s for s in remaining_seminars if s != second_choice]
            third_choice = random.choice(final_remaining)
            
            preferences = [first_choice, second_choice, third_choice]
            students.append(Student(student_id, preferences))
        
        return students

class TargetSizeOptimizer:
    def __init__(self, config: Config):
        self.config = config
    
    def generate_balanced_sizes(self, students: List[Student], attempt: int = 0) -> Dict[str, int]:
        """学生の希望を考慮したバランスの取れた目標人数を生成"""
        # 各セミナーへの第1希望数をカウント
        first_choice_count = defaultdict(int)
        for student in students:
            first_choice_count[student.preferences[0]] += 1
        
        # 基本サイズを設定
        target_sizes = {sem: self.config.min_size for sem in self.config.seminars}
        remaining = self.config.num_students - sum(target_sizes.values())
        
        # 第1希望の分布に基づいて残りを配分
        if attempt % 3 == 0:  # 希望重視
            allocation_strategy = "demand_based"
        elif attempt % 3 == 1:  # バランス重視
            allocation_strategy = "balanced"
        else:  # ランダム要素追加
            allocation_strategy = "mixed"
        
        if allocation_strategy == "demand_based":
            # 第1希望が多いセミナーに優先配分
            sorted_seminars = sorted(self.config.seminars, 
                                     key=lambda x: first_choice_count[x], reverse=True)
        elif allocation_strategy == "balanced":
            #均等に配分を試みる
            sorted_seminars = self.config.seminars.copy()
            random.shuffle(sorted_seminars)
        else:  # mixed
            # ランダム要素を加えた配分
            sorted_seminars = self.config.seminars.copy()
            random.shuffle(sorted_seminars)
        
        # 残り人数を配分
        for _ in range(remaining):
            for sem in sorted_seminars:
                if target_sizes[sem] < self.config.max_size:
                    target_sizes[sem] += 1
                    break
            else:
                # すべて最大に達した場合
                sem = random.choice(self.config.seminars)
                target_sizes[sem] += 1
        
        # 最終調整
        total = sum(target_sizes.values())
        while total != self.config.num_students:
            if total < self.config.num_students:
                available_sems = [s for s in self.config.seminars 
                                 if target_sizes[s] < self.config.max_size * 1.2]  # 少し緩和
                if available_sems:
                    sem = random.choice(available_sems)
                    target_sizes[sem] += 1
                    total += 1
                else:
                    break
            else:
                reducible_sems = [s for s in self.config.seminars 
                                 if target_sizes[s] > self.config.min_size]
                if reducible_sems:
                    sem = random.choice(reducible_sems)
                    target_sizes[sem] -= 1
                    total -= 1
                else:
                    break
        
        return target_sizes

class HungarianMatcher:
    """改良されたハンガリアン法風のマッチング"""
    
    def __init__(self, config: Config):
        self.config = config
    
    def create_cost_matrix(self, students: List[Student], target_sizes: Dict[str, int]) -> np.ndarray:
        """学生-セミナー間のコスト行列を作成（負のスコア = コスト）"""
        matrix = np.zeros((len(students), len(self.config.seminars)))
        
        for i, student in enumerate(students):
            for j, seminar in enumerate(self.config.seminars):
                score = student.calculate_score(seminar, self.config.magnification)
                # より高いスコアほど低いコストにする
                matrix[i][j] = 100.0 - score  # 最大スコア想定での変換
        
        return matrix
    
    def solve_with_capacity_constraints(self, students: List[Student], 
                                        target_sizes: Dict[str, int]) -> Tuple[float, Dict[str, List[Tuple[int, float]]]]:
        """容量制約付きの最適割り当てを解く"""
        
        # 拡張された割り当て問題として解く
        assignments = {sem: [] for sem in self.config.seminars}
        unassigned_students = set(range(len(students)))
        
        # 各セミナーの容量まで繰り返し最良マッチを探す
        for iteration in range(self.config.num_students):
            if not unassigned_students:
                break
            
            best_match = None
            best_score = -float('inf')
            best_student_idx = None
            best_seminar = None
            
            # 全ての未割り当て学生と受け入れ可能なセミナーの組み合わせを評価
            for student_idx in unassigned_students:
                student = students[student_idx]
                for seminar in self.config.seminars:
                    if len(assignments[seminar]) < target_sizes[seminar]:
                        score = student.calculate_score(seminar, self.config.magnification)
                        
                        # 容量との兼ね合いも考慮したスコア調整
                        capacity_factor = 1.0
                        remaining_capacity = target_sizes[seminar] - len(assignments[seminar])
                        if remaining_capacity == 1:  # 最後の席
                            capacity_factor = 1.1  # 少し優遇
                        
                        adjusted_score = score * capacity_factor
                        
                        if adjusted_score > best_score:
                            best_score = adjusted_score
                            best_match = (student_idx, seminar, score)
                            best_student_idx = student_idx
                            best_seminar = seminar
            
            # 最良のマッチを確定
            if best_match:
                student_idx, seminar, score = best_match
                assignments[seminar].append((students[student_idx].id, score))
                unassigned_students.remove(student_idx)
            else:
                # 強制割り当て（容量制約を少し緩和）
                if unassigned_students:
                    student_idx = next(iter(unassigned_students))
                    student = students[student_idx]
                    
                    # 最も空いているセミナーに割り当て
                    available_seminars = [(sem, len(assignments[sem])) for sem in self.config.seminars]
                    available_seminars.sort(key=lambda x: x[1])
                    
                    seminar = available_seminars[0][0]
                    score = student.calculate_score(seminar, self.config.magnification)
                    assignments[seminar].append((student.id, score))
                    unassigned_students.remove(student_idx)
        
        # 総スコア計算
        total_score = sum(score for sem in assignments for _, score in assignments[sem])
        
        return total_score, assignments

class LocalSearchOptimizer:
    """局所探索による改善"""
    
    def __init__(self, config: Config):
        self.config = config
    
    def improve_assignment(self, students: List[Student], assignments: Dict[str, List[Tuple[int, float]]], 
                           target_sizes: Dict[str, int], max_iterations: int = 1000) -> Tuple[float, Dict[str, List[Tuple[int, float]]]]:
        """局所探索で割り当てを改善"""
        
        current_assignments = {sem: list(assignments[sem]) for sem in assignments}
        current_score = sum(score for sem in current_assignments for _, score in current_assignments[sem])
        
        students_dict = {s.id: s for s in students}
        improved = True
        iteration = 0
        
        while improved and iteration < max_iterations:
            improved = False
            iteration += 1
            
            # 2-opt風の改善: 2つの学生の割り当てを交換
            for sem1 in self.config.seminars:
                for sem2 in self.config.seminars:
                    if sem1 >= sem2 or not current_assignments[sem1] or not current_assignments[sem2]:
                        continue
                    
                    for i, (student1_id, _) in enumerate(current_assignments[sem1]):
                        for j, (student2_id, _) in enumerate(current_assignments[sem2]):
                            student1 = students_dict[student1_id]
                            student2 = students_dict[student2_id]
                            
                            # 交換後のスコアを計算
                            old_score1 = student1.calculate_score(sem1, self.config.magnification)
                            old_score2 = student2.calculate_score(sem2, self.config.magnification)
                            new_score1 = student1.calculate_score(sem2, self.config.magnification)
                            new_score2 = student2.calculate_score(sem1, self.config.magnification)
                            
                            score_diff = (new_score1 + new_score2) - (old_score1 + old_score2)
                            
                            if score_diff > 0.01:  # 改善があれば交換
                                current_assignments[sem1][i] = (student2_id, new_score2)
                                current_assignments[sem2][j] = (student1_id, new_score1)
                                current_score += score_diff
                                improved = True
        
        return current_score, current_assignments

class SeminarOptimizer:
    def __init__(self, config: Config):
        self.config = config
        self.preference_generator = PreferenceGenerator(config)
        self.target_optimizer = TargetSizeOptimizer(config)
        self.hungarian_matcher = HungarianMatcher(config)
        self.local_optimizer = LocalSearchOptimizer(config)
    
    def optimize_single_pattern(self, pattern_id: int) -> Tuple[float, Dict[str, List[Tuple[int, float]]], Dict[str, int]]:
        """単一パターンの最適化"""
        try:
            # 1. 希望データ生成
            students = self.preference_generator.generate_realistic_preferences(42 + pattern_id)
            
            # 2. 目標人数最適化
            target_sizes = self.target_optimizer.generate_balanced_sizes(students, pattern_id)
            
            # 3. ハンガリアン法風マッチング
            score, assignments = self.hungarian_matcher.solve_with_capacity_constraints(students, target_sizes)
            
            # 4. 局所探索で改善
            improved_score, improved_assignments = self.local_optimizer.improve_assignment(
                students, assignments, target_sizes, max_iterations=500
            )
            
            return improved_score, improved_assignments, target_sizes
            
        except Exception as e:
            logger.error(f"Pattern {pattern_id} optimization failed: {e}")
            return 0.0, {sem: [] for sem in self.config.seminars}, {}
    
    def optimize_parallel(self) -> Tuple[Dict[str, int], float, Dict[str, List[Tuple[int, float]]], int]:
        """並列最適化の実行"""
        best_score = 0
        best_pattern = None
        best_assignments = None
        best_pattern_id = 0
        
        score_history = []  # 途中経過スコア記録用

        logger.info(f"並列最適化開始: {self.config.num_patterns}パターンを{self.config.max_workers}プロセスで評価")
        start_time = time.time()
        
        with ProcessPoolExecutor(max_workers=self.config.max_workers) as executor:
            # タスクを投入
            future_to_pattern = {
                executor.submit(self.optimize_single_pattern, pattern_id): pattern_id 
                for pattern_id in range(self.config.num_patterns)
            }
            
            completed = 0
            for future in as_completed(future_to_pattern):
                pattern_id = future_to_pattern[future]
                completed += 1
                
                try:
                    score, assignments, target_sizes = future.result()
                    
                    if score > best_score:
                        best_score = score
                        best_pattern = target_sizes
                        best_assignments = assignments
                        best_pattern_id = pattern_id
                        elapsed = time.time() - start_time
                        logger.info(f"[新記録] パターン{pattern_id}: スコア {score:.2f} （経過時間: {elapsed:.1f}s）")
                        score_history.append((completed, pattern_id, score, elapsed))
                    
                    if completed % 1000 == 0: # ログ出力頻度を調整
                        elapsed = time.time() - start_time
                        logger.info(f"[途中経過] {completed}/{self.config.num_patterns} 完了 | "
                                     f"最高得点: {best_score:.2f} | 経過時間: {elapsed:.1f}s")
                        
                except Exception as e:
                    logger.error(f"Pattern {pattern_id} failed: {e}")
        
        elapsed_time = time.time() - start_time
        logger.info(f"最適化完了 (所要時間: {elapsed_time:.1f}s)")
        
        try:
            csv_path = os.path.join(self.config.output_dir, "score_progress.csv")
            df = pd.DataFrame(score_history, columns=["Completed", "PatternID", "Score", "ElapsedTime"])
            df.to_csv(csv_path, index=False)
            logger.info(f"途中経過スコア履歴を保存しました: {csv_path}")
        except Exception as e:
            logger.error(f"スコア履歴CSV保存エラー: {e}")
        
        return best_pattern, best_score, best_assignments, best_pattern_id

    def validate_assignment(self, assignments: Dict[str, List[Tuple[int, float]]], 
                            target_sizes: Dict[str, int]) -> bool:
        """割り当て結果の妥当性を検証"""
        total_assigned = sum(len(assignments[sem]) for sem in self.config.seminars)
        if total_assigned != self.config.num_students:
            logger.error(f"Total assigned students {total_assigned} != {self.config.num_students}")
            return False
        
        all_students = set()
        for sem in self.config.seminars:
            for student_id, _ in assignments[sem]:
                if student_id in all_students:
                    logger.error(f"Duplicate assignment for student {student_id}")
                    return False
                all_students.add(student_id)
        
        for sem in self.config.seminars:
            actual_size = len(assignments[sem])
            target_size = target_sizes[sem]
            if abs(actual_size - target_size) > 1:  # 1人までの誤差は許容
                logger.warning(f"Seminar {sem} has {actual_size} students, target was {target_size}")
        
        return True

    def generate_pdf_report(self, best_pattern: Dict[str, int], best_score: float, 
                            best_assignments: Dict[str, List[Tuple[int, float]]], pattern_id: int) -> bool:
        """高度なPDFレポート生成"""
        try:
            doc = SimpleDocTemplate(self.config.pdf_file, pagesize=letter)
            styles = getSampleStyleSheet()
            elements = []
            
            # タイトル
            elements.append(Paragraph("高精度セミナー割り当て最適化結果", styles['Title']))
            elements.append(Paragraph(f"パターンID: {pattern_id} | 総得点: {best_score:.2f}", styles['Heading2']))
            elements.append(Spacer(1, 12))
            
            # サマリー情報
            elements.append(Paragraph(f"総学生数: {self.config.num_students}人", styles['Normal']))
            elements.append(Paragraph(f"評価パターン数: {self.config.num_patterns}", styles['Normal']))
            elements.append(Paragraph(f"並列プロセス数: {self.config.max_workers}", styles['Normal']))
            elements.append(Spacer(1, 12))
            
            # 満足度統計
            satisfaction_stats = self._calculate_satisfaction_stats(best_assignments)
            elements.append(Paragraph("学生満足度統計:", styles['Heading2']))
            elements.append(Paragraph(f"第1希望達成: {satisfaction_stats['first']:.1f}%", styles['Normal']))
            elements.append(Paragraph(f"第2希望達成: {satisfaction_stats['second']:.1f}%", styles['Normal']))
            elements.append(Paragraph(f"第3希望達成: {satisfaction_stats['third']:.1f}%", styles['Normal']))
            elements.append(Paragraph(f"希望外: {satisfaction_stats['none']:.1f}%", styles['Normal']))
            elements.append(Spacer(1, 12))
            
            # セミナー別詳細テーブル
            table_data = [["セミナー", "目標", "実際", "総得点", "平均満足度", "第1希望数", "詳細"]]
            
            for sem in self.config.seminars:
                students_scores = best_assignments[sem]
                target_size = best_pattern[sem]
                actual_size = len(students_scores)
                total_score = sum(score for _, score in students_scores)
                avg_satisfaction = total_score / actual_size if actual_size > 0 else 0
                
                # 第1希望達成数をカウント（実装は簡略化）
                first_choice_count = sum(1 for _, score in students_scores if score >= 3.0)  # 簡易判定
                
                detail = ", ".join([f"S{s}({sc:.1f})" for s, sc in students_scores[:3]])
                if len(students_scores) > 3:
                    detail += f"... (他{len(students_scores)-3}人)"
                
                mag_indicator = f" ({self.config.magnification[sem]}x)" if sem in self.config.magnification else ""
                
                table_data.append([
                    sem.upper() + mag_indicator,
                    str(target_size),
                    str(actual_size),
                    f"{total_score:.1f}",
                    f"{avg_satisfaction:.2f}",
                    str(first_choice_count),
                    detail
                ])
            
            table = Table(table_data)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('GRID', (0, 0), (-1, -1), 1, colors.black),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
            ]))
            
            elements.append(table)
            elements.append(Spacer(1, 12))
            
            # アルゴリズム情報
            elements.append(Paragraph("使用アルゴリズム:", styles['Heading2']))
            elements.append(Paragraph("1. リアルな希望分布生成", styles['Normal']))
            elements.append(Paragraph("2. 容量制約付きハンガリアン法風マッチング", styles['Normal']))
            elements.append(Paragraph("3. 局所探索による改善", styles['Normal']))
            elements.append(Paragraph("4. 並列処理による高速化", styles['Normal']))
            
            doc.build(elements)
            logger.info(f"高度なPDFレポートを生成: {self.config.pdf_file}")
            return True
            
        except Exception as e:
            logger.error(f"PDF生成エラー: {e}")
            return False
    
    def _calculate_satisfaction_stats(self, assignments: Dict[str, List[Tuple[int, float]]]) -> Dict[str, float]:
        """満足度統計を計算"""
        # 簡略化された実装 - 実際にはより詳細な分析が必要
        total_students = sum(len(assignments[sem]) for sem in assignments)
        
        # スコアベースでの大まかな分類
        first_choice = sum(1 for sem in assignments for _, score in assignments[sem] if score >= 3.0)
        second_choice = sum(1 for sem in assignments for _, score in assignments[sem] if 2.0 <= score < 3.0)
        third_choice = sum(1 for sem in assignments for _, score in assignments[sem] if 1.0 <= score < 2.0)
        none_choice = total_students - first_choice - second_choice - third_choice
        
        return {
            'first': (first_choice / total_students) * 100,
            'second': (second_choice / total_students) * 100,
            'third': (third_choice / total_students) * 100,
            'none': (none_choice / total_students) * 100
        }
    
    def save_csv_results(self, assignments: Dict[str, List[Tuple[int, float]]]) -> bool:
        """CSV結果保存"""
        csv_file = os.path.join(self.config.output_dir, "best_assignment_advanced.csv")
        try:
            with open(csv_file, "w", newline="", encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Seminar", "Student_ID", "Score", "Rank"])
                
                for sem in self.config.seminars:
                    for student_id, score in assignments[sem]:
                        # スコアから希望順位を推定
                        if score >= 3.0:
                            rank = "1st"
                        elif score >= 2.0:
                            rank = "2nd"  
                        elif score >= 1.0:
                            rank = "3rd"
                        else:
                            rank = "None"
                        writer.writerow([sem, student_id, f"{score:.2f}", rank])
            
            logger.info(f"CSV結果を保存: {csv_file}")
            return True
        except Exception as e:
            logger.error(f"CSV保存エラー: {e}")
            return False
    
    def run_optimization(self) -> Tuple[Dict[str, int], float, Dict[str, List[Tuple[int, float]]]]:
        """メイン最適化実行"""
        try:
            logger.info("=== 高精度セミナー割り当て最適化開始 ===")
            
            # 並列最適化実行
            best_pattern, best_score, best_assignments, best_pattern_id = self.optimize_parallel()
            
            # 結果検証
            if not self.validate_assignment(best_assignments, best_pattern):
                logger.error("割り当て結果が妥当でないため、処理を終了します。")
                return {}, 0.0, {}
            
            # PDFレポート生成
            self.generate_pdf_report(best_pattern, best_score, best_assignments, best_pattern_id)
            
            # CSV保存
            self.save_csv_results(best_assignments)
            
            logger.info("=== 最適化処理完了 ===")
            return best_pattern, best_score, best_assignments
        
        except Exception as e:
            logger.error(f"最適化実行中にエラーが発生: {e}")
            return {}, 0.0, {}

# メイン実行部分
if __name__ == "__main__":
    config = Config()
    optimizer = SeminarOptimizer(config)
    pattern, score, assignments = optimizer.run_optimization()
    
    if pattern:
        logger.info("最適化結果を表示します。")
        for sem in config.seminars:
            assigned_students = assignments[sem]
            logger.info(f"セミナー {sem.upper()}: 目標 {pattern[sem]}人 / 実際 {len(assigned_students)}人")
    else:
        logger.error("最適化に失敗しました。")