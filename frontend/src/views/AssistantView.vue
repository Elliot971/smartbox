<template>
  <section class="assistant-grid">
    <!-- 左侧：模式选择 + 输入 -->
    <div class="panel pad sidebar-panel">
      <div class="tabs">
        <button class="tab" :class="{ active: mode === 'chat' }" @click="switchMode('chat')">车间问答</button>
        <button class="tab" :class="{ active: mode === 'analyze' }" @click="switchMode('analyze')">事件分析</button>
      </div>

      <!-- 车间问答模式 -->
      <template v-if="mode === 'chat'">
        <label class="field-label">模型选择</label>
        <div class="model-options">
          <button
            v-for="m in models"
            :key="m.id"
            class="model-card"
            :class="{ active: selectedModel === m.id }"
            @click="selectedModel = m.id"
          >
            <span class="model-icon" :style="{ background: m.color }">{{ m.abbr }}</span>
            <div class="model-text">
              <div class="model-name">{{ m.label }}</div>
              <div class="model-desc">{{ m.desc }}</div>
            </div>
          </button>
        </div>

        <label class="field-label">向 FOD 智能助手提问</label>
        <div class="quick-questions">
          <button v-for="q in quickQuestions" :key="q" class="quick-q" @click="chatMessage = q">{{ q }}</button>
        </div>
        <textarea v-model="chatMessage" class="input chat-input" rows="5" placeholder="例如：扭矩扳手有什么功能？螺丝刀使用后怎么维护？"></textarea>
        <button class="btn send-btn" :disabled="loading" @click="askChat">
          {{ loading ? '思考中...' : '发送问题' }}
        </button>
      </template>

      <!-- 事件分析模式 -->
      <template v-else>
        <label class="field-label">分析目标</label>
        <select v-model="targetType" class="select" style="margin: 6px 0 16px;">
          <option value="alert">异常告警</option>
          <option value="event">借还事件</option>
        </select>
        <label class="field-label">目标 ID</label>
        <input v-model.number="targetId" class="input" type="number" min="1" style="margin: 6px 0 16px;" />
        <label class="field-label">问题</label>
        <textarea v-model="question" class="input chat-input" rows="5"></textarea>
        <button class="btn send-btn" :disabled="loading" @click="analyze">
          {{ loading ? '分析中...' : '调用大模型分析' }}
        </button>
      </template>
    </div>

    <!-- 右侧：结果展示 -->
    <div class="panel pad result-panel">
      <div class="section-title">
        <h2 class="result-title">{{ mode === 'chat' ? '助手回答' : '分析结果' }}</h2>
        <span v-if="mode === 'chat' && chatResult" class="model-badge">{{ chatResult.model }}</span>
        <span v-if="mode === 'analyze' && result" class="badge" :class="result.risk_level">{{ result.risk_level }}</span>
      </div>

      <!-- 车间问答结果 -->
      <template v-if="mode === 'chat'">
        <div class="chat-output">
          <template v-if="chatResult">
            <div class="chat-answer" v-html="renderAnswer(chatResult.answer)"></div>
            <div class="chat-meta" v-if="chatResult.model">模型：{{ chatResult.model }}</div>
          </template>
          <template v-else>
            <div class="placeholder-text">
              向 FOD 智能助手提问，获取工具功能、维修规范、车间常见问题的专业解答。
              <br /><br />
              可以问：
              <ul>
                <li>扭矩扳手有什么功能？怎么正确使用？</li>
                <li>螺丝刀使用后怎么维护保养？</li>
                <li>车间发现工具丢失该怎么处理？</li>
                <li>扳手打滑导致螺栓损伤怎么办？</li>
              </ul>
            </div>
          </template>
        </div>
      </template>

      <!-- 事件分析结果 -->
      <template v-else>
        <div class="assistant-output analyze-output">
          <template v-if="result">
风险等级：{{ result.risk_level }}

摘要：
{{ result.summary }}

处置建议：
{{ result.suggested_action }}
          </template>
          <template v-else>
选择一条异常或借还事件，系统会把结构化记录发送给云端大模型，生成 FOD 风险等级、原因摘要和处置建议。
          </template>
        </div>
      </template>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { analyzeTarget, chatWithAssistantStream } from '../api/client';

const mode = ref<'chat' | 'analyze'>('chat');
const loading = ref(false);

const models = [
  { id: 'zai-org/glm-5.2', label: 'GLM-5.2', abbr: 'GLM', color: '#2563eb', desc: '通用对话，快速响应' },
  { id: 'moonshotai/kimi-k2.7-code', label: 'Kimi K2.7', abbr: 'KIMI', color: '#7c3aed', desc: '代码与逻辑推理' },
  { id: 'deepseek/deepseek-v4-pro', label: 'DeepSeek V4', abbr: 'DS', color: '#059669', desc: '深度推理分析' },
];
const selectedModel = ref('zai-org/glm-5.2');

