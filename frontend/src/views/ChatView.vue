<template>
  <section class="chat-page">
    <div ref="feedRef" class="chat-feed">
      <div v-if="app.showWelcomeCard.value" class="hero-card">
        <div class="hero-orb"></div>
        <strong>开始一段新的对话</strong>
        <p>点击下方输入框后，页面会切换为正式聊天态，消息区接管空间，输入区固定在页面底部。</p>
        <div class="prompt-list">
          <button
            v-for="prompt in app.prompts"
            :key="prompt"
            type="button"
            class="prompt-chip"
            @click="applyPrompt(prompt)"
          >
            {{ prompt }}
          </button>
        </div>
        <div class="meta-row">
          <span>{{ app.chatMode.value === "stream" ? "流式问答" : "标准问答" }}</span>
          <span>Top K {{ app.topK.value }}</span>
          <span>{{ app.state.username || "未登录" }}</span>
        </div>
      </div>

      <div
        v-for="(msg, index) in app.messages.value"
        :key="msg.id || `${msg.role}-${index}`"
        class="message-row"
        :class="{ user: msg.role === 'user' }"
      >
        <div v-if="msg.role !== 'user'" class="message-mark">AI</div>
        <div class="message-bubble" :class="[bubbleClass(msg.role), { 'is-streaming': isStreamingMessage(msg) }]">
          <template v-if="!app.stringifyMessage(msg.content) && isStreamingMessage(msg)">
            <div class="thinking-copy">正在思考...</div>
          </template>
          <template v-else-if="msg.role === 'assistant' && !isStreamingMessage(msg) && hasRichMessage(msg.content)">
            <TravelPlanMessage :content="app.stringifyMessage(msg.content)" />
          </template>
          <template v-else>
            {{ app.stringifyMessage(msg.content) }}
          </template>
          <div v-if="isStreamingMessage(msg)" class="thinking-dots" :class="{ compact: !!app.stringifyMessage(msg.content) }">
            <span></span>
            <span></span>
            <span></span>
          </div>
          <div v-if="canFeedback(msg)" class="feedback-actions">
            <button
              type="button"
              class="feedback-btn"
              :class="{ selected: msg.feedback_type === 'like' }"
              :disabled="msg.feedbackLoading"
              @click="app.submitFeedback(msg, 'like')"
            >
              喜欢
            </button>
            <button
              type="button"
              class="feedback-btn"
              :class="{ selected: msg.feedback_type === 'dislike' }"
              :disabled="msg.feedbackLoading"
              @click="app.submitFeedback(msg, 'dislike')"
            >
              不喜欢
            </button>
          </div>
        </div>
        <div v-if="msg.role === 'user'" class="message-mark">我</div>
      </div>

      <div v-if="app.thinking.value" class="message-row">
        <div class="message-mark">AI</div>
        <div class="message-bubble is-thinking">
          <div class="thinking-copy">正在思考...</div>
          <div class="thinking-dots">
            <span></span>
            <span></span>
            <span></span>
          </div>
        </div>
      </div>
    </div>

    <footer class="composer-shell">
      <div class="status-line">{{ app.chatStatus.value }}</div>
      <div class="composer-body">
        <div class="textarea-panel">
          <textarea
            ref="textareaRef"
            v-model="app.question.value"
            :disabled="app.loading.chat"
            placeholder="输入你的问题，AI 会结合当前资料为你整理答案"
            @focus="handleComposerFocus"
            @keydown.enter.exact.prevent="handleSendChat"
            @input="syncComposerHeight"
          ></textarea>

          <div class="action-group">
            <button class="primary" type="button" :disabled="app.loading.chat" @click="handleSendChat">
              <span>{{ app.loading.chat ? "..." : "发送" }}</span>
            </button>
          </div>
        </div>
      </div>
    </footer>
  </section>
</template>

<script setup>
import { nextTick, onMounted, ref, watch } from "vue";
import TravelPlanMessage from "../components/TravelPlanMessage.vue";
import { useAssistantApp } from "../composables/useAssistantApp";

