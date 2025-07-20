import os
import json
import logging
import random
import numpy as np
from sklearn.cluster import KMeans
from ortools.sat.python import cp_model

# ロギング設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s:%(lineno)d - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ConfigLoader:
    """設定ファイルを読み込むクラス"""
    def __init__(self, config_path='config/config.json'):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self):
        """設定ファイルを読み込む"""
        if not os.path.exists(self.config_path):
            logger.warning(f"設定ファイルが見つかりません: {self.config_path}。デフォルト設定を使用します。")
            return self._create_default_config()
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
            logger.info(f"設定ファイルを読み込みました: {self.config_path}")
            return config
        except json.JSONDecodeError as e:
            logger.error(f"設定ファイルのJSONデコードエラー: {e}")
            return self._create_default_config()
        except Exception as e:
            logger.error(f"設定ファイルの読み込み中にエラーが発生しました: {e}")
            return self._create_default_config()

    def _create_default_config(self):
        """デフォルト設定を作成し、ファイルに保存する"""
        default_config = {
            "data_directory": "data",
            "seminars_file": "seminars.json",
            "students_file": "students.json",
            "results_file": "optimization_results.json",
            "num_seminars": 5,
            "min_capacity": 3, # グローバルな最小定員（seminar_specific_capacitiesがない場合のフォールバック）
            "max_capacity": 6, # グローバルな最大定員（seminar_specific_capacitiesがない場合のフォールバック）
            "seminar_specific_capacities": [
                # ゼミごとの定員を詳細に設定する場合、ここにリストとして追加
                # 例: {"id": "Seminar A", "min_capacity": 4, "max_capacity": 7},
                #     {"id": "Seminar B", "min_capacity": 3, "max_capacity": 5}
                # このリストが空または存在しない場合、上記のmin_capacity/max_capacityが使用されます
            ],
            "num_students": 20,
            "min_preferences": 3,
            "max_preferences": 5,
            "ga_population_size": 100,
            "ga_generations": 200,
            "ga_mutation_rate": 0.1,
            "ga_crossover_rate": 0.8,
            "k_means_clusters": 5,
            "debug_mode": True
        }
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=4)
            logger.info(f"デフォルト設定ファイルを生成しました: {self.config_path}")
        except Exception as e:
            logger.error(f"デフォルト設定ファイルの書き込み中にエラーが発生しました: {e}")
        return default_config

