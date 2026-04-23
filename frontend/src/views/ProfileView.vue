<template>
  <section class="view-scroll">
    <article class="panel-card">
      <div class="panel-inner">
        <div class="panel-head">
          <div class="head-copy">
            <h2>个人信息</h2>
            <p>查看当前账户的基础资料与联系信息。</p>
          </div>
          <span class="panel-pill">profile</span>
        </div>

        <div class="info-list">
          <div class="info-item">
            <span>名字</span>
            <strong>{{ app.profileData.name || "未设置" }}</strong>
          </div>
          <div class="info-item">
            <span>账号</span>
            <strong>{{ app.profileData.username || "未登录" }}</strong>
          </div>
          <div class="info-item">
            <span>密码</span>
            <strong>{{ maskedPassword }}</strong>
          </div>
          <div class="info-item">
            <span>邮箱</span>
            <strong>{{ app.profileData.email || "未设置" }}</strong>
          </div>
        </div>

        <div class="action-row">
          <button class="primary" type="button" :disabled="app.loading.profile" @click="app.getProfile">
            {{ app.loading.profile ? "刷新中..." : "刷新资料" }}
          </button>
        </div>
      </div>
    </article>
  </section>
</template>

<script setup>
import { computed, onMounted } from "vue";
import { useAssistantApp } from "../composables/useAssistantApp";

const app = useAssistantApp();
const maskedPassword = computed(() => (app.profileData.password ? "*".repeat(Math.max(6, app.profileData.password.length)) : "未设置"));

onMounted(() => {
  if (app.state.token && !app.profileLoaded.value) {
    app.getProfile();
  }
});
</script>

<style scoped>
.view-scroll { height: 100%; min-height: 0; display: flex; flex-direction: column; padding: 0 18px calc(18px + env(safe-area-inset-bottom, 0px)); }
.panel-card { flex: 1; min-height: 0; padding: 20px; border-radius: 30px; border: 1px solid var(--card-border); background: var(--card-bg); box-shadow: var(--surface-shadow); display: flex; }
.panel-inner { flex: 1; display: flex; flex-direction: column; justify-content: center; max-width: 420px; width: 100%; margin: 0 auto; }
.panel-head { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 24px; align-items: flex-start; }
.head-copy { text-align: center; flex: 1; }
.panel-head h2 { margin: 0; font-size: 22px; letter-spacing: -0.02em; }
.panel-head p { margin: 8px 0 0; color: var(--text-secondary); font-size: 13px; line-height: 1.8; letter-spacing: 0.01em; }
.panel-pill { height: fit-content; padding: 8px 12px; border-radius: 999px; background: rgba(255, 255, 255, 0.78); color: var(--text-secondary); font-size: 11px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }
.info-list { display: grid; gap: 12px; }
.info-item { padding: 14px 16px; border-radius: 18px; background: linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(240, 240, 244, 0.92)); border: 1px solid var(--card-border); text-align: center; }
.info-item span { display: block; color: var(--text-secondary); font-size: 12px; letter-spacing: 0.06em; margin-bottom: 8px; }
.info-item strong { display: block; color: var(--text-main); font-size: 15px; line-height: 1.7; letter-spacing: 0.01em; word-break: break-word; }
.action-row { display: flex; justify-content: center; gap: 10px; margin-top: 18px; }
.primary { padding: 12px 18px; border-radius: 999px; cursor: pointer; min-width: 120px; color: #fff; font-weight: 800; letter-spacing: 0.04em; background: linear-gradient(180deg, var(--button-dark-start), var(--button-dark-end)); }
</style>
