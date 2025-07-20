# test_seminar_optimizer.py

import pytest
import os
import shutil
import logging
import numpy as np
import numbers # For checking integer types

# main.py から必要なクラスをインポート
from seminar_optimization.main import Student, Config, SeminarOptimizer, MultiStageOptimizer

# テスト用のロガー設定 (テスト実行時のログ出力を制御)
@pytest.fixture(autouse=True)
def cap_log(caplog):
    # テスト実行中はロギングレベルをDEBUGに設定
    caplog.set_level(logging.DEBUG)
    yield
    # テスト終了後にロギングレベルを元に戻す（またはデフォルトに戻す）
    caplog.set_level(logging.INFO)

# テスト結果ディレクトリの準備とクリーンアップ
@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown_test_results():
    test_output_dir = "test_results"
    # テストディレクトリが存在すれば削除し、新しく作成
    if os.path.exists(test_output_dir):
        shutil.rmtree(test_output_dir)
    os.makedirs(test_output_dir)
    yield
    # テスト終了後にテストディレクトリをクリーンアップ
    if os.path.exists(test_output_dir):
        shutil.rmtree(test_output_dir)

# Studentクラスのテスト (main.pyのStudentクラスに合わせたテスト)
class TestStudent:
    def test_student_creation(self):
        """Studentクラスが正しく初期化されるかテスト"""
        student = Student(id=1, preferences=["A", "B"], features=np.array([1.0, 2.0]))
        assert student.id == 1
        assert student.preferences == ["A", "B"]
        assert np.array_equal(student.features, np.array([1.0, 2.0]))

    def test_student_default_values(self):
        """Studentクラスのデフォルト値が正しく設定されるかテスト"""
        student = Student(id=2)
        assert student.preferences == []
        assert np.array_equal(student.features, np.array([]))

# Configクラスのテスト
class TestConfig:
    def test_config_creation(self):
        """Configクラスが正しく初期化されるかテスト"""
        config = Config(
            seminars=["A", "B"],
            min_size=1,
            max_size=5,
            num_students=10,
            preference_weights={"1st": 5.0},
            cp_time_limit=60,
            output_dir="output",
            kmeans_n_clusters=3,
            kmeans_random_state=10
        )
        assert config.seminars == ["A", "B"]
        assert config.min_size == 1
        assert config.max_size == 5
        assert config.num_students == 10
        assert config.preference_weights == {"1st": 5.0}
        assert config.cp_time_limit == 60
        assert config.output_dir == "output"
        assert config.kmeans_n_clusters == 3
        assert config.kmeans_random_state == 10

