"""Talk to Admin — internal staff <-> organization-admin messaging
(app/models/admin_message.py).

Two sides, decided by permission at the API layer, never by the caller's
say-so: a staff member (`admin_message.send`) has exactly one conversation —
their own — and reaches it only through "mine" operations that take no
conversation id, so they cannot address anyone else's. The admin side
(`admin_message.manage`) sees every conversation in its organization and
addresses them by id; every such lookup is scoped to the caller's
organization here on top of RLS, so another tenant's id is a plain 404.

Read state: a message is unread until the *other* side opens the
conversation; opening marks that side's incoming messages read (and, on the
admin side, records which admin read them). Plain REST — the UI polls.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.exceptions import NotFoundError
from app.models.admin_message import AdminConversation, AdminMessage
from app.models.user import User

#: Most recent messages returned for one conversation (oldest first).
MESSAGE_PAGE_SIZE = 200


@dataclass(frozen=True)
class ConversationSummary:
    conversation: AdminConversation
    last_message: AdminMessage | None
    unread_count: int


def _organization_id(user: User) -> uuid.UUID:
    # The API layer only lets organization members in; a platform account
    # (organization_id NULL) never reaches here.
    assert user.organization_id is not None
    return user.organization_id


async def get_own_conversation(db: AsyncSession, *, user: User) -> AdminConversation | None:
    return await db.scalar(
        select(AdminConversation)
        .where(
            AdminConversation.organization_id == _organization_id(user),
            AdminConversation.employee_user_id == user.id,
        )
        .options(joinedload(AdminConversation.employee))
    )


async def _get_or_create_own_conversation(db: AsyncSession, *, user: User) -> AdminConversation:
    conversation = await get_own_conversation(db, user=user)
    if conversation is not None:
        return conversation
    conversation = AdminConversation(
        organization_id=_organization_id(user), employee_user_id=user.id
    )
    db.add(conversation)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        # A concurrent first message created it; use that one.
        conversation = await get_own_conversation(db, user=user)
        assert conversation is not None
    return conversation


async def get_conversation_for_admin(
    db: AsyncSession, *, admin: User, conversation_id: uuid.UUID
) -> AdminConversation:
    conversation = await db.scalar(
        select(AdminConversation)
        .where(
            AdminConversation.id == conversation_id,
            AdminConversation.organization_id == _organization_id(admin),
        )
        .options(joinedload(AdminConversation.employee))
    )
    if conversation is None:
        raise NotFoundError("Conversation not found.")
    return conversation


async def list_messages(
    db: AsyncSession, conversation: AdminConversation
) -> list[AdminMessage]:
    newest = (
        await db.execute(
            select(AdminMessage)
            .where(
                AdminMessage.conversation_id == conversation.id,
                AdminMessage.organization_id == conversation.organization_id,
            )
            .options(joinedload(AdminMessage.sender))
            .order_by(AdminMessage.created_at.desc(), AdminMessage.id.desc())
            .limit(MESSAGE_PAGE_SIZE)
        )
    ).scalars()
    return list(reversed(list(newest)))


async def _post(
    db: AsyncSession,
    *,
    conversation: AdminConversation,
    sender: User,
    from_admin: bool,
    body: str,
) -> AdminMessage:
    message = AdminMessage(
        organization_id=conversation.organization_id,
        conversation_id=conversation.id,
        sender_user_id=sender.id,
        from_admin=from_admin,
        body=body,
        # Wall-clock, not the transaction's now(): two messages written in
        # one transaction must still order correctly.
        created_at=datetime.now(UTC),
    )
    db.add(message)
    await db.flush()
    # The message row's own timestamp, so ordering and the inbox agree.
    conversation.last_message_at = message.created_at
    await db.flush()
    await db.refresh(message, attribute_names=["sender"])
    return message


async def send_to_admins(db: AsyncSession, *, sender: User, body: str) -> AdminMessage:
    conversation = await _get_or_create_own_conversation(db, user=sender)
    return await _post(db, conversation=conversation, sender=sender, from_admin=False, body=body)


async def reply_as_admin(
    db: AsyncSession, *, admin: User, conversation_id: uuid.UUID, body: str
) -> AdminMessage:
    conversation = await get_conversation_for_admin(
        db, admin=admin, conversation_id=conversation_id
    )
    return await _post(db, conversation=conversation, sender=admin, from_admin=True, body=body)


async def _mark_read(
    db: AsyncSession, *, conversation: AdminConversation, from_admin: bool, reader: User
) -> int:
    result = await db.execute(
        update(AdminMessage)
        .where(
            AdminMessage.conversation_id == conversation.id,
            AdminMessage.organization_id == conversation.organization_id,
            AdminMessage.from_admin.is_(from_admin),
            AdminMessage.read_at.is_(None),
        )
        .values(read_at=datetime.now(UTC), read_by_user_id=reader.id)
        .execution_options(synchronize_session=False)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


async def mark_own_conversation_read(db: AsyncSession, *, user: User) -> int:
    """The staff member opened their conversation: admins' replies are read."""
    conversation = await get_own_conversation(db, user=user)
    if conversation is None:
        return 0
    return await _mark_read(db, conversation=conversation, from_admin=True, reader=user)


