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
import sys

os.environ.setdefault("MOCK_LLM", "1")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.messages import HumanMessage

from valka_agent.config import check_startup_config, DB_PATH
from valka_agent.graph import build_graph, get_sqlite_checkpointer

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
                  "What's in the Beef & Tripe Blend?")
    check("routed to product_question", result["intent"] == "product_question",
          f"got intent={result['intent']!r}")
    check("kb_citations populated", len(result["kb_citations"]) > 0,
          f"got kb_citations={result['kb_citations']!r}")
    check("cites the beef & tripe doc", "beef_tripe_blend.md" in result["kb_citations"],
          f"got kb_citations={result['kb_citations']!r}")


def conversation_2_feeding_transition(graph):
    print("\n=== Conversation 2: feeding transition (multi-turn) ===")
    thread_id = "demo-2-feeding-transition"

    r1 = send(graph, thread_id, "I want to switch my dog to raw.")
    check("routed to feeding_transition", r1["intent"] == "feeding_transition",
          f"got intent={r1['intent']!r}")
    check("asks for weight/current food", any(
        kw in r1["messages"][-1].content.lower() for kw in ("weigh", "currently eating")
    ), r1["messages"][-1].content)

    r2 = send(graph, thread_id, "She's 60 pounds, on kibble right now.")
    check("captured weight_lbs=60.0", r2["transition_data"].get("weight_lbs") == 60.0,
          f"got transition_data={r2['transition_data']!r}")
    check("captured current_food=kibble", r2["transition_data"].get("current_food") == "kibble",
          f"got transition_data={r2['transition_data']!r}")
    check("asks for product/sensitivity next", any(
        kw in r2["messages"][-1].content.lower() for kw in ("which product", "sensitivities")
    ), r2["messages"][-1].content)

    r3 = send(graph, thread_id, "Beef & Tripe Blend, normal sensitivity.")
    td = r3["transition_data"]
    check("captured target_product", td.get("target_product") == "Beef & Tripe Blend",
          f"got transition_data={td!r}")
    check("captured sensitivity=normal", td.get("sensitivity") == "normal",
          f"got transition_data={td!r}")

    reply = r3["messages"][-1].content
    check("schedule mentions Day 1 amount (0.375 lb)", "0.375" in reply, reply)
    check("schedule mentions Day 7 steady state (1.5 lb)", reply.count("1.5") >= 2, reply)
    check("schedule spans 7 days", "Day 7" in reply and "Day 8" not in reply, reply)


def conversation_3_order_status(graph):
    print("\n=== Conversation 3: order status ===")
    result = send(graph, "demo-3-order-status",
                  "Hi! Do you know if my order has shipped yet?")
    check("routed to order_status", result["intent"] == "order_status",
          f"got intent={result['intent']!r}")
    check("response is short", len(result["messages"][-1].content) < 400,
          "response too long for a smalltalk/order-status turn")


def main():
    check_startup_config()
    print(f"MOCK_LLM={os.environ.get('MOCK_LLM')}  db={DB_PATH}")

    checkpointer = get_sqlite_checkpointer(DB_PATH)
    graph = build_graph(checkpointer=checkpointer)

    conversation_1_product_question(graph)
    conversation_2_feeding_transition(graph)
    conversation_3_order_status(graph)

    print("\n" + "=" * 60)
    if FAILURES:
        print(f"{len(FAILURES)} CHECK(S) FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("All smoke checks passed.")


if __name__ == "__main__":
    main()
