"""Recruiter freeform notes on an Application."""

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_permission
from app.db.session import get_db
from app.models.note import Note
from app.models.user import User
from app.schemas.note import NoteCreateRequest, NoteResponse
from app.services import note_service

router = APIRouter(prefix="/applications/{application_id}/notes", tags=["recruiter-notes"])


def _to_response(note: Note) -> NoteResponse:
    return NoteResponse(
        id=note.id,
        application_id=note.application_id,
        author_id=note.author_id,
        author_name=note.author.full_name,
        body=note.body,
        created_at=note.created_at,
    )


@router.get("", response_model=list[NoteResponse])
async def list_notes(
    application_id: uuid.UUID,
    _: User = Depends(require_permission("note.read")),
    db: AsyncSession = Depends(get_db),
) -> list[NoteResponse]:
    notes = await note_service.list_notes(db, application_id)
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
        author_id=current_user.id,
        body=payload.body,
    )
    return _to_response(note)
