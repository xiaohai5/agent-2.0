# Route Display Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild route display to use waypoints-based AMap API calls, on-demand calculation with Redis caching, and a DaySelector for per-day viewing.

**Architecture:** New `RouteService` handles waypoints-based AMap driving route calculation with Redis caching. New `GET /api/plans/{plan_id}/routes` endpoint serves routes on demand. Frontend `loadRoutes()` fetches routes when user clicks "show route", MapView renders with a DaySelector component for filtering by day.

**Tech Stack:** Python/FastAPI backend, AMap REST API, Redis caching, Vue 3 frontend, AMap JS SDK v2.0

---

### Task 1: Create route_service.py

**Files:**
- Create: `backend/app/services/route_service.py`

- [ ] **Step 1: Write route_service.py**

```python
from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

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

            if len(coords) < 2:
                # Single location: markers only, no polyline
                markers = _build_markers(coords, day.get("day", i + 1))
                polyline = []
            else:
                markers = _build_markers(coords, day.get("day", i + 1))
                polyline = await _calculate_day_polyline(coords)

            result_days.append({
                "day": day.get("day", i + 1),
                "title": day.get("title", f"第{i + 1}天"),
                "color": color,
                "polyline": polyline,
                "markers": markers,
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
    coords: list[dict[str, Any]], day_num: int
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
    Single AMap API call produces a continuous polyline.
    """
    if len(coords) < 2:
        return []

    origin = f"{coords[0]['lng']},{coords[0]['lat']}"
    destination = f"{coords[-1]['lng']},{coords[-1]['lat']}"

    params: dict[str, str | int] = {
        "key": AMAP_KEY,
        "origin": origin,
        "destination": destination,
        "extensions": "all",
        "strategy": "0",
    }

    # Middle points as waypoints
    if len(coords) > 2:
        waypoints = ";".join(
            f"{c['lng']},{c['lat']}" for c in coords[1:-1]
        )
        params["waypoints"] = waypoints

    url = f"{AMAP_REST_URL}/direction/driving?{urlencode(params)}"
    try:
        data = await _fetch_json_async(url)
    except (HTTPError, URLError, OSError, TimeoutError):
        return []

    if data.get("status") != "1":
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
    except (KeyError, ValueError, TypeError):
        return []

    return polyline
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/route_service.py
git commit -m "feat: add RouteService with waypoints-based calculation and Redis caching"
```

---

### Task 2: Add GET /api/plans/{plan_id}/routes endpoint

**Files:**
- Modify: `backend/app/api/routes/saved_plan.py`
- Modify: `backend/app/schemas/saved_plan.py`

- [ ] **Step 1: Add route response schemas to saved_plan.py**

Add these schemas after line 17 of `backend/app/schemas/saved_plan.py`:

```python
class RouteMarker(BaseModel):
    lng: float
    lat: float
    name: str
    type: str  # "start" | "end" | "waypoint" | "start_end"


class RouteDayData(BaseModel):
    day: int
    title: str
    color: str
    polyline: list[list[float]] = Field(default_factory=list)
    markers: list[RouteMarker] = Field(default_factory=list)


class RoutePlanData(BaseModel):
    plan_id: int
    title: str
    days: list[RouteDayData] = Field(default_factory=list)
```

- [ ] **Step 2: Add route endpoint to saved_plan.py routes**

Add to `backend/app/api/routes/saved_plan.py` after the router definition (line 14):

