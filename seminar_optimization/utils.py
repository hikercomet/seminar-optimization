import random
from collections import defaultdict
# 修正: Dict, List, Tuple を dict, list, tuple に変更
# from typing import Dict, List, Tuple 
import numpy as np
from dataclasses import asdict
import csv 

# 外部モジュールからのインポート
from models import Config, Student 

class PreferenceGenerator:
    def __init__(self, config_dict: dict): # 修正: dictを使用
        self.config = Config(**config_dict) 
    
    def generate_realistic_preferences(self, seed: int) -> list[Student]: # 修正: listを使用
        """より現実的な希望分布を生成します"""
        random.seed(seed)
        students = []
        
        if not self.config.seminars:
            raise ValueError("Config.seminars が設定されていません。自動生成できません。")

        popularity_weights = {sem: 1.0 for sem in self.config.seminars}
        popularity_weights.update({
            'a': 1.5, 'd': 1.8, 'q': 1.2, 'm': 0.7, 'o': 0.5
        })
        
        for student_id in range(1, self.config.num_students + 1):
            if random.random() < self.config.q_boost_probability:
                first_choice = 'q'
            else:
                seminars_list = list(self.config.seminars)
                weights = [popularity_weights[sem] for sem in seminars_list]
                first_choice = random.choices(seminars_list, weights=weights)[0]
            
            remaining_seminars = [s for s in self.config.seminars if s != first_choice]
            
            second_weights = []
            for sem in remaining_seminars:
                base_weight = popularity_weights[sem]
                if abs(ord(first_choice) - ord(sem)) <= 2:
                    base_weight *= 1.3
                second_weights.append(base_weight)
            
            second_choice = random.choices(remaining_seminars, weights=second_weights)[0]
            
            final_remaining = [s for s in remaining_seminars if s != second_choice]
            third_choice = random.choice(final_remaining)
            
            preferences = [first_choice, second_choice, third_choice]
            students.append(Student(student_id, preferences))
        
        return students

    def load_preferences_from_csv(self, file_path: str) -> list[Student]: # 修正: listを使用
        """CSVファイルから学生の希望データを読み込みます。"""
        students = []
        with open(file_path, 'r', newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader) 
            
            for row in reader:
                try:
                    student_id = int(row[0])
                    preferences = [p.strip() for p in row[1:4] if p.strip()] 
                    students.append(Student(student_id, preferences))
                except ValueError as e:
                    print(f"警告: CSVの行をスキップしました (無効なデータ形式): {row} - エラー: {e}")
                except IndexError:
                    print(f"警告: CSVの行をスキップしました (列数が不足しています): {row}")
        return students

class TargetSizeOptimizer:
    def __init__(self, config_dict: dict): # 修正: dictを使用
        self.config = Config(**config_dict) 
    
    def generate_balanced_sizes(self, students: list[Student], attempt: int = 0) -> dict[str, int]: # 修正: list, dictを使用
        """学生の希望を考慮したバランスの取れた目標定員を生成します (多様な戦略)"""
        first_choice_count = defaultdict(int)
        for student in students:
            first_choice_count[student.preferences[0]] += 1
        
        if not self.config.seminars:
            raise ValueError("Config.seminars が設定されていません。目標定員を生成できません。")

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
            avg_first_choice = sum(first_choice_count.values()) / len(self.config.seminars)
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
                sem = random.choice(self.config.seminars)
                target_sizes[sem] += 1
        
        total = sum(target_sizes.values())
        while total != self.config.num_students:
            if total < self.config.num_students:
                available_sems = [s for s in self.config.seminars 
                                  if target_sizes[s] < self.config.max_size * 1.2]
                if available_sems:
                    sem = random.choice(available_sems)
                    target_sizes[sem] += 1
                    total += 1
                else:
                    break
            else:
                reducible_sems = [s for s in self.config.seminars 
                                  if target_sizes[s] > self.config.min_size]
                if reducible_sems:
                    sem = random.choice(reducible_sems)
                    target_sizes[sem] -= 1
                    total -= 1
                else:
                    break
        
        return target_sizes
