import random
import math
import logging
import threading
import time # timeモジュールをインポート
from typing import List, Tuple, Dict, Any, Optional, Callable

# BaseOptimizerとOptimizationResultをutilsからインポート
# プロジェクトの構造に合わせてパスを修正
from seminar_optimization.utils import BaseOptimizer, OptimizationResult
# ロギングは logger_config.py で一元的に設定されるため、ここではロガーの取得のみ
from seminar_optimization.logger_config import logger

class SeminarProblem:
    """
    セミナー割り当て問題を定義するクラス。
    セミナーデータと学生データを基に、初期割り当ての生成、割り当ての評価、制約チェックを行う。
    """
    def __init__(self, seminars_data: List[Dict[str, Any]], students_data: List[Dict[str, Any]], config: Dict[str, Any]):
        self.seminars = {s['id']: s for s in seminars_data}
        self.students = {st['id']: st for st in students_data}
        self.seminar_ids = list(self.seminars.keys())
        self.student_ids = list(self.students.keys())
        self.config = config # スコア重みなどの設定を保持
        logger.debug(f"SeminarProblem初期化: セミナー数={len(self.seminars)}, 学生数={len(self.students)}")

        # スコア重みを設定から取得
        self.score_weights = self.config.get("score_weights", {
            "1st_choice": 5.0,
            "2nd_choice": 2.0,
            "3rd_choice": 1.0,
            "other_preference": 0.5
        })
        logger.debug(f"SeminarProblem: スコア重み: {self.score_weights}")

    def evaluate(self, assignment: Dict[str, str]) -> float:
        """
        与えられた割り当てのフィットネス（コスト）を評価する。
        フィットネスは最小化されるべき値（低いほど良い）。
        ここでは、BaseOptimizerのスコア（高いほど良い）の負の値を返す。
        """
        if not self._is_feasible_assignment(assignment):
            # 制約違反の割り当てには非常に大きなペナルティを与える
            return float('inf') 

        total_score = 0.0
        for student_id, assigned_seminar_id in assignment.items():
            student_prefs = self.students.get(student_id, {}).get('preferences', [])
            
            # 希望順位に基づいたスコア加算
            try:
                rank = student_prefs.index(assigned_seminar_id) + 1
                if rank == 1:
                    total_score += self.score_weights.get("1st_choice", 5.0)
                elif rank == 2:
                    total_score += self.score_weights.get("2nd_choice", 2.0)
                elif rank == 3:
                    total_score += self.score_weights.get("3rd_choice", 1.0)
                else:
                    total_score += self.score_weights.get("other_preference", 0.5)
            except ValueError:
                # 希望リストにないセミナーに割り当てられた場合
                total_score += self.score_weights.get("other_preference", 0.5) # あるいは0点など、ペナルティを課す

        # 未割り当て学生に対するペナルティ（フィットネスを増加させる）
        assigned_students = set(assignment.keys())
        unassigned_students_count = len(self.student_ids) - len(assigned_students)
        total_score -= unassigned_students_count * 100.0 # 未割り当ては大きなペナルティ

        # TSLは最小化問題として設計されているため、スコアの負の値を返す
        return -total_score

    def get_initial_random_assignment(self) -> Dict[str, str]:
        """
        ランダムな初期割り当てを生成する。
        各学生をランダムなセミナーに割り当てるが、定員制約は考慮しない（後で修正が必要になる可能性あり）。
        """
        assignment = {}
        # セミナーIDが空の場合のハンドリング
        if not self.seminar_ids:
            logger.warning("SeminarProblem: セミナーIDが定義されていません。初期割り当てを生成できません。")
            return {}

        for student_id in self.student_ids:
            assignment[student_id] = random.choice(self.seminar_ids)
        logger.debug(f"SeminarProblem: ランダムな初期割り当てを生成しました。学生数: {len(assignment)}")
        return assignment

    def _is_feasible_assignment(self, assignment: Dict[str, str]) -> bool:
        """
        現在の割り当てが制約を満たしているかチェックする。
        ここでは、セミナーの最大定員制約をチェックする。
        """
        seminar_counts = {s_id: 0 for s_id in self.seminar_ids}
        for student_id, seminar_id in assignment.items():
            if seminar_id not in self.seminar_ids:
                logger.warning(f"SeminarProblem: 無効なセミナーID '{seminar_id}' が割り当てに含まれています。")
                return False # 存在しないセミナーへの割り当ては無効
            seminar_counts[seminar_id] += 1

        for seminar_id, count in seminar_counts.items():
            capacity = self.seminars.get(seminar_id, {}).get('capacity', float('inf')) # 定義されていない場合は無限大
            if count > capacity:
                logger.warning(f"SeminarProblem: 制約違反: セミナー '{seminar_id}' の定員 ({capacity}) を超えています ({count}人割り当て)。")
                return False
        logger.debug("SeminarProblem: すべての定員制約を満たしています。割り当ては実行可能です。")
        return True

    def get_seminar_capacities(self) -> Dict[str, int]:
        """セミナーIDとその定員を辞書で返す。"""
        return {s_id: self.seminars[s_id]['capacity'] for s_id in self.seminar_ids}

