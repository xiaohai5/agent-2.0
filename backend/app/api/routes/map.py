from __future__ import annotations

import asyncio
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import json

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

router = APIRouter()

# Lazy-loaded MCP agent (initialized on first use)
_amap_agent = None


async def _get_amap_agent():
    global _amap_agent
    if _amap_agent is None:
        from backend.app.agent.tool_agents import build_amap_tool_agent

        _amap_agent = build_amap_tool_agent()
    return _amap_agent

AMAP_REST_URL = "https://restapi.amap.com/v3"
AMAP_KEY = "1f8c43d66527b0fdf3c98ded711f86b7"


def _fetch_json(url: str) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0", "Connection": "close"})
    with urlopen(req, timeout=8) as resp:
        return json.loads(resp.read())


@router.get("/pois")
async def map_pois(
    location: str = Query(..., min_length=3, description="lng,lat"),
    radius: int = Query(default=2000, ge=100, le=50000),
    types: Optional[str] = Query(default=None, description="POI type codes"),
    keywords: Optional[str] = Query(default=None, description="search keywords"),
    offset: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    if "," not in location:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="location must be lng,lat")
    params = {
        "key": AMAP_KEY,
        "location": location.strip(),
        "radius": radius,
        "offset": offset,
        "extensions": "all",
    }
    if types:
        params["types"] = types.strip()
    if keywords:
        params["keywords"] = keywords.strip()

    url = f"{AMAP_REST_URL}/place/around?{urlencode(params)}"
    try:
        data = await asyncio.to_thread(_fetch_json, url)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AMap API 请求失败: {exc}")
    if data.get("status") != "1":
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AMap API 返回错误: {data.get('info', '未知')}")
    return {"code": 0, "message": "ok", "data": data}


# Map item type → AMap POI type codes
ITEM_TYPE_TO_AMAP_TYPES: dict[str, str] = {
    "hotel": "100000",       # 住宿服务
    "dining": "050000",      # 餐饮服务
    "attraction": "110000",  # 风景名胜
}

@router.get("/search")
async def map_search(
    keywords: str = Query(..., min_length=1),
    city: Optional[str] = Query(default=None),
    types: Optional[str] = Query(default=None),
    offset: int = Query(default=15, ge=1, le=50),
) -> dict[str, Any]:
    params = {
        "key": AMAP_KEY,
        "keywords": keywords.strip(),
        "offset": offset,
        "extensions": "all",
    }
    if city:
        params["city"] = city.strip()
        params["citylimit"] = "true"
    if types:
        params["types"] = types.strip()

    url = f"{AMAP_REST_URL}/place/text?{urlencode(params)}"
    try:
        data = await asyncio.to_thread(_fetch_json, url)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AMap API 请求失败: {exc}")
    if data.get("status") != "1":
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AMap API 返回错误: {data.get('info', '未知')}")
    return {"code": 0, "message": "ok", "data": data}


class DrivingRouteRequest(BaseModel):
    origin: str = Field(..., description="lng,lat")
    destination: str = Field(..., description="lng,lat")
    waypoints: list[str] = Field(default_factory=list, description="list of lng,lat")


@router.post("/driving-route")
async def map_driving_route(payload: DrivingRouteRequest) -> dict[str, Any]:
    """Get a driving route path that visits all waypoints in order."""
    params: dict[str, Any] = {
        "key": AMAP_KEY,
        "origin": payload.origin.strip(),
        "destination": payload.destination.strip(),
        "extensions": "all",
        "strategy": "0",  # fastest route
    }
    if payload.waypoints:
        params["waypoints"] = ";".join(w.strip() for w in payload.waypoints)

    url = f"{AMAP_REST_URL}/direction/driving?{urlencode(params)}"
    try:
        data = await asyncio.to_thread(_fetch_json, url)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AMap API 请求失败: {exc}")
    if data.get("status") != "1":
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AMap API 返回错误: {data.get('info', '未知')}")

    # Extract path coordinates from route steps
    paths: list[list[list[float]]] = []
    try:
        route = data["route"]
        for path_item in route.get("paths", []):
            steps = path_item.get("steps", [])
            coords: list[list[float]] = []
            for step in steps:
                polyline = step.get("polyline", "")
                if polyline:
                    for pt in polyline.split(";"):
                        parts = pt.split(",")
                        if len(parts) == 2:
                            coords.append([float(parts[0]), float(parts[1])])
            if coords:
                paths.append(coords)
    except (KeyError, ValueError, TypeError):
        pass

    return {
        "code": 0,
        "message": "ok",
        "data": {"paths": paths, "raw": data},
    }


