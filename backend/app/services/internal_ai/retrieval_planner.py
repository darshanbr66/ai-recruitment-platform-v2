"""Decides what to load for a classified internal AI query, and runs the
matching engine where a candidate<->job question needs an explainable
score. Every read goes through an existing, tenant-scoped service
(application_service/job_service/candidate_service) or an explicit
`organization_id` filter — never a query that could reach another tenant's
rows (CLAUDE.md § 9: "Every AI request must verify... organization... The
AI must only retrieve records the user is authorized to access.").
"""

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import Application, ApplicationStatus
from app.models.candidate import Candidate
from app.models.job import Job, JobStatus
from app.models.match_result import MatchResult
from app.schemas.internal_ai import InternalAIQueryContext
from app.services import application_service, candidate_service, job_service
from app.services.application_service import ApplicationFilters
from app.services.internal_ai.intent_detection import QueryContext, QueryIntent
from app.services.matching import match_engine

#: How many candidates a "find candidates for this role" / pipeline-wide
#: query returns — enough to be useful, capped so one query can't force
#: computing (and returning) an unbounded number of matches.
_MAX_CANDIDATES_PER_QUERY = 10
_NAME_RESOLUTION_LIMIT = 5


@dataclass
class RetrievedData:
    candidates: list[Candidate] = field(default_factory=list)
    jobs: list[Job] = field(default_factory=list)
    #: (candidate, job, match_result) triples — enough for the caller to
    #: build both CandidateCard and MatchCard responses without re-querying.
    matches: list[tuple[Candidate, Job, MatchResult]] = field(default_factory=list)
    pipeline_stats: dict[str, Any] | None = None
    #: Set when nothing could be resolved (e.g. no candidate/job matched a
    #: free-text name) — the caller uses this to shape a helpful reply
    #: instead of silently returning nothing.
    note: str | None = None


async def _resolve_candidates_by_name(
    db: AsyncSession, organization_id: uuid.UUID, names: list[str]
) -> list[Candidate]:
    if not names:
        return []
    conditions = [Candidate.full_name.ilike(f"%{name}%") for name in names]
    result = await db.execute(
        select(Candidate)
        .where(
            Candidate.organization_id == organization_id,
            Candidate.deleted_at.is_(None),
            or_(*conditions),
        )
        .limit(_NAME_RESOLUTION_LIMIT)
    )
    return list(result.scalars().all())


async def _resolve_jobs_by_title(
    db: AsyncSession, organization_id: uuid.UUID, titles: list[str]
) -> list[Job]:
    if not titles:
        return []
    conditions = [Job.title.ilike(f"%{title}%") for title in titles]
    result = await db.execute(
        select(Job)
        .where(Job.organization_id == organization_id, Job.deleted_at.is_(None), or_(*conditions))
        .limit(_NAME_RESOLUTION_LIMIT)
    )
    return list(result.scalars().all())


async def _match_for(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    candidate: Candidate,
    job: Job,
    application_id: uuid.UUID | None,
    requested_by_user_id: uuid.UUID,
    reuse_existing: bool,
) -> MatchResult:
    if reuse_existing:
        existing = await match_engine.get_latest_match(db, candidate_id=candidate.id, job_id=job.id)
        if existing is not None:
            return existing
    return await match_engine.run_match(
        db,
        organization_id=organization_id,
        candidate_id=candidate.id,
        job_id=job.id,
        application_id=application_id,
        requested_by_user_id=requested_by_user_id,
    )


async def _pipeline_stats(db: AsyncSession, organization_id: uuid.UUID) -> dict[str, Any]:
    status_result = await db.execute(
        select(Application.status, func.count(Application.id))
        .where(
            Application.organization_id == organization_id, Application.deleted_at.is_(None)
        )
        .group_by(Application.status)
    )
    status_counts: dict[ApplicationStatus, int] = {
        status: count for status, count in status_result.all()
    }

    open_jobs = await db.scalar(
        select(func.count(Job.id)).where(
            Job.organization_id == organization_id,
            Job.status == JobStatus.OPEN,
            Job.deleted_at.is_(None),
        )
    )
    top_jobs_result = await db.execute(
        select(Job.title, func.count(Application.id).label("count"))
        .join(Application, Application.job_id == Job.id)
        .where(Job.organization_id == organization_id, Application.deleted_at.is_(None))
        .group_by(Job.id, Job.title)
        .order_by(func.count(Application.id).desc())
        .limit(5)
    )
    return {
        "applications_by_status": {
            status.value: count for status, count in status_counts.items()
        },
        "open_jobs": int(open_jobs or 0),
        "top_jobs_by_applications": [
            {"title": title, "application_count": count}
            for title, count in top_jobs_result.all()
        ],
    }