```python
from backend.app.schemas.saved_plan import RoutePlanData
from backend.app.services.route_service import RouteService

route_service = RouteService(redis_url=SETTINGS.redis_url)


@router.get("/{plan_id}/routes", response_model=ApiResponse[RoutePlanData])
async def get_plan_routes(
    plan_id: int,
    days: str | None = Query(default=None, description="逗号分隔的天编号，如 1,2,3"),
    user_id: int = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[RoutePlanData]:
    day_list = None
    if days:
        try:
            day_list = [int(d.strip()) for d in days.split(",") if d.strip()]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="days 参数格式错误，应为逗号分隔的数字",
            )

    result = await route_service.get_plan_routes(
        db=db, plan_id=plan_id, user_id=user_id, days=day_list,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="计划不存在",
        )
    return ApiResponse(message="ok", data=RoutePlanData(**result))
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/saved_plan.py backend/app/api/routes/saved_plan.py
git commit -m "feat: add GET /api/plans/{plan_id}/routes endpoint"
```

---

### Task 3: Clean up saved_plan_service.py

**Files:**
- Modify: `backend/app/services/saved_plan_service.py`

- [ ] **Step 1: Remove deprecated enrichment code**

Remove the following from `backend/app/services/saved_plan_service.py`:

1. Remove `import asyncio` (line 3) if only used for `create_task` — we'll replace with direct import
2. Remove unused imports: `re`, `traceback`, `urlencode` from `urllib.parse`, `Request`/`urlopen` from `urllib.request`
3. Remove constants `AMAP_REST_URL`, `AMAP_KEY`, `GEOCODE_CACHE_TTL`, `ITEM_TYPE_TO_AMAP_TYPES` (lines 24-35)
4. Remove functions: `_extract_location_name`, `_haversine`, `_pick_best_poi`, `_amap_fetch`, `_amap_fetch_async` (lines 42-128)
5. Remove methods: `_extract_city`, `_geocode_with_context`, `_get_driving_route`, `_enrich_plan` (all from `SavedPlanService`)
6. In `create_plan` method, remove the `asyncio.create_task(self._enrich_plan(...))` line

The final `create_plan` method should be:

```python
async def create_plan(
    self,
    db: AsyncSession,
    user_id: int,
    payload: SavedPlanCreate,
) -> dict[str, Any]:
    plan_data = {
        "days": [d.model_dump() for d in payload.days],
        "overview": payload.overview,
        "title": payload.title,
    }
    plan = await plan_crud.create_plan(
        db=db,
        user_id=user_id,
        title=payload.title,
        plan_data=plan_data,
        source_message_id=payload.source_message_id,
        overview=payload.overview,
    )
    await self._invalidate_cache(user_id)
    return _plan_to_dict(plan)
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/services/saved_plan_service.py
git commit -m "refactor: remove deprecated background enrichment and pairwise route calculation"
```

---

### Task 4: Add loadRoutes to useAssistantApp.js and remove polling

**Files:**
- Modify: `frontend/src/composables/useAssistantApp.js`

- [ ] **Step 1: Add loadRoutes method**

Add after the `setActiveRoute` function (around line 714):

```javascript
async function loadRoutes(planId, days) {
  if (!state.token) return null;
  const path = days && days.length
    ? `/api/plans/${planId}/routes?days=${days.join(",")}`
    : `/api/plans/${planId}/routes`;
  const data = await client.request(path, { method: "GET" });
  return data || null;
}
```

- [ ] **Step 2: Remove polling logic from confirmPlan**

In `confirmPlan()` (line 717), remove the polling block (lines 750-781). The method should end after:

```javascript
savedPlans.value = [newPlan, ...savedPlans.value];
return newPlan;
```

Remove these lines:
```javascript
// After saving, poll for enrichment
if (state.token) {
  const planId = newPlan.id;
  let attempts = 0;
  // ... all polling code ...
  setTimeout(poll, pollInterval);
}
```

- [ ] **Step 3: Export loadRoutes**

Add `loadRoutes` to the return object (around line 888):

```javascript
const instance = {
  // ... existing exports ...
  loadRoutes,
};
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/composables/useAssistantApp.js
git commit -m "feat: add loadRoutes method, remove polling logic"
```

---

### Task 5: Update PlansView.vue button logic

**Files:**
- Modify: `frontend/src/views/PlansView.vue`

