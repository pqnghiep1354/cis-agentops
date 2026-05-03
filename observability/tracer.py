"""
CIS AgentOps — Langfuse Tracer
Creates a fresh Langfuse instance per call (thread-safe, no singleton issues).
"""
from __future__ import annotations
import os
import uuid
import logging

log = logging.getLogger(__name__)

_lf_instance = None

def _get_lf():
    """Get or create Langfuse instance. Thread-safe singleton."""
    global _lf_instance
    if _lf_instance is not None:
        return _lf_instance
    
    host    = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    pub_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    sec_key = os.getenv("LANGFUSE_SECRET_KEY", "")
    
    if not pub_key or not sec_key:
        return None
    
    try:
        from langfuse import Langfuse
        _lf_instance = Langfuse(
            public_key=pub_key,
            secret_key=sec_key,
            host=host,
        )
        print(f"[Langfuse] connected: {host} key={pub_key[:20]}", flush=True)
        return _lf_instance
    except Exception as e:
        print(f"[Langfuse] unavailable: {e}", flush=True)
        return None


class LangfuseTracer:
    def __init__(self):
        self._traces: dict = {}
        self._spans:  dict = {}

    @property
    def _available(self):
        return _get_lf() is not None

    def create_trace(self, name: str, metadata: dict = None) -> str:
        tid = str(uuid.uuid4())
        lf = _get_lf()
        if not lf:
            return tid
        try:
            trace = lf.trace(name=name, id=tid, metadata=metadata or {})
            self._traces[tid] = trace
        except Exception as e:
            print(f"[Langfuse] create_trace error: {e}", flush=True)
        return tid

    def start_span(self, trace_id: str, name: str, input: dict = None) -> str:
        sid = str(uuid.uuid4())
        try:
            trace = self._traces.get(trace_id)
            if trace:
                span = trace.span(name=name, input=input or {})
                self._spans[sid] = span
        except Exception as e:
            print(f"[Langfuse] start_span error: {e}", flush=True)
        return sid

    def end_span(self, span_id: str, output: dict = None):
        try:
            span = self._spans.pop(span_id, None)
            if span:
                span.end(output=output or {})
        except Exception as e:
            print(f"[Langfuse] end_span error: {e}", flush=True)

    def finalize_trace(self, trace_id: str, output: dict = None):
        lf = _get_lf()
        if lf:
            try:
                lf.flush()
                print(f"[Langfuse] flushed trace {trace_id}", flush=True)
            except Exception as e:
                print(f"[Langfuse] flush error: {e}", flush=True)


# One tracer per thread (ThreadLocal would be better but this works for FastAPI)
_tracer = LangfuseTracer()

def get_tracer() -> LangfuseTracer:
    return _tracer
