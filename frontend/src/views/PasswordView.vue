<template>
  <section class="ios-page ios-page-stack ios-scroll">
    <PagePanel title="安全设置" description="更新登录密码，并调整本轮问答的检索数量。" eyebrow="Security">
      <form class="form-stack" @submit.prevent="app.changePassword">
        <div class="field-grid">
          <IosField label="用户名">
            <input v-model="app.pwd.username" placeholder="请输入用户名" />
          </IosField>
          <IosField label="Top K">
            <input v-model="app.topK.value" type="number" min="1" max="10" />
          </IosField>
        </div>

        <IosField label="旧密码">
          <input v-model="app.pwd.old_password" type="password" autocomplete="current-password" placeholder="请输入当前密码" />
        </IosField>
        <IosField label="新密码">
          <input v-model="app.pwd.new_password" type="password" autocomplete="new-password" placeholder="请输入新密码" />
        </IosField>
        <IosField label="确认新密码">
          <input v-model="app.pwd.confirm_password" type="password" autocomplete="new-password" placeholder="再次输入新密码" />
        </IosField>

        <IosButton class="submit-btn" :disabled="app.loading.password" type="submit">
          {{ app.loading.password ? "提交中..." : "提交修改" }}
        </IosButton>

        <div class="ios-status">{{ app.authStatus.value }}</div>
      </form>
    </PagePanel>
  </section>
</template>

<script setup>
import { onMounted } from "vue";
import IosButton from "../components/IosButton.vue";
import IosField from "../components/IosField.vue";
import PagePanel from "../components/PagePanel.vue";
import { useAssistantApp } from "../composables/useAssistantApp";

const app = useAssistantApp();

onMounted(() => {
  if (app.state.username && !app.pwd.username) {
    app.pwd.username = app.state.username;
  }
});
</script>

<style scoped>
.form-stack {
  display: grid;
  gap: 13px;
}

.field-grid {
  display: grid;
  grid-template-columns: 1fr 110px;
  gap: 12px;
}

.submit-btn {
  width: 100%;
}

@media (max-width: 420px) {
  .field-grid {
    grid-template-columns: 1fr;
  }
}
</style>
