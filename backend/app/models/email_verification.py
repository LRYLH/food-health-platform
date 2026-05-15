from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class EmailVerificationPurpose(StrEnum):
    register = "register"


class EmailVerificationCode(Base):
    __tablename__ = "email_verification_codes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    purpose: Mapped[EmailVerificationPurpose] = mapped_column(
        Enum(EmailVerificationPurpose),
        index=True,
    )
    code_hash: Mapped[str] = mapped_column(String(255))
    is_used: Mapped[bool] = mapped_column(default=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime)
    sent_ip: Mapped[str | None] = mapped_column(String(64))
    verify_attempts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )
