from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class Config:
    seminars: Optional[list[str]] = None
    magnification: Optional[dict[str, float]] = None
    min_size: int = 5
    max_size: int = 10
    num_students: Optional[int] = None 
    num_patterns: int = 200000 # Greedy+LSの場合は試行回数、GAの場合は世代数
    early_stop_threshold: float = 0.001
    no_improvement_limit: int = 1000
    output_dir: str = "results"
    pdf_file: str = None
    q_boost_probability: float = 0.2
    max_workers: int = 8
    
    local_search_iterations: int = 500
    initial_temperature: float = 1.0
    cooling_rate: float = 0.995
    preference_weights: Optional[dict[str, float]] = None

    # 新しい設定項目: 最適化戦略の選択
    # "Greedy_LS": 貪欲法 + 局所探索
    # "GA_LS": 遺伝的アルゴリズム + 局所探索 (Lamarckian GA)
    # "ILP": 整数線形計画法
    # "CP": 制約プログラミング (CP-SAT)
    # "Multilevel": 多段階最適化
    optimization_strategy: str = "Greedy_LS" 

    # 遺伝的アルゴリズム (GA) 用の追加パラメータ
    ga_population_size: int = 100 # GAの個体数
    ga_crossover_rate: float = 0.8 # 交叉率 (0.0 - 1.0)
    ga_mutation_rate: float = 0.05 # 突然変異率 (0.0 - 1.0)

    # ILP / CP 用の追加パラメータ
    solver_time_limit_seconds: int = 300 # ソルバーの最大実行時間 (秒)
    ilp_solver_threads: int = 1 # ILPソルバーが使用するスレッド数

    # Multilevel 用の追加パラメータ
    multilevel_initial_greedy_runs: int = 5 # 初期貪欲法の試行回数 (Multilevelの第一段階)
    multilevel_refinement_iterations: int = 1000 # 最終局所探索の反復回数 (Multilevelの第二段階)

    def __post_init__(self):
        if self.pdf_file is None:
            import os 
            self.pdf_file = os.path.join(self.output_dir, "seminar_results_advanced.pdf")
        
        if self.preference_weights is None:
            self.preference_weights = {"1st": 5.0, "2nd": 2.0, "3rd": 1.0}


class Student:
    def __init__(self, student_id: int, preferences: list[str]):
        self.id = student_id
        self.preferences = preferences
        self.assigned_seminar = None
        self.satisfaction_score = 0.0
    
    def get_preference_rank(self, seminar: str) -> int:
        """セミナーに対する希望順位を返します (1位=0, 2位=1, 3位=2, その他=-1)"""
        try:
            return self.preferences.index(seminar)
        except ValueError:
            return -1
    
    def calculate_score(self, seminar: str, magnification: dict[str, float], preference_weights: dict[str, float]) -> float:
        """特定のセミナーに割り当てられた場合のスコアを計算します"""
        rank = self.get_preference_rank(seminar)
        
        if rank == 0:  # 1位希望
            base_score = preference_weights.get("1st", 5.0)
        elif rank == 1:  # 2位希望
            base_score = preference_weights.get("2nd", 2.0)
        elif rank == 2:  # 3位希望
            base_score = preference_weights.get("3rd", 1.0)
        else:  # 希望なし
            base_score = 0.0
        
        return base_score * magnification.get(seminar, 1.0)
