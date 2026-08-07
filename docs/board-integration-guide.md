# ESP32-P4 板端与 Web 后端对接文档

> 面向板端（ESP32-P4 固件）开发者。Web 后端由 Web 应用组维护，接口已就绪。
> 最后更新：2026-07-08

## 1. 总体架构

```
ESP32-P4 (板端固件)                          Web 后端 (data/esp-web)
┌─────────────────────────┐                 ┌──────────────────────────┐
│ WiFi: ESP-Hosted +       │   HTTP POST     │ FastAPI                   │
│ esp_wifi_remote → 连 AP  │ ──────────────> │ /api/device/snapshot      │
│                          │   JSON + Key    │ /api/device/events        │
│ cloud_uploader 模块       │                 │ /api/inspection/*         │
│ (异步队列 + 上传任务)     │ <────────────── │ { ok, message, data }     │
└─────────────────────────┘   响应 JSON      └──────────────────────────┘
         │                                                   │
         │ WiFi 连上后即可发送                                  │ MySQL 持久化
         │ 不需要和看 Web 的人同 WiFi                           │
         └── 只要能访问后端地址（公网 IP 或同局域网）即可         │
```

- **协议**：HTTP POST + JSON body（不用 MQTT、不用 RainMaker）。
- **Wi-Fi**：P4 通过板载 ESP32-C6 + ESP-Hosted 连 Wi-Fi，连上后可像普通 ESP32 一样用 `esp_http_client`、BSD socket。
- **距离**：取决于 Wi-Fi AP 覆盖，普通室内路由 2.4GHz 约 30–50 米，工业 AP 更远。
- **不需要和看 Web 的人在同一个 Wi-Fi**：板子只要能访问后端地址即可。后端部署在公网时，板子连任意能上网的 Wi-Fi 就行。

## 2. 后端接口规范

所有板端接口前缀 `/api/device`，需要请求头鉴权。

### 2.1 鉴权

| 请求头 | 值 | 说明 |
|--------|-----|------|
| `Content-Type` | `application/json` | 固定 |
| `X-Device-Key` | `CEKo80S7a1wbe5UZj3QB5Lrl` | 后端 `.env.production` 里 `DEVICE_API_KEY` 的值 |

- 开发环境：后端 `DEVICE_API_KEY` 为空时跳过校验，可不带头。
- 生产环境：必须带，否则返回 401。
- 当前生产环境 Key 为 `CEKo80S7a1wbe5UZj3QB5Lrl`，请板端同学在固件 Kconfig 或代码中配置。

### 2.2 POST /api/device/snapshot — 上传工具柜当前状态

**用途**：上报全部槽位的实时状态（心跳/状态同步）。建议关门确认后、或检测完成后发送。

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `device_code` | string | 是 | 设备编号，如 `"FOD-TOOLBOX-001"` |
| `timestamp` | string (ISO 8601) | 否 | 如 `"2026-06-17T10:30:00+08:00"`；不传则用后端时间 |
| `firmware_version` | string | 否 | 固件版本，如 `"p4-demo-0.1.0"` |
| `total` | int | 否 | 槽位总数 |
| `available` | int | 否 | 可用工具数 |
| `slots` | array | 否 | 槽位列表，见下 |

`slots[]` 每项：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `slot_no` | int | 是 | 槽位编号，从 1 开始 |
| `tool_code` | string | 否 | 工具编号，如 `"W-001"` |
| `tool_name` | string | 否 | 工具名称，如 `"扭矩扳手"` |
| `tool_class` | string | 否 | 工具类别，如 `"torque_wrench"` |
| `status` | string | 是 | 见下方状态值表 |
| `confidence` | float | 否 | 检测置信度 0.0–1.0 |

**`status` 取值**：

| 值 | 含义 | UI 颜色对应 |
|----|------|-------------|
| `present` | 工具在位（可借出） | 绿 |
| `available` | 等同 present（后端两者都算可用） | 绿 |
| `borrowed` | 已借出（空槽） | 红 |
| `uncertain` | 检测不确定，待人工确认 | 黄 |
| `missing` | 应在却不在（异常） | 黄 |
| `wrong` | 放错槽位（类别不符） | 黄 |

> 板端 `tool_slot_status_t` 枚举到字符串的映射建议：
> `TOOL_SLOT_AVAILABLE` → `"present"`，`TOOL_SLOT_BORROWED` → `"borrowed"`，
> `TOOL_SLOT_WARNING` → `"uncertain"`，`TOOL_SLOT_EMPTY` → `"borrowed"`（空槽按借出处理）。

**响应**：

```json
{
  "ok": true,
  "message": "ok",
  "data": { "device_id": 1, "device_code": "FOD-TOOLBOX-001", "available": 10, "total": 12 }
}
```

**示例请求体**（见 `backend/sample_payloads/snapshot.json`）：

