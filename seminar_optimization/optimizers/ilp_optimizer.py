import pulp
import logging
from typing import Dict, List, Tuple

from models import Student, Config # StudentとConfigモデルをインポート

logger = logging.getLogger(__name__)

class ILPOptimizer:
    """
    整数線形計画法 (ILP) を用いてセミナー割り当て問題を最適化するクラス。
    """
    def __init__(self, config: Config, students: List[Student]):
        self.config = config
        self.students = students
        self.student_preferences_map = {s.id: s.preferences for s in students}
        self.seminar_names = config.seminars
        self.min_size = config.min_size
        self.max_size = config.max_size
        self.preference_weights = config.preference_weights
        self.num_students = len(students)
        self.ilp_time_limit = config.ilp_time_limit

        # 希望順位の重みを辞書に変換
        self.weights = {
            1: self.preference_weights.get("1st", 5.0),
            2: self.preference_weights.get("2nd", 2.0),
            3: self.preference_weights.get("3rd", 1.0)
        }

    def optimize(self) -> Tuple[Dict[str, int], float, Dict[str, List[Tuple[int, float]]]]:
        """
        ILPモデルを構築し、PuLPソルバーを用いて最適化を実行します。
        """
        logger.info("ILPモデルの構築を開始します...")

        # 問題の定義
        # 最大化問題 (Maximize) として定義
        prob = pulp.LpProblem("Seminar_Assignment", pulp.LpMaximize)

        # 変数の定義
        # x[s_id][sem_name] = 1 なら学生 s_id がセミナー sem_name に割り当てられる、0 なら割り当てられない
        x = pulp.LpVariable.dicts("x", 
                                  [(s.id, sem) for s in self.students for sem in self.seminar_names],
                                  cat='Binary') # バイナリ変数 (0または1)

        # 各セミナーの目標定員も変数として定義
        # これにより、定員自体も最適化の一部となる
        # ただし、今回はConfigから与えられる目標定員に近づけるのではなく、
        # 厳密な定員制約として扱うため、ここでは目標定員を固定値として使用する。
        # もし目標定員も最適化したい場合は、別途変数として定義し、目的関数や制約に追加する必要がある。
        # 現状の設計では、TargetSizeOptimizerが目標定員を生成し、ILPはそれに従って割り当てる。
        # しかし、ILPはそれ自体で最適な定員を見つけることも可能。
        # ここでは、ILPが「全ての学生を割り当てつつ、希望を最大化する」ことを目指す。
        # その結果として各セミナーの人数が決まる。

        # 目的関数の定義
        # 総スコアを最大化する
        # 各学生が割り当てられたセミナーが何番目の希望かによってスコアを加算
        prob += pulp.lpSum(
            self.get_preference_score(s.id, sem) * x[(s.id, sem)]
            for s in self.students for sem in self.seminar_names
        ), "Total_Preference_Score"

        # 制約の定義

        # 1. 各学生はちょうど1つのセミナーに割り当てられる
        for s in self.students:
            prob += pulp.lpSum(x[(s.id, sem)] for sem in self.seminar_names) == 1, f"One_Seminar_Per_Student_{s.id}"

        # 2. 各セミナーの定員制約 (最小定員と最大定員)
        # ここでは、TargetSizeOptimizerによって生成された目標定員を直接使用せず、
        # Configで指定されたmin_sizeとmax_sizeを直接制約として使用する。
        # これにより、ILPはこれらの範囲内で最適な割り当てを見つける。
        # もしTargetSizeOptimizerの出力をILPに渡したい場合は、その出力をここで利用する。
        # 現状の設計では、ILPは独立して割り当てを決定する。
        
        # ILPが最適な定員を見つけるようにするには、セミナーの最終的な人数を変数として定義し、
        # それにmin_sizeとmax_sizeの制約をかける。
        # y[sem] = セミナーsemに割り当てられる学生数
        y = pulp.LpVariable.dicts("y", self.seminar_names, lowBound=self.min_size, upBound=self.max_size, cat='Integer')

        for sem in self.seminar_names:
            # セミナーsemに割り当てられる学生の合計はy[sem]に等しい
            prob += pulp.lpSum(x[(s.id, sem)] for s in self.students) == y[sem], f"Seminar_Capacity_Definition_{sem}"
            
            # y[sem] は min_size と max_size の間になければならない (これはyの定義で既に指定済み)
            # prob += y[sem] >= self.min_size, f"Min_Capacity_{sem}"
            # prob += y[sem] <= self.max_size, f"Max_Capacity_{sem}"


        logger.info("ILPモデルの構築が完了しました。ソルバーを実行します...")

        # ソルバーの選択と実行
        # COIN-OR CBC (デフォルト) を使用
        # timeLimit を設定
        solver = pulp.PULP_CBC_CMD(timeLimit=self.ilp_time_limit, msg=True)
        prob.solve(solver)

        logger.info(f"ソルバーの状態: {pulp.LpStatus[prob.status]}")

        if prob.status == pulp.LpStatus.Optimal or prob.status == pulp.LpStatus.NotSolved:
            # 最適解が見つかった場合、または時間制限で停止した場合
            overall_best_score = pulp.value(prob.objective)
            
            final_assignments: Dict[str, List[Tuple[int, float]]] = {sem: [] for sem in self.seminar_names}
            best_pattern_sizes: Dict[str, int] = {sem: 0 for sem in self.seminar_names}

            for s in self.students:
                for sem in self.seminar_names:
                    if x[(s.id, sem)].value() == 1:
                        score_contrib = self.get_preference_score(s.id, sem)
                        final_assignments[sem].append((s.id, score_contrib))
                        best_pattern_sizes[sem] += 1
                        break # 各学生は1つのセミナーにしか割り当てられないため

            logger.info(f"ILP最適化結果 - スコア: {overall_best_score:.2f}")
            logger.info(f"ILP最適化結果 - 定員パターン: {best_pattern_sizes}")
            return best_pattern_sizes, overall_best_score, final_assignments
        else:
            logger.warning("ILPソルバーが最適な解を見つけられませんでした。")
            return {}, -1.0, {}

    def get_preference_score(self, student_id: int, seminar_name: str) -> float:
        """
        学生が特定のセミナーに割り当てられた場合のスコア貢献度を計算します。
        """
        prefs = self.student_preferences_map.get(student_id, [])
        try:
            rank = prefs.index(seminar_name.lower()) + 1 # 0-indexed to 1-indexed
            return self.weights.get(rank, 0.0) # 3位以下の希望は0点
        except ValueError:
            return 0.0 # 希望リストにないセミナーに割り当てられた場合
