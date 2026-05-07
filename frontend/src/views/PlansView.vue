<template>
  <section class="plans-page">
    <!-- Empty state -->
    <div v-if="app.savedPlans.value.length === 0" class="empty-state">
      <div class="empty-icon-wrap">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
          <line x1="16" y1="2" x2="16" y2="6"/>
          <line x1="8" y1="2" x2="8" y2="6"/>
          <line x1="3" y1="10" x2="21" y2="10"/>
          <path d="M8 14h.01M12 14h.01M16 14h.01"/>
        </svg>
      </div>
      <strong>还没有出行计划</strong>
      <p>在对话中让 AI 助手帮你规划行程，<br/>点击确认按钮即可添加到此处</p>
    </div>

    <!-- Plan tabs -->
    <div v-else class="plans-scroll ios-scroll">
      <article
        v-for="plan in app.savedPlans.value"
        :key="plan.id"
        class="plan-tab glass-card"
        :class="{ expanded: expandedId === plan.id }"
      >
        <!-- Tab header (always visible) -->
        <div
          class="tab-trigger"
          role="button"
          tabindex="0"
          @click="togglePlan(plan.id)"
          @keydown.enter.prevent="togglePlan(plan.id)"
          @keydown.space.prevent="togglePlan(plan.id)"
        >
          <div class="tab-left">
            <div class="tab-icon-wrap" :style="{ background: iconBg(plan.id), color: iconColor(plan.id) }">
              <svg v-if="iconKey(plan.id) === 'map'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="10" r="3"/><path d="M12 2a8 8 0 0 0-8 8c0 5.4 8 12 8 12s8-6.6 8-12a8 8 0 0 0-8-8z"/>
              </svg>
              <svg v-else-if="iconKey(plan.id) === 'star'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
              </svg>
              <svg v-else-if="iconKey(plan.id) === 'compass'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/><polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>
              </svg>
              <svg v-else-if="iconKey(plan.id) === 'mountain'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17 10l-5 5-5-5"/><path d="M3 18h18"/>
              </svg>
              <svg v-else-if="iconKey(plan.id) === 'sun'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
              </svg>
              <svg v-else-if="iconKey(plan.id) === 'building'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="4" y="2" width="16" height="20" rx="2"/><line x1="9" y1="6" x2="15" y2="6"/><line x1="9" y1="10" x2="15" y2="10"/><line x1="9" y1="14" x2="15" y2="14"/><line x1="12" y1="14" x2="12" y2="22"/>
              </svg>
              <svg v-else-if="iconKey(plan.id) === 'train'" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="4" y="3" width="16" height="16" rx="2"/><line x1="4" y1="11" x2="20" y2="11"/><line x1="8" y1="19" x2="8" y2="21"/><line x1="16" y1="19" x2="16" y2="21"/><line x1="12" y1="3" x2="12" y2="19"/><circle cx="8" cy="8" r="1"/><circle cx="16" cy="8" r="1"/>
              </svg>
              <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
              </svg>
            </div>
            <div class="tab-info">
              <strong class="tab-title">{{ plan.title }}</strong>
              <span class="tab-meta">
                {{ formatDate(plan.createdAt) }}
                <span class="tab-meta-sep">·</span>
                {{ plan.days.length }} 天行程
              </span>
            </div>
          </div>
          <div class="tab-right">
            <button
              class="route-btn route-btn-inline"
              :class="{ active: isActiveRoutePlan(plan.id), loading: routeLoading === plan.id }"
              :disabled="routeLoading === plan.id"
              @click.stop="confirmRoute(plan)"
            >
              <svg v-if="routeLoading !== plan.id" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                <polygon points="3 11 22 2 13 21 11 13 3 11"/>
              </svg>
              <span v-else class="btn-spinner"></span>
              <span>{{ routeLoading === plan.id ? '加载中' : isActiveRoutePlan(plan.id) ? '已显示' : '显示路线' }}</span>
            </button>
            <button class="tab-delete" @click.stop="removePlan(plan.id)" aria-label="删除计划">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>
            </button>
            <div class="tab-chevron" :class="{ open: expandedId === plan.id }">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><polyline points="6 9 12 15 18 9"/></svg>
            </div>
          </div>
        </div>

        <!-- Expanded timeline -->
        <div v-if="expandedId === plan.id" class="tab-body">
          <p v-if="plan.overview" class="plan-overview">{{ plan.overview }}</p>

          <div class="timeline">
            <template v-for="(day, di) in plan.days" :key="`day-${di}`">
              <div class="day-head">
                <div class="day-dot"></div>
                <h3 class="day-title">{{ day.title }}</h3>
              </div>

              <template v-for="(item, ii) in day.items" :key="`item-${di}-${ii}`">
                <div class="tl-item" :class="{ 'no-time': !item.time }">
                  <div class="tl-line"></div>
                  <div class="tl-node" :class="`node-${item.type}`">
                    <svg v-if="item.type === 'transport'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="1" y="3" width="15" height="11"/><polyline points="16 8 20 8 23 11 23 16 16 16"/><circle cx="5.5" cy="18.5" r="1.5"/><circle cx="18.5" cy="18.5" r="1.5"/>
                    </svg>
                    <svg v-else-if="item.type === 'hotel'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M3 21V9a2 2 0 0 1 2-2h2V3h10v4h2a2 2 0 0 1 2 2v12"/><path d="M7 21v-4h10v4"/><path d="M8 8h.01M12 8h.01M16 8h.01"/>
                    </svg>
                    <svg v-else-if="item.type === 'dining'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                      <path d="M18 8h1a4 4 0 0 1 0 8h-1"/><path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"/><line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/>
                    </svg>
                    <svg v-else-if="item.type === 'attraction'" width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                      <circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
                    </svg>
                    <svg v-else width="9" height="9" viewBox="0 0 24 24" fill="currentColor">
                      <circle cx="12" cy="12" r="5"/>
                    </svg>
                  </div>
                  <div class="tl-content">
                    <span v-if="item.time" class="tl-time">{{ item.time }}</span>
                    <span class="tl-desc">{{ item.description }}</span>
                  </div>
                </div>
              </template>
            </template>
          </div>

        </div>
      </article>

      <div class="feed-pad"></div>
    </div>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { useAssistantApp } from "../composables/useAssistantApp";

