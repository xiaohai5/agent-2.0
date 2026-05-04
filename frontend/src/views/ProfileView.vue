<template>
  <section class="ios-page ios-page-stack ios-scroll">
    <PagePanel title="个人资料" description="当前账户的基础资料与本地保存的登录信息。" eyebrow="Profile">
      <div class="profile-hero">
        <div class="profile-avatar">{{ avatarText }}</div>
        <div>
          <strong>{{ app.profileData.name || app.profileData.username || "未登录用户" }}</strong>
          <span>{{ app.profileData.email || "暂无邮箱信息" }}</span>
        </div>
      </div>

      <div class="ios-list">
        <div class="ios-list-row">
          <div class="ios-list-copy"><span>名字</span><strong>{{ app.profileData.name || "未设置" }}</strong></div>
        </div>
        <div class="ios-list-row">
          <div class="ios-list-copy"><span>账号</span><strong>{{ app.profileData.username || "未登录" }}</strong></div>
        </div>
        <div class="ios-list-row">
          <div class="ios-list-copy"><span>密码</span><strong>{{ maskedPassword }}</strong></div>
        </div>
        <div class="ios-list-row">
          <div class="ios-list-copy"><span>邮箱</span><strong>{{ app.profileData.email || "未设置" }}</strong></div>
        </div>
      </div>

      <div class="ios-action-row action-gap">
        <IosButton :disabled="app.loading.profile" @click="app.getProfile">
          {{ app.loading.profile ? "刷新中..." : "刷新资料" }}
        </IosButton>
      </div>
    </PagePanel>
  </section>
</template>

<script setup>
import { computed, onMounted } from "vue";
import IosButton from "../components/IosButton.vue";
import PagePanel from "../components/PagePanel.vue";
import { useAssistantApp } from "../composables/useAssistantApp";

const app = useAssistantApp();
const maskedPassword = computed(() => (app.profileData.password ? "•".repeat(Math.max(6, app.profileData.password.length)) : "未设置"));
const avatarText = computed(() => (app.profileData.username ? app.profileData.username.slice(0, 1).toUpperCase() : "我"));

onMounted(() => {
  if (app.state.token && !app.profileLoaded.value) {
    app.getProfile();
  }
});
</script>

<style scoped>
.profile-hero {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px;
  margin-bottom: 14px;
  border-radius: 14px;
  background: #f9fafb;
  border: 1px solid rgba(0, 0, 0, 0.04);
}

.profile-avatar {
  width: 56px;
  height: 56px;
  flex: 0 0 56px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  background: #6366f1;
  font-size: 22px;
  font-weight: 700;
}

.profile-hero strong,
.profile-hero span {
  display: block;
  word-break: break-word;
}

.profile-hero strong {
  font-size: 18px;
  line-height: 1.35;
  color: #1f2937;
}

.profile-hero span {
  margin-top: 4px;
  color: #6b7280;
  font-size: 13px;
}

.action-gap {
  margin-top: 16px;
}
</style>
