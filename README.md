# Travel Agent

一个面向出行场景的智能助手项目，包含：

- `FastAPI` 后端接口
- `Streamlit` 前端工作台
- 基于 `Chroma` 的用户级知识库
- 基于 `LangGraph` 的多路由对话编排
- 面向出行问答的 RAG、路线规划、票务咨询与通用问答能力

当前仓库不是单纯的 RAG Demo，而是一个把账号系统、文档知识库、对话编排和前端工作台串起来的完整原型。

## 功能概览

- 用户注册、登录、资料查询、修改密码
- 文档上传、解析、切分、向量化入库
- 用户隔离的知识库检索问答
- 基于 LangGraph 的多路由对话流程
- 支持普通接口和流式接口两种聊天模式
- 支持对话确认节点与最终摘要输出
- 提供聊天图评测数据与测试脚本

## 项目结构

```text
.
|-- backend/                  FastAPI 后端
|   |-- app/
|   |   |-- api/routes/       鉴权、聊天、知识库接口
|   |   |-- core/             数据库初始化
|   |   |-- crued/            业务逻辑
|   |   |-- graphs/           LangGraph 对话图
|   |   |-- models/           数据模型
|   |   |-- schemas/          请求/响应模型
|   |   `-- utils/            工具函数
|-- web/                      Streamlit 前端
|-- llm/                      RAG、检索、重排、文档解析
|-- test/                     图评测与测试数据
|-- chroma_db/                本地 Chroma 数据目录
|-- main.py                   启动入口
|-- project_config.py         全局配置
|-- requirements.txt          Python 依赖
|-- API_SPEC.md               接口说明
`-- test_main.http            HTTP 调试样例
```

## 技术栈

- Python
- FastAPI
- Streamlit
- SQLAlchemy
- LangChain
- LangGraph
- ChromaDB
- OpenAI API
- Transformers / Torch / FlagEmbedding

## 核心模块

### 1. 对话图

对话图位于 [backend/app/graphs/chat_graph.py](/d:/daima/项目/agent/backend/app/graphs/chat_graph.py)。

当前流程大致包含：

- 问题预处理
- 路由判断
- 确认门控
- 任务执行
- 答案生成
- 结果校验
- 最终摘要整理

其中，客服化整理相关节点使用的是单独部署的模型链路，不是默认通用大模型直出。
当前 `customer_service_rewriter` 以及相关整理节点接入的是通过 `vLLM` 部署、挂载 `LoRA` 的微调模型，用于把图执行结果整理成更稳定、更贴近客服话术的输出。

### 2. RAG 能力

RAG 相关代码主要位于 [llm/](/d:/daima/项目/agent/llm)。

当前实现包含：

- 文档解析与导入
- 面向不同文档类型的切分策略
- Chroma 向量库存储
- 混合检索与重排
- 用户级 collection 隔离

支持的文档类型包括：

- `.pdf`
- `.txt`
- `.md`
- `.html`
- `.htm`
- `.csv`
- `.json`
- `.jsonl`
- `.xls`
- `.xlsx`
- 其他可由 `Docling` 解析的格式

### 3. 前端工作台

前端位于 [web/app.py](/d:/daima/项目/agent/web/app.py)。

主要包含两个工作区：

- 知识库管理
- 对话交互

## 环境准备

建议环境：

- Python 3.10+
- MySQL 8+
- 可用的 OpenAI 兼容接口

安装依赖：

```bash
pip install -r requirements.txt
```

如果你会使用 Excel、Docling 或本地重排模型，可能还需要额外依赖；以 `requirements.txt` 为准。

## 环境变量

项目配置入口位于 [project_config.py](/d:/daima/项目/agent/project_config.py)。

常用环境变量示例：

```ini
OPENAI_API_KEY=your_openai_key
OPENAI_API_KEY1=your_openai_key
OPENAI_BASE_URL=https://your-openai-compatible-endpoint/v1

LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
DOCLING_TOKENIZER=BAAI/bge-m3

API_BASE_URL=http://127.0.0.1:8000/api
ASYNC_DATABASE_URL=mysql+aiomysql://root:123456@localhost:3306/agent?charset=utf8mb4

VECTOR_COLLECTION=knowledge_base
MD5_PATH=./md5.txt

TOP_K=5
CHUNK_SIZE=500
CHUNK_OVERLAP=50
TABLE_ROW_BATCH_SIZE=5
TABLE_ROW_OVERLAP=1

REQUEST_TIMEOUT_SECONDS=30
CHAT_TIMEOUT_SECONDS=300
UPLOAD_TIMEOUT_SECONDS=1800

RETRIEVAL_PROFILE=online
USE_QUERY_REWRITE=false
FINAL_RANK_ENABLED=true
RERANK_ENABLED=true
RERANK_MODEL_NAME=BAAI/bge-reranker-v2-m3
RERANK_DEVICE=cuda:0
RERANK_USE_FP16=true
RERANK_NORMALIZE=true
```

说明：

