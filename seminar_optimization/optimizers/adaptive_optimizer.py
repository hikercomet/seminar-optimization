import numpy as np
import random
import time
import logging
import threading
from typing import Dict, List, Tuple, Any, Callable, Optional
from collections import deque

# BaseOptimizerとOptimizationResultをutilsからインポート
from seminar_optimization.seminar_optimization.utils import BaseOptimizer, OptimizationResult
# ロギングは logger_config.py で一元的に設定されるため、ここではロガーの取得のみ
from seminar_optimization.seminar_optimization.logger_config import logger

# 各最適化アルゴリズムをインポート
from seminar_optimization.optimizers.greedy_ls_optimizer import GreedyLSOptimizer
from seminar_optimization.optimizers.genetic_algorithm_optimizer import GeneticAlgorithmOptimizer
from seminar_optimization.optimizers.ilp_optimizer import ILPOptimizer
from seminar_optimization.optimizers.cp_sat_optimizer import CPSATOptimizer
from seminar_optimization.optimizers.multilevel_optimizer import MultilevelOptimizer

# オプティマイザのマッピングを定義
OPTIMIZER_MAP = {
    "Greedy_LS": GreedyLSOptimizer,
    "GA_LS": GeneticAlgorithmOptimizer,
    "ILP": ILPOptimizer,
    "CP": CPSATOptimizer,
    "Multilevel": MultilevelOptimizer
}

