"""Authenticated async batch-summarization endpoints.

``POST /api/batch`` enqueues a :func:`..jobs.tasks.run_batch` job that summarizes
many URLs into one stored digest; ``GET /api/batch/{job_id}`` reports the job's
status and, once finished, the id of the digest it produced. The job runs under
the same tier/quota policy as a single summarize.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ...service.auth import current_user
from ...service.jobs import queue as job_queue
from ...service.jobs import tasks
from ...service.models import User
from ...service.schemas import BatchRequest, JobOut

router = APIRouter(prefix="/api/batch", tags=["batch"])


@router.post("", response_model=JobOut)
async def enqueue_batch(
    req: BatchRequest,
    user: User = Depends(current_user),
) -> JobOut:
    """Enqueue a batch summarization of ``req.urls`` for the authenticated user."""
    job = job_queue.get_queue().enqueue(
        tasks.run_batch,
        str(user.id),
        [str(u) for u in req.urls],
        req.output_format.value if req.output_format else None,
        req.summarizer.value if req.summarizer else None,
        req.model,
    )
    return JobOut(job_id=job.id, status=job.get_status())


@router.get("/{job_id}", response_model=JobOut)
async def batch_status(
    job_id: str,
    user: User = Depends(current_user),
) -> JobOut:
    """Report a batch job's status; include ``digest_id`` once it has finished."""
    from rq.job import Job

    job = Job.fetch(job_id, connection=job_queue.get_queue().connection)
    digest_id = job.result if job.is_finished else None
    return JobOut(job_id=job.id, status=job.get_status(), digest_id=digest_id)