const app = useAssistantApp();
const feedRef = ref(null);
const textareaRef = ref(null);

const MIN_TEXTAREA_HEIGHT = 28;
const MAX_TEXTAREA_HEIGHT = 160;

function bubbleClass(role) {
  if (role === "user") return "is-user";
  if (role === "assistant") return "is-assistant";
  return "is-system";
}

function isStreamingMessage(msg) {
  return msg?.role === "assistant" && !!msg?.streaming;
}

function hasRichMessage(content) {
  const text = app.stringifyMessage(content);
  return /!\[[^\]]*\]\(https?:\/\/[^)\s]+\)/.test(text) || /^(🍜|🏨)?\s*(餐厅|酒店)\s*\d+/m.test(text);
}

function canFeedback(msg) {
  return msg?.role === "assistant" && !msg?.streaming && !!app.stringifyMessage(msg.content);
}

function applyPrompt(prompt) {
  app.question.value = prompt;
}

function handleComposerFocus() {
  app.dismissWelcomeCard();
}

async function handleSendChat() {
  await app.sendChat();
  await pinFeedToBottom();
}

async function pinFeedToBottom(behavior = "auto") {
  await nextTick();
  if (!feedRef.value) return;
  feedRef.value.scrollTo({
    top: feedRef.value.scrollHeight,
    behavior,
  });
}

function syncComposerHeight() {
  const textarea = textareaRef.value;
  if (!textarea) return;

  textarea.style.height = "auto";
  const nextHeight = Math.min(Math.max(textarea.scrollHeight, MIN_TEXTAREA_HEIGHT), MAX_TEXTAREA_HEIGHT);
  textarea.style.height = `${nextHeight}px`;
  textarea.style.overflowY = textarea.scrollHeight > MAX_TEXTAREA_HEIGHT ? "auto" : "hidden";
}

watch(
  () => [app.messages.value.length, app.thinking.value, app.showWelcomeCard.value],
  async () => {
    await nextTick();
    await pinFeedToBottom();
  },
  { immediate: true }
);

watch(
  () => app.question.value,
  async () => {
    await nextTick();
    syncComposerHeight();
  },
  { immediate: true }
);

onMounted(async () => {
  if (app.state.token) {
    app.dismissWelcomeCard();
  }
  await nextTick();
  syncComposerHeight();
  await pinFeedToBottom();
});
</script>

<style scoped>
.chat-page {
  height: 100%;
  min-height: 0;
  display: grid;
  grid-template-rows: 1fr auto;
  overflow: hidden;
  padding: 0 18px 0;
}

.chat-feed {
  min-height: 0;
  overflow-y: auto;
  padding: 0 0 18px 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.chat-feed::-webkit-scrollbar,
textarea::-webkit-scrollbar {
  width: 0;
  height: 0;
  display: none;
}

.hero-card {
  flex: 0 0 auto;
  padding: 20px;
  border-radius: 30px;
  border: 1px solid var(--card-border);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.54));
  box-shadow: var(--surface-shadow);
}

