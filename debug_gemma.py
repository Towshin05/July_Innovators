
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

from services.gemma_service import _call_gemma, _render_prompt, MODEL

token = os.getenv("OPENROUTER_API_KEY")
if not token:
    print("ERROR: OPENROUTER_API_KEY not set in .env")
    sys.exit(1)

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}

sample_text = "On 21 July 2026, police fired tear gas at student protesters in "
"front of the University of Dhaka central gate. Several students were injured "
"and taken to Dhaka Medical College Hospital. The protest was against a new "
"transport fare hike announced earlier in the week."

prompt = _render_prompt(sample_text)
content_parts = [{"type": "text", "text": prompt}]

print(f"Model: {MODEL}")
print(f"Prompt length: {len(prompt)} chars")
print("Calling OpenRouter...")
print("-" * 60)

content = _call_gemma(headers, content_parts)
print(f"Response length: {len(content)} chars")
print(f"Finish reason (if visible in raw): see below")
print("=" * 60)
print("RAW CONTENT:")
print(repr(content[:1000]))
print("=" * 60)
print("HUMAN-READABLE:")
print(content[:1500])
print("=" * 60)
