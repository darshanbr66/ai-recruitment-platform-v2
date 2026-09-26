"""Talk to Admin (app/services/admin_messaging_service.py). Staff-only —
mounted under `/api/v1/recruiter/*`, never on a public or candidate route.

- `/mine...` — the caller's own conversation with the admins
  (`admin_message.send`). No conversation id is accepted, so a staff member
  can only ever reach their own thread.
- `/conversations...` — the admin inbox (`admin_message.manage`), scoped to
  the caller's organization.
- `/unread-count` — whichever side the caller is on (either permission).
"""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, granted_permission_codes, require_permission
from app.core.exceptions import ForbiddenError
from app.db.session import get_db
from app.models.admin_message import AdminConversation, AdminMessage
from app.models.user import User
from app.schemas.admin_message import (
    AdminConversationDetail,
    AdminConversationSummary,
    AdminMessageCreateRequest,
    AdminMessageReadResult,
    AdminMessageResponse,
    AdminMessageUnreadCount,
)
from app.services import admin_messaging_service

router = APIRouter(prefix="/admin-messages", tags=["recruiter-admin-messages"])

SEND = "admin_message.send"
MANAGE = "admin_message.manage"
_PREVIEW_LENGTH = 140


def _organization_member(user: User) -> User:
    if user.organization_id is None:
        raise ForbiddenError("Talk to Admin is only available to organization accounts.")
    return user


async def _staff(user: User = Depends(require_permission(SEND))) -> User:
    return _organization_member(user)


async def _admin(user: User = Depends(require_permission(MANAGE))) -> User:
    return _organization_member(user)


def _message(message: AdminMessage) -> AdminMessageResponse:
    return AdminMessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        body=message.body,
        from_admin=message.from_admin,
        sender_user_id=message.sender_user_id,
        sender_name=message.sender.full_name if message.sender is not None else None,
        created_at=message.created_at,
        read_at=message.read_at,
    )


async def _detail(
    db: AsyncSession, conversation: AdminConversation
) -> AdminConversationDetail:
    messages = await admin_messaging_service.list_messages(db, conversation)
    return AdminConversationDetail(
        id=conversation.id,
        employee_user_id=conversation.employee_user_id,
        employee_name=conversation.employee.full_name,
        employee_email=conversation.employee.email,
        messages=[_message(m) for m in messages],
    )


@router.get("/unread-count", response_model=AdminMessageUnreadCount)
async def unread_count(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AdminMessageUnreadCount:
    """Backs the nav badge: admin replies the caller hasn't read (staff), or
    staff messages no admin has read (admins)."""
    _organization_member(current_user)
    codes = await granted_permission_codes(db, current_user)
    if MANAGE in codes:
        unread = await admin_messaging_service.count_unread_for_admins(db, admin=current_user)
    elif SEND in codes:
        unread = await admin_messaging_service.count_unread_for_staff(db, user=current_user)
    else:
        raise ForbiddenError("You do not have permission to perform this action.")
    return AdminMessageUnreadCount(unread=unread)


@router.get("/mine", response_model=AdminConversationDetail)
async def get_my_conversation(
    current_user: User = Depends(_staff),
    db: AsyncSession = Depends(get_db),
) -> AdminConversationDetail:
    conversation = await admin_messaging_service.get_own_conversation(db, user=current_user)
    if conversation is None:
        return AdminConversationDetail(
            id=None,
            employee_user_id=current_user.id,
            employee_name=current_user.full_name,
            employee_email=current_user.email,
            messages=[],
        )
    return await _detail(db, conversation)


@router.post("/mine", response_model=AdminMessageResponse, status_code=201)
async def send_message_to_admins(
    payload: AdminMessageCreateRequest,
    current_user: User = Depends(_staff),
    db: AsyncSession = Depends(get_db),
) -> AdminMessageResponse:
    message = await admin_messaging_service.send_to_admins(
        db, sender=current_user, body=payload.body
    )
    return _message(message)


@router.post("/mine/read", response_model=AdminMessageReadResult)
async def mark_my_conversation_read(
    current_user: User = Depends(_staff),
    db: AsyncSession = Depends(get_db),
) -> AdminMessageReadResult:
    updated = await admin_messaging_service.mark_own_conversation_read(db, user=current_user)
    return AdminMessageReadResult(updated=updated)


@router.get("/conversations", response_model=list[AdminConversationSummary])
async def list_conversations(
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AdminConversationSummary]:
    summaries = await admin_messaging_service.list_conversations_for_admin(
        db, admin=current_user
    )
    return [
        AdminConversationSummary(
            id=s.conversation.id,
            employee_user_id=s.conversation.employee_user_id,
            employee_name=s.conversation.employee.full_name,
            employee_email=s.conversation.employee.email,
            last_message_at=s.conversation.last_message_at,
            last_message_preview=(
                s.last_message.body[:_PREVIEW_LENGTH] if s.last_message else None
            ),
            last_message_from_admin=s.last_message.from_admin if s.last_message else None,
            unread_count=s.unread_count,
        )
        for s in summaries
    ]


@router.get("/conversations/{conversation_id}", response_model=AdminConversationDetail)
async def get_conversation(
    conversation_id: uuid.UUID,
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminConversationDetail:
    conversation = await admin_messaging_service.get_conversation_for_admin(
        db, admin=current_user, conversation_id=conversation_id
    )
    return await _detail(db, conversation)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=AdminMessageResponse,
    status_code=201,
)
async def reply_to_conversation(
    conversation_id: uuid.UUID,
    payload: AdminMessageCreateRequest,
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminMessageResponse:
    message = await admin_messaging_service.reply_as_admin(
        db, admin=current_user, conversation_id=conversation_id, body=payload.body
    )
    return _message(message)


@router.post("/conversations/{conversation_id}/read", response_model=AdminMessageReadResult)
async def mark_conversation_read(
    conversation_id: uuid.UUID,
    current_user: User = Depends(_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminMessageReadResult:
    updated = await admin_messaging_service.mark_read_as_admin(
        db, admin=current_user, conversation_id=conversation_id
    )
    return AdminMessageReadResult(updated=updated)
