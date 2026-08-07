import { onMounted, onUnmounted, ref } from 'vue';
import { getToken } from './auth';

export function useRealtime(onMessage: () => void) {
  let source: EventSource | null = null;
  let retryCount = 0;
  let retryTimer: number | null = null;

  function connect() {
    const token = getToken();
    if (!token) return;

    // SSE 不支持自定义 header，用 URL 参数传 token
    const url = `/api/stream/events?token=${encodeURIComponent(token)}`;
    source = new EventSource(url);

    source.onopen = () => {
      retryCount = 0;
    };

    source.onmessage = () => {
      onMessage();
    };

    source.onerror = () => {
      source?.close();
      source = null;
      // 自动重连，最多 5 次，间隔递增
      retryCount++;
      if (retryCount <= 5) {
        const delay = Math.min(retryCount * 3000, 15000);
        retryTimer = window.setTimeout(() => connect(), delay);
      }
    };
  }

  onMounted(() => {
    connect();
  });

  onUnmounted(() => {
    source?.close();
    source = null;
    if (retryTimer) window.clearTimeout(retryTimer);
  });
}
