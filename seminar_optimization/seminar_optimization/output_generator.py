import os
from datetime import datetime
import logging
import pandas as pd
import csv # csvモジュールを明示的にインポート
import json # <-- 追加: jsonモジュールをインポート
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
# output_generator.py は seminar_optimization/seminar_optimization/seminar_optimization/output_generator.py にあると仮定
def register_japanese_font():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # プロジェクトルート (3階層上) を取得
    project_root = os.path.abspath(os.path.join(script_dir, '..', '..', '..'))
    # フォントディレクトリはプロジェクトルートの 'fonts' サブディレクトリ
    font_path = os.path.join(project_root, 'fonts', 'ipaexg.ttf')
    
    if not os.path.exists(font_path):
        logger.warning(f"output_generator: 日本語フォントファイルが見つかりません: {font_path}。PDFレポートの日本語表示に問題がある可能性があります。フォントファイルを '{os.path.dirname(font_path)}' ディレクトリに配置してください。")
        return False
    
    try:
        pdfmetrics.registerFont(TTFont('IPAexGothic', font_path))
        pdfmetrics.registerFontFamily('IPAexGothic', normal='IPAexGothic')
        logger.info(f"日本語フォント 'IPAexGothic' を登録しました: {font_path}")
        return True
    except Exception as e:
        logger.error(f"日本語フォントの登録中にエラーが発生しました: {e}", exc_info=True)
        return False

# フォント登録をモジュールロード時に一度だけ実行
JAPANESE_FONT_REGISTERED = register_japanese_font()


def _calculate_satisfaction_stats(students: List[Dict[str, Any]], final_assignment: Dict[str, str]) -> Dict[str, Any]:
    """
    学生の満足度に関する統計情報を計算する。
    """
    logger.debug("満足度統計を計算中...")
    total_students = len(students)
    assigned_students = 0
    first_choice_count = 0
    second_choice_count = 0
    third_choice_count = 0
    other_choice_count = 0
    unassigned_count = 0

    student_pref_map = {s['id']: s['preferences'] for s in students}

    for student_id, assigned_seminar_id in final_assignment.items():
        if assigned_seminar_id: # 割り当てられている場合
            assigned_students += 1
            prefs = student_pref_map.get(student_id, [])
            
            try:
                rank = prefs.index(assigned_seminar_id) + 1
                if rank == 1:
                    first_choice_count += 1
                elif rank == 2:
                    second_choice_count += 1
                elif rank == 3:
                    third_choice_count += 1
                else:
                    other_choice_count += 1
            except ValueError:
                # 希望リストにないセミナーに割り当てられた場合
                other_choice_count += 1
        else:
            unassigned_count += 1 # これは通常、final_assignmentに含まれないため、別途計算されるべきだが念のため

    # final_assignment に含まれない学生が未割り当て学生
    actual_unassigned_students = set(student_pref_map.keys()) - set(final_assignment.keys())
    unassigned_count = len(actual_unassigned_students)

    logger.debug("満足度統計の計算が完了しました。")
    return {
        "総学生数": total_students,
        "割り当て済み学生数": assigned_students,
        "未割り当て学生数": unassigned_count,
        "第1希望割り当て数": first_choice_count,
        "第2希望割り当て数": second_choice_count,
        "第3希望割り当て数": third_choice_count,
        "第4希望以降/希望外割り当て数": other_choice_count,
        "第1希望率": f"{first_choice_count / assigned_students * 100:.2f}%" if assigned_students > 0 else "0.00%",
        "第3希望以内率": f"{(first_choice_count + second_choice_count + third_choice_count) / assigned_students * 100:.2f}%" if assigned_students > 0 else "0.00%",
        "未割り当て率": f"{unassigned_count / total_students * 100:.2f}%" if total_students > 0 else "0.00%"
    }

