import { computed, reactive, ref, watch } from "vue";
import { Capacitor } from "@capacitor/core";
import { createApiClient } from "../api/client";

const DEFAULT_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";
const INTRO_KEY = "agent_intro_acknowledged";
const INITIAL_SYSTEM_MESSAGE =
  "叮咚，您的私人出行小助手已上线。\n查车票、排路线、找酒店、挖美食都可以交给我。";

function getDefaultBaseUrl() {
  if (DEFAULT_BASE_URL) return DEFAULT_BASE_URL;
  if (!Capacitor.isNativePlatform()) return "";
  if (Capacitor.getPlatform() === "android") return "http://10.0.2.2:8000";
  return "http://localhost:8000";
}

function getInitialBaseUrl() {
  const defaultBaseUrl = getDefaultBaseUrl();
  if (DEFAULT_BASE_URL) {
    localStorage.setItem("agent_base_url", defaultBaseUrl);
    return defaultBaseUrl;
  }
  return localStorage.getItem("agent_base_url") || defaultBaseUrl;
}

function normalizeText(value, fallback = "") {
  if (value == null) return fallback;
  if (typeof value === "string") return value || fallback;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (Array.isArray(value)) return value.map((item) => normalizeText(item, "")).filter(Boolean).join("\n");

  if (typeof value === "object") {
    if (typeof value.content === "string") return value.content || fallback;
    if (typeof value.answer === "string") return value.answer || fallback;
    if (typeof value.message === "string") return value.message || fallback;
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return fallback;
    }
  }

  return fallback;
}

function createId(prefix) {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return `${prefix}-${crypto.randomUUID()}`;
  }
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function createChatMessage(role, content, metadata = {}) {
  return {
    id: metadata.id || createId(role === "assistant" ? "msg_ai" : role === "user" ? "msg_user" : "msg_system"),
    role,
    content: normalizeText(content, ""),
    conversation_id: metadata.conversation_id || "",
    route: metadata.route || "chat",
    model: metadata.model || null,
    tool_calls: metadata.tool_calls ?? null,
    answer_source: metadata.answer_source ?? null,
    user_message: metadata.user_message || "",
    feedback_type: metadata.feedback_type || "",
    feedbackLoading: false,
  };
}

function normalizeDoc(doc, index = 0) {
  return {
    id: doc?.id ?? index,
    filename: normalizeText(doc?.filename, "未命名文档"),
    status: normalizeText(doc?.status, "未知状态"),
  };
}

const state = reactive({
  token: localStorage.getItem("agent_token") || "",
  username: localStorage.getItem("agent_username") || "",
  history: [],
});

const profileData = reactive({
  name: localStorage.getItem("agent_profile_name") || "",
  username: localStorage.getItem("agent_profile_username") || localStorage.getItem("agent_username") || "",
  password: localStorage.getItem("agent_profile_password") || "",
  email: localStorage.getItem("agent_profile_email") || "",
});

const menuOpen = ref(false);
const introVisible = ref(localStorage.getItem(INTRO_KEY) !== "1");
const thinking = ref(false);
const showWelcomeCard = ref(true);
const baseUrl = ref(getInitialBaseUrl());
const chatMode = ref("stream");
const topK = ref(3);
const scope = ref("当前登录用户文档");
const question = ref("");
const chatStatus = ref("准备就绪，登录后即可上传文档并开始问答。");
const authStatus = ref(state.token ? `已恢复登录状态：${state.username || "当前用户"}` : "请先注册或登录账户。");
const profile = ref("个人信息尚未刷新。");
const profileLoaded = ref(false);
const docsLoaded = ref(false);
const loading = reactive({
  auth: false,
  profile: false,
  password: false,
  docs: false,
  upload: false,
  chat: false,
});
const login = reactive({ username: "", password: "" });
const register = reactive({ username: "", email: "", password: "" });
const pwd = reactive({ username: state.username || "", old_password: "", new_password: "", confirm_password: "" });
const docs = ref([]);
const file = ref(null);
const prompts = ["总结已上传文档", "根据文档回答问题", "给出下一步建议"];
const conversationId = ref(createId("conv"));
const messages = ref([createChatMessage("system", INITIAL_SYSTEM_MESSAGE, { conversation_id: conversationId.value })]);
const TYPEWRITER_BATCH_SIZE = 3;
const TYPEWRITER_DELAY_MS = 14;