class SmartGeocodeItem(BaseModel):
    name: str = Field(..., min_length=1, description="location name/description")
    type: str = Field(default="general", description="hotel/dining/attraction/general")


class SmartGeocodeRequest(BaseModel):
    locations: list[SmartGeocodeItem] = Field(..., min_length=1, max_length=50)
    city: Optional[str] = Field(default=None, description="destination city")


@router.post("/smart-geocode")
async def map_smart_geocode(payload: SmartGeocodeRequest) -> dict[str, Any]:
    """Geocode locations using AMap MCP agent for intelligent matching."""
    if not payload.locations:
        return {"code": 0, "message": "ok", "data": {"results": []}}

    # Build a structured prompt for the MCP agent
    city_hint = f"，城市限定在{payload.city}" if payload.city else ""
    location_list = "\n".join(
        f"{i + 1}. {loc.name}（类型：{loc.type}）" for i, loc in enumerate(payload.locations)
    )
    prompt = (
        f"请逐一为以下地点进行地理编码，获取准确坐标{city_hint}：\n"
        f"{location_list}\n\n"
        "要求：\n"
        "1. 对每个地点调用 maps_text_search 搜索，必要时添加城市/区域限定\n"
        "2. 如果酒店名称不够精确，尝试用完整名称+区域搜索\n"
        "3. 确保返回的坐标与地点名称匹配\n"
        "4. 返回每个地点的：名称、经度(lng)、纬度(lat)、地址"
    )

    try:
        agent = await _get_amap_agent()
        raw_response = await agent.ask(prompt)
        response_data = json.loads(raw_response)
    except (json.JSONDecodeError, Exception) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"MCP geocode 请求失败: {exc}",
        )

    # Extract POI results from MCP tool responses
    results: list[dict[str, Any]] = []
    tool_results = response_data.get("data", [])

    for tr in tool_results:
        if not isinstance(tr, dict):
            continue
        raw = tr.get("raw") or tr.get("results") or []
        items = raw if isinstance(raw, list) else [raw]
        for item in items:
            if not isinstance(item, dict):
                continue
            for candidate in _collect_poi_candidates(item):
                name = str(candidate.get("name", "")).strip()
                location = str(candidate.get("location", ""))
                if not name or not location:
                    continue
                parts = location.split(",")
                if len(parts) != 2:
                    continue
                try:
                    lng, lat = float(parts[0]), float(parts[1])
                except (ValueError, TypeError):
                    continue
                results.append({
                    "name": name,
                    "lng": lng,
                    "lat": lat,
                    "address": candidate.get("address", ""),
                    "city": candidate.get("cityname", candidate.get("city", "")),
                })

    return {"code": 0, "message": "ok", "data": {"results": results}}


def _collect_poi_candidates(data: Any) -> list[dict[str, Any]]:
    """Recursively collect POI dicts (with 'name' field) from nested JSON."""
    candidates: list[dict[str, Any]] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("name"):
                candidates.append(item)
            else:
                candidates.extend(_collect_poi_candidates(item))
        return candidates

    if not isinstance(data, dict):
        return candidates

    if data.get("name"):
        candidates.append(data)

    for key in ("pois", "results", "data", "list", "items", "places", "hotels", "restaurants"):
        value = data.get(key)
        if isinstance(value, (list, dict)):
            candidates.extend(_collect_poi_candidates(value))

    return candidates


@router.get("/ip-locate")
async def map_ip_locate() -> dict[str, Any]:
    params = {"key": AMAP_KEY}
    url = f"{AMAP_REST_URL}/ip?{urlencode(params)}"
    try:
        data = await asyncio.to_thread(_fetch_json, url)
    except (HTTPError, URLError, OSError, TimeoutError) as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AMap API 请求失败: {exc}")
    if data.get("status") != "1":
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"AMap API 返回错误: {data.get('info', '未知')}")
    return {"code": 0, "message": "ok", "data": data}
