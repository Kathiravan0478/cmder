# Code Logger – Offline AI-Assisted Code Analysis and Reasoning

A portable, IDE-integratable system for **recording code changes** (natural language + syntax/logic/flow), **vector embeddings**, and **contextual Q&A** over your codebase. Based on the research paper *"Offline AI-Assisted Code Analysis and Reasoning Using Lightweight LLMs and Vector Embeddings"*.

- **Integratable with any IDE**: VSCode extension + CLI so Cursor, Vim, or other editors can use the same backend via commands.
- **Portable**: Docker Compose (backend + Qdrant), `requirements.txt`, and clear setup for Windows, macOS, and Linux. Clone and run on any system or from GitHub.

## Features (from the paper)

- **Logger modes**: Code Logger (periodic diff analysis), Structure Logger (folder-level changes), Full Code Logger (both).
- **Commands**: Activate / Deactivate / Initialize / Terminate Logger, Delete Logs, Deactivate Mode.
- **REST API**:  
  - `POST /api/analyze-diff` – analyze code diffs, store vectors, return summaries.  
  - `POST /api/answer-query` – semantic search + LLM answers about the codebase.  
  - `GET/POST /api/summarize-codebase` – high-level codebase summary.
- **Vector store**: Qdrant for codebase vectors (cosine similarity).
- **Embeddings**: Gemini embedding model (or optional offline fallback).
- **LLM**: Groq (or Gemini) for summarization and query answering.

## Project layout

```
logger/
├── backend/          # Flask API (analyze-diff, answer-query, summarize-codebase)
├── cli/              # CLI for any IDE (code-logger init, analyze-diff, answer-query, summarize)
├── extension/        # VSCode extension (Code Logger commands + modes)
├── docker-compose.yml
├── .env.example
└── README.md
```

## Quick start (portable on any system)

### 1. Clone and start backend + Qdrant (Docker)

Run the stack in Docker; the API and Qdrant are then available system-wide at `localhost:5000` and `localhost:6333`. Use the CLI and VSCode extension from the host with no extra config.

```bash
git clone <your-repo-url> logger && cd logger
cp .env.example .env
# Edit .env: set GEMINI_API_KEY and optionally GROQ_API_KEY
docker-compose up -d
```

- API: `http://localhost:5000` (reachable from the host; CLI and extension use this by default)
- Qdrant: `http://localhost:6333`
- Backend starts only after Qdrant is healthy; `/api/health` reports both API and Qdrant status.

#### Docker setup for access from any directory

1. **From the project root** (where `docker-compose.yml` lives):
   ```bash
   cd /path/to/cmder
   cp .env.example .env
   ```
   Edit `.env` and set at least `GEMINI_API_KEY`. Optionally set `GROQ_API_KEY` for faster LLM answers.

2. **Start the stack:**
   ```bash
   docker-compose up -d
   ```
   Wait until both containers are healthy (`docker compose ps` should show `healthy` for backend and qdrant).

3. **Use the model and API from any directory on your machine:**
   - **CLI:** Install once (`cd cli && pip install -e .`), then from **any folder** run:
     ```bash
     code-logger health
     code-logger init
     code-logger answer-query "Where is X handled?"
     ```
     The CLI uses `http://localhost:5000` by default, so it works from any directory.
   - **VSCode extension:** Set `codeLogger.apiUrl` to `http://localhost:5000` (default). Works in any workspace.
   - **Optional:** To always point at this backend from every terminal, add to your `~/.zshrc` or `~/.bashrc`:
     ```bash
     export CODE_LOGGER_API_URL=http://localhost:5000
     ```
     Then the CLI and any script using this env will reach the Docker backend from anywhere.

4. **Stop the stack:** `docker-compose down` (data in Qdrant is kept in a Docker volume).

### 2. Run without Docker (local Python + Qdrant)

**Qdrant** (one of):

- Docker only: `docker run -p 6333:6333 qdrant/qdrant:v1.7.4`
- Or install from [qdrant.tech](https://qdrant.tech/documentation/install/)

**Backend:**

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp ../.env.example ../.env   # edit .env with API keys (GEMINI_API_KEY, etc.)
# From repo root, load .env then run (Windows: use set or a .env loader):
cd ..
export $(grep -v '^#' .env | xargs)
cd backend && PYTHONPATH=. python3 run.py
# Or: PYTHONPATH=. python3 run.py   (use python3 if python is not found)
# Or: PYTHONPATH=. flask --app app run --host=0.0.0.0 --port=5000
```

### 3. CLI (any IDE)

```bash
cd cli
pip install -e .
code-logger health
code-logger init
code-logger activate
code-logger answer-query "Where is authentication handled?"
code-logger summarize --collection repo_myproject
code-logger terminate   # delete collection
code-logger delete-logs  # remove local .code-logger dir
```

When the backend runs in **Docker**, use the CLI from the host; default `CODE_LOGGER_API_URL=http://localhost:5000` works.

| Command | Description |
|---------|-------------|
| `health` | Check API and Qdrant connectivity |
| `init` | Create vector collection for current repo |
| `activate` | Same as init; ensures logger is ready |
| `deactivate` | No-op (CLI has no daemon) |
| `terminate` | Delete the collection (terminate logger) |
| `delete-logs` | Remove local `.code-logger` directory |
| `analyze-diff` | Send a diff to the API |
| `answer-query` | Ask a question about the codebase |
| `summarize` / `summarize-codebase` | Get codebase summary |

Use the same commands from scripts or your IDE’s “run external tool” to integrate with any editor.

### 4. VSCode extension

```bash
cd extension
npm install
npm run compile
# In VSCode: Run > Run Extension (F5) or package and install .vsix
```

Then: **Code Logger: Initialize Logger** → **Activate Logger** → choose mode (Code / Structure / Full). Use **Answer Query** and **Summarize Codebase** from the command palette.

## Configuration

| Variable | Description |
|----------|-------------|
| `QDRANT_URL` | Qdrant URL (default `http://localhost:6333`; in Docker use `http://qdrant:6333`) |
| `GEMINI_API_KEY` | For embeddings (and optional LLM) |
| `GROQ_API_KEY` | For fast LLM summarization/answers |
| `CODE_LOGGER_API_URL` | Used by CLI/extension. **When backend runs in Docker**, use `http://localhost:5000` on the host so CLI/extension can reach the API. |

Extension settings (VSCode): `codeLogger.apiUrl`, `codeLogger.intervalSeconds`, `codeLogger.logDir`.

## API summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/health` | GET | Health check (includes Qdrant connectivity) |
| `/api/init-collection` | POST | Create empty vector collection for a codebase |
| `/api/analyze-diff` | POST | Send diff → embed → store → return summary |
| `/api/answer-query` | POST | Query → embed → retrieve → LLM answer |
| `/api/summarize-codebase` | GET/POST | Summarize codebase (architecture, modules, etc.) |
| `/api/delete-collection` | POST | Delete a collection by `collection_id` |
| `/api/terminate` | POST | Terminate logger (delete collection for codebase) |

## License

Use and modify as needed for your research or product. Attribution to the paper is appreciated.
