import os
import csv
import logging
from typing import Dict, List, Tuple, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# 外部モジュールからのインポート
from models import Config, Student
from utils import PreferenceGenerator 

logger = logging.getLogger(__name__)

def generate_pdf_report(config: Config, best_pattern: dict[str, int], best_score: float, # 修正: dictを使用
                        best_assignments: dict[str, list[tuple[int, float]]], pattern_id: int, # 修正: dict, list, tupleを使用
                        is_intermediate: bool = False, iteration_count: Optional[int] = None) -> bool:
    """
    詳細なPDFレポートを生成します (英語)。
    is_intermediate=Trueの場合、途中経過レポートとしてファイル名に試行回数が含まれます。
    """
    try:
        if is_intermediate and iteration_count is not None:
            pdf_file_name = f"seminar_results_intermediate_{iteration_count}.pdf"
        else:
            pdf_file_name = "seminar_results_advanced.pdf"
        
        pdf_file_path = os.path.join(config.output_dir, pdf_file_name)
        doc = SimpleDocTemplate(pdf_file_path, pagesize=letter)
        styles = getSampleStyleSheet()
        
        styles['Normal'].fontName = 'IPAexGothic' 
        styles['Title'].fontName = 'IPAexGothic' 
        styles['Heading1'].fontName = 'IPAexGothic' 
        styles['Heading2'].fontName = 'IPAexGothic' 
        styles['Heading3'].fontName = 'IPAexGothic' 

        elements = []
        
        report_title = "High-Precision Seminar Assignment Optimization Results"
        if is_intermediate:
            report_title += f" (Intermediate Report - Iteration {iteration_count})"
        elements.append(Paragraph(report_title, styles['Title']))
        elements.append(Paragraph(f"Pattern ID: {pattern_id} | Total Score: {best_score:.2f}", styles['Heading2']))
        elements.append(Spacer(1, 12))
        
        elements.append(Paragraph(f"Total Students: {config.num_students}", styles['Normal']))
        elements.append(Paragraph(f"Number of Patterns Evaluated: {config.num_patterns}", styles['Normal']))
        elements.append(Paragraph(f"Number of Parallel Processes: {config.max_workers}", styles['Normal']))
        elements.append(Spacer(1, 12))
        
        from evaluation import calculate_satisfaction_stats 
        satisfaction_stats = calculate_satisfaction_stats(config, best_assignments, pattern_id) 
        elements.append(Paragraph("Student Satisfaction Statistics:", styles['Heading2']))
        elements.append(Paragraph(f"1st Preference Achieved: {satisfaction_stats['first']:.1f}%", styles['Normal']))
        elements.append(Paragraph(f"2nd Preference Achieved: {satisfaction_stats['second']:.1f}%", styles['Normal']))
        elements.append(Paragraph(f"3rd Preference Achieved: {satisfaction_stats['third']:.1f}%", styles['Normal']))
        elements.append(Paragraph(f"Not Preferred: {satisfaction_stats['none']:.1f}%", styles['Normal']))
        elements.append(Spacer(1, 12))
        
        table_data = [["Seminar", "Target", "Actual", "Total Score", "Avg. Satisfaction", "1st Pref. Count", "Details"]]
        
        temp_pref_gen = PreferenceGenerator(asdict(config))
        students_for_stats = temp_pref_gen.generate_realistic_preferences(42 + pattern_id)
        students_dict_for_stats = {s.id: s for s in students_for_stats}

        for sem in config.seminars:
            students_scores = best_assignments[sem]
            target_size = best_pattern[sem]
            actual_size = len(students_scores)
            total_score = sum(score for _, score in students_scores)
            avg_satisfaction = total_score / actual_size if actual_size > 0 else 0
            
            first_choice_count = 0
            for student_id, _ in students_scores:
                student_obj = students_dict_for_stats.get(student_id)
                if student_obj and student_obj.get_preference_rank(sem) == 0:
                    first_choice_count += 1
            
            detail = ", ".join([f"S{s}({sc:.1f})" for s, sc in students_scores[:min(len(students_scores), 5)]]) 
            if len(students_scores) > 5:
                detail += f"... ({len(students_scores)-5} others)"
            
            mag_indicator = f" ({config.magnification[sem]}x)" if sem in config.magnification else ""
            
            table_data.append([
                sem.upper() + mag_indicator,
                str(target_size),
                str(actual_size),
                f"{total_score:.1f}",
                f"{avg_satisfaction:.2f}",
                str(first_choice_count),
                detail
            ])
        
        table = Table(table_data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'IPAexGothic'), 
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'IPAexGothic'), 
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        
        elements.append(table)
        elements.append(Spacer(1, 12))
        
        elements.append(Paragraph("Algorithms Used:", styles['Heading2']))
        elements.append(Paragraph("1. Realistic Preference Distribution Generation", styles['Normal']))
        elements.append(Paragraph("2. **Greedy Initial Assignment**", styles['Normal'])) 
        elements.append(Paragraph("3. Local Search Improvement (2-opt & Single Move + Simplified Simulated Annealing)", styles['Normal']))
        elements.append(Paragraph("4. Speedup through Parallel Processing", styles['Normal']))
        
        doc.build(elements)
        logger.info(f"PDF report generated: {pdf_file_path}")
        return True
        
    except Exception as e:
        logger.error(f"PDF generation error: {e}")
        return False

def save_csv_results(config: Config, assignments: dict[str, list[tuple[int, float]]], pattern_id: int, # 修正: dict, list, tupleを使用
                     is_intermediate: bool = False, iteration_count: Optional[int] = None) -> bool:
    """
    割当結果をCSVファイルに保存します。
    is_intermediate=Trueの場合、途中経過レポートとしてファイル名に試行回数が含まれます。
    """
    if is_intermediate and iteration_count is not None:
        csv_file_name = f"best_assignment_intermediate_{iteration_count}.csv"
    else:
        csv_file_name = "best_assignment_advanced.csv"

    csv_file_path = os.path.join(config.output_dir, csv_file_name)
    try:
        with open(csv_file_path, "w", newline="", encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Seminar", "Student_ID", "Score", "Rank"])
            
            temp_pref_gen = PreferenceGenerator(asdict(config))
            students_for_csv = temp_pref_gen.generate_realistic_preferences(42 + pattern_id)
            students_dict_for_csv = {s.id: s for s in students_for_csv}

            for sem in config.seminars:
                for student_id, score in assignments[sem]:
                    rank_str = "None"
                    student_obj = students_dict_for_csv.get(student_id)
                    if student_obj:
                        rank = student_obj.get_preference_rank(sem)
                        if rank == 0:
                            rank_str = "1st"
                        elif rank == 1:
                            rank_str = "2nd"
                        elif rank == 2:
                            rank_str = "3rd"
                    writer.writerow([sem, student_id, f"{score:.2f}", rank_str])
        logger.info(f"CSV results saved to: {csv_file_path}")
        return True
    except Exception as e:
        logger.error(f"CSV saving error: {e}")
        return False

