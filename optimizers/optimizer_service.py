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
# optimizer_service.py が optimizers/ に移動したため、
# seminar_optimization パッケージ内のモジュールは相対パスでインポートします。
from seminar_optimization.utils import (
    BaseOptimizer,
    OptimizationResult
)
# ロギングは logger_config.py で一元的に設定されるため、ここではロガーの取得のみ
from seminar_optimization.logger_config import logger
# スキーマ定義は schemas.py からインポート
from seminar_optimization.schemas import SEMINARS_SCHEMA, STUDENTS_SCHEMA, CONFIG_SCHEMA

# 各最適化アルゴリズムをインポート（同じ optimizers パッケージ内なので相対インポートを使用）
from optimizers.greedy_ls_optimizer import GreedyLSOptimizer
from optimizers.genetic_algorithm_optimizer import GeneticAlgorithmOptimizer
from optimizers.ilp_optimizer import ILPOptimizer
from optimizers.cp_sat_optimizer import CPSATOptimizer
from optimizers.multilevel_optimizer import MultilevelOptimizer
from optimizers.adaptive_optimizer import AdaptiveOptimizer
from optimizers.tsl_optimizer import TSLOptimizer

# オプティマイザのマッピングを定義
OPTIMIZER_MAP = {
    "Greedy_LS": GreedyLSOptimizer,
    "GA_LS": GeneticAlgorithmOptimizer,
    "ILP": ILPOptimizer,
    "CP": CPSATOptimizer,
    "Multilevel": MultilevelOptimizer,
    "Adaptive": AdaptiveOptimizer,
    "TSL": TSLOptimizer # TSLOptimizerを追加
}

