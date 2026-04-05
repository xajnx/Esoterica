import os
import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, List, Literal, Optional, cast
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# --- Load environment ---
load_dotenv()

# --- Persona Loading ---
PERSONA_PATH = Path(__file__).resolve().parent.parent / "persona.md"
if PERSONA_PATH.exists():
    PERSONA_TEXT = PERSONA_PATH.read_text(encoding="utf-8")
else:
    PERSONA_TEXT = "You are Miryana, a wise guide of esoteric and religious knowledge."

BASE_DIR = Path(__file__).resolve().parent

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
_VECTOR_STORE_RAW = os.getenv("VECTOR_STORE_PATH", "./data/vector_store.faiss")
VECTOR_STORE_PATH = str((BASE_DIR / _VECTOR_STORE_RAW).resolve()) if not Path(_VECTOR_STORE_RAW).is_absolute() else _VECTOR_STORE_RAW
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "4"))
OPENAI_TIMEOUT_SEC = float(os.getenv("OPENAI_TIMEOUT_SEC", "45"))

# Populated in lifespan if API key is present; None triggers placeholder responses.
openai_client = None
vector_index = None
vector_metadata: list[dict] = []


def _vector_metadata_path() -> Path:
    return Path(VECTOR_STORE_PATH).with_suffix(".meta.json")


def _load_vector_store() -> None:
    global vector_index, vector_metadata
    index_path = Path(VECTOR_STORE_PATH)
    metadata_path = _vector_metadata_path()
    if not index_path.exists() or not metadata_path.exists():
        vector_index = None
        vector_metadata = []
        return

    import faiss

    vector_index = faiss.read_index(str(index_path))
    vector_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))


async def _retrieve_passages(query: str, top_k: Optional[int] = None) -> list[dict]:
    if not openai_client or vector_index is None or not vector_metadata:
        return []

    import faiss
    import numpy as np

    emb = await openai_client.embeddings.create(model=EMBEDDING_MODEL, input=query)
    query_vec = np.array([emb.data[0].embedding], dtype="float32")
    faiss.normalize_L2(query_vec)

    k = min(top_k or RETRIEVAL_TOP_K, len(vector_metadata))
    scores, indices = vector_index.search(query_vec, k)

    passages: list[dict] = []
    for idx, score in zip(indices[0], scores[0]):
        if idx < 0 or idx >= len(vector_metadata):
            continue
        item = vector_metadata[idx]
        passages.append(
            {
                "source": item.get("source", "Unknown Source"),
                "chunk_id": item.get("chunk_id", idx),
                "content": item.get("content", ""),
                "score": float(score),
            }
        )
    return passages


def _build_retrieval_context(passages: list[dict]) -> str:
    if not passages:
        return ""
    lines = [
        "Retrieved source passages:",
        "Use these as grounding context when relevant and cite with [Source | chunk N].",
    ]
    for p in passages:
        source = p.get("source", "Unknown Source")
        chunk_id = p.get("chunk_id", "?")
        content = p.get("content", "")
        lines.append(f"[{source} | chunk {chunk_id}] {content}")
    return "\n".join(lines)

# --- Mode-specific prompt instructions ---
_MODE_INSTRUCTIONS: dict[str, str] = {
    "quick": (
        "Respond in 2-3 clear sentences. "
        "Use plain language, highlight one strong cross-tradition parallel, and avoid flowery phrasing."
    ),
    "deep": (
        "Provide a thorough comparative analysis in grounded, modern language. "
        "Include historical context, key figures or themes, parallel patterns across traditions, "
        "and meaningful distinctions. Use citations where possible (Book, Chapter, Verse; tradition name; historical source)."
    ),
}

_TONE_GUARDRAILS = (
    "Tone calibration: Speak as a calm, wise matron and trusted guide. "
    "Prioritize clarity over performance. Use occasional poetic phrasing sparingly, "
    "but avoid theatrical language, mystical grandstanding, excessive metaphor, and dramatic self-mythologizing. "
    "Be reverent, confident, and practical."
)

_TONE_PROFILES: dict[str, str] = {
    "balanced": (
        "Default tone. Clear, grounded, and warm. Keep poetic language light and occasional."
    ),
    "poetic": (
        "Use slightly more lyrical cadence while staying clear and practical. "
        "Do not become theatrical or abstract."
    ),
    "scholarly": (
        "Use precise, analytic language with minimal ornament. "
        "Favor structure, definitions, and historical clarity over flourish."
    ),
}

