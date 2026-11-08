import { describe, it, expect, vi } from 'vitest';
import { AudioSession } from './audio-session';

describe('Audio session lifecycle', () => {
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
