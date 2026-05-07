<template>
  <section class="chat-page">
    <!-- Cherry blossom petal layer -->
    <div class="petal-layer" aria-hidden="true">
      <span v-for="n in 14" :key="'p'+n" class="petal" :style="petalStyle(n)"></span>
    </div>

    <!-- Sparkle container -->
    <div ref="sparkleRef" class="sparkle-layer" aria-hidden="true"></div>

    <div ref="feedRef" class="chat-feed ios-scroll">
      <!-- Welcome screen -->
      <transition name="welcome">
        <div v-if="app.showWelcomeCard.value" class="welcome-screen">
          <div class="welcome-icon-wrap">
            <div class="welcome-icon">
              <img v-if="aiAvatarUrl" :src="aiAvatarUrl" alt="AI 助手" class="welcome-ai-img" />
              <svg v-else width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 6v6l3.5 2"/>
              </svg>
            </div>
            <!-- Orbit sparkles -->
            <span class="orbit-sparkle s1">✦</span>
            <span class="orbit-sparkle s2">✧</span>
            <span class="orbit-sparkle s3">･</span>
          </div>
          <h1 class="welcome-title">有什么可以帮你的？</h1>
          <p class="welcome-desc">随时随地查询行程、文档和出行建议</p>

          <div class="prompt-grid">
            <button
              v-for="prompt in app.prompts"
              :key="prompt"
              type="button"
              class="prompt-card"
              @click="applyPrompt(prompt)"
            >
              <span class="prompt-icon">
                <template v-if="prompt.includes('总结')">📋</template>
                <template v-else-if="prompt.includes('回答')">💬</template>
                <template v-else>💡</template>
              </span>
              <span class="prompt-text">{{ prompt }}</span>
              <span class="prompt-shine"></span>
            </button>
          </div>
        </div>
      </transition>

      <!-- Messages -->
      <template v-for="(msg, index) in app.messages.value" :key="msg.id || `${msg.role}-${index}`">
        <div v-if="msg.role === 'system'" class="message-row is-system">
          <div class="system-bubble">{{ app.stringifyMessage(msg.content) }}</div>
        </div>

        <div v-else-if="msg.role !== 'user'" class="message-row">
          <div class="msg-avatar" :class="{ invisible: isGrouped(index, 'assistant') }">
            <div class="avatar-circle ai-av">
              <img v-if="aiAvatarUrl" :src="aiAvatarUrl" alt="AI" />
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"/>
              </svg>
            </div>
          </div>
          <div class="msg-body">
            <template v-if="!app.stringifyMessage(msg.content) && isStreamingMessage(msg)">
              <div class="bubble ai-bubble">
                <div class="typing-dots"><span></span><span></span><span></span></div>
              </div>
            </template>
            <template v-else-if="!isStreamingMessage(msg) && hasRichMessage(msg.content)">
              <div class="bubble ai-bubble rich-bubble" :class="{ 'has-corner': canShowActions(msg) || (canConfirmPlan(msg) && !isPlanConfirmed(msg)) }">
                <TravelPlanMessage :content="app.stringifyMessage(msg.content)" />
                <div class="bubble-corner">
                  <button v-if="canConfirmPlan(msg) && !isPlanConfirmed(msg)" class="corner-confirm-btn" type="button" @click="confirmThisPlan(msg)">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                    <span>确认</span>
                  </button>
                  <span v-else-if="isPlanConfirmed(msg)" class="corner-confirmed-tag">已确认</span>
                  <MessageActions v-if="canShowActions(msg)" :message="msg" @copy="copyMessage" @feedback="app.submitFeedback" />
                </div>
              </div>
            </template>
            <template v-else>
              <div class="bubble ai-bubble" :class="{ 'has-corner': canShowActions(msg) || (canConfirmPlan(msg) && !isPlanConfirmed(msg)) }">
                {{ app.stringifyMessage(msg.content) }}
                <div class="bubble-corner">
                  <button v-if="canConfirmPlan(msg) && !isPlanConfirmed(msg)" class="corner-confirm-btn" type="button" @click="confirmThisPlan(msg)">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                    <span>确认</span>
                  </button>
                  <span v-else-if="isPlanConfirmed(msg)" class="corner-confirmed-tag">已确认</span>
                  <MessageActions v-if="canShowActions(msg)" :message="msg" @copy="copyMessage" @feedback="app.submitFeedback" />
                </div>
              </div>
            </template>
          </div>
        </div>

        <div v-else class="message-row is-user">
          <div class="msg-body user-body">
            <div class="bubble user-bubble">{{ app.stringifyMessage(msg.content) }}</div>
          </div>
          <div class="msg-avatar" :class="{ invisible: isGrouped(index, 'user') }">
            <div class="avatar-circle user-av">
              <img v-if="app.profileData.avatarUrl" :src="app.profileData.avatarUrl" alt="" />
              <span v-else>{{ avatarText }}</span>
            </div>
          </div>
        </div>
      </template>

      <!-- Thinking -->
      <div v-if="app.thinking.value" class="message-row">
        <div class="msg-avatar">
          <div class="avatar-circle ai-av">
            <img v-if="aiAvatarUrl" :src="aiAvatarUrl" alt="AI" />
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm-1-13h2v6h-2zm0 8h2v2h-2z"/></svg>
          </div>
        </div>
        <div class="msg-body">
          <div class="bubble ai-bubble">
            <div class="typing-dots"><span></span><span></span><span></span></div>
          </div>
        </div>
      </div>
      <div class="feed-pad"></div>
    </div>

    <!-- Input area -->
    <footer class="input-area glass-bar">
      <div class="input-bar">
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
          <svg v-if="!app.loading.chat" width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
          <span v-else class="send-spinner"></span>
        </button>
      </div>
    </footer>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import MessageActions from "../components/MessageActions.vue";
