from __future__ import annotations

import asyncio
from contextlib import suppress
import logging

from .database import SessionLocal
from .services.core import active_session, finish_due_timer, observe_distraction, utcnow
from .services.delivery import deliver_pending_telegram, poll_telegram_callbacks


logger = logging.getLogger(__name__)


async def worker_loop(interval_seconds: int = 10):
    while True:
        db = SessionLocal()
        try:
            now = utcnow()
            session = active_session(db)
            if session and session.status == "running":
                if not finish_due_timer(db, session, now):
                    observe_distraction(db, session, now)
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Focus timer or distraction worker failed")
        finally:
            db.close()

        for operation, label in (
            (deliver_pending_telegram, "Telegram delivery"),
            (poll_telegram_callbacks, "Telegram callback polling"),
        ):
            db = SessionLocal()
            try:
                await operation(db)
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("%s failed", label)
            finally:
                db.close()
        await asyncio.sleep(interval_seconds)


async def stop_worker(task: asyncio.Task | None):
    if not task:
        return
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
