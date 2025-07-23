import numpy as np
import random
import time
import logging # ロギングを追加
import threading
from typing import Dict, List, Tuple, Any, Callable, Optional
from collections import deque # パフォーマンス履歴を保持するため

# BaseOptimizerとOptimizationResultをutilsからインポート
from seminar_optimization.seminar_optimization.utils import BaseOptimizer, OptimizationResult # <-- 修正: 相対インポート
# ロギングは logger_config.py で一元的に設定されるため、ここではロガーの取得のみ
from seminar_optimization.seminar_optimization.logger_config import logger # <-- 修正: 相対インポート

# 各最適化アルゴリズムをインポート
# 動的インポートを避けるため、ここにリストアップ
from seminar_optimization.optimizers.greedy_ls_optimizer import GreedyLSOptimizer # <-- 修正: 相対インポート
from seminar_optimization.optimizers.genetic_algorithm_optimizer import GeneticAlgorithmOptimizer # <-- 修正: 相対インポート
from seminar_optimization.optimizers.ilp_optimizer import ILPOptimizer # <-- 修正: 相対インポート
from seminar_optimization.optimizers.cp_sat_optimizer import CPSATOptimizer # <-- 修正: 相対インポート
from seminar_optimization.optimizers.multilevel_optimizer import MultilevelOptimizer # <-- 修正: 相対インポート

