# WitnessBridge AI

> **Citizen evidence intelligence platform** for journalists, NGOs, and humanitarian
> organizations. Upload photos, scanned documents, or PDFs of citizen-submitted
> evidence and get back a structured media brief plus a downloadable A4 PDF.

Built for a 2-day hackathon. Single-page Streamlit UI, local SQLite storage, and a
Python-only pipeline that calls a free vision-capable LLM via OpenRouter.

---

## 🌍 The problem

When a protest, a disaster, or a human-rights violation happens, the people on
the ground often have **raw evidence in their pockets** — smartphone photos,
screenshots, scanned documents, voice notes — but **no safe, fast way to turn
that chaos into something a journalist, NGO, or human-rights monitor can act
on**.

Practitioners report the same pain points again and again:

- **Hours, not minutes.** A reporter receives 200 photos from a single incident
  in seven languages. Manually transcribing, sorting, and writing a brief can
  eat an entire day.
- **No structure.** A folder of JPEGs is not a story. Editors need a category, a
  location, a date, and a short factual summary before they can even decide
  whether to publish.
- **Source-safety risk.** Cloud-based "AI" tools often upload the evidence to
  third-party servers, exposing sources and breaking chain-of-custody.
- **Lost context.** A photo of a fire without a location and a date is just a
  photo. The metadata *is* the value.
- **Bengali + English mix.** Most off-the-shelf tools handle English only,
  which excludes a huge share of South-Asian evidence.

**WitnessBridge AI turns that raw pile into a structured, source-safe, locally
stored brief in under a minute**, while keeping every file on the journalist's
own machine.

---

## ✨ Features

- **Single-file upload** — drag in a PNG, JPG, or PDF.
- **Vision-capable analysis** — the LLM sees the image directly (no separate OCR
  captioning step required); OCR is still run as a fallback for text-only consumers.
- **Bengali + English** OCR via [EasyOCR].
- **PDF text extraction** via PyMuPDF for scanned / digital PDFs.
- **Structured JSON output** — `category`, `location`, `occurred_at`, `summary`,
  `key_facts`, `visual_description`, `headline`, `body_markdown`.
- **Deduplication** — identical files (sha-256) are detected and the existing
  brief is returned instead of re-analyzing.
- **A4 PDF brief** — generated with ReportLab; includes headline, metadata table,
  summary, visual description, key facts, brief body, and the original source
  image when the upload is a photo.
- **Dashboard** — review all incidents processed so far.
- **Detail page** — full record of one incident, with inline image preview.
- **About page** — project explainer + ethics note.
- **100% local storage** — uploads, SQLite DB, and PDFs all stay on your disk.

---

## 🧱 Project layout

```
h:\WitnessBridgeAI\
├── app.py                          # Streamlit entry point + 4 pages
├── requirements.txt                # Pinned Python dependencies
├── verify_schema.py                # Quick DB schema sanity check
├── debug_gemma.py                  # Direct OpenRouter smoke test
│
├── database/
│   ├── __init__.py
│   ├── db.py                       # SQLAlchemy engine, SessionLocal, init_db()
│   └── models.py                   # Evidence, Incident, Brief ORM models
│
├── services/
│   ├── __init__.py
│   ├── evidence_processor.py       # Upload → OCR/PDF → LLM → persist pipeline
│   ├── ocr_service.py              # EasyOCR (en + bn)
│   ├── pdf_service.py              # PyMuPDF text extraction
│   ├── gemma_service.py            # OpenRouter client + fallback chain
│   ├── report_service.py           # ReportLab PDF generation
│   └── audio_service.py            # (placeholder for future Whisper support)
│
├── prompts/
│   └── gemma_prompt.txt            # LLM system prompt (uses $evidence_text)
│
├── uploads/                        # Stored original evidence files (gitignored)
├── reports/                        # Generated PDF briefs (gitignored)
└── database/witnessbridge.db       # SQLite DB (gitignored)
```

---

## 🚀 Quick start

### 1. Prerequisites

- **Python 3.10+** (developed and tested with 3.11)
- An **OpenRouter API key** (free tier works) — get one at <https://openrouter.ai>

### 2. Install dependencies

```powershell
 pip install -r requirements.txt
```

> `easyocr` downloads model weights on first run (~100 MB). GPU is **not**
> required; CPU is forced in `ocr_service.py`.

### 3. Configure secrets

Create a `.env` file in the project root (gitignored):

```env
OPENROUTER_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
```

### 4. Launch the app

```powershell
 streamlit run app.py
```

Streamlit opens at <http://localhost:8501>.

---

## 🧠 How the pipeline works

