import os
from datetime import datetime, timedelta, timezone

import httpx
from sqlalchemy import select

from .models import Field, WeatherSnapshot, now_utc


async def fetch_forecast(session, field: Field) -> list[WeatherSnapshot]:
    coordinates = field.gps_coordinates or {}
    api_key = os.getenv("OPENWEATHERMAP_API_KEY")
    rows = []
    if api_key and coordinates.get("lat") is not None and coordinates.get("lng") is not None:
        url = "https://api.openweathermap.org/data/2.5/forecast"
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, params={"lat": coordinates["lat"], "lon": coordinates["lng"], "appid": api_key, "units": "metric"})
            response.raise_for_status()
            data = response.json()
        for item in data.get("list", [])[:8]:
            forecast_time = datetime.fromtimestamp(item["dt"], tz=timezone.utc)
            rows.append(WeatherSnapshot(field_id=field.id, fetched_at=now_utc(), forecast_time=forecast_time, temperature_c=item.get("main", {}).get("temp"), humidity_pct=item.get("main", {}).get("humidity"), rainfall_mm=item.get("rain", {}).get("3h", 0), rain_probability=item.get("pop", 0), wind_speed_kmh=(item.get("wind", {}).get("speed", 0) * 3.6), description=(item.get("weather") or [{}])[0].get("description")))
    else:
        for offset in range(3):
            rows.append(WeatherSnapshot(field_id=field.id, fetched_at=now_utc(), forecast_time=now_utc() + timedelta(hours=offset), temperature_c=28, humidity_pct=60, rainfall_mm=0, rain_probability=0.1, wind_speed_kmh=8, description="demo forecast"))
    for row in rows:
        existing = session.scalar(select(WeatherSnapshot).where(WeatherSnapshot.field_id == row.field_id, WeatherSnapshot.forecast_time == row.forecast_time))
        if not existing:
            session.add(row)
    session.flush()
    return rows


def irrigation_advice(snapshots: list[WeatherSnapshot], moisture: float | None = None) -> dict:
    rain_probability = max((row.rain_probability or 0 for row in snapshots[:3]), default=0)
    if rain_probability > 0.7:
        return {"should_irrigate": False, "reason": "Rain probability exceeds 70% in the next three hours", "rain_probability": rain_probability}
    return {"should_irrigate": (moisture or 100) < 35, "reason": "Moisture is below the irrigation trigger" if (moisture or 100) < 35 else "Moisture is currently adequate", "rain_probability": rain_probability, "duration_minutes": 20}
