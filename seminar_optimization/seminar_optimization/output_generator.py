import os
from datetime import datetime
import logging
import pandas as pd
import csv # csvモジュールを明示的にインポート
from typing import List, Dict, Any, Tuple, Optional

# ReportLab のインポート
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm

logger = logging.getLogger(__name__)

# --- ヘルパー関数 ---
def _calculate_satisfaction_stats(students: List[Dict[str, Any]], assignment: Dict[str, str]) -> Dict[str, Any]:
    """
    学生の満足度統計を計算する。
    Args:
        students: 全学生のデータリスト (例: [{"id": "S1", "preferences": ["SemA", "SemB"]}])
        assignment: 学生IDと割り当てられたセミナーIDの辞書 (例: {"S1": "SemA", "S2": "SemB"})
    Returns:
        満足度統計の辞書
    """
    stats = {
        '1st_choice': 0,
        '2nd_choice': 0,
        '3rd_choice': 0,
        'other_preference': 0,
        'no_preference_met': 0,
        'unassigned': 0,
        'total_students': len(students)
    }
    
    assigned_student_ids = set(assignment.keys())
    
    for student in students:
        student_id = student['id']
        assigned_seminar = assignment.get(student_id)
        preferences = student.get('preferences', [])

        if student_id not in assigned_student_ids or assigned_seminar is None:
            stats['unassigned'] += 1
        else:
            try:
                rank = preferences.index(assigned_seminar)
                if rank == 0:
                    stats['1st_choice'] += 1
                elif rank == 1:
                    stats['2nd_choice'] += 1
                elif rank == 2:
                    stats['3rd_choice'] += 1
                else:
                    stats['other_preference'] += 1
            except ValueError:
                # 希望リストにないセミナーに割り当てられた場合
                stats['no_preference_met'] += 1
    
    total_assigned_students = stats['1st_choice'] + stats['2nd_choice'] + stats['3rd_choice'] + stats['other_preference'] + stats['no_preference_met']
    stats['total_assigned_students'] = total_assigned_students

    # 割合の計算
    if stats['total_students'] > 0:
        stats['1st_choice_ratio'] = (stats['1st_choice'] / stats['total_students']) * 100
        stats['2nd_choice_ratio'] = (stats['2nd_choice'] / stats['total_students']) * 100
        stats['3rd_choice_ratio'] = (stats['3rd_choice'] / stats['total_students']) * 100
        stats['other_preference_ratio'] = (stats['other_preference'] / stats['total_students']) * 100
        stats['no_preference_met_ratio'] = (stats['no_preference_met'] / stats['total_students']) * 100
        stats['unassigned_ratio'] = (stats['unassigned'] / stats['total_students']) * 100
    else:
        for key in ['1st_choice_ratio', '2nd_choice_ratio', '3rd_choice_ratio', 'other_preference_ratio', 'no_preference_met_ratio', 'unassigned_ratio']:
            stats[key] = 0.0

    return stats

def _get_seminar_assignment_details(seminars: List[Dict[str, Any]], assignment: Dict[str, str], seminar_capacities: Dict[str, int]) -> List[Dict[str, Any]]:
    """
    セミナーごとの割り当て詳細を計算する。
    """
    seminar_counts: Dict[str, int] = {s['id']: 0 for s in seminars}
    for assigned_seminar_id in assignment.values():
        if assigned_seminar_id in seminar_counts:
            seminar_counts[assigned_seminar_id] += 1

    details = []
    for seminar in seminars:
        seminar_id = seminar['id']
        capacity = seminar_capacities.get(seminar_id, 0)
        assigned_count = seminar_counts.get(seminar_id, 0)
        remaining_capacity = capacity - assigned_count
        magnification = seminar.get('magnification', 1.0) # 倍率も取得

        details.append({
            'seminar_id': seminar_id,
            'capacity': capacity,
            'assigned_students_count': assigned_count,
            'remaining_capacity': remaining_capacity,
            'magnification': magnification
        })
    return details

def _get_unassigned_students_details(students: List[Dict[str, Any]], assignment: Dict[str, str]) -> List[str]:
    """
    未割り当て学生のIDリストを返す。
    """
    assigned_student_ids = set(assignment.keys())
    unassigned_students = [s['id'] for s in students if s['id'] not in assigned_student_ids]
    return sorted(unassigned_students)


