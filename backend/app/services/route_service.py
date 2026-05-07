from __future__ import annotations

import asyncio
import copy
import json
import logging
import math
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.crued import saved_plan as plan_crud

try:
    from redis.asyncio import Redis
except ModuleNotFoundError:  # pragma: no cover - optional cache dependency
    Redis = None

AMAP_REST_URL = "https://restapi.amap.com/v3"
AMAP_KEY = "1f8c43d66527b0fdf3c98ded711f86b7"
ROUTE_CACHE_TTL = 3600  # 1 hour
CACHE_VERSION = "v8"  # bump when route result structure changes

DAY_COLORS = [
    "#4A7FBF", "#FF9500", "#34C759", "#FF3B30",
    "#AF52DE", "#007AFF", "#FF2D55", "#5AC8FA",
]

SEGMENT_COLORS = [
    "#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#DDA0DD",
    "#F4D03F", "#BB8FCE", "#5DADE2", "#F8C471", "#82E0AA",
    "#F1948A", "#AED6F1", "#E8A87C", "#58D68D", "#F5B041",
    "#A569BD", "#48C9B0", "#DC7633", "#7FB3D8", "#B7950B",
]


CITY_PATTERNS = [
    "目的地", "城市", "出发城市", "到达城市",
]
ACTION_PREFIXES = [
    "游览", "参观", "前往", "到达", "入住", "从", "出发",
    "步行至", "乘车至", "骑车至", "打车至", "地铁至",
    "逛", "看", "去", "到", "逛一逛",
]


def _extract_city(plan_data: dict[str, Any]) -> str:
    """Extract city context from plan overview / title."""
    overview = str(plan_data.get("overview", "") or "")
    title = str(plan_data.get("title", "") or "")
    text = f"{title}\n{overview}"

    for line in text.split("\n"):
        line = line.strip()
        for key in CITY_PATTERNS:
            if key in line:
                parts = line.split(key, 1)
                if len(parts) == 2:
                    city = parts[1].replace("：", "").replace(":", "").strip("。，, \t")
                    if city and len(city) <= 10:
                        return city

    # Try to find city names in first 200 chars (common cities)
    common_cities = [
        "北京", "上海", "广州", "深圳", "杭州", "南京", "成都", "重庆",
        "武汉", "西安", "苏州", "天津", "长沙", "郑州", "东莞", "青岛",
        "沈阳", "宁波", "昆明", "大连", "厦门", "合肥", "佛山", "无锡",
        "福州", "济南", "哈尔滨", "长春", "温州", "石家庄", "泉州", "南宁",
        "贵阳", "南昌", "太原", "金华", "常州", "惠州", "徐州", "嘉兴",
        "南通", "洛阳", "三亚", "海口", "桂林", "大理", "丽江", "拉萨",
        "乌鲁木齐", "呼和浩特", "银川", "兰州", "西宁", "珠海", "中山",
    ]
    head = text[:200]
    for city in common_cities:
        if city in head:
            return city
    return ""


def _clean_place_name(description: str) -> str:
    """Strip common travel action prefixes from a description."""
    text = description.strip()
    if not text:
        return text

    # Remove leading emoji (U+1F300–U+1FAFF, U+2600–U+27BF)
    while text and (
        0x1F300 <= ord(text[0]) <= 0x1FAFF
        or 0x2600 <= ord(text[0]) <= 0x27BF
    ):
        text = text[1:]

    # Drop markdown remnants and parenthetical tips before geocoding.
    text = re.sub(r"\*\*|`|#+", "", text)

    label_match = re.search(r"(?:入住酒店|住宿建议|住宿|酒店|餐厅|午餐|晚餐|早餐)\s*[：:\s]+(.+)$", text)
    if label_match:
        return _clean_place_name(label_match.group(1))

    text = re.sub(r"[（(].*?[）)]", "", text).strip()

    # Extract destination from "从...前往..." / "从...到..." / "步行至..." patterns.
    dest_match = re.search(r"(?:前往|到达|游览|参观|打卡|入住)(.+?)(?:[，。；;、,\.\s]|$)", text)
    if dest_match:
        return dest_match.group(1).strip()

    dest_match = re.search(
        r"(?:步行至|乘车至|骑车至|打车至|地铁至|换乘至|坐车到|去往|抵达)(.+?)(?:[，。；;、,\.\s]|$)",
        text,
    )
    if dest_match:
        return dest_match.group(1).strip()

    # Remove action prefix (shortest match first to leave the place name intact)
    for prefix in ACTION_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix):]
            break

    # Split label:value patterns (e.g. "午餐建议：全聚德")
    for sep in ("：", ":"):
        if sep in text:
            value = text.split(sep, 1)[1].strip()
            if len(value) >= 2:
                return _clean_place_name(value)

    # Keep the first concrete phrase and remove common duration/cost details.
    text = re.split(r"[，。；;、,]\s*", text, maxsplit=1)[0].strip()
    text = re.sub(r"^(?:在)?附近的?", "", text).strip()
    text = re.sub(r"(?:享用|品尝|用餐|吃|游览|参观|打卡|拍照).*", "", text).strip()
    text = re.sub(r"(?:约|大约)?\d+(?:\.\d+)?\s*(?:小时|分钟|h|min|公里|km).*", "", text, flags=re.I).strip()
    text = re.sub(r"(?:门票|预算|费用|人均|价格).*", "", text).strip()

    return text.strip()


