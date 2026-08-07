<template>
  <section class="panel pad">
    <div class="section-title">
      <h2>一号工具箱槽位状态</h2>
      <div style="display:flex; gap:8px; align-items:center;">
        <span class="muted" style="font-size:12px;">共 {{ tools.length }} 件工具 · 在位 {{ presentCount }} · 借出 {{ borrowedCount }}</span>
        <button class="btn" @click="showForm = !showForm">{{ showForm ? '收起' : '添加工具' }}</button>
        <button class="btn btn-secondary" @click="load">刷新</button>
      </div>
    </div>

    <!-- 添加/编辑工具表单 -->
    <div v-if="showForm" class="tool-form">
      <div class="form-row">
        <div>
          <label>工具编号 *</label>
          <input v-model="form.tool_code" class="input" placeholder="如 T-010" />
        </div>
        <div>
          <label>工具名称 *</label>
          <input v-model="form.tool_name" class="input" placeholder="如 扭矩扳手" />
        </div>
        <div>
          <label>类别</label>
          <select v-model="form.tool_class" class="select">
            <option value="">请选择</option>
            <option v-for="c in toolClasses" :key="c.value" :value="c.value">{{ c.label }}</option>
          </select>
        </div>
        <div>
          <label>规格</label>
          <input v-model="form.spec" class="input" placeholder="如 10-100N·m" />
        </div>
      </div>
      <div class="form-row" style="align-items:flex-end;">
        <div class="upload-box" @click="fileInput?.click()">
          <img v-if="previewUrl" :src="previewUrl" class="form-preview" />
          <span v-else class="upload-ph">+ 图片</span>
          <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="handleFile" />
        </div>
        <div style="display:flex; gap:8px; flex:1;">
          <button class="btn" :disabled="saving" @click="save">
            {{ saving ? '保存中...' : (editingId ? '更新' : '添加') }}
          </button>
          <button v-if="editingId" class="btn btn-secondary" @click="resetForm">取消</button>
        </div>
      </div>
    </div>

    <!-- 槽位网格 -->
    <div class="slot-grid">
      <div v-for="tool in mergedTools" :key="tool.id" class="slot-card" :class="tool.status">
        <div class="slot-head">
          <span>S{{ String(tool.slot_no || tool.id).padStart(2, '0') }}</span>
          <span class="badge" :class="tool.status">{{ statusText(tool.status) }}</span>
        </div>
        <div class="slot-img-wrap">
          <img v-if="tool.image_url" :src="tool.image_url" class="slot-img" />
          <div v-else class="slot-img-ph">{{ (tool.tool_name || '?').charAt(0) }}</div>
        </div>
        <span class="slot-name">{{ tool.tool_name || '未配置' }}</span>
        <span class="slot-code">{{ tool.tool_code || '-' }} · {{ classLabel(tool.tool_class) }}</span>
        <div v-if="tool.spec" class="slot-spec">{{ tool.spec }}</div>
        <div v-if="tool.confidence != null" class="slot-conf">置信度 {{ Math.round(tool.confidence * 100) }}%</div>
        <div class="slot-actions">
          <button class="btn small" @click="editTool(tool)">编辑</button>
          <button class="btn small btn-danger" @click="tool.id != null && removeTool(tool.id)">删除</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { createTool, deleteTool, fetchSlots, fetchTools, updateTool, uploadToolImageDirect, type SlotState, type Tool } from '../api/client';
import { useRealtime } from '../stores/useRealtime';

const toolClasses = [
  { value: 'screwdriver', label: '螺丝刀' },
  { value: 'socket_screwdriver', label: '套筒螺丝刀' },
  { value: 'pliers', label: '老虎钳' },
  { value: 'wrench', label: '扳手' },
  { value: 'crimper', label: '压线钳' },
  { value: 'electronic_pliers', label: '电子钳' },
  { value: 'hammer', label: '锤子' },
  { value: 'tape_measure', label: '卷尺' },
];

const tools = ref<Tool[]>([]);
const slotStates = ref<SlotState[]>([]);
const showForm = ref(false);
const saving = ref(false);
const editingId = ref<number | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const pendingFile = ref<File | null>(null);
const previewUrl = ref('');

const form = ref<Tool>({ tool_code: '', tool_name: '', tool_class: '', spec: '', status: 'present', image_url: '' });

// 合并工具台账 + 板端实时状态
const mergedTools = computed(() => {
  const stateMap = new Map(slotStates.value.map(s => [s.tool_code, s]));
  return tools.value.map((t, i) => {
    const live = stateMap.get(t.tool_code);
    return {
      ...t,
      slot_no: i + 1,
      status: live?.status || t.status,
      confidence: live?.confidence ?? null,
    };
  });
});

