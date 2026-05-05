<template>
  <AppShell />
  <div class="debug-panel">
    <div class="debug-header" @click="showDebug = !showDebug">
      DEBUG {{ showDebug ? "▲" : "▼" }}
    </div>
    <div v-if="showDebug" class="debug-body">
      <div v-for="(line, i) in app.debugLog" :key="i" class="debug-line">{{ line }}</div>
      <div v-if="!app.debugLog.length" class="debug-line">等待操作...</div>
    </div>
  </div>
</template>

<script setup>
import { ref } from "vue";
import AppShell from "./components/AppShell.vue";
import { useAssistantApp } from "./composables/useAssistantApp";

const app = useAssistantApp();
const showDebug = ref(true);
</script>

<style>
.debug-panel {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 9999;
  background: rgba(0, 0, 0, 0.92);
  color: #0f0;
  font-family: monospace;
  font-size: 10px;
  max-height: 40vh;
  overflow-y: auto;
  border-top: 2px solid #0f0;
}
.debug-header {
  padding: 4px 8px;
  font-weight: bold;
  cursor: pointer;
  background: #111;
  position: sticky;
  top: 0;
  z-index: 1;
}
.debug-body {
  padding: 4px 8px;
}
.debug-line {
  padding: 2px 0;
  border-bottom: 1px solid rgba(0, 255, 0, 0.15);
  word-break: break-all;
}
</style>
