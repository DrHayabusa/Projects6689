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

| Variable     | Value                              |
| ------------ | ---------------------------------- |
| `OLLAMA_URL` | `http://46.152.253.223:11434`      |
| `MODEL_NAME` | `qwen2.5-coder:32b`                |
| `PORT`       | `80` (optional, defaults to 80)    |

## Getting started

```bash
cd artifacts
npm install

# Run backend (port 80) and frontend (port 5173) together:
npm run dev

# …or individually:
npm run dev:api
npm run dev:web
```

The Vite dev server proxies `/api` to the api-server, so relative fetch calls
work without hardcoding ports.

### Production build

```bash
npm run build      # builds api-server -> dist/ and web -> dist/
npm run start      # starts the api-server
```

## Verifying

1. Confirm Ollama has the model:
   ```bash
   curl http://46.152.253.223:11434/api/tags   # should list qwen2.5-coder:32b
   ```
2. Test the translate endpoint:
   ```bash
   curl -X POST http://localhost:80/api/translate \
     -H "Content-Type: application/json" \
     -d '{"text":"hello","source":"en-US","target":"ar-SA"}'
   # Expected: {"translation":"مرحباً"} in ~15 seconds
   ```
3. Open the app in **Chrome or Edge** (required for the Web Speech API). Hold the
   English button, speak, release — it should translate and speak aloud.

> Note: `qwen2.5-coder:32b` takes ~15 seconds to respond. The 120s server-side
> timeout is intentional.