```
 ┌──────────────┐    ┌────────────────┐    ┌──────────────────┐    ┌──────────────┐
 │  File upload │ -> │ Persist + SHA  │ -> │ OCR (image)  or  │ -> │ Gemma via    │
 │  PNG/JPG/PDF │    │ to uploads/    │    │ PyMuPDF (PDF)    │    │ OpenRouter   │
 └──────────────┘    └────────────────┘    └──────────────────┘    └──────────────┘
                                                                           │
                                                            ┌──────────────┴──────────────┐
                                                            ▼                             ▼
                                                       Vision model              Text-only fallback
                                                  (gpt-oss-20b / gemma-4)         (Nemotron)
                                                                           │
                                                                           ▼
                                                            ┌──────────────────────────┐
                                                            │ SQLite: Evidence         │
                                                            │ Incident / Brief         │
                                                            └──────────────────────────┘
                                                                           │
                                                                           ▼
                                                            ┌──────────────────────────┐
                                                            │ ReportLab PDF brief      │
                                                            │ (A4, includes image)     │
                                                            └──────────────────────────┘
```

### Stage-by-stage

| Stage | File | What it does |
|-------|------|--------------|
| **Persist** | `services/evidence_processor.py` | Copies the upload to `uploads/`, hashes it (sha-256). |
| **Dedupe** | `services/evidence_processor.py` | If the hash matches an existing `Evidence` row that already has a `Brief`, returns the cached result immediately. |
| **Extract text** | `services/ocr_service.py` / `services/pdf_service.py` | EasyOCR (`["en", "bn"]`) for images; PyMuPDF for PDFs. |
| **Analyze** | `services/gemma_service.py` | Renders the prompt from `prompts/gemma_prompt.txt`, attaches the image as a base64 data URL, and POSTs to OpenRouter. |
| **Repair** | `services/gemma_service.py` | Tries `json.loads`; falls back to a greedy-brace extractor + truncation-closer if the model cut off mid-JSON. |
| **Retry / fallback** | `services/gemma_service.py` | On `429` or `404`, cycles through `VISION_MODELS` (when an image is attached) or `FALLBACK_MODELS` (text-only). If the output still looks truncated, it asks the model to **continue** the JSON in a second turn. |
| **Persist** | `services/evidence_processor.py` | Writes `Evidence`, `Incident`, and `Brief` rows in a single transaction. |
| **Render PDF** | `services/report_service.py` | ReportLab story: title → metadata table → embedded source image → summary → visual description → key facts → brief body. |

---

## 🛡 Resilience features

The free OpenRouter tier is flaky. The pipeline is hardened against the common
breakages:

- **Truncation detection** — `_looks_truncated()` checks brace and quote balance
  on every response. Truncated JSON triggers a *continue-from-where-you-left-off*
  second turn before giving up.
- **JSON repair** — strips Markdown fences, greedy regex from the first `{` to
  the last `}`, closes unterminated strings and braces.
- **Model fallback chain** — primary + 3 backups; when an image is attached, the
  chain is restricted to vision-capable models so non-vision endpoints can't
  poison the run with 404s.
- **Schema-level errors** — `Incident.visual_description` column exists even if
  the upload is a PDF, so re-running on an older database never raises
  `OperationalError`.
- **Prompt escaping** — uses `string.Template` with `$evidence_text` so the JSON
  schema example in the prompt (full of `{` / `}`) is never re-interpreted as
  format placeholders.

---

## 🗄 Database schema

```text
Evidence
  id, filename, stored_path, mime_type, file_hash (UNIQUE),
  extracted_text, created_at

Incident   (1:1 → Evidence)
  id, evidence_id, category, location, occurred_at, summary,
  key_facts (JSON string), visual_description, created_at

Brief      (1:1 → Incident)
  id, incident_id, headline, body_markdown, pdf_path, created_at
```

File hashes are the dedupe key; re-uploading the same image returns the cached
brief instead of re-calling the LLM.

---


## 🌐 Pages in the Streamlit UI

| Page | What it does |
|------|--------------|
| **📤 Upload Evidence** (default) | Drop a PNG/JPG/PDF → click *Analyze Evidence* → quick preview. |
| **📊 Dashboard** | Browse every incident in the DB. |
| **📄 Detail** | Full record for one incident, with inline image preview, raw OCR/PDF text, and PDF download. |
| **ℹ️ About** | Project explainer, ethics statement, future-work list. |

---

## 🔭 What it does **not** do

- ❌ Verify evidence authenticity.
- ❌ Authenticate or deanonymize sources.
- ❌ Assign blame or speculate beyond the source material.
- ❌ Store anything off your machine.

The LLM is explicitly instructed (in `prompts/gemma_prompt.txt`) to **never
identify individuals by name or facial features** and to say "unclear" rather
than invent details.

---

## 🛠 Future work

- Audio/video transcription via OpenAI Whisper (`services/audio_service.py` is
  scaffolded but not yet wired).
- Multi-language UI (Bengali interface).
- Authentication and audit logging.
- Cloud deployment with object storage.

---

## 📜 License

MIT license.
