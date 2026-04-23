<template>
  <teleport to="body">
    <transition name="fade">
      <div v-if="open" class="mask" @click.self="$emit('confirm')">
        <div class="modal-card">
          <div class="modal-pill">使用说明</div>
          <h2>欢迎进入文档助手</h2>
          <p>顶部右侧头像可以打开用户菜单，聊天页只保留对话本身，其他功能都通过页面切换进入。</p>
          <p>首次确认后将不再自动弹出，你仍然可以正常登录、上传文档并继续聊天。</p>
          <div class="actions">
            <button class="ghost" type="button" @click="$emit('confirm')">关闭</button>
            <button class="primary" type="button" @click="$emit('confirm')">我已知道</button>
          </div>
        </div>
      </div>
    </transition>
  </teleport>
</template>

<script setup>
defineProps({ open: { type: Boolean, default: false } });
defineEmits(["confirm"]);
</script>

<style scoped>
.mask { position: fixed; inset: 0; background: rgba(21, 21, 24, 0.24); backdrop-filter: blur(8px); display: grid; place-items: center; padding: 20px; z-index: 40; }
.modal-card { width: min(100%, 360px); padding: 24px; border-radius: 28px; border: 1px solid var(--card-border); background: rgba(255, 255, 255, 0.9); box-shadow: 0 30px 80px rgba(17, 17, 22, 0.16); }
.modal-pill { display: inline-flex; padding: 8px 12px; border-radius: 999px; background: rgba(245, 245, 247, 0.92); color: var(--text-secondary); font-size: 12px; font-weight: 700; }
h2 { margin: 14px 0 10px; font-size: 24px; line-height: 1.2; }
p { margin: 0 0 10px; color: var(--text-secondary); font-size: 14px; line-height: 1.8; }
.actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; }
.ghost, .primary { min-width: 92px; padding: 12px 18px; border-radius: 999px; cursor: pointer; }
.ghost { background: var(--button-light); border: 1px solid var(--card-border); color: var(--text-main); font-weight: 700; }
.primary { color: #fff; font-weight: 800; background: linear-gradient(180deg, var(--button-dark-start), var(--button-dark-end)); }
.fade-enter-active, .fade-leave-active { transition: opacity 0.18s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }
</style>
