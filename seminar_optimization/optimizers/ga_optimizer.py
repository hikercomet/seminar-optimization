# seminar_optimization/optimizers/ga_optimizer.py

import random
import json
from typing import List, Dict, Any, Tuple

class GAOptimizer:
    """
    遺伝的アルゴリズム（GA）を用いてセミナー割り当て問題を最適化するクラス。
    """

    def __init__(self,
                 seminars: List[Dict[str, Any]],
                 students: List[Dict[str, Any]],
                 config: Dict[str, Any]):
        """
        GAOptimizerのコンストラクタ。

        Args:
            seminars (List[Dict[str, Any]]): セミナーのリスト。各セミナーはID、定員などを含む辞書。
            students (List[Dict[str, Any]]): 学生のリスト。各学生はID、希望セミナーなどを含む辞書。
            config (Dict[str, Any]): GAのパラメータ（個体数、世代数、交叉率、突然変異率など）を含む設定辞書。
        """
        self.seminars = seminars
        self.students = students
        self.config = config

        # GAパラメータの読み込み
        self.population_size = config.get("population_size", 100)
        self.generations = config.get("generations", 500)
        self.crossover_rate = config.get("crossover_rate", 0.8)
        self.mutation_rate = config.get("mutation_rate", 0.01)

        # その他の初期化（必要に応じて追加）
        self.seminar_capacities = {s['id']: s['capacity'] for s in seminars}
        self.student_preferences = {s['id']: s['preferences'] for s in students}
        self.student_ids = [s['id'] for s in students]
        self.seminar_ids = [s['id'] for s in seminars]


    def _initialize_population(self) -> List[List[str]]:
        """
        初期個体群を生成する。
        各個体は学生ごとの割り当てセミナーIDのリストで表現される。
        例: ['seminar_A', 'seminar_B', 'seminar_A', ...] (学生1, 学生2, 学生3, ... の順)
        定員制約を満たすように初期化を工夫することも可能だが、
        まずはランダムに割り当てるシンプルな方法から始める。
        """
        population = []
        for _ in range(self.population_size):
            individual = []
            for student_id in self.student_ids:
                # 各学生をランダムなセミナーに割り当てる
                # 後で定員制約を考慮した初期化を検討することも可能
                assigned_seminar = random.choice(self.seminar_ids)
                individual.append(assigned_seminar)
            population.append(individual)
        return population

    def _evaluate_fitness(self, individual: List[str]) -> Tuple[float, Dict[str, int]]:
        """
        個体の適合度を評価する。
        適合度は、学生の希望との合致度と、セミナー定員超過のペナルティに基づいて計算される。
        適合度が高いほど良い割り当てとする。

        Args:
            individual (List[str]): 学生ごとの割り当てセミナーIDのリスト。

        Returns:
            Tuple[float, Dict[str, int]]:
                - 適合度スコア (float)
                - 各セミナーの現在の割り当て人数 (Dict[str, int])
        """
        score = 0.0
        seminar_counts = {seminar_id: 0 for seminar_id in self.seminar_ids}

        # 学生の希望との合致度を計算
        for i, student_id in enumerate(self.student_ids):
            assigned_seminar = individual[i]
            preferences = self.student_preferences.get(student_id, [])

            # 希望順位に応じたスコア加算
            if assigned_seminar == preferences[0]:
                score += 10.0  # 第1希望
            elif len(preferences) > 1 and assigned_seminar == preferences[1]:
                score += 5.0   # 第2希望
            elif len(preferences) > 2 and assigned_seminar == preferences[2]:
                score += 2.0   # 第3希望
            # 希望にない場合はスコア加算なし

            seminar_counts[assigned_seminar] += 1

        # 定員超過に対するペナルティ
        for seminar_id, count in seminar_counts.items():
            capacity = self.seminar_capacities.get(seminar_id, 0)
            if count > capacity:
                score -= (count - capacity) * 20.0  # 超過人数に応じて大きなペナルティ

        return score, seminar_counts

    def _select_parents(self, population: List[List[str]], fitnesses: List[float]) -> List[List[str]]:
        """
        ルーレット選択やトーナメント選択などを用いて、次世代の親となる個体を選択する。
        ここではルーレット選択の簡易版を実装。
        """
        selected_parents = []
        total_fitness = sum(fitnesses)
        if total_fitness == 0: # 全ての適合度が0の場合の対策
            return random.choices(population, k=self.population_size)

        # 適合度を正規化して確率を計算
        probabilities = [f / total_fitness for f in fitnesses]

        # 適合度に基づいて個体を選択
        # k=self.population_size で、新しい個体群と同じ数の親を選択
        selected_parents = random.choices(population, weights=probabilities, k=self.population_size)
        return selected_parents


    def _crossover(self, parent1: List[str], parent2: List[str]) -> Tuple[List[str], List[str]]:
        """
        2つの親個体から交叉により新しい2つの子個体を生成する。
        一点交叉や二点交叉などを実装。ここでは一点交叉。
        """
        if random.random() < self.crossover_rate:
            # 交叉点をランダムに選択
            crossover_point = random.randint(1, len(parent1) - 1)
            child1 = parent1[:crossover_point] + parent2[crossover_point:]
            child2 = parent2[:crossover_point] + parent1[crossover_point:]
            return child1, child2
        else:
            return parent1, parent2 # 交叉しない場合は親をそのまま返す

    def _mutate(self, individual: List[str]) -> List[str]:
        """
        個体に突然変異を適用する。
        ランダムな学生の割り当てセミナーをランダムな別のセミナーに変更する。
        """
        mutated_individual = list(individual) # コピーを作成して元の個体を変更しない
        for i in range(len(mutated_individual)):
            if random.random() < self.mutation_rate:
                # ランダムなセミナーに割り当てを変更
                mutated_individual[i] = random.choice(self.seminar_ids)
        return mutated_individual

    def optimize(self) -> Dict[str, Any]:
        """
        遺伝的アルゴリズムを実行し、最適なセミナー割り当てを見つける。

        Returns:
            Dict[str, Any]: 最適化結果。
                - 'assignments': 学生IDと割り当てセミナーIDの辞書
                - 'total_score': 最適な割り当ての適合度
                - 'seminar_counts': 各セミナーの最終的な割り当て人数
        """
        population = self._initialize_population()
        best_individual = None
        best_fitness = -float('inf') # 最小値で初期化

        for generation in range(self.generations):
            fitnesses = [self._evaluate_fitness(ind)[0] for ind in population]

            # 現在の世代のベスト個体を追跡
            current_best_fitness = max(fitnesses)
            current_best_index = fitnesses.index(current_best_fitness)
            current_best_individual = population[current_best_index]

            if current_best_fitness > best_fitness:
                best_fitness = current_best_fitness
                best_individual = current_best_individual

            # 次世代の個体群を生成
            new_population = []
            parents = self._select_parents(population, fitnesses)

            # エリート選択 (任意): 最も適合度の高い個体を次世代に無条件で引き継ぐ
            # ここでは、ベスト個体を1つ引き継ぐ例
            if best_individual:
                 new_population.append(best_individual)

            # 交叉と突然変異で残りの個体を生成
            # population_size - 1 はエリート選択で1つ追加したため
            for i in range(0, len(parents) - 1, 2):
                parent1 = parents[i]
                parent2 = parents[i+1]
                child1, child2 = self._crossover(parent1, parent2)
                new_population.append(self._mutate(child1))
                if len(new_population) < self.population_size: # 個体数が上限を超えないように
                    new_population.append(self._mutate(child2))

            # 個体群のサイズを調整 (もし増えすぎた場合)
            population = new_population[:self.population_size]

            # 進捗表示 (任意)
            if generation % 50 == 0:
                print(f"Generation {generation}: Best Fitness = {best_fitness:.2f}")

        # 最適な個体から割り当て結果を生成
        final_assignments = {}
        if best_individual:
            for i, student_id in enumerate(self.student_ids):
                final_assignments[student_id] = best_individual[i]

        final_score, final_seminar_counts = self._evaluate_fitness(best_individual) if best_individual else (0.0, {})

        return {
            "assignments": final_assignments,
            "total_score": final_score,
            "seminar_counts": final_seminar_counts
        }

