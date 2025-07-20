import logging
import random
import copy
import threading
import time
from typing import Dict, List, Any, Callable, Optional, Tuple
from sklearn.cluster import KMeans # クラスタリング用

# BaseOptimizerとOptimizationResultをutilsからインポート
from utils import BaseOptimizer, OptimizationResult

logger = logging.getLogger(__name__)

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

        # 固有のパラメータはconfigから取得
        self.num_clusters = config.get("multilevel_clusters", 5)
        self.local_search_iterations = config.get("local_search_iterations", 5000)
        self.no_improvement_limit = config.get("no_improvement_limit", 1000) # 局所探索の改善停止条件

        # K-MeansのためのセミナーIDからインデックスへのマッピング
        self.seminar_to_idx = {seminar_id: i for i, seminar_id in enumerate(self.seminar_ids)}
        self.idx_to_seminar = {i: seminar_id for seminar_id, i in self.seminar_to_idx.items()}

    # _calculate_score, _is_feasible_assignment, _get_unassigned_students はBaseOptimizerから継承されるため削除

    def _get_student_preference_vector(self, student_id: str) -> List[int]:
        """
        学生の希望をベクトル表現に変換する。
        各セミナーIDに対応する位置に希望順位の重みを設定する。
        """
        vector = [0] * len(self.seminar_ids)
        preferences = self.student_preferences.get(student_id, [])
        for rank, seminar_id in enumerate(preferences):
            if seminar_id in self.seminar_to_idx:
                # 希望順位に応じて重み付け（例: 1st=3, 2nd=2, 3rd=1）
                weight = 0
                if rank == 0: weight = 3
                elif rank == 1: weight = 2
                elif rank == 2: weight = 1
                vector[self.seminar_to_idx[seminar_id]] = weight
        return vector

    def _cluster_students(self) -> Dict[int, List[Dict[str, Any]]]:
        """
        学生を希望に基づいてクラスタリングする。
        """
        if len(self.students) < self.num_clusters:
            self._log(f"学生数 ({len(self.students)}) がクラスタ数 ({self.num_clusters}) より少ないため、クラスタリングをスキップします。", level=logging.WARNING)
            # クラスタリングできない場合は、全学生を単一のクラスタに入れる
            return {0: self.students}

        self._log(f"{len(self.students)}人の学生を{self.num_clusters}個のクラスタにクラスタリング中...")
        student_vectors = []
        student_id_map = {}
        for student in self.students:
            student_id = student['id']
            student_vectors.append(self._get_student_preference_vector(student_id))
            student_id_map[student_id] = student

        kmeans = KMeans(n_clusters=self.num_clusters, random_state=42, n_init=10)
        cluster_labels = kmeans.fit_predict(student_vectors)

        clustered_students: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(self.num_clusters)}
        for i, student in enumerate(self.students):
            clustered_students[cluster_labels[i]].append(student)

        self._log(f"クラスタリング完了。クラスタごとの学生数: {[len(v) for v in clustered_students.values()]}")
        return clustered_students

    def _optimize_cluster(self, students_in_cluster: List[Dict[str, Any]],
                          progress_callback: Callable[[str], None],
                          cancel_event: threading.Event) -> Dict[str, str]:
        """
        単一のクラスタ内で最適化を行う（ここでは簡易的な局所探索を使用）。
        より複雑なオプティマイザ（例: GreedyLSOptimizer）を呼び出すことも可能。
        """
        if not students_in_cluster:
            return {}

        self._log(f"クラスタ最適化開始: 学生数 {len(students_in_cluster)}")
        current_assignment = {}
        # 各学生を希望順に割り当てていく初期解生成
        for student in students_in_cluster:
            student_id = student['id']
            assigned = False
            for preferred_seminar_id in student['preferences']:
                if preferred_seminar_id in self.seminar_capacities:
                    # 仮割り当てを試みる
                    temp_assignment = current_assignment.copy()
                    temp_assignment[student_id] = preferred_seminar_id
                    if self._is_feasible_assignment(temp_assignment): # BaseOptimizerから継承
                        current_assignment[student_id] = preferred_seminar_id
                        assigned = True
                        break
            if not assigned:
                # 希望するセミナーに割り当てられなかった場合、ランダムに空きのあるセミナーに割り当てる
                # ただし、ここではシンプルに未割り当てのままにする
                pass # current_assignmentには追加しない

        # 初期解のスコアを計算
        best_assignment = current_assignment.copy()
        best_score = self._calculate_score(best_assignment) # BaseOptimizerから継承

        # 局所探索（ここでは簡易的なスワップ）
        no_improvement_count = 0
        for i in range(self.local_search_iterations):
            if cancel_event.is_set():
                self._log("クラスタ最適化がキャンセルされました。")
                return {}

            student_id1 = random.choice(list(best_assignment.keys()))
            seminar_id1 = best_assignment[student_id1]

            # 別の学生とセミナーをスワップ
            student_id2 = random.choice(list(best_assignment.keys()))
            seminar_id2 = best_assignment[student_id2]

            if student_id1 == student_id2:
                continue

            temp_assignment = best_assignment.copy()
            temp_assignment[student_id1] = seminar_id2
            temp_assignment[student_id2] = seminar_id1

            if self._is_feasible_assignment(temp_assignment): # BaseOptimizerから継承
                new_score = self._calculate_score(temp_assignment) # BaseOptimizerから継承
                if new_score > best_score:
                    best_score = new_score
                    best_assignment = temp_assignment
                    no_improvement_count = 0
                    # self._log(f"クラスタ局所探索: スコア改善 {new_score:.2f}", level=logging.DEBUG)
                else:
                    no_improvement_count += 1
            else:
                no_improvement_count += 1

            if no_improvement_count >= self.no_improvement_limit:
                self._log(f"クラスタ局所探索: {self.no_improvement_limit}回改善が見られなかったため、早期終了します。")
                break
        
        self._log(f"クラスタ最適化完了: 学生数 {len(students_in_cluster)}, 最終スコア {best_score:.2f}")
        return best_assignment

    def _global_local_search(self, initial_assignment: Dict[str, str],
                             progress_callback: Callable[[str], None],
                             cancel_event: threading.Event) -> Tuple[Dict[str, str], float]:
        """
        全体的な局所探索を実行して、解をさらに改善する。
        """
        self._log("グローバル局所探索を開始します。")
        best_assignment = initial_assignment.copy()
        best_score = self._calculate_score(best_assignment) # BaseOptimizerから継承
        
        no_improvement_count = 0
        for i in range(self.local_search_iterations):
            if cancel_event.is_set():
                self._log("グローバル局所探索がキャンセルされました。")
                return {}, -float('inf')

            # 2人の学生を選び、割り当てを交換してみる
            student_ids = list(best_assignment.keys())
            if len(student_ids) < 2:
                break # 交換できる学生がいない
            
            s1_id, s2_id = random.sample(student_ids, 2)
            s1_seminar = best_assignment[s1_id]
            s2_seminar = best_assignment[s2_id]

            temp_assignment = best_assignment.copy()
            temp_assignment[s1_id] = s2_seminar
            temp_assignment[s2_id] = s1_seminar

            if self._is_feasible_assignment(temp_assignment): # BaseOptimizerから継承
                new_score = self._calculate_score(temp_assignment) # BaseOptimizerから継承
                if new_score > best_score:
                    best_score = new_score
                    best_assignment = temp_assignment
                    no_improvement_count = 0
                    # self._log(f"グローバル局所探索: スコア改善 {new_score:.2f}", level=logging.DEBUG)
                else:
                    no_improvement_count += 1
            else:
                no_improvement_count += 1

            if no_improvement_count >= self.no_improvement_limit:
                self._log(f"グローバル局所探索: {self.no_improvement_limit}回改善が見られなかったため、早期終了します。")
                break
        
        self._log(f"グローバル局所探索完了。最終スコア: {best_score:.2f}")
        return best_assignment, best_score

    def optimize(self) -> OptimizationResult: # 返り値をOptimizationResultに
        """
        多段階最適化アルゴリズムのメイン実行関数。
        """
        self._log("Multilevel 最適化を開始します。")
        start_time = time.time()
        cancel_event = threading.Event() # スレッド内でキャンセルイベントを管理

        # ステップ1: 学生をクラスタリング
        clustered_students = self._cluster_students()
        if not clustered_students:
            self._log("学生のクラスタリングに失敗しました。", level=logging.ERROR)
            return OptimizationResult(
                status="NO_SOLUTION_FOUND",
                message="学生のクラスタリングに失敗しました。",
                best_score=-float('inf'),
                best_assignment={},
                seminar_capacities=self.seminar_capacities,
                unassigned_students=self.student_ids,
                optimization_strategy="Multilevel"
            )

        # progress_callbackが設定されていれば、キャンセルイベントをProgressDialogに渡す
        if self.progress_callback:
            # progress_callbackはGUIのメソッドなので、直接キャンセルイベントを操作しない
            # ここでは内部のcancel_eventを使用
            pass

        # ステップ2: 各クラスタ内で最適化
        overall_initial_assignment = {}
        for cluster_id, students_in_cluster in clustered_students.items():
            self._log(f"クラスタ {cluster_id} の最適化中 ({len(students_in_cluster)} 学生)...")
            if cancel_event.is_set():
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
            
            cluster_assignment = self._optimize_cluster(students_in_cluster, self.progress_callback, cancel_event)
            overall_initial_assignment.update(cluster_assignment)
        
        if not overall_initial_assignment:
            self._log("クラスタ最適化後に有効な初期解が生成されませんでした。", level=logging.ERROR)
            return OptimizationResult(
                status="NO_SOLUTION_FOUND",
                message="クラスタ最適化後に有効な初期解が生成されませんでした。",
                best_score=-float('inf'),
                best_assignment={},
                seminar_capacities=self.seminar_capacities,
                unassigned_students=self._get_unassigned_students(overall_initial_assignment),
                optimization_strategy="Multilevel"
            )

        # ステップ3: 全体で局所探索
        self._log("グローバル局所探索で解を改善中...")
        final_assignment, final_score = self._global_local_search(overall_initial_assignment, self.progress_callback, cancel_event)

        if cancel_event.is_set():
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

        status_str = "OPTIMAL" if final_score > -float('inf') else "NO_SOLUTION_FOUND"
        message_str = "多段階最適化が成功しました。" if final_score > -float('inf') else "多段階最適化で有効な解が見つかりませんでした。"
        unassigned_students_list = self._get_unassigned_students(final_assignment)

        return OptimizationResult(
            status=status_str,
            message=message_str,
            best_score=final_score,
            best_assignment=final_assignment,
            seminar_capacities=self.seminar_capacities,
            unassigned_students=unassigned_students_list,
            optimization_strategy="Multilevel"
        )

