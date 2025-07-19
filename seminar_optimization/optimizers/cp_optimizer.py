import logging
from typing import Dict, List, Tuple, Callable
from ortools.sat.python import cp_model

# 外部モジュールからのインポート
from models import Config, Student

logger = logging.getLogger(__name__)

class CPOptimizer:
    """
    制約プログラミング (CP-SAT) を用いてセミナー割り当てを最適化するクラスです。
    ここでは、希望順位の高い学生の満足度を優先的に最大化する多段階の目的関数を試みます。
    """
    def __init__(self, config_dict: dict, students: list[Student], target_sizes: dict[str, int]):
        self.config = Config(**config_dict)
        self.students = students
        self.target_sizes = target_sizes
        self.students_dict = {s.id: s for s in students}
        self.seminar_names = self.config.seminars
        self.seminar_indices = {name: i for i, name in enumerate(self.seminar_names)}
        self.student_indices = {s.id: i for i, s in enumerate(self.students)}

    def run_cp(self, progress_callback: Callable[[str], None]) -> tuple[float, dict[str, list[tuple[int, float]]]]:
        """
        CPモデルを構築し、ソルバーを実行して最適なセミナー割り当てを見つけます。
        ここでは、優先順位付きの目的関数を設定します。
        1. 第1希望に割り当てられた学生数を最大化
        2. 第2希望に割り当てられた学生数を最大化
        3. 第3希望に割り当てられた学生数を最大化
        4. 全体の満足度スコアを最大化
        """
        logger.info("CP最適化を開始します。")
        progress_callback("CPモデルを構築中...")

        model = cp_model.CpModel()

        # 変数の定義: x[s_idx][sem_idx] = 1 なら学生s_idxがセミナーsem_idxに割り当てられる
        x = {}
        for s_idx, student in enumerate(self.students):
            for sem_idx, sem_name in enumerate(self.seminar_names):
                x[(s_idx, sem_idx)] = model.NewBoolVar(f'x_{student.id}_{sem_name}')

        # 制約1: 各学生はちょうど1つのセミナーに割り当てられる
        for s_idx, student in enumerate(self.students):
            model.Add(sum(x[(s_idx, sem_idx)] for sem_idx, _ in enumerate(self.seminar_names)) == 1)

        # 制約2: 各セミナーの最小定員と最大定員
        for sem_idx, sem_name in enumerate(self.seminar_names):
            model.Add(sum(x[(s_idx, sem_idx)] for s_idx, _ in enumerate(self.students)) >= self.config.min_size)
            model.Add(sum(x[(s_idx, sem_idx)] for s_idx, _ in enumerate(self.students)) <= self.config.max_size)

        # 目的関数の定義 (優先順位付き)
        # 各学生が希望順位のセミナーに割り当てられたかを示す変数
        is_1st_choice = {}
        is_2nd_choice = {}
        is_3rd_choice = {}

        for s_idx, student in enumerate(self.students):
            is_1st_choice[s_idx] = model.NewBoolVar(f'is_1st_choice_{student.id}')
            is_2nd_choice[s_idx] = model.NewBoolVar(f'is_2nd_choice_{student.id}')
            is_3rd_choice[s_idx] = model.NewBoolVar(f'is_3rd_choice_{student.id}')

            # 第1希望のセミナーに割り当てられた場合
            rank0_seminars_vars = []
            for sem_idx, sem_name in enumerate(self.seminar_names):
                if student.get_preference_rank(sem_name) == 0:
                    rank0_seminars_vars.append(x[(s_idx, sem_idx)])
            if rank0_seminars_vars:
                model.AddBoolOr(rank0_seminars_vars).OnlyEnforceIf(is_1st_choice[s_idx])
                model.AddBoolAnd([is_1st_choice[s_idx].Not()]).OnlyEnforceIf(sum(rank0_seminars_vars) == 0)
            else: # 第1希望がない学生の場合
                model.Add(is_1st_choice[s_idx] == 0)

            # 第2希望のセミナーに割り当てられた場合 (第1希望ではない場合)
            rank1_seminars_vars = []
            for sem_idx, sem_name in enumerate(self.seminar_names):
                if student.get_preference_rank(sem_name) == 1:
                    rank1_seminars_vars.append(x[(s_idx, sem_idx)])
            if rank1_seminars_vars:
                model.AddBoolOr(rank1_seminars_vars).OnlyEnforceIf(is_2nd_choice[s_idx])
                model.AddBoolAnd([is_2nd_choice[s_idx].Not()]).OnlyEnforceIf(sum(rank1_seminars_vars) == 0)
            else:
                model.Add(is_2nd_choice[s_idx] == 0)

            # 第3希望のセミナーに割り当てられた場合 (第1, 2希望ではない場合)
            rank2_seminars_vars = []
            for sem_idx, sem_name in enumerate(self.seminar_names):
                if student.get_preference_rank(sem_name) == 2:
                    rank2_seminars_vars.append(x[(s_idx, sem_idx)])
            if rank2_seminars_vars:
                model.AddBoolOr(rank2_seminars_vars).OnlyEnforceIf(is_3rd_choice[s_idx])
                model.AddBoolAnd([is_3rd_choice[s_idx].Not()]).OnlyEnforceIf(sum(rank2_seminars_vars) == 0)
            else:
                model.Add(is_3rd_choice[s_idx] == 0)

        # 目的関数: 優先度の高い順に最大化
        # OR-ToolsのAddDecisionStrategyやSearchForOptimalSolutionsを使っても良いが、
        # ここではLinearRelaxationを許容する重み付けで表現する
        # より厳密な優先順位付けは、複数のSolveコールやコールバックで実現できるが、複雑になるため今回は重み付けで表現
        total_score_objective = []
        for s_idx, student in enumerate(self.students):
            for sem_idx, sem_name in enumerate(self.seminar_names):
                score = student.calculate_score(sem_name, self.config.magnification, self.config.preference_weights)
                total_score_objective.append(int(score * 1000) * x[(s_idx, sem_idx)])

        # 1st, 2nd, 3rd choiceの満足度を非常に高い重みで最大化
        # その後、全体のスコアを最大化
        # 重みは、前の目標の最大値よりも十分に大きくする
        # 例えば、学生数 * 1000000 などの大きな値
        max_possible_students = len(self.students)
        
        model.Maximize(
            sum(is_1st_choice.values()) * (max_possible_students * 1000000) +
            sum(is_2nd_choice.values()) * (max_possible_students * 10000) +
            sum(is_3rd_choice.values()) * (max_possible_students * 100) +
            sum(total_score_objective)
        )

        # ソルバーの設定と実行
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.config.solver_time_limit_seconds
        solver.parameters.num_workers = self.config.ilp_solver_threads # ILPと同様にスレッド数を設定
        
        progress_callback(f"CPソルバーを実行中... (制限時間: {self.config.solver_time_limit_seconds}秒)")
        status = solver.Solve(model)

        final_assignments: Dict[str, List[Tuple[int, float]]] = {sem: [] for sem in self.seminar_names}
        total_score = 0.0

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            progress_callback("CP解が見つかりました。結果を処理中...")
            for s_idx, student in enumerate(self.students):
                for sem_idx, sem_name in enumerate(self.seminar_names):
                    if solver.Value(x[(s_idx, sem_idx)]) == 1:
                        score = student.calculate_score(sem_name, self.config.magnification, self.config.preference_weights)
                        final_assignments[sem_name].append((student.id, score))
                        total_score += score
            logger.info(f"CP最適化完了。ステータス: {solver.StatusName(status)}, スコア: {total_score:.2f}")
        else:
            logger.warning(f"CPソルバーが最適解を見つけられませんでした。ステータス: {solver.StatusName(status)}")
            progress_callback(f"CPソルバーが解を見つけられませんでした。ステータス: {solver.StatusName(status)}")

        return total_score, final_assignments

