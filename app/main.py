import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.bot import start_bot
from app.database import init_db
from app.modules.files.storage import ensure_storage_layout


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_storage_layout()
    await init_db()
    bot_task = asyncio.create_task(start_bot())
    yield
    bot_task.cancel()
    try:
        await bot_task
    except asyncio.CancelledError:
        pass


app = FastAPI(title="SHARiK Consultation AI System", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "consultation-ai-system"}


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "SHARiK digital Consultation AI System"}
