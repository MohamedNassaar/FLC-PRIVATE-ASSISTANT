# FLC Private AI Assistant — same-day prototype

This is a local-first demonstration for synthetic sample data. It supports text-searchable PDF/TXT/MD/CSV upload, evidence-backed document Q&A through an optional local Ollama model, basic invoice-field extraction, CSV export, a local activity log, and a clearly labelled QuickBooks sample-data screen.

## Quick start on Mac Studio

1. Install Python 3.11 or newer and Ollama from their official websites.
2. In Terminal, open this folder and run:

   ```sh
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ollama pull qwen2.5:7b
   ollama serve
   ```

3. In a second Terminal window, activate the same environment and run:

   ```sh
   streamlit run app.py
   ```

4. Open the local address Streamlit prints (normally `http://localhost:8501`). Upload `data/sample_supplier_agreement.txt` and `data/sample_invoice.txt` using the uploader. Ask “What are the payment terms?”

If Ollama is stopped, search still retrieves matching source excerpts, but generated answers are unavailable. Set `OLLAMA_MODEL` to a model already installed locally if preferred.

## Data and network behavior

- Uploaded original files are saved under `data/uploads/`; extracted text and the SQLite index are saved in `data/assistant.db`. The app does not call a hosted AI API.
- Ollama requests are sent to the local machine at `localhost:11434`; no document is intentionally sent off-device by the app.
- Internet is required to install Python packages and download Ollama/model files. Local inference works offline after installation.
- The QuickBooks screen is static synthetic data. There is no QuickBooks login, OAuth, or company connection in this same-day build.
- Keep this prototype bound to the local machine. Do not expose Streamlit to a network or use real confidential files before security review.

## Known limitations

- Search uses simple keyword overlap, not a production vector database or robust semantic retrieval.
- Q&A quality depends on the chosen local model; citations point to retrieved excerpts and still need user verification.
- PDF text extraction does not OCR scanned pages. OCR, spreadsheet parsing, stronger invoice validation and deduplication are later-stage work.
- Invoice extraction is heuristic and must be reviewed against each original document.
- No authentication, encryption-at-rest configuration, backup policy, or multi-user controls are supplied. Use only non-confidential samples in this prototype.
- QuickBooks integration, email, production records and external actions are not implemented.

## Suggested stages and planning estimates

Planning estimates only; confirm hardware, sample types, acceptance criteria and engineer rate before committing.

| Stage | Scope | Indicative duration | Cost method |
|---|---|---:|---|
| Today: demo | Run this local app, test synthetic samples, demonstrate Q&A and invoice CSV | 4–8 focused hours | 4–8 × agreed hourly rate |
| Prototype hardening | OCR, spreadsheet parsing, evaluation set, improved retrieval, packaging and handover | 5–10 working days | 5–10 days × agreed day rate |
| QuickBooks test | Intuit OAuth sandbox, minimum read-only scopes, secure token storage and selected reports | 3–7 working days after app credentials/access | 3–7 days × agreed day rate |
| Pilot | Access controls, encryption/backup plan, audit review, user testing, operational docs | 2–4 weeks | Estimate after discovery |

Do not promise a fixed total until Mac Studio specs, document volumes, QuickBooks access and required accounting fields are agreed. The engineer should fill in location, availability, portfolio, rate, and ongoing support costs with truthful personal details; this starter intentionally does not fabricate them.
