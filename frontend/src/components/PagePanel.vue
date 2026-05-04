<template>
  <article class="ios-panel">
    <div v-if="title || eyebrow || description" class="ios-panel-head">
      <div class="ios-panel-title">
        <h2 v-if="title">{{ title }}</h2>
        <p v-if="description">{{ description }}</p>
      </div>
      <span v-if="eyebrow" class="ios-pill">{{ eyebrow }}</span>
    </div>
    <slot />
  </article>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: "",
  },
  description: {
    type: String,
    default: "",
  },
  eyebrow: {
    type: String,
    default: "",
  },
});
</script>