def save_pdf_report(
    config: Dict[str, Any], # Configオブジェクトではなく辞書を受け取る
    final_assignment: Dict[str, str], # 学生ID -> セミナーID の形式
    optimization_strategy: str, # 最適化戦略名を直接受け取る
    is_intermediate: bool = False,
    iteration_count: Optional[int] = None
):
    """
    最終割り当て結果をPDFレポートとして保存します。
    Args:
        config: アプリケーション設定の辞書。これには 'students_data_for_report' と 'seminars_data_for_report' が含まれる想定。
        final_assignment: 学生IDと割り当てられたセミナーIDの辞書。
        optimization_strategy: 使用された最適化戦略の名前。
        is_intermediate: 中間レポートかどうか。
        iteration_count: 中間レポートの場合のイテレーション回数。
    """
    students = config.get('students_data_for_report', []) # ここでstudentsデータをconfigから取得
    seminars = config.get('seminars_data_for_report', []) # ここでseminarsデータをconfigから取得
    seminar_capacities = {s['id']: s['capacity'] for s in seminars}

    output_dir = config.get('data_directory', 'data')
    os.makedirs(output_dir, exist_ok=True)
    
    current_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file_base = config.get('results_file', 'optimization_results.json').replace('.json', '')
    if is_intermediate:
        output_filename = os.path.join(output_dir, f"intermediate_{results_file_base}_{optimization_strategy}_iter_{iteration_count}.pdf")
    else:
        output_filename = os.path.join(output_dir, f"{results_file_base}_{optimization_strategy}_{current_time_str}.pdf")

    doc = SimpleDocTemplate(output_filename, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # タイトル
    story.append(Paragraph(f"セミナー割り当て最適化レポート ({optimization_strategy})", styles['h1']))
    story.append(Spacer(1, 0.5 * cm))

    # 基本情報
    story.append(Paragraph(f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Paragraph(f"最適化戦略: {optimization_strategy}", styles['Normal']))
    story.append(Spacer(1, 0.5 * cm))

    # 学生の満足度統計
    satisfaction_stats = _calculate_satisfaction_stats(students, final_assignment)
    story.append(Paragraph("学生の満足度統計", styles['h2']))
    
    satisfaction_data = [
        ["選択順位", "学生数", "割合 (%)"],
        ["1st Choice", satisfaction_stats['1st_choice'], f"{satisfaction_stats['1st_choice_ratio']:.2f}%"],
        ["2nd Choice", satisfaction_stats['2nd_choice'], f"{satisfaction_stats['2nd_choice_ratio']:.2f}%"],
        ["3rd Choice", satisfaction_stats['3rd_choice'], f"{satisfaction_stats['3rd_choice_ratio']:.2f}%"],
        ["Other Preference", satisfaction_stats['other_preference'], f"{satisfaction_stats['other_preference_ratio']:.2f}%"],
        ["No Preference Met", satisfaction_stats['no_preference_met'], f"{satisfaction_stats['no_preference_met_ratio']:.2f}%"],
        ["未割り当て", satisfaction_stats['unassigned'], f"{satisfaction_stats['unassigned_ratio']:.2f}%"],
        ["合計", satisfaction_stats['total_assigned_students'] + satisfaction_stats['unassigned'], "100.00%"]
    ]
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ])
    table = Table(satisfaction_data)
    table.setStyle(table_style)
    story.append(table)
    story.append(Spacer(1, 0.5 * cm))

    # セミナーごとの割り当て状況
    seminar_details = _get_seminar_assignment_details(seminars, final_assignment, seminar_capacities)
    story.append(Paragraph("セミナーごとの割り当て状況", styles['h2']))
    
    seminar_data_table = [["セミナーID", "定員", "割り当て数", "空き", "倍率"]]
    for detail in seminar_details:
        seminar_data_table.append([
            detail['seminar_id'],
            detail['capacity'],
            detail['assigned_students_count'],
            detail['remaining_capacity'],
            f"{detail['magnification']:.2f}x"
        ])
    table = Table(seminar_data_table)
    table.setStyle(table_style)
    story.append(table)
    story.append(Spacer(1, 0.5 * cm))

    # 未割り当て学生
    unassigned_students_list = _get_unassigned_students_details(students, final_assignment)
    if unassigned_students_list:
        story.append(Paragraph("未割り当て学生", styles['h2']))
        unassigned_text = ", ".join(unassigned_students_list)
        story.append(Paragraph(unassigned_text, styles['Normal']))
        story.append(Spacer(1, 0.5 * cm))
    else:
        story.append(Paragraph("全ての学生が割り当てられました。", styles['Normal']))
        story.append(Spacer(1, 0.5 * cm))

    try:
        doc.build(story)
        logger.info(f"PDFレポート '{output_filename}' を正常に生成しました。")
    except Exception as e:
        logger.error(f"PDFレポートのビルド中にエラーが発生しました: {e}")
        raise


