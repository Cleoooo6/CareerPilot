"""工具注册与调用。"""
from contextvars import ContextVar
from typing import Any

from pydantic import ValidationError

from app.tools.base import (
    ToolArgumentError,
    ToolError,
    ToolSpec,
    UnknownToolError,
)

_current_tool_user_id: ContextVar[str | None] = ContextVar(
    "tool_user_id", default=None
)


def get_tool_user_id() -> str | None:
    return _current_tool_user_id.get()


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        if spec.name in self._tools:
            raise ValueError(f"工具重复注册：{spec.name}")
        self._tools[spec.name] = spec

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._tools))

    def definitions(self) -> list[dict[str, Any]]:
        return [self._tools[name].openai_schema() for name in self.names]

    def specs(self) -> list[ToolSpec]:
        return [self._tools[name] for name in self.names]

    def execute(
        self,
        name: str,
        arguments: dict[str, Any],
        *,
        user_id: str | None = None,
    ) -> dict[str, Any]:
        spec = self._tools.get(name)
        if spec is None:
            raise UnknownToolError(name)
        try:
            parsed = spec.args_schema.model_validate(arguments)
        except ValidationError as exc:
            raise ToolArgumentError(name, str(exc)) from exc
        token = _current_tool_user_id.set(user_id)
        try:
            return spec.handler(parsed)
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError("TOOL_EXECUTION_ERROR", f"工具 {name} 执行失败") from exc
        finally:
            _current_tool_user_id.reset(token)


def build_default_registry() -> ToolRegistry:
    from app.tools.market import MARKET_TOOLS
    from app.tools.mock import MockEchoTool
    from app.tools.roadmap import ROADMAP_TOOLS

    registry = ToolRegistry()
    registry.register(MockEchoTool)
    for tool in MARKET_TOOLS:
        registry.register(tool)
    for tool in ROADMAP_TOOLS:
        registry.register(tool)
    return registry
