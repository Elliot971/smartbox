import axios from 'axios';
import { getToken, logout } from '../stores/auth';

export const api = axios.create({
  baseURL: '/api',
  timeout: 30000
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token && config.headers) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      logout();
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export interface DashboardSummary {
  devices_total: number;
  online_devices: number;
  tools_total: number;
  tools_available: number;
  open_alerts: number;
  today_events: number;
}

export interface SlotState {
  device_code: string;
  slot_no: number;
  tool_code: string;
  tool_name: string;
  tool_class: string;
  status: string;
  confidence: number | null;
  updated_at: string | null;
}

export interface OperationRecord {
  id: number;
  event_id: string;
  device_code: string;
  operator_name: string;
  result_type: string;
  opened_at: string | null;
  closed_at: string | null;
  synced_at: string;
}

export interface AlertItem {
  id: number;
  device_code: string;
  alert_type: string;
  severity: string;
  title: string;
  description: string;
  status: string;
  created_at: string;
}

export interface DamageInspection {
  id: number;
  device_code: string;
  tool_code: string;
  tool_name: string;
  tool_class: string;
  image_url: string;
  heatmap_url?: string;
  status: string;
  severity: string;
  confidence: number | null;
  summary: string;
  raw_result: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface DamageInspectionCreate {
  device_code: string;
  tool_code: string;
  tool_name: string;
  tool_class: string;
  image_url: string;
}

export async function fetchDashboard() {
  return (await api.get<DashboardSummary>('/query/dashboard')).data;
}

export async function fetchSlots() {
  return (await api.get<SlotState[]>('/query/slots')).data;
}

export async function fetchEvents(limit = 30) {
  return (await api.get<OperationRecord[]>('/query/events', { params: { limit } })).data;
}

export async function fetchAlerts(limit = 30) {
  return (await api.get<AlertItem[]>('/query/alerts', { params: { limit } })).data;
}

export async function deleteAlert(id: number) {
  await api.delete(`/query/alerts/${id}`);
}

export async function clearAllAlerts() {
  return (await api.delete<{ ok: boolean; deleted: number }>('/query/alerts')).data;
}

export async function fetchDamageInspections(limit = 50) {
  return (await api.get<DamageInspection[]>('/inspection/tasks', { params: { limit } })).data;
}

export async function createDamageInspection(payload: DamageInspectionCreate) {
  return (await api.post<DamageInspection>('/inspection/tasks', payload)).data;
}

export async function analyzeDamageInspection(id: number) {
  return (await api.post<{ ok: boolean; task: DamageInspection }>(`/inspection/tasks/${id}/analyze`, null, { timeout: 180000 })).data.task;
}

export async function deleteDamageInspection(id: number) {
  await api.delete(`/inspection/tasks/${id}`);
}

export async function deleteToolInspections(toolCode: string) {
  return (await api.delete<{ ok: boolean; deleted: number }>(`/inspection/tool-summary/${toolCode}`)).data;
}

export interface ToolDamageSummary {
  tool_id: number;
  tool_code: string;
  tool_name: string;
  image_url: string;
  heatmap_url?: string;
  latest_status: string;
  latest_severity: string;
  latest_summary: string;
  task_count: number;
}

export async function fetchToolDamageSummary() {
  return (await api.get<ToolDamageSummary[]>('/inspection/tool-summary')).data;
}

export async function uploadAndAnalyze(file: File, toolCode = '', toolName = '上传检测', toolClass = '') {
  const form = new FormData();
  form.append('file', file);
  const res = await api.post('/inspection/upload-and-analyze', form, {
    params: { tool_code: toolCode, tool_name: toolName, tool_class: toolClass },
    timeout: 180000,
  });
  return res.data;
}

export async function analyzeTarget(target_type: 'alert' | 'event', target_id: number, question = '') {
  return (await api.post('/ai/analyze', { target_type, target_id, question }, { timeout: 90000 })).data;
}

export async function chatWithAssistant(message: string, context: Record<string, unknown> = {}, model = '') {
  return (await api.post('/ai/chat', { message, context, model }, { timeout: 60000 })).data;
}

export async function* chatWithAssistantStream(
  message: string,
  context: Record<string, unknown> = {},
  model = ''
): AsyncGenerator<string> {
  const token = getToken();
  const res = await fetch('/api/ai/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, context, model }),
  });
  if (!res.ok) {
    throw new Error(`HTTP ${res.status}`);
  }
  const reader = res.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        try {
          const chunk = JSON.parse(line.slice(6));
          if (chunk.content) {
            yield chunk.content;
          }
        } catch { /* skip malformed lines */ }
      }
    }
  }
}

// ===== Tool Management =====

export interface Tool {
  id?: number;
  tool_code: string;
  tool_name: string;
  tool_class: string;
  status: string;
  image_url?: string;
  spec?: string;
}

export async function fetchTools() {
  return (await api.get<Tool[]>('/tools')).data;
}

export async function createTool(payload: Tool) {
  return (await api.post<Tool>('/tools', payload)).data;
}

export async function uploadToolImageDirect(id: number, file: File) {
  const form = new FormData();
  form.append('file', file);
  return (await api.post<Tool>(`/tools/${id}/image`, form, {
    timeout: 30000,
  })).data;
}

export async function updateTool(id: number, payload: Partial<Tool>, imageFile?: File) {
  const updated = (await api.put<Tool>(`/tools/${id}`, payload)).data;
  if (imageFile) {
    return await uploadToolImageDirect(id, imageFile);
  }
  return updated;
}

export async function deleteTool(id: number) {
  await api.delete(`/tools/${id}`);
}

export async function uploadToolImage(file: File) {
  const form = new FormData();
  form.append('file', file);
  const res = await api.post<{ url: string }>('/upload/image', form, {
    timeout: 30000,
  });
  return res.data.url;
}
