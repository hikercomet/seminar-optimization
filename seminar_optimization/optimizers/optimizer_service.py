import os
import json
import logging
import random
import numpy as np
import csv
import time
import threading
from typing import Dict, List, Any, Optional, Callable, Tuple
import jsonschema # データスキーマ検証用

# 新しく作成したutilsモジュールから共通関数をインポート
from utils import (
    BaseOptimizer,
    OptimizationResult
)

# 各最適化アルゴリズムをインポート
from .greedy_ls_optimizer import GreedyLSOptimizer
from .genetic_algorithm_optimizer import GeneticAlgorithmOptimizer
from .ilp_optimizer import ILPOptimizer
from .cp_sat_optimizer import CPSATOptimizer
from .multilevel_optimizer import MultilevelOptimizer
from .adaptive_optimizer import AdaptiveOptimizer

logger = logging.getLogger(__name__) # モジュールレベルのロガーを使用
logger.setLevel(logging.DEBUG) # DEBUGレベルのメッセージも出力

# --- スキーマ定義 (入力データ検証用) ---
SEMINARS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "capacity": {"type": "integer", "minimum": 1},
            "magnification": {"type": "number", "minimum": 0} # オプションフィールド
        },
        "required": ["id", "capacity"]
    }
}

STUDENTS_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "preferences": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1 # 最低1つの希望は必要
            }
        },
        "required": ["id", "preferences"]
    }
}

