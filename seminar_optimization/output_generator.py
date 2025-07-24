import os
from datetime import datetime
import logging
import pandas as pd
import csv
import json
from typing import List, Dict, Any, Tuple, Optional

# ReportLab のインポート
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont # 日本語フォント対応のため

# ロギングは logger_config.py で一元的に設定されるため、ここではロガーの取得のみ
from seminar_optimization.logger_config import logger

def find_font_file(font_filename="ipaexg.ttf", search_root=None):
    """
    指定されたフォントファイルをプロジェクトルート以下から探索する。
    """
    if search_root is None:
        # 現在のファイル (__file__) の3階層上をプロジェクトルートとみなす
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # output_generator.py は seminar_optimization/seminar_optimization/output_generator.py にあるため、
        # プロジェクトルートは3階層上 (C:\Users\hiker\seminar_optimization)
        search_root = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))

    logger.info(f"'{font_filename}' を検索しています（ルート: {search_root}）...")
    for root, dirs, files in os.walk(search_root):
        if font_filename in files:
            font_path = os.path.join(root, font_filename)
            logger.info(f"フォントファイルが見つかりました: {font_path}")
            return font_path

    logger.warning(f"フォントファイル '{font_filename}' が見つかりませんでした。")
    return None

def register_japanese_font_auto():
    """
    IPAexGothic フォントを自動探索して登録する。
    """
    font_path = find_font_file("ipaexg.ttf")
    if not font_path:
        logger.warning("output_generator: 日本語フォントファイルが見つかりませんでした。PDFレポートの日本語表示に問題がある可能性があります。")
        return False

    try:
        pdfmetrics.registerFont(TTFont('IPAexGothic', font_path))
        pdfmetrics.registerFontFamily('IPAexGothic', normal='IPAexGothic')
        logger.info(f"日本語フォント 'IPAexGothic' を登録しました: {font_path}")
        return True
    except Exception as e:
        logger.error(f"日本語フォントの登録中にエラーが発生しました: {e}", exc_info=True)
        return False

# グローバルフラグ
JAPANESE_FONT_REGISTERED = register_japanese_font_auto()


def _calculate_satisfaction_stats(students_data: List[Dict[str, Any]], final_assignment: Dict[str, str]) -> Dict[str, Any]:
    """
    学生の希望満足度に関する統計を計算する。
    """
    logger.debug("満足度統計の計算を開始します。")
    total_students = len(students_data)
    assigned_students = len(final_assignment)
    unassigned_students_count = total_students - assigned_students

    first_choice_count = 0
    second_choice_count = 0
    third_choice_count = 0
    other_preference_count = 0
    assigned_to_unpreferred_count = 0

    student_preferences_map = {s['id']: s['preferences'] for s in students_data}

    for student_id, assigned_seminar_id in final_assignment.items():
        preferences = student_preferences_map.get(student_id, [])
        try:
            rank = preferences.index(assigned_seminar_id) + 1
            if rank == 1:
                first_choice_count += 1
            elif rank == 2:
                second_choice_count += 1
            elif rank == 3:
                third_choice_count += 1
            else:
                other_preference_count += 1
        except ValueError:
            assigned_to_unpreferred_count += 1 # 希望リストにないセミナーに割り当てられた場合

    logger.info(f"満足度統計: 第1希望: {first_choice_count}, 第2希望: {second_choice_count}, 第3希望: {third_choice_count}, その他希望: {other_preference_count}, 希望外: {assigned_to_unpreferred_count}, 未割り当て: {unassigned_students_count}")

    return {
        "Total Students": total_students,
        "Assigned Students": assigned_students,
        "Unassigned Students": unassigned_students_count,
        "Assigned to 1st Choice": first_choice_count,
        "Assigned to 2nd Choice": second_choice_count,
        "Assigned to 3rd Choice": third_choice_count,
        "Assigned to Other Preferred": other_preference_count,
        "Assigned to Unpreferred": assigned_to_unpreferred_count
    }

