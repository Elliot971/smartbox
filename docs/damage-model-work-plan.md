# 云端工具损坏检测模型工作计划

> 最后更新：2026-07-06
> 代码位置：`vision_training/cloud_damage_detection/`
> Web 后端对接：`data/esp-web/backend/app/services/damage_model.py`

## 1. 现状

### 1.1 已完成

| 组件 | 状态 | 说明 |
|------|------|------|
| 训练脚本 `train_patchcore.py` | ✅ 就绪 | 支持 MVTec AD / VisA 数据集，用 Anomalib 2.5 + PatchCore + WideResNet50 |
| 推理服务 `serve_damage_model.py` | ✅ 就绪 | FastAPI 服务，`POST /predict` 接口，支持 checkpoint 加载和 mock 模式 |
| Web 后端对接 `damage_model.py` | ✅ 就绪 | 通过 `DAMAGE_MODEL_URL` 调用推理服务，支持 mock 降级 |
| 图片上传 + 自动分析 | ✅ 就绪 | `POST /api/inspection/upload-and-analyze` 上传图片并自动分析 |
| 工具损坏概览 | ✅ 就绪 | `GET /api/inspection/tool-summary` 返回每个工具最新检测结果 |
| 前端检测页面 | ✅ 就绪 | 拖拽上传 + 工具概览卡片 + 任务记录列表 |
| 模型配置 `patchcore_mvtec.yaml` | ✅ 就绪 | backbone、阈值、部署端口等 |

### 1.2 当前限制

| 问题 | 影响 |
|------|------|
| **未训练真实工具模型** | 当前只有 MVTec AD/VisA 上的预训练，没有真实工具图片的 PatchCore checkpoint |
| **推理服务未部署** | 4090 服务器上 `serve_damage_model.py` 未启动，Web 后端走 mock 逻辑 |
| **image_url 传递方式** | 推理服务期望本地文件路径，Web 后端传的是 `/uploads/...` URL，需要适配 |
| **无真实损坏样本** | 缺少真实损坏工具的照片用于验证和调参 |

## 2. 架构

```
板端 / 工人上传图片
        │
        ▼
Web 后端 (FastAPI)
  POST /api/inspection/upload-and-analyze
  ├─ 保存图片到 uploads/inspections/
  ├─ 创建 DamageInspection 数据库记录
  └─ 调用 DAMAGE_MODEL_URL/predict ──────┐
        │                                  │
        ▼                                  ▼
  更新数据库 status/severity/summary   4090 服务器
  SSE 推送到前端                      serve_damage_model.py (FastAPI :18080)
                                     ├─ PatchCore 模型
                                     ├─ WideResNet50 backbone
                                     └─ 返回 anomaly_score + status
```

### 数据流

1. 图片来源：板端上传（关柜后拍照）或工人手动上传（Web 页面拖拽）
2. Web 后端保存图片到 `backend/uploads/inspections/`
3. Web 后端调 `POST http://<4090服务器>:18080/predict`，传 `image_url`（本地路径或 URL）
4. 推理服务用 PatchCore 计算异常分数
5. 异常分数 > 0.70 → `damaged`，> 0.45 → `suspected`，否则 `normal`
6. Web 后端更新数据库，SSE 推送到前端

## 3. 待办事项

### 阶段 1：部署推理服务到 4090 服务器（当前优先）

> 目标：让 Web 后端的损坏检测从 mock 切换到真实模型

- [ ] 在 4090 服务器创建 conda 环境
  ```bash
  conda create -n damage-cloud python=3.11 -y
  conda activate damage-cloud
  pip install -r vision_training/cloud_damage_detection/requirements.txt
  ```

- [ ] 下载 MVTec AD 数据集（或 VisA）到服务器
  ```bash
  python vision_training/cloud_damage_detection/scripts/download_public_data.py
  ```
  优先类别：`metal_nut`、`screw`、`capsule`（金属/小零件，最接近工具）