.hero-orb {
  width: 58px;
  height: 58px;
  border-radius: 999px;
  background: linear-gradient(135deg, #fdfdfd, #d7d7df);
  box-shadow: 0 14px 28px rgba(18, 18, 22, 0.08);
}

.hero-card strong {
  display: block;
  margin-top: 14px;
  font-size: 28px;
  line-height: 1.1;
  letter-spacing: -0.02em;
}

.hero-card p {
  margin: 10px 0 0;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.85;
}

.prompt-list,
.meta-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.prompt-list {
  margin-top: 16px;
}

.prompt-chip,
.meta-row span {
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid var(--card-border);
  background: rgba(255, 255, 255, 0.82);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.01em;
}

.meta-row {
  margin-top: 14px;
}

.meta-row span {
  color: var(--text-muted);
}

.message-row {
  display: flex;
  align-items: flex-end;
  gap: 10px;
}

.message-row.user {
  justify-content: flex-end;
}

.message-mark {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  border: 1px solid var(--card-border);
  background: rgba(255, 255, 255, 0.82);
  box-shadow: var(--soft-shadow);
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.04em;
}

.message-bubble {
  max-width: calc(100% - 52px);
  padding: 14px 16px;
  border-radius: 22px;
  font-size: 14px;
  line-height: 1.78;
  white-space: pre-wrap;
  word-break: break-word;
  box-shadow: var(--soft-shadow);
}

.message-bubble.is-streaming {
  min-width: 108px;
}

.is-assistant,
.is-system,
.is-thinking {
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid var(--card-border);
}

.is-user {
  background: linear-gradient(180deg, rgba(237, 237, 240, 0.92), rgba(223, 223, 228, 0.94));
  border: 1px solid rgba(255, 255, 255, 0.98);
}

.thinking-copy {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.02em;
}

.thinking-dots {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}

.thinking-dots.compact {
  margin-top: 8px;
}

.thinking-dots span {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #8f8f97;
  animation: pulse 1.1s ease-in-out infinite;
}

.thinking-dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.thinking-dots span:nth-child(3) {
  animation-delay: 0.3s;
}

.feedback-actions {
  display: flex;
  gap: 6px;
  margin-top: 8px;
  padding-top: 4px;
}

.feedback-btn {
  border: 1px solid rgba(176, 176, 184, 0.56);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.62);
  color: var(--text-muted);
  cursor: pointer;
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  padding: 5px 8px;
  transition: background-color 0.16s ease, border-color 0.16s ease, color 0.16s ease;
}

.feedback-btn:hover,
.feedback-btn.selected {
  background: #1f2026;
  border-color: #1f2026;
  color: #fff;
}

.composer-shell {
  padding: 12px 0 calc(12px + env(safe-area-inset-bottom, 0px));
  background: linear-gradient(180deg, rgba(235, 235, 239, 0), rgba(235, 235, 239, 0.88) 20%, rgba(235, 235, 239, 0.98));
}

.status-line {
  min-height: 16px;
  color: #90929b;
  font-size: 11px;
  line-height: 1.35;
  letter-spacing: 0.01em;
  margin: 0 0 4px;
  padding: 0 6px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.composer-body {
  min-width: 0;
}

.textarea-panel {
  position: relative;
  display: block;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(213, 213, 219, 0.55);
  padding: 8px 50px 10px 14px;
}

textarea {
  width: 100%;
  min-height: 28px;
  max-height: 160px;
  resize: none;
  border: 0;
  background: transparent;
  color: var(--text-main);
  outline: none;
  padding: 8px 0 6px;
  font-size: 16px;
  line-height: 1.5;
  letter-spacing: 0.01em;
  overflow-y: hidden;
  transition: height 0.2s ease;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

textarea::placeholder {
  color: #8a8c95;
}

textarea:focus {
  box-shadow: none;
}

textarea:disabled {
  opacity: 0.72;
  cursor: not-allowed;
}

.action-group {
  position: absolute;
  right: 10px;
  bottom: 10px;
  display: flex;
  align-items: center;
}

.primary {
  min-width: 48px;
  height: 32px;
  padding: 0 10px;
  display: inline-grid;
  place-items: center;
  color: #fff;
  background: #1f2026;
  box-shadow: none;
  font-size: 12px;
  font-weight: 800;
  border: 0;
  border-radius: 999px;
  cursor: pointer;
  transition: background-color 0.2s ease, transform 0.2s ease, opacity 0.2s ease;
}

.primary:hover {
  background: #111216;
  transform: translateY(-1px);
}

button:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

@keyframes pulse {
  0%,
  80%,
  100% {
    opacity: 0.28;
    transform: translateY(0);
  }

  40% {
    opacity: 1;
    transform: translateY(-2px);
  }
}

@media (max-width: 480px) {
  .chat-page {
    padding: 0 10px 0;
  }

  .composer-shell {
    padding-bottom: calc(10px + env(safe-area-inset-bottom, 0px));
  }

  .action-group {
    right: 10px;
  }
}
</style>
