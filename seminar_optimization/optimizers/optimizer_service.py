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

# 新しく作成したutilsモジュールから共通関数をインポート (絶対インポートに変更)
from utils import (
    BaseOptimizer,
    OptimizationResult
)

# 各最適化アルゴリズムをインポート (絶対インポートに変更)
from seminar_optimization.optimizers.greedy_ls_optimizer import GreedyLSOptimizer
from seminar_optimization.optimizers.genetic_algorithm_optimizer import GeneticAlgorithmOptimizer # クラス名を適切に調整
from seminar_optimization.optimizers.ilp_optimizer import ILPOptimizer
from seminar_optimization.optimizers.cp_sat_optimizer import CPSATOptimizer # クラス名を適切に調整
from seminar_optimization.optimizers.multilevel_optimizer import MultilevelOptimizer
from seminar_optimization.optimizers.adaptive_optimizer import AdaptiveOptimizer

logger = logging.getLogger(__name__) # モジュールレベルのロガーを使用

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
        "required": ["id", "capacity"],
        "additionalProperties": False
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
                "minItems": 1 # 最低1つの希望は必須とする
            }
        },
        "required": ["id", "preferences"],
        "additionalProperties": False
    }
}

class DataLoader:
    """
    セミナーと学生のデータを様々な形式から読み込み、生成するためのクラス。
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def _validate_data(self, seminars_data: List[Dict[str, Any]], students_data: List[Dict[str, Any]]):
        """データのスキーマ検証を実行する。"""
        try:
            jsonschema.validate(instance=seminars_data, schema=SEMINARS_SCHEMA)
            jsonschema.validate(instance=students_data, schema=STUDENTS_SCHEMA)
            # データ内容の追加検証（例：学生の希望セミナーIDが実際に存在するセミナーIDであるか）
            existing_seminar_ids = {s['id'] for s in seminars_data}
            for student in students_data:
                for preferred_seminar_id in student['preferences']:
                    if preferred_seminar_id not in existing_seminar_ids:
                        raise ValueError(f"学生 {student['id']} の希望セミナー '{preferred_seminar_id}' が存在しません。")

            logger.info("データスキーマと内容の検証に成功しました。")
        except jsonschema.exceptions.ValidationError as e:
            logger.error(f"データスキーマの検証に失敗しました: {e.message} (パス: {e.path})")
            raise ValueError(f"入力データが無効です: {e.message} (パス: {e.path})")
        except ValueError as e:
            logger.error(f"データ内容の検証に失敗しました: {e}")
            raise
        except Exception as e:
            logger.error(f"データ検証中に予期せぬエラーが発生しました: {e}")
            raise

    def load_from_json(self, seminars_file_path: str, students_file_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """JSONファイルからデータを読み込む。"""
        try:
            with open(seminars_file_path, 'r', encoding='utf-8') as f:
                seminars_data = json.load(f)
            with open(students_file_path, 'r', encoding='utf-8') as f:
                students_data = json.load(f)
            self._validate_data(seminars_data, students_data) # 読み込み後に検証
            logger.info(f"JSONファイルからデータ '{seminars_file_path}', '{students_file_path}' を読み込みました。")
            return seminars_data, students_data
        except FileNotFoundError as e:
            logger.error(f"ファイルが見つかりません: {e.filename}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"JSONファイルのデコードエラー: {e}")
            raise
        except Exception as e:
            logger.error(f"JSONファイルの読み込み中にエラーが発生しました: {e}")
            raise

    def load_from_csv(self, seminars_csv_path: str, students_csv_path: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """CSVファイルからデータを読み込む。"""
        seminars_data = []
        students_data = []
        try:
            # セミナーCSVの読み込み (seminar_id,capacity)
            with open(seminars_csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                if 'seminar_id' not in reader.fieldnames or 'capacity' not in reader.fieldnames:
                    raise ValueError("セミナーCSVのヘッダーが不正です。'seminar_id'と'capacity'が必要です。")
                for row in reader:
                    seminars_data.append({
                        'id': row['seminar_id'],
                        'capacity': int(row['capacity'])
                    })

            # 学生CSVの読み込み (student_id,preferred_seminar_1,preferred_seminar_2,...)
            with open(students_csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader) # ヘッダー行を読み込む
                
                if 'student_id' not in header:
                    raise ValueError("学生CSVのヘッダーが不正です。'student_id'が必要です。")
                
                student_id_idx = header.index('student_id')
                
                for row_idx, row in enumerate(reader):
                    if len(row) <= student_id_idx: # 行の長さが足りない場合
                        logger.warning(f"学生CSVの不正な行をスキップしました (行 {row_idx+2}: カラム数が不足)。")
                        continue
                    
                    student_id = row[student_id_idx]
                    preferences = []
                    # 'preferred_seminar_X' の形式の列を全て希望として追加
                    for col_idx, col_name in enumerate(header):
                        if col_name.startswith('preferred_seminar_') and col_idx < len(row):
                            if row[col_idx]: # 空でない場合のみ追加
                                preferences.append(row[col_idx])
                    
                    if not preferences:
                        logger.warning(f"学生 {student_id} (行 {row_idx+2}) に希望セミナーが設定されていません。")
                        # 希望がない学生もデータ構造としては追加しておく
                    
                    students_data.append({
                        'id': student_id,
                        'preferences': preferences
                    })
            
            self._validate_data(seminars_data, students_data) # 読み込み後に検証
            logger.info(f"CSVファイルからデータ '{seminars_csv_path}', '{students_csv_path}' を読み込みました。")
            return seminars_data, students_data
        except FileNotFoundError as e:
            logger.error(f"ファイルが見つかりません: {e.filename}")
            raise
        except ValueError as e:
            logger.error(f"CSVファイルの形式エラーまたはデータ検証エラー: {e}")
            raise
        except Exception as e:
            logger.error(f"CSVファイルの読み込み中にエラーが発生しました: {e}")
            raise

    def generate_data(self,
                      num_seminars: int,
                      min_capacity: int,
                      max_capacity: int,
                      num_students: int,
                      min_preferences: int,
                      max_preferences: int,
                      preference_distribution: str = "random", # "random", "uniform", "biased"
                      preference_bias_factor: float = 0.3 # 偏りの度合い (0.0-1.0), biasedの場合にのみ適用
                      ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        指定された条件に基づいてダミーのセミナーと学生のデータを生成する。
        """
        seminars_data = []
        for i in range(num_seminars):
            seminar_id = f"S{i+1:03d}"
            capacity = random.randint(min_capacity, max_capacity)
            seminars_data.append({'id': seminar_id, 'capacity': capacity})

        student_data = []
        seminar_ids = [s['id'] for s in seminars_data]

        if not seminar_ids: # セミナーが一つも生成されない場合のエラー回避
            raise ValueError("セミナーが生成されませんでした。セミナー数を1以上に設定してください。")

        for i in range(num_students):
            student_id = f"ST{i+1:03d}"
            num_prefs = random.randint(min_preferences, max_preferences)
            
            preferences = []
            if preference_distribution == "random":
                # 全てのセミナーからランダムに希望を選択
                preferences = random.sample(seminar_ids, min(num_prefs, len(seminar_ids)))
            elif preference_distribution == "uniform":
                # 各セミナーにできるだけ均等に希望が分散するように選択
                # (ここでは単純にランダムだが、より高度な均等配分ロジックも可能)
                preferences = random.sample(seminar_ids, min(num_prefs, len(seminar_ids)))
            elif preference_distribution == "biased":
                # 人気セミナー（IDが若いセミナーなど）に偏りを持たせる
                # バイアスプールの作成: 偏りをつけたいセミナーを複数回リストに入れる
                num_biased_seminars = max(1, int(len(seminar_ids) * preference_bias_factor))
                biased_pool = []
                for j, sid in enumerate(seminar_ids):
                    if j < num_biased_seminars:
                        biased_pool.extend([sid] * int(5 / (j + 1))) # 上位ほど強くバイアス
                    else:
                        biased_pool.append(sid)
                
                # バイアスプールから希望を選択し、重複を排除して指定数にする
                selected_prefs_raw = random.sample(biased_pool, min(num_prefs * 2, len(biased_pool))) # 多めに選択して重複削除
                preferences = []
                for p in selected_prefs_raw:
                    if p not in preferences and len(preferences) < num_prefs:
                        preferences.append(p)
                # 指定数に満たない場合は、残りをランダムに補完
                if len(preferences) < num_prefs:
                    remaining_seminars = [s for s in seminar_ids if s not in preferences]
                    preferences.extend(random.sample(remaining_seminars, min(num_prefs - len(preferences), len(remaining_seminars))))
            
            student_data.append({'id': student_id, 'preferences': preferences})
        
        self._validate_data(seminars_data, student_data) # 生成後も検証
        logger.info(f"ダミーデータを生成しました: セミナー数={num_seminars}, 学生数={num_students}")
        return seminars_data, student_data


