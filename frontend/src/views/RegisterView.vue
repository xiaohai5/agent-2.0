<template>
  <section class="auth-page">
    <article class="auth-card">
      <div class="auth-card__inner">
        <div class="auth-card__head">
          <div class="auth-card__copy">
            <h2>注册账号</h2>
            <p>填写基础信息后即可创建新账号。</p>
          </div>
          <span class="auth-pill">register</span>
        </div>

        <div class="auth-form">
          <label class="auth-field">
            <span>注册用户名</span>
            <input v-model="app.register.username" placeholder="请输入注册用户名" />
          </label>

          <label class="auth-field">
            <span>注册邮箱</span>
            <input v-model="app.register.email" type="email" placeholder="请输入邮箱地址" />
          </label>

          <label class="auth-field">
            <span>注册密码</span>
            <input v-model="app.register.password" type="password" placeholder="请设置登录密码" />
          </label>

          <div class="auth-actions">
            <button class="auth-button auth-button--primary" type="button" :disabled="app.loading.auth" @click="submitRegister">
              {{ app.loading.auth ? "提交中..." : "注册" }}
            </button>
            <button class="auth-button auth-button--ghost" type="button" @click="router.push('/account')">返回登录</button>
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

async function submitRegister() {
  await app.doRegister();
  if (app.state.token) {
    router.push({ name: "chat" });
  }
}
</script>

<style scoped>
</style>
