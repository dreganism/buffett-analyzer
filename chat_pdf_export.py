# chat_pdf_export.py
# PDF export functionality for ChatGPT conversations
# Extends the existing report.py functionality

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.lib import colors
from datetime import datetime
from typing import List, Dict
import os

def export_chat_to_pdf(filename: str, 
                      ticker: str, 
                      chat_history: List[Dict], 
                      company_data: Dict) -> str:
    """
    Export ChatGPT conversation to PDF with company context.
    
    Args:
        filename: Output PDF filename
        ticker: Company ticker symbol
        chat_history: List of chat messages
        company_data: Company financial data for context
    
    Returns:
        str: Path to the created PDF file
    """
    
    # Ensure filename ends with .pdf
    if not filename.endswith('.pdf'):
        filename += '.pdf'
    
    doc = SimpleDocTemplate(filename, pagesize=letter, 
                          rightMargin=72, leftMargin=72, 
                          topMargin=72, bottomMargin=18)
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Custom styles for chat
    user_style = ParagraphStyle(
        'UserMessage',
        parent=styles['Normal'],
        backgroundColor=HexColor('#E3F2FD'),
        borderColor=HexColor('#1976D2'),
        borderWidth=1,
        borderPadding=8,
        leftIndent=20,
        rightIndent=10,
        spaceAfter=12
    )
    
    assistant_style = ParagraphStyle(
        'AssistantMessage', 
        parent=styles['Normal'],
        backgroundColor=HexColor('#F5F5F5'),
        borderColor=HexColor('#757575'),
        borderWidth=1,
        borderPadding=8,
        leftIndent=10,
        rightIndent=20,
        spaceAfter=12
    )
    
    timestamp_style = ParagraphStyle(
        'Timestamp',
        parent=styles['Normal'],
        fontSize=8,
        textColor=HexColor('#666666'),
        alignment=1  # Right align
    )
    
    # Build the document content
    story = []
    
    # Title page
    title = Paragraph(f"ChatGPT Financial Analysis", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))
    
    subtitle = Paragraph(f"Company: {ticker}", styles['Heading2'])
    story.append(subtitle)
    story.append(Spacer(1, 12))
    
    export_date = Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", 
                           styles['Normal'])
    story.append(export_date)
    story.append(Spacer(1, 24))
    
    # Company context section
    story.append(Paragraph("Company Financial Summary", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    context_text = f"""
    <b>Net Income:</b> {company_data.get('net_income', 'N/A')}<br/>
    <b>Sales:</b> {company_data.get('sales', 'N/A')}<br/>
    <b>Owner Earnings:</b> {company_data.get('owner_earnings', 'N/A')}<br/>
    <b>Look-Through Earnings:</b> {company_data.get('look_through_earnings', 'N/A')}<br/>
    <b>Altman Z-Score:</b> {company_data.get('altman_z', 'N/A')}<br/>
    <b>Capital Preservation Score:</b> {company_data.get('capital_preservation', 'N/A')}<br/>
    <b>Buffett Score:</b> {company_data.get('buffett_score', 'N/A')}
    """
    
    context_para = Paragraph(context_text, styles['Normal'])
    story.append(context_para)
    story.append(Spacer(1, 24))
    
    # Chat conversation section
    if chat_history:
        story.append(Paragraph("ChatGPT Analysis Conversation", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        for msg in chat_history:
            # Timestamp
            timestamp_text = f"{msg['timestamp']} - {msg['role'].title()}"
            timestamp_para = Paragraph(timestamp_text, timestamp_style)
            story.append(timestamp_para)
            story.append(Spacer(1, 6))
            
            # Message content
            content = msg['content'].replace('\n', '<br/>')
            
            if msg['role'] == 'user':
                style = user_style
                icon = "👤 You:"
            else:
                style = assistant_style
                icon = "🤖 ChatGPT:"
            
            message_text = f"<b>{icon}</b><br/>{content}"
            message_para = Paragraph(message_text, style)
            story.append(message_para)
            story.append(Spacer(1, 18))
    else:
        story.append(Paragraph("No conversation history to export.", styles['Normal']))
    
    # Add disclaimer
    story.append(Spacer(1, 24))
    disclaimer = Paragraph(
        "<b>Disclaimer:</b> This analysis is for informational purposes only and should not be "
        "considered as investment advice. AI-generated responses may contain errors or biases. "
        "Please consult with a qualified financial advisor before making investment decisions.",
        styles['Normal']
    )
    story.append(disclaimer)
    
    # Build PDF
    doc.build(story)
    
    return filename


def export_enhanced_chat_pdf(filename: str, 
                           ticker: str, 
                           chat_history: List[Dict], 
                           company_data: Dict,
                           buffett_metrics: Dict) -> str:
    """
    Enhanced PDF export with additional Buffett analysis integration.
    
    Args:
        filename: Output PDF filename
        ticker: Company ticker symbol  
        chat_history: List of chat messages
        company_data: Company financial data
        buffett_metrics: Additional Buffett-specific metrics
    
    Returns:
        str: Path to the created PDF file
    """
    
    if not filename.endswith('.pdf'):
        filename += '.pdf'
    
    doc = SimpleDocTemplate(filename, pagesize=letter,
                          rightMargin=72, leftMargin=72,
                          topMargin=72, bottomMargin=18)
    
    styles = getSampleStyleSheet()
    story = []
    
    # Enhanced title page with Buffett focus
    title = Paragraph(f"Buffett-Style Analysis: {ticker}", styles['Title'])
    story.append(title)
    story.append(Spacer(1, 12))
    
    subtitle = Paragraph("AI-Assisted Investment Analysis", styles['Heading2'])
    story.append(subtitle)
    story.append(Spacer(1, 24))
    
    # Executive Summary Box
    summary_style = ParagraphStyle(
        'Summary',
        parent=styles['Normal'],
        backgroundColor=HexColor('#FFF8E1'),
        borderColor=HexColor('#F57F17'),
        borderWidth=2,
        borderPadding=12,
        spaceAfter=18
    )
    
    summary_text = f"""
    <b>Investment Summary for {ticker}</b><br/><br/>
    <b>Overall Buffett Score:</b> {company_data.get('buffett_score', 'N/A')}<br/>
    <b>Circle of Competence:</b> {buffett_metrics.get('circle_of_competence', 'Check required')}<br/>
    <b>Owner Earnings Quality:</b> {company_data.get('owner_earnings', 'N/A')}<br/>
    <b>Capital Preservation:</b> {company_data.get('capital_preservation', 'N/A')}<br/>
    <b>Business Moat Assessment:</b> Requires further analysis<br/><br/>
    <b>Export Date:</b> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
    """
    
    summary_para = Paragraph(summary_text, summary_style)
    story.append(summary_para)
    
    # Key Metrics Table
    story.append(Paragraph("Key Financial Metrics", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    metrics_data = [
        ["Metric", "Value"],
        ["Net Income", company_data.get('net_income', 'N/A')],
        ["Sales/Revenue", company_data.get('sales', 'N/A')],
        ["Owner Earnings", company_data.get('owner_earnings', 'N/A')],
        ["Look-Through Earnings", company_data.get('look_through_earnings', 'N/A')],
        ["Altman Z-Score", company_data.get('altman_z', 'N/A')],
        ["Capital Preservation", company_data.get('capital_preservation', 'N/A')],
        ["Buffett Score", company_data.get('buffett_score', 'N/A')]
    ]
    
    metrics_table = Table(metrics_data, colWidths=[250, 200])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1f77b4")),
        ('TEXTCOLOR',(0,0),(-1,0), colors.white),
        ('ALIGN',(0,0),(-1,-1),'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,0), 12),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND',(0,1),(-1,-1), colors.HexColor("#f8f9fa")),
        ('GRID', (0,0), (-1,-1), 1, colors.HexColor("#dee2e6")),
        ('FONTSIZE', (0,1), (-1,-1), 10),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#f8f9fa")])
    ]))
    
    story.append(metrics_table)
    story.append(Spacer(1, 24))
    
    # ChatGPT insights section
    story.append(Paragraph("AI Investment Insights", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    if chat_history:
        # Add chat history with enhanced formatting
        for i, msg in enumerate(chat_history):
            if msg['role'] == 'user':
                style = ParagraphStyle(
                    'UserQ',
                    parent=styles['Normal'],
                    backgroundColor=HexColor('#E8F5E8'),
                    borderColor=HexColor('#4CAF50'),
                    borderWidth=1,
                    borderPadding=8,
                    spaceAfter=6,
                    fontSize=10
                )
                header = f"<b>Question {i//2 + 1} ({msg['timestamp']}):</b>"
            else:
                style = ParagraphStyle(
                    'AIAnswer',
                    parent=styles['Normal'],
                    backgroundColor=HexColor('#F0F8FF'),
                    borderColor=HexColor('#2196F3'),
                    borderWidth=1,
                    borderPadding=8,
                    spaceAfter=12,
                    fontSize=10
                )
                header = f"<b>AI Analysis:</b>"
            
            content = f"{header}<br/>{msg['content'].replace('\n', '<br/>')}"
            para = Paragraph(content, style)
            story.append(para)
            story.append(Spacer(1, 6))
    else:
        story.append(Paragraph("No AI conversation recorded for this analysis.", styles['Normal']))
    
    # Add Buffett principles reference
    story.append(PageBreak())
    story.append(Paragraph("Warren Buffett's Investment Principles", styles['Heading2']))
    story.append(Spacer(1, 12))
    
    principles_text = """
    <b>1. Circle of Competence:</b> Invest only in businesses you understand completely.<br/><br/>
    <b>2. Economic Moats:</b> Look for companies with sustainable competitive advantages.<br/><br/>
    <b>3. Owner Earnings:</b> Focus on real cash generation, not just reported earnings.<br/><br/>
    <b>4. Management Quality:</b> Invest in companies with honest, capable management.<br/><br/>
    <b>5. Intrinsic Value:</b> Buy when market price is significantly below intrinsic value.<br/><br/>
    <b>6. Long-term Perspective:</b> Hold great businesses for the very long term.<br/><br/>
    <b>7. Capital Allocation:</b> Management should efficiently deploy shareholder capital.<br/><br/>
    <b>8. Financial Strength:</b> Companies should have strong balance sheets and manageable debt.<br/><br/>
    <b>9. Predictable Earnings:</b> Prefer businesses with stable, predictable cash flows.<br/><br/>
    <b>10. Price Discipline:</b> Be patient and disciplined about entry prices.
    """
    
    principles_para = Paragraph(principles_text, styles['Normal'])
    story.append(principles_para)
    
    # Final disclaimer
    story.append(Spacer(1, 24))
    final_disclaimer = Paragraph(
        "<b>Important Disclaimer:</b> This report combines traditional financial analysis with AI-generated insights. "
        "While the financial metrics are based on reported data, the AI analysis should be considered supplementary "
        "and may contain inaccuracies. This is not investment advice. Always conduct your own research and consult "
        "with qualified financial professionals before making investment decisions. Past performance does not guarantee future results.",
        ParagraphStyle('Disclaimer', parent=styles['Normal'], fontSize=8, textColor=HexColor('#666666'))
    )
    story.append(final_disclaimer)
    
    # Build the enhanced PDF
    doc.build(story)
    return filename