from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from ...schemas.admin import (
    KnowledgeUploadResponse,
    SyncVectorsRequest,
    SyncVectorsResponse,
)
from ...services.knowledge_service import (
    KnowledgeDocumentNotFound,
    save_knowledge_document,
    stage_knowledge_document,
    sync_knowledge_vectors as run_vector_sync,
)


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
def sync_knowledge_vectors(
    payload: SyncVectorsRequest,
    background_tasks: BackgroundTasks,
) -> SyncVectorsResponse:
    try:
        stage_knowledge_document(payload.document_id)
    except KnowledgeDocumentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    background_tasks.add_task(run_vector_sync, payload.document_id)
    return SyncVectorsResponse(
        status="syncing",
        message="Vector sync started",
    )
