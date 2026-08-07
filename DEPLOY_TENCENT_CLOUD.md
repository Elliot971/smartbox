# 腾讯云 CVM 部署说明

本文档用于将 FOD 智能工具箱 Web 管理平台部署到腾讯云服务器。当前方案采用 Docker Compose：Vue 前端由 Nginx 托管，FastAPI 后端提供 API，MySQL 保存业务数据。

## 1. 服务器建议

- Ubuntu 22.04 或 24.04
- 2 核 4G 起步
- 40G 云硬盘
- 安全组开放 22、80；有域名和 HTTPS 时开放 443
- 不要把 MySQL 3306 暴露到公网

## 2. 安装 Docker

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
newgrp docker
```

检查：

```bash
docker version
docker compose version
```

如果 `docker compose version` 报错，说明 Compose v2 插件没有安装成功，可执行：

```bash
sudo apt install -y docker-compose-plugin
docker compose version
```

## 3. 上传项目

将 `data/esp-web` 上传到服务器，例如：

```bash
scp -r data/esp-web ubuntu@SERVER_IP:/opt/esp-web
```

进入目录：

```bash
cd /opt/esp-web
```

## 4. 配置环境变量

```bash
cp .env.production.example .env.production
nano .env.production
```

必须修改：

```env
MYSQL_ROOT_PASSWORD=强密码
MYSQL_PASSWORD=强密码
DATABASE_URL=mysql+pymysql://esp_user:同上MYSQL_PASSWORD@mysql:3306/esp_toolbox?charset=utf8mb4
CORS_ORIGINS=http://服务器公网IP
DEVICE_API_KEY=设备上传密钥
```

后续有域名时，将 `CORS_ORIGINS` 改为域名地址。

## 5. 启动生产服务

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

首次启动前可以检查配置是否能被 Docker Compose 正确解析：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production config
```

查看状态：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production ps
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f backend
```

浏览器访问：

```text
http://服务器公网IP
```

健康检查：

```bash
curl http://服务器公网IP/health
```

## 6. ESP32-P4 上传地址

设备端 HTTP 地址配置为：

```text
http://服务器公网IP/api/device/snapshot
http://服务器公网IP/api/device/events
```

请求头必须带：

```http
X-Device-Key: .env.production 中的 DEVICE_API_KEY
Content-Type: application/json
```

## 7. 测试上报

在服务器目录执行：

```bash
curl -X POST http://127.0.0.1/api/device/snapshot \
  -H "X-Device-Key: $(grep DEVICE_API_KEY .env.production | cut -d= -f2-)" \
  -H "Content-Type: application/json" \
  --data @backend/sample_payloads/snapshot.json
```

## 8. HTTPS

比赛演示可先用公网 IP。若有域名，建议使用 Nginx Proxy Manager、Caddy 或 Certbot 配置 HTTPS。启用 HTTPS 后，设备上传地址改为：

```text
https://你的域名/api/device/events
```

## 9. 数据备份

导出 MySQL：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production exec mysql \
  mysqldump -uroot -p esp_toolbox > backup.sql
```

至少在比赛演示前备份一次。
