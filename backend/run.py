#!/usr/bin/env python3
"""Run the Code Logger API locally (development)."""
import os
import sys

# Load .env from repo root if present
repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_file = os.path.join(repo_root, ".env")
if os.path.isfile(env_file):
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import app

if __name__ == "__main__":
    from app.config import Config
    port = Config.FLASK_PORT
    print(f" * API: http://0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=os.getenv("FLASK_ENV") == "development")
