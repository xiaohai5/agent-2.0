# Agent 2.0

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white">
  <img alt="Vue 3" src="https://img.shields.io/badge/Vue_3-Frontend-4FC08D?logo=vuedotjs&logoColor=white">
  <img alt="Vite" src="https://img.shields.io/badge/Vite_6-Build-646CFF?logo=vite&logoColor=white">
  <img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-Agent_Orchestration-5B21B6">
  <img alt="ChromaDB" src="https://img.shields.io/badge/ChromaDB-Vector_Store-F97316">
  <img alt="Redis" src="https://img.shields.io/badge/Redis-Short_Memory-DC382D?logo=redis&logoColor=white">
  <img alt="MySQL" src="https://img.shields.io/badge/MySQL-8-4479A1?logo=mysql&logoColor=white">
  <img alt="Capacitor" src="https://img.shields.io/badge/Capacitor_7-Android-119EFF?logo=capacitor&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white">
</p>

Agent 2.0 是一个面向旅行生活服务与知识问答的智能助手。采用 **FastAPI** 后端 + **Vue 3 / Vite** 前端 + **MySQL + Redis + ChromaDB** 数据层，基于 **LangGraph** 双 Agent 工作流驱动对话，集成 **MCP 协议**（高德地图、12306 火车票）实现旅行规划、路线可视化与生活服务路由，同时支持文档上传解析、向量检索与轻量知识图谱（GraphRAG）问答。

## 功能概览

- **双 Agent 对话** — MemoryAgent（记忆管理）+ DialogAgent（对话生成），由 LangGraph StateGraph 编排四节点流程：记忆检索 → 工具准备 → 响应生成 → 记忆更新。
- **智能路由** — 基于 skill 的自动路由，将用户意图分类为：旅行规划、车票服务、酒店餐饮、知识库问答、通用聊天五个模块，按需加载参考文件。
- **MCP 工具集成** — 高德地图 MCP（POI 搜索、地理编码、驾车路线规划）与 12306 MCP（火车票查询、时刻表），支持工具调用链。
- **旅行规划与地图可视化** — AI 生成多日旅行计划，自动地理编码 + 最近邻排序优化路线，分段驾车路线计算与折线绘制，支持保存计划并在 MapView 上按天切换展示。
- **文档上传与 RAG** — 支持多种格式文档上传（Docling 解析），分块存入 ChromaDB 向量库，混合检索（向量 + BM25 关键词）+ 可选 BGE 重排序。
- **轻量知识图谱** — 从文档中抽取实体关系，构建 GraphRAG 索引，支持结构化知识检索。
- **用户系统** — 注册、登录、个人信息管理、密码修改，JWT Bearer 鉴权。
- **流式聊天** — 支持 SSE 流式输出聊天补全。
- **反馈收集与 DPO 导出** — 用户对回复打分/备注，支持导出 DPO 训练数据集（JSONL / JSON / CSV）。
- **图片代理** — 服务端代理外部图片（如高德 POI 图片），规避 WebView 混合内容与跨域问题。
- **Capacitor Android App** — Vue 3 前端通过 Capacitor 7 打包为原生 Android 应用，原生 HTTP 客户端规避 WebView CORS。
- **Docker Compose 一键部署** — 前端 Nginx + 后端 FastAPI + MySQL + Redis 四大服务编排。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | Python 3.11、FastAPI、Uvicorn |
| 异步 ORM | SQLAlchemy Async + aiomysql |
| 数据验证 | Pydantic v2 |
| 关系数据库 | MySQL 8 |
| 短期记忆 / 缓存 | Redis 7 |
| 向量存储 | ChromaDB |
| AI 工作流 | LangGraph、LangChain、langchain-openai |
| 工具协议 | MCP（langchain-mcp-adapters） |
| 文档解析 | Docling、Docling Core |
| 嵌入 / 重排序 | OpenAI Embeddings、FlagEmbedding（BGE-reranker-v2-m3、BGE-M3） |
| 深度学习 | PyTorch、Transformers |
| 前端框架 | Vue 3（Composition API）、Vue Router 4 |
| 构建工具 | Vite 6 |
| 移动端 | Capacitor 7（Android） |
| Web 服务器 | Nginx（前端静态资源 + API 反向代理） |
| 容器化 | Docker、Docker Compose |

