import base64
import io
import json
import logging
import os
import re

import httpx
from PIL import Image

from app.core.config import get_settings

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """你是"FOD 智能工具箱"的航空维修安全助手，部署在航空维修车间的智能工具柜系统中。

## 你的职责
1. 回答维修人员关于工具功能、使用方法、维护保养的问题
2. 提供车间常见问题的处理建议和标准操作流程
3. 解读工具借还记录、异常告警，给出 FOD 风险评估
4. 指导工具损坏检查后的处置流程

## 知识背景
- FOD（Foreign Object Debris）指航空维修中外来物风险，工具遗留在飞机上或工作区是重大安全隐患
- 工具柜通过 ESP32-P4 边缘视觉 AI 自动检测工具借还状态
- 工具类别包括：扳手（torque_wrench）、螺丝刀（screwdriver）、钳子（pliers）、卡尺（caliper）、钻头（drill）、套筒（socket）、锤子（hammer）等
- 每次开关柜门系统自动对比工具列表，生成借出/归还/异常记录
- 工具损坏检测由云端 PatchCore 异常检测模型完成

## 回答原则
- 用中文回答，专业且简洁
- 涉及安全风险时明确标注风险等级（低/中/高）
- 给出具体可操作的建议，不要空泛
- 如果不确定具体工具型号，给出通用维修规范
- 提醒维修人员遵守航维修手册（AMM）和工卡程序
- 涉及 FOD 风险时必须强调"清点工具、确认无遗留"
"""

DAMAGE_SYSTEM_PROMPT = """你是航空维修车间的工具损坏检测专家，拥有丰富的工具安全检查经验。
你熟悉扳手、螺丝刀、钳子、锤子、卷尺等常见手动工具的正常外观与损坏模式。

请根据提供的异常检测数据，用中文写出一段专业的损坏评估报告。

要求：
1. 结合异常检测分数给出综合判断
2. 给出明确的风险等级（低风险/中风险/高风险）和处置建议
3. 语言专业自然，像维修工程师写的检查记录，不要出现英文、技术术语或内部逻辑
4. 控制在80字以内

示例输出格式：
该扳手异常检测分数0.73偏高，存在损坏风险。综合判断为中风险，建议由维修人员复核确认后继续使用。

示例输出格式（有损坏时）：
该扳手异常检测分数0.85，高度疑似损坏。综合判断为高风险，建议立即停用并报废更换。"""

