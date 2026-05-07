<template>
  <section class="ios-page ios-page-stack ios-scroll">
    <PagePanel title="个人资料" description="当前账户的基础资料与本地保存的登录信息。" eyebrow="Profile">
      <div class="profile-hero">
        <button class="profile-avatar" type="button" aria-label="Change avatar" @click="openAvatarPicker">
          <img v-if="app.profileData.avatarUrl" :src="app.profileData.avatarUrl" alt="" />
          <span v-else>{{ avatarText }}</span>
        </button>
        <input ref="avatarInputRef" class="avatar-input" type="file" accept="image/*" @change="handleAvatarChange" />
        <div>
          <strong>{{ app.profileData.name || app.profileData.username || "未登录用户" }}</strong>
          <span>{{ app.profileData.email || "暂无邮箱信息" }}</span>
        </div>
      </div>

      <div class="ios-list">
        <div class="ios-list-row"><div class="ios-list-copy"><span>名字</span><strong>{{ app.profileData.name || "未设置" }}</strong></div></div>
        <div class="ios-list-row"><div class="ios-list-copy"><span>账号</span><strong>{{ app.profileData.username || "未登录" }}</strong></div></div>
        <div class="ios-list-row"><div class="ios-list-copy"><span>密码</span><strong>{{ maskedPassword }}</strong></div></div>
        <div class="ios-list-row"><div class="ios-list-copy"><span>邮箱</span><strong>{{ app.profileData.email || "未设置" }}</strong></div></div>
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
import { computed, onMounted, ref } from "vue";
import IosButton from "../components/IosButton.vue";
import PagePanel from "../components/PagePanel.vue";
import { useAssistantApp } from "../composables/useAssistantApp";

const app = useAssistantApp();
const avatarInputRef = ref(null);
const maskedPassword = computed(() => (app.profileData.password ? "•".repeat(Math.max(6, app.profileData.password.length)) : "未设置"));
const avatarText = computed(() => (app.profileData.username ? app.profileData.username.slice(0, 1).toUpperCase() : "我"));

function openAvatarPicker() {
  avatarInputRef.value?.click();
}

async function handleAvatarChange(event) {
  const file = event.target.files?.[0];
  if (file) await app.setUserAvatarFromFile(file);
  event.target.value = "";
}

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
  padding: 16px;
  margin-bottom: 18px;
  border-radius: var(--r-lg);
  background: var(--bg-2);
}

.profile-avatar {
  width: 64px;
  height: 64px;
  flex: 0 0 64px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #ffffff;
  background: linear-gradient(135deg, #007aff, #5856d6);
  border: none;
  padding: 0;
  cursor: pointer;
  overflow: hidden;
  font-size: 24px;
  font-weight: 700;
  box-shadow: 0 4px 12px rgba(0, 122, 255, 0.2);
  transition: transform 0.18s var(--ease-spring), box-shadow 0.18s ease;
}
.profile-avatar:active { transform: scale(0.96); }
.profile-avatar img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}
.avatar-input { display: none; }

.profile-hero strong,
.profile-hero span { display: block; word-break: break-word; }
.profile-hero strong { font-size: 18px; font-weight: 600; line-height: 1.35; color: var(--label); }
.profile-hero span { margin-top: 4px; color: var(--label-2); font-size: 13px; }
.action-gap { margin-top: 18px; }
</style>
