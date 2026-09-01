import asyncio
import json

from fastapi.responses import StreamingResponse

subscribers: set[asyncio.Queue] = set()


async def publish(event: dict) -> None:
    for queue in list(subscribers):
        await queue.put(event)


async def telemetry_stream():
    queue = asyncio.Queue()
    subscribers.add(queue)
    try:
        while True:
            event = await queue.get()
            yield f"data: {json.dumps(event)}\n\n"
    finally:
        subscribers.discard(queue)


def stream_response():
    return StreamingResponse(telemetry_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "Connection": "keep-alive"})
