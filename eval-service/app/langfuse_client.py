"""
Thin wrapper around Langfuse so the rest of eval-service (and, if
teammates import this module, the other services) can trace a
pipeline run without sprinkling Langfuse SDK calls everywhere.

Usage:
    from app.langfuse_client import traced_run

    with traced_run(question_id="q_001", question="...") as run:
        with run.span("retrieval", input={"query": q}) as sp:
            results = do_retrieval(q)
            sp.end(output={"n_results": len(results)})

        with run.span("generation", input={...}) as sp:
            answer = call_llm(...)
            sp.end(output=answer, usage={"input": 120, "output": 40})

If LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are not set, this
degrades to a no-op tracer so the eval pipeline still runs without a
Langfuse account configured.

NOTE ON SDK VERSION: `pip install langfuse` currently pulls v4.x,
which replaced the old `client.trace(...)` / `trace.span(...)` API
with an OpenTelemetry-based one (`start_as_current_observation`).
There is no `.trace()` method on the v4 client at all — code written
against the old API raises AttributeError the moment real keys are
set and it actually runs. This module targets the real, installed
v4 API. A "trace" isn't its own object anymore — it's just whatever
span you start first with no parent active; nesting happens
automatically via OTel's context, not by passing a trace object
around.
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
    if not os.getenv("LANGFUSE_PUBLIC_KEY") or not os.getenv("LANGFUSE_SECRET_KEY"):
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


class _NullSpanCtx:
    def __enter__(self):
        return _NoOpSpan()

    def __exit__(self, *exc):
        return False


class _RealSpanCtx:
    """Wraps a real v4 `start_as_current_observation(...)` context
    manager so callers get the same `sp.end(output=..., usage=...)`
    shape regardless of whether tracing is actually on."""

    def __init__(self, cm):
        self._cm = cm
        self._span = None
        self._start = None

    def __enter__(self):
        self._start = time.time()
        self._span = self._cm.__enter__()
        return self

    def end(self, output: Any = None, usage: Optional[Dict[str, int]] = None):
        latency_ms = (time.time() - self._start) * 1000 if self._start else None
        update_kwargs: Dict[str, Any] = {"output": output, "metadata": {"latency_ms": latency_ms}}
        if usage:
            update_kwargs["usage_details"] = usage
        self._span.update(**update_kwargs)

    def __exit__(self, exc_type, exc, tb):
        if exc is not None:
            self._span.update(level="ERROR", status_message=str(exc))
        return self._cm.__exit__(exc_type, exc, tb)


class TracedRun:
    """One end-to-end traced request: a question through the pipeline.

    The root span here IS the trace — v4 has no separate trace object.
    Every `.span(...)` called inside the `with traced_run(...)` block
    nests under it automatically via OTel's active-span context.
    """

    def __init__(self, question_id: str, question: str):
        self._client = get_langfuse()
        self._root_cm = None
        self._root_span = None
        if self._client is not None:
            self._root_cm = self._client.start_as_current_observation(
                name="ledger-pipeline",
                as_type="span",
                input={"question_id": question_id, "question": question},
                metadata={"question_id": question_id},
            )
            self._root_span = self._root_cm.__enter__()

    def span(self, name: str, input: Any = None):
        if self._client is None:
            return _NullSpanCtx()
        cm = self._client.start_as_current_observation(name=name, as_type="span", input=input)
        return _RealSpanCtx(cm)

    def finish(self, output: Any = None):
        if self._root_span is not None:
            self._root_span.update(output=output)

    def _close(self):
        if self._root_cm is not None:
            self._root_cm.__exit__(None, None, None)


@contextmanager
def traced_run(question_id: str, question: str):
    run = TracedRun(question_id, question)
    try:
        yield run
    finally:
        run._close()