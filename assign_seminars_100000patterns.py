# seminar_optimization.py
import random
import csv
import os

# 定数と設定
SEMINARS = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q']
MAGNIFICATION = {'a': 2.0, 'd': 3.0, 'm': 0.5, 'o': 0.25}
MIN_SIZE, MAX_SIZE = 5, 10
NUM_STUDENTS = 112
NUM_PATTERNS = 100000
EARLY_STOP_THRESHOLD = 0.000001  # 0.1%改善なしで終了
NO_IMPROVEMENT_LIMIT = 1000
OUTPUT_DIR = "results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 希望データを生成する関数
def generate_preferences(seed):
    random.seed(seed)
    preferences = {}
    for student_id in range(1, NUM_STUDENTS + 1):
        prefs = random.sample(SEMINARS, 3)
        preferences[student_id] = {'first': prefs[0], 'second': prefs[1], 'third': prefs[2]}
    return preferences

# 人数配分を生成する関数
def generate_pattern(remaining_seminars, remaining_students):
    sizes = []
    for _ in range(remaining_seminars - 1):
        max_possible = min(MAX_SIZE, remaining_students - (remaining_seminars - 1) * MIN_SIZE)
        min_possible = max(MIN_SIZE, remaining_students - (remaining_seminars - 1) * MAX_SIZE)
        size = random.randint(min_possible, max_possible)
        sizes.append(size)
        remaining_students -= size
    sizes.append(remaining_students)
    random.shuffle(sizes)
    return sizes

# 割り当てを実行する関数
def assign_students(preferences, target_sizes):
    assignments = {sem: [] for sem in SEMINARS}
    assigned_students = set()
    
    for sem in SEMINARS:
        target_size = target_sizes[sem]
        available = []
        for student, prefs in preferences.items():
            if student in assigned_students:
                continue
            if prefs['first'] == sem:
                available.append((student, 3))
            elif prefs['second'] == sem:
                available.append((student, 2))
            elif prefs['third'] == sem:
                available.append((student, 1))
        
        available.sort(key=lambda x: x[1], reverse=True)
        for student, score in available[:target_size]:
            assignments[sem].append((student, score))
            assigned_students.add(student)
        
        remaining = target_size - len(assignments[sem])
        if remaining > 0:
            unassigned = [s for s in range(1, NUM_STUDENTS + 1) if s not in assigned_students]
            for student in unassigned[:remaining]:
                assignments[sem].append((student, 0))
                assigned_students.add(student)
    
    total_score = sum(score for sem in assignments for _, score in assignments[sem])
    return total_score, assignments

# メイン処理
def optimize_assignments():
    best_score = 0
    best_pattern = None
    best_assignments = None
    no_improvement_count = 0
    
    for pattern_id in range(NUM_PATTERNS):
        # 各パターンで希望データと人数配分を生成
        preferences = generate_preferences(42 + pattern_id)
        target_sizes = {'a': 10, 'd': 7, 'm': 10, 'o': 10}
        sizes = generate_pattern(13, 75)
        for sem, size in zip([s for s in SEMINARS if s not in ['a', 'd', 'm', 'o']], sizes):
            target_sizes[sem] = size
        
        # 割り当てと得点計算
        total_score, assignments = assign_students(preferences, target_sizes)
        
        # 最高得点の更新
        if total_score > best_score:
            best_score = total_score
            best_pattern = target_sizes.copy()
            best_assignments = assignments.copy()
            no_improvement_count = 0
        else:
            no_improvement_count += 1
        
        # 早期終了チェック
        if no_improvement_count >= NO_IMPROVEMENT_LIMIT and best_score > 0:
            print(f"Early stopping at pattern {pattern_id + 1}: No improvement for {NO_IMPROVEMENT_LIMIT} patterns")
            break
    
    # 結果をCSVに保存
    with open(os.path.join(OUTPUT_DIR, "best_assignment.csv"), "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Seminar", "Students", "Scores"])
        for sem in SEMINARS:
            students = [s for s, _ in best_assignments[sem]]
            scores = [sc for _, sc in best_assignments[sem]]
            writer.writerow([sem, students, scores])
    
    print(f"Best Pattern (ID {pattern_id}):")
    print(f"Target Sizes: {best_pattern}")
    print(f"Total Score: {best_score}")
    for sem in SEMINARS:
        print(f"{sem}: {len(best_assignments[sem])} students, Scores={[(s, sc) for s, sc in best_assignments[sem]]}")
    
    return best_pattern, best_score, best_assignments

if __name__ == "__main__":
    try:
        best_pattern, best_score, best_assignments = optimize_assignments()
    except Exception as e:
        print(f"Error occurred: {e}")

# requirements.txt
# pandas
# matplotlib