- [ ] **Step 1: Update confirmRoute to call loadRoutes**

Replace the `confirmRoute` function (line 192) with:

```javascript
async function confirmRoute(plan) {
  if (isActiveRoutePlan(plan.id)) {
    app.setActiveRoute(null);
  } else {
    try {
      const routeData = await app.loadRoutes(plan.id);
      if (routeData) {
        app.setActiveRoute({ ...plan, routeData });
      }
    } catch (_) {
      // Fall back to plan without route data
      app.setActiveRoute({ ...plan, routeData: null });
    }
  }
}
```

- [ ] **Step 2: Add loading state to route button**

Add a `routeLoading` ref:

```javascript
const routeLoading = ref(null); // plan id that is currently loading
```

Update `confirmRoute`:

```javascript
async function confirmRoute(plan) {
  if (isActiveRoutePlan(plan.id)) {
    app.setActiveRoute(null);
  } else {
    routeLoading.value = plan.id;
    try {
      const routeData = await app.loadRoutes(plan.id);
      if (routeData) {
        app.setActiveRoute({ ...plan, routeData });
      }
    } catch (_) {
      app.setActiveRoute({ ...plan, routeData: null });
    } finally {
      routeLoading.value = null;
    }
  }
}
```

Update the route button template (line 116) to show loading:

```html
<button
  class="route-btn"
  :class="{ active: isActiveRoutePlan(plan.id), loading: routeLoading === plan.id }"
  :disabled="routeLoading === plan.id"
  @click.stop="confirmRoute(plan)"
>
  <svg v-if="routeLoading !== plan.id" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
    <polygon points="3 11 22 2 13 21 11 13 3 11"/>
  </svg>
  <span v-else class="btn-spinner"></span>
  <span>{{ routeLoading === plan.id ? '加载中...' : isActiveRoutePlan(plan.id) ? '已显示路线' : '显示路线' }}</span>
</button>
```

Add spinner CSS after `.route-btn.active`:

```css
.route-btn.loading { opacity: 0.7; }
.btn-spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/views/PlansView.vue
git commit -m "feat: update PlansView to call loadRoutes before showing map"
```

---

### Task 6: Rewrite MapView.vue route rendering with DaySelector

**Files:**
- Modify: `frontend/src/views/MapView.vue`

- [ ] **Step 1: Replace loadRoutePlan with renderRoute**

Remove the `loadRoutePlan` function entirely (lines 242-327). Add the new `renderRoute` function:

```javascript
const activeDay = ref(0); // 0 = all days, 1/2/3 = specific day

function renderRoute(plan) {
  clearRoutePlanMarkers();
  if (!plan || !map) return;

  const routeData = plan.routeData;
  if (!routeData || !routeData.days) {
    showStatus("路线数据暂不可用");
    return;
  }

  const allDays = routeData.days;
  const visibleDays = activeDay.value === 0
    ? allDays
    : allDays.filter((d) => d.day === activeDay.value);

  if (visibleDays.length === 0) return;

  let totalMarkers = 0;
  let totalPolylines = 0;

  for (const day of visibleDays) {
    // Draw polyline
    if (day.polyline && day.polyline.length > 0) {
      const polyline = new window.AMap.Polyline({
        path: day.polyline,
        strokeColor: day.color,
        strokeWeight: 6,
        strokeOpacity: 0.9,
        lineJoin: "round",
        lineCap: "round",
        zIndex: 999,
      });
      polyline.setMap(map);
      routePlanPolylines.push(polyline);
      totalPolylines++;
    }

    // Draw markers
    for (const m of day.markers) {
      let marker;
      if (m.type === "start_end") {
        marker = createStartEndMarker(m.lng, m.lat, m.name, "both");
      } else if (m.type === "start") {
        marker = createStartEndMarker(m.lng, m.lat, m.name, "start");
      } else if (m.type === "end") {
        marker = createStartEndMarker(m.lng, m.lat, m.name, "end");
      } else {
        marker = createColoredMarker(m.lng, m.lat, m.name, day.color, `D${day.day}`);
      }
      marker.setMap(map);
      routePlanMarkers.push(marker);
      totalMarkers++;
    }
  }

  if (routePlanMarkers.length > 0) {
    map.setFitView(routePlanMarkers, true, [60, 60, 60, 60]);
  }

  showStatus(`共 ${allDays.length} 天 · ${totalMarkers} 个地点 · ${totalPolylines} 条路线`);
}
```

