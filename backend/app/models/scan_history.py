from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, Enum, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base


class ScanStatus(StrEnum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class RiskLevel(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"
    unknown = "unknown"


class ScanHistory(Base):
    __tablename__ = "scan_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    image_path: Mapped[str | None] = mapped_column(String(255))
    question: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus),
        default=ScanStatus.pending,
        index=True,
    )
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel),
        default=RiskLevel.unknown,
    )
    summary: Mapped[str | None] = mapped_column(Text)
    warnings: Mapped[list[str]] = mapped_column(JSON, default=list)
    suggestions: Mapped[list[str]] = mapped_column(JSON, default=list)
    extracted_text: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_result: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = relationship("User", back_populates="scan_history")