def save_csv_results(
    config: Dict[str, Any], # Configオブジェクトではなく辞書を受け取る
    final_assignment: Dict[str, str], # 学生ID -> セミナーID の形式
    optimization_strategy: str, # 最適化戦略名を直接受け取る
    is_intermediate: bool = False,
    iteration_count: Optional[int] = None
):
    """
    最終割り当て結果をCSVファイルとして保存します。
    Args:
        config: アプリケーション設定の辞書。これには 'students_data_for_report' と 'seminars_data_for_report' が含まれる想定。
        final_assignment: 学生IDと割り当てられたセミナーIDの辞書。
        optimization_strategy: 使用された最適化戦略の名前。
        is_intermediate: 中間レポートかどうか。
        iteration_count: 中間レポートの場合のイテレーション回数。
    """
    students = config.get('students_data_for_report', []) # ここでstudentsデータをconfigから取得
    seminars = config.get('seminars_data_for_report', []) # ここでseminarsデータをconfigから取得
    seminar_capacities = {s['id']: s['capacity'] for s in seminars}

    output_dir = config.get('data_directory', 'data')
    results_file_base = config.get('results_file', 'optimization_results.json').replace('.json', '')

    os.makedirs(output_dir, exist_ok=True)

    current_time_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_filename_assignment = os.path.join(output_dir, f"{results_file_base}_assignment_{optimization_strategy}_{current_time_str}.csv")
    output_filename_summary = os.path.join(output_dir, f"{results_file_base}_summary_{optimization_strategy}_{current_time_str}.csv")

    if is_intermediate:
        output_filename_assignment = os.path.join(output_dir, f"intermediate_assignment_iter_{iteration_count}.csv")
        output_filename_summary = os.path.join(output_dir, f"intermediate_summary_iter_{iteration_count}.csv")

    try:
        # 割り当て結果の詳細CSV
        with open(output_filename_assignment, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Student ID', 'Assigned Seminar ID', 'Preference Rank', 'Is Preferred'])
            
            for student_info in students:
                student_id = student_info['id']
                assigned_seminar = final_assignment.get(student_id)
                preferences = student_info.get('preferences', [])
                
                if assigned_seminar:
                    try:
                        rank = preferences.index(assigned_seminar) + 1 # 0-indexed to 1-indexed
                        is_preferred = True
                    except ValueError:
                        rank = -1 # Not in preferences
                        is_preferred = False
                    writer.writerow([student_id, assigned_seminar, rank, is_preferred])
                else:
                    writer.writerow([student_id, 'UNASSIGNED', '', ''])
        logger.info(f"CSV割り当てレポート '{output_filename_assignment}' を正常に生成しました。")

        # 概要統計CSV
        with open(output_filename_summary, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Statistic', 'Value'])
            satisfaction_stats = _calculate_satisfaction_stats(students, final_assignment)
            for key, value in satisfaction_stats.items():
                writer.writerow([key, value])
            
            seminar_details = _get_seminar_assignment_details(seminars, final_assignment, seminar_capacities)
            writer.writerow([])
            writer.writerow(['Seminar ID', 'Capacity', 'Assigned Count', 'Remaining Capacity', 'Magnification'])
            for detail in seminar_details:
                writer.writerow([
                    detail['seminar_id'],
                    detail['capacity'],
                    detail['assigned_students_count'],
                    detail['remaining_capacity'],
                    detail['magnification']
                ])
        logger.info(f"CSV概要レポート '{output_filename_summary}' を正常に生成しました。")

    except Exception as e:
        logger.error(f"CSVレポートの生成中にエラーが発生しました: {e}")
        raise

