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
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont # 日本語フォント対応のため

# ロギングは logger_config.py で一元的に設定されるため、ここではロガーの取得のみ
from seminar_optimization.seminar_optimization.logger_config import logger # <-- 修正: 相対インポート

# 日本語フォントの登録 (IPAexGothicを仮定)
# プロジェクトのルートディレクトリからの相対パスでフォントを探す
# output_generator.py は seminar_optimization/seminar_optimization/output_generator.py にあると仮定
# プロジェクトルートは一つ上のディレクトリのさらに一つ上のディレクトリ
def register_japanese_font():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # プロジェクトのルートディレクトリを特定
    # seminar_optimization/seminar_optimization/output_generator.py から見て ../../fonts/ipaexg.ttf
    project_root = os.path.abspath(os.path.join(script_dir, '..', '..'))
    font_path = os.path.join(project_root, 'fonts', 'ipaexg.ttf')
    
    try:
        if os.path.exists(font_path):
            pdfmetrics.registerFont(TTFont('IPAexGothic', font_path))
            logger.info(f"output_generator: 日本語フォント 'IPAexGothic' を登録しました。パス: {font_path}")
        else:
            logger.warning(f"output_generator: 日本語フォントファイルが見つかりません: {font_path}。PDFレポートの日本語表示に問題がある可能性があります。フォントファイルを '{os.path.join(project_root, 'fonts')}' ディレクトリに配置してください。")
    except Exception as e:
        logger.error(f"output_generator: 日本語フォントの登録中にエラーが発生しました: {e}", exc_info=True)

register_japanese_font()


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
    logger.debug("_calculate_satisfaction_stats: 学生満足度統計の計算を開始シマス。")
    student_preferences_map = {s['id']: s['preferences'] for s in students}

    stats = {
        '1st_choice': 0,
        '2nd_choice': 0,
        '3rd_choice': 0,
        'other_preference': 0,
        'no_preference_met': 0,
        'unassigned': 0,
        'total_students': len(students)
    }

    for student_id in student_preferences_map.keys():
        assigned_seminar = assignment.get(student_id)
        if assigned_seminar is None:
            stats['unassigned'] += 1
            logger.debug(f"学生 {student_id}: 未割り当て。")
            continue

        preferences = student_preferences_map.get(student_id, [])
        try:
            rank = preferences.index(assigned_seminar) + 1
            if rank == 1:
                stats['1st_choice'] += 1
                logger.debug(f"学生 {student_id}: 第1希望 ({assigned_seminar}) に割り当て。")
            elif rank == 2:
                stats['2nd_choice'] += 1
                logger.debug(f"学生 {student_id}: 第2希望 ({assigned_seminar}) に割り当て。")
            elif rank == 3:
                stats['3rd_choice'] += 1
                logger.debug(f"学生 {student_id}: 第3希望 ({assigned_seminar}) に割り当て。")
            else:
                stats['other_preference'] += 1
                logger.debug(f"学生 {student_id}: 第{rank}希望 ({assigned_seminar}) に割り当て。")
        except ValueError:
            stats['no_preference_met'] += 1
            logger.debug(f"学生 {student_id}: 希望リスト外のセミナー ({assigned_seminar}) に割り当て。")
    
    logger.info(f"_calculate_satisfaction_stats: 学生満足度統計計算完了。統計: {stats}")
    return stats

def _get_seminar_assignment_details(
    seminars: List[Dict[str, Any]], 
    assignment: Dict[str, str], 
    seminar_capacities: Dict[str, int]
    ) -> List[Dict[str, Any]]:
    """
    各セミナーの割り当て詳細（割り当て数、残り定員、倍率など）を計算する。
    """
    logger.debug("_get_seminar_assignment_details: セミナー割り当て詳細の計算を開始シマス。")
    seminar_details: List[Dict[str, Any]] = []
    seminar_counts: Dict[str, int] = {s_id: 0 for s_id in seminar_capacities.keys()}

    for assigned_seminar_id in assignment.values():
        if assigned_seminar_id in seminar_counts:
            seminar_counts[assigned_seminar_id] += 1
    
    seminar_magnifications = {s['id']: s.get('magnification', 1.0) for s in seminars}

    for seminar in seminars:
        seminar_id = seminar['id']
        capacity = seminar['capacity']
        assigned_count = seminar_counts.get(seminar_id, 0)
        remaining_capacity = capacity - assigned_count
        magnification = seminar_magnifications.get(seminar_id, 1.0)

        seminar_details.append({
            'seminar_id': seminar_id,
            'capacity': capacity,
            'assigned_students_count': assigned_count,
            'remaining_capacity': remaining_capacity,
            'magnification': magnification
        })
        logger.debug(f"セミナー {seminar_id}: 割り当て数={assigned_count}, 残り定員={remaining_capacity}, 倍率={magnification}")

    logger.info("_get_seminar_assignment_details: セミナー割り当て詳細計算完了。")
    return seminar_details

