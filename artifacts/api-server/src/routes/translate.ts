import { Router } from "express";

const router = Router();

function validateBody(body: unknown): { text: string; source: string; target: string } | null {
  if (!body || typeof body !== "object") return null;
  const { text, source, target } = body as Record<string, unknown>;
  if (typeof text !== "string" || !text.trim()) return null;
  if (typeof source !== "string" || !source.trim()) return null;
  if (typeof target !== "string" || !target.trim()) return null;
  return { text, source, target };
}

const OLLAMA_URL = process.env.OLLAMA_URL ?? "http://localhost:11434";
const MODEL_NAME = process.env.MODEL_NAME ?? "qwen2.5-coder:32b";

function buildSystemPrompt(source: string, target: string): string {
  const isEnToAr = source.includes("en") && target.includes("ar");
  const isArToEn = source.includes("ar") && target.includes("en");
  if (isEnToAr) {
    return "You are a professional live interpreter specializing in authentic modern Hijazi Arabic. " +
      "Translate English into natural spoken Hijazi Arabic suitable for respectful everyday and business conversations in western Saudi Arabia. " +
      "Preserve tone. Preserve intent. Never explain. Never answer questions. Never summarize. Never add notes. " +
      "Return ONLY the translated text.";
  } else if (isArToEn) {
    return "You are a professional live interpreter. " +
      "Translate authentic Hijazi Arabic into fluent professional English. " +
      "Preserve tone. Preserve meaning. Return ONLY the translated English. " +
      "Never explain. Never answer questions. Never add commentary.";
  }
  return `You are a professional live interpreter. Translate from ${source} to ${target}. ` +
    "Preserve tone and meaning exactly. Return ONLY the translated text. Never explain or add commentary.";
}

router.post("/translate", async (req, res) => {
  const validated = validateBody(req.body);
  if (!validated) {
    res.status(400).json({ error: "Invalid request" });
    return;
  }
  const { text, source, target } = validated;
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120000);
  try {
    const ollamaRes = await fetch(`${OLLAMA_URL}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: MODEL_NAME,
        stream: false,
        messages: [
          { role: "system", content: buildSystemPrompt(source, target) },
          { role: "user", content: text },
        ],
      }),
      signal: controller.signal,
    });
    if (!ollamaRes.ok) {
      res.status(502).json({ error: "Translation service error" });
      return;
    }
    const data = await ollamaRes.json() as { message?: { content?: string } };
    const translation = data.message?.content?.trim();
    if (!translation) {
      res.status(502).json({ error: "Empty response" });
      return;
    }
    res.json({ translation });
  } catch (err: unknown) {
    if (err instanceof Error && err.name === "AbortError") {
      res.status(504).json({ error: "Translation timed out" });
    } else {
      res.status(500).json({ error: "Unexpected error" });
    }
  } finally {
    clearTimeout(timeout);
  }
});

export default router;
