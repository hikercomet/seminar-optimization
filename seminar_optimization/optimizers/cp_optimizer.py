import logging
from typing import Dict, List, Tuple, Any

from ortools.sat.python import cp_model # OR-Tools CP-SATソルバーをインポート
from models import Student, Config # StudentとConfigモデルをインポート

logger = logging.getLogger(__name__)

class CPOptimizer:
    """
    制約プログラミング (CP-SAT) を用いてセミナー割り当て問題を最適化するクラス。
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
        self.cp_time_limit = config.cp_time_limit

        # 希望順位の重みを辞書に変換（より柔軟に対応）
        self.weights = {}
        for i in range(1, 6):  # 1位から5位まで対応
            if i == 1:
                key = "1st"
            elif i == 2:
                key = "2nd"
            elif i == 3:
                key = "3rd"
            else:
                key = f"{i}th"
            
            # デフォルト値: 1位=5点, 2位=2点, 3位=1点, それ以下=0点
            default_weight = max(0.0, 6.0 - i) if i <= 3 else 0.0
            self.weights[i] = self.preference_weights.get(key, default_weight)

        # デバッグモードの設定
        self.debug_mode = getattr(config, 'debug_mode', False)

    def validate_inputs(self) -> List[str]:
        """入力データの妥当性を検証し、問題があれば警告を返す"""
        warnings = []
        
        # 学生数と定員の整合性チェック
        total_min_capacity = len(self.seminar_names) * self.min_size
        total_max_capacity = len(self.seminar_names) * self.max_size
        
        if self.num_students < total_min_capacity:
            warnings.append(f"学生数({self.num_students})が最小定員合計({total_min_capacity})より少ない")
        elif self.num_students > total_max_capacity:
            warnings.append(f"学生数({self.num_students})が最大定員合計({total_max_capacity})より多い")
        
        # 希望データの妥当性チェック
        for student in self.students:
            if not student.preferences:
                warnings.append(f"学生{student.id}に希望データがありません")
            elif len(student.preferences) < 3:
                warnings.append(f"学生{student.id}の希望が{len(student.preferences)}個しかありません")
        
        # セミナー名の重複チェック
        if len(set(self.seminar_names)) != len(self.seminar_names):
            warnings.append("セミナー名に重複があります")
        
        return warnings

    def optimize(self) -> Tuple[Dict[str, int], float, Dict[str, List[Tuple[int, float]]]]:
        """
        CP-SATモデルを構築し、ソルバーを用いて最適化を実行します。
        """
        logger.info("CP-SATモデルの構築を開始します...")

        # 入力検証
        warnings = self.validate_inputs()
        for warning in warnings:
            logger.warning(warning)

        # モデルの作成
        model = cp_model.CpModel()

        # 変数とスコアを事前計算してパフォーマンスを向上
        # x[s_id][sem_name] = 1 なら学生 s_id がセミナー sem_name に割り当てられる
        x: Dict[Tuple[int, str], Any] = {}  # cp_model.IntVar型だが、Anyで回避
        score_matrix: Dict[Tuple[int, str], float] = {}  # (student_id, seminar) -> score の事前計算
        
        for s in self.students:
            for sem in self.seminar_names:
                var_name = f'x_{s.id}_{sem}'
                x[(s.id, sem)] = model.NewBoolVar(var_name)
                score_matrix[(s.id, sem)] = self.get_preference_score(s.id, sem)

        # 制約の定義

        # 1. 各学生はちょうど1つのセミナーに割り当てられる
        for s in self.students:
            model.Add(sum(x[(s.id, sem)] for sem in self.seminar_names) == 1)

        # 2. 各セミナーの定員制約 (最小定員と最大定員)
        for sem in self.seminar_names:
            student_count = sum(x[(s.id, sem)] for s in self.students)
            model.Add(student_count >= self.min_size)
            model.Add(student_count <= self.max_size)

        # 目的関数の定義
        # 総スコアを最大化する
        # スコアが0の項目は除外してパフォーマンスを向上
        objective_terms = [
            int(score_matrix[(s.id, sem)] * 100) * x[(s.id, sem)]
            for s in self.students
            for sem in self.seminar_names
            if score_matrix[(s.id, sem)] > 0  # スコアが0の項目は除外
        ]
        
        if not objective_terms:
            logger.warning("有効なスコア項目が見つかりません。すべての学生の希望が無効な可能性があります。")
            # 最低限の目的関数を設定（すべて0点でも動作するように）
            objective_terms = [0 * x[(s.id, sem)] for s in self.students for sem in self.seminar_names]
        
        model.Maximize(sum(objective_terms))

        logger.info("CP-SATモデルの構築が完了しました。ソルバーを実行します...")

        # ソルバーの作成と実行
        solver = cp_model.CpSolver()
        # タイムリミットを設定
        solver.parameters.max_time_in_seconds = self.cp_time_limit
        
        # 並列処理の活用（利用可能な場合）
        try:
            solver.parameters.num_search_workers = 4
        except AttributeError:
            pass  # 古いバージョンでは利用できない場合がある
        
        # 進捗ログの設定（デバッグモードの場合）
        if self.debug_mode:
            try:
                solver.parameters.log_search_progress = True
            except AttributeError:
                pass

        status = solver.Solve(model)

        logger.info(f"CP-SATソルバーの状態: {solver.StatusName(status)}")

        if status == cp_model.OPTIMAL:
            logger.info("最適解が見つかりました")
            return self._analyze_solution(solver, x, score_matrix)
        elif status == cp_model.FEASIBLE:
            logger.info("実行可能解が見つかりました（最適性は保証されません）")
            return self._analyze_solution(solver, x, score_matrix)
        else:
            logger.error(f"解が見つかりませんでした。ステータス: {solver.StatusName(status)}")
            return self._handle_infeasible_case()

    def _analyze_solution(self, solver: cp_model.CpSolver, 
                         x: Dict[Tuple[int, str], Any], 
                         score_matrix: Dict[Tuple[int, str], float]) -> Tuple[Dict[str, int], float, Dict[str, List[Tuple[int, float]]]]:
        """解の詳細分析を行う"""
        overall_score = solver.ObjectiveValue() / 100.0
        final_assignments: Dict[str, List[Tuple[int, float]]] = {sem: [] for sem in self.seminar_names}
        pattern_sizes: Dict[str, int] = {sem: 0 for sem in self.seminar_names}
        
        # 希望順位別の集計
        preference_stats = {1: 0, 2: 0, 3: 0, 'others': 0}
        
        for s in self.students:
            for sem in self.seminar_names:
                if solver.Value(x[(s.id, sem)]) == 1:
                    score = score_matrix[(s.id, sem)]
                    final_assignments[sem].append((s.id, score))
                    pattern_sizes[sem] += 1
                    
                    # 希望順位の統計
                    rank = self._get_preference_rank(s.id, sem)
                    if 1 <= rank <= 3:
                        preference_stats[rank] += 1
                    else:
                        preference_stats['others'] += 1
                    break
        
        # 統計情報のログ出力
        logger.info(f"最終スコア: {overall_score:.2f}")
        logger.info(f"定員配分: {pattern_sizes}")
        logger.info(f"希望順位別配分: 1位:{preference_stats[1]}人, "
                    f"2位:{preference_stats[2]}人, 3位:{preference_stats[3]}人, "
                    f"その他:{preference_stats['others']}人")
        
        return pattern_sizes, overall_score, final_assignments

    def _handle_infeasible_case(self) -> Tuple[Dict[str, int], float, Dict[str, List[Tuple[int, float]]]]:
        """制約を満たす解が存在しない場合の処理"""
        logger.error("実行可能解が存在しません。制約を緩和することを検討してください。")
        
        # 制約緩和の提案
        total_students = self.num_students
        num_seminars = len(self.seminar_names)
        avg_per_seminar = total_students / num_seminars
        
        suggested_min = max(1, int(avg_per_seminar * 0.8))
        suggested_max = int(avg_per_seminar * 1.2)
        
        logger.info(f"提案: 最小定員を{suggested_min}、"
                    f"最大定員を{suggested_max}に調整してみてください")
        logger.info(f"現在の設定: 最小定員={self.min_size}, 最大定員={self.max_size}")
        
        return {}, -1.0, {}

    def get_preference_score(self, student_id: int, seminar_name: str) -> float:
        """
        学生が特定のセミナーに割り当てられた場合のスコア貢献度を計算します。
        """
        prefs = self.student_preferences_map.get(student_id, [])
        
        # セミナー名の正規化を統一
        normalized_seminar = seminar_name.strip().lower()
        normalized_prefs = [p.strip().lower() for p in prefs]
        
        try:
            rank = normalized_prefs.index(normalized_seminar) + 1  # 0-indexed to 1-indexed
            return self.weights.get(rank, 0.0)  # 定義されていない順位は0点
        except ValueError:
            return 0.0  # 希望リストにないセミナーに割り当てられた場合

    def _get_preference_rank(self, student_id: int, seminar_name: str) -> int:
        """学生の希望におけるセミナーの順位を取得（統計用）"""
        prefs = self.student_preferences_map.get(student_id, [])
        normalized_seminar = seminar_name.strip().lower()
        normalized_prefs = [p.strip().lower() for p in prefs]
        
        try:
            return normalized_prefs.index(normalized_seminar) + 1
        except ValueError:
            return 999  # 希望リストにない場合は大きな数値を返す