import random
import concurrent.futures
import time
import json
import logging
from typing import Dict, List, Tuple, Any, Callable, Optional
from dataclasses import dataclass, asdict, field
from datetime import datetime
import os
import math # mathモジュールを追加

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class Student:
    """学生の情報を保持するデータクラス"""
    id: int
    preferences: List[str] # 希望セミナーのリスト (例: ['a', 'b', 'c'])

@dataclass
class Config:
    """最適化設定を保持するデータクラス"""
    seminars: List[str] = field(default_factory=list)
    magnification: Dict[str, float] = field(default_factory=dict)
    min_size: int = 5
    max_size: int = 10
    num_students: int = 0 # 学生総数はPreferenceGeneratorで設定される
    q_boost_probability: float = 0.2
    num_patterns: int = 200000 # Greedy_LSの試行回数、GA_LSの世代数
    max_workers: int = 8
    local_search_iterations: int = 500
    initial_temperature: float = 1.0
    cooling_rate: float = 0.995
    preference_weights: Dict[str, float] = field(default_factory=lambda: {"1st": 5.0, "2nd": 2.0, "3rd": 1.0})
    optimization_strategy: str = "Greedy_LS" # "Greedy_LS", "GA_LS", "ILP", "CP", "Multilevel"
    ga_population_size: int = 100
    ga_crossover_rate: float = 0.8
    ga_mutation_rate: float = 0.05
    ilp_time_limit: int = 300 # seconds
    cp_time_limit: int = 300 # seconds
    multilevel_clusters: int = 5

