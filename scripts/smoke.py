# V1 DEMO IMPLEMENTATION — built for a deadline, not yet understood by
# Miguel. Do not extend without a rebuild pass. See build spec Definition
# of Done.
"""Runs the three demo conversations directly against the graph — no API,
no browser, no network by default (forces MOCK_LLM=1 unless already set).

Usage:
    python scripts/smoke.py            # offline, deterministic
    MOCK_LLM=0 python scripts/smoke.py # real Groq/Gemini calls
"""
import os
import subprocess
import sys
import tempfile

os.environ.setdefault("MOCK_LLM", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage

from valka_agent.config import check_startup_config
from valka_agent.graph import build_graph, get_sqlite_checkpointer
from valka_agent.kb import get_kb

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Run as `python -c` in a fresh subprocess (real process boundary, not just a
# new object in this script) to prove the escalate pause survives on disk
# rather than in some in-memory LangGraph structure. Each snippet builds its
# own SqliteSaver/connection against the shared db path passed via env.
_PAUSE_SNIPPET = """
import os, sys
from langchain_core.messages import HumanMessage
from valka_agent.graph import build_graph, get_sqlite_checkpointer

checkpointer = get_sqlite_checkpointer(os.environ["VALKA_DB_PATH"])
graph = build_graph(checkpointer=checkpointer)
config = {"configurable": {"thread_id": os.environ["VALKA_THREAD_ID"]}}
result = graph.invoke(
    {"messages": [HumanMessage(content="I want a refund, my dog had an allergic reaction")]},
    config,
)
assert result.get("__interrupt__"), f"expected a pause, got {result!r}"
assert result.get("awaiting_human") is True, f"got awaiting_human={result.get('awaiting_human')!r}"
print("PAUSED", flush=True)
"""

_RESUME_SNIPPET = """
import os, sys
from langgraph.types import Command
from valka_agent.graph import build_graph, get_sqlite_checkpointer

checkpointer = get_sqlite_checkpointer(os.environ["VALKA_DB_PATH"])
graph = build_graph(checkpointer=checkpointer)
config = {"configurable": {"thread_id": os.environ["VALKA_THREAD_ID"]}}
result = graph.invoke(Command(resume=os.environ["VALKA_HUMAN_REPLY"]), config)
assert result.get("awaiting_human") is False, f"got awaiting_human={result.get('awaiting_human')!r}"
print("RESUMED:" + result["messages"][-1].content, flush=True)
"""


def _run_subprocess_snippet(snippet: str, env: dict) -> str:
    proc = subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=REPO_ROOT,
        env={**os.environ, **env},
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise AssertionError(f"subprocess failed (exit {proc.returncode}):\n{proc.stderr}")
    return proc.stdout.strip()

FAILURES = []


def check(label: str, condition: bool, detail: str = "") -> None:
    status = "PASS" if condition else "FAIL"
    print(f"    [{status}] {label}" + (f" — {detail}" if detail and not condition else ""))
    if not condition:
        FAILURES.append(f"{label}: {detail}")


def send(graph, thread_id: str, text: str) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    print(f"\n  > {text}")
    result = graph.invoke({"messages": [HumanMessage(content=text)]}, config)
    reply = result["messages"][-1].content
    print(f"  < {reply}")
    return result


def conversation_1_product_question(graph):
    print("\n=== Conversation 1: product question ===")
    result = send(graph, "demo-1-product-question",
                  "What's in Everyday Wag?")
    check("routed to product_question", result["intent"] == "product_question",
          f"got intent={result['intent']!r}")
    check("kb_citations populated", len(result["kb_citations"]) > 0,
          f"got kb_citations={result['kb_citations']!r}")
    check("cites the everyday wag doc", "everyday_wag.md" in result["kb_citations"],
          f"got kb_citations={result['kb_citations']!r}")


def conversation_2_feeding_plan(graph):
    print("\n=== Conversation 2: feeding plan (multi-turn) ===")
    thread_id = "demo-2-feeding-plan"

    r1 = send(graph, thread_id, "I want to start feeding my dog raw.")
    check("routed to feeding_plan", r1["intent"] == "feeding_plan",
          f"got intent={r1['intent']!r}")
    check("asks for weight/dogs/life stage", any(
        kw in r1["messages"][-1].content.lower() for kw in ("weight", "life stage")
    ), r1["messages"][-1].content)

    r2 = send(graph, thread_id, "She's 60 pounds, just one dog, and she's an adult.")
    fpd = r2["feeding_plan_data"]
    check("captured weight_lbs=60.0", fpd.get("weight_lbs") == 60.0, f"got feeding_plan_data={fpd!r}")
    check("captured num_dogs=1", fpd.get("num_dogs") == 1, f"got feeding_plan_data={fpd!r}")
    check("captured life_stage=adult", fpd.get("life_stage") == "adult", f"got feeding_plan_data={fpd!r}")
    check("asks for activity/body condition next", any(
        kw in r2["messages"][-1].content.lower() for kw in ("active", "body condition")
    ), r2["messages"][-1].content)

    r3 = send(graph, thread_id, "Moderate activity, ideal weight.")
    fpd = r3["feeding_plan_data"]
    check("captured activity_level=moderate", fpd.get("activity_level") == "moderate", f"got feeding_plan_data={fpd!r}")
    check("captured body_condition=ideal", fpd.get("body_condition") == "ideal", f"got feeding_plan_data={fpd!r}")
    check("asks for product/percent next", any(
        kw in r3["messages"][-1].content.lower() for kw in ("which product", "percentage")
    ), r3["messages"][-1].content)

    r4 = send(graph, thread_id, "Everyday Wag, 100%.")
    fpd = r4["feeding_plan_data"]
    check("captured target_product", fpd.get("target_product") == "Everyday Wag",
          f"got feeding_plan_data={fpd!r}")
    check("captured percent_valka=100", fpd.get("percent_valka") == 100, f"got feeding_plan_data={fpd!r}")

    reply = r4["messages"][-1].content
    check("plan mentions daily total (1.5 lb)", "1.5" in reply, reply)
    check("plan mentions a cost estimate", "cost" in reply.lower(), reply)
    check("plan mentions shipping", "shipping" in reply.lower(), reply)
    check("plan never mentions BJ's pricing", "bj" not in reply.lower(), reply)


def conversation_5_product_recommendation(graph):
    print("\n=== Conversation 5: product recommendation (multi-turn) ===")
    thread_id = "demo-5-product-recommendation"

    r1 = send(graph, thread_id, "What would you recommend for my dog?")
    check("routed to product_recommendation", r1["intent"] == "product_recommendation",
          f"got intent={r1['intent']!r}")
    check("asks for avoid-ingredient/priority", any(
        kw in r1["messages"][-1].content.lower() for kw in ("avoid", "protein")
    ), r1["messages"][-1].content)

    r2 = send(graph, thread_id, "No allergies, and budget matters most to me.")
    rd = r2["recommendation_data"]
    check("captured avoid_ingredient=none", rd.get("avoid_ingredient") == "none",
          f"got recommendation_data={rd!r}")
    check("captured priority=budget", rd.get("priority") == "budget",
          f"got recommendation_data={rd!r}")
    check("kb_citations covers the full catalog", len(r2["kb_citations"]) == len(get_kb().product_docs()),
          f"got kb_citations={r2['kb_citations']!r}")
    # Not asserting on the recommendation's actual product pick here: under
    # MOCK_LLM that text is a blind truncated echo of the catalog (same
    # limitation as product_question's mock, see llm.py), not real
    # reasoning about price/fit -- verify the real-LLM pick manually
    # against the current pricing in data/kb/*.md if this matters.


def conversation_3_order_status(graph):
    print("\n=== Conversation 3: order status ===")
    result = send(graph, "demo-3-order-status",
                  "Hi! Do you know if my order has shipped yet?")
    check("routed to order_status", result["intent"] == "order_status",
          f"got intent={result['intent']!r}")
    check("response is short", len(result["messages"][-1].content) < 400,
          "response too long for a smalltalk/order-status turn")


def conversation_6_spanish_bilingual(graph):
    print("\n=== Conversation 6: Spanish-language smalltalk + catalog browse ===")
    thread_id = "demo-6-espanol"

    r1 = send(graph, thread_id, "Hola, buenos días")
    check("routed to smalltalk", r1["intent"] == "smalltalk", f"got intent={r1['intent']!r}")
    check("detected language=es", r1.get("language") == "es", f"got language={r1.get('language')!r}")
    check("replied in Spanish", "Hola" in r1["messages"][-1].content, r1["messages"][-1].content)

    r2 = send(graph, thread_id, "¿Qué productos tienen disponibles?")
    check("routed to product_question", r2["intent"] == "product_question",
          f"got intent={r2['intent']!r}")
    check("Spanish browse-all query matched the full catalog", len(r2["kb_citations"]) == len(get_kb().product_docs()),
          f"got kb_citations={r2['kb_citations']!r}")


def conversation_4_escalate_interrupt_resume():
    print("\n=== Conversation 4: escalate -> interrupt -> resume across a process restart ===")
    print("  (each half below runs in its own `python -c` subprocess, sharing only the sqlite file)")

    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite", prefix="valka-escalate-smoke-")
    os.close(db_fd)
    os.remove(db_path)  # let sqlite create it fresh

    env = {
        "VALKA_DB_PATH": db_path,
        "VALKA_THREAD_ID": "demo-4-escalate",
        "VALKA_HUMAN_REPLY": "A team member will reach out within 24 hours.",
    }

    try:
        pause_out = _run_subprocess_snippet(_PAUSE_SNIPPET, env)
        print(f"  [process 1] > I want a refund, my dog had an allergic reaction")
        print(f"  [process 1] < {pause_out}")
        check("first process paused on interrupt()", pause_out == "PAUSED", pause_out)

        resume_out = _run_subprocess_snippet(_RESUME_SNIPPET, env)
        print(f"  [process 2] > (resume) {env['VALKA_HUMAN_REPLY']}")
        print(f"  [process 2] < {resume_out}")
        check("second (fresh) process resumed the same thread",
              resume_out == f"RESUMED:{env['VALKA_HUMAN_REPLY']}", resume_out)
    except AssertionError as e:
        check("escalate interrupt/resume across restart", False, str(e))
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def main():
    check_startup_config()

    # Own throwaway db, not the real DB_PATH: thread_ids here are hardcoded,
    # and DB_PATH is a persistent file (that's the point, for the live demo).
    # Reusing it here would mean each smoke.py run starts from whatever state
    # the *previous* run left those threads in instead of a clean slate --
    # e.g. a rerun would find demo-2's feeding_plan_data already fully
    # populated and skip straight to the plan on turn 1, then misroute
    # turns 2-3 as smalltalk/product_question. Bit for bit the same bug
    # conversation_4 below tests *for* (state must survive a real restart)
    # is exactly what breaks a hardcoded thread_id smoke test that ISN'T
    # given a fresh db -- so give it one.
    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite", prefix="valka-smoke-")
    os.close(db_fd)
    os.remove(db_path)
    print(f"MOCK_LLM={os.environ.get('MOCK_LLM')}  db={db_path} (throwaway, per-run)")

    try:
        checkpointer = get_sqlite_checkpointer(db_path)
        graph = build_graph(checkpointer=checkpointer)

        conversation_1_product_question(graph)
        conversation_2_feeding_plan(graph)
        conversation_3_order_status(graph)
        conversation_4_escalate_interrupt_resume()
        conversation_5_product_recommendation(graph)
        conversation_6_spanish_bilingual(graph)
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)

    print("\n" + "=" * 60)
    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("All smoke checks passed.")


if __name__ == "__main__":
    main()