## 项目结构

```text
.
├── backend/
│   └── app/
│       ├── agent/                  # 双 Agent 工作流（LangGraph）
│       │   ├── dual_agent_workflow.py   # StateGraph 编排
│       │   ├── dialog_agent.py          # 对话生成 + 工具调用
│       │   ├── memory_agent.py          # 长短期记忆管理
│       │   ├── memory_state.py          # 类型化状态定义
│       │   ├── tool_agents.py           # MCP 工具 Agent
│       │   ├── tools.py                 # LangChain Tool 封装
│       │   ├── skill_loader.py          # Skill 文件加载
│       │   └── models.py                # 模块类型枚举
│       ├── api/
│       │   ├── deps.py                  # FastAPI 依赖注入
│       │   └── routes/
│       │       ├── auth.py              # 认证（注册/登录/资料/密码）
│       │       ├── chat.py              # 聊天补全（标准 + SSE 流式）
│       │       ├── feedback.py          # 反馈收集 + DPO 导出
│       │       ├── map.py               # 高德地图代理 API
│       │       ├── saved_plan.py        # 旅行计划 CRUD
│       │       └── vector_store.py      # 文档上传/检索/GraphRAG
│       ├── core/
│       │   └── database.py              # 异步 SQLAlchemy 引擎
│       ├── crued/                       # 数据访问层
│       ├── memory/                      # 记忆管理模块
│       │   ├── manager.py               # 记忆管理器
│       │   ├── short_term.py            # Redis 短期记忆
│       │   ├── long_term.py             # Markdown 长期记忆
│       │   ├── redis_store.py           # Redis 存储封装
│       │   ├── retriever.py             # 记忆检索
│       │   ├── extractor.py             # 用户画像提取
│       │   └── schemas.py               # 记忆数据结构
│       ├── models/                      # SQLAlchemy ORM 模型
│       ├── schemas/                     # Pydantic 请求/响应 Schema
│       ├── services/                    # 业务逻辑层
│       │   ├── auth_service.py
│       │   ├── document_service.py
│       │   ├── dual_agent_service.py
│       │   ├── feedback_service.py
│       │   ├── graphrag_service.py
│       │   ├── kg_retriever.py          # 知识图谱检索
│       │   ├── route_service.py         # 路线规划与缓存
│       │   └── saved_plan_service.py
│       ├── utils/
│       └── main.py                      # FastAPI 应用入口
├── frontend/
│   ├── src/
│   │   ├── api/client.js               # HTTP 客户端（fetch + CapacitorHttp）
│   │   ├── components/                  # 通用组件
│   │   │   ├── AppShell.vue             # 应用壳（导航 + 布局）
│   │   │   ├── BottomTabBar.vue         # 底部标签栏
│   │   │   ├── IntroModal.vue           # 引导弹窗
│   │   │   ├── MessageActions.vue       # 消息操作按钮
│   │   │   ├── TravelPlanMessage.vue    # 旅行计划消息卡片
│   │   │   └── ...
│   │   ├── composables/                 # 组合式函数
│   │   │   └── useAssistantApp.js       # 助手应用核心逻辑
│   │   ├── views/                       # 页面视图
│   │   │   ├── AccountView.vue          # 登录
│   │   │   ├── RegisterView.vue         # 注册
│   │   │   ├── ChatView.vue             # 对话主页
│   │   │   ├── MapView.vue              # 地图路线展示
│   │   │   ├── PlansView.vue            # 旅行计划列表
│   │   │   ├── DocumentsView.vue        # 文档管理
│   │   │   ├── ProfileView.vue          # 个人资料
│   │   │   └── PasswordView.vue         # 修改密码
│   │   ├── router/index.js              # Vue Router 配置
│   │   ├── main.js
│   │   ├── App.vue
│   │   └── styles.css
│   ├── android/                         # Capacitor Android 工程
│   ├── deploy/nginx.conf                # 前端 Nginx 配置
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile                       # 多阶段构建（Node + Nginx）
├── llm/                                 # RAG / 检索模块
│   ├── llm.py                           # LLM 客户端初始化
│   ├── chunking.py                      # 文本分块
│   ├── load.py                          # 文档加载
│   ├── hybrid_retriever.py              # 混合检索（向量 + BM25）
│   ├── reranker.py                      # 交叉编码器重排序
│   └── get_res.py                       # RAG 服务入口
├── memory/                              # Agent 长期记忆（Markdown 文件）
├── skills/                              # Agent Skill 定义
│   └── travel-life-service-auto-router/ # 旅行生活自动路由
│       ├── SKILL.md                     # 路由规则 + 模块定义
│       └── references/                  # 各模块参考文件
├── tests/                               # 后端测试
├── docs/                                # 文档
│   ├── deploy-compose.md
│   └── android-webview-cors.md
├── compose.yaml                         # Docker Compose 编排
├── Dockerfile                           # 后端容器镜像
├── requirements.txt                     # Python 依赖
├── project_config.py                    # 运行时配置单点
├── main.py                              # 顶层 ASGI 入口
└── .env                                 # 环境变量（不入库）
```

