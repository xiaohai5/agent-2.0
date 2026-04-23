<template>
  <section class="view-scroll">
    <article class="panel-card">
      <div class="panel-head">
        <div class="head-copy">
          <h2>文档中心</h2>
          <p>上传、管理并查看当前账户下的知识文档。</p>
        </div>
        <span class="panel-pill">docs</span>
      </div>

      <div class="tag-row">
        <span>统一响应</span>
        <span>Token 鉴权</span>
        <span>本地存储</span>
      </div>

      <label class="field">
        <span>上传文档</span>
        <input type="file" @change="app.pickFile" />
      </label>

      <div class="action-row">
        <button class="ghost" type="button" :disabled="app.loading.upload" @click="app.uploadDoc">
          {{ app.loading.upload ? "上传中..." : "上传文档" }}
        </button>
        <button class="ghost" type="button" @click="app.vectorize">查看检索范围</button>
      </div>

      <label class="field">
        <span>检索范围</span>
        <select v-model="app.scope.value">
          <option value="当前登录用户文档">当前登录用户文档</option>
          <option value="最近上传文档">最近上传文档</option>
          <option value="全部已索引文档">全部已索引文档</option>
        </select>
      </label>

      <div class="action-row">
        <button class="primary" type="button" :disabled="app.loading.docs" @click="app.fetchDocs">
          {{ app.loading.docs ? "刷新中..." : "查看文档列表" }}
        </button>
      </div>

      <div class="status-box">{{ app.chatStatus.value }}</div>
    </article>

    <article class="panel-card">
      <div class="panel-head">
        <div class="head-copy">
          <h2>文档列表</h2>
          <p>向下滑动查看当前接口返回的文档内容。</p>
        </div>
        <span class="panel-pill">list</span>
      </div>

      <div v-if="!app.docs.value.length" class="status-box">登录后即可查看当前账户下的文档列表。</div>

      <div v-else class="doc-list">
        <div v-for="doc in app.docs.value" :key="`${doc.id}-${doc.filename}`" class="doc-item">
          <div class="doc-copy">
            <strong>{{ app.stringifyMessage(doc.filename) }}</strong>
            <small>#{{ doc.id }} · {{ app.stringifyMessage(doc.status) }}</small>
          </div>
          <button class="danger" type="button" :disabled="app.loading.docs" @click="app.deleteDoc(doc.filename)">删除</button>
        </div>
      </div>
    </article>
  </section>
</template>

<script setup>
import { onMounted } from "vue";
import { useAssistantApp } from "../composables/useAssistantApp";

const app = useAssistantApp();

onMounted(() => {
  if (app.state.token && !app.docsLoaded.value) {
    app.fetchDocs();
  }
});
</script>

<style scoped>
.view-scroll { height: 100%; min-height: 0; overflow-y: auto; padding: 0 18px calc(18px + env(safe-area-inset-bottom, 0px)); display: grid; gap: 14px; align-content: start; }
.panel-card { padding: 20px; border-radius: 30px; border: 1px solid var(--card-border); background: var(--card-bg); box-shadow: var(--surface-shadow); }
.panel-head { display: flex; justify-content: space-between; gap: 12px; margin-bottom: 16px; align-items: flex-start; }
.head-copy { flex: 1; }
.panel-head h2 { margin: 0; font-size: 22px; letter-spacing: -0.02em; }
.panel-head p { margin: 8px 0 0; color: var(--text-secondary); font-size: 13px; line-height: 1.8; letter-spacing: 0.01em; }
.panel-pill { height: fit-content; padding: 8px 12px; border-radius: 999px; background: rgba(255, 255, 255, 0.78); color: var(--text-secondary); font-size: 11px; font-weight: 800; letter-spacing: 0.08em; text-transform: uppercase; }
.tag-row { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px; }
.tag-row span { padding: 8px 10px; border-radius: 14px; background: rgba(255, 255, 255, 0.74); color: var(--text-secondary); font-size: 12px; font-weight: 700; letter-spacing: 0.04em; }
.field { display: grid; gap: 8px; color: var(--text-secondary); font-size: 12px; font-weight: 700; letter-spacing: 0.04em; margin-bottom: 12px; }
.field input, .field select { width: 100%; padding: 14px 16px; border-radius: 20px; border: 1px solid rgba(200, 200, 207, 0.72); background: rgba(255, 255, 255, 0.92); color: var(--text-main); outline: none; line-height: 1.6; }
.action-row { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 12px; }
.primary, .ghost, .danger { padding: 12px 18px; border-radius: 999px; cursor: pointer; letter-spacing: 0.04em; }
.primary, .danger { color: #fff; font-weight: 800; background: linear-gradient(180deg, var(--button-dark-start), var(--button-dark-end)); }
.ghost { background: rgba(255, 255, 255, 0.9); border: 1px solid var(--card-border); color: var(--text-main); font-weight: 700; }
.status-box { padding: 14px 16px; border-radius: 20px; background: rgba(255, 255, 255, 0.9); border: 1px solid var(--card-border); color: var(--text-secondary); font-size: 14px; line-height: 1.8; white-space: pre-wrap; }
.doc-list { display: grid; gap: 10px; }
.doc-item { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 14px 16px; border-radius: 20px; background: rgba(255, 255, 255, 0.9); border: 1px solid var(--card-border); }
.doc-copy { min-width: 0; }
.doc-item strong { display: block; font-size: 14px; line-height: 1.7; letter-spacing: 0.01em; word-break: break-word; }
.doc-item small { display: block; margin-top: 4px; color: var(--text-secondary); font-size: 12px; line-height: 1.6; letter-spacing: 0.03em; word-break: break-word; }
</style>
