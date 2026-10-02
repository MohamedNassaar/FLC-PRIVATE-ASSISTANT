from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path

import requests
import streamlit as st

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "assistant.db"
UPLOAD_DIR = DATA_DIR / "uploads"
SUPPORTED = {"pdf", "txt", "md", "csv"}

st.set_page_config(page_title="FLC Private Assistant", page_icon="🔒", layout="wide")


def db():
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY, name TEXT, text TEXT, added_at TEXT)")
    conn.execute("CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, time TEXT, action TEXT, detail TEXT)")
    return conn


def log(action: str, detail: str):
    with db() as conn:
        conn.execute("INSERT INTO events(time, action, detail) VALUES(?,?,?)", (datetime.now().isoformat(timespec="seconds"), action, detail[:500]))


def extract_text(name: str, raw: bytes) -> str:
    ext = Path(name).suffix.lower().lstrip(".")
    if ext in {"txt", "md", "csv"}:
        return raw.decode("utf-8", errors="replace")
    if ext == "pdf":
        try:
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            return f"[PDF extraction error: {exc}]"
    return ""


def save_original(name: str, raw: bytes) -> Path:
    """Keep the uploaded original locally, using only its basename."""
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(name.replace("\\", "/")).name
    safe_name = re.sub(r"[^A-Za-z0-9._ -]", "_", safe_name).strip(" .") or "uploaded_file"
    target = UPLOAD_DIR / safe_name
    target.write_bytes(raw)
    return target


def chunks(text: str, size: int = 1100):
    paragraphs = [p.strip() for p in re.split(r"\n+", text) if p.strip()]
    result, current = [], ""
    for paragraph in paragraphs:
        if len(current) + len(paragraph) > size and current:
            result.append(current)
            current = ""
        current += paragraph + "\n"
    if current:
        result.append(current)
    return result or ([text[:size]] if text.strip() else [])


def retrieve(question: str, limit: int = 5):
    terms = set(re.findall(r"[a-z0-9]{3,}", question.lower()))
    with db() as conn:
        docs = conn.execute("SELECT name,text,added_at FROM documents").fetchall()
    scored = []
    for name, text, added_at in docs:
        for part in chunks(text):
            words = set(re.findall(r"[a-z0-9]{3,}", part.lower()))
            score = len(terms & words) / max(1, len(terms))
            if score:
                # Prefer newer material only when relevance is otherwise equal.
                scored.append((score, added_at, name, part.strip()))
    return [(score, name, part) for score, _, name, part in sorted(scored, key=lambda row: (row[0], row[1]), reverse=True)[:limit]]


def local_answer(question: str, hits):
    endpoint = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    model = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")
    if not hits:
        return "I could not find supporting information in the loaded documents. Please provide a relevant source document."
    context = "\n\n".join(f"[{i}] {name}: {text}" for i, (_, name, text) in enumerate(hits, 1))
    prompt = ("Answer only from the evidence below. If evidence is insufficient, say what is missing. "
              "Cite every factual claim using [1], [2], etc. Do not guess.\n\n"
              f"Evidence:\n{context}\n\nQuestion: {question}\nAnswer:")
    try:
        response = requests.post(endpoint, json={"model": model, "prompt": prompt, "stream": False}, timeout=120)
        response.raise_for_status()
        return response.json().get("response", "No answer returned.").strip()
    except requests.RequestException:
        return "Local model unavailable. Retrieved evidence is shown below; start Ollama or review the source excerpts directly."


def invoice_fields(text: str):
    patterns = {
        "Supplier": [r"(?:supplier|from|vendor)\s*[:#-]?\s*([^\n]+)", r"^([^\n]{2,80})"],
        "Invoice number": [r"(?:invoice\s*(?:no\.?|number|#))\s*[:#-]?\s*([A-Z0-9][A-Z0-9/-]+)"],
        "Date": [r"(?:invoice\s*date|date)\s*[:#-]?\s*(\d{1,4}[/-]\d{1,2}[/-]\d{1,4}|[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})"],
        "Amount": [r"(?:total\s*due|amount\s*due|grand\s*total|total)\s*[:$ ]+\$?\s*([0-9,]+\.\d{2})"],
    }
    out = {}
    for key, candidates in patterns.items():
        value = None
        for pattern in candidates:
            match = re.search(pattern, text, re.I | re.M)
            if match:
                value = match.group(1).strip(" $\t")[:120]
                break
        out[key] = value or "Uncertain / not found"
    return out


def _csv(rows):
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


