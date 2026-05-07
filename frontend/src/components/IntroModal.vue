<template>
  <teleport to="body">
    <transition name="alert">
      <div v-if="open" class="mask" @click.self="$emit('confirm')">
        <section class="alert-card" role="dialog" aria-modal="true" aria-labelledby="intro-title">
          <div class="alert-icon-wrap">
            <div class="alert-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 6v6l3.5 2"/>
              </svg>
            </div>
            <span class="alert-sparkle a1">✦</span>
            <span class="alert-sparkle a2">✧</span>
          </div>
          <h2 id="intro-title">出行文档助手</h2>
          <p>查车票、排路线、找酒店、挖美食，你的随身出行管家。</p>
          <div class="alert-actions">
            <button class="alert-btn primary" type="button" @click="$emit('confirm')">开始使用</button>
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
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: rgba(61, 48, 85, 0.30);
  backdrop-filter: blur(16px) saturate(180%);
  -webkit-backdrop-filter: blur(16px) saturate(180%);
  z-index: 40;
}

.alert-card {
  width: min(100%, 300px);
  padding: 32px 24px 24px;
  border-radius: 24px;
  background: #ffffff;
  box-shadow: 0 24px 64px rgba(61, 48, 85, 0.20), 0 0 40px rgba(126, 200, 227, 0.12);
  text-align: center;
}

.alert-icon-wrap {
  position: relative;
  display: inline-block;
  margin-bottom: 20px;
}

.alert-icon {
  width: 68px; height: 68px;
  display: grid; place-items: center;
  border-radius: 18px;
  background: linear-gradient(135deg, var(--sky), var(--ocean), var(--azure));
  color: #ffffff;
  box-shadow: 0 8px 28px rgba(126, 200, 227, 0.35);
  animation: bounce-in 0.55s var(--ease-bounce) both;
  animation-delay: 0.08s;
}

.alert-sparkle {
  position: absolute;
  font-size: 15px;
  color: var(--ocean);
  animation: sparkle-twinkle 2s ease-in-out infinite;
  pointer-events: none;
}
.alert-sparkle.a1 { top: -6px; right: -8px; animation-delay: 0s; }
.alert-sparkle.a2 { bottom: -4px; left: -8px; animation-delay: 0.8s; color: var(--sky); }

h2 {
  margin: 0 0 8px;
  font-size: 20px;
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.3px;
  color: var(--label);
}

p {
  margin: 0 0 24px;
  color: var(--label-2);
  font-size: 14px;
  line-height: 1.55;
}

.alert-actions { display: flex; justify-content: center; }

.alert-btn {
  min-height: 46px;
  padding: 0 36px;
  border-radius: 14px;
  font-size: 16px;
  font-weight: 700;
  cursor: pointer;
  border: none;
  transition: transform 0.18s var(--ease-spring), box-shadow 0.2s ease;
}
.alert-btn:active { transform: scale(0.96); }

.alert-btn.primary {
  color: #ffffff;
  background: linear-gradient(135deg, var(--sky), var(--ocean));
  box-shadow: 0 4px 16px rgba(126, 200, 227, 0.35);
}

/* Alert transition */
.alert-enter-active { transition: opacity 0.25s ease; }
.alert-leave-active { transition: opacity 0.18s ease; }
.alert-enter-active .alert-card { transition: transform 0.40s var(--ease-spring-soft), opacity 0.22s ease; }
.alert-leave-active .alert-card { transition: transform 0.15s ease, opacity 0.15s ease; }
.alert-enter-from, .alert-leave-to { opacity: 0; }
.alert-enter-from .alert-card { opacity: 0; transform: scale(0.85) translateY(12px); }
.alert-leave-to .alert-card { opacity: 0; transform: scale(0.92); }
</style>
