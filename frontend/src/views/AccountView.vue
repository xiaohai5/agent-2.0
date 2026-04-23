<template>
  <section class="auth-page">
    <article class="auth-card">
      <div class="auth-card__inner">
        <div class="auth-card__head">
          <div class="auth-card__copy">
            <h2>账户入口</h2>
            <p>请输入用户名和密码后继续使用。</p>
          </div>
          <span class="auth-pill">auth</span>
        </div>

        <div class="auth-form">
          <label class="auth-field">
            <span>用户名</span>
            <input v-model="app.login.username" placeholder="请输入用户名" />
          </label>

          <label class="auth-field">
            <span>密码</span>
            <input v-model="app.login.password" type="password" placeholder="请输入密码" />
          </label>

          <div class="auth-actions">
            <button class="auth-button auth-button--primary" type="button" :disabled="app.loading.auth" @click="submitLogin">
              {{ app.loading.auth ? "登录中..." : "登录" }}
            </button>
            <button class="auth-button auth-button--ghost" type="button" @click="router.push('/register')">注册</button>
          </div>

          <div class="auth-status">{{ app.authStatus.value }}</div>
        </div>
      </div>
    </article>
  </section>
</template>

<script setup>
import { useRouter } from "vue-router";
import { useAssistantApp } from "../composables/useAssistantApp";

const app = useAssistantApp();
const router = useRouter();

async function submitLogin() {
  await app.doLogin();
  if (app.state.token) {
    router.push({ name: "chat" });
  }
}
</script>

<style scoped>
</style>
