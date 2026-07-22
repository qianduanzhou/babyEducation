# Moon Sprout Stories

一个胎教故事生成应用：React 前端、FastAPI 后端、SQLite 历史库，支持注册登录、用户隔离、故事生成、搜索、删除和阅读到底自动标记已读。

## 本地开发

1. 复制配置：

```powershell
Copy-Item .env.example .env
```

2. 启动后端：

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

3. 启动前端：

```powershell
Set-Location frontend
npm install
npm run dev
```

前端默认地址为 `http://localhost:5173`，Vite 会把 `/api` 代理到 `http://127.0.0.1:8000`。

## 大模型配置

大模型参数不再写入 `.env`。登录网页后点击右上角 `AI 配置`，可以保存当前用户自己的：

- Base URL：OpenAI 兼容接口地址，例如 `https://api.openai.com/v1`
- API Key：保存后不会在页面明文回显，留空保存会保持原 Key
- 模型名称
- Headers JSON：会合并到请求头
- 全局补充提示词

代码内置系统提示词会约束故事温柔、安全、简单，适合宝宝胎教朗读。没有配置 API Key 时，会使用本地兜底故事，方便开发调试。

## 镜像构建和推送

填写 `.env` 中的：

```env
REGISTRY=registry.example.com
REGISTRY_USERNAME=your-username
REGISTRY_PASSWORD=your-password
IMAGE_NAMESPACE=baby-education
VERSION=0.1.0
```

执行：

```powershell
.\scripts\push-images.ps1
```

脚本会构建并推送：

- `${REGISTRY}/${IMAGE_NAMESPACE}/baby-education-frontend:${VERSION}`
- `${REGISTRY}/${IMAGE_NAMESPACE}/baby-education-backend:${VERSION}`

## 部署机启动

把根目录的 `docker-compose.yml` 和填写好的 `.env` 复制到部署机，然后执行：

```powershell
docker compose --env-file .env up -d
```

默认前端端口由 `FRONTEND_PORT` 控制，后端端口由 `BACKEND_PORT` 控制。SQLite 数据保存在 Docker volume `backend_data` 中。
