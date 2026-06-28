import express from "express";
import cors from "cors";
import apiRouter from "./routes/index";

const app = express();

app.use(cors());
app.use(express.json({ limit: "1mb" }));

// All application routes live under /api. The proxy forwards /api here and
// serves the Vite frontend on /.
app.use("/api", apiRouter);

const PORT = Number(process.env.PORT ?? 80);

app.listen(PORT, () => {
  console.log(`ASSISTRAN api-server listening on :${PORT}`);
  console.log(`  OLLAMA_URL = ${process.env.OLLAMA_URL ?? "http://localhost:11434 (default)"}`);
  console.log(`  MODEL_NAME = ${process.env.MODEL_NAME ?? "qwen2.5-coder:32b (default)"}`);
});
