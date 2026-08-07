# FOD 智能工具箱云管理平台

前后端分离 Web 应用，用于展示 ESP32-P4 智能工具箱上传的工具状态、借还记录和异常告警，并通过云端大模型生成 FOD 风险分析建议。

## 技术栈

- 后端：FastAPI、SQLAlchemy、MySQL、SSE、httpx
- 前端：Vue 3、TypeScript、Vite
- 数据库：MySQL 8
- 设备通信：第一版使用 HTTP POST；前端实时刷新使用 SSE
- 生产部署：Docker Compose、Nginx

当前不强制使用 MQTT。HTTP POST 更适合比赛 MVP、ESP 端调试和本地演示；后续多设备或弱网场景再扩展 MQTT。

## 目录

```text
esp-web/
  backend/                  FastAPI 后端
  frontend/                 Vue 前端
  docker-compose.yml        本地开发 MySQL
  docker-compose.prod.yml   生产部署
  .env.production.example   生产环境变量模板
  DEPLOY_TENCENT_CLOUD.md   腾讯云部署说明
```

## 本地开发

### 1. 启动 MySQL

```bash
cd data/esp-web
docker compose up -d mysql
```

如果本机已经有 MySQL，也可以不用 Docker，只要创建数据库和账号：

```bash
mysql -uroot -p < backend/sql/init.sql
```

### 2. 启动后端

```bash
cd data/esp-web/backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python run.py
```

接口文档：

```text
http://127.0.0.1:8000/docs
```

后端根路径只返回 API 状态。Web 页面不是 8000 端口。

### 3. 启动前端

```bash
cd data/esp-web/frontend
npm install
npm run dev
```

访问：

```text
http://127.0.0.1:5173
```

## ESP32-P4 上报接口

状态快照：

```http
POST /api/device/snapshot
```

操作事件：

```http
POST /api/device/events
```

建议 ESP 端生成全局唯一 `event_id`，断网补传时后端会按 `event_id` 去重。

生产环境需要带设备上传密钥：

```http
X-Device-Key: your-device-key
Content-Type: application/json
```

开发环境如果不配置 `DEVICE_API_KEY`，可以不带该请求头。

## 大模型配置

默认 `LLM_PROVIDER=mock`，不需要 API Key，也会返回模拟风险分析结果。

如果使用 OpenAI-compatible 网关或乐鑫 AI Gateway 一类兼容接口，在 `backend/.env` 或生产 `.env.production` 配置：

```env
LLM_PROVIDER=ai_gateway
LLM_BASE_URL=https://your-gateway.example.com/v1
LLM_API_KEY=your-key
LLM_MODEL=your-model
```

后端不会把 API Key 下发给 ESP32-P4 或前端。

## 腾讯云部署

见：

```text
DEPLOY_TENCENT_CLOUD.md
```

生产部署入口：

```bash
cp .env.production.example .env.production
# 修改 .env.production 中的密码、服务器地址和 DEVICE_API_KEY
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```