class DataLoader:
    """
    セミナーと学生のデータをロード、生成、検証するクラス。
    """
    def __init__(self, config: Dict[str, Any], logger: logging.Logger): # logger 引数を追加
        self.config = config
        self.logger = logger # ロガーをインスタンス変数として保持
        self.logger.debug("DataLoader: 設定とロガーで初期化されました。")

    def _validate_data(self, seminars: List[Dict[str, Any]], students: List[Dict[str, Any]]):
        """
        入力データをスキーマに対して検証する。
        """
        self.logger.debug("DataLoader: 入力データのスキーマ検証を開始します。")
        try:
            jsonschema.validate(instance=seminars, schema=SEMINARS_SCHEMA)
            jsonschema.validate(instance=students, schema=STUDENTS_SCHEMA)
            self.logger.info("DataLoader: セミナーと学生のデータはスキーマ検証に合格しました。")
        except jsonschema.exceptions.ValidationError as e:
            self.logger.error(f"DataLoader: データ検証エラー: {e.message} (パス: {e.path})", exc_info=True)
            raise ValueError(f"入力データがスキーマに準拠していません: {e.message} (パス: {e.path})")
        
        # 追加の論理的検証
        seminar_ids = {s['id'] for s in seminars}
        student_ids = {s['id'] for s in students}

        if not seminar_ids:
            raise ValueError("セミナーデータが空です。")
        if not student_ids:
            raise ValueError("学生データが空です。")
        
        # 学生の希望が実在するセミナーIDであるかチェック
        for student in students:
            for pref_seminar_id in student['preferences']:
                if pref_seminar_id not in seminar_ids:
                    self.logger.error(f"DataLoader: 不正な希望セミナーID: 学生 '{student['id']}' が存在しないセミナー '{pref_seminar_id}' を希望しています。")
                    raise ValueError(f"学生 '{student['id']}' の希望セミナー '{pref_seminar_id}' が存在しません。")
        self.logger.debug("DataLoader: 論理的データ検証も完了しました。")

    def load_from_json(self, seminars_file_path: str, students_file_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        JSONファイルからセミナーと学生のデータをロードする。
        """
        self.logger.info(f"DataLoader: JSONファイルからデータをロード中: セミナー '{seminars_file_path}', 学生 '{students_file_path}'")
        try:
            with open(seminars_file_path, 'r', encoding='utf-8') as f:
                seminars = json.load(f)
            with open(students_file_path, 'r', encoding='utf-8') as f:
                students = json.load(f)
            
            self._validate_data(seminars, students)
            self.logger.info(f"DataLoader: JSONファイルからデータ ({len(seminars)}セミナー, {len(students)}学生) を正常にロードしました。")
            return seminars, students
        except FileNotFoundError as e:
            self.logger.error(f"DataLoader: ファイルが見つかりません: {e.filename}", exc_info=True)
            raise FileNotFoundError(f"指定されたファイルが見つかりません: {e.filename}")
        except json.JSONDecodeError as e:
            self.logger.error(f"DataLoader: JSONデコードエラー: {e.msg} (ファイル: {e.doc})", exc_info=True)
            raise ValueError(f"JSONファイルの解析に失敗しました: {e.msg}")
        except Exception as e:
            self.logger.error(f"DataLoader: JSONロード中に予期せぬエラーが発生しました: {e}", exc_info=True)
            raise

    def load_from_csv(self, seminars_file_path: str, students_file_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        CSVファイルからセミナーと学生のデータをロードする。
        """
        self.logger.info(f"DataLoader: CSVファイルからデータをロード中: セミナー '{seminars_file_path}', 学生 '{students_file_path}'")
        seminars: List[Dict[str, Any]] = []
        students: List[Dict[str, Any]] = []

        try:
            # セミナーCSVのロード
            with open(seminars_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    seminar_id = row.get('id')
                    capacity_str = row.get('capacity')
                    magnification_str = row.get('magnification')

                    if not seminar_id or not capacity_str:
                        raise ValueError(f"セミナーCSVに 'id' または 'capacity' がありません: {row}")
                    
                    try:
                        capacity = int(capacity_str)
                        if capacity <= 0:
                            raise ValueError(f"セミナー '{seminar_id}' の定員は正の整数である必要があります。")
                    except ValueError:
                        raise ValueError(f"セミナー '{seminar_id}' の定員 '{capacity_str}' が不正な数値です。")
                    
                    seminar_data = {'id': seminar_id, 'capacity': capacity}
                    if magnification_str:
                        try:
                            magnification = float(magnification_str)
                            seminar_data['magnification'] = magnification
                        except ValueError:
                            self.logger.warning(f"セミナー '{seminar_id}' の倍率 '{magnification_str}' が不正な数値です。スキップします。")
                    seminars.append(seminar_data)
            self.logger.debug(f"DataLoader: {len(seminars)} 個のセミナーをCSVからロードしました。")

            # 学生CSVのロード
            with open(students_file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    student_id = row.get('id')
                    preferences_str = row.get('preferences')

                    if not student_id or not preferences_str:
                        raise ValueError(f"学生CSVに 'id' または 'preferences' がありません: {row}")
                    
                    preferences = [p.strip() for p in preferences_str.split(',') if p.strip()]
                    if not preferences:
                        self.logger.warning(f"学生 '{student_id}' の希望リストが空です。")

                    students.append({'id': student_id, 'preferences': preferences})
            self.logger.debug(f"DataLoader: {len(students)} 人の学生をCSVからロードしました。")
            
            self._validate_data(seminars, students)
            self.logger.info(f"DataLoader: CSVファイルからデータ ({len(seminars)}セミナー, {len(students)}学生) を正常にロードしました。")
            return seminars, students
        except FileNotFoundError as e:
            self.logger.error(f"ファイルが見つかりません: {e.filename}", exc_info=True)
            raise FileNotFoundError(f"指定されたファイルが見つかりません: {e.filename}")
        except Exception as e:
            self.logger.error(f"DataLoader: CSVロード中に予期せぬエラーが発生しました: {e}", exc_info=True)
            raise

    def generate_data(self,
                      num_seminars: int,
                      min_capacity: int,
                      max_capacity: int,
                      num_students: int,
                      min_preferences: int,
                      max_preferences: int,
                      preference_distribution: str = "random"
                      ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        ランダムなセミナーと学生のデータを生成する。
        """
        self.logger.info(f"DataLoader: ランダムデータを生成中: セミナー数={num_seminars}, 学生数={num_students}")
        seminars: List[Dict[str, Any]] = []
        students: List[Dict[str, Any]] = []

        # セミナーの生成
        for i in range(num_seminars):
            seminar_id = f"Sem{i+1:03d}"
            capacity = random.randint(min_capacity, max_capacity)
            magnification = round(random.uniform(0.8, 1.5), 2) # 倍率もランダムに生成
            seminars.append({"id": seminar_id, "capacity": capacity, "magnification": magnification})
            self.logger.debug(f"DataLoader: 生成されたセミナー: ID={seminar_id}, 定員={capacity}, 倍率={magnification}")
        
        seminar_ids = [s['id'] for s in seminars]
        
        # 学生の生成
        for i in range(num_students):
            student_id = f"S{i+1:04d}"
            num_prefs = random.randint(min_preferences, max_preferences)
            
            preferences: List[str] = []
            if preference_distribution == "random":
                preferences = random.sample(seminar_ids, min(num_prefs, len(seminar_ids)))
                self.logger.debug(f"DataLoader: 学生 {student_id}: ランダム希望 {preferences}")
            elif preference_distribution == "uniform":
                # 各セミナーが均等に選ばれるようにする（厳密には難しいが、ここではランダムサンプリング）
                preferences = random.sample(seminar_ids, min(num_prefs, len(seminar_ids)))
                self.logger.debug(f"DataLoader: 学生 {student_id}: 均等分布希望 {preferences}")
            elif preference_distribution == "biased":
                # 特定のセミナーに希望が集中するようにバイアスをかける
                # 例: 最初の数個のセミナーに高い確率で希望が集中
                biased_seminars = random.choices(seminar_ids[:min(5, num_seminars)], k=num_prefs) # 最初の5つのセミナーに偏らせる
                other_seminars = random.sample(seminar_ids, num_prefs) # 残りはランダム
                preferences = list(set(biased_seminars + other_seminars))[:num_prefs] # 重複を排除し、希望数に合わせる
                random.shuffle(preferences) # 順序をシャッフル
                self.logger.debug(f"DataLoader: 学生 {student_id}: 偏った希望 {preferences}")
            
            students.append({"id": student_id, "preferences": preferences})
        self.logger.debug(f"DataLoader: {len(students)} 人の学生を生成しました。")

        self._validate_data(seminars, students)
        self.logger.info(f"DataLoader: ランダムデータ生成完了。({len(seminars)}セミナー, {len(students)}学生)")
        return seminars, students

def run_optimization_service(
    seminars: List[Dict[str, Any]],
    students: List[Dict[str, Any]],
    config: Dict[str, Any],
    cancel_event: threading.Event,
    progress_callback: Callable[[str], None]
) -> OptimizationResult:
    """
    指定されたデータと設定に基づいて最適化を実行するサービス関数。
    """
    logger.info("optimizer_service: 最適化サービスを開始します。")
    optimization_strategy = config.get("optimization_strategy", "Greedy_LS")
    logger.info(f"optimizer_service: 選択された最適化戦略: {optimization_strategy}")

    optimizer: Optional[BaseOptimizer] = None
    try:
        logger.info("optimizer_service: オプティマイザのインスタンス生成前")
        if optimization_strategy == "Greedy_LS":
            optimizer = GreedyLSOptimizer(seminars, students, config, progress_callback)
        elif optimization_strategy == "GA_LS":
            optimizer = GeneticAlgorithmOptimizer(seminars, students, config, progress_callback)
        elif optimization_strategy == "ILP":
            optimizer = ILPOptimizer(seminars, students, config, progress_callback)
        elif optimization_strategy == "CP":
            optimizer = CPSATOptimizer(seminars, students, config, progress_callback)
        elif optimization_strategy == "Multilevel":
            optimizer = MultilevelOptimizer(seminars, students, config, progress_callback)
        elif optimization_strategy == "Adaptive":
            optimizer = AdaptiveOptimizer(seminars, students, config, progress_callback)
        else:
            raise ValueError(f"不明な最適化戦略: {optimization_strategy}")
        
        logger.info("optimizer_service: オプティマイザのインスタンス生成後")
        logger.debug(f"optimizer_service: オプティマイザ '{optimization_strategy}' のインスタンスを作成しました。")

        # オプティマイザのoptimizeメソッドを呼び出す。cancel_eventをサポートしているかチェック
        logger.info("optimizer_service: optimize() 実行前")
        if hasattr(optimizer, 'optimize') and 'cancel_event' in optimizer.optimize.__code__.co_varnames:
            result = optimizer.optimize(cancel_event=cancel_event)
            logger.info("optimizer_service: optimize()（cancel_event付き）実行後")
            logger.debug(f"optimizer_service: オプティマイザ '{optimization_strategy}' をキャンセルイベント付きで実行しました。")
        else:
            result = optimizer.optimize()
            logger.info("optimizer_service: optimize() 実行後")
            logger.debug(f"optimizer_service: オプティマイザ '{optimization_strategy}' を実行しました。")

        logger.info(f"optimizer_service: 最適化完了。ステータス: {result.status}, スコア: {result.best_score:.2f}")

        # レポート生成
        logger.info("optimizer_service: レポート生成処理呼び出し前")
        _generate_reports(config, result.best_assignment, seminars, students, optimization_strategy)
        logger.info("optimizer_service: レポート生成処理呼び出し後")

        return result

    except ImportError as e:
        logger.error(f"optimizer_service: 最適化アルゴリズムのインポートエラー: {e}", exc_info=True)
        return OptimizationResult(
            status="FAILED",
            message=f"最適化アルゴリズムのロードに失敗しました: {e}",
            best_score=-float('inf'),
            best_assignment={},
            seminar_capacities={s['id']: s['capacity'] for s in seminars} if seminars else {},
            unassigned_students=[s['id'] for s in students] if students else [],
            optimization_strategy=optimization_strategy
        )
    except Exception as e:
        logger.error(f"optimizer_service: 最適化中に予期せぬエラーが発生しました: {e}", exc_info=True)
        return OptimizationResult(
            status="FAILED",
            message=f"最適化中にエラーが発生しました: {e}",
            best_score=-float('inf'),
            best_assignment={},
            seminar_capacities={s['id']: s['capacity'] for s in seminars} if seminars else {},
            unassigned_students=[s['id'] for s in students] if students else [],
            optimization_strategy=optimization_strategy
        )

def _generate_reports(
    config: Dict[str, Any],
    assignment: Dict[str, str],
    seminars: List[Dict[str, Any]], # レポート生成に必要な生データ
    students: List[Dict[str, Any]], # レポート生成に必要な生データ
    optimization_strategy: str
):
    """レポートを生成するヘルパー関数。"""
    logger.debug("optimizer_service: レポート生成を開始します。")
    try:
        # output_generatorを絶対インポートに変更
        from seminar_optimization.output_generator import save_pdf_report, save_csv_results
        
        # output_generatorに渡す前にconfigに必要なデータを追加
        report_config = config.copy()
        report_config['students_data_for_report'] = students
        report_config['seminars_data_for_report'] = seminars

        if config.get("generate_pdf_report", False):
            logger.info("optimizer_service: PDFレポートを生成します。")
            save_pdf_report(
                config=report_config,
                final_assignment=assignment,
                optimization_strategy=optimization_strategy,
                is_intermediate=False
            )
            logger.debug("optimizer_service: PDFレポート生成関数を呼び出しました。")

        if config.get("generate_csv_report", False):
            logger.info("optimizer_service: CSVレポートを生成します。")
            save_csv_results(
                config=report_config,
                final_assignment=assignment,
                optimization_strategy=optimization_strategy,
                is_intermediate=False
            )
            logger.debug("optimizer_service: CSVレポート生成関数を呼び出しました。")
        logger.info("optimizer_service: レポート生成処理が完了しました。")
    except ImportError as e:
        logger.error(f"optimizer_service: レポート生成モジュールのインポートエラー: {e}", exc_info=True)
        logger.error("output_generator.py が seminar_optimization/seminar_optimization/ パッケージ内に正しく配置されているか確認してください。")
    except Exception as e:
        logger.error(f"optimizer_service: レポートの生成中にエラーが発生しました: {e}", exc_info=True)
        raise
