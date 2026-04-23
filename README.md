# Agent 2.0

Agent 2.0 是一个面向旅行与生活服务场景的智能助手项目，包含 FastAPI 后端、Vue 3 前端、MySQL 持久化、Chroma 向量库、GraphRAG 文档处理、双 Agent 对话工作流以及移动端 Capacitor 集成。

项目后端负责用户认证、文档上传与知识库检索、对话生成、用户长期记忆、反馈采集和 DPO 数据导出；前端提供账号管理、聊天、文档管理和移动端适配界面。

## 系统架构

```mermaid
flowchart LR
    User["用户<br/>Web / Android"] --> Frontend["前端应用<br/>Vue 3 + Vite + Capacitor"]

    Frontend -->|"REST API / NDJSON Stream"| Backend["FastAPI 后端"]

    subgraph API["API 接口层"]
        AuthAPI["Auth API<br/>注册 / 登录 / 用户资料 / 改密"]
        ChatAPI["Chat API<br/>普通对话 / 流式对话"]
        VectorAPI["Vector Store API<br/>上传 / 列表 / 删除 / 图谱摘要"]
        FeedbackAPI["Feedback API<br/>反馈 / 训练数据导出 / DPO 导出"]
        ImageProxy["Image Proxy API"]
    end

    Backend --> AuthAPI
    Backend --> ChatAPI
    Backend --> VectorAPI
    Backend --> FeedbackAPI
    Backend --> ImageProxy

    subgraph Services["业务服务层"]
        AuthService["AuthService<br/>用户认证"]
        ChatService["DualAgentChatService<br/>双 Agent 对话服务"]
        DocService["DocumentService<br/>文档处理"]
        GraphService["GraphRAGService<br/>图谱抽取"]
        FeedbackService["FeedbackService<br/>反馈与数据集导出"]
    end

    AuthAPI --> AuthService
    ChatAPI --> ChatService
    VectorAPI --> DocService
    VectorAPI --> GraphService
    FeedbackAPI --> FeedbackService

    subgraph Agent["Agent 智能体层"]
        Workflow["DualAgentWorkflow"]
        MemoryAgent["MemoryAgent<br/>长期记忆"]
        DialogAgent["DialogAgent<br/>对话生成"]
        SkillLoader["Skill Loader<br/>技能加载"]
        ToolAgents["Tool Agents<br/>工具调用"]
    end

    ChatService --> Workflow
    Workflow --> MemoryAgent
    Workflow --> DialogAgent
    DialogAgent --> SkillLoader
    DialogAgent --> ToolAgents

    subgraph Skills["旅行生活服务技能"]
        Travel["旅行规划"]
        Ticket["火车票服务"]
        Hotel["酒店餐饮推荐"]
        RagSkill["知识库问答"]
        General["通用聊天"]
    end

    SkillLoader --> Travel
    SkillLoader --> Ticket
    SkillLoader --> Hotel
    SkillLoader --> RagSkill
    SkillLoader --> General

    subgraph ModelTools["模型 / RAG / 外部工具"]
        LLM["OpenAI Compatible LLM"]
        Embedding["Embedding Model"]
        LangGraph["LangGraph"]
        LangChain["LangChain"]
        Docling["Docling 文档解析"]
        Retriever["Hybrid Retriever<br/>向量检索 + BM25"]
        Reranker["Reranker 重排"]
        AMap["高德 AMap MCP"]
        Train12306["12306 MCP"]
    end

    DialogAgent --> LLM
    Workflow --> LangGraph
    DialogAgent --> LangChain
    ToolAgents --> AMap
    ToolAgents --> Train12306
    RagSkill --> Retriever
    Retriever --> Reranker
    DocService --> Docling
    Docling --> Embedding
    Embedding --> Retriever

    subgraph Data["数据持久化层"]
        MySQL[("MySQL<br/>用户 / Token / 用户记忆<br/>文档记录 / 反馈 / GraphRAG 图谱数据")]
        Chroma[("ChromaDB<br/>知识库向量")]
        Files["backend/data<br/>上传文件 / 应用状态"]
        MD5["md5.txt<br/>文档去重"]
    end

    AuthService --> MySQL
    MemoryAgent <--> MySQL
    DocService --> MySQL
    DocService --> Files
    DocService --> MD5
    GraphService --> MySQL
    FeedbackService --> MySQL
    Retriever <--> Chroma
    Embedding --> Chroma
```

## 核心功能

- 用户系统：支持注册、登录、个人资料获取、修改密码，认证方式为 `Bearer Token`。
- 智能对话：通过 `MemoryAgent + DialogAgent` 双 Agent 工作流生成回答，并将用户记忆持久化到 MySQL。
- 旅行生活服务：内置 `travel-life-service-auto-router` 技能，可覆盖旅行规划、火车票服务、酒店餐饮推荐、知识问答和通用聊天。
- RAG 知识库：支持上传文档，使用 Docling 切分解析、Embedding、Chroma 向量存储、BM25/向量混合召回和重排。
- GraphRAG：文档上传后可生成语义块、实体、关系，并提供图谱摘要接口。
- 反馈闭环：支持对 AI 回复点赞/点踩，并导出训练数据或 DPO 数据集。
- 前端与移动端：Vue 3 + Vite Web 应用，配套 Capacitor Android 工程。

