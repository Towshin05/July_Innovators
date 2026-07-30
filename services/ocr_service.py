

from pathlib import Path
import easyocr
import numpy as np

from PIL import Image



_READER = easyocr.Reader(["en", "bn"], gpu=False, verbose=False)


def extract_text(file_path: str, mime_type: str) -> str:

  
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"OCR: image not found at {file_path}")

    
    with Image.open(path) as img:

        rgb_image = img.convert("RGB")

     
        pixel_array = np.array(rgb_image)


    results = _READER.readtext(pixel_array, detail=1, paragraph=False)

    lines = [text for (_bbox, text, conf) in results if conf >= 0.3]

    return "\n".join(lines).strip()


if __name__ == "__main__":
    import sys


  
    sample = sys.argv[1] if len(sys.argv) > 1 else "test_ocr.jpg"

    try:
        result = extract_text(sample, "image/jpeg")
        print("=" * 60)
        print(f"OCR result from {sample}:")
        print("=" * 60)
        print(result if result else "[no text detected]")
        print("=" * 60)
        print(f"Lines: {len(result.splitlines())}  Characters: {len(result)}")
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        print("Place a test image at that path and try again.")
    except Exception as e:
     
        print(f"ERROR: {type(e).__name__}: {e}")
        print("Check that the file is a valid image (JPG, PNG, BMP, WEBP).")
