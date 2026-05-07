<template>
  <button
    class="ios-button"
    :class="[`ios-button--${variant}`, { 'is-icon': iconOnly }]"
    :type="type"
    @click="burst"
  >
    <span v-if="icon" class="ios-button__icon" aria-hidden="true">{{ icon }}</span>
    <span v-if="!iconOnly" class="ios-button__label"><slot /></span>
  </button>
</template>

<script setup>
import { ref } from "vue";

const props = defineProps({
  variant: { type: String, default: "primary" },
  type: { type: String, default: "button" },
  icon: { type: String, default: "" },
  iconOnly: { type: Boolean, default: false },
});

const sparkles = ref([]);
let sid = 0;

function burst(e) {
  if (props.variant === 'ghost' || props.type === 'submit') return;
  const rect = e.currentTarget.getBoundingClientRect();
  const x = e.clientX - rect.left;
  const y = e.clientY - rect.top;
  const id = ++sid;
  sparkles.value = [...sparkles.value.slice(-3), { id, x, y }];
  setTimeout(() => {
    sparkles.value = sparkles.value.filter(s => s.id !== id);
  }, 500);
}
</script>

<style scoped>
.ios-button {
  min-height: 46px;
  padding: 0 20px;
  border-radius: 12px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.2px;
  cursor: pointer;
  transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1), background 0.18s ease, opacity 0.18s ease, box-shadow 0.18s ease;
  user-select: none;
  border: none;
  position: relative;
  overflow: visible;
}

.ios-button:active { transform: scale(0.96); }

.ios-button--primary {
  color: #ffffff;
  background: linear-gradient(135deg, var(--sky), var(--ocean));
  box-shadow: 0 3px 12px rgba(126, 200, 227, 0.30);
}
.ios-button--primary:active { box-shadow: 0 1px 4px rgba(126, 200, 227, 0.18); }

.ios-button--secondary {
  color: var(--ocean);
  background: transparent;
}
.ios-button--secondary:active { background: rgba(74, 127, 191, 0.08); }

.ios-button--ghost {
  min-height: 44px;
  color: var(--label-2);
  font-weight: 400;
  background: transparent;
}
.ios-button--ghost:active { background: var(--fill-4); }

.ios-button--plain {
  min-height: 38px;
  color: var(--label);
  background: var(--fill-4);
  border-radius: 10px;
}
.ios-button--plain:active { background: var(--fill-3); }

.ios-button--danger {
  color: #ffffff;
  background: linear-gradient(135deg, #ff6b7a, #ff3b50);
}
.ios-button--danger:active { opacity: 0.85; }

.ios-button.is-icon {
  width: 44px; padding: 0; border-radius: 50%;
}

.ios-button__icon { font-size: 16px; line-height: 1; }
</style>
