import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import router as api_router
from app.bot import start_bot
from app.config import get_settings
from app.database import init_db
from app.logging_config import configure_logging
from app.modules.files.storage import ensure_storage_layout

configure_logging()
logger = logging.getLogger(__name__)


async def run_bot_safely() -> None:
    try:
        logger.info("Starting Telegram polling")
        await start_bot()
        logger.info("Telegram polling stopped")
    except asyncio.CancelledError:
        logger.info("Telegram polling cancelled")
        raise
    except Exception:
        logger.exception("Telegram polling crashed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("Starting FastAPI application")
    if settings.api_auth_enabled and not settings.api_token:
        logger.warning("API_AUTH_ENABLED=true but API_TOKEN is empty; /api auth will reject requests")
    ensure_storage_layout()
    await init_db()
    bot_task: asyncio.Task | None = None
    if settings.bot_token:
        bot_task = asyncio.create_task(run_bot_safely())
    else:
        logger.info("Telegram bot disabled: BOT_TOKEN is empty")
    yield
    if bot_task is not None:
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass
    logger.info("FastAPI application stopped")


app = FastAPI(title="SHARiK Consultation AI System", lifespan=lifespan)
app.include_router(api_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "consultation-ai-system"}


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "SHARiK digital Consultation AI System"}
