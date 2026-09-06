from fastapi import FastAPI
from contextlib import asynccontextmanager
from sqlalchemy import text
from src.api.statement import router as statements_router
from src.api.ingestion import router as ingestion_router
from src.db.database import Base, engine, SessionLocal
from src.models.statement import BankStatement
from src.models.athlete_contract import AthleteContract
from src.models.document import Document, DocumentChunk, DocumentReviewDecision
from src.models.security import DataWorkspace, WorkspaceMembership
from src.models.user import User
from src.core.logging import configure_logging
from src.core.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.AUTO_CREATE_TABLES:
        Base.metadata.create_all(bind=engine)
    yield

configure_logging()
app = FastAPI(title="Forward-Deployed AI Data Harness", lifespan=lifespan)

app.include_router(statements_router, prefix="/statements", tags=["statements"])
app.include_router(ingestion_router, prefix="/ingestions", tags=["ingestions"])


@app.get("/health/live")
def liveness_check():
    return {"status": "ok"}


@app.get("/health/ready")
def readiness_check():
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ready"}
