<template>
  <div class="map-page">
    <!-- Loading -->
    <div v-if="loading" class="map-loading">
      <div class="loading-spinner"></div>
      <p>地图加载中...</p>
    </div>

    <!-- Error -->
    <div v-else-if="errorMsg" class="map-error glass-card">
      <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
      <strong>地图加载失败</strong>
      <p>{{ errorMsg }}</p>
      <button class="retry-btn" @click="initMap">重试</button>
    </div>

    <!-- Map -->
    <div v-show="!loading && !errorMsg" id="amap-container" ref="mapContainer" class="map-container"></div>

    <!-- Locate button -->
    <button v-if="!loading && !errorMsg" class="locate-btn glass-card" @click="locateMe" aria-label="定位">
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="3"/>
        <line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/>
        <line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/>
      </svg>
    </button>

    <!-- Travel count badge -->
    <div v-if="travelMarkers.length > 0" class="travel-badge glass-bar">
      行程 {{ travelMarkers.length }} 个地点
    </div>

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

    <!-- Status -->
    <div v-if="statusText" class="map-status glass-bar">{{ statusText }}</div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useAssistantApp } from "../composables/useAssistantApp";

const app = useAssistantApp();
const mapContainer = ref(null);
const statusText = ref("");
const loading = ref(true);
const errorMsg = ref("");

const AMAP_JS_KEY = import.meta.env.VITE_AMAP_JS_KEY || "";

let map = null;
let geocoder = null;
let currentMarker = null;
let travelMarkers = [];
let routePlanMarkers = [];
let routePlanPolylines = [];
let myLocation = null;

const activeDay = ref(0); // 0 = all days

const dayOptions = computed(() => {
  const plan = app.activeRoutePlan.value;
  if (!plan || !plan.routeData || !plan.routeData.days) return [];
  const opts = [{ value: 0, label: "全部", color: "#4A7FBF" }];
  for (const d of plan.routeData.days) {
    opts.push({ value: d.day, label: `D${d.day}`, color: d.color });
  }
  return opts;
});

const DAY_COLORS = [
  "#4A7FBF", "#FF9500", "#34C759", "#FF3B30",
  "#AF52DE", "#007AFF", "#FF2D55", "#5AC8FA",
];

function loadScript(url) {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${url}"]`)) return resolve();
    const script = document.createElement("script");
    script.src = url;
    script.onload = resolve;
    script.onerror = () => reject(new Error("AMap SDK 加载失败"));
    document.head.appendChild(script);
  });
}

async function initMap() {
  if (!mapContainer.value) return;
  loading.value = true;
  errorMsg.value = "";

  try {
    await loadScript(
      `https://webapi.amap.com/maps?v=2.0&key=${AMAP_JS_KEY}&plugin=AMap.Geocoder,AMap.Geolocation`
    );

    if (map) { map.destroy(); map = null; }

    map = new window.AMap.Map(mapContainer.value, {
      zoom: 14,
      center: [116.397428, 39.90923],
      viewMode: "2D",
      resizeEnable: true,
    });

    geocoder = new window.AMap.Geocoder();
    loading.value = false;

    locateByIP();
    renderTravelPois();

    // Load the route plan if one was set before the map was ready
    if (app.activeRoutePlan.value) {
      renderRoute(app.activeRoutePlan.value);
    }
  } catch (e) {
    loading.value = false;
    errorMsg.value = e.message || "未知错误";
  }
}

// ── Backend API ──

async function apiGet(path) {
  const resp = await fetch(`${app.baseUrl.value}/api/map${path}`, {
    headers: app.state.token ? { Authorization: `Bearer ${app.state.token}` } : {},
  });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ message: resp.statusText }));
    throw new Error(err.detail || err.message || "请求失败");
  }
  return resp.json();
}

// ── Create marker helper ──

function createPoiMarker(lng, lat, poi, category) {
  const marker = new window.AMap.Marker({ position: [lng, lat], title: poi.name });
  marker.setMap(map);

  const stars = poi.biz_ext?.rating
    ? `<span style="color:#ff9500;margin-left:6px;">${"★".repeat(Math.round(Number(poi.biz_ext.rating)))} ${poi.biz_ext.rating}</span>`
    : poi.rating
      ? `<span style="color:#ff9500;margin-left:6px;">${"★".repeat(Math.round(Number(poi.rating)))}</span>`
      : "";
  const cost = poi.biz_ext?.cost ? `人均 ¥${poi.biz_ext.cost}<br/>` : "";
  const infoContent = [
    `<div style="min-width:140px;font-size:13px;">`,
    `<strong style="color:#263548;">${poi.name}</strong>${stars}<br/>`,
    poi.address ? `<span style="color:rgba(38,53,72,0.58);font-size:12px;">${poi.address}</span><br/>` : "",
    cost,
    category ? `<span style="color:#7EC8E3;font-size:11px;">${category}</span>` : "",
    `</div>`,
  ].join("");

  marker.on("click", () => {
    new window.AMap.InfoWindow({
      content: infoContent,
      offset: new window.AMap.Pixel(0, -30),
    }).open(map, [lng, lat]);
  });

  return marker;
}