def _hotel_name_variants(value: str) -> list[str]:
    text = value.strip()
    if not text:
        return []
    match = re.search(r"(.+?)[（(]([^）)]+)[）)]", text)
    if not match:
        return []
    brand = match.group(1).strip()
    qualifier = match.group(2).strip()
    variants = [text, f"{brand}{qualifier}", f"{qualifier}{brand}"]
    if qualifier.endswith("店"):
        variants.append(f"{brand}{qualifier[:-1]}")
    return variants


def _candidate_place_names(item: dict[str, Any] | str) -> list[str]:
    """Return ordered place-name candidates for POI search and marker display."""
    if isinstance(item, str):
        raw_groups = [[_clean_place_name(item), item]]
    else:
        explicit_values = [
            item.get("placeName") or item.get("place_name"),
            item.get("name"),
            item.get("title"),
        ]
        raw_groups = []
        for value in explicit_values:
            text = str(value or "").strip()
            if text:
                raw_groups.append([text, *_hotel_name_variants(text), _clean_place_name(text)])
        description = str(item.get("description") or "").strip()
        if description:
            labeled = re.search(r"(?:入住酒店|住宿建议|住宿|酒店|餐厅|午餐|晚餐|早餐)\s*[：:\s]+(.+)$", description)
            description_place = labeled.group(1).strip() if labeled else description
            raw_groups.append([*_hotel_name_variants(description_place), _clean_place_name(description), description])

    candidates: list[str] = []
    seen: set[str] = set()
    for group in raw_groups:
        for raw in group:
            candidate = str(raw or "").strip()
            candidate = candidate.strip(" \t\r\n-—:：，。；;、")
            if len(candidate) < 2 or candidate in seen:
                continue
            seen.add(candidate)
            candidates.append(candidate)
    return candidates


def _display_place_name(item: dict[str, Any]) -> str:
    candidates = _candidate_place_names(item)
    if candidates:
        return candidates[0]
    return str(item.get("description") or "").strip()


def _score_poi(poi: dict[str, Any], keyword: str) -> int:
    name = str(poi.get("name") or "")
    address = str(poi.get("address") or "")
    adname = str(poi.get("adname") or "")
    haystack = f"{name} {address} {adname}"
    tokens = [t for t in re.split(r"[（）()·\s-]+", keyword) if len(t) >= 2]

    score = 0
    if keyword and keyword in name:
        score += 40
    for token in tokens:
        if token in name:
            score += 18
        elif token in haystack:
            score += 10
    if "王府井" in keyword and "王府井" in haystack:
        score += 25
    if any(word in keyword for word in ("酒店", "宾馆", "旅馆")) and any(word in name for word in ("酒店", "宾馆", "旅馆", "如家")):
        score += 12
    return score


def _pick_best_poi(pois: list[dict[str, Any]], keyword: str) -> dict[str, Any] | None:
    if not pois:
        return None
    return max(pois, key=lambda poi: _score_poi(poi, keyword))


