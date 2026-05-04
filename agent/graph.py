"""
CIS AgentOps — LangGraph Full Pipeline Graph
Orchestrates: ingest → seo → rag_retrieve → generate → validate → [hitl|export]

Key design decisions:
  - LangGraph is the primary orchestrator (replaces Step Functions for local)
  - SqliteSaver checkpoints state after every node (survives crashes)
  - Max 3 regeneration attempts before HITL to prevent infinite loops
  - Langfuse spans wrap every node for full traceability
"""
from __future__ import annotations
import os
import uuid
from langgraph.graph import StateGraph, END
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

from agent.state import CISState
from agent.nodes.ingestion import ingestion_node
from agent.nodes.seo import seo_node
from agent.nodes.rag_retrieve import rag_node
from agent.nodes.generate import generate_node
from agent.nodes.validate import validate_node
from agent.nodes.export import export_node
from agent.nodes.hitl import hitl_node
from observability.tracer import get_tracer

MAX_REGEN = 3  # guardrail: never loop more than 3 times


# ── Routing logic ────────────────────────────────────────────────────────────

def route_after_validation(state: CISState) -> str:
    """
    After validation:
      quality ≥ 7.0  → export
      quality < 7.0 AND regen < MAX_REGEN → regenerate
      quality < 7.0 AND regen ≥ MAX_REGEN → hitl
    """
    vr = state.get("validation_result", {})
    score = vr.get("quality_score", 0)
    regen = state.get("regeneration_count", 0)

    if score >= 7.0:
        return "export"
    elif regen < MAX_REGEN:
        return "generate"   # loop back — regen count tracked in generate_node
    else:
        return "hitl"


def route_after_hitl(state: CISState) -> str:
    if state.get("hitl_approved"):
        return "export"
    return END   # rejected → terminal state


# ── Build graph ──────────────────────────────────────────────────────────────

def build_graph(checkpointer=None):
    """Build and compile the CIS pipeline graph."""
    g = StateGraph(CISState)

    # Add nodes
    g.add_node("ingestion", ingestion_node)
    g.add_node("seo",      seo_node)
    g.add_node("rag",      rag_node)
    g.add_node("generate", generate_node)
    g.add_node("validate", validate_node)
    g.add_node("export",   export_node)
    g.add_node("hitl",     hitl_node)

    # Entry point
    g.set_entry_point("ingestion")

    # Linear edges
    g.add_edge("ingestion", "seo")
    g.add_edge("seo",      "rag")
    g.add_edge("rag",      "generate")
    g.add_edge("generate", "validate")

    # Conditional routing after validation
    g.add_conditional_edges(
        "validate",
        route_after_validation,
        {
            "export":   "export",
            "generate": "generate",   # regeneration loop
            "hitl":     "hitl",
        }
    )

    # HITL routing
    g.add_conditional_edges(
        "hitl",
        route_after_hitl,
        {
            "export": "export",
            END:      END,
        }
    )

    g.add_edge("export", END)

    # Checkpointer (SqliteSaver for local; replace with AsyncPostgresSaver for prod)
    if checkpointer is None:
        conn = sqlite3.connect(".checkpoints.db", check_same_thread=False)
        checkpointer = SqliteSaver(conn)

    return g.compile(checkpointer=checkpointer)


# ── Run single tour ──────────────────────────────────────────────────────────

def run_pipeline(tour_input: dict, thread_id: str = None) -> CISState:
    """
    Run the full CIS pipeline for a single tour.

    Args:
        tour_input: dict matching TourInput schema
        thread_id: for checkpointing (auto-generated if None)

    Returns:
        Final CISState with all stage outputs populated
    """
    graph = build_graph()
    tracer = get_tracer()

    thread_id = thread_id or str(uuid.uuid4())
    # Pass thread_id as trace_id so API run_id == langfuse trace_id
    trace_id = thread_id
    tracer.create_trace_with_id(
        trace_id=trace_id,
        name="cis-pipeline",
        metadata={"tour": tour_input.get("tour_name"), "thread": thread_id}
    )
    print(f"[Graph] trace_id={trace_id[:8]}", flush=True)

    initial_state: CISState = {
        "tour_input": tour_input,
        "seo_context": None,
        "rag_context": None,
        "generated_content": None,
        "validation_result": None,
        "regeneration_count": 0,
        "hitl_approved": None,
        "export_id": None,
        "trace_id": trace_id,
        "stage_timings": {},
        "total_cost_usd": 0.0,
        "messages": [],
    }

    config = {"configurable": {"thread_id": thread_id}}
    final_state = graph.invoke(initial_state, config=config)

    tracer.finalize_trace(trace_id, output={
        "quality_score": final_state.get("validation_result", {}).get("quality_score"),
        "total_cost_usd": final_state.get("total_cost_usd"),
        "export_id": final_state.get("export_id"),
    })

    return final_state


if __name__ == "__main__":
    # Quick smoke test with dummy tour
    sample = {
        "tour_name": "Halong Bay Discovery",
        "destination": "Vietnam",
        "duration_days": 3,
        "raw_description": "Cruise through Halong Bay limestone karsts, kayak sea caves, sunset on deck.",
        "highlights": ["UNESCO World Heritage Site", "Kayaking", "Floating Villages"],
        "inclusions": ["Cabin", "All Meals", "Guided Tours"],
        "price_usd": 650.0,
        "supplier_name": "Vietnam Luxury Cruises",
    }
    result = run_pipeline(sample)
    print(f"\n✅ Pipeline complete")
    print(f"   Quality score: {result['validation_result']['quality_score']:.1f}/10")
    print(f"   Total cost:    ${result['total_cost_usd']:.4f}")
    print(f"   Export ID:     {result.get('export_id', 'N/A (hitl or failed)')}")
    print(f"   Stage timings: {result['stage_timings']}")
