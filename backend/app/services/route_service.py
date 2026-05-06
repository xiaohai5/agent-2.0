from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.crued import saved_plan as plan_crud

AMAP_REST_URL = "https://restapi.amap.com/v3"
AMAP_KEY = "1f8c43d66527b0fdf3c98ded711f86b7"
ROUTE_CACHE_TTL = 3600  # 1 hour

DAY_COLORS = [
    "#4A7FBF", "#FF9500", "#34C759", "#FF3B30",
    "#AF52DE", "#007AFF", "#FF2D55", "#5AC8FA",
]


def _fetch_json(url: str) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0", "Connection": "close"})
    with urlopen(req, timeout=8) as resp:
        return json.loads(resp.read())


async def _fetch_json_async(url: str) -> dict[str, Any]:
    return await asyncio.to_thread(_fetch_json, url)


class RouteService:
    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url
        self._redis: Redis | None = None

    async def _get_redis(self) -> Redis | None:
        if self._redis is not None:
            return self._redis
        if not self.redis_url:
            return None
        try:
            client = Redis.from_url(self.redis_url, decode_responses=True)
            await client.ping()
            self._redis = client
            return client
        except Exception:
            self._redis = None
            return None

    @staticmethod
    def _cache_key(plan_id: int, days: tuple[int, ...] | None) -> str:
        days_str = "_".join(str(d) for d in days) if days else "all"
        return f"route:plan:{plan_id}:{days_str}"

    async def _invalidate_cache(self, plan_id: int) -> None:
        r = await self._get_redis()
        if not r:
            return
        # Scan and delete all route cache keys for this plan
        cursor = 0
        pattern = f"route:plan:{plan_id}:*"
        while True:
            cursor, keys = await r.scan(cursor, match=pattern, count=100)
            if keys:
                await r.delete(*keys)
            if cursor == 0:
                break

    async def get_plan_routes(
        self,
        db: AsyncSession,
        plan_id: int,
        user_id: int,
        days: list[int] | None = None,
    ) -> dict[str, Any] | None:
        plan = await plan_crud.get_plan_by_id(db, plan_id, user_id)
        if not plan:
            return None

        plan_data = plan.plan_data or {}
        all_days: list[dict[str, Any]] = plan_data.get("days", [])

        # Filter days if requested
        if days:
            day_set = set(days)
            target_days = [d for d in all_days if d.get("day") in day_set]
        else:
            target_days = all_days

        days_key = tuple(sorted(days)) if days else None
        cache_key = self._cache_key(plan_id, days_key)

        # Try cache
        r = await self._get_redis()
        if r:
            cached = await r.get(cache_key)
            if cached:
                return json.loads(cached)

        # Calculate routes
        result_days = []
        for i, day in enumerate(target_days):
            items = day.get("items", [])
            coords = _collect_coordinates(items)
            color = DAY_COLORS[i % len(DAY_COLORS)]

            markers = _build_markers(coords)
            if len(coords) < 2:
                # Single location: markers only, no polyline
                polyline = []
                chunked = False
            else:
                polyline = await _calculate_day_polyline(coords)
                chunked = len(coords) > 18

            result_days.append({
                "day": day.get("day", i + 1),
                "title": day.get("title", f"第{i + 1}天"),
                "color": color,
                "polyline": polyline,
                "markers": markers,
                "chunked": chunked,
            })

        result = {
            "plan_id": plan_id,
            "title": plan.title,
            "days": result_days,
        }

        # Cache
        if r:
            await r.set(cache_key, json.dumps(result, ensure_ascii=False), ex=ROUTE_CACHE_TTL)

        return result


