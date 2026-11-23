"""工具注册与调用。"""
from typing import Any

from pydantic import ValidationError

from app.tools.base import (
    ToolArgumentError,
    ToolError,
    ToolSpec,
    UnknownToolError,
)


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

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        spec = self._tools.get(name)
        if spec is None:
            raise UnknownToolError(name)
        try:
            parsed = spec.args_schema.model_validate(arguments)
        except ValidationError as exc:
            raise ToolArgumentError(name, str(exc)) from exc
        try:
            return spec.handler(parsed)
        except ToolError:
            raise
        except Exception as exc:
            raise ToolError("TOOL_EXECUTION_ERROR", f"工具 {name} 执行失败") from exc


def build_default_registry() -> ToolRegistry:
    from app.tools.mock import MockEchoTool

    registry = ToolRegistry()
    registry.register(MockEchoTool)
    return registry
