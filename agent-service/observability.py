from contextlib import contextmanager
from pathlib import Path
import os
from typing import Any, Iterator

from dotenv import load_dotenv
from langfuse import Langfuse


load_dotenv(Path(__file__).resolve().parents[1] / "eval-service" / ".env")
_client = None


def _get_client():
    global _client
    if _client is None and os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"):
        _client = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.getenv("LANGFUSE_HOST", os.getenv("LANGFUSE_BASE_URL", "https://cloud.langfuse.com")),
        )
    return _client


@contextmanager
def observation(name: str, input: Any = None) -> Iterator[Any]:
    client = _get_client()
    if client is None:
        yield None
        return
    with client.start_as_current_observation(name=name, as_type="span", input=input) as span:
        try:
            yield span
        except Exception as exc:
            span.update(level="ERROR", status_message=str(exc))
            raise
        finally:
            client.flush()
