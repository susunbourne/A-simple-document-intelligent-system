from fastapi import FastAPI
from contextlib import asynccontextmanager
from src.api.statement import router as statements_router
from src.db.database import Base, engine
from src.models.statement import BankStatement

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(title="Document Intelligent System", lifespan=lifespan)

app.include_router(statements_router, prefix="/statements", tags=["statements"])