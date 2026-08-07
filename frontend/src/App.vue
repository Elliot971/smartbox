<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">FOD</div>
        <div>
          <strong>智能工具箱</strong>
          <span>AIoT 管理平台</span>
        </div>
      </div>
      <nav class="nav">
        <RouterLink v-for="item in nav" :key="item.path" :to="item.path">
          <span class="nav-icon">{{ item.icon }}</span>
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>
      <div class="side-status">
        <span class="pulse-dot"></span>
        <div>
          <strong>ESP32-P4</strong>
          <small>HTTP + SSE 实时同步</small>
        </div>
      </div>
    </aside>

    <main class="main">
      <header class="topbar">
        <div>
          <h1>{{ title }}</h1>
          <p>端侧识别、本地闭环、云端增强分析</p>
        </div>
        <div class="top-actions">
          <span class="online-pill">云端服务在线</span>
          <span>{{ now }}</span>
          <button v-if="isAuthenticated" class="logout-btn" @click="handleLogout">退出登录</button>
        </div>
      </header>
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router';
import { isAuthenticated, logout } from './stores/auth';

const route = useRoute();
const router = useRouter();
const title = computed(() => String(route.meta.title || '总览大屏'));
const now = ref('');
let timer = 0;

function handleLogout() {
  logout();
  router.push('/login');
}

const nav = [
  { path: '/dashboard', label: '总览大屏', icon: 'D' },
  { path: '/cabinet', label: '工具箱状态', icon: 'S' },
  { path: '/records', label: '借还记录', icon: 'R' },
  { path: '/alerts', label: '异常告警', icon: 'A' },
  { path: '/inspections', label: '损坏检测', icon: 'V' },
  { path: '/assistant', label: '大模型助手', icon: 'AI' }
];

function updateTime() {
  now.value = new Date().toLocaleString('zh-CN', { hour12: false });
}

onMounted(() => {
  updateTime();
  timer = window.setInterval(updateTime, 1000);
});

onUnmounted(() => window.clearInterval(timer));
</script>

<style scoped>
.logout-btn {
  background: transparent;
  border: 1px solid rgba(148, 163, 184, 0.25);
  color: #cbd5e1;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  cursor: pointer;
}
.logout-btn:hover {
  background: rgba(148, 163, 184, 0.15);
}
</style>