st.title("🔒 FLC Private AI Assistant")
st.caption("Local-first proof of concept · synthetic data recommended · human review required")
with st.sidebar:
    st.subheader("Privacy and setup")
    st.write("Uploaded originals are stored in `data/uploads/`; extracted text and the search index are stored in `data/assistant.db`. The optional Ollama model runs locally. No document is sent to a hosted AI service by this app.")
    st.write("Internet is needed to install dependencies and download a model. QuickBooks test connection requires Intuit OAuth and internet; it is off by default.")
    st.code("OLLAMA_MODEL=qwen2.5:7b", language="text")
    page = st.radio("Workspace", ["Documents & answers", "Invoice extraction", "QuickBooks test", "Activity log"])

if page == "Documents & answers":
    st.header("Load documents and ask questions")
    uploaded = st.file_uploader("Add synthetic or approved sample files", type=sorted(SUPPORTED), accept_multiple_files=True)
    if uploaded and st.button("Index uploaded files"):
        count = 0
        with db() as conn:
            for f in uploaded:
                raw = f.getvalue()
                save_original(f.name, raw)
                text = extract_text(f.name, raw)
                if text.strip():
                    conn.execute("DELETE FROM documents WHERE name=?", (f.name,))
                    conn.execute("INSERT INTO documents(name,text,added_at) VALUES(?,?,?)", (f.name, text, datetime.now().isoformat(timespec="seconds")))
                    count += 1
        log("index", f"Indexed {count} file(s)")
        st.success(f"Indexed {count} file(s). Scanned PDFs need OCR before their text can be searched.")
    with db() as conn:
        names = [x[0] for x in conn.execute("SELECT name FROM documents ORDER BY name")]
    st.write("Indexed files:", ", ".join(names) if names else "None yet")
    if names:
        remove_name = st.selectbox("Remove an old file from search", names)
        if st.button("Remove selected file from search index"):
            with db() as conn:
                conn.execute("DELETE FROM documents WHERE name=?", (remove_name,))
            log("remove_from_index", remove_name)
            st.success(f"Removed {remove_name} from search. Its original file is still kept in data/uploads/.")
            st.rerun()
    st.caption("Answers search all files listed above. Newer files win when matching excerpts are equally relevant. Use the remove control to exclude outdated files; originals remain in data/uploads/.")
    question = st.text_input("Question", placeholder="What is the payment term in the supplier agreement?")
    if st.button("Find answer", disabled=not question):
        hits = retrieve(question)
        answer = local_answer(question, hits)
        log("search", question)
        st.markdown("#### Answer")
        st.write(answer)
        st.markdown("#### Supporting excerpts")
        if hits:
            for i, (_, name, part) in enumerate(hits, 1):
                with st.expander(f"[{i}] {name}"):
                    st.write(part)
        else:
            st.info("No matching evidence found. The assistant will not invent an answer.")

elif page == "Invoice extraction":
    st.header("Invoice fields (review before use)")
    files = st.file_uploader("Upload invoices as text-searchable PDF or TXT", type=["pdf", "txt"], accept_multiple_files=True)
    if files:
        rows = []
        for f in files:
            raw = f.getvalue()
            save_original(f.name, raw)
            text = extract_text(f.name, raw)
            rows.append({"File": f.name, **invoice_fields(text)})
        st.dataframe(rows, use_container_width=True)
        st.warning("Rule-based extraction is approximate. Confirm every value against the original invoice; scanned PDFs require OCR.")
        st.download_button("Download CSV", data="\ufeff" + _csv(rows), file_name="invoice_review.csv", mime="text/csv")
        log("invoice_extract", f"Extracted {len(rows)} invoice(s)")

elif page == "QuickBooks test":
    st.header("QuickBooks Online test company")
    st.info("This build includes a safe sample-data demonstration only. Live QuickBooks OAuth is intentionally not configured. The production-ready OAuth setup needs an Intuit developer app, callback URL, token storage and explicit company approval.")
    st.write("Sample read-only view (no connection made)")
    st.dataframe([
        {"Type": "Open invoice", "Reference": "INV-1042", "Counterparty": "Northstar Office Supplies", "Balance": "$640.00", "Status": "Sample"},
        {"Type": "Expense", "Reference": "EXP-220", "Counterparty": "Harbor Utilities", "Balance": "$185.40", "Status": "Sample"},
    ], use_container_width=True)
    st.caption("Nothing in this prototype can create, edit, pay or send anything in QuickBooks.")

else:
    st.header("Local activity log")
    with db() as conn:
        rows = conn.execute("SELECT time,action,detail FROM events ORDER BY id DESC LIMIT 200").fetchall()
    st.dataframe([{"Time": t, "Action": a, "Detail": d} for t, a, d in rows], use_container_width=True)