const client = createApiClient(() => baseUrl.value, () => state.token);
const sent = computed(() => messages.value.some((item) => item.role === "user"));
const tokenText = computed(() => (state.token ? `Bearer ${state.token}` : "尚未登录"));

watch(baseUrl, (value) => {
  localStorage.setItem("agent_base_url", value);
});

function saveAuth(token, username) {
  state.token = token || "";
  state.username = username || "";
  pwd.username = username || "";
  profileData.username = username || "";
  localStorage.setItem("agent_token", state.token);
  localStorage.setItem("agent_username", state.username);
}

function saveProfileData(data = {}) {
  profileData.name = normalizeText(data.name || data.nickname || data.full_name || data.username, "");
  profileData.username = normalizeText(data.username || data.account || state.username, "");
  profileData.email = normalizeText(data.email, "");
  localStorage.setItem("agent_profile_name", profileData.name);
  localStorage.setItem("agent_profile_username", profileData.username);
  localStorage.setItem("agent_profile_email", profileData.email);
}

function savePasswordText(password = "") {
  profileData.password = normalizeText(password, "");
  localStorage.setItem("agent_profile_password", profileData.password);
}

function appendMessage(role, content, metadata = {}) {
  const message = createChatMessage(role, content, {
    conversation_id: conversationId.value,
    ...metadata,
  });
  messages.value.push(message);
  return message;
}

function dismissWelcomeCard() {
  showWelcomeCard.value = false;
}

function toggleMenu() {
  menuOpen.value = !menuOpen.value;
}

function closeMenu() {
  menuOpen.value = false;
}

function acknowledgeIntro() {
  introVisible.value = false;
  localStorage.setItem(INTRO_KEY, "1");
}

async function doLogin() {
  const username = login.username.trim();
  const password = login.password.trim();
  if (!username || !password) {
    authStatus.value = "请输入用户名和密码后再登录。";
    return;
  }

  authStatus.value = "正在登录...";
  loading.auth = true;
  try {
    const data = await client.request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    saveAuth(data?.access_token, data?.username);
    savePasswordText(password);
    authStatus.value = `登录成功，当前用户：${normalizeText(data?.username, "未命名用户")}`;
    chatStatus.value = "登录成功，正在进入对话页...";
    await getProfile();
    showWelcomeCard.value = false;
  } catch (error) {
    authStatus.value = `登录失败：${error.message}`;
  } finally {
    loading.auth = false;
  }
}

async function doRegister() {
  loading.auth = true;
  try {
    const data = await client.request("/api/auth/register", {
      method: "POST",
      body: JSON.stringify(register),
    });
    saveAuth(data?.access_token, data?.username);
    login.username = register.username;
    login.password = register.password;
    savePasswordText(register.password);
    authStatus.value = `注册成功，已自动登录：${normalizeText(data?.username, "未命名用户")}`;
    chatStatus.value = "注册完成，正在进入对话页...";
    await getProfile();
    showWelcomeCard.value = false;
  } catch (error) {
    authStatus.value = `注册失败：${error.message}`;
  } finally {
    loading.auth = false;
  }
}

async function getProfile() {
  loading.profile = true;
  try {
    const data = await client.request("/api/auth/profile", {
      method: "GET",
      json: false,
    });
    saveProfileData(data || {});
    profile.value = "个人信息已更新。";
    pwd.username = normalizeText(data?.username, pwd.username);
    profileLoaded.value = true;
    authStatus.value = "个人资料获取成功。";
  } catch (error) {
    profile.value = `获取失败：${error.message}`;
    authStatus.value = `个人资料获取失败：${error.message}`;
  } finally {
    loading.profile = false;
  }
}

async function changePassword() {
  if (pwd.new_password !== pwd.confirm_password) {
    authStatus.value = "两次输入的新密码不一致。";
    return;
  }

  loading.password = true;
  try {
    const data = await client.request("/api/auth/change-password", {
      method: "POST",
      body: JSON.stringify(pwd),
    });
    savePasswordText(pwd.new_password);
    authStatus.value = normalizeText(data?.message, "密码修改成功。");
  } catch (error) {
    authStatus.value = `密码修改失败：${error.message}`;
  } finally {
    loading.password = false;
  }
}

