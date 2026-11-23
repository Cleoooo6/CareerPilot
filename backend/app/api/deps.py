"""开发态用户身份依赖。

注意：这不是认证。阶段一只用 X-User-Id 或默认 demo-user 做数据隔离骨架；
真正的登录、密码、令牌与授权在后续阶段实现。
"""
import re

from fastapi import Header

from app.core.config import get_settings
from app.core.errors import AppError

_USER_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def get_user_id(x_user_id: str | None = Header(default=None, alias="X-User-Id")) -> str:
    user_id = (x_user_id or get_settings().default_user_id).strip()
    if not _USER_ID_RE.fullmatch(user_id):
        raise AppError(
            "INVALID_USER_ID",
            "X-User-Id 只允许 1-64 位字母、数字、下划线、点和短横线",
            status_code=400,
        )
    return user_id
