"""CIS AgentOps — Token Cost Estimator"""

# USD per 1M tokens
MODEL_COSTS = {
    "claude-sonnet-4-6":          {"input": 3.0,  "output": 15.0},
    "claude-haiku-4-5-20251001":  {"input": 0.25, "output": 1.25},
    "gpt-4.1":                    {"input": 2.0,  "output": 8.0},
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    costs = MODEL_COSTS.get(model, {"input": 3.0, "output": 15.0})
    return round(
        (input_tokens * costs["input"] + output_tokens * costs["output"]) / 1_000_000,
        6
    )


def format_cost_report(stage_costs: dict) -> str:
    lines = ["Cost Breakdown:"]
    total = 0.0
    for stage, cost in stage_costs.items():
        lines.append(f"  {stage:15s}: ${cost:.6f}")
        total += cost
    lines.append(f"  {'TOTAL':15s}: ${total:.6f}")
    return "\n".join(lines)
