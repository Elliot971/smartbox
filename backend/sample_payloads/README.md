# 示例上报

后端启动后，可以用以下命令模拟 ESP32-P4 上报：

```bash
curl -X POST http://127.0.0.1:8000/api/device/snapshot \
  -H "X-Device-Key: dev-device-key" \
  -H "Content-Type: application/json" \
  --data @backend/sample_payloads/snapshot.json

curl -X POST http://127.0.0.1:8000/api/device/events \
  -H "X-Device-Key: dev-device-key" \
  -H "Content-Type: application/json" \
  --data @backend/sample_payloads/event.json
```

开发环境如果没有配置 `DEVICE_API_KEY`，可以不带 `X-Device-Key`。生产环境必须配置。