async def _geocode_place(description: str | dict[str, Any], city: str) -> tuple[float, float] | None:
    """Use AMap POI text search to find coordinates for a place name."""
    candidates = _candidate_place_names(description)
    if not candidates:
        return None

    for cleaned in candidates[:4]:
        params: dict[str, str | int] = {
            "key": AMAP_KEY,
            "keywords": cleaned,
            "offset": 5,
        }
        if city:
            params["city"] = city

        url = f"{AMAP_REST_URL}/place/text?{urlencode(params)}"
        data = await _fetch_amap_json_with_retry(url, f"POI search geocoding for '{cleaned}'")
        if not data:
            continue

        pois = data.get("pois", [])
        poi = _pick_best_poi(pois, cleaned)
        if not poi:
            continue

        location = str(poi.get("location", "")).strip()
        parts = location.split(",")
        if len(parts) == 2:
            try:
                return float(parts[0]), float(parts[1])
            except ValueError:
                continue
    return None


async def _fetch_amap_json_with_retry(
    url: str,
    context: str,
    attempts: int = 3,
) -> dict[str, Any] | None:
    """Fetch AMap JSON and briefly back off when the API rate-limits us."""
    last_info = ""
    for attempt in range(attempts):
        try:
            data = await _fetch_json_async(url)
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            logger.warning("AMap %s failed: %s", context, exc)
            return None

        if data.get("status") == "1":
            return data

        last_info = str(data.get("info") or data.get("infocode") or "N/A")
        logger.warning(
            "AMap %s returned non-OK: status=%s info=%s",
            context,
            data.get("status"),
            last_info,
        )
        if not _is_amap_rate_limit(last_info) or attempt == attempts - 1:
            return None
        await asyncio.sleep(0.35 * (attempt + 1))
    return None


def _is_amap_rate_limit(info: str) -> bool:
    return any(token in info.upper() for token in ("QPS", "LIMIT", "EXCEEDED", "TOO_FAST"))


ROUTE_NOTE_RE = re.compile(r"(景点间交通|返回交通|交通方式|小贴士|提醒|注意事项|提前|避免排队)")
ROUTE_ACTION_RE = re.compile(
    r"(?:前往|到达|抵达|游览|参观|打卡|入住|去往|步行至|乘车至|打车至|地铁至|换乘至|坐车到)([^，。；;、,.]{2,40})"
)
ROUTE_LABEL_RE = re.compile(
    r"(?:入住酒店|住宿建议|住宿|酒店|景点|地点|餐厅|午餐|晚餐|早餐|目的地|终点)\s*[：:\s]+([^，。；;、,.]{2,40})"
)