## 本地开发

### 后端

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS / Linux
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

健康检查：

```text
http://127.0.0.1:8000/api/health
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

开发环境下，Vite 会将 `/api` 请求代理到 `http://127.0.0.1:8000`。

默认访问地址：

```text
http://127.0.0.1:5173
```

## 环境变量

后端根目录 `.env` 示例：

```env
# LLM
OPENAI_API_KEY=your-openai-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

# 数据库
ASYNC_DATABASE_URL=mysql+aiomysql://root:password@localhost:3306/agent?charset=utf8mb4
REDIS_URL=redis://localhost:6379/0

# MCP 工具
AMAP_MCP_URL=https://mcp.amap.com/mcp?key=your-amap-key
TICKET_MCP_COMMAND=npx
TICKET_MCP_ARGS=-y,12306-mcp

# ChromaDB
CHROMA_PERSIST_DIRECTORY=./chroma_db

# LangSmith（可选）
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=agent-2.0

# 代理（可选）
HTTP_PROXY=
HTTPS_PROXY=
```

前端 `.env.production` 示例：

```env
VITE_API_BASE_URL=https://your-domain.com
```

前后端通过同一域名部署且 Nginx 将 `/api` 转发到后端时，`VITE_API_BASE_URL` 可留空。

## Docker Compose 部署

复制环境变量模板：

```bash
cp .env.docker.example .env
```

编辑 `.env`，填写真实密钥和数据库密码，然后启动：

```bash
docker compose up -d --build
```

查看状态：

```bash
docker compose ps
docker compose logs -f backend
```

访问：

```text
http://your-server-ip
```

详细步骤见 [Docker Compose 部署文档](docs/deploy-compose.md)。

## Android App 构建

手机 App 基于 Capacitor 7 Android。构建前先配置正式 API 地址：

```env
# frontend/.env.production
VITE_API_BASE_URL=https://your-domain.com
```

然后执行：

```bash
cd frontend
npm install
npm run build
npx cap sync android
```

使用 Android Studio 打开 `frontend/android` 目录，可生成调试 APK 或签名后的 release APK / AAB。

注意：真机 App 不能使用 `http://127.0.0.1:8000` 作为后端地址，必须使用公网 IP 或域名。

## 常用 API

```text
GET   /api/health

# 认证
POST  /api/auth/register
POST  /api/auth/login
GET   /api/auth/profile
POST  /api/auth/change-password

# 聊天
POST  /api/chat/completion
POST  /api/chat/completion/stream

# 文档
GET   /api/vector-store/documents
POST  /api/vector-store/upload
POST  /api/vector-store/graphrag/summary

# 地图
POST  /api/map/poi/search
POST  /api/map/geocode
POST  /api/map/driving

# 旅行计划
GET   /api/saved-plans
POST  /api/saved-plans
GET   /api/saved-plans/{plan_id}
PUT   /api/saved-plans/{plan_id}
DELETE /api/saved-plans/{plan_id}

# 反馈
POST  /api/feedback
GET   /api/feedback/export
```

需要登录的接口请携带：

```text
Authorization: Bearer <access_token>
```

## 注意事项

- `.env`、`chroma_db/`、`backend/data/`、`frontend/dist/`、`node_modules/` 不应提交到 Git。
- 生产环境建议启用 HTTPS。
- 前后端分域部署时需要在后端 `main.py` 的 CORS 白名单中加上正式前端域名。
- Docker 部署时 MySQL、Redis、ChromaDB 和 memory 数据均通过 volume 持久化。
