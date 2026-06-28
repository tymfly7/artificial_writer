"""The RQ queue and scheduler, built from ``settings.redis_url``.

Imports of ``redis`` / ``rq`` / ``rq_scheduler`` are kept inside the accessor
functions so this module (and anything importing it) stays light, and so the
optional ``server`` dependencies are only needed when a queue is actually built.
Tests monkeypatch :func:`get_queue` to return an inline (``is_async=False``)
queue backed by ``fakeredis``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ...core.config import get_settings

if TYPE_CHECKING:
    from redis import Redis
    from rq import Queue
    from rq_scheduler import Scheduler

QUEUE_NAME = "default"


def get_redis() -> Redis:
    """Build a Redis connection from ``settings.redis_url``."""
    from redis import Redis

    return Redis.from_url(get_settings().redis_url)


def get_queue() -> Queue:
    """Return the ``"default"`` RQ queue."""
    from rq import Queue

    return Queue(QUEUE_NAME, connection=get_redis())


def get_scheduler() -> Scheduler:
    """Return an rq-scheduler bound to the ``"default"`` queue."""
    from rq_scheduler import Scheduler

    return Scheduler(queue_name=QUEUE_NAME, connection=get_redis())


def run_worker() -> None:  # pragma: no cover - exercised by the worker process
    """Entrypoint (``artwriter-worker``) for an RQ worker on the configured Redis.

    Reads ``settings.redis_url`` so the worker needs no extra ``--url`` flag; this
    is the command the compose ``worker`` service runs.
    """
    from rq import Worker

    from ...core.config import configure_logging

    configure_logging()
    Worker([QUEUE_NAME], connection=get_redis()).work()
