<template>
  <div class="app-shell" @click="closeMenu">
    <div class="device-frame">
      <div class="device-screen">
        <div class="bg-fog bg-fog-left"></div>
        <div class="bg-fog bg-fog-right"></div>

        <header v-if="isChatPage" class="app-header chat-header">
          <div class="status-row">
            <span>9:41</span>
            <span>5G · 82%</span>
          </div>

          <div class="header-main">
            <div class="brand-block">
              <div class="brand-pill">
                <span class="brand-dot"></span>
                <span>{{ currentTitle }}</span>
              </div>
              <div class="brand-copy">
                <strong>智能助手工作台</strong>
                <p>移动端优先布局，聊天与功能页清晰分区。</p>
              </div>
            </div>

            <div class="menu-anchor" ref="menuRef">
              <button class="avatar-btn" type="button" @click.stop="toggleMenu">
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

        <header v-else class="app-header simple-header">
          <div class="simple-bar">
            <button class="back-btn" type="button" @click="goBack">←</button>
            <span class="simple-title">{{ currentTitle }}</span>
            <div class="simple-space"></div>
          </div>
        </header>

        <main class="page-body" :class="{ 'page-body-chat': isChatPage, 'page-body-simple': !isChatPage }">
          <RouterView />
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

const currentTitle = computed(() => route.meta.title || "聊天");
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
  if (window.history.length > 1) {
    router.back();
    return;
  }
  router.push("/chat");
}
</script>

<style scoped>
.app-shell { min-height: 100dvh; padding: 10px; }
.device-frame { width: min(100%, 460px); min-height: calc(100dvh - 20px); margin: 0 auto; padding: 10px; border-radius: 38px; background: linear-gradient(180deg, #fbfbfc, #e7e7ea); border: 1px solid rgba(255, 255, 255, 0.95); box-shadow: 0 34px 90px rgba(20, 20, 24, 0.12); position: relative; }
.device-frame::before { content: ""; position: absolute; top: 8px; left: 50%; transform: translateX(-50%); width: 124px; height: 24px; border-radius: 0 0 18px 18px; background: #dfdfe4; }
.device-screen { min-height: calc(100dvh - 40px); height: calc(100dvh - 40px); border-radius: 30px; overflow: hidden; position: relative; display: flex; flex-direction: column; border: 1px solid rgba(255, 255, 255, 0.96); background: radial-gradient(circle at top left, rgba(255, 255, 255, 0.96), transparent 30%), linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(243, 243, 246, 0.96) 52%, rgba(235, 235, 239, 0.98)); }
.bg-fog { position: absolute; border-radius: 999px; pointer-events: none; }
.bg-fog-left { top: 118px; left: -26px; width: 148px; height: 148px; background: radial-gradient(circle, rgba(255, 255, 255, 0.88), transparent 72%); }
.bg-fog-right { top: 184px; right: -34px; width: 164px; height: 164px; background: radial-gradient(circle, rgba(216, 216, 222, 0.72), transparent 74%); }
.app-header { position: relative; z-index: 2; }
.chat-header { padding: 14px 18px 10px; }
.simple-header { padding: 14px 18px 6px; }
.status-row { display: flex; justify-content: space-between; align-items: center; color: var(--text-secondary); font-size: 13px; font-weight: 700; letter-spacing: 0.04em; margin-bottom: 10px; }
.header-main { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.brand-pill { display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px; border-radius: 999px; background: rgba(255, 255, 255, 0.72); border: 1px solid var(--card-border); box-shadow: var(--soft-shadow); color: var(--text-secondary); font-size: 11px; font-weight: 700; letter-spacing: 0.06em; }
.brand-dot { width: 7px; height: 7px; border-radius: 999px; background: #7f7f88; }
.brand-copy { margin-top: 12px; }
.brand-copy strong { display: block; font-size: 24px; font-weight: 800; letter-spacing: -0.02em; }
.brand-copy p { margin: 8px 0 0; color: var(--text-secondary); font-size: 13px; line-height: 1.8; letter-spacing: 0.01em; }
.menu-anchor { position: relative; flex: 0 0 auto; }
.avatar-btn, .back-btn { width: 46px; height: 46px; border-radius: 999px; border: 1px solid var(--card-border); background: linear-gradient(180deg, rgba(255, 255, 255, 0.95), rgba(238, 238, 242, 0.92)); box-shadow: var(--soft-shadow); color: #55555f; font-size: 16px; font-weight: 800; cursor: pointer; }
.simple-bar { display: grid; grid-template-columns: 46px 1fr 46px; align-items: center; gap: 10px; }
.simple-title { text-align: center; font-size: 16px; font-weight: 800; letter-spacing: 0.02em; color: var(--text-main); }
.simple-space { width: 46px; height: 46px; }
.page-body { flex: 1; min-height: 0; position: relative; z-index: 1; }
.page-body-chat { padding-top: 0; }
.page-body-simple { padding-top: 6px; }
.menu-fade-enter-active, .menu-fade-leave-active { transition: opacity 0.18s ease, transform 0.18s ease; }
.menu-fade-enter-from, .menu-fade-leave-to { opacity: 0; transform: translateY(-8px); }
@media (max-width: 480px) {
  .app-shell { padding: 0; }
  .device-frame { width: 100%; min-height: 100dvh; border-radius: 0; padding: 0; border: 0; }
  .device-frame::before { display: none; }
  .device-screen { height: 100dvh; min-height: 100dvh; border-radius: 0; border: 0; }
  .chat-header,
  .simple-header { padding-top: calc(14px + env(safe-area-inset-top, 0px)); }
}
</style>
