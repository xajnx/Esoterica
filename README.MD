# Esoterica AI

Esoterica AI is a comparative religion and myth analysis chatbot powered by a FastAPI backend and React frontend.

Miryana is the guiding voice: wise, grounded, and citation-aware.

## What Works Today

- FastAPI chat backend with OpenAI integration.
- Retrieval-augmented generation (RAG) using FAISS.
- Seed corpus + ingestion script.
- React chat UI with:
  - Quick Summary / Deep Dive mode
  - Balanced / Poetic / Scholarly tone selector
  - Inline source citation pills

## Tech Stack

- Backend: FastAPI, OpenAI Python SDK, FAISS, python-dotenv
- Frontend: Vite, React, Tailwind, Axios

## Repository Layout

```text
backend/
  app.py
  ingest.py
  requirements.txt
  .env.example
  data/
    corpus/
frontend/
  package.json
  index.html
  src/
persona.md
roadmap
```

## Prerequisites

- Python 3.11+
- Node.js 18+ (or 20+ recommended)
- npm
- OpenAI API key

## Quick Start (Minimal Headache)

Run from project root (`Esoterica/`) unless noted.

### 1. Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env` and set your key:

```env
OPENAI_API_KEY=sk-...
MODEL_NAME=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
RETRIEVAL_TOP_K=4
OPENAI_TIMEOUT_SEC=45
VECTOR_STORE_PATH=./data/vector_store.faiss
```

### 2. Build the vector store (one-time or when corpus changes)

```bash
cd backend
source .venv/bin/activate
python ingest.py
```

Expected outputs:

- `backend/data/vector_store.faiss`
- `backend/data/vector_store.meta.json`

### 3. Start backend

```bash
cd backend
source .venv/bin/activate
uvicorn app:app --reload --port 8000 --app-dir $(pwd)
```

Health check:

- http://127.0.0.1:8000/health

### 4. Start frontend

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open:

- http://localhost:5173

If backend is not on port 8000, create `frontend/.env`:

```env
VITE_API_BASE=http://localhost:8000
```

Restart frontend after `.env` changes.

## Day-to-Day Dev Commands

Backend:

```bash
cd backend && source .venv/bin/activate && uvicorn app:app --reload --port 8000 --app-dir $(pwd)
```

Frontend:

```bash
cd frontend && npm run dev
```

Rebuild vectors after corpus updates:

```bash
cd backend && source .venv/bin/activate && python ingest.py
```

## Common Problems and Fixes

| Issue | Cause | Fix |
|---|---|---|
| `npm ERR! enoent ... Esoterica/package.json` | Running npm from repo root | Run npm commands from `frontend/` |
| `Address already in use` on `:8000` | Old backend process still running | `kill $(lsof -ti:8000)` then restart uvicorn |
| `rag_ready: false` in `/health` | Vector store missing or wrong path | Run `python ingest.py`, verify `VECTOR_STORE_PATH` |
| 404/failed chat in UI | Backend not running or wrong API base | Start backend; verify `VITE_API_BASE` |
| No citations in responses | Retrieval not loaded | Confirm `/health` shows `rag_ready: true` |

## Notes

- `persona.md` is loaded by backend and used in system prompt construction.
- `backend/data/corpus/` currently contains seed summary texts for bootstrapping.
- Real secrets belong in local `.env` only. Never commit credentials.

## Roadmap

See `roadmap` for upcoming phases and expansion ideas.