class DataLoader:
    """セミナーと学生のデータを読み込むクラス"""
    def __init__(self, config):
        self.config = config
        self.data_dir = self.config.get('data_directory', 'data')
        os.makedirs(self.data_dir, exist_ok=True)
        self.seminars_file = os.path.join(self.data_dir, self.config.get('seminars_file', 'seminars.json'))
        self.students_file = os.path.join(self.data_dir, self.config.get('students_file', 'students.json'))

        # self.seminars と self.students を初期化
        self.seminars = []
        self.students = []

        # データファイルが存在しない場合、ダミーデータを生成
        if not os.path.exists(self.seminars_file) or not os.path.exists(self.students_file):
            logger.info("データファイルが見つかりません。ダミーデータを生成します。")
            self._generate_dummy_data() # これが self.seminars と self.students を設定する
        else:
            logger.info("既存のデータファイルを読み込みます。")
            # ファイルが存在する場合は、ここでデータを読み込んで属性に設定する
            loaded_seminars, loaded_students = self.load_data()
            self.seminars = loaded_seminars
            self.students = loaded_students

    def _generate_dummy_data(self):
        """ダミーのセミナーと学生データを生成する"""
        num_seminars = self.config.get('num_seminars', 5)
        global_min_capacity = self.config.get('min_capacity', 3)
        global_max_capacity = self.config.get('max_capacity', 6)
        num_students = self.config.get('num_students', 20)
        min_preferences = self.config.get('min_preferences', 3)
        max_preferences = self.config.get('max_preferences', 5)
        
        seminar_specific_capacities = self.config.get('seminar_specific_capacities', [])

        seminars = []
        if seminar_specific_capacities:
            # seminar_specific_capacitiesが設定されている場合
            for i, seminar_detail in enumerate(seminar_specific_capacities):
                # num_seminarsで指定された数を超過しないように調整
                if len(seminars) >= num_seminars:
                    break
                seminar_id = seminar_detail.get("id", f"Seminar {chr(65 + i)}")
                min_cap = seminar_detail.get("min_capacity", global_min_capacity)
                max_cap = seminar_detail.get("max_capacity", global_max_capacity)
                capacity = random.randint(min_cap, max_cap)
                seminars.append({
                    "id": seminar_id,
                    "capacity": capacity
                })
            # num_seminarsとseminar_specific_capacitiesの数が異なる場合を考慮
            if len(seminars) < num_seminars:
                logger.warning(f"seminar_specific_capacitiesの数がnum_seminars({num_seminars})より少ないです。不足分はデフォルト設定で生成します。")
                for i in range(len(seminars), num_seminars):
                    seminars.append({
                        "id": f"Seminar {chr(65 + i)}",
                        "capacity": random.randint(global_min_capacity, global_max_capacity)
                    })
            elif len(seminars) > num_seminars:
                logger.warning(f"seminar_specific_capacitiesの数がnum_seminars({num_seminars})より多いです。最初の{num_seminars}個のセミナーを使用します。")
                seminars = seminars[:num_seminars]
        else:
            # seminar_specific_capacitiesが設定されていない場合、従来のランダム生成
            for i in range(num_seminars):
                seminars.append({
                    "id": f"Seminar {chr(65 + i)}",
                    "capacity": random.randint(global_min_capacity, global_max_capacity)
                })
        
        total_capacity = sum(s['capacity'] for s in seminars)
        if num_students > total_capacity:
            logger.warning(f"警告: 設定された学生数({num_students})がセミナーの総定員({total_capacity})を超過しています。学生数を総定員に合わせます。")
            num_students = total_capacity
        elif num_students < total_capacity:
            logger.info(f"情報: 設定された学生数({num_students})がセミナーの総定員({total_capacity})より少ないです。")


        students = []
        seminar_ids = [s['id'] for s in seminars]
        for i in range(num_students):
            num_prefs = random.randint(min_preferences, max_preferences)
            preferences = random.sample(seminar_ids, min(num_prefs, len(seminar_ids)))
            students.append({
                "id": f"Student {i + 1}",
                "preferences": preferences
            })

        with open(self.seminars_file, 'w', encoding='utf-8') as f:
            json.dump(seminars, f, indent=4, ensure_ascii=False)
        with open(self.students_file, 'w', encoding='utf-8') as f:
            json.dump(students, f, indent=4, ensure_ascii=False)
        logger.info(f"ダミーデータを生成しました: {len(seminars)}セミナー, {len(students)}学生")
        
        # ダミーデータを生成した場合も、DataLoaderの属性に設定する
        self.seminars = seminars
        self.students = students

    def load_data(self):
        """セミナーと学生のデータを読み込む"""
        try:
            with open(self.seminars_file, 'r', encoding='utf-8') as f:
                seminars = json.load(f)
            with open(self.students_file, 'r', encoding='utf-8') as f:
                students = json.load(f)
            logger.info(f"セミナーデータ({len(seminars)}件)と学生データ({len(students)}件)を読み込みました。")
            return seminars, students
        except FileNotFoundError:
            logger.error("データファイルが見つかりません。ダミーデータが生成されているか確認してください。")
            return [], []
        except json.JSONDecodeError as e:
            logger.error(f"データファイルのJSONデコードエラー: {e}")
            return [], []
        except Exception as e:
            logger.error(f"データファイルの読み込み中にエラーが発生しました: {e}")
            return [], []

class CPSATOptimizer:
    """CP-SATソルバーを使用してセミナー割り当てを最適化するクラス"""
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
                elif len(student['preferences']) < len(self.seminar_ids):
                    logger.debug(f"デバッグ: 学生ID {student['id']} の希望が{len(student['preferences'])}個しかありません。")


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

