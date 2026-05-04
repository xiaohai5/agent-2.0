<template>
  <div class="app-shell" @click="closeMenu">
    <div class="desktop-halo"></div>

    <div class="device-frame">
      <div class="device-screen">
        <header class="app-header" :class="{ 'is-chat': isChatPage }">
          <div class="status-row">
            <span>9:41</span>
            <span>5G · 82%</span>
          </div>

          <div class="top-bar">
            <button v-if="!isChatPage" class="circle-btn" type="button" aria-label="返回" @click="goBack">‹</button>
            <div v-else class="brand-mark" aria-hidden="true">A</div>

            <div class="title-block">
              <span>{{ app.state.token ? app.state.username || "已登录" : "未登录" }}</span>
              <strong>{{ currentTitle }}</strong>
            </div>

            <div class="menu-anchor" ref="menuRef">
              <button class="avatar-btn" type="button" aria-label="打开用户菜单" @click.stop="toggleMenu">
                <span>{{ avatarText }}</span>
              </button>

              <transition name="menu-fade">
                <UserMenu
                  v-if="app.menuOpen.value"
                  :username="app.state.username"
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

        <IntroModal :open="app.introVisible.value" @confirm="app.acknowledgeIntro" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";
import { RouterView, useRoute, useRouter } from "vue-router";
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

function toggleMenu() {
  app.toggleMenu();
}

function closeMenu(event) {
  if (!app.menuOpen.value) return;
  if (menuRef.value?.contains(event.target)) return;
  app.closeMenu();
}

function handleNavigate(target) {
  app.closeMenu();
  router.push(target);
}

function handleLogout() {
  app.logout();
  router.push("/chat");
}

function goBack() {
  router.push("/chat");
}
</script>

<style scoped>
.app-shell {
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: 18px;
  position: relative;
  overflow: hidden;
  background: #f0f2f5;
}

.desktop-halo {
  display: none;
}

.device-frame {
  width: min(100%, 460px);
  height: min(920px, calc(100dvh - 36px));
  min-height: 680px;
  padding: 10px;
  border-radius: 42px;
  background: #e0e3e8;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1);
  position: relative;
  z-index: 1;
}

.device-frame::before {
  content: "";
  position: absolute;
  top: 10px;
  left: 50%;
  width: 100px;
  height: 24px;
  border-radius: 0 0 14px 14px;
  transform: translateX(-50%);
  background: #1c1c1e;
  z-index: 5;
}

.device-screen {
  height: 100%;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  position: relative;
  border-radius: 34px;
  background: #ffffff;
}

.app-header {
  position: relative;
  z-index: 4;
  padding: 14px 18px 12px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(255, 255, 255, 0.7), rgba(255, 255, 255, 0));
}

.status-row {
  height: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 4px;
  color: #1c1c1e;
  font-size: 12px;
  font-weight: 800;
}

.top-bar {
  margin-top: 12px;
  display: grid;
  grid-template-columns: 44px 1fr 44px;
  align-items: center;
  gap: 12px;
}

.brand-mark,
.circle-btn,
.avatar-btn {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 999px;
  background: #f5f5f7;
  border: 1px solid rgba(0, 0, 0, 0.08);
  color: #1c1c1e;
  font-weight: 900;
}

.brand-mark {
  color: #fff;
  background: #1c1c1e;
}

.circle-btn,
.avatar-btn {
  cursor: pointer;
  transition: transform 0.15s cubic-bezier(0.34, 1.2, 0.64, 1), background 0.15s ease;
}

.circle-btn {
  font-size: 30px;
  line-height: 1;
  color: #1c1c1e;
}

.circle-btn:active,
.avatar-btn:active {
  transform: scale(0.9);
}

.title-block {
  min-width: 0;
  text-align: center;
}

.title-block span {
  display: block;
  color: #8e8e93;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.25;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.title-block strong {
  display: block;
  margin-top: 2px;
  font-size: 20px;
  line-height: 1.2;
  letter-spacing: -0.3px;
  color: #1c1c1e;
}

.menu-anchor {
  position: relative;
}

.page-body {
  flex: 1;
  min-height: 0;
  height: 0;
  position: relative;
  z-index: 1;
}

.menu-fade-enter-active,
.menu-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.menu-fade-enter-from,
.menu-fade-leave-to {
  opacity: 0;
  transform: translateY(-8px) scale(0.98);
}

@media (min-width: 900px) {
  .device-frame {
    width: min(100%, 520px);
  }
}

@media (max-width: 520px) {
  .app-shell {
    display: block;
    padding: 0;
    background: #ffffff;
  }

  .desktop-halo,
  .device-frame::before {
    display: none;
  }

  .device-frame {
    width: 100%;
    height: 100dvh;
    min-height: 0;
    padding: 0;
    border-radius: 0;
    box-shadow: none;
    background: transparent;
  }

  .device-screen {
    border-radius: 0;
    background: #ffffff;
  }

  .app-header {
    padding-top: calc(10px + env(safe-area-inset-top, 0px));
  }
}
</style>
