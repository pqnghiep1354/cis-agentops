"""
CIS AgentOps — Validation Node
29 brand/quality rules, 4-layer validation:
  L1: Structural (required fields, length limits)
  L2: Brand voice (forbidden words, approved vocabulary)
  L3: SEO compliance (keyword density, meta tag length)
  L4: Semantic quality (coherence, specificity)
"""
from __future__ import annotations
import re
import time
from agent.state import CISState, ValidationResult
from observability.tracer import get_tracer

# ── Rule definitions ──────────────────────────────────────────────────────────

FORBIDDEN_WORDS = [
    "deal", "cheap", "book now", "instant booking", "amazing", "unforgettable",
    "perfect", "best ever", "incredible", "awesome", "fantastic", "great value",
]

APPROVED_VOCAB = ["curated", "designed", "refined", "tailored", "journey",
                  "experience", "discover", "exclusive", "bespoke"]

RULES = {
    # Layer 1: Structural
    "v01_title_exists":        lambda c, t, s: bool(c.get("title")),
    "v02_title_length":        lambda c, t, s: 5 <= len(c.get("title", "")) <= 60,
    "v03_tagline_exists":      lambda c, t, s: bool(c.get("tagline")),
    "v04_tagline_length":      lambda c, t, s: 20 <= len(c.get("tagline", "")) <= 120,
    "v05_description_exists":  lambda c, t, s: bool(c.get("description")),
    "v06_description_length":  lambda c, t, s: 150 <= len(c.get("description", "").split()) <= 500,
    "v07_highlights_count":    lambda c, t, s: 3 <= len(c.get("highlights", [])) <= 8,
    "v08_meta_title_length":   lambda c, t, s: len(c.get("seo_meta_title", "")) <= 60,
    "v09_meta_desc_length":    lambda c, t, s: len(c.get("seo_meta_description", "")) <= 155,
    "v10_no_empty_highlights": lambda c, t, s: all(h.strip() for h in c.get("highlights", [])),

    # Layer 2: Brand voice
    "v11_no_forbidden_words":  lambda c, t, s: not any(
        fw in (c.get("description", "") + c.get("title", "")).lower()
        for fw in FORBIDDEN_WORDS
    ),
    "v12_no_exclamation":      lambda c, t, s: "!" not in c.get("description", ""),
    "v13_no_all_caps":         lambda c, t, s: not re.search(r"\b[A-Z]{4,}\b", c.get("description", "")),
    "v14_approved_vocab_used": lambda c, t, s: any(
        w in c.get("description", "").lower() for w in APPROVED_VOCAB
    ),
    "v15_no_first_person":     lambda c, t, s: not re.search(
        r"\b(we |our |us )\b", c.get("description", "").lower()
    ),

    # Layer 3: SEO compliance
    "v16_keyword_in_title":    lambda c, t, s: any(
        kw.lower() in c.get("title", "").lower() or kw.lower() in c.get("description", "").lower()
        for kw in (s.get("keywords", [])[:3] if s else [])
    ) if s and s.get("keywords") else True,
    "v17_keyword_in_meta":     lambda c, t, s: any(
        kw.lower() in c.get("seo_meta_title", "").lower()
        for kw in (s.get("keywords", [])[:2] if s else [])
    ) if s and s.get("keywords") else True,
    "v18_destination_mentioned": lambda c, t, s: (
        t.get("destination", "").split(",")[0].lower() in c.get("description", "").lower()
    ),
    "v19_duration_mentioned":  lambda c, t, s: (
        str(t.get("duration_days", "")) in c.get("description", "")
        or str(t.get("duration_days", "")) + "-day" in c.get("description", "")
    ),

    # Layer 4: Semantic quality
    "v20_no_repetition":       lambda c, t, s: len(set(c.get("highlights", []))) == len(c.get("highlights", [])),
    "v21_title_not_generic":   lambda c, t, s: c.get("title", "").lower() not in [
        "tour title", "luxury tour", "travel experience", "vacation package"
    ],
    "v22_description_prose":   lambda c, t, s: "-" not in c.get("description", "")[:50],
    "v23_price_not_in_desc":   lambda c, t, s: "$" not in c.get("description", ""),
    "v24_meta_unique":         lambda c, t, s: c.get("seo_meta_title") != c.get("title"),
    "v25_highlight_specific":  lambda c, t, s: all(
        len(h.split()) >= 2 for h in c.get("highlights", [])
    ),
    "v26_no_placeholder":      lambda c, t, s: "[" not in (c.get("description", "") + c.get("title", "")),
    "v27_tagline_evocative":   lambda c, t, s: len(c.get("tagline", "").split()) >= 4,
    "v28_description_variety": lambda c, t, s: len(
        set(c.get("description", "").lower().split())
    ) / max(len(c.get("description", "").split()), 1) > 0.5,
    "v29_no_url_in_content":   lambda c, t, s: "http" not in c.get("description", ""),
}

# Weight per rule (higher = more impact on quality score)
RULE_WEIGHTS = {
    **{r: 1.0 for r in RULES},
    "v11_no_forbidden_words": 3.0,   # critical brand rule
    "v06_description_length": 2.0,
    "v14_approved_vocab_used": 2.0,
    "v18_destination_mentioned": 2.0,
}


def validate_node(state: CISState) -> dict:
    tracer = get_tracer()
    span_id = tracer.start_span(
        trace_id=state["trace_id"],
        name="validate",
        input={"tour": state["tour_input"]["tour_name"]}
    )

    start = time.time()
    content = state.get("generated_content") or {}
    tour_input = state["tour_input"]
    seo_context = state.get("seo_context")

    passed = []
    failed = []
    total_weight = 0.0
    earned_weight = 0.0

    for rule_id, rule_fn in RULES.items():
        weight = RULE_WEIGHTS.get(rule_id, 1.0)
        total_weight += weight
        try:
            result = rule_fn(content, tour_input, seo_context)
            if result:
                passed.append(rule_id)
                earned_weight += weight
            else:
                failed.append(rule_id)
        except Exception:
            failed.append(rule_id)

    quality_score = round((earned_weight / total_weight) * 10, 2)
    needs_hitl = quality_score < 5.0  # very low → human review regardless

    elapsed_ms = (time.time() - start) * 1000
    timings = dict(state.get("stage_timings", {}))
    timings["validate"] = elapsed_ms

    result: ValidationResult = {
        "passed_rules": passed,
        "failed_rules": failed,
        "quality_score": quality_score,
        "needs_hitl": needs_hitl,
        "regeneration_count": state.get("regeneration_count", 0),
    }

    tracer.end_span(span_id, output={
        "quality_score": quality_score,
        "passed": len(passed),
        "failed": len(failed),
        "failed_rules": failed[:5],
    })

    return {"validation_result": result, "stage_timings": timings}
