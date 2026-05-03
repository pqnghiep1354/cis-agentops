"""
CIS AgentOps — Content Generation Node
Multi-LLM fallback: Claude Sonnet → Claude Haiku → GPT-4.1
Langfuse span wraps every generation attempt.
Pydantic schema enforced on output.
"""
from __future__ import annotations
import os
import time
import json
from typing import Optional

from anthropic import Anthropic, APIError
from pydantic import BaseModel, field_validator

from agent.state import CISState, GeneratedContent
from guardrails.schemas import TourContentOutput
from guardrails.injection_guard import check_injection
from observability.tracer import get_tracer
from observability.cost_tracker import estimate_cost

# Token cost table (USD per 1M tokens)
MODEL_COSTS = {
    "claude-sonnet-4-6":      {"input": 3.0,  "output": 15.0},
    "claude-haiku-4-5-20251001": {"input": 0.25, "output": 1.25},
    "gpt-4.1":                {"input": 2.0,  "output": 8.0},
}


SYSTEM_PROMPT = """You are an expert luxury travel copywriter for Adventure Asia.
Brand voice: calm, refined, aspirational. Target: affluent professionals 40-60.

APPROVED words: Curated, Designed, Refined, Tailored, Journey, Experience, Discover
FORBIDDEN words: Deal, Cheap, Book Now, Instant booking, Amazing, Unforgettable, Perfect

Output ONLY valid JSON matching this schema — no explanation, no markdown:
{
  "title": "string (max 60 chars, brand-voice headline)",
  "tagline": "string (max 120 chars, evocative one-liner)",
  "description": "string (200-400 words, refined prose, no bullets)",
  "highlights": ["string", ...],
  "seo_meta_title": "string (max 60 chars, keyword-rich)",
  "seo_meta_description": "string (max 155 chars)"
}"""


def _build_user_prompt(state: CISState) -> str:
    ti = state["tour_input"]
    seo = state.get("seo_context") or {}
    rag = state.get("rag_context") or {}
    regen_count = state.get("regeneration_count", 0)

    # Include few-shot examples from RAG
    examples_block = ""
    examples = rag.get("reranked_examples", [])
    if examples:
        examples_block = "\n\nFEW-SHOT EXAMPLES (high-quality reference content):\n"
        for i, ex in enumerate(examples[:2], 1):
            examples_block += f"\nExample {i}:\n{ex['document'][:500]}\n"

    # Regeneration context (tell LLM why it failed before)
    regen_block = ""
    if regen_count > 0:
        vr = state.get("validation_result") or {}
        failed = vr.get("failed_rules", [])
        regen_block = f"\n\nPREVIOUS ATTEMPT FAILED. Fix these issues: {', '.join(failed[:5])}"

    return f"""Tour to rewrite:
Name: {ti['tour_name']}
Destination: {ti['destination']}
Duration: {ti['duration_days']} days
Raw description: {ti['raw_description']}
Highlights: {', '.join(ti.get('highlights', []))}
Price: ${ti['price_usd']:,.0f} USD

SEO keywords to naturally incorporate: {', '.join(seo.get('keywords', [])[:5])}
People also ask: {', '.join(seo.get('people_also_ask', [])[:3])}
{examples_block}{regen_block}

Generate the tour content JSON now:"""


def _call_claude(prompt: str, model: str, client: Anthropic) -> tuple[str, int, int]:
    """Returns (text, input_tokens, output_tokens)"""
    response = client.messages.create(
        model=model,
        max_tokens=1200,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    text = response.content[0].text
    return text, response.usage.input_tokens, response.usage.output_tokens


def _call_openai(prompt: str) -> tuple[str, int, int]:
    """GPT-4.1 fallback"""
    from openai import OpenAI
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    response = client.chat.completions.create(
        model="gpt-4.1",
        max_tokens=1200,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        response_format={"type": "json_object"}
    )
    msg = response.choices[0].message.content
    usage = response.usage
    return msg, usage.prompt_tokens, usage.completion_tokens


def _parse_and_validate(raw_text: str) -> Optional[dict]:
    """Parse JSON from LLM output, validate against Pydantic schema."""
    try:
        # Strip markdown code fences if present
        text = raw_text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        data = json.loads(text.strip())
        validated = TourContentOutput(**data)
        return validated.model_dump()
    except Exception:
        return None


def generate_node(state: CISState) -> dict:
    """
    Content generation with:
    - Multi-LLM fallback chain (Sonnet → Haiku → GPT-4.1)
    - Pydantic schema enforcement on output
    - Prompt injection guard on raw inputs
    - Langfuse span per attempt
    - Cost + latency tracking
    """
    tracer = get_tracer()
    span_id = tracer.start_span(
        trace_id=state["trace_id"],
        name="content-generate",
        input={"tour": state["tour_input"]["tour_name"],
               "regen": state.get("regeneration_count", 0)}
    )

    # Injection guard on raw supplier input
    raw_desc = state["tour_input"].get("raw_description", "")
    if check_injection(raw_desc):
        tracer.end_span(span_id, output={"error": "injection_detected"})
        # Return safe fallback — don't crash the pipeline
        return {
            "generated_content": None,
            "validation_result": {
                "passed_rules": [],
                "failed_rules": ["INJECTION_GUARD: suspicious input detected"],
                "quality_score": 0.0,
                "needs_hitl": True,
                "regeneration_count": state.get("regeneration_count", 0),
            }
        }

    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    prompt = _build_user_prompt(state)

    fallback_chain = [
        ("claude-sonnet-4-6",        lambda p: _call_claude(p, "claude-sonnet-4-6", client)),
        ("claude-haiku-4-5-20251001", lambda p: _call_claude(p, "claude-haiku-4-5-20251001", client)),
        ("gpt-4.1",                  lambda p: _call_openai(p)),
    ]

    start = time.time()
    generated = None
    model_used = None
    input_tokens = output_tokens = 0

    for model_name, call_fn in fallback_chain:
        try:
            raw_text, in_tok, out_tok = call_fn(prompt)
            parsed = _parse_and_validate(raw_text)
            if parsed:
                generated = parsed
                model_used = model_name
                input_tokens = in_tok
                output_tokens = out_tok
                break
            # Schema validation failed → try next model
        except APIError as e:
            if "overloaded" in str(e).lower() or "throttl" in str(e).lower():
                continue   # try next tier
            raise
        except Exception:
            continue

    elapsed_ms = (time.time() - start) * 1000
    cost = estimate_cost(model_used or "claude-sonnet-4-6", input_tokens, output_tokens)

    if generated:
        content: GeneratedContent = {
            **generated,
            "model_used": model_used,
            "tokens_used": input_tokens + output_tokens,
            "latency_ms": elapsed_ms,
            "cost_usd": cost,
        }
    else:
        content = None

    tracer.end_span(span_id, output={
        "model_used": model_used,
        "tokens": input_tokens + output_tokens,
        "cost_usd": cost,
        "latency_ms": elapsed_ms,
        "success": generated is not None,
    })

    timings = dict(state.get("stage_timings", {}))
    timings["generate"] = elapsed_ms
    regen_count = state.get("regeneration_count", 0) + (1 if state.get("generated_content") else 0)

    return {
        "generated_content": content,
        "stage_timings": timings,
        "regeneration_count": regen_count,
        "total_cost_usd": state.get("total_cost_usd", 0.0) + cost,
    }
