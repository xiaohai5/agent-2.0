<template>
  <section class="chat-page">
    <!-- Animated bubble background -->
    <div class="bubble-bg">
      <div class="bubble" v-for="n in 12" :key="n" :style="bubbleStyle(n)"></div>
    </div>

    <div ref="feedRef" class="chat-feed ios-scroll">
      <!-- Welcome screen -->
      <div v-if="app.showWelcomeCard.value" class="welcome-screen">
        <div class="welcome-logo">✦</div>
        <h1 class="welcome-title">有什么可以帮你的？</h1>

        <div class="prompt-grid">
          <button
            v-for="prompt in app.prompts"
            :key="prompt"
            type="button"
            class="prompt-card"
            @click="applyPrompt(prompt)"
          >
            {{ prompt }}
          </button>
        </div>

        <div class="meta-info">
          <span>{{ app.chatMode.value === "stream" ? "流式" : "标准" }} · Top K {{ app.topK.value }}</span>
        </div>
      </div>

      <!-- Messages -->
      <div
        v-for="(msg, index) in app.messages.value"
        :key="msg.id || `${msg.role}-${index}`"
        class="message"
        :class="{ 'is-user': msg.role === 'user', 'is-assistant': msg.role !== 'user' }"
      >
        <!-- AI message layout -->
        <template v-if="msg.role !== 'user'">
          <div class="message-avatar">
            <div class="avatar-circle ai-av">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"/>
              </svg>
            </div>
          </div>
          <div class="message-content">
            <div class="message-body">
              <template v-if="!app.stringifyMessage(msg.content) && isStreamingMessage(msg)">
                <div class="bubble-bubble ai-bubble">
                  <div class="typing-indicator">
                    <span></span><span></span><span></span>
                  </div>
                </div>
              </template>
              <template v-else-if="!isStreamingMessage(msg) && hasRichMessage(msg.content)">
                <div class="bubble-bubble ai-bubble rich-bubble">
                  <TravelPlanMessage :content="app.stringifyMessage(msg.content)" />
                  <div v-if="canShowActions(msg)" class="message-actions">
                    <button type="button" class="action-btn" @click="copyMessage(msg)" title="复制">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                    </button>
                    <button type="button" class="action-btn" :class="{ active: msg.feedback_type === 'like' }" :disabled="msg.feedbackLoading" @click="app.submitFeedback(msg, 'like')" title="喜欢">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
                    </button>
                    <button type="button" class="action-btn" :class="{ active: msg.feedback_type === 'dislike' }" :disabled="msg.feedbackLoading" @click="app.submitFeedback(msg, 'dislike')" title="不喜欢">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>
                    </button>
                  </div>
                </div>
              </template>
              <template v-else>
                <div class="bubble-bubble ai-bubble">
                  {{ app.stringifyMessage(msg.content) }}
                  <div v-if="canShowActions(msg)" class="message-actions">
                    <button type="button" class="action-btn" @click="copyMessage(msg)" title="复制">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                    </button>
                    <button type="button" class="action-btn" :class="{ active: msg.feedback_type === 'like' }" :disabled="msg.feedbackLoading" @click="app.submitFeedback(msg, 'like')" title="喜欢">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>
                    </button>
                    <button type="button" class="action-btn" :class="{ active: msg.feedback_type === 'dislike' }" :disabled="msg.feedbackLoading" @click="app.submitFeedback(msg, 'dislike')" title="不喜欢">
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>
                    </button>
                  </div>
                </div>
              </template>
              <div v-if="isStreamingMessage(msg) && app.stringifyMessage(msg.content)" class="typing-inline">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        </template>

        <!-- User message layout (right aligned) -->
        <template v-else>
          <div class="message-content user-content">
            <div class="message-body">
              <div class="bubble-bubble user-bubble">{{ app.stringifyMessage(msg.content) }}</div>
            </div>
          </div>
          <div class="message-avatar">
            <div class="avatar-circle user-av">{{ avatarText }}</div>
          </div>
        </template>
      </div>

      <!-- Thinking state -->
      <div v-if="app.thinking.value" class="message is-assistant">
        <div class="message-avatar">
          <div class="avatar-circle ai-av">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"/>
            </svg>
          </div>
        </div>
        <div class="message-content">
          <div class="message-body">
            <div class="bubble-bubble ai-bubble">
              <div class="typing-indicator">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Input area -->
    <footer class="input-area">
      <div class="input-wrapper">
        <textarea
          ref="textareaRef"
          v-model="app.question.value"
          :disabled="app.loading.chat"
          placeholder="给 AI 助手发送消息"
          rows="1"
          @focus="handleComposerFocus"
          @keydown.enter.exact.prevent="handleSendChat"
          @input="syncComposerHeight"
        ></textarea>
        <button
          class="send-button"
          type="button"
          :disabled="!app.question.value.trim() || app.loading.chat"
          aria-label="发送"
          @click="handleSendChat"
        >
          <svg v-if="!app.loading.chat" width="18" height="18" viewBox="0 0 24 24" fill="none">
            <path d="M22 2L11 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M22 2L15 22L11 13L2 9L22 2Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span v-else class="loading-dots"><span></span><span></span><span></span></span>
        </button>
      </div>
      <div class="input-footer">
        <span>{{ app.chatStatus.value || 'AI 助手可能会犯错，请核实重要信息' }}</span>
      </div>
    </footer>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import TravelPlanMessage from "../components/TravelPlanMessage.vue";
