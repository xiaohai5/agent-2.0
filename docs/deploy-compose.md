# Docker Compose 部署

## 服务器部署

1. 在服务器上安装 Docker 和 Docker Compose 插件。
2. 将 `.env.docker.example` 复制为 `.env`，然后填写真实密钥和密码。
3. 构建并启动整套服务：

```bash
docker compose up -d --build
```

4. 查看服务状态：

```bash
docker compose ps
docker compose logs -f backend
```

5. 打开应用：

```text
http://your-server-ip
```

前端容器使用 Nginx 托管 Vite 构建产物，所有 `/api/` 请求都会反向代理到后端容器。

## 常用命令

```bash
docker compose down
docker compose restart backend
docker compose logs -f frontend
docker compose exec backend python -c "from backend.app.core.database import ASYNC_DATABASE_URL; print(ASYNC_DATABASE_URL)"
```

拉取新代码后更新部署：

```bash
git pull
docker compose up -d --build
```

## HTTPS

生产环境建议启用 HTTPS。可以在宿主机上用 Nginx 或 Caddy 做最外层反向代理，也可以把 `.env` 里的 `APP_PORT` 改成内部端口，例如 `8080`，再把你的域名反向代理到 `127.0.0.1:8080`。

## Android App 构建

这个手机端是 Capacitor Android 项目。要生成可安装的 App，需要先构建前端资源，再同步到 Android 工程：

```bash
cd frontend
npm install
npm run build
npx cap sync android
```

然后用 Android Studio 打开 `frontend/android`，构建调试 APK，或者生成已签名的 release APK/AAB。

如果真机需要访问已部署的后端，构建前要先配置正式 API 地址：

```env
VITE_API_BASE_URL=https://your-domain.com
```

修改后重新执行前端构建和 Android 同步。
