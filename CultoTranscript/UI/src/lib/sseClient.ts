import type { SSEEventDTO, EventType } from '../types';
import { config } from './config';

export class SSEClient {
  private eventSource: EventSource | null = null;
  private reconnectTimeout: number | null = null;
  private listeners: Map<EventType, Set<(data: any) => void>> = new Map();

  connect() {
    if (this.eventSource) {
      return;
    }

    this.eventSource = new EventSource(config.sseUrl);

    this.eventSource.onopen = () => {
      console.log('SSE connection established');
    };

    this.eventSource.onmessage = (event) => {
      try {
        const data: SSEEventDTO = JSON.parse(event.data);
        this.notifyListeners(data.type, data);
      } catch (error) {
        console.error('Failed to parse SSE event:', error);
      }
    };

    this.eventSource.onerror = () => {
      console.error('SSE connection error');
      this.disconnect();
      
      // Attempt to reconnect after 5 seconds
      this.reconnectTimeout = window.setTimeout(() => {
        console.log('Attempting to reconnect SSE...');
        this.connect();
      }, 5000);
    };
  }

  disconnect() {
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
      this.reconnectTimeout = null;
    }
  }

  on(eventType: EventType, callback: (data: any) => void) {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType)!.add(callback);
  }

  off(eventType: EventType, callback: (data: any) => void) {
    const listeners = this.listeners.get(eventType);
    if (listeners) {
      listeners.delete(callback);
    }
  }

  private notifyListeners(eventType: EventType, data: any) {
    const listeners = this.listeners.get(eventType);
    if (listeners) {
      listeners.forEach((callback) => callback(data));
    }
  }
}

export const sseClient = new SSEClient();
