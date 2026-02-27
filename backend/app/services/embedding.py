"""Embedding service using Gemini (or configurable alternative)."""
from typing import List
from app.config import Config


def get_embedding_client():
    """Return embedding client based on config."""
    if Config.USE_GEMINI_EMBEDDING and Config.GEMINI_API_KEY:
        import google.generativeai as genai
        genai.configure(api_key=Config.GEMINI_API_KEY)
        return "gemini", genai
    # Fallback: use sentence-transformers for offline/portable use
    try:
        from sentence_transformers import SentenceTransformer
        return "sentence", SentenceTransformer("all-MiniLM-L6-v2")
    except Exception:
        return None, None


_embedding_client = None
_embedding_type = None


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a list of texts. Returns 3072-dim or 384-dim for MiniLM."""
    global _embedding_client, _embedding_type
    if _embedding_client is None:
        _embedding_type, _embedding_client = get_embedding_client()
    if _embedding_client is None:
        raise RuntimeError(
            "No embedding backend. Set GEMINI_API_KEY or install sentence-transformers."
        )
    if _embedding_type == "gemini":
        result = []
        for t in texts:
            r = _embedding_client.embed_content(
                model=Config.EMBEDDING_MODEL,
                content=t,
                task_type="retrieval_document",
            )
            emb = r.get("embedding") or (r.get("embeddings") or [None])[0]
            if emb is None and hasattr(r, "embedding"):
                emb = getattr(r, "embedding", None)
            result.append(emb)
        return result
    if _embedding_type == "sentence":
        return _embedding_client.encode(texts).tolist()
    raise RuntimeError("Unknown embedding type")


def get_vector_size() -> int:
    """Return embedding dimension (3072 for Gemini, 384 for MiniLM)."""
    global _embedding_client, _embedding_type
    if _embedding_client is None:
        _embedding_type, _embedding_client = get_embedding_client()
    if _embedding_type == "gemini":
        return 3072
    if _embedding_type == "sentence":
        return 384
    return Config.VECTOR_SIZE
