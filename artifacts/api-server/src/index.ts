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

app.listen(PORT, () => {
  console.log(`ASSISTRAN listening on :${PORT}`);
  console.log(`  OLLAMA_URL = ${process.env.OLLAMA_URL ?? "http://localhost:11434 (default)"}`);
  console.log(`  MODEL_NAME = ${process.env.MODEL_NAME ?? "qwen2.5-coder:32b (default)"}`);
  if (serveWeb) {
    console.log(`  Web UI    = serving ${webDist}`);
    console.log(`  → Open http://localhost:${PORT} in Chrome or Edge`);
  } else {
    console.log("  Web UI    = not built (API only). Run the web build to serve the UI here.");
  }
});
