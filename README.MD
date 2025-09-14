# Esoterica AI

Esoterica AI is an experimental chatbot designed to **deep dive into the world’s religions, myths, and esoteric traditions**.  
Its purpose is to reveal **patterns, congruences, and resonances** across belief systems while respecting their unique voices.  

At its heart is **Miryana**, a prophetess-like persona who guides users with wisdom, poetic cadence, and scholarly grounding.  

---

## Project Structure

```
backend/
	app.py                # FastAPI entrypoint (/chat, /health)
	requirements.txt      # Python dependencies
	.env.example          # Environment variable template
	models/               # (Future) model loaders, chains
	data/                 # Corpora, ingestion outputs (FAISS, chunks)
frontend/
	index.html            # Vite entry HTML
	package.json          # React/Tailwind dependencies
	tailwind.config.js    # Tailwind config
	postcss.config.js     # PostCSS pipeline
	src/
		main.jsx            # React root renderer
		styles.css          # Tailwind layers
		components/
			ChatApp.jsx       # Overall chat container
			ChatWindow.jsx    # Scrollable conversation area
			MessageList.jsx   # Renders messages
			InputBox.jsx      # User input form
persona.md              # Persona definition for Miryana
roadmap                 # Phased development plan
.gitignore
```

---

## Persona (Miryana)
See `persona.md`. The backend loads this file at startup (placeholder now) and the frontend seeds the intro message for immediate voice continuity. Future enhancement: inject persona text as a system prompt for every LLM call + retrieval-augmented context.

Sample intro (auto-shown in UI):
> I am Miryana, a keeper of echoes and threads... (see full text in `persona.md`).

Guidelines embedded: poetic, comparative, reverent, non-dogmatic, offers quick vs deep analysis.

---

## Getting Started

### 1. Backend (FastAPI)
Create and activate a virtual environment, install deps, run server:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # add your API keys
uvicorn app:app --reload --port 8000
```

Health check: http://localhost:8000/health

### 2. Frontend (Vite + React + Tailwind)
```bash
cd frontend
npm install
npm run dev
```

Visit: http://localhost:5173 (default Vite port). Chat sends POST /chat to backend at http://localhost:8000.

If backend is at a different origin, set `VITE_API_BASE` in a `frontend/.env`:
```
VITE_API_BASE=http://localhost:8000
```

Restart dev server after changes to env vars.

---

## Environment Variables
Backend `.env` (copy from `.env.example`):
```
OPENAI_API_KEY=sk-...
MODEL_NAME=gpt-4o-mini
VECTOR_STORE_PATH=./backend/data/vector_store.faiss
```
Frontend `.env` (optional):
```
VITE_API_BASE=http://localhost:8000
```

Never commit real secrets—`.env` is ignored.

---

## Current Features
- Persona intro displayed on load.
- Mode switch: Quick Summary vs Deep Dive (affects placeholder response style).
- Basic error handling and loading state.
- CORS open for development.

---

## Planned Near-Term Enhancements (Phase 2 & 3)
1. Inject persona text as system prompt to actual LLM provider.
2. Add ingestion script:
	 - Load seed texts (Genesis 1–3, Enuma Elish, Rig Veda Hymn of Creation, Pyramid Text excerpt).
	 - Chunk & embed (OpenAI embeddings or local) -> store in FAISS.
3. Retrieval Augmented Generation (RAG):
	 - Query vector store for top-k passages.
	 - Compose prompt: persona + user query + retrieved passages.
4. Display citations inline (e.g., [Genesis 1:2], [Enuma Elish Tablet I]).

---

## Longer-Term Ideas (Phase 4+)
- Persona avatar & theming.
- Toggle: Quick vs Deep vs Source-Cited.
- Scroll “unrolling” animation while generating.
- Logging of retrieved passages.
- Multi-language support.
- Comparative timeline & harmonic map visualization.

---

## Development Notes
- Keep responses side-effect free until actual model integration.
- Add tests later for prompt formatting & retrieval ranking.
- Consider abstraction layer for: PersonaManager, RetrievalPipeline, PromptComposer.

---

## Contributing
1. Fork & branch (`feature/xyz`).
2. Keep persona tone intact.
3. For new corpora provide source + licensing notes.

---

## License
TBD (recommendation: start with MIT unless corpus licensing requires additional clauses).

---

## Quick Troubleshooting
| Issue | Fix |
|-------|-----|
| 404 on /chat | Ensure backend running on :8000, correct VITE_API_BASE | 
| CORS error | Confirm FastAPI CORS allows frontend origin | 
| Tailwind classes not applied | Ensure `styles.css` imported & dev server restarted | 
| Persona not loading | Check `persona.md` exists at project root |

---

## Roadmap Reference
See `roadmap` file for phased plan. Current repository state corresponds to end of Phase 1.

---

May Miryana guide your iterations: illuminate, compare, never coerce.


