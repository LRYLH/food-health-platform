from pathlib import Path
import shutil
from uuid import uuid4

from fastapi import UploadFile

from ..core.config import settings


class KnowledgeDocumentNotFound(FileNotFoundError):
    pass


def _knowledge_dir() -> Path:
    path = settings.knowledge_upload_dir
    path.mkdir(parents=True, exist_ok=True)
    return path


def _standards_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / "algorithm" / "data" / "standards"
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


def find_knowledge_document(document_id: str) -> Path:
    matches = sorted(_knowledge_dir().glob(f"{document_id}.*"))
    if not matches:
        raise KnowledgeDocumentNotFound(f"Knowledge document not found: {document_id}")
    return matches[0]


def stage_knowledge_document(document_id: str) -> Path:
    source = find_knowledge_document(document_id)
    target = _standards_dir() / source.name
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
    return target


def sync_knowledge_vectors(document_id: str) -> None:
    stage_knowledge_document(document_id)

    from ..algorithm.rag_engine.indexer import main as run_indexer

    run_indexer()
