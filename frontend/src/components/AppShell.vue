<template>
  <div class="app-shell" @click="closeMenu">
    <div class="device-frame">
      <div class="device-screen">
        <header class="app-header glass-bar">
          <div class="top-bar">
            <button v-if="!isChatPage" class="nav-btn back-btn" type="button" aria-label="返回" @click="goBack">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
            </button>
            <div v-else class="header-spacer"></div>

            <div class="title-block">
              <strong>{{ currentTitle }}</strong>
            </div>

            <div class="menu-anchor" ref="menuRef">
              <button class="avatar-btn" type="button" aria-label="打开用户菜单" @click.stop="toggleMenu">
                <img v-if="app.profileData.avatarUrl" :src="app.profileData.avatarUrl" alt="" />
                <span v-else>{{ avatarText }}</span>
              </button>

              <transition name="menu-fade">
                <UserMenu
                  v-if="app.menuOpen.value"
                  :username="app.state.username"
                  :avatar-url="app.profileData.avatarUrl"
                  @navigate="handleNavigate"
                  @logout="handleLogout"
                />
              </transition>
            </div>
          </div>
        </header>

        <main class="page-body">
          <RouterView v-slot="{ Component }">
            <transition name="slide-page" mode="out-in">
              <component :is="Component" />
            </transition>
          </RouterView>
        </main>

        <BottomTabBar v-if="showTabBar" />

        <IntroModal :open="app.introVisible.value" @confirm="app.acknowledgeIntro" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";
import BottomTabBar from "./BottomTabBar.vue";
import IntroModal from "./IntroModal.vue";
import UserMenu from "./UserMenu.vue";
import { useAssistantApp } from "../composables/useAssistantApp";

const app = useAssistantApp();
const route = useRoute();
const router = useRouter();
const menuRef = ref(null);

const currentTitle = computed(() => route.meta.title || "对话");
const avatarText = computed(() => (app.state.username ? app.state.username.slice(0, 1).toUpperCase() : "我"));
const isChatPage = computed(() => route.name === "chat");
const showTabBar = computed(() => route.meta.showTabBar !== false);

function toggleMenu() { app.toggleMenu(); }
function closeMenu(event) {
  if (!app.menuOpen.value) return;
  if (menuRef.value?.contains(event.target)) return;
  app.closeMenu();
}
function handleNavigate(target) { app.closeMenu(); router.push(target); }
function handleLogout() { app.logout(); router.push("/chat"); }
function goBack() { router.push("/chat"); }
</script>

<style scoped>
.app-shell {
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: 16px;
  position: relative;
  overflow: hidden;
  background: linear-gradient(160deg, #e3eaf3, #e8eef7, #eaf1f9);
}

/* ── Device Frame ── */
.device-frame {
  width: min(100%, 460px);
  height: min(920px, calc(100dvh - 32px));
  min-height: 680px;
  border-radius: 44px;
  background: linear-gradient(160deg, #d3dce8, #c8d3e3, #d0d9e5);
  box-shadow:
    0 12px 48px rgba(61, 48, 85, 0.15),
    inset 0 1px 0 rgba(255, 255, 255, 0.5),
    0 0 60px rgba(126, 200, 227, 0.12);
  position: relative;
  z-index: 1;
  overflow: hidden;
}

.device-screen {
  height: 100%;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
  border-radius: 36px;
  background: linear-gradient(175deg, #fdfeff 0%, #f8fafd 100%);
}

/* ── Header ── */
.app-header {
  position: relative;
  z-index: 4;
  padding: 6px 14px;
  flex-shrink: 0;
}

/* ── Top Bar ── */
.top-bar {
  display: grid;
  grid-template-columns: 40px 1fr 40px;
  align-items: center;
  gap: 10px;
  min-height: 44px;
}

.header-spacer { width: 40px; height: 40px; }

.nav-btn,
.avatar-btn {
  width: 40px; height: 40px;
  display: grid; place-items: center;
  border-radius: 50%;
  border: none;
  color: var(--label);
  font-weight: 700;
}

.nav-btn {
  background: var(--fill-4);
  cursor: pointer;
  transition: transform 0.2s var(--ease-spring), background 0.15s ease;
}
.nav-btn:active { transform: scale(0.9); background: var(--fill-3); }
.back-btn svg { display: block; }

.avatar-btn {
  background: linear-gradient(135deg, rgba(126,200,227,0.25), rgba(74,127,191,0.15));
  cursor: pointer;
  overflow: hidden;
  transition: transform 0.2s var(--ease-spring), box-shadow 0.2s ease;
  font-size: 13px;
  font-weight: 600;
  color: var(--label);
}
.avatar-btn img { width: 100%; height: 100%; display: block; object-fit: cover; }
.avatar-btn:active { transform: scale(0.9); box-shadow: 0 0 14px rgba(126,200,227,0.3); }

/* ── Title ── */
.title-block { min-width: 0; text-align: center; }
.title-block strong {
  display: block;
  font-size: 17px;
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.3px;
  color: var(--label);
}

/* ── Menu ── */
.menu-anchor { position: relative; }

.page-body { flex: 1; min-height: 0; height: 0; position: relative; z-index: 1; }

.menu-fade-enter-active,
.menu-fade-leave-active {
  transition: opacity 0.2s var(--ease-ease), transform 0.25s var(--ease-spring);
}
.menu-fade-enter-from,
.menu-fade-leave-to { opacity: 0; transform: translateY(-8px) scale(0.95); }

@media (min-width: 900px) { .device-frame { width: min(100%, 520px); } }

@media (max-width: 520px) {
  .app-shell { display: block; padding: 0; background: #f8fafd; }
  .device-frame {
    width: 100%; height: 100dvh; min-height: 0;
    border-radius: 0; box-shadow: none; background: transparent;
  }
  .device-screen { border-radius: 0; }
  .app-header { padding-top: calc(4px + env(safe-area-inset-top, 0px)); }
}
</style>
