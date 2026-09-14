# Valka Agent — v1 demo

> **V1 DEMO IMPLEMENTATION** — built for a deadline (2026-09-07 night, demo
> 2026-09-08 morning). On 2026-09-13, `state.py`/`calculator.py`/`graph.py`/
> `nodes/` were rebuilt by hand against `Brief_Estrategico_Valka_IA-1.pdf`
> (the real Valka brand/product brief): the feeding model changed from a
> one-time transition-to-100% schedule to the brief's actual sustained
> 25/50/75/100% blend model, and the whole conversational layer (prompts,
> templates, field extraction) became bilingual (English/Spanish). Nutrition
> percentages are still **sourced placeholders** (see `calculator.py`'s
> docstring for citations), not approved Valka/vet numbers — pending
> verification and family/vet sign-off before production use.

## ⚠️ Knowledge base: real data, pending approval

`data/kb/*.md` now holds real proposed Valka product/pricing/promo data
(2026-09-14), replacing the earlier invented placeholders — but it's not
yet formally approved (unchecked approval boxes in the source documents).
See `data/kb/README_PLACEHOLDER.md` for what's real vs. still pending, and
`CLAUDE.md` for the brand rules the bot must never violate (never surface
BJ's internal pricing, never imply Valka/BJ's products are identical).

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

- [x] `state.py`, `graph.py`, seven nodes (`classify_intent`,
      `product_question`, `gather_feeding_plan_info`,
      `gather_recommendation_info`, `order_status`, `escalate`,
      `smalltalk`), feeding-plan calculator (unit-tested), SQLite
      checkpointer, LLM wrapper (Groq → Gemini → mock),
      `scripts/smoke.py` covering six demo conversations (incl. one in
      Spanish)
- [x] Post-demo addition: `product_recommendation` intent + a 7th node,
      `gather_recommendation_info`, mirroring `gather_feeding_plan_info`'s
      loop-back shape. Added state.py fields (`recommendation_data`).
- [x] Phase 2: `interrupt()` on the escalate path + resume across restarts —
      `scripts/smoke.py`'s 4th conversation proves this across a real OS
      process boundary (two separate `python -c` subprocesses sharing only
      a sqlite file on disk), not just a fresh object in the same script
- [x] Phase 3: FastAPI + SSE (`valka_agent/api/main.py`), React/Vite
      frontend (`frontend/`, text chat only). Escalation surfaces as a
      real human-in-the-loop control: a banner + reply box that calls
      `/api/resume`, not just a passive indicator.
- [x] 2026-09-13 rebuild: bilingual (English/Spanish) prompts, templates,
      and field extraction throughout; feeding calculator rebuilt around
      the brief's sustained 25/50/75/100% Valka/kibble blend model instead
      of a one-time transition-to-100% schedule.
- [x] 2026-09-14 live-test fixes: migrated off the fully-deprecated
      `google-generativeai` SDK/retired `gemini-1.5-flash` to `google-genai`/
      `gemini-3.6-flash`; added embeddings-based KB search (RAG) with
      keyword-overlap as the offline/failure fallback; `_chat()` now treats
      an empty completion as a failure (was silently returned as-is,
      skipping every fallback); LLM provider order flipped **back** to
      Groq-primary/Gemini-fallback after live testing showed
      `gemini-3.6-flash`'s free tier is only 20 requests/day against
      Groq's ~1000/day (confirmed via Groq's live rate-limit headers and a
      web search, not just assumed -- see llm.py's module docstring for
      the full back-and-forth on this).
- [ ] Phase 4: voice, behind `VITE_ENABLE_VOICE` flag
- [ ] Not yet started (later brief phases): multi-dog profiles/persistence,
      reminders/subscriptions, breeder/professional panel, real (non-
      placeholder) nutrition/pricing/KB content

### Running the live demo (not just the smoke script)

Two terminals for now (see Phase 3 notes below for why not one):

