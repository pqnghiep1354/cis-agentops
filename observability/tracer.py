"""
CIS AgentOps — Langfuse Tracer (thread-safe, no singleton)
Creates fresh Langfuse instance per pipeline run.
"""
from __future__ import annotations
import os
import uuid
import logging

log = logging.getLogger(__name__)


def _make_lf():
    """Create a fresh Langfuse instance from current env vars."""
    host    = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
    pub_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    sec_key = os.environ.get("LANGFUSE_SECRET_KEY", "")

    if not pub_key or not sec_key:
        return None
    try:
        from langfuse import Langfuse
        lf = Langfuse(public_key=pub_key, secret_key=sec_key, host=host)
        print(f"[Langfuse] connected: {host[:30]} pk={pub_key[:16]}", flush=True)
        return lf
    except Exception as e:
        print(f"[Langfuse] init error: {e}", flush=True)
        return None


class LangfuseTracer:
    """One instance per pipeline run — not a singleton."""

    def __init__(self):
        self._lf     = _make_lf()
        self._traces: dict = {}
        self._spans:  dict = {}

    @property
    def _available(self) -> bool:
        return self._lf is not None

    def create_trace(self, name: str, metadata: dict = None) -> str:
        tid = str(uuid.uuid4())
        return self.create_trace_with_id(tid, name, metadata)

    def create_trace_with_id(self, trace_id: str, name: str, metadata: dict = None) -> str:
        if not self._lf:
            return trace_id
        try:
            trace = self._lf.trace(name=name, id=trace_id, metadata=metadata or {})
            self._traces[trace_id] = trace
            print(f"[Langfuse] trace created: {trace_id[:8]} name={name}", flush=True)
        except Exception as e:
            print(f"[Langfuse] create_trace error: {e}", flush=True)
        return trace_id

    def start_span(self, trace_id: str, name: str, input: dict = None) -> str:
        sid = str(uuid.uuid4())
        if not self._lf:
            return sid
        try:
            trace = self._traces.get(trace_id)
            if trace:
                span = trace.span(name=name, input=input or {})
                self._spans[sid] = span
        except Exception as e:
            print(f"[Langfuse] start_span error: {e}", flush=True)
        return sid

    def end_span(self, span_id: str, output: dict = None):
        if not self._lf:
            return
        try:
            span = self._spans.pop(span_id, None)
            if span:
                span.end(output=output or {})
        except Exception as e:
            print(f"[Langfuse] end_span error: {e}", flush=True)

    def finalize_trace(self, trace_id: str, output: dict = None):
        if not self._lf:
            return
        try:
            self._lf.flush()
            print(f"[Langfuse] flushed {trace_id[:8]}", flush=True)
        except Exception as e:
            print(f"[Langfuse] flush error: {e}", flush=True)


def get_tracer() -> LangfuseTracer:
    """Create a fresh tracer per call — safe for background threads."""
    return LangfuseTracer()
