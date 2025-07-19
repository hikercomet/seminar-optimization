from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class Config:
    seminars: Optional[list[str]] = None # 修正: listを使用
    magnification: Optional[dict[str, float]] = None # 修正: dictを使用
    min_size: int = 5
    max_size: int = 10
    num_students: Optional[int] = None 
    num_patterns: int = 200000
    early_stop_threshold: float = 0.001
    no_improvement_limit: int = 1000
    output_dir: str = "results"
    pdf_file: str = None
    q_boost_probability: float = 0.2
    max_workers: int = 8
    
    local_search_iterations: int = 500
    initial_temperature: float = 1.0
    cooling_rate: float = 0.995
    preference_weights: Optional[dict[str, float]] = None # 修正: dictを使用

    def __post_init__(self):
        if self.pdf_file is None:
            import os 
            self.pdf_file = os.path.join(self.output_dir, "seminar_results_advanced.pdf")
        
        if self.preference_weights is None:
            self.preference_weights = {"1st": 5.0, "2nd": 2.0, "3rd": 1.0}


class Student:
    def __init__(self, student_id: int, preferences: list[str]): # 修正: listを使用
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
    
    def calculate_score(self, seminar: str, magnification: dict[str, float], preference_weights: dict[str, float]) -> float: # 修正: dictを使用
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
