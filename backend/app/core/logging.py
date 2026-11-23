"""JSON 日志、请求 ID 与敏感信息脱敏。"""
import json
import logging
import re
import sys
from contextvars import ContextVar

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

_DSN_PASSWORD_RE = re.compile(r"(postgresql(?:\+\w+)?://[^:\s]+:)([^@\s]+)(@)", re.IGNORECASE)
_BEARER_RE = re.compile(r"(Bearer\s+)([A-Za-z0-9._\-]+)", re.IGNORECASE)
_SK_RE = re.compile(r"\b(sk-[A-Za-z0-9]{4})[A-Za-z0-9]+")
_REGISTERED_SECRETS: set[str] = set()
_REDACTED = "***REDACTED***"


def register_secret(value: str | None) -> None:
    if value:
        _REGISTERED_SECRETS.add(value)


def clear_registered_secrets() -> None:
    _REGISTERED_SECRETS.clear()


def redact(text: str) -> str:
    if not text:
        return text
    text = _DSN_PASSWORD_RE.sub(r"\1" + _REDACTED + r"\3", text)
    text = _BEARER_RE.sub(r"\1" + _REDACTED, text)
    text = _SK_RE.sub(r"\1" + _REDACTED, text)
    for secret in tuple(_REGISTERED_SECRETS):
        text = text.replace(secret, _REDACTED)
    return text


def current_request_id() -> str:
    return request_id_ctx.get()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(record.getMessage()),
            "request_id": getattr(record, "request_id", None) or current_request_id(),
        }
        for key in ("event", "node_name", "status", "duration_ms", "run_id", "user_id"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO", secrets: tuple[str, ...] = ()) -> None:
    for secret in secrets:
        register_secret(secret)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    logging.getLogger("uvicorn.access").handlers = [handler]
    logging.getLogger("uvicorn.access").propagate = False