def _get_seminar_assignment_details(seminars_data: List[Dict[str, Any]], final_assignment: Dict[str, str], seminar_capacities: Dict[str, int]) -> List[Dict[str, Any]]:
    """
    各セミナーの割り当て詳細（割り当て数、残り定員など）を取得する。
    """
    logger.debug("セミナー割り当て詳細の取得を開始します。")
    seminar_counts: Dict[str, int] = {s['id']: 0 for s in seminars_data}
    seminar_magnifications: Dict[str, float] = {s['id']: s.get('magnification', 1.0) for s in seminars_data}

    for assigned_seminar_id in final_assignment.values():
        if assigned_seminar_id in seminar_counts:
            seminar_counts[assigned_seminar_id] += 1

    details = []
    for seminar in seminars_data:
        seminar_id = seminar['id']
        capacity = seminar_capacities.get(seminar_id, 0)
        assigned_count = seminar_counts.get(seminar_id, 0)
        remaining_capacity = capacity - assigned_count
        magnification = seminar_magnifications.get(seminar_id, 1.0) # 倍率を取得

        details.append({
            "seminar_id": seminar_id,
            "capacity": capacity,
            "assigned_students_count": assigned_count,
            "remaining_capacity": remaining_capacity,
            "magnification": magnification
        })
        logger.debug(f"セミナー {seminar_id}: 定員 {capacity}, 割り当て {assigned_count}, 残り {remaining_capacity}, 倍率 {magnification}")

    logger.info("セミナー割り当て詳細の取得が完了しました。")
    return details

