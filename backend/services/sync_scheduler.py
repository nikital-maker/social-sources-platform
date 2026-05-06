import asyncio
import logging
from datetime import datetime, timezone

from backend.services.sync_config import list_sync_configs, run_sync_for_config

log = logging.getLogger(__name__)

_CHECK_INTERVAL_SECONDS = 60
_task: asyncio.Task | None = None


def _minutes_since(ts_str: str | None) -> float:
    if not ts_str:
        return float("inf")
    try:
        ts = datetime.fromisoformat(str(ts_str).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts).total_seconds() / 60
    except Exception:
        return float("inf")


async def _sync_loop():
    log.info("Sync scheduler started (check every %ds)", _CHECK_INTERVAL_SECONDS)
    while True:
        try:
            await asyncio.sleep(_CHECK_INTERVAL_SECONDS)
            configs = list_sync_configs()
            for cfg in configs:
                if not cfg.get("sync_enabled"):
                    continue
                interval = int(cfg.get("sync_interval_minutes", 30) or 30)
                elapsed = _minutes_since(cfg.get("last_sync_at"))
                if elapsed < interval:
                    continue
                log.info(
                    "Auto-sync: %s / %s (last sync %.0f min ago, interval %d min)",
                    cfg.get("spreadsheet_name"), cfg.get("tab_title"), elapsed, interval,
                )
                try:
                    result = await asyncio.to_thread(run_sync_for_config, cfg)
                    log.info("Auto-sync result: %s", result)
                except Exception:
                    log.exception("Auto-sync failed for config %s", cfg.get("id"))
        except asyncio.CancelledError:
            log.info("Sync scheduler stopped")
            break
        except Exception:
            log.exception("Sync scheduler tick error")


def start_scheduler():
    global _task
    if _task is None or _task.done():
        _task = asyncio.create_task(_sync_loop())


def stop_scheduler():
    global _task
    if _task and not _task.done():
        _task.cancel()
        _task = None