```json
{
  "device_code": "FOD-TOOLBOX-001",
  "timestamp": "2026-06-17T10:30:00+08:00",
  "firmware_version": "p4-demo-0.1.0",
  "total": 12,
  "available": 10,
  "slots": [
    { "slot_no": 1, "tool_code": "W-001", "tool_name": "扭矩扳手", "tool_class": "torque_wrench", "status": "present", "confidence": 0.96 },
    { "slot_no": 2, "tool_code": "S-002", "tool_name": "螺丝刀", "tool_class": "screwdriver", "status": "borrowed", "confidence": 0.91 },
    { "slot_no": 4, "tool_code": "C-004", "tool_name": "卡尺", "tool_class": "caliper", "status": "uncertain", "confidence": 0.51 }
  ]
}
```

### 2.3 POST /api/device/events — 上传一次开关门操作事件

**用途**：一次完整的借还操作结束（关门确认）后上报，包含借出/归还/异常列表。

**请求体**：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `event_id` | string | 是 | 事件唯一 ID，建议格式 `<device_code>-<时间戳>-<序号>`，如 `"FOD-TOOLBOX-001-20260617103022-0001"`；后端按此去重 |
| `device_code` | string | 是 | 设备编号 |
| `operator` | object | 否 | 操作员信息 |
| `event_type` | string | 否 | 默认 `"operation"` |
| `result_type` | string | 否 | 见下方取值 |
| `opened_at` | string (ISO 8601) | 否 | 开门时间 |
| `closed_at` | string (ISO 8601) | 否 | 关门时间 |
| `borrowed` | array | 否 | 本次借出的工具列表 |
| `returned` | array | 否 | 本次归还的工具列表 |
| `anomalies` | array | 否 | 异常项列表（见第 4 节异常分类） |
| `raw` | object | 否 | 原始附加数据，板端可放任何额外字段 |

`operator`：

| 字段 | 类型 | 说明 |
|------|------|------|
| `user_code` | string | 工号，如 `"EMP023"` |
| `name` | string | 姓名，如 `"张三"` |
| `auth_type` | string | `"nfc"` / `"face"` / `"safety_check"` |

`borrowed`/`returned`/`anomalies` 每项（`ToolChangeIn`）：

| 字段 | 类型 | 说明 |
|------|------|------|
| `slot_no` | int | 槽位号 |
| `tool_code` | string | 工具编号 |
| `tool_name` | string | 工具名称 |
| `tool_class` | string | 工具类别 |
| `confidence` | float | 检测置信度 |

**`result_type` 取值**：

| 值 | 含义 |
|----|------|
| `borrow_ok` | 借出成功 |
| `return_ok` | 归还成功 |
| `anomaly` | 存在异常（配合 `anomalies` 列表） |
| `auth_failed` | 认证失败 |

**响应**：

```json
{
  "ok": true,
  "message": "ok",
  "data": { "id": 42, "event_id": "FOD-TOOLBOX-001-20260617103022-0001", "created": true }
}
```

- `created: true` 表示新建，`false` 表示该 `event_id` 已存在（重复上报会被忽略，不会报错）。

**示例请求体**（见 `backend/sample_payloads/event.json`）：

```json
{
  "event_id": "FOD-TOOLBOX-001-20260617103022-0001",
  "device_code": "FOD-TOOLBOX-001",
  "operator": { "user_code": "EMP023", "name": "张三", "auth_type": "face" },
  "opened_at": "2026-06-17T10:30:22+08:00",
  "closed_at": "2026-06-17T10:31:10+08:00",
  "event_type": "operation",
  "result_type": "anomaly",
  "borrowed": [
    { "slot_no": 2, "tool_code": "S-002", "tool_name": "螺丝刀", "tool_class": "screwdriver", "confidence": 0.91 }
  ],
  "returned": [],
  "anomalies": [
    { "slot_no": 4, "tool_code": "C-004", "tool_name": "卡尺", "tool_class": "caliper", "confidence": 0.51 }
  ]
}
```

## 3. 板端模块设计建议（cloud_uploader）

Web 组已和板端同学确认采用**方案 B：异步队列 + 独立上传任务**。

### 3.1 文件布局

```
main/
  cloud_uploader.h      # 公共 API + 数据结构
  cloud_uploader.c      # 队列、任务、HTTP、JSON、重试
  CMakeLists.txt        # 加 cloud_uploader.c；PRIV_REQUIRES 加 esp_http_client、cjson、esp_timer
  Kconfig.projbuild     # 新增 "Cloud Uploader" 菜单
```

### 3.2 模块边界

- **只做**：序列化 JSON → 排队 → HTTP POST → 重试。
- **不做**：工具检测、before/after 对比、UI 更新、event_id 生成逻辑（这些由 `cabinet_core` 等业务层负责）。
- 调用方填结构体 → 调 post 函数 → 立即返回（不阻塞）。