# 各学生は自身の割り当てと個人的な最良割り当てを持ち、教師や他の学生から学習します。
class Student:
    """
    学習アルゴリズムにおける生徒の基底クラス。
    全ての生徒タイプに共通の機能を提供します。
    """
    def __init__(self, problem: SeminarProblem, student_id_alias: str):
        self.problem = problem
        self.id = student_id_alias # アルゴリズム内で使用する生徒のエイリアス（例: 探索型_1）
        self.current_assignment = self.problem.get_initial_random_assignment()
        self.current_fitness = self.problem.evaluate(self.current_assignment)
        self.personal_best_assignment = dict(self.current_assignment) # 個人的な最良割り当て
        self.personal_best_fitness = self.current_fitness # 個人的な最良フィットネス
        logger.debug(f"Student {self.id} 初期化: 初期フィットネス={self.current_fitness:.2f}")

    def _update_personal_best(self):
        """
        現在の割り当てが個人的な最良割り当てよりも良い場合（フィットネスが低い場合）、更新します。
        """
        if self.current_fitness < self.personal_best_fitness:
            self.personal_best_assignment = dict(self.current_assignment)
            self.personal_best_fitness = self.current_fitness
            logger.debug(f"Student {self.id}: 個人最良フィットネスを更新: {self.personal_best_fitness:.2f}")

    def learn(self, global_best_assignment: Dict[str, str], iteration: int, total_iterations: int, phase: str, teacher_memory: List[Dict[str, Any]] = None):
        """
        学習ロジック（各生徒タイプでオーバーライドされます）。
        global_best_assignment: 教師が持つ現在の全体最良割り当て。
        iteration: 現在の反復回数。
        total_iterations: 総反復回数。
        phase: 現在の学習フェーズ ('Preparation', 'Execution', 'Review')。
        teacher_memory: 教師のメモリ（過去の優良割り当てリスト）。
        """
        raise NotImplementedError("このメソッドは各生徒タイプで実装する必要があります。")

    def _perturb_assignment(self, assignment: Dict[str, str], perturbation_strength: float) -> Dict[str, str]:
        """
        割り当てを微調整（摂動）するヘルパーメソッド。
        離散的な割り当てに対して、ランダムな学生のセミナーを変更するなどの操作を行います。
        perturbation_strength: 摂動の強さ (0.0から1.0)
        """
        new_assignment = dict(assignment)
        student_ids = list(new_assignment.keys())
        
        if not student_ids:
            return new_assignment # 学生がいない場合は何もしない

        num_students_to_perturb = max(1, int(len(student_ids) * perturbation_strength))
        
        # 摂動する学生をランダムに選択
        students_to_perturb = random.sample(student_ids, min(num_students_to_perturb, len(student_ids)))
        
        available_seminars = self.problem.seminar_ids
        if not available_seminars:
            logger.warning("Student: 利用可能なセミナーがありません。摂動できません。")
            return new_assignment # セミナーがない場合は何もしない

        for s_id in students_to_perturb:
            # ランダムなセミナーに再割り当て
            new_assignment[s_id] = random.choice(available_seminars)
        
        # TODO: ここに学生の希望やセミナー定員などの制約を考慮した、よりインテリジェントな摂動ロジックを追加する
        # 例: 優先度の高いセミナーが空いていればそちらに移動、定員オーバーを解消するなど
        logger.debug(f"Student {self.id}: 割り当てを摂動しました。摂動強度: {perturbation_strength:.2f}")
        return new_assignment