function logout() {
  saveAuth("", "");
  profile.value = "个人信息尚未刷新。";
  profileLoaded.value = false;
  docsLoaded.value = false;
  docs.value = [];
  state.history = [];
  profileData.name = "";
  profileData.username = "";
  profileData.password = "";
  profileData.email = "";
  localStorage.removeItem("agent_profile_name");
  localStorage.removeItem("agent_profile_username");
  localStorage.removeItem("agent_profile_password");
  localStorage.removeItem("agent_profile_email");
  conversationId.value = createId("conv");
  messages.value = [createChatMessage("system", "已退出登录。重新登录后可以继续上传文档和发起对话。", { conversation_id: conversationId.value })];
  authStatus.value = "登录状态已清空。";
  chatStatus.value = "已退出登录。";
  closeMenu();
}

function pickFile(event) {
  file.value = event.target.files?.[0] || null;
  if (file.value) {
    chatStatus.value = `已选择文件：${normalizeText(file.value.name, "未命名文件")}`;
  }
}

async function fetchDocs() {
  loading.docs = true;
  try {
    const data = await client.request("/api/vector-store/documents", {
      method: "GET",
      json: false,
    });
    docs.value = Array.isArray(data) ? data.map(normalizeDoc) : [];
    docsLoaded.value = true;
    chatStatus.value = `文档列表已刷新，共 ${docs.value.length} 个文件。`;
  } catch (error) {
    docs.value = [];
    chatStatus.value = `文档列表获取失败：${error.message}`;
  } finally {
    loading.docs = false;
  }
}

async function uploadDoc() {
  if (!file.value) {
    chatStatus.value = "请先选择一个要上传的文件。";
    return;
  }

  loading.upload = true;
  const formData = new FormData();
  formData.append("file", file.value);

  try {
    const data = await client.upload("/api/vector-store/upload", formData);
    chatStatus.value = `文档上传成功：${normalizeText(data?.filename, file.value.name)}，状态：${normalizeText(data?.status, "已接收")}`;
    file.value = null;
    await fetchDocs();
  } catch (error) {
    chatStatus.value = `文档上传失败：${error.message}`;
  } finally {
    loading.upload = false;
  }
}

async function deleteDoc(name) {
  loading.docs = true;
  try {
    await client.request(`/api/vector-store/documents?filename=${encodeURIComponent(name)}`, {
      method: "DELETE",
      json: false,
    });
    chatStatus.value = `文档已删除：${normalizeText(name, "未知文档")}`;
    await fetchDocs();
  } catch (error) {
    chatStatus.value = `文档删除失败：${error.message}`;
    loading.docs = false;
  }
}

function vectorize() {
  chatStatus.value = `当前检索范围：${scope.value}。上传完成后会自动建立可检索索引。`;
}

function normalizeHistory(history) {
  return (Array.isArray(history) ? history : [])
    .map((item) => createChatMessage(item?.role, item?.content))
    .filter((item) => item.role && item.content);
}

function getPreviousUserMessage(message) {
  if (message?.user_message) return message.user_message;
  const index = messages.value.findIndex((item) => item.id === message?.id);
  for (let i = index - 1; i >= 0; i -= 1) {
    if (messages.value[i]?.role === "user") return normalizeText(messages.value[i].content, "");
  }
  return "";
}

