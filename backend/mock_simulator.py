import asyncio
import math
import random
from datetime import datetime, timezone

from .ingestion_service import ingest_reading


async def stream_field(session_factory, field_id: str, interval_seconds: int = 30):
    moisture = 62.0
    while True:
        hour = datetime.now(timezone.utc).hour
        temperature = 27 + 4 * math.sin((hour / 24) * math.tau)
        payload = {"timestamp": datetime.now(timezone.utc).isoformat(), "soil_moisture": max(20, moisture + random.gauss(0, 1)), "ph": 6.4 + random.gauss(0, 0.05), "raw_n": 148 + random.gauss(0, 4), "raw_p": 42 + random.gauss(0, 2), "raw_k": 110 + random.gauss(0, 3), "temperature": temperature, "humidity": 60 + random.gauss(0, 3)}
        with session_factory() as session:
            ingest_reading(session, field_id, payload)
            session.commit()
        moisture = max(20, moisture - 0.5)
        await asyncio.sleep(interval_seconds)
