<template>
  <div class="grid">
    <!-- 工人上传照片检测 -->
    <section class="panel pad">
      <div class="section-title">
        <div>
          <h2>工具损坏检测</h2>
          <p class="muted">上传工具照片，云端 AI 模型（AnomalyDINO + AdaCLIP）自动检测损坏。板端传回的照片也会自动分析。</p>
        </div>
        <button class="btn" @click="loadAll">刷新</button>
      </div>

      <div class="upload-zone" @click="uploadInput?.click()" @dragover.prevent @drop.prevent="handleDrop">
        <template v-if="uploading">
          <span class="uploading-text">分析中... {{ uploadProgress }}</span>
        </template>
        <template v-else>
          <span class="upload-icon">+</span>
          <span class="upload-label">点击或拖拽上传工具照片</span>
          <span class="muted" style="font-size:11px;">支持 JPG/PNG，云端自动分析损坏</span>
        </template>
        <input ref="uploadInput" type="file" accept="image/*" style="display:none" @change="handleUpload" />
      </div>
    </section>

    <!-- 工具损坏检测结果概览 -->
    <section class="panel pad">
      <div class="section-title">
        <h2>工具检测概览</h2>
        <span class="muted">{{ toolSummary.length }} 件工具</span>
      </div>
      <div class="tool-damage-grid">
        <div v-for="tool in toolSummary" :key="tool.tool_id" class="tool-damage-card" :class="tool.latest_status">
          <div class="td-img-wrap">
            <img v-if="tool.image_url" :src="tool.image_url" class="td-img" />
            <div v-else class="td-img-ph">{{ tool.tool_name.charAt(0) }}</div>
          </div>
          <div class="td-info">
            <div class="td-name">{{ tool.tool_name }}
              <button class="td-del" title="删除该工具的检测记录" @click="removeTool(tool.tool_code)">删除</button>
            </div>
            <div class="td-code">{{ tool.tool_code }}</div>
            <span class="badge" :class="tool.latest_status">{{ statusText(tool.latest_status) }}</span>
            <div class="td-summary">{{ tool.latest_summary || '尚未检测' }}</div>
            <div class="td-count" v-if="tool.task_count > 0">历史检测 {{ tool.task_count }} 次</div>
          </div>
        </div>
      </div>
    </section>

    <!-- 检测任务列表 -->
    <section class="panel pad">
      <div class="section-title">
        <h2>检测任务记录</h2>
        <span class="muted">共 {{ tasks.length }} 条</span>
      </div>
      <div class="task-list">
        <div v-for="task in tasks.slice(0, 20)" :key="task.id" class="task-row">
          <div class="task-img-wrap">
            <img v-if="task.image_url" :src="task.image_url" class="task-img" />
            <div v-else class="task-img-ph">?</div>
          </div>
          <div class="task-info">
            <div class="task-name">{{ task.tool_name }} <span class="muted">({{ task.tool_code || '-' }})</span></div>
            <div class="task-summary">{{ task.summary || '待分析' }}</div>
            <div class="task-meta">{{ formatTime(task.updated_at) }}</div>
          </div>
          <div class="task-badges">
            <span class="badge" :class="task.status">{{ statusText(task.status) }}</span>
            <span class="badge" :class="task.severity">{{ task.severity }}</span>
            <span v-if="task.confidence != null" class="muted">{{ Math.round(task.confidence * 100) }}%</span>
          </div>
          <div class="task-actions">
            <button class="btn small" :disabled="analyzingId === task.id" @click="analyze(task.id)">
              {{ analyzingId === task.id ? '分析中' : '重新分析' }}
            </button>
            <button class="btn small danger" @click="remove(task.id)">删除</button>
          </div>
        </div>
        <div v-if="tasks.length === 0" class="muted" style="text-align:center; padding:24px;">
          暂无检测任务。上传工具照片或等板端传回照片后自动创建。
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import {
  analyzeDamageInspection,
  deleteDamageInspection,
  deleteToolInspections,
  fetchDamageInspections,
  fetchToolDamageSummary,
  uploadAndAnalyze,
  type DamageInspection,
  type ToolDamageSummary,
} from '../api/client';

const tasks = ref<DamageInspection[]>([]);
const toolSummary = ref<ToolDamageSummary[]>([]);
const uploading = ref(false);
const uploadProgress = ref('');
const analyzingId = ref<number | null>(null);
const uploadInput = ref<HTMLInputElement | null>(null);

function statusText(status: string) {
  const map: Record<string, string> = { pending: '待分析', normal: '正常', damaged: '损坏', suspected: '疑似异常', failed: '失败' };
  return map[status] || status;
}

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-';
}

