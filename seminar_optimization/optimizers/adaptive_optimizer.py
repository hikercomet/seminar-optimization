import numpy as np
import random
import time
import logging
import threading # <-- ここに threading モジュールのインポートを追加
from typing import Dict, List, Tuple, Any, Callable, Optional

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
                 config: Dict[str, Any],\
                 progress_callback: Optional[Callable[[str], None]] = None): # progress_callbackを追加
        # BaseOptimizerの__init__を呼び出す
        super().__init__(seminars, students, config, progress_callback)
        logger.debug("AdaptiveOptimizer: 初期化を開始します。")

        # 利用可能な最適化戦略の辞書
        self.optimizers: Dict[str, BaseOptimizer] = {
            "Greedy_LS": GreedyLSOptimizer(seminars, students, config, progress_callback),
            "GA_LS": GeneticAlgorithmOptimizer(seminars, students, config, progress_callback),
            "ILP": ILPOptimizer(seminars, students, config, progress_callback),
            "CP": CPSATOptimizer(seminars, students, config, progress_callback),
            "Multilevel": MultilevelOptimizer(seminars, students, config, progress_callback)
        }
        logger.debug(f"AdaptiveOptimizer: 利用可能な最適化戦略: {list(self.optimizers.keys())}")

        # 戦略の評価と選択に関するパラメータ
        self.strategy_weights: Dict[str, float] = {name: 1.0 for name in self.optimizers.keys()}
        self.learning_rate = config.get("adaptive_learning_rate", 0.1)
        self.evaluation_history: Dict[str, List[float]] = {name: [] for name in self.optimizers.keys()}
        self.max_history_size = config.get("adaptive_max_history_size", 5) # 過去N回の結果を考慮
        self.initial_strategy = config.get("adaptive_initial_strategy", "Greedy_LS") # 初期戦略
        self.strategy_order = config.get("adaptive_strategy_order", ["Greedy_LS", "GA_LS", "Multilevel", "CP", "ILP"]) # 試行順序のデフォルト
        logger.debug(f"AdaptiveOptimizer: 初期戦略重み: {self.strategy_weights}, 学習率: {self.learning_rate}, 履歴サイズ: {self.max_history_size}, 初期戦略: {self.initial_strategy}, 試行順序: {self.strategy_order}")

        self.best_overall_score = -float('inf')
        self.best_overall_assignment: Dict[str, str] = {}
        self.current_strategy_name: Optional[str] = None

        self.max_optimization_attempts = config.get("adaptive_max_attempts", 3) # 最大試行回数
        logger.debug(f"AdaptiveOptimizer: 最大最適化試行回数: {self.max_optimization_attempts}")

    def _select_strategy(self) -> str:
        """
        現在の戦略の重みに基づいて、次の最適化戦略を選択する。
        ルーレット選択のような確率的選択を行う。
        """
        total_weight = sum(self.strategy_weights.values())
        if total_weight == 0: # 全ての重みが0の場合、均等に選択
            logger.warning("AdaptiveOptimizer: 全ての戦略重みが0です。ランダムに戦略を選択します。")
            return random.choice(list(self.optimizers.keys()))

        r = random.uniform(0, total_weight)
        cumulative_weight = 0.0
        for strategy_name, weight in self.strategy_weights.items():
            cumulative_weight += weight
            if r <= cumulative_weight:
                logger.debug(f"AdaptiveOptimizer: 戦略 '{strategy_name}' を選択しました (重み: {weight:.2f}, 累積重み: {cumulative_weight:.2f}, ランダム値: {r:.2f})")
                return strategy_name
        
        # フォールバック (念のため)
        return random.choice(list(self.optimizers.keys()))

    def _update_strategy_weights(self, strategy_name: str, score: float, duration: float, status: str):
        """
        最適化結果に基づいて戦略の重みを更新する。
        スコアが高いほど、その戦略の重みを増やす。
        実行時間やステータスも考慮に入れることができる。
        """
        current_weight = self.strategy_weights.get(strategy_name, 1.0)
        
        # スコアに基づく報酬
        reward = 0.0
        if status == "OPTIMAL" or status == "FEASIBLE":
            if self.best_overall_score > -float('inf'): # 以前に有効な解が見つかっている場合
                # スコアが全体ベストに近いほど高い報酬
                reward = (score / self.best_overall_score) if self.best_overall_score != 0 else 1.0
                reward = max(0.1, min(10.0, reward)) # 報酬をクリップ
            else: # 初めて有効な解が見つかった場合
                reward = 1.0 # 基本報酬
        elif status == "CANCELLED":
            reward = -0.5 # キャンセルされた場合はペナルティ
        else: # INFEASIBLE, NO_SOLUTION_FOUND, FAILED, ERROR
            reward = -1.0 # 失敗した場合は大きなペナルティ
        
        # 実行時間に基づくペナルティ (オプション)
        # duration_penalty = 0.0
        # if duration > 0:
        #     duration_penalty = min(1.0, duration / self.config.get("adaptive_max_expected_duration", 600)) # 600秒を基準に正規化
        # reward -= duration_penalty * 0.1 # 小さなペナルティとして適用

        new_weight = current_weight + self.learning_rate * reward
        new_weight = max(0.1, new_weight) # 重みが負にならないように最小値を設定
        self.strategy_weights[strategy_name] = new_weight
        
        # 評価履歴を更新
        self.evaluation_history[strategy_name].append(score)
        if len(self.evaluation_history[strategy_name]) > self.max_history_size:
            self.evaluation_history[strategy_name].pop(0) # 古い履歴を削除

        self._log(f"AdaptiveOptimizer: 戦略 '{strategy_name}' の重みを更新しました。報酬: {reward:.2f}, 新しい重み: {new_weight:.2f}")
        logger.debug(f"AdaptiveOptimizer: 戦略重み: {self.strategy_weights}")
        logger.debug(f"AdaptiveOptimizer: 評価履歴 ({strategy_name}): {self.evaluation_history[strategy_name]}")


    def optimize(self, cancel_event: Optional[threading.Event] = None) -> OptimizationResult:
        """
        適応型最適化プロセスを実行する。
        """
        self._log("AdaptiveOptimizer: 最適化を開始します。")
        logger.debug("AdaptiveOptimizer: optimize メソッド呼び出し。")

        attempts = 0
        current_best_result: Optional[OptimizationResult] = None

        while attempts < self.max_optimization_attempts:
            if cancel_event and cancel_event.is_set():
                self._log(f"AdaptiveOptimizer: 最適化がキャンセルされました。")
                logger.info("AdaptiveOptimizer: キャンセルイベントが設定されたため、ループを終了します。")
                break

            attempts += 1
            self._log(f"AdaptiveOptimizer: 最適化試行 {attempts}/{self.max_optimization_attempts}。")
            
            # 初回または重みがリセットされた場合は初期戦略から開始
            if attempts == 1 or sum(self.strategy_weights.values()) == 0:
                self.current_strategy_name = self.initial_strategy
                self._log(f"AdaptiveOptimizer: 初回試行または重みリセットのため、初期戦略 '{self.current_strategy_name}' を選択。")
            else:
                self.current_strategy_name = self._select_strategy()
                self._log(f"AdaptiveOptimizer: 次の戦略 '{self.current_strategy_name}' を選択しました。")

            optimizer = self.optimizers.get(self.current_strategy_name)
            if not optimizer:
                self._log(f"AdaptiveOptimizer: 戦略 '{self.current_strategy_name}' が見つかりません。スキップします。", level=logging.ERROR)
                continue

            try:
                self._log(f"AdaptiveOptimizer: 戦略 '{self.current_strategy_name}' の実行を開始します。")
                strategy_start_time = time.time()
                
                # ILP/CP/MultilevelOptimizerはcancel_eventを受け取る
                if hasattr(optimizer, 'optimize') and 'cancel_event' in optimizer.optimize.__code__.co_varnames:
                    result = optimizer.optimize(cancel_event=cancel_event)
                else:
                    result = optimizer.optimize() # cancel_eventを持たないオプティマイザ
                
                strategy_end_time = time.time()
                strategy_duration = strategy_end_time - strategy_start_time
                self._log(f"AdaptiveOptimizer: 戦略 '{self.current_strategy_name}' の実行が完了しました。ステータス: {result.status}, スコア: {result.best_score:.2f}, 実行時間: {strategy_duration:.2f}秒")
                logger.debug(f"AdaptiveOptimizer: 戦略 '{self.current_strategy_name}' の結果メッセージ: {result.message}")

                # 最適化結果に基づいて戦略の重みを更新
                self._update_strategy_weights(self.current_strategy_name, result.best_score, strategy_duration, result.status)

                if result.status == "OPTIMAL" or result.status == "FEASIBLE":
                    if result.best_score > self.best_overall_score:
                        self.best_overall_score = result.best_score
                        self.best_overall_assignment = result.best_assignment
                        current_best_result = result
                        self._log(f"AdaptiveOptimizer: 新しい全体ベストスコアが見つかりました: {self.best_overall_score:.2f} (戦略: {self.current_strategy_name})")
                        # 最適解が見つかったら、さらなる改善の可能性が低いと判断し、早期終了も検討できる
                        # if self.config.get("adaptive_stop_on_optimal", False) and result.status == "OPTIMAL":
                        #     self._log("AdaptiveOptimizer: 最適解が見つかったため、最適化を早期終了します。")
                        #     break
                
                if result.status == "CANCELLED":
                    self._log(f"AdaptiveOptimizer: 戦略 '{self.current_strategy_name}' がキャンセルされました。")
                    # キャンセルされた場合は、ループを終了する
                    self.current_strategy_name = None # ループ終了
                    break
                
            except Exception as e:
                self._log(f"AdaptiveOptimizer: 戦略 '{self.current_strategy_name}' の実行中にエラーが発生しました: {e}", level=logging.ERROR)
                logger.exception(f"AdaptiveOptimizer: 戦略 '{self.current_strategy_name}' の実行中に予期せぬエラーが発生しました。")
                # エラーが発生した戦略は一時的に利用不可にするか、低い評価を与える
                # 簡単化のため、ここで重みを大幅に減らす
                self._update_strategy_weights(self.current_strategy_name, -float('inf'), 0, "FAILED")
                self.current_strategy_name = None # ループ終了
                break # エラーが発生したら適応型ループを終了

        self._log("AdaptiveOptimizer: 最適化が完了しました。")
        
        status = "NO_SOLUTION_FOUND"
        message = "最適解が見つかりませんでした。"
        unassigned_students: List[str] = []

        if current_best_result is None:
            message = "最適解が見つかりませんでした。"
            status = "FAILED"
            logger.warning("AdaptiveOptimizer: いずれの戦略からも有効な結果が得られませんでした。")
        else:
            message = "最適化が成功しました。"
            status = current_best_result.status # OPTIMAL または FEASIBLE
            unassigned_students = self._get_unassigned_students(self.best_overall_assignment)
            logger.info(f"AdaptiveOptimizer: 最終的なベストスコア: {self.best_overall_score:.2f}, 最終ステータス: {status}")

        return OptimizationResult(
            status=status,
            message=message,
            best_score=self.best_overall_score,
            best_assignment=self.best_overall_assignment if self.best_overall_assignment is not None else {},
            seminar_capacities=self.seminar_capacities,
            unassigned_students=unassigned_students,
            optimization_strategy="Adaptive"
        )
