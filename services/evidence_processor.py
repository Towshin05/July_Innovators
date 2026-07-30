
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional


from database.db import get_session

from database.models import Evidence, Incident, Brief

from services.ocr_service import extract_text as extract_image_text
from services.pdf_service import extract_text as extract_pdf_text
from services.gemma_service import analyze

PROJECT_ROOT = Path(__file__).parent.parent
UPLOADS_DIR = PROJECT_ROOT / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)  



def _sha256_of_file(file_path: Path) -> str:

    hasher = hashlib.sha256()

    with open(file_path, "rb") as f:
     
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def _persist_upload(file_path: Path, mime_type: str) -> Path:
   
    digest = _sha256_of_file(file_path)
    suffix = file_path.suffix.lower() or ".bin"
    dest = UPLOADS_DIR / f"{digest[:16]}{suffix}"

   
    if not dest.exists():
        shutil.copy2(file_path, dest)

    return dest



def _extract_text(file_path: Path, mime_type: str) -> str:

    if mime_type.startswith("image/"):
        
        return extract_image_text(str(file_path), mime_type)

    elif mime_type == "application/pdf":
       
        return extract_pdf_text(str(file_path), mime_type)

    elif mime_type.startswith("audio/") or mime_type.startswith("video/"):
 
        raise NotImplementedError(
            f"Audio/video transcription is not yet wired up. "
            f"MIME type: {mime_type}. "
            f"Use Whisper locally or convert audio -> text first."
        )

    else:
        
        raise ValueError(
            f"Unsupported MIME type: {mime_type!r}. "
            f"Supported: image/*, application/pdf. "
            f"Audio/video coming soon."
        )



def process_evidence(file_path: str, mime_type: str) -> dict:

    src = Path(file_path)

    if not src.exists():
        raise FileNotFoundError(f"Evidence file not found: {file_path}")

    stored_path = _persist_upload(src, mime_type)
    mime = mime_type
    digest = _sha256_of_file(stored_path)  

    with get_session() as session:
    
        existing = session.query(Evidence).filter_by(file_hash=digest).first()
        if existing and existing.incident and existing.incident.brief:

            inc = existing.incident
            brf = inc.brief
            return {
                "evidence_id": existing.id,
                "incident_id": inc.id,
                "brief_id": brf.id,
                "category": inc.category,
                "location": inc.location,
                "occurred_at": inc.occurred_at.isoformat() if inc.occurred_at else None,
                "summary": inc.summary,
                "key_facts": json.loads(inc.key_facts),  # stored as JSON string
                "visual_description": inc.visual_description or "",
                "headline": brf.headline,
                "body_markdown": brf.body_markdown,
                "deduplicated": True,  
            }

      
        extracted = _extract_text(stored_path, mime)

        
        if mime.startswith("image/"):
            image_arg = str(stored_path)
            text_arg = extracted or ""  
        else:
            image_arg = None
            text_arg = extracted
            if not text_arg or not text_arg.strip():
                raise RuntimeError(
                    "No text could be extracted from the file. "
                    "If this is a scanned image, try a clearer photo."
                )


        try:
            analysis = analyze(text_arg, image_path=image_arg)
        except Exception as e:
            raise RuntimeError(
                f"Analysis failed: {e}"
            ) from e

       
        evidence = Evidence(
            filename=src.name,                       
            stored_path=str(stored_path),             
            mime_type=mime,
            file_hash=digest,                        
            extracted_text=extracted,               
            created_at=datetime.utcnow(),
        )
        session.add(evidence)

        session.flush()

        incident = Incident(
            evidence_id=evidence.id,
            category=analysis["category"],
            location=analysis.get("location"),
            occurred_at=_parse_dt(analysis.get("occurred_at")),
            summary=analysis["summary"],
            key_facts=json.dumps(analysis["key_facts"]),  
            visual_description=analysis.get("visual_description") or None,
            created_at=datetime.utcnow(),
        )
        session.add(incident)
        session.flush()

        brief = Brief(
            incident_id=incident.id,
            headline=analysis["headline"],
            body_markdown=analysis["body_markdown"],
            pdf_path=None,
            created_at=datetime.utcnow(),
        )
        session.add(brief)
        session.flush()

        session.commit()

        
        return {
            "evidence_id": evidence.id,
            "incident_id": incident.id,
            "brief_id": brief.id,
            "category": incident.category,
            "location": incident.location,
            "occurred_at": (
                incident.occurred_at.isoformat() if incident.occurred_at else None
            ),
            "summary": incident.summary,
            "key_facts": analysis["key_facts"],
            "visual_description": analysis.get("visual_description") or "",
            "headline": brief.headline,
            "body_markdown": brief.body_markdown,
            "deduplicated": False,
        }



def _parse_dt(value) -> Optional[datetime]:

    if not value:
        return None

    
    formats = [
        "%Y-%m-%d %H:%M:%S",   
        "%Y-%m-%d",           
        "%d %B %Y, %I:%M %p",  
        "%d %B %Y",           
        "%B %d, %Y",           
    ]
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue  


    return None


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 3:
        print("Usage: python services/evidence_processor.py <file_path> <mime_type>")
        print('Example: python services/evidence_processor.py test.jpg "image/jpeg"')
        sys.exit(1)

  
    from database.db import init_db
    init_db()

  
    result = process_evidence(sys.argv[1], sys.argv[2])
    print(json.dumps(result, indent=2, ensure_ascii=False))