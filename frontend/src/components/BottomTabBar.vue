<template>
  <nav class="tab-bar glass-bar" aria-label="主导航">
    <router-link to="/chat" class="tab-item" :class="{ active: $route.name === 'chat' }">
      <svg class="tab-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
      <span class="tab-label">交流</span>
      <span class="tab-dot"></span>
    </router-link>

    <router-link to="/map" class="tab-item" :class="{ active: $route.name === 'map' }">
      <svg class="tab-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <circle cx="12" cy="10" r="3"/>
        <path d="M12 2a8 8 0 0 0-8 8c0 5.4 8 12 8 12s8-6.6 8-12a8 8 0 0 0-8-8z"/>
      </svg>
      <span class="tab-label">导航</span>
      <span class="tab-dot"></span>
    </router-link>

    <router-link to="/plans" class="tab-item" :class="{ active: $route.name === 'plans' }">
      <svg class="tab-icon" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
        <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
        <line x1="16" y1="2" x2="16" y2="6"/>
        <line x1="8" y1="2" x2="8" y2="6"/>
        <line x1="3" y1="10" x2="21" y2="10"/>
        <path d="M8 14h.01M12 14h.01M16 14h.01"/>
      </svg>
      <span class="tab-label">计划</span>
      <span class="tab-dot"></span>
    </router-link>
  </nav>
</template>

<script setup>
import { useRoute } from "vue-router";
const $route = useRoute();
</script>

<style scoped>
.tab-bar {
  display: flex;
  justify-content: space-around;
  align-items: flex-end;
  padding: 6px 8px calc(6px + env(safe-area-inset-bottom, 0px));
  border-top: 0.5px solid var(--hairline);
  flex-shrink: 0;
  position: relative;
  z-index: 4;
}

.tab-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 4px 12px;
  min-width: 64px;
  text-decoration: none;
  color: var(--label-3);
  position: relative;
  transition: color 0.25s var(--ease-ease);
  -webkit-tap-highlight-color: transparent;
}

.tab-item.active {
  color: var(--ocean);
}

.tab-item:active { transform: scale(0.94); }

.tab-icon {
  transition: transform 0.3s var(--ease-spring);
}
.tab-item.active .tab-icon {
  transform: translateY(-1px);
}

.tab-label {
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.2px;
  line-height: 1;
}

.tab-dot {
  position: absolute;
  top: 2px;
  width: 4px; height: 4px;
  border-radius: 50%;
  background: var(--sky);
  opacity: 0;
  transform: scale(0);
  transition: opacity 0.25s ease, transform 0.3s var(--ease-spring);
}
.tab-item.active .tab-dot {
  opacity: 1;
  transform: scale(1);
}
</style>
