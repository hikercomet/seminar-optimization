# seminar_optimization/optimizer_service.py

import json
import csv
import random
import os
import logging
import numpy as np
from sklearn.cluster import KMeans
from ortools.sat.python import cp_model
from collections import defaultdict

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SeminarOptimizerCore:
    """CP-SATソルバーを使用してセミナー割り当てを最適化するコアロジック"""
    def __init__(self, seminars, students, debug_mode=False):
        self.seminars = seminars
        self.students = students
        self.debug_mode = debug_mode
        self.seminar_ids = [s['id'] for s in seminars]
        self.seminar_capacities = {s['id']: s['capacity'] for s in seminars}
        self.student_ids = [s['id'] for s in students]
        self.student_preferences = {s['id']: s['preferences'] for s in students}

        if self.debug_mode:
            logger.debug("デバッグモードが有効です。")
            total_student_count = len(self.students)
            total_seminar_capacity = sum(self.seminar_capacities.values())
            if total_student_count > total_seminar_capacity:
                logger.warning(f"警告: 学生数({total_student_count})が全セミナーの総定員({total_seminar_capacity})を超過しています。解が見つからない可能性があります。")
            elif total_student_count < total_seminar_capacity:
                logger.info(f"情報: 学生数({total_student_count})が全セミナーの総定員({total_seminar_capacity})より少ないです。")
            
            for student in students:
                if not student['preferences']:
                    logger.warning(f"警告: 学生ID {student['id']} に希望データがありません。")
                # elif len(student['preferences']) < len(self.seminar_ids):
                #     logger.debug(f"デバッグ: 学生ID {student['id']} の希望が{len(student['preferences'])}個しかありません。")


    def solve(self, time_limit=60):
        """CP-SATモデルを構築し、解を求める"""
        model = cp_model.CpModel()

        x = {}
        for student_id in self.student_ids:
            for seminar_id in self.seminar_ids:
                x[(student_id, seminar_id)] = model.NewBoolVar(f'x_{student_id}_{seminar_id}')

        for student_id in self.student_ids:
            model.Add(sum(x[(student_id, seminar_id)] for seminar_id in self.seminar_ids) == 1)

        for seminar_id in self.seminar_ids:
            model.Add(sum(x[(student_id, seminar_id)] for student_id in self.student_ids) <= self.seminar_capacities[seminar_id])

        objective_terms = []
        for student_id in self.student_ids:
            for rank, preferred_seminar_id in enumerate(self.student_preferences[student_id]):
                score = 0
                if rank == 0:
                    score = 100
                elif rank == 1:
                    score = 50
                elif rank == 2:
                    score = 25
                
                if preferred_seminar_id in self.seminar_ids:
                    objective_terms.append(x[(student_id, preferred_seminar_id)] * score)
                else:
                    logger.warning(f"学生 {student_id} の希望 {preferred_seminar_id} は存在しないセミナーIDです。")
                    pass

        model.Maximize(sum(objective_terms))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit
        solver.parameters.num_search_workers = 16
        solver.parameters.log_search_progress = True

        logger.info("CP-SATモデルの構築を開始します...")
        logger.info(f"ソルバーの実行を開始します (時間制限: {time_limit}秒, ワーカー数: {solver.parameters.num_search_workers})...")
        status = solver.Solve(model)

        assignment = {}
        total_score = 0
        
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            logger.info("解が見つかりました。")
            for student_id in self.student_ids:
                assigned_seminar = None
                for seminar_id in self.seminar_ids:
                    if solver.Value(x[(student_id, seminar_id)]) == 1:
                        assigned_seminar = seminar_id
                        assignment[student_id] = assigned_seminar
                        
                        if student_id in self.student_preferences and assigned_seminar in self.student_preferences[student_id]:
                            rank = self.student_preferences[student_id].index(assigned_seminar)
                            if rank == 0:
                                total_score += 100
                            elif rank == 1:
                                total_score += 50
                            elif rank == 2:
                                total_score += 25
                        break
            
            return assignment, total_score, status
        else:
            logger.error(f"解が見つかりませんでした。ソルバーステータス: {solver.StatusName(status)}")
            if status == cp_model.INFEASIBLE:
                logger.error("実行可能解が存在しません。制約が厳しすぎる可能性があります。")
                total_student_count = len(self.students)
                total_seminar_capacity = sum(self.seminar_capacities.values())
                if total_student_count > total_seminar_capacity:
                    logger.info(f"提案: 学生数({total_student_count})がセミナーの総定員({total_seminar_capacity})を超過しています。学生数を減らすか、セミナー定員を増やすことを検討してください。")
                elif total_student_count < total_seminar_capacity:
                    logger.info(f"提案: 学生数({total_student_count})がセミナーの総定員({total_seminar_capacity})より少ないです。セミナーの定員を学生数に近づけるか、学生数を増やすことを検討してください。")
                else:
                    logger.info(f"提案: 学生数とセミナー総定員は一致していますが、学生の希望とセミナーの定員制約が厳しすぎる可能性があります。希望の多様化や定員の調整を検討してください。")
            return {}, 0, status