# SeminarOptimizerクラスのテスト
class TestSeminarOptimizer:
    @pytest.fixture
    def sample_config(self):
        """テスト用のConfigオブジェクトを提供するフィクスチャ"""
        # num_studentsはsample_studentsの数に合わせて調整する
        return Config(
            seminars=['Seminar A', 'Seminar B', 'Seminar C'],
            min_size=1,
            max_size=2,
            num_students=6, # sample_studentsの数に合わせる
            preference_weights={"1st": 5.0, "2nd": 3.0, "3rd": 1.0},
            cp_time_limit=10,
            output_dir="test_results",
            kmeans_n_clusters=2,
            kmeans_random_state=42,
            debug_mode=True
        )

    @pytest.fixture
    def sample_students(self):
        """テスト用のStudentオブジェクトのリストを提供するフィクスチャ"""
        # main.py の Student クラスの定義に合わせて修正
        return [
            Student(id=1, preferences=['Seminar A', 'Seminar B', 'Seminar C']),
            Student(id=2, preferences=['Seminar B', 'Seminar A', 'Seminar C']),
            Student(id=3, preferences=['Seminar C', 'Seminar B', 'Seminar A']),
            Student(id=4, preferences=['Seminar A', 'Seminar C']),
            Student(id=5, preferences=[]), # 希望データがない学生
            Student(id=6, preferences=['Seminar X', 'Seminar A']) # 存在しないセミナーを希望する学生
        ]

    @pytest.fixture
    def seminar_optimizer(self, sample_config, sample_students):
        """SeminarOptimizerインスタンスを提供するフィクスチャ"""
        return SeminarOptimizer(sample_config, sample_students)

    def test_get_preference_score(self, seminar_optimizer):
        """get_preference_scoreメソッドのテスト"""
        # 1st preference
        assert seminar_optimizer.get_preference_score(1, "Seminar A") == 5.0
        # 2nd preference
        assert seminar_optimizer.get_preference_score(1, "Seminar B") == 3.0
        # 3rd preference
        assert seminar_optimizer.get_preference_score(1, "Seminar C") == 1.0
        # Not in preferences
        assert seminar_optimizer.get_preference_score(1, "Seminar D") == 0.0
        # Case sensitivity and stripping
        assert seminar_optimizer.get_preference_score(1, " seminar a ") == 5.0
        # 存在しない学生ID
        assert seminar_optimizer.get_preference_score(99, "Seminar A") == 0.0


    def test_validate_inputs(self, seminar_optimizer, sample_config, sample_students, caplog):
        """validate_inputsメソッドのテスト"""
        # 正常系: 警告なしのケース
        valid_config = Config(
            seminars=["A", "B"],
            min_size=1,
            max_size=2,
            num_students=2,
            preference_weights={"1st": 5.0},
            cp_time_limit=10,
            output_dir="test_results",
            kmeans_n_clusters=1,
            kmeans_random_state=42,
            debug_mode=False
        )
        valid_students = [
            Student(id=1, preferences=["A"]),
            Student(id=2, preferences=["B"])
        ]
        valid_optimizer = SeminarOptimizer(valid_config, valid_students)
        warnings = valid_optimizer.validate_inputs()
        assert len(warnings) == 0

        # 警告が出るケース: 学生数と定員の不整合
        # 学生数が最小定員合計より少ない
        config_low_students = Config(
            seminars=["A", "B"], min_size=2, max_size=3, num_students=1,
            preference_weights={"1st": 5.0}, cp_time_limit=10, output_dir="test_results",
            kmeans_n_clusters=1, kmeans_random_state=42
        )
        optimizer_low_students = SeminarOptimizer(config_low_students, [Student(id=1, preferences=["A"])])
        warnings = optimizer_low_students.validate_inputs()
        assert any("学生数" in w and "最小定員合計" in w for w in warnings)

        # 学生数が最大定員合計より多い
        config_high_students = Config(
            seminars=["A", "B"], min_size=1, max_size=1, num_students=3,
            preference_weights={"1st": 5.0}, cp_time_limit=10, output_dir="test_results",
            kmeans_n_clusters=1, kmeans_random_state=42
        )
        optimizer_high_students = SeminarOptimizer(config_high_students, [Student(id=1, preferences=["A"]), Student(id=2, preferences=["B"]), Student(id=3, preferences=["A"])])
        warnings = optimizer_high_students.validate_inputs()
        assert any("学生数" in w and "最大定員合計" in w for w in warnings)

        # 警告が出るケース: 希望データがない学生 (sample_studentsを使用)
        warnings = seminar_optimizer.validate_inputs()
        assert any(f"学生ID {5} に希望データがありません" in w for w in warnings)

        # 警告が出るケース: 希望セミナー名が設定されたセミナーリストに含まれていない (sample_studentsを使用)
        assert any(f"学生ID {6} の希望セミナー 'Seminar X' が、設定されたセミナーリストに含まれていません。" in w for w in warnings)

        # 警告が出るケース: 重み設定がない
        config_no_weights = Config(
            seminars=["A"], min_size=1, max_size=1, num_students=1,
            preference_weights={}, cp_time_limit=10, output_dir="test_results",
            kmeans_n_clusters=1, kmeans_random_state=42
        )
        optimizer_no_weights = SeminarOptimizer(config_no_weights, [Student(id=1, preferences=["A"])])
        warnings = optimizer_no_weights.validate_inputs()
        assert "警告: 希望順位の重みが設定されていません。" in warnings

    def test_optimize_optimal_solution(self, seminar_optimizer, sample_config, caplog):
        """optimizeメソッドのテスト (最適解が見つかるケース)"""
        with caplog.at_level(logging.INFO):
            pattern_sizes, overall_score, final_assignments = seminar_optimizer.optimize()

            # 解が見つかったことを確認
            assert overall_score >= 0
            assert len(pattern_sizes) == len(seminar_optimizer.seminar_names)
            assert sum(pattern_sizes.values()) == seminar_optimizer.num_students

            # ログに「最適解が見つかりました」または「実行可能解が見つかりました」が出力されたか確認
            # caplog.records をループして、メッセージ内容を確認
            found_solution_log = False
            for record in caplog.records:
                if "最適解が見つかりました" in record.message or "実行可能解が見つかりました" in record.message:
                    found_solution_log = True
                    break
            assert found_solution_log

            # 各セミナーの定員制約が守られているか確認
            for seminar, count in pattern_sizes.items():
                assert seminar_optimizer.min_size <= count <= seminar_optimizer.max_size

            # 各学生が1つのセミナーに割り当てられているか確認
            assigned_student_ids = set()
            for sem_students in final_assignments.values():
                for student_id, _ in sem_students:
                    assigned_student_ids.add(student_id)
            assert len(assigned_student_ids) == seminar_optimizer.num_students


    def test_optimize_infeasible_case(self, sample_config, caplog):
        """
        optimizeメソッドのテスト (実行可能解が見つからないケース)
        制約が厳しすぎる設定でテストする。
        """
        # 極端な制約を設定して、解が見つからないようにする
        infeasible_config = Config(
            seminars=["A", "B"],
            min_size=10, # 各セミナーに10人必要だが、学生は少ない
            max_size=10,
            num_students=3, # 学生は3人しかいない
            preference_weights={"1st": 5.0},
            cp_time_limit=1, # 短い時間制限
            output_dir="test_results",
            kmeans_n_clusters=1,
            kmeans_random_state=42
        )
        infeasible_students = [
            Student(id=1, preferences=["A"]),
            Student(id=2, preferences=["B"]),
            Student(id=3, preferences=["A"])
        ]
        infeasible_optimizer = SeminarOptimizer(infeasible_config, infeasible_students)

        # ログキャプチャレベルをlogging.INFOに変更して、提案メッセージをキャプチャできるようにする
        with caplog.at_level(logging.INFO):
            pattern_sizes, overall_score, final_assignments = infeasible_optimizer.optimize()

            # 解が見つからなかったことを示す値が返されることを確認
            assert overall_score == -1.0
            assert not pattern_sizes
            # final_assignmentsは空の辞書ではなく、セミナー名がキーで値が空リストの辞書になることを確認
            assert final_assignments == {'A': [], 'B': []}

            # ログに「解が見つかりませんでした」と「実行可能解が存在しません」が出力されたか確認
            found_no_solution_log = False
            found_infeasible_log = False
            found_suggestion_log = False
            for record in caplog.records:
                if "解が見つかりませんでした" in record.message:
                    found_no_solution_log = True
                if "実行可能解が存在しません" in record.message:
                    found_infeasible_log = True
                if "提案: セミナーの最小定員を約" in record.message and "最大定員を約" in record.message:
                    found_suggestion_log = True
            assert found_no_solution_log
            assert found_infeasible_log
            assert found_suggestion_log


