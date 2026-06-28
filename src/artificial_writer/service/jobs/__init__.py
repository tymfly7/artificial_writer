"""Asynchronous background jobs: batch summarization and scheduled feed polling.

RQ workers run the synchronous task functions in :mod:`.tasks`; the queue and
scheduler are built from ``settings.redis_url`` in :mod:`.queue`. This package is
part of the optional ``server`` extra (it needs ``redis``, ``rq``,
``rq-scheduler``, and ``feedparser``).
"""

from __future__ import annotations
