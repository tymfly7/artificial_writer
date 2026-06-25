"""Multi-tenant service layer for Artificial Writer.

This package adds the data + auth layer that turns the single-user engine in
:mod:`artificial_writer.core` into a multi-tenant web service: SQLAlchemy 2.0
async models, password/API-key authentication, a per-user repository, and the
one ``summarize_for_user`` entry point the web layer calls.

It depends on ``core`` but never changes its behavior. Everything here is
optional and only required when the ``server`` extra is installed.
"""

from __future__ import annotations
