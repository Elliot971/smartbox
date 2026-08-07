<template>
  <section class="panel pad">
    <div class="section-title">
      <h2>异常告警</h2>
      <div style="display:flex; gap:8px; align-items:center;">
        <button class="filter-tab" :class="{active: filter==='all'}" @click="filter='all'">全部</button>
        <button class="filter-tab" :class="{active: filter==='open'}" @click="filter='open'">未处理</button>
        <button class="filter-tab" :class="{active: filter==='closed'}" @click="filter='closed'">已处理</button>
        <button class="btn" @click="load">刷新</button>
        <button class="btn btn-danger" @click="clearAll">清空全部</button>
      </div>
    </div>
    <div class="alert-list">
      <div v-for="alert in filteredAlerts" :key="alert.id" class="alert-card" :class="alert.severity">
        <div class="alert-header">
          <span class="badge" :class="alert.severity">{{ severityText(alert.severity) }}</span>
          <span class="alert-title">{{ alert.title }}</span>
          <span class="alert-status" :class="alert.status">{{ statusText(alert.status) }}</span>
          <span class="alert-time">{{ formatTime(alert.created_at) }}</span>
        </div>
        <div class="alert-desc">{{ alert.description }}</div>
        <div class="alert-meta" v-if="parseMeta(alert.description).hasMeta">
          <span v-if="parseMeta(alert.description).scoreInfo" class="meta-item score">
            分数: {{ parseMeta(alert.description).scoreInfo }}
          </span>
          <span v-if="parseMeta(alert.description).operatorInfo" class="meta-item operator">
            操作人: {{ parseMeta(alert.description).operatorInfo }}
          </span>
        </div>
        <div class="alert-actions">
          <button class="btn small danger" @click="remove(alert.id)">删除</button>
        </div>
      </div>
      <div v-if="filteredAlerts.length === 0" class="muted" style="text-align:center; padding:24px;">
        暂无异常告警。
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { fetchAlerts, deleteAlert, clearAllAlerts, type AlertItem } from '../api/client';
import { useRealtime } from '../stores/useRealtime';

import { computed, onMounted, ref } from 'vue';
const alerts = ref<AlertItem[]>([]);
const filter = ref<'all' | 'open' | 'closed'>('all');
const filteredAlerts = computed(() => {
  if (filter.value === 'all') return alerts.value;
  return alerts.value.filter(a => a.status === filter.value);
});

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-';
}

function severityText(s: string) {
  const map: Record<string, string> = { high: '高危', medium: '中危', low: '低危' };
  return map[s] || s;
}

function statusText(s: string) {
  const map: Record<string, string> = { open: '未处理', closed: '已处理' };
  return map[s] || s;
}

function parseMeta(desc: string) {
  // 兼容新旧格式：分数变化： 或 异常分数: 或 分数：
  const scoreMatch = desc.match(/分数变化：\s*([\d.→]+)/) || desc.match(/异常分数:\s*([\d.→]+)/) || desc.match(/分数：\s*([\d.]+)/);
  const operatorMatch = desc.match(/最近操作人：\s*([^|()]+)/) || desc.match(/最近操作人:\s*([^|()]+)/);
  // 清理操作人信息：去掉括号内容
  let operatorInfo = operatorMatch ? operatorMatch[1].trim() : '';
  // 去掉可能的括号残留
  operatorInfo = operatorInfo.replace(/\(.*\)/, '').trim();
  return {
    hasMeta: !!(scoreMatch || operatorMatch),
    scoreInfo: scoreMatch ? scoreMatch[1].trim() : '',
    operatorInfo: operatorInfo,
  };
}

async function load() {
  alerts.value = await fetchAlerts(50);
}

async function remove(id: number) {
  if (!confirm('确认删除该告警记录？')) return;
  try {
    await deleteAlert(id);
    await load();
  } catch (err: any) {
    alert('删除失败：' + (err?.message || '未知错误'));
  }
}

async function clearAll() {
  if (!confirm('确认清空所有异常告警记录？此操作不可恢复。')) return;
  try {
    const res = await clearAllAlerts();
    alert(`已清空 ${res.deleted} 条告警记录`);
    await load();
  } catch (err: any) {
    alert('清空失败：' + (err?.message || '未知错误'));
  }
}

useRealtime(load);
onMounted(load);
</script>

<style scoped>
.alert-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.alert-card {
  padding: 14px 16px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  border-radius: 8px;
  background: rgba(15, 23, 42, 0.6);
}
.alert-card.high {
  border-left: 3px solid #ef4444;
}
.alert-card.medium {
  border-left: 3px solid #f59e0b;
}
.alert-card.low {
  border-left: 3px solid #22c55e;
}
.alert-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
.alert-title {
  font-weight: 600;
  font-size: 14px;
  flex: 1;
}
.alert-status {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
}
.alert-status.open {
  background: rgba(239, 68, 68, 0.15);
  color: #fca5a5;
}
.alert-status.closed {
  background: rgba(34, 197, 94, 0.15);
  color: #86efac;
}
.alert-time {
  font-size: 12px;
  color: #94a3b8;
}
.alert-desc {
  font-size: 13px;
  color: #cbd5e1;
  line-height: 1.5;
  margin-bottom: 6px;
}
.alert-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.meta-item {
  font-size: 12px;
  padding: 3px 8px;
  border-radius: 4px;
}
.meta-item.score {
  background: rgba(245, 158, 11, 0.12);
  color: #fcd34d;
}
.meta-item.operator {
  background: rgba(96, 165, 250, 0.12);
  color: #93c5fd;
}
.alert-actions {
  display: flex;
  gap: 8px;
}
.filter-tab {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.2);
  color: #94a3b8;
  padding: 6px 14px;
  border-radius: 999px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}
.filter-tab:hover { color: #cbd5e1; }
.filter-tab.active {
  background: rgba(37, 99, 235, 0.2);
  color: #93c5fd;
  border-color: rgba(37, 99, 235, 0.4);
}
</style>