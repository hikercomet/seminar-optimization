import json
import csv
import random
from typing import Dict, List, Any, Tuple
import os
import math
import logging
from datetime import datetime # datetimeを追加
from dataclasses import asdict # asdictを追加

from models import Config, Student # ConfigとStudentモデルをインポート

logger = logging.getLogger(__name__)

class PreferenceGenerator:
    """学生の希望とセミナー定員を生成・読み込みするクラス"""

    def __init__(self, config_dict: dict):
        self.config = Config(**config_dict)
        self.seminar_names = self.config.seminars
        self.num_students = self.config.num_students
        self.q_boost_probability = self.config.q_boost_probability
        self.num_preferences_to_consider = 3 # 固定値としておく

    def generate_realistic_preferences(self, seed: int = None) -> list[Student]:
        """
        より現実的な学生の希望リストを生成します。
        一部のセミナーに人気が集中する傾向をシミュレートします。
        """
        if seed is not None:
            random.seed(seed)

        students: list[Student] = []
        
        # 人気セミナーのリスト (例: 'a', 'b', 'c' など)
        # 設定された倍率に基づいて人気セミナーを決定
        popular_seminars = []
        if self.config.magnification:
            # 倍率が高いセミナーほど人気とする
            sorted_magnification = sorted(self.config.magnification.items(), key=lambda item: item[1], reverse=True)
            for sem, mag in sorted_magnification:
                # 倍率に応じてリストに追加する回数を変える
                popular_seminars.extend([sem] * int(mag * 5)) 
        
        # もし人気セミナーリストが空なら、全てのセミナーを均等に人気とする
        if not popular_seminars:
            popular_seminars = list(self.seminar_names)
        
        # 'q'セミナーが存在し、ブースト確率が設定されている場合
        q_seminar_exists = 'q' in [s.lower() for s in self.seminar_names]

        for i in range(self.num_students):
            student_id = i + 1
            preferences: list[str] = []
            
            # 第一希望の生成
            first_preference = None
            if q_seminar_exists and random.random() < self.q_boost_probability:
                # 'q'セミナーを第一希望にする
                first_preference = next((s for s in self.seminar_names if s.lower() == 'q'), None)
            
            if first_preference is None:
                # 人気セミナーから第一希望をランダムに選択
                first_preference = random.choice(popular_seminars)
            
            preferences.append(first_preference)
            
            # 残りの希望を生成
            remaining_seminars = [s for s in self.seminar_names if s != first_preference]
            random.shuffle(remaining_seminars) # 残りのセミナーをシャッフル
            
            # num_preferences_to_consider まで希望を追加
            for j in range(min(self.num_preferences_to_consider - 1, len(remaining_seminars))):
                preferences.append(remaining_seminars[j])
            
            students.append(Student(student_id, preferences))
        
        return students

    def load_preferences_from_csv(self, filepath: str) -> list[Student]:
        """
        CSVファイルから学生の希望を読み込みます。
        CSV形式: student_id,preference1,preference2,preference3,...
        """
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"学生希望ファイルが見つかりません: {filepath}")
        
        students: list[Student] = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader) # ヘッダー行をスキップ
            
            if 'student_id' not in header:
                raise ValueError("CSVファイルには 'student_id' 列が必要です。")
            
            for row in reader:
                if not row or not row[0].strip(): # 空行やstudent_idが空の行をスキップ
                    continue
                try:
                    student_id = int(row[0])
                    # preferencesは2列目以降
                    preferences = [p.strip() for p in row[1:] if p.strip()]
                    students.append(Student(student_id, preferences))
                except ValueError as e:
                    logger.error(f"CSVファイルの行の解析に失敗しました (行: {row}): {e}")
                    raise ValueError(f"CSVファイルの形式が不正です。学生IDは整数、希望は文字列である必要があります。問題の行: {row}")
        
        if not students:
            raise ValueError("CSVファイルから学生データを読み込めませんでした。ファイルが空であるか、形式が不正です。")
            
        return students

