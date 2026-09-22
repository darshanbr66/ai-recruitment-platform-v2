"""Notes: the original application-scoped shared commentary (`router`,
mounted under `/applications/{id}/notes`) and the standalone personal Notes
workspace (`workspace_router`, mounted at `/notes`) — one Note model, one
set of visibility/ownership rules (app/services/note_service.py), never two
Notes implementations.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.core.exceptions import NotFoundError
from app.db.session import get_db
from app.models.note import Note, NoteVisibility
from app.models.user import User
from app.schemas.note import (
    NoteCreateRequest,
    NoteResponse,
    NoteUpdateRequest,
    StandaloneNoteCreateRequest,
)
from app.services import note_service

router = APIRouter(prefix="/applications/{application_id}/notes", tags=["recruiter-notes"])
workspace_router = APIRouter(prefix="/notes", tags=["recruiter-notes"])


def _to_response(note: Note) -> NoteResponse:
    return NoteResponse(
        id=note.id,
        application_id=note.application_id,
        candidate_id=note.candidate_id,
        job_id=note.job_id,
        author_id=note.author_id,
        author_name=note.author.full_name,
        title=note.title,
        body=note.body,
        category=note.category,
        color=note.color,
        visibility=note.visibility,
        pinned=note.pinned,
        pinned_at=note.pinned_at,
        created_at=note.created_at,
        updated_at=note.updated_at,
    )


# --- application-scoped (unchanged shape, now visibility-aware) ------------


@router.get("", response_model=list[NoteResponse])
async def list_notes(
    application_id: uuid.UUID,
    current_user: User = Depends(require_permission("note.read")),
    db: AsyncSession = Depends(get_db),
) -> list[NoteResponse]:
    notes = await note_service.list_notes(db, application_id, current_user_id=current_user.id)
    return [_to_response(note) for note in notes]


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_note(
    application_id: uuid.UUID,
    payload: NoteCreateRequest,
    current_user: User = Depends(require_permission("note.manage")),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    assert current_user.organization_id is not None
    note = await note_service.create_note(
        db,
        organization_id=current_user.organization_id,
        application_id=application_id,
        actor=current_user,
        body=payload.body,
        title=payload.title,
        category=payload.category,
        color=payload.color,
        visibility=payload.visibility,
    )
    return _to_response(note)


# --- standalone personal Notes workspace ------------------------------------


@workspace_router.get("", response_model=list[NoteResponse])
async def list_my_notes(
    current_user: User = Depends(require_permission("note.read")),
    db: AsyncSession = Depends(get_db),
    search: str | None = Query(default=None, max_length=200),
    category: str | None = Query(default=None, max_length=100),
    visibility: NoteVisibility | None = Query(default=None),
    candidate_id: uuid.UUID | None = Query(default=None),
    job_id: uuid.UUID | None = Query(default=None),
    sort: str = Query(default="created_at", pattern="^(created_at|updated_at|title)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[NoteResponse]:
    assert current_user.organization_id is not None
    notes = await note_service.list_my_notes(
        db,
        organization_id=current_user.organization_id,
        user_id=current_user.id,
        search=search,
        category=category,
        visibility=visibility,
        candidate_id=candidate_id,
        job_id=job_id,
        sort=sort,  # type: ignore[arg-type]
        descending=order == "desc",
        limit=limit,
        offset=offset,
    )
    return [_to_response(note) for note in notes]


@workspace_router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_my_note(
    payload: StandaloneNoteCreateRequest,
    current_user: User = Depends(require_permission("note.manage")),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    assert current_user.organization_id is not None
    note = await note_service.create_note(
        db,
        organization_id=current_user.organization_id,
        actor=current_user,
        body=payload.body,
        title=payload.title,
        category=payload.category,
        color=payload.color,
        visibility=payload.visibility,
        application_id=payload.application_id,
        candidate_id=payload.candidate_id,
        job_id=payload.job_id,
    )
    return _to_response(note)


async def _get_visible_note(db: AsyncSession, note_id: uuid.UUID, current_user: User) -> Note:
    note = await note_service.get_note(db, note_id)
    if note is None:
        raise NotFoundError("Note not found.")
    if note.visibility == NoteVisibility.PRIVATE and note.author_id != current_user.id:
        # Indistinguishable from "not found" — a private note's existence is
        # not even confirmed to anyone but its author.
        raise NotFoundError("Note not found.")
    return note


@workspace_router.get("/{note_id}", response_model=NoteResponse)
async def get_my_note(
    note_id: uuid.UUID,
    current_user: User = Depends(require_permission("note.read")),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    note = await _get_visible_note(db, note_id, current_user)
    return _to_response(note)


@workspace_router.patch("/{note_id}", response_model=NoteResponse)
async def update_my_note(
    note_id: uuid.UUID,
    payload: NoteUpdateRequest,
    current_user: User = Depends(require_permission("note.manage")),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    note = await _get_visible_note(db, note_id, current_user)
    fields = payload.model_fields_set
    updated = await note_service.update_note(
        db,
        note,
        actor=current_user,
        body=payload.body,
        title=payload.title if "title" in fields else "__unset__",
        category=payload.category if "category" in fields else "__unset__",
        color=payload.color if "color" in fields else "__unset__",
        visibility=payload.visibility,
        application_id=payload.application_id if "application_id" in fields else "__unset__",
        candidate_id=payload.candidate_id if "candidate_id" in fields else "__unset__",
        job_id=payload.job_id if "job_id" in fields else "__unset__",
    )
    return _to_response(updated)


@workspace_router.post("/{note_id}/pin", response_model=NoteResponse)
async def toggle_pin_my_note(
    note_id: uuid.UUID,
    current_user: User = Depends(require_permission("note.manage")),
    db: AsyncSession = Depends(get_db),
) -> NoteResponse:
    """Toggles pinned/unpinned — author-only, same as any other edit."""
    note = await _get_visible_note(db, note_id, current_user)
    updated = await note_service.toggle_pin(db, note, actor=current_user)
    return _to_response(updated)


@workspace_router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_note(
    note_id: uuid.UUID,
    current_user: User = Depends(require_permission("note.manage")),
    db: AsyncSession = Depends(get_db),
) -> None:
    note = await _get_visible_note(db, note_id, current_user)
    await note_service.delete_note(db, note, actor=current_user)
