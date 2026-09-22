"""Notes — both the original application-scoped shared commentary
(`list_notes`/`create_note` against one Application) and the standalone
personal Notes workspace (`list_my_notes`), which can also link to a
candidate, a job, or nothing at all. One table, one set of rules — never a
parallel Notes implementation.

Visibility (`NoteVisibility`) governs reads only: PRIVATE notes are filtered
out of every listing here unless the caller is the author. Only the author
may ever update or delete a note (enforced here, not just at the API layer,
so a future caller of this module can't accidentally bypass it) — shared
visibility means "others can read it", never "others can edit it".
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.job import Job
from app.models.note import Note, NoteVisibility
from app.models.user import User
from app.services import activity_service


async def _validate_links(
    db: AsyncSession,
    *,
    application_id: uuid.UUID | None,
    candidate_id: uuid.UUID | None,
    job_id: uuid.UUID | None,
) -> None:
    """RLS already scopes `db.get()` to the caller's own tenant, so an id
    from another organization is indistinguishable from a nonexistent one —
    exactly the 404 this raises (the same pattern application_service.py
    uses for its own foreign references)."""
    if application_id is not None and await db.get(Application, application_id) is None:
        raise NotFoundError("Application not found.")
    if candidate_id is not None and await db.get(Candidate, candidate_id) is None:
        raise NotFoundError("Candidate not found.")
    if job_id is not None and await db.get(Job, job_id) is None:
        raise NotFoundError("Job not found.")

SortField = Literal["created_at", "updated_at", "title"]


async def create_note(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    actor: User,
    body: str,
    title: str | None = None,
    category: str | None = None,
    color: str | None = None,
    visibility: NoteVisibility = NoteVisibility.SHARED,
    application_id: uuid.UUID | None = None,
    candidate_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
) -> Note:
    await _validate_links(
        db, application_id=application_id, candidate_id=candidate_id, job_id=job_id
    )
    note = Note(
        organization_id=organization_id,
        author_id=actor.id,
        body=body,
        title=title,
        category=category,
        color=color,
        visibility=visibility,
        application_id=application_id,
        candidate_id=candidate_id,
        job_id=job_id,
    )
    db.add(note)
    await db.flush()

    # Never the body — only safe, non-sensitive metadata, even for a
    # PRIVATE note (the same "title/category, never content" rule every
    # activity entry below follows).
    await activity_service.record_activity(
        db,
        organization_id=organization_id,
        actor=actor,
        action="NOTE_CREATED",
        entity_type="note",
        entity_id=note.id,
        entity_label=title or "Untitled note",
        description=f"Created a {visibility.value.lower()} note.",
    )

    reloaded = await db.execute(
        select(Note).where(Note.id == note.id).options(joinedload(Note.author))
    )
    return reloaded.scalar_one()


def _visible_to(user_id: uuid.UUID) -> ColumnElement[bool]:
    """A note is visible to `user_id` if it's SHARED, or if they wrote it —
    the one rule every listing in this module applies."""
    return or_(Note.visibility == NoteVisibility.SHARED, Note.author_id == user_id)


async def list_notes(
    db: AsyncSession, application_id: uuid.UUID, *, current_user_id: uuid.UUID
) -> list[Note]:
    """The application detail page's note feed — unchanged in shape, now
    also honoring visibility (a PRIVATE note created for this application
    from the standalone workspace is hidden from anyone but its author,
    same as everywhere else)."""
    result = await db.execute(
        select(Note)
        .where(Note.application_id == application_id, _visible_to(current_user_id))
        .options(joinedload(Note.author))
        .order_by(Note.created_at.desc())
    )
    return list(result.scalars().all())


async def get_note(db: AsyncSession, note_id: uuid.UUID) -> Note | None:
    result = await db.execute(
        select(Note).where(Note.id == note_id).options(joinedload(Note.author))
    )
    return result.scalar_one_or_none()


async def list_my_notes(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    user_id: uuid.UUID,
    search: str | None = None,
    category: str | None = None,
    visibility: NoteVisibility | None = None,
    candidate_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    sort: SortField = "created_at",
    descending: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> list[Note]:
    """The standalone Notes workspace: every note visible to `user_id` —
    their own (private or shared) plus everyone else's shared ones —
    searchable/filterable/sortable. Pinned notes always sort first,
    regardless of the chosen sort field, which only orders within each of
    the two groups (pinned / not pinned)."""
    query = (
        select(Note)
        .where(Note.organization_id == organization_id, _visible_to(user_id))
        .options(joinedload(Note.author))
    )
    if search:
        term = f"%{search.strip()}%"
        # Title/body/category on the note itself, plus the name of a linked
        # candidate or job — never the linked entity's other fields, and
        # never a cross-tenant lookup (the subqueries are already implicitly
        # scoped to rows this note could reference, since the FK targets
        # were validated against the caller's own tenant when linked).
        query = query.where(
            or_(
                Note.title.ilike(term),
                Note.body.ilike(term),
                Note.category.ilike(term),
                Note.candidate_id.in_(select(Candidate.id).where(Candidate.full_name.ilike(term))),
                Note.job_id.in_(select(Job.id).where(Job.title.ilike(term))),
            )
        )
    if category:
        query = query.where(Note.category == category)
    if visibility:
        query = query.where(Note.visibility == visibility)
    if candidate_id:
        query = query.where(Note.candidate_id == candidate_id)
    if job_id:
        query = query.where(Note.job_id == job_id)

    sort_columns = {
        "created_at": Note.created_at, "updated_at": Note.updated_at, "title": Note.title,
    }
    sort_column = sort_columns[sort]
    query = query.order_by(
        Note.pinned.desc(),
        sort_column.desc() if descending else sort_column.asc(),
        Note.id.asc(),
    )
    query = query.limit(limit).offset(offset)

    result = await db.execute(query)
    return list(result.scalars().all())


def _require_author(note: Note, user_id: uuid.UUID) -> None:
    if note.author_id != user_id:
        raise ForbiddenError("Only the author can edit or delete this note.")


async def update_note(
    db: AsyncSession,
    note: Note,
    *,
    actor: User,
    title: str | None | Literal["__unset__"] = "__unset__",
    body: str | None = None,
    category: str | None | Literal["__unset__"] = "__unset__",
    color: str | None | Literal["__unset__"] = "__unset__",
    visibility: NoteVisibility | None = None,
    candidate_id: uuid.UUID | None | Literal["__unset__"] = "__unset__",
    job_id: uuid.UUID | None | Literal["__unset__"] = "__unset__",
    application_id: uuid.UUID | None | Literal["__unset__"] = "__unset__",
) -> Note:
    """`"__unset__"` (vs. `None`) distinguishes "leave this field alone"
    from "clear it" for the nullable fields — a PATCH must be able to
    explicitly unlink a candidate/job/application, not just add one."""
    _require_author(note, actor.id)

    await _validate_links(
        db,
        application_id=application_id if application_id != "__unset__" else None,
        candidate_id=candidate_id if candidate_id != "__unset__" else None,
        job_id=job_id if job_id != "__unset__" else None,
    )

    visibility_changed = visibility is not None and visibility != note.visibility

    if body is not None:
        note.body = body
    if title != "__unset__":
        note.title = title
    if category != "__unset__":
        note.category = category
    if color != "__unset__":
        note.color = color
    if visibility is not None:
        note.visibility = visibility
    if candidate_id != "__unset__":
        note.candidate_id = candidate_id
    if job_id != "__unset__":
        note.job_id = job_id
    if application_id != "__unset__":
        note.application_id = application_id

    await db.flush()

    description = "Updated a note."
    if visibility_changed:
        description = f"Changed a note's visibility to {note.visibility.value.lower()}."
    await activity_service.record_activity(
        db,
        organization_id=note.organization_id,
        actor=actor,
        action="NOTE_UPDATED",
        entity_type="note",
        entity_id=note.id,
        entity_label=note.title or "Untitled note",
        description=description,
    )
    return note


async def toggle_pin(db: AsyncSession, note: Note, *, actor: User) -> Note:
    """Author-only, like every other note edit — pinning is metadata about
    the note, not a per-viewer preference (see the model's docstring)."""
    _require_author(note, actor.id)
    note.pinned = not note.pinned
    note.pinned_at = datetime.now(UTC) if note.pinned else None
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=note.organization_id,
        actor=actor,
        action="NOTE_PINNED" if note.pinned else "NOTE_UNPINNED",
        entity_type="note",
        entity_id=note.id,
        entity_label=note.title or "Untitled note",
        description=f"{'Pinned' if note.pinned else 'Unpinned'} a note.",
    )
    return note


async def delete_note(db: AsyncSession, note: Note, *, actor: User) -> None:
    _require_author(note, actor.id)
    note_id, title, organization_id = note.id, note.title, note.organization_id
    await db.delete(note)
    await db.flush()

    await activity_service.record_activity(
        db,
        organization_id=organization_id,
        actor=actor,
        action="NOTE_DELETED",
        entity_type="note",
        entity_id=note_id,
        entity_label=title or "Untitled note",
        description="Deleted a note.",
    )