class TargetSizeOptimizer:
    """セミナーの目標定員を最適化するクラス"""

    def __init__(self, config_dict: dict):
        self.config = Config(**config_dict)
        self.seminar_names = self.config.seminars
        self.min_size = self.config.min_size
        self.max_size = self.config.max_size
        self.magnification = self.config.magnification

    def generate_balanced_sizes(self, students: list[Student], seed: int = None) -> dict[str, int]:
        """
        学生の総数と各セミナーの倍率を考慮して、バランスの取れた目標定員を生成します。
        """
        if seed is not None:
            random.seed(seed)

        if not self.seminar_names:
            raise ValueError("セミナー名が設定されていません。")
        if not students:
            raise ValueError("学生データがありません。")

        num_students = len(students)
        
        # 倍率が設定されていないセミナーにはデフォルトで1.0を適用
        seminar_magnifications = {sem: self.magnification.get(sem, 1.0) for sem in self.seminar_names}
        
        # 倍率の合計
        total_magnification = sum(seminar_magnifications.values())
        
        # 各セミナーの初期目標定員を計算
        target_sizes: Dict[str, int] = {}
        remaining_students = num_students
        
        # まず、倍率に基づいて割り振りを計算し、最小定員を保証
        for sem in self.seminar_names:
            if total_magnification > 0:
                # 倍率に基づいて均等に割り振る
                initial_target = round(num_students * (seminar_magnifications[sem] / total_magnification))
            else:
                # 倍率が設定されていない場合は均等割り振り
                initial_target = num_students // len(self.seminar_names)

            # 最小定員を保証
            target_sizes[sem] = max(self.min_size, initial_target)
            remaining_students -= target_sizes[sem]

        # 残りの学生数を定員上限と合計定員を考慮して調整
        # 残りの学生を、まだ最大定員に達していないセミナーにランダムに割り振る
        for _ in range(remaining_students):
            eligible_seminars = [
                sem for sem in self.seminar_names
                if target_sizes[sem] < self.max_size
            ]
            if not eligible_seminars:
                break # 全てのセミナーが最大定員に達した
            
            # ランダムにセミナーを選んで1人追加
            sem_to_add = random.choice(eligible_seminars)
            target_sizes[sem_to_add] += 1

        # 各セミナーの定員が最大定員を超えないように調整
        # 超過分を他のセミナーに再配分
        excess_students = 0
        for sem in self.seminar_names:
            if target_sizes[sem] > self.max_size:
                excess = target_sizes[sem] - self.max_size
                target_sizes[sem] = self.max_size
                excess_students += excess
        
        # 超過した学生を、まだ最大定員に達していないセミナーに再配分
        while excess_students > 0:
            eligible_seminars = [
                sem for sem in self.seminar_names
                if target_sizes[sem] < self.max_size
            ]
            if not eligible_seminars:
                # 再配分できるセミナーがない場合（非常に稀なケース）
                logger.warning("Warning: Could not reallocate all excess students. Some seminars might exceed max_size.")
                break
            
            sem_to_add = random.choice(eligible_seminars)
            target_sizes[sem_to_add] += 1
            excess_students -= 1

        # 最終チェック：合計学生数が一致するか、最小・最大定員が守られているか
        current_total_students = sum(target_sizes.values())
        if current_total_students != num_students:
            # 合計が合わない場合、微調整
            diff = num_students - current_total_students
            
            # 足りない場合は追加
            if diff > 0:
                for _ in range(diff):
                    eligible = [s for s in self.seminar_names if target_sizes[s] < self.max_size]
                    if eligible:
                        target_sizes[random.choice(eligible)] += 1
                    else:
                        # 全てのセミナーが最大定員の場合、どこかに追加せざるを得ない
                        target_sizes[random.choice(self.seminar_names)] += 1
            # 多い場合は減らす
            elif diff < 0:
                for _ in range(abs(diff)):
                    eligible = [s for s in self.seminar_names if target_sizes[s] > self.min_size]
                    if eligible:
                        target_sizes[random.choice(eligible)] -= 1
                    else:
                        # 全てのセミナーが最小定員の場合、どこかから減らすしかない
                        target_sizes[random.choice(self.seminar_names)] -= 1

        # 最終的な定員が最小・最大範囲内に収まっているか確認（デバッグ用）
        for sem, size in target_sizes.items():
            if not (self.min_size <= size <= self.max_size):
                logger.warning(f"Warning: Seminar {sem} target size {size} is outside [{self.min_size}, {self.max_size}] after adjustment.")

        return target_sizes

def calculate_score(assignments: Dict[str, List[Tuple[int, float]]], student_preferences: Dict[int, List[str]], preference_weights: Dict[str, float]) -> float:
    """
    割り当て結果のスコアを計算します。
    学生の希望順位に応じた重み付けを行い、合計スコアを算出します。
    """
    total_score = 0.0
    
    # 希望順位の重みを辞書に変換
    weights = {
        1: preference_weights.get("1st", 5.0),
        2: preference_weights.get("2nd", 2.0),
        3: preference_weights.get("3rd", 1.0)
    }
    
    # 各学生について割り当てられたセミナーが何番目の希望かを確認し、スコアを加算
    for seminar, assigned_students_list in assignments.items():
        for student_id, _ in assigned_students_list: # スコアは割り当て後に再計算するため、ここでは使用しない
            if student_id in student_preferences:
                prefs = student_preferences[student_id]
                try:
                    # seminarは小文字で格納されている可能性があるので、比較前に小文字に変換
                    rank = prefs.index(seminar.lower()) + 1 # 0-indexed to 1-indexed
                    if rank <= 3: # 3位希望まで考慮
                        total_score += weights.get(rank, 0.0)
                except ValueError:
                    # 希望リストにないセミナーに割り当てられた場合、スコアは加算しない
                    pass
    return total_score