const presentCount = computed(() => mergedTools.value.filter(t => t.status === 'present' || t.status === 'available').length);
const borrowedCount = computed(() => mergedTools.value.filter(t => t.status === 'borrowed').length);

function statusText(status: string) {
  const map: Record<string, string> = { present: '在位', available: '在位', borrowed: '借出', misplaced: '错放', uncertain: '待确认', empty: '空槽', missing: '丢失', wrong: '错放', damaged: '损坏' };
  return map[status] || status;
}

function classLabel(cls: string) {
  const found = toolClasses.find(c => c.value === cls);
  return found ? found.label : cls || '未分类';
}

async function load() {
  const [toolList, slots] = await Promise.all([fetchTools(), fetchSlots()]);
  tools.value = toolList;
  slotStates.value = slots;
}

function editTool(tool: Tool) {
  editingId.value = tool.id!;
  form.value = { ...tool };
  previewUrl.value = tool.image_url || '';
  pendingFile.value = null;
  showForm.value = true;
}

function resetForm() {
  editingId.value = null;
  form.value = { tool_code: '', tool_name: '', tool_class: '', spec: '', status: 'present', image_url: '' };
  previewUrl.value = '';
  pendingFile.value = null;
}

function handleFile(e: Event) {
  const target = e.target as HTMLInputElement;
  if (target.files && target.files[0]) {
    pendingFile.value = target.files[0];
    previewUrl.value = URL.createObjectURL(target.files[0]);
  }
}

async function save() {
  if (!form.value.tool_code || !form.value.tool_name) {
    alert('请填写工具编号和名称');
    return;
  }
  saving.value = true;
  try {
    const payload = { ...form.value };
    delete (payload as any).id;
    delete (payload as any).created_at;
    if (editingId.value) {
      if (pendingFile.value) {
        delete (payload as any).image_url;
      }
      await updateTool(editingId.value, payload, pendingFile.value || undefined);
    } else {
      if (pendingFile.value) {
        // For new tool, create first then upload image
        delete (payload as any).image_url;
        const newTool = await createTool(payload);
        await uploadToolImageDirect(newTool.id!, pendingFile.value);
      } else {
        await createTool(payload);
      }
    }
    await load();
    resetForm();
    showForm.value = false;
  } catch (err: any) {
    console.error('保存失败:', err);
    const detail = err?.response?.data?.detail;
    const status = err?.response?.status;
    const message = err?.message;
    alert(`保存失败：${detail || message || '未知错误'} (HTTP ${status || '?'})`);
  } finally {
    saving.value = false;
  }
}

async function removeTool(id: number) {
  if (!confirm('确认删除该工具？')) return;
  await deleteTool(id);
  await load();
}

useRealtime(load);
onMounted(load);
</script>

<style scoped>
.tool-form {
  background: rgba(8, 13, 28, 0.6);
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 18px;
}
.form-row {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}
.form-row > div { flex: 1; }
.form-row label {
  display: block;
  font-size: 12px;
  color: #94a3b8;
  margin-bottom: 4px;
}
.upload-box {
  width: 80px;
  height: 80px;
  border: 2px dashed rgba(148, 163, 184, 0.3);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  overflow: hidden;
  flex-shrink: 0;
}
.upload-box:hover { border-color: #2563eb; }
.form-preview { max-width: 100%; max-height: 100%; object-fit: contain; }
.upload-ph { color: #94a3b8; font-size: 20px; }

.btn-secondary {
  background: rgba(148, 163, 184, 0.15);
  color: #cbd5e1;
}
.btn-danger {
  background: rgba(239, 68, 68, 0.2);
  color: #fca5a5;
}

.slot-img-wrap {
  height: 100px;
  margin-bottom: 10px;
  border-radius: 6px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
}
.slot-img { max-height: 100%; max-width: 100%; object-fit: contain; }
.slot-img-ph {
  width: 40px; height: 40px;
  border-radius: 50%;
  background: rgba(96, 165, 250, 0.14);
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; font-weight: bold; color: #93c5fd;
}
.slot-spec { font-size: 11px; color: #94a3b8; margin-top: 2px; }
.slot-conf { font-size: 11px; color: #94a3b8; margin-top: 2px; }
.slot-actions {
  display: flex;
  gap: 6px;
  margin-top: 10px;
}
.slot-actions .btn { flex: 1; }
</style>