def save_pdf_report(
    config: Dict[str, Any],
    final_assignment: Dict[str, str],
    optimization_strategy: str,
    is_intermediate: bool = False
):
    """
    最適化結果をPDFレポートとして保存する。
    """
    logger.info("save_pdf_report: PDFレポートの生成を開始シマス。")
    try:
        output_dir = config.get("output_directory", "results")
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_type = "intermediate" if is_intermediate else "final"
        output_filename = os.path.join(output_dir, f"seminar_assignment_report_{optimization_strategy}_{report_type}_{timestamp}.pdf")

        doc = SimpleDocTemplate(output_filename, pagesize=A4,
                                rightMargin=cm, leftMargin=cm,
                                topMargin=cm, bottomMargin=cm)
        styles = getSampleStyleSheet()

        # 日本語対応のスタイルを定義
        # Normalスタイルをベースにフォントを設定
        styles.add(ParagraphStyle(name='JapaneseNormal',
                                  parent=styles['Normal'],
                                  fontName='IPAexGothic',
                                  fontSize=10,
                                  leading=12))
        styles.add(ParagraphStyle(name='JapaneseHeading1',
                                  parent=styles['h1'],
                                  fontName='IPAexGothic',
                                  fontSize=18,
                                  leading=22,
                                  spaceAfter=6))
        styles.add(ParagraphStyle(name='JapaneseHeading2',
                                  parent=styles['h2'],
                                  fontName='IPAexGothic',
                                  fontSize=14,
                                  leading=18,
                                  spaceAfter=6))
        logger.debug("save_pdf_report: 日本語対応のPDFスタイルを定義しました。")

        story = []

        # タイトル
        story.append(Paragraph("セミナー割り当て最適化レポート", styles['JapaneseHeading1']))
        story.append(Spacer(1, 0.5*cm))

        # 概要
        story.append(Paragraph("概要", styles['JapaneseHeading2']))
        story.append(Paragraph(f"<b>生成日時:</b> {datetime.now().strftime('%Y年%m月%d日 %H時%M分%S秒')}", styles['JapaneseNormal']))
        story.append(Paragraph(f"<b>最適化戦略:</b> {optimization_strategy}", styles['JapaneseNormal']))
        story.append(Spacer(1, 0.2*cm))
        logger.debug("save_pdf_report: レポート概要を追加しました。")

        # 学生の満足度統計
        students_data = config.get('students_data_for_report', [])
        seminars_data = config.get('seminars_data_for_report', [])
        seminar_capacities = {s['id']: s['capacity'] for s in seminars_data}
        student_preferences_map = {s['id']: s['preferences'] for s in students_data}


        satisfaction_stats = _calculate_satisfaction_stats(students_data, final_assignment)
        story.append(Paragraph("学生の満足度統計", styles['JapaneseHeading2']))
        satisfaction_data = [
            ['項目', '人数'],
            ['第1希望に割り当て', satisfaction_stats['1st_choice']],
            ['第2希望に割り当て', satisfaction_stats['2nd_choice']],
            ['第3希望に割り当て', satisfaction_stats['3rd_choice']],
            ['その他の希望に割り当て', satisfaction_stats['other_preference']],
            ['希望外に割り当て', satisfaction_stats['no_preference_met']],
            ['未割り当て', satisfaction_stats['unassigned']],
            ['総学生数', satisfaction_stats['total_students']]
        ]
        satisfaction_table = Table(satisfaction_data, colWidths=[4*cm, 3*cm])
        satisfaction_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'IPAexGothic'),
            ('FONTNAME', (0,1), (-1,-1), 'IPAexGothic'),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-1), colors.beige),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        story.append(satisfaction_table)
        story.append(Spacer(1, 0.5*cm))
        logger.debug("save_pdf_report: 学生満足度統計テーブルを追加しました。")

        # セミナー割り当て詳細
        seminar_details = _get_seminar_assignment_details(seminars_data, final_assignment, seminar_capacities)
        story.append(Paragraph("セミナー割り当て詳細", styles['JapaneseHeading2']))
        seminar_table_data = [
            ['セミナーID', '定員', '割り当て数', '残り定員', '倍率']
        ]
        for detail in seminar_details:
            seminar_table_data.append([
                detail['seminar_id'],
                detail['capacity'],
                detail['assigned_students_count'],
                detail['remaining_capacity'],
                f"{detail['magnification']:.2f}"
            ])
        
        seminar_table = Table(seminar_table_data, colWidths=[3*cm, 2*cm, 2*cm, 2*cm, 2*cm])
        seminar_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey),
            ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('FONTNAME', (0,0), (-1,0), 'IPAexGothic'),
            ('FONTNAME', (0,1), (-1,-1), 'IPAexGothic'),
            ('BOTTOMPADDING', (0,0), (-1,0), 12),
            ('BACKGROUND', (0,1), (-1,-1), colors.lightgrey),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ]))
        story.append(seminar_table)
        story.append(Spacer(1, 0.5*cm))
        logger.debug("save_pdf_report: セミナー割り当て詳細テーブルを追加しました。")

        # 個別割り当てリスト（オプション、データ量が多い場合は省略）
        if len(final_assignment) <= 200: # 例: 200人以下の場合のみ詳細リストを生成
            story.append(Paragraph("個別学生割り当てリスト", styles['JapaneseHeading2']))
            assignment_list_data = [['学生ID', '割り当てセミナー', '希望順位']]
            
            # ソートして表示をわかりやすく
            sorted_assignments = sorted(final_assignment.items(), key=lambda item: item[0])

            for student_id, assigned_seminar in sorted_assignments:
                preferences = student_preferences_map.get(student_id, [])
                rank_str = "未割り当て"
                if assigned_seminar:
                    try:
                        rank = preferences.index(assigned_seminar) + 1
                        rank_str = f"第{rank}希望"
                    except ValueError:
                        rank_str = "希望外"
                assignment_list_data.append([student_id, assigned_seminar if assigned_seminar else "UNASSIGNED", rank_str])

            assignment_list_table = Table(assignment_list_data, colWidths=[3*cm, 3*cm, 3*cm])
            assignment_list_table.setStyle(TableStyle([
                ('BACKGROUND', (0,0), (-1,0), colors.grey),
                ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('FONTNAME', (0,0), (-1,0), 'IPAexGothic'),
                ('FONTNAME', (0,1), (-1,-1), 'IPAexGothic'),
                ('BOTTOMPADDING', (0,0), (-1,0), 12),
                ('BACKGROUND', (0,1), (-1,-1), colors.beige),
                ('GRID', (0,0), (-1,-1), 1, colors.black)
            ]))
            story.append(assignment_list_table)
            story.append(Spacer(1, 0.5*cm))
            logger.debug("save_pdf_report: 個別学生割り当てリストテーブルを追加しました。")
        else:
            story.append(Paragraph("※学生数が多いため、個別学生割り当てリストは省略されました。", styles['JapaneseNormal']))
            logger.info("save_pdf_report: 学生数が多いため、個別割り当てリストは省略されました。")


        doc.build(story)
        logger.info(f"save_pdf_report: PDFレポートを正常に生成しました: {output_filename}")

    except Exception as e:
        logger.error(f"save_pdf_report: PDFレポートの生成中にエラーが発生しました: {e}", exc_info=True)
        raise

