<template>
  <section class="ios-page auth-view ios-scroll">
    <PagePanel title="欢迎回来" description="登录后即可上传文档、管理知识库并继续你的对话。" eyebrow="Account">
      <form class="form-stack" @submit.prevent="submitLogin">
        <IosField label="用户名">
          <input v-model="app.login.username" autocomplete="username" placeholder="请输入用户名" />
        </IosField>

        <IosField label="密码">
          <input v-model="app.login.password" autocomplete="current-password" type="password" placeholder="请输入密码" />
        </IosField>

        <div class="ios-action-row">
          <IosButton class="grow" :disabled="app.loading.auth" type="submit">
            {{ app.loading.auth ? "登录中..." : "登录" }}
          </IosButton>
          <IosButton variant="secondary" @click="router.push('/register')">注册</IosButton>
        </div>

        <div class="ios-status">{{ app.authStatus.value }}</div>
      </form>
    </PagePanel>
  </section>
</template>

<script setup>
import { useRouter } from "vue-router";
import IosButton from "../components/IosButton.vue";
import IosField from "../components/IosField.vue";
import PagePanel from "../components/PagePanel.vue";
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
.auth-view {
  display: grid;
  align-items: center;
}

.form-stack {
  display: grid;
  gap: 14px;
}

.grow {
  flex: 1;
}
</style>
