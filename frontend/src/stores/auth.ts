import { ref, computed } from 'vue';
import { api } from '../api/client';

const TOKEN_KEY = 'esp_web_token';

const token = ref<string | null>(localStorage.getItem(TOKEN_KEY));

export const isAuthenticated = computed(() => !!token.value);

export function getToken(): string | null {
  return token.value;
}

export async function login(username: string, password: string): Promise<void> {
  const res = await api.post<{ access_token: string; token_type: string }>('/auth/login', {
    username,
    password,
  });
  token.value = res.data.access_token;
  localStorage.setItem(TOKEN_KEY, res.data.access_token);
}

export function logout(): void {
  token.value = null;
  localStorage.removeItem(TOKEN_KEY);
}

export function initAuth(): void {
  const saved = localStorage.getItem(TOKEN_KEY);
  if (saved) {
    token.value = saved;
  }
}
