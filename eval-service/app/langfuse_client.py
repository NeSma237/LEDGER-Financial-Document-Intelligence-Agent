"""
Thin wrapper around Langfuse so the rest of eval-service (and, if
teammates import this module, the other services) can trace a
pipeline run without sprinkling Langfuse SDK calls everywhere.

Usage:
    from app.langfuse_client import get_langfuse, traced_run

    with traced_run(question_id="q_001", question="...") as run:
        with run.span("retrieval", input={"query": q}) as sp:
            results = do_retrieval(q)
            sp.end(output={"n_results": len(results)})

        with run.span("generation", input={...}) as sp:
            answer = call_llm(...)
            sp.end(output=answer, usage={"input": 120, "output": 40})

If LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are not set, this
degrades to a no-op tracer so the eval pipeline still runs (and can
be demoed) without a Langfuse account configured yet.
"""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional

try:
    from langfuse import Langfuse
    _LANGFUSE_AVAILABLE = True
except ImportError:  # pragma: no cover - allows running before pip install
    _LANGFUSE_AVAILABLE = False


_client: Optional["Langfuse"] = None


def get_langfuse() -> Optional["Langfuse"]:
    """Return a singleton Langfuse client, or None if not configured."""
    global _client
    if not _LANGFUSE_AVAILABLE:
        return None
    if os.getenv("LANGFUSE_PUBLIC_KEY") is None or os.getenv("LANGFUSE_SECRET_KEY") is None:
        return None
    if _client is None:
        _client = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
    return _client


class _NoOpSpan:
    def end(self, **kwargs):
        pass


class _NoOpTrace:
    def span(self, name: str, **kwargs):
        return _NullSpanCtx()

    def update(self, **kwargs):
        pass


class _NullSpanCtx:
    def __enter__(self):
        return _NoOpSpan()

    def __exit__(self, *exc):
        return False


class _RealSpanCtx:
    def __init__(self, langfuse_trace, name: str, input: Any = None):
        self._trace = langfuse_trace
        self._name = name
        self._input = input
        self._span = None
        self._start = None

    def __enter__(self):
        self._start = time.time()
        self._span = self._trace.span(name=self._name, input=self._input)
        return self

    def end(self, output: Any = None, usage: Optional[Dict[str, int]] = None):
        latency_ms = (time.time() - self._start) * 1000 if self._start else None
        self._span.end(output=output, metadata={"latency_ms": latency_ms}, usage=usage)

    def __exit__(self, exc_type, exc, tb):
        if exc is not None:
            self._span.end(level="ERROR", status_message=str(exc))
        return False


class TracedRun:
    """One end-to-end traced request: a question through the pipeline."""

    def __init__(self, question_id: str, question: str):
        lf = get_langfuse()
        self._question_id = question_id
        if lf is not None:
            self._trace = lf.trace(
                name="ledger-pipeline",
                input={"question_id": question_id, "question": question},
                metadata={"question_id": question_id},
            )
        else:
            self._trace = _NoOpTrace()

    def span(self, name: str, input: Any = None):
        if isinstance(self._trace, _NoOpTrace):
            return _NullSpanCtx()
        return _RealSpanCtx(self._trace, name, input)

    def finish(self, output: Any = None):
        if not isinstance(self._trace, _NoOpTrace):
            self._trace.update(output=output)


@contextmanager
def traced_run(question_id: str, question: str):
    run = TracedRun(question_id, question)
    try:
        yield run
    finally:
        pass
