"""
CIS AgentOps — HITL Node (Human-in-the-Loop)
Local: CLI prompt. Production: SQS waitForTaskToken.
"""
from __future__ import annotations
import os
from agent.state import CISState
from observability.tracer import get_tracer

AUTO_APPROVE_HITL = os.getenv("AUTO_APPROVE_HITL", "false").lower() == "true"


def hitl_node(state: CISState) -> dict:
    tracer = get_tracer()
    span_id = tracer.start_span(
        trace_id=state["trace_id"],
        name="hitl",
        input={"quality_score": state.get("validation_result", {}).get("quality_score")}
    )

    content = state.get("generated_content") or {}
    vr = state.get("validation_result") or {}

    print("\n" + "="*60)
    print("⚠️  HUMAN REVIEW REQUIRED")
    print("="*60)
    print(f"Tour:    {state['tour_input']['tour_name']}")
    print(f"Score:   {vr.get('quality_score', 0):.1f}/10")
    print(f"Failed:  {', '.join(vr.get('failed_rules', [])[:5])}")
    print(f"\nGenerated title: {content.get('title', 'N/A')}")
    print(f"Generated desc:  {content.get('description', 'N/A')[:200]}...")
    print("="*60)

    if AUTO_APPROVE_HITL:
        approved = True
        print("AUTO_APPROVE_HITL=true → auto-approving for notebook demo")
    else:
        while True:
            choice = input("\nApprove? [y/n]: ").strip().lower()
            if choice in ("y", "n"):
                approved = choice == "y"
                break

    tracer.end_span(span_id, output={"approved": approved})
    return {"hitl_approved": approved}
