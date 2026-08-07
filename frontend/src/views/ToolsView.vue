<template>
  <section class="grid cols-3">
    <!-- 添加/编辑工具表单 -->
    <div class="panel pad">
      <div class="section-title">
        <h2>{{ editingId ? '编辑工具' : '添加工具' }}</h2>
      </div>

      <label>工具编号 *</label>
      <input v-model="form.tool_code" class="input" placeholder="如 W-001" style="margin: 6px 0 12px;" />

      <label>工具名称 *</label>
      <input v-model="form.tool_name" class="input" placeholder="如 扭矩扳手" style="margin: 6px 0 12px;" />

      <label>工具类别</label>
      <select v-model="form.tool_class" class="select" style="margin: 6px 0 12px;">
        <option value="">-- 请选择 --</option>
        <option v-for="c in toolClasses" :key="c.value" :value="c.value">{{ c.label }}</option>
      </select>

      <label>规格型号</label>
      <input v-model="form.spec" class="input" placeholder="如 10-100N·m" style="margin: 6px 0 12px;" />

      <label>状态</label>
      <select v-model="form.status" class="select" style="margin: 6px 0 12px;">
        <option value="present">在位</option>
        <option value="borrowed">已借出</option>
        <option value="uncertain">待确认</option>
        <option value="damaged">损坏</option>
      </select>

      <label>工具图片</label>
      <div class="upload-area" @click="triggerFileInput" @dragover.prevent @drop.prevent="handleDrop">
        <template v-if="previewUrl">
          <img :src="previewUrl" class="preview-img" />
          <span class="upload-hint">点击更换图片</span>
        </template>
        <template v-else>
          <span class="upload-icon">+</span>
          <span class="upload-hint">点击或拖拽上传图片</span>
        </template>
        <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="handleFileChange" />
      </div>

      <div style="display:flex; gap:8px; margin-top:16px;">
        <button class="btn" style="flex:1" :disabled="saving" @click="save">
          {{ saving ? '保存中...' : (editingId ? '更新' : '添加') }}
        </button>
        <button v-if="editingId" class="btn btn-secondary" @click="resetForm">取消</button>
      </div>
    </div>

    <!-- 工具列表 -->
    <div class="panel pad" style="grid-column: span 2;">
      <div class="section-title">
        <h2>工具列表 ({{ tools.length }})</h2>
        <input v-model="search" class="input" placeholder="搜索名称或编号..." style="width:200px; padding:6px 10px;" />
      </div>

      <div class="tool-grid">
        <div v-for="tool in filteredTools" :key="tool.id" class="tool-card">
          <div class="tool-img-wrap">
            <img v-if="tool.image_url" :src="tool.image_url" class="tool-thumb" />
            <div v-else class="tool-thumb-placeholder">{{ tool.tool_name.charAt(0) }}</div>
          </div>
          <div class="tool-info">
            <div class="tool-name">{{ tool.tool_name }}</div>
            <div class="tool-code">{{ tool.tool_code }} · {{ tool.tool_class || '未分类' }}</div>
            <div class="tool-spec">{{ tool.spec || '无规格' }}</div>
            <span class="badge" :class="tool.status">{{ statusLabel(tool.status) }}</span>
          </div>
          <div class="tool-actions">
            <button class="btn-sm" @click="editTool(tool)">编辑</button>
            <button class="btn-sm btn-danger" @click="tool.id != null && removeTool(tool.id)">删除</button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { createTool, deleteTool, fetchTools, updateTool, uploadToolImageDirect, type Tool } from '../api/client';

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
const search = ref('');
const saving = ref(false);
const editingId = ref<number | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);
const pendingFile = ref<File | null>(null);
const previewUrl = ref('');

const form = ref<Tool>({
  tool_code: '',
  tool_name: '',
  tool_class: '',
  spec: '',
  status: 'present',
  image_url: '',
});

