"""模型与工具元信息（不发起真实模型调用）。"""
from fastapi import APIRouter, Depends

from app.api.deps import AuthContext, get_auth_context
from app.core.llm import LLMClient
from app.core.logging import current_request_id
from app.schemas.chat import LLMStatusOut, ToolListOut, ToolOut
from app.schemas.common import ApiResponse
from app.tools import FUTURE_TOOL_NAMES, build_default_registry

router = APIRouter(tags=["meta"])


@router.get("/llm/status", response_model=ApiResponse[LLMStatusOut])
def llm_status(
    _: AuthContext = Depends(get_auth_context),
) -> ApiResponse[LLMStatusOut]:
    status = LLMClient().status()
    return ApiResponse(
        data=LLMStatusOut.model_validate(status),
        request_id=current_request_id(),
    )


@router.get("/tools", response_model=ApiResponse[ToolListOut])
def list_tools(
    _: AuthContext = Depends(get_auth_context),
) -> ApiResponse[ToolListOut]:
    registry = build_default_registry()
    registered = [
        ToolOut(
            name=spec.name,
            description=spec.description,
            input_schema=spec.args_schema.model_json_schema(),
        )
        for spec in registry.specs()
    ]
    return ApiResponse(
        data=ToolListOut(
            registered=registered,
            planned=list(FUTURE_TOOL_NAMES),
        ),
        request_id=current_request_id(),
    )
