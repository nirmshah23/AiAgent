import { describe, it, expect, vi } from 'vitest';
import { AudioSession } from './audio-session';

describe('Audio session lifecycle', () => {
  function coldSession() {
    class TestSocket {
      static readonly OPEN = 1;
      static latest: TestSocket;
      readyState = 1;
      onmessage?: (event: MessageEvent) => void;
      send = vi.fn();
      close = vi.fn();
      constructor() { TestSocket.latest = this; }
    }
    vi.stubGlobal('WebSocket', TestSocket);
    vi.stubGlobal('AudioContext', class {
      state = 'running';
      resume = () => Promise.resolve();
      close = () => Promise.resolve();
    });
    const session = new AudioSession();
    session.connect();
    return { session, socket: TestSocket.latest };
  }

  it('allows cold model loading beyond ten seconds but ends an unresponsive connection', () => {
    vi.useFakeTimers();
    const { session, socket } = coldSession();
    try {
      vi.advanceTimersByTime(15000);
      expect(session.connecting()).toBe(true);
      expect(session.error()).toBe('');
      vi.advanceTimersByTime(45000);
      expect(session.connecting()).toBe(false);
      expect(session.error()).toContain('Connection timed out');
      expect(socket.close).toHaveBeenCalledOnce();
    } finally {
      session.disconnect();
      vi.useRealTimers();
      vi.unstubAllGlobals();
    }
  });

  it('cancels the connection deadline after a delayed ready event', () => {
    vi.useFakeTimers();
    const { session, socket } = coldSession();
    try {
      vi.advanceTimersByTime(15000);
      socket.onmessage?.(new MessageEvent('message', { data: JSON.stringify({ type: 'ready' }) }));
      vi.advanceTimersByTime(60000);
      expect(session.connected()).toBe(true);
      expect(session.error()).toBe('');
      expect(socket.send).toHaveBeenCalledWith('welcome');
      expect(socket.close).not.toHaveBeenCalled();
    } finally {
      session.disconnect();
      vi.useRealTimers();
      vi.unstubAllGlobals();
    }
  });

  it('does not request microphone access before a session connects', async () => {
    const getUserMedia = vi.fn();
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } });
    const session = new AudioSession();
    await session.press();
    expect(getUserMedia).not.toHaveBeenCalled();
    expect(session.recording()).toBe(false);
  });

  it('stops a delayed microphone grant after release without recording', async () => {
    const stop = vi.fn();
    let grant: (stream: MediaStream) => void = () => {};
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: {
      getUserMedia: () => new Promise<MediaStream>(resolve => { grant = resolve; }),
    } });
    const session = new AudioSession();
    session.connected.set(true);
    const pending = session.press();
    session.release();
    grant({ getTracks: () => [{ stop }] } as unknown as MediaStream);
    await pending;
    expect(stop).toHaveBeenCalledOnce();
    expect(session.recording()).toBe(false);
  });
});