# オプティマイザのマッピングを定義
OPTIMIZER_MAP = {
    "Greedy_LS": GreedyLSOptimizer,
    "GA_LS": GeneticAlgorithmOptimizer,
    "ILP": ILPOptimizer,
    "CP": CPSATOptimizer,
    "Multilevel": MultilevelOptimizer
}

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
        logger.debug("AdaptiveOptimizer: 初期化を開始します。")

        # 適応型最適化固有のパラメータ
        self.strategy_history: Dict[str, deque] = {name: deque(maxlen=config.get("adaptive_history_size", 5)) for name in OPTIMIZER_MAP.keys()}
        self.exploration_epsilon = config.get("adaptive_exploration_epsilon", 0.1) # 探索率
        self.learning_rate = config.get("adaptive_learning_rate", 0.2) # 学習率
        
        # パフォーマンス評価の重み
        self.score_weight = config.get("adaptive_score_weight", 0.6)
        self.unassigned_weight = config.get("adaptive_unassigned_weight", 0.3)
        self.time_weight = config.get("adaptive_time_weight", 0.1)
        self.max_time_for_normalization = config.get("max_time_for_normalization", 600) # 時間正規化のための最大時間 (秒)

        self.strategy_scores: Dict[str, float] = {name: 0.0 for name in OPTIMIZER_MAP.keys()} # 各戦略の累積スコア
        self.current_strategy_name: Optional[str] = None
        
        logger.info("AdaptiveOptimizer: 適応型最適化の初期化が完了しました。")
        logger.debug(f"AdaptiveOptimizer: 探索率={self.exploration_epsilon}, 学習率={self.learning_rate}")
        logger.debug(f"AdaptiveOptimizer: スコア重み={self.score_weight}, 未割り当て重み={self.unassigned_weight}, 時間重み={self.time_weight}")


    def _normalize_score(self, score: float, min_score: float, max_score: float) -> float:
        """スコアを0-1の範囲に正規化する"""
        if max_score == min_score:
            return 0.5 # 変化がない場合は中間値
        return (score - min_score) / (max_score - min_score)

    def _normalize_unassigned(self, unassigned_count: int, max_unassigned: int) -> float:
        """未割り当て数を0-1の範囲に正規化する (少ないほど良いので1-x)"""
        if max_unassigned == 0:
            return 1.0 # 未割り当てがなければ最高
        return 1.0 - (unassigned_count / max_unassigned)

    def _normalize_time(self, duration: float) -> float:
        """時間を0-1の範囲に正規化する (短いほど良いので1-x)"""
        # max_time_for_normalization を超える場合は0に近づける
        normalized_time = min(duration, self.max_time_for_normalization) / self.max_time_for_normalization
        return 1.0 - normalized_time


    def _update_strategy_performance(self, strategy_name: str, result: OptimizationResult, duration: float):
        """
        各戦略のパフォーマンスを更新する。
        スコア、未割り当て学生数、実行時間を考慮して評価する。
        """
        if result.status in ["OPTIMAL", "FEASIBLE"]:
            # 正規化されたパフォーマンス指標を計算
            # スコアは高いほど良い
            # 未割り当て学生数は少ないほど良い
            # 実行時間は短いほど良い

            # スコアの正規化 (仮の最小・最大スコアを使用)
            # 実際のアプリケーションでは、過去の実行履歴から動的に範囲を決定するか、
            # 経験的な値を設定する必要があります。
            # ここでは、学生数 * 1st_choice_weight を最大スコアの目安とする
            max_possible_score = len(self.student_ids) * self.config.get("score_weights", {}).get("1st_choice", 3.0)
            min_possible_score = 0.0 # 最低は0点
            normalized_score = self._normalize_score(result.best_score, min_possible_score, max_possible_score)

            # 未割り当て学生数の正規化
            max_unassigned = len(self.student_ids) # 全員未割り当てが最大
            normalized_unassigned = self._normalize_unassigned(len(result.unassigned_students), max_unassigned)

            # 時間の正規化
            normalized_time = self._normalize_time(duration)

            # 総合パフォーマンススコアを計算
            performance_score = (
                self.score_weight * normalized_score +
                self.unassigned_weight * normalized_unassigned +
                self.time_weight * normalized_time
            )
            
            self.strategy_history[strategy_name].append(performance_score)
            
            # 移動平均や指数平滑平均のような形で累積スコアを更新
            # ここでは簡易的に、過去の履歴の平均を使用
            avg_performance = sum(self.strategy_history[strategy_name]) / len(self.strategy_history[strategy_name])
            
            # 学習率を考慮して戦略の累積スコアを更新
            self.strategy_scores[strategy_name] = (1 - self.learning_rate) * self.strategy_scores[strategy_name] + self.learning_rate * avg_performance
            
            self._log(f"AdaptiveOptimizer: 戦略 '{strategy_name}' のパフォーマンスを更新しました。正規化スコア: {normalized_score:.2f}, 未割り当て: {normalized_unassigned:.2f}, 時間: {normalized_time:.2f}, 総合パフォーマンス: {performance_score:.2f}, 累積スコア: {self.strategy_scores[strategy_name]:.2f}")
        else:
            # 失敗した場合はペナルティを与えるか、スコアを更新しない
            # ここでは、累積スコアを少し下げる
            self.strategy_scores[strategy_name] = max(0.0, self.strategy_scores[strategy_name] * 0.8 - 0.1) # 0.8倍して0.1引く
            self._log(f"AdaptiveOptimizer: 戦略 '{strategy_name}' が失敗しました。累積スコアを調整: {self.strategy_scores[strategy_name]:.2f}")


    def _select_strategy(self) -> str:
        """
        現在のパフォーマンス履歴に基づいて最適な戦略を選択する。
        ε-greedy戦略を使用し、探索と活用のバランスを取る。
        """
        if random.random() < self.exploration_epsilon:
            # 探索: ランダムな戦略を選択
            selected_strategy = random.choice(list(OPTIMIZER_MAP.keys()))
            self._log(f"AdaptiveOptimizer: ε-greedy探索により戦略 '{selected_strategy}' をランダムに選択しました。")
        else:
            # 活用: 最も高い累積スコアを持つ戦略を選択
            # 初期状態（全て0.0）の場合もランダムに選ぶ
            if all(score == 0.0 for score in self.strategy_scores.values()):
                selected_strategy = random.choice(list(OPTIMIZER_MAP.keys()))
                self._log(f"AdaptiveOptimizer: 全ての戦略スコアが初期値のため、ランダムに戦略 '{selected_strategy}' を選択しました。")
            else:
                selected_strategy = max(self.strategy_scores, key=self.strategy_scores.get)
                self._log(f"AdaptiveOptimizer: 活用により戦略 '{selected_strategy}' を選択しました (累積スコア: {self.strategy_scores[selected_strategy]:.2f})。")
        
        self.current_strategy_name = selected_strategy
        return selected_strategy

    def optimize(self, cancel_event: Optional[threading.Event] = None) -> OptimizationResult:
        """
        適応型最適化プロセスを実行する。
        複数の戦略を順番に試行し、最も良い結果を返す。
        """
        start_overall_time = time.time()
        self._log("AdaptiveOptimizer: 適応型最適化を開始します...")

        best_overall_score = -float('inf')
        best_overall_assignment: Dict[str, str] = {}
        final_status = "NO_SOLUTION_FOUND"
        final_message = "適応型最適化で有効な解が見つかりませんでした。"
        final_strategy_used = "N/A"

        # 試行する戦略のリスト (ここではすべての戦略を一度は試す)
        strategies_to_try = list(OPTIMIZER_MAP.keys())
        random.shuffle(strategies_to_try) # 試行順序をランダム化

        for strategy_name in strategies_to_try:
            if cancel_event and cancel_event.is_set():
                self._log("AdaptiveOptimizer: 全体最適化がキャンセルされました。")
                final_status = "CANCELLED"
                final_message = "最適化がユーザーによってキャンセルされました。"
                break

            # ε-greedy選択 (ここでは既に全戦略を試すので、選択ロジックは簡略化)
            # 実際の適応型では、ここで _select_strategy() を呼び出す
            self.current_strategy_name = strategy_name
            self._log(f"AdaptiveOptimizer: 戦略 '{self.current_strategy_name}' を試行します。")

            optimizer_class = OPTIMIZER_MAP.get(self.current_strategy_name)
            if not optimizer_class:
                self._log(f"AdaptiveOptimizer: 未知の最適化戦略: {self.current_strategy_name}。スキップします。", level=logging.ERROR)
                continue

            optimizer_instance = optimizer_class(
                seminars=self.seminars,
                students=self.students,
                config=self.config,
                progress_callback=self.progress_callback
            )

            strategy_start_time = time.time()
            current_result = optimizer_instance.optimize(cancel_event)
            strategy_end_time = time.time()
            duration = strategy_end_time - strategy_start_time

            self._log(f"AdaptiveOptimizer: 戦略 '{self.current_strategy_name}' 完了。ステータス: {current_result.status}, スコア: {current_result.best_score:.2f}, 時間: {duration:.2f}秒")

            # パフォーマンスを更新
            self._update_strategy_performance(self.current_strategy_name, current_result, duration)

            # 最も良い結果を保持
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

        # キャンセルされた場合は、キャンセルステータスを優先
        if cancel_event and cancel_event.is_set():
            final_status = "CANCELLED"
            final_message = "最適化がユーザーによってキャンセルされました。"
            best_overall_score = -float('inf') # キャンセルされた場合はスコアを無効にする
            unassigned_students = self.student_ids # 全員未割り当てとみなす

        return OptimizationResult(
            status=final_status,
            message=final_message,
            best_score=best_overall_score,
            best_assignment=best_overall_assignment,
            seminar_capacities=self.seminar_capacities,
            unassigned_students=unassigned_students,
            optimization_strategy=final_strategy_used
        )
