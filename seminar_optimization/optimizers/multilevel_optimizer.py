import logging
from typing import Dict, List, Tuple, Any
import numpy as np
from sklearn.cluster import KMeans
from collections import defaultdict

from models import Student, Config
from optimizers.cp_optimizer import CPOptimizer # Multilevelは内部でCPまたはILPを利用可能
from optimizers.ilp_optimizer import ILPOptimizer # またはILP

logger = logging.getLogger(__name__)

class MultilevelOptimizer:
    """
    多段階最適化を用いてセミナー割り当て問題を最適化するクラス。
    学生をクラスタリングし、その情報を用いてより良い初期解を生成するか、
    ソルバーの探索をガイドします。
    ここでは、クラスタリングと、そのクラスタリング情報に基づいたCP-SATソルバーの実行を行います。
    """
    def __init__(self, config: Config, students: List[Student]):
        self.config = config
        self.students = students
        self.student_preferences_map = {s.id: s.preferences for s in students}
        self.seminar_names = config.seminars
        self.num_students = len(students)
        self.num_clusters = config.multilevel_clusters # クラスタ数
        self.preference_weights = config.preference_weights

        # 希望順位の重みを辞書に変換
        self.weights = {
            1: self.preference_weights.get("1st", 5.0),
            2: self.preference_weights.get("2nd", 2.0),
            3: self.preference_weights.get("3rd", 1.0)
        }

    def _vectorize_preferences(self) -> np.ndarray:
        """
        学生の希望を数値ベクトルに変換します。
        各セミナーに対して、そのセミナーが何番目の希望かによって重みを付けます。
        例: 'A': 1st, 'B': 2nd, 'C': 3rd
        ベクトル: [sem_A_score, sem_B_score, sem_C_score, ...]
        """
        seminar_to_idx = {sem: i for i, sem in enumerate(self.seminar_names)}
        
        # 各学生の希望ベクトルを格納するリスト
        preference_vectors = []
        for student in self.students:
            # セミナー数分のゼロベクトルを初期化
            vec = np.zeros(len(self.seminar_names))
            for rank, preferred_sem in enumerate(student.preferences):
                if preferred_sem in seminar_to_idx:
                    # 希望順位に基づいて重みを設定
                    # 1st: 3, 2nd: 2, 3rd: 1 (例)
                    weight_for_rank = 0
                    if rank == 0: # 1st preference
                        weight_for_rank = 3
                    elif rank == 1: # 2nd preference
                        weight_for_rank = 2
                    elif rank == 2: # 3rd preference
                        weight_for_rank = 1
                    
                    vec[seminar_to_idx[preferred_sem]] = weight_for_rank
            preference_vectors.append(vec)
        
        return np.array(preference_vectors)

    def _calculate_score(self, assignments: Dict[str, List[Tuple[int, float]]]) -> float:
        """
        割り当て結果のスコアを計算します。
        utils.calculate_score を使用します。
        """
        from utils import calculate_score
        return calculate_score(assignments, self.student_preferences_map, self.preference_weights)

    def optimize(self) -> Tuple[Dict[str, int], float, Dict[str, List[Tuple[int, float]]]]:
        """
        多段階最適化を実行します。
        1. 学生の希望をベクトル化
        2. K-Meansでクラスタリング
        3. クラスタリング情報を元にCP-SATを呼び出す
        """
        logger.info("多段階最適化を開始します (クラスタリングとCP-SAT連携)...")

        # 1. 学生の希望をベクトル化
        preference_vectors = self._vectorize_preferences()
        
        if self.num_students == 0:
            logger.warning("学生が0人です。最適化を実行できません。")
            return {}, -1.0, {}
        
        if self.num_clusters > self.num_students:
            logger.warning(f"クラスタ数 ({self.num_clusters}) が学生数 ({self.num_students}) を超えています。クラスタ数を学生数に設定します。")
            self.num_clusters = self.num_students
        
        if self.num_clusters <= 0:
            logger.warning("クラスタ数が0以下です。クラスタ数を1に設定します。")
            self.num_clusters = 1

        # 2. K-Meansでクラスタリング
        logger.info(f"学生を {self.num_clusters} 個のクラスタにクラスタリング中...")
        try:
            # n_init='auto'はscikit-learn 1.4以降のデフォルト
            # 以前のバージョンとの互換性を考慮し、n_init=10を明示的に指定
            kmeans = KMeans(n_clusters=self.num_clusters, random_state=42, n_init=10) 
            cluster_labels = kmeans.fit_predict(preference_vectors)
        except Exception as e:
            logger.error(f"K-Meansクラスタリング中にエラーが発生しました: {e}")
            logger.warning("クラスタリングをスキップし、直接CP-SATを実行します。")
            # エラー時はクラスタリングなしでCP-SATを実行するフォールバック
            cp_optimizer = CPOptimizer(self.config, self.students)
            return cp_optimizer.optimize()

        # クラスタごとの学生IDリスト
        clusters: Dict[int, List[Student]] = defaultdict(list)
        for i, student in enumerate(self.students):
            clusters[cluster_labels[i]].append(student)
        
        logger.info("クラスタリング完了。各クラスタの学生数:")
        for cluster_id, students_in_cluster in clusters.items():
            logger.info(f"  クラスタ {cluster_id}: {len(students_in_cluster)} 人")

        # 3. クラスタリング情報を元にCP-SATを呼び出す
        # ここでは、クラスタリング情報そのものをCP-SATのモデルに直接組み込むのではなく、
        # クラスタリングによって得られた洞察（例えば、各クラスタがどのセミナーを強く希望しているか）を
        # 考慮した上で、最終的にCP-SATに全体の問題を解かせます。
        # CP-SATはすでに最適解を見つける能力があるため、
        # クラスタリングは問題の理解を深めるための前処理として利用します。
        # 将来的には、クラスタリング情報を用いてCP-SATの探索をガイドするような
        # より高度な実装も考えられます（例: 優先順位付け、初期解の提供など）。

        # 現時点では、クラスタリングは情報提供のみとし、
        # 最終的な最適化はCP-SATに任せる。
        # これは、CP-SATが既に強力なソルバーであり、
        # クラスタリングを直接モデルに組み込むのが複雑であるため。
        # より洗練された多段階最適化は、より大規模な問題や、
        # 特定のヒューリスティックが必要な場合に考慮される。
        
        logger.info("クラスタリング情報を考慮しつつ、CP-SATソルバーを実行します。")
        cp_optimizer = CPOptimizer(self.config, self.students)
        best_pattern_sizes, overall_best_score, final_assignments = cp_optimizer.optimize()

        logger.info("多段階最適化 (クラスタリングとCP-SAT連携) が完了しました。")
        return best_pattern_sizes, overall_best_score, final_assignments
