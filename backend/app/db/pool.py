"""PostgreSQL 连接池生命周期。"""
import logging

from psycopg_pool import ConnectionPool

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)
_POOL: ConnectionPool | None = None


def open_pool(settings: Settings | None = None) -> ConnectionPool:
    global _POOL
    if _POOL is None:
        cfg = settings or get_settings()
        pool = ConnectionPool(
            cfg.database_url,
            min_size=cfg.db_pool_min_size,
            max_size=cfg.db_pool_max_size,
            timeout=cfg.db_pool_timeout,
            open=False,
            name="careerpilot",
        )
        pool.open()
        _POOL = pool
        logger.info("db_pool_opened")
    return _POOL


def get_pool() -> ConnectionPool:
    if _POOL is None:
        raise RuntimeError("数据库连接池尚未初始化")
    return _POOL


def close_pool() -> None:
    global _POOL
    if _POOL is not None:
        _POOL.close()
        _POOL = None
        logger.info("db_pool_closed")


def check_database() -> bool:
    try:
        with get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except Exception:
        logger.exception("db_ready_check_failed")
        return False
