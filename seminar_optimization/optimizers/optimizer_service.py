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
# seminar_optimization パッケージ内のモジュールは絶対パスでインポートします。
from seminar_optimization.seminar_optimization.utils import (
    BaseOptimizer,
    OptimizationResult
)
# ロギングは logger_config.py で一元的に設定されるため、ここではロガーの取得のみ
from seminar_optimization.seminar_optimization.logger_config import logger # <-- 修正: 相対インポート
# スキーマ定義は schemas.py からインポート
from seminar_optimization.seminar_optimization.schemas import SEMINARS_SCHEMA, STUDENTS_SCHEMA, CONFIG_SCHEMA

# 各最適化アルゴリズムをインポート（同じ optimizers パッケージ内なので相対インポートも可能ですが、
# 明示的に絶対インポートを維持します。これは好みによります。）
from optimizers.greedy_ls_optimizer import GreedyLSOptimizer
from optimizers.genetic_algorithm_optimizer import GeneticAlgorithmOptimizer
from optimizers.ilp_optimizer import ILPOptimizer
from optimizers.cp_sat_optimizer import CPSATOptimizer
from optimizers.multilevel_optimizer import MultilevelOptimizer
from optimizers.adaptive_optimizer import AdaptiveOptimizer

# オプティマイザのマッピングを定義
OPTIMIZER_MAP = {
    "Greedy_LS": GreedyLSOptimizer,
    "GA_LS": GeneticAlgorithmOptimizer,
    "ILP": ILPOptimizer,
    "CP": CPSATOptimizer,
    "Multilevel": MultilevelOptimizer,
    "Adaptive": AdaptiveOptimizer
}

class OptimizerService:
    """
    セミナー割り当て最適化のビジネスロジックをカプセル化するサービス。
    データの読み込み、最適化の実行、結果の保存を担当する。
    """
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        logger.debug("OptimizerService: 初期化を開始します。")
        # 設定のスキーマ検証
        try:
            jsonschema.validate(instance=self.config, schema=CONFIG_SCHEMA)
            logger.info("OptimizerService: 設定のスキーマ検証に成功しました。")
        except jsonschema.exceptions.ValidationError as e:
            logger.critical(f"OptimizerService: 設定のスキーマ検証エラー: {e.message} (パス: {'.'.join(map(str, e.path))})", exc_info=True)
            raise ValueError(f"設定ファイルの形式が不正です: {e.message} (パス: {'.'.join(map(str, e.path))})")

        # プロジェクトのルートディレクトリを基準に出力ディレクトリを解決
        # optimizer_service.py は seminar_optimization/optimizers/optimizer_service.py にあると仮定
        # プロジェクトルートは一つ上のディレクトリのさらに一つ上のディレクトリ
        script_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
        
        # configから取得した相対パスをプロジェクトルートからの絶対パスに変換
        output_dir_relative = self.config.get("output_directory", "results")
        self.output_directory = os.path.join(project_root, output_dir_relative)
        
        os.makedirs(self.output_directory, exist_ok=True) # 出力ディレクトリが存在しない場合は作成
        logger.info(f"OptimizerService: 出力ディレクトリ: {self.output_directory}")

    def run_optimization(self,
                         seminars: List[Dict[str, Any]],
                         students: List[Dict[str, Any]],
                         cancel_event: Optional[threading.Event] = None,
                         progress_callback: Optional[Callable[[str], None]] = None) -> OptimizationResult:
        """
        指定されたデータと戦略に基づいて最適化を実行する。
        """
        logger.info(f"OptimizerService: 最適化戦略 '{self.optimization_strategy}' を実行します。")
        
        optimizer_class = OPTIMIZER_MAP.get(self.optimization_strategy)
        if not optimizer_class:
            logger.error(f"OptimizerService: 未知の最適化戦略が指定されました: {self.optimization_strategy}")
            return OptimizationResult(
                status="MODEL_INVALID",
                message=f"未知の最適化戦略: {self.optimization_strategy}",
                best_score=-float('inf'),
                best_assignment={},
                seminar_capacities={s['id']: s['capacity'] for s in seminars},
                unassigned_students=[s['id'] for s in students],
                optimization_strategy=self.optimization_strategy
            )

        optimizer = optimizer_class(
            seminars=seminars,
            students=students,
            config=self.config,
            progress_callback=progress_callback
        )

        try:
            result = optimizer.optimize(cancel_event)
            logger.info(f"OptimizerService: 最適化が完了しました。ステータス: {result.status}, スコア: {result.best_score:.2f}")
            return result
        except Exception as e:
            logger.exception(f"OptimizerService: 最適化中にエラーが発生しました (戦略: {self.optimization_strategy})")
            return OptimizationResult(
                status="FAILED",
                message=f"最適化中にエラーが発生しました: {e}",
                best_score=-float('inf'),
                best_assignment={},
                seminar_capacities={s['id']: s['capacity'] for s in seminars},
                unassigned_students=[s['id'] for s in students],
                optimization_strategy=self.optimization_strategy
            )

def run_optimization_service(
    seminars: List[Dict[str, Any]],
    students: List[Dict[str, Any]],
    config: Dict[str, Any],
    cancel_event: Optional[threading.Event] = None,
    progress_callback: Optional[Callable[[str], None]] = None
) -> OptimizationResult:
    """
    外部から呼び出される最適化サービスのエントリポイント。
    """
    logger.info("optimizer_service: 最適化サービスを開始します。")
    service = OptimizerService(config)
    
    result = service.run_optimization(seminars, students, cancel_event, progress_callback)
    
    # レポート生成
    _generate_reports(config, result.best_assignment, result.optimization_strategy, seminars, students)

    logger.info("optimizer_service: 最適化サービスが終了しました。")
    return result

def _generate_reports(
    config: Dict[str, Any],
    assignment: Dict[str, str],
    optimization_strategy: str,
    seminars: List[Dict[str, Any]],
    students: List[Dict[str, Any]]
):
    """
    最適化結果に基づいてレポートを生成するヘルパー関数。
    """
    logger.info("optimizer_service: レポート生成処理を開始します。")
    try:
        # output_generator.py からレポート保存関数をインポート
        # optimizer_service.py が optimizers/ に移動したため、絶対パスでインポートします。
        from seminar_optimization.output_generator import save_csv_results, save_pdf_report
        
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
        logger.error(f"optimizer_service: レポート生成中に予期せぬエラーが発生しました: {e}", exc_info=True)

