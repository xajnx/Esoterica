import json
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Literal, Optional, cast

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
VECTOR_STORE_PATH = (
    str((BASE_DIR / _VECTOR_STORE_RAW).resolve())
    if not Path(_VECTOR_STORE_RAW).is_absolute()
    else _VECTOR_STORE_RAW
)
RETRIEVAL_TOP_K = int(os.getenv("RETRIEVAL_TOP_K", "4"))
OPENAI_TIMEOUT_SEC = float(os.getenv("OPENAI_TIMEOUT_SEC", "45"))
_CHAT_DB_RAW = os.getenv("CHAT_DB_PATH", "./data/chat_history.db")
CHAT_DB_PATH = (
    str((BASE_DIR / _CHAT_DB_RAW).resolve()) if not Path(_CHAT_DB_RAW).is_absolute() else _CHAT_DB_RAW
)

# Populated in lifespan if API key is present; None triggers placeholder responses.
openai_client = None
vector_index = None
vector_metadata: list[dict] = []


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _vector_metadata_path() -> Path:
    return Path(VECTOR_STORE_PATH).with_suffix(".meta.json")


def _chat_db_connection() -> sqlite3.Connection:
    db_path = Path(CHAT_DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _init_chat_db() -> None:
    with _chat_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                pinned INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        # Lightweight migration for older databases created before the `pinned` column existed.
        existing_cols = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(conversations)").fetchall()
        }
        if "pinned" not in existing_cols:
            conn.execute("ALTER TABLE conversations ADD COLUMN pinned INTEGER NOT NULL DEFAULT 0")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                citations TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id, id)"
        )


def _conversation_exists(conversation_id: str) -> bool:
    with _chat_db_connection() as conn:
        row = conn.execute("SELECT id FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
    return row is not None


def _create_conversation_record(title: Optional[str]) -> dict:
    now = _utc_now_iso()
    conversation_id = str(uuid.uuid4())
    safe_title = (title or "Untitled Conversation").strip() or "Untitled Conversation"
    with _chat_db_connection() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, pinned, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (conversation_id, safe_title, 0, now, now),
        )
    return {
        "id": conversation_id,
        "title": safe_title,
        "pinned": False,
        "created_at": now,
        "updated_at": now,
        "message_count": 0,
    }


