<template>
  <div class="menu-panel glass-card" @click.stop>
    <button type="button" class="menu-user" @click="$emit('navigate', username ? '/profile' : '/account')">
      <span class="menu-avatar">
        <img v-if="avatarUrl" :src="avatarUrl" alt="" />
        <span v-else>{{ username ? username.slice(0, 1).toUpperCase() : "我" }}</span>
      </span>
      <span class="menu-copy">
        <strong>{{ username || "未登录" }}</strong>
        <small>{{ username ? "查看个人资料" : "登录后使用完整功能" }}</small>
      </span>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M9 18l6-6-6-6"/></svg>
    </button>

    <div class="menu-divider"></div>

    <div class="menu-list">
      <button type="button" @click="$emit('navigate', '/password')">
        <span>修改密码</span>
      </button>
      <button type="button" @click="$emit('navigate', '/documents')">
        <span>文档管理</span>
      </button>
    </div>

    <div class="menu-divider"></div>

    <div class="menu-list">
      <button type="button" class="menu-logout" @click="$emit('logout')">
        <span>退出登录</span>
      </button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  username: { type: String, default: "" },
  avatarUrl: { type: String, default: "" },
});
defineEmits(["navigate", "logout"]);
</script>

<style scoped>
.menu-panel {
  position: absolute;
  top: 52px;
  right: 0;
  width: 260px;
  padding: 4px;
  border-radius: 16px;
  z-index: 20;
}

.menu-user {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 8px;
  border-radius: 12px;
  background: transparent;
  color: var(--label);
  text-align: left;
  cursor: pointer;
  border: none;
  transition: background 0.15s ease;
}
.menu-user:active { background: var(--fill-4); }
.menu-user svg { color: var(--label-3); flex: 0 0 auto; }

.menu-avatar {
  width: 40px;
  height: 40px;
  flex: 0 0 40px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  background: linear-gradient(135deg, #007aff, #5856d6);
  font-weight: 700;
  font-size: 15px;
  overflow: hidden;
}
.menu-avatar img {
  width: 100%;
  height: 100%;
  display: block;
  object-fit: cover;
}

.menu-copy { min-width: 0; flex: 1; }
.menu-copy strong,
.menu-copy small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.menu-copy strong { font-size: 15px; font-weight: 600; color: var(--label); }
.menu-copy small { margin-top: 2px; color: var(--label-2); font-size: 12px; }

.menu-divider {
  height: 1px;
  margin: 4px 8px;
  background: var(--hairline);
}

.menu-list button {
  width: 100%;
  min-height: 42px;
  display: flex;
  align-items: center;
  padding: 0 10px;
  border-radius: 10px;
  background: transparent;
  color: var(--label);
  font-size: 15px;
  font-weight: 400;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease;
  border: none;
}
.menu-list button:active { background: var(--fill-4); }
.menu-logout { color: var(--red) !important; }
</style>