def save_pdf_report(
    config: Dict[str, Any],
    final_assignment: Dict[str, str],
    optimization_strategy: str,
    is_intermediate: bool = False
):
    """
    最適化結果をPDFレポートとして保存する。
    """
    logger.info("PDFレポートの生成を開始します。")

    if not JAPANESE_FONT_REGISTERED:
        logger.warning("日本語フォントが登録されていないため、PDFレポートの日本語表示に問題がある可能性があります。")

    output_dir = config.get("output_directory", "results")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_type = "intermediate" if is_intermediate else "final"
    output_filename = os.path.join(output_dir, f"seminar_assignment_report_{optimization_strategy}_{report_type}_{timestamp}.pdf")

    doc = SimpleDocTemplate(output_filename, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    # 日本語スタイルを定義（フォントが登録されている場合）
    if JAPANESE_FONT_REGISTERED:
        styles.add(ParagraphStyle(name='JapaneseTitle', fontName='IPAexGothic', fontSize=18, leading=22, alignment=1))
        styles.add(ParagraphStyle(name='JapaneseHeading2', fontName='IPAexGothic', fontSize=14, leading=16, spaceAfter=6))
        styles.add(ParagraphStyle(name='JapaneseNormal', fontName='IPAexGothic', fontSize=10, leading=12))
        styles.add(ParagraphStyle(name='JapaneseCode', fontName='IPAexGothic', fontSize=9, leading=10, textColor=colors.darkgreen))
        normal_style = styles['JapaneseNormal']
        heading2_style = styles['JapaneseHeading2']
        title_style = styles['JapaneseTitle']
    else:
        logger.warning("日本語フォントが登録されていないため、デフォルトフォントを使用します。")
        normal_style = styles['Normal']
        heading2_style = styles['h2']
        title_style = styles['h1']

    # タイトル
    story.append(Paragraph(f"セミナー割り当て最適化レポート ({report_type.capitalize()})", title_style))
    story.append(Spacer(1, 0.5*cm))
    story.append(Paragraph(f"最適化戦略: {optimization_strategy}", normal_style))
    story.append(Paragraph(f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", normal_style))
    story.append(Spacer(1, 1*cm))

    # 最適化設定の概要
    story.append(Paragraph("最適化設定の概要", heading2_style))
    config_summary_data = []
    # レポートに含める主要な設定項目を抽出
    relevant_config_keys = [
        "num_seminars", "min_capacity", "max_capacity", "num_students",
        "min_preferences", "max_preferences", "preference_distribution",
        "optimization_strategy", "ga_population_size", "ga_generations",
        "ilp_time_limit", "cp_time_limit", "multilevel_clusters",
        "greedy_ls_iterations", "local_search_iterations",
        "early_stop_no_improvement_limit", "initial_temperature", "cooling_rate",
        "q_boost_probability", "num_preferences_to_consider",
        "max_adaptive_iterations", "strategy_time_limit", "random_seed"
    ]
    for key in relevant_config_keys:
        if key in config:
            config_summary_data.append([key, str(config[key])])
    
    # スコア重みも追加
    if "score_weights" in config:
        for weight_key, weight_value in config["score_weights"].items():
            config_summary_data.append([f"score_weights_{weight_key}", str(weight_value)])

    config_table = Table(config_summary_data, colWidths=[6*cm, 6*cm])
    config_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.lightgrey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.black),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,-1), 'IPAexGothic' if JAPANESE_FONT_REGISTERED else 'Helvetica'),
        ('BOTTOMPADDING', (0,0), (-1,0), 6),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black)
    ]))
    story.append(config_table)
    story.append(Spacer(1, 1*cm))


    # 概要統計
    story.append(Paragraph("概要統計", heading2_style))
    students_data = config.get('students_data_for_report', [])
    seminars_data = config.get('seminars_data_for_report', [])
    seminar_capacities_for_report = {s['id']: s['capacity'] for s in seminars_data}

    satisfaction_stats = _calculate_satisfaction_stats(students_data, final_assignment)
    stats_data = [[key, str(value)] for key, value in satisfaction_stats.items()]
    stats_table = Table(stats_data, colWidths=[6*cm, 3*cm])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'IPAexGothic' if JAPANESE_FONT_REGISTERED else 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    story.append(stats_table)
    story.append(Spacer(1, 1*cm))

    # セミナー割り当て詳細
    story.append(Paragraph("セミナー割り当て詳細", heading2_style))
    seminar_details = _get_seminar_assignment_details(seminars_data, final_assignment, seminar_capacities_for_report)
    seminar_table_data = [["セミナーID", "定員", "割り当て数", "残り定員", "倍率"]]
    for detail in seminar_details:
        seminar_table_data.append([
            detail['seminar_id'],
            detail['capacity'],
            detail['assigned_students_count'],
            detail['remaining_capacity'],
            detail['magnification']
        ])
    seminar_table = Table(seminar_table_data, colWidths=[3*cm, 2*cm, 2*cm, 2*cm, 2*cm])
    seminar_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'IPAexGothic' if JAPANESE_FONT_REGISTERED else 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    story.append(seminar_table)
    story.append(Spacer(1, 1*cm))

    # 学生ごとの割り当て
    story.append(Paragraph("学生ごとの割り当て", heading2_style))
    student_assignment_data = [["学生ID", "割り当てセミナー", "希望順位"]]
    student_preferences_map = {s['id']: s['preferences'] for s in students_data}

    for student_id in sorted(final_assignment.keys()): # 学生IDでソート
        assigned_seminar_id = final_assignment[student_id]
        preferences = student_preferences_map.get(student_id, [])
        try:
            rank = preferences.index(assigned_seminar_id) + 1
            rank_str = f"第{rank}希望"
        except ValueError:
            rank_str = "希望外"
        student_assignment_data.append([student_id, assigned_seminar_id, rank_str])

    # 未割り当て学生の追加
    all_student_ids = {s['id'] for s in students_data}
    assigned_student_ids = set(final_assignment.keys())
    unassigned_students_list = sorted(list(all_student_ids - assigned_student_ids))
    if unassigned_students_list:
        # 未割り当て学生のリストを別のセクションとして追加
        story.append(Spacer(1, 1*cm))
        story.append(Paragraph("未割り当て学生リスト", heading2_style))
        unassigned_table_data = [["学生ID"]]
        for student_id in unassigned_students_list:
            unassigned_table_data.append([student_id])
        
        unassigned_table = Table(unassigned_table_data, colWidths=[3*cm])
        unassigned_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.red),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'IPAexGothic' if JAPANESE_FONT_REGISTERED else 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-1), colors.lightcoral),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        story.append(unassigned_table)
        story.append(Spacer(1, 1*cm)) # テーブルの後にスペースを追加

    # 学生割り当てテーブル
    student_table = Table(student_assignment_data, colWidths=[3*cm, 3*cm, 3*cm])
    student_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'IPAexGothic' if JAPANESE_FONT_REGISTERED else 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.lightcyan),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    story.append(student_table)

    try:
        doc.build(story)
        logger.info(f"PDFレポート '{output_filename}' を正常に生成しました。")
    except Exception as e:
        logger.error(f"PDFレポートの生成中にエラーが発生しました: {e}", exc_info=True)
        logger.error("PDFレポートの生成に失敗しました。ReportLabのインストール、フォントパス、またはデータ形式を確認してください。")