def save_csv_results(
    config: Dict[str, Any],
    final_assignment: Dict[str, str],
    optimization_strategy: str,
    is_intermediate: bool = False
):
    """
    最適化結果をCSVファイルとして保存する。
    """
    logger.info("save_csv_results: CSVレポートの生成を開始シマス。")
    try:
        output_dir = config.get("output_directory", "results")
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_type = "intermediate" if is_intermediate else "final"

        output_filename_assignment = os.path.join(output_dir, f"assignment_results_{optimization_strategy}_{report_type}_{timestamp}.csv")
        output_filename_summary = os.path.join(output_dir, f"summary_stats_{optimization_strategy}_{report_type}_{timestamp}.csv")

        students_data = config.get('students_data_for_report', [])
        seminars_data = config.get('seminars_data_for_report', [])
        seminar_capacities = {s['id']: s['capacity'] for s in seminars_data}
        student_preferences_map = {s['id']: s['preferences'] for s in students_data}

        # 割り当て結果CSV
        with open(output_filename_assignment, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Student ID', 'Assigned Seminar', 'Preference Rank', 'Is Preferred Choice'])
            logger.debug(f"CSV割り当てレポート '{output_filename_assignment}' のヘッダーを書き込みました。")
            
            for student_id in student_preferences_map.keys():
                assigned_seminar = final_assignment.get(student_id)
                if assigned_seminar:
                    preferences = student_preferences_map.get(student_id, [])
                    rank = ''
                    is_preferred = False
                    try:
                        rank_idx = preferences.index(assigned_seminar) + 1
                        rank = f"第{rank_idx}希望"
                        is_preferred = True # 希望リストにあればTrue
                        logger.debug(f"学生 {student_id}: {assigned_seminar} (希望順位: {rank_idx})")
                    except ValueError:
                        rank = "希望外"
                        is_preferred = False
                    writer.writerow([student_id, assigned_seminar, rank, is_preferred])
                else:
                    writer.writerow([student_id, 'UNASSIGNED', '', ''])
                    logger.debug(f"学生 {student_id}: 未割り当て。")
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

            seminar_details = _get_seminar_assignment_details(seminars_data, final_assignment, seminar_capacities)
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

    except Exception as e:
        logger.error(f"save_csv_results: CSVレポートの生成中にエラーが発生しました: {e}", exc_info=True)
        raise
