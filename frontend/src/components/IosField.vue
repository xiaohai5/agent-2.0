<template>
  <label class="ios-field">
    <span class="ios-field__label">{{ label }}</span>
    <slot />
  </label>
</template>

<script setup>
defineProps({
  label: {
    type: String,
    required: true,
  },
});
</script>

<style scoped>
.ios-field {
  display: grid;
  gap: 6px;
  color: #6b7280;
  font-size: 12px;
  font-weight: 600;
}

.ios-field__label {
  padding-left: 2px;
}

.ios-field :deep(input),
.ios-field :deep(select),
.ios-field :deep(textarea) {
  width: 100%;
  min-height: 46px;
  padding: 12px 14px;
  border-radius: 10px;
  border: 1px solid rgba(0, 0, 0, 0.1);
  background: #fff;
  color: #1f2937;
  outline: none;
  transition: border-color 0.18s ease, box-shadow 0.18s ease;
}

.ios-field :deep(input:focus),
.ios-field :deep(select:focus),
.ios-field :deep(textarea:focus) {
  border-color: rgba(0, 0, 0, 0.2);
  box-shadow: 0 0 0 2px rgba(0, 0, 0, 0.05);
}

.ios-field :deep(input::placeholder),
.ios-field :deep(textarea::placeholder) {
  color: #9ca3af;
}
</style>