def save_csv_results(
    config: Dict[str, Any],
    final_assignment: Dict[str, str],
    optimization_strategy: str,
    is_intermediate: bool = False
):
    """
    最適化結果をCSVファイルとして保存する。
    """
    logger.info("CSVレポートの生成を開始します。")

    output_dir = config.get("output_directory", "results")
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_type = "intermediate" if is_intermediate else "final"

    output_filename_assignment = os.path.join(output_dir, f"seminar_assignment_{optimization_strategy}_{report_type}_{timestamp}.csv")
    output_filename_summary = os.path.join(output_dir, f"seminar_summary_{optimization_strategy}_{report_type}_{timestamp}.csv")

    students_data = config.get('students_data_for_report', [])
    seminars_data = config.get('seminars_data_for_report', [])
    seminar_capacities_for_report = {s['id']: s['capacity'] for s in seminars_data}

    # 学生割り当てCSV
    with open(output_filename_assignment, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['student_id', 'assigned_seminar_id', 'preferred_rank'])
        logger.debug(f"CSV割り当てレポート '{output_filename_assignment}' のヘッダーを書き込みました。")

        student_preferences_map = {s['id']: s['preferences'] for s in students_data}

        for student_id in sorted(final_assignment.keys()):
            assigned_seminar_id = final_assignment[student_id]
            preferences = student_preferences_map.get(student_id, [])
            try:
                rank = preferences.index(assigned_seminar_id) + 1
                rank_str = str(rank)
            except ValueError:
                rank_str = "unpreferred" # 希望リストにないセミナーに割り当てられた場合
            writer.writerow([student_id, assigned_seminar_id, rank_str])
        
        # 未割り当て学生の追加
        all_student_ids = {s['id'] for s in students_data}
        assigned_student_ids = set(final_assignment.keys())
        unassigned_students_list = sorted(list(all_student_ids - assigned_student_ids))
        for student_id in unassigned_students_list:
            writer.writerow([student_id, "unassigned", "N/A"])

    logger.info(f"CSV割り当てレポート '{output_filename_assignment}' を正常に生成しました。")

    # 概要統計CSV
    with open(output_filename_summary, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Statistic', 'Value'])
        logger.debug(f"CSV概要レポート '{output_filename_summary}' のヘッダーを書き込みました。")

        satisfaction_stats = _calculate_satisfaction_stats(students_data, final_assignment)
        for key, value in satisfaction_stats.items():
            writer.writerow([key, value])
            logger.debug(f"概要統計: {key} = {value}")
        
        writer.writerow([]) # 空行
        writer.writerow(['Seminar ID', 'Capacity', 'Assigned Count', 'Remaining Capacity', 'Magnification'])
        logger.debug("概要統計: セミナー詳細のヘッダーを書き込みました。")

        seminar_details = _get_seminar_assignment_details(seminars_data, final_assignment, seminar_capacities_for_report)
        for detail in seminar_details:
            writer.writerow([
                detail['seminar_id'],
                detail['capacity'],
                detail['assigned_students_count'],
                detail['remaining_capacity'],
                detail['magnification']
            ])
            logger.debug(f"概要統計: セミナー {detail['seminar_id']} 詳細を書き込みました。")
    logger.info(f"CSV概要レポート '{output_filename_summary}' を正常に生成しました。")

