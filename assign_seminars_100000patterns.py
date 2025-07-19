# seminar_optimization_improved.py
import random
import csv
import os
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.fonts import addMapping

# 定数と設定
SEMINARS = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q']
MAGNIFICATION = {'a': 2.0, 'd': 3.0, 'm': 0.5, 'o': 0.25}
MIN_SIZE, MAX_SIZE = 5, 10
NUM_STUDENTS = 112
NUM_PATTERNS = 100000
EARLY_STOP_THRESHOLD = 0.001
NO_IMPROVEMENT_LIMIT = 1000
OUTPUT_DIR = "results"
os.makedirs(OUTPUT_DIR, exist_ok=True)
PDF_FILE = os.path.join(OUTPUT_DIR, "seminar_results.pdf")

# フォント設定（黒塗り対策）
addMapping('Helvetica', 0, 0, 'Helvetica')  # 標準フォント
addMapping('Helvetica', 1, 1, 'Helvetica-Bold')  # ボールドフォント

# 希望データを生成（qの第1希望を20%増強）
def generate_preferences(seed):
    """学生の希望を生成"""
    random.seed(seed)
    preferences = {}
    for student_id in range(1, NUM_STUDENTS + 1):
        prefs = random.sample(SEMINARS, 3)
        if random.random() < 0.2:  # qの第1希望を20%増やす
            prefs[0] = 'q'
        preferences[student_id] = {'first': prefs[0], 'second': prefs[1], 'third': prefs[2]}
    return preferences

def generate_target_sizes():
    """セミナーの目標人数を生成（合計がNUM_STUDENTSになるように調整）"""
    sizes = [MIN_SIZE] * len(SEMINARS)
    remaining_students = NUM_STUDENTS - sum(sizes)
    
    for _ in range(remaining_students):
        available_seminars = [i for i, size in enumerate(sizes) if size < MAX_SIZE]
        if not available_seminars:
            seminar_idx = random.randint(0, len(SEMINARS) - 1)
        else:
            seminar_idx = random.choice(available_seminars)
        sizes[seminar_idx] += 1
    
    target_sizes = {sem: size for sem, size in zip(SEMINARS, sizes)}
    total = sum(target_sizes.values())
    if total != NUM_STUDENTS:
        diff = NUM_STUDENTS - total
        if diff > 0:
            for _ in range(abs(diff)):
                sem = random.choice(SEMINARS)
                target_sizes[sem] += 1
        else:
            for _ in range(abs(diff)):
                available_sems = [s for s in SEMINARS if target_sizes[s] > MIN_SIZE]
                if available_sems:
                    sem = random.choice(available_sems)
                    target_sizes[sem] -= 1
    return target_sizes

def calculate_score(student, preferences, seminar, magnification=True):
    """学生のセミナーに対するスコアを計算"""
    prefs = preferences[student]
    base_score = 0
    if prefs['first'] == seminar:
        base_score = 3
    elif prefs['second'] == seminar:
        base_score = 2
    elif prefs['third'] == seminar:
        base_score = 1
    else:
        base_score = 0
    return base_score * MAGNIFICATION.get(seminar, 1.0) if magnification else base_score

def assign_students(preferences, target_sizes):
    """学生をセミナーに割り当て（シャッフル再試行を追加）"""
    assignments = {sem: [] for sem in SEMINARS}
    assigned_students = set()
    
    for _ in range(3):  # 3回再試行
        assigned_students.clear()
        for sem in SEMINARS:
            target_size = target_sizes[sem]
            candidates = [(s, calculate_score(s, preferences, sem)) for s in range(1, NUM_STUDENTS + 1) if s not in assigned_students]
            candidates.sort(key=lambda x: x[1], reverse=True)
            for student, score in candidates[:target_size]:
                assignments[sem].append((student, score))
                assigned_students.add(student)
        
        if len(assigned_students) == NUM_STUDENTS:
            break
        
        random.shuffle(list(preferences.items()))
    
    # 未割り当ての処理
    unassigned = set(range(1, NUM_STUDENTS + 1)) - assigned_students
    if unassigned:
        print(f"Warning: {len(unassigned)} students remain unassigned: {list(unassigned)}")
        for student in unassigned:
            available_seminars = [sem for sem in SEMINARS if len(assignments[sem]) < target_sizes[sem]]
            if available_seminars:
                sem = random.choice(available_seminars)
                score = calculate_score(student, preferences, sem)
                assignments[sem].append((student, score))
            else:
                sem = random.choice(SEMINARS)
                score = calculate_score(student, preferences, sem)
                assignments[sem].append((student, score))
    
    total_score = sum(score for sem in assignments for _, score in assignments[sem])
    return total_score, assignments

