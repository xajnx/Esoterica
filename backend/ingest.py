import json
import math
import os
from pathlib import Path

import faiss
import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
CORPUS_DIR = BASE_DIR / "data" / "corpus"
_VECTOR_STORE_RAW = os.getenv("VECTOR_STORE_PATH", "./data/vector_store.faiss")
VECTOR_STORE_PATH = (BASE_DIR / _VECTOR_STORE_RAW).resolve() if not Path(_VECTOR_STORE_RAW).is_absolute() else Path(_VECTOR_STORE_RAW)
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "900"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "150"))
BATCH_SIZE = int(os.getenv("EMBED_BATCH_SIZE", "64"))


def chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []

    chunks: list[str] = []
    step = max(1, chunk_size - overlap)
    for start in range(0, len(cleaned), step):
        piece = cleaned[start : start + chunk_size].strip()
        if piece:
            chunks.append(piece)
        if start + chunk_size >= len(cleaned):
            break
    return chunks


def collect_documents(corpus_dir: Path) -> list[dict]:
    documents: list[dict] = []
    for file_path in sorted(corpus_dir.glob("*.txt")):
        raw_text = file_path.read_text(encoding="utf-8").strip()
        chunks = chunk_text(raw_text, CHUNK_SIZE, CHUNK_OVERLAP)
        for i, content in enumerate(chunks, start=1):
            documents.append(
                {
                    "source": file_path.stem,
                    "chunk_id": i,
                    "content": content,
                }
            )
    return documents


def batched(items: list[str], batch_size: int):
    total = len(items)
    for i in range(0, total, batch_size):
        yield items[i : i + batch_size]


def embed_documents(client: OpenAI, docs: list[dict]) -> np.ndarray:
    inputs = [d["content"] for d in docs]
    all_vectors: list[list[float]] = []

    total_batches = math.ceil(len(inputs) / BATCH_SIZE)
    for n, batch in enumerate(batched(inputs, BATCH_SIZE), start=1):
        response = client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        batch_vectors = [item.embedding for item in response.data]
        all_vectors.extend(batch_vectors)
        print(f"Embedded batch {n}/{total_batches} ({len(batch)} chunks)")

    vectors = np.array(all_vectors, dtype="float32")
    faiss.normalize_L2(vectors)
    return vectors


def main() -> None:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("OPENAI_API_KEY is missing in backend/.env")

    if not CORPUS_DIR.exists():
        raise SystemExit(f"Corpus directory does not exist: {CORPUS_DIR}")

    docs = collect_documents(CORPUS_DIR)
    if not docs:
        raise SystemExit(f"No .txt corpus files found under: {CORPUS_DIR}")

    print(f"Collected {len(docs)} chunks from {CORPUS_DIR}")
    client = OpenAI(api_key=api_key)
    vectors = embed_documents(client, docs)

    index: faiss.Index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)  # type: ignore[call-arg]

    VECTOR_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(VECTOR_STORE_PATH))

    meta_path = VECTOR_STORE_PATH.with_suffix(".meta.json")
    meta_path.write_text(json.dumps(docs, ensure_ascii=True, indent=2), encoding="utf-8")

    print(f"Wrote FAISS index: {VECTOR_STORE_PATH}")
    print(f"Wrote metadata: {meta_path}")
    print("Ingestion complete.")


if __name__ == "__main__":
    main()