const app = useAssistantApp();
const expandedId = ref(null);
const routeLoading = ref(null); // plan id that is currently loading

onMounted(() => { app.fetchPlans(); });

const PLAN_ICONS = ["map", "star", "compass", "mountain", "sun", "building", "train", "globe"];
const PLAN_COLORS = [
  { bg: "rgba(74,127,191,0.14)", color: "#4A7FBF" },
  { bg: "rgba(255,149,0,0.12)", color: "#FF9500" },
  { bg: "rgba(52,199,89,0.11)", color: "#30B353" },
  { bg: "rgba(255,59,48,0.10)", color: "#FF3B30" },
  { bg: "rgba(175,82,222,0.11)", color: "#AF52DE" },
  { bg: "rgba(0,122,255,0.10)", color: "#007AFF" },
  { bg: "rgba(255,45,85,0.10)", color: "#FF2D55" },
  { bg: "rgba(90,200,250,0.13)", color: "#5AC8FA" },
];

function iconKey(planId) {
  const idx = app.savedPlans.value.findIndex((p) => p.id === planId);
  return PLAN_ICONS[idx % PLAN_ICONS.length];
}
function iconBg(planId) {
  const idx = app.savedPlans.value.findIndex((p) => p.id === planId);
  return PLAN_COLORS[idx % PLAN_COLORS.length].bg;
}
function iconColor(planId) {
  const idx = app.savedPlans.value.findIndex((p) => p.id === planId);
  return PLAN_COLORS[idx % PLAN_COLORS.length].color;
}

