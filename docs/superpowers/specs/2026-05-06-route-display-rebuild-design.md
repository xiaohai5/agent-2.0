# Route Display Rebuild Design

## Goal

Rebuild the route display feature from frontend to backend. Based on saved plans, display driving routes on the map that connect sequentially. Every location must be accurately connected with correct routes.

## Problem Summary

Current implementation has multiple issues:

1. **Pairwise route calculation** — calls AMap driving API for each consecutive pair (A→B, B→C...), producing polylines that may not connect smoothly at segment boundaries.
2. **Background enrichment with polling** — routes are calculated in background `_enrich_plan`, frontend polls for up to 30s waiting for results. Fragile and poor UX.
3. **Cross-day disconnection** — no routes between days.
4. **Regex-based geocoding fallback** — inaccurate for items without AI-provided coordinates (but this is rare since AI returns coordinates).

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Route calculation | Waypoints-based single API call per day | AMap optimizes the entire route; polyline is naturally continuous |
| Calculation timing | On-demand when user clicks "show route" | Accuracy first; no stale pre-calculated routes |
| Caching | Redis, TTL 1 hour | Speed for repeat views; invalidated on plan update |
| Day switching | DaySelector component + API filter | User can view per-day or all days |
| Old code | Remove background enrichment and polling | Clean break from broken approach |

## Architecture

### Backend

**New endpoint:** `GET /api/plans/{plan_id}/routes?days=1,2,3`

- `days` (optional): comma-separated day numbers. Omit for all days.
- Response includes per-day polylines, markers, and optional cross-day connections.

**Route calculation per day:**
1. Collect all items with coordinates (lng, lat) in order
2. First item → `origin`, last item → `destination`, middle items → `waypoints`
3. Single AMap `/direction/driving` call
4. Extract polyline from response steps
5. Cache in Redis with key `route:{plan_id}:{days_hash}`, TTL 3600s

**Edge cases:**
- Day with only 1 location → return empty polyline, marker only
- Item missing coordinates → mark as `status: "partial"`, skip in route
- AMap API failure → return error with retry guidance
- Too many waypoints (>16) → split into chunks
- Same location as start and end → marker type `start_end`

**Response schema:**
```json
{
  "code": 0,
  "data": {
    "plan_id": 1,
    "title": "北京三日游",
    "days": [{
      "day": 1,
      "title": "第1天",
      "color": "#4A7FBF",
      "polyline": [[116.397, 39.908], [116.403, 39.916]],
      "markers": [
        {"lng": 116.397, "lat": 39.908, "name": "天安门", "type": "start"},
        {"lng": 116.403, "lat": 39.916, "name": "故宫", "type": "waypoint"},
        {"lng": 116.410, "lat": 39.920, "name": "XX酒店", "type": "end"}
      ]
    }]
  }
}
```

**Marker types:**
- `start` — first location of the day
- `end` — last location of the day
- `waypoint` — intermediate location
- `start_end` — when start and end are the same location

**Files to create/modify:**
- `backend/app/api/routes/plans.py` — add `GET /{plan_id}/routes` endpoint
- `backend/app/services/route_service.py` — new service with waypoints-based calculation + caching
- `backend/app/services/saved_plan_service.py` — remove `_enrich_plan`, `_get_driving_route`

### Frontend

**Data flow:**
```
PlansView: click "显示路线"
  → useAssistantApp.loadRoutes(planId)
    → GET /api/plans/{planId}/routes
  → set activeRoutePlan with full route data
  → MapView watch triggers renderRoute()
    → draw markers + polylines per day
    → show DaySelector
```

**DaySelector component:**
- Position: top-center of map, floating pill buttons
- Buttons: `[全部] [D1] [D2] [D3]` (dynamically generated from plan days)
- "全部" = show all days; clicking a specific day = show only that day
- Each day button uses its assigned color
- Clicking "全部" when a single day is active restores all days

**MapView changes:**
- Replace `loadRoutePlan()` with `renderRoute()` that consumes new API response format
- Remove polling-related status messages
- Add `activeDay` ref to track which day(s) are visible
- Filter markers/polylines by `activeDay`

**PlansView changes:**
- "显示路线" button calls `app.loadRoutes(plan.id)` before setting `activeRoutePlan`
- Show loading state on button while fetching

**useAssistantApp changes:**
- Add `loadRoutes(planId, days?)` method
- Simplify `activeRoutePlan` to store API response directly
- Remove polling logic from `confirmPlan()`

**Files to modify:**
- `frontend/src/views/MapView.vue` — rewrite route rendering, add DaySelector
- `frontend/src/views/PlansView.vue` — update button logic
- `frontend/src/composables/useAssistantApp.js` — add loadRoutes, remove polling

### Code to Remove

**Backend:**
- `SavedPlanService._enrich_plan()` — entire background enrichment method
- `SavedPlanService._get_driving_route()` — pairwise route calculation
- `SavedPlanService._geocode_with_context()` — only if no longer needed
- `PlanDay.routes` field in schema — no longer pre-stored

**Frontend:**
- `loadRoutePlan()` in MapView — replaced by `renderRoute()`
- Polling logic in `confirmPlan()` — no longer needed
- Status messages referencing "路线计算中..."

### Day Colors

Preserve existing color palette:
```js
const DAY_COLORS = [
  "#4A7FBF", "#FF9500", "#34C759", "#FF3B30",
  "#AF52DE", "#007AFF", "#FF2D55", "#5AC8FA",
];
```

## Implementation Order

1. Backend: Create `route_service.py` with waypoints-based calculation + Redis caching
2. Backend: Add `GET /api/plans/{plan_id}/routes` endpoint
3. Backend: Remove deprecated code from `saved_plan_service.py`
4. Frontend: Add `loadRoutes` to `useAssistantApp.js`
5. Frontend: Update `PlansView.vue` button logic
6. Frontend: Rewrite `MapView.vue` route rendering + DaySelector
7. Integration test: save plan → view routes → switch days