- [ ] 训练基线模型
  ```bash
  python vision_training/cloud_damage_detection/scripts/train_patchcore.py \
    --dataset mvtec_ad \
    --dataset-root /data/mvtec_ad \
    --category metal_nut \
    --output-dir vision_training/cloud_damage_detection/models/checkpoints
  ```

- [ ] 启动推理服务
  ```bash
  python vision_training/cloud_damage_detection/scripts/serve_damage_model.py \
    --checkpoint vision_training/cloud_damage_detection/models/checkpoints/patchcore.ckpt \
    --host 0.0.0.0 --port 18080
  ```

- [ ] 验证推理服务
  ```bash
  curl http://<4090服务器>:18080/health
  curl -X POST http://<4090服务器>:18080/predict \
    -H "Content-Type: application/json" \
    -d '{"image_url": "/path/to/test.jpg", "tool_name": "螺丝刀"}'
  ```

- [ ] 配置 Web 后端 `.env`
  ```env
  DAMAGE_MODEL_URL=http://<4090服务器>:18080
  ```
  重启后端，验证 `POST /api/inspection/upload-and-analyze` 返回真实模型结果

### 阶段 2：修复 image_url 传递问题

> 问题：Web 后端传给推理服务的 `image_url` 是 `/uploads/inspressions/xxx.jpg`（相对路径），
> 推理服务在另一台服务器上无法访问这个路径。

方案选择（二选一）：

**方案 A（推荐）：Web 后端传图片文件给推理服务**
- 改 `serve_damage_model.py` 的 `/predict` 接口，接收 multipart 图片文件
- 改 `damage_model.py`，用 `httpx` 上传图片文件而不是传 URL
- 优点：推理服务不需要访问 Web 服务器的文件系统
- 缺点：需要改两端代码

**方案 B：Web 后端传完整 URL**
- 改 `damage_model.py`，把 `image_url` 拼成完整 URL（如 `http://<web服务器>/uploads/...`）
- 推理服务用 `httpx` 下载图片再推理
- 优点：改动小
- 缺点：推理服务需要能访问 Web 服务器

### 阶段 3：采集真实工具数据

> 目标：用真实工具照片训练更准确的 PatchCore 模型

- [ ] 拍摄 8 类工具的正常照片（每类 50-100 张）
  - 用板端摄像头或手机拍摄
  - 不同角度、光照、位置
  - 全部是"正常"状态（没有损坏）
  - 存放路径：`工具数据集/损坏检测/正常/<tool_class>/`

- [ ] 拍摄损坏工具照片（每类 10-20 张，用于验证）
  - 模拟常见损坏：磨损、变形、裂纹、缺失
  - 存放路径：`工具数据集/损坏检测/损坏/<tool_class>/`

- [ ] 按工具类别训练独立模型（或单一模型 + 类别感知）
  ```bash
  # 每个工具类别一个 checkpoint
  python train_patchcore.py --dataset custom \
    --dataset-root /data/tool_damage --category screwdriver
  ```

- [ ] 调参：`suspected_score` 和 `damaged_score` 阈值
  - 在真实数据上跑混淆矩阵
  - 目标：误报率 < 10%，漏报率 < 5%

### 阶段 4：增强推理服务

- [ ] 返回热力图（anomaly heatmap）
  - PatchCore 原生支持热力图输出
  - 推理服务保存热力图到文件，返回 `heatmap_path`
  - Web 后端展示热力图叠加在原图上

- [ ] 多工具检测（一张图含多个工具）
  - 当前推理服务按整图计算异常分数
  - 如果一张照片有多个工具，需要先裁剪到单个工具区域再分别检测
  - 可以用板端的工具检测模型先定位裁剪，再送 PatchCore

- [ ] 模型版本管理
  - checkpoint 按日期命名：`patchcore_screwdriver_20260706.ckpt`
  - 推理服务支持热加载新 checkpoint
  - Web 后端记录使用的模型版本

