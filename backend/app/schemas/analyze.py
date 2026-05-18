from datetime import datetime

from pydantic import BaseModel

from ..models.scan_history import ScanStatus


class TaskSubmitResponse(BaseModel):
    task_id: str
    status: ScanStatus


class RagResultPayload(BaseModel):
    answer: str
    reference: list[str]


class TaskStatusResponse(BaseModel):
    status: ScanStatus
    result: RagResultPayload | None = None


class HistoryRecord(BaseModel):
    task_id: str
    food_name: str | None
    risk_level: str
    created_at: datetime


class HistoryResponse(BaseModel):
    total: int
    records: list[HistoryRecord]
