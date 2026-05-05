# Android WebView 跨域请求失败问题

## 现象

手机 APK 点击登录后，后端日志无任何请求到达。DEBUG 面板显示 `API错误: Failed to fetch`。同一手机的浏览器访问 `http://175.27.169.218` 完全正常。

## 根因

APK 使用 Capacitor WebView 加载本地打包的页面，页面来源（Origin）为 `capacitor://localhost`。

JS 通过 `fetch()` 向 `http://175.27.169.218` 发 API 请求时，浏览器判定为跨域请求（自定义 scheme → HTTP）。Android WebView 对来自自定义 scheme 的跨域请求在底层直接拦截，**连 OPTIONS 预检请求都不会发出去**——所以服务器日志完全看不到请求。

```
APK 中的请求链路（失败）：
  capacitor://localhost → fetch(HTTP) → ❌ WebView 拦截 → Failed to fetch

浏览器中的请求链路（成功）：
  http://175.27.169.218 → fetch(同源) → ✅ 直接放行
```

即使后端已正确配置 CORS（`allow_origins` 包含 `capacitor://localhost`，`allow_origin_regex` 匹配 `capacitor://.*`），WebView 也从不发送请求，CORS 配置根本用不上。

## 解决方案

用 `CapacitorHttp`（Android 原生 OkHttp）替代 `fetch()` 发 API 请求。原生 HTTP 层不受 WebView CORS 策略约束。

### 实现要点

```js
import { Capacitor, CapacitorHttp } from "@capacitor/core";

const isNative = Capacitor.isNativePlatform();

// 原生平台用 CapacitorHttp，浏览器用 fetch
const result = await CapacitorHttp.request({
  method: "POST",
  url: "http://175.27.169.218/api/auth/login",
  headers: { "Content-Type": "application/json" },
  data: { username, password },
  responseType: "json",
});
```

### 注意事项

- SSE 流式请求：`CapacitorHttp` 不支持 ReadableStream，需获取完整响应后解析 SSE 事件，会失去实时流式体验
- 文件上传：`CapacitorHttp` 可直接传 `FormData`，无需额外处理
- 浏览器开发环境：保留 `fetch()` 路径，不影响本地 `npm run dev` 调试

## 涉及文件

- [frontend/src/api/client.js](../frontend/src/api/client.js) — API 客户端，核心修复
- [frontend/capacitor.config.ts](../frontend/capacitor.config.ts) — Capacitor 配置（不需要 `server.url`，页面从本地加载即可）
- [frontend/android/app/src/main/AndroidManifest.xml](../frontend/android/app/src/main/AndroidManifest.xml) — 需保留 `usesCleartextTraffic="true"`
- [frontend/android/app/src/main/res/xml/network_security_config.xml](../frontend/android/app/src/main/res/xml/network_security_config.xml) — 需放行目标 IP

---

## 云服务器部署指南

### 1. 环境要求

- 服务器：Linux（Ubuntu 20.04+ / CentOS 7+）
- Docker ≥ 24.0，Docker Compose ≥ 2.0
- 安全组 / 防火墙放行端口：**80**（Web 前端）、**8000**（API 直连，可选）

### 2. 上传代码到服务器

```bash
# 在本地打包（排除 node_modules、build 产物等）
git archive --format=tar.gz -o agent2.tar.gz HEAD

# 上传到服务器
scp agent2.tar.gz root@175.27.169.218:/opt/

# 服务器上解压
ssh root@175.27.169.218
cd /opt && tar -xzf agent2.tar.gz -C agent2 && cd agent2
```

### 3. 配置环境变量

```bash
cp .env.docker.example .env
vi .env
```

需要填写的关键变量：

```ini
APP_PORT=80

MYSQL_DATABASE=agent
MYSQL_USER=agent
MYSQL_PASSWORD=<设置一个强密码>
MYSQL_ROOT_PASSWORD=<设置一个强密码>

OPENAI_API_KEY=sk-xxxxxxxx
OPENAI_BASE_URL=https://api.openai-proxy.org/v1
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small

AMAP_MCP_URL=https://mcp.amap.com/mcp?key=<你的高德Key>
TICKET_MCP_ARGS=-y,12306-mcp
```

### 4. 构建前端（在服务器上）

因为 Docker Compose 中前端构建参数 `VITE_API_BASE_URL: ""` 传空，前端会使用 `.env.production` 中配置的 API 地址。如需修改，编辑 `frontend/.env.production`：

```ini
VITE_API_BASE_URL=http://175.27.169.218
```

### 5. 启动所有服务

```bash
docker compose up -d --build
```

首次启动会自动：
- 拉取 MySQL 8.4、Redis 7 镜像
- 构建后端镜像（Python + FastAPI）
- 构建前端镜像（Vite 打包 + Nginx）
- 初始化数据库表结构

### 6. 验证部署

```bash
# 检查所有容器运行状态
docker compose ps

# 检查后端健康
curl http://localhost:8000/api/health

# 通过 Nginx 验证
curl http://localhost/api/health

# 外网验证（从你电脑或手机浏览器）
curl http://175.27.169.218/api/health
```

### 7. 常用运维命令

```bash
# 查看后端日志
docker compose logs -f backend

# 查看 Nginx 日志
docker compose logs -f frontend

# 重启单个服务
docker compose restart backend

# 更新代码后重新构建并部署
git pull
docker compose up -d --build

# 停止所有服务
docker compose down

# 停止并删除数据卷（⚠️ 会清除数据库）
docker compose down -v
```

### 8. 服务架构

```
┌─────────────────────────────────────────┐
│                  服务器                    │
│                                           │
│  :80  ┌──────────┐     ┌──────────────┐  │
│  ◄────┤  Nginx   ├────►│  FastAPI     │  │
│       │ (frontend)│     │  :8000       │  │
│       └──────────┘     └──┬───┬───┬───┘  │
│                           │   │   │       │
│              ┌────────────┘   │   │       │
│              ▼                ▼   ▼       │
│       ┌──────┐  ┌───────┐ ┌──────────┐  │
│       │MySQL │  │ Redis │ │ChromaDB │  │
│       │:3306 │  │ :6379 │ │(文件存储)│  │
│       └──────┘  └───────┘ └──────────┘  │
└─────────────────────────────────────────┘
```

- **Nginx**：端口 80，提供前端静态文件 + 反向代理 `/api/` 到 FastAPI
- **FastAPI**：端口 8000（内网），处理业务逻辑
- **MySQL**：用户数据、对话历史、反馈
- **Redis**：会话缓存
- **ChromaDB**：文档向量存储（持久化到挂载卷）
