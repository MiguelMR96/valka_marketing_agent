# Valka Agent — v1 demo

> **V1 DEMO IMPLEMENTATION** — built for a deadline (2026-09-07 night, demo
> 2026-09-08 morning), not yet understood by Miguel. See the build spec
> Definition of Done. `graph.py`/`nodes/`/interrupt logic get rebuilt by hand
> by Sunday 2026-09-13 — this is a working reference, not the final code.

## ⚠️ Placeholder knowledge base

`data/kb/*.md` are **invented placeholder products**, not real Valka
content — the real scrape wasn't available at build time. See
`data/kb/README_PLACEHOLDER.md`. **Swap these before showing anyone who
knows the real product line.**

## Setup

Python 3.12, managed with [`uv`](https://docs.astral.sh/uv/) (no venv/pip
needed — uv manages its own).

```bash
make install       # uv sync --extra dev
cp .env.example .env
# fill in GROQ_API_KEY / GEMINI_API_KEY, or set MOCK_LLM=1 for offline mode
```

## Running things

**One command, cold machine:**

```bash
./scripts/demo.sh   # installs deps, runs unit tests, runs the smoke script
```

This is the primary documented entry point — it only needs `uv` (installs
itself if missing) and doesn't depend on `make` being present, which it
wasn't on the machine this was built on. If you do have `make`, `make demo`
wraps the same script; `make install` / `make test` / `make smoke` run the
individual steps.

`scripts/smoke.py` forces `MOCK_LLM=1` unless you already set it, so it
always runs offline by default. Run `MOCK_LLM=0 ./scripts/demo.sh` to hit
real Groq/Gemini instead.

Missing API keys with `MOCK_LLM` unset fail immediately at startup with a
clear error — never mid-conversation.

## Status (Phase 3 of 4 complete)

- [x] `state.py`, `graph.py`, six nodes, feeding calculator (unit-tested),
      SQLite checkpointer, LLM wrapper (Groq → Gemini → mock),
      `scripts/smoke.py` covering the three demo conversations
- [x] Post-demo addition: `product_recommendation` intent + a 7th node,
      `gather_recommendation_info`, mirroring `gather_transition_info`'s
      loop-back shape. Added state.py fields (`recommendation_data`), which
      the original spec marked hands-off for this pass -- flagging that
      explicitly since it's the one file meant to stay verbatim.
- [x] Phase 2: `interrupt()` on the escalate path + resume across restarts —
      `scripts/smoke.py`'s 4th conversation proves this across a real OS
      process boundary (two separate `python -c` subprocesses sharing only
      a sqlite file on disk), not just a fresh object in the same script
- [x] Phase 3: FastAPI + SSE (`valka_agent/api/main.py`), React/Vite
      frontend (`frontend/`, text chat only). Escalation surfaces as a
      real human-in-the-loop control: a banner + reply box that calls
      `/api/resume`, not just a passive indicator.
- [ ] Phase 4: voice, behind `VITE_ENABLE_VOICE` flag

### Running the live demo (not just the smoke script)

Two terminals for now (see Phase 3 notes below for why not one):

```bash
uv run uvicorn valka_agent.api.main:app --port 8000   # backend
cd frontend && npm install && npm run dev              # frontend, :5173
```

Needs `GROQ_API_KEY` (or `GEMINI_API_KEY`) in `.env`, or `MOCK_LLM=1`, same
startup check as the smoke script. **Note:** the build spec's original
model choice, `llama-3.3-70b-versatile`, is no longer available on Groq's
free tier (confirmed against the live API on 2026-09-08) — this now uses
`openai/gpt-oss-20b`. See the comment in `llm.py` for why 20b over 120b.

## Deploying (Render, free tier)

`render.yaml` is a Render Blueprint that deploys both services in one step:
a free Python web service for the backend and a free static site for the
frontend. In the Render dashboard: **New -> Blueprint**, point it at this
repo, and it reads `render.yaml` automatically.

