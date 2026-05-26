import io
from typing import List, Dict, Any

from backend.utils import logger

def generate_tactical_pdf(messages: List[Dict[str, Any]]) -> bytes:
    """
    Compiles a structured set of chat messages into a beautifully styled multi-page
    tactical PDF dossier using ReportLab.
    Falls back gracefully to a beautifully formatted text/markdown file if ReportLab is not available.
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.pdfgen import canvas
        
        logger.info("Initializing ReportLab PDF Exporter...")
        
        # We write to an in-memory byte buffer
        pdf_buffer = io.BytesIO()
        
        # Setup document template with 0.75 in (54 pt) margins
        doc = SimpleDocTemplate(
            pdf_buffer,
            pagesize=letter,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54
        )
        
        # Custom Canvas for dynamic headers and footers (page numbers)
        class NumberedCanvas(canvas.Canvas):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self._saved_page_states = []

            def showPage(self):
                self._saved_page_states.append(dict(self.__dict__))
                self._startPage()

            def save(self):
                num_pages = len(self._saved_page_states)
                for state in self._saved_page_states:
                    self.__dict__.update(state)
                    self.draw_page_decorations(num_pages)
                    super().showPage()
                super().save()

            def draw_page_decorations(self, total_pages):
                self.saveState()
                self.setFont("Helvetica-Bold", 8)
                self.setFillColor(colors.HexColor("#0D9488")) # Teal primary accent
                
                # Header
                self.drawString(54, 750, "⚽ FOOTBOT TACTICAL SUITE")
                self.setFont("Helvetica", 8)
                self.setFillColor(colors.HexColor("#64748B"))
                self.drawRightString(doc.pagesize[0] - 54, 750, "Tactical Analysis Dossier")
                
                # Header line
                self.setStrokeColor(colors.HexColor("#E2E8F0"))
                self.setLineWidth(0.5)
                self.line(54, 742, doc.pagesize[0] - 54, 742)
                
                # Footer line
                self.line(54, 48, doc.pagesize[0] - 54, 48)
                
                # Footer
                self.drawString(54, 34, "Confidential - For Professional Coaching Use Only")
                self.drawRightString(doc.pagesize[0] - 54, 34, f"Page {self._pageNumber} of {total_pages}")
                self.restoreState()
                
        # Define Color Palette
        PRIMARY = colors.HexColor("#0F172A")    # Deep slate
        SECONDARY = colors.HexColor("#0D9488")  # Vibrant Teal
        TEXT_COLOR = colors.HexColor("#334155") # Dark charcoal for readability
        BG_LIGHT = colors.HexColor("#F8FAFC")   # Soft white-blue
        
        # Styles
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CoverTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=22,
            leading=26,
            textColor=PRIMARY,
            spaceAfter=15
        )
        
        subtitle_style = ParagraphStyle(
            'CoverSubtitle',
            fontName='Helvetica',
            fontSize=11,
            leading=15,
            textColor=SECONDARY,
            spaceAfter=30
        )
        
        h1_style = ParagraphStyle(
            'SectionH1',
            parent=styles['Heading2'],
            fontName='Helvetica-Bold',
            fontSize=13,
            leading=16,
            textColor=PRIMARY,
            spaceBefore=18,
            spaceAfter=8,
            keepWithNext=True
        )
        
        user_msg_style = ParagraphStyle(
            'UserMsg',
            fontName='Helvetica-BoldOblique',
            fontSize=10,
            leading=14,
            textColor=SECONDARY,
            spaceAfter=10
        )
        
        body_style = ParagraphStyle(
            'TacticalBody',
            fontName='Helvetica',
            fontSize=9.5,
            leading=14,
            textColor=TEXT_COLOR,
            spaceAfter=8
        )
        
        citation_style = ParagraphStyle(
            'CitationBody',
            fontName='Helvetica-Oblique',
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#475569"),
            spaceAfter=4
        )
        
        story = []
        
        # --- TITLE PAGE / DOSSIER HEADER ---
        story.append(Spacer(1, 20))
        story.append(Paragraph("FOOTBOT TACTICAL DOSSIER", title_style))
        story.append(Paragraph("Compiled High-Fidelity Match Telemetry & Strategy Report", subtitle_style))
        story.append(HRFlowable(width="100%", thickness=2, color=SECONDARY, spaceAfter=20, spaceBefore=0))
        
        # Iterate through the messages in the chat session
        for msg_idx, msg in enumerate(messages):
            role = msg.get("role", "user").lower()
            content = msg.get("content", "").strip()
            
            if role == "user":
                story.append(Spacer(1, 10))
                story.append(Paragraph(f"📋 QUERY {msg_idx // 2 + 1}:", h1_style))
                
                # Format the user query nicely in a styled gray box
                p_user = Paragraph(f"\"{content}\"", user_msg_style)
                user_table = Table([[p_user]], colWidths=[doc.width])
                user_table.setStyle(TableStyle([
                    ('BACKGROUND', (0,0), (-1,-1), BG_LIGHT),
                    ('PADDING', (0,0), (-1,-1), 10),
                    ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#CBD5E1")),
                    ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                ]))
                story.append(user_table)
                story.append(Spacer(1, 10))
            
            elif role == "assistant":
                story.append(Paragraph(f"💡 ANALYST RESPONSE:", h1_style))
                
                # ReportLab Paragraphs require XML escaping for symbols like '<', '>', '&'
                clean_content = content.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                
                # Convert basic Markdown bold and lists to PDF markup
                clean_content = clean_content.replace("\n\n", "<br/><br/>")
                clean_content = clean_content.replace("\n- ", "<br/>• ")
                clean_content = clean_content.replace("\n* ", "<br/>• ")
                
                # Clean up any potential markdown headers
                import re
                clean_content = re.sub(r'###\s+(.*?)\n', r'<b>\1</b><br/>', clean_content)
                clean_content = re.sub(r'####\s+(.*?)\n', r'<b>\1</b><br/>', clean_content)
                clean_content = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', clean_content)
                
                # Fix escaped tags
                clean_content = clean_content.replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>").replace("&lt;br/&gt;", "<br/>").replace("&lt;br/&gt;&lt;br/&gt;", "<br/><br/>")
                
                story.append(Paragraph(clean_content, body_style))
                
                # Add citation audits if they are loaded in this message
                sources = msg.get("sources", [])
                if sources:
                    story.append(Spacer(1, 10))
                    story.append(Paragraph("📚 Referenced Sources & Citations:", h1_style))
                    
                    citation_items = []
                    for s in sources:
                        idx = s.get("index", "?")
                        source_file = s.get("source", "Unknown document")
                        page = f", Page {s.get('page')}" if s.get('page') else ""
                        score = f" (relevance score: {s.get('score', 0.0):.3f})" if s.get('score') else ""
                        
                        citation_text = f"<b>[{idx}] {source_file}{page}</b>{score}: {s.get('text', '')[:180].strip()}..."
                        clean_citation = citation_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("&lt;b&gt;", "<b>").replace("&lt;/b&gt;", "</b>")
                        citation_items.append([Paragraph(clean_citation, citation_style)])
                        
                    citation_table = Table(citation_items, colWidths=[doc.width])
                    citation_table.setStyle(TableStyle([
                        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
                        ('PADDING', (0,0), (-1,-1), 6),
                        ('BOTTOMPADDING', (0,-1), (-1,-1), 6),
                        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
                        ('LINEBELOW', (0,0), (-1,-2), 0.5, colors.HexColor("#E2E8F0")),
                    ]))
                    story.append(citation_table)
                
                # Separate queries by a page break for maximum professional printing aesthetics
                if msg_idx < len(messages) - 1:
                    story.append(PageBreak())
        
        # Build Document
        doc.build(story, canvasmaker=NumberedCanvas)
        pdf_bytes = pdf_buffer.getvalue()
        pdf_buffer.close()
        
        logger.info("Successfully compiled tactical PDF dossier brochure.")
        return pdf_bytes
        
    except Exception as pdf_err:
        logger.error(f"ReportLab PDF generation failed or library is not installed: {str(pdf_err)}")
        logger.info("Falling back to a beautifully compiled Markdown text dossier...")
        
        # Graceful fallback: compile high fidelity Markdown text
        md_lines = [
            "# ⚽ FOOTBOT TACTICAL SUITE DOSSIER",
            "This is a high-fidelity plain-text tactical analysis report. (ReportLab PDF fell back to Markdown text).",
            "========================================================================\n"
        ]
        
        for idx, msg in enumerate(messages):
            role = msg.get("role", "user").upper()
            content = msg.get("content", "").strip()
            
            md_lines.append(f"## {role} ({idx + 1})")
            md_lines.append(content)
            md_lines.append("\n" + "-"*40 + "\n")
            
            sources = msg.get("sources", [])
            if sources:
                md_lines.append("### Referenced Sources:")
                for s in sources:
                    page_str = f", Page {s.get('page')}" if s.get('page') else ""
                    md_lines.append(f" - [{s.get('index')}] File: {s.get('source')}{page_str} (Score: {s.get('score', 0.0):.3f})")
                md_lines.append("\n" + "-"*40 + "\n")
                
        return "\n".join(md_lines).encode("utf-8")
