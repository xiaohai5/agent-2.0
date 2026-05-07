<template>
  <section class="ios-page ios-page-stack ios-scroll">
    <PagePanel title="文档中心" description="上传、索引并管理当前账户下的知识文档。" eyebrow="Docs">
      <div class="tag-row">
        <span>Token 鉴权</span>
        <span>自动索引</span>
        <span>问答检索</span>
      </div>

      <div class="form-stack">
        <IosField label="上传文档">
          <input type="file" @change="app.pickFile" />
        </IosField>

        <div class="ios-action-row">
          <IosButton :disabled="app.loading.upload" @click="app.uploadDoc">
            {{ app.loading.upload ? "上传中..." : "上传文档" }}
          </IosButton>
        </div>

        <IosButton :disabled="app.loading.docs" @click="app.fetchDocs">
          {{ app.loading.docs ? "刷新中..." : "查看文档列表" }}
        </IosButton>
      </div>
    </PagePanel>

    <PagePanel title="文档列表" description="下方展示当前账户的文档，可直接删除。" eyebrow="List">
      <div v-if="!app.docs.value.length" class="empty-state">
        <div class="empty-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
        </div>
        <strong>暂无文档</strong>
        <p>登录后上传文档，或点击刷新查看当前账户的文档列表。</p>
      </div>

      <div v-else class="doc-list">
        <div v-for="doc in app.docs.value" :key="`${doc.id}-${doc.filename}`" class="doc-item">
          <div class="doc-icon">DOC</div>
          <div class="doc-copy">
            <strong>{{ app.stringifyMessage(doc.filename) }}</strong>
            <small>#{{ doc.id }} &middot; {{ app.stringifyMessage(doc.status) }}</small>
          </div>
          <IosButton variant="danger" :disabled="app.loading.docs" @click="app.deleteDoc(doc.filename)">删除</IosButton>
        </div>
      </div>
    </PagePanel>
  </section>
</template>

<script setup>
import { onMounted } from "vue";
import IosButton from "../components/IosButton.vue";
import IosField from "../components/IosField.vue";
import PagePanel from "../components/PagePanel.vue";
import { useAssistantApp } from "../composables/useAssistantApp";

const app = useAssistantApp();

onMounted(() => {
  if (app.state.token && !app.docsLoaded.value) {
    app.fetchDocs();
  }
});
</script>

<style scoped>
.tag-row { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }
.tag-row span {
  padding: 5px 10px;
  border-radius: var(--r-full);
  background: var(--fill-3);
  color: var(--label-2);
  font-size: 12px;
  font-weight: 600;
}
.form-stack { display: grid; gap: 14px; }

.empty-state {
  min-height: 170px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  padding: 28px 24px;
  border-radius: var(--r-lg);
  background: var(--bg-2);
  text-align: center;
}
.empty-icon { color: #c7c7cc; }
.empty-state strong { font-size: 17px; font-weight: 600; color: var(--label); }
.empty-state p { max-width: 280px; margin: 0; color: var(--label-2); font-size: 13px; line-height: 1.55; }

.doc-list { display: grid; gap: 10px; }
.doc-item {
  display: grid;
  grid-template-columns: 44px 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid var(--hairline);
  background: #ffffff;
}
.doc-icon {
  width: 44px; height: 44px;
  display: grid; place-items: center;
  border-radius: 10px;
  color: #ffffff; background: #1c1c1e;
  font-size: 11px; font-weight: 700;
}
.doc-copy { min-width: 0; }
.doc-copy strong, .doc-copy small { display: block; overflow-wrap: anywhere; }
.doc-copy strong { font-size: 14px; font-weight: 600; line-height: 1.45; color: var(--label); }
.doc-copy small { margin-top: 4px; color: var(--label-2); font-size: 12px; }

@media (max-width: 420px) {
  .doc-item { grid-template-columns: 40px 1fr; }
  .doc-item :deep(.ios-button) { grid-column: 1 / -1; width: 100%; }
}
</style>
