from collections.abc import Callable
from typing import Any

from langgraph.config import get_stream_writer


def get_writer() -> Callable[[Any], None]:
    try:
        return get_stream_writer()
    except Exception:
        return lambda _: None
