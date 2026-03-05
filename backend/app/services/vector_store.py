"""Qdrant vector store for codebase vectors."""
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, Filter, FieldCondition, MatchValue
from app.config import Config


def get_qdrant_client() -> QdrantClient:
    """Create Qdrant client."""
    return QdrantClient(url=Config.QDRANT_URL)


def ensure_collection(client: QdrantClient, collection_id: str, vector_size: int):
    """Create collection if it does not exist."""
    try:
        client.get_collection(collection_id)
    except Exception:
        client.create_collection(
            collection_name=collection_id,
            vectors_config={"size": vector_size, "distance": Distance.COSINE},
        )


def upsert_code_vectors(
    collection_id: str,
    points: List[Dict[str, Any]],
    vector_size: int,
) -> None:
    """Upsert code diff vectors into Qdrant. Each point: id, vector, payload (file_path, diff, etc)."""
    client = get_qdrant_client()
    ensure_collection(client, collection_id, vector_size)
    qpoints = [
        PointStruct(
            id=pt["id"],
            vector=pt["vector"],
            payload={
                "file_path": pt.get("file_path", ""),
                "diff_old": pt.get("diff_old", ""),
                "diff_new": pt.get("diff_new", ""),
                "commit_id": pt.get("commit_id", ""),
                "author": pt.get("author", ""),
                "model": pt.get("model", ""),
            },
        )
        for pt in points
    ]
    client.upsert(collection_name=collection_id, points=qpoints)


def search_vectors(
    collection_id: str,
    query_vector: List[float],
    top_k: int = 30,
    vector_size: int = 3072,
) -> List[Dict[str, Any]]:
    """Search for similar vectors. Returns list of payloads with score."""
    client = get_qdrant_client()
    ensure_collection(client, collection_id, vector_size)
    results = client.search(
        collection_name=collection_id,
        query_vector=query_vector,
        limit=top_k,
    )
    return [
        {
            "id": r.id,
            "score": r.score,
            "file_path": r.payload.get("file_path", ""),
            "diff_old": r.payload.get("diff_old", ""),
            "diff_new": r.payload.get("diff_new", ""),
            "commit_id": r.payload.get("commit_id", ""),
            "author": r.payload.get("author", ""),
        }
        for r in results
    ]


def collection_exists(collection_id: str) -> bool:
    """Check if collection exists."""
    try:
        get_qdrant_client().get_collection(collection_id)
        return True
    except Exception:
        return False


def delete_collection(collection_id: str) -> bool:
    """Delete a collection (terminate logger for that codebase). Returns True if deleted."""
    try:
        client = get_qdrant_client()
        client.get_collection(collection_id)
        client.delete_collection(collection_name=collection_id)
        return True
    except Exception:
        return False
