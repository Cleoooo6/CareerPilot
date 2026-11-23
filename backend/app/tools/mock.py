"""阶段一唯一真实注册的工具：Mock 回声工具。

它不是职业业务工具，只用于验证注册/参数校验/调用/结果回传链路。
"""
from typing import Any

from pydantic import BaseModel, Field

from app.tools.base import ToolSpec


class MockEchoArgs(BaseModel):
    text: str = Field(min_length=1, max_length=2000, description="要回显的文本")


def _echo(args: MockEchoArgs) -> dict[str, Any]:
    return {"echo": args.text, "mock": True, "business_implemented": False}


MockEchoTool = ToolSpec(
    name="mock_echo",
    description="阶段一 Mock 工具：验证工具注册、参数校验与调用链路，不代表业务能力。",
    args_schema=MockEchoArgs,
    handler=_echo,
)