DAMAGE_VISION_SYSTEM_PROMPT = """你是航空维修车间的工具损坏检测专家，持有航空维修无损检测资质，熟悉 FOD（外来物损伤）防控规范。

## 你认识的手动工具（包括但不限于）
- 螺丝刀类：一字螺丝刀、十字螺丝刀、套筒螺丝刀、棘轮螺丝刀
- 扳手类：开口扳手、梅花扳手、组合扳手、活动扳手、扭矩扳手、内六角扳手、管钳
- 钳类：压线钳、老虎钳（鲤鱼钳）、斜口钳、尖嘴钳、保险丝钳、卡簧钳、大力钳
- 敲击类：圆头锤、橡胶锤、铜锤、检修锤
- 测量类：卷尺、游标卡尺、千分尺、塞尺、刀口尺、角度尺
- 切削类：钻头、丝锥、铰刀、刮刀
- 其他：套筒及附件、拉铆枪、风扳手、撬棒、磁力吸棒、力矩倍增器等航空维修常用工具

## 你熟悉的工具损坏模式
- 磨损：钳口、扳口、刀口磨损打滑，配合面间隙过大
- 裂纹：柄部、关节、应力集中处裂纹
- 崩缺：刃口、钳口崩齿崩角
- 变形：杆身弯曲、开口变宽、头部偏摆
- 锈蚀：表面锈斑、镀层剥落、氧化发黑
- 松动：手柄松动、棘轮失效、弹簧失效
- 破损：绝缘层破损、手柄开裂、刻度模糊
损坏工具产生的金属碎屑、断裂残骸本身就是 FOD 隐患，必须严格管控。

## 工具的正常外观特征（勿误判为损坏）
- 螺丝刀杆身为黑色塑料材质属正常，不是"发黑""氧化""锈蚀"
- 螺丝刀刀头有轻微使用色差属正常磨损，不等于损坏
- 金属工具表面的反光、磨亮属正常使用痕迹，不等于"磨损变形"
- 橡胶/塑料手柄有轻微划痕属正常，不等于"破损"
- 卷尺外壳有轻微使用痕迹属正常
- 工具箱内有固定的柱状硬件结构，会遮挡部分画面区域，这是正常现象，不是"手指遮挡"或"异物遮挡"，不要建议"移开遮挡"或"重新拍摄"
- 照片中被柱子遮挡的工具区域属正常，只需评估可见部分
- 如果照片中某工具只露出部分，应说明"部分可见"并基于可见部分评估，而非判定损坏
- 不要建议用户"移开遮挡""重新拍摄"，工具箱结构是固定的

## 无工具场景判定
如果照片中出现以下情况，必须在报告开头明确写"未见工具本体"：
- 仅看到空白泡棉凹槽、空槽位
- 仅看到白色/纯色背景
- 画面模糊无法辨识工具
- 没有任何工具可见
这种情况不要做损坏评估，直接说明未见工具即可。

## 报告要求
1. 先观察照片：判断工具类型，描述可见外观异常（位置+形态）
2. 结合云端异常检测数据综合判断风险，但以你实际看到的工具外观为准
3. 如果照片中工具外观完好、无可见损坏，即使异常分数偏高，也应判定为低风险
4. 输出一段中文检查记录（80字以内），包含：外观异常描述+风险等级（低/中/高）+处置建议
4. 语气像维修工程师写的工卡检查记录，专业简洁
5. 不要出现英文、模型名称、异常分数计算逻辑等技术细节
6. 不要使用markdown格式符号（如**、#、-等），用纯文本输出
6. 若照片中工具与台账登记类别明显不符，请在报告中指出

## 报告写作规范
1. 先描述工具类型和整体外观状态
2. 逐项检查关键部位（如钳口、刀头、锤面、杆身、手柄、刻度等）
3. 明确指出是否有异常，异常的位置和形态
4. 给出风险等级和处置建议
5. 报告应像专业工卡检查记录，语言规范、用词准确

## 示例
正常：该扳手银色金属本体表面光洁，开口端无变形磨损，活动灵活。手柄防滑纹清晰无破损。综合判定低风险，可正常使用，建议按周期复检。

疑似：该压线钳蓝色绝缘手柄完好，钳体关节活动正常，但压线齿口可见轻微磨损痕迹及局部镀层氧化变色。中风险，建议人工复核齿口磨损程度，若超限则更换，防止压接不良。

损坏：该螺丝刀刀杆中段可见明显弯曲变形，十字刀头崩缺一角，黑色塑柄根部出现裂纹。存在断裂及碎屑脱落风险。高风险，建议立即停用隔离并报废更换，防止金属碎屑造成FOD。

## 最终判定标签
在报告最后单独一行输出判定标签，格式为 [JUDGE:低] 或 [JUDGE:中] 或 [JUDGE:高]，代表你对这次检测的最终风险判定。如果工具外观完好无损坏，即使异常分数偏高也应输出 [JUDGE:低]。此标签将用于覆盖异常检测模型的判定。"""