import { useAssistantApp } from "../composables/useAssistantApp";

const app = useAssistantApp();
const feedRef = ref(null);
const textareaRef = ref(null);

const avatarText = computed(() => (app.state.username ? app.state.username.slice(0, 1).toUpperCase() : "我"));

const MIN_TEXTAREA_HEIGHT = 24;
const MAX_TEXTAREA_HEIGHT = 200;

function bubbleStyle(n) {
  const size = 20 + Math.random() * 60;
  const left = Math.random() * 100;
  const delay = Math.random() * 20;
  const duration = 15 + Math.random() * 20;
  const opacity = 0.03 + Math.random() * 0.06;
  return {
    width: `${size}px`,
    height: `${size}px`,
    left: `${left}%`,
    animationDelay: `${delay}s`,
    animationDuration: `${duration}s`,
    opacity: opacity,
  };
}

function isStreamingMessage(msg) {
  return msg?.role === "assistant" && !!msg?.streaming;
}

function hasRichMessage(content) {
  const text = app.stringifyMessage(content);
  return /!\[[^\]]*\]\(https?:\/\/[^)\s]+\)/.test(text) || /^(🍜|🏨)?\s*(餐厅|酒店)\s*\d+/m.test(text);
}

function canShowActions(msg) {
  return msg?.role === "assistant" && !msg?.streaming && !!app.stringifyMessage(msg.content);
}

function copyMessage(msg) {
  const text = app.stringifyMessage(msg.content);
  if (text) {
    navigator.clipboard.writeText(text).catch(() => {});
  }
}

function applyPrompt(prompt) {
  app.question.value = prompt;
  app.dismissWelcomeCard();
}

function handleComposerFocus() {
  app.dismissWelcomeCard();
}

async function handleSendChat() {
  if (!app.question.value.trim()) return;
  await app.sendChat();
  await pinFeedToBottom("smooth");
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
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: linear-gradient(135deg, #f5f7fa 0%, #e4e9f0 100%);
  position: relative;
}

/* Animated bubble background */
.bubble-bg {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}

.bubble {
  position: absolute;
  bottom: -80px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(139, 92, 246, 0.1));
  animation: float-up linear infinite;
}

@keyframes float-up {
  0% {
    transform: translateY(0) scale(1);
    opacity: 0;
  }
  10% {
    opacity: var(--opacity, 0.05);
  }
  90% {
    opacity: var(--opacity, 0.05);
  }
  100% {
    transform: translateY(-120vh) scale(0.4);
    opacity: 0;
  }
}

.chat-feed {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 1;
  padding-bottom: 8px;
}

/* Welcome screen */
.welcome-screen {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  text-align: center;
}

.welcome-logo {
  width: 56px;
  height: 56px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  font-size: 28px;
  margin-bottom: 24px;
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.3);
}

.welcome-title {
  margin: 0 0 32px;
  font-size: 28px;
  font-weight: 600;
  color: #1f2937;
  line-height: 1.3;
}

.prompt-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  max-width: 560px;
  width: 100%;
}

.prompt-card {
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid rgba(0, 0, 0, 0.06);
  color: #374151;
  font-size: 14px;
  line-height: 1.45;
  text-align: left;
  cursor: pointer;
  transition: all 0.2s ease;
  backdrop-filter: blur(10px);
}