def _append_message(
    conversation_id: str,
    role: Literal["user", "assistant", "system"],
    content: str,
    citations: Optional[list[dict]] = None,
    created_at: Optional[str] = None,
) -> None:
    if not _conversation_exists(conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")

    now = created_at or _utc_now_iso()
    citations_payload = json.dumps(citations or [])

    with _chat_db_connection() as conn:
        conn.execute(
            """
            INSERT INTO messages (conversation_id, role, content, citations, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (conversation_id, role, content, citations_payload, now),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )


def _list_conversations() -> list[dict]:
    with _chat_db_connection() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   c.pinned,
                   COUNT(m.id) AS message_count
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            GROUP BY c.id
            ORDER BY c.pinned DESC, c.updated_at DESC
            """
        ).fetchall()

    return [{**dict(row), "pinned": bool(row["pinned"])} for row in rows]


def _get_conversation(conversation_id: str) -> dict:
    with _chat_db_connection() as conn:
        convo = conn.execute(
            "SELECT id, title, pinned, created_at, updated_at FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if convo is None:
            raise HTTPException(status_code=404, detail="Conversation not found")

        messages = conn.execute(
            """
            SELECT role, content, citations, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,),
        ).fetchall()

    parsed_messages: list[dict] = []
    for row in messages:
        parsed_messages.append(
            {
                "role": row["role"],
                "content": row["content"],
                "citations": json.loads(row["citations"]),
                "timestamp": row["created_at"],
            }
        )

    return {
        "id": convo["id"],
        "title": convo["title"],
        "pinned": bool(convo["pinned"]),
        "created_at": convo["created_at"],
        "updated_at": convo["updated_at"],
        "messages": parsed_messages,
    }


def _update_conversation(
    conversation_id: str,
    title: Optional[str] = None,
    pinned: Optional[bool] = None,
) -> dict:
    if title is None and pinned is None:
        raise HTTPException(status_code=400, detail="No conversation fields provided for update")

    updates: list[str] = []
    values: list[Any] = []

    if title is not None:
        safe_title = title.strip()
        if not safe_title:
            raise HTTPException(status_code=400, detail="Title cannot be empty")
        updates.append("title = ?")
        values.append(safe_title)

    if pinned is not None:
        updates.append("pinned = ?")
        values.append(1 if pinned else 0)

    now = _utc_now_iso()
    updates.append("updated_at = ?")
    values.append(now)
    values.append(conversation_id)

    with _chat_db_connection() as conn:
        cur = conn.execute(
            f"UPDATE conversations SET {', '.join(updates)} WHERE id = ?",
            tuple(values),
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")

    return _get_conversation(conversation_id)


def _delete_conversation(conversation_id: str) -> None:
    with _chat_db_connection() as conn:
        cur = conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")


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
    _init_chat_db()
    yield
    openai_client = None


# --- FastAPI init ---
app = FastAPI(title="Esoterica AI Backend", version="0.3.0", lifespan=lifespan)

# --- CORS (restrict to known dev origins) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
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
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    persona: str
    mode: str
    tone: str
    citations: List[dict] = []


class ConversationSummary(BaseModel):
    id: str
    title: str
    pinned: bool = False
    created_at: str
    updated_at: str
    message_count: int


class ConversationCreateRequest(BaseModel):
    title: Optional[str] = None


class ConversationRenameRequest(BaseModel):
    title: Optional[str] = None
    pinned: Optional[bool] = None


class ConversationImportMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    citations: List[dict] = []
    timestamp: Optional[str] = None


class ConversationImportRequest(BaseModel):
    title: str
    messages: List[ConversationImportMessage]


class ConversationMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
    citations: List[dict] = []
    timestamp: str


class ConversationDetail(BaseModel):
    id: str
    title: str
    pinned: bool = False
    created_at: str
    updated_at: str
    messages: List[ConversationMessage]


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
        note = f"[{label} - set OPENAI_API_KEY in backend/.env to activate Miryana]"
        if mode == "quick":
            return (
                f"{note}\nBrief reflection on '{message[:120]}': "
                "Across traditions a common thread surfaces - ask for a Deep Dive to follow it further."
            ), []
        return (
            f"{note}\nYour inquiry '{message}' stirs old rivers of wisdom. "
            "Creation hymns, prophetic visions, sacred law - all threads in a larger tapestry await grounding in the source texts."
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
        "chat_persistence_ready": Path(CHAT_DB_PATH).exists(),
        "chat_db_path": CHAT_DB_PATH,
    }


@app.get("/conversations", response_model=List[ConversationSummary])
async def list_conversations():
    return [ConversationSummary(**item) for item in _list_conversations()]


@app.post("/conversations", response_model=ConversationSummary)
async def create_conversation(req: ConversationCreateRequest):
    return ConversationSummary(**_create_conversation_record(req.title))


@app.post("/conversations/import", response_model=ConversationDetail)
async def import_conversation(req: ConversationImportRequest):
    created = _create_conversation_record(req.title)
    for msg in req.messages:
        _append_message(
            created["id"],
            msg.role,
            msg.content,
            citations=msg.citations,
            created_at=msg.timestamp,
        )
    return ConversationDetail(**_get_conversation(created["id"]))


@app.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(conversation_id: str):
    return ConversationDetail(**_get_conversation(conversation_id))


@app.patch("/conversations/{conversation_id}", response_model=ConversationDetail)
async def rename_conversation(conversation_id: str, req: ConversationRenameRequest):
    return ConversationDetail(**_update_conversation(conversation_id, title=req.title, pinned=req.pinned))


@app.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    _delete_conversation(conversation_id)
    return {"status": "deleted", "id": conversation_id}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")
    try:
        reply_text, citations = await generate_reply(req.message, req.history, req.mode, req.tone)
        if req.conversation_id:
            now = _utc_now_iso()
            _append_message(req.conversation_id, "user", req.message, created_at=now)
            _append_message(req.conversation_id, "assistant", reply_text, citations=citations, created_at=now)
        return ChatResponse(
            reply=reply_text,
            persona="Miryana",
            mode=req.mode,
            tone=req.tone,
            citations=citations,
        )
    except HTTPException:
        raise
    except Exception as e:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(e))


# Run helper for manual execution (optional)
if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
