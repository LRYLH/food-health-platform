from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from ..core.config import settings


def _knowledge_dir() -> Path:
    path = settings.knowledge_upload_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


async def save_knowledge_document(file: UploadFile) -> tuple[str, int]:
    suffix = Path(file.filename or "").suffix or ".bin"
    document_id = uuid4().hex
    path = _knowledge_dir() / f"{document_id}{suffix}"
    content = await file.read()
    path.write_bytes(content)
    return document_id, _estimate_chunks(content)


def _estimate_chunks(content: bytes, chunk_size: int = 1200) -> int:
    if not content:
        return 0
    return max(1, (len(content) + chunk_size - 1) // chunk_size)
