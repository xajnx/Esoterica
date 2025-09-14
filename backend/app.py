import os
from pathlib import Path
from typing import List, Optional
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
    PERSONA_TEXT = "Miryana persona file missing. Proceeding with fallback voice."

# --- FastAPI init ---
app = FastAPI(title="Esoterica AI Backend", version="0.1.0")

# --- CORS (allow localhost dev) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Models ---
class ChatRequest(BaseModel):
    message: str
    history: Optional[List[dict]] = None  # list of {role, content}
    mode: Optional[str] = "deep"  # 'quick' or 'deep'

class ChatResponse(BaseModel):
    reply: str
    persona: str
    mode: str

# --- Placeholder LLM Logic ---
# In future: integrate LangChain, embeddings, retrieval from FAISS, etc.
def generate_reply(message: str, mode: str = "deep") -> str:
    # Very naive placeholder that echoes and uses persona context.
    # Replace with actual chain using persona as system prompt.
    intro_line = "I am Miryana, keeper of echoes. "
    if mode == "quick":
        return intro_line + f"Brief reflection: {message[:140]} ... Patterns across traditions will be revealed more deeply in deep mode."  # noqa: E501
    else:
        return (
            intro_line
            + "Your inquiry stirs old rivers of wisdom. "
            + f"You asked: '{message}'. One might compare creation hymns, prophetic visions, and sacred law — all threads in a larger tapestry. (Placeholder response)"
        )

# --- Routes ---
@app.get("/health")
async def health():
    return {"status": "ok", "persona_loaded": PERSONA_PATH.exists()}

@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")
    try:
        reply_text = generate_reply(req.message, req.mode or "deep")
        return ChatResponse(reply=reply_text, persona="Miryana", mode=req.mode or "deep")
    except Exception as e:  # pragma: no cover (simple placeholder)
        raise HTTPException(status_code=500, detail=str(e))

# --- Startup Event (future: load vector store, model clients) ---
@app.on_event("startup")
async def startup_event():
    # Placeholder for future initialization (FAISS load, embeddings, etc.)
    pass

# Run helper for manual execution (optional)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
