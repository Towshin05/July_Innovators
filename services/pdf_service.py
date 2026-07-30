
import fitz  
from services.ocr_service import extract_text as ocr_extract_text


def _looks_like_text(text: str, min_chars: int = 20) -> bool:

    return len(text.strip()) >= min_chars

def extract_text(file_path: str, mime_type: str = "application/pdf") -> str:
 
    with fitz.open(file_path) as doc:
        
        pages_text: list[str] = []

        for page_index, page in enumerate(doc):
         
            direct_text = page.get_text("text")

            if _looks_like_text(direct_text):
                pages_text.append(direct_text.strip())
            else:
               
                pix = page.get_pixmap(dpi=200)
                temp_path = f"_pdf_page_{page_index}.png"
                pix.save(temp_path)

            
                try:
                    page_text = ocr_extract_text(temp_path, "image/png")
                    if page_text:
                        pages_text.append(page_text)
                finally:
                  
                    from pathlib import Path
                    Path(temp_path).unlink(missing_ok=True)

     
        return "\n\n".join(pages_text)
