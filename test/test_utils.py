import unittest
import sys
import os

# プロジェクトのルートディレクトリをsys.pathに追加
# test_utils.py が seminar-optimization/tests にあると仮定
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# seminar_optimization パッケージからインポート
from seminar_optimization.utils import BaseOptimizer, OptimizationResult

class TestBaseOptimizer(unittest.TestCase):
    """
    BaseOptimizer クラスのメソッドをテストする。
    """
    def setUp(self):
        """
        各テストメソッドの実行前に共通のセットアップを行う。
        """
        # テスト用のセミナーと学生データ
        self.seminars_data = [
            {"id": "SemA", "capacity": 10, "magnification": 1.2},
            {"id": "SemB", "capacity": 5, "magnification": 1.0},
            {"id": "SemC", "capacity": 8, "magnification": 0.9}
        ]
        self.students_data = [
            {"id": "S1", "preferences": ["SemA", "SemB", "SemC"]},
            {"id": "S2", "preferences": ["SemB", "SemA"]},
            {"id": "S3", "preferences": ["SemA", "SemC"]},
            {"id": "S4", "preferences": ["SemC", "SemB", "SemA"]},
            {"id": "S5", "preferences": ["SemA"]},
            {"id": "S6", "preferences": ["SemB", "SemC"]},
        ]
        # テスト用の設定（スコア重みを含む）
        self.config = {
            "score_weights": {
                "1st_choice": 3.0,
                "2nd_choice": 2.0,
                "3rd_choice": 1.0,
                "other_preference": 0.5
            },
            "random_seed": 42 # テストの再現性のためシードを固定
        }
        # BaseOptimizerのインスタンスを作成
        self.optimizer = BaseOptimizer(self.seminars_data, self.students_data, self.config)

    def test_calculate_score_perfect_match(self):
        """
        全ての学生が第1希望に割り当てられた場合のスコア計算をテストする。
        """
        assignment = {
            "S1": "SemA", # 1st choice (3.0 * 1.2 = 3.6)
            "S2": "SemB", # 1st choice (3.0 * 1.0 = 3.0)
            "S3": "SemA", # 1st choice (3.0 * 1.2 = 3.6)
            "S4": "SemC", # 1st choice (3.0 * 0.9 = 2.7)
            "S5": "SemA", # 1st choice (3.0 * 1.2 = 3.6)
            "S6": "SemB", # 1st choice (3.0 * 1.0 = 3.0)
        }
        # 定員オーバーしないように調整
        # SemA: 3人 (定員10)
        # SemB: 2人 (定員5)
        # SemC: 1人 (定員8)
        expected_score = (3.0 * 1.2) * 3 + (3.0 * 1.0) * 2 + (3.0 * 0.9) * 1
        self.assertAlmostEqual(self.optimizer._calculate_score(assignment), expected_score, places=5)
        self.assertTrue(self.optimizer._is_feasible_assignment(assignment))

    def test_calculate_score_mixed_preferences(self):
        """
        異なる希望順位に割り当てられた場合のスコア計算をテストする。
        """
        assignment = {
            "S1": "SemB", # 2nd choice (2.0 * 1.0 = 2.0)
            "S2": "SemA", # 2nd choice (2.0 * 1.2 = 2.4)
            "S3": "SemC", # 2nd choice (1.0 * 0.9 = 0.9)
            "S4": "SemA", # 3rd choice (1.0 * 1.2 = 1.2)
            "S5": "SemB", # Not preferred by S5 (0.0)
            "S6": "SemC", # 2nd choice (1.0 * 0.9 = 0.9)
        }
        # 定員オーバーしないように調整
        # SemA: 2人 (定員10)
        # SemB: 2人 (定員5)
        # SemC: 2人 (定員8)
        expected_score = (2.0 * 1.0) + (2.0 * 1.2) + (1.0 * 0.9) + (1.0 * 1.2) + 0.0 + (1.0 * 0.9)
        self.assertAlmostEqual(self.optimizer._calculate_score(assignment), expected_score, places=5)
        self.assertTrue(self.optimizer._is_feasible_assignment(assignment))

    def test_is_feasible_assignment_valid(self):
        """
        有効な割り当て（定員内）の実行可能性をテストする。
        """
        assignment = {
            "S1": "SemA",
            "S2": "SemA",
            "S3": "SemB",
            "S4": "SemC",
        }
        self.assertTrue(self.optimizer._is_feasible_assignment(assignment))

    def test_is_feasible_assignment_exceeds_capacity(self):
        """
        定員を超える割り当ての実行可能性をテストする。
        SemBの定員は5
        """
        assignment = {
            "S1": "SemB",
            "S2": "SemB",
            "S3": "SemB",
            "S4": "SemB",
            "S5": "SemB",
            "S6": "SemB", # SemBの定員を超える
        }
        self.assertFalse(self.optimizer._is_feasible_assignment(assignment))

    def test_is_feasible_assignment_invalid_seminar_id(self):
        """
        存在しないセミナーIDへの割り当ての実行可能性をテストする。
        """
        assignment = {
            "S1": "SemX", # 存在しないセミナー
            "S2": "SemA",
        }
        self.assertFalse(self.optimizer._is_feasible_assignment(assignment))

    def test_get_unassigned_students(self):
        """
        未割り当て学生のリスト取得をテストする。
        """
        assignment = {
            "S1": "SemA",
            "S2": "SemB",
            "S3": "SemA",
        }
        unassigned = self.optimizer._get_unassigned_students(assignment)
        # 未割り当ては S4, S5, S6
        self.assertCountEqual(unassigned, ["S4", "S5", "S6"])
        self.assertEqual(len(unassigned), 3)

    def test_get_unassigned_students_all_assigned(self):
        """
        全ての学生が割り当てられた場合の未割り当て学生リストをテストする。
        """
        assignment = {s['id']: s['preferences'][0] for s in self.students_data if s['preferences']}
        # ただし、この割り当ては定員制約を満たさない可能性があるので注意
        unassigned = self.optimizer._get_unassigned_students(assignment)
        self.assertEqual(len(unassigned), 0)
        self.assertEqual(unassigned, [])

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

