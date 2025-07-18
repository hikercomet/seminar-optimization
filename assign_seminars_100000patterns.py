import random
import math

# セミナー情報
seminars = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q']
magnification = {'a': 2.0, 'd': 3.0, 'm': 0.5, 'o': 0.25}
min_size, max_size = 5, 10
num_students = 112
num_patterns = 100000
early_stop_threshold = 0.001  # 0.1%改善なしで終了
no_improvement_limit = 1000

# 希望データ生成（シード42）
random.seed(42)
preferences = {}
for i in range(1, num_students + 1):
    prefs = random.sample(seminars, 3)
    preferences[i] = {'first': prefs[0], 'second': prefs[1], 'third': prefs[2]}

applicants = {sem: {'first': 0, 'second': 0, 'third': 0, 'total': 0} for sem in seminars}
for student, prefs in preferences.items():
    applicants[prefs['first']]['first'] += 1
    applicants[prefs['first']]['total'] += 1
    applicants[prefs['second']]['second'] += 1
    applicants[prefs['second']]['total'] += 1
    applicants[prefs['third']]['third'] += 1
    applicants[prefs['third']]['total'] += 1

# 人数配分をランダムに生成
def generate_pattern(remaining_seminars, remaining_students):
    sizes = []
    for i in range(remaining_seminars - 1):
        max_possible = min(max_size, remaining_students - (remaining_seminars - i - 1) * min_size)
        min_possible = max(min_size, remaining_students - (remaining_seminars - i - 1) * max_size)
        size = random.randint(min_possible, max_possible)
        sizes.append(size)
        remaining_students -= size
    sizes.append(remaining_students)
    random.shuffle(sizes)
    return sizes

# 100,000パターンの割り当てと得点計算
best_score = 0
best_pattern = None
best_assignments = None
no_improvement_count = 0
patterns = []

for pattern_id in range(num_patterns):
    random.seed(42 + pattern_id)
    target_sizes = {'a': 10, 'd': 7, 'm': 10, 'o': 10}
    sizes = generate_pattern(13, 75)
    for sem, size in zip([s for s in seminars if s not in ['a', 'd', 'm', 'o']], sizes):
        target_sizes[sem] = size
    
    # 割り当て
    assignments = {sem: [] for sem in seminars}
    assigned_students = set()
    
    for sem in seminars:
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
            unassigned = [s for s in range(1, num_students + 1) if s not in assigned_students]
            for student in unassigned[:remaining]:
                assignments[sem].append((student, 0))
                assigned_students.add(student)
    
    total_score = sum(score for sem in assignments for _, score in assignments[sem])
    patterns.append((pattern_id, target_sizes, total_score, assignments))
    
    if total_score > best_score:
        best_score = total_score
        best_pattern = target_sizes
        best_assignments = assignments
        no_improvement_count = 0
    else:
        no_improvement_count += 1
    
    # 早期終了チェック
    if no_improvement_count >= no_improvement_limit and best_score > 0:
        print(f"Early stopping at pattern {pattern_id + 1}: No improvement for {no_improvement_limit} patterns")
        break

# 最高得点のパターンの出力
print(f"Best Pattern (ID {patterns[-1][0]}):")
print(f"Target Sizes: {best_pattern}")
print(f"Total Score: {best_score}")
for sem in seminars:
    print(f"{sem}: {len(best_assignments[sem])} students, Scores={[(s, sc) for s, sc in best_assignments[sem]]}")

