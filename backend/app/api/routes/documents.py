from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.document import UploadDocumentResponse
from app.services.document_service import (
    FileTooLargeError,
    UnsupportedFileTypeError,
    UploadProcessingError,
    WorkflowNotFoundError,
    create_document_upload,
)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=UploadDocumentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadDocumentResponse:
    try:
        result = await create_document_upload(
            db=db,
            file=file,
            current_user=current_user,
            settings=settings,
        )
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except FileTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc))
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except UploadProcessingError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))

    return UploadDocumentResponse(run_id=result.run_id)
