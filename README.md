# Agent 2.0

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white">
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white">
  <img alt="Vue" src="https://img.shields.io/badge/Vue_3-Frontend-42B883?logo=vuedotjs&logoColor=white">
  <img alt="LangGraph" src="https://img.shields.io/badge/LangGraph-Agent_Workflow-5B21B6">
  <img alt="GraphRAG" src="https://img.shields.io/badge/GraphRAG-Knowledge_Graph-F97316">
</p>

Agent 2.0 是一个面向旅行生活服务与知识问答的智能助手项目。项目采用 FastAPI 后端、Vue 3 + Vite 前端、MySQL 数据库、Redis 短期记忆、Chroma 向量库，并集成 LangGraph、LangChain、GraphRAG、Docling 和 Capacitor Android。

## 功能概览

- 用户注册、登录、资料管理和密码修改。
- `MemoryAgent + DialogAgent` 双 Agent 对话流程。
- Redis 短期记忆和 Markdown 长期记忆。
- 文档上传、解析、向量化、检索和知识库问答。
- 旅行规划、酒店餐饮推荐、车票服务等生活服务路由。
- 支持流式聊天接口。
- Vue 3 Web 前端和 Capacitor Android App。
- Docker Compose 一键部署前端、后端、MySQL 和 Redis。

## 技术栈

- 后端：Python 3.11、FastAPI、Uvicorn、SQLAlchemy Async、Pydantic。
- 数据存储：MySQL 8、Redis、ChromaDB。
- AI/RAG：LangGraph、LangChain、langchain-openai、Docling、FlagEmbedding、Transformers、Torch。
- 前端：Vue 3、Vue Router、Vite。
- 移动端：Capacitor Android。
- 部署：Docker、Docker Compose、Nginx。

## 项目结构

```text
.
├── backend/
│   └── app/
│       ├── agent/              # Agent 对话与记忆逻辑
│       ├── api/                # FastAPI 路由
│       ├── core/               # 数据库等核心配置
│       ├── crued/              # 数据访问层
│       ├── memory/             # 长短期记忆模块
│       ├── models/             # SQLAlchemy 模型
│       ├── schemas/            # Pydantic Schema
│       ├── services/           # 业务服务
│       └── main.py             # FastAPI 应用入口
├── frontend/
│   ├── android/                # Capacitor Android 工程
│   ├── deploy/                 # 前端容器 Nginx 配置
│   ├── src/                    # Vue 应用源码
│   ├── package.json
│   └── vite.config.js
├── llm/                        # 知识库、检索和模型调用
├── memory/                     # 长期记忆 Markdown 模板
├── skills/                     # Agent 技能与参考资料
├── tests/                      # 测试目录
├── compose.yaml                # Docker Compose 配置
├── Dockerfile                  # 后端容器配置
├── project_config.py           # 项目运行配置
└── requirements.txt            # Python 依赖
```

## 本地开发

### 后端

```bash
python -m venv .venv
.venv\Scripts\activate
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

默认访问地址：

```text
http://127.0.0.1:5173
```

开发环境下，Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 环境变量

后端根目录 `.env` 示例：

```env
OPENAI_API_KEY=your-openai-api-key
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
ASYNC_DATABASE_URL=mysql+aiomysql://root:password@localhost:3306/agent?charset=utf8mb4
REDIS_URL=redis://localhost:6379/0
AMAP_MCP_URL=https://mcp.amap.com/mcp?key=your-amap-key
TICKET_MCP_COMMAND=npx
TICKET_MCP_ARGS=-y,12306-mcp
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=agent-2.0
```

前端 `.env.production` 示例：

```env
VITE_API_BASE_URL=https://your-domain.com
```

如果前端和后端通过同一个域名部署，且 Nginx 将 `/api` 转发到后端，可以将 `VITE_API_BASE_URL` 留空。

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

手机 App 基于 Capacitor Android。构建前先确认正式 API 地址：

```env
VITE_API_BASE_URL=https://your-domain.com
```

然后执行：

```bash
cd frontend
npm install
npm run build
npx cap sync android
```

使用 Android Studio 打开：

```text
frontend/android
```

可以生成调试 APK，或生成签名后的 release APK/AAB 用于分发和上架。

注意：真机 App 不能使用 `http://127.0.0.1:8000` 作为后端地址，必须使用公网 IP 或域名。

## 常用 API

```text
GET  /
GET  /api/health
GET  /api/image-proxy?url=<image_url>

POST /api/auth/register
POST /api/auth/login
GET  /api/auth/profile
POST /api/auth/change-password

POST /api/chat/completion
POST /api/chat/completion/stream

GET  /api/vector-store/documents
POST /api/vector-store/upload
POST /api/feedback
```

需要登录的接口请携带：

```text
Authorization: Bearer <access_token>
```

## 注意事项

- `.env`、`chroma_db/`、`backend/data/`、`frontend/dist/`、`node_modules/` 不应提交到 Git。
- 生产环境建议启用 HTTPS。
- 如果单独部署前后端域名，需要在后端 CORS 中加入正式前端域名。
- Docker 部署时，MySQL、Redis、Chroma 和 memory 数据都通过 volume 持久化。
