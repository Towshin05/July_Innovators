# WitnessBridge AI

AI-powered evidence intelligence platform that transforms raw citizen-submitted evidence into structured media briefs.

Built for a 3-days AI Hackathon using Streamlit, Python, SQLite, OCR, Vision AI, and OpenRouter.

---

## Problem

Journalists, NGOs, and humanitarian organizations often receive large volumes of unstructured evidence such as photos, scanned documents, and reports during disasters, protests, or humanitarian crises.

Processing this evidence manually is slow and difficult because:

- Images and scanned documents must be transcribed before analysis.
- Evidence arrives in multiple languages, especially Bengali and English.
- Important information such as location, date, and key facts is buried inside raw files.
- Writing a factual media brief takes significant manual effort.
- Large volumes of evidence become difficult to organize quickly during emergencies.

WitnessBridge AI automates this workflow by extracting information from uploaded evidence, analyzing it with AI, and generating a structured report within minutes.

---

## Solution

WitnessBridge AI provides an end-to-end pipeline that:

- Uploads images and PDF documents
- Extracts text using OCR and PDF processing
- Uses a Vision AI model to describe image content
- Combines extracted information into a unified evidence context
- Translates Bengali content to English when required
- Analyzes the evidence using GPT-OSS via OpenRouter
- Generates:
  - Incident category
  - Location
  - Timeline
  - Key facts
  - News headline
  - Structured media brief
- Stores all results locally in SQLite
- Exports professional PDF reports using ReportLab

---


## Tech Stack

- Python
- Streamlit
- SQLite
- SQLAlchemy
- EasyOCR
- PyMuPDF
- Pillow
- ReportLab
- OpenRouter API
- GPT-OSS-20B
- Vision-capable LLM

---

## Project Workflow

```
User Upload
      │
      ▼
Image / PDF
      │
      ▼
OCR + PDF Extraction + Vision Analysis
      │
      ▼
Combined Evidence Text
      │
      ▼
GPT-OSS (OpenRouter)
      │
      ▼
Structured JSON Analysis
      │
      ▼
SQLite Storage
      │
      ▼
PDF Media Brief
```

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
## Installation

```bash
git clone https://github.com/yourusername/WitnessBridgeAI.git

cd WitnessBridgeAI
## Installation

```bash
git clone https://github.com/yourusername/WitnessBridgeAI.git

cd WitnessBridgeAI

```

---

## Environment Variables

Create a `.env` file.

```
OPENROUTER_API_KEY=your_api_key
```



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
