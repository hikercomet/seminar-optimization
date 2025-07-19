import logging
import os
import time
from dataclasses import asdict
from concurrent.futures import ProcessPoolExecutor, as_completed
import pandas as pd
import json
import sys
# 修正: Dict, List, Tuple は Python 3.9+ で不要なため削除 (または小文字に修正)
# from typing import Dict, List, Tuple # この行を削除またはコメントアウト

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 外部モジュールからのインポート
from models import Config, Student
from utils import PreferenceGenerator, TargetSizeOptimizer
from optimizer import GreedyAssigner, LocalSearchOptimizer, _optimize_single_pattern_task # _optimize_single_pattern_taskはmain.pyに移動

from evaluation import validate_assignment, calculate_satisfaction_stats
from output import generate_pdf_report, save_csv_results

# ReportLabのフォント登録（main.pyで実行時に一度だけ行う）
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# スクリプトのディレクトリを取得し、フォントファイルのパスを構築
script_dir = os.path.dirname(os.path.abspath(__file__))
font_path = os.path.join(script_dir, 'ipaexg.ttf')

try:
    pdfmetrics.registerFont(TTFont('IPAexGothic', font_path))
except Exception as e:
    logger.warning(f"IPAexGothic.ttf（{font_path}）の読み込みに失敗しました。日本語が正しく表示されない可能性があります。エラー: {e}")
    logger.error("IPAexフォントをダウンロードし、スクリプトと同じディレクトリに配置してください。")
    logger.error("ダウンロードはこちら: https://moji.or.jp/ipafont/ipaexfont/")


class SeminarOptimizer:
    def __init__(self, config: Config, students_data: list[Student]): # 修正: listを使用
        self.config = config
        self.students_data = students_data
    
    def optimize_parallel(self) -> tuple[dict, float, dict, int]: # 修正: dict, tupleを使用
        """並列最適化を実行します"""
        best_score = 0
        best_pattern = None
        best_assignments = None
        best_pattern_id = 0
        
        score_history = []

        logger.info(f"Starting parallel optimization: {self.config.num_patterns} patterns evaluated with {self.config.max_workers} processes")
        start_time = time.time()
        
        config_for_workers = asdict(self.config)

        with ProcessPoolExecutor(max_workers=self.config.max_workers) as executor:
            future_to_pattern = {
                executor.submit(_optimize_single_pattern_task, config_for_workers, pattern_id, self.students_data): pattern_id 
                for pattern_id in range(self.config.num_patterns)
            }
            
            completed = 0
            for future in as_completed(future_to_pattern):
                pattern_id = future_to_pattern[future]
                completed += 1
                
                try:
                    score, assignments, target_sizes = future.result()
                    
                    if score > best_score:
                        best_score = score
                        best_pattern = target_sizes
                        best_assignments = assignments
                        best_pattern_id = pattern_id
                        elapsed = time.time() - start_time
                        logger.info(f"[New Record] Pattern {pattern_id}: Score {score:.2f} (Elapsed Time: {elapsed:.1f}s)")
                        score_history.append((completed, pattern_id, score, elapsed))
                    
                    if completed % 5000 == 0:
                        elapsed = time.time() - start_time
                        logger.info(f"--- [Intermediate Report] {completed}/{self.config.num_patterns} completed ---")
                        logger.info(f"Current Best Score: {best_score:.2f} (Pattern ID: {best_pattern_id}) | Elapsed Time: {elapsed:.1f}s")
                        
                        if best_pattern and best_assignments:
                            logger.info("  <Details of Current Best Assignment>")
                            for sem_name in self.config.seminars:
                                current_assigned = len(best_assignments[sem_name])
                                current_total_score = sum(s for _, s in best_assignments[sem_name])
                                target_s = best_pattern.get(sem_name, 0)
                                logger.info(f"    Seminar {sem_name.upper()}: Target Size={target_s}, Actual Size={current_assigned}, Total Score={current_total_score:.2f}")
                            logger.info("---------------------------------------")
                            
                            generate_pdf_report(self.config, best_pattern, best_score, best_assignments, best_pattern_id, 
                                                is_intermediate=True, iteration_count=completed)
                            save_csv_results(self.config, best_assignments, best_pattern_id, 
                                             is_intermediate=True, iteration_count=completed)
                            logger.info(f"Intermediate report generated for {completed} patterns.")
                        
                except Exception as e:
                    logger.error(f"Pattern {pattern_id} failed with unhandled exception: {e}")
        
        elapsed_time = time.time() - start_time
        logger.info(f"Optimization completed (Duration: {elapsed_time:.1f}s)")
        
        try:
            csv_path = os.path.join(self.config.output_dir, "score_progress.csv")
            df = pd.DataFrame(score_history, columns=["Completed", "PatternID", "Score", "ElapsedTime"])
            df.to_csv(csv_path, index=False)
            logger.info(f"Score progress history saved to: {csv_path}")
        except Exception as e:
            logger.error(f"Error saving score history CSV: {e}")
        
        return best_pattern, best_score, best_assignments, best_pattern_id

    def run_optimization(self) -> tuple[dict, float, dict]: # 修正: dict, tupleを使用
        """最適化プロセスを実行するメイン関数"""
        try:
            logger.info("=== Starting High-Precision Seminar Assignment Optimization ===")
            best_pattern, best_score, best_assignments, best_pattern_id = self.optimize_parallel()
            if not best_pattern or not best_assignments:
                logger.error("An error occurred during optimization, no valid results obtained.")
                return {}, 0.0, {}
            
            if not validate_assignment(self.config, best_assignments, best_pattern):
                logger.warning("Warning: Issues found during assignment validation. PDF/CSV will be generated, but please check the results carefully.")
            
            generate_pdf_report(self.config, best_pattern, best_score, best_assignments, best_pattern_id)
            save_csv_results(self.config, best_assignments, best_pattern_id) 
            
            logger.info("=== Optimization Process Completed ===")
            return best_pattern, best_score, best_assignments
        except Exception as e:
            logger.error(f"An unexpected error occurred during overall optimization: {e}")
            return {}, 0.0, {}

