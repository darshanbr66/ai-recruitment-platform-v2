import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.note import Note


async def create_note(
    db: AsyncSession, *, organization_id: uuid.UUID, application_id: uuid.UUID, author_id: uuid.UUID, body: str
) -> Note:
    note = Note(
        organization_id=organization_id, application_id=application_id, author_id=author_id, body=body
    )
    db.add(note)
    await db.flush()
    reloaded = await db.execute(
        select(Note).where(Note.id == note.id).options(joinedload(Note.author))
    )
    return reloaded.scalar_one()


async def list_notes(db: AsyncSession, application_id: uuid.UUID) -> list[Note]:
    result = await db.execute(
        select(Note)
        .where(Note.application_id == application_id)
        .options(joinedload(Note.author))
        .order_by(Note.created_at.desc())
    )
    return list(result.scalars().all())