async def mark_read_as_admin(
    db: AsyncSession, *, admin: User, conversation_id: uuid.UUID
) -> int:
    """An admin opened the conversation: the staff member's messages are read."""
    conversation = await get_conversation_for_admin(
        db, admin=admin, conversation_id=conversation_id
    )
    return await _mark_read(db, conversation=conversation, from_admin=False, reader=admin)


async def count_unread_for_staff(db: AsyncSession, *, user: User) -> int:
    """Admin replies the staff member hasn't opened yet."""
    count = await db.scalar(
        select(func.count(AdminMessage.id))
        .join(AdminConversation, AdminConversation.id == AdminMessage.conversation_id)
        .where(
            AdminConversation.organization_id == _organization_id(user),
            AdminConversation.employee_user_id == user.id,
            AdminMessage.from_admin.is_(True),
            AdminMessage.read_at.is_(None),
        )
    )
    return int(count or 0)


async def count_unread_for_admins(db: AsyncSession, *, admin: User) -> int:
    """Staff messages in the organization no admin has opened yet."""
    count = await db.scalar(
        select(func.count(AdminMessage.id)).where(
            AdminMessage.organization_id == _organization_id(admin),
            AdminMessage.from_admin.is_(False),
            AdminMessage.read_at.is_(None),
        )
    )
    return int(count or 0)


async def list_conversations_for_admin(
    db: AsyncSession, *, admin: User
) -> list[ConversationSummary]:
    """The organization's conversations, most recent activity first, each
    with its newest message and its unread (staff -> admin) count — three
    set-based queries, no per-conversation round trips."""
    organization_id = _organization_id(admin)
    conversations = list(
        (
            await db.execute(
                select(AdminConversation)
                .where(
                    AdminConversation.organization_id == organization_id,
                    AdminConversation.last_message_at.is_not(None),
                )
                .options(joinedload(AdminConversation.employee))
                .order_by(AdminConversation.last_message_at.desc(), AdminConversation.id)
            )
        ).scalars()
    )
    if not conversations:
        return []
    ids = [c.id for c in conversations]

    unread_rows = await db.execute(
        select(AdminMessage.conversation_id, func.count(AdminMessage.id))
        .where(
            AdminMessage.organization_id == organization_id,
            AdminMessage.conversation_id.in_(ids),
            AdminMessage.from_admin.is_(False),
            AdminMessage.read_at.is_(None),
        )
        .group_by(AdminMessage.conversation_id)
    )
    unread = {conversation_id: int(count) for conversation_id, count in unread_rows.all()}

    latest = (
        await db.execute(
            select(AdminMessage)
            .where(
                AdminMessage.organization_id == organization_id,
                AdminMessage.conversation_id.in_(ids),
            )
            .distinct(AdminMessage.conversation_id)
            .order_by(
                AdminMessage.conversation_id,
                AdminMessage.created_at.desc(),
                AdminMessage.id.desc(),
            )
        )
    ).scalars()
    latest_by_conversation = {m.conversation_id: m for m in latest}

    return [
        ConversationSummary(
            conversation=c,
            last_message=latest_by_conversation.get(c.id),
            unread_count=unread.get(c.id, 0),
        )
        for c in conversations
    ]