class ExploratoryStudent(Student):
    """
    探索型の生徒。広範囲を探索し、局所最適解に陥るのを防ぎます。
    """
    def learn(self, global_best_assignment: Dict[str, str], iteration: int, total_iterations: int, phase: str, teacher_memory: List[Dict[str, Any]] = None):
        # 探索ステップのサイズは、反復が進むにつれて減少します。
        step_factor = 1.0 - (iteration / total_iterations) # 1.0 -> 0.0
        current_perturb_strength = 0.3 * step_factor + 0.05 # 最小5%は摂動

        if random.random() < 0.7:
            # 高い確率で自身の現在地から大きくランダムジャンプ
            self.current_assignment = self._perturb_assignment(self.current_assignment, current_perturb_strength)
            logger.debug(f"ExploratoryStudent {self.id}: 大規模な探索を行いました。")
        else:
            # グローバル最良割り当ての方向へ少し移動しつつ、探索も行う
            # ここでは「方向へ移動」を、グローバル最良割り当ての一部をコピーし、残りを摂動する、と解釈
            temp_assignment = dict(global_best_assignment)
            # グローバル最良割り当ての80%を維持し、20%をランダムに摂動するイメージ
            self.current_assignment = self._perturb_assignment(temp_assignment, 0.2) 
            logger.debug(f"ExploratoryStudent {self.id}: グローバル最良解の方向へ摂動しました。")
            
        self.current_fitness = self.problem.evaluate(self.current_assignment)
        self._update_personal_best()

class LocalStudent(Student):
    """
    局所型の生徒。現在の最良割り当ての周辺を重点的に探索し、改善を目指します。
    """
    def learn(self, global_best_assignment: Dict[str, str], iteration: int, total_iterations: int, phase: str, teacher_memory: List[Dict[str, Any]] = None):
        # ステップサイズは、反復が進むにつれてグローバル最良割り当てへの集中度が高まります。
        step_factor = iteration / total_iterations # 0.0 -> 1.0
        current_perturb_strength = 0.1 * (1 - step_factor) + 0.01 # 全体的な摂動サイズは減少、最小1%

        target_assignment = global_best_assignment if random.random() < 0.8 else self.personal_best_assignment
        self.current_assignment = self._perturb_assignment(target_assignment, current_perturb_strength)
        logger.debug(f"LocalStudent {self.id}: 局所探索を行いました。")
        
        self.current_fitness = self.problem.evaluate(self.current_assignment)
        self._update_personal_best()