import TravelPlanMessage from "../components/TravelPlanMessage.vue";
import { useAssistantApp } from "../composables/useAssistantApp";

const app = useAssistantApp();
const feedRef = ref(null);
const textareaRef = ref(null);
const sparkleRef = ref(null);

const avatarText = computed(() => (app.state.username ? app.state.username.slice(0, 1).toUpperCase() : "我"));
const aiAvatarUrl = computed(() => {
  const base = import.meta.env.BASE_URL || "/";
  return `${base}ai-avatar.png`;
});

const MIN_TEXTAREA_HEIGHT = 24;
const MAX_TEXTAREA_HEIGHT = 200;

function petalStyle(n) {
  const left = (n * 7.3 + 3) % 100;
  const size = 10 + (n % 3) * 5;
  const duration = 12 + (n % 5) * 4;
  const delay = (n * 1.7) % 14;
  const opacity = 0.2 + (n % 3) * 0.08;
  const drift = (n % 2 === 0 ? 1 : -1) * (20 + n * 5);
  return {
    left: `${left}%`,
    width: `${size}px`,
    height: `${size}px`,
    animationDuration: `${duration}s`,
    animationDelay: `${delay}s`,
    opacity,
    '--drift': `${drift}px`,
  };
}

function burstSparkles(x, y) {
  if (!sparkleRef.value) return;
  const colors = ['#7EC8E3','#A8D8EA','#5B9BD5','#D4EEFF','#4A7FBF'];
  for (let i = 0; i < 8; i++) {
    const dot = document.createElement('span');
    const angle = (i / 8) * Math.PI * 2;
    const dist = 18 + Math.random() * 22;
    dot.style.cssText = `
      position:absolute;left:${x}px;top:${y}px;width:6px;height:6px;border-radius:50%;
      background:${colors[i % colors.length]};pointer-events:none;
      animation:sparkle-pop 0.55s var(--ease-ease) both;
      transform:translate(${Math.cos(angle)*dist}px,${Math.sin(angle)*dist}px);
    `;
    sparkleRef.value.appendChild(dot);
    setTimeout(() => dot.remove(), 600);
  }
}

function isStreamingMessage(msg) { return msg?.role === "assistant" && !!msg?.streaming; }

function hasRichMessage(content) {
  const text = app.stringifyMessage(content);
  return /!\[[^\]]*\]\(https?:\/\/[^)\s]+\)/.test(text) || /^(🍜|🏨)?\s*(餐厅|酒店)\s*\d+/m.test(text);
}

function canShowActions(msg) { return msg?.role === "assistant" && !msg?.streaming && !!app.stringifyMessage(msg.content); }

