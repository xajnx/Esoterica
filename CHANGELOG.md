# Changelog

All notable changes to this project are documented in this file.

## [0.2.0] - 2026-04-04

### Added
- OpenAI-backed chat generation in `backend/app.py`.
- RAG ingestion pipeline via `backend/ingest.py`.
- Seed corpus files under `backend/data/corpus/`.
- Retrieval context injection and citation metadata in backend responses.
- Frontend citation pill rendering in `frontend/src/components/MessageList.jsx`.
- Tone selector (Balanced, Poetic, Scholarly) in `frontend/src/components/ChatApp.jsx`.
- Additional backend env options in `backend/.env.example`:
  - `EMBEDDING_MODEL`
  - `RETRIEVAL_TOP_K`
  - `OPENAI_TIMEOUT_SEC`

### Changed
- Strengthened backend request schema with typed `mode`, `tone`, and structured history.
- Updated CORS defaults for local development origins.
- Migrated startup setup to FastAPI lifespan pattern.
- Pinned backend dependency versions in `backend/requirements.txt`.
- Improved prompt style guardrails to reduce theatrical response tone.

### Fixed
- Resolved vector-store path handling to be robust across working directories.
- Added ignore rules for generated FAISS metadata artifacts.

## [0.1.0] - 2025-09-14

### Added
- Initial FastAPI + Vite/React/Tailwind scaffold.
- Basic chat UI and backend `/chat` + `/health` endpoints.
- Miryana persona bootstrap files and early project docs.
