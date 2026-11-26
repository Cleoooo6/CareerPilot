import argparse
import asyncio
import logging
import time

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.pool import close_pool, open_pool
from app.industry_pulse.sources import FEED_SOURCES, source_by_key
from app.services.industry_pulse_service import get_industry_pulse_service

logger = logging.getLogger(__name__)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="CareerPilot Industry Pulse RSS collector")
    parser.add_argument("--once", action="store_true", help="执行单轮采集后退出")
    parser.add_argument("--interval", type=int, default=0, help="持续运行间隔秒数")
    parser.add_argument(
        "--source",
        default="",
        help="只采集指定 key，多个用逗号分隔；默认全部启用来源",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=0,
        help="覆盖单个 Feed 的最大条目数（1-100）",
    )
    parser.add_argument(
        "--max-new-articles",
        type=int,
        default=0,
        help="全局最多新增文章数；0 表示不限制",
    )
    return parser.parse_args()


def _selected_sources(raw: str):
    if not raw.strip():
        return None
    keys = [item.strip() for item in raw.split(",") if item.strip()]
    selected = []
    for key in keys:
        source = source_by_key(key)
        if source is None:
            raise SystemExit(f"未知来源: {key}")
        selected.append(source)
    return tuple(selected)


def _run_once(selected, max_items: int, max_new_articles: int) -> dict:
    settings = get_settings()
    if max_items:
        settings.industry_pulse_max_items_per_feed = max(1, min(100, max_items))
    cap = max_new_articles if max_new_articles > 0 else None
    result = asyncio.run(
        get_industry_pulse_service().collect_once(
            sources=selected, max_new_articles=cap
        )
    )
    logger.info("industry_pulse_run_result %s", result)
    return result


def main() -> None:
    args = _parse_args()
    settings = get_settings()
    configure_logging(settings.log_level)
    selected = _selected_sources(args.source)
    open_pool(settings)
    try:
        if args.once or args.interval <= 0:
            _run_once(selected, args.max_items, args.max_new_articles)
            return
        logger.info("industry_pulse_interval_start seconds=%s", args.interval)
        while True:
            try:
                _run_once(selected, args.max_items, args.max_new_articles)
            except Exception:
                logger.exception("industry_pulse_interval_run_failed")
            time.sleep(max(1, args.interval))
    except KeyboardInterrupt:
        logger.info("industry_pulse_stopped")
    finally:
        close_pool()


if __name__ == "__main__":
    main()