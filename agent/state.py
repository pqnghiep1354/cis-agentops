"""
CIS AgentOps — LangGraph State Schema
TypedDict with full pipeline state. Checkpointed at every node.
"""
from __future__ import annotations
from typing import TypedDict, Annotated, Optional
from langgraph.graph.message import add_messages


class TourInput(TypedDict):
    tour_name: str
    destination: str
    duration_days: int
    raw_description: str
    highlights: list
    inclusions: list
    price_usd: float
    supplier_name: str


class SEOContext(TypedDict):
    keywords: list
    people_also_ask: list
    search_volume: int
    competitor_angles: list


class RAGContext(TypedDict):
    retrieved_examples: list          # raw ChromaDB hits
    rewritten_query: str              # LLM-rewritten query
    reranked_examples: list           # after cross-encoder rerank
    retrieval_score: float            # avg cosine similarity


class GeneratedContent(TypedDict):
    title: str
    tagline: str
    description: str
    highlights: list
    seo_meta_title: str
    seo_meta_description: str
    model_used: str
    tokens_used: int
    latency_ms: float
    cost_usd: float


class ValidationResult(TypedDict):
    passed_rules: list
    failed_rules: list
    quality_score: float              # 0–10
    needs_hitl: bool
    regeneration_count: int


class CISState(TypedDict):
    # Input
    tour_input: TourInput

    # Stage outputs
    seo_context: Optional[SEOContext]
    rag_context: Optional[RAGContext]
    generated_content: Optional[GeneratedContent]
    validation_result: Optional[ValidationResult]

    # Control flow
    regeneration_count: int           # cap at MAX_REGEN to prevent loops
    hitl_approved: Optional[bool]
    export_id: Optional[str]

    # Observability
    trace_id: Optional[str]
    stage_timings: dict               # node_name → elapsed ms
    total_cost_usd: float

    # LangGraph messages (supports streaming)
    messages: Annotated[list, add_messages]