def run_optimization_service(
    seminars: List[Dict[str, Any]], # GUIから直接データを受け取る
    students: List[Dict[str, Any]], # GUIから直接データを受け取る
    config: Dict[str, Any], # 設定辞書を直接受け取る
    cancel_event: threading.Event,
    progress_callback: Optional[Callable[[str], None]] = None # 進捗コールバックを追加
) -> OptimizationResult:
    """
    最適化サービスを実行するメイン関数。
    データと設定を直接受け取る。
    """
    logger.info("最適化サービスを開始します。")
    start_time = time.time()

    optimization_strategy = config.get("optimization_strategy", "Greedy_LS")
    
    if progress_callback:
        progress_callback(f"最適化戦略: {optimization_strategy} を選択しました。")

    # データは既にGUIで準備・検証されているため、ここでは基本的な整合性チェックのみ
    if not seminars or not students:
        msg = "最適化に必要なセミナーまたは学生データが提供されていません。"
        logger.error(msg)
        if progress_callback: progress_callback(msg)
        return OptimizationResult(
            status="ERROR", message=msg, best_score=-1, best_assignment={}, seminar_capacities={}, unassigned_students=[], optimization_strategy=optimization_strategy
        )
    
    # ここで最終的なデータ検証を行う
    try:
        data_loader_temp = DataLoader(config) # configは検証には不要だが、DataLoaderのinitに必要
        data_loader_temp._validate_data(seminars, students)
    except Exception as e:
        msg = f"最適化サービス開始前のデータ検証に失敗しました: {e}"
        logger.error(msg)
        if progress_callback: progress_callback(msg)
        return OptimizationResult(
            status="ERROR", message=msg, best_score=-1, best_assignment={}, seminar_capacities={}, unassigned_students=[], optimization_strategy=optimization_strategy
        )


    optimizer: BaseOptimizer = None
    try:
        # ここで各オプティマイザのインスタンスを生成し、progress_callbackを渡す
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
        
        if progress_callback:
            progress_callback(f"'{optimization_strategy}' オプティマイザを初期化しました。最適化を開始します...")

        # オプティマイザの実行
        result = optimizer.optimize()

        if cancel_event.is_set():
            result.status = "CANCELLED"
            result.message = "最適化がユーザーによってキャンセルされました。"
            logger.info("最適化がキャンセルされました。")
            if progress_callback:
                progress_callback("最適化がキャンセルされました。")
            return result
        
        final_assignment = result.best_assignment
        final_score = result.best_score
        unassigned_students = result.unassigned_students
        status = result.status
        message = result.message

    except Exception as e:
        logger.exception(f"最適化中にエラーが発生しました: {e}")
        if progress_callback:
            progress_callback(f"最適化中にエラーが発生しました: {e}")
        return OptimizationResult(
            status="ERROR",
            message=f"最適化中にエラーが発生しました: {e}",
            best_score=-1,
            best_assignment={},
            seminar_capacities={s['id']: s['capacity'] for s in seminars},
            unassigned_students=[],
            optimization_strategy=optimization_strategy
        )

    end_time = time.time()
    duration = end_time - start_time
    logger.info(f"最適化完了。実行時間: {duration:.2f}秒。ステータス: {status}")
    if progress_callback:
        progress_callback(f"最適化完了。実行時間: {duration:.2f}秒。ステータス: {status}")

    # レポート生成 (既存のロジックを保持しつつ、必要なデータを渡す)
    _generate_reports(config, final_assignment, seminars, students, optimization_strategy)

    return OptimizationResult(
        status=status,
        message=message,
        best_score=final_score,
        best_assignment=final_assignment,
        seminar_capacities={s['id']: s['capacity'] for s in seminars},
        unassigned_students=unassigned_students,
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
    try:
        # output_generatorを絶対インポートに変更
        from seminar_optimization.output_generator import save_pdf_report, save_csv_results
        
        # output_generatorに渡す前にconfigに必要なデータを追加
        report_config = config.copy()
        report_config['students_data_for_report'] = students
        report_config['seminars_data_for_report'] = seminars

        if config.get("generate_pdf_report", False):
            save_pdf_report(
                config=report_config,
                final_assignment=assignment,
                optimization_strategy=optimization_strategy,
                is_intermediate=False
            )

        if config.get("generate_csv_report", False):
            save_csv_results(
                config=report_config,
                final_assignment=assignment,
                optimization_strategy=optimization_strategy,
                is_intermediate=False
            )
    except ImportError as e:
        logger.error(f"レポート生成モジュールのインポートに失敗しました: {e}")
    except Exception as e:
        logger.exception(f"レポート生成中にエラーが発生しました: {e}")