const filteredTools = computed(() => {
  const q = search.value.trim().toLowerCase();
  if (!q) return tools.value;
  return tools.value.filter(t =>
    t.tool_name.toLowerCase().includes(q) || t.tool_code.toLowerCase().includes(q)
  );
});

function statusLabel(status: string) {
  const map: Record<string, string> = {
    present: '在位', borrowed: '已借出', uncertain: '待确认', damaged: '损坏', missing: '丢失', wrong: '放错',
  };
  return map[status] || status;
}

async function loadTools() {
  tools.value = await fetchTools();
}

function triggerFileInput() {
  fileInput.value?.click();
}

function handleFileChange(e: Event) {
  const target = e.target as HTMLInputElement;
  if (target.files && target.files[0]) {
    setFile(target.files[0]);
  }
}

function handleDrop(e: DragEvent) {
  const files = e.dataTransfer?.files;
  if (files && files[0]) {
    setFile(files[0]);
  }
}

function setFile(file: File) {
  pendingFile.value = file;
  previewUrl.value = URL.createObjectURL(file);
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
        delete (payload as any).image_url;
        const newTool = await createTool(payload);
        await uploadToolImageDirect(newTool.id!, pendingFile.value);
      } else {
        await createTool(payload);
      }
    }
    await loadTools();
    resetForm();
  } catch (err: any) {
    console.error('保存失败:', err);
    alert(err?.response?.data?.detail || err?.message || '保存失败');
  } finally {
    saving.value = false;
  }
}

function editTool(tool: Tool) {
  editingId.value = tool.id!;
  form.value = { ...tool };
  previewUrl.value = tool.image_url || '';
  pendingFile.value = null;
}

function resetForm() {
  editingId.value = null;
  form.value = { tool_code: '', tool_name: '', tool_class: '', spec: '', status: 'present', image_url: '' };
  previewUrl.value = '';
  pendingFile.value = null;
}

async function removeTool(id: number) {
  if (!confirm('确认删除该工具？')) return;
  await deleteTool(id);
  await loadTools();
}

onMounted(loadTools);
</script>

<style scoped>
.upload-area {
  border: 2px dashed var(--border, #444);
  border-radius: 8px;
  height: 140px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  gap: 6px;
  transition: border-color 0.2s;
  overflow: hidden;
  position: relative;
}
.upload-area:hover { border-color: var(--primary, #4a9eff); }
.preview-img { max-height: 110px; max-width: 90%; border-radius: 6px; }
.upload-icon { font-size: 32px; color: #94a3b8; }
.upload-hint { font-size: 12px; color: #94a3b8; }

.tool-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 12px;
}
.tool-card {
  background: var(--bg-panel, #1e1e2e);
  border: 1px solid var(--border, #333);
  border-radius: 10px;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.tool-img-wrap {
  height: 120px;
  background: var(--bg-dark, #141420);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}
.tool-thumb { max-height: 100%; max-width: 100%; object-fit: contain; }
.tool-thumb-placeholder {
  width: 48px; height: 48px;
  border-radius: 50%;
  background: var(--primary-dim, #2a3a5a);
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; font-weight: bold;
  color: #cbd5e1;
}
.tool-info { padding: 10px 12px; flex: 1; }
.tool-name { font-weight: 600; font-size: 14px; margin-bottom: 2px; }
.tool-code { font-size: 12px; color: #94a3b8; margin-bottom: 2px; }
.tool-spec { font-size: 11px; color: #94a3b8; margin-bottom: 6px; }
.tool-actions { display: flex; gap: 6px; padding: 0 12px 12px; }
.btn-sm {
  flex: 1; padding: 4px 8px; border-radius: 6px;
  border: 1px solid var(--border, #444);
  background: transparent; color: #e2e8f0;
  cursor: pointer; font-size: 12px;
}
.btn-sm:hover { background: var(--bg-darker, #2a2a3e); }
.btn-danger { color: var(--danger, #ff5555); border-color: var(--danger-dim, #553333); }
.btn-danger:hover { background: var(--danger-dim, #332222); }
</style>
