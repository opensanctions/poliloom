"""FastAPI application setup for PoliLoom."""
from fastapi import FastAPI
from .politicians import router as politicians_router

app = FastAPI(
    title="PoliLoom API",
    description="API for extracting politician metadata from Wikipedia and web sources to enrich Wikidata",
    version="0.1.0"
)

app.include_router(politicians_router, prefix="/politicians", tags=["politicians"])

@app.get("/")
async def root():
    return {"message": "PoliLoom API"}