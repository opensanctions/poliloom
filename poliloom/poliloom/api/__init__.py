"""FastAPI application setup for PoliLoom."""

import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ..logging import setup_logging
from .politicians import router as politicians_router
from .archived_pages import router as archived_pages_router
from .entities import router as entities_router

# Configure logging
setup_logging()

app = FastAPI(
    title="PoliLoom API",
    description="API for extracting politician metadata from Wikipedia and web sources to enrich Wikidata",
    version="0.1.0",
)

# Configure CORS
cors_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in cors_origins],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(politicians_router, prefix="/politicians", tags=["politicians"])
app.include_router(
    archived_pages_router, prefix="/archived-pages", tags=["archived-pages"]
)
app.include_router(entities_router, tags=["entities"])


@app.get("/")
async def root():
    return {"message": "PoliLoom API"}
