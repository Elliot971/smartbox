import { onMounted, onUnmounted } from 'vue';

export function useRealtime(onMessage: () => void) {
  let source: EventSource | null = null;

  onMounted(() => {
    source = new EventSource('/api/stream/events');
    source.onmessage = () => onMessage();
  });

  onUnmounted(() => {
    source?.close();
    source = null;
  });
}

