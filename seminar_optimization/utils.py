import random
from collections import defaultdict
from typing import Dict, List, Tuple
import numpy as np
from dataclasses import asdict
import csv 

# 外部モジュールからのインポート
from models import Config, Student 

class PreferenceGenerator:
    def __init__(self, config_dict: dict):
        self.config = Config(**config_dict) 
    
    def generate_realistic_preferences(self, seed: int) -> list[Student]:
        """より現実的な希望分布を生成します"""
        random.seed(seed)
        students = []
        
        if not self.config.seminars:
            raise ValueError("Config.seminars が設定されていません。自動生成できません。")
        if self.config.num_students is None:
            raise ValueError("Config.num_students が設定されていません。自動生成できません。")

        popularity_weights = {sem: 1.0 for sem in self.config.seminars}
        popularity_weights.update({
            'a': 1.5, 'd': 1.8, 'q': 1.2, 'm': 0.7, 'o': 0.5
        })
        
        for student_id in range(1, self.config.num_students + 1):
            preferences = []
            available_seminars = list(self.config.seminars)

            # 1st preference
            if random.random() < self.config.q_boost_probability and 'q' in available_seminars:
                first_choice = 'q'
            else:
                seminars_list = list(available_seminars)
                weights = [popularity_weights.get(sem, 1.0) for sem in seminars_list]
                if sum(weights) == 0: # 全ての重みが0の場合のフォールバック
                    first_choice = random.choice(seminars_list)
                else:
                    first_choice = random.choices(seminars_list, weights=weights, k=1)[0]
            preferences.append(first_choice)
            if first_choice in available_seminars: # 既に削除されている可能性を考慮
                available_seminars.remove(first_choice)

            # Generate up to num_preferences_to_consider (max 3 for current scoring logic)
            # min(self.config.num_preferences_to_consider, len(self.config.seminars))
            # len(self.config.seminars) - 1 は、既に1つ選択された後なので、残りのセミナー数
            for i in range(1, min(self.config.num_preferences_to_consider, len(self.config.seminars))):
                if not available_seminars:
                    break # もう利用可能なセミナーがない場合

                if i == 1: # 2nd preference
                    second_weights = []
                    for sem in available_seminars:
                        base_weight = popularity_weights.get(sem, 1.0)
                        if abs(ord(first_choice) - ord(sem)) <= 2:
                            base_weight *= 1.3
                        second_weights.append(base_weight)
                    
                    if sum(second_weights) == 0:
                        next_choice = random.choice(available_seminars)
                    else:
                        next_choice = random.choices(available_seminars, weights=second_weights, k=1)[0]
                else: # 3rd and subsequent preferences (if num_preferences_to_consider > 2)
                    # Simple random choice for beyond 2nd preference, or more complex logic can be added
                    next_choice = random.choice(available_seminars)
                
                preferences.append(next_choice)
                if next_choice in available_seminars: # 既に削除されている可能性を考慮
                    available_seminars.remove(next_choice)
        
            students.append(Student(student_id, preferences))
        
        return students

    def load_preferences_from_csv(self, file_path: str) -> list[Student]:
        """CSVファイルから学生の希望データを読み込みます。"""
        students = []
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader) 
            
            for row in reader:
                try:
                    student_id = int(row[0])
                    # 希望順位は preference1, preference2, preference3 の列から取得
                    # Config.num_preferences_to_consider に合わせて列数を動的に読み込むことも可能だが、
                    # ここでは現在のCSVフォーマット(3希望まで)に合わせる
                    preferences = [p.strip() for p in row[1:4] if p.strip()] 
                    students.append(Student(student_id, preferences))
                except ValueError as e:
                    print(f"警告: CSVの行をスキップしました (無効なデータ形式): {row} - エラー: {e}")
                except IndexError:
                    print(f"警告: CSVの行をスキップしました (列数が不足しています): {row}")
        return students

class TargetSizeOptimizer:
    def __init__(self, config_dict: dict):
        self.config = Config(**config_dict) 
    
    def generate_balanced_sizes(self, students: list[Student], attempt: int = 0) -> dict[str, int]:
        """学生の希望を考慮したバランスの取れた目標定員を生成します (多様な戦略)"""
        first_choice_count = defaultdict(int)
        for student in students:
            if student.preferences: # 希望が空でないことを確認
                first_choice_count[student.preferences[0]] += 1
        
        if not self.config.seminars:
            raise ValueError("Config.seminars が設定されていません。目標定員を生成できません。")
        if self.config.num_students is None:
            raise ValueError("Config.num_students が設定されていません。目標定員を生成できません。")

        target_sizes = {sem: self.config.min_size for sem in self.config.seminars}
        remaining = self.config.num_students - sum(target_sizes.values())
        
        strategy_index = attempt % 5 
        
        if strategy_index == 0:  # 希望数に基づく重み付け
            sorted_seminars = sorted(self.config.seminars, 
                                     key=lambda x: first_choice_count[x], reverse=True)
        elif strategy_index == 1:  # バランス重視 (シャッフル)
            sorted_seminars = self.config.seminars.copy()
            random.shuffle(sorted_seminars)
        elif strategy_index == 2:  # ランダム要素を追加
            sorted_seminars = self.config.seminars.copy()
            random.shuffle(sorted_seminars)
        elif strategy_index == 3: # 新規: 平均より1位希望が多いセミナーをブースト
            avg_first_choice = sum(first_choice_count.values()) / len(self.config.seminars) if len(self.config.seminars) > 0 else 0
            sorted_seminars = sorted(self.config.seminars,
                                     key=lambda x: first_choice_count[x] if first_choice_count[x] > avg_first_choice else 0,
                                     reverse=True)
        else: # strategy_index == 4 # 新規: より均等な分布を目指す
            sorted_seminars = self.config.seminars.copy()
            sorted_seminars.sort(key=lambda x: target_sizes[x]) 
        
        for _ in range(remaining):
            for sem in sorted_seminars:
                if target_sizes[sem] < self.config.max_size:
                    target_sizes[sem] += 1
                    break
            else:
                can_increase = False
                for s in self.config.seminars:
                    if target_sizes[s] < self.config.max_size:
                        can_increase = True
                        break
                if not can_increase:
                    break
                
                sem = random.choice([s for s in self.config.seminars if target_sizes[s] < self.config.max_size])
                target_sizes[sem] += 1
        
        total = sum(target_sizes.values())
        while total != self.config.num_students:
            if total < self.config.num_students:
                available_sems = [s for s in self.config.seminars 
                                  if target_sizes[s] < self.config.max_size] 
                if available_sems:
                    sem = random.choice(available_sems)
                    target_sizes[sem] += 1
                    total += 1
                else:
                    break
            else: # total > self.config.num_students
                reducible_sems = [s for s in self.config.seminars 
                                  if target_sizes[s] > self.config.min_size]
                if reducible_sems:
                    sem = random.choice(reducible_sems)
                    target_sizes[sem] -= 1
                    total -= 1
                else:
                    break
        
        return target_sizes
