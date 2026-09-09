# Valka Agent — v1 Demo Handoff

Deadline: demo to Dad's boss tomorrow morning. Build tonight.

Read this together with `<<FILL: absolute path to dad-agent-build-spec.md>>`.

If you cannot read that file, stop and tell Miguel. Do not infer the node table, the architecture, or the definition of done from this addendum — they live in the original spec and this document does not restate them.

This addendum overrides two sections of the original spec, for this pass only: "Division of labour" and "Definition of Done". Everything else — stack, architecture, node table, the feeding calculator's requirements — applies exactly as written.

## Before you start: three things Miguel must have filled in

If any of these are still `<<FILL: ...>>`, stop and ask.

1. Path to dad-agent-build-spec.md (above)
2. Path to the scraped Valka content: `<<FILL: path to scrape>>`
3. Working directory for the fresh WSL build: `<<FILL: e.g. ~/projects/valka-agent>>`

## What's different for this pass

Normally state.py, graph.py, all nodes, and the interrupt/resume logic are hand-written by Miguel to actually learn LangGraph. For tonight only, build all of it so there's a working demo tomorrow. This is not a permanent change to how this project works — see "After the demo" below.

## Definition of Done for tonight (overrides the original spec's DoD)

The original DoD requires that Miguel can explain the code. That does not apply tonight and is explicitly deferred. Tonight's DoD is:

- The three demo conversations in "Demo script" below run end to end without errors or manual intervention.
- The feeding calculator's arithmetic is correct and unit-tested.
- `make demo` (or one documented command) starts everything from a cold machine.
- Missing API keys fail loudly at startup, not mid-conversation.
- `MOCK_LLM=1` runs the full demo script with no network.

Nothing else is required tonight. Completeness against the original spec is secondary to these five items.

## Build order — this is a priority list, not a checklist

Build in this order. Stop at each checkpoint and report before continuing, so Miguel can test while you keep going.

### Phase 1 — the graph, testable from the CLI

- state.py (verbatim, below — do not redesign)
- graph.py: all nodes, all edges, conditional routing out of classify_intent, loop-back edge on gather_transition_info
- nodes/: all six node functions per the original spec's node table
- Feeding transition calculator: pure function, real arithmetic in Python, no LLM involvement in the numbers
- SQLite checkpointer, thread_id = conversation
- LLM wrapper: Groq (Llama 3.3 70B) primary, Gemini fallback, MOCK_LLM=1 third path
- scripts/smoke.py: runs the three demo conversations against the graph directly, no API, no browser. Prints each turn and asserts the expected outcomes.

**CHECKPOINT 1** — stop and report. Miguel runs `python scripts/smoke.py` and verifies the numbers by hand before you build anything on top of this.

### Phase 2 — the escalate interrupt

- interrupt() on the escalate path, resume flow, verified through the checkpointer across process restarts (kill it, restart, resume the same thread_id)
- Extend scripts/smoke.py to cover interrupt → resume

**CHECKPOINT 2** — stop and report.

### Phase 3 — API and UI

- FastAPI + SSE streaming
- React + Vite frontend, text chat only
- Escalation must surface in the UI as something a human can respond to. If that's not trivially doable, make the escalate path visible but non-blocking and say so in your report — a hung demo is worse than a shallow one.

**CHECKPOINT 3** — stop and report. This is a shippable demo. Everything below is upside.

### Phase 4 — voice, behind a flag

- Web Speech API STT/TTS, off by default, enabled with `VITE_ENABLE_VOICE=true`
- The text chat must work identically with voice disabled. Mic permission failures, HTTPS issues, or recognition errors must never break the chat path.

If you run out of time, cut from the bottom. Do not skip ahead.

## Knowledge base — hard stop

Format the KB from the real scraped Valka content at the path given above.

If that path is missing or empty, stop and tell Miguel. Do not generate a placeholder catalogue. The audience tomorrow is a boss at the pet food company who knows these products. Invented product facts are worse than a narrower demo.

