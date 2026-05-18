from fastapi import APIRouter, File, UploadFile

from ...schemas.admin import (
    KnowledgeUploadResponse,
    SyncVectorsRequest,
    SyncVectorsResponse,
)
from ...services.knowledge_service import save_knowledge_document


router = APIRouter(prefix="/admin/knowledge", tags=["admin-knowledge"])


@router.post("/upload", response_model=KnowledgeUploadResponse)
async def upload_knowledge_document(
    file: UploadFile = File(...),
) -> KnowledgeUploadResponse:
    document_id, chunks_count = await save_knowledge_document(file)
    return KnowledgeUploadResponse(
        document_id=document_id,
        parsed_chunks_count=chunks_count,
    )


@router.post("/sync-vectors", response_model=SyncVectorsResponse)
def sync_knowledge_vectors(_: SyncVectorsRequest) -> SyncVectorsResponse:
    return SyncVectorsResponse(
        status="syncing",
        message="后台已开始向量化入库",
    )