.prompt-card:hover {
  background: rgba(255, 255, 255, 0.95);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.prompt-card:active {
  transform: scale(0.98);
}

.meta-info {
  margin-top: 24px;
}

.meta-info span {
  color: #9ca3af;
  font-size: 12px;
}

/* Messages */
.message {
  display: flex;
  gap: 10px;
  padding: 4px 20px;
  animation: fade-in 0.3s ease both;
}

.message.is-user {
  justify-content: flex-end;
}

/* Avatar */
.message-avatar {
  flex: 0 0 30px;
  align-self: center;
}

.avatar-circle {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 600;
}

.user-av {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
}

.ai-av {
  background: #1c1c1e;
  color: #fff;
}

/* Message content */
.message-content {
  max-width: 75%;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.user-content {
  align-items: flex-end;
}

/* Bubble styles - long oval shape */
.bubble-bubble {
  padding: 10px 16px;
  font-size: 15px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  max-width: 100%;
}

.ai-bubble {
  background: rgba(255, 255, 255, 0.9);
  color: #1f2937;
  border-radius: 20px 20px 20px 6px;
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  position: relative;
  padding-bottom: 32px;
}

.ai-bubble .message-actions {
  position: absolute;
  bottom: 6px;
  right: 8px;
  display: flex;
  gap: 2px;
  opacity: 0;
  transition: opacity 0.2s ease;
  pointer-events: none;
}

.ai-bubble:hover .message-actions {
  opacity: 1;
  pointer-events: auto;
}

.user-bubble {
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  color: #fff;
  border-radius: 20px 20px 6px 20px;
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.25);
}

.rich-bubble {
  padding: 12px 16px;
  max-width: 320px;
}

/* Typing indicator */
.typing-indicator {
  display: flex;
  gap: 5px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #9ca3af;
  animation: typing 1.4s ease-in-out infinite;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

.typing-inline {
  display: inline-flex;
  gap: 3px;
  margin-left: 4px;
  vertical-align: middle;
}

.typing-inline span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: #9ca3af;
  animation: typing 1.4s ease-in-out infinite;
}

.typing-inline span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-inline span:nth-child(3) {
  animation-delay: 0.4s;
}

/* Message actions */
.message-actions {
  display: flex;
  gap: 2px;
}

.action-btn {
  width: 26px;
  height: 26px;
  display: grid;
  place-items: center;
  border-radius: 6px;
  background: transparent;
  border: none;
  color: #c0c4cc;
  cursor: pointer;
  transition: all 0.15s ease;
}

.action-btn:hover {
  background: rgba(0, 0, 0, 0.05);
  color: #6b7280;
}

.action-btn.active {
  color: #6366f1;
}

.action-btn:disabled {
  opacity: 0.4;
  cursor: default;
}

/* Input area */
.input-area {
  padding: 8px 20px 16px;
  position: relative;
  z-index: 1;
  background: linear-gradient(to top, rgba(245, 247, 250, 1) 60%, rgba(245, 247, 250, 0));
}

.input-wrapper {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 24px;
  border: 1px solid rgba(0, 0, 0, 0.08);
  padding: 10px 14px;
  transition: all 0.2s ease;
  backdrop-filter: blur(10px);
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
}

.input-wrapper:focus-within {
  border-color: rgba(99, 102, 241, 0.3);
  box-shadow: 0 2px 16px rgba(99, 102, 241, 0.12);
}

.input-wrapper textarea {
  flex: 1;
  min-height: 24px;
  max-height: 160px;
  resize: none;
  border: none;
  outline: none;
  background: transparent;
  color: #1f2937;
  font-size: 15px;
  line-height: 1.5;
  overflow-y: hidden;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.input-wrapper textarea::-webkit-scrollbar {
  display: none;
}

.input-wrapper textarea::placeholder {
  color: #9ca3af;
}

.send-button {
  width: 34px;
  height: 34px;
  flex: 0 0 34px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  border: none;
  color: #fff;
  cursor: pointer;
  transition: all 0.2s ease;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
}

.send-button:hover:not(:disabled) {
  transform: scale(1.05);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
}

.send-button:active:not(:disabled) {
  transform: scale(0.95);
}

.send-button:disabled {
  background: #e5e7eb;
  color: #9ca3af;
  cursor: default;
  box-shadow: none;
}

.loading-dots {
  display: flex;
  gap: 3px;
}

.loading-dots span {
  width: 4px;
  height: 4px;
  border-radius: 50%;
  background: #fff;
  animation: typing 1s ease-in-out infinite;
}

.loading-dots span:nth-child(2) {
  animation-delay: 0.15s;
}

.loading-dots span:nth-child(3) {
  animation-delay: 0.3s;
}

.input-footer {
  text-align: center;
  padding-top: 8px;
}

.input-footer span {
  color: #9ca3af;
  font-size: 11px;
}

/* Animations */
@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes typing {
  0%, 60%, 100% {
    opacity: 0.3;
    transform: translateY(0);
  }
  30% {
    opacity: 1;
    transform: translateY(-3px);
  }
}

@media (max-width: 520px) {
  .message {
    padding: 3px 14px;
  }

  .welcome-screen {
    padding: 32px 16px;
  }

  .prompt-grid {
    grid-template-columns: 1fr;
  }

  .input-area {
    padding: 8px 14px 14px;
  }
}
</style>
