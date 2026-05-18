from pydantic import BaseModel, Field


class KnowledgeUploadResponse(BaseModel):
    document_id: str
    parsed_chunks_count: int


class SyncVectorsRequest(BaseModel):
    document_id: str = Field(min_length=1, max_length=128)


class SyncVectorsResponse(BaseModel):
    status: str
    message: str
