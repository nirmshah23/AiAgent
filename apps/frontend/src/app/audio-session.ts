import { Injectable, signal } from '@angular/core';

@Injectable({ providedIn: 'root' })
export class AudioSession {
  readonly connected = signal(false);
  readonly connecting = signal(false);
  readonly recording = signal(false);
  readonly error = signal('');
  readonly bytes = signal(0);
  private socket?: WebSocket;
  private context?: AudioContext;
  private stream?: MediaStream;
  private source?: MediaStreamAudioSourceNode;
  private processor?: AudioWorkletNode;
  private heartbeat?: ReturnType<typeof setInterval>;
  private connectionTimeout?: ReturnType<typeof setTimeout>;
  private held = false;
  private generation = 0;
  private turn = 0;

  connect(): void {
    if (this.connecting() || this.connected()) return;
    this.error.set('');
    this.bytes.set(0);
    this.connecting.set(true);
    const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/v1/audio`);
    this.socket = socket;
    this.connectionTimeout = setTimeout(() => {
      if (!this.connected()) this.fail('Connection timed out. Check the voice service and try again.');
    }, 10000);
    socket.onmessage = event => {
      if (this.socket !== socket) return;
      const message: { type: string; audio_bytes?: number } = JSON.parse(event.data);
      if (message.type === 'ready') {
        clearTimeout(this.connectionTimeout);
        this.connecting.set(false);
        this.connected.set(true);
        this.heartbeat = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) socket.send('ping');
        }, 20000);
      }
      if (message.type === 'paused') this.bytes.set(message.audio_bytes ?? 0);
    };
    socket.onerror = () => {
      if (this.socket === socket) this.fail('Unable to connect. Check that the voice service is running, then try again.');
    };
    socket.onclose = () => {
      if (this.socket === socket) this.fail('Session disconnected. Start a new session to continue.');
    };
  }

  async press(): Promise<void> {
    if (!this.connected() || this.held) return;
    this.held = true;
    const generation = this.generation;
    const turn = ++this.turn;
    this.error.set('');
    let stream: MediaStream | undefined;
    let context: AudioContext | undefined;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: {
        channelCount: 1, echoCancellation: true, noiseSuppression: true,
        autoGainControl: true,
      }});
      if (!this.held || generation !== this.generation || turn !== this.turn) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      this.stream = stream;
      context = new AudioContext({ sampleRate: 16000 });
      if (context.sampleRate !== 16000) throw new Error('Unsupported audio sample rate');
      this.context = context;
      await context.audioWorklet.addModule('pcm-worklet.js');
      await context.resume();
      if (!this.held || generation !== this.generation || turn !== this.turn) {
        stream.getTracks().forEach(track => track.stop());
        if (context.state !== 'closed') await context.close();
        return;
      }
      this.source = context.createMediaStreamSource(stream);
      const processor = new AudioWorkletNode(context, 'pcm-capture');
      this.processor = processor;
      processor.port.onmessage = (event: MessageEvent<ArrayBuffer>) => {
        if (!this.held || !this.recording() || this.processor !== processor) return;
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN || this.socket.bufferedAmount > 65536) {
          this.fail('The connection cannot keep up with audio. Start a new session to retry.');
          return;
        }
        this.socket.send(event.data);
      };
      this.socket?.send('start');
      this.recording.set(true);
      this.source.connect(processor);
      // Worklet emits silence; microphone audio is never played locally.
      processor.connect(context.destination);
      stream.getAudioTracks()[0]?.addEventListener('ended', () => {
        if (this.stream === stream) this.release();
      });
    } catch {
      stream?.getTracks().forEach(track => track.stop());
      if (context && context.state !== 'closed') void context.close().catch(() => {});
      if (generation === this.generation && turn === this.turn) {
        this.release();
        this.error.set('Microphone unavailable. Allow microphone access in your browser and hold Space again.');
      }
    }
  }

  release(): void {
    this.held = false;
    ++this.turn;
    const wasRecording = this.recording();
    this.recording.set(false);
    this.processor?.disconnect();
    if (this.processor) this.processor.port.onmessage = null;
    this.processor = undefined;
    this.source?.disconnect();
    this.source = undefined;
    this.stream?.getTracks().forEach(track => track.stop());
    this.stream = undefined;
    const context = this.context;
    this.context = undefined;
    if (context && context.state !== 'closed') void context.close().catch(() => {});
    if (wasRecording && this.socket?.readyState === WebSocket.OPEN) this.socket.send('stop');
  }

  disconnect(): void {
    ++this.generation;
    this.release();
    clearInterval(this.heartbeat);
    clearTimeout(this.connectionTimeout);
    const socket = this.socket;
    this.socket = undefined;
    if (socket?.readyState === WebSocket.OPEN) socket.send('end');
    socket?.close();
    this.connecting.set(false);
    this.connected.set(false);
  }

  private fail(message: string): void {
    this.disconnect();
    this.error.set(message);
  }
}
