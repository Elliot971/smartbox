<template>
  <section class="panel pad">
    <div class="section-title">
      <h2>异常告警</h2>
      <div style="display:flex; gap:8px;">
        <button class="btn" @click="load">刷新</button>
        <button class="btn btn-danger" @click="clearAll">清空全部</button>
      </div>
    </div>
    <table class="table">
      <thead>
        <tr>
          <th>ID</th>
          <th>设备</th>
          <th>级别</th>
          <th>标题</th>
          <th>描述</th>
          <th>状态</th>
          <th>时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="alert in alerts" :key="alert.id">
          <td>{{ alert.id }}</td>
          <td>{{ alert.device_code }}</td>
          <td><span class="badge" :class="alert.severity">{{ alert.severity }}</span></td>
          <td>{{ alert.title }}</td>
          <td>{{ alert.description }}</td>
          <td>{{ alert.status }}</td>
          <td>{{ formatTime(alert.created_at) }}</td>
          <td><button class="btn small danger" @click="remove(alert.id)">删除</button></td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { fetchAlerts, deleteAlert, clearAllAlerts, type AlertItem } from '../api/client';
import { useRealtime } from '../stores/useRealtime';

const alerts = ref<AlertItem[]>([]);

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-';
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
