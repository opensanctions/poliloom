"""SSE endpoint for real-time event streaming."""

import asyncio
import json

from fastapi import APIRouter, Depends
from starlette.responses import StreamingResponse

from ..sse import subscribe, unsubscribe
from .auth import get_current_user, User

router = APIRouter()

KEEPALIVE_INTERVAL = 30  # seconds


@router.get("/events")
async def events(current_user: User = Depends(get_current_user)):
    queue = subscribe(str(current_user.user_id))

    async def generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=KEEPALIVE_INTERVAL
                    )
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                if event is None:
                    break
                yield f"data: {json.dumps(event)}\n\n"
        finally:
            unsubscribe(str(current_user.user_id), queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={"X-Accel-Buffering": "no"},
    )