function isGrouped(index, role) {
  if (index === 0) return false;
  const prev = app.messages.value[index - 1];
  if (!prev) return false;
  if (role === 'assistant') return prev.role === 'assistant';
  if (role === 'user') return prev.role === 'user';
  return false;
}

const confirmedPlanIds = ref([]);

function copyMessage(msg) {
  const text = app.stringifyMessage(msg.content);
  if (text) { navigator.clipboard.writeText(text).catch(() => {}); }
}

function canConfirmPlan(msg) {
  return app.isTravelPlanMessage(msg.content);
}

function isPlanConfirmed(msg) {
  return confirmedPlanIds.value.includes(msg.id);
}

async function confirmThisPlan(msg) {
  const plan = await app.confirmPlan(msg);
  if (plan) {
    confirmedPlanIds.value.push(msg.id);
  }
}

function applyPrompt(prompt) { app.question.value = prompt; app.dismissWelcomeCard(); }
function handleComposerFocus() { app.dismissWelcomeCard(); }

async function handleSendChat(e) {
  if (!app.question.value.trim()) return;
  if (e?.target) {
    const rect = e.target.getBoundingClientRect();
    burstSparkles(rect.left + rect.width/2, rect.top + rect.height/2);
  }
  await app.sendChat();
  await pinFeedToBottom("smooth");
}

async function pinFeedToBottom(behavior = "auto") {
  await nextTick();
  if (!feedRef.value) return;
  feedRef.value.scrollTo({ top: feedRef.value.scrollHeight, behavior });
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
  async () => { await nextTick(); await pinFeedToBottom(); },
  { immediate: true }
);
watch(
  () => app.question.value,
  async () => { await nextTick(); syncComposerHeight(); },
  { immediate: true }
);

onMounted(async () => {
  if (app.state.token) app.dismissWelcomeCard();
  await nextTick(); syncComposerHeight(); await pinFeedToBottom();
});
</script>

<style scoped>
/* ── Chat container ── */
.chat-page {
  height: 100%;
  min-height: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: linear-gradient(175deg, #fefcfd 0%, #f8fafd 30%, #f0f7fc 70%, #fbfdfe 100%);
  position: relative;
}

/* ── Cherry blossom petal layer ── */
.petal-layer {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  z-index: 0;
}
.petal {
  position: absolute;
  top: -20px;
  border-radius: 50% 0 50% 0;
  background: linear-gradient(135deg, var(--sky), var(--ocean));
  animation: petal-fall linear infinite;
}
.petal::after {
  content: "";
  position: absolute;
  inset: 0;
  border-radius: inherit;
  background: inherit;
  animation: petal-sway 3s ease-in-out infinite;
}

/* ── Sparkle layer ── */
.sparkle-layer {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 3;
}

/* ── Chat Feed ── */
.chat-feed {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  position: relative;
  z-index: 1;
  padding: 8px 0 0;
}
.feed-pad { height: 8px; flex-shrink: 0; }

/* ── Welcome Screen ── */
.welcome-screen {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  text-align: center;
}

.welcome-icon-wrap {
  position: relative;
  margin-bottom: 28px;
}

.welcome-icon {
  width: 78px;
  height: 78px;
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--sky), var(--ocean), var(--azure));
  color: #ffffff;
  box-shadow: 0 8px 32px rgba(126, 200, 227, 0.35), 0 0 0 6px rgba(126, 200, 227, 0.10);
  animation: float-gentle 3.5s var(--ease-in-out) infinite, glow-pulse 3s ease-in-out infinite;
  overflow: hidden;
}
.welcome-ai-img { width: 100%; height: 100%; display: block; object-fit: cover; }

/* Orbit sparkles around the welcome icon */
.orbit-sparkle {
  position: absolute;
  font-size: 14px;
  color: var(--sky);
  animation: sparkle-twinkle 2s ease-in-out infinite;
  pointer-events: none;
}
.orbit-sparkle.s1 { top: -8px; right: -4px; animation-delay: 0s; color: var(--ocean); }
.orbit-sparkle.s2 { bottom: -6px; left: -6px; animation-delay: 0.7s; color: var(--azure); }
.orbit-sparkle.s3 { top: 50%; right: -14px; animation-delay: 1.4s; font-size: 10px; color: var(--sky); }