async function submitFeedback(message, feedbackType) {
  if (!message || message.role !== "assistant" || message.streaming || message.feedbackLoading) return;
  if (!state.token) {
    chatStatus.value = "请先登录，再提交反馈。";
    return;
  }

  const userMessage = getPreviousUserMessage(message);
  const aiMessage = normalizeText(message.content, "");
  if (!userMessage || !aiMessage) return;

  message.feedbackLoading = true;
  try {
    const data = await client.request("/api/feedback", {
      method: "POST",
      body: JSON.stringify({
        conversation_id: message.conversation_id || conversationId.value,
        message_id: message.id,
        user_message: userMessage,
        ai_message: aiMessage,
        feedback_type: feedbackType,
        route: message.route || "chat",
        model: message.model || null,
        tool_calls: message.tool_calls || null,
        answer_source: message.answer_source || null,
      }),
    });
    message.feedback_type = data?.feedback_type || feedbackType;
    chatStatus.value = "反馈已保存。";
  } catch (error) {
    chatStatus.value = `反馈保存失败：${error.message}`;
  } finally {
    message.feedbackLoading = false;
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function typewriterMessage(message, text) {
  const chars = Array.from(normalizeText(text, ""));
  message.content = "";

  for (let index = 0; index < chars.length; index += TYPEWRITER_BATCH_SIZE) {
    message.content += chars.slice(index, index + TYPEWRITER_BATCH_SIZE).join("");
    await sleep(TYPEWRITER_DELAY_MS);
  }
}

async function sendChat() {
  const currentQuestion = question.value.trim();
  if (!currentQuestion) {
    chatStatus.value = "请输入问题后再发送。";
    return;
  }
  if (!state.token) {
    chatStatus.value = "请先登录，再发起对话。";
    return;
  }

  dismissWelcomeCard();
  loading.chat = true;
  thinking.value = chatMode.value !== "stream";
  appendMessage("user", currentQuestion);
  question.value = "";
  chatStatus.value = "AI 正在整理上下文并生成回复...";

  const payload = {
    question: currentQuestion,
    top_k: Number(topK.value || 3),
    history: normalizeHistory(state.history),
    conversation_id: conversationId.value,
  };

  try {
    if (chatMode.value === "stream") {
      await sendStream(payload);
    } else {
      const data = await client.request("/api/chat/completion", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      state.history = normalizeHistory(data?.history);
      appendMessage("assistant", data?.answer || "后端未返回内容。", {
        conversation_id: data?.conversation_id || conversationId.value,
        user_message: currentQuestion,
        route: data?.route || "chat",
        model: data?.model || null,
        tool_calls: data?.tool_calls || null,
        answer_source: data?.answer_source || null,
      });
      chatStatus.value = "本轮对话已完成。";
    }
  } catch (error) {
    appendMessage("assistant", `请求失败：${error.message}`, {
      user_message: currentQuestion,
      route: "chat",
    });
    chatStatus.value = `对话失败：${error.message}`;
  } finally {
    thinking.value = false;
    loading.chat = false;
  }
}

async function sendStream(payload) {
  const streamMessage = reactive(createChatMessage("assistant", "", {
    conversation_id: conversationId.value,
    user_message: payload.question,
  }));
  streamMessage.streaming = true;
  messages.value.push(streamMessage);

  try {
    await client.stream("/api/chat/completion/stream", payload, {
      onStatus(message) {
        chatStatus.value = `处理中：${normalizeText(message, "")}`;
      },
      onChunk(content) {
        streamMessage.content += normalizeText(content, "");
      },
      async onDone(data) {
        const answer = normalizeText(data?.answer, streamMessage.content || "后端未返回内容。");
        await typewriterMessage(streamMessage, answer);
        state.history = normalizeHistory(data?.history);
        streamMessage.conversation_id = data?.conversation_id || streamMessage.conversation_id;
        streamMessage.route = data?.route || "chat";
        streamMessage.model = data?.model || null;
        streamMessage.tool_calls = data?.tool_calls || null;
        streamMessage.answer_source = data?.answer_source || null;
        streamMessage.streaming = false;
        chatStatus.value = "流式回复已完成。";
      },
    });
    streamMessage.streaming = false;
  } catch (error) {
    streamMessage.streaming = false;
    if (!streamMessage.content.trim()) {
      messages.value = messages.value.filter((item) => item !== streamMessage);
    }
    throw error;
  }
}

function clearChat() {
  state.history = [];
  conversationId.value = createId("conv");
  messages.value = [createChatMessage("system", "本地对话历史已清空。新的问题会从空上下文开始。", { conversation_id: conversationId.value })];
  chatStatus.value = "对话历史已清空。";
}

const instance = {
  state,
  profileData,
  menuOpen,
  introVisible,
  thinking,
  showWelcomeCard,
  baseUrl,
  chatMode,
  topK,
  scope,
  question,
  chatStatus,
  authStatus,
  profile,
  profileLoaded,
  docsLoaded,
  loading,
  login,
  register,
  pwd,
  docs,
  prompts,
  conversationId,
  messages,
  sent,
  tokenText,
  stringifyMessage: normalizeText,
  dismissWelcomeCard,
  toggleMenu,
  closeMenu,
  acknowledgeIntro,
  doLogin,
  doRegister,
  getProfile,
  changePassword,
  logout,
  pickFile,
  fetchDocs,
  uploadDoc,
  deleteDoc,
  vectorize,
  sendChat,
  submitFeedback,
  clearChat,
};

export function useAssistantApp() {
  return instance;
}