function clearTravelMarkers() {
  travelMarkers.forEach((m) => map.remove(m));
  travelMarkers = [];
}

function clearRoutePlanMarkers() {
  routePlanMarkers.forEach((m) => map.remove(m));
  routePlanMarkers = [];
  routePlanPolylines.forEach((p) => { p.setMap(null); });
  routePlanPolylines = [];
}

function createColoredMarker(lng, lat, name, color, dayLabel) {
  const content = `<div style="
    display:flex;align-items:center;gap:4px;
  ">
    <div style="
      width:14px;height:14px;border-radius:50%;background:${color};
      border:2.5px solid #fff;box-shadow:0 1px 5px rgba(0,0,0,0.25);
      flex-shrink:0;
    "></div>
    <span style="font-size:11px;font-weight:600;color:${color};white-space:nowrap;">${dayLabel}</span>
  </div>`;
  const marker = new window.AMap.Marker({
    position: [lng, lat],
    title: name,
    content,
    offset: new window.AMap.Pixel(0, -7),
    zIndex: 900,
  });
  marker.on("click", () => {
    new window.AMap.InfoWindow({
      content: `<div style="font-size:13px;padding:2px 6px;"><strong>${name}</strong></div>`,
      offset: new window.AMap.Pixel(0, -28),
    }).open(map, [lng, lat]);
  });
  return marker;
}

function createStartEndMarker(lng, lat, name, type) {
  const isBoth = type === "both";
  const isStart = type === "start";
  const bgColor = "#FF9500";
  const label = isBoth ? "始终" : isStart ? "起" : "终";
  const text = isBoth ? "起终点" : isStart ? "起点" : "终点";
  const content = `<div style="
    display:flex;flex-direction:column;align-items:center;gap:1px;
  ">
    <div style="
      width:24px;height:24px;border-radius:50%;background:${bgColor};
      border:3px solid #fff;box-shadow:0 2px 8px rgba(0,0,0,0.3);
      display:grid;place-items:center;
      color:#fff;font-size:${isBoth ? '9px' : '12px'};font-weight:700;
    ">${label}</div>
    <span style="font-size:10px;font-weight:600;color:${bgColor};white-space:nowrap;">${text}</span>
  </div>`;
  const marker = new window.AMap.Marker({
    position: [lng, lat],
    title: `${text}：${name}`,
    content,
    offset: new window.AMap.Pixel(0, -16),
    zIndex: 1000,
  });
  marker.on("click", () => {
    new window.AMap.InfoWindow({
      content: `<div style="font-size:13px;padding:2px 6px;"><strong>${text}：${name}</strong></div>`,
      offset: new window.AMap.Pixel(0, -36),
    }).open(map, [lng, lat]);
  });
  return marker;
}

function drawRoutePolyline(path, color) {
  const polyline = new window.AMap.Polyline({
    path,
    strokeColor: color,
    strokeWeight: 6,
    strokeOpacity: 0.95,
    lineJoin: "round",
    lineCap: "round",
    zIndex: 999,
  });
  polyline.setMap(map);
  routePlanPolylines.push(polyline);
  return polyline;
}


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

  showStatus(`${allDays.length} 天 · ${totalMarkers} 个地点 · ${totalPolylines} 条路线`);
}

function switchDay(day) {
  activeDay.value = day;
  renderRoute(app.activeRoutePlan.value);
}

// ── IP Location ──

async function locateByIP() {
  try {
    const result = await apiGet("/ip-locate");
    const data = result?.data;
    if (data?.rectangle) {
      const [sw, ne] = data.rectangle.split(";");
      const [swLng, swLat] = sw.split(",").map(Number);
      const [neLng, neLat] = ne.split(",").map(Number);
      myLocation = [(swLng + neLng) / 2, (swLat + neLat) / 2];
      map.setZoomAndCenter(12, myLocation);
      showStatus(`已定位到 ${data.city || data.province || ""}`);
    }
  } catch (_) {}
}

// ── Geolocation ──

