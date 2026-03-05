"""REST API routes: analyze-diff, answer-query, summarize-codebase."""
import uuid
from flask import request, jsonify
from app.services.embedding import get_embeddings, get_vector_size
from app.services.vector_store import (
    ensure_collection,
    upsert_code_vectors,
    search_vectors,
    get_qdrant_client,
    delete_collection as delete_collection_store,
)
from app.services.llm import summarize_with_llm


def register_routes(app):
    """Register all API routes."""

    @app.route("/api/health", methods=["GET"])
    def health():
        """Health check; includes Qdrant connectivity so Docker knows full stack is ready."""
        try:
            client = get_qdrant_client()
            client.get_collections()
            qdrant = "ok"
        except Exception as e:
            return jsonify({
                "status": "degraded",
                "service": "code-logger-api",
                "qdrant": "error",
                "error": str(e),
            }), 503
        return jsonify({
            "status": "ok",
            "service": "code-logger-api",
            "qdrant": qdrant,
        })

    @app.route("/api/analyze-diff", methods=["POST"])
    def analyze_diff():
        """
        Accept code diff, embed it, store in Qdrant, and return natural language summary.
        Payload: collection_id, file_path, diff: {old, new}, commit_id?, author?, model?
        """
        try:
            data = request.get_json() or {}
            collection_id = data.get("collection_id") or "default_repo"
            file_path = data.get("file_path", "")
            diff = data.get("diff", {})
            old_code = diff.get("old", "")
            new_code = diff.get("new", "")
            commit_id = data.get("commit_id", "")
            author = data.get("author", "")
            model = data.get("model", "")

            text_to_embed = f"file:{file_path}\nold:\n{old_code}\nnew:\n{new_code}"
            vectors = get_embeddings([text_to_embed])
            vector_size = get_vector_size()
            ensure_collection(get_qdrant_client(), collection_id, vector_size)
            point_id = str(uuid.uuid4())
            upsert_code_vectors(
                collection_id,
                [
                    {
                        "id": point_id,
                        "vector": vectors[0],
                        "file_path": file_path,
                        "diff_old": old_code,
                        "diff_new": new_code,
                        "commit_id": commit_id,
                        "author": author,
                        "model": model,
                    }
                ],
                vector_size,
            )

            context = f"File: {file_path}\nOld snippet:\n{old_code[:1500]}\nNew snippet:\n{new_code[:1500]}"
            prompt = (
                "Summarize the following code change in 1-3 concise sentences. "
                "Focus on what was added, removed, or changed (syntax, logic, or flow)."
            )
            summary = summarize_with_llm(
                f"{prompt}\n\n{context}",
                system="You are a code change summarizer. Output only the summary.",
            )
            return jsonify({
                "summary": summary,
                "file_path": file_path,
                "collection_id": collection_id,
                "stored": True,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/answer-query", methods=["POST"])
    def answer_query():
        """
        Embed query, search vector DB, pass context to LLM, return answer.
        Payload: collection_id, query, top_k?, model?
        """
        try:
            data = request.get_json() or {}
            collection_id = data.get("collection_id") or "default_repo"
            query = data.get("query", "")
            top_k = int(data.get("top_k", 30))

            if not query:
                return jsonify({"error": "query is required"}), 400

            query_vectors = get_embeddings([query])
            vector_size = get_vector_size()
            results = search_vectors(
                collection_id, query_vectors[0], top_k=top_k, vector_size=vector_size
            )
            if not results:
                return jsonify({
                    "answer": "No relevant code context found in the vector database. Initialize the logger and log some changes first.",
                    "file_path": None,
                    "confidence": 0.0,
                })

            context_parts = []
            for r in results[:10]:
                context_parts.append(
                    f"File: {r['file_path']}\nDiff (new):\n{r.get('diff_new', '')[:800]}\n"
                )
            context = "\n---\n".join(context_parts)
            prompt = f"Question: {query}\n\nRelevant code context:\n{context}\n\nAnswer the question based only on the code context above. Be concise."
            answer = summarize_with_llm(
                prompt,
                system="You are a codebase assistant. Answer only based on the provided code context.",
            )
            best = results[0]
            return jsonify({
                "answer": answer,
                "file_path": best.get("file_path"),
                "confidence": round(float(best.get("score", 0)), 2),
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/summarize-codebase", methods=["GET", "POST"])
    def summarize_codebase():
        """
        Summarize entire codebase: retrieve diverse vectors and generate architecture/key modules summary.
        GET or POST with collection_id (default_repo).
        """
        try:
            if request.method == "POST":
                data = request.get_json() or {}
            else:
                data = request.args or {}
            collection_id = data.get("collection_id") or "default_repo"
            top_k = int(data.get("top_k", 50))

            # Use a generic query to retrieve a broad set of vectors
            query = "main architecture modules components entry points"
            query_vectors = get_embeddings([query])
            vector_size = get_vector_size()
            results = search_vectors(
                collection_id, query_vectors[0], top_k=top_k, vector_size=vector_size
            )
            if not results:
                return jsonify({
                    "summary_file": f"{collection_id}_summary.md",
                    "summary": {
                        "architecture": "No codebase data in vector store yet.",
                        "key_modules": [],
                        "recent_changes": [],
                        "risks": [],
                    },
                })

            context = "\n\n".join(
                [
                    f"File: {r['file_path']}\n{r.get('diff_new', '')[:600]}"
                    for r in results[:20]
                ]
            )
            prompt = (
                "Based on the following code snippets from a codebase, produce a short structured summary with: "
                "1) architecture (2-3 sentences), 2) key_modules (list), 3) recent_changes (list), 4) risks (list). "
                "Output in JSON-like format with keys: architecture, key_modules, recent_changes, risks."
            )
            summary_text = summarize_with_llm(
                f"{prompt}\n\n{context}",
                system="You are a codebase summarizer. Output structured summary only.",
            )
            # Parse loosely into structure
            summary = {
                "architecture": summary_text[:500],
                "key_modules": [],
                "recent_changes": [r.get("file_path", "") for r in results[:5]],
                "risks": [],
            }
            return jsonify({
                "summary_file": f"{collection_id}_summary.md",
                "summary": summary,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/init-collection", methods=["POST"])
    def init_collection():
        """Create empty collection for a codebase (called on Initialize Logger)."""
        try:
            data = request.get_json() or {}
            collection_id = data.get("collection_id") or "default_repo"
            vector_size = get_vector_size()
            ensure_collection(get_qdrant_client(), collection_id, vector_size)
            return jsonify({
                "collection_id": collection_id,
                "vector_size": vector_size,
                "created": True,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/delete-collection", methods=["POST"])
    def delete_collection_route():
        """Delete a collection (terminate logger for that codebase)."""
        try:
            data = request.get_json() or {}
            collection_id = data.get("collection_id") or "default_repo"
            deleted = delete_collection_store(collection_id)
            return jsonify({
                "collection_id": collection_id,
                "deleted": deleted,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/terminate", methods=["POST"])
    def terminate():
        """Terminate logger: delete collection and clear server-side state for that codebase."""
        try:
            data = request.get_json() or {}
            collection_id = data.get("collection_id") or "default_repo"
            deleted = delete_collection_store(collection_id)
            return jsonify({
                "collection_id": collection_id,
                "terminated": True,
                "collection_deleted": deleted,
            })
        except Exception as e:
            return jsonify({"error": str(e)}), 500