- [ ] **Step 2: Add DaySelector to template**

Add after the travel badge div (line 33 in original):

```html
<!-- Day selector -->
<div v-if="dayOptions.length > 1" class="day-selector glass-bar">
  <button
    v-for="opt in dayOptions"
    :key="opt.value"
    class="day-chip"
    :class="{ active: activeDay === opt.value }"
    :style="activeDay === opt.value ? { background: opt.color, color: '#fff' } : { color: opt.color, borderColor: opt.color }"
    @click="switchDay(opt.value)"
  >
    {{ opt.label }}
  </button>
</div>
```

Replace `dayOptions` computed:

```javascript
const dayOptions = computed(() => {
  const plan = app.activeRoutePlan.value;
  if (!plan || !plan.routeData || !plan.routeData.days) return [];
  const opts = [{ value: 0, label: "全部", color: "#4A7FBF" }];
  for (const d of plan.routeData.days) {
    opts.push({ value: d.day, label: `D${d.day}`, color: d.color });
  }
  return opts;
});
```

Add `switchDay` function:

```javascript
function switchDay(day) {
  activeDay.value = day;
  renderRoute(app.activeRoutePlan.value);
}
```

- [ ] **Step 3: Update watch to use renderRoute**

Replace the `activeRoutePlan` watch (line 438):

```javascript
watch(
  () => app.activeRoutePlan.value,
  (plan) => {
    activeDay.value = 0;
    renderRoute(plan);
  },
  { deep: true }
);
```

- [ ] **Step 4: Add DaySelector CSS**

Add after the `.map-status` styles:

```css
.day-selector {
  position: absolute;
  top: 68px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  gap: 6px;
  padding: 4px;
  border-radius: var(--r-full);
  z-index: 3;
  box-shadow: var(--shadow-sm);
}
.day-chip {
  padding: 4px 14px;
  border-radius: var(--r-full);
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
  border: 1.5px solid transparent;
  background: rgba(255,255,255,0.9);
  transition: all 0.2s ease;
  white-space: nowrap;
}
.day-chip:active { transform: scale(0.93); }
```

- [ ] **Step 5: Add computed import**

Ensure `computed` is imported in the `<script setup>` (line 40):

```javascript
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/MapView.vue
git commit -m "feat: rewrite MapView route rendering with DaySelector and on-demand routes"
```

---

### Task 7: Integration verification

- [ ] **Step 1: Start backend and verify the new endpoint works**

```bash
# Start the backend server (if not running)
cd d:/daima/project/agent2.0
# Test the endpoint with a plan ID
curl -s http://localhost:8000/api/plans/1/routes | python -m json.tool
```

Expected: Route data with days containing polylines and markers.

- [ ] **Step 2: Verify frontend loads routes on button click**

Check that:
1. PlansView shows "显示路线" button for each plan
2. Clicking it shows a loading spinner on the button
3. The MapView renders with DaySelector and route polylines
4. Clicking day chips filters the display
5. Clicking "全部" shows all days

- [ ] **Step 3: Verify edge cases**

Test these scenarios:
1. Plan with only 1 location in a day — should show marker but no polyline
2. Plan with missing coordinates — should skip those items
3. Plan where start and end are the same hotel — should show "始终" marker

- [ ] **Step 4: Commit if any final tweaks needed**

```bash
git add -A
git commit -m "chore: integration verification tweaks"
```