## 技术栈

- 后端：Python、FastAPI、SQLAlchemy Async、Pydantic、Uvicorn
- 数据库：MySQL、ChromaDB
- Agent 与 LLM：LangGraph、LangChain、LangChain OpenAI、LangChain MCP Adapters
- 文档与检索：Docling、Chroma、BM25、FlagEmbedding、Transformers、Torch
- 前端：Vue 3、Vue Router、Vite
- 移动端：Capacitor Android

## 项目结构

```text
.
├── backend/
│   └── app/
│       ├── agent/              # 双 Agent 工作流、记忆 Agent、对话 Agent、工具封装
│       ├── api/
│       │   ├── deps.py         # 登录态依赖与鉴权
│       │   └── routes/         # auth / chat / vector-store / feedback 路由
│       ├── core/               # 数据库初始化与会话
│       ├── crued/              # 数据访问层
│       ├── models/             # SQLAlchemy 模型
│       ├── schemas/            # Pydantic 请求与响应模型
│       ├── services/           # 认证、文档、对话、反馈、GraphRAG 服务
│       └── main.py             # FastAPI 应用入口
├── frontend/
│   ├── android/                # Capacitor Android 工程
│   ├── src/
│   │   ├── api/                # API 客户端
│   │   ├── components/         # 页面组件
│   │   ├── composables/        # 前端业务状态与逻辑
│   │   ├── router/             # Vue Router
│   │   └── views/              # 登录、注册、聊天、文档、账号页面
│   ├── package.json
│   └── vite.config.js
├── llm/                        # 文档切分、知识库、检索、重排和 LLM 相关模块
├── skills/
│   └── travel-life-service-auto-router/
│       ├── SKILL.md
│       └── references/         # 旅行规划、车票、餐饮酒店、RAG、通用聊天参考规则
├── tests/                      # Agent 工作流与记忆相关测试
├── chroma_db/                  # 本地向量库运行时数据，通常不提交
├── backend/data/               # 上传文件和应用状态运行时数据，通常不提交
├── main.py                     # 根入口，导出 backend.app.main:app
├── project_config.py           # 项目运行配置
└── requirements.txt            # Python 依赖
```

## 环境要求

- Python 3.11 或更高版本
- Node.js 18 或更高版本
- MySQL 8.x
- 可访问的 OpenAI 兼容 API
- 如需本地重排模型，建议准备可用 GPU；没有 GPU 时需要调整 `project_config.py` 中的 rerank 设备配置
- 如需 Android 打包，需要 Android Studio 与 JDK

## 后端启动

1. 创建并激活 Python 虚拟环境。

```bash
python -m venv .venv
.venv\Scripts\activate
```

2. 安装后端依赖。

```bash
pip install -r requirements.txt
```

3. 创建 MySQL 数据库。

```sql
CREATE DATABASE agent CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

4. 修改 `project_config.py` 中的运行配置。

至少需要确认以下配置：

- `openai_api_key`：OpenAI 或兼容服务的 API Key
- `openai_base_url`：OpenAI 兼容接口地址
- `llm_model`：对话模型名称
- `embedding_model`：Embedding 模型名称
- `async_database_url`：MySQL 异步连接地址，例如 `mysql+aiomysql://root:123456@localhost:3306/agent?charset=utf8mb4`
- `chroma_persist_directory`：Chroma 向量库目录，默认 `./chroma_db`
- `amap_mcp_url`：高德 MCP 地址，用于地图、POI 等旅行生活服务
- `ticket_mcp_command` / `ticket_mcp_args`：12306 MCP 工具启动配置
- `http_proxy` / `https_proxy` / `all_proxy` / `no_proxy`：按需设置代理

注意：当前配置文件中包含本地开发用的密钥字段。正式提交或部署前，建议改为环境变量或私有配置文件管理，避免密钥泄露。

5. 启动后端服务。

```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

也可以使用根入口启动。

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

6. 检查服务状态。

```text
http://127.0.0.1:8000/api/health
```

## 前端启动

1. 安装依赖。

```bash
cd frontend
npm install
```

2. 本地开发启动。

```bash
npm run dev
```

默认访问地址：

```text
http://127.0.0.1:5173
```

3. 配置 API 地址。

浏览器本地开发时，`frontend/.env.example` 中的 `VITE_API_BASE_URL` 可以留空，并通过 Vite 代理访问后端。

Android 或远程后端调试时，复制 `.env.example` 为 `.env`，并设置后端地址：

```env
VITE_API_BASE_URL=http://192.168.1.10:8000
```

4. 构建前端。

```bash
npm run build
```

## Android 调试

同步 Capacitor 工程：

```bash
cd frontend
npm run cap:sync
```

构建并打开 Android 工程：

```bash
npm run cap:android
```

使用移动端实时调试：

```bash
npm run dev:mobile
npm run android:live
```

`android:live` 默认使用 `http://10.0.2.2:5173`，适合 Android 模拟器访问宿主机 Vite 服务。