### 阶段 5：LLM 增强损坏报告

- [ ] 损坏检测结果送大模型生成自然语言报告
  - PatchCore 输出：`status=damaged, score=0.82, heatmap=...`
  - 送 GLM-5.2 / DeepSeek 生成：
    ```
    工具名称：扭矩扳手
    检测结果：损坏
    异常分数：0.82
    异常位置：手柄中段
    
    建议：该扳手手柄存在明显裂纹，可能导致使用时断裂。
    建议立即停用并报废，从工具柜中移除，登记更换。
    ```
  - 存入 `DamageInspection.summary` 字段

## 4. 配置参考

### 推理服务参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--checkpoint` | 空 | PatchCore checkpoint 路径，空则走 mock |
| `--port` | 18080 | 服务端口 |
| `--suspected-score` | 0.45 | 疑似异常阈值 |
| `--damaged-score` | 0.70 | 确认损坏阈值 |
| `--accelerator` | auto | `auto` / `gpu` / `cpu` |
| `--lazy-unload` | False | 每次推理后释放 GPU 显存 |

### Web 后端 `.env` 配置

```env
DAMAGE_MODEL_URL=http://<4090服务器IP>:18080
DAMAGE_MODEL_API_KEY=
DAMAGE_MODEL_TIMEOUT=20.0
```

- `DAMAGE_MODEL_URL` 为空时走 mock 逻辑（关键词匹配）
- 配好后 Web 后端自动切换到真实模型

### 模型配置 `patchcore_mvtec.yaml`

| 参数 | 值 | 说明 |
|------|-----|------|
| backbone | `wide_resnet50_2` | 特征提取网络 |
| layers | `layer2, layer3` | 提取哪些层特征 |
| coreset_sampling_ratio | 0.1 | 核心集采样比例 |
| image_size | 384 | 输入图片尺寸 |
| suspected_score | 0.45 | 疑似阈值 |
| damaged_score | 0.70 | 损坏阈值 |

## 5. 接口规范

### 推理服务（4090 服务器）

**GET /health**
```json
{ "ok": true, "model_ready": true, "checkpoint": "/path/to/patchcore.ckpt" }
```

**POST /predict**
```json
// 请求
{ "task_id": 1, "tool_code": "T-001", "tool_name": "螺丝刀", "tool_class": "screwdriver", "image_url": "/path/to/image.jpg" }

// 响应
{
  "status": "suspected",        // normal / suspected / damaged
  "severity": "medium",         // low / medium / high
  "confidence": 0.73,           // max(score, 1-score)
  "summary": "Anomaly score 0.62; suspected wear...",
  "anomaly_score": 0.62,       // 原始异常分数
  "heatmap_path": "",           // 热力图路径（阶段 4）
  "model_ready": true,
  "checkpoint": "/path/to/patchcore.ckpt"
}
```

### Web 后端接口

| 接口 | 方法 | 用途 |
|------|------|------|
| `/api/inspection/upload-and-analyze` | POST | 上传图片 + 自动分析 |
| `/api/inspection/tasks` | POST | 创建检测任务 |
| `/api/inspection/tasks` | GET | 获取任务列表 |
| `/api/inspection/tasks/{id}/analyze` | POST | 触发分析 |
| `/api/inspection/tool-summary` | GET | 工具损坏概览 |

## 6. 时间线建议

| 阶段 | 预估工时 | 优先级 |
|------|----------|--------|
| 1. 部署推理服务 | 2-3 小时 | 高（当前优先） |
| 2. 修复 image_url 传递 | 1-2 小时 | 高 |
| 3. 采集真实工具数据 | 1-2 天 | 中 |
| 4. 增强推理服务（热力图/多工具） | 1-2 天 | 中 |
| 5. LLM 增强报告 | 2-3 小时 | 低（锦上添花） |

## 7. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-07-06 | 初版，梳理现状 + 5 阶段计划 |