async function loadAll() {
  const [t, s] = await Promise.all([fetchDamageInspections(80), fetchToolDamageSummary()]);
  tasks.value = t;
  toolSummary.value = s;
}

async function handleUpload(e: Event) {
  const target = e.target as HTMLInputElement;
  if (target.files && target.files[0]) {
    await doUpload(target.files[0]);
  }
}

function handleDrop(e: DragEvent) {
  const files = e.dataTransfer?.files;
  if (files && files[0]) {
    doUpload(files[0]);
  }
}

async function doUpload(file: File) {
  uploading.value = true;
  uploadProgress.value = '上传中...';
  try {
    uploadProgress.value = '云端分析中...';
    await uploadAndAnalyze(file);
    await loadAll();
  } catch (err: any) {
    alert('分析失败：' + (err?.message || '未知错误'));
  } finally {
    uploading.value = false;
    if (uploadInput.value) uploadInput.value.value = '';
  }
}

async function analyze(id: number) {
  analyzingId.value = id;
  try {
    await analyzeDamageInspection(id);
    await loadAll();
  } catch (err: any) {
    alert('重新分析失败：' + (err?.message || '未知错误'));
  } finally {
    analyzingId.value = null;
  }
}

async function remove(id: number) {
  if (!confirm('确认删除该检测记录？')) return;
  try {
    await deleteDamageInspection(id);
    await loadAll();
  } catch (err: any) {
    alert('删除失败：' + (err?.message || '未知错误'));
  }
}

async function removeTool(toolCode: string) {
  if (!confirm('确认删除该工具的所有检测记录？')) return;
  try {
    await deleteToolInspections(toolCode);
    await loadAll();
  } catch (err: any) {
    alert('删除失败：' + (err?.message || '未知错误'));
  }
}

onMounted(loadAll);
</script>

<style scoped>
.upload-zone {
  border: 2px dashed rgba(148, 163, 184, 0.22);
  border-radius: 10px;
  height: 120px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 6px;
  cursor: pointer;
  transition: border-color 0.2s;
}
.upload-zone:hover { border-color: #2563eb; }
.upload-icon { font-size: 28px; color: #94a3b8; }
.upload-label { font-size: 14px; color: #94a3b8; }
.uploading-text { color: #93c5fd; font-size: 14px; }

.tool-damage-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.tool-damage-card {
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 8px;
  overflow: hidden;
  background: rgba(15, 23, 42, 0.88);
}
.tool-damage-card.normal { border-color: rgba(34, 197, 94, 0.4); }
.tool-damage-card.damaged { border-color: rgba(239, 68, 68, 0.4); }
.tool-damage-card.suspected { border-color: rgba(245, 158, 11, 0.4); }

.td-img-wrap {
  height: 100px;
  background: rgba(0, 0, 0, 0.3);
  display: flex; align-items: center; justify-content: center;
  overflow: hidden;
}
.td-img { max-height: 100%; max-width: 100%; object-fit: contain; }
.td-img-ph {
  width: 36px; height: 36px; border-radius: 50%;
  background: rgba(96, 165, 250, 0.14);
  display: flex; align-items: center; justify-content: center;
  font-size: 16px; font-weight: bold; color: #93c5fd;
}
.td-info { padding: 10px 12px; }
.td-name { font-weight: 600; font-size: 14px; }
.td-code { font-size: 11px; color: #94a3b8; margin-bottom: 4px; }
.td-summary { font-size: 12px; color: #94a3b8; margin-top: 6px; line-height: 1.4; }
.td-count { font-size: 11px; color: #94a3b8; margin-top: 4px; }
.td-del {
  float: right;
  background: transparent;
  border: 1px solid rgba(239, 68, 68, 0.3);
  color: rgba(239, 68, 68, 0.8);
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s;
}
.td-del:hover { background: rgba(239, 68, 68, 0.15); color: #ef4444; }

.task-list { display: flex; flex-direction: column; gap: 8px; }
.task-row {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 10px;
  border: 1px solid rgba(148, 163, 184, 0.12);
  border-radius: 8px;
}
.task-img-wrap {
  width: 60px; height: 60px;
  border-radius: 6px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.3);
  flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
}
.task-img { max-width: 100%; max-height: 100%; object-fit: contain; }
.task-img-ph { color: #94a3b8; font-size: 20px; }
.task-info { flex: 1; }
.task-name { font-weight: 600; font-size: 13px; }
.task-summary { font-size: 12px; color: #94a3b8; margin: 2px 0; }
.task-meta { font-size: 11px; color: #94a3b8; }
.task-badges { display: flex; gap: 6px; align-items: center; }
.task-actions { flex-shrink: 0; }
</style>