class BalancedStudent(Student):
    """
    バランス型の生徒。探索と活用のバランスを取りながら学習します。
    """
    def learn(self, global_best_assignment: Dict[str, str], iteration: int, total_iterations: int, phase: str, teacher_memory: List[Dict[str, Any]] = None):
        # 探索と活用の重みは、反復とフェーズに応じて適応的に変化します。
        exploration_weight = 0.5 * (1 - iteration / total_iterations) # 時間とともに減少
        exploitation_weight = 0.5 * (iteration / total_iterations) # 時間とともに増加
        base_perturb_strength = 0.05

        new_assignment = dict(self.current_assignment)
        student_ids = list(new_assignment.keys())
        
        if not student_ids:
            return # 学生がいない場合は何もしない

        # 個人最良解、全体最良解、ランダム探索の影響を合成
        for s_id in student_ids:
            if random.random() < exploitation_weight:
                # 活用フェーズ：個人最良解または全体最良解から学生の割り当てをコピー
                if random.random() < 0.5:
                    new_assignment[s_id] = self.personal_best_assignment.get(s_id, new_assignment[s_id])
                else:
                    new_assignment[s_id] = global_best_assignment.get(s_id, new_assignment[s_id])
            elif random.random() < exploration_weight:
                # 探索フェーズ：ランダムなセミナーに割り当て
                available_seminars = self.problem.seminar_ids
                if available_seminars:
                    new_assignment[s_id] = random.choice(available_seminars)
        
        # 最後に全体的な微摂動を適用して多様性を確保
        self.current_assignment = self._perturb_assignment(new_assignment, base_perturb_strength)
        logger.debug(f"BalancedStudent {self.id}: 探索と活用のバランスを取りながら学習しました。")

        self.current_fitness = self.problem.evaluate(self.current_assignment)
        self._update_personal_best()

# --- 3. 教師クラス (Teacher Class) ---
# 教師は生徒たちの学習を監督し、全体的な最良割り当てと過去の優良割り当てを管理します。
class Teacher:
    """
    生徒の学習を監督し、全体最良割り当てと過去の優良割り当て（メモリ）を管理するクラス。
    """
    def __init__(self, problem: SeminarProblem):
        self.problem = problem
        self.global_best_assignment: Optional[Dict[str, str]] = None # 全体最良割り当て
        self.global_best_fitness: float = float('inf') # 全体最良フィットネス (低いほど良い)
        self.memory: List[Dict[str, Any]] = [] # 過去の優良割り当てを保存するメモリ
        logger.debug("Teacher: 初期化を開始しました。")

    def update_global_best(self, students: List[Student]):
        """
        現在の生徒たちの個人的最良割り当てから、全体最良割り当てを更新します。
        フィットネスが低いほど良い解とみなします。
        """
        updated = False
        for student in students:
            if student.personal_best_fitness < self.global_best_fitness:
                self.global_best_fitness = student.personal_best_fitness
                self.global_best_assignment = dict(student.personal_best_assignment)
                updated = True
        
        # 現在の全体最良割り当てもメモリに追加します。
        if updated and self.global_best_assignment and self.global_best_fitness != float('inf'):
            self.add_to_memory(self.global_best_assignment, self.global_best_fitness)
            logger.debug(f"Teacher: 全体最良フィットネスを更新: {self.global_best_fitness:.2f}")

    def add_to_memory(self, assignment: Dict[str, str], fitness: float, max_memory_size: int = 10):
        """
        優良割り当てをメモリに追加し、フィットネスでソートして、最大サイズを維持します。
        """
        # 同じ解が既にメモリにある場合は追加しない
        # ここではシンプルに、同じフィットネス値の割り当ては追加しない
        # より厳密な重複チェックが必要な場合は、割り当て内容も比較する
        if not any(m['fitness'] == fitness for m in self.memory):
            self.memory.append({'assignment': dict(assignment), 'fitness': fitness})
            self.memory.sort(key=lambda x: x['fitness']) # フィットネスが小さい順にソート
            self.memory = self.memory[:max_memory_size] # メモリサイズを制限
            logger.debug(f"Teacher: メモリに割り当てを追加しました。現在のメモリサイズ: {len(self.memory)}")

    def get_best_from_memory(self) -> Optional[Dict[str, str]]:
        """
        メモリから最も良い割り当てを返します。
        """
        if self.memory:
            logger.debug(f"Teacher: メモリから最良割り当てを取得しました (フィットネス: {self.memory[0]['fitness']:.2f})")
            return self.memory[0]['assignment']
        logger.debug("Teacher: メモリが空です。")
        return None

