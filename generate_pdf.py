from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

# PDF生成
doc = SimpleDocTemplate("seminar_assignments.pdf", pagesize=letter)
styles = getSampleStyleSheet()
elements = []

# タイトル
elements.append(Paragraph("セミナー割り当て結果（最高得点パターン）", styles['Title']))
elements.append(Spacer(1, 12))

# 人数データ
data = [['セミナー', '人数', '得点']] + [
    ['a', 10, 27], ['b', 7, 21], ['c', 8, 23], ['d', 7, 21], ['e', 5, 15],
    ['f', 5, 14], ['g', 5, 15], ['h', 10, 29], ['i', 5, 15], ['j', 5, 15],
    ['k', 5, 15], ['l', 5, 15], ['m', 10, 21], ['n', 5, 14], ['o', 10, 15],
    ['p', 5, 14], ['q', 5, 3]
]
table = Table(data)
table.setStyle(TableStyle([
    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ('FONTSIZE', (0, 0), (-1, 0), 14),
    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
    ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ('GRID', (0, 0), (-1, -1), 1, colors.black)
]))
elements.append(table)
elements.append(Spacer(1, 12))

# 総得点
elements.append(Paragraph(f"総得点: 289", styles['Normal']))

# PDFビルド
doc.build(elements)