// 车间问答
const chatMessage = ref('');
const chatResult = ref<{ answer: string; model: string } | null>(null);

const quickQuestions = [
  '扭矩扳手有什么功能？',
  '螺丝刀使用后怎么维护？',
  '工具丢失该怎么处理？',
  '什么是 FOD 风险？',
  '压线钳的正确使用方法',
  '锤子使用安全注意事项',
];

// 事件分析
const targetType = ref<'alert' | 'event'>('alert');
const targetId = ref(1);
const question = ref('请分析该记录是否存在 FOD 风险，并给出管理员处置建议。');
const result = ref<{ risk_level: string; summary: string; suggested_action: string } | null>(null);

function switchMode(m: 'chat' | 'analyze') {
  mode.value = m;
}

function renderAnswer(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/### (.*)/g, '<h4>$1</h4>')
    .replace(/## (.*)/g, '<h3>$1</h3>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br />');
}

async function askChat() {
  if (!chatMessage.value.trim()) return;
  loading.value = true;
  chatResult.value = { answer: '', model: selectedModel.value };
  try {
    for await (const chunk of chatWithAssistantStream(chatMessage.value, {}, selectedModel.value)) {
      chatResult.value = { ...chatResult.value, answer: chatResult.value.answer + chunk };
    }
  } catch (err: any) {
    chatResult.value = { answer: '请求失败：' + (err?.message || '未知错误'), model: selectedModel.value };
  } finally {
    loading.value = false;
  }
}

async function analyze() {
  loading.value = true;
  result.value = null;
  try {
    result.value = await analyzeTarget(targetType.value, targetId.value, question.value);
  } catch (err: any) {
    result.value = {
      risk_level: 'high',
      summary: '分析请求失败：' + (err?.response?.data?.detail || err?.message || '未知错误，请检查目标ID是否存在'),
      suggested_action: '请确认目标类型和ID正确，且后端大模型服务正常。',
    };
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.assistant-grid {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 16px;
  min-height: calc(100vh - 140px);
}

.field-label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: #cbd5e1;
  margin-bottom: 8px;
}

.model-options {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 18px;
}
.model-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 10px;
  background: transparent;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
}
.model-card:hover { border-color: #2563eb; background: rgba(37, 99, 235, 0.06); }
.model-card.active { border-color: #2563eb; background: rgba(37, 99, 235, 0.14); }

.model-icon {
  width: 40px; height: 40px;
  border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  font-size: 13px; font-weight: 800; color: #fff;
  flex-shrink: 0;
}
.model-text { flex: 1; }
.model-name { font-size: 14px; font-weight: 600; color: #e2e8f0; }
.model-desc { font-size: 12px; color: #94a3b8; margin-top: 2px; }

.tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 18px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.16);
}
.tab {
  flex: 1;
  padding: 10px 12px;
  border: none;
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-size: 14px;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}
.tab.active { color: #93c5fd; border-bottom-color: #2563eb; }
.tab:hover { color: #e2e8f0; }

.model-badge {
  display: inline-flex;
  padding: 5px 12px;
  border-radius: 999px;
  background: rgba(96, 165, 250, 0.14);
  color: #93c5fd;
  font-size: 12px;
}

.quick-questions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.quick-q {
  padding: 6px 12px;
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  background: transparent;
  color: #94a3b8;
  cursor: pointer;
  font-size: 13px;
  transition: all 0.2s;
}
.quick-q:hover { border-color: #2563eb; color: #93c5fd; }

.chat-input { font-size: 14px; }
.send-btn { margin-top: 14px; width: 100%; padding: 12px; font-size: 15px; }

.result-panel { display: flex; flex-direction: column; }
.result-title { font-size: 18px; }

.chat-output { flex: 1; min-height: 300px; }
.chat-answer {
  line-height: 1.9;
  font-size: 15px;
}
.chat-answer :deep(h3) { margin: 16px 0 8px; color: #93c5fd; font-size: 16px; }
.chat-answer :deep(h4) { margin: 14px 0 6px; color: #93c5fd; font-size: 15px; }

.chat-meta { margin-top: 20px; font-size: 12px; color: #94a3b8; }

.placeholder-text {
  color: #94a3b8; line-height: 2.2; font-size: 14px;
}
.placeholder-text ul { padding-left: 20px; margin-top: 10px; }
.placeholder-text li { margin: 6px 0; }

.analyze-output { font-size: 15px; line-height: 1.9; }

@media (max-width: 900px) {
  .assistant-grid { grid-template-columns: 1fr; }
}
</style>