# --- 4. TSLOptimizer クラス (BaseOptimizerを継承) ---
class TSLOptimizer(BaseOptimizer):
    """
    教師・生徒学習アルゴリズムをセミナー割り当て問題に適用するオプティマイザ。
    """
    def __init__(self,
                 seminars: List[Dict[str, Any]],
                 students: List[Dict[str, Any]],
                 config: Dict[str, Any],
                 progress_callback: Optional[Callable[[str], None]] = None):
        super().__init__(seminars, students, config, progress_callback)
        logger.debug("TSLOptimizer: 初期化を開始します。")

        self.problem = SeminarProblem(seminars, students, config) # SeminarProblemを初期化
        self.teacher = Teacher(self.problem)
        self.students: List[Student] = []

        # 生徒の数を設定から取得、またはデフォルト値を設定
        num_exploratory = config.get("tsl_num_exploratory_students", 10)
        num_local = config.get("tsl_num_local_students", 10)
        num_balanced = config.get("tsl_num_balanced_students", 10)

        for i in range(num_exploratory):
            self.students.append(ExploratoryStudent(self.problem, f"探索型_{i+1}"))
        for i in range(num_local):
            self.students.append(LocalStudent(self.problem, f"局所型_{i+1}"))
        for i in range(num_balanced):
            self.students.append(BalancedStudent(self.problem, f"バランス型_{i+1}"))
        random.shuffle(self.students) # 生徒の順序をランダム化
        logger.debug(f"TSLOptimizer: {len(self.students)}人の生徒を生成しました。")

        # 全体最良割り当てを初期化します（最初の生徒の割り当てから）。
        if self.students:
            initial_student = random.choice(self.students)
            self.teacher.global_best_assignment = dict(initial_student.current_assignment)
            self.teacher.global_best_fitness = initial_student.current_fitness
            self.teacher.add_to_memory(self.teacher.global_best_assignment, self.teacher.global_best_fitness)
            logger.info(f"TSLOptimizer: 初期全体最良フィットネス: {self.teacher.global_best_fitness:.2f}")
        else:
            logger.warning("TSLOptimizer: 生徒がいないため、全体最良割り当てを初期化できません。")

    def optimize(self, cancel_event: Optional[threading.Event] = None) -> OptimizationResult:
        """
        教師・生徒学習アルゴリズムを実行し、最適なセミナー割り当てを見つけます。
        """
        max_iterations = self.config.get("tsl_max_iterations", 100)
        time_limit = self.config.get("tsl_time_limit", None) # configから時間制限を取得
        start_time = time.time()

        history = [] # 各反復での最良フィットネスを記録

        # フェーズの割合を定義
        preparation_ratio = self.config.get("tsl_preparation_ratio", 0.2)
        execution_ratio = self.config.get("tsl_execution_ratio", 0.6)
        review_ratio = self.config.get("tsl_review_ratio", 0.2) 

        prep_iterations = int(max_iterations * preparation_ratio)
        exec_iterations = int(max_iterations * execution_ratio)
        review_iterations = max_iterations - prep_iterations - exec_iterations

        self._log(f"--- TSL アルゴリズム開始 ---", level=logging.INFO)
        self._log(f"総反復回数: {max_iterations}", level=logging.INFO)
        self._log(f"予習フェーズ: {prep_iterations} 反復", level=logging.INFO)
        self._log(f"本番フェーズ: {exec_iterations} 反復", level=logging.INFO)
        self._log(f"復習フェーズ: {review_iterations} 反復", level=logging.INFO)
        self._log("-" * 30, level=logging.INFO)

        for i in range(max_iterations):
            if cancel_event and cancel_event.is_set():
                self._log("TSLOptimizer: 最適化がユーザーによってキャンセルされました。", level=logging.INFO)
                return OptimizationResult(
                    status="CANCELLED",
                    message="最適化がユーザーによってキャンセルされました。",
                    best_score=-float('inf'), # キャンセルされた場合はスコアを無効にする
                    best_assignment={},
                    seminar_capacities=self.problem.get_seminar_capacities(),
                    unassigned_students=self.student_ids,
                    optimization_strategy="TSL"
                )
            
            if time_limit and (time.time() - start_time > time_limit):
                self._log(f"TSLOptimizer: 時間制限 ({time_limit}秒) に達しました。", level=logging.INFO)
                break

            current_phase = ""
            if i < prep_iterations:
                current_phase = "Preparation" # 予習
            elif i < prep_iterations + exec_iterations:
                current_phase = "Execution" # 本番
            else:
                current_phase = "Review" # 復習

            # 教師は現在の生徒のパフォーマンスに基づいて全体最良割り当てを更新します。
            self.teacher.update_global_best(self.students)

            # 生徒は全体最良割り当て（および場合によっては教師のメモリ）から学習します。
            for student in self.students:
                learning_target = self.teacher.global_best_assignment
                
                # 復習フェーズでは、生徒は低い確率で教師のメモリから学習することもあります。
                if current_phase == "Review" and random.random() < self.config.get("tsl_memory_learn_prob", 0.1): # 10%の確率
                    mem_best = self.teacher.get_best_from_memory()
                    if mem_best:
                        learning_target = mem_best # メモリの最良解を学習ターゲットにする
                
                if learning_target: # learning_targetがNoneでないことを確認
                    student.learn(learning_target, i, max_iterations, current_phase, self.teacher.memory)
                else:
                    # 初期化に失敗した場合のフォールバック (ありえないはずだが安全のため)
                    student.learn(student.current_assignment, i, max_iterations, current_phase, self.teacher.memory)

            # 進捗を記録します。
            history.append({
                'iteration': i + 1,
                'phase': current_phase,
                'global_best_fitness': self.teacher.global_best_fitness
            })

            if (i + 1) % 10 == 0 or i == 0 or i == max_iterations - 1:
                self._log(f"反復 {i+1} ({current_phase}): 最良フィットネス = {self.teacher.global_best_fitness:.4f}", level=logging.INFO)
            
            # 進捗コールバックを呼び出す
            if self.progress_callback:
                self.progress_callback(f"TSL最適化: フェーズ '{current_phase}', 反復 {i+1}/{max_iterations}, 最良フィットネス: {self.teacher.global_best_fitness:.2f}")


        self._log("-" * 30, level=logging.INFO)
        self._log(f"--- TSL アルゴリズム終了 ---", level=logging.INFO)
        self._log(f"最終最良フィットネス: {self.teacher.global_best_fitness:.4f}", level=logging.INFO)

        final_assignments = self.teacher.global_best_assignment if self.teacher.global_best_assignment else {}
        
        # BaseOptimizerのスコア計算メソッドで最終スコアを再計算 (高いほど良い)
        final_score = self._calculate_score(final_assignments) 

        # 未割り当て学生のリストを取得
        unassigned_students = self._get_unassigned_students(final_assignments)

        # OptimizationResult オブジェクトを返す
        return OptimizationResult(
            status="OPTIMAL" if final_score > -float('inf') else "NO_SOLUTION_FOUND",
            message="TSL最適化が成功しました。" if final_score > -float('inf') else "TSL最適化で有効な解が見つかりませんでした。",
            best_score=final_score,
            best_assignment=final_assignments,
            seminar_capacities=self.problem.get_seminar_capacities(),
            unassigned_students=unassigned_students,
            optimization_strategy="TSL"
        )

    # BaseOptimizerの _calculate_score をSeminarProblemから利用できるようにする
    # あるいは、SeminarProblem.evaluate の中で直接呼び出す
    def _calculate_score(self, assignments: Dict[str, str]) -> float:
        """
        BaseOptimizerの_calculate_scoreをオーバーライドまたはラップして、
        SeminarProblem.evaluateから呼び出せるようにします。
        """
        # ここで親クラス (BaseOptimizer) の _calculate_score を呼び出す
        # BaseOptimizerのscoreが高いほど良いので、TSLのfitnessと逆にする必要はない
        # SeminarProblem.evaluateが負の値を返すため、そのままBaseOptimizerのスコア計算を使用
        return super()._calculate_score(assignments)
