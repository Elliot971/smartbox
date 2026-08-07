<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <div class="brand-mark">FOD</div>
        <div>
          <strong>智能工具箱</strong>
          <span>管理平台</span>
        </div>
      </div>
      <h2>管理员登录</h2>
      <form @submit.prevent="handleLogin">
        <div class="field">
          <label>账号</label>
          <input v-model="username" type="text" placeholder="请输入账号" required />
        </div>
        <div class="field">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="请输入密码" required />
        </div>
        <p v-if="error" class="error">{{ error }}</p>
        <button type="submit" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { login } from '../stores/auth';

const router = useRouter();
const username = ref('');
const password = ref('');
const loading = ref(false);
const error = ref('');

async function handleLogin() {
  loading.value = true;
  error.value = '';
  try {
    await login(username.value, password.value);
    router.push('/dashboard');
  } catch (e: any) {
    error.value = e.response?.data?.detail || '登录失败，请检查账号密码';
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #0f172a 0%, #1e293b 50%, #0f172a 100%);
}
.login-card {
  width: 360px;
  padding: 36px 32px;
  background: rgba(30, 41, 59, 0.95);
  border: 1px solid rgba(96, 165, 250, 0.15);
  border-radius: 16px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), 0 0 0 1px rgba(96, 165, 250, 0.05);
  backdrop-filter: blur(12px);
}
.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
}
.brand-mark {
  width: 44px;
  height: 44px;
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  color: #fff;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 14px;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.3);
}
.brand strong {
  display: block;
  font-size: 18px;
  color: #f1f5f9;
}
.brand span {
  color: #94a3b8;
  font-size: 13px;
}
h2 {
  margin: 0 0 24px;
  font-size: 20px;
  color: #e2e8f0;
}
.field {
  margin-bottom: 18px;
}
label {
  display: block;
  margin-bottom: 6px;
  font-size: 14px;
  color: #cbd5e1;
}
input {
  width: 100%;
  padding: 11px 14px;
  background: rgba(15, 23, 42, 0.6);
  border: 1px solid rgba(96, 165, 250, 0.2);
  border-radius: 8px;
  font-size: 14px;
  color: #f1f5f9;
  box-sizing: border-box;
  transition: border-color 0.2s;
}
input::placeholder {
  color: #94a3b8;
}
input:focus {
  outline: none;
  border-color: #3b82f6;
  background: rgba(15, 23, 42, 0.8);
}
button {
  width: 100%;
  padding: 12px;
  background: linear-gradient(135deg, #2563eb, #0ea5e9);
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s;
}
button:hover:not(:disabled) {
  opacity: 0.9;
}
button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.error {
  color: #f87171;
  font-size: 13px;
  margin-bottom: 12px;
  padding: 8px 12px;
  background: rgba(239, 68, 68, 0.1);
  border-radius: 6px;
}
</style>