Render will prompt for `GROQ_API_KEY` during blueprint creation (marked
`sync: false` in `render.yaml` so it's never committed) — paste your key
there. Everything else (`MOCK_LLM`, `ALLOWED_ORIGINS`, `VITE_API_BASE`) is
already set in the blueprint.

**If the deployed frontend can't reach the backend** (chat just hangs):
the blueprint assumes Render grants the exact subdomains
`valka-agent-backend.onrender.com` / `valka-agent-frontend.onrender.com`.
That only fails if those names are already taken by someone else on
Render, in which case check the real URLs in the dashboard and manually
update `ALLOWED_ORIGINS` (on the backend service) and `VITE_API_BASE` (on
the frontend service) to match, then trigger a manual redeploy of each.

**Known limitations of the free tier**, not bugs:
- The backend sleeps after 15 min idle; the next request takes 30-60s to
  wake it back up.
- The backend's disk is ephemeral — `checkpoints.sqlite` resets on every
  sleep/wake or redeploy, so conversation history (including any
  in-progress feeding-transition/recommendation flow, or an escalated
  thread waiting to be resumed) does not survive that. Fine for someone
  trying the demo fresh; not a real memory store.

## Design notes for the rebuild pass

- **Seven nodes** (six original + `gather_recommendation_info`) = one per
  intent (`product_question`, `gather_transition_info`,
  `gather_recommendation_info`, `order_status`, `escalate`, `smalltalk`) +
  `classify_intent`. The original six were inferred from the addendum's
  demo script and `state.py`'s intent enum, since the original build spec's
  node table wasn't available at build time — verify against the real spec
  before treating this as gospel.
- **The gather_transition_info "loop-back"** is realized at the graph's
  *entry point*, not as a same-turn self-edge: `_route_from_entry` in
  `graph.py` checks whether the previous turn's `intent` was
  `feeding_transition` and fields are still missing, and if so routes
  straight back into `gather_transition_info` next turn, skipping
  re-classification. A same-turn self-loop isn't meaningful here since one
  `graph.invoke()` only ever sees one new human message.
- **Only two nodes call an LLM**: `classify_intent` and `product_question`.
  `order_status`, `smalltalk`, and the feeding schedule itself are fully
  templated/deterministic — kept that way on purpose to shrink the demo's
  network dependency surface. Revisit this if the real spec calls for LLM
  involvement elsewhere.
- **The API's chat/resume endpoints are GET, not POST**, so the frontend
  can use the browser's native `EventSource` for SSE instead of hand-rolling
  a parser over `fetch()`'s streaming body — `EventSource` can't carry a
  POST body, so the turn's text travels as a query param. Fine for a local
  demo; would need to change for anything public-facing.
- **Two terminals for the live demo** (`uvicorn` + `vite dev`), unlike
  `scripts/demo.sh`'s one-command smoke path — no time tonight to write a
  process-supervisor script that backgrounds one and traps the other's
  Ctrl-C. `scripts/demo.sh` remains the one-command entry point for the
  automated checks; this is only for driving the UI by hand.
- **`scripts/smoke.py` uses its own throwaway sqlite db**, created fresh and
  deleted on every run — not the real `DB_PATH`. The demo conversations use
  hardcoded `thread_id`s, and the checkpointer persists state across process
  runs by design (that's the whole point of Phase 2); pointing the smoke
  script at the same file the live demo/API would use meant a second run
  picked up a previous run's finished `transition_data` and misrouted
  turns 2-3. Conversation 4 (escalate/interrupt) gets its own separate
  throwaway db per invocation for the same reason.
- **Field extraction in `gather_transition_info`** is regex/keyword-based,
  not LLM-based — slot values feed real arithmetic, so predictability beat
  flexibility for tonight. It gates product/sensitivity extraction on
  weight_lbs and current_food already being known, otherwise an opening
  message like "I want to switch my dog to raw" gets misread as a product
  name (this was a real bug caught during the Phase 1 smoke run — see git
  history).
