import os
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import logging
import pandas as pd

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm

from models import Config, Student # ConfigとStudentモデルをインポート
from evaluation import calculate_satisfaction_stats # 満足度統計計算関数をインポート

logger = logging.getLogger(__name__)

def generate_pdf_report(
    config: Config,
    target_sizes: Dict[str, int],
    final_score: float, 
    final_assignments: Dict[str, List[Tuple[int, float]]], 
    pattern_id: int,
    students_for_stats: List[Student], # 学生リストを明示的に受け取る
    is_intermediate: bool = False,
    iteration_count: Optional[int] = None
):
    """
    最適化されたセミナー割り当て結果をPDFレポートとして生成します。
    """
    output_filename = config.pdf_file
    if is_intermediate:
        # 中間レポートのファイル名を生成
        output_filename = os.path.join(config.output_dir, f"intermediate_report_pattern_{pattern_id}_iter_{iteration_count}.pdf")
    
    doc = SimpleDocTemplate(output_filename, pagesize=A4)
    styles = getSampleStyleSheet()
    
    # 日本語フォントスタイルを定義します
    # main.pyで'IPAexGothic'が登録されていることを前提とします
    styles.add(ParagraphStyle(name='JapaneseNormal',
                              fontName='IPAexGothic',
                              fontSize=10,
                              leading=12))
    styles.add(ParagraphStyle(name='JapaneseHeading1',
                              fontName='IPAexGothic',
                              fontSize=14,
                              leading=16,
                              spaceAfter=12,
                              alignment=1)) # 中央揃え
    styles.add(ParagraphStyle(name='JapaneseHeading2',
                              fontName='IPAexGothic',
                              fontSize=12,
                              leading=14,
                              spaceAfter=8))

    story = []

    # タイトル
    report_title = "セミナー割り当て最適化レポート"
    if is_intermediate:
        report_title = f"中間レポート (パターンID: {pattern_id}, 試行回数: {iteration_count})"
    story.append(Paragraph(report_title, styles['JapaneseHeading1']))
    story.append(Spacer(1, 0.5*cm))

    # 基本情報
    story.append(Paragraph(f"生成日時: {datetime.now().strftime('%Y年%m月%d日 %H時%M分%S秒')}", styles['JapaneseNormal']))
    story.append(Paragraph(f"総学生数: {config.num_students}人", styles['JapaneseNormal']))
    story.append(Paragraph(f"総セミナー数: {len(config.seminars)}", styles['JapaneseNormal']))
    story.append(Paragraph(f"最適化戦略: {config.optimization_strategy}", styles['JapaneseNormal']))
    story.append(Spacer(1, 0.5*cm))

    # 最終スコア
    story.append(Paragraph(f"最終最適化スコア: <font color='red'><b>{final_score:.2f}</b></font>", styles['JapaneseHeading2']))
    story.append(Spacer(1, 0.5*cm))

    # 各セミナーの割り当て詳細
    story.append(Paragraph("各セミナーの割り当て詳細", styles['JapaneseHeading2']))
    
    seminar_assignment_data = [['セミナー名', '目標定員', '割り当て学生数', '学生ID']]
    for sem_name in config.seminars:
        assigned_students_list = sorted([s_id for s_id, _ in final_assignments.get(sem_name, [])])
        assigned_count = len(assigned_students_list)
        target_size = target_sizes.get(sem_name, 0)
        seminar_assignment_data.append([
            sem_name,
            str(target_size),
            str(assigned_count),
            ", ".join(map(str, assigned_students_list))
        ])

    table_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'IPAexGothic'),
        ('FONTNAME', (0,1), (-1,-1), 'IPAexGothic'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
    ])
    
    # テーブルの幅をページ幅に合わせます
    table_width = doc.width
    col_widths = [table_width * 0.15, table_width * 0.15, table_width * 0.15, table_width * 0.55]
    
    seminar_table = Table(seminar_assignment_data, colWidths=col_widths)
    seminar_table.setStyle(table_style)
    story.append(seminar_table)
    story.append(Spacer(1, 1*cm))

    # 学生の満足度統計
    story.append(Paragraph("学生の満足度統計", styles['JapaneseHeading2']))
    
    # calculate_satisfaction_stats 関数に実際の学生リストを渡す
    satisfaction_stats = calculate_satisfaction_stats(config, students_for_stats, final_assignments)

    satisfaction_data = [
        ['項目', '学生数', '割合 (%)'],
        ['第1希望に割り当て', satisfaction_stats['1st_choice'], f"{satisfaction_stats['1st_choice']/config.num_students*100:.2f}" if config.num_students > 0 else "0.00"],
        ['第2希望に割り当て', satisfaction_stats['2nd_choice'], f"{satisfaction_stats['2nd_choice']/config.num_students*100:.2f}" if config.num_students > 0 else "0.00"],
        ['第3希望に割り当て', satisfaction_stats['3rd_choice'], f"{satisfaction_stats['3rd_choice']/config.num_students*100:.2f}" if config.num_students > 0 else "0.00"],
        ['3位以降の希望に割り当て', satisfaction_stats['other_preference'], f"{satisfaction_stats['other_preference']/config.num_students*100:.2f}" if config.num_students > 0 else "0.00"],
        ['希望外に割り当て', satisfaction_stats['no_preference_met'], f"{satisfaction_stats['no_preference_met']/config.num_students*100:.2f}" if config.num_students > 0 else "0.00"],
        ['未割り当て', satisfaction_stats['unassigned'], f"{satisfaction_stats['unassigned']/config.num_students*100:.2f}" if config.num_students > 0 else "0.00"],
        ['合計', config.num_students, '100.00' if config.num_students > 0 else "0.00"]
    ]

    satisfaction_table_style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'IPAexGothic'),
        ('FONTNAME', (0,1), (-1,-1), 'IPAexGothic'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.lightgrey),
        ('GRID', (0,0), (-1,-1), 1, colors.black),
        ('BOX', (0,0), (-1,-1), 1, colors.black),
    ])
    
    satisfaction_table_col_widths = [table_width * 0.3, table_width * 0.2, table_width * 0.2]
    satisfaction_table = Table(satisfaction_data, colWidths=satisfaction_table_col_widths)
    satisfaction_table.setStyle(satisfaction_table_style)
    story.append(satisfaction_table)
    story.append(Spacer(1, 1*cm))

    try:
        doc.build(story)
        logger.info(f"PDFレポート '{output_filename}' を正常に生成しました。")
    except Exception as e:
        logger.error(f"PDFレポートのビルド中にエラーが発生しました: {e}")
        raise

def save_csv_results(
    config: Config,
    final_assignments: Dict[str, List[Tuple[int, float]]],
    pattern_id: int,
    is_intermediate: bool = False,
    iteration_count: Optional[int] = None
):
    """
    最終割り当て結果をCSVファイルとして保存します。
    """
    output_filename = os.path.join(config.output_dir, f"seminar_assignments_pattern_{pattern_id}.csv")
    if is_intermediate:
        output_filename = os.path.join(config.output_dir, f"intermediate_assignments_pattern_{pattern_id}_iter_{iteration_count}.csv")

    data = []
    for sem_name, assigned_list in final_assignments.items():
        for student_id, score in assigned_list:
            data.append({'student_id': student_id, 'assigned_seminar': sem_name, 'assignment_score': score})
    
    df = pd.DataFrame(data)
    df.to_csv(output_filename, index=False, encoding='utf-8')
    logger.info(f"CSV結果を '{output_filename}' に保存しました。")

