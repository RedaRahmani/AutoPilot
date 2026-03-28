"""
Unit tests for document_service magic-byte detection and file streaming.

All tests are isolated from the database — they work entirely in memory or
against temporary files provided by pytest's tmp_path fixture.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pytest
from fastapi import UploadFile

from app.services.document_service import (
    FileTooLargeError,
    UnsupportedFileTypeError,
    _MIME_TO_EXT,
    _detect_mime,
    _stream_to_temp,
)

# ── Minimal byte samples with real magic signatures ───────────────────────────

# Each sample is long enough to exceed a single read call so the streaming
# path is exercised, but short enough to keep tests fast.
_PDF = b"%PDF-1.4 \n" + b"\x00" * 512          # PDF magic: %PDF
_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 512   # PNG magic: 8-byte signature
_JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 512     # JPEG magic: SOI + APP0 marker
_TXT = b"Hello, this is plain text and not a supported type."
_EMPTY = b""

_MAX = 10 * 1024 * 1024  # 10 MiB — the default limit


def _upload(content: bytes, filename: str = "upload") -> UploadFile:
    """Build an UploadFile backed by an in-memory BytesIO."""
    return UploadFile(filename=filename, file=io.BytesIO(content))


# ── _detect_mime ──────────────────────────────────────────────────────────────


def test_detect_mime_pdf() -> None:
    assert _detect_mime(_PDF[:16]) == "application/pdf"


def test_detect_mime_png() -> None:
    assert _detect_mime(_PNG[:16]) == "image/png"


def test_detect_mime_jpeg() -> None:
    assert _detect_mime(_JPG[:16]) == "image/jpeg"


def test_detect_mime_unknown_returns_none() -> None:
    assert _detect_mime(_TXT[:16]) is None


def test_detect_mime_empty_returns_none() -> None:
    assert _detect_mime(b"") is None


def test_detect_mime_partial_png_magic_not_matched() -> None:
    """Only the first byte of the PNG signature must not trigger a match."""
    # PNG needs all 8 signature bytes; one byte is not enough.
    assert _detect_mime(b"\x89" + b"\x00" * 15) is None


def test_detect_mime_partial_pdf_magic_not_matched() -> None:
    """Incomplete %PDF prefix must not match."""
    assert _detect_mime(b"%PD" + b"\x00" * 13) is None


# ── _stream_to_temp ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stream_pdf_accepted(tmp_path: Path) -> None:
    dest = tmp_path / "out.tmp"
    mime, size, digest = await _stream_to_temp(_upload(_PDF), dest, _MAX)

    assert mime == "application/pdf"
    assert size == len(_PDF)
    assert len(digest) == 64  # SHA-256 produces a 64-character hex string


@pytest.mark.asyncio
async def test_stream_png_accepted(tmp_path: Path) -> None:
    dest = tmp_path / "out.tmp"
    mime, size, _ = await _stream_to_temp(_upload(_PNG), dest, _MAX)

    assert mime == "image/png"
    assert size == len(_PNG)


@pytest.mark.asyncio
async def test_stream_jpeg_accepted(tmp_path: Path) -> None:
    dest = tmp_path / "out.tmp"
    mime, size, _ = await _stream_to_temp(_upload(_JPG), dest, _MAX)

    assert mime == "image/jpeg"
    assert size == len(_JPG)


@pytest.mark.asyncio
async def test_stream_unknown_bytes_rejected(tmp_path: Path) -> None:
    dest = tmp_path / "out.tmp"
    with pytest.raises(UnsupportedFileTypeError):
        await _stream_to_temp(_upload(_TXT), dest, _MAX)


@pytest.mark.asyncio
async def test_stream_empty_file_rejected(tmp_path: Path) -> None:
    dest = tmp_path / "out.tmp"
    with pytest.raises(UnsupportedFileTypeError):
        await _stream_to_temp(_upload(_EMPTY), dest, _MAX)


@pytest.mark.asyncio
async def test_stream_enforces_size_limit(tmp_path: Path) -> None:
    """A file whose content exceeds max_bytes must raise FileTooLargeError."""
    dest = tmp_path / "out.tmp"
    # _PDF is ~522 bytes; a 10-byte limit guarantees rejection.
    with pytest.raises(FileTooLargeError):
        await _stream_to_temp(_upload(_PDF), dest, max_bytes=10)


@pytest.mark.asyncio
async def test_stream_checksum_matches_content(tmp_path: Path) -> None:
    """SHA-256 digest returned by _stream_to_temp must match the full content."""
    dest = tmp_path / "out.tmp"
    _, _, digest = await _stream_to_temp(_upload(_PDF), dest, _MAX)

    assert digest == hashlib.sha256(_PDF).hexdigest()


@pytest.mark.asyncio
async def test_stream_writes_content_to_disk(tmp_path: Path) -> None:
    """The streamed bytes must be written verbatim to the destination path."""
    dest = tmp_path / "out.tmp"
    await _stream_to_temp(_upload(_PDF), dest, _MAX)

    assert dest.read_bytes() == _PDF


# ── _MIME_TO_EXT invariants ───────────────────────────────────────────────────


def test_mime_to_ext_covers_all_supported_types() -> None:
    assert "application/pdf" in _MIME_TO_EXT
    assert "image/png" in _MIME_TO_EXT
    assert "image/jpeg" in _MIME_TO_EXT


def test_mime_to_ext_only_maps_safe_extensions() -> None:
    """Extension map must contain exactly the expected safe set."""
    assert set(_MIME_TO_EXT.values()) == {".pdf", ".png", ".jpg"}
