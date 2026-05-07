<template>
  <section class="ios-page ios-page-stack ios-scroll">
    <PagePanel title="安全设置" description="更新你的登录密码。" eyebrow="Security">
      <form class="form-stack" @submit.prevent="handleChangePassword">
        <IosField label="用户名">
          <input v-model="app.pwd.username" placeholder="请输入用户名" />
        </IosField>

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

        <p v-if="passwordMsg" class="form-msg" :class="{ 'is-error': passwordError }">{{ passwordMsg }}</p>
      </form>
    </PagePanel>
  </section>
</template>

<script setup>
import { onMounted, ref } from "vue";
import IosButton from "../components/IosButton.vue";
import IosField from "../components/IosField.vue";
import PagePanel from "../components/PagePanel.vue";
import { useAssistantApp } from "../composables/useAssistantApp";

const app = useAssistantApp();
const passwordMsg = ref("");
const passwordError = ref(false);

async function handleChangePassword() {
  passwordMsg.value = "";
  passwordError.value = false;
  await app.changePassword();
  if (app.authStatus.value === "密码修改成功") {
    passwordMsg.value = "密码修改成功";
  } else if (app.authStatus.value) {
    passwordMsg.value = app.authStatus.value;
    passwordError.value = true;
  }
}

onMounted(() => {
  if (app.state.username && !app.pwd.username) {
    app.pwd.username = app.state.username;
  }
});
</script>

<style scoped>
.form-stack { display: grid; gap: 15px; }
.submit-btn { width: 100%; }
.form-msg {
  margin: 0;
  text-align: center;
  font-size: 13px;
  color: var(--green);
}
.form-msg.is-error { color: var(--red); }
</style>
