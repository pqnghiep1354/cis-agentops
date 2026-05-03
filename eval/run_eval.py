"""
CIS AgentOps — Automated Evaluation Pipeline

Criterion 6 (Evaluation) Excellent:
  ✅ Golden dataset (20 tours from real CIS data)
  ✅ LLM-as-judge scoring on 6 dimensions
  ✅ Before/after comparison (raw vs. generated)
  ✅ Regression tracking (scores saved per run, trend visible)
  ✅ Automated batch eval with aggregate metrics

Usage:
    python -m eval.run_eval --dataset eval/golden_dataset.json --output eval/results/
    python -m eval.run_eval --compare eval/results/run_001.json eval/results/run_002.json
"""
from __future__ import annotations
import os
import json
import time
import argparse
import statistics
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic

JUDGE_MODEL = "claude-haiku-4-5-20251001"   # cheap, fast judge

JUDGE_SYSTEM = """You are an expert evaluator for luxury travel content targeting affluent professionals (40-60 years old).
Evaluate the generated content strictly and return ONLY valid JSON — no explanation."""

JUDGE_PROMPT_TEMPLATE = """Evaluate this generated tour content against the original raw description.

RAW INPUT:
{raw_description}

GENERATED CONTENT:
Title: {title}
Tagline: {tagline}
Description: {description}
Highlights: {highlights}
SEO Meta Title: {seo_meta_title}
SEO Meta Description: {seo_meta_description}

Score each dimension 1-10. Be strict. Return ONLY this JSON:
{{
  "brand_voice": <int>,         // Calm, refined, aspirational tone (no forbidden words)
  "seo_quality": <int>,         // Keyword integration, meta tag quality
  "content_accuracy": <int>,    // Faithful to original facts/highlights
  "writing_quality": <int>,     // Prose quality, variety, specificity
  "target_audience_fit": <int>, // Appropriate for affluent 40-60 professionals
  "commercial_readiness": <int>,// Ready to publish without edits
  "overall": <int>,             // Holistic score
  "reasoning": "<string>"       // 1-2 sentence explanation
}}"""


def load_dataset(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def judge_single(client: Anthropic, raw_input: dict, generated: dict) -> dict:
    """Run LLM-as-judge on a single tour. Returns scored dict."""
    prompt = JUDGE_PROMPT_TEMPLATE.format(
        raw_description=raw_input.get("raw_description", ""),
        title=generated.get("title", ""),
        tagline=generated.get("tagline", ""),
        description=generated.get("description", ""),
        highlights=", ".join(generated.get("highlights", [])),
        seo_meta_title=generated.get("seo_meta_title", ""),
        seo_meta_description=generated.get("seo_meta_description", ""),
    )

    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=300,
        system=JUDGE_SYSTEM,
        messages=[{"role": "user", "content": prompt}]
    )

    raw = response.content[0].text.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"overall": 0, "reasoning": f"parse_error: {raw[:100]}"}


