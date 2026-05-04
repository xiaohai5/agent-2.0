<template>
  <div class="menu-panel" @click.stop>
    <button type="button" class="menu-user" @click="$emit('navigate', username ? '/profile' : '/account')">
      <span class="menu-avatar">{{ username ? username.slice(0, 1).toUpperCase() : "我" }}</span>
      <span class="menu-copy">
        <strong>{{ username || "未登录" }}</strong>
        <small>{{ username ? "查看个人资料" : "前往登录入口" }}</small>
      </span>
    </button>

    <div class="menu-list">
      <button type="button" @click="$emit('navigate', '/password')"><span>安全设置</span><i>›</i></button>
      <button type="button" @click="$emit('navigate', '/documents')"><span>文档中心</span><i>›</i></button>
      <button type="button" @click="$emit('logout')"><span>退出登录</span><i>›</i></button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  username: {
    type: String,
    default: "",
  },
});

defineEmits(["navigate", "logout"]);
</script>

<style scoped>
.menu-panel {
  position: absolute;
  top: 54px;
  right: 0;
  width: 248px;
  padding: 8px;
  border-radius: 18px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  background: #fff;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.12);
  z-index: 20;
}

.menu-user {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border-radius: 14px;
  background: #f5f5f7;
  color: #1c1c1e;
  text-align: left;
  cursor: pointer;
  border: none;
  transition: background 0.15s ease;
}

.menu-user:active {
  background: #e5e5ea;
}

.menu-avatar {
  width: 36px;
  height: 36px;
  flex: 0 0 36px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  color: #fff;
  background: #1c1c1e;
  font-weight: 700;
  font-size: 14px;
}

.menu-copy {
  min-width: 0;
}

.menu-copy strong,
.menu-copy small {
  display: block;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.menu-copy strong {
  font-size: 14px;
  color: #1c1c1e;
}

.menu-copy small {
  margin-top: 2px;
  color: #8e8e93;
  font-size: 12px;
}

.menu-list {
  margin-top: 4px;
  overflow: hidden;
  border-radius: 14px;
}

.menu-list button {
  width: 100%;
  min-height: 42px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 12px;
  background: transparent;
  color: #1c1c1e;
  font-weight: 600;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease;
  border: none;
}

.menu-list button:active {
  background: #f5f5f7;
}

.menu-list i {
  color: #c7c7cc;
  font-size: 20px;
  font-style: normal;
}
</style>