async def plan_and_retrieve(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    requested_by_user_id: uuid.UUID,
    query_context: QueryContext,
    explicit: InternalAIQueryContext,
) -> RetrievedData:
    data = RetrievedData()

    is_pipeline_query = (
        query_context.intent == QueryIntent.PIPELINE_INTELLIGENCE
        and not explicit.candidate_id
        and not explicit.job_id
    )
    if is_pipeline_query:
        data.pipeline_stats = await _pipeline_stats(db, organization_id)
        return data

    # --- Resolve the candidate(s) in scope ---
    candidates: list[Candidate] = []
    if explicit.candidate_id is not None:
        candidate = await candidate_service.get_candidate(db, explicit.candidate_id)
        if candidate is not None:
            candidates = [candidate]
    elif explicit.candidate_ids:
        result = await db.execute(
            select(Candidate).where(
                Candidate.id.in_(explicit.candidate_ids),
                Candidate.organization_id == organization_id,
            )
        )
        candidates = list(result.scalars().all())
    elif query_context.candidate_names:
        candidates = await _resolve_candidates_by_name(
            db, organization_id, query_context.candidate_names
        )

    # --- Resolve the job(s) in scope ---
    jobs: list[Job] = []
    if explicit.job_id is not None:
        job = await job_service.get_job(db, explicit.job_id)
        if job is not None:
            jobs = [job]
    elif explicit.application_id is not None:
        application = await application_service.get_application(db, explicit.application_id)
        if application is not None:
            jobs = [application.job]
            if not candidates:
                candidates = [application.candidate]
    elif query_context.job_titles:
        jobs = await _resolve_jobs_by_title(db, organization_id, query_context.job_titles)

    data.candidates = candidates
    data.jobs = jobs

    if not candidates and not jobs:
        data.note = "I couldn't find a specific candidate or job matching that question."
        return data

    # --- CANDIDATE_SPECIFIC / COMPARISON: one or more candidates, one job ---
    wants_candidate_match = query_context.intent in (
        QueryIntent.CANDIDATE_SPECIFIC, QueryIntent.COMPARISON,
    )
    if candidates and (jobs or wants_candidate_match):
        target_job = jobs[0] if jobs else None
        if target_job is None and len(candidates) == 1:
            # No job named: use the candidate's most recent application.
            applications = await application_service.list_applications(
                db,
                organization_id,
                filters=ApplicationFilters(candidate_id=candidates[0].id),
                limit=1,
            )
            if applications:
                target_job = applications[0].job
                data.jobs = [target_job]
        if target_job is not None:
            # The explicit application_id only ever applies to a single,
            # already-resolved candidate (the caller is viewing that one
            # application) — never spread across a multi-candidate compare.
            single_application_id = (
                explicit.application_id
                if len(candidates) == 1 and explicit.application_id
                else None
            )
            for candidate in candidates[:_MAX_CANDIDATES_PER_QUERY]:
                match = await _match_for(
                    db,
                    organization_id=organization_id,
                    candidate=candidate,
                    job=target_job,
                    application_id=single_application_id,
                    requested_by_user_id=requested_by_user_id,
                    reuse_existing=True,
                )
                data.matches.append((candidate, target_job, match))
        return data

    # --- ROLE_SPECIFIC: one job, find/rank its applicants ---
    if jobs and not candidates:
        target_job = jobs[0]
        applications = await application_service.list_applications(
            db, organization_id, filters=ApplicationFilters(job_id=target_job.id),
            limit=_MAX_CANDIDATES_PER_QUERY,
        )
        for application in applications:
            match = await _match_for(
                db,
                organization_id=organization_id,
                candidate=application.candidate,
                job=target_job,
                application_id=application.id,
                requested_by_user_id=requested_by_user_id,
                reuse_existing=True,
            )
            data.matches.append((application.candidate, target_job, match))
        data.matches.sort(key=lambda triple: triple[2].overall_match_score or 0, reverse=True)
        return data

    return data
