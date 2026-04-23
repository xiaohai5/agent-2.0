<template>
  <div class="travel-plan">
    <section v-if="recommendationSections.length" class="section">
      <article v-for="section in recommendationSections" :key="section.title" class="recommend-section">
        <div v-if="!isImageOnlySection(section.title)" class="section-head">
          <h3>{{ section.title }}</h3>
        </div>

        <div class="recommend-grid">
          <article v-for="item in section.items" :key="item.key" class="recommend-card">
            <strong class="recommend-title">{{ item.title || `${item.type}${item.index}` }}</strong>

            <div class="recommend-copy">
              <p v-if="item.address">地址：{{ item.address }}</p>
              <p v-if="item.reason">推荐原因：{{ item.reason }}</p>
              <p v-for="detail in item.details" :key="detail.label">{{ detail.label }}：{{ detail.value }}</p>
            </div>

            <a
              v-if="item.image && !item.image.failed"
              class="image-card"
              :href="item.image.url"
              target="_blank"
              rel="noreferrer"
            >
              <img
                :src="item.image.src"
                :alt="item.title || item.image.alt"
                loading="lazy"
                referrerpolicy="no-referrer"
                @error="handleImageError($event, item.image)"
              />
              <span>{{ item.title ? `${item.title} 图片` : item.image.alt }}</span>
            </a>

            <a
              v-else-if="item.image"
              class="image-link"
              :href="item.image.url"
              target="_blank"
              rel="noreferrer"
            >
              查看原图
            </a>
          </article>
        </div>
      </article>
    </section>

    <section v-if="standaloneImages.length && !recommendationSections.length" class="section">
      <div class="image-grid">
        <a
          v-for="(image, index) in standaloneImages"
          :key="`${image.url}-${index}`"
          class="image-card"
          :href="image.url"
          target="_blank"
          rel="noreferrer"
        >
          <img
            v-if="!image.failed"
            :src="image.src"
            :alt="image.alt || '推荐图片'"
            loading="lazy"
            referrerpolicy="no-referrer"
            @error="handleImageError($event, image)"
          />
          <span>{{ image.alt || "推荐图片" }}</span>
        </a>
      </div>
    </section>

    <p v-if="!recommendationSections.length && !standaloneImages.length" class="plain-text">{{ content }}</p>
  </div>
</template>

<script setup>
import { Capacitor } from "@capacitor/core";
import { computed } from "vue";

const props = defineProps({
  content: {
    type: String,
    default: "",
  },
});

const parsedContent = computed(() => parseRecommendationContent(props.content));
const recommendationSections = computed(() => parsedContent.value.sections);
const standaloneImages = computed(() => parsedContent.value.images);

