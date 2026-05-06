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
  avatarUrl: localStorage.getItem("agent_profile_avatar") || "",
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
const chatStatus = ref("");
const authStatus = ref(state.token ? "已登录" : "");
const profile = ref("");
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
const travelPois = ref([]);
const savedPlans = ref([]);
const activeRoutePlan = ref(null);
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

function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result || "");
    reader.onerror = () => reject(reader.error || new Error("Failed to read image."));
    reader.readAsDataURL(file);
  });
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error("Failed to load image."));
    image.src = src;
  });
}

async function resizeAvatarDataUrl(dataUrl) {
  const image = await loadImage(dataUrl);
  const size = 320;
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  if (!context) return dataUrl;

  canvas.width = size;
  canvas.height = size;
  const sourceSize = Math.min(image.naturalWidth || image.width, image.naturalHeight || image.height);
  const sourceX = ((image.naturalWidth || image.width) - sourceSize) / 2;
  const sourceY = ((image.naturalHeight || image.height) - sourceSize) / 2;
  context.drawImage(image, sourceX, sourceY, sourceSize, sourceSize, 0, 0, size, size);
  return canvas.toDataURL("image/jpeg", 0.86);
}

async function setUserAvatarFromFile(file) {
  if (!file || !file.type?.startsWith("image/")) return;

  try {
    const dataUrl = await readFileAsDataUrl(file);
    profileData.avatarUrl = await resizeAvatarDataUrl(dataUrl);
    localStorage.setItem("agent_profile_avatar", profileData.avatarUrl);
    profile.value = "头像已更新。";
  } catch (error) {
    profile.value = `头像更新失败：${error.message}`;
  }
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
  if (!username || !password) return;

  authStatus.value = "";
  loading.auth = true;
  try {
    const data = await client.request("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
    saveAuth(data?.access_token, data?.username);
    savePasswordText(password);
    authStatus.value = "";
    await getProfile();
    showWelcomeCard.value = false;
  } catch (error) {
    authStatus.value = error.message;
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
    authStatus.value = "";
    await getProfile();
    showWelcomeCard.value = false;
  } catch (error) {
    authStatus.value = error.message;
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
  } catch (error) {
    profile.value = `获取失败：${error.message}`;
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
    authStatus.value = "密码修改成功";
  } catch (error) {
    authStatus.value = error.message;
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
  profileData.avatarUrl = "";
  localStorage.removeItem("agent_profile_name");
  localStorage.removeItem("agent_profile_username");
  localStorage.removeItem("agent_profile_password");
  localStorage.removeItem("agent_profile_email");
  localStorage.removeItem("agent_profile_avatar");
  conversationId.value = createId("conv");
  messages.value = [createChatMessage("system", "已退出登录。", { conversation_id: conversationId.value })];
  authStatus.value = "";
  closeMenu();
}

function pickFile(event) {
  file.value = event.target.files?.[0] || null;
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
  } catch (error) {
    docs.value = [];
  } finally {
    loading.docs = false;
  }
}

async function uploadDoc() {
  if (!file.value) return;

  loading.upload = true;
  const formData = new FormData();
  formData.append("file", file.value);

  try {
    await client.upload("/api/vector-store/upload", formData);
    file.value = null;
    await fetchDocs();
  } catch (error) {
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
    await fetchDocs();
  } catch (error) {
    loading.docs = false;
  }
}

function vectorize() {}

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
  if (!state.token) return;

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
  } catch (_error) {
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
  if (!currentQuestion) return;
  if (!state.token) return;

  dismissWelcomeCard();
  loading.chat = true;
  thinking.value = chatMode.value !== "stream";
  appendMessage("user", currentQuestion);
  question.value = "";

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
      travelPois.value = data?.pois || [];
      appendMessage("assistant", data?.answer || "后端未返回内容。", {
        conversation_id: data?.conversation_id || conversationId.value,
        user_message: currentQuestion,
        route: data?.route || "chat",
        model: data?.model || null,
        tool_calls: data?.tool_calls || null,
        answer_source: data?.answer_source || null,
      });
    }
  } catch (error) {
    appendMessage("assistant", `请求失败：${error.message}`, {
      user_message: currentQuestion,
      route: "chat",
    });
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
      onStatus(_message) {},
      onChunk(content) {
        streamMessage.content += normalizeText(content, "");
      },
      async onDone(data) {
        const answer = normalizeText(data?.answer, streamMessage.content || "后端未返回内容。");
        await typewriterMessage(streamMessage, answer);
        state.history = normalizeHistory(data?.history);
        travelPois.value = data?.pois || [];
        streamMessage.conversation_id = data?.conversation_id || streamMessage.conversation_id;
        streamMessage.route = data?.route || "chat";
        streamMessage.model = data?.model || null;
        streamMessage.tool_calls = data?.tool_calls || null;
        streamMessage.answer_source = data?.answer_source || null;
        streamMessage.streaming = false;
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
  messages.value = [createChatMessage("system", "对话历史已清空。", { conversation_id: conversationId.value })];
}

// ── Travel Plan ──

const TRANSPORT_KEYS = ["地铁", "公交", "火车", "高铁", "动车", "飞机", "航班", "打车", "出租", "网约车", "步行", "骑行", "开车", "自驾", "大巴", "客运", "轮渡", "船", "磁悬浮", "机场大巴", "摆渡车", "班车"];
const DINING_KEYS = ["餐厅", "饭店", "美食", "小吃", "食堂", "饭馆", "火锅", "烧烤", "海鲜", "面馆", "快餐", "咖啡", "奶茶", "早餐", "午餐", "晚餐", "吃饭", "用餐", "就餐", "品尝", "美食街", "夜市", "大排档", "自助餐"];
const HOTEL_KEYS = ["酒店", "宾馆", "旅馆", "民宿", "客栈", "入住", "住宿", "青旅", "度假村", "公寓", "下榻"];
const ATTRACTION_KEYS = ["景点", "公园", "广场", "博物馆", "长城", "故宫", "寺庙", "塔", "湖", "山", "游览", "参观", "观光", "拍照", "打卡", "逛街", "购物", "老街", "胡同", "园林", "遗址", "演出", "表演"];

function detectItemType(text) {
  const t = text || "";
  if (HOTEL_KEYS.some((k) => t.includes(k))) return "hotel";
  if (TRANSPORT_KEYS.some((k) => t.includes(k))) return "transport";
  if (DINING_KEYS.some((k) => t.includes(k))) return "dining";
  if (ATTRACTION_KEYS.some((k) => t.includes(k))) return "attraction";
  return "general";
}

function stripMarkdown(line) {
  return line
    .replace(/^[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE00}-\u{FEFF}\u{200D}\u{20E3}\u{2702}-\u{27B0}\u{2B50}\u{2934}-\u{2935}\u{25AA}-\u{25FE}\u{2B05}-\u{2B07}\u{2B1B}-\u{2B1C}\u{3030}\u{303D}\u{3297}\u{3299}]\s*/u, "")
    .replace(/^#{1,4}\s*/, "")
    .replace(/^[-*•]\s*/, "")
    .replace(/^\d+[.、]\s*/, "")
    .replace(/^\*\*/, "")
    .replace(/\*\*$/, "")
    .trim();
}

function parseTravelPlanFromText(rawText) {
  const text = String(rawText || "");
  const lines = text.split(/\r?\n/);

  const days = [];
  let currentDay = null;
  let overviewLines = [];
  let inOverview = true;

  const dayHeaderRe = /^第\s*([一二三四五六七八九十\d]+)\s*天\s*(?:[：:]\s*(.*))?/;
  const dayHeaderRe2 = /^Day\s*(\d+)\s*[：:]\s*(.*)/i;
  const timeRe = /^(\d{1,2}:\d{2})(?:\s*[-–—]\s*(\d{1,2}:\d{2}))?\s*(.*)/;
  const roughTimeRe = /^(早晨|上午|中午|下午|傍晚|晚上|夜间|半夜|凌晨)\s*[：:]?\s*(.*)/;
const activityRe = /^(午餐建议|晚餐建议|早餐建议|住宿|交通方式|购物推荐|娱乐推荐|夜宵建议)\s*[：:]?\s*(.*)/;

  function flushDay() {
    if (!currentDay) return;
    if (currentDay.items.length === 0) {
      const note = currentDay.notes.join(" ").trim();
      if (note) {
        currentDay.items.push({ time: "", type: "general", description: note });
      }
    }
    days.push(currentDay);
    currentDay = null;
  }

  function startDay(dayNum, title) {
    flushDay();
    currentDay = { day: dayNum, title: title || `第${dayNum}天`, items: [], notes: [] };
  }

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;

    const cleanLine = stripMarkdown(line);

    // Skip header/footer sections
    if (/^(?:#{1,4}\s*)?(?:行程总览|推荐车次|出行提醒|温馨提示|费用预算|行程预算|注意事项|小贴士|旅行小贴士)/.test(line) || /^(?:#{1,4}\s*)?(?:行程总览|推荐车次|出行提醒|温馨提示|费用预算|行程预算|注意事项|小贴士|旅行小贴士)/.test(cleanLine)) {
      const isOverview = /行程总览/.test(cleanLine) || /推荐车次/.test(cleanLine);
      inOverview = isOverview;
      // 出行提醒之后的内容不再加入行程
      if (/出行提醒|温馨提示|注意事项|小贴士|旅行小贴士/.test(cleanLine)) {
        inOverview = true;
        continue;
      }
      if (!isOverview) continue;
      overviewLines.push(cleanLine);
      continue;
    }

    const dayMatch = cleanLine.match(dayHeaderRe) || cleanLine.match(dayHeaderRe2);
    if (dayMatch) {
      inOverview = false;
      const dayNum = parseInt(dayMatch[1]) || parseChineseNumber(dayMatch[1]) || (days.length + 1);
      const title = dayMatch[2] || `第${dayNum}天`;
      startDay(dayNum, title);
      continue;
    }

    if (inOverview) {
      overviewLines.push(cleanLine);
      continue;
    }

    if (!currentDay) {
      startDay(days.length + 1, `第${days.length + 1}天`);
    }

    const timeMatch = cleanLine.match(timeRe);
    if (timeMatch) {
      const time = timeMatch[1];
      const endTime = timeMatch[2] || "";
      const desc = (timeMatch[3] || "").trim().replace(/^[：:]\s*/, "");
      const type = detectItemType(desc);
      currentDay.items.push({ time, endTime, type, description: desc });
      continue;
    }

    const roughMatch = cleanLine.match(roughTimeRe);
    if (roughMatch) {
      const time = roughMatch[1];
      const desc = (roughMatch[2] || "").trim().replace(/^[：:]\s*/, "");
      const type = detectItemType(desc);
      currentDay.items.push({ time, endTime: "", type, description: desc });
      continue;
    }

    const actMatch = cleanLine.match(activityRe);
    if (actMatch) {
      const time = actMatch[1];
      const desc = (actMatch[2] || "").trim().replace(/^[：:]\s*/, "");
      const type = detectItemType(time + desc);
      currentDay.items.push({ time, endTime: "", type, description: desc });
      continue;
    }

    // Generic Label：Value pattern (e.g., "景点间交通：地铁2号线")
    const genericMatch = cleanLine.match(/^(.{2,12}?)[：:]\s*(.+)$/);
    if (genericMatch && genericMatch[2].length >= 2) {
      const label = genericMatch[1];
      const value = genericMatch[2];
      const type = detectItemType(label + value);
      currentDay.items.push({ time: label, endTime: "", type, description: value });
      continue;
    }

    currentDay.notes.push(cleanLine);
  }

  flushDay();

  let title = "出行计划";
  for (const line of overviewLines) {
    const m = line.match(/^(.{1,30})(?:：|:)\s*(.+)/);
    if (m && m[1].length <= 12) {
      title = m[1].replace(/^[🍜🏨🎯🚗✈️📍🗺️]\s*/, "");
      break;
    }
  }
  if (title === "出行计划" && overviewLines.length > 0) {
    title = overviewLines[0].replace(/^[🍜🏨🎯🚗✈️📍🗺️]\s*/, "").slice(0, 40);
  }

  return { title, days, overview: overviewLines.join("\n") };
}

function parseChineseNumber(str) {
  const map = { "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10 };
  if (str === "十") return 10;
  if (str.length === 2 && str[0] === "十") return 10 + (map[str[1]] || 0);
  if (str.length === 2 && str[1] === "十") return (map[str[0]] || 1) * 10;
  return map[str] || null;
}
function isTravelPlanMessage(content) {
  const text = normalizeText(content, "");
  if (!text || text.length < 30) return false;
  const hasDayStructure = /第\s*[一二三四五六七八九十\d]+\s*天/.test(text) || /Day\s*\d+/i.test(text);
  const hasTripKeywords = /行程|旅行|旅游|出游|攻略|路线/.test(text);
  const hasTimeSchedule = /\d{1,2}:\d{2}/.test(text);
  return hasDayStructure || (hasTripKeywords && hasTimeSchedule);
}

function setActiveRoute(plan) {
  activeRoutePlan.value = plan ? { ...plan } : null;
}

async function loadRoutes(planId, days) {
  if (!state.token) return null;
  const path = days && days.length
    ? `/api/plans/${planId}/routes?days=${days.join(",")}`
    : `/api/plans/${planId}/routes`;
  const data = await client.request(path, { method: "GET" });
  return data || null;
}

async function confirmPlan(message) {
  if (!message) return null;
  const rawText = normalizeText(message.content, "");
  if (!rawText) return null;

  const plan = parseTravelPlanFromText(rawText);
  if (!plan.days.length) return null;

  // Persist to backend
  if (state.token) {
    try {
      const data = await client.request("/api/plans", {
        method: "POST",
        body: JSON.stringify({
          title: plan.title,
          days: plan.days,
          overview: plan.overview,
          source_message_id: message.id,
        }),
      });
      const saved = data;
      if (saved) {
        const newPlan = {
          id: saved.id,
          title: saved.title,
          createdAt: saved.created_at || saved.createdAt || new Date().toISOString(),
          sourceMessageId: saved.source_message_id || message.id,
          days: saved.plan_data?.days || plan.days,
          overview: saved.plan_data?.overview || saved.overview || plan.overview,
        };
        savedPlans.value = [newPlan, ...savedPlans.value];
        return newPlan;
      }
    } catch (_) {
      // Fall back to local-only if API fails
    }
  }

  // Local fallback
  const newPlan = {
    id: createId("plan"),
    title: plan.title,
    createdAt: new Date().toISOString(),
    sourceMessageId: message.id,
    days: plan.days,
    overview: plan.overview,
  };
  savedPlans.value = [newPlan, ...savedPlans.value];
  return newPlan;
}

async function fetchPlans() {
  if (!state.token) return;
  try {
    const data = await client.request("/api/plans", { method: "GET" });
    const plans = data?.plans || [];
    savedPlans.value = plans.map((p) => ({
      id: p.id,
      title: p.title,
      createdAt: p.created_at || p.createdAt || "",
      sourceMessageId: p.source_message_id || "",
      days: p.plan_data?.days || [],
      overview: p.plan_data?.overview || p.overview || "",
    }));
  } catch (_) {
    // Keep local plans if fetch fails
  }
}

async function removePlanApi(planId) {
  if (activeRoutePlan.value?.id === planId) activeRoutePlan.value = null;

  // Remove from backend
  if (state.token) {
    try {
      await client.request(`/api/plans/${planId}`, { method: "DELETE" });
    } catch (_) {}
  }

  // Remove from local state
  const idx = savedPlans.value.findIndex((p) => p.id === planId);
  if (idx >= 0) savedPlans.value.splice(idx, 1);
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
  travelPois,
  savedPlans,
  activeRoutePlan,
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
  setUserAvatarFromFile,
  logout,
  pickFile,
  fetchDocs,
  uploadDoc,
  deleteDoc,
  vectorize,
  sendChat,
  submitFeedback,
  clearChat,
  isTravelPlanMessage,
  confirmPlan,
  fetchPlans,
  removePlanApi,
  setActiveRoute,
  loadRoutes,
};

export function useAssistantApp() {
  return instance;
}
