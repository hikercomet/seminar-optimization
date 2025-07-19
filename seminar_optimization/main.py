import logging
import os
import sys
import json
import random
import time
from typing import Dict, List, Any, Optional, Callable, Tuple
from concurrent.futures import ProcessPoolExecutor

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# GUIモジュールから設定取得関数をインポートします
from gui_input import launch_gui_and_get_settings

# ReportLabのフォント登録（PDFレポート生成用）
# main.pyで実行時に一度だけ行います
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import cm

# 外部モジュールをインポートします
# これらのファイルは別途提供されます
from models import Seminar, Student, Assignment
from utils import load_seminar_config, load_student_preferences, generate_seminar_capacities, generate_student_preferences, calculate_assignment_score
from optimizer import Optimizer
from evaluation import generate_pdf_report

# スクリプトのディレクトリを取得し、フォントファイルのパスを構築します
script_dir = os.path.dirname(os.path.abspath(__file__))
font_path = os.path.join(script_dir, 'ipaexg.ttf')

try:
    pdfmetrics.registerFont(TTFont('IPAexGothic', font_path))
    logger.info("IPAexGothicフォントを登録しました。")
except Exception as e:
    logger.warning(f"IPAexGothic.ttf（{font_path}）の読み込みに失敗しました。日本語が正しく表示されない可能性があります。エラー: {e}")
    logger.error("IPAexフォントをダウンロードし、スクリプトと同じディレクトリに配置してください。")
    logger.error("ダウンロードはこちら: https://moji.or.jp/ipafont/ipaexfont/")

# ---- メイン実行 ----

if __name__ == "__main__":
    logger.info("セミナー割当最適化ツールを起動します。")
    
    # GUIを起動し、ユーザー設定を取得します
    user_settings = launch_gui_and_get_settings()

    if user_settings is None:
        logger.info("ユーザーによって設定がキャンセルされました。プログラムを終了します。")
        sys.exit(0)

    logger.info("GUIから設定を取得しました。最適化を開始します。")
    
    seminars: List[Seminar] = []
    students: List[Student] = []
    
    # データソースの選択に基づいてデータを準備します
    if user_settings["data_source"] == "manual":
        # 手動データの場合
        config_file = user_settings.get("config_file_path")
        student_file = user_settings.get("student_file_path")

        if not config_file or not os.path.exists(config_file):
            logger.error(f"指定された設定ファイルが見つかりません: {config_file}")
            sys.exit(1)
        if not student_file or not os.path.exists(student_file):
            logger.error(f"指定された学生希望ファイルが見つかりません: {student_file}")
            sys.exit(1)

        try:
            seminar_data = load_seminar_config(config_file)
            student_preferences_data = load_student_preferences(student_file)

            # Seminarオブジェクトの生成
            for name, capacity in seminar_data.items():
                seminars.append(Seminar(name, capacity))
            
            # Studentオブジェクトの生成
            for student_id, prefs in student_preferences_data.items():
                students.append(Student(student_id, prefs))

            logger.info("手動データを正常に読み込みました。")

        except Exception as e:
            logger.error(f"手動データの読み込み中にエラーが発生しました: {e}")
            sys.exit(1)

    else: # "auto" の場合
        # 自動生成データの場合
        seminar_names = user_settings.get("seminars", ['A', 'B', 'C'])
        num_students = user_settings.get("num_students", 30)
        min_size = user_settings.get("min_size", 5)
        max_size = user_settings.get("max_size", 10)
        q_boost_probability = user_settings.get("q_boost_probability", 0.2)
        num_preferences_to_consider = user_settings.get("num_preferences_to_consider", 3)
        magnification_data = user_settings.get("magnification", {})

        try:
            # セミナー定員の自動生成
            capacities = generate_seminar_capacities(seminar_names, num_students, min_size, max_size, magnification_data)
            for name, capacity in capacities.items():
                seminars.append(Seminar(name, capacity))

            # 学生希望の自動生成
            student_preferences_data = generate_student_preferences(
                num_students, seminar_names, q_boost_probability, num_preferences_to_consider
            )
            for student_id, prefs in student_preferences_data.items():
                students.append(Student(student_id, prefs))

            logger.info("自動生成データを正常に作成しました。")

        except Exception as e:
            logger.error(f"自動生成データの作成中にエラーが発生しました: {e}")
            sys.exit(1)

    # 最適化パラメータの取得
    optimization_params = {
        "num_patterns": user_settings.get("num_patterns", 200000),
        "max_workers": user_settings.get("max_workers", 8),
        "local_search_iterations": user_settings.get("local_search_iterations", 500),
        "initial_temperature": user_settings.get("initial_temperature", 1.0),
        "cooling_rate": user_settings.get("cooling_rate", 0.995),
        "preference_weights": {
            "1st": user_settings.get("preference_weights_1st", 5.0),
            "2nd": user_settings.get("preference_weights_2nd", 2.0),
            "3rd": user_settings.get("preference_weights_3rd", 1.0),
        },
        "early_stop_threshold": user_settings.get("early_stop_threshold", 0.001),
        "no_improvement_limit": user_settings.get("no_improvement_limit", 1000),
        "log_enabled": user_settings.get("log_enabled", True),
        "save_intermediate": user_settings.get("save_intermediate", False),
    }

    # 最適化の実行
    optimizer = Optimizer(seminars, students, calculate_assignment_score, optimization_params)
    
    logger.info("最適化を開始します...")
    try:
        best_assignment, best_score = optimizer.run_optimization()
        logger.info(f"最適化が完了しました。最終スコア: {best_score:.4f}")
        
        # 最終割り当て結果のログ出力
        logger.info("\n--- 最終割り当て結果 ---")
        output_message = "セミナー割り当て結果:\n"
        for seminar_name, student_ids in best_assignment.assignments.items():
            output_message += f"  セミナー {seminar_name}: 学生ID {sorted(student_ids)}\n"
        logger.info(output_message)

        # PDFレポートの生成
        report_filename = f"seminar_assignment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        try:
            generate_pdf_report(best_assignment, best_score, seminars, students, report_filename)
            logger.info(f"PDFレポートを生成しました: {report_filename}")
        except Exception as e:
            logger.error(f"PDFレポートの生成中にエラーが発生しました: {e}")

    except Exception as e:
        logger.error(f"最適化の実行中に予期せぬエラーが発生しました: {e}")
        sys.exit(1)

    logger.info("プログラムを終了します。")