### 3.3 建议公共 API

```c
typedef struct {
    int slot_no;
    char tool_code[32];
    char tool_name[32];
    char tool_class[32];
    char status[16];      // "present" / "borrowed" / "uncertain" / "missing" / "wrong"
    float confidence;
} cloud_slot_t;

typedef struct {
    char device_code[32];
    char firmware_version[16];
    int total;
    int available;
    const cloud_slot_t *slots;
    int slot_count;
} cloud_snapshot_t;

typedef struct {
    int slot_no;
    char tool_code[32];
    char tool_name[32];
    char tool_class[32];
    float confidence;
} cloud_tool_change_t;

typedef struct {
    char event_id[48];
    char device_code[32];
    struct {
        char user_code[32];
        char name[32];
        char auth_type[16];
    } operator;
    char event_type[16];     // "operation"
    char result_type[24];    // "borrow_ok" / "return_ok" / "anomaly" / "auth_failed"
    char opened_at[32];      // ISO 8601
    char closed_at[32];
    const cloud_tool_change_t *borrowed;
    int borrowed_count;
    const cloud_tool_change_t *returned;
    int returned_count;
    const cloud_tool_change_t *anomalies;
    int anomaly_count;
} cloud_event_t;

/* 初始化（在 app_main WiFi 初始化之后调用） */
esp_err_t cloud_uploader_init(void);

/* 异步入队，立即返回；ESP_OK 表示已入队 */
esp_err_t cloud_uploader_post_snapshot(const cloud_snapshot_t *snapshot);
esp_err_t cloud_uploader_post_event(const cloud_event_t *event);

/* 是否就绪（WiFi 已连接且任务运行中） */
bool cloud_uploader_is_ready(void);
```

### 3.4 内部架构

| 组件 | 建议 |
|------|------|
| 队列 | FreeRTOS Queue，深度 8–16，每项是序列化后的 JSON 字符串指针（入队时 cJSON 打包，出队发送后 free） |
| 上传任务 | `cloud_upload_task`，优先级 3（低），栈 6–8 KB，核心 0 |
| HTTP 客户端 | `esp_http_client`（IDF 内置），POST 方法，超时 10–15s |
| JSON | `cJSON`（IDF 内置）打包请求体；解析响应 |
| 时间戳 | 用 `wifi_manager` 已启动的 SNTP 拿 UTC 时间，格式化成 ISO 8601 |
| WiFi 状态 | 调用 `wifi_manager_is_connected()` 判断是否可发 |

### 3.5 重试与错误策略

| 情况 | 处理 |
|------|------|
| WiFi 未连接 | 任务阻塞等待，连上后自动消费队列 |
| HTTP 超时 / 5xx | 指数退避重试：1s → 2s → 4s → 8s → 16s → 32s → 60s（上限），最多 5 次 |
| HTTP 4xx | 不重试（请求有问题，重发也没用），记日志后丢弃 |
| HTTP 2xx | 成功，出队下一项 |
| 队列满 | 丢弃最旧的 **snapshot**（状态可重新采集），**保留 event**（事件不能丢） |
| 单条 event 重试耗尽 | 写 SD 卡日志待后续补传（可选） |

### 3.6 Kconfig 配置

建议在 `Kconfig.projbuild` 新增：

```
menu "Cloud Uploader"
    config CLOUD_UPLOADER_URL
        string "Backend base URL"
        default "http://119.91.237.137:8088"
    config CLOUD_UPLOADER_DEVICE_CODE
        string "Device code"
        default "FOD-TOOLBOX-001"
    config CLOUD_UPLOADER_API_KEY
        string "X-Device-Key"
        default "CEKo80S7a1wbe5UZj3QB5Lrl"
endmenu
```

- 本地开发：URL 填 `http://127.0.0.1:8000`，Key 留空。
- 生产：URL 填 `http://119.91.237.137:8088`，Key 填 `CEKo80S7a1wbe5UZj3QB5Lrl`。

## 4. 异常分类（重要）

板端要上报的"异常"分两类，分别走不同接口：

### 4.1 操作异常（板端本地检测，立即上报）

由 `cabinet_core` 做 before/after 工具状态对比得出，通过 `/api/device/events` 的 `anomalies` 字段上报：

| 场景 | 判断逻辑 | result_type |
|------|----------|-------------|
| 工具丢失 | before 有、after 没有，且不是本次借出 | `anomaly` |
| 放错槽位 | after 检测到的工具类别和该槽位预期不符 | `anomaly` |
| 未授权开门 | NFC/人脸认证未通过但门被打开 | `anomaly` |

**不需要等云端模型**，板端自己就能判断。

### 4.2 工具损坏异常（云端模型检测，单独链路）

通过 `/api/inspection/*` 接口，需要传图片：