class SeminarOptimizer:
    """
    セミナー割当最適化のメインクラス。
    複数の最適化戦略をサポートし、進捗をGUIに報告します。
    """
    def __init__(self, config: Config, students: List[Student], progress_callback: Optional[Callable[[str], None]] = None):
        self.config = config
        self.students = students
        self.student_preferences_map = {s.id: s.preferences for s in students}
        self.progress_callback = progress_callback
        self.seminar_names = config.seminars
        self.min_size = config.min_size
        self.max_size = config.max_size
        self.magnification = config.magnification
        self.preference_weights = config.preference_weights
        self.num_students = len(self.students)

        # TargetSizeOptimizer はここでインスタンス化
        from utils import TargetSizeOptimizer
        self.target_size_optimizer = TargetSizeOptimizer(asdict(self.config))

    def _report_progress(self, message: str):
        """進捗をGUIに報告するヘルパー関数"""
        if self.progress_callback:
            self.progress_callback(message)
            logger.info(f"Progress: {message}")

    def _initial_assignment_greedy(self, target_sizes: Dict[str, int]) -> Dict[str, List[int]]:
        """
        学生を貪欲法で初期割り当てします。
        各学生の第一希望を優先し、定員に空きがある限り割り当てます。
        """
        assignments: Dict[str, List[int]] = {sem: [] for sem in self.seminar_names}
        
        # 学生をランダムな順序で処理
        shuffled_students = list(self.students)
        random.shuffle(shuffled_students)

        # 第一希望の割り当て
        for student in shuffled_students:
            for pref_sem in student.preferences:
                if pref_sem in self.seminar_names and len(assignments[pref_sem]) < target_sizes[pref_sem]:
                    assignments[pref_sem].append(student.id)
                    break # 割り当てられたら次の学生へ

        # 未割り当ての学生を処理
        unassigned_students = [
            s.id for s in shuffled_students
            if s.id not in [sid for sublist in assignments.values() for sid in sublist]
        ]
        
        # 未割り当ての学生を空きのあるセミナーにランダムに割り当てる
        for student_id in unassigned_students:
            # まだ定員に空きがあるセミナーをランダムに選択
            available_seminars = [
                sem for sem in self.seminar_names
                if len(assignments[sem]) < target_sizes[sem]
            ]
            if available_seminars:
                chosen_sem = random.choice(available_seminars)
                assignments[chosen_sem].append(student_id)
            else:
                # 全てのセミナーが定員に達している場合、最小定員を無視して割り当てる
                # これは非常に稀なケースだが、全ての学生を割り当てるために必要
                chosen_sem = random.choice(self.seminar_names)
                assignments[chosen_sem].append(student_id)
                logger.warning(f"Student {student_id} assigned to {chosen_sem} even though it's full. This should be rare.")

        return assignments

    def _calculate_assignment_score(self, assignments: Dict[str, List[int]]) -> float:
        """
        割り当て結果のスコアを計算します。
        utils.calculate_score を使用します。
        """
        from utils import calculate_score
        # student_preferences_map は {student_id: [pref1, pref2, ...]} の形式
        # calculate_score は {seminar_name: [(student_id, score_contrib), ...]} の形式を期待する
        # ここでは student_id のリストなので、ダミーのスコア貢献度0.0で渡す
        formatted_assignments = {sem: [(sid, 0.0) for sid in sids] for sem, sids in assignments.items()}
        return calculate_score(formatted_assignments, self.student_preferences_map, self.preference_weights)

    def _perform_local_search(self, initial_assignments: Dict[str, List[int]], target_sizes: Dict[str, int]) -> Dict[str, List[int]]:
        """
        与えられた初期割り当てに対して焼きなまし法による局所探索を行います。
        """
        current_assignments = initial_assignments
        current_score = self._calculate_assignment_score(current_assignments)
        best_assignments = current_assignments
        best_score = current_score

        T = self.config.initial_temperature
        cooling_rate = self.config.cooling_rate
        
        # 割り当てを学生IDからセミナー名へのマップに変換
        student_to_seminar: Dict[int, str] = {}
        for sem, sids in current_assignments.items():
            for sid in sids:
                student_to_seminar[sid] = sem

        for i in range(self.config.local_search_iterations):
            # 新しい状態を生成 (近傍探索)
            # 1. ランダムな学生を選び、別のセミナーに移動させる
            # 2. 2人の学生を選び、セミナーを交換する
            
            new_student_to_seminar = student_to_seminar.copy()
            
            move_type = random.choice(["move", "swap"])

            if move_type == "move":
                student_id = random.choice(list(self.student_preferences_map.keys()))
                current_sem = new_student_to_seminar[student_id]
                
                # 移動先のセミナー候補 (現在のセミナー以外)
                possible_target_seminars = [s for s in self.seminar_names if s != current_sem]
                if not possible_target_seminars:
                    continue # 移動できない場合はスキップ

                target_sem = random.choice(possible_target_seminars)
                
                new_student_to_seminar[student_id] = target_sem

            elif move_type == "swap":
                if len(self.students) < 2: # 学生が2人未満なら交換できない
                    continue
                
                student1_id, student2_id = random.sample(list(self.student_preferences_map.keys()), 2)
                sem1 = new_student_to_seminar[student1_id]
                sem2 = new_student_to_seminar[student2_id]

                if sem1 == sem2: # 同じセミナーにいる場合は交換しても意味がない
                    continue

                new_student_to_seminar[student1_id] = sem2
                new_student_to_seminar[student2_id] = sem1

            # 新しい割り当て辞書を構築
            new_assignments: Dict[str, List[int]] = {sem: [] for sem in self.seminar_names}
            for sid, sem in new_student_to_seminar.items():
                new_assignments[sem].append(sid)

            # 定員制約の確認 (ソフト制約としてスコアに反映させることも可能)
            # ここではハード制約として、定員超過の場合はペナルティを課すか、無効な状態とする
            is_valid_assignment = True
            for sem, sids in new_assignments.items():
                if len(sids) > target_sizes[sem]:
                    is_valid_assignment = False
                    break
            
            if not is_valid_assignment:
                # 無効な割り当ては受け入れない
                continue

            new_score = self._calculate_assignment_score(new_assignments)

            # 焼きなまし法の判定
            if new_score > current_score:
                current_assignments = new_assignments
                current_score = new_score
            else:
                # 悪い解でも一定確率で受け入れる
                delta_score = new_score - current_score
                if T > 0 and random.random() < math.exp(delta_score / T):
                    current_assignments = new_assignments
                    current_score = new_score
            
            # ベストスコアの更新
            if current_score > best_score:
                best_assignments = current_assignments
                best_score = current_score
            
            # 温度の冷却
            T *= cooling_rate
        
        return best_assignments

    def _run_greedy_local_search(self) -> Tuple[Dict[str, int], float, Dict[str, List[Tuple[int, float]]]]:
        """
        貪欲法と局所探索を組み合わせた最適化を実行します。
        """
        overall_best_score = -1.0
        overall_best_pattern_sizes: Dict[str, int] = {}
        overall_final_assignments: Dict[str, List[Tuple[int, float]]] = {}

        self._report_progress("目標定員パターンの生成と最適化を開始します...")

        for i in range(self.config.num_patterns):
            if i % 100 == 0:
                self._report_progress(f"試行 {i+1}/{self.config.num_patterns} を実行中...")

            # 1. 目標定員パターンを生成
            # generate_balanced_sizes は {seminar_name: size} のDictを返す
            target_sizes = self.target_size_optimizer.generate_balanced_sizes(self.students, seed=random.randint(0, 100000))
            
            # 2. 初期割り当て (貪欲法)
            initial_assignments = self._initial_assignment_greedy(target_sizes)
            
            # 3. 局所探索 (焼きなまし法)
            optimized_assignments = self._perform_local_search(initial_assignments, target_sizes)
            
            # 4. スコア計算
            current_score = self._calculate_assignment_score(optimized_assignments)
            
            # 5. 最良のパターンを更新
            if current_score > overall_best_score:
                overall_best_score = current_score
                overall_best_pattern_sizes = target_sizes
                
                # final_assignments の形式に変換 (学生IDとスコア貢献度)
                overall_final_assignments = {
                    sem: [(sid, self._get_student_score_contribution(sid, sem)) for sid in sids]
                    for sem, sids in optimized_assignments.items()
                }
                logger.info(f"New best score found: {overall_best_score:.2f} with pattern: {target_sizes}")
        
        self._report_progress("最適化が完了しました。")
        return overall_best_pattern_sizes, overall_best_score, overall_final_assignments

    def _get_student_score_contribution(self, student_id: int, assigned_seminar: str) -> float:
        """
        特定の学生が割り当てられたセミナーから得るスコア貢献度を計算します。
        """
        prefs = self.student_preferences_map.get(student_id, [])
        weights = self.preference_weights
        
        try:
            rank = prefs.index(assigned_seminar.lower()) + 1 # 0-indexed to 1-indexed
            if rank == 1:
                return weights.get("1st", 5.0)
            elif rank == 2:
                return weights.get("2nd", 2.0)
            elif rank == 3:
                return weights.get("3rd", 1.0)
            else:
                return 0.0 # 3位以下の希望はスコア貢献なし
        except ValueError:
            return 0.0 # 希望リストにないセミナーに割り当てられた場合

    def _run_genetic_algorithm_local_search(self) -> Tuple[Dict[str, int], float, Dict[str, List[Tuple[int, float]]]]:
        """
        遺伝的アルゴリズムと局所探索を組み合わせた最適化を実行します。
        各個体はセミナーの目標定員パターンと、そのパターンに対する割り当て解を表します。
        """
        population_size = self.config.ga_population_size
        num_generations = self.config.num_patterns # num_patternsを世代数として使用
        crossover_rate = self.config.ga_crossover_rate
        mutation_rate = self.config.ga_mutation_rate

        self._report_progress("遺伝的アルゴリズムの初期個体群を生成中...")

        # 個体群の初期化: 各個体は (target_sizes, assignments, score) のタプル
        population: List[Tuple[Dict[str, int], Dict[str, List[int]], float]] = []
        for _ in range(population_size):
            target_sizes = self.target_size_optimizer.generate_balanced_sizes(self.students)
            initial_assignments = self._initial_assignment_greedy(target_sizes)
            # GAの各個体生成時にも局所探索を適用
            optimized_assignments = self._perform_local_search(initial_assignments, target_sizes)
            score = self._calculate_assignment_score(optimized_assignments)
            population.append((target_sizes, optimized_assignments, score))
        
        overall_best_score = max(p[2] for p in population)
        overall_best_individual = next(p for p in population if p[2] == overall_best_score)
        
        self._report_progress(f"GA開始時のベストスコア: {overall_best_score:.2f}")

        for generation in range(num_generations):
            self._report_progress(f"GA世代 {generation+1}/{num_generations} を実行中...")

            # 選択 (ルーレット選択など)
            # スコアが負にならないように調整
            min_score = min(p[2] for p in population)
            adjusted_scores = [p[2] - min_score + 1 for p in population] # 全て正の値にする
            total_adjusted_score = sum(adjusted_scores)
            
            if total_adjusted_score == 0: # 全てのスコアが同じで0の場合
                selection_probabilities = [1.0 / population_size] * population_size
            else:
                selection_probabilities = [s / total_adjusted_score for s in adjusted_scores]

            # 新しい個体群の準備
            new_population: List[Tuple[Dict[str, int], Dict[str, List[int]], float]] = []

            # エリート選択 (最も良い個体を次世代に引き継ぐ)
            best_current_individual = max(population, key=lambda x: x[2])
            new_population.append(best_current_individual)

            while len(new_population) < population_size:
                # 親の選択
                parent1_idx = random.choices(range(population_size), weights=selection_probabilities, k=1)[0]
                parent2_idx = random.choices(range(population_size), weights=selection_probabilities, k=1)[0]
                
                parent1_target_sizes = population[parent1_idx][0]
                parent2_target_sizes = population[parent2_idx][0]

                child_target_sizes = parent1_target_sizes # デフォルトは親1
                
                # 交叉
                if random.random() < crossover_rate:
                    child_target_sizes = self._crossover_target_sizes(parent1_target_sizes, parent2_target_sizes)
                
                # 突然変異
                if random.random() < mutation_rate:
                    child_target_sizes = self._mutate_target_sizes(child_target_sizes)
                
                # 新しい目標定員で割り当てと局所探索
                child_initial_assignments = self._initial_assignment_greedy(child_target_sizes)
                child_optimized_assignments = self._perform_local_search(child_initial_assignments, child_target_sizes)
                child_score = self._calculate_assignment_score(child_optimized_assignments)
                
                new_population.append((child_target_sizes, child_optimized_assignments, child_score))
            
            population = new_population

            # 全体ベストの更新
            current_generation_best_score = max(p[2] for p in population)
            if current_generation_best_score > overall_best_score:
                overall_best_score = current_generation_best_score
                overall_best_individual = max(population, key=lambda x: x[2])
                logger.info(f"Generation {generation+1}: New best score found: {overall_best_score:.2f}")

        self._report_progress("遺伝的アルゴリズム最適化が完了しました。")
        
        # 最終結果の整形
        best_target_sizes = overall_best_individual[0]
        best_assignments_raw = overall_best_individual[1] # student_idのリスト
        final_assignments_formatted = {
            sem: [(sid, self._get_student_score_contribution(sid, sem)) for sid in sids]
            for sem, sids in best_assignments_raw.items()
        }

        return best_target_sizes, overall_best_score, final_assignments_formatted

    def _crossover_target_sizes(self, parent1: Dict[str, int], parent2: Dict[str, int]) -> Dict[str, int]:
        """
        目標定員パターンに対する交叉操作。
        各セミナーの定員をランダムに親から引き継ぐ。
        """
        child = {}
        for sem in self.seminar_names:
            if random.random() < 0.5:
                child[sem] = parent1.get(sem, self.config.min_size)
            else:
                child[sem] = parent2.get(sem, self.config.min_size)
        
        # 合計学生数を維持するように調整 (簡略化のため、ここでは単純な合計調整)
        current_total = sum(child.values())
        diff = self.num_students - current_total
        
        # 調整はランダムなセミナーに対して行う
        adjustable_seminars = list(self.seminar_names)
        random.shuffle(adjustable_seminars)

        for sem in adjustable_seminars:
            if diff == 0:
                break
            if diff > 0: # 足りない場合
                if child[sem] < self.config.max_size:
                    child[sem] += 1
                    diff -= 1
            else: # 多い場合
                if child[sem] > self.config.min_size:
                    child[sem] -= 1
                    diff += 1
        
        # 最終的に合計が合わない場合、ランダムに調整を試みる (厳密な制約は難しい)
        while diff != 0:
            sem = random.choice(self.seminar_names)
            if diff > 0:
                if child[sem] < self.config.max_size:
                    child[sem] += 1
                    diff -= 1
            else:
                if child[sem] > self.config.min_size:
                    child[sem] -= 1
                    diff += 1

        return child

    def _mutate_target_sizes(self, target_sizes: Dict[str, int]) -> Dict[str, int]:
        """
        目標定員パターンに対する突然変異操作。
        ランダムなセミナーの定員を増減させる。
        """
        mutated_sizes = target_sizes.copy()
        
        # ランダムなセミナーを2つ選び、一方を増やし、もう一方を減らす
        if len(self.seminar_names) < 2:
            return mutated_sizes # セミナーが少ない場合は変異できない

        sem1, sem2 = random.sample(self.seminar_names, 2)

        # sem1を増やし、sem2を減らす (定員制約内で)
        if mutated_sizes[sem1] < self.config.max_size and mutated_sizes[sem2] > self.config.min_size:
            mutated_sizes[sem1] += 1
            mutated_sizes[sem2] -= 1
        elif mutated_sizes[sem2] < self.config.max_size and mutated_sizes[sem1] > self.config.min_size:
            # 逆の操作
            mutated_sizes[sem2] += 1
            mutated_sizes[sem1] -= 1
        
        return mutated_sizes

    def _run_ilp_optimization(self) -> Tuple[Dict[str, int], float, Dict[str, List[Tuple[int, float]]]]:
        """
        整数線形計画法 (ILP) を用いた最適化を実行します。
        (実装は別途必要)
        """
        self._report_progress("整数線形計画法 (ILP) を実行中... (開発中)")
        # ここにILPソルバーの呼び出しロジックを実装
        # 例: pulp, ortools などを使用
        time.sleep(2) # シミュレーション
        self._report_progress("ILP最適化は現在開発中です。")
        return {}, -1.0, {} # ダミーの戻り値

    def _run_cp_optimization(self) -> Tuple[Dict[str, int], float, Dict[str, List[Tuple[int, float]]]]:
        """
        制約プログラミング (CP-SAT) を用いた最適化を実行します。
        (実装は別途必要)
        """
        self._report_progress("制約プログラミング (CP-SAT) を実行中... (開発中)")
        # ここにCP-SATソルバーの呼び出しロジックを実装
        # 例: ortools を使用
        time.sleep(2) # シミュレーション
        self._report_progress("CP-SAT最適化は現在開発中です。")
        return {}, -1.0, {} # ダミーの戻り値

    def _run_multilevel_optimization(self) -> Tuple[Dict[str, int], float, Dict[str, List[Tuple[int, float]]]]:
        """
        多段階最適化を実行します。
        (実装は別途必要)
        """
        self._report_progress("多段階最適化を実行中... (開発中)")
        # ここに多段階最適化のロジックを実装
        time.sleep(2) # シミュレーション
        self._report_progress("多段階最適化は現在開発中です。")
        return {}, -1.0, {} # ダミーの戻り値

    def run_optimization(self) -> Tuple[Dict[str, int], float, Dict[str, List[Tuple[int, float]]]]:
        """
        選択された最適化戦略に基づいて最適化を実行します。
        """
        start_time = time.time()
        
        # どの最適化戦略が実行されるかを進捗報告に表示
        self._report_progress(f"最適化戦略 '{self.config.optimization_strategy}' を開始します。")

        best_pattern_sizes: Dict[str, int] = {}
        overall_best_score: float = -1.0
        final_assignments: Dict[str, List[Tuple[int, float]]] = {}

        if self.config.optimization_strategy == "Greedy_LS":
            best_pattern_sizes, overall_best_score, final_assignments = self._run_greedy_local_search()
        elif self.config.optimization_strategy == "GA_LS":
            best_pattern_sizes, overall_best_score, final_assignments = self._run_genetic_algorithm_local_search()
        elif self.config.optimization_strategy == "ILP":
            best_pattern_sizes, overall_best_score, final_assignments = self._run_ilp_optimization()
        elif self.config.optimization_strategy == "CP":
            best_pattern_sizes, overall_best_score, final_assignments = self._run_cp_optimization()
        elif self.config.optimization_strategy == "Multilevel":
            best_pattern_sizes, overall_best_score, final_assignments = self._run_multilevel_optimization()
        else:
            self._report_progress(f"不明な最適化戦略: {self.config.optimization_strategy}")
            logger.error(f"Unknown optimization strategy: {self.config.optimization_strategy}")

        end_time = time.time()
        elapsed_time = end_time - start_time
        self._report_progress(f"最適化処理が完了しました。所要時間: {elapsed_time:.2f}秒")
        logger.info(f"Optimization finished in {elapsed_time:.2f} seconds.")

        # 結果を保存
        from utils import save_results
        save_results(best_pattern_sizes, overall_best_score, final_assignments, self.config, True, False) # log_enabled, save_intermediate は仮

        return best_pattern_sizes, overall_best_score, final_assignments