function parseRecommendationContent(content) {
  const lines = String(content || "")
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  const sections = [];
  let currentSection = null;
  let currentItem = null;

  const ensureSection = (title) => {
    const normalizedTitle = title || "推荐";
    if (!currentSection || currentSection.title !== normalizedTitle) {
      currentSection = { title: normalizedTitle, items: [] };
      sections.push(currentSection);
    }
    return currentSection;
  };

  const flushItem = () => {
    if (!currentItem) return;
    normalizeItemTitle(currentItem);
    if (currentItem.title || currentItem.address || currentItem.reason || currentItem.image) {
      currentItem.key = `${currentItem.type}-${currentItem.index}-${currentItem.title || currentItem.address || currentItem.image?.url}`;
      ensureSection(currentItem.sectionTitle).items.push(currentItem);
    }
    currentItem = null;
  };

  for (const rawLine of lines) {
    const line = stripLeadingEmoji(rawLine);
    const itemMatch = line.match(/^(餐厅|酒店)\s*(\d+)/);
    const sectionMatch = line.match(/^(?:餐厅|餐饮|酒店|住宿)(?:推荐)?$/);

    if (itemMatch) {
      flushItem();
      const type = itemMatch[1];
      currentItem = {
        type,
        index: itemMatch[2],
        sectionTitle: type === "酒店" ? "酒店推荐" : "餐厅推荐",
        title: "",
        address: "",
        reason: "",
        details: [],
        image: null,
      };
      continue;
    }

    if (sectionMatch) {
      flushItem();
      ensureSection(line.endsWith("推荐") ? line : `${line}推荐`);
      continue;
    }

    const [label, value] = splitField(rawLine);
    const normalizedLabel = normalizeLabel(label);

    if (!currentItem && isNameLabel(normalizedLabel) && value) {
      const type = inferItemType(currentSection?.title);
      currentItem = {
        type,
        index: String((currentSection?.items.length || 0) + 1),
        sectionTitle: currentSection?.title || `${type}推荐`,
        title: value,
        address: "",
        reason: "",
        details: [],
        image: null,
      };
      ensureSection(currentItem.sectionTitle);
      continue;
    }

    if (!currentItem && extractImages(rawLine).length) {
      ensureSection("推荐");
      currentItem = {
        type: "推荐",
        index: String(currentSection.items.length + 1),
        sectionTitle: currentSection.title,
        title: "",
        address: "",
        reason: "",
        details: [],
        image: null,
      };
    }

    if (!currentItem) continue;

    if (isNameLabel(normalizedLabel)) {
      currentItem.title = value;
      continue;
    }

    if (isAddressLabel(normalizedLabel)) {
      currentItem.address = value;
      continue;
    }

    if (isReasonLabel(normalizedLabel)) {
      currentItem.reason = value;
      continue;
    }

    if (value && normalizedLabel !== "图片" && !isImageLabel(normalizedLabel)) {
      currentItem.details.push({ label, value });
      continue;
    }

    const images = extractImages(rawLine, currentItem.title || `${currentItem.type}${currentItem.index}`);
    if (images.length) {
      currentItem.image = images[0];
    }
  }

  flushItem();

  return {
    sections: sections.map((section) => ({
      ...section,
      items: section.items.filter((item) => item.title || item.address || item.reason || item.image).slice(0, 5),
    })).filter((section) => section.items.length),
    images: extractImages(content),
  };
}

function normalizeItemTitle(item) {
  const title = String(item.title || "").trim();
  const imageAlt = String(item.image?.alt || "").trim();
  const genericTitle = !title || /^(图片|推荐)\s*\d*$/i.test(title) || /^(图片|推荐)$/.test(title);
  const usefulAlt = imageAlt && !/^(图片|推荐图片)\s*\d*$/i.test(imageAlt);

  if (genericTitle && usefulAlt) {
    item.title = imageAlt;
  }
}

function inferItemType(sectionTitle = "") {
  const title = String(sectionTitle || "");
  if (/酒店|住宿/.test(title)) return "酒店";
  if (/餐厅|餐饮|美食/.test(title)) return "餐厅";
  return "推荐";
}

function isNameLabel(label) {
  return ["名称", "酒店名称", "餐厅名称", "名称或区域"].includes(label);
}

function isAddressLabel(label) {
  return ["地址", "位置"].includes(label);
}

function isReasonLabel(label) {
  return ["推荐原因", "推荐理由", "描述", "简介", "特色"].includes(label);
}

function isImageLabel(label) {
  return ["图片", "图片链接", "照片", "图", "photo", "image"].includes(label.toLowerCase());
}

function isImageOnlySection(title) {
  return /^(图片推荐|推荐图片)$/i.test(String(title || "").trim());
}

function stripLeadingEmoji(value) {
  return String(value || "")
    .replace(/^[\u{1F300}-\u{1FAFF}\u2600-\u27BF]\s*/u, "")
    .trim();
}

function splitField(line) {
  const cleanLine = stripLeadingEmoji(line);
  const match = cleanLine.match(/^([^:：]+)[:：]\s*(.*)$/);
  if (!match) return ["", ""];
  return [match[1].trim(), match[2].trim()];
}

function normalizeLabel(label) {
  return stripLeadingEmoji(label).replace(/\s+/g, "");
}

function extractImages(value, fallbackAlt = "推荐图片") {
  const text = String(value || "");
  const markdownMatches = Array.from(text.matchAll(/!\[([^\]]*)\]\((https?:\/\/[^)\s]+)\)/g)).map((match) => ({
    alt: match[1]?.trim() || fallbackAlt,
    url: normalizeImageUrl(match[2]?.trim()),
  }));

  if (markdownMatches.length) {
    return uniqueImages(markdownMatches);
  }

  const urls = Array.from(text.matchAll(/https?:\/\/[^\s)]+/g)).map((item) => item[0]);
  return uniqueImages(urls.map((url, index) => ({
    url: normalizeImageUrl(url),
    alt: index === 0 ? fallbackAlt : `${fallbackAlt} ${index + 1}`,
  })));
}

