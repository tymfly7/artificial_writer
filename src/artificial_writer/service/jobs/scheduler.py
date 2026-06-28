"""Register and run the periodic feed-polling schedule.

Each :class:`~..models.Feed` is polled on its own ``cadence_minutes`` interval by
an rq-scheduler job that enqueues :func:`..jobs.tasks.poll_feed`. :func:`main` is
the entrypoint for the dedicated ``scheduler`` process (e.g. a compose service):
it registers the schedule from the current feeds, then runs the scheduler loop.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ...core.config import configure_logging
from .. import repository
from ..db import get_sessionmaker
from . import queue, tasks

if TYPE_CHECKING:
    from rq_scheduler import Scheduler

logger = logging.getLogger(__name__)

_JOB_ID_PREFIX = "poll-feed-"


def _job_id(feed_id: object) -> str:
    return f"{_JOB_ID_PREFIX}{feed_id}"


async def _all_feeds() -> list[tuple[str, int]]:
    """Return ``(feed_id, cadence_minutes)`` for every feed."""
    async with get_sessionmaker()() as session:
        return [(str(f.id), f.cadence_minutes) for f in await repository.list_all_feeds(session)]


def register_feed_schedules(scheduler: Scheduler | None = None) -> int:
    """(Re)register a periodic ``poll_feed`` job for every feed.

    Existing feed-poll jobs are cancelled first so the schedule always reflects
    the current set of feeds and cadences. Returns the number of jobs registered.
    """
    sched = scheduler if scheduler is not None else queue.get_scheduler()

    # Drop any previously-registered feed-poll jobs to avoid duplicates.
    for job in sched.get_jobs():
        if job.id.startswith(_JOB_ID_PREFIX):
            sched.cancel(job)

    feeds = asyncio.run(_all_feeds())
    now = datetime.now(timezone.utc)
    for feed_id, cadence_minutes in feeds:
        sched.schedule(
            scheduled_time=now,
            func=tasks.poll_feed,
            args=[feed_id],
            interval=max(cadence_minutes, 1) * 60,
            repeat=None,  # repeat forever
            id=_job_id(feed_id),
        )
    logger.info("Registered %d feed-poll schedule(s)", len(feeds))
    return len(feeds)


def main() -> None:
    """Entrypoint for the scheduler process: register schedules and run the loop."""
    configure_logging()
    scheduler = queue.get_scheduler()
    register_feed_schedules(scheduler)
    logger.info("Starting feed-poll scheduler loop")
    scheduler.run()


if __name__ == "__main__":  # pragma: no cover
    main()
