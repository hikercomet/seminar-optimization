import json
import csv
import random
import logging
from typing import List, Dict, Any, Optional, Tuple
import jsonschema # データスキーマ検証用

# ロギングは logger_config.py で一元的に設定されるため、ここではロガーの取得のみ
from seminar_optimization.logger_config import logger
# スキーマ定義は schemas.py からインポート
from seminar_optimization.schemas import SEMINARS_SCHEMA, STUDENTS_SCHEMA

class DataGenerator:
    """
    セミナー割り当て問題のためのデータを生成またはロードするクラス。
    """
    def __init__(self, config: Dict[str, Any], logger_instance: Optional[logging.Logger] = None):
        self.config = config
        self.logger = logger_instance if logger_instance else logging.getLogger(__name__)
        self.logger.debug("DataGenerator: 初期化を開始します。")

    def generate_data(self,
                      num_seminars: Optional[int] = None,
                      min_capacity: Optional[int] = None,
                      max_capacity: Optional[int] = None,
                      num_students: Optional[int] = None,
                      min_preferences: Optional[int] = None,
                      max_preferences: Optional[int] = None,
                      preference_distribution: str = "random"
                     ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        ランダムなセミナーと学生のデータを生成する。
        GUIからの入力があればそれを優先し、なければconfigを使用する。
        """
        self.logger.info("DataGenerator: ランダムなセミナーと学生のデータを生成します。")

        # GUIからの引数を優先し、なければconfigから取得
        num_seminars = num_seminars if num_seminars is not None else self.config.get("num_seminars", 10)
        min_capacity = min_capacity if min_capacity is not None else self.config.get("min_capacity", 5)
        max_capacity = max_capacity if max_capacity is not None else self.config.get("max_capacity", 10)
        num_students = num_students if num_students is not None else self.config.get("num_students", 50)
        min_preferences = min_preferences if min_preferences is not None else self.config.get("min_preferences", 3)
        max_preferences = max_preferences if max_preferences is not None else self.config.get("max_preferences", 5)
        preference_distribution = preference_distribution if preference_distribution else self.config.get("preference_distribution", "random")
        random_seed = self.config.get("random_seed", None)

        if random_seed is not None:
            random.seed(random_seed)
            # numpy も使用している場合、numpy.random.seed も設定する
            try:
                import numpy as np
                np.random.seed(random_seed)
            except ImportError:
                self.logger.warning("Numpyがインストールされていないため、numpy.random.seedは設定されません。")
            self.logger.debug(f"DataGenerator: 乱数シードを {random_seed} に設定しました。")

        seminars: List[Dict[str, Any]] = []
        for i in range(num_seminars):
            seminar_id = f"S{i+1:03d}"
            capacity = random.randint(min_capacity, max_capacity)
            seminars.append({"id": seminar_id, "capacity": capacity})
        self.logger.debug(f"DataGenerator: {num_seminars} 個のセミナーを生成しました。")

        students: List[Dict[str, Any]] = []
        seminar_ids = [s["id"] for s in seminars]
        for i in range(num_students):
            student_id = f"ST{i+1:04d}"
            num_prefs = random.randint(min_preferences, max_preferences)
            
            prefs = []
            if preference_distribution == "random":
                prefs = random.sample(seminar_ids, min(num_prefs, len(seminar_ids)))
            elif preference_distribution == "uniform":
                # 各セミナーが均等に選ばれるようにする（単純な実装）
                # 実際にはより複雑なロジックが必要になる場合がある
                available_seminars = list(seminar_ids)
                random.shuffle(available_seminars)
                prefs = available_seminars[:min(num_prefs, len(available_seminars))]
            elif preference_distribution == "biased":
                # 特定のセミナーが選ばれやすいようにバイアスをかける
                # 例: 最初の数個のセミナーが選ばれやすい
                biased_pool = seminar_ids[:min(5, len(seminar_ids))] * 5 + seminar_ids # 最初の5つを5倍の重みに
                prefs = random.sample(biased_pool, min(num_prefs, len(biased_pool)))
                prefs = list(dict.fromkeys(prefs)) # 重複を削除し、順序を保持
                if len(prefs) < num_prefs: # 足りない場合はランダムに追加
                    remaining_seminars = [s for s in seminar_ids if s not in prefs]
                    prefs.extend(random.sample(remaining_seminars, min(num_prefs - len(prefs), len(remaining_seminars))))
            
            students.append({"id": student_id, "preferences": prefs})
        self.logger.debug(f"DataGenerator: {num_students} 人の学生を生成しました。")

        # 生成されたデータの検証
        self._validate_data(seminars, students)
        self.logger.info("DataGenerator: データ生成と検証が完了しました。")
        return seminars, students

    def load_from_json(self, seminars_file_path: str, students_file_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        JSONファイルからセミナーと学生のデータをロードする。
        """
        self.logger.info(f"DataGenerator: JSONファイルからデータをロードします。セミナー: {seminars_file_path}, 学生: {students_file_path}")
        try:
            with open(seminars_file_path, 'r', encoding='utf-8') as f:
                seminars_data = json.load(f)
            with open(students_file_path, 'r', encoding='utf-8') as f:
                students_data = json.load(f)
            self.logger.debug("DataGenerator: JSONファイルの読み込みが完了しました。")
            self._validate_data(seminars_data, students_data)
            self.logger.info("DataGenerator: JSONデータのロードと検証が完了しました。")
            return seminars_data, students_data
        except FileNotFoundError as e:
            self.logger.error(f"DataGenerator: ファイルが見つかりません: {e.filename}", exc_info=True)
            raise FileNotFoundError(f"指定されたファイルが見つかりません: {e.filename}")
        except json.JSONDecodeError as e:
            self.logger.error(f"DataGenerator: JSONファイルの解析エラー: {e.msg} (行: {e.lineno}, 列: {e.colno})", exc_info=True)
            raise ValueError(f"JSONファイルの形式が不正です: {e.msg}")
        except Exception as e:
            self.logger.error(f"DataGenerator: JSONファイルのロード中に予期せぬエラーが発生しました: {e}", exc_info=True)
            raise RuntimeError(f"JSONファイルのロード中にエラーが発生しました: {e}")

    def load_from_csv(self, seminars_file_path: str, students_file_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        CSVファイルからセミナーと学生のデータをロードする。
        """
        self.logger.info(f"DataGenerator: CSVファイルからデータをロードします。セミナー: {seminars_file_path}, 学生: {students_file_path}")
        seminars_data = []
        students_data = []
        try:
            # セミナーCSVの読み込み
            with open(seminars_file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                if 'id' not in reader.fieldnames or 'capacity' not in reader.fieldnames:
                    raise ValueError("セミナーCSVには 'id' と 'capacity' カラムが必要です。")
                for row in reader:
                    seminars_data.append({
                        "id": row["id"],
                        "capacity": int(row["capacity"]),
                        "magnification": float(row.get("magnification", 0.0)) # オプション
                    })
            self.logger.debug(f"DataGenerator: セミナーCSVファイル '{seminars_file_path}' を読み込みました。")

            # 学生CSVの読み込み
            with open(students_file_path, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                if 'id' not in reader.fieldnames or 'preferences' not in reader.fieldnames:
                    raise ValueError("学生CSVには 'id' と 'preferences' カラムが必要です。")
                for row in reader:
                    preferences = [p.strip() for p in row["preferences"].split(',') if p.strip()]
                    students_data.append({
                        "id": row["id"],
                        "preferences": preferences
                    })
            self.logger.debug(f"DataGenerator: 学生CSVファイル '{students_file_path}' を読み込みました。")

            self._validate_data(seminars_data, students_data)
            self.logger.info("DataGenerator: CSVデータのロードと検証が完了しました。")
            return seminars_data, students_data
        except FileNotFoundError as e:
            self.logger.error(f"DataGenerator: ファイルが見つかりません: {e.filename}", exc_info=True)
            raise FileNotFoundError(f"指定されたファイルが見つかりません: {e.filename}")
        except ValueError as e:
            self.logger.error(f"DataGenerator: CSVデータの型変換エラーまたは形式エラー: {e}。数値フィールドや必須カラムを確認してください。", exc_info=True)
            raise ValueError(f"CSVデータの形式が不正です: {e}")
        except KeyError as e:
            self.logger.error(f"DataGenerator: CSVヘッダーが見つかりません: {e}。必要なカラムが存在するか確認してください。", exc_info=True)
            raise ValueError(f"CSVの必須カラム '{e}' が見つかりません。")
        except Exception as e:
            self.logger.error(f"DataGenerator: CSVファイルのロード中に予期せぬエラーが発生しました: {e}", exc_info=True)
            raise RuntimeError(f"CSVファイルのロード中にエラーが発生しました: {e}")

    def _validate_data(self, seminars: List[Dict[str, Any]], students: List[Dict[str, Any]]):
        """
        ロードまたは生成されたセミナーと学生のデータをスキーマに基づいて検証する。
        """
        self.logger.debug("DataGenerator: データのスキーマ検証を開始します。")
        try:
            jsonschema.validate(instance=seminars, schema=SEMINARS_SCHEMA)
            self.logger.debug("DataGenerator: セミナーデータのスキーマ検証に成功しました。")
        except jsonschema.exceptions.ValidationError as e:
            self.logger.error(f"DataGenerator: セミナーデータのスキーマ検証エラー: {e.message} (パス: {'.'.join(map(str, e.path))})", exc_info=True)
            raise ValueError(f"セミナーデータの形式が不正です: {e.message} (パス: {'.'.join(map(str, e.path))})")
        
        try:
            jsonschema.validate(instance=students, schema=STUDENTS_SCHEMA)
            self.logger.debug("DataGenerator: 学生データのスキーマ検証に成功しました。")
        except jsonschema.exceptions.ValidationError as e:
            self.logger.error(f"DataGenerator: 学生データのスキーマ検証エラー: {e.message} (パス: {'.'.join(map(str, e.path))})", exc_info=True)
            raise ValueError(f"学生データの形式が不正です: {e.message} (パス: {'.'.join(map(str, e.path))})")

        # 論理的な検証
        seminar_ids = {s['id'] for s in seminars}
        if not seminar_ids:
            self.logger.error("DataGenerator: 論理的検証エラー: セミナーが一つも定義されていません。")
            raise ValueError("セミナーが一つも定義されていません。")

        for student in students:
            for pref_seminar_id in student['preferences']:
                if pref_seminar_id not in seminar_ids:
                    self.logger.error(f"DataGenerator: 論理的検証エラー: 学生 '{student['id']}' の希望セミナー '{pref_seminar_id}' が存在しません。")
                    raise ValueError(f"学生 '{student['id']}' の希望セミナー '{pref_seminar_id}' が存在しません。")
        self.logger.info("DataGenerator: データ生成の論理的検証に成功しました。")

