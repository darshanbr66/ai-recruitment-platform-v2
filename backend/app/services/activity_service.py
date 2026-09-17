"""Append-only activity/audit trail (app/models/activity.py). Every write
goes through `record_activity` — nothing else ever inserts into this table,
and nothing in the app updates or deletes a row here (CLAUDE.md § 3:
candidate deletion, and other destructive/state-changing actions, must not
disappear from the system untraceably)."""

import uuid

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity import Activity
from app.models.user import User


async def record_activity(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor: User | None,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    entity_label: str | None = None,
    description: str | None = None,
    reason: str | None = None,
) -> Activity:
    activity = Activity(
        organization_id=organization_id,
        actor_user_id=actor.id if actor else None,
        actor_name=actor.full_name if actor else None,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_label=entity_label,
        description=description,
        reason=reason,
    )
    db.add(activity)
    await db.flush()
    return activity


async def list_activities(
    db: AsyncSession,
    organization_id: uuid.UUID,
    *,
    search: str | None = None,
    action: str | None = None,
    entity_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[Activity]:
    query = select(Activity).where(Activity.organization_id == organization_id)

    if action:
        query = query.where(Activity.action == action)
    if entity_type:
        query = query.where(Activity.entity_type == entity_type)
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                Activity.entity_label.ilike(term),
                Activity.actor_name.ilike(term),
                Activity.description.ilike(term),
                Activity.reason.ilike(term),
                Activity.action.ilike(term),
            )
        )

    query = query.order_by(Activity.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    return list(result.scalars().all())