# --- テスト用の簡易データ ---
if __name__ == "__main__":
    # 実際のデータはファイルから読み込むことを想定
    sample_seminars = [
        {"id": "seminar_A", "capacity": 2},
        {"id": "seminar_B", "capacity": 2},
        {"id": "seminar_C", "capacity": 1},
    ]

    sample_students = [
        {"id": "student_1", "preferences": ["seminar_A", "seminar_B", "seminar_C"]},
        {"id": "student_2", "preferences": ["seminar_A", "seminar_C", "seminar_B"]},
        {"id": "student_3", "preferences": ["seminar_B", "seminar_A", "seminar_C"]},
        {"id": "student_4", "preferences": ["seminar_B", "seminar_C", "seminar_A"]},
        {"id": "student_5", "preferences": ["seminar_C", "seminar_A", "seminar_B"]},
    ]

    ga_config = {
        "population_size": 50,
        "generations": 200,
        "crossover_rate": 0.8,
        "mutation_rate": 0.05,
    }

    print("GAOptimizerを初期化中...")
    optimizer = GAOptimizer(sample_seminars, sample_students, ga_config)
    print("最適化を開始...")
    result = optimizer.optimize()

    print("\n--- 最適化結果 ---")
    print(f"総適合度: {result['total_score']:.2f}")
    print("割り当て:")
    for student_id, seminar_id in result['assignments'].items():
        print(f"  {student_id}: {seminar_id}")
    print("セミナーごとの人数:")
    for seminar_id, count in result['seminar_counts'].items():
        capacity = next(s['capacity'] for s in sample_seminars if s['id'] == seminar_id)
        print(f"  {seminar_id}: {count} / {capacity} (定員)")

    # 定員超過があるか確認
    over_capacity = False
    for seminar_id, count in result['seminar_counts'].items():
        capacity = next(s['capacity'] for s in sample_seminars if s['id'] == seminar_id)
        if count > capacity:
            print(f"警告: {seminar_id} が定員を {count - capacity} 人超過しています！")
            over_capacity = True
    if not over_capacity:
        print("全てのセミナーが定員内に収まっています。")