class SeminarOptimizer:
    """セミナー割り当ての全体的なプロセスを管理するクラス"""
    def __init__(self, config_path='config/config.json'):
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.config
        # DataLoaderのインスタンス化時に、データが読み込まれるか生成される
        self.data_loader = DataLoader(self.config) 
        self.debug_mode = self.config.get('debug_mode', False)
        if self.debug_mode:
            logger.debug("デバッグモードが有効です。")

    def run_clustering(self, students):
        """学生の希望に基づいてK-Meansクラスタリングを実行する"""
        logger.info("K-Meansクラスタリングを開始します...")
        # DataLoaderのインスタンスが初期化時にseminars属性を持つようになったため、直接アクセス可能
        seminar_ids_from_data = [s['id'] for s in self.data_loader.seminars] 
        
        student_vectors = []
        for i, student in enumerate(students):
            vector = [0] * len(seminar_ids_from_data)
            for pref_seminar_id in student['preferences']:
                try:
                    idx = seminar_ids_from_data.index(pref_seminar_id)
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

        num_clusters = self.config.get('k_means_clusters', 5)
        if num_clusters > len(student_vectors):
            num_clusters = len(student_vectors)
            logger.warning(f"学生数({len(student_vectors)})がクラスター数({self.config.get('k_means_clusters', 5)})より少ないため、クラスター数を{num_clusters}に調整しました。")
        
        if num_clusters == 0:
            logger.warning("学生数が0人のため、K-Meansクラスタリングは実行されません。")
            return {}

        kmeans = KMeans(n_clusters=num_clusters, random_state=0, n_init=10)
        clusters = kmeans.fit_predict(student_vectors)

        student_clusters = {students[i]['id']: clusters[i] for i in range(len(students))}
        
        logger.info(f"K-Meansクラスタリングが完了しました。クラスター数: {num_clusters}")
        
        cluster_counts = {np.int32(cluster_id): sum(1 for student_id, c_id in student_clusters.items() if c_id == cluster_id) for cluster_id in set(clusters)}
        logger.info(f"各クラスターの学生数: {cluster_counts}")

        if self.debug_mode:
            logger.debug("学生のクラスタリング結果:")
            for student_id, cluster_id in student_clusters.items():
                student_info = next(s for s in students if s['id'] == student_id)
                logger.debug(f"学生ID: {student_id}, 希望: {student_info['preferences']}, クラスタID: {cluster_id}")

        return student_clusters

    def run_optimization(self):
        """最適化プロセスを実行する"""
        # DataLoaderの__init__で既にデータが読み込まれているため、ここでは直接self.data_loader.seminars/studentsを使用
        seminars = self.data_loader.seminars
        students = self.data_loader.students

        if not seminars or not students:
            logger.error("セミナーまたは学生データが読み込まれていません。最適化を中止します。")
            return

        student_clusters = self.run_clustering(students)

        cluster_results = {i: {'students': [], 'seminars': self.data_loader.seminars} for i in range(self.config.get('k_means_clusters', 5))}
        
        for student_id, cluster_id in student_clusters.items():
            student_info = next(s for s in students if s['id'] == student_id)
            if cluster_id in cluster_results:
                cluster_results[cluster_id]['students'].append(student_info)
            else:
                cluster_results[cluster_id] = {'students': [student_info], 'seminars': self.data_loader.seminars}

        final_assignment = {}
        total_overall_score = 0
        
        logger.info("CP-SATソルバーによる最適化を開始します...")

        for cluster_id, data in cluster_results.items():
            cluster_students = data['students']
            if not cluster_students:
                logger.info(f"クラスター {cluster_id} に学生がいません。スキップします。")
                continue

            logger.info(f"クラスター {cluster_id} の学生 {len(cluster_students)} 人に対して最適化を実行します。")
            
            optimizer = CPSATOptimizer(data['seminars'], cluster_students, self.debug_mode)
            assignment, score, status = optimizer.solve()

            if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
                final_assignment.update(assignment)
                total_overall_score += score
            else:
                logger.warning(f"クラスター {cluster_id} で解が見つかりませんでした。このクラスターの結果は統合されません。")

        if final_assignment:
            logger.info("\n--- 最適化結果 ---")
            logger.info(f"総適合度 (合計スコア): {total_overall_score}")

            logger.info("\n--- 学生の割り当て ---")
            for student_id in sorted(final_assignment.keys(), key=lambda x: int(x.split(' ')[1])):
                assigned_seminar = final_assignment[student_id]
                original_student_info = next(s for s in students if s['id'] == student_id)
                preferences = original_student_info.get('preferences', [])
                
                rank = -1
                if assigned_seminar in preferences:
                    rank = preferences.index(assigned_seminar) + 1
                
                rank_str = f"({rank}位希望)" if rank != -1 else "(希望外)"
                logger.info(f"学生 {student_id}: {assigned_seminar} {rank_str}")

            logger.info("\n--- セミナーの割り当て状況 ---")
            seminar_counts = {s['id']: 0 for s in seminars}
            for assigned_seminar in final_assignment.values():
                seminar_counts[assigned_seminar] += 1

            for seminar in seminars:
                seminar_id = seminar['id']
                capacity = seminar['capacity']
                assigned_students = seminar_counts.get(seminar_id, 0)
                status = "定員内"
                if assigned_students > capacity:
                    status = f"定員超過 (+{assigned_students - capacity})"
                elif assigned_students < capacity:
                    status = f"空きあり ({capacity - assigned_students}席)"
                logger.info(f"セミナー {seminar_id}: 割り当て {assigned_students} / 定員 {capacity} ({status})")

            results_path = os.path.join(self.data_loader.data_dir, self.config.get('results_file', 'optimization_results.json'))
            output_data = {
                "total_score": total_overall_score,
                "student_assignments": final_assignment,
                "seminar_summary": {
                    s['id']: {
                        "capacity": s['capacity'],
                        "assigned_students": seminar_counts.get(s['id'], 0)
                    } for s in seminars
                }
            }
            with open(results_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, indent=4, ensure_ascii=False)
            logger.info(f"最適化結果が '{results_path}' に保存されました。")

        else:
            logger.error("最適化結果が得られませんでした。")

if __name__ == "__main__":
    config_loader = ConfigLoader()
    # DataLoaderのインスタンス化時に、データが読み込まれるか生成されるようになった
    data_loader = DataLoader(config_loader.config) 
    optimizer = SeminarOptimizer(config_path='config/config.json')
    optimizer.run_optimization()