def _get_seminar_assignment_details(seminars: List[Dict[str, Any]], final_assignment: Dict[str, str], seminar_capacities: Dict[str, int]) -> List[Dict[str, Any]]:
    """
    各セミナーの割り当て詳細（割り当て数、空き定員、倍率など）を計算する。
    """
    logger.debug("セミナー割り当て詳細を計算中...")
    seminar_details = []
    seminar_counts = {s_id: 0 for s_id in seminar_capacities.keys()}
    for student_id, seminar_id in final_assignment.items():
        seminar_counts[seminar_id] = seminar_counts.get(seminar_id, 0) + 1

    seminar_map = {s['id']: s for s in seminars}

    for seminar_id, capacity in seminar_capacities.items():
        assigned_students_count = seminar_counts.get(seminar_id, 0)
        remaining_capacity = capacity - assigned_students_count
        
        # 元のセミナーデータから倍率を取得、なければデフォルト0
        original_magnification = seminar_map.get(seminar_id, {}).get('magnification', 0)
        
        # 実際の倍率を計算 (割り当て数 / 定員)
        calculated_magnification = assigned_students_count / capacity if capacity > 0 else 0

        seminar_details.append({
            "seminar_id": seminar_id,
            "capacity": capacity,
            "assigned_students_count": assigned_students_count,
            "remaining_capacity": remaining_capacity,
            "magnification": f"{calculated_magnification:.2f}", # 計算された倍率
            "original_magnification": original_magnification # 元データにあった倍率
        })
    logger.debug("セミナー割り当て詳細の計算が完了しました。")
    return seminar_details


def save_pdf_report(config: Dict[str, Any], final_assignment: Dict[str, str], optimization_strategy: str, is_intermediate: bool = False):
    """
    最適化結果をPDFレポートとして保存する。
    """
    logger.info("PDFレポートの生成を開始します。")
    if not JAPANESE_FONT_REGISTERED:
        logger.error("日本語フォントが登録されていないため、PDFレポートの生成をスキップします。")
        return

    output_dir = config.get("output_directory", "output")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_type = "intermediate_" if is_intermediate else ""
    output_filename = os.path.join(output_dir, f"seminar_assignment_report_{report_type}{timestamp}.pdf")

    doc = SimpleDocTemplate(output_filename, pagesize=A4)
    styles = getSampleStyleSheet()
    
    # 日本語対応のスタイルを定義
    styles.add(ParagraphStyle(name='NormalJapanese',
                              parent=styles['Normal'],
                              fontName='IPAexGothic',
                              fontSize=10,
                              leading=12))
    styles.add(ParagraphStyle(name='Heading1Japanese',
                              parent=styles['h1'],
                              fontName='IPAexGothic',
                              fontSize=18,
                              leading=22,
                              spaceAfter=6))
    styles.add(ParagraphStyle(name='Heading2Japanese',
                              parent=styles['h2'],
                              fontName='IPAexGothic',
                              fontSize=14,
                              leading=18,
                              spaceAfter=6))

    story = []

    # タイトル
    story.append(Paragraph("セミナー割り当て最適化レポート", styles['Heading1Japanese']))
    story.append(Spacer(1, 0.5 * cm))

    # 概要
    story.append(Paragraph("概要", styles['Heading2Japanese']))
    story.append(Paragraph(f"<b>生成日時:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['NormalJapanese']))
    story.append(Paragraph(f"<b>最適化戦略:</b> {optimization_strategy}", styles['NormalJapanese']))
    story.append(Paragraph(f"<b>最終スコア:</b> {config.get('best_score', 'N/A'):.2f}", styles['NormalJapanese']))
    story.append(Paragraph(f"<b>未割り当て学生数:</b> {len(config.get('unassigned_students', []))}", styles['NormalJapanese']))
    story.append(Spacer(1, 0.5 * cm))

    # 学生の満足度統計
    story.append(Paragraph("学生の満足度統計", styles['Heading2Japanese']))
    students_data = config.get('students_data_for_report', [])
    satisfaction_stats = _calculate_satisfaction_stats(students_data, final_assignment)
    
    satisfaction_data = []
    for key, value in satisfaction_stats.items():
        satisfaction_data.append([Paragraph(key, styles['NormalJapanese']), Paragraph(str(value), styles['NormalJapanese'])])
    
    satisfaction_table = Table(satisfaction_data, colWidths=[6*cm, 6*cm])
    satisfaction_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'IPAexGothic'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    story.append(satisfaction_table)
    story.append(Spacer(1, 0.5 * cm))

    # セミナーごとの割り当て詳細
    story.append(Paragraph("セミナーごとの割り当て詳細", styles['Heading2Japanese']))
    seminars_data = config.get('seminars_data_for_report', [])
    seminar_capacities = {s['id']: s['capacity'] for s in seminars_data} # configから取得
    seminar_details = _get_seminar_assignment_details(seminars_data, final_assignment, seminar_capacities)

    seminar_table_data = [[
        Paragraph("セミナーID", styles['NormalJapanese']),
        Paragraph("定員", styles['NormalJapanese']),
        Paragraph("割り当て数", styles['NormalJapanese']),
        Paragraph("空き定員", styles['NormalJapanese']),
        Paragraph("倍率", styles['NormalJapanese'])
    ]]
    for detail in seminar_details:
        seminar_table_data.append([
            Paragraph(detail['seminar_id'], styles['NormalJapanese']),
            Paragraph(str(detail['capacity']), styles['NormalJapanese']),
            Paragraph(str(detail['assigned_students_count']), styles['NormalJapanese']),
            Paragraph(str(detail['remaining_capacity']), styles['NormalJapanese']),
            Paragraph(str(detail['magnification']), styles['NormalJapanese'])
        ])
    
    seminar_table = Table(seminar_table_data, colWidths=[3*cm, 2*cm, 2*cm, 2*cm, 2*cm])
    seminar_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, -1), 'IPAexGothic'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ]))
    story.append(seminar_table)
    story.append(Spacer(1, 0.5 * cm))

    # 個別割り当て (大量になる可能性があるので、PDFでは省略するか、別途CSVを推奨)
    # ここでは例として、未割り当て学生のみをリストアップ
    story.append(Paragraph("未割り当て学生", styles['Heading2Japanese']))
    unassigned_students = config.get('unassigned_students', [])
    if unassigned_students:
        unassigned_text = ", ".join(unassigned_students)
        story.append(Paragraph(unassigned_text, styles['NormalJapanese']))
    else:
        story.append(Paragraph("未割り当て学生はいません。", styles['NormalJapanese']))
    story.append(Spacer(1, 0.5 * cm))

    try:
        doc.build(story)
        logger.info(f"PDFレポートを正常に生成しました: {output_filename}")
    except Exception as e:
        logger.error(f"PDFレポートの生成中にエラーが発生しました: {e}", exc_info=True)


