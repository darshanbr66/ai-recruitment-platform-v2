import uuid
from collections import Counter

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.application import ApplicationStatus
from app.models.assessment import AssessmentInvitation, AssessmentResult, InvitationStatus
from app.models.job import JobStatus
from app.models.screening import ScreeningRun, ScreeningStatus
from app.schemas.report import (
    AssessmentSummaryStats,
    CampusDriveCount,
    JobApplicationCount,
    ReportOverview,
    ScreeningSummary,
    StatusCount,
)
from app.services import application_service, campus_drive_service, candidate_service, job_service


async def get_overview(db: AsyncSession, organization_id: uuid.UUID) -> ReportOverview:
    """Aggregates real, tenant-scoped rows — every count here comes from
    the same RLS-protected queries the recruiter/candidate/job endpoints
    use, never a separate denormalized/cached table (docs/database.md
    has no reporting-specific schema yet; this is the honest MVP)."""
    jobs = await job_service.list_jobs(db, organization_id)
    candidates = await candidate_service.list_candidates(db, organization_id)
    applications = await application_service.list_applications(db, organization_id)

    status_counts = Counter(application.status.value for application in applications)
    job_counts = Counter(application.job_id for application in applications)
    job_titles = {job.id: job.title for job in jobs}

    return ReportOverview(
        total_jobs=len(jobs),
        open_jobs=sum(1 for job in jobs if job.status == JobStatus.OPEN),
        total_candidates=len(candidates),
        total_applications=len(applications),
        selected_candidates=sum(1 for a in applications if a.status == ApplicationStatus.SELECTED),
        rejected_candidates=sum(1 for a in applications if a.status == ApplicationStatus.REJECTED),
        hired_candidates=sum(1 for a in applications if a.status == ApplicationStatus.HIRED),
        applications_by_status=[
            StatusCount(status=status, count=count) for status, count in status_counts.items()
        ],
        applications_by_job=[
            JobApplicationCount(job_id=job_id, job_title=job_titles.get(job_id, "Unknown"), count=count)
            for job_id, count in job_counts.most_common()
        ],
        screening=await _screening_summary(db, organization_id),
        assessments=await _assessment_summary(db, organization_id),
        campus_drives=await _campus_drive_counts(db, organization_id),
    )


async def _screening_summary(db: AsyncSession, organization_id: uuid.UUID) -> ScreeningSummary:
    result = await db.execute(
        select(ScreeningRun.status, ScreeningRun.overall_score).where(
            ScreeningRun.organization_id == organization_id
        )
    )
    rows = result.all()
    completed_scores = [score for status, score in rows if status == ScreeningStatus.COMPLETED and score is not None]
    return ScreeningSummary(
        total_runs=len(rows),
        completed=sum(1 for status, _ in rows if status == ScreeningStatus.COMPLETED),
        failed=sum(1 for status, _ in rows if status == ScreeningStatus.FAILED),
        average_score=round(sum(completed_scores) / len(completed_scores), 1) if completed_scores else None,
    )


async def _assessment_summary(db: AsyncSession, organization_id: uuid.UUID) -> AssessmentSummaryStats:
    result = await db.execute(
        select(AssessmentInvitation.id, AssessmentInvitation.status).where(
            AssessmentInvitation.organization_id == organization_id
        )
    )
    invitations = result.all()
    submitted_ids = [inv_id for inv_id, status in invitations if status == InvitationStatus.SUBMITTED]

    passed = 0
    if submitted_ids:
        passed_result = await db.execute(
            select(func.count(AssessmentResult.id)).where(
                AssessmentResult.invitation_id.in_(submitted_ids), AssessmentResult.passed.is_(True)
            )
        )
        passed = passed_result.scalar_one()

    return AssessmentSummaryStats(
        total_invitations=len(invitations), submitted=len(submitted_ids), passed=passed
    )


async def _campus_drive_counts(db: AsyncSession, organization_id: uuid.UUID) -> list[CampusDriveCount]:
    drives = await campus_drive_service.list_campus_drives(db, organization_id)
    counts = await campus_drive_service.application_counts(db, organization_id)
    return [
        CampusDriveCount(drive_id=drive.id, drive_name=drive.name, application_count=counts.get(drive.id, 0))
        for drive in drives
    ]
