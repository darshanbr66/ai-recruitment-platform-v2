import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TenantScopedMixin, TimestampMixin, UUIDPrimaryKeyMixin


class CandidateReapplyGrant(UUIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, Base):
    """An HR user allowing one candidate to self-apply again before the
    3-month reapply window has passed (app/services/reapply_service.py).

    Single-use: the candidate's next self-service application stamps
    `used_at` / `used_by_application_id`, after which the normal window
    applies again. At most one unused grant per candidate (partial unique
    index). Rows are never deleted — together with the
    CANDIDATE_REAPPLY_GRANTED / CANDIDATE_REAPPLY_GRANT_USED activities they
    are the audit trail of who allowed what, when and why.
    """

    __tablename__ = "candidate_reapply_grants"
    __table_args__ = (
        Index(
            "uq_candidate_reapply_grants_open",
            "candidate_id",
            unique=True,
            postgresql_where="used_at IS NULL",
        ),
    )

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # SET NULL keeps the grant if the account is ever removed; the actor's
    # name is also snapshotted on the matching Activity row.
    granted_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_by_application_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("applications.id", ondelete="SET NULL"), nullable=True
    )
