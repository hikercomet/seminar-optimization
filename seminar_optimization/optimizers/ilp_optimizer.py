import logging
from typing import Dict, List, Tuple, Callable
from ortools.sat.python import cp_model

# 外部モジュールからのインポート
from models import Config, Student

logger = logging.getLogger(__name__)

class ILPOptimizer:
    """
    整数線形計画法 (ILP) を用いてセミナー割り当てを最適化するクラスです。
    Google OR-Tools の CP-SAT ソルバーを使用します。
    """
    def __init__(self, config_dict: dict, students: list[Student], target_sizes: dict[str, int]):
        self.config = Config(**config_dict)
        self.students = students
        self.target_sizes = target_sizes
        self.students_dict = {s.id: s for s in students}
        self.seminar_names = self.config.seminars
        self.seminar_indices = {name: i for i, name in enumerate(self.seminar_names)}
        self.student_indices = {s.id: i for i, s in enumerate(self.students)}

    def run_ilp(self, progress_callback: Callable[[str], None]) -> tuple[float, dict[str, list[tuple[int, float]]]]:
        """
        ILPモデルを構築し、ソルバーを実行して最適なセミナー割り当てを見つけます。
        """
        logger.info("ILP最適化を開始します。")
        progress_callback("ILPモデルを構築中...")

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
            # 目標定員を優先的に使用し、min_sizeとmax_sizeでクリップする
            min_cap = max(self.config.min_size, self.target_sizes.get(sem_name, self.config.min_size))
            max_cap = min(self.config.max_size, self.target_sizes.get(sem_name, self.config.max_size))
            
            # ただし、ILPでは厳密なmin/max制約を課す
            # target_sizesはあくまでガイドとして使い、ここではconfigのmin/max_sizeを直接使う
            model.Add(sum(x[(s_idx, sem_idx)] for s_idx, _ in enumerate(self.students)) >= self.config.min_size)
            model.Add(sum(x[(s_idx, sem_idx)] for s_idx, _ in enumerate(self.students)) <= self.config.max_size)

        # 目的関数の定義: 総学生満足度スコアの最大化
        objective_terms = []
        for s_idx, student in enumerate(self.students):
            for sem_idx, sem_name in enumerate(self.seminar_names):
                score = student.calculate_score(sem_name, self.config.magnification, self.config.preference_weights)
                objective_terms.append(int(score * 1000) * x[(s_idx, sem_idx)]) # スコアを整数に変換して精度を保つ

        model.Maximize(sum(objective_terms))

        # ソルバーの設定と実行
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = self.config.solver_time_limit_seconds
        solver.parameters.num_workers = self.config.ilp_solver_threads # スレッド数を設定
        
        progress_callback(f"ILPソルバーを実行中... (制限時間: {self.config.solver_time_limit_seconds}秒)")
        status = solver.Solve(model)

        final_assignments: Dict[str, List[Tuple[int, float]]] = {sem: [] for sem in self.seminar_names}
        total_score = 0.0

        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            progress_callback("ILP解が見つかりました。結果を処理中...")
            for s_idx, student in enumerate(self.students):
                for sem_idx, sem_name in enumerate(self.seminar_names):
                    if solver.Value(x[(s_idx, sem_idx)]) == 1:
                        score = student.calculate_score(sem_name, self.config.magnification, self.config.preference_weights)
                        final_assignments[sem_name].append((student.id, score))
                        total_score += score
            logger.info(f"ILP最適化完了。ステータス: {solver.StatusName(status)}, スコア: {total_score:.2f}")
        else:
            logger.warning(f"ILPソルバーが最適解を見つけられませんでした。ステータス: {solver.StatusName(status)}")
            progress_callback(f"ILPソルバーが解を見つけられませんでした。ステータス: {solver.StatusName(status)}")

        return total_score, final_assignments

