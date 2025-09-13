# report.py
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from datetime import datetime

def export_pdf(filename, company_name, buffett_score, metrics: dict):
    doc = SimpleDocTemplate(filename, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    styles = getSampleStyleSheet()
    content = []

    title_style = styles['Title']
    subtitle_style = styles['Heading2']
    normal = styles['BodyText']

    content.append(Paragraph("Company Report", title_style))
    content.append(Paragraph(f"Company: <b>{company_name}</b>", normal))
    content.append(Paragraph(f"Date: {datetime.today().strftime('%Y-%m-%d')}", normal))
    content.append(Spacer(1, 12))

    content.append(Paragraph(f"<b>Buffett Score:</b> {buffett_score:.1f}/100", subtitle_style))
    content.append(Spacer(1, 6))

    data = [["Metric", "Value"]] + [[k, str(v)] for k, v in metrics.items()]
    table = Table(data, colWidths=[200, 300])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#d9e6f2")),
        ('TEXTCOLOR',(0,0),(-1,0),colors.black),
        ('ALIGN',(0,0),(-1,-1),'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND',(0,1),(-1,-1),colors.whitesmoke),
        ('GRID', (0,0), (-1,-1), 0.25, colors.grey)
    ]))
    content.append(table)

    doc.build(content)
    return filename
