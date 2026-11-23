import pytest

from app.tools.base import ToolArgumentError, UnknownToolError
from app.tools.mock import MockEchoArgs, MockEchoTool
from app.tools.registry import ToolRegistry, build_default_registry


def test_default_registry_has_only_mock_tool():
    registry = build_default_registry()
    assert registry.names == ("mock_echo",)
    definitions = registry.definitions()
    assert definitions[0]["function"]["name"] == "mock_echo"


def test_execute_mock_echo():
    registry = build_default_registry()
    result = registry.execute("mock_echo", {"text": "hello"})
    assert result == {"echo": "hello", "mock": True, "business_implemented": False}


def test_unknown_tool_rejected():
    registry = build_default_registry()
    with pytest.raises(UnknownToolError):
        registry.execute("search_jobs", {"query": "python"})


def test_invalid_tool_arguments_rejected():
    registry = build_default_registry()
    with pytest.raises(ToolArgumentError):
        registry.execute("mock_echo", {"text": ""})


def test_duplicate_registration_rejected():
    registry = ToolRegistry()
    registry.register(MockEchoTool)
    with pytest.raises(ValueError):
        registry.register(MockEchoTool)


def test_tool_schema_is_pydantic_derived():
    schema = MockEchoArgs.model_json_schema()
    assert schema["required"] == ["text"]
    assert schema["properties"]["text"]["maxLength"] == 2000