## API 概览

### 健康检查

```text
GET /
GET /api/health
GET /api/image-proxy?url=<image_url>
```

### 用户认证

```text
POST /api/auth/register
POST /api/auth/login
GET  /api/auth/profile
POST /api/auth/change-password
```

除注册和登录外，接口需要请求头：

```text
Authorization: Bearer <access_token>
```

### 智能对话

```text
POST /api/chat/completion
POST /api/chat/completion/stream
```

请求体示例：

```json
{
  "question": "帮我规划一个两天的杭州旅行",
  "top_k": 5,
  "history": [],
  "conversation_id": "demo-conversation"
}
```

流式接口返回 `application/x-ndjson`，事件类型包含 `status`、`chunk`、`done`、`error`。

### 文档知识库

```text
POST   /api/vector-store/upload
GET    /api/vector-store/documents
GET    /api/vector-store/graph?filename=<filename>
DELETE /api/vector-store/documents?filename=<filename>
```

上传接口使用 `multipart/form-data`，字段名为 `file`。

### 用户反馈

```text
POST /api/feedback
```

请求体示例：

```json
{
  "conversation_id": "demo-conversation",
  "message_id": "assistant-message-id",
  "user_message": "用户原始问题",
  "ai_message": "AI 回复内容",
  "feedback_type": "like",
  "route": "chat",
  "model": "gpt-4o-mini",
  "tool_calls": null,
  "answer_source": null
}
```

`feedback_type` 支持 `like` 和 `dislike`。

### 反馈导出

导出全部反馈：

```text
GET /api/feedback/export/all?format=csv
GET /api/feedback/export/all?format=json
GET /api/feedback/export/all?feedback_type=like&format=csv
GET /api/feedback/export/all?feedback_type=dislike&format=csv
```

导出 DPO 数据集：

```text
GET /api/feedback/export/dpo?format=jsonl
GET /api/feedback/export/dpo?format=json
GET /api/feedback/export/dpo?format=csv
```

JSONL 下载示例：

```bash
curl "http://127.0.0.1:8000/api/feedback/export/dpo?format=jsonl" -o dpo_feedback_dataset.jsonl
```

DPO 数据结构示例：

```json
{
  "prompt": "用户问题",
  "chosen": "更优回答",
  "rejected": "较差回答",
  "chosen_messages": [
    {"role": "user", "content": "用户问题"},
    {"role": "assistant", "content": "更优回答"}
  ],
  "rejected_messages": [
    {"role": "user", "content": "用户问题"},
    {"role": "assistant", "content": "较差回答"}
  ],
  "metadata": {}
}
```

## 数据表

应用启动时会通过 `Base.metadata.create_all` 自动创建数据表。当前主要表包括：

- `users`：用户账号信息
- `user_tokens`：登录 Token
- `user_memory`：用户长期记忆状态
- `document_items`：上传文档记录
- `message_feedback`：AI 回复反馈与训练数据来源
- GraphRAG 相关表：语义块、实体、关系等图谱数据

## 测试与检查

编译检查后端代码：

```bash
python -m compileall backend\app
```

运行测试：

```bash
pytest
```

构建前端：

```bash
cd frontend
npm run build
```

## 运行时目录与版本控制

以下目录或文件属于运行时数据、依赖或构建产物，已经在 `.gitignore` 中排除，通常不应提交：

- `chroma_db/`
- `backend/data/`
- `frontend/node_modules/`
- `frontend/dist/`
- `frontend/android/**/build/`
- `__pycache__/`
- `md5.txt`

如果需要迁移知识库或上传文件数据，请单独备份 `chroma_db/` 和 `backend/data/`。

## 常见问题

### 后端启动时报数据库连接失败

请确认 MySQL 已启动，数据库 `agent` 已创建，并检查 `project_config.py` 中的 `async_database_url` 用户名、密码、端口和数据库名是否正确。

### 上传文档或检索很慢

文档解析、Embedding、重排模型加载和 Chroma 写入都可能耗时。大文件上传时可关注 `upload_timeout_seconds`，如果没有 GPU，也可以关闭重排或将 `rerank_device` 调整为 CPU。

### 前端请求后端失败

请确认后端运行在 `http://127.0.0.1:8000`，浏览器开发时检查 Vite 代理配置；Android 真机调试时不要使用 `127.0.0.1` 指向电脑，需要改为电脑在局域网中的 IP 地址。

### MCP 工具不可用

高德和 12306 工具依赖 `project_config.py` 中的 MCP 配置以及本机网络环境。若工具不可用，对话主流程仍可运行，但实时地图、POI、车票信息能力会受影响。