class MultiStageOptimizer:
    """K-MeansクラスタリングとCP-SATを組み合わせた多段階最適化クラス"""
    def __init__(self, seminars, students, k_means_clusters=5, debug_mode=False):
        self.seminars = seminars
        self.students = students
        self.k_means_clusters = k_means_clusters
        self.debug_mode = debug_mode
        self.seminar_ids = [s['id'] for s in seminars]

    def run_clustering(self):
        """学生の希望に基づいてK-Meansクラスタリングを実行する"""
        logger.info("K-Meansクラスタリングを開始します...")
        
        student_vectors = []
        for student in self.students:
            vector = [0] * len(self.seminar_ids)
            for pref_seminar_id in student['preferences']:
                try:
                    idx = self.seminar_ids.index(pref_seminar_id)
                    rank = student['preferences'].index(pref_seminar_id)
                    if rank == 0: vector[idx] = 3
                    elif rank == 1: vector[idx] = 2
                    elif rank == 2: vector[idx] = 1
                    else: vector[idx] = 0.5
                except ValueError:
                    logger.warning(f"学生 {student['id']} の希望 {pref_seminar_id} は存在しないセミナーIDです。")
                    pass
            student_vectors.append(vector)

        if not student_vectors:
            logger.warning("クラスタリングする学生データがありません。")
            return {}

        num_clusters = self.k_means_clusters
        if num_clusters > len(student_vectors):
            num_clusters = len(student_vectors)
            logger.warning(f"学生数({len(student_vectors)})がクラスター数({self.k_means_clusters})より少ないため、クラスター数を{num_clusters}に調整しました。")
        
        if num_clusters == 0:
            logger.warning("学生数が0人のため、K-Meansクラスタリングは実行されません。")
            return {}

        kmeans = KMeans(n_clusters=num_clusters, random_state=0, n_init=10)
        clusters = kmeans.fit_predict(student_vectors)

        student_clusters = {self.students[i]['id']: clusters[i] for i in range(len(self.students))}
        
        logger.info(f"K-Meansクラスタリングが完了しました。クラスター数: {num_clusters}")
        
        cluster_counts = {np.int32(cluster_id): sum(1 for student_id, c_id in student_clusters.items() if c_id == cluster_id) for cluster_id in set(clusters)}
        logger.info(f"各クラスターの学生数: {cluster_counts}")

        if self.debug_mode:
            logger.debug("学生のクラスタリング結果:")
            for student_id, cluster_id in student_clusters.items():
                student_info = next(s for s in self.students if s['id'] == student_id)
                logger.debug(f"学生ID: {student_id}, 希望: {student_info['preferences']}, クラスタID: {cluster_id}")

        return student_clusters

    def optimize(self):
        """多段階最適化プロセスを実行する"""
        student_clusters = self.run_clustering()

        cluster_results = {i: {'students': [], 'seminars': self.seminars} for i in range(self.k_means_clusters)}
        
        for student_id, cluster_id in student_clusters.items():
            student_info = next(s for s in self.students if s['id'] == student_id)
            if cluster_id in cluster_results:
                cluster_results[cluster_id]['students'].append(student_info)
            else:
                cluster_results[cluster_id] = {'students': [student_info], 'seminars': self.seminars}

        final_assignment = {}
        total_overall_score = 0
        
        logger.info("CP-SATソルバーによる最適化を開始します...")

        for cluster_id, data in cluster_results.items():
            cluster_students = data['students']
            if not cluster_students:
                logger.info(f"クラスター {cluster_id} に学生がいません。スキップします。")
                continue

            logger.info(f"クラスター {cluster_id} の学生 {len(cluster_students)} 人に対して最適化を実行します。")
            
            optimizer = SeminarOptimizerCore(data['seminars'], cluster_students, self.debug_mode)
            assignment, score, status = optimizer.solve()

            if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
                final_assignment.update(assignment)
                total_overall_score += score
            else:
                logger.warning(f"クラスター {cluster_id} で解が見つかりませんでした。このクラスターの結果は統合されません。")

        return final_assignment, total_overall_score

