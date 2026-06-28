# ASSISTRAN — Two-Way AI Push-To-Talk Speech Interpreter

ASSISTRAN is a **push-to-talk AI interpreter** — not a chatbot. It works like a
professional live walkie-talkie interpreter between two people:

- **Person A** holds the **English** button → speaks → releases
  → ASSISTRAN translates to **Hijazi Arabic** and speaks it aloud.
- **Person B** holds the **Arabic** button → speaks → releases
  → ASSISTRAN translates to **English** and speaks it aloud.

The mic **never** continuously listens. Recording only happens while a button is
held.

## Architecture

```
Browser (React frontend)
  ↓  POST /api/translate  { text, source, target }
Express API server (api-server)
  ↓  POST /api/chat
Ollama server (external at OLLAMA_URL)
  ↓
qwen2.5-coder:32b
```

The proxy routes `/api` to the Express server and `/` to the Vite frontend. The
frontend uses relative fetch URLs (`/api/translate`) — never hardcoded ports.
The browser **never** talks to Ollama directly.

## Tech stack

**Frontend** (`web/`)
- React 19 + Vite (TypeScript)
- Tailwind CSS v4
- Framer Motion (animations)
- lucide-react (icons)
- Web Speech API (`SpeechRecognition`) for capture, `SpeechSynthesis` for playback
- TanStack Query for the generated-style `useTranslate` hook

**Backend** (`api-server/`)
- Node.js + Express 5 (TypeScript)
- Built with esbuild
- Calls Ollama only from the server

**API client** (`packages/api-client-react/`)
- `@workspace/api-client-react` — typed client + `useTranslate` mutation hook,
  shaped from `api-server/openapi.yaml`.

## Workspace layout

```
artifacts/
├── package.json                  # npm workspaces root
├── api-server/                   # Express 5 backend
│   ├── openapi.yaml              # API spec (POST /translate)
│   └── src/routes/translate.ts   # translation route
├── packages/api-client-react/    # @workspace/api-client-react (useTranslate)
└── web/                          # React + Vite frontend
    └── src/Interpreter.tsx       # the single-page PTT interpreter UI
```

## Environment variables

Set these for the **api-server** (e.g. Replit secrets, or a `.env` — see
`.env.example`):

| Variable     | Value                                                                 |
| ------------ | --------------------------------------------------------------------- |
| `OLLAMA_URL` | `http://127.0.0.1:11434` if Ollama is on the **same** machine, or `http://<host>:11434` for a remote one |
| `MODEL_NAME` | `qwen2.5-coder:32b`                                                    |
| `PORT`       | `8080` via `run.sh` (the server itself defaults to `80`)              |

> **Important:** Ollama binds to `127.0.0.1` by default. If the app runs on the
> same machine as Ollama, use `http://127.0.0.1:11434` — pointing `OLLAMA_URL`
> at the machine's **public IP** will get `ECONNREFUSED` (→ 500), because Ollama
> isn't listening on the public interface.

## Quickest start — one command, one link

**macOS / Linux / Git Bash:**
```bash
cd artifacts
./run.sh
```

**Windows (cmd or double-click):**
```cmd
cd artifacts
run.cmd
```

> On Windows **cmd/PowerShell, do not use the bash form** `OLLAMA_URL=... ./run.sh`
> — it sets nothing and won't run the shell script. Use `run.cmd` (which sets
> sensible defaults), or set vars first with `set OLLAMA_URL=http://127.0.0.1:11434`.
> Use `127.0.0.1`, not `localhost`: on Windows `localhost` can resolve to IPv6
> `::1` while Ollama listens on IPv4, which causes a 500.

`run.sh` / `run.cmd` install deps, build the frontend + backend, and start a
**single server that serves both the UI and the API on one port**. It prints the
link:

```
>>> Open this link in Chrome or Edge:
>>> http://localhost:8080
```

Override the defaults via env vars:

```bash
PORT=3000 OLLAMA_URL=http://my-ollama:11434 ./run.sh
```

> The host you run this on must be able to reach your Ollama server. Web Speech
> API capture/playback runs in the browser, so **open the link in Chrome or
> Edge** (Safari/Firefox aren't supported).

## Dev mode (two servers, hot reload)

```bash
cd artifacts
npm install

# Backend on :8080, frontend on :5173 (Vite proxies /api -> backend):
PORT=8080 npm run dev:api
# in another terminal:
API_TARGET=http://localhost:8080 npm run dev:web
# open http://localhost:5173
```

The Vite dev server proxies `/api` to the api-server, so relative fetch calls
work without hardcoding ports.

### Manual production build

```bash
npm run build      # builds api-server -> dist/ and web -> dist/
npm run start      # single server serves the API + the built UI on $PORT (default 80)
```

When `web/dist` exists, the api-server automatically serves it (with SPA
fallback) on the same port as the API — no separate static host or proxy needed.
Set `WEB_DIST` to serve a build from a custom location.

## Verifying

1. Confirm Ollama has the model:
   ```bash
   curl http://46.152.253.223:11434/api/tags   # should list qwen2.5-coder:32b
   ```
2. Test the translate endpoint (adjust the port to match how you started it):
   ```bash
   curl -X POST http://localhost:8080/api/translate \
     -H "Content-Type: application/json" \
     -d '{"text":"hello","source":"en-US","target":"ar-SA"}'
   # Expected: {"translation":"مرحباً"} in ~15 seconds
   ```
3. Open the app in **Chrome or Edge** (required for the Web Speech API). Hold the
   English button, speak, release — it should translate and speak aloud.

> Note: `qwen2.5-coder:32b` takes ~15 seconds to respond. The 120s server-side
> timeout is intentional.
