<template>
  <div class="menu-panel" @click.stop>
    <button type="button" class="menu-user menu-user-btn" @click="$emit('navigate', username ? '/profile' : '/account')">
      <strong>{{ username || "未登录" }}</strong>
      <span>{{ username ? "点击前往个人信息" : "点击前往账户入口" }}</span>
    </button>
    <button type="button" @click="$emit('navigate', '/password')"><span>修改密码</span><span>→</span></button>
    <button type="button" @click="$emit('navigate', '/documents')"><span>文档中心</span><span>→</span></button>
    <button type="button" @click="$emit('logout')"><span>退出登录</span><span>→</span></button>
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
.menu-panel { position: absolute; top: 56px; right: 0; width: 236px; padding: 10px; border-radius: 24px; border: 1px solid var(--card-border); background: rgba(255, 255, 255, 0.84); backdrop-filter: blur(22px); box-shadow: 0 30px 80px rgba(17, 17, 22, 0.14); z-index: 20; }
.menu-user { padding: 10px 12px; border-radius: 18px; background: linear-gradient(180deg, rgba(255, 255, 255, 0.84), rgba(240, 240, 244, 0.92)); margin-bottom: 8px; }
.menu-user-btn { display: block; text-align: left; }
.menu-user strong { display: block; font-size: 14px; }
.menu-user span { display: block; margin-top: 4px; color: var(--text-secondary); font-size: 12px; }
button { width: 100%; display: flex; justify-content: space-between; align-items: center; padding: 12px 14px; border-radius: 16px; background: transparent; color: var(--text-main); font-weight: 700; text-align: left; cursor: pointer; }
button:hover { background: rgba(239, 239, 243, 0.9); }
</style>