def _build_route_waypoints(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize timeline items into map waypoints before geocoding/routing."""
    waypoints: list[dict[str, Any]] = []
    for item in items:
        waypoint = _route_waypoint_from_item(item)
        if not waypoint:
            continue
        if _is_duplicate_waypoint(waypoints, waypoint):
            continue
        waypoints.append(waypoint)
    return waypoints


def _route_waypoint_from_item(item: dict[str, Any]) -> dict[str, Any] | None:
    place_name = _extract_route_place_name(item)
    if not place_name:
        return None

    waypoint = copy.deepcopy(item)
    waypoint["_route_waypoint"] = True
    waypoint["placeName"] = place_name
    waypoint["name"] = place_name
    waypoint["type"] = _infer_waypoint_type(item, place_name)

    # Coordinates attached to old timeline items may belong to the uncleaned
    # sentence. Re-geocode normalized route waypoints instead.
    waypoint.pop("lng", None)
    waypoint.pop("lat", None)
    return waypoint


def _extract_route_place_name(item: dict[str, Any]) -> str:
    time = str(item.get("time") or "")
    item_type = str(item.get("type") or "")
    description = str(item.get("description") or "").strip()
    explicit = str(item.get("placeName") or item.get("name") or "").strip()
    text = " ".join(part for part in (time, item_type, explicit, description) if part)

    if ROUTE_NOTE_RE.search(text):
        return ""
    if explicit and not _looks_like_transport_only(explicit):
        return _normalize_route_place_name(explicit)

    label_match = ROUTE_LABEL_RE.search(description)
    if label_match:
        return _normalize_route_place_name(label_match.group(1))

    action_matches = ROUTE_ACTION_RE.findall(description)
    if action_matches:
        return _normalize_route_place_name(action_matches[0])

    if re.match(r"^(建议|推荐)[:：]?", description):
        suggestion = re.sub(r"^(建议|推荐)[:：]?", "", description).strip()
        suggestion = re.sub(r"^(?:在)?附近的?", "", suggestion)
        suggestion = re.split(r"(?:享用|品尝|用餐|吃|游览|参观|打卡|拍照)", suggestion, maxsplit=1)[0]
        return _normalize_route_place_name(suggestion)

    if item_type in {"hotel", "dining", "attraction", "general"}:
        return _normalize_route_place_name(description)
    return ""


def _normalize_route_place_name(value: str) -> str:
    raw = str(value or "").strip()
    if re.search(r"(酒店|宾馆|旅馆|民宿|客栈|如家)", raw) and re.search(r"[（(].+?[）)]", raw):
        text = raw
    else:
        text = _clean_place_name(raw)
    text = re.sub(r"^(?:在)?附近的?", "", text).strip()
    text = re.sub(r"(?:享用|品尝|用餐|吃|游览|参观|打卡|拍照|了解|体验).*", "", text).strip()
    text = text.strip(" \t\r\n-—:：，。；;、")
    if _looks_like_transport_only(text):
        return ""
    return text if 2 <= len(text) <= 40 else ""


def _looks_like_transport_only(value: str) -> bool:
    text = str(value or "")
    if "步行街" in text:
        return False
    return bool(re.search(r"(约?\d+\s*(分钟|小时|公里|km)|地铁|公交|打车|步行|骑行|自驾|换乘)", text))


def _infer_waypoint_type(item: dict[str, Any], place_name: str) -> str:
    item_type = str(item.get("type") or "general").lower()
    if item_type == "transport":
        item_type = "general"
    if any(word in place_name for word in ("餐厅", "饭店", "全聚德", "烤鸭")):
        return "dining"
    if any(word in place_name for word in ("景点", "广场", "故宫", "博物馆", "天安门", "步行街", "公园")):
        return "attraction"
    if any(word in place_name for word in ("酒店", "宾馆", "旅馆", "民宿", "如家")):
        return "hotel"
    text = f"{item.get('time') or ''} {item.get('description') or ''}"
    if item_type == "general" and any(word in text for word in ("午餐", "晚餐", "早餐")):
        return "dining"
    return item_type if item_type in {"hotel", "dining", "attraction"} else "general"


def _is_duplicate_waypoint(waypoints: list[dict[str, Any]], waypoint: dict[str, Any]) -> bool:
    name = str(waypoint.get("name") or "")
    for existing in waypoints:
        if str(existing.get("name") or "") == name:
            return True
    return False


def _fetch_json(url: str) -> dict[str, Any]:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0", "Connection": "close"})
    with urlopen(req, timeout=8) as resp:
        return json.loads(resp.read())


async def _fetch_json_async(url: str) -> dict[str, Any]:
    return await asyncio.to_thread(_fetch_json, url)


class RouteService:
    def __init__(self, redis_url: str | None = None) -> None:
        self.redis_url = redis_url
        self._redis: Any | None = None

    async def _get_redis(self) -> Any | None:
        if self._redis is not None:
            return self._redis
        if not self.redis_url or Redis is None:
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
        return f"route:{CACHE_VERSION}:plan:{plan_id}:{days_str}"

    async def _invalidate_cache(self, plan_id: int) -> None:
        r = await self._get_redis()
        if not r:
            return
        # Scan and delete all route cache keys for this plan (across all versions)
        cursor = 0
        pattern = f"route:*:plan:{plan_id}:*"
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

        plan_data = copy.deepcopy(plan.plan_data or {})
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

        # Extract city context for geocoding fallback
        city = _extract_city(plan_data)

        # Calculate routes
        result_days = []
        for i, day in enumerate(target_days):
            items = day.get("items", [])
            route_items = _build_route_waypoints(items)
            await _enrich_route_waypoints(route_items, city)
            coords = _collect_coordinates(route_items)
            coords = _optimize_route_coordinates(coords)
            color = DAY_COLORS[i % len(DAY_COLORS)]

            markers = _build_markers(coords)
            if len(coords) < 2:
                polyline = []
                chunked = False
                segments = []
            else:
                polyline = await _calculate_day_polyline(coords)
                chunked = len(coords) > 18
                segments = await _calculate_segment_polylines(coords)

            result_days.append({
                "day": day.get("day", i + 1),
                "title": day.get("title", f"第{i + 1}天"),
                "color": color,
                "polyline": polyline,
                "markers": markers,
                "chunked": chunked,
                "segments": segments,
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
        if not _is_route_waypoint(item):
            continue
        lng = item.get("lng")
        lat = item.get("lat")
        if lng is not None and lat is not None:
            coord = {
                "lng": float(lng),
                "lat": float(lat),
                "name": _display_place_name(item),
                "type": item.get("type", "general"),
            }
            if _is_duplicate_coord(coords, coord):
                continue
            coords.append(coord)
    return coords


def _optimize_route_coordinates(coords: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Use the hotel as route anchor and order stops by nearest-neighbor distance."""
    if len(coords) <= 2:
        return coords

    start_idx = _find_route_hotel_index(coords)
    if start_idx is None:
        return _nearest_neighbor_route(coords[0], coords[1:], close_loop=False)

    hotel = coords[start_idx]
    stops = [
        coord for idx, coord in enumerate(coords)
        if idx != start_idx and not _same_route_coord(coord, hotel)
    ]
    if not stops:
        return [hotel]

    optimized = _nearest_neighbor_route(hotel, stops, close_loop=True)
    return optimized


def _find_route_hotel_index(coords: list[dict[str, Any]]) -> int | None:
    for idx, coord in enumerate(coords):
        if _is_hotel_coord(coord):
            return idx
    return None


def _is_hotel_coord(coord: dict[str, Any]) -> bool:
    name = str(coord.get("name") or "")
    coord_type = str(coord.get("type") or "").lower()
    return coord_type == "hotel" or any(word in name for word in ("酒店", "宾馆", "旅馆", "民宿", "客栈", "如家"))


def _nearest_neighbor_route(
    start: dict[str, Any],
    stops: list[dict[str, Any]],
    close_loop: bool,
) -> list[dict[str, Any]]:
    route = [copy.deepcopy(start)]
    remaining = [copy.deepcopy(stop) for stop in stops]
    current = route[0]

    while remaining:
        next_idx = min(
            range(len(remaining)),
            key=lambda idx: _route_distance(current, remaining[idx]),
        )
        current = remaining.pop(next_idx)
        route.append(current)

    if close_loop:
        route.append(copy.deepcopy(start))
    return route


def _route_distance(a: dict[str, Any], b: dict[str, Any]) -> float:
    """Approximate distance in meters between two lng/lat coordinates."""
    lng1 = math.radians(float(a["lng"]))
    lat1 = math.radians(float(a["lat"]))
    lng2 = math.radians(float(b["lng"]))
    lat2 = math.radians(float(b["lat"]))
    d_lng = lng2 - lng1
    d_lat = lat2 - lat1
    hav = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lng / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(hav))