if __name__ == "__main__":
    # この部分はGUIから呼び出されるため、直接実行されることは少ない
    # デバッグ用に簡単なテストケースを記述
    from utils import PreferenceGenerator, setup_logging

    setup_logging(log_enabled=True)

    # デフォルト設定
    default_seminars = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't']
    default_magnification = {'a': 2.0, 'b': 1.5, 'q': 3.0}
    default_preference_weights = {"1st": 5.0, "2nd": 2.0, "3rd": 1.0}

    # Configオブジェクトの作成
    config = Config(
        seminars=default_seminars,
        magnification=default_magnification,
        min_size=5,
        max_size=10,
        num_students=112, # この値はPreferenceGeneratorによって上書きされる
        q_boost_probability=0.2,
        num_patterns=1000, # テスト用に少なく設定
        max_workers=4,
        local_search_iterations=100, # テスト用に少なく設定
        initial_temperature=1.0,
        cooling_rate=0.995,
        preference_weights=default_preference_weights,
        optimization_strategy="Greedy_LS", # テスト戦略
        ga_population_size=50,
        ga_crossover_rate=0.8,
        ga_mutation_rate=0.05
    )

    # 学生の希望を自動生成
    pref_gen = PreferenceGenerator(asdict(config))
    students = pref_gen.generate_realistic_preferences(seed=42)
    config.num_students = len(students) # 実際の学生数でConfigを更新

    # 最適化の実行
    optimizer = SeminarOptimizer(config, students)
    best_sizes, best_score, final_assigns = optimizer.run_optimization()

    print("\n--- 最適化結果 ---")
    print(f"最終ベストスコア: {best_score:.2f}")
    print(f"最適目標定員パターン: {best_sizes}")
    # print("最終割り当て:", final_assigns) # 量が多いのでコメントアウト
