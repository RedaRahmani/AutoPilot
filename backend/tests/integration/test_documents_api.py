"""
Integration tests for POST /api/documents/upload.

All requests are real multipart uploads using bytes that genuinely match or
fail the server's magic-byte detection.  The DB session is rolled back after
each test so the database remains clean between runs.
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.user import User
from app.models.workflow import Workflow
from app.models.workflow_run import WorkflowRun

# ── Byte fixtures with real magic signatures ──────────────────────────────────

_PDF = b"%PDF-1.4 \n" + b"\x00" * 512
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 512
_JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 512
_TXT = b"Not a recognised file type"


def _file(
    content: bytes,
    filename: str = "invoice.pdf",
    content_type: str = "application/octet-stream",
) -> tuple:
    """Build a (field_name, (filename, file_obj, content_type)) tuple for httpx."""
    return ("file", (filename, io.BytesIO(content), content_type))


# ── Auth / access control ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_unauthenticated_returns_401(client: AsyncClient) -> None:
    response = await client.post(
        "/api/documents/upload",
        files=[_file(_PDF)],
    )
    assert response.status_code == 401


# ── Happy path ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_valid_pdf_returns_202_with_run_id(
    client: AsyncClient,
    auth_token: str,
) -> None:
    response = await client.post(
        "/api/documents/upload",
        files=[_file(_PDF)],
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 202
    body = response.json()
    assert "run_id" in body
    uuid.UUID(body["run_id"])  # must be a valid UUID; raises ValueError if not


@pytest.mark.asyncio
async def test_upload_valid_png_returns_202(
    client: AsyncClient,
    auth_token: str,
) -> None:
    response = await client.post(
        "/api/documents/upload",
        files=[_file(_PNG, "scan.png", "image/png")],
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_upload_valid_jpeg_returns_202(
    client: AsyncClient,
    auth_token: str,
) -> None:
    response = await client.post(
        "/api/documents/upload",
        files=[_file(_JPG, "photo.jpg", "image/jpeg")],
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 202


# ── Error cases ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_bad_file_type_returns_400(
    client: AsyncClient,
    auth_token: str,
) -> None:
    """Plain-text bytes must be rejected even when the client claims PDF."""
    response = await client.post(
        "/api/documents/upload",
        # Client lies about content-type; server must detect from magic bytes.
        files=[_file(_TXT, "fake.pdf", "application/pdf")],
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_upload_too_large_returns_413(
    client: AsyncClient,
    auth_token: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.core.config import get_settings

    # Tighten the limit so the ~522-byte _PDF sample exceeds it.
    monkeypatch.setattr(get_settings(), "max_upload_size_bytes", 10)

    response = await client.post(
        "/api/documents/upload",
        files=[_file(_PDF)],
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 413


# ── DB state after a successful upload ───────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_creates_document_row(
    client: AsyncClient,
    auth_token: str,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    response = await client.post(
        "/api/documents/upload",
        files=[_file(_PDF, "invoice.pdf", "application/pdf")],
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 202

    result = await db_session.execute(
        select(Document).where(Document.uploaded_by == test_user.id)
    )
    doc = result.scalar_one()

    assert doc.original_filename == "invoice.pdf"
    assert doc.mime_type == "application/pdf"
    assert doc.file_size_bytes == len(_PDF)
    assert doc.checksum_sha256 is not None
    assert len(doc.checksum_sha256) == 64  # SHA-256 hex digest
    assert doc.uploaded_by == test_user.id
    assert doc.storage_backend == "local"


@pytest.mark.asyncio
async def test_upload_creates_workflow_run_row(
    client: AsyncClient,
    auth_token: str,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    response = await client.post(
        "/api/documents/upload",
        files=[_file(_PDF)],
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 202
    run_id = uuid.UUID(response.json()["run_id"])

    run_result = await db_session.execute(
        select(WorkflowRun).where(WorkflowRun.id == run_id)
    )
    run = run_result.scalar_one()

    assert run.document_id is not None
    assert run.triggered_by == test_user.id
    assert run.status == "pending"

    # Confirm the run is linked to the invoice_processing workflow.
    wf_result = await db_session.execute(
        select(Workflow).where(Workflow.slug == "invoice_processing")
    )
    workflow = wf_result.scalar_one()
    assert run.workflow_id == workflow.id


@pytest.mark.asyncio
async def test_upload_links_document_and_run(
    client: AsyncClient,
    auth_token: str,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    """The WorkflowRun must reference the Document created in the same request."""
    response = await client.post(
        "/api/documents/upload",
        files=[_file(_PDF)],
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 202
    run_id = uuid.UUID(response.json()["run_id"])

    doc_result = await db_session.execute(
        select(Document).where(Document.uploaded_by == test_user.id)
    )
    doc = doc_result.scalar_one()

    run_result = await db_session.execute(
        select(WorkflowRun).where(WorkflowRun.id == run_id)
    )
    run = run_result.scalar_one()

    assert run.document_id == doc.id


# ── File persistence ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upload_file_written_to_upload_dir(
    client: AsyncClient,
    auth_token: str,
    test_user: User,
    db_session: AsyncSession,
    tmp_upload_dir: Path,
) -> None:
    response = await client.post(
        "/api/documents/upload",
        files=[_file(_PDF)],
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 202

    result = await db_session.execute(
        select(Document).where(Document.uploaded_by == test_user.id)
    )
    doc = result.scalar_one()
    storage = Path(doc.storage_path)

    assert storage.exists(), "Uploaded file must be present on disk after upload"
    assert storage.parent.resolve() == tmp_upload_dir.resolve()


@pytest.mark.asyncio
async def test_storage_path_is_uuid_based_not_original_filename(
    client: AsyncClient,
    auth_token: str,
    test_user: User,
    db_session: AsyncSession,
) -> None:
    """
    Storage path must be UUID-based.  The original filename is recorded as
    metadata only; it must not appear in the on-disk path.
    """
    original_filename = "confidential_invoice_2024.pdf"
    response = await client.post(
        "/api/documents/upload",
        files=[_file(_PDF, original_filename, "application/pdf")],
        headers={"Authorization": f"Bearer {auth_token}"},
    )
    assert response.status_code == 202

    result = await db_session.execute(
        select(Document).where(Document.uploaded_by == test_user.id)
    )
    doc = result.scalar_one()

    assert "confidential_invoice_2024" not in Path(doc.storage_path).name
    # original_filename is still stored as metadata
    assert doc.original_filename == original_filename
