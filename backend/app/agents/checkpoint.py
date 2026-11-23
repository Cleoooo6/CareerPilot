"""Checkpoint 设计边界。

阶段一提供 Checkpoint 工厂接口，但默认且唯一实现是进程内 MemorySaver。

事实声明：
- MemorySaver 不是持久化能力；进程退出后状态丢失。
- PostgreSQL 持久化 checkpoint 本阶段未实现、未验证。
- 业务会话历史由 PostgreSQL 的 conversation/message/agent_run 表保存，
  不等同于 LangGraph Checkpoint。
"""
from langgraph.checkpoint.memory import MemorySaver


def create_checkpointer(backend: str = "memory"):
    if backend != "memory":
        raise NotImplementedError(
            "阶段一仅实现 MemorySaver；PostgreSQL 持久化 Checkpoint 未实现"
        )
    return MemorySaver()
