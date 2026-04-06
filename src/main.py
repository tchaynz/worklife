from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.config import settings
from src.gateway.whatsapp import router as whatsapp_router
from src.utils.logger import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    # Import agents to trigger registry.register() calls
    import src.agents.finance  # noqa: F401
    import src.agents.logistics  # noqa: F401
    yield


app = FastAPI(title="WorkLife", version="0.1.0", lifespan=lifespan)
app.include_router(whatsapp_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "service": "worklife", "env": settings.app_env}