## state.py — use this exact schema, do not redesign it

Worked out by hand and understood, not generated. Use verbatim:

```python
from typing import TypedDict, Optional, Literal
from typing_extensions import Annotated
from langgraph.graph.message import add_messages


def merge_dict(existing: dict | None, update: dict | None) -> dict:
    """Reducer for transition_data: shallow-merge new fields in
    without wiping out fields collected on earlier turns.
    Guards against an empty channel on the first update."""
    return {**(existing or {}), **(update or {})}


class TransitionData(TypedDict, total=False):
    weight_lbs: float
    current_food: Literal["kibble", "other_raw", "mixed"]
    target_product: str
    sensitivity: Literal["low", "normal", "high"]


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]
    intent: Optional[Literal[
        "product_question", "feeding_transition",
        "order_status", "escalate", "smalltalk"
    ]]
    transition_data: Annotated[TransitionData, merge_dict]
    kb_citations: list[str]
    escalation_reason: Optional[str]
    awaiting_human: bool
```

Only `messages` (append, via add_messages) and `transition_data` (merge, via merge_dict) need custom reducers. Every other field replaces on update — that's intentional, not an oversight.

## Demo script — these are the acceptance tests

These three conversations must run cleanly. Encode them in scripts/smoke.py and test against them throughout.

### 1. Product question

`<<FILL: a real question about a real Valka product, e.g. "What's in the beef and tripe blend?">>`

Must route to product_question, cite from the KB, populate kb_citations, and not invent product facts. If the KB doesn't cover it, it must say so rather than guess.

### 2. Feeding transition — multi-turn, the centrepiece

Turn 1: "I want to switch my dog to raw." Turn 2: (agent asks) → "She's 60 pounds, on kibble right now." Turn 3: (agent asks) → `<<FILL: real product name>>`, normal sensitivity.

Must route to feeding_transition, loop on gather_transition_info until transition_data has all four fields, merge across turns without losing earlier answers, then produce a day-by-day schedule with real arithmetic. A 60 lb dog at 2.5% is 1.5 lb/day — Miguel checks the full schedule by hand at Checkpoint 1.

### 3. Smalltalk / order status

`<<FILL: whichever of the two Dad is more likely to be asked>>`

Must route correctly and stay short. This exists to show the classifier working, not to be impressive.

Escalation: decide with Miguel whether it's in the live demo. If nobody is playing the human respondent tomorrow, it stays out of the script and is demonstrated only through the smoke test.

## Environment

- Fresh build in WSL at the path given above
- Python `<<FILL: version>>`, uv or venv — pick one, document it in the README
- .env.example committed with GROQ_API_KEY, GEMINI_API_KEY, MOCK_LLM, VITE_ENABLE_VOICE
- Startup check: if a required key is missing and MOCK_LLM is not set, exit with a clear error before the server binds. Never discover this at the first user turn.
- MOCK_LLM=1 returns canned responses covering the full demo script, no network. This is the insurance policy for bad wifi or a Groq rate limit tomorrow morning.
- One documented command to start everything. Two terminals is acceptable only if the README says so explicitly.

## Marking and isolation

Every file outside state.py gets this header:

```
# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
```

Also: commit everything on a branch named v1-demo and tag the final demo state v1-demo-frozen. The comment headers won't survive the first refactor; the tag will, and it's what next week's hand-written pass diffs against.

## After the demo

By Sunday 13 September, graph.py, nodes/, and the interrupt logic get rebuilt by hand, using tonight's version only as a working reference — same guided process used for state.py.

The original spec's rule stands going forward: "If Claude Code writes the graph, this project teaches nothing." Tonight is the one exception, made consciously, for a real deadline — not the new default.

The realistic failure mode is not forgetting this rule. It's the demo going well, the boss asking for three more things, and the rebuild never getting scheduled because the code already works. Hence the date.