def save_results(best_pattern_sizes: Dict[str, int], overall_best_score: float, final_assignments: Dict[str, List[Tuple[int, float]]], config: Config, log_enabled: bool, save_intermediate: bool):
    """
    最適化結果をJSONファイルとして保存します。
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = "optimization_results"
    os.makedirs(output_dir, exist_ok=True)

    results_data = {
        "timestamp": timestamp,
        "config_parameters": asdict(config), # Configオブジェクトを辞書に変換
        "best_pattern_sizes": best_pattern_sizes,
        "overall_best_score": overall_best_score,
        "final_assignments": {sem: [s[0] for s in students] for sem, students in final_assignments.items()} # 学生IDのみ保存
    }

    output_filepath = os.path.join(output_dir, f"optimization_result_{timestamp}.json")
    try:
        with open(output_filepath, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, ensure_ascii=False, indent=4)
        logger.info(f"最適化結果を '{output_filepath}' に保存しました。")
    except Exception as e:
        logger.error(f"結果の保存中にエラーが発生しました: {e}")

    # 詳細ログと中間結果の保存は、必要に応じて実装
    if log_enabled:
        # 例: 詳細な割り当てログをCSVで保存
        log_filepath = os.path.join(output_dir, f"detailed_assignments_{timestamp}.csv")
        try:
            with open(log_filepath, 'w', encoding='utf-8', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["Student ID", "Assigned Seminar", "Preference Rank", "Score Contribution"])
                
                # 学生の希望をIDで検索できるように変換
                student_prefs_map = {}
                # config_parametersからstudent_preferencesを取得する代わりに、
                # SeminarOptimizerから渡されたstudentsオブジェクトから直接取得する
                # ここではconfigオブジェクトにstudent_preferencesは含まれないため、
                # main.pyから渡されるstudentsリストを直接使うか、
                # save_results関数の引数にstudent_preferences_mapを追加する必要がある。
                # 現状の呼び出し元(main.py)ではstudent_preferences_mapが渡されていないため、
                # ここではダミーとして空の辞書を使用するか、このロギング部分を修正する必要がある。
                # 簡単のため、ここではダミーを使用し、実際には呼び出し元で渡すように修正を推奨。
                # または、Configにstudent_preferencesを含める。
                # 今回は、Configにstudent_preferencesを含めない設計なので、
                # main.pyの_get_student_score_contributionのように、
                # SeminarOptimizerのインスタンス変数として持たせるのが適切。
                # save_results関数はあくまで結果を保存するユーティリティなので、
                # 学生の希望はfinal_assignmentsに含まれる情報から推測するか、
                # 別途引数で渡すのが良い。
                # ここでは、簡略化のため、`final_assignments`から学生IDを取得し、
                # 割り当てられたセミナーとの関連のみを記録する。
                # 希望順位やスコア貢献は、この関数では直接計算せず、
                # `final_assignments`に含まれる情報（もしあれば）を利用する。
                # 現在の`final_assignments`は`(student_id, score_contribution)`のタプルなので、それを利用する。

                for seminar, assigned_students_list in final_assignments.items():
                    for student_id, score_contrib in assigned_students_list:
                        # ここでは希望順位は直接わからないため、N/Aとするか、
                        # main.pyから渡す際に含める必要がある。
                        # 現状のfinal_assignmentsの形式では、score_contribは含まれているのでそれを使う。
                        writer.writerow([student_id, seminar, "N/A", score_contrib]) # 希望順位はN/A
            logger.info(f"詳細な割り当てログを '{log_filepath}' に保存しました。")
        except Exception as e:
            logger.error(f"詳細ログの保存中にエラーが発生しました: {e}")

    if save_intermediate:
        # 中間結果の保存ロジック (例: 各世代のベストスコア、GAの個体群など)
        # これは最適化アルゴリズム内部で実装されるべきであり、ここではファイルパスの提供のみ
        logger.info("中間結果の保存が有効になっていますが、具体的な実装は最適化アルゴリズムに依存します。")

def setup_logging(log_enabled: bool = True, level=logging.INFO):
    """
    ロギングを設定します。
    """
    # 既存のハンドラをクリア
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    
    if log_enabled:
        log_dir = "logs"
        os.makedirs(log_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filepath = os.path.join(log_dir, f"optimization_{timestamp}.log")

        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_filepath, encoding='utf-8'),
                logging.StreamHandler() # コンソールにも出力
            ]
        )
    else:
        logging.basicConfig(level=logging.CRITICAL, handlers=[logging.NullHandler()]) # 全てのログ出力を抑制
