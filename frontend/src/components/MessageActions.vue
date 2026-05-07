<template>
  <div class="bubble-actions">
    <button class="action-icon" type="button" aria-label="Copy" @click="$emit('copy', message)">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <rect x="9" y="9" width="11" height="11" rx="2"></rect>
        <path d="M5 15V6a2 2 0 0 1 2-2h9"></path>
      </svg>
    </button>
    <button
      class="action-icon"
      type="button"
      aria-label="Useful"
      :class="{ active: message.feedback_type === 'like' }"
      :disabled="message.feedbackLoading"
      @click="$emit('feedback', message, 'like')"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M7 22V10"></path>
        <path d="M15 6.5 14 10h5.4a2 2 0 0 1 1.9 2.5l-1.4 6A2 2 0 0 1 18 20H7"></path>
        <path d="M7 10 12 2l.9.7A4 4 0 0 1 15 6.5"></path>
        <path d="M3 10h4v12H3z"></path>
      </svg>
    </button>
    <button
      class="action-icon"
      type="button"
      aria-label="Not useful"
      :class="{ active: message.feedback_type === 'dislike' }"
      :disabled="message.feedbackLoading"
      @click="$emit('feedback', message, 'dislike')"
    >
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M17 2v12"></path>
        <path d="M9 17.5 10 14H4.6a2 2 0 0 1-1.9-2.5l1.4-6A2 2 0 0 1 6 4h11"></path>
        <path d="M17 14 12 22l-.9-.7A4 4 0 0 1 9 17.5"></path>
        <path d="M21 14h-4V2h4z"></path>
      </svg>
    </button>
  </div>
</template>

<script setup>
defineProps({
  message: {
    type: Object,
    required: true,
  },
});

defineEmits(["copy", "feedback"]);
</script>

<style scoped>
.bubble-actions.bubble-actions {
  display: flex;
  align-items: center;
  gap: 1px;
}

.action-icon {
  width: 22px;
  height: 22px;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: #6f6f76;
  cursor: pointer;
  display: grid;
  place-items: center;
  transition: background 0.15s ease, color 0.15s ease, transform 0.15s ease;
}

.action-icon:hover {
  background: rgba(0, 0, 0, 0.06);
  color: #1d1d1f;
}

.action-icon:active { transform: scale(0.94); }

.action-icon.active {
  background: rgba(0, 122, 255, 0.12);
  color: #007aff;
}

.action-icon:disabled {
  cursor: default;
  opacity: 0.45;
}

.action-icon svg {
  width: 14px;
  height: 14px;
  fill: none;
  stroke: currentColor;
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}
</style>
