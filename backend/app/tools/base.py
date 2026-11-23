"""工具注册基础类型。"""
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel


class ToolError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class UnknownToolError(ToolError):
    def __init__(self, name: str) -> None:
        super().__init__("UNKNOWN_TOOL", f"未注册的工具：{name}")


class ToolArgumentError(ToolError):
    def __init__(self, name: str, message: str) -> None:
        super().__init__("TOOL_ARGUMENT_ERROR", f"工具 {name} 参数非法：{message}")


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_schema: type[BaseModel]
    handler: Callable[[BaseModel], dict[str, Any]]

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.args_schema.model_json_schema(),
            },
        }