def save_csv_results(config: Dict[str, Any], final_assignment: Dict[str, str], optimization_strategy: str, is_intermediate: bool = False):
    """
    最適化結果をCSVファイルとして保存する。
    """
    logger.info("CSVレポートの生成を開始します。")
    output_dir = config.get("output_directory", "output")
    os.makedirs(output_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_type = "intermediate_" if is_intermediate else ""
    output_filename_assignment = os.path.join(output_dir, f"assignment_results_{report_type}{timestamp}.csv")
    output_filename_summary = os.path.join(output_dir, f"summary_results_{report_type}{timestamp}.csv")

    students_data = config.get('students_data_for_report', [])
    seminars_data = config.get('seminars_data_for_report', [])
    seminar_capacities = {s['id']: s['capacity'] for s in seminars_data} # configから取得

    try:
        # 個別割り当てCSV
        with open(output_filename_assignment, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Student ID', 'Assigned Seminar ID', 'Preference Rank', 'Original Preferences'])
            logger.debug(f"CSV割り当てレポート '{output_filename_assignment}' のヘッダーを書き込みました。")

            student_pref_map = {s['id']: s['preferences'] for s in students_data}

            for student_id in sorted(students_data, key=lambda s: s['id']): # 学生IDでソート
                s_id = student_id['id']
                assigned_seminar = final_assignment.get(s_id, 'UNASSIGNED')
                
                prefs = student_pref_map.get(s_id, [])
                preference_rank = ''
                if assigned_seminar != 'UNASSIGNED' and assigned_seminar in prefs:
                    preference_rank = prefs.index(assigned_seminar) + 1
                elif assigned_seminar != 'UNASSIGNED':
                    preference_rank = 'N/A (Not in preferences)'

                writer.writerow([s_id, assigned_seminar, preference_rank, json.dumps(prefs)]) # 希望リストをJSON文字列として保存
                logger.debug(f"学生 {s_id} の割り当てをCSVに書き込みました。")
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
        logger.error(f"CSVレポートの生成中にエラーが発生しました: {e}", exc_info=True)