function locateMe() {
  if (!map) return;

  window.AMap.plugin("AMap.Geolocation", () => {
    const geo = new window.AMap.Geolocation({ enableHighAccuracy: true, timeout: 8000 });
    geo.getCurrentPosition(async (status, result) => {
      if (status === "complete" && result.position) {
        const { lng, lat } = result.position;
        myLocation = [lng, lat];
        map.setZoomAndCenter(17, [lng, lat]);

        if (currentMarker) { map.remove(currentMarker); }

        let address = "";
        if (geocoder) {
          try {
            const geoResult = await new Promise((resolve) => {
              geocoder.getAddress([lng, lat], (s, r) => resolve(r));
            });
            if (geoResult?.regeocode?.formattedAddress) {
              address = geoResult.regeocode.formattedAddress;
            }
          } catch (_) {}
        }

        currentMarker = new window.AMap.Marker({
          position: [lng, lat],
          title: address || "我的位置",
          zIndex: 100,
        });
        currentMarker.setMap(map);

        new window.AMap.InfoWindow({
          content: `<div style="min-width:140px;font-size:13px;"><strong>我的位置</strong><br/><span style="color:rgba(38,53,72,0.58);">${address || `${lng.toFixed(6)}, ${lat.toFixed(6)}`}</span></div>`,
          offset: new window.AMap.Pixel(0, -30),
        }).open(map, [lng, lat]);

        showStatus(address ? `已定位：${address.slice(0, 20)}...` : "已定位");
      } else {
        showStatus("GPS定位失败，尝试IP定位...");
        await locateByIP();
      }
    });
  });
}

// ── Travel plan POIs from chat ──

function renderTravelPois() {
  if (!map) return;
  const pois = app.travelPois.value;
  if (!pois.length) return;

  const validPois = pois.filter((p) => p.lng != null && p.lat != null);
  if (!validPois.length) return;

  clearTravelMarkers();

  const markers = [];
  validPois.forEach((poi) => {
    const marker = createPoiMarker(poi.lng, poi.lat, {
      name: poi.name,
      address: poi.address,
      rating: poi.rating,
    }, poi.type || "行程");
    markers.push(marker);
  });

  travelMarkers = markers;

  if (markers.length) {
    map.setFitView(markers, true, [60, 60, 60, 60]);
    showStatus(`已加载 ${markers.length} 个旅行地点`);
  }
}

function showStatus(msg) {
  statusText.value = msg;
  setTimeout(() => { statusText.value = ""; }, 2500);
}

// ── Watch ──

watch(
  () => app.travelPois.value,
  () => { renderTravelPois(); },
  { deep: true }
);

watch(
  () => app.activeRoutePlan.value,
  (plan) => {
    activeDay.value = 0;
    renderRoute(plan);
  },
  { deep: true }
);

onMounted(() => { initMap(); });

onUnmounted(() => {
  clearRoutePlanMarkers();
  if (map) { map.destroy(); map = null; }
});
</script>

<style scoped>
.map-page {
  position: absolute;
  inset: 0;
  overflow: hidden;
}

.map-container {
  width: 100%;
  height: 100%;
}

/* Loading */
.map-loading {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: linear-gradient(175deg, #fdfeff, #f8fafd);
  z-index: 10;
  color: var(--label-2);
  font-size: 14px;
}
.loading-spinner {
  width: 36px; height: 36px;
  border: 3px solid var(--hairline);
  border-top-color: var(--sky);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* Error */
.map-error {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  z-index: 10;
  margin: 12px;
  border-radius: var(--r-xl);
  background: #fff;
  text-align: center;
  padding: 24px;
}
.map-error svg { color: var(--red); }
.map-error strong { color: var(--label); font-size: 16px; }
.map-error p { color: var(--label-2); font-size: 13px; margin: 0; max-width: 280px; }
.retry-btn {
  margin-top: 8px;
  padding: 8px 24px;
  border-radius: var(--r-full);
  background: linear-gradient(135deg, var(--sky), var(--ocean));
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  border: none;
}

/* Locate button */
.locate-btn {
  position: absolute;
  right: 12px;
  bottom: 24px;
  width: 44px; height: 44px;
  display: grid; place-items: center;
  border-radius: 50%;
  color: var(--ocean);
  cursor: pointer;
  z-index: 2;
  transition: transform 0.2s var(--ease-spring), box-shadow 0.2s ease;
}
.locate-btn:active { transform: scale(0.9); }

/* Travel badge */
.travel-badge {
  position: absolute;
  top: 68px;
  right: 12px;
  padding: 6px 12px;
  border-radius: var(--r-full);
  font-size: 12px;
  font-weight: 700;
  color: var(--ocean);
  box-shadow: var(--shadow-sm);
  z-index: 2;
}

/* Status toast */
.map-status {
  position: absolute;
  top: 120px;
  left: 50%;
  transform: translateX(-50%);
  padding: 8px 16px;
  border-radius: var(--r-full);
  font-size: 13px;
  font-weight: 600;
  color: var(--label);
  box-shadow: var(--shadow-sm);
  z-index: 3;
  pointer-events: none;
  white-space: nowrap;
}

/* Day selector */
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
</style>