# MultiStageOptimizerクラスのテスト
class TestMultiStageOptimizer:
    @pytest.fixture
    def sample_config(self):
        """テスト用のConfigオブジェクトを提供するフィクスチャ (MultiStageOptimizer用)"""
        # num_studentsはsample_studentsの数に合わせて調整する
        return Config(
            seminars=['Seminar A', 'Seminar B', 'Seminar C'],
            min_size=1,
            max_size=2,
            num_students=6, # sample_studentsの数に合わせる
            preference_weights={"1st": 5.0, "2nd": 3.0, "3rd": 1.0},
            cp_time_limit=10,
            output_dir="test_results",
            kmeans_n_clusters=1, # ここを2から1に変更し、全ての学生が1つのクラスターにまとめられるようにする
            kmeans_random_state=42,
            debug_mode=True
        )

    @pytest.fixture
    def sample_students(self):
        """テスト用のStudentオブジェクトのリストを提供するフィクスチャ (MultiStageOptimizer用)"""
        return [
            Student(id=1, preferences=['Seminar A', 'Seminar B', 'Seminar C']),
            Student(id=2, preferences=['Seminar B', 'Seminar A', 'Seminar C']),
            Student(id=3, preferences=['Seminar C', 'Seminar B', 'Seminar A']),
            Student(id=4, preferences=['Seminar A', 'Seminar C']),
            Student(id=5, preferences=[]), # 希望データがない学生
            Student(id=6, preferences=['Seminar X', 'Seminar A']) # 存在しないセミナーを希望する学生
        ]

    def test_run_clustering(self, sample_config, sample_students, caplog):
        """K-Meansクラスタリングの実行テスト"""
        multi_optimizer = MultiStageOptimizer(sample_config, sample_students)

        with caplog.at_level(logging.INFO):
            multi_optimizer.run_clustering()

            # K-Meansモデルが作成されたことを確認
            # 希望がない学生（id=5）と存在しないセミナーを希望する学生（id=6）は特徴量ベクトルが全て0になる可能性があるため、
            # クラスタリングがスキップされる場合がある。その場合、kmeans_modelはNoneになる。
            # このテストでは、クラスタリングが実行されることを期待する。
            assert multi_optimizer.kmeans_model is not None
            # 各学生にcluster_idが割り当てられたことを確認
            for student in sample_students:
                # クラスタリングがスキップされた学生はcluster_idを持たない可能性があるため、hasattrで確認
                if hasattr(student, 'cluster_id'):
                    assert isinstance(student.cluster_id, (int, numbers.Integral))
                else:
                    # スキップされた学生（例: 希望がない学生）はcluster_idを持たないことを許容
                    assert student.id == 5 or student.id == 6


    def test_run_clustering_no_features(self, sample_config, caplog):
        """特徴量データがない場合のK-Meansクラスタリングのテスト"""
        # 希望がない学生のみのリスト
        students_no_prefs = [Student(id=1, preferences=[]), Student(id=2, preferences=[])]
        config_no_prefs = Config(
            seminars=sample_config.seminars,
            min_size=sample_config.min_size,
            max_size=sample_config.max_size,
            num_students=len(students_no_prefs), # 学生数に合わせる
            preference_weights=sample_config.preference_weights,
            cp_time_limit=sample_config.cp_time_limit,
            output_dir=sample_config.output_dir,
            kmeans_n_clusters=sample_config.kmeans_n_clusters,
            kmeans_random_state=sample_config.kmeans_random_state,
            debug_mode=sample_config.debug_mode
        )
        multi_optimizer = MultiStageOptimizer(config_no_prefs, students_no_prefs)

        with caplog.at_level(logging.WARNING):
            multi_optimizer.run_clustering()
            # K-Meansモデルが作成されないことを確認
            assert multi_optimizer.kmeans_model is None
            # ログに「クラスタリングをスキップします」が出力されたか確認
            assert any("クラスタリングをスキップします" in record.message for record in caplog.records)


    def test_run_end_to_end(self, sample_config, sample_students, caplog):
        """MultiStageOptimizerのend-to-endテスト"""
        multi_optimizer = MultiStageOptimizer(sample_config, sample_students)

        with caplog.at_level(logging.INFO):
            pattern_sizes, overall_score, final_assignments = multi_optimizer.run()

            # クラスタリングと最適化の両方が実行されたことを確認
            # 希望がない学生（id=5）と存在しないセミナーを希望する学生（id=6）は特徴量ベクトルが全て0になる可能性があるため、
            # クラスタリングがスキップされる場合がある。その場合、kmeans_modelはNoneになる。
            # このテストでは、クラスタリングが実行されることを期待する。
            assert multi_optimizer.kmeans_model is not None
            assert overall_score >= 0
            assert len(pattern_sizes) == len(sample_config.seminars)
            assert sum(pattern_sizes.values()) == len(sample_students)

            # 各セミナーが定員制約を満たしているか確認
            for sem, count in pattern_sizes.items():
                assert sample_config.min_size <= count <= sample_config.max_size

            # 各学生が1つのセミナーに割り当てられているか確認
            assigned_student_ids = set()
            for sem_students in final_assignments.values():
                for student_id, _ in sem_students:
                    assigned_student_ids.add(student_id)
            assert len(assigned_student_ids) == len(sample_students)

            # ここからが前回の応答で欠落していた部分です
            # 出力ファイルが生成されたことを確認 (debug_mode=Trueの場合)
            output_dir = sample_config.output_dir
            assert os.path.exists(output_dir)
            assert os.path.isdir(output_dir)

            # CSVファイルが生成されたことを確認
            csv_file_path = os.path.join(output_dir, "seminar_assignments.csv")
            assert os.path.exists(csv_file_path)

            # CSVファイルの内容を検証 (簡易的なチェック)
            with open(csv_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                assert len(lines) > 1 # ヘッダーとデータ行
                # ヘッダーの確認
                assert "Student ID,Assigned Seminar,Preference Score,Cluster ID" in lines[0]
                # 各学生が割り当てられているか、スコアが数値かなどを確認
                # ここでは詳細な内容検証は省略し、ファイルが存在することと基本的な形式をチェック

            # JSONファイルが生成されたことを確認
            json_file_path = os.path.join(output_dir, "seminar_optimization_results.json")
            assert os.path.exists(json_file_path)

            # JSONファイルの内容を検証 (簡易的なチェック)
            import json
            with open(json_file_path, 'r', encoding='utf-8') as f:
                results_json = json.load(f)
                assert "overall_score" in results_json
                assert "seminar_assignments" in results_json
                assert "seminar_pattern_sizes" in results_json
                assert "config" in results_json
                assert "warnings" in results_json
                assert isinstance(results_json["overall_score"], float)
                assert isinstance(results_json["seminar_assignments"], dict)
                assert isinstance(results_json["seminar_pattern_sizes"], dict)

