
import base64
import json
import mimetypes
import os
import re
from pathlib import Path
from string import Template


import requests

from dotenv import load_dotenv
load_dotenv()


PROMPT_FILE = Path(__file__).parent.parent / "prompts" / "gemma_prompt.txt"


OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

MODEL = "openai/gpt-oss-20b:free"


VISION_MODELS = [
    "openai/gpt-oss-20b:free",
    "google/gemma-4-26b-a4b-it:free",
    "inclusionai/ling-3.0-flash:free",
]


FALLBACK_MODELS = [
    "openai/gpt-oss-20b:free",
    "google/gemma-4-26b-a4b-it:free",
    "inclusionai/ling-3.0-flash:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
]

REQUEST_TIMEOUT = 120


def _load_prompt_template() -> str:

    return PROMPT_FILE.read_text(encoding="utf-8")


def _render_prompt(evidence_text: str) -> str:

    template = Template(_load_prompt_template())
    safe_text = evidence_text or "(no text — image only)"
    return template.substitute(evidence_text=safe_text)


def _encode_image_as_data_url(image_path: str) -> str:
    """Read an image file and return a base64 data URL suitable for
    OpenRouter's multimodal `image_url` content type.

    Format: data:<mime>;base64,<bytes>
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    mime, _ = mimetypes.guess_type(str(path))
    if not mime or not mime.startswith("image/"):
        
        mime = "image/jpeg"

    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _repair_json(text: str) -> dict | None:
 
    
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.MULTILINE)


    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

   
    for match in re.finditer(r"\{.*\}", text, re.DOTALL):
        candidate = match.group(0)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

  
    if text.strip().startswith("{") and not text.strip().endswith("}"):
     
        candidate = text.rstrip().rstrip(",")
 
        if candidate.count('"') % 2 == 1:
            candidate += '"'
        candidate += "}"
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass

    return None


def _looks_truncated(text: str) -> bool:
   
    stripped = text.strip()
    if not stripped:
        return False
   
    if "{" not in stripped:
        return False
   
    if stripped.count("{") != stripped.count("}"):
        return True
  
    if stripped.count('"') % 2 != 0:
        return True
    return False


def analyze(evidence_text: str, image_path: str | None = None) -> dict:

    if not image_path and (not evidence_text or not evidence_text.strip()):
        raise ValueError("analyze(): evidence_text is empty and no image provided.")

    prompt = _render_prompt(evidence_text or "(no text — image only)")

    token = os.getenv("OPENROUTER_API_KEY")
    if not token:
        raise RuntimeError("api key not found")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

  
    content_parts = []
    if image_path:
        try:
            data_url = _encode_image_as_data_url(image_path)
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": data_url},
            })
        except FileNotFoundError as e:
            raise RuntimeError(f"Could not attach image: {e}") from e

    content_parts.append({"type": "text", "text": prompt})

   
    has_image = any(
        part.get("type") == "image_url"
        for part in content_parts
        if isinstance(part, dict)
    )
    parsed, content = _call_with_fallback(
        headers, content_parts, vision_only=has_image
    )

   
    if parsed is None and _looks_truncated(content):
        continuation_parts = list(content_parts) + [
            {"type": "text", "text": "Your previous response was cut off. "
                                      "Continue EXACTLY where you left off and "
                                      "finish the JSON object. Output only the "
                                      "remaining JSON, no commentary."}
        ]

        messages = [
            {"role": "user", "content": content_parts},
            {"role": "assistant", "content": content},
            {"role": "user", "content": continuation_parts[-1]["text"]},
        ]
        content2 = _call_gemma(headers, messages, max_tokens=4000)
       
        parsed = _try_parse_json(content + content2)
        if parsed is None:
            parsed = _try_parse_json(content2)

    if parsed is None:
        raise RuntimeError(
            "Could not parse JSON from model output.\n"
            f"Raw output (first 500 chars):\n{content[:500]}\n\n"
            "Tip: the free Gemma route truncates long outputs. "
            "Try again, or reduce body_markdown size in the prompt."
        )

    required_keys = ["category", "location", "summary", "key_facts",
                     "visual_description", "headline", "body_markdown"]
    for key in required_keys:
        if key == "key_facts":
            parsed.setdefault(key, [])
        else:
            parsed.setdefault(key, "")

    return parsed


def _call_with_fallback(
    headers: dict,
    content_parts: list,
    vision_only: bool = False,
) -> tuple[dict | None, str]:
    """Try the primary model, then fallbacks, until one returns parseable JSON
    or we exhaust the list. Returns (parsed_dict_or_None, raw_content).

    If `vision_only` is True, only models in VISION_MODELS are tried.
    """
    global MODEL  

    pool = VISION_MODELS if vision_only else FALLBACK_MODELS
  
    candidates = [MODEL] + [m for m in pool if m != MODEL]
    last_error: Exception | None = None
    last_content = ""

    for candidate in candidates:
        MODEL = candidate
        try:
            content = _call_gemma(headers, content_parts)
        except RuntimeError as e:
         
            last_error = e
            continue

        last_content = content
        parsed = _try_parse_json(content)
        if parsed is not None:
            return parsed, content

    if last_error:
        msg = (
            "All vision-capable fallback models failed. "
            if vision_only
            else "All fallback models failed. "
        )
        raise RuntimeError(
            f"{msg}Last error: {last_error}. "
            f"Wait 60 seconds or check your OpenRouter quota."
        ) from last_error
    return None, last_content


def _call_gemma(headers: dict, content_or_messages, max_tokens: int = 4000) -> str:
   
    if isinstance(content_or_messages, list) and content_or_messages and \
            isinstance(content_or_messages[0], dict) and \
            "role" in content_or_messages[0]:
        messages = content_or_messages
    else:
        messages = [{"role": "user", "content": content_or_messages}]

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": max_tokens,
    }

    response = requests.post(
        OPENROUTER_API_URL,
        headers=headers,
        json=payload,
        timeout=REQUEST_TIMEOUT,
    )

 
    if response.status_code in (429, 404):
        raise RuntimeError(
            f"OpenRouter returned {response.status_code} for model "
            f"{MODEL!r}: {response.text[:200]}"
        )

    response.raise_for_status()
    data = response.json()

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise RuntimeError(f"Unexpected API response shape: {data}")


def _try_parse_json(content: str) -> dict | None:
    """Try `json.loads`, then `_repair_json`. Returns None on failure."""
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        pass
    return _repair_json(content or "")