def _collect_coordinates(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collect items that have valid lng/lat, preserving order."""
    coords = []
    for item in items:
        lng = item.get("lng")
        lat = item.get("lat")
        if lng is not None and lat is not None:
            coords.append({
                "lng": float(lng),
                "lat": float(lat),
                "name": item.get("description", ""),
                "type": item.get("type", "general"),
            })
    return coords


def _build_markers(
    coords: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build marker list with start/end/waypoint/start_end types."""
    if not coords:
        return []

    markers = []
    same_start_end = (
        len(coords) >= 2
        and coords[0]["name"] == coords[-1]["name"]
    )

    for i, c in enumerate(coords):
        if i == 0 and i == len(coords) - 1:
            # Single location
            marker_type = "start_end"
        elif i == 0:
            marker_type = "start_end" if same_start_end else "start"
        elif i == len(coords) - 1:
            if same_start_end:
                continue  # skip duplicate marker at end of loop trip
            marker_type = "end"
        else:
            marker_type = "waypoint"

        markers.append({
            "lng": c["lng"],
            "lat": c["lat"],
            "name": c["name"],
            "type": marker_type,
        })

    return markers


async def _calculate_day_polyline(
    coords: list[dict[str, Any]],
) -> list[list[float]]:
    """Calculate driving route for a day using waypoints.

    First coord = origin, last = destination, middle = waypoints.
    If more than 18 total coordinates, the waypoint list is split into
    overlapping chunks (each chunk < 18 total points, overlapping by 1
    coordinate) and multiple AMap API calls are made.
    """
    if len(coords) < 2:
        return []

    # The AMap API supports at most 16 waypoints (18 total points:
    # origin + 16 waypoints + destination).  If our list fits in one
    # call, take the fast path.
    if len(coords) <= 18:
        return await _call_amap_driving(coords)

    # ---- Chunked request path -------------------------------------------
    # Each chunk is up to 18 points, overlapping by 1 with the next chunk
    # to maintain path continuity.
    chunk_size = 18
    overlap = 1
    chunks: list[list[dict[str, Any]]] = []
    start = 0
    while start < len(coords):
        end = min(start + chunk_size, len(coords))
        chunks.append(coords[start:end])
        start += chunk_size - overlap

    # Fetch all chunks concurrently
    chunk_polylines = await asyncio.gather(
        *[_call_amap_driving(chunk) for chunk in chunks],
    )

    # Stitch polylines together, discarding the overlapping tail of each
    # chunk (except the last chunk) to avoid duplicating points.
    full_polyline: list[list[float]] = []
    for idx, pl in enumerate(chunk_polylines):
        if pl:
            if idx > 0:
                # The previous chunk's final point is the same as this
                # chunk's first point -- skip the first point of this chunk
                # to avoid duplication.
                full_polyline.extend(pl[1:])
            else:
                full_polyline.extend(pl)

    return full_polyline


async def _call_amap_driving(
    coords: list[dict[str, Any]],
) -> list[list[float]]:
    """Make a single AMap driving API call for *coords* (max 18 points)."""
    origin = f"{coords[0]['lng']},{coords[0]['lat']}"
    destination = f"{coords[-1]['lng']},{coords[-1]['lat']}"

    params: dict[str, str | int] = {
        "key": AMAP_KEY,
        "origin": origin,
        "destination": destination,
        "extensions": "all",
        "strategy": "0",
    }

    if len(coords) > 2:
        waypoints = ";".join(
            f"{c['lng']},{c['lat']}" for c in coords[1:-1]
        )
        params["waypoints"] = waypoints

    url = f"{AMAP_REST_URL}/direction/driving?{urlencode(params)}"
    try:
        data = await _fetch_json_async(url)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        logger.warning(
            "AMap driving API HTTP error (total points %d): %s",
            len(coords),
            exc,
        )
        return []

    if data.get("status") != "1":
        logger.warning(
            "AMap driving API returned non-OK status (total points %d): "
            "status=%s info=%s",
            len(coords),
            data.get("status"),
            data.get("info", "N/A"),
        )
        return []

    polyline: list[list[float]] = []
    try:
        route = data["route"]
        for path_item in route.get("paths", []):
            for step in path_item.get("steps", []):
                poly_str = step.get("polyline", "")
                if poly_str:
                    for pt in poly_str.split(";"):
                        parts = pt.split(",")
                        if len(parts) == 2:
                            polyline.append([float(parts[0]), float(parts[1])])
            break  # Only use first path
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning(
            "Failed to parse AMap driving response (total points %d): %s",
            len(coords),
            exc,
        )
        return []

    return polyline