# _optimize_single_pattern_task も students_data を受け取るように変更
# 修正: Dict, List, Tuple を dict, list, tuple に変更
def _optimize_single_pattern_task(config_dict: dict, pattern_id: int, all_students: list[Student]) -> tuple[float, dict[str, list[tuple[int, float]]], dict[str, int]]:
    """
    並列処理のための単一パターン最適化タスク。
    この関数はプロセス間で安全にpickle化できるようトップレベルに配置されています。
    """
    try:
        current_config = Config(**config_dict) 

        target_optimizer = TargetSizeOptimizer(config_dict)
        greedy_assigner = GreedyAssigner(config_dict) 
        
        local_optimizer = LocalSearchOptimizer(
            config_dict,
            num_iterations=current_config.local_search_iterations,
            initial_temperature=current_config.initial_temperature,
            cooling_rate=current_config.cooling_rate
        )
        
        students = all_students 

        target_sizes = target_optimizer.generate_balanced_sizes(students, pattern_id)
        
        score, assignments = greedy_assigner.assign_students_greedily(students, target_sizes)
        
        improved_score, improved_assignments = local_optimizer.improve_assignment(
            students, assignments, target_sizes
        )
        
        return improved_score, improved_assignments, target_sizes
            
    except Exception as e:
        logger.error(f"Pattern {pattern_id} optimization failed: {e}")
        return 0.0, {sem: [] for sem in Config(**config_dict).seminars}, {}