- `OPENAI_API_KEY` 或 `OPENAI_API_KEY1` 用于模型调用
- `OPENAI_BASE_URL` 用于接入兼容 OpenAI 的模型服务
- `ASYNC_DATABASE_URL` 用于用户、令牌、文档记录等关系型数据
- `API_BASE_URL` 供 Streamlit 前端请求后端接口
- `chroma_db/` 保存本地向量库数据

## 启动方式

### 1. 启动后端

在项目根目录执行：

```bash
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

访问地址：

- 首页：`http://127.0.0.1:8000/`
- Swagger：`http://127.0.0.1:8000/docs`

后端启动时会自动执行数据库初始化。

### 2. 启动前端

```bash
streamlit run web/app.py
```

默认通过 `API_BASE_URL` 与后端通信。

## 接口概览

后端入口位于 [backend/app/main.py](/d:/daima/项目/agent/backend/app/main.py)。

### 鉴权

- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/profile`
- `POST /api/auth/change-password`

### 知识库

- `POST /api/vector-store/upload`
- `GET /api/vector-store/documents`
- `DELETE /api/vector-store/documents`

### 对话

- `POST /api/chat/completion`
- `POST /api/chat/completion/stream`

更详细的请求样例可参考：

- [API_SPEC.md](/d:/daima/项目/agent/API_SPEC.md)
- [test_main.http](/d:/daima/项目/agent/test_main.http)

## 对话路由说明

当前对话图会根据问题类型在不同能力之间路由。相关节点代码位于 [backend/app/graphs/chat_graph_nodes/](/d:/daima/项目/agent/backend/app/graphs/chat_graph_nodes)。

典型路由包括：

- `ticket`：票务、车次、余票、改签等问题
- `roadmap`：路线、景点串联、出行顺序等问题
- `rag`：基于已上传文档的知识检索问答
- `other`：通用出行建议或兜底问答

此外还包含：

- 历史上下文压缩
- 需要用户确认时的门控逻辑
- 最终答案整理与摘要

说明：

- 通用检索、任务执行和图编排与“客服整理”链路是分开的
- 客服整理节点使用 `vLLM + LoRA` 微调模型，主要负责结果改写、客服化表达和最终输出润色

## RAG 工作流

文档上传后的典型流程如下：

1. 解析原始文件
2. 按文档类型生成 `Document`
3. 补充文件名、用户 ID 等元数据
4. 按文本、Markdown、表格、结构化内容分别切分
5. 写入用户隔离的 Chroma collection
6. 在数据库中记录上传文件

检索阶段会经过当前项目中的混合召回与排序链路，再交给回答生成模块组织最终答案。

## 测试与评测

当前仓库里已经有聊天图评测相关文件：

- [test/test_chat_graph_eval_suite.py](/d:/daima/项目/agent/test/test_chat_graph_eval_suite.py)
- [test/fixtures/chat_graph_eval_dataset.json](/d:/daima/项目/agent/test/fixtures/chat_graph_eval_dataset.json)

如果你要继续补测试，建议优先覆盖：

- 路由命中是否正确
- RAG 问答链路是否稳定
- 流式输出事件格式是否符合前端预期
- 确认节点和最终摘要结构是否兼容

## 常见问题

### 1. 前端连不上后端

优先检查：

- 后端是否已启动
- `API_BASE_URL` 是否正确
- 端口是否为 `8000`

### 2. 模型调用失败

优先检查：

- `OPENAI_API_KEY` 或 `OPENAI_API_KEY1` 是否已配置
- `OPENAI_BASE_URL` 是否可访问
- 当前模型名是否可用

### 3. 文档上传失败

优先检查：

- 文件格式是否受支持
- 解析依赖是否安装完整
- 是否超过 `UPLOAD_TIMEOUT_SECONDS`
- `chroma_db/` 是否可写

### 4. 数据库初始化失败

优先检查：

- MySQL 是否启动
- `ASYNC_DATABASE_URL` 是否正确
- 对应数据库是否已经创建

## 开发入口

你如果要继续扩展项目，建议从这些文件开始看：

- [main.py](/d:/daima/项目/agent/main.py)
- [backend/app/main.py](/d:/daima/项目/agent/backend/app/main.py)
- [backend/app/graphs/chat_graph.py](/d:/daima/项目/agent/backend/app/graphs/chat_graph.py)
- [backend/app/api/routes/chat.py](/d:/daima/项目/agent/backend/app/api/routes/chat.py)
- [backend/app/api/routes/vector_store.py](/d:/daima/项目/agent/backend/app/api/routes/vector_store.py)
- [llm/load.py](/d:/daima/项目/agent/llm/load.py)
- [llm/knowledge_base.py](/d:/daima/项目/agent/llm/knowledge_base.py)

## 项目定位

这个项目适合作为：

- 毕设或课程原型
- RAG + Agent + 工作流编排实践项目
- 出行场景智能助手 Demo
- 后续继续扩展成多工具旅行规划平台的基础版本
