"""
CIS AgentOps — Langfuse Tracer Wrapper
Gracefully degrades to no-op logging if Langfuse is unreachable.
Reads env vars lazily at first use (not at module import time).
"""
from __future__ import annotations
import os
import uuid
import logging

log = logging.getLogger(__name__)


class LangfuseTracer:
    def __init__(self):
        host   = os.getenv("LANGFUSE_HOST", "http://localhost:3000")
        pub_key = os.getenv("LANGFUSE_PUBLIC_KEY", "lf-pub-local-key")
        sec_key = os.getenv("LANGFUSE_SECRET_KEY", "lf-sec-local-key")

        try:
            from langfuse import Langfuse
            self._lf = Langfuse(
                public_key=pub_key,
                secret_key=sec_key,
                host=host,
            )
            self._traces = {}
            self._spans  = {}
            self._available = True
            log.info(f"Langfuse connected: {host}")
        except Exception as e:
            log.warning(f"Langfuse unavailable ({e}), using no-op tracer")
            self._available = False

    def create_trace(self, name: str, metadata: dict = None) -> str:
        if not self._available:
            return str(uuid.uuid4())
        trace = self._lf.trace(name=name, metadata=metadata or {})
        self._traces[trace.id] = trace
        return trace.id

    def start_span(self, trace_id: str, name: str, input: dict = None) -> str:
        if not self._available:
            return str(uuid.uuid4())
        trace = self._traces.get(trace_id)
        if not trace:
            return str(uuid.uuid4())
        span = trace.span(name=name, input=input or {})
        self._spans[span.id] = span
        return span.id

    def end_span(self, span_id: str, output: dict = None):
        if not self._available:
            return
        span = self._spans.get(span_id)
        if span:
            span.end(output=output or {})

    def finalize_trace(self, trace_id: str, output: dict = None):
        if not self._available:
            return
        try:
            self._lf.flush()
        except Exception as e:
            log.warning(f"Langfuse flush error: {e}")


_tracer_instance = None


def get_tracer() -> LangfuseTracer:
    global _tracer_instance
    if _tracer_instance is None:
        _tracer_instance = LangfuseTracer()
    return _tracer_instance
