"""统一领域异常。"""
from typing import Any


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class NotFoundError(AppError):
    def __init__(self, message: str = "资源不存在", details: dict[str, Any] | None = None):
        super().__init__("NOT_FOUND", message, status_code=404, details=details)


class ConflictError(AppError):
    def __init__(self, message: str = "资源状态冲突", details: dict[str, Any] | None = None):
        super().__init__("CONFLICT", message, status_code=409, details=details)


class ForbiddenError(AppError):
    def __init__(self, message: str = "无权访问该资源", details: dict[str, Any] | None = None):
        super().__init__("FORBIDDEN", message, status_code=403, details=details)
