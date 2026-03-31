"""FastAPI application setup for PoliLoom."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from ..logging import setup_logging
from ..sse import event_bus
from .politicians import router as politicians_router
from .sources import router as sources_router
from .entities import router as entities_router
from .events import router as events_router
from .stats import router as stats_router

# Configure logging
setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    ready = event_bus.start()
    await ready.wait()
    yield
    await event_bus.stop()


app = FastAPI(
    title="PoliLoom API",
    description="API for extracting politician metadata from Wikipedia and web sources to enrich Wikidata",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(politicians_router, prefix="/politicians", tags=["politicians"])
app.include_router(sources_router, prefix="/sources", tags=["sources"])
app.include_router(entities_router, tags=["entities"])
app.include_router(events_router, prefix="/events", tags=["events"])
app.include_router(stats_router, prefix="/stats", tags=["stats"])


@app.get("/")
async def root():
    return {"message": "PoliLoom API"}
