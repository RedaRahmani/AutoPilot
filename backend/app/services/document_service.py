from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.models.document import Document
from app.models.user import User
from app.models.workflow import Workflow
from app.models.workflow_run import WorkflowRun


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DocumentServiceError(Exception):
    """Base for all document-service errors."""


class UnsupportedFileTypeError(DocumentServiceError):
    def __init__(self, detected: str | None = None) -> None:
        msg = (
            f"Unsupported file type: {detected!r}"
            if detected
            else "File type could not be determined from content"
        )
        super().__init__(msg)


class FileTooLargeError(DocumentServiceError):
    def __init__(self, limit_bytes: int) -> None:
        super().__init__(
            f"File exceeds the maximum allowed size of {limit_bytes:,} bytes"
        )


class WorkflowNotFoundError(DocumentServiceError):
    def __init__(self, slug: str) -> None:
        super().__init__(f"Workflow '{slug}' not found or is inactive")


class UploadProcessingError(DocumentServiceError):
    """Wraps unexpected I/O or DB failures during upload."""


# ---------------------------------------------------------------------------
# Magic-byte / MIME detection
# ---------------------------------------------------------------------------

# Ordered by signature length descending so longer matches win if prefixes overlap.
_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a", "image/png"),   # PNG (8 bytes)
    (b"\x25\x50\x44\x46", "application/pdf"),               # %PDF (4 bytes)
    (b"\xff\xd8\xff", "image/jpeg"),                        # JPEG SOI (3 bytes)
]
_PROBE_SIZE = 16  # more than enough to match any signature above

_MIME_TO_EXT: dict[str, str] = {
    "application/pdf": ".pdf",
    "image/png": ".png",
    "image/jpeg": ".jpg",
}


def _detect_mime(header: bytes) -> str | None:
    for magic, mime in _SIGNATURES:
        if header.startswith(magic):
            return mime
    return None


# ---------------------------------------------------------------------------
# Return value
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class UploadResult:
    run_id: uuid.UUID
    document_id: uuid.UUID


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_CHUNK_SIZE = 65_536  # 64 KiB — balances memory use and syscall frequency


async def _stream_to_temp(
    file: UploadFile,
    temp_path: Path,
    max_bytes: int,
) -> tuple[str, int, str]:
    """Stream *file* into *temp_path* in chunks.

    Simultaneously:
    - detects MIME from first chunk's magic bytes
    - enforces max_bytes limit
    - computes SHA-256

    Returns ``(detected_mime, total_bytes, sha256_hex)``.

    Raises:
    - ``UnsupportedFileTypeError`` — empty file or unrecognised magic bytes
    - ``FileTooLargeError`` — stream exceeded *max_bytes*
    - ``UploadProcessingError`` — OS-level write failure

    The caller is responsible for unlinking *temp_path* on any exception.
    """
    detected_mime: str | None = None
    total_bytes = 0
    sha = hashlib.sha256()
    first = True

    try:
        with temp_path.open("wb") as fh:
            while True:
                chunk = await file.read(_CHUNK_SIZE)
                if not chunk:
                    break

                if first:
                    detected_mime = _detect_mime(chunk[:_PROBE_SIZE])
                    if detected_mime is None:
                        raise UnsupportedFileTypeError()
                    first = False

                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise FileTooLargeError(max_bytes)

                sha.update(chunk)
                fh.write(chunk)

    except (UnsupportedFileTypeError, FileTooLargeError):
        raise
    except OSError as exc:
        raise UploadProcessingError(f"Disk write failed: {exc}") from exc

    if first:
        # Loop never ran — file was empty.
        raise UnsupportedFileTypeError()

    return detected_mime, total_bytes, sha.hexdigest()  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Main service function
# ---------------------------------------------------------------------------


async def create_document_upload(
    *,
    db: AsyncSession,
    file: UploadFile,
    current_user: User,
    settings: Settings,
) -> UploadResult:
    """Validate, store, and register an uploaded document.

    Flow:
    1. Optionally reject on Content-Length header (non-authoritative fast path).
    2. Stream file to a temp path, detecting MIME and enforcing size limit.
    3. Look up the configured workflow.
    4. Insert Document + WorkflowRun rows and commit.
    5. Atomically rename temp file to its final path.

    Returns an ``UploadResult`` containing the new ``run_id`` and
    ``document_id``.  Cleans up the temp file on any failure before the
    commit; surfaces a detailed ``UploadProcessingError`` if the rename fails
    after a successful commit (split-brain ops scenario).
    """
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Opportunistic early rejection — Content-Length is client-supplied and
    # untrustworthy, but rejecting obvious oversize requests saves disk I/O.
    content_length = (file.headers or {}).get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > settings.max_upload_size_bytes:
                raise FileTooLargeError(settings.max_upload_size_bytes)
        except ValueError:
            pass  # malformed header; the stream check is authoritative

    # ── Phase 1: stream to temp file ─────────────────────────────────────────
    temp_path = upload_dir / f"{uuid.uuid4()}.tmp"

    try:
        detected_mime, total_bytes, hex_digest = await _stream_to_temp(
            file, temp_path, settings.max_upload_size_bytes
        )
    except Exception:
        temp_path.unlink(missing_ok=True)
        raise

    # ── Phase 2: DB records + atomic rename ──────────────────────────────────
    ext = _MIME_TO_EXT[detected_mime]
    final_path = upload_dir / f"{uuid.uuid4()}{ext}"

    try:
        stmt = select(Workflow).where(
            Workflow.slug == settings.default_upload_workflow_slug,
            Workflow.is_active.is_(True),
        )
        result = await db.execute(stmt)
        workflow = result.scalar_one_or_none()
        if workflow is None:
            raise WorkflowNotFoundError(settings.default_upload_workflow_slug)

        document = Document(
            original_filename=file.filename or "",
            storage_path=str(final_path),
            storage_backend="local",
            mime_type=detected_mime,
            file_size_bytes=total_bytes,
            checksum_sha256=hex_digest,
            uploaded_by=current_user.id,
        )
        db.add(document)
        # Flush so SQLAlchemy resolves document.id before we reference it below.
        await db.flush()

        run = WorkflowRun(
            workflow_id=workflow.id,
            document_id=document.id,
            triggered_by=current_user.id,
            status="pending",
        )
        db.add(run)
        await db.commit()

    except (WorkflowNotFoundError, UploadProcessingError):
        temp_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        temp_path.unlink(missing_ok=True)
        raise UploadProcessingError(f"Failed to persist upload records: {exc}") from exc

    # Rename after commit: the file becomes reachable only once its DB record
    # is durable.  Both paths share the same upload_dir so os.rename is atomic.
    try:
        temp_path.rename(final_path)
    except OSError as exc:
        # Split-brain: DB committed but file unreachable.  Surface with
        # enough context for ops to reconcile manually.
        raise UploadProcessingError(
            f"DB records committed (run={run.id}, doc={document.id}) "
            f"but temp→final rename failed: {exc}"
        ) from exc

    return UploadResult(run_id=run.id, document_id=document.id)
