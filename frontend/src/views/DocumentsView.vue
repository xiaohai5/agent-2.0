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
          <IosButton variant="secondary" @click="app.vectorize">查看检索范围</IosButton>
        </div>

        <IosField label="检索范围">
          <select v-model="app.scope.value">
            <option value="当前登录用户文档">当前登录用户文档</option>
            <option value="最近上传文档">最近上传文档</option>
            <option value="全部已索引文档">全部已索引文档</option>
          </select>
        </IosField>

        <IosButton :disabled="app.loading.docs" @click="app.fetchDocs">
          {{ app.loading.docs ? "刷新中..." : "查看文档列表" }}
        </IosButton>

        <div class="ios-status">{{ app.chatStatus.value }}</div>
      </div>
    </PagePanel>

    <PagePanel title="文档列表" description="下方展示接口返回的文档状态，可直接删除。" eyebrow="List">
      <div v-if="!app.docs.value.length" class="empty-state">
        <span>▤</span>
        <strong>暂无文档</strong>
        <p>登录后上传文档，或点击刷新查看当前账户的文档列表。</p>
      </div>

      <div v-else class="doc-list">
        <div v-for="doc in app.docs.value" :key="`${doc.id}-${doc.filename}`" class="doc-item">
          <div class="doc-icon">DOC</div>
          <div class="doc-copy">
            <strong>{{ app.stringifyMessage(doc.filename) }}</strong>
            <small>#{{ doc.id }} · {{ app.stringifyMessage(doc.status) }}</small>
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
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.tag-row span {
  padding: 6px 10px;
  border-radius: 8px;
  background: #f3f4f6;
  color: #6b7280;
  font-size: 12px;
  font-weight: 600;
}

.form-stack {
  display: grid;
  gap: 13px;
}

.empty-state {
  min-height: 170px;
  display: grid;
  place-items: center;
  align-content: center;
  gap: 8px;
  padding: 24px;
  border-radius: 14px;
  background: #f9fafb;
  text-align: center;
}

.empty-state span {
  color: #d1d5db;
  font-size: 30px;
}

.empty-state strong {
  font-size: 17px;
  color: #1f2937;
}

.empty-state p {
  max-width: 280px;
  margin: 0;
  color: #6b7280;
  font-size: 13px;
  line-height: 1.65;
}

.doc-list {
  display: grid;
  gap: 10px;
}

.doc-item {
  display: grid;
  grid-template-columns: 44px 1fr auto;
  align-items: center;
  gap: 10px;
  padding: 12px;
  border-radius: 12px;
  border: 1px solid rgba(0, 0, 0, 0.06);
  background: #fff;
}

.doc-icon {
  width: 44px;
  height: 44px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  color: #fff;
  background: #1c1c1e;
  font-size: 11px;
  font-weight: 700;
}

.doc-copy {
  min-width: 0;
}

.doc-copy strong,
.doc-copy small {
  display: block;
  overflow-wrap: anywhere;
}

.doc-copy strong {
  font-size: 14px;
  line-height: 1.45;
  color: #1f2937;
}

.doc-copy small {
  margin-top: 4px;
  color: #6b7280;
  font-size: 12px;
}

@media (max-width: 420px) {
  .doc-item {
    grid-template-columns: 40px 1fr;
  }

  .doc-item :deep(.ios-button) {
    grid-column: 1 / -1;
    width: 100%;
  }
}
</style>