def _build_system_prompt(
    mode: Literal["quick", "deep"],
    tone: Literal["balanced", "poetic", "scholarly"],
) -> str:
    return (
        f"{PERSONA_TEXT.strip()}\n\n"
        f"{_TONE_GUARDRAILS}\n\n"
        f"Tone profile: {_TONE_PROFILES[tone]}\n\n"
        f"Response style: {_MODE_INSTRUCTIONS[mode]}"
    )

# --- Lifespan (startup / shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    global openai_client
    if _OPENAI_API_KEY:
        from openai import AsyncOpenAI

        openai_client = AsyncOpenAI(
            api_key=_OPENAI_API_KEY,
            timeout=OPENAI_TIMEOUT_SEC,
            max_retries=1,
        )
    _load_vector_store()
    yield
    openai_client = None

# --- FastAPI init ---
app = FastAPI(title="Esoterica AI Backend", version="0.2.0", lifespan=lifespan)

# --- CORS (restrict to known dev origins) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# --- Models ---
class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = None
    mode: Literal["quick", "deep"] = "deep"
    tone: Literal["balanced", "poetic", "scholarly"] = "balanced"

class ChatResponse(BaseModel):
    reply: str
    persona: str
    mode: str
    tone: str
    citations: List[dict] = []

# --- LLM reply generator ---
# System prompt = full persona (authoritative) + mode instruction.
# History role=system entries are stripped to prevent prompt injection from the client.
async def generate_reply(
    message: str,
    history: Optional[List["ChatMessage"]],
    mode: Literal["quick", "deep"],
    tone: Literal["balanced", "poetic", "scholarly"],
) -> tuple[str, list[dict]]:
    if not openai_client:
        # Placeholder until OPENAI_API_KEY is configured in backend/.env
        label = "Quick Summary" if mode == "quick" else "Deep Dive"
        note = f"[{label} — set OPENAI_API_KEY in backend/.env to activate Miryana]"
        if mode == "quick":
            return (
                f"{note}\nBrief reflection on '{message[:120]}': "
                "Across traditions a common thread surfaces — ask for a Deep Dive to follow it further."
            ), []
        return (
            f"{note}\nYour inquiry '{message}' stirs old rivers of wisdom. "
            "Creation hymns, prophetic visions, sacred law — all threads in a larger tapestry await grounding in the source texts."
        ), []

    messages: list[dict] = [{"role": "system", "content": _build_system_prompt(mode, tone)}]
    if history:
        for msg in history:
            if msg.role != "system":  # guard: never let client inject system prompts
                messages.append({"role": msg.role, "content": msg.content})

    retrieved = await _retrieve_passages(message)
    retrieval_context = _build_retrieval_context(retrieved)
    if retrieval_context:
        messages.append({"role": "user", "content": retrieval_context})

    messages.append({"role": "user", "content": message})

    completion = await openai_client.chat.completions.create(
        model=MODEL_NAME,
        messages=cast(Any, messages),
        temperature={"balanced": 0.6, "poetic": 0.8, "scholarly": 0.35}[tone],
        max_tokens=200 if mode == "quick" else 900,
    )
    reply_text = completion.choices[0].message.content or ""
    citations = [
        {"source": p["source"], "chunk_id": p["chunk_id"]}
        for p in retrieved
        if p.get("content", "").strip()
    ]
    return reply_text, citations

# --- Routes ---
@app.get("/health")
async def health():
    return {
        "status": "ok",
        "persona_loaded": PERSONA_PATH.exists(),
        "llm_ready": openai_client is not None,
        "model": MODEL_NAME,
        "rag_ready": vector_index is not None and len(vector_metadata) > 0,
        "vector_chunks": len(vector_metadata),
        "embedding_model": EMBEDDING_MODEL,
    }

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")
    try:
        reply_text, citations = await generate_reply(req.message, req.history, req.mode, req.tone)
        return ChatResponse(
            reply=reply_text,
            persona="Miryana",
            mode=req.mode,
            tone=req.tone,
            citations=citations,
        )
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(e))

# Run helper for manual execution (optional)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
