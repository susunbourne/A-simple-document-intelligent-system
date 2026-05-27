from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from src.db.session import get_db
from src.workflows.statement_workflow import StatementWorkflow
from src.schemas.bank_statement import StatementResponse


router = APIRouter()

@router.post("/upload", response_model=StatementResponse, status_code=status.HTTP_201_CREATED)
async def upload_statement(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)

):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF files are supported.")
    
    try:
        file_bytes = await file.read()
        workflow = StatementWorkflow(db)
        result = await workflow.run_analysis_flow(
            file_bytes=file_bytes,
            filename=file.filename
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))