class OptimizerService:
    """
    最適化アルゴリズムの実行を管理するサービス層。
    データ検証、アルゴリズム選択、実行、結果のレポート生成を行う。
    """
    def __init__(self, progress_callback: Optional[Callable[[str], None]] = None, logger_instance: Optional[logging.Logger] = None):
        """
        OptimizerServiceのコンストラクタ。
        Args:
            progress_callback (Optional[Callable[[str], None]]): 進捗メッセージをUIに送るためのコールバック関数。
            logger_instance (Optional[logging.Logger]): 使用するロガーインスタンス。
        """
        self.progress_callback = progress_callback
        self.logger = logger_instance if logger_instance else logging.getLogger(__name__)
        self.logger.debug("OptimizerService: 初期化を開始します。")

    def _validate_data(self, seminars: List[Dict[str, Any]], students: List[Dict[str, Any]], config: Dict[str, Any]):
        """
        入力データ（セミナー、学生、設定）をスキーマに基づいて検証する。
        """
        self.logger.info("OptimizerService: 入力データのスキーマ検証を開始します。")
        try:
            jsonschema.validate(instance=seminars, schema=SEMINARS_SCHEMA)
            self.logger.debug("OptimizerService: セミナーデータのスキーマ検証に成功しました。")
            jsonschema.validate(instance=students, schema=STUDENTS_SCHEMA)
            self.logger.debug("OptimizerService: 学生データのスキーマ検証に成功しました。")
            jsonschema.validate(instance=config, schema=CONFIG_SCHEMA)
            self.logger.debug("OptimizerService: 設定データのスキーマ検証に成功しました。")
        except jsonschema.exceptions.ValidationError as e:
            self.logger.error(f"OptimizerService: データ検証エラー: {e.message} (パス: {'.'.join(map(str, e.path))})", exc_info=True)
            raise ValueError(f"入力データの形式が不正です: {e.message} (パス: {'.'.join(map(str, e.path))})")
        except Exception as e:
            self.logger.error(f"OptimizerService: 予期せぬデータ検証エラー: {e}", exc_info=True)
            raise RuntimeError(f"データ検証中に予期せぬエラーが発生しました: {e}")
        self.logger.info("OptimizerService: 入力データのスキーマ検証が完了しました。")

    def optimize(self, seminars: List[Dict[str, Any]], students: List[Dict[str, Any]], config: Dict[str, Any], cancel_event: Optional[threading.Event] = None) -> OptimizationResult:
        """
        指定された最適化戦略に基づいてセミナー割り当て最適化を実行する。
        Args:
            seminars (List[Dict[str, Any]]): セミナーデータのリスト。
            students (List[Dict[str, Any]]): 学生データのリスト。
            config (Dict[str, Any]): 最適化設定を含む辞書。
            cancel_event (Optional[threading.Event]): キャンセルイベント。設定されている場合、最適化を中断する。
        Returns:
            OptimizationResult: 最適化の結果。
        """
        self.logger.info("OptimizerService: 最適化処理を開始します。")
        
        # データ検証
        try:
            self._validate_data(seminars, students, config)
        except (ValueError, RuntimeError) as e:
            return OptimizationResult(
                status="FAILED",
                message=f"データ検証エラー: {e}",
                best_score=-float('inf'),
                best_assignment={},
                seminar_capacities={}, # エラー時は空
                unassigned_students=[s['id'] for s in students], # 全員未割り当て
                optimization_strategy=config.get("optimization_strategy", "Unknown")
            )

        strategy_name = config.get("optimization_strategy", "Greedy_LS")
        OptimizerClass = OPTIMIZER_MAP.get(strategy_name)

        if not OptimizerClass:
            self.logger.error(f"OptimizerService: 未知の最適化戦略が指定されました: {strategy_name}")
            return OptimizationResult(
                status="FAILED",
                message=f"未知の最適化戦略: {strategy_name}",
                best_score=-float('inf'),
                best_assignment={},
                seminar_capacities={s['id']: s.get('capacity', 0) for s in seminars},
                unassigned_students=[s['id'] for s in students],
                optimization_strategy=strategy_name
            )

        self.logger.info(f"OptimizerService: 選択された最適化戦略: {strategy_name}")
        self.logger.debug(f"OptimizerService: config: {config}")

        optimizer = OptimizerClass(
            seminars=seminars,
            students=students,
            config=config,
            progress_callback=self.progress_callback
        )

        try:
            result = optimizer.optimize(cancel_event=cancel_event)
            self.logger.info(f"OptimizerService: 最適化が完了しました。ステータス: {result.status}, スコア: {result.best_score:.2f}")

            # レポート生成をここで行う
            self._generate_reports(result.best_assignment, result.optimization_strategy, seminars, students, config, result.seminar_capacities)

            return result
        except Exception as e:
            self.logger.exception(f"OptimizerService: 最適化アルゴリズム '{strategy_name}' の実行中に予期せぬエラーが発生しました。")
            return OptimizationResult(
                status="FAILED",
                message=f"最適化アルゴリズムの実行中にエラーが発生しました: {e}",
                best_score=-float('inf'),
                best_assignment={},
                seminar_capacities={s['id']: s.get('capacity', 0) for s in seminars},
                unassigned_students=[s['id'] for s in students],
                optimization_strategy=strategy_name
            )

    def _generate_reports(self, assignment: Dict[str, str], optimization_strategy: str, seminars: List[Dict[str, Any]], students: List[Dict[str, Any]], config: Dict[str, Any], seminar_capacities: Dict[str, int]):
        """
        最適化結果に基づいてレポートを生成する。
        """
        self.logger.info("OptimizerService: レポート生成処理を開始します。")
        try:
            # output_generatorモジュールをインポート
            # output_generator.py が seminar_optimization/output_generator.py にあると仮定
            from seminar_optimization.output_generator import save_csv_results, save_pdf_report
        
            # output_generatorに渡す前にconfigに必要なデータを追加
            report_config = config.copy()
            report_config['students_data_for_report'] = students
            report_config['seminars_data_for_report'] = seminars
            report_config['seminar_capacities_for_report'] = seminar_capacities # 容量情報を追加

            if config.get("generate_pdf_report", False):
                self.logger.info("OptimizerService: PDFレポートを生成します。")
                save_pdf_report(
                    config=report_config,
                    final_assignment=assignment,
                    optimization_strategy=optimization_strategy,
                    is_intermediate=False
                )
                self.logger.debug("OptimizerService: PDFレポート生成関数を呼び出しました。")

            if config.get("generate_csv_report", False):
                self.logger.info("OptimizerService: CSVレポートを生成します。")
                save_csv_results(
                    config=report_config,
                    final_assignment=assignment,
                    optimization_strategy=optimization_strategy,
                    is_intermediate=False
                )
                self.logger.debug("OptimizerService: CSVレポート生成関数を呼び出しました。")
            self.logger.info("OptimizerService: レポート生成処理が完了しました。")
        except ImportError as e:
            self.logger.error(f"OptimizerService: レポート生成モジュールのインポートエラー: {e}", exc_info=True)
            self.logger.error("output_generator.py が seminar_optimization/output_generator.py パッケージ内に正しく配置されているか確認してください。")
        except Exception as e:
            self.logger.error(f"OptimizerService: レポート生成中に予期せぬエラーが発生しました: {e}", exc_info=True)