function normalizeImageUrl(url) {
  if (!url) return "";
  const normalized = String(url).trim();
  if (!isCompleteImageUrl(normalized)) return "";
  return normalized;
}

function isCompleteImageUrl(url) {
  try {
    const parsed = new URL(url);
    if (!["http:", "https:"].includes(parsed.protocol)) return false;
    if (!parsed.hostname.includes(".")) return false;
    return /\.[a-z0-9]{2,5}(?:[?#].*)?$/i.test(parsed.pathname) || /\/showpic\/[a-z0-9]+$/i.test(parsed.pathname);
  } catch {
    return false;
  }
}

function uniqueImages(images) {
  const seen = new Set();
  return images.map((image) => ({
    ...image,
    sources: buildImageSources(image.url),
    src: buildImageSources(image.url)[0] || image.url,
    sourceIndex: 0,
    failed: false,
  })).filter((image) => {
    if (!image.url || seen.has(image.url)) return false;
    seen.add(image.url);
    return true;
  });
}

function buildImageSources(url) {
  if (!url) return [];
  const proxyUrl = `${getApiBaseUrl()}/api/image-proxy?url=${encodeURIComponent(url)}`;
  return [proxyUrl, url];
}

function isAutonaviImageUrl(_url) {
  return false;
}

function getApiBaseUrl() {
  const configured = localStorage.getItem("agent_base_url") || import.meta.env.VITE_API_BASE_URL || "";
  if (configured) return configured.replace(/\/+$/, "");
  if (!Capacitor.isNativePlatform()) return "";
  if (Capacitor.getPlatform() === "android") return "http://10.0.2.2:8000";
  return "http://localhost:8000";
}

function handleImageError(event, image) {
  const nextIndex = Number(image.sourceIndex || 0) + 1;
  if (nextIndex < image.sources.length) {
    image.sourceIndex = nextIndex;
    image.src = image.sources[nextIndex];
    event.target.src = image.src;
    return;
  }

  image.failed = true;
}
</script>

<style scoped>
.travel-plan {
  width: 100%;
  display: grid;
  gap: 14px;
  white-space: normal;
}

.section,
.recommend-section {
  display: grid;
  gap: 10px;
}

.section-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.section-head h3 {
  margin: 0;
  font-size: 16px;
  font-weight: 800;
}

.recommend-grid {
  display: grid;
  gap: 0;
}

.recommend-card {
  display: grid;
  gap: 8px;
  padding: 12px 0;
  border-bottom: 1px solid rgba(221, 224, 230, 0.82);
  min-width: 0;
  overflow: hidden;
}

.recommend-card:first-child {
  padding-top: 0;
}

.recommend-card:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

.recommend-copy {
  display: grid;
  gap: 4px;
}

.recommend-title {
  color: #21232b;
  font-size: 18px;
  line-height: 1.5;
  font-weight: 900;
  word-break: break-word;
}

.recommend-copy p {
  margin: 0;
  color: #4f5565;
  font-size: 13px;
  line-height: 1.65;
}

.image-grid {
  display: grid;
  gap: 10px;
}

.image-card {
  display: grid;
  gap: 5px;
  color: inherit;
  text-decoration: none;
  width: min(100%, 280px);
  min-width: 0;
}

.image-card img {
  width: 100%;
  height: clamp(92px, 24vw, 150px);
  max-height: 24vh;
  display: block;
  border-radius: 12px;
  aspect-ratio: 16 / 9;
  object-fit: cover;
  background: rgba(239, 241, 245, 0.9);
}

.image-card span {
  color: #646b7a;
  font-size: 12px;
}

.image-link {
  width: fit-content;
  color: #4f67d8;
  font-size: 12px;
  text-decoration: none;
}

.plain-text {
  margin: 0;
  white-space: pre-wrap;
}

@media (max-width: 480px) {
  .recommend-card {
    padding: 10px 0;
  }

  .image-card img {
    height: clamp(86px, 30vw, 128px);
  }

  .recommend-title {
    font-size: 17px;
  }
}
</style>
