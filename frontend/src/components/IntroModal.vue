<template>
  <teleport to="body">
    <transition name="sheet">
      <div v-if="open" class="mask" @click.self="$emit('confirm')">
        <section class="sheet-card" role="dialog" aria-modal="true" aria-labelledby="intro-title">
          <div class="grabber"></div>
          <span class="ios-pill">首次使用</span>
          <h2 id="intro-title">欢迎进入出行文档助手</h2>
          <p>右上角头像可以打开账户菜单；聊天、文档、个人资料通过底部标签快速切换。</p>
          <p>确认后不会再次自动弹出，你仍然可以正常登录、上传文档并继续对话。</p>
          <div class="actions">
            <button class="ghost" type="button" @click="$emit('confirm')">稍后再看</button>
            <button class="primary" type="button" @click="$emit('confirm')">开始使用</button>
          </div>
        </section>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
defineProps({ open: { type: Boolean, default: false } });
defineEmits(["confirm"]);
</script>

<style scoped>
.mask {
  position: fixed;
  inset: 0;
  display: grid;
  place-items: end center;
  padding: 20px;
  background: rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  z-index: 40;
}

.sheet-card {
  width: min(100%, 420px);
  padding: 10px 22px 22px;
  border-radius: 22px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  background: #fff;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.12);
}

.grabber {
  width: 36px;
  height: 4px;
  margin: 0 auto 16px;
  border-radius: 999px;
  background: #d1d5db;
}

h2 {
  margin: 12px 0 6px;
  font-size: 22px;
  line-height: 1.2;
  letter-spacing: -0.2px;
  color: #1c1c1e;
}

p {
  margin: 0 0 8px;
  color: #8e8e93;
  font-size: 14px;
  line-height: 1.65;
}

.actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 16px;
}

.ghost,
.primary {
  min-height: 44px;
  border-radius: 14px;
  font-weight: 700;
  cursor: pointer;
  border: none;
  transition: transform 0.15s cubic-bezier(0.34, 1.2, 0.64, 1), background 0.15s ease;
}

.ghost:active,
.primary:active {
  transform: scale(0.97);
}

.ghost {
  color: #1c1c1e;
  background: #f5f5f7;
}

.primary {
  color: #fff;
  background: #1c1c1e;
}

.sheet-enter-active,
.sheet-leave-active {
  transition: opacity 0.2s ease;
}

.sheet-enter-active .sheet-card,
.sheet-leave-active .sheet-card {
  transition: transform 0.22s ease, opacity 0.22s ease;
}

.sheet-enter-from,
.sheet-leave-to {
  opacity: 0;
}

.sheet-enter-from .sheet-card,
.sheet-leave-to .sheet-card {
  opacity: 0;
  transform: translateY(28px) scale(0.98);
}
</style>
