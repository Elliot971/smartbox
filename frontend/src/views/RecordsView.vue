<template>
  <section class="panel pad">
    <div class="section-title">
      <h2>借还记录</h2>
      <button class="btn" @click="load">刷新</button>
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
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { fetchEvents, type OperationRecord } from '../api/client';
import { useRealtime } from '../stores/useRealtime';

const events = ref<OperationRecord[]>([]);

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-';
}

async function load() {
  events.value = await fetchEvents(50);
}

useRealtime(load);
onMounted(load);
</script>

