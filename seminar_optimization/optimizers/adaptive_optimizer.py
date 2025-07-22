import numpy as np
import random
import time
import logging
import threading
from typing import Dict, List, Tuple, Any, Callable, Optional
from collections import deque # パフォーマンス履歴を保持するため

# BaseOptimizerとOptimizationResultをutilsからインポート
from utils import BaseOptimizer, OptimizationResult

# 各最適化アルゴリズムをインポート
from optimizers.greedy_ls_optimizer import GreedyLSOptimizer
from optimizers.genetic_algorithm_optimizer import GeneticAlgorithmOptimizer
from optimizers.ilp_optimizer import ILPOptimizer
from optimizers.cp_sat_optimizer import CPSATOptimizer
from optimizers.multilevel_optimizer import MultilevelOptimizer

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # DEBUGレベルのメッセージも出力

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
                 progress_callback: Optional[Callable[[str], None]] = None):
        # BaseOptimizerの__init__を呼び出す
        super().__init__(seminars, students, config, progress_callback)
        self._log("AdaptiveOptimizer: 初期化を開始シマス。")

        # 利用可能な最適化戦略
        # Pylanceエラー対策のため、インポートされたクラス名を直接参照
        self.strategies: Dict[str, Callable[..., BaseOptimizer]] = {
            "Greedy_LS": GreedyLSOptimizer,
            "GA_LS": GeneticAlgorithmOptimizer,
            "ILP": ILPOptimizer,
            "CP": CPSATOptimizer,
            "Multilevel": MultilevelOptimizer,
        }
        self.strategy_names = list(self.strategies.keys())

        # 各戦略の初期重み (均等に開始)
        self.strategy_weights: Dict[str, float] = {name: 1.0 / len(self.strategy_names) for name in self.strategy_names}
        # 各戦略のパフォーマンス履歴 (dequeで最新のN件を保持)
        self.strategy_performance_history: Dict[str, deque] = {name: deque(maxlen=self.config.get("adaptive_history_size", 5)) for name in self.strategy_names}

        # 適応型最適化のパラメータ
        self.max_adaptive_iterations = config.get("max_adaptive_iterations", 5)
        self.exploration_epsilon = config.get("adaptive_exploration_epsilon", 0.2) # ε-greedy探索の確率
        self.learning_rate = config.get("adaptive_learning_rate", 0.1) # 重み更新の学習率

        # パフォーマンス評価の重み
        self.score_weight = config.get("adaptive_score_weight", 0.6)
        self.unassigned_weight = config.get("adaptive_unassigned_weight", 0.3)
        self.time_weight = config.get("adaptive_time_weight", 0.1)

        # 正規化のための最大値 (config.jsonで設定可能に)
        self.max_time_for_normalization = config.get("max_time_for_normalization", 600) # 例: 10分
        # 最大可能スコアの概算 (学生数 * 第1希望の重み * 最大倍率)
        self.max_score_for_normalization = len(self.student_ids) * self.config.get("preference_weights", {}).get("1st", 5.0) * max(self.seminar_magnifications.values(), default=1.0)
        
        self._log(f"AdaptiveOptimizer: {len(self.strategy_names)} 個の戦略で初期化されました。")
        self._log(f"AdaptiveOptimizer: 初期重み: {self.strategy_weights}")
        self._log(f"AdaptiveOptimizer: 最大適応イテレーション: {self.max_adaptive_iterations}, 探索率: {self.exploration_epsilon}")

    def _calculate_performance_score(self, result: OptimizationResult, duration: float) -> float:
        """
        最適化結果と実行時間に基づいて、戦略のパフォーマンススコアを計算する。
        スコアは0から1の範囲に正規化されることを目指す。
        """
        if result.status in ["FAILED", "INFEASIBLE", "MODEL_INVALID", "NO_SOLUTION_FOUND"]:
            self._log(f"パフォーマンス計算: 戦略 '{result.optimization_strategy}' が失敗ステータス '{result.status}' を返しました。スコアは0とします。", level=logging.WARNING)
            return 0.0 # 失敗した戦略のパフォーマンスは0

        # スコアの正規化 (0-1)
        normalized_score = result.best_score / self.max_score_for_normalization if self.max_score_for_normalization > 0 else 0.0
        normalized_score = max(0.0, min(1.0, normalized_score)) # 0-1の範囲にクリップ

        # 未割り当て学生数の正規化 (0-1, 0が最適)
        if len(self.student_ids) > 0:
            normalized_unassigned = 1.0 - (len(result.unassigned_students) / len(self.student_ids))
        else:
            normalized_unassigned = 1.0 # 学生がいない場合は完全に割り当てられたとみなす
        normalized_unassigned = max(0.0, min(1.0, normalized_unassigned))

        # 実行時間の正規化 (0-1, 短いほど最適)
        normalized_time = 1.0 - (duration / self.max_time_for_normalization) if self.max_time_for_normalization > 0 else 0.0
        normalized_time = max(0.0, min(1.0, normalized_time)) # 0-1の範囲にクリップ

        # 加重平均で総合パフォーマンススコアを計算
        performance_score = (
            self.score_weight * normalized_score +
            self.unassigned_weight * normalized_unassigned +
            self.time_weight * normalized_time
        )
        
        self._log(f"パフォーマンス計算: 戦略 '{result.optimization_strategy}' - スコア: {normalized_score:.2f}, 未割り当て: {normalized_unassigned:.2f}, 時間: {normalized_time:.2f} -> 総合: {performance_score:.2f}")
        return performance_score

    def _update_strategy_weights(self, strategy_name: str, performance_score: float):
        """
        戦略のパフォーマンススコアに基づいて、その戦略の重みを更新する。
        指数移動平均 (EMA) の概念を使用。
        """
        self.strategy_performance_history[strategy_name].append(performance_score)
        
        # 履歴の平均を新しい重みとする
        # 失敗した戦略は重みを非常に低く設定し、選択されにくくする
        if performance_score == 0.0 and len(self.strategy_performance_history[strategy_name]) == self.strategy_performance_history[strategy_name].maxlen:
            # 履歴が全て0の場合、重みを大幅に減らす
            self.strategy_weights[strategy_name] = -100.0 # 非常に低い値
            self._log(f"戦略 '{strategy_name}' が連続して低パフォーマンスのため、重みを大幅に減らしました。", level=logging.WARNING)
        else:
            # EMA (Exponential Moving Average) のように更新
            current_average_performance = np.mean(list(self.strategy_performance_history[strategy_name]))
            current_weight = self.strategy_weights.get(strategy_name, 0.0) # 既存の重みを取得
            
            # 学習率を適用して重みを更新
            new_weight = (1 - self.learning_rate) * current_weight + self.learning_rate * current_average_performance
            self.strategy_weights[strategy_name] = new_weight
            self._log(f"戦略 '{strategy_name}' の重みを更新しました。新重み: {new_weight:.4f} (平均パフォーマンス: {current_average_performance:.4f})")

        # 全体の重みを正規化 (合計が1になるように)
        # 負の重みは正規化から除外、または非常に低い値として扱う
        positive_weights = {name: w for name, w in self.strategy_weights.items() if w > 0}
        total_positive_weight = sum(positive_weights.values())

        if total_positive_weight > 0:
            for name in positive_weights:
                self.strategy_weights[name] /= total_positive_weight
        else:
            # 全ての重みが0以下の場合、均等にリセット
            self._log("全ての戦略の重みが0以下になりました。重みを均等にリセットします。", level=logging.WARNING)
            self.strategy_weights = {name: 1.0 / len(self.strategy_names) for name in self.strategy_names}

        self._log(f"AdaptiveOptimizer: 更新後の戦略重み: {self.strategy_weights}")


    def _select_strategy(self) -> str:
        """
        現在の重みに基づいて、ε-greedy戦略で次の最適化戦略を選択する。
        """
        # 探索 (Exploration)
        if random.random() < self.exploration_epsilon:
            # 失敗していない戦略の中からランダムに選択
            available_strategies = [name for name, weight in self.strategy_weights.items() if weight > -99.0] # 非常に低い重みは避ける
            if available_strategies:
                selected_strategy = random.choice(available_strategies)
                self._log(f"AdaptiveOptimizer: 探索のため、戦略 '{selected_strategy}' をランダムに選択しました。")
                return selected_strategy
            else:
                self._log("AdaptiveOptimizer: 探索可能な戦略が見つかりませんでした。重みから選択します。", level=logging.WARNING)
        
        # 活用 (Exploitation)
        # 現在の重みが最も高い戦略を選択
        # 負の無限大の重みを持つ戦略は選択肢から除外
        valid_strategies = {name: weight for name, weight in self.strategy_weights.items() if weight > -99.0}
        if not valid_strategies:
            self._log("AdaptiveOptimizer: 選択可能な有効な戦略がありません。Greedy_LSをフォールバックとして使用します。", level=logging.ERROR)
            return "Greedy_LS" # フォールバック

        selected_strategy = max(valid_strategies, key=valid_strategies.get)
        self._log(f"AdaptiveOptimizer: 活用のため、最も重みの高い戦略 '{selected_strategy}' を選択しました。")
        return selected_strategy

    def optimize(self, cancel_event: Optional[threading.Event] = None) -> OptimizationResult:
        """
        適応型最適化アルゴリズムを実行する。
        """
        self._log("AdaptiveOptimizer: 最適化を開始します。")
        start_overall_time = time.time()

        best_overall_score = -float('inf')
        best_overall_assignment: Dict[str, str] = {}
        final_status = "NO_SOLUTION_FOUND"
        final_message = "最適解が見つかりませんでした。"
        final_strategy_used = "N/A"

        for iteration in range(self.max_adaptive_iterations):
            if cancel_event and cancel_event.is_set():
                self._log("AdaptiveOptimizer: 最適化がユーザーによってキャンセルされました。")
                final_status = "CANCELLED"
                final_message = "最適化がユーザーによってキャンセルされました。"
                break

            self._log(f"--- AdaptiveOptimizer イテレーション {iteration + 1}/{self.max_adaptive_iterations} ---")
            
            # 次の戦略を選択
            self.current_strategy_name = self._select_strategy()
            self._log(f"AdaptiveOptimizer: 選択された戦略: {self.current_strategy_name}")

            # 選択された戦略のオプティマイザをインスタンス化
            optimizer_class = self.strategies.get(self.current_strategy_name)
            if not optimizer_class:
                self._log(f"AdaptiveOptimizer: 不明な戦略 '{self.current_strategy_name}' が選択されました。スキップします。", level=logging.ERROR)
                continue

            current_optimizer = optimizer_class(self.seminars, self.students, self.config, 
                                                progress_callback=lambda msg: self._log(f"[{self.current_strategy_name}] {msg}", level=logging.DEBUG))
            
            iteration_start_time = time.time()
            current_result: Optional[OptimizationResult] = None
            try:
                # 各オプティマイザのoptimizeメソッドにcancel_eventを渡す
                current_result = current_optimizer.optimize(cancel_event=cancel_event)
            except Exception as e:
                self._log(f"AdaptiveOptimizer: 戦略 '{self.current_strategy_name}' の実行中に予期せぬエラーが発生しました: {e}", level=logging.ERROR, exc_info=True)
                # エラーが発生した戦略はパフォーマンススコアを0として扱う
                current_result = OptimizationResult(
                    status="FAILED",
                    message=f"エラー: {e}",
                    best_score=-float('inf'),
                    best_assignment={},
                    seminar_capacities=self.seminar_capacities,
                    unassigned_students=self.student_ids,
                    optimization_strategy=self.current_strategy_name
                )
            
            iteration_end_time = time.time()
            duration = iteration_end_time - iteration_start_time
            self._log(f"AdaptiveOptimizer: 戦略 '{self.current_strategy_name}' 完了。ステータス: {current_result.status}, スコア: {current_result.best_score:.2f}, 時間: {duration:.2f}s")

            # パフォーマンススコアを計算し、重みを更新
            performance_score = self._calculate_performance_score(current_result, duration)
            self._update_strategy_weights(self.current_strategy_name, performance_score)

            # 全体的なベスト結果を更新
            if current_result.status in ["OPTIMAL", "FEASIBLE"] and current_result.best_score > best_overall_score:
                best_overall_score = current_result.best_score
                best_overall_assignment = current_result.best_assignment
                final_status = current_result.status
                final_message = f"最適化が成功しました (戦略: {self.current_strategy_name})"
                final_strategy_used = self.current_strategy_name
                self._log(f"AdaptiveOptimizer: 全体的なベストスコアを更新: {best_overall_score:.2f} (戦略: {self.current_strategy_name})")

        self._log("AdaptiveOptimizer: 最適化が完了しました。")
        
        # 最終結果の決定
        if not best_overall_assignment:
            final_message = "いずれの戦略からも有効な解が見つかりませんでした。"
            final_status = "NO_SOLUTION_FOUND"
            self._log("AdaptiveOptimizer: いずれの戦略からも有効な結果が得られませんでした。", level=logging.WARNING)
        
        unassigned_students: List[str] = []
        if best_overall_assignment:
            unassigned_students = self._get_unassigned_students(best_overall_assignment)
            self._log(f"AdaptiveOptimizer: 最終的なベストスコア: {best_overall_score:.2f}, 最終ステータス: {final_status}, 未割り当て学生数: {len(unassigned_students)}")

        return OptimizationResult(
            status=final_status,
            message=final_message,
            best_score=best_overall_score,
            best_assignment=best_overall_assignment,
            seminar_capacities=self.seminar_capacities,
            unassigned_students=unassigned_students,
            optimization_strategy="Adaptive" # AdaptiveOptimizerが最終的に使用された戦略
        )
