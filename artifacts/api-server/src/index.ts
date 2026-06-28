import express from "express";
import cors from "cors";
import { fileURLToPath } from "node:url";
import path from "node:path";
import fs from "node:fs";
import apiRouter from "./routes/index";

const app = express();

app.use(cors());
app.use(express.json({ limit: "1mb" }));

// All application routes live under /api.
app.use("/api", apiRouter);

// Optionally serve the built frontend so the whole app runs as one origin on a
// single port (clone → build → start → open one link). In dev you can still run
// the Vite server separately; this only kicks in when web/dist exists.
const dirname = path.dirname(fileURLToPath(import.meta.url));
const webDist = process.env.WEB_DIST ?? path.resolve(dirname, "../../web/dist");
const serveWeb = fs.existsSync(path.join(webDist, "index.html"));
if (serveWeb) {
  app.use(express.static(webDist));
  // SPA fallback. Express 5 routes plain "*" differently, so use a final
  // catch-all middleware for non-API GET requests instead of app.get("*").
  app.use((req, res, next) => {
    if (req.method !== "GET" || req.path.startsWith("/api")) {
      next();
      return;
    }
    res.sendFile(path.join(webDist, "index.html"));
  });
}

const PORT = Number(process.env.PORT ?? 80);
const OLLAMA_URL = process.env.OLLAMA_URL ?? "http://localhost:11434";
const MODEL_NAME = process.env.MODEL_NAME ?? "qwen2.5-coder:32b";

// On boot, probe Ollama so connectivity problems show up immediately in the
// server log instead of only when a translation fails.
async function probeOllama(): Promise<void> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const res = await fetch(`${OLLAMA_URL}/api/tags`, { signal: controller.signal });
    if (!res.ok) {
      console.warn(`  Ollama    = reachable but /api/tags returned ${res.status}`);
      return;
    }
    const data = (await res.json()) as { models?: Array<{ name?: string }> };
    const names = (data.models ?? []).map((m) => m.name ?? "").filter(Boolean);
    const hasModel = names.some((n) => n === MODEL_NAME || n.startsWith(`${MODEL_NAME.split(":")[0]}:`));
    console.log(`  Ollama    = OK (${names.length} model(s) available)`);
    if (!hasModel) {
      console.warn(`  ⚠ Model "${MODEL_NAME}" not found. Run: ollama pull ${MODEL_NAME}`);
    }
  } catch (err: unknown) {
    const cause =
      err instanceof Error && err.cause && typeof err.cause === "object"
        ? (err.cause as { code?: string }).code
        : undefined;
    const detail = cause ?? (err instanceof Error ? err.name : "unknown error");
    console.error(`  ⚠ Ollama  = NOT reachable at ${OLLAMA_URL} (${detail}).`);
    console.error(`    Translations will return 500 until this is fixed. Checks:`);
    console.error(`      • Is Ollama running on THIS machine?  curl ${OLLAMA_URL}/api/tags`);
    console.error(`      • If using WSL, 127.0.0.1 is the WSL VM, not the Windows host.`);
    console.error(`      • Try http://127.0.0.1:11434 (IPv4) instead of localhost.`);
  } finally {
    clearTimeout(timeout);
  }
}

app.listen(PORT, () => {
  console.log(`ASSISTRAN listening on :${PORT}`);
  console.log(`  OLLAMA_URL = ${OLLAMA_URL}${process.env.OLLAMA_URL ? "" : " (default)"}`);
  console.log(`  MODEL_NAME = ${MODEL_NAME}${process.env.MODEL_NAME ? "" : " (default)"}`);
  if (serveWeb) {
    console.log(`  Web UI    = serving ${webDist}`);
    console.log(`  → Open http://localhost:${PORT} in Chrome or Edge`);
  } else {
    console.log("  Web UI    = not built (API only). Run the web build to serve the UI here.");
  }
  void probeOllama();
});