.welcome-title {
  margin: 0 0 6px;
  font-size: 28px;
  font-weight: 700;
  color: var(--label);
  line-height: 1.2;
  letter-spacing: -0.3px;
}

.welcome-desc {
  margin: 0 0 32px;
  color: var(--label-2);
  font-size: 15px;
  line-height: 1.45;
}

.prompt-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px;
  max-width: 480px;
  width: 100%;
}

.prompt-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px;
  border-radius: var(--r-xl);
  background: rgba(255,255,255,0.75);
  border: 1.5px solid rgba(126, 200, 227, 0.25);
  color: var(--label);
  font-size: 14px;
  line-height: 1.4;
  text-align: left;
  cursor: pointer;
  transition: all 0.3s var(--ease-spring);
  position: relative;
  overflow: hidden;
}
.prompt-card:hover {
  transform: translateY(-2px);
  border-color: var(--sky);
  box-shadow: 0 6px 20px rgba(126, 200, 227, 0.20);
}
.prompt-card:active {
  transform: scale(0.97);
  background: rgba(126, 200, 227, 0.08);
}

.prompt-shine {
  position: absolute;
  top: 0; left: -100%;
  width: 60%;
  height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent);
  transition: left 0.5s ease;
}
.prompt-card:hover .prompt-shine { left: 120%; }

.prompt-icon { font-size: 20px; flex-shrink: 0; }
.prompt-text { min-width: 0; }

/* Welcome fade */
.welcome-enter-active { transition: opacity 0.4s ease; }
.welcome-leave-active { transition: opacity 0.2s ease; }
.welcome-enter-from, .welcome-leave-to { opacity: 0; }

/* ── Message Row ── */
.message-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
  padding: 2px 14px;
  animation: msg-in 0.45s var(--ease-bounce) both;
}
.message-row.is-user { justify-content: flex-end; }
.message-row.is-system { justify-content: center; padding-top: 10px; padding-bottom: 10px; }

.system-bubble {
  padding: 6px 16px;
  border-radius: var(--r-full);
  background: rgba(74, 127, 191, 0.12);
  color: var(--label-2);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.45;
  max-width: 82%;
  text-align: center;
}

/* ── Avatar ── */
.msg-avatar { flex: 0 0 34px; align-self: flex-end; margin-bottom: 0; transition: opacity 0.2s ease; }
.msg-avatar.invisible { opacity: 0; }

