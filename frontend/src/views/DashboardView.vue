<template>
  <section class="grid cols-4">
    <div class="panel pad metric">
      <label>在线设备</label>
      <strong><span>{{ summary.online_devices }}</span> / {{ summary.devices_total }}</strong>
    </div>
    <div class="panel pad metric">
      <label>可用工具</label>
      <strong><span>{{ summary.tools_available }}</span> / {{ summary.tools_total }}</strong>
    </div>
    <div class="panel pad metric">
      <label>今日开柜</label>
      <strong><span>{{ summary.today_events }}</span> 次</strong>
    </div>
    <div class="panel pad metric">
      <label>未处理异常</label>
      <strong><span>{{ summary.open_alerts }}</span> 条</strong>
    </div>
  </section>

  <section class="grid cols-3" style="margin-top: 16px;">
    <div class="panel pad" style="grid-column: span 2;">
      <div class="section-title">
        <h2>实时槽位</h2>
        <RouterLink to="/cabinet" class="badge">查看全部</RouterLink>
      </div>
      <div class="slot-grid">
        <div v-for="tool in mergedTools.slice(0, 4)" :key="tool.id" class="slot-card" :class="tool.status">
          <div class="slot-head">
            <span>S{{ String(tool.slot_no).padStart(2, '0') }}</span>
            <span class="badge" :class="tool.status">{{ statusText(tool.status) }}</span>
          </div>
          <div class="dash-slot-img">
            <img v-if="tool.image_url" :src="tool.image_url" class="slot-img" />
            <div v-else class="slot-img-ph">{{ (tool.tool_name || '?').charAt(0) }}</div>
          </div>
          <span class="slot-name">{{ tool.tool_name || '未配置' }}</span>
          <span class="slot-code">{{ tool.tool_code || '-' }}</span>
        </div>
      </div>
    </div>

    <div class="panel pad">
      <div class="section-title">
        <h2>大模型风险摘要</h2>
      </div>
      <p class="assistant-output">
        {{ riskText }}
      </p>
      <RouterLink to="/assistant" class="btn">进入 AI 助手</RouterLink>
    </div>
  </section>

  <section class="panel pad" style="margin-top: 16px;">
    <div class="section-title">
      <h2>最近借还记录</h2>
      <RouterLink to="/records" class="badge">更多</RouterLink>
    </div>
    <table class="table">
      <thead>
        <tr>
          <th>事件编号</th>
          <th>操作者</th>
          <th>结果</th>
          <th>同步时间</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="event in events.slice(0, 6)" :key="event.id">
          <td>{{ event.event_id }}</td>
          <td>{{ event.operator_name || '-' }}</td>
          <td><span class="badge" :class="event.result_type">{{ event.result_type || '-' }}</span></td>
          <td>{{ formatTime(event.synced_at) }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { RouterLink } from 'vue-router';
import { fetchDashboard, fetchEvents, fetchSlots, fetchTools, type DashboardSummary, type OperationRecord, type SlotState, type Tool } from '../api/client';
import { useRealtime } from '../stores/useRealtime';

const summary = ref<DashboardSummary>({
  devices_total: 0, online_devices: 0, tools_total: 0, tools_available: 0, open_alerts: 0, today_events: 0
});
const tools = ref<Tool[]>([]);
const slotStates = ref<SlotState[]>([]);
const events = ref<OperationRecord[]>([]);
const riskText = ref('系统会根据异常记录、工具错放、超时未还和识别不确定事件生成风险摘要。当前未发现高风险事件。');

const mergedTools = computed(() => {
  const stateMap = new Map(slotStates.value.map(s => [s.tool_code, s]));
  return tools.value.map((t, i) => {
    const live = stateMap.get(t.tool_code);
    return { ...t, slot_no: i + 1, status: live?.status || t.status, confidence: live?.confidence ?? null };
  });
});

function statusText(status: string) {
  const map: Record<string, string> = { present: '在位', available: '在位', borrowed: '借出', misplaced: '错放', uncertain: '不确定', empty: '空槽', missing: '丢失', wrong: '错放', damaged: '损坏' };
  return map[status] || status;
}

function formatTime(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-';
}

async function load() {
  const [s, t, sl, e] = await Promise.all([fetchDashboard(), fetchTools(), fetchSlots(), fetchEvents(10)]);
  summary.value = s; tools.value = t; slotStates.value = sl; events.value = e;
}

useRealtime(load);
onMounted(load);
</script>

<style scoped>
.dash-slot-img {
  height: 70px;
  margin-bottom: 8px;
  border-radius: 6px;
  overflow: hidden;
  background: rgba(0, 0, 0, 0.3);
  display: flex; align-items: center; justify-content: center;
}
.slot-img { max-height: 100%; max-width: 100%; object-fit: contain; }
.slot-img-ph {
  width: 32px; height: 32px; border-radius: 50%;
  background: rgba(96, 165, 250, 0.14);
  display: flex; align-items: center; justify-content: center;
  font-size: 14px; font-weight: bold; color: #93c5fd;
}
</style>