if __name__ == "__main__":
    current_dir = os.path.dirname(__file__)
    data_dir = os.path.join(current_dir, 'data')
    os.makedirs(data_dir, exist_ok=True) # dataディレクトリが存在しない場合は作成

    # ユーザーにデータ入力方法を選択させる
    print("セミナー割当最適化ツールのデータ入力方法を選択してください:")
    print("1. 自分で用意したデータを使用 (seminar_config.json と students_preferences.csv)")
    print("2. 自動生成されたデータを使用")
    
    choice = input("選択肢の番号を入力してください (1または2): ")

    initial_config = None
    all_students = []

    # デフォルトのセミナーと倍率設定
    default_seminars = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q']
    default_magnification = {'a': 1.5, 'd': 1.8, 'q': 1.2, 'm': 0.7, 'o': 0.5}
    default_preference_weights = {"1st": 5.0, "2nd": 2.0, "3rd": 1.0}

    if choice == '1':
        # 1. セミナー設定をJSONファイルから読み込む
        config_file_path = os.path.join(data_dir, 'seminar_config.json')
        try:
            with open(config_file_path, 'r', encoding='utf-8') as f:
                seminar_settings = json.load(f)
            
            # Configオブジェクトを外部設定で初期化
            initial_config = Config(
                seminars=seminar_settings.get('seminars', default_seminars),
                magnification=seminar_settings.get('magnification', default_magnification),
                min_size=seminar_settings.get('min_size', 5),
                max_size=seminar_settings.get('max_size', 10),
                num_students=seminar_settings.get('num_students'),
                q_boost_probability=seminar_settings.get('q_boost_probability', 0.2),
                num_patterns=seminar_settings.get('num_patterns', 200000),
                max_workers=seminar_settings.get('max_workers', 8),
                local_search_iterations=seminar_settings.get('local_search_iterations', 500),
                initial_temperature=seminar_settings.get('initial_temperature', 1.0),
                cooling_rate=seminar_settings.get('cooling_rate', 0.995),
                preference_weights=seminar_settings.get('preference_weights', default_preference_weights)
            )
            logger.info(f"セミナー設定を {config_file_path} から読み込みました。")

        except FileNotFoundError:
            logger.error(f"エラー: セミナー設定ファイルが見つかりません: {config_file_path}")
            logger.error("自分で用意したデータを使用する場合、seminar_config.json が必要です。")
            sys.exit(1)
        except json.JSONDecodeError:
            logger.error(f"エラー: セミナー設定ファイル {config_file_path} のJSON形式が不正です。")
            sys.exit(1)
        
        # 2. 学生の希望データをCSVファイルから読み込む
        students_file_path = os.path.join(data_dir, 'students_preferences.csv')
        preference_generator = PreferenceGenerator(asdict(initial_config)) 
        try:
            all_students = preference_generator.load_preferences_from_csv(students_file_path)
            initial_config.num_students = len(all_students)
            logger.info(f"学生希望データを {students_file_path} から読み込みました。学生数: {initial_config.num_students} 人。")
        except FileNotFoundError:
            logger.error(f"エラー: 学生希望ファイルが見つかりません: {students_file_path}")
            logger.error("自分で用意したデータを使用する場合、students_preferences.csv が必要です。")
            sys.exit(1)

    elif choice == '2':
        logger.info("自動生成されたデータを使用します。")
        # 自動生成の場合のデフォルト設定
        initial_config = Config(
            seminars=default_seminars,
            magnification=default_magnification,
            min_size=5,
            max_size=10,
            num_students=112,
            num_patterns=200000,
            max_workers=8,
            local_search_iterations=500,
            initial_temperature=1.0,
            cooling_rate=0.995,
            preference_weights=default_preference_weights
        )
        
        # 学生データを自動生成
        preference_generator = PreferenceGenerator(asdict(initial_config))
        all_students = preference_generator.generate_realistic_preferences(42)
        initial_config.num_students = len(all_students)
        logger.info(f"自動生成された学生データを使用します。学生数: {initial_config.num_students} 人。")

    else:
        print("無効な選択です。プログラムを終了します。")
        sys.exit(1)

    # ユーザーが設定値を入力できるようにする
    print("\n--- 最適化設定の入力 ---")
    print("現在の設定値が表示されます。変更しない場合はEnterキーを押してください。")

    # num_patterns
    while True:
        try:
            user_input = input(f"試行回数 (num_patterns) [現在の値: {initial_config.num_patterns}]: ")
            if user_input == "":
                break
            new_val = int(user_input)
            if new_val <= 0:
                print("試行回数は正の整数である必要があります。")
                continue
            initial_config.num_patterns = new_val
            break
        except ValueError:
            print("無効な入力です。整数を入力してください。")

    # min_size
    while True:
        try:
            user_input = input(f"セミナー最小定員 (min_size) [現在の値: {initial_config.min_size}]: ")
            if user_input == "":
                break
            new_val = int(user_input)
            if new_val <= 0:
                print("最小定員は正の整数である必要があります。")
                continue
            initial_config.min_size = new_val
            break
        except ValueError:
            print("無効な入力です。整数を入力してください。")

    # max_size
    while True:
        try:
            user_input = input(f"セミナー最大定員 (max_size) [現在の値: {initial_config.max_size}]: ")
            if user_input == "":
                break
            new_val = int(user_input)
            if new_val <= 0:
                print("最大定員は正の整数である必要があります。")
                continue
            if new_val < initial_config.min_size:
                print(f"最大定員は最小定員 ({initial_config.min_size}) 以上である必要があります。")
                continue
            initial_config.max_size = new_val
            break
        except ValueError:
            print("無効な入力です。整数を入力してください。")

    # max_workers
    while True:
        try:
            user_input = input(f"並列処理数 (max_workers) [現在の値: {initial_config.max_workers}]: ")
            if user_input == "":
                break
            new_val = int(user_input)
            if new_val <= 0:
                print("並列処理数は正の整数である必要があります。")
                continue
            initial_config.max_workers = new_val
            break
        except ValueError:
            print("無効な入力です。整数を入力してください。")

    # q_boost_probability (自動生成の場合のみ関連性が高いが、一応設定可能にする)
    if choice == '2': # 自動生成の場合のみプロンプトを出す
        while True:
            try:
                user_input = input(f"'q'セミナーの希望ブースト確率 (q_boost_probability) [現在の値: {initial_config.q_boost_probability}]: ")
                if user_input == "":
                    break
                new_val = float(user_input)
                if not (0.0 <= new_val <= 1.0):
                    print("確率は0.0から1.0の間の数値である必要があります。")
                    continue
                initial_config.q_boost_probability = new_val
                break
            except ValueError:
                print("無効な入力です。数値を入力してください。")
    
    # local_search_iterations
    while True:
        try:
            user_input = input(f"局所探索の反復回数 (local_search_iterations) [現在の値: {initial_config.local_search_iterations}]: ")
            if user_input == "":
                break
            new_val = int(user_input)
            if new_val <= 0:
                print("反復回数は正の整数である必要があります。")
                continue
            initial_config.local_search_iterations = new_val
            break
        except ValueError:
            print("無効な入力です。整数を入力してください。")

    # initial_temperature
    while True:
        try:
            user_input = input(f"焼きなまし法の初期温度 (initial_temperature) [現在の値: {initial_config.initial_temperature}]: ")
            if user_input == "":
                break
            new_val = float(user_input)
            if new_val <= 0:
                print("初期温度は正の数値である必要があります。")
                continue
            initial_config.initial_temperature = new_val
            break
        except ValueError:
            print("無効な入力です。数値を入力してください。")

    # cooling_rate
    while True:
        try:
            user_input = input(f"焼きなまし法の冷却率 (cooling_rate) [現在の値: {initial_config.cooling_rate}]: ")
            if user_input == "":
                break
            new_val = float(user_input)
            if not (0.0 < new_val < 1.0):
                print("冷却率は0.0より大きく1.0未満の数値である必要があります。")
                continue
            initial_config.cooling_rate = new_val
            break
        except ValueError:
            print("無効な入力です。数値を入力してください。")
            
    # preference_weights (1st, 2nd, 3rd)
    print("\n--- 希望順位のスコア重み (preference_weights) の設定 ---")
    print(f"現在の値: 1位={initial_config.preference_weights['1st']:.1f}, 2位={initial_config.preference_weights['2nd']:.1f}, 3位={initial_config.preference_weights['3rd']:.1f}")

    while True:
        try:
            user_input = input(f"1位希望のスコア重み (1st) [現在の値: {initial_config.preference_weights['1st']:.1f}]: ")
            if user_input == "":
                break
            new_val = float(user_input)
            if new_val < 0:
                print("スコア重みは0以上の数値である必要があります。")
                continue
            initial_config.preference_weights['1st'] = new_val
            break
        except ValueError:
            print("無効な入力です。数値を入力してください。")

    while True:
        try:
            user_input = input(f"2位希望のスコア重み (2nd) [現在の値: {initial_config.preference_weights['2nd']:.1f}]: ")
            if user_input == "":
                break
            new_val = float(user_input)
            if new_val < 0:
                print("スコア重みは0以上の数値である必要があります。")
                continue
            initial_config.preference_weights['2nd'] = new_val
            break
        except ValueError:
            print("無効な入力です。数値を入力してください。")

    while True:
        try:
            user_input = input(f"3位希望のスコア重み (3rd) [現在の値: {initial_config.preference_weights['3rd']:.1f}]: ")
            if user_input == "":
                break
            new_val = float(user_input)
            if new_val < 0:
                print("スコア重みは0以上の数値である必要があります。")
                continue
            initial_config.preference_weights['3rd'] = new_val
            break
        except ValueError:
            print("無効な入力です。数値を入力してください。")
            
    # early_stop_threshold (現在未使用だが、設定可能に)
    while True:
        try:
            user_input = input(f"早期終了閾値 (early_stop_threshold) [現在の値: {initial_config.early_stop_threshold}]: ")
            if user_input == "":
                break
            new_val = float(user_input)
            if new_val < 0:
                print("閾値は0以上の数値である必要があります。")
                continue
            initial_config.early_stop_threshold = new_val
            break
        except ValueError:
            print("無効な入力です。数値を入力してください。")

    # no_improvement_limit (現在未使用だが、設定可能に)
    while True:
        try:
            user_input = input(f"改善なし制限 (no_improvement_limit) [現在の値: {initial_config.no_improvement_limit}]: ")
            if user_input == "":
                break
            new_val = int(user_input)
            if new_val <= 0:
                print("制限は正の整数である必要があります。")
                continue
            initial_config.no_improvement_limit = new_val
            break
        except ValueError:
            print("無効な入力です。整数を入力してください。")


    # 出力ディレクトリの作成 (Config初期化後に実行)
    os.makedirs(initial_config.output_dir, exist_ok=True)

    # SeminarOptimizerに読み込んだ学生データを渡す
    optimizer = SeminarOptimizer(initial_config, all_students)

    best_pattern_sizes, overall_best_score, final_assignments = optimizer.run_optimization()

    logger.info("\n--- Final Results ---")
    logger.info(f"Overall Best Score: {overall_best_score:.2f}")
    
    if best_pattern_sizes:
        logger.info("Optimal Target Sizes per Seminar:")
        for sem, size in best_pattern_sizes.items():
            logger.info(f"  Seminar {sem.upper()}: {size}")
    
    if final_assignments:
        logger.info("\nFinal Best Assignment Details:")
        pass 
    
    if final_assignments and best_pattern_sizes:
        logger.info("\n--- Validating Final Assignment ---")
        is_valid = validate_assignment(initial_config, final_assignments, best_pattern_sizes)
        logger.info(f"Assignment Valid: {is_valid}")
    else:
        logger.error("No final assignments or target sizes to validate.")

