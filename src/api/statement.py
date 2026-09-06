import logging
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, Query, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import Union
from src.core.config import settings
from src.core.errors import AppError
from src.core.logging import log_event, privacy_safe_file_id
from src.db.session import get_db
from src.workflows.statement_workflow import StatementWorkflow
from src.schemas.bank_statement import StatementResponse, StatementResponseList
from src.schemas.athlete_contract import AthleteContractResponse, AthleteContractResponseList
from src.schemas.review import (
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewHistoryItem,
    ReviewHistoryResponse,
    ReviewQueueItem,
    ReviewQueueResponse,
)
from src.models.document import Document
from src.models.statement import BankStatement
from src.models.athlete_contract import AthleteContract
from src.services.auth import AuthorizedWorkspace, require_workspace_permission
from src.services.review_service import (
    ReviewConflictError,
    ReviewDocumentNotFoundError,
    ReviewService,
    ReviewValidationError,
)

router = APIRouter()
logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.pptx', '.png', '.jpg'}


@router.get("/review", response_model=ReviewQueueResponse)
def list_review_documents(
    status_filter: str = Query(default="needs_review", alias="status"),
    access: AuthorizedWorkspace = Depends(require_workspace_permission("document.read")),
    db: Session = Depends(get_db),
):
    documents = (
        db.query(Document)
        .filter(
            Document.tenant_id == access.workspace_id,
            Document.processing_status == status_filter,
        )
        .order_by(Document.created_at.desc())
        .limit(100)
        .all()
    )
    return ReviewQueueResponse(
        documents=[ReviewQueueItem.model_validate(document) for document in documents]
    )


@router.post("/review/{document_id}/decision", response_model=ReviewDecisionResponse)
def decide_review_document(
    document_id: int,
    request: ReviewDecisionRequest,
    access: AuthorizedWorkspace = Depends(require_workspace_permission("review.write")),
    db: Session = Depends(get_db),
):
    try:
        result = ReviewService(db).decide(
            workspace=access,
            document_id=document_id,
            request=request,
        )
    except ReviewDocumentNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail={"code": "review_document_not_found"}) from exc
    except ReviewConflictError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"code": "review_conflict", "message": str(exc)},
        ) from exc
    except ReviewValidationError as exc:
        db.rollback()
        raise HTTPException(
            status_code=422,
            detail={"code": "invalid_review_decision", "message": str(exc)},
        ) from exc
    decision = result.decision
    return ReviewDecisionResponse(
        decision_id=decision.decision_id,
        document_id=decision.document_id,
        action=decision.action,
        previous_status=decision.previous_status,
        new_status=decision.new_status,
        review_version=result.review_version,
        actor_subject=decision.actor_subject,
        actor_role=decision.actor_role,
        created_at=decision.created_at,
    )


@router.get("/review/{document_id}/history", response_model=ReviewHistoryResponse)
def get_review_history(
    document_id: int,
    access: AuthorizedWorkspace = Depends(require_workspace_permission("document.read")),
    db: Session = Depends(get_db),
):
    try:
        document, decisions = ReviewService(db).history(access.workspace_id, document_id)
    except ReviewDocumentNotFoundError as exc:
        db.rollback()
        raise HTTPException(status_code=404, detail={"code": "review_document_not_found"}) from exc
    return ReviewHistoryResponse(
        document_id=document.document_id,
        review_version=document.review_version,
        decisions=[ReviewHistoryItem.model_validate(item) for item in decisions],
    )

@router.post(
    "/upload",
    response_model=Union[StatementResponseList, AthleteContractResponseList],
    status_code=status.HTTP_201_CREATED,
    deprecated=True,
)
async def upload_statement(
    file: UploadFile = File(...),
    access: AuthorizedWorkspace = Depends(require_workspace_permission("document.ingest")),
    db: Session = Depends(get_db)

):
    request_id = str(uuid4())
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "missing_filename", "message": "Uploaded file must have a filename.", "request_id": request_id},
        )
    ext = os.path.splitext(file.filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "unsupported_file_type",
                "message": f"Unsupported file type: {ext}.",
                "allowed_types": sorted(ALLOWED_EXTENSIONS),
                "request_id": request_id,
            },
        )
    
    try:
        file_bytes = await file.read()
        if len(file_bytes) > settings.MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail={
                    "code": "file_too_large",
                    "message": f"Uploaded file exceeds {settings.MAX_UPLOAD_BYTES} bytes.",
                    "request_id": request_id,
                },
            )
        log_event(
            logger,
            "upload_received",
            request_id=request_id,
            file_id=privacy_safe_file_id(file.filename),
            file_size_bytes=len(file_bytes),
        )
        workflow = StatementWorkflow(db)
        result = await workflow.run_analysis_flow(
            file_bytes=file_bytes,
            filename=file.filename,
            request_id=request_id,
            tenant_id=access.workspace_id,
        )
        # normalize to list
        if not isinstance(result, list):
            result = [result]

        if len(result) == 0:
            return StatementResponseList(statements=[])

        first = result[0]
        if isinstance(first, BankStatement):
            return StatementResponseList(statements=[StatementResponse.model_validate(r) for r in result])
        elif isinstance(first, AthleteContract):
            return AthleteContractResponseList(contracts=[AthleteContractResponse.model_validate(r) for r in result])
        else:
            # fallback: try bank statement serialization
            return StatementResponseList(statements=[StatementResponse.model_validate(r) for r in result])
    except AppError as e:
        log_event(
            logger,
            "upload_failed",
            request_id=request_id,
            error_code=e.code.value,
            status_code=e.status_code,
        )
        raise HTTPException(
            status_code=e.status_code,
            detail={
                "code": e.code.value,
                "message": e.message,
                "details": e.details,
                "request_id": request_id,
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        log_event(
            logger,
            "upload_failed",
            request_id=request_id,
            error_code="internal_error",
            status_code=500,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "code": "internal_error",
                "message": "Unexpected server error while processing the document.",
                "request_id": request_id,
            },
        ) from e
