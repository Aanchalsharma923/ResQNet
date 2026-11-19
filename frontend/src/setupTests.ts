import '@testing-library/jest-dom';

// Global mock for WebSocket in JSDOM test environment to prevent hanging socket handles
class MockWebSocket {
  static CONNECTING = 0;
  static OPEN = 1;
  static CLOSING = 2;
  static CLOSED = 3;

  onopen: (() => void) | null = null;
  onmessage: ((event: any) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: ((error: any) => void) | null = null;
  readyState = 0;

  constructor(public url: string) {
    // Keep initial state CONNECTING for tests that inspect initial disconnect/connecting status
  }

  send() {}
  close() {
    this.readyState = 3;
    if (this.onclose) this.onclose();
  }
}

(globalThis as any).WebSocket = (globalThis as any).WebSocket || MockWebSocket;
