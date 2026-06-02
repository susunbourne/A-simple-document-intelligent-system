from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import Union
from src.db.session import get_db
from src.workflows.statement_workflow import StatementWorkflow
from src.schemas.bank_statement import StatementResponse, StatementResponseList
from src.schemas.athlete_contract import AthleteContractResponse, AthleteContractResponseList
from src.models.statement import BankStatement
from src.models.athlete_contract import AthleteContract
import os

router = APIRouter()

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.pptx', '.png', '.jpg'}

@router.post("/upload", response_model=Union[StatementResponseList, AthleteContractResponseList], status_code=status.HTTP_201_CREATED)
async def upload_statement(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)

):
    ext = os.path.splitext(file.filename.lower())[1]
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {ext}. Allowed types are: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    try:
        file_bytes = await file.read()
        workflow = StatementWorkflow(db)
        result = await workflow.run_analysis_flow(
            file_bytes=file_bytes,
            filename=file.filename
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
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))