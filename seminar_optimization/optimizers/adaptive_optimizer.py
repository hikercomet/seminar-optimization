import numpy as np
import random
import time
import logging
from typing import Dict, List, Tuple, Any, Callable, Optional

# BaseOptimizerとOptimizationResultをutilsからインポート (絶対インポートに変更)
from utils import BaseOptimizer, OptimizationResult

# 各最適化アルゴリズムをインポート (絶対インポートに変更)
from seminar_optimization.optimizers.greedy_ls_optimizer import GreedyLSOptimizer
from seminar_optimization.optimizers.genetic_algorithm_optimizer import GeneticAlgorithmOptimizer
from seminar_optimization.optimizers.ilp_optimizer import ILPOptimizer
from seminar_optimization.optimizers.cp_sat_optimizer import CPSATOptimizer
from seminar_optimization.optimizers.multilevel_optimizer import MultilevelOptimizer

logger = logging.getLogger(__name__)

class AdaptiveOptimizer(BaseOptimizer): # BaseOptimizerを継承
    """
    適応型最適化アルゴリズム。
    複数の最適化戦略（Greedy_LS, GA_LS, ILP, CP, Multilevel）を組み合わせ、
    問題の特性や過去のパフォーマンスに基づいて最適な戦略を動的に選択または切り替える。
    """

    def __init__(self,
                 seminars: List[Dict[str, Any]],
                 students: List[Dict[str, Any]],
                 config: Dict[str, Any],
                 progress_callback: Optional[Callable[[str], None]] = None): # progress_callbackを追加
        # BaseOptimizerの__init__を呼び出す
        super().__init__(seminars, students, config, progress_callback)

        # 固有のパラメータはconfigから取得
        self.q_boost_probability = config.get("q_boost_probability", 0.2)
        self.num_preferences_to_consider = config.get("num_preferences_to_consider", 3)
        self.max_adaptive_iterations = config.get("max_adaptive_iterations", 5) # 適応型最適化の最大試行回数
        self.strategy_time_limit = config.get("strategy_time_limit", 60) # 各戦略の最大実行時間 (秒)

        # 各戦略のパフォーマンスを追跡するための辞書 (Q学習のQ値のようなもの)
        # キー: 戦略名, 値: (成功回数, 総スコア) または (成功回数, 平均スコア)
        self.strategy_performance: Dict[str, Dict[str, Any]] = {
            "Greedy_LS": {"successes": 0, "total_score": 0.0, "runs": 0},
            "GA_LS": {"successes": 0, "total_score": 0.0, "runs": 0},
            "ILP": {"successes": 0, "total_score": 0.0, "runs": 0},
            "CP": {"successes": 0, "total_score": 0.0, "runs": 0},
            "Multilevel": {"successes": 0, "total_score": 0.0, "runs": 0},
        }
        self.available_strategies = list(self.strategy_performance.keys())
        self.current_strategy_name: Optional[str] = None

        self.best_overall_assignment: Optional[Dict[str, str]] = None
        self.best_overall_score = -float('inf')

        # 問題の特性を分析
        self.problem_complexity = self._analyze_problem_complexity()

    def _analyze_problem_complexity(self) -> Dict[str, Any]:
        """
        問題の特性（複雑性）を分析し、戦略選択のヒントにする。
        """
        num_students = len(self.students)
        num_seminars = len(self.seminars)
        avg_capacity = sum(self.seminar_capacities.values()) / num_seminars if num_seminars > 0 else 0
        total_capacity = sum(self.seminar_capacities.values())

        # 学生の希望の重複度を計算
        preference_counts: Dict[str, int] = {s_id: 0 for s_id in self.seminar_ids}
        for student in self.students:
            for pref_seminar in student['preferences']:
                if pref_seminar in preference_counts:
                    preference_counts[pref_seminar] += 1
        
        # 希望が集中しているセミナーの割合
        highly_demanded_seminars = [s_id for s_id, count in preference_counts.items() if count > avg_capacity * 1.5]
        
        complexity = {
            "num_students": num_students,
            "num_seminars": num_seminars,
            "avg_capacity": avg_capacity,
            "total_capacity": total_capacity,
            "capacity_ratio": num_students / total_capacity if total_capacity > 0 else 0, # 学生数/総定員
            "highly_demanded_seminars_count": len(highly_demanded_seminars)
        }
        self._log(f"問題の複雑性分析: {complexity}", level=logging.DEBUG)
        return complexity

    def _select_strategy(self) -> str:
        """
        現在の問題の特性と過去のパフォーマンスに基づいて、次の最適化戦略を選択する。
        Q学習のようなアプローチを簡易的に実装。
        """
        # 初期段階や探索が必要な場合はランダムに選択
        if random.random() < self.q_boost_probability or all(s["runs"] < 1 for s in self.strategy_performance.values()):
            selected_strategy = random.choice(self.available_strategies)
            self._log(f"戦略選択: 探索のためランダムに '{selected_strategy}' を選択しました。", level=logging.DEBUG)
            return selected_strategy
        
        # 過去のパフォーマンスに基づいて選択 (平均スコアが高いもの)
        # スコアが負の場合は0として扱うか、非常に小さい値として扱う
        best_avg_score = -float('inf')
        best_strategy = None

        for strategy_name, stats in self.strategy_performance.items():
            if stats["runs"] > 0:
                avg_score = stats["total_score"] / stats["runs"]
            else:
                avg_score = -float('inf') # まだ実行されていない戦略は低い評価

            if avg_score > best_avg_score:
                best_avg_score = avg_score
                best_strategy = strategy_name
        
        if best_strategy is None: # 全ての戦略がまだ実行されていない場合
            best_strategy = random.choice(self.available_strategies)

        self._log(f"戦略選択: 過去のパフォーマンスに基づいて '{best_strategy}' を選択しました (最高平均スコア: {best_avg_score:.2f})。", level=logging.DEBUG)
        return best_strategy

    def _update_strategy_performance(self, strategy_name: str, result: OptimizationResult):
        """
        戦略の実行結果に基づいてパフォーマンス統計を更新する。
        """
        stats = self.strategy_performance[strategy_name]
        stats["runs"] += 1
        if result.status in ["OPTIMAL", "FEASIBLE"]: # 成功とみなすステータス
            stats["successes"] += 1
            stats["total_score"] += result.best_score
        self._log(f"戦略 '{strategy_name}' のパフォーマンスを更新しました: {stats}", level=logging.DEBUG)


    def optimize(self) -> OptimizationResult: # 返り値をOptimizationResultに
        """
        適応型最適化アルゴリズムのメイン実行関数。
        """
        self._log("AdaptiveOptimizer: 最適化を開始します。")
        self.best_overall_assignment = None
        self.best_overall_score = -float('inf')
        
        for i in range(self.max_adaptive_iterations):
            if self.progress_callback:
                self.progress_callback(f"適応型最適化イテレーション {i+1}/{self.max_adaptive_iterations}")
            self._log(f"AdaptiveOptimizer: イテレーション {i+1}/{self.max_adaptive_iterations} を開始します。")

            # 次の戦略を選択
            next_strategy = self._select_strategy()
            self.current_strategy_name = next_strategy
            self._log(f"AdaptiveOptimizer: 次の戦略は '{self.current_strategy_name}' です。")
            
            optimizer: BaseOptimizer = None
            try:
                # 各オプティマイザのインスタンスを生成し、progress_callbackを渡す
                if self.current_strategy_name == "Greedy_LS":
                    optimizer = GreedyLSOptimizer(self.seminars, self.students, self.config, self.progress_callback)
                elif self.current_strategy_name == "GA_LS":
                    optimizer = GeneticAlgorithmOptimizer(self.seminars, self.students, self.config, self.progress_callback)
                elif self.current_strategy_name == "ILP":
                    optimizer = ILPOptimizer(self.seminars, self.students, self.config, self.progress_callback)
                elif self.current_strategy_name == "CP":
                    optimizer = CPSATOptimizer(self.seminars, self.students, self.config, self.progress_callback)
                elif self.current_strategy_name == "Multilevel":
                    optimizer = MultilevelOptimizer(self.seminars, self.students, self.config, self.progress_callback)
                else:
                    raise ValueError(f"不明な最適化戦略: {self.current_strategy_name}")

                # 各戦略に時間制限を設定 (configから取得したstrategy_time_limitを渡す)
                # ILP/CPは自身のtime_limitを持つため、ここでは主に反復ベースのアルゴリズムに影響
                # configを直接変更するのではなく、オプティマイザの初期化時に渡す
                # 例: self.config["ilp_time_limit"] = self.strategy_time_limit

                # オプティマイザの実行
                strategy_result = optimizer.optimize()

                # パフォーマンスを更新
                self._update_strategy_performance(self.current_strategy_name, strategy_result)

                # 全体的なベスト解を更新
                if strategy_result.status in ["OPTIMAL", "FEASIBLE"] and strategy_result.best_score > self.best_overall_score:
                    self.best_overall_score = strategy_result.best_score
                    self.best_overall_assignment = strategy_result.best_assignment.copy()
                    self._log(f"AdaptiveOptimizer: 全体ベストスコアが更新されました: {self.best_overall_score:.2f} (戦略: {self.current_strategy_name})")
                elif strategy_result.status == "CANCELLED":
                    self._log(f"AdaptiveOptimizer: 戦略 '{self.current_strategy_name}' がキャンセルされました。")
                    # キャンセルされた場合は、ループを終了する
                    self.current_strategy_name = None # ループ終了
                    break
                
            except Exception as e:
                self._log(f"AdaptiveOptimizer: 戦略 '{self.current_strategy_name}' の実行中にエラーが発生しました: {e}", level=logging.ERROR)
                # エラーが発生した戦略は一時的に利用不可にするか、低い評価を与える
                # 簡単化のため、ここでNoneにする。
                self.current_strategy_name = None # ループ終了
                break # エラーが発生したら適応型ループを終了

        self._log("AdaptiveOptimizer: 最適化が完了しました。")
        
        status = "NO_SOLUTION_FOUND"
        message = "最適解が見つかりませんでした。"
        unassigned_students: List[str] = []

        if self.best_overall_assignment is None:
            message = "最適解が見つかりませんでした。"
            status = "FAILED"
        else:
            message = "最適化が成功しました。"
            status = "OPTIMAL" # またはFEASIBLE
            unassigned_students = self._get_unassigned_students(self.best_overall_assignment)


        return OptimizationResult(
            status=status,
            message=message,
            best_score=self.best_overall_score,
            best_assignment=self.best_overall_assignment if self.best_overall_assignment else {},
            seminar_capacities=self.seminar_capacities,
            unassigned_students=unassigned_students,
            optimization_strategy="Adaptive"
        )