1. `POST /api/inspection/upload-and-analyze` — 直接上传图片文件（multipart），自动创建任务并调用云端损坏检测模型
   - 参数：`file`（图片文件）、`tool_code`、`tool_name`、`tool_class`（查询参数）
   - 返回：`DamageInspectionOut`（含 status/severity/summary/confidence）
2. `POST /api/inspection/tasks` — 只创建任务（传 `image_url`），不立即分析
3. `POST /api/inspection/tasks/{id}/analyze` — 对已有任务触发云端模型分析
4. `GET /api/inspection/tool-summary` — 获取所有有图片工具的最新损坏检测结果

后端调 `DAMAGE_MODEL_URL` 配置的 PatchCore 模型服务，返回 `normal` / `suspected` / `damaged`。

**图片上传已实现**：板端可以直接用 multipart/form-data 上传 JPG/PNG 到 `/api/inspection/upload-and-analyze`，后端保存图片并自动分析。

## 5. 图片上传

图片上传已实现（方案 B：multipart 直传），板端有两种方式：

| 接口 | 用途 | 方式 |
|------|------|------|
| `POST /api/inspection/upload-and-analyze` | 上传图片并自动分析 | multipart/form-data，`file` 字段 + 查询参数 `tool_code/tool_name/tool_class` |
| `POST /api/inspection/tasks` + `POST /api/inspection/tasks/{id}/analyze` | 先创建任务再手动触发分析 | JSON body，`image_url` 字段 |

### 板端上传图片示例（esp_http_client）

```c
// 设置 Content-Type: multipart/form-data
// 用 esp_http_client_fill_header 设置 boundary
// 手动构造 multipart body 或用 esp_http_client 的 form-data 支持
// file 字段 = JPEG 图片二进制数据
// 查询参数: tool_code=T-001&tool_name=螺丝刀&tool_class=screwdriver
```

**注意**：
- 图片保存路径：后端 `uploads/inspections/` 目录
- 静态访问：`/uploads/inspections/<filename>`
- 支持格式：JPG / PNG
- 超时建议：60 秒（图片较大时）

## 6. 调用时机建议

```
app_main()
  ├─ nvs / spiffs / sdcard
  ├─ wifi_manager_init()           # 连 WiFi
  ├─ cloud_uploader_init()         # 初始化上传模块（创建队列+任务）
  └─ ... UI / cabinet_core

# 业务流程中的调用点（由 cabinet_core 驱动）：
开门前检测完成 → 可选发 snapshot（同步初始状态）
关门后检测 + diff 完成
  ├─ 构造 cloud_event_t（borrowed/returned/anomalies）
  ├─ cloud_uploader_post_event(&event)     # 立即入队
  └─ cloud_uploader_post_snapshot(&snap)   # 顺手更新状态
```

## 7. 后端地址

| 环境 | 地址 |
|------|------|
| 本地开发 | `http://127.0.0.1:8000/api/device/*` |
| 生产（腾讯云） | `http://119.91.237.137:8088/api/device/*` |

- 后端 API 文档（Swagger）：`http://119.91.237.137:8088/docs`
- 健康检查：`http://119.91.237.137:8088/health`

## 8. 联调步骤

1. Web 组启动后端（`docker compose up` 或本地 `uvicorn`），确认 `http://<地址>/health` 返回 `{"ok": true}`。
2. 板端先不带 Key（开发环境）curl 测试：
   ```bash
   curl -X POST http://<地址>/api/device/snapshot \
     -H "Content-Type: application/json" \
     --data @backend/sample_payloads/snapshot.json
   ```
3. 板端固件集成 `cloud_uploader`，先用 sample JSON 跑通。
4. 接入真实业务数据（工具检测结果）。
5. 生产环境加上 `X-Device-Key`。

## 9. 字段速查表

| 板端结构 | 后端字段 | 接口 |
|----------|----------|------|
| `cloud_snapshot_t.device_code` | `device_code` | snapshot |
| `cloud_slot_t.status` | `slots[].status` | snapshot |
| `cloud_event_t.event_id` | `event_id`（去重用） | events |
| `cloud_tool_change_t` | `borrowed[]/returned[]/anomalies[]` | events |
| `operator.user_code/name/auth_type` | `operator.*` | events |
| `result_type` | `result_type` | events |
| ISO 8601 时间 | `opened_at/closed_at/timestamp` | 两者 |

## 10. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初版，基于方案 B（异步队列）和现有后端 schema |
| 2026-07-06 | 更新：图片上传已实现（multipart 直传），新增 `/api/inspection/upload-and-analyze` 接口，新增工具损坏概览接口 |
| 2026-07-08 | 更新：补充生产环境地址 `http://119.91.237.137:8088` 与 `X-Device-Key: CEKo80S7a1wbe5UZj3QB5Lrl` |
