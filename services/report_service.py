
import json
import re
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm


from reportlab.lib import colors


from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Image as RLImage,
)

from reportlab.platypus import Table, TableStyle

from PIL import Image as PILImage

from database.db import get_session
from database.models import Incident, Evidence, Brief



PROJECT_ROOT = Path(__file__).parent.parent
REPORT_DIR = PROJECT_ROOT / "reports"


REPORT_DIR.mkdir(parents=True, exist_ok=True)




def _build_styles():
   
    base = getSampleStyleSheet()

   
    title_style = ParagraphStyle(
        "DocTitle",
        parent=base["Title"],
        fontSize=22,             
        textColor=colors.HexColor("#1a1a2e"),  
        spaceAfter=20,           
        alignment=1,            
    )

    
    h2_style = ParagraphStyle(
        "DocH2",
        parent=base["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#16213e"),
        spaceBefore=12,
        spaceAfter=6,
    )

   
    body_style = ParagraphStyle(
        "DocBody",
        parent=base["BodyText"],
        fontSize=11,
        leading=14,
        spaceAfter=8,
    )

    bullet_style = ParagraphStyle(
        "DocBullet",
        parent=body_style,
        leftIndent=20,            
        bulletIndent=10,         
    )

    
    facts_header_style = ParagraphStyle(
        "FactsHeader",
        parent=base["Heading3"],
        fontSize=12,
        textColor=colors.HexColor("#0f3460"),
        spaceBefore=10,
        spaceAfter=4,
    )


    return {
        "title": title_style,
        "h2": h2_style,
        "body": body_style,
        "bullet": bullet_style,
        "facts_header": facts_header_style,
    }


def _markdown_to_flowables(markdown_text: str, styles: dict) -> list:
 
    if not markdown_text or not markdown_text.strip():
        return [Paragraph("(No content)", styles["body"])]

  
    flowables: list = []

    
    blocks = re.split(r"\n\s*\n", markdown_text.strip())

    for block in blocks:
      
        block = block.strip()
        if not block:
            continue

        
        if block.startswith("## "):
            heading_text = block[3:].strip()
           
            heading_text = _escape(heading_text)
            flowables.append(Paragraph(heading_text, styles["h2"]))
            continue

     
        lines = block.split("\n")
        if all(line.lstrip().startswith(("- ", "* ")) for line in lines if line.strip()):
            for line in lines:
                stripped = line.lstrip()
                if not stripped:
                    continue
               
                bullet_text = stripped[2:].strip()
                flowables.append(
                    Paragraph(
                        f"&bull;&nbsp;{_escape(bullet_text)}",
                        styles["bullet"],
                    )
                )
          
            flowables.append(Spacer(1, 6))
            continue

        para_text = _convert_inline_markdown(block)
        flowables.append(Paragraph(para_text, styles["body"]))

    return flowables


def _convert_inline_markdown(text: str) -> str:

    text = _escape(text)

    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)

   
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<i>\1</i>", text)

    return text


def _escape(text: str) -> str:

    return (
        text.replace("&", "&amp;")   
                                       
            .replace("<", "&lt;")
            .replace(">", "&gt;")
    )

def _on_page(canvas, doc):
   
    canvas.saveState()

 
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#555555"))  

   
    canvas.drawString(72, 800, "WitnessBridge AI  |  Citizen Evidence Brief")

 
    canvas.setStrokeColor(colors.HexColor("#cccccc"))
    canvas.line(72, 790, 540, 790)

   
    canvas.setFont("Helvetica", 8)

    canvas.drawString(
        72, 30,  
        f"Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
    )
    canvas.drawRightString(
        540, 30,  
        f"Page {doc.page}",
    )

    canvas.restoreState()