def run_optimization_service(config_data: dict, seminars_data: list = None, students_data: list = None) -> dict:
    """
    外部から呼び出される最適化サービスのエントリーポイント。
    config_data: 設定を含む辞書
    seminars_data: セミナーデータ（直接渡された場合）
    students_data: 学生データ（直接渡された場合）
    """
    logger.info("最適化サービスを開始します。")

    # 設定の取得
    debug_mode = config_data.get('debug_mode', False)
    k_means_clusters = config_data.get('k_means_clusters', 5)
    
    # データソースの選択とデータの準備
    data_source = config_data.get('data_source', 'dummy')
    
    current_seminars = []
    current_students = []

    if data_source == 'json' or data_source == 'csv':
        # JSON/CSVはファイルパスが渡されるが、このサービスでは直接ファイル読み込みを行わない
        # フロントエンドから渡されたダミーデータ（または実際のデータ）を使用
        if seminars_data and students_data:
            current_seminars = seminars_data
            current_students = students_data
            logger.info(f"フロントエンドから渡されたデータを使用します (ソース: {data_source})。")
        else:
            logger.error(f"データソースが'{data_source}'ですが、セミナーまたは学生データが渡されませんでした。最適化を中止します。")
            return {"error": "データが不足しています。", "status": "FAILED"}
    elif data_source == 'code_input':
        if seminars_data and students_data:
            current_seminars = seminars_data
            current_students = students_data
            logger.info("コードからの直接入力データを使用します。")
        else:
            logger.error("データソースが'code_input'ですが、セミナーまたは学生データが渡されませんでした。最適化を中止します。")
            return {"error": "データが不足しています。", "status": "FAILED"}
    elif data_source == 'dummy':
        num_seminars = config_data.get('dummy_num_seminars', 5)
        num_students = config_data.get('dummy_num_students', 20)
        
        # ダミーデータの生成ロジックをここに統合
        current_seminars = []
        global_min_capacity = config_data.get('min_capacity', 3)
        global_max_capacity = config_data.get('max_capacity', 6)
        seminar_specific_capacities = config_data.get('seminar_specific_capacities', [])

        if seminar_specific_capacities:
            for i, seminar_detail in enumerate(seminar_specific_capacities):
                if len(current_seminars) >= num_seminars: break
                seminar_id = seminar_detail.get("id", f"Seminar {chr(65 + i)}")
                min_cap = seminar_detail.get("min_capacity", global_min_capacity)
                max_cap = seminar_detail.get("max_capacity", global_max_capacity)
                capacity = random.randint(min_cap, max_cap)
                current_seminars.append({"id": seminar_id, "capacity": capacity})
            if len(current_seminars) < num_seminars:
                logger.warning(f"特定のセミナー定員設定の数が不足しています。不足分はデフォルトで生成します。")
                for i in range(len(current_seminars), num_seminars):
                    current_seminars.append({"id": f"Seminar {chr(65 + i)}", "capacity": random.randint(global_min_capacity, global_max_capacity)})
            elif len(current_seminars) > num_seminars:
                current_seminars = current_seminars[:num_seminars]
        else:
            for i in range(num_seminars):
                current_seminars.append({"id": f"Seminar {chr(65 + i)}", "capacity": random.randint(global_min_capacity, global_max_capacity)})
        
        total_capacity = sum(s['capacity'] for s in current_seminars)
        if num_students > total_capacity:
            logger.warning(f"設定された学生数({num_students})がセミナーの総定員({total_capacity})を超過しています。学生数を総定員に合わせます。")
            num_students = total_capacity
        elif num_students < total_capacity:
            logger.info(f"情報: 設定された学生数({num_students})がセミナーの総定員({total_capacity})より少ないです。")

        current_students = []
        seminar_ids = [s['id'] for s in current_seminars]
        min_preferences = config_data.get('min_preferences', 3)
        max_preferences = config_data.get('max_preferences', 5)

        for i in range(num_students):
            num_prefs = random.randint(min_preferences, max_preferences)
            preferences = random.sample(seminar_ids, min(num_prefs, len(seminar_ids)))
            current_students.append({"id": f"Student {i + 1}", "preferences": preferences})
        
        logger.info(f"ダミーデータを生成しました: {len(current_seminars)}セミナー, {len(current_students)}学生。")

    else:
        logger.error(f"不明なデータソース '{data_source}' が指定されました。最適化を中止します。")
        return {"error": "不明なデータソース", "status": "FAILED"}

    if not current_seminars or not current_students:
        logger.error("セミナーまたは学生データが準備できませんでした。最適化を中止します。")
        return {"error": "データ準備失敗", "status": "FAILED"}

    # 最適化の実行
    optimizer = MultiStageOptimizer(current_seminars, current_students, k_means_clusters, debug_mode)
    final_assignment, total_overall_score = optimizer.optimize()

    # 結果の集計
    seminar_counts = {s['id']: 0 for s in current_seminars}
    for assigned_seminar in final_assignment.values():
        seminar_counts[assigned_seminar] += 1

    seminar_summary = {}
    for seminar in current_seminars:
        seminar_id = seminar['id']
        capacity = seminar['capacity']
        assigned_students = seminar_counts.get(seminar_id, 0)
        seminar_summary[seminar_id] = {
            "capacity": capacity,
            "assigned_students": assigned_students,
            "status": "定員内"
        }
        if assigned_students > capacity:
            seminar_summary[seminar_id]["status"] = f"定員超過 (+{assigned_students - capacity})"
        elif assigned_students < capacity:
            seminar_summary[seminar_id]["status"] = f"空きあり ({capacity - assigned_students}席)"

    # 結果を返す
    return {
        "total_score": total_overall_score,
        "student_assignments": final_assignment,
        "seminar_summary": seminar_summary,
        "status": "SUCCESS"
    }

# このファイルが直接実行された場合のテスト用
if __name__ == "__main__":
    # ダミー設定
    test_config = {
        "data_source": "dummy",
        "dummy_num_seminars": 3,
        "dummy_num_students": 7,
        "min_capacity": 2,
        "max_capacity": 3,
        "min_preferences": 1,
        "max_preferences": 2,
        "k_means_clusters": 2,
        "debug_mode": True
    }
    
    # テスト実行
    result = run_optimization_service(test_config)
    print("\n--- サービス実行結果 ---")
    print(json.dumps(result, indent=4, ensure_ascii=False))

    # コードからの直接入力のテスト
    test_seminars_data = [
        {"id": "Test_S1", "capacity": 2},
        {"id": "Test_S2", "capacity": 3}
    ]
    test_students_data = [
        {"id": "Test_ST1", "preferences": ["Test_S1"]},
        {"id": "Test_ST2", "preferences": ["Test_S2"]},
        {"id": "Test_ST3", "preferences": ["Test_S1", "Test_S2"]}
    ]
    test_config_code_input = {
        "data_source": "code_input",
        "k_means_clusters": 1,
        "debug_mode": True
    }
    result_code_input = run_optimization_service(test_config_code_input, test_seminars_data, test_students_data)
    print("\n--- コード入力サービス実行結果 ---")
    print(json.dumps(result_code_input, indent=4, ensure_ascii=False))
