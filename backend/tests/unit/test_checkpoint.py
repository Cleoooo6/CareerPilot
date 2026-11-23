import pytest
from langgraph.checkpoint.memory import MemorySaver

from app.agents.checkpoint import create_checkpointer


def test_memory_checkpointer_is_explicitly_memory_only():
    checkpointer = create_checkpointer("memory")
    assert isinstance(checkpointer, MemorySaver)


def test_postgres_checkpoint_is_not_implemented():
    with pytest.raises(NotImplementedError):
        create_checkpointer("postgres")
