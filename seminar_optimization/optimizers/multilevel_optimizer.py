import logging
import random
import copy
import threading
import time
from typing import Dict, List, Any, Callable, Optional, Tuple
from sklearn.cluster import KMeans # クラスタリング用
import numpy as np # KMeansの入力用

# BaseOptimizerとOptimizationResultをutilsからインポート
from utils import BaseOptimizer, OptimizationResult

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) # DEBUGレベルのメッセージも出力

class MultilevelOptimizer(BaseOptimizer): # BaseOptimizerを継承
    """
    多段階最適化アルゴリズム。
    学生をクラスタリングし、各クラスタ内で最適化を行った後、
    全体で局所探索を行う。
    """
    def __init__(self,
                 seminars: List[Dict[str, Any]],
                 students: List[Dict[str, Any]],
                 config: Dict[str, Any],\
                 progress_callback: Optional[Callable[[str], None]] = None): # progress_callbackを追加
        # BaseOptimizerの__init__を呼び出す
        super().__init__(seminars, students, config, progress_callback)
        logger.debug("MultilevelOptimizer: 初期化を開始します。")

        # 固有のパラメータはconfigから取得
        self.num_clusters = config.get("multilevel_clusters", 5)
        self.local_search_iterations = config.get("local_search_iterations", 5000)
        self.no_improvement_limit = config.get("no_improvement_limit", 1000) # 局所探索の改善停止条件
        logger.debug(f"MultilevelOptimizer: クラスタ数: {self.num_clusters}, 局所探索イテレーション: {self.local_search_iterations}, 改善なし停止リミット: {self.no_improvement_limit}")

        # K-MeansのためのセミナーIDからインデックスへのマッピング
        self.seminar_to_idx = {seminar_id: i for i, seminar_id in enumerate(self.seminar_ids)}
        self.idx_to_seminar = {i: seminar_id for i, seminar_id in enumerate(self.seminar_ids)}
        logger.debug(f"MultilevelOptimizer: セミナーID-インデックスマッピング: {self.seminar_to_idx}")

    def _get_student_preference_vector(self, student_id: str) -> np.ndarray:
        """
        学生の希望をベクトル表現に変換する。
        各セミナーに対する希望度を数値化する。
        例: [1, 0.5, 0.2, 0, ...] (1位希望、2位希望、3位希望、それ以外)
        """
        vector = np.zeros(len(self.seminar_ids))
        preferences = self.student_preferences.get(student_id, [])
        
        # スコア計算の重み付けをconfigから取得、デフォルト値を設定
        score_weights = self.config.get("score_weights", {
            "1st_choice": 3.0,
            "2nd_choice": 2.0,
            "3rd_choice": 1.0,
            "other_preference": 0.5
        })
        
        for i, pref_seminar_id in enumerate(preferences):
            if pref_seminar_id in self.seminar_to_idx:
                idx = self.seminar_to_idx[pref_seminar_id]
                if i == 0: # 1st choice
                    vector[idx] = score_weights["1st_choice"]
                elif i == 1: # 2nd choice
                    vector[idx] = score_weights["2nd_choice"]
                elif i == 2: # 3rd choice
                    vector[idx] = score_weights["3rd_choice"]
                else: # other preferences
                    vector[idx] = score_weights["other_preference"]
        logger.debug(f"学生 {student_id} の希望ベクトルを生成しました。")
        return vector

    def _cluster_students(self) -> Dict[int, List[str]]:
        """
        K-Meansクラスタリングを用いて学生をクラスタに分割する。
        """
        self._log(f"Multilevel: 学生を {self.num_clusters} 個のクラスタに分割中...")
        if len(self.student_ids) < self.num_clusters:
            logger.warning(f"学生数 ({len(self.student_ids)}) がクラスタ数 ({self.num_clusters}) より少ないため、クラスタ数を学生数に調整します。")
            self.num_clusters = len(self.student_ids)
            if self.num_clusters == 0:
                return {} # 学生がいない場合は空の辞書を返す

        # 学生の希望ベクトルを生成
        student_vectors = []
        for student_id in self.student_ids:
            student_vectors.append(self._get_student_preference_vector(student_id))
        
        if not student_vectors:
            logger.warning("学生データが空のため、クラスタリングできません。")
            return {}

        X = np.array(student_vectors)

        # K-Meansモデルの初期化と学習
        kmeans = KMeans(n_clusters=self.num_clusters, random_state=0, n_init=10) # n_initを追加
        kmeans.fit(X)
        logger.debug("MultilevelOptimizer: K-Meansクラスタリングを実行しました。")

        # クラスタ結果を辞書に格納
        clusters: Dict[int, List[str]] = {i: [] for i in range(self.num_clusters)}
        for i, student_id in enumerate(self.student_ids):
            cluster_id = kmeans.labels_[i]
            clusters[cluster_id].append(student_id)
        
        self._log(f"Multilevel: 学生を {self.num_clusters} 個のクラスタに分割しました。")
        for cluster_id, s_ids in clusters.items():
            logger.debug(f"  クラスタ {cluster_id}: {len(s_ids)} 人の学生")
        return clusters

    def _local_search_within_cluster(self, 
                                     current_assignment: Dict[str, str], 
                                     cluster_students: List[str],
                                     cancel_event: threading.Event
                                     ) -> Dict[str, str]:
        """
        特定のクラスタ内の学生に焦点を当てた局所探索。
        """
        local_assignment = current_assignment.copy()
        current_score = self._calculate_score(local_assignment)
        logger.debug(f"クラスタ内局所探索を開始。クラスタ学生数: {len(cluster_students)}, 初期スコア: {current_score:.2f}")

        no_improvement_count = 0
        for i in range(self.local_search_iterations):
            if cancel_event.is_set():
                logger.info("クラスタ内局所探索: キャンセルイベントが設定されたため終了します。")
                break
            
            # ランダムな学生を選び、現在の割り当てから削除
            student_to_move_id = random.choice(cluster_students)
            original_seminar_id = local_assignment.pop(student_to_move_id, None)

            # その学生をランダムなセミナーに割り当てる (または未割り当てのままにする)
            # この段階では、クラスタ内の学生に焦点を当てるが、割り当て先は全体のセミナー
            possible_seminars = list(self.seminar_ids) + [None] 
            random.shuffle(possible_seminars)

            found_better_move = False
            for new_seminar_id in possible_seminars:
                neighbor_assignment = local_assignment.copy()
                if new_seminar_id is not None:
                    neighbor_assignment[student_to_move_id] = new_seminar_id
                
                # 新しい割り当てが実行可能かチェック
                if self._is_feasible_assignment(neighbor_assignment):
                    neighbor_score = self._calculate_score(neighbor_assignment)
                    if neighbor_score > current_score:
                        current_score = neighbor_score
                        local_assignment = neighbor_assignment.copy()
                        no_improvement_count = 0
                        found_better_move = True
                        logger.debug(f"クラスタ内局所探索: 改善が見られました。学生 {student_to_move_id} を {original_seminar_id} から {new_seminar_id} へ。新スコア: {current_score:.2f}")
                        break
            
            if not found_better_move:
                no_improvement_count += 1
                if original_seminar_id is not None: # 元の割り当てに戻す
                    local_assignment[student_to_move_id] = original_seminar_id
                logger.debug(f"クラスタ内局所探索: 学生 {student_to_move_id} の移動で改善なし。連続改善なしカウント: {no_improvement_count}")

            if no_improvement_count >= self.no_improvement_limit:
                logger.debug(f"クラスタ内局所探索: {self.no_improvement_limit}回改善が見られなかったため、早期終了します。")
                break
        
        logger.debug(f"クラスタ内局所探索完了。最終スコア: {current_score:.2f}")
        return local_assignment

    def _global_local_search(self, 
                             initial_assignment: Dict[str, str], 
                             progress_callback: Optional[Callable[[str], None]],
                             cancel_event: threading.Event
                             ) -> Tuple[Dict[str, str], float]:
        """
        全体の割り当てに対して局所探索を行う。
        """
        self._log("Multilevel: グローバル局所探索で解を改善中...")
        current_assignment = initial_assignment.copy()
        current_score = self._calculate_score(current_assignment)
        best_assignment = current_assignment.copy()
        best_score = current_score
        
        no_improvement_count = 0
        logger.info(f"グローバル局所探索開始時のスコア: {best_score:.2f}")

        for i in range(self.local_search_iterations):
            if cancel_event.is_set():
                self._log("Multilevel: グローバル局所探索がキャンセルされました。")
                logger.info("グローバル局所探索: キャンセルイベントが設定されたため終了します。")
                break

            if i % 5000 == 0: # 5000イテレーションごとに進捗を報告
                self._log(f"Multilevel: グローバル局所探索イテレーション {i}/{self.local_search_iterations} (現在のベストスコア: {best_score:.2f})")
                logger.debug(f"グローバル局所探索: 現在の割り当ての実行可能性チェック: {self._is_feasible_assignment(current_assignment)}")

            # 近傍解の生成戦略 (ランダムな学生を別のセミナーに移動)
            if not current_assignment: # 割り当てが空の場合の例外処理
                student_to_move_id = random.choice(self.student_ids)
                original_seminar_id = None
            else:
                student_to_move_id = random.choice(list(current_assignment.keys()))
                original_seminar_id = current_assignment.pop(student_to_move_id)

            temp_assignment = current_assignment.copy()

            possible_seminars = list(self.seminar_ids) + [None] 
            random.shuffle(possible_seminars)

            found_better_neighbor = False
            for new_seminar_id in possible_seminars:
                neighbor_assignment = temp_assignment.copy()
                if new_seminar_id is not None:
                    neighbor_assignment[student_to_move_id] = new_seminar_id
                
                # 新しい割り当てが実行可能かチェック
                if self._is_feasible_assignment(neighbor_assignment):
                    neighbor_score = self._calculate_score(neighbor_assignment)
                    logger.debug(f"グローバル局所探索イテレーション {i}: 学生 {student_to_move_id} を {original_seminar_id} から {new_seminar_id} へ移動を試行。スコア: {neighbor_score:.2f}")

                    if neighbor_score > best_score:
                        best_score = neighbor_score
                        best_assignment = neighbor_assignment.copy()
                        no_improvement_count = 0 # 改善が見られたのでカウントをリセット
                        found_better_neighbor = True
                        logger.info(f"グローバル局所探索: スコアが改善しました！新しいベストスコア: {best_score:.2f} (イテレーション {i})")
                        break # より良い解が見つかったので、この学生の移動はこれで確定
            
            if not found_better_neighbor:
                no_improvement_count += 1
                if original_seminar_id is not None: # 元の割り当てに戻す
                    current_assignment[student_to_move_id] = original_seminar_id
                logger.debug(f"グローバル局所探索イテレーション {i}: 改善が見られませんでした。連続改善なしカウント: {no_improvement_count}")

            if no_improvement_count >= self.no_improvement_limit:
                self._log(f"Multilevel: グローバル局所探索で {self.no_improvement_limit}回改善が見られなかったため、早期終了します。")
                logger.info(f"グローバル局所探索: 早期終了時のベストスコア: {best_score:.2f}")
                break
            
            # 現在の割り当てを更新 (ここでは、常にベストなものに更新する戦略)
            current_assignment = best_assignment.copy()
            current_score = best_score

        self._log(f"Multilevel: グローバル局所探索完了。最終ベストスコア: {best_score:.2f}")
        logger.debug(f"グローバル局所探索: 最終割り当ての実行可能性チェック: {self._is_feasible_assignment(best_assignment)}")
        return best_assignment, best_score


    def optimize(self, cancel_event: Optional[threading.Event] = None) -> OptimizationResult:
        """
        多段階最適化を実行する。
        """
        self._log("Multilevel 最適化を開始します。")
        start_time = time.time()
        logger.debug("MultilevelOptimizer: optimize メソッド呼び出し。")

        if not self.student_ids:
            self._log("Multilevel: 学生データがありません。最適化をスキップします。", level=logging.WARNING)
            return OptimizationResult(
                status="NO_SOLUTION_FOUND",
                message="学生データが提供されていません。",
                best_score=-float('inf'),
                best_assignment={},
                seminar_capacities=self.seminar_capacities,
                unassigned_students=self.student_ids,
                optimization_strategy="Multilevel"
            )

        if len(self.student_ids) < self.num_clusters:
            self._log(f"Multilevel: 学生数 ({len(self.student_ids)}) がクラスタ数 ({self.num_clusters}) より少ないため、クラスタ数を学生数に調整します。", level=logging.WARNING)
            self.num_clusters = len(self.student_ids)
            if self.num_clusters == 0: # 学生が0人の場合
                 return OptimizationResult(
                    status="NO_SOLUTION_FOUND",
                    message="学生データが提供されていません。",
                    best_score=-float('inf'),
                    best_assignment={},
                    seminar_capacities=self.seminar_capacities,
                    unassigned_students=self.student_ids,
                    optimization_strategy="Multilevel"
                )

        # ステップ1: 学生をクラスタリング
        clusters = self._cluster_students()
        if not clusters:
            self._log("Multilevel: クラスタリングに失敗しました。最適化を終了します。", level=logging.ERROR)
            return OptimizationResult(
                status="FAILED",
                message="クラスタリングに失敗しました。",
                best_score=-float('inf'),
                best_assignment={},
                seminar_capacities=self.seminar_capacities,
                unassigned_students=self.student_ids,
                optimization_strategy="Multilevel"
            )
        
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

        # ステップ2: 各クラスタ内で局所探索
        overall_initial_assignment: Dict[str, str] = {}
        self._log("Multilevel: 各クラスタ内で局所探索を実行中...")
        for cluster_id, students_in_cluster in clusters.items():
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
            
            self._log(f"Multilevel: クラスタ {cluster_id} ({len(students_in_cluster)} 学生) の局所探索を開始します。")
            # 各クラスタの学生に焦点を当てた初期割り当てを生成（ここではランダムに割り当ててから修復）
            # または、既存の全体割り当ての一部として扱う
            temp_assignment_for_cluster = {s_id: random.choice(self.seminar_ids) for s_id in students_in_cluster}
            temp_assignment_for_cluster = self._repair_assignment(temp_assignment_for_cluster) # クラスタ内の初期割り当てを修復

            # クラスタ内局所探索を実行
            cluster_optimized_assignment = self._local_search_within_cluster(temp_assignment_for_cluster, students_in_cluster, cancel_event)
            
            # 全体割り当てに統合
            overall_initial_assignment.update(cluster_optimized_assignment)
            self._log(f"Multilevel: クラスタ {cluster_id} の局所探索が完了しました。")
            logger.debug(f"Multilevel: クラスタ {cluster_id} の割り当て学生数: {len(cluster_optimized_assignment)}")

        # 全体割り当ての実行可能性を再確認し、必要であれば修復
        overall_initial_assignment = self._repair_assignment(overall_initial_assignment)
        self._log(f"Multilevel: 全クラスタの割り当てを統合し、初期グローバル割り当てを生成しました。割り当て学生数: {len(overall_initial_assignment)}")
        logger.debug(f"Multilevel: 統合された初期割り当ての実行可能性: {self._is_feasible_assignment(overall_initial_assignment)}")

        if cancel_event and cancel_event.is_set():
            self._log("Multilevel 最適化がキャンセルされました。")
            return OptimizationResult(\
                status="CANCELLED",
                message="最適化がユーザーによってキャンセルされました。",
                best_score=-float('inf'),
                best_assignment={},
                seminar_capacities=self.seminar_capacities,
                unassigned_students=self.student_ids,
                optimization_strategy="Multilevel"
            )

        # ステップ3: 全体で局所探索
        self._log("グローバル局所探索で解を改善中...")
        final_assignment, final_score = self._global_local_search(overall_initial_assignment, self.progress_callback, cancel_event)

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

