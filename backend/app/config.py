"""Configuration for the code logger backend."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""
    # API
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")

    # Qdrant
    QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
    QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
    QDRANT_URL = os.getenv("QDRANT_URL", f"http://{QDRANT_HOST}:{QDRANT_PORT}")
    VECTOR_SIZE = 3072  # Gemini embedding dimension

    # Embedding (Gemini)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "models/embedding-001")

    # LLM (Groq or Gemini for summarization)
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
    GEMINI_LLM_MODEL = os.getenv("GEMINI_LLM_MODEL", "gemini-1.5-flash")

    # Fallback to Gemini for embeddings if Groq not used for embeddings
    USE_GEMINI_EMBEDDING = os.getenv("USE_GEMINI_EMBEDDING", "true").lower() == "true"
