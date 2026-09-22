# LinguSim

> LinguSim doesn't just teach you a language. It puts you into situations where you actually
> have to use it, throws a curveball when you least expect it, and changes what you practice
> next based on how you handled it. Not a chatbot — a simulation engine you have to survive.

LinguSim is an adaptive, voice-based language simulation engine. Learners pick a real-world
mission (ordering food, a hotel check-in problem, ...) and have to talk their way through it
live. The conversation isn't a fixed script: partway through, it can throw in a scripted
complication — the item they ordered is sold out, the reservation isn't found — and the AI
reacts to it in character. Afterward, a Simulation Coach evaluates not just grammar and
vocabulary but whether the learner could recover when things didn't go as planned, and
recommends what to practice next.

## How It Works

LinguSim operates through a real-time, event-driven architecture that bridges the learner's browser with cloud AI services. Here is how the data flows during a session:

1. **Voice Streaming:** When a mission starts, the frontend captures audio from microphone and streams it directly to the backend over a WebSocket connection. 
2. **AI Voice Agent:** The backend acts as a relay, immediately forwarding audio to the AssemblyAI Voice Agent API. This cloud service handles Speech-to-Text, LLM reasoning (deciding what to say), and Text-to-Speech (generating a voice reply) all at once. The generated audio streams back through the backend to the browser.
3. **Dynamic Complications:** The backend tracks the conversation. Every few turns, it quietly injects a "complication" (e.g., "tell the learner their credit card was declined") directly into the AI Voice Agent's system prompt. The AI naturally weaves this into its very next spoken response.
4. **Tool-Calling and MCP:** If the learner don't understand a phrase or don't know how to say a word, the AI can give a hint. To prevent the AI from guessing or hallucinating translations, it is equipped with a specific tool. When the AI uses this tool, the backend routes the request to an in-process **MCP (Model Context Protocol) Server**. This MCP Server connects to a real external translation API (MyMemory API) to fetch the accurate translation and returns it to the AI, which then uses it to help the learner.
5. **Evaluation Agent:** When the learner ends the session, the live voice connection closes. The backend takes the full text transcript of the conversation and hands it to a separate Evaluator Agent (using AssemblyAI's LLM Gateway). This Evaluator runs its own loop, using internal tools to read past learner profile, analyze how well the learner handled the complications, and consult the scenario bank to recommend next mission.
6. **Feedback & Progression:** The final evaluation is saved to a PostgreSQL database, the learner profile is updated, and the results are sent back to the frontend to display personalized debrief.

## Running locally

### 1. Start Postgres

```bash
docker compose up -d postgres
```

Exposed on host port **5544**, not Postgres's usual 5432.
The backend still talks to it on the internal Docker network at
`postgres:5432` regardless; only the host-side port differs.

### 2. Backend

```bash
cd backend
uv sync --group dev
uv run uvicorn app.main:app --reload --port 8000
```

Copy `.env.example` to `.env` at the repo root and set `ASSEMBLYAI_API_KEY`. It also needs Postgres reachable (`localhost:5544` by default) — the
backend creates its tables on startup.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:3000`. It talks to the backend at `http://localhost:8000` /
`ws://localhost:8000` by default — override via `NEXT_PUBLIC_API_BASE_URL` /
`NEXT_PUBLIC_WS_BASE_URL` (see `frontend/.env.local.example`).

