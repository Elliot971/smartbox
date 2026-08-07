<template>
  <section class="panel pad">
    <div class="section-title">
      <h2>借还记录</h2>
      <div style="display:flex; gap:8px; align-items:center;">
        <span class="muted" style="font-size:12px;">共 {{ total }} 条</span>
        <button class="btn" @click="load">刷新</button>
      </div>
    </div>
    <table class="table">
      <thead>
        <tr>
          <th>事件编号</th>
          <th>设备</th>
          <th>操作者</th>
          <th>结果</th>
          <th>开柜</th>
          <th>关柜</th>
          <th>同步</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="event in events" :key="event.id">
          <td>{{ event.event_id }}</td>
          <td>{{ event.device_code }}</td>
          <td>{{ event.operator_name || '-' }}</td>
          <td><span class="badge" :class="event.result_type">{{ event.result_type || '-' }}</span></td>
          <td>{{ formatTime(event.opened_at) }}</td>
          <td>{{ formatTime(event.closed_at) }}</td>
          <td>{{ formatTime(event.synced_at) }}</td>
        </tr>
      </tbody>
    </table>
    <div class="pagination">
      <button class="btn small" :disabled="page <= 1" @click="prevPage">上一页</button>
      <span class="muted" style="font-size:12px;">第 {{ page }} 页</span>
      <button class="btn small" :disabled="events.length < pageSize" @click="nextPage">下一页</button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { fetchEvents, type OperationRecord } from '../api/client';
import { useRealtime } from '../stores/useRealtime';

const events = ref<OperationRecord[]>([]);
const page = ref(1);
const pageSize = 20;
const total = ref(0);

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-';
}

async function load() {
  const offset = (page.value - 1) * pageSize;
  events.value = await fetchEvents(pageSize * 5);
  total.value = events.value.length;
  // 分页切片
  events.value = events.value.slice(offset, offset + pageSize);
}

function prevPage() {
  if (page.value > 1) {
    page.value--;
    load();
  }
}

function nextPage() {
  if (events.value.length >= pageSize) {
    page.value++;
    load();
  }
}

useRealtime(load);
onMounted(load);
</script>

<style scoped>
.pagination {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 12px;
  margin-top: 16px;
}
</style>