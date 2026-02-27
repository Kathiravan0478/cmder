"""CLI commands: activate, deactivate, initialize, terminate, delete-logs, analyze-diff, answer-query, summarize."""
import os
import json
import time
import argparse
import requests
from pathlib import Path


def get_api_base():
    return os.getenv("CODE_LOGGER_API_URL", "http://localhost:5000")


def get_collection_id(cwd=None):
    cwd = cwd or os.getcwd()
    return "repo_" + os.path.basename(cwd.rstrip(os.sep)).replace(" ", "_")[:64]


def api_get(path, **kwargs):
    return requests.get(get_api_base() + path, timeout=30, **kwargs)


def api_post(path, json_data=None, **kwargs):
    return requests.post(
        get_api_base() + path,
        json=json_data,
        timeout=60,
        **kwargs,
    )


def cmd_health():
    r = api_get("/api/health")
    r.raise_for_status()
    print(json.dumps(r.json(), indent=2))


def cmd_init(cwd=None):
    cwd = cwd or os.getcwd()
    cid = get_collection_id(cwd)
    r = api_post("/api/init-collection", json_data={"collection_id": cid})
    r.raise_for_status()
    print(json.dumps(r.json(), indent=2))
    return cid


def cmd_analyze_diff(file_path, old_content, new_content, commit_id="", author="", collection_id=None):
    collection_id = collection_id or get_collection_id()
    payload = {
        "collection_id": collection_id,
        "file_path": file_path,
        "diff": {"old": old_content, "new": new_content},
        "commit_id": commit_id,
        "author": author,
    }
    r = api_post("/api/analyze-diff", json_data=payload)
    r.raise_for_status()
    print(json.dumps(r.json(), indent=2))
    return r.json()


def cmd_answer_query(query, top_k=30, collection_id=None):
    collection_id = collection_id or get_collection_id()
    r = api_post(
        "/api/answer-query",
        json_data={"collection_id": collection_id, "query": query, "top_k": top_k},
    )
    r.raise_for_status()
    print(json.dumps(r.json(), indent=2))
    return r.json()


def cmd_summarize_codebase(collection_id=None):
    collection_id = collection_id or get_collection_id()
    r = api_post(
        "/api/summarize-codebase",
        json_data={"collection_id": collection_id},
    )
    r.raise_for_status()
    print(json.dumps(r.json(), indent=2))
    return r.json()


def cmd_delete_logs(log_dir=None):
    log_dir = log_dir or os.path.join(os.getcwd(), ".code-logger")
    if not os.path.isdir(log_dir):
        print("No .code-logger directory found.")
        return
    for f in Path(log_dir).rglob("*"):
        if f.is_file():
            f.unlink()
    for d in sorted(Path(log_dir).rglob("*"), key=lambda p: -len(p.parts)):
        if d.is_dir():
            d.rmdir()
    if os.path.isdir(log_dir):
        os.rmdir(log_dir)
    print("Logs deleted.")


def main():
    parser = argparse.ArgumentParser(description="Code Logger CLI - any IDE integration")
    sub = parser.add_subparsers(dest="command", help="Commands")

    sub.add_parser("health", help="Check API health")
    sub.add_parser("init", help="Initialize logger / create collection")
    p_analyze = sub.add_parser("analyze-diff", help="Analyze code diff (file old new)")
    p_analyze.add_argument("file_path", help="File path")
    p_analyze.add_argument("--old", required=True, help="Old content or path to file")
    p_analyze.add_argument("--new", required=True, help="New content or path to file")
    p_analyze.add_argument("--commit", default="", help="Commit ID")
    p_analyze.add_argument("--author", default="", help="Author")
    p_analyze.add_argument("--collection", default=None, help="Collection ID")
    p_query = sub.add_parser("answer-query", help="Ask a question about the codebase")
    p_query.add_argument("query", nargs="+", help="Query text")
    p_query.add_argument("--top-k", type=int, default=30)
    p_query.add_argument("--collection", default=None)
    p_sum = sub.add_parser("summarize", help="Summarize codebase")
    p_sum.add_argument("--collection", default=None)
    p_summary_c = sub.add_parser("summarize-codebase")
    p_summary_c.add_argument("--collection", default=None)
    p_del = sub.add_parser("delete-logs", help="Remove .code-logger log files")
    p_del.add_argument("--log-dir", default=None, help="Override .code-logger path")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    base = get_api_base()
    if args.command != "delete-logs" and args.command != "health":
        try:
            api_get("/api/health").raise_for_status()
        except Exception as e:
            print("API not reachable at", base, "-", e)
            return 1

    if args.command == "health":
        cmd_health()
    elif args.command == "init":
        cmd_init()
    elif args.command == "analyze-diff":
        old_val = args.old
        new_val = args.new
        if os.path.isfile(old_val):
            with open(old_val, "r", encoding="utf-8", errors="replace") as f:
                old_val = f.read()
        if os.path.isfile(new_val):
            with open(new_val, "r", encoding="utf-8", errors="replace") as f:
                new_val = f.read()
        cmd_analyze_diff(
            args.file_path,
            old_val,
            new_val,
            commit_id=args.commit,
            author=args.author,
            collection_id=args.collection,
        )
    elif args.command == "answer-query":
        cmd_answer_query(
            " ".join(args.query),
            top_k=args.top_k,
            collection_id=args.collection,
        )
    elif args.command in ("summarize", "summarize-codebase"):
        cmd_summarize_codebase(collection_id=getattr(args, "collection", None))
    elif args.command == "delete-logs":
        cmd_delete_logs(log_dir=args.log_dir)
    return 0


if __name__ == "__main__":
    exit(main() or 0)