def _same_route_coord(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if str(a.get("name") or "") and str(a.get("name") or "") == str(b.get("name") or ""):
        return True
    return (
        abs(float(a["lng"]) - float(b["lng"])) < 0.00008
        and abs(float(a["lat"]) - float(b["lat"])) < 0.00008
    )


async def _enrich_route_waypoints(items: list[dict[str, Any]], city: str) -> None:
    for item in items:
        if item.get("lng") is not None and item.get("lat") is not None:
            continue
        coords = await _geocode_place(item, city)
        if coords:
            item["lng"], item["lat"] = coords
        await asyncio.sleep(0.12)


def _is_route_waypoint(item: dict[str, Any]) -> bool:
    if item.get("_route_waypoint"):
        return True

    text = " ".join(
        str(item.get(key) or "")
        for key in ("time", "type", "placeName", "name", "description")
    )
    item_type = str(item.get("type") or "general").lower()
    place_name = _display_place_name(item)

    if not place_name:
        return False
    if re.search(r"(景点间交通|返回交通|交通方式|小贴士|提醒|注意事项|提前|避免排队)", text):
        return False
    if item_type == "transport" and "步行街" not in text:
        return False
    if re.match(r"^(建议|备注|说明)[:：]?", str(item.get("description") or "").strip()) and item_type not in {"dining", "hotel"}:
        return False
    return True


def _is_duplicate_coord(coords: list[dict[str, Any]], coord: dict[str, Any]) -> bool:
    for existing in coords:
        if existing.get("name") == coord.get("name"):
            return True
        if (
            abs(float(existing["lng"]) - float(coord["lng"])) < 0.00008
            and abs(float(existing["lat"]) - float(coord["lat"])) < 0.00008
        ):
            return True
    return False


def _build_markers(
    coords: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build marker list with start/end/waypoint types, numbered and colored.

    Each waypoint gets a sequential number (1-based) and a color that
    matches the route segment arriving at or departing from it:
      - waypoint 0 (start):   color = SEGMENT_COLORS[0]  (first departing segment)
      - waypoint i (1..n-2):  color = SEGMENT_COLORS[i]  (the segment departing from it)
      - waypoint n-1 (end):   color = SEGMENT_COLORS[n-2] (last arriving segment)
    """
    if not coords:
        return []

    n = len(coords)
    seg_count = n - 1  # number of segments between consecutive waypoints
    markers = []
    same_start_end = (
        n >= 2
        and coords[0]["name"] == coords[-1]["name"]
    )

    for i, c in enumerate(coords):
        # Determine marker type
        if i == 0 and i == n - 1:
            marker_type = "start_end"
        elif i == 0:
            marker_type = "start_end" if same_start_end else "start"
        elif i == n - 1:
            if same_start_end:
                continue  # skip duplicate marker at end of loop trip
            marker_type = "end"
        else:
            marker_type = "waypoint"

        # Color: use the segment departing from this waypoint, or
        # the last arriving segment for the final waypoint.
        seg_idx = i if i < seg_count else seg_count - 1
        color = SEGMENT_COLORS[seg_idx % len(SEGMENT_COLORS)] if seg_count > 0 else DAY_COLORS[0]

        markers.append({
            "lng": c["lng"],
            "lat": c["lat"],
            "name": c["name"],
            "type": marker_type,
            "num": i + 1,          # 1-based display number
            "color": color,
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
        polyline = await _call_amap_driving(coords)
        return polyline or _straight_polyline(coords)

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
        if not pl and idx < len(chunks):
            pl = _straight_polyline(chunks[idx])
        if pl:
            if idx > 0:
                # The previous chunk's final point is the same as this
                # chunk's first point -- skip the first point of this chunk
                # to avoid duplication.
                full_polyline.extend(pl[1:])
            else:
                full_polyline.extend(pl)

    return full_polyline


def _straight_polyline(coords: list[dict[str, Any]]) -> list[list[float]]:
    """Fallback polyline that keeps every waypoint visible when routing fails."""
    return [[float(c["lng"]), float(c["lat"])] for c in coords if c.get("lng") is not None and c.get("lat") is not None]


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
    data = await _fetch_amap_json_with_retry(
        url,
        f"driving route for {len(coords)} point(s)",
    )
    if not data:
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


async def _calculate_segment_polylines(
    coords: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Calculate individual driving polylines for each consecutive pair.

    All segment API calls are issued concurrently.  Each segment carries its
    own polyline, color, numeric label, and label position (midpoint of the
    two waypoints).
    """
    if len(coords) < 2:
        return []

    async def _calc_one(idx: int) -> dict[str, Any]:
        pair = [coords[idx], coords[idx + 1]]
        seg_polyline = await _call_amap_driving(pair)
        if not seg_polyline:
            seg_polyline = _straight_polyline(pair)
        color = SEGMENT_COLORS[idx % len(SEGMENT_COLORS)]
        label_lng = (pair[0]["lng"] + pair[1]["lng"]) / 2.0
        label_lat = (pair[0]["lat"] + pair[1]["lat"]) / 2.0
        return {
            "polyline": seg_polyline,
            "color": color,
            "label": str(idx + 1),
            "from_name": _truncate_name(coords[idx].get("name", "")),
            "to_name": _truncate_name(coords[idx + 1].get("name", "")),
            "label_lng": label_lng,
            "label_lat": label_lat,
        }

    tasks = [asyncio.create_task(_calc_one(i)) for i in range(len(coords) - 1)]
    return list(await asyncio.gather(*tasks))


def _truncate_name(name: str, max_len: int = 8) -> str:
    """Truncate a place name for display."""
    text = _clean_place_name(name)
    if not text:
        text = name.strip()
    if len(text) > max_len:
        return text[:max_len - 1] + "…"
    return text