function togglePlan(id) {
  expandedId.value = expandedId.value === id ? null : id;
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const h = String(d.getHours()).padStart(2, "0");
  const min = String(d.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${day} ${h}:${min}`;
}

function removePlan(id) {
  if (expandedId.value === id) expandedId.value = null;
  app.removePlanApi(id);
}

function isActiveRoutePlan(planId) {
  return app.activeRoutePlan.value?.id === planId;
}

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
</script>

<style scoped>
.plans-page {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: linear-gradient(175deg, #fefcfd 0%, #f8fafd 30%, #f0f7fc 70%, #fbfdfe 100%);
}

/* ── Empty ── */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px 24px;
  text-align: center;
}
.empty-icon-wrap {
  width: 80px; height: 80px;
  display: grid; place-items: center;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(126,200,227,0.15), rgba(74,127,191,0.10));
  color: var(--label-3);
  margin-bottom: 8px;
}
.empty-state strong {
  font-size: 18px;
  font-weight: 700;
  color: var(--label);
}
.empty-state p {
  margin: 0;
  font-size: 14px;
  color: var(--label-2);
  line-height: 1.6;
}

/* ── Scroll ── */
.plans-scroll {
  flex: 1;
  min-height: 0;
  position: relative;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 12px;
  padding-bottom: calc(22px + env(safe-area-inset-bottom, 0px));
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.feed-pad { height: 22px; flex-shrink: 0; }

/* ── Plan Tab ── */
.plan-tab {
  border-radius: var(--r-lg);
  background: rgba(255,255,255,0.82);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 0.5px solid var(--hairline);
  box-shadow: var(--shadow-sm);
  overflow: hidden;
  transition: box-shadow 0.25s ease, border-color 0.25s ease;
}
.plan-tab.expanded {
  position: absolute;
  inset: 12px 12px calc(12px + env(safe-area-inset-bottom, 0px)) 12px;
  z-index: 5;
  display: flex;
  flex-direction: column;
  border-color: rgba(126,200,227,0.35);
  box-shadow: 0 4px 20px rgba(126,200,227,0.12);
}

/* ── Tab trigger ── */
.tab-trigger {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 16px;
  border: none;
  background: transparent;
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
  transition: background 0.15s ease;
}
.tab-trigger:active { background: rgba(126,200,227,0.05); }
.tab-trigger:focus-visible {
  outline: 2px solid rgba(74,127,191,0.45);
  outline-offset: -2px;
}

.tab-left {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
  text-align: left;
}

.tab-icon-wrap {
  width: 38px; height: 38px;
  border-radius: 12px;
  display: grid; place-items: center;
  flex-shrink: 0;
  transition: transform 0.2s var(--ease-spring);
}

.tab-info { min-width: 0; }
.tab-title {
  display: block;
  font-size: 15px;
  font-weight: 700;
  color: var(--label);
  letter-spacing: -0.2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tab-meta {
  display: block;
  margin-top: 2px;
  font-size: 12px;
  color: var(--label-3);
  font-weight: 500;
}
.tab-meta-sep { margin: 0 4px; }

.tab-right {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

.tab-delete {
  width: 28px; height: 28px;
  display: grid; place-items: center;
  border-radius: 50%;
  border: none;
  background: var(--fill-4);
  color: var(--label-3);
  cursor: pointer;
  transition: all 0.2s ease;
}
.tab-delete:hover {
  background: rgba(255,59,48,0.12);
  color: var(--red);
}

.tab-chevron {
  color: var(--label-3);
  transition: transform 0.3s var(--ease-spring);
  display: grid; place-items: center;
}
.tab-chevron.open { transform: rotate(180deg); }

/* ── Tab body ── */
.tab-body {
  padding: 0 16px 16px 16px;
  flex: 1;
  min-height: 0;
  max-height: none;
  overflow-y: auto;
  overscroll-behavior: contain;
  -webkit-overflow-scrolling: touch;
  animation: expand-in 0.35s var(--ease-bounce) both;
}
.tab-body::-webkit-scrollbar { width: 4px; }
.tab-body::-webkit-scrollbar-track { background: transparent; }
.tab-body::-webkit-scrollbar-thumb { background: rgba(38, 53, 72, 0.14); border-radius: 4px; }

@keyframes expand-in {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.route-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 7px 16px;
  border: none;
  border-radius: var(--r-full);
  background: linear-gradient(135deg, var(--sky), var(--ocean));
  color: #fff;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 3px 12px rgba(126, 200, 227, 0.30);
  transition: all 0.25s var(--ease-spring);
}
.route-btn:active { transform: scale(0.93); }
.route-btn.active {
  background: rgba(74, 127, 191, 0.12);
  color: var(--ocean);
  box-shadow: none;
}
.route-btn.loading { opacity: 0.7; }
.route-btn-inline {
  min-width: 86px;
  height: 30px;
  justify-content: center;
  padding: 6px 11px;
  font-size: 12px;
  white-space: nowrap;
}
.btn-spinner {
  width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}

.plan-overview {
  margin: 0 0 14px;
  padding: 8px 12px;
  font-size: 13px;
  color: var(--label-2);
  line-height: 1.55;
  white-space: pre-wrap;
  background: rgba(126,200,227,0.06);
  border-radius: 8px;
}

/* ── Timeline ── */
.timeline { position: relative; padding-left: 0; }

.day-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 2px;
  position: relative;
}
.day-head + .day-head { margin-top: 16px; }

.day-dot {
  width: 12px; height: 12px;
  border-radius: 50%;
  background: var(--ocean);
  box-shadow: 0 0 0 4px rgba(74,127,191,0.15);
  flex-shrink: 0;
  z-index: 1;
}
.day-title {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  color: var(--ocean);
  letter-spacing: -0.2px;
}

.tl-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  min-height: 36px;
  position: relative;
}

.tl-line {
  position: absolute;
  left: 5.5px;
  top: 0;
  bottom: 0;
  width: 1.5px;
  background: linear-gradient(180deg, var(--hairline), rgba(126,200,227,0.3));
  z-index: 0;
}
.tl-item:last-child .tl-line { height: 50%; }

.tl-node {
  width: 28px; height: 28px;
  border-radius: 50%;
  display: grid; place-items: center;
  flex-shrink: 0;
  z-index: 1;
  margin-top: 2px;
}

.node-transport { background: rgba(91,155,213,0.12); color: #5B9BD5; }
.node-hotel { background: rgba(126,200,227,0.14); color: #4A7FBF; }
.node-dining { background: rgba(255,149,0,0.10); color: #FF9500; }
.node-attraction { background: rgba(52,199,89,0.10); color: #34C759; }
.node-general { background: rgba(142,142,147,0.10); color: #8E8E93; }

.tl-content {
  flex: 1;
  min-width: 0;
  padding-top: 2px;
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
}

.tl-time {
  font-size: 12px;
  font-weight: 700;
  color: var(--ocean);
  background: rgba(74,127,191,0.08);
  padding: 1px 6px;
  border-radius: 4px;
  white-space: nowrap;
  flex-shrink: 0;
}

.tl-desc {
  font-size: 14px;
  color: var(--label);
  line-height: 1.5;
  word-break: break-word;
}

.tl-item.no-time .tl-desc {
  color: var(--label-2);
  font-size: 13px;
}

@media (max-width: 520px) {
  .plans-scroll { padding: 10px; gap: 8px; }
  .plan-tab.expanded {
    inset: 10px 10px calc(10px + env(safe-area-inset-bottom, 0px)) 10px;
  }
  .tab-trigger { padding: 12px 14px; align-items: flex-start; }
  .tab-body {
    padding: 0 14px 14px 14px;
    max-height: none;
  }
  .route-btn-inline {
    min-width: 34px;
    width: 34px;
    padding: 0;
  }
  .route-btn-inline span:not(.btn-spinner) { display: none; }
}
</style>