def validate_assignment(assignments, target_sizes):
    """割り当て結果の妥当性を検証"""
    total_assigned = sum(len(assignments[sem]) for sem in SEMINARS)
    if total_assigned != NUM_STUDENTS:
        print(f"Error: Total assigned students {total_assigned} != {NUM_STUDENTS}")
        return False
    for sem in SEMINARS:
        actual_size = len(assignments[sem])
        target_size = target_sizes[sem]
        if actual_size != target_size:
            print(f"Warning: Seminar {sem} has {actual_size} students, target was {target_size}")
    return True

def generate_pdf_report(best_pattern, best_score, best_assignments, pattern_id):
    """PDF レポートを生成（黒塗り対策）"""
    try:
        doc = SimpleDocTemplate(PDF_FILE, pagesize=letter)
        styles = getSampleStyleSheet()
        elements = []
        
        elements.append(Paragraph(f"セミナー割り当て最適化結果 (パターンID: {pattern_id})", styles['Title']))
        elements.append(Spacer(1, 12))
        
        elements.append(Paragraph(f"総学生数: {NUM_STUDENTS}人", styles['Normal']))
        elements.append(Paragraph(f"総得点: {best_score:.2f}", styles['Normal']))
        elements.append(Spacer(1, 12))
        
        table_data = [["セミナー", "割り当て人数", "セミナー得点", "平均スコア", "詳細"]]
        for sem in SEMINARS:
            students_scores = best_assignments[sem]
            size = len(students_scores)
            total_score = sum(score for _, score in students_scores)
            avg_score = total_score / size if size > 0 else 0
            detail = ", ".join([f"S{s}({sc:.1f})" for s, sc in students_scores[:5]])
            if len(students_scores) > 5:
                detail += f"... (他{len(students_scores)-5}人)"
            table_data.append([sem.upper(), str(size), f"{total_score:.1f}", f"{avg_score:.2f}", detail])
        
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),  # ヘッダー背景
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),      # ヘッダー黒文字
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),    # セル白背景
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),     # セル黒文字
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 12))
        
        elements.append(Paragraph("重み付け設定:", styles['Heading2']))
        for sem, mag in MAGNIFICATION.items():
            elements.append(Paragraph(f"セミナー {sem.upper()}: {mag}倍", styles['Normal']))
        
        doc.build(elements)
        print(f"PDF レポートを生成しました: {PDF_FILE}")
        return True
    except Exception as e:
        print(f"PDF生成エラー: {e}")
        return False

def optimize_and_generate_pdf():
    """最適化の実行とPDF生成"""
    best_score = 0
    best_pattern = None
    best_assignments = None
    best_pattern_id = 0
    no_improvement_count = 0
    
    print(f"最適化開始: {NUM_PATTERNS}パターンを評価します...")
    
    for pattern_id in range(NUM_PATTERNS):
        if (pattern_id + 1) % 10000 == 0:
            print(f"進捗: {pattern_id + 1}/{NUM_PATTERNS} (現在の最高得点: {best_score:.2f})")
        
        preferences = generate_preferences(42 + pattern_id)
        target_sizes = generate_target_sizes()
        total_score, assignments = assign_students(preferences, target_sizes)
        
        if not validate_assignment(assignments, target_sizes):
            continue
        
        if total_score > best_score:
            best_score = total_score
            best_pattern = target_sizes.copy()
            best_assignments = assignments.copy()
            best_pattern_id = pattern_id
            no_improvement_count = 0
            print(f"新記録! パターン{pattern_id}: スコア {total_score:.2f}")
        else:
            no_improvement_count += 1
        
        if no_improvement_count >= NO_IMPROVEMENT_LIMIT and best_score > 0:
            print(f"早期終了: {NO_IMPROVEMENT_LIMIT}パターン連続で改善なし (パターン {pattern_id + 1})")
            break
    
    print(f"\n=== 最適化結果 ===")
    print(f"最高得点: {best_score:.2f}")
    print(f"最適パターンID: {best_pattern_id}")
    for sem in SEMINARS:
        size = len(best_assignments[sem]) if sem in best_assignments else 0
        total_sem_score = sum(score for _, score in best_assignments[sem]) if sem in best_assignments else 0
        print(f"  {sem.upper()}: {size}人 (得点: {total_sem_score:.1f})")
    
    csv_file = os.path.join(OUTPUT_DIR, "best_assignment.csv")
    try:
        with open(csv_file, "w", newline="", encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Seminar", "Student_ID", "Score"])
            for sem in SEMINARS:
                for student, score in best_assignments[sem]:
                    writer.writerow([sem, student, score])
        print(f"CSV結果を保存しました: {csv_file}")
    except Exception as e:
        print(f"CSV保存エラー: {e}")
    
    if generate_pdf_report(best_pattern, best_score, best_assignments, best_pattern_id):
        print("レポート生成完了")
    
    return best_pattern, best_score, best_assignments

if __name__ == "__main__":
    try:
        best_pattern, best_score, best_assignments = optimize_and_generate_pdf()
    except Exception as e:
        print(f"エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()