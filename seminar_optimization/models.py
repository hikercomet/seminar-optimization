from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class Student:
    """学生の情報を保持するデータクラス"""
    id: int
    preferences: List[str] # 希望セミナーのリスト (例: ['a', 'b', 'c'])

@dataclass
class Config:
    """最適化設定を保持するデータクラス"""
    seminars: List[str] = field(default_factory=list)
    magnification: Dict[str, float] = field(default_factory=dict)
    min_size: int = 5
    max_size: int = 10
    num_students: int = 0 # 学生総数はPreferenceGeneratorで設定される
    q_boost_probability: float = 0.2
    num_patterns: int = 200000 # Greedy_LSの試行回数、GA_LSの世代数
    max_workers: int = 8
    local_search_iterations: int = 500
    initial_temperature: float = 1.0
    cooling_rate: float = 0.995
    preference_weights: Dict[str, float] = field(default_factory=lambda: {"1st": 5.0, "2nd": 2.0, "3rd": 1.0})
    optimization_strategy: str = "Greedy_LS" # "Greedy_LS", "GA_LS", "ILP", "CP", "Multilevel"
    ga_population_size: int = 100
    ga_crossover_rate: float = 0.8
    ga_mutation_rate: float = 0.05
    # 新しく追加されたパラメータ: これらの行がmodels.pyに存在することを確認してください！
    ilp_time_limit: int = 300 # ILPソルバーの時間制限 (秒)
    cp_time_limit: int = 300  # CP-SATソルバーの時間制限 (秒)
    multilevel_clusters: int = 5 # 多段階最適化のクラスタ数
    # 出力ディレクトリの追加
    output_dir: str = "results" # 最適化結果の出力先ディレクトリ
    pdf_file: str = "seminar_assignment_report.pdf" # PDFレポートのファイル名
    csv_file: str = "seminar_assignment_results.csv" # CSV結果のファイル名