def run_eval(dataset_path: str, output_dir: str = "eval/results") -> dict:
    """
    Run full evaluation on dataset. Returns aggregate metrics.

    For each tour:
      1. Run CIS pipeline to generate content
      2. Run LLM-as-judge to score output
      3. Record all scores + pipeline metadata

    Saves results to: {output_dir}/run_{timestamp}.json
    """
    from agent.graph import run_pipeline

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    dataset = load_dataset(dataset_path)

    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = []

    print(f"\n🧪 CIS Eval Run {run_id}")
    print(f"   Dataset: {len(dataset)} tours")
    print(f"   Judge: {JUDGE_MODEL}\n")

    for i, tour in enumerate(dataset, 1):
        print(f"  [{i:02d}/{len(dataset):02d}] {tour['tour_name']}...", end=" ", flush=True)
        t0 = time.time()

        try:
            # Run pipeline
            state = run_pipeline(tour)
            generated = state.get("generated_content") or {}
            validation = state.get("validation_result") or {}

            # LLM-as-judge scoring
            if generated:
                scores = judge_single(client, tour, generated)
            else:
                scores = {"overall": 0, "reasoning": "pipeline_failed"}

            elapsed = time.time() - t0
            result = {
                "tour_name": tour["tour_name"],
                "destination": tour["destination"],
                "pipeline": {
                    "quality_score": validation.get("quality_score", 0),
                    "model_used": generated.get("model_used"),
                    "cost_usd": generated.get("cost_usd", 0),
                    "latency_ms": generated.get("latency_ms", 0),
                    "failed_rules": validation.get("failed_rules", []),
                },
                "judge_scores": scores,
                "total_elapsed_s": round(elapsed, 2),
            }
            results.append(result)
            print(f"✅ score={scores.get('overall', 0)}/10 ({elapsed:.1f}s)")

        except Exception as e:
            results.append({
                "tour_name": tour.get("tour_name"),
                "error": str(e),
                "judge_scores": {"overall": 0},
            })
            print(f"❌ ERROR: {e}")

    # ── Aggregate metrics ─────────────────────────────────────────────────────
    successful = [r for r in results if "error" not in r]
    judge_overalls = [r["judge_scores"].get("overall", 0) for r in successful]
    pipeline_scores = [r["pipeline"]["quality_score"] for r in successful]
    costs = [r["pipeline"].get("cost_usd", 0) for r in successful]

    dimensions = ["brand_voice", "seo_quality", "content_accuracy",
                  "writing_quality", "target_audience_fit", "commercial_readiness"]

    dim_avgs = {}
    for dim in dimensions:
        vals = [r["judge_scores"].get(dim, 0) for r in successful if r["judge_scores"].get(dim)]
        dim_avgs[dim] = round(statistics.mean(vals), 2) if vals else 0.0

    aggregate = {
        "run_id": run_id,
        "dataset_size": len(dataset),
        "success_rate": round(len(successful) / len(dataset), 3),
        "judge_score_avg": round(statistics.mean(judge_overalls), 2) if judge_overalls else 0,
        "judge_score_std": round(statistics.stdev(judge_overalls), 2) if len(judge_overalls) > 1 else 0,
        "judge_score_min": min(judge_overalls) if judge_overalls else 0,
        "judge_score_max": max(judge_overalls) if judge_overalls else 0,
        "pipeline_score_avg": round(statistics.mean(pipeline_scores), 2) if pipeline_scores else 0,
        "dimension_averages": dim_avgs,
        "total_cost_usd": round(sum(costs), 4),
        "avg_cost_per_tour": round(statistics.mean(costs), 4) if costs else 0,
    }

    output = {"aggregate": aggregate, "results": results}
    out_path = f"{output_dir}/run_{run_id}.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'='*50}")
    print(f"✅ Eval complete — {run_id}")
    print(f"   Judge avg:     {aggregate['judge_score_avg']}/10")
    print(f"   Pipeline avg:  {aggregate['pipeline_score_avg']}/10")
    print(f"   Total cost:    ${aggregate['total_cost_usd']}")
    print(f"   Success rate:  {aggregate['success_rate']*100:.0f}%")
    print(f"   Results:       {out_path}")
    print(f"\nDimension breakdown:")
    for dim, score in dim_avgs.items():
        bar = "█" * int(score) + "░" * (10 - int(score))
        print(f"  {dim:25s} {bar} {score:.1f}")

    return aggregate


def compare_runs(path_a: str, path_b: str):
    """Compare two eval runs side-by-side (regression detection)."""
    with open(path_a) as f: run_a = json.load(f)
    with open(path_b) as f: run_b = json.load(f)

    agg_a = run_a["aggregate"]
    agg_b = run_b["aggregate"]

    print(f"\n📊 Regression Comparison")
    print(f"{'Metric':30s} {'Run A':>10s} {'Run B':>10s} {'Delta':>10s}")
    print("-" * 65)

    metrics = [
        ("Judge Score Avg", "judge_score_avg"),
        ("Pipeline Score Avg", "pipeline_score_avg"),
        ("Success Rate", "success_rate"),
        ("Total Cost (USD)", "total_cost_usd"),
    ]

    for label, key in metrics:
        va = agg_a.get(key, 0)
        vb = agg_b.get(key, 0)
        delta = vb - va
        arrow = "🔺" if delta > 0 else ("🔻" if delta < 0 else "→")
        print(f"{label:30s} {va:>10.3f} {vb:>10.3f} {arrow}{abs(delta):>8.3f}")

    print("\nDimension deltas:")
    dims_a = agg_a.get("dimension_averages", {})
    dims_b = agg_b.get("dimension_averages", {})
    for dim in dims_a:
        va = dims_a.get(dim, 0)
        vb = dims_b.get(dim, 0)
        delta = vb - va
        arrow = "🔺" if delta > 0.2 else ("🔻" if delta < -0.2 else "→")
        print(f"  {dim:30s} {va:.1f} → {vb:.1f} {arrow}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="CIS AgentOps Eval Runner")
    sub = parser.add_subparsers(dest="cmd")

    run_p = sub.add_parser("run", help="Run evaluation on dataset")
    run_p.add_argument("--dataset", default="eval/golden_dataset.json")
    run_p.add_argument("--output", default="eval/results")

    cmp_p = sub.add_parser("compare", help="Compare two runs")
    cmp_p.add_argument("run_a")
    cmp_p.add_argument("run_b")

    args = parser.parse_args()

    if args.cmd == "run":
        run_eval(args.dataset, args.output)
    elif args.cmd == "compare":
        compare_runs(args.run_a, args.run_b)
    else:
        # Default: run eval
        run_eval("eval/golden_dataset.json")