```bash
uv run uvicorn valka_agent.api.main:app --port 8000   # backend
cd frontend && npm install && npm run dev              # frontend, :5173
```

Needs `GROQ_API_KEY` (or `GEMINI_API_KEY`) in `.env`, or `MOCK_LLM=1`, same
startup check as the smoke script. Groq is tried first (1000 requests/day
free tier, confirmed live), Gemini is the fallback (`gemini-3.6-flash`'s
free tier is only 20 requests/day -- see llm.py's module docstring for how
this order got flipped twice). **Note:** the build spec's original model
choice, `llama-3.3-70b-versatile`, is no longer available on Groq's free
tier (confirmed against the live API on 2026-09-08) — Groq now uses
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
  in-progress feeding-plan/recommendation flow, or an escalated
  thread waiting to be resumed) does not survive that. Fine for someone
  trying the demo fresh; not a real memory store.

## Design notes for the rebuild pass

- **Seven nodes** (six original + `gather_recommendation_info`) = one per
  intent (`product_question`, `gather_feeding_plan_info`,
  `gather_recommendation_info`, `order_status`, `escalate`, `smalltalk`) +
  `classify_intent`.
- **The `gather_feeding_plan_info`/`gather_recommendation_info` "loop-back"**
  is realized at the graph's *entry point*, not as a same-turn self-edge:
  `_route_from_entry` in `graph.py` checks whether the previous turn's
  `intent` was still mid-collection (fields missing) AND the new message
  actually extracted something toward a missing field, and if so routes
  straight back into the gather node next turn, skipping re-classification.
  If the new message doesn't look like an answer (a topic change, an
  unrelated question), it falls through to `classify_intent` instead — see
  the comment in `_route_from_entry` for the bug this specifically fixes
  (a gather flow that couldn't be escaped once started).
- **The feeding-plan model is a sustained blend ratio**, not a one-time
  transition: the customer picks and stays at 25/50/75/100% Valka mixed
  with kibble (per `Brief_Estrategico_Valka_IA-1.pdf`'s "Modelo flexible de
  incorporación"). See `calculator.py`'s docstring for the full model and
  for citations behind the placeholder nutrition percentages — these are
  NOT approved Valka/vet numbers yet.
- **Bilingual (English/Spanish) throughout**: `nodes/_helpers.py`'s
  `detect_language`/`resolve_language` pick and stick to a language per
  thread using a deterministic keyword heuristic (works under `MOCK_LLM=1`
  too); every templated node response has EN/ES variants, and the two
  LLM-backed nodes pass an explicit language instruction to the model
  rather than letting it guess. The KB docs themselves (`data/kb/*.md`) are
  still English-only placeholder content — `kb.py`'s synonym map and
  browse-all pattern bridge common Spanish queries onto them in the
  meantime, but real bilingual KB content is still pending.
- **Only two nodes call an LLM**: `classify_intent` and
  `product_question`/`gather_recommendation_info`. `order_status`,
  `smalltalk`, and the feeding-plan calculation itself are fully
  templated/deterministic — kept that way on purpose to shrink the demo's
  network dependency surface.
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
  picked up a previous run's finished `feeding_plan_data` and misrouted
  turns 2-3. Conversation 4 (escalate/interrupt) gets its own separate
  throwaway db per invocation for the same reason.
- **Field extraction in `gather_feeding_plan_info`** is regex/keyword-based,
  not LLM-based — slot values feed real arithmetic, so predictability beat
  flexibility. It gates product/percent extraction on the first five fields
  (weight, dog count, life stage, activity, body condition) already being
  known, otherwise an opening message like "I want to start feeding my dog
  raw" gets misread as a product name or blend percentage (this class of
  bug was caught during the original build's smoke run — see git history).
  A `life_stage` of `pregnant_lactating` short-circuits to a safe
  human/vet-referral message instead of computing anything — the brief is
  explicit that this needs pre-approved rules the app doesn't have.
