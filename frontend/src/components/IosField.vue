<template>
  <label class="ios-field">
    <span class="ios-field__label">{{ label }}</span>
    <slot />
  </label>
</template>

<script setup>
defineProps({
  label: { type: String, required: true },
});
</script>

<style scoped>
.ios-field {
  display: grid;
  gap: 6px;
  color: var(--label-2);
  font-size: 12px;
  font-weight: 600;
}

.ios-field__label {
  padding-left: 2px;
  letter-spacing: 0;
}

.ios-field :deep(input),
.ios-field :deep(select),
.ios-field :deep(textarea) {
  width: 100%;
  min-height: 46px;
  padding: 12px 14px;
  border-radius: 12px;
  border: 1.5px solid rgba(61, 48, 85, 0.14);
  background: #ffffff;
  color: var(--label);
  outline: none;
  font-size: 15px;
  transition: border-color 0.22s ease, box-shadow 0.22s ease;
}

.ios-field :deep(input:focus),
.ios-field :deep(select:focus),
.ios-field :deep(textarea:focus) {
  border-color: var(--ocean);
  box-shadow: 0 0 0 4px rgba(74, 127, 191, 0.12);
}

.ios-field :deep(input::placeholder),
.ios-field :deep(textarea::placeholder) {
  color: var(--label-3);
}
</style>
