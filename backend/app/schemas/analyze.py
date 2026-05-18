from datetime import datetime

from pydantic import BaseModel, Field

from ..models.scan_history import RiskLevel, ScanStatus


class AnalyzeSubmitResponse(BaseModel):
    task_id: str
    status: ScanStatus
    message: str


class AnalyzeResultResponse(BaseModel):
    task_id: str
    status: ScanStatus
    risk_level: RiskLevel
    summary: str | None
    warnings: list[str]
    suggestions: list[str]
    extracted_text: dict
    raw_result: dict
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ScanHistoryItem(BaseModel):
    task_id: str
    status: ScanStatus
    risk_level: RiskLevel
    summary: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AnalyzeTextRequest(BaseModel):
    product_name: str | None = Field(default=None, max_length=128)
    ingredients: list[str] = Field(default_factory=list)
    nutrition: dict[str, str | float | int] = Field(default_factory=dict)
    question: str | None = Field(default=None, max_length=500)


class AnalyzeResultRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=64)


class TaskSubmitResponse(BaseModel):
    task_id: str
    status: ScanStatus


class TaskResultPayload(BaseModel):
    food_name: str | None
    ingredients: list[str]
    risk_level: str
    health_advice: str
    tts_audio_url: str | None = None


class TaskStatusResponse(BaseModel):
    status: ScanStatus
    result: TaskResultPayload | None = None


class HistoryRecord(BaseModel):
    task_id: str
    food_name: str | None
    risk_level: str
    created_at: datetime


class HistoryResponse(BaseModel):
    total: int
    records: list[HistoryRecord]