.avatar-circle {
  width: 34px; height: 34px;
  border-radius: 50%;
  display: grid; place-items: center;
  font-size: 13px; font-weight: 600;
  overflow: hidden;
  box-shadow: 0 2px 6px rgba(61,48,85,0.08);
}
.avatar-circle img { width: 100%; height: 100%; display: block; object-fit: cover; }
.user-av { background: linear-gradient(135deg, var(--sky), var(--ocean)); color: #fff; }
.ai-av { background: linear-gradient(135deg, #e2eef8, #d8e6f4); color: #7b95b0; }

/* ── iMessage Bubbles (anime-kawaii) ── */
.bubble {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  padding: 10px 15px;
  font-size: 15px;
  line-height: 1.48;
  white-space: pre-wrap;
  word-break: break-word;
  max-width: 260px;
  position: relative;
}

.ai-bubble {
  background: linear-gradient(135deg, #f2f7fc, #e8f1f9);
  color: var(--label);
  border-radius: 20px 20px 20px 5px;
  box-shadow: 0 2px 8px rgba(61,48,85,0.05);
}
.ai-bubble.has-corner { padding-bottom: 26px; }
.ai-bubble::after {
  content: "";
  position: absolute;
  bottom: 0;
  left: -6px;
  width: 14px;
  height: 14px;
  background: #e8f1f9;
  clip-path: polygon(100% 0, 0% 100%, 100% 100%);
}

.user-bubble {
  background: linear-gradient(135deg, var(--sky), var(--ocean));
  color: #ffffff;
  border-radius: 20px 20px 5px 20px;
  box-shadow: 0 3px 10px rgba(126, 200, 227, 0.28);
}
.user-bubble::after {
  content: "";
  position: absolute;
  bottom: 0;
  right: -6px;
  width: 14px;
  height: 14px;
  background: var(--ocean);
  clip-path: polygon(0 0, 100% 100%, 0% 100%);
}

.rich-bubble { max-width: 320px; padding: 12px 14px; }
.rich-bubble::after { display: none; }

/* ── Bubble corner actions: confirm + copy/like/dislike ── */
.bubble-corner {
  position: absolute;
  bottom: 4px;
  right: 6px;
  display: flex;
  align-items: center;
  gap: 2px;
  z-index: 2;
}

.corner-confirm-btn {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 3px 8px;
  border: none;
  border-radius: 10px;
  background: rgba(74, 127, 191, 0.14);
  color: var(--ocean);
  font-size: 11px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s ease;
}
.corner-confirm-btn:hover {
  background: rgba(74, 127, 191, 0.26);
}
.corner-confirm-btn:active {
  transform: scale(0.94);
}

.corner-confirmed-tag {
  font-size: 10px;
  font-weight: 600;
  color: var(--ocean);
  white-space: nowrap;
  padding: 2px 6px;
  border-radius: 8px;
  background: rgba(74, 127, 191, 0.08);
}

/* ── Typing Dots ── */
.typing-dots { display: flex; gap: 4px; align-items: center; padding: 4px 2px; }
.typing-dots span {
  width: 7px; height: 7px; border-radius: 50%;
  background: linear-gradient(135deg, var(--sky), var(--ocean));
  animation: dot-bounce-anime 1.2s ease-in-out infinite;
}
.typing-dots span:nth-child(2) { animation-delay: 0.15s; }
.typing-dots span:nth-child(3) { animation-delay: 0.30s; }

@keyframes dot-bounce-anime {
  0%, 60%, 100% { opacity: 0.4; transform: scale(1); }
  30% { opacity: 1; transform: scale(1.3); }
}

/* ── Message Body ── */
.msg-body { max-width: 75%; min-width: 0; display: flex; flex-direction: column; }
.user-body { align-items: flex-end; }

/* ── Input Area ── */
.input-area {
  padding: 8px 12px 10px;
  position: relative;
  z-index: 2;
  border-top: 0.5px solid var(--hairline);
}

.input-bar {
  display: flex;
  align-items: flex-end;
  gap: 10px;
  background: rgba(255,255,255,0.85);
  border-radius: 26px;
  padding: 6px 6px 6px 16px;
  transition: all 0.25s var(--ease-ease);
  border: 2px solid rgba(126, 200, 227, 0.18);
}
.input-bar:focus-within {
  background: #ffffff;
  border-color: var(--sky);
  box-shadow: 0 0 0 5px rgba(126, 200, 227, 0.10);
}

.input-bar textarea {
  flex: 1;
  min-height: 24px;
  max-height: 140px;
  resize: none;
  border: none;
  outline: none;
  background: transparent;
  color: var(--label);
  font-size: 15px;
  line-height: 1.45;
  overflow-y: hidden;
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.input-bar textarea::-webkit-scrollbar { display: none; }
.input-bar textarea::placeholder { color: var(--label-3); }

.send-button {
  width: 38px; height: 38px;
  flex: 0 0 38px;
  display: grid; place-items: center;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--sky), var(--ocean));
  border: none;
  color: #ffffff;
  cursor: pointer;
  box-shadow: 0 3px 10px rgba(126, 200, 227, 0.3);
  transition: transform 0.22s var(--ease-spring), box-shadow 0.22s ease;
}
.send-button:active:not(:disabled) { transform: scale(0.85); }
.send-button:disabled { background: #c8d8e8; box-shadow: none; cursor: default; }

.send-spinner {
  width: 15px; height: 15px;
  border: 2px solid rgba(255,255,255,0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Message In ── */
@keyframes msg-in {
  from { opacity: 0; transform: translateY(12px) scale(0.92); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

/* ── Mobile ── */
@media (max-width: 520px) {
  .message-row { padding: 2px 10px; }
  .welcome-screen { padding: 32px 16px; }
  .welcome-title { font-size: 24px; }
  .prompt-grid { grid-template-columns: 1fr; }
  .input-area { padding: 6px 8px calc(8px + env(safe-area-inset-bottom, 0px)); }
}
</style>
