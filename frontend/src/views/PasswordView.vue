<template>
  <section class="view-scroll">
    <article class="panel-card">
      <div class="panel-head">
        <div class="head-copy">
          <h2>修改密码</h2>
          <p>更新登录密码，并同步调整本轮问答的检索数量。</p>
        </div>
        <span class="panel-pill">security</span>
      </div>

      <div class="grid-two">
        <label class="field">
          <span>用户名</span>
          <input v-model="app.pwd.username" placeholder="请输入用户名" />
        </label>
        <label class="field">
          <span>Top K</span>
          <input v-model="app.topK.value" type="number" min="1" max="10" />
        </label>
      </div>

      <label class="field">
        <span>旧密码</span>
        <input v-model="app.pwd.old_password" type="password" placeholder="请输入当前密码" />
      </label>
      <label class="field">
        <span>新密码</span>
        <input v-model="app.pwd.new_password" type="password" placeholder="请输入新密码" />
      </label>
      <label class="field">
        <span>确认新密码</span>
        <input v-model="app.pwd.confirm_password" type="password" placeholder="请再次输入新密码" />
      </label>

      <div class="action-row">
        <button class="primary" type="button" :disabled="app.loading.password" @click="app.changePassword">
          {{ app.loading.password ? "提交中..." : "提交修改" }}
        </button>
      </div>

      <div class="status-box">{{ app.authStatus.value }}</div>
    </article>
  </section>
</template>

<script setup>
import { onMounted } from "vue";
import { useAssistantApp } from "../composables/useAssistantApp";

const app = useAssistantApp();

onMounted(() => {
  if (app.state.username && !app.pwd.username) {
    app.pwd.username = app.state.username;
  }
});
</script>

<style scoped>
.view-scroll { height: 100%; min-height: 0; display: flex; flex-direction: column; padding: 0 18px calc(18px + env(safe-area-inset-bottom, 0px)); }
.panel-card { flex: 1; min-height: 0; padding: 20px; border-radius: 30px; border: 1px solid var(--card-border); background: var(--card-bg); box-shadow: var(--surface-shadow); display: flex; flex-direction: column; justify-content: center; }
.panel-head { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 18px; align-items: flex-start; }
.head-copy { flex: 1; }
.panel-head h2 { margin: 0; font-size: 22px; letter-spacing: -0.02em; }
.panel-head p { margin: 8px 0 0; color: var(--text-secondary); font-size: 13px; line-height: 1.8; letter-spacing: 0.01em; }
.panel-pill { height: fit-content; padding: 8px 12px; border-radius: 999px; background: rgba(255, 255, 255, 0.78); color: var(--text-secondary); font-size: 11px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }
.grid-two { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 10px; }
.field { display: grid; gap: 8px; color: var(--text-secondary); font-size: 12px; font-weight: 700; letter-spacing: 0.04em; margin-bottom: 10px; }
.field input { width: 100%; padding: 14px 16px; border-radius: 20px; border: 1px solid rgba(200, 200, 207, 0.72); background: rgba(255, 255, 255, 0.92); color: var(--text-main); outline: none; line-height: 1.6; }
.action-row { display: flex; gap: 10px; margin-top: 14px; }
.primary { padding: 12px 18px; border-radius: 999px; color: #fff; font-weight: 800; letter-spacing: 0.04em; background: linear-gradient(180deg, var(--button-dark-start), var(--button-dark-end)); cursor: pointer; }
.status-box { margin-top: 14px; padding: 14px 16px; border-radius: 20px; background: rgba(255, 255, 255, 0.9); border: 1px solid var(--card-border); color: var(--text-secondary); font-size: 14px; line-height: 1.8; white-space: pre-wrap; }
@media (max-width: 420px) { .grid-two { grid-template-columns: 1fr; } }
</style>