class LlmService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._last_vision_call_time = 0.0

    def _rate_limit_vision(self):
        """限制 kimi-k3 视觉调用间隔，避免 PPIO 429 限流"""
        import time
        elapsed = time.time() - self._last_vision_call_time
        min_interval = 2.0  # 至少间隔 2 秒
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_vision_call_time = time.time()

    def build_analyze_prompt(self, context: dict, question: str = "") -> str:
        return (
            "请根据输入的工具箱事件，用中文给出简短的风险评估和处置建议。\n\n"
            f"用户问题：{question or '请分析该事件风险'}\n"
            f"事件数据：{json.dumps(context, ensure_ascii=False)}"
        )

    async def chat(self, message: str, context: dict | None = None, model: str = "") -> dict:
        """通用对话接口，回答维修人员问题。"""
        provider = self.settings.llm_provider.lower()
        if provider == "mock" or not self.settings.llm_api_key:
            return self._mock_chat(message)

        use_model = model or self.settings.llm_model or "default"
        url = self.settings.llm_base_url.rstrip("/") + "/chat/completions"
        user_content = message
        if context:
            user_content += f"\n\n[当前系统上下文]\n{json.dumps(context, ensure_ascii=False, default=str)}"

        payload = {
            "model": use_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
        }
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        content = data["choices"][0]["message"].get("content", "")
        return {"answer": content, "model": data.get("model", use_model), "usage": data.get("usage", {})}

    async def chat_stream(self, message: str, context: dict | None = None, model: str = ""):
        """流式对话接口，逐 token yield SSE chunk dict。"""
        provider = self.settings.llm_provider.lower()
        if provider == "mock" or not self.settings.llm_api_key:
            answer = self._mock_chat(message)["answer"]
            yield {"content": answer}
            yield {"done": True}
            return

        use_model = model or self.settings.llm_model or "default"
        url = self.settings.llm_base_url.rstrip("/") + "/chat/completions"
        user_content = message
        if context:
            user_content += f"\n\n[当前系统上下文]\n{json.dumps(context, ensure_ascii=False, default=str)}"

        payload = {
            "model": use_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
            "stream": True,
        }
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                async with client.stream("POST", url, json=payload, headers=headers) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield {"content": content}
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
            yield {"done": True}
        except Exception as e:
            yield {"error": str(e)}
            yield {"done": True}

    def generate_damage_report_sync(
        self, tool_name: str, tool_class: str, status: str, anomaly_score: float,
        model_used: str, severity: str, confidence: float, image_path: str = "",
        heatmap_path: str = "",
    ) -> str:
        """根据损坏检测结果生成自然语言报告。优先用 kimi-k3 多模态看图，失败回退 GLM 文本。"""
        provider = self.settings.llm_provider.lower()
        if provider == "mock" or not self.settings.llm_api_key:
            return self._mock_damage_report(tool_name, status, anomaly_score)

        # 优先：有图片且配置了视觉模型时，用多模态看图写报告
        if image_path and self.settings.llm_vision_model:
            vision_report = self._generate_vision_report(
                image_path, tool_name, tool_class, status,
                anomaly_score, model_used, severity, confidence,
                heatmap_path=heatmap_path,
            )
            if vision_report:
                return vision_report
            logger.warning("视觉报告生成失败，回退到文本报告")

        # 回退：纯文本 GLM 报告
        return self._generate_text_report(
            tool_name, tool_class, status, anomaly_score,
            model_used, severity, confidence,
        )

    def _shrink_image_to_base64(self, image_path: str, max_side: int = 1024, quality: int = 85) -> str:
        """压缩图片为 base64（JPEG，限边长），适配多模态 API 输入。"""
        img = Image.open(image_path).convert("RGB")
        w, h = img.size
        if max(w, h) > max_side:
            ratio = max_side / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=quality)
        return base64.b64encode(buf.getvalue()).decode()

    def _generate_vision_report(
        self, image_path: str, tool_name: str, tool_class: str, status: str,
        anomaly_score: float, model_used: str, severity: str, confidence: float,
        heatmap_path: str = "",
    ) -> str:
        """用多模态视觉模型（kimi-k3）看图生成损坏检测报告。失败返回空串。"""
        self._rate_limit_vision()
        if not os.path.isfile(image_path):
            logger.warning("图片不存在，跳过视觉报告: %s", image_path)
            return ""

        try:
            img_b64 = self._shrink_image_to_base64(image_path)
        except Exception:
            logger.exception("图片压缩失败: %s", image_path)
            return ""

        # 加载热力图（如果有）
        heatmap_b64 = ""
        if heatmap_path and os.path.isfile(heatmap_path):
            try:
                heatmap_b64 = self._shrink_image_to_base64(heatmap_path, max_side=512)
            except Exception:
                logger.warning("热力图压缩失败: %s", heatmap_path)

        api_key = self.settings.llm_vision_api_key or self.settings.llm_api_key
        base_url = self.settings.llm_vision_base_url or self.settings.llm_base_url
        url = base_url.rstrip("/") + "/chat/completions"
        model = self.settings.llm_vision_model

        if tool_class:
            user_text = (
                f"工具台账：{tool_name or '未知工具'}（类别：{tool_class}）\n"
                f"云端异常检测：异常分数 {anomaly_score:.2f}，自动判定 {status}，置信度 {confidence:.2f}\n"
                "图片来源：工具箱内部固定摄像头自动拍摄，画面可能有固定柱状结构遮挡部分区域，属正常现象。\n\n"
                "请观察这张工具实拍照片，结合检测数据写一段损坏评估检查记录。"
                "若照片中工具与台账类别明显不符，请在报告中指出。"
            )
            if heatmap_b64:
                user_text += "\n\n第二张图是异常检测热力图（红=高异常，蓝=低异常），用于辅助定位潜在损坏区域，请结合热力图关注高异常区域的具体状况。"
        else:
            user_text = (
                "请识别照片中的工具类型，观察其外观状况，"
                f"结合云端异常检测数据（异常分数 {anomaly_score:.2f}，自动判定 {status}）"
                "写一段损坏评估检查记录，包含：工具类型、外观描述、风险等级、处置建议。"
            )
            if heatmap_b64:
                user_text += "\n\n第二张图是异常检测热力图（红=高异常，蓝=低异常），用于辅助定位潜在损坏区域，请结合热力图关注高异常区域的具体状况。"
        combined_text = DAMAGE_VISION_SYSTEM_PROMPT + "\n\n" + user_text
        content_parts = [
            {"type": "text", "text": combined_text},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
        ]
        if heatmap_b64:
            content_parts.append(
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{heatmap_b64}"}},
            )
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": content_parts},
            ],
            "max_tokens": 4096,
            "reasoning_effort": "low",
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        for attempt in range(2):
            try:
                with httpx.Client(timeout=120) as client:
                    resp = client.post(url, json=payload, headers=headers)
                    if resp.status_code != 200:
                        logger.warning("视觉模型返回 %d: %s", resp.status_code, resp.text[:200])
                        if attempt == 0:
                            import time; time.sleep(5)
                            continue
                    resp.raise_for_status()
                    data = resp.json()
                content = data["choices"][0]["message"].get("content", "").strip()
                if not content:
                    logger.warning("视觉模型返回空 content（可能 reasoning 耗尽 tokens）")
                    return ""
                logger.info("视觉报告生成成功 (model=%s, %d字)", data.get("model", model), len(content))
                import re as _re
                judge_match = _re.search(r'\[JUDGE:(低|中|高)\]', content)
                if judge_match:
                    content = _re.sub(r'\s*\[JUDGE:(低|中|高)\]\s*$', '', content).strip()
                logger.info("视觉报告生成成功 (model=%s, %d字, judge=%s)", data.get("model", model), len(content), judge_match.group(1) if judge_match else "none")
                return content
            except Exception:
                if attempt == 0:
                    logger.warning("视觉模型第1次调用失败，5s后重试")
                    import time; time.sleep(5)
                    continue
                logger.exception("视觉模型调用失败（重试后仍失败）")
                return ""

    def locate_tool_vision(self, image_path: str, tool_name: str, tool_class: str) -> list[float] | None:
        """用 kimi-k3 多模态在整图中定位目标工具，返回归一化 bbox [x1,y1,x2,y2] 或 None。

        用于 YOLO detect-tools 找不到匹配工具时的回退。
        """
        if not os.path.isfile(image_path):
            return None
        if not self.settings.llm_vision_model:
            return None

        try:
            img_b64 = self._shrink_image_to_base64(image_path)
        except Exception:
            logger.exception("定位图片压缩失败: %s", image_path)
            return None

        api_key = self.settings.llm_vision_api_key or self.settings.llm_api_key
        base_url = self.settings.llm_vision_base_url or self.settings.llm_base_url
        url = base_url.rstrip("/") + "/chat/completions"
        model = self.settings.llm_vision_model

        if tool_class:
            prompt = (
                f"请在这张照片中找到工具「{tool_name or '未知工具'}」（类别：{tool_class}）。\n"
                "返回该工具在图片中的位置，格式为四个 0~1 的归一化坐标 [x1, y1, x2, y2]：\n"
                "- (x1,y1) 是工具区域左上角，(x2,y2) 是右下角\n"
                "- 坐标相对于图片宽高归一化（0=最左/最上，1=最右/最下）\n"
                "- 如果图中只有一个工具，返回 [0, 0, 1, 1]\n"
                "- 如果找不到该工具，返回 [0, 0, 0, 0]\n"
                "只返回方括号内的四个数字，不要其他文字。"
            )
        else:
            prompt = (
                "请找到图中主要工具的位置，返回格式为四个 0~1 的归一化坐标 [x1, y1, x2, y2]：\n"
                "- (x1,y1) 是工具区域左上角，(x2,y2) 是右下角\n"
                "- 坐标相对于图片宽高归一化（0=最左/最上，1=最右/最下）\n"
                "- 如果图中只有一个工具，返回 [0, 0, 1, 1]\n"
                "- 如果找不到工具，返回 [0, 0, 0, 0]\n"
                "只返回方括号内的四个数字，不要其他文字。"
            )
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            ]}],
            "temperature": 0.1,
            "max_tokens": 1024,
            "reasoning_effort": "low",
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            content = data["choices"][0]["message"].get("content", "").strip()
            if not content:
                return None
            # Extract first 4 floats from the response (kimi-k3 may prepend reasoning)
            nums = re.findall(r"0?\.\d+|[01]\b", content)
            if len(nums) < 4:
                return None
            bbox = [float(nums[i]) for i in range(4)]
            # Clamp to [0, 1]
            bbox = [max(0.0, min(1.0, v)) for v in bbox]
            # [0,0,0,0] means not found
            if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
                logger.info("kimi-k3 定位：未找到工具 %s, raw=%s", tool_name, content[:80])
                return None
            logger.info("kimi-k3 定位成功: %s bbox=%s", tool_name, [round(v, 3) for v in bbox])
            return bbox
        except Exception:
            logger.exception("kimi-k3 工具定位失败")
            return None

    def _generate_text_report(
        self, tool_name: str, tool_class: str, status: str, anomaly_score: float,
        model_used: str, severity: str, confidence: float,
    ) -> str:
        """纯文本 GLM 报告（视觉失败时的回退）。"""
        prompt = (
            f"工具名称：{tool_name or '未知工具'}\n"
            f"工具类别：{tool_class or '未知'}\n"
            f"检测结果：{status}\n"
            f"异常分数：{anomaly_score:.2f}\n"
            f"置信度：{confidence:.2f}\n"
            f"检测模型：{model_used}\n\n"
            "请根据以上云端异常检测结果，用中文生成一段简洁的损坏评估报告（80字以内），"
            "包括：异常情况描述、风险等级判断、处置建议。不要出现英文或技术术语。"
        )
        url = self.settings.llm_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.llm_model or "default",
            "messages": [
                {"role": "system", "content": DAMAGE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
        }
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            content = data["choices"][0]["message"].get("content", "").strip()
            return content or f"[{model_used}] 异常分数 {anomaly_score:.2f}，状态：{status}。请人工复核。"
        except Exception:
            return f"[{model_used}] 异常分数 {anomaly_score:.2f}，状态：{status}。LLM 报告生成失败，请人工复核。"

    async def generate_damage_report(
        self, tool_name: str, tool_class: str, status: str, anomaly_score: float,
        model_used: str, severity: str, confidence: float
    ) -> str:
        """根据损坏检测结果生成自然语言报告。"""
        provider = self.settings.llm_provider.lower()
        if provider == "mock" or not self.settings.llm_api_key:
            return self._mock_damage_report(tool_name, status, anomaly_score)

        prompt = (
            f"工具名称：{tool_name or '未知工具'}\n"
            f"工具类别：{tool_class or '未知'}\n"
            f"检测结果：{status}\n"
            f"异常分数：{anomaly_score:.2f}\n"
            f"置信度：{confidence:.2f}\n"
            f"检测模型：{model_used}\n\n"
            "请根据以上云端异常检测结果，用中文生成一段简洁的损坏评估报告（100字以内），"
            "包括：异常情况描述、风险等级判断、处置建议。"
        )
        url = self.settings.llm_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.llm_model or "default",
            "messages": [
                {"role": "system", "content": DAMAGE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 2048,
        }
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
            return data["choices"][0]["message"].get("content", "").strip() or f"[{model_used}] 异常分数 {anomaly_score:.2f}，状态：{status}。请人工复核。"
        except Exception:
            return f"[{model_used}] 异常分数 {anomaly_score:.2f}，状态：{status}。LLM 报告生成失败，请人工复核。"

    def _mock_damage_report(self, tool_name: str, status: str, anomaly_score: float) -> str:
        if status == "damaged":
            return f"该{tool_name or '工具'}检测到明显异常（异常分数 {anomaly_score:.2f}），存在损坏风险。建议立即停用并隔离，通知管理人员进行人工检查，确认后从工具柜中移除并登记更换。"
        if status == "suspected":
            return f"该{tool_name or '工具'}存在疑似异常（异常分数 {anomaly_score:.2f}），建议人工复核后再决定是否继续使用。"
        return f"该{tool_name or '工具'}未发现明显损坏（异常分数 {anomaly_score:.2f}），可正常使用。"

    async def analyze(self, context: dict, question: str = "") -> dict:
        """事件风险分析接口（原有功能）。"""
        prompt = self.build_analyze_prompt(context, question)
        provider = self.settings.llm_provider.lower()

        if provider == "mock" or not self.settings.llm_api_key:
            return self._mock_analyze(context, prompt)

        url = self.settings.llm_base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.settings.llm_model or "default",
            "messages": [
                {"role": "system", "content": DAMAGE_SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 4096,
        }
        headers = {"Authorization": f"Bearer {self.settings.llm_api_key}"}
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        msg = data["choices"][0]["message"]
        content = msg.get("content", "").strip()
        return self._parse_response(content, prompt)

    def _mock_chat(self, message: str) -> dict:
        answer = (
            f"[Mock 模式] 收到您的问题：「{message}」\n\n"
            "当前未配置大模型 API，请在 backend/.env 中设置 LLM_PROVIDER、LLM_API_KEY、LLM_BASE_URL、LLM_MODEL。\n"
            "配置后重启后端即可使用真实大模型对话。"
        )
        return {"answer": answer, "model": "mock", "usage": {}}

    def _mock_analyze(self, context: dict, prompt: str) -> dict:
        raw_text = json.dumps(context, ensure_ascii=False)
        high_markers = ["misplaced", "anomaly", "warning", "uncertain", "未授权", "错放"]
        medium_markers = ["borrowed", "return", "missing"]
        if any(marker in raw_text for marker in high_markers):
            risk = "high"
            summary = "检测到工具状态异常或识别不确定，存在 FOD 管控风险。"
            action = "请管理员复核对应槽位和操作者记录，必要时要求重新扫描并锁定工具箱。"
        elif any(marker in raw_text for marker in medium_markers):
            risk = "medium"
            summary = "检测到工具借还行为，请关注是否按时归还。"
            action = "保持记录同步，若超过规定时长未归还则升级告警。"
        else:
            risk = "low"
            summary = "当前记录未发现明显异常。"
            action = "继续保持设备在线和日志同步。"
        response = {"risk_level": risk, "summary": summary, "suggested_action": action}
        return {"parsed": response, "raw": json.dumps(response, ensure_ascii=False), "prompt": prompt}

    def _parse_response(self, content: str, prompt: str) -> dict:
        # Try to parse JSON if present
        parsed = {}
        try:
            clean = content.strip().strip("`").strip()
            if clean.startswith("json"):
                clean = clean[4:].strip()
            start = clean.find("{")
            end = clean.rfind("}")
            if start >= 0 and end >= start:
                parsed = json.loads(clean[start : end + 1])
        except (json.JSONDecodeError, ValueError):
            parsed = {}

        # If JSON parsing failed, treat the whole content as summary text
        if not parsed:
            # Try to extract risk level from text
            text_lower = content.lower()
            if any(w in text_lower for w in ["高风险", "high", "严重", "紧急"]):
                risk = "high"
            elif any(w in text_lower for w in ["中风险", "medium", "注意", "一般"]):
                risk = "medium"
            else:
                risk = "low"
            parsed = {
                "risk_level": risk,
                "summary": content[:500] if content else "分析结果为空。",
                "suggested_action": "请管理员根据以上分析复核该事件。",
            }
        else:
            parsed.setdefault("risk_level", "medium")
            parsed.setdefault("summary", content[:500] if content else "分析结果为空。")
            parsed.setdefault("suggested_action", "请管理员复核该事件。")

        return {"parsed": parsed, "raw": content, "prompt": prompt}


llm_service = LlmService()
