<template>
  <button class="ios-button" :class="[`ios-button--${variant}`, { 'is-icon': iconOnly }]" :type="type">
    <span v-if="icon" class="ios-button__icon" aria-hidden="true">{{ icon }}</span>
    <span v-if="!iconOnly" class="ios-button__label"><slot /></span>
  </button>
</template>

<script setup>
defineProps({
  variant: {
    type: String,
    default: "primary",
  },
  type: {
    type: String,
    default: "button",
  },
  icon: {
    type: String,
    default: "",
  },
  iconOnly: {
    type: Boolean,
    default: false,
  },
});
</script>

<style scoped>
.ios-button {
  min-height: 44px;
  padding: 0 16px;
  border-radius: 10px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.15s cubic-bezier(0.34, 1.2, 0.64, 1), background 0.15s ease, opacity 0.15s ease;
  user-select: none;
  border: none;
}

.ios-button:active {
  transform: scale(0.96);
}

.ios-button--primary {
  color: #fff;
  background: #1c1c1e;
}

.ios-button--secondary {
  color: #1c1c1e;
  background: #f5f5f7;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.ios-button--plain {
  min-height: 38px;
  color: #1c1c1e;
  background: #f5f5f7;
}

.ios-button--danger {
  color: #fff;
  background: #ef4444;
}

.ios-button.is-icon {
  width: 44px;
  padding: 0;
  border-radius: 50%;
}

.ios-button__icon {
  font-size: 16px;
  line-height: 1;
}
</style>
