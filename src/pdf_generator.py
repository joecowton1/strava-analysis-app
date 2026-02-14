"""
PDF generation module for ride analysis reports.
"""
from __future__ import annotations

import json
import html
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


def generate_ride_pdf(
    activity_data: Dict[str, Any],
    analysis_data: Dict[str, Any],
    output_path: str
) -> str:
    """
    Generate a PDF report for a ride analysis.
    
    Args:
        activity_data: Activity data from Strava API
        analysis_data: Dictionary with 'metrics' and 'narrative' from analysis
        output_path: Path where PDF should be saved
    
    Returns:
        Path to the generated PDF file
    """
    if not REPORTLAB_AVAILABLE:
        raise RuntimeError("ReportLab not installed. Install with: pip install reportlab")
    
    # Ensure output directory exists
    output_path_obj = Path(output_path)
    output_path_obj.parent.mkdir(parents=True, exist_ok=True)
    
    # Create PDF document
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Container for the 'Flowable' objects
    story = []
    
    # Define styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1E88E5'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1565C0'),
        spaceAfter=12,
        spaceBefore=20,
        fontName='Helvetica-Bold'
    )
    
    metric_label_style = ParagraphStyle(
        'MetricLabel',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#666666'),
        fontName='Helvetica'
    )
    
    metric_value_style = ParagraphStyle(
        'MetricValue',
        parent=styles['Normal'],
        fontSize=14,
        textColor=colors.HexColor('#000000'),
        fontName='Helvetica-Bold'
    )
    
    narrative_style = ParagraphStyle(
        'Narrative',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        spaceAfter=12,
        alignment=TA_JUSTIFY,
        leading=16
    )
    
    # Title
    ride_name = activity_data.get("name", "Untitled Ride")
    story.append(Paragraph(ride_name, title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Ride date
    start_date = activity_data.get("start_date", "")
    if start_date:
        try:
            dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            date_str = dt.strftime("%B %d, %Y at %I:%M %p")
            story.append(Paragraph(f"<b>Date:</b> {date_str}", styles['Normal']))
            story.append(Spacer(1, 0.1*inch))
        except:
            pass
    
    # Key Metrics Section
    story.append(Paragraph("Ride Metrics", heading_style))
    
    # Prepare metrics table
    distance_km = activity_data.get("distance", 0) / 1000
    moving_time_sec = activity_data.get("moving_time", 0)
    elapsed_time_sec = activity_data.get("elapsed_time", 0)
    elevation_gain = activity_data.get("total_elevation_gain", 0)
    avg_speed_kmh = activity_data.get("average_speed", 0) * 3.6
    max_speed_kmh = activity_data.get("max_speed", 0) * 3.6
    
    metrics_data = [
        ["Distance", f"{distance_km:.2f} km"],
        ["Moving Time", f"{moving_time_sec // 60} min {moving_time_sec % 60} sec"],
        ["Elevation Gain", f"{elevation_gain:.0f} m"],
        ["Avg Speed", f"{avg_speed_kmh:.2f} km/h"],
        ["Max Speed", f"{max_speed_kmh:.2f} km/h"],
    ]
    
    # Add optional metrics
    if activity_data.get("weighted_average_watts"):
        metrics_data.append(["Avg Power", f"{activity_data['weighted_average_watts']:.0f} W"])
    if activity_data.get("average_heartrate"):
        metrics_data.append(["Avg Heart Rate", f"{activity_data['average_heartrate']:.0f} bpm"])
        if activity_data.get("max_heartrate"):
            metrics_data.append(["Max Heart Rate", f"{activity_data['max_heartrate']:.0f} bpm"])
    if activity_data.get("average_cadence"):
        metrics_data.append(["Avg Cadence", f"{activity_data['average_cadence']:.0f} rpm"])
    
    # Create metrics table
    metrics_table = Table(metrics_data, colWidths=[2.5*inch, 2.5*inch])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E3F2FD')),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#1565C0')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#BBDEFB')),
    ]))
    
    story.append(metrics_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Analysis Section
    story.append(Paragraph("AI Analysis", heading_style))
    
    # Metrics from analysis
    analysis_metrics = analysis_data.get("metrics", {})
    if analysis_metrics:
        if analysis_metrics.get("performance_summary"):
            story.append(Paragraph(f"<b>Performance Summary:</b> {analysis_metrics['performance_summary']}", narrative_style))
            story.append(Spacer(1, 0.1*inch))
        
        if analysis_metrics.get("effort_level"):
            story.append(Paragraph(f"<b>Effort Level:</b> {analysis_metrics['effort_level']}", narrative_style))
            story.append(Spacer(1, 0.1*inch))
        
        if analysis_metrics.get("notable_highlights"):
            highlights = analysis_metrics["notable_highlights"]
            if isinstance(highlights, list):
                highlights_text = "<br/>".join([f"• {h}" for h in highlights])
                story.append(Paragraph(f"<b>Highlights:</b><br/>{highlights_text}", narrative_style))
                story.append(Spacer(1, 0.1*inch))
        
        if analysis_metrics.get("improvement_areas"):
            improvements = analysis_metrics["improvement_areas"]
            if isinstance(improvements, list):
                improvements_text = "<br/>".join([f"• {i}" for i in improvements])
                story.append(Paragraph(f"<b>Areas for Improvement:</b><br/>{improvements_text}", narrative_style))
                story.append(Spacer(1, 0.2*inch))
    
    # Narrative analysis
    narrative = analysis_data.get("narrative", "")
    if narrative:
        story.append(Paragraph("Detailed Analysis", heading_style))
        # Keep rendering robust: strip common markdown tokens and escape to valid XML/HTML.
        # (ReportLab Paragraph expects valid markup; naive replacements can break parsing.)
        cleaned = narrative
        # Strip markdown heading prefixes at line starts
        cleaned = cleaned.replace("\n### ", "\n").replace("\n## ", "\n").replace("\n# ", "\n")
        if cleaned.startswith("### "):
            cleaned = cleaned[4:]
        elif cleaned.startswith("## "):
            cleaned = cleaned[3:]
        elif cleaned.startswith("# "):
            cleaned = cleaned[2:]

        # Strip emphasis/code markers (leave content readable)
        for token in ("**", "__", "`"):
            cleaned = cleaned.replace(token, "")

        # Escape to safe HTML/XML and preserve line breaks
        narrative_html = html.escape(cleaned).replace("\n", "<br/>")
        story.append(Paragraph(narrative_html, narrative_style))
    
    # Build PDF
    doc.build(story)
    
    return output_path

