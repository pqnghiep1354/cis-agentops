"""
CIS AgentOps — Langfuse Tracer Wrapper (v4 compatible)
Langfuse v4 uses OpenTelemetry under the hood.
Gracefully degrades to no-op if unavailable.
"""
from __future__ import annotations
import os
import uuid
import logging

log = logging.getLogger(__name__)


class LangfuseTracer:
    def __init__(self):
        host    = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        pub_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
        sec_key = os.getenv("LANGFUSE_SECRET_KEY", "")

        self._available = False
        self._sdk = None

        if not pub_key or not sec_key:
            log.warning("Langfuse keys not set — tracing disabled")
            return

        try:
            # Langfuse v4 SDK
            from langfuse import Langfuse
            self._sdk = Langfuse(
                public_key=pub_key,
                secret_key=sec_key,
                host=host,
            )
            self._available = True
            log.info(f"Langfuse v4 connected: {host}")
        except Exception as e:
            log.warning(f"Langfuse unavailable: {e}")

        self._traces: dict = {}
        self._spans:  dict = {}

    def create_trace(self, name: str, metadata: dict = None) -> str:
        tid = str(uuid.uuid4())
        if not self._available:
            return tid
        try:
            trace = self._sdk.trace(name=name, id=tid, metadata=metadata or {})
            self._traces[tid] = trace
        except Exception as e:
            log.debug(f"create_trace error: {e}")
        return tid

    def start_span(self, trace_id: str, name: str, input: dict = None) -> str:
        sid = str(uuid.uuid4())
        if not self._available:
            return sid
        try:
            trace = self._traces.get(trace_id)
            if trace:
                span = trace.span(name=name, input=input or {})
                self._spans[sid] = span
        except Exception as e:
            log.debug(f"start_span error: {e}")
        return sid

    def end_span(self, span_id: str, output: dict = None):
        if not self._available:
            return
        try:
            span = self._spans.pop(span_id, None)
            if span:
                span.end(output=output or {})
        except Exception as e:
            log.debug(f"end_span error: {e}")

    def finalize_trace(self, trace_id: str, output: dict = None):
        if not self._available:
            return
        try:
            self._sdk.flush()
        except Exception as e:
            log.debug(f"flush error: {e}")


_tracer_instance: LangfuseTracer | None = None


def get_tracer() -> LangfuseTracer:
    global _tracer_instance
    if _tracer_instance is None:
        _tracer_instance = LangfuseTracer()
    return _tracer_instance