class AdaptiveOptimizer(BaseOptimizer):
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
        super().__init__(seminars, students, config, progress_callback)
        self._log("AdaptiveOptimizer: 初期化を開始します。", level=logging.DEBUG)

        # 適応型最適化固有のパラメータ
        self.strategy_history: Dict[str, deque] = {name: deque(maxlen=config.get("adaptive_history_size", 5)) for name in OPTIMIZER_MAP.keys()}
        self.exploration_epsilon = config.get("adaptive_exploration_epsilon", 0.1) # 探索率
        self.learning_rate = config.get("adaptive_learning_rate", 0.2) # 学習率
        
        # パフォーマンス評価の重み
        self.score_weight = config.get("adaptive_score_weight", 0.4) # 合計スコアの重み
        self.unassigned_weight = config.get("adaptive_unassigned_weight", 0.2) # 未割り当て学生数の重み
        self.time_weight = config.get("adaptive_time_weight", 0.1) # 実行時間の重み
        # 第一希望割り当て数から、希望順位満足度に変更
        self.preference_satisfaction_weight = config.get("adaptive_preference_satisfaction_weight", 0.2) # 希望順位満足度の重み (変更)
        self.load_balance_weight = config.get("adaptive_load_balance_weight", 0.05) # セミナー負荷分散の重み
        self.min_satisfaction_weight = config.get("adaptive_min_satisfaction_weight", 0.05) # 最小学生満足度の重み

        # 重みの合計が1になるように調整を推奨
        total_weights = (self.score_weight + self.unassigned_weight + self.time_weight +
                         self.preference_satisfaction_weight + self.load_balance_weight + self.min_satisfaction_weight)
        if abs(total_weights - 1.0) > 1e-6:
            self._log(f"AdaptiveOptimizer: 評価重みの合計が1ではありません ({total_weights:.2f})。調整してください。", level=logging.WARNING)


        self.max_time_for_normalization = config.get("adaptive_max_time_for_normalization", 600) # 時間正規化のための最大時間 (秒)
        self.max_iterations = config.get("adaptive_max_iterations", 5) # 適応型最適化の最大イテレーション数
        self.max_total_time = config.get("adaptive_max_total_time", 600) # 適応型最適化の総時間制限 (秒)

        self.strategy_scores: Dict[str, float] = {name: 0.0 for name in OPTIMIZER_MAP.keys()} # 各戦略の累積スコア
        self.current_strategy_name: Optional[str] = None
        
        # preference_weightsをインスタンス変数として保持
        self.preference_weights = {k: float(v) for k, v in config.get("preference_weights", {}).items()}

        self._log("AdaptiveOptimizer: 適応型最適化の初期化が完了しました。", level=logging.INFO)
        self._log(f"AdaptiveOptimizer: 探索率={self.exploration_epsilon}, 学習率={self.learning_rate}", level=logging.DEBUG)
        self._log(f"AdaptiveOptimizer: 評価重み: スコア={self.score_weight}, 未割り当て={self.unassigned_weight}, 時間={self.time_weight}, 希望満足度={self.preference_satisfaction_weight}, 負荷分散={self.load_balance_weight}, 最小満足度={self.min_satisfaction_weight}", level=logging.DEBUG)


    def _normalize_score(self, score: float, min_score: float, max_score: float) -> float:
        """スコアを0-1の範囲に正規化する"""
        if max_score <= min_score:
            return 0.5 # 変化がない場合は中間値
        return (score - min_score) / (max_score - min_score)

    def _normalize_unassigned(self, unassigned_count: int) -> float:
        """未割り当て数を0-1の範囲に正規化する (少ないほど良いので1-x)"""
        max_unassigned = len(self.student_ids) # 最大未割り当て数は学生総数
        if max_unassigned == 0:
            return 1.0 # 学生がいなければ未割り当ては常に0で最高
        return 1.0 - (unassigned_count / max_unassigned)

    def _normalize_time(self, duration: float) -> float:
        """時間を0-1の範囲に正規化する (短いほど良いので1-x)"""
        normalized_time = min(duration, self.max_time_for_normalization) / self.max_time_for_normalization
        return 1.0 - normalized_time

    def _calculate_preference_satisfaction_score(self, assignment: Dict[str, str]) -> float:
        """
        学生の希望順位に応じた満足度スコアを合計して計算する。
        preference_weights (例: {"1st": 5.0, "2nd": 2.0, "3rd": 1.0}) を参照。
        """
        total_satisfaction_score = 0.0
        for student_id, assigned_seminar_id in assignment.items():
            student_info = next((s for s in self.students if s['id'] == student_id), None)
            if student_info and student_info.get('preferences'):
                for i, pref in enumerate(student_info['preferences']):
                    if pref['seminar_id'] == assigned_seminar_id:
                        rank_key = ""
                        if i == 0: rank_key = "1st"
                        elif i == 1: rank_key = "2nd"
                        elif i == 2: rank_key = "3rd"
                        # 必要に応じて4th, 5thなどを追加
                        # preferencesはconfigでnum_preferences_to_considerが設定されているはず
                        else: rank_key = f"{i+1}th" # その他のランク
                        
                        total_satisfaction_score += self.preference_weights.get(rank_key, 0.0)
                        break # この学生は割り当てが見つかったので次の学生へ
        return total_satisfaction_score

    def _normalize_preference_satisfaction_score(self, current_sat_score: float) -> float:
        """希望順位満足度スコアを0-1の範囲に正規化する"""
        # 全ての学生が第一希望に割り当てられた場合の最大スコア
        max_possible_sat_score = len(self.student_ids) * self.preference_weights.get("1st", 0.0)
        
        if max_possible_sat_score == 0: # 学生がいない、または1stの重みが0の場合
            return 0.5 # 中間値
        
        return current_sat_score / max_possible_sat_score


    def _calculate_seminar_load_balance(self, assignment: Dict[str, str]) -> float:
        """セミナーの負荷分散を計算する (標準偏差が小さいほど良い)"""
        seminar_counts: Dict[str, int] = {s['id']: 0 for s in self.seminars}
        for seminar_id in assignment.values():
            seminar_counts[seminar_id] += 1
        
        # 割り当てられた学生がいるセミナーのみを考慮
        active_seminar_counts = [count for count in seminar_counts.values() if count > 0]
        
        if not active_seminar_counts:
            return 0.0 # 全員未割り当ての場合など、負荷分散の評価ができない
        
        return float(np.std(active_seminar_counts)) # 標準偏差を返す

    def _normalize_load_balance(self, std_dev: float) -> float:
        """セミナー負荷分散の標準偏差を0-1の範囲に正規化する (小さいほど良いので1-x)"""
        # 経験的に、または問題の規模に応じて最大標準偏差を設定
        # ここでは仮に、学生総数の半分を最大値の目安とする
        max_possible_std_dev = len(self.student_ids) / 2 
        if max_possible_std_dev == 0: # 学生がいない場合
            return 1.0
        
        normalized_std_dev = min(std_dev, max_possible_std_dev) / max_possible_std_dev
        return 1.0 - normalized_std_dev

    def _calculate_min_student_satisfaction(self, assignment: Dict[str, str]) -> float:
        """学生ごとの最小満足度スコアを計算する"""
        min_satisfaction = float('inf')
        
        for student_id in self.student_ids:
            assigned_seminar_id = assignment.get(student_id)
            current_student_score = 0.0
            
            if assigned_seminar_id:
                student_info = next((s for s in self.students if s['id'] == student_id), None)
                if student_info and student_info.get('preferences'):
                    for i, pref in enumerate(student_info['preferences']):
                        if pref['seminar_id'] == assigned_seminar_id:
                            rank_key = ""
                            if i == 0: rank_key = "1st"
                            elif i == 1: rank_key = "2nd"
                            elif i == 2: rank_key = "3rd"
                            else: rank_key = f"{i+1}th"
                            current_student_score = self.preference_weights.get(rank_key, 0.0)
                            break
            min_satisfaction = min(min_satisfaction, current_student_score)
        
        return min_satisfaction if min_satisfaction != float('inf') else 0.0

    def _normalize_min_satisfaction(self, min_sat_score: float) -> float:
        """最小学生満足度を0-1の範囲に正規化する"""
        # 最大可能スコアは、preference_weightsで定義された第一希望の重み
        max_possible_min_sat = self.preference_weights.get("1st", 0.0)
        min_possible_min_sat = 0.0 # 最小は0点 (未割り当てなど)

        if max_possible_min_sat <= min_possible_min_sat:
            return 0.5
        return (min_sat_score - min_possible_min_sat) / (max_possible_min_sat - min_possible_min_sat)


    def _update_strategy_performance(self, strategy_name: str, result: OptimizationResult, duration: float):
        """
        各戦略のパフォーマンスを更新する。
        スコア、未割り当て学生数、実行時間、希望順位満足度、セミナー負荷分散、最小学生満足度を考慮して評価する。
        """
        if result.status in ["OPTIMAL", "FEASIBLE"]:
            # スコアの正規化 (これはresult.best_score自体がpreference_weightsで計算されているはずなので、そのままで良い)
            # max_possible_scoreは、全ての学生が第一希望に割り当てられた場合のスコアの合計が妥当
            max_possible_score = sum(self.preference_weights.get("1st", 0.0) for student in self.students if student.get("preferences"))
            if not max_possible_score:
                max_possible_score = 1.0 # ゼロ除算回避
            min_possible_score = 0.0
            normalized_score = self._normalize_score(result.best_score, min_possible_score, max_possible_score)

            # 未割り当て学生数の正規化
            normalized_unassigned = self._normalize_unassigned(len(result.unassigned_students))

            # 時間の正規化
            normalized_time = self._normalize_time(duration)

            # --- 希望順位満足度の計算と正規化 (新規/変更) ---
            current_preference_satisfaction_score = self._calculate_preference_satisfaction_score(result.best_assignment)
            normalized_preference_satisfaction = self._normalize_preference_satisfaction_score(current_preference_satisfaction_score)

            # セミナー負荷分散
            load_balance_std_dev = self._calculate_seminar_load_balance(result.best_assignment)
            normalized_load_balance = self._normalize_load_balance(load_balance_std_dev)

            # 学生ごとの最小満足度
            min_student_satisfaction = self._calculate_min_student_satisfaction(result.best_assignment)
            normalized_min_satisfaction = self._normalize_min_satisfaction(min_student_satisfaction)
            
            # 総合パフォーマンススコアを計算
            performance_score = (
                self.score_weight * normalized_score +
                self.unassigned_weight * normalized_unassigned +
                self.time_weight * normalized_time +
                self.preference_satisfaction_weight * normalized_preference_satisfaction + # ここが変更
                self.load_balance_weight * normalized_load_balance +
                self.min_satisfaction_weight * normalized_min_satisfaction
            )
            
            self.strategy_history[strategy_name].append(performance_score)
            
            if self.strategy_history[strategy_name]:
                avg_performance = sum(self.strategy_history[strategy_name]) / len(self.strategy_history[strategy_name])
            else:
                avg_performance = performance_score

            self.strategy_scores[strategy_name] = (1 - self.learning_rate) * self.strategy_scores[strategy_name] + self.learning_rate * avg_performance
            
            self._log(f"AdaptiveOptimizer: 戦略 '{strategy_name}' のパフォーマンスを更新しました。正規化スコア: {normalized_score:.2f}, 未割り当て: {normalized_unassigned:.2f}, 時間: {normalized_time:.2f}, 希望満足度: {normalized_preference_satisfaction:.2f}, 負荷分散: {normalized_load_balance:.2f}, 最小満足度: {normalized_min_satisfaction:.2f}, 総合パフォーマンス: {performance_score:.2f}, 累積スコア: {self.strategy_scores[strategy_name]:.2f}")
        else:
            self.strategy_scores[strategy_name] = max(0.0, self.strategy_scores[strategy_name] * 0.8 - 0.1)
            self._log(f"AdaptiveOptimizer: 戦略 '{strategy_name}' が失敗しました。累積スコアを調整: {self.strategy_scores[strategy_name]:.2f}", level=logging.INFO)


    def _select_strategy(self) -> str:
        """
        現在のパフォーマンス履歴に基づいて最適な戦略を選択する。
        ε-greedy戦略を使用し、探索と活用のバランスを取る。
        """
        if random.random() < self.exploration_epsilon:
            selected_strategy = random.choice(list(OPTIMIZER_MAP.keys()))
            self._log(f"AdaptiveOptimizer: ε-greedy探索により戦略 '{selected_strategy}' をランダムに選択しました。", level=logging.DEBUG)
        else:
            if all(score == 0.0 for score in self.strategy_scores.values()):
                selected_strategy = random.choice(list(OPTIMIZER_MAP.keys()))
                self._log(f"AdaptiveOptimizer: 全ての戦略スコアが初期値のため、ランダムに戦略 '{selected_strategy}' を選択しました。", level=logging.DEBUG)
            else:
                selected_strategy = max(self.strategy_scores, key=self.strategy_scores.get)
                self._log(f"AdaptiveOptimizer: 活用により戦略 '{selected_strategy}' を選択しました (累積スコア: {self.strategy_scores[selected_strategy]:.2f})。", level=logging.DEBUG)
        
        self.current_strategy_name = selected_strategy
        return selected_strategy

    def optimize(self, cancel_event: Optional[threading.Event] = None) -> OptimizationResult:
        """
        適応型最適化プロセスを実行する。
        各イテレーションで最適な戦略を選択し、実行する。
        所定のイテレーション数または時間制限まで繰り返す。
        """
        start_overall_time = time.time()
        self._log("AdaptiveOptimizer: 適応型最適化を開始します...", level=logging.INFO)

        best_overall_score = -float('inf')
        best_overall_assignment: Dict[str, str] = {}
        final_status = "NO_SOLUTION_FOUND"
        final_message = "適応型最適化で有効な解が見つかりませんでした。"
        final_strategy_used = "N/A"

        for i in range(self.max_iterations):
            if cancel_event and cancel_event.is_set():
                self._log("AdaptiveOptimizer: 全体最適化がキャンセルされました。", level=logging.INFO)
                final_status = "CANCELLED"
                final_message = "最適化がユーザーによってキャンセルされました。"
                break
            
            if (time.time() - start_overall_time) > self.max_total_time:
                self._log(f"AdaptiveOptimizer: 総時間制限 ({self.max_total_time}秒) に達しました。", level=logging.INFO)
                final_status = "TIME_LIMIT_EXCEEDED"
                final_message = "最適化が時間制限により終了しました。"
                break

            self.current_strategy_name = self._select_strategy()
            self._log(f"AdaptiveOptimizer: イテレーション {i+1}/{self.max_iterations}: 戦略 '{self.current_strategy_name}' を試行します。", level=logging.INFO)

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

            self._log(f"AdaptiveOptimizer: 戦略 '{self.current_strategy_name}' 完了。ステータス: {current_result.status}, スコア: {current_result.best_score:.2f}, 時間: {duration:.2f}秒", level=logging.INFO)

            self._update_strategy_performance(self.current_strategy_name, current_result, duration)

            if current_result.status in ["OPTIMAL", "FEASIBLE"] and current_result.best_score > best_overall_score:
                best_overall_score = current_result.best_score
                best_overall_assignment = current_result.best_assignment
                final_status = current_result.status
                final_message = f"最適化が成功しました (戦略: {self.current_strategy_name})"
                final_strategy_used = self.current_strategy_name
                self._log(f"AdaptiveOptimizer: 全体的なベストスコアを更新: {best_overall_score:.2f} (戦略: {self.current_strategy_name})", level=logging.INFO)

        self._log("AdaptiveOptimizer: 最適化が完了しました。", level=logging.INFO)
        
        if not best_overall_assignment:
            final_message = "いずれの戦略からも有効な解が見つかりませんでした。"
            final_status = "NO_SOLUTION_FOUND"
            self._log("AdaptiveOptimizer: いずれの戦略からも有効な結果が得られませんでした。", level=logging.WARNING)
        
        unassigned_students: List[str] = []
        if best_overall_assignment:
            unassigned_students = self._get_unassigned_students(best_overall_assignment)
            self._log(f"AdaptiveOptimizer: 最終的なベストスコア: {best_overall_score:.2f}, 最終ステータス: {final_status}, 未割り当て学生数: {len(unassigned_students)}", level=logging.INFO)

        if cancel_event and cancel_event.is_set():
            final_status = "CANCELLED"
            final_message = "最適化がユーザーによってキャンセルされました。"
            best_overall_score = -float('inf')
            unassigned_students = self.student_ids

        return OptimizationResult(
            status=final_status,
            message=final_message,
            best_score=best_overall_score,
            best_assignment=best_overall_assignment,
            seminar_capacities=self.seminar_capacities,
            unassigned_students=unassigned_students,
            optimization_strategy=final_strategy_used
        )