import random
import copy
import threading
import time
from typing import Dict, List, Any, Callable, Optional, Tuple
from sklearn.cluster import KMeans # クラスタリング用
import numpy as np # KMeansの入力用

# BaseOptimizerとOptimizationResultをutilsからインポート
from seminar_optimization.utils import BaseOptimizer, OptimizationResult
# ロギングは logger_config.py で一元的に設定されるため、ここではロガーの取得のみ
from seminar_optimization.logger_config import logger

class MultilevelOptimizer(BaseOptimizer): # BaseOptimizerを継承
    """
    多段階最適化アルゴリズム。
    学生をクラスタリングし、各クラスタ内で最適化を行った後、
    全体で局所探索を行う。
    """
    def __init__(self,
                 seminars: List[Dict[str, Any]],
                 students: List[Dict[str, Any]],
                 config: Dict[str, Any],
                 progress_callback: Optional[Callable[[str], None]] = None): # progress_callbackを追加
        # BaseOptimizerの__init__を呼び出す
        super().__init__(seminars, students, config, progress_callback)
        logger.debug("MultilevelOptimizer: 初期化を開始します。")

        # 固有のパラメータはconfigから取得
        self.num_clusters = config.get("multilevel_clusters", 5)
        self.local_search_iterations = config.get("local_search_iterations", 5000)
        self.no_improvement_limit = config.get("early_stop_no_improvement_limit", 500) # 局所探索の早期停止リミット
        logger.debug(f"MultilevelOptimizer: クラスタ数: {self.num_clusters}, 局所探索イテレーション: {self.local_search_iterations}, 改善停止リミット: {self.no_improvement_limit}")

    def _cluster_students(self) -> Dict[int, List[str]]:
        """
        学生の希望に基づいて学生をクラスタリングする。
        各学生の希望セミナーをone-hotエンコーディングし、KMeansを使用する。
        """
        logger.debug("MultilevelOptimizer: 学生のクラスタリングを開始します。")
        if not self.student_ids or not self.seminar_ids:
            logger.warning("MultilevelOptimizer: 学生またはセミナーのデータがないため、クラスタリングをスキップします。")
            return {0: list(self.student_ids)} # 全員を単一クラスタに

        # 学生の希望をベクトル化（one-hotエンコーディング）
        student_vectors = []
        seminar_id_to_idx = {s_id: i for i, s_id in enumerate(self.seminar_ids)}
        
        for student_id in self.student_ids:
            vector = [0] * len(self.seminar_ids)
            preferences = self.student_preferences.get(student_id, [])
            for pref_seminar_id in preferences:
                if pref_seminar_id in seminar_id_to_idx:
                    vector[seminar_id_to_idx[pref_seminar_id]] = 1 # 希望するセミナーに1を設定
            student_vectors.append(vector)
        
        if not student_vectors:
            logger.warning("MultilevelOptimizer: 学生ベクトルが生成されませんでした。クラスタリングをスキップします。")
            return {0: list(self.student_ids)} # 全員を単一クラスタに

        X = np.array(student_vectors)

        # クラスタ数が学生数を超える場合は、学生数に合わせる
        n_clusters = min(self.num_clusters, len(self.student_ids))
        if n_clusters <= 1:
            logger.info("MultilevelOptimizer: クラスタ数が1以下または学生数以下のため、クラスタリングを行わず全員を単一クラスタとします。")
            return {0: list(self.student_ids)}

        kmeans = KMeans(n_clusters=n_clusters, random_state=self.config.get("random_seed"), n_init='auto')
        kmeans.fit(X)
        
        clusters: Dict[int, List[str]] = {i: [] for i in range(n_clusters)}
        for i, student_id in enumerate(self.student_ids):
            clusters[kmeans.labels_[i]].append(student_id)
        
        logger.info(f"MultilevelOptimizer: 学生を {n_clusters} 個のクラスタにクラスタリングしました。")
        for cluster_id, students_in_cluster in clusters.items():
            logger.debug(f"  クラスタ {cluster_id}: {len(students_in_cluster)} 人の学生")
        return clusters

    def _local_search_multilevel(self, initial_assignment: Dict[str, str], progress_callback: Optional[Callable[[str], None]] = None, cancel_event: Optional[threading.Event] = None) -> Tuple[Dict[str, str], float]:
        """
        多段階最適化の最終段階で行う局所探索。
        焼きなまし法を適用して、より広範囲の探索を可能にする。
        """
        logger.debug("MultilevelOptimizer: 多段階局所探索（焼きなまし法）を開始します。")
        current_assignment = initial_assignment.copy()
        current_score = self._calculate_score(current_assignment)
        best_assignment = current_assignment.copy()
        best_score = current_score

        temperature = self.config.get("initial_temperature", 1.0)
        cooling_rate = self.config.get("cooling_rate", 0.995)
        
        no_improvement_count = 0

        self._log(f"Multilevel: 最終局所探索（焼きなまし法）開始。初期スコア: {current_score:.2f}")

        for i in range(self.local_search_iterations):
            if cancel_event and cancel_event.is_set():
                self._log(f"Multilevel: 局所探索がイテレーション {i} でキャンセルされました。")
                break

            if (i + 1) % 1000 == 0:
                self._log(f"Multilevel: 局所探索イテレーション {i+1}/{self.local_search_iterations}。現在のベストスコア: {best_score:.2f}, 温度: {temperature:.4f}")

            # 近傍解の生成 (ランダムな学生の割り当てを変更)
            if not self.student_ids: # 学生がいない場合
                break
            student_id = random.choice(self.student_ids)
            
            # 割り当て変更の候補を生成
            # 1. 現在の割り当てを解除（未割り当てにする）
            # 2. 別のセミナーに移動
            
            original_seminar = current_assignment.get(student_id)
            
            candidate_assignments = []

            # オプション1: 未割り当てにする
            temp_assignment_unassigned = current_assignment.copy()
            if student_id in temp_assignment_unassigned:
                del temp_assignment_unassigned[student_id]
            if self._is_feasible_assignment(temp_assignment_unassigned):
                candidate_assignments.append(temp_assignment_unassigned)

            # オプション2: 別のセミナーに割り当てる
            for seminar_id in self.seminar_ids:
                if seminar_id == original_seminar: # 同じセミナーはスキップ
                    continue
                temp_assignment_move = current_assignment.copy()
                temp_assignment_move[student_id] = seminar_id
                
                if self._is_feasible_assignment(temp_assignment_move):
                    candidate_assignments.append(temp_assignment_move)
            
            if not candidate_assignments:
                continue # 有効な近傍解がない場合

            # ランダムに近傍解を一つ選択
            next_assignment = random.choice(candidate_assignments)
            next_score = self._calculate_score(next_assignment)

            # 焼きなまし法の判定基準
            # (next_score - current_score) > 0 はスコア改善
            # exp((next_score - current_score) / temperature) は悪化を受け入れる確率
            if next_score > current_score or \
               random.random() < np.exp((next_score - current_score) / temperature):
                current_assignment = next_assignment
                current_score = next_score
                logger.debug(f"Multilevel: 割り当てを更新。現在のスコア: {current_score:.2f}")

                if current_score > best_score:
                    best_score = current_score
                    best_assignment = current_assignment.copy()
                    no_improvement_count = 0
                    logger.debug(f"Multilevel: ベストスコアを更新: {best_score:.2f}")
                else:
                    no_improvement_count += 1
            else:
                no_improvement_count += 1

            # 温度の冷却
            temperature *= cooling_rate

            # 早期停止
            if no_improvement_count >= self.no_improvement_limit:
                self._log(f"Multilevel: {self.no_improvement_limit} イテレーションの間改善がなかったため、早期停止します。")
                break

        logger.info(f"MultilevelOptimizer: 多段階局所探索が完了しました。最終ベストスコア: {best_score:.2f}")
        return best_assignment, best_score

    def optimize(self, cancel_event: Optional[threading.Event] = None) -> OptimizationResult:
        """
        多段階最適化プロセスを実行する。
        """
        start_time = time.time()
        self._log("Multilevel 最適化を開始します...")

        # 1. 学生のクラスタリング
        clusters = self._cluster_students()
        
        # 2. 各クラスタ内で初期割り当てを生成（簡易的な貪欲法）
        # ここでは、各クラスタの学生をランダムな順序で、利用可能なセミナーに割り当てる
        # クラスタ内での最適化は、より洗練されたアルゴリズム（例: Greedy_LS）を呼び出すことも可能だが、
        # シンプルさのためここでは簡易的な割り当てを行う
        initial_assignment: Dict[str, str] = {}
        seminar_current_counts = {s_id: 0 for s_id in self.seminar_ids}

        for cluster_id, student_ids_in_cluster in clusters.items():
            self._log(f"Multilevel: クラスタ {cluster_id} の学生を初期割り当て中...")
            random.shuffle(student_ids_in_cluster) # クラスタ内の学生もシャッフル

            for student_id in student_ids_in_cluster:
                preferences = self.student_preferences.get(student_id, [])
                assigned = False
                for preferred_seminar_id in preferences:
                    capacity = self.seminar_capacities.get(preferred_seminar_id)
                    if capacity is not None and seminar_current_counts[preferred_seminar_id] < capacity:
                        initial_assignment[student_id] = preferred_seminar_id
                        seminar_current_counts[preferred_seminar_id] += 1
                        assigned = True
                        break
                if not assigned:
                    pass # 未割り当てのままにする

        self._log(f"Multilevel: 全クラスタの初期割り当てが完了しました。割り当てられた学生数: {len(initial_assignment)}")
        
        # 3. 全体で局所探索（焼きなまし法）
        final_assignment, final_score = self._local_search_multilevel(initial_assignment, self.progress_callback, cancel_event)

        if cancel_event and cancel_event.is_set():
            self._log("Multilevel 最適化がキャンセルされました。")
            return OptimizationResult(
                status="CANCELLED",
                message="最適化がユーザーによってキャンセルされました。",
                best_score=-float('inf'),
                best_assignment={},
                seminar_capacities=self.seminar_capacities,
                unassigned_students=self.student_ids,
                optimization_strategy="Multilevel"
            )

        end_time = time.time()
        duration = end_time - start_time
        self._log(f"Multilevel 最適化完了。実行時間: {duration:.2f}秒")
        logger.info(f"Multilevel: 最終スコア: {final_score:.2f}")

        status_str = "OPTIMAL" if final_score > -float('inf') else "NO_SOLUTION_FOUND"
        message_str = "多段階最適化が成功しました。" if final_score > -float('inf') else "多段階最適化で有効な解が見つかりませんでした。"
        unassigned_students_list = self._get_unassigned_students(final_assignment)
        logger.debug(f"Multilevel: 最終割り当ての実行可能性チェック: {self._is_feasible_assignment(final_assignment)}")

        return OptimizationResult(
            status=status_str,
            message=message_str,
            best_score=final_score,
            best_assignment=final_assignment,
            seminar_capacities=self.seminar_capacities,
            unassigned_students=unassigned_students_list,
            optimization_strategy="Multilevel"
        )