def generate_pdf(incident_id: int) -> Path:

    with get_session() as session:

        incident = (
            session.query(Incident)
            .filter(Incident.id == incident_id)
            .first()
        )
        if not incident:
            raise LookupError(f"No incident with id={incident_id}")

        brief = incident.brief
        if not brief:
            raise LookupError(
                f"Incident {incident_id} has no brief — "
                f"the analysis may have failed partway."
            )

        headline = brief.headline
        body_markdown = brief.body_markdown
        category = incident.category
        location = incident.location or "Unclear"
        summary = incident.summary
        visual_description = incident.visual_description or ""

        try:
            key_facts = json.loads(incident.key_facts or "[]")
            if not isinstance(key_facts, list):
                key_facts = []
        except (json.JSONDecodeError, TypeError, ValueError):
           
            key_facts = []

        occurred_at_str = (
            incident.occurred_at.strftime("%d %B %Y")
            if incident.occurred_at
            else "Date unclear"
        )

       
        evidence_row = incident.evidence
        evidence_filename = evidence_row.filename if evidence_row else None
        evidence_mime = evidence_row.mime_type if evidence_row else ""
        evidence_stored_path = (
            str(evidence_row.stored_path) if evidence_row else None
        )


    pdf_path = REPORT_DIR / f"incident_{incident_id}.pdf"



    if evidence_stored_path and evidence_mime.startswith("image/"):
        source_image_path = Path(evidence_stored_path)
        if not source_image_path.exists():
            source_image_path = None
    else:
        source_image_path = None


    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        leftMargin=72,    
        rightMargin=72,
        topMargin=72,
        bottomMargin=72,
        title=headline,
        author="WitnessBridge AI",
    )


    styles = _build_styles()


    story: list = []

    story.append(Paragraph(_escape(headline), styles["title"]))


    metadata_table = Table(
        [
            ["Category", category],
            ["Location", location],
            ["Date",     occurred_at_str],
        ],

        colWidths=[100, 350],
    )
    metadata_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
                # Padding: 6 points on top/bottom, 8 points on left/right.
                ("PADDING", (0, 0), (-1, -1), 6),
                # Thin gray border around the whole table.
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                # Inner vertical line between the two columns.
                ("LINEAFTER", (0, 0), (0, -1), 0.5, colors.HexColor("#cccccc")),
                # Bold the label cells.
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                # Slightly smaller font for the values.
                ("FONTSIZE", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(metadata_table)
    story.append(Spacer(1, 14))

    if source_image_path and source_image_path.exists():
        try:
         
            max_w = 451
            with PILImage.open(source_image_path) as pil_img:
                iw, ih = pil_img.size
            if iw > 0 and ih > 0:
                ratio = max_w / iw
                display_w = max_w
                display_h = ih * ratio
              
                if display_h > 600:
                    ratio = 600 / ih
                    display_h = 600
                    display_w = iw * ratio
                story.append(PageBreak())
                story.append(Paragraph("Source Image", styles["h2"]))
                story.append(
                    RLImage(
                        str(source_image_path),
                        width=display_w,
                        height=display_h,
                    )
                )
                if evidence_filename:
                    story.append(Spacer(1, 6))
                    story.append(
                        Paragraph(
                            _escape(f"Original filename: {evidence_filename}"),
                            styles["body"],
                        )
                    )
        except Exception:
    
            pass


    story.append(Paragraph("Summary", styles["h2"]))
    story.append(Paragraph(_escape(summary), styles["body"]))
    story.append(Spacer(1, 8))

    if visual_description and visual_description.strip() and \
            visual_description.strip().lower() != "no image provided":
        story.append(Paragraph("Visual Description", styles["h2"]))
        story.append(
            Paragraph(_escape(visual_description), styles["body"])
        )
        story.append(Spacer(1, 8))


    if key_facts:
        story.append(Paragraph("Key Facts", styles["h2"]))
        for fact in key_facts:

            story.append(
                Paragraph(f"&bull;&nbsp;{_escape(fact)}", styles["bullet"])
            )
        story.append(Spacer(1, 8))


    story.append(Paragraph("Brief", styles["h2"]))
    story.extend(_markdown_to_flowables(body_markdown, styles))


    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)


    with get_session() as session:

        brief_row = session.query(Brief).filter_by(incident_id=incident_id).first()
        if brief_row:
           
            brief_row.pdf_path = str(pdf_path)
       
            session.commit()

    return pdf_path



if __name__ == "__main__":
  
    import sys

    if len(sys.argv) < 2:
        print("Usage: python services/report_service.py <incident_id>")
        sys.exit(1)

  
    from database.db import init_db
    init_db()

    try:
       
        path = generate_pdf(int(sys.argv[1]))
        print(f"Generated: {path}")
    except LookupError as e:
        print(f"Not found: {e}")
    except ValueError:
        print(f"incident_id must be an integer, got: {sys.argv[1]!r}")