# Working with this repo

Valka Agent: a LangGraph-based bilingual (EN/ES) chat assistant for Valka,
a raw dog food brand (products manufactured by BJ's Raw Pet Food, but
Valka has its own brand identity — never present them as identical). See
`README.md` for architecture/status and `data/kb/README_PLACEHOLDER.md`
for the state of the knowledge base.

## Git workflow

- **Push after every commit, without being asked.** `git commit` followed
  by `git push origin main` in the same step, unless the user says
  otherwise for that specific change.
- Only commit when the user actually asks for a commit — don't commit
  proactively mid-task.
- **Commit messages are one line.** No multi-paragraph body, no bullet
  list of what changed — a single concise line describing the change.
- **No `Co-Authored-By: Claude` trailer.** Do not add it, even though
  Claude Code's default attribution instructions say to.
- Never commit internal/confidential strategy documents (brand briefs,
  pricing proposals, anything marked "CONFIDENTIAL" or "working
  proposal") — add them to `.gitignore` instead. Ask before committing
  anything you're not sure about on this front.

## Before pushing anything that touches conversation behavior

Run, in this order, and don't push if any fail:
1. `uv run python -m pytest tests/ -q`
2. `uv run python scripts/smoke.py` (offline, `MOCK_LLM=1` — this is the
   default unless overridden)
3. `cd frontend && npm run build` if `frontend/` changed
4. For anything touching `llm.py`, prompts, or the KB: also start the
   backend for real (`MOCK_LLM=0`, real keys from `.env`) and drive at
   least one real conversation through `curl`/the SSE endpoint before
   calling it done. Offline tests passing does not mean the real LLM path
   works — this has caught real bugs (blank responses, wrong-language
   replies, a fully broken provider) that the mock path couldn't surface.

## Don't guess external API details

Model names, rate limits, and SDK packages for Groq/Gemini go stale
without much warning — this has already happened twice in one session
(a retired model, a fully deprecated SDK, and an assumed-but-wrong
free-tier rate limit). Before hardcoding a model name or reasoning about
which provider is "more generous," verify live: call `ListModels`, check
actual `x-ratelimit-*` response headers, or do a real completion call. Web
search corroborates but live API responses are the source of truth.

## Brand/content rules the bot must never violate

- Never let the bot present BJ's Raw Pet Food pricing, or any BJ's-sourced
  internal benchmark, as something a customer sees — those documents are
  explicitly internal-reference-only.
- Never imply Valka and BJ's products are identical, or call Valka "the
  cheap version of BJ's."
- Data pulled from an unapproved/working-proposal document (unchecked
  approval boxes) should not be treated as final fact in customer-facing
  copy without confirming it's been approved.
- Every customer-facing string (templates, prompts, KB docs where
  practical) needs both an English and a Spanish version — this is an
  explicit brief requirement, not optional polish.
- Invented/placeholder data (nutrition numbers, prices, KB content) must
  be clearly marked as such in code comments — follow the existing
  `PLACEHOLDER` convention in `data/kb/*.md` and `calculator.py`.
