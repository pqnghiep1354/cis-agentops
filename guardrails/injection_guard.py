"""
CIS AgentOps — Prompt Injection Guard
Detects adversarial patterns in supplier-provided text before sending to LLM.
"""
import re

INJECTION_PATTERNS = [
    r"ignore (previous|all|above) instructions",
    r"you are now",
    r"forget everything",
    r"system prompt",
    r"<\|.*?\|>",                          # token injection
    r"\[INST\]|\[/INST\]",                 # Llama-style
    r"act as (a|an|the)\s+\w+",
    r"DAN\b",                              # Do Anything Now
    r"jailbreak",
    r"override (your|all) (rules|instructions)",
    r"reveal (your|the) (system|instructions|prompt)",
]

COMPILED = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def check_injection(text: str) -> bool:
    """Returns True if injection attempt detected."""
    for pattern in COMPILED:
        if pattern.search(text):
            return True
    return False
