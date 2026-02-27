import * as vscode from "vscode";
import * as path from "path";
import * as fs from "fs";

const LOG_DIR = ".code-logger";
type LoggerMode = "none" | "code" | "structure" | "full";

let state: {
  active: boolean;
  mode: LoggerMode;
  intervalHandle: ReturnType<typeof setInterval> | null;
  collectionId: string;
  fileHashes: Map<string, string>;
  lastTree: string;
} = {
  active: false,
  mode: "none",
  intervalHandle: null,
  collectionId: "",
  fileHashes: new Map(),
  lastTree: "",
};

function getConfig() {
  const cfg = vscode.workspace.getConfiguration("codeLogger");
  return {
    apiUrl: (cfg.get("apiUrl") as string) || "http://localhost:5000",
    intervalSeconds: (cfg.get("intervalSeconds") as number) || 60,
    logDir: (cfg.get("logDir") as string) || LOG_DIR,
  };
}

function getWorkspaceRoot(): string | null {
  const folders = vscode.workspace.workspaceFolders;
  if (!folders || folders.length === 0) return null;
  return folders[0].uri.fsPath;
}

function getCollectionId(): string {
  const root = getWorkspaceRoot();
  if (!root) return "default_repo";
  const name = path.basename(root).replace(/\s/g, "_").slice(0, 64);
  return `repo_${name}`;
}

function logDirPath(): string {
  const root = getWorkspaceRoot();
  if (!root) return path.join(process.cwd(), LOG_DIR);
  return path.join(root, getConfig().logDir);
}

function ensureLogDir(): string {
  const dir = logDirPath();
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  return dir;
}

async function apiGet(relPath: string): Promise<unknown> {
  const { apiUrl } = getConfig();
  const res = await fetch(`${apiUrl}${relPath}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

async function apiPost(relPath: string, body: object): Promise<unknown> {
  const { apiUrl } = getConfig();
  const res = await fetch(`${apiUrl}${relPath}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

function simpleHash(s: string): string {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h << 5) - h + s.charCodeAt(i);
  return (h >>> 0).toString(16);
}

function dirTree(dir: string, prefix = ""): string {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  const lines: string[] = [];
  const skip = new Set(["node_modules", ".git", ".code-logger", "__pycache__", ".venv", "venv"]);
  for (const e of entries.sort((a, b) => a.name.localeCompare(b.name))) {
    if (skip.has(e.name)) continue;
    const full = path.join(dir, e.name);
    const line = prefix + (e.isDirectory() ? `${e.name}/` : e.name);
    lines.push(line);
    if (e.isDirectory()) lines.push(dirTree(full, prefix + "  "));
  }
  return lines.join("\n");
}

function recordDirectoryTree() {
  const root = getWorkspaceRoot();
  if (!root) return;
  const tree = dirTree(root);
  if (tree === state.lastTree) return;
  state.lastTree = tree;
  const dir = ensureLogDir();
  const file = path.join(dir, "structure.log");
  const header = `\n--- ${new Date().toISOString()} ---\n`;
  fs.appendFileSync(file, header + tree + "\n");
}

async function collectDiffs(): Promise<Array<{ filePath: string; old: string; new: string }>> {
  const root = getWorkspaceRoot();
  if (!root) return [];
  const diffs: Array<{ filePath: string; old: string; new: string }> = [];
  const ext = [".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".rs", ".c", ".cpp", ".h", ".cs", ".rb", ".php", ".md", ".json"];
  const rootDir: string = root;
  function walk(d: string) {
    const entries = fs.readdirSync(d, { withFileTypes: true });
    const skip = new Set(["node_modules", ".git", ".code-logger", "__pycache__", ".venv", "venv"]);
    for (const e of entries) {
      if (skip.has(e.name)) continue;
      const full = path.join(d, e.name);
      if (e.isDirectory()) walk(full);
      else if (ext.some((x) => e.name.endsWith(x))) {
        const rel = path.relative(rootDir, full);
        let content = "";
        try {
          content = fs.readFileSync(full, "utf-8");
        } catch {}
        const hash = simpleHash(content);
        const prev = state.fileHashes.get(rel);
        if (prev !== undefined && prev !== hash) {
          diffs.push({ filePath: rel, old: "(previous)", new: content.slice(0, 8000) });
        }
        state.fileHashes.set(rel, hash);
      }
    }
  }
  walk(root);
  return diffs;
}

async function runAnalyzeDiff() {
  const root = getWorkspaceRoot();
  if (!root) return;
  const cid = state.collectionId || getCollectionId();
  const diffs = await collectDiffs();
  const dir = ensureLogDir();
  const codeLog = path.join(dir, "code_summary.log");
  for (const d of diffs) {
    try {
      const res = await apiPost("/api/analyze-diff", {
        collection_id: cid,
        file_path: d.filePath,
        diff: { old: d.old, new: d.new },
      }) as { summary?: string };
      const line = `[${new Date().toISOString()}] ${d.filePath}: ${(res.summary || "").trim()}\n`;
      fs.appendFileSync(codeLog, line);
    } catch (e) {
      fs.appendFileSync(codeLog, `[${new Date().toISOString()}] ${d.filePath}: ERROR ${e}\n`);
    }
  }
  if (state.mode === "structure" || state.mode === "full") recordDirectoryTree();
}

function startInterval() {
  if (state.intervalHandle) return;
  const { intervalSeconds } = getConfig();
  state.intervalHandle = setInterval(() => {
    if (state.mode === "code" || state.mode === "full") runAnalyzeDiff();
    else if (state.mode === "structure") recordDirectoryTree();
  }, intervalSeconds * 1000);
}

function stopInterval() {
  if (state.intervalHandle) {
    clearInterval(state.intervalHandle);
    state.intervalHandle = null;
  }
}

export async function activate(context: vscode.ExtensionContext) {
  state.collectionId = getCollectionId();

  context.subscriptions.push(
    vscode.commands.registerCommand("codeLogger.activate", async () => {
      state.active = true;
      state.collectionId = getCollectionId();
      if (state.mode === "none") state.mode = "full";
      try {
        await apiPost("/api/init-collection", { collection_id: state.collectionId });
      } catch (e) {
        vscode.window.showWarningMessage("Code Logger: API unreachable. Start backend and Qdrant.");
      }
      ensureLogDir();
      recordDirectoryTree();
      startInterval();
      vscode.window.showInformationMessage("Code Logger activated.");
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codeLogger.deactivate", () => {
      state.active = false;
      stopInterval();
      vscode.window.showInformationMessage("Code Logger deactivated.");
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codeLogger.initialize", async () => {
      state.collectionId = getCollectionId();
      ensureLogDir();
      const root = getWorkspaceRoot();
      if (root) {
        state.lastTree = dirTree(root);
        const dir = ensureLogDir();
        fs.writeFileSync(path.join(dir, "structure.log"), state.lastTree + "\n");
      }
      try {
        await apiPost("/api/init-collection", { collection_id: state.collectionId });
        vscode.window.showInformationMessage("Code Logger initialized.");
      } catch (e) {
        vscode.window.showErrorMessage("Code Logger: Failed to init collection. " + String(e));
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codeLogger.terminate", () => {
      state.active = false;
      state.mode = "none";
      stopInterval();
      state.fileHashes.clear();
      vscode.window.showInformationMessage("Code Logger terminated.");
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codeLogger.deleteLogs", () => {
      const dir = logDirPath();
      if (fs.existsSync(dir)) {
        fs.rmSync(dir, { recursive: true });
        vscode.window.showInformationMessage("Code Logger: Logs deleted.");
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codeLogger.deactivateMode", () => {
      state.mode = "none";
      stopInterval();
      vscode.window.showInformationMessage("Code Logger: Mode deactivated.");
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codeLogger.setModeCode", () => {
      state.mode = "code";
      if (state.active) startInterval();
      vscode.window.showInformationMessage("Code Logger: Mode set to Code Logger.");
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codeLogger.setModeStructure", () => {
      state.mode = "structure";
      if (state.active) startInterval();
      vscode.window.showInformationMessage("Code Logger: Mode set to Structure Logger.");
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codeLogger.setModeFull", () => {
      state.mode = "full";
      if (state.active) startInterval();
      vscode.window.showInformationMessage("Code Logger: Mode set to Full Code Logger.");
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codeLogger.answerQuery", async () => {
      const query = await vscode.window.showInputBox({ prompt: "Ask about your codebase" });
      if (!query) return;
      try {
        const res = await apiPost("/api/answer-query", {
          collection_id: state.collectionId || getCollectionId(),
          query,
          top_k: 30,
        }) as { answer?: string; file_path?: string };
        const msg = (res.answer || "").trim();
        const fp = res.file_path ? ` (${res.file_path})` : "";
        vscode.window.showInformationMessage(msg.slice(0, 200) + (msg.length > 200 ? "…" : "") + fp);
        const doc = await vscode.workspace.openTextDocument({ content: msg, language: "markdown" });
        await vscode.window.showTextDocument(doc);
      } catch (e) {
        vscode.window.showErrorMessage("Code Logger: " + String(e));
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand("codeLogger.summarizeCodebase", async () => {
      try {
        const res = await apiPost("/api/summarize-codebase", {
          collection_id: state.collectionId || getCollectionId(),
        }) as { summary?: { architecture?: string; key_modules?: string[] }; summary_file?: string };
        const dir = ensureLogDir();
        const name = res.summary_file || "summary.md";
        const file = path.join(dir, name);
        const text = [
          "# Codebase Summary",
          "",
          "## Architecture",
          res.summary?.architecture || "",
          "",
          "## Key modules",
          ...(res.summary?.key_modules || []).map((m) => `- ${m}`),
        ].join("\n");
        fs.writeFileSync(file, text);
        const doc = await vscode.workspace.openTextDocument(file);
        await vscode.window.showTextDocument(doc);
        vscode.window.showInformationMessage("Code Logger: Summary saved to " + name);
      } catch (e) {
        vscode.window.showErrorMessage("Code Logger: " + String(e));
      }
    })
  );
}

export function deactivate() {
  stopInterval();
}
