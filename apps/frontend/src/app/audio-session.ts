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
  private playback?: AudioContext;
  private playbackEnd = 0;
  private playing = new Set<AudioBufferSourceNode>();
  private finishing = false;
  private playbackSuppressed = false;

  connect(): void {
    if (this.connecting() || this.connected()) return;
    this.finishing = false;
    this.playbackSuppressed = false;
    try {
      this.playback = new AudioContext({ sampleRate: 16000 });
      void this.playback.resume().catch(() => this.fail('Audio playback unavailable. Start a new session to retry.'));
    } catch {
      this.error.set('Audio playback unavailable in this browser.');
      return;
    }
    this.error.set('');
    this.bytes.set(0);
    this.connecting.set(true);
    const socket = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/v1/audio`);
    this.socket = socket;
    socket.binaryType = 'arraybuffer';
    this.connectionTimeout = setTimeout(() => {
      if (!this.connected()) this.fail('Connection timed out. Check the voice service and try again.');
    }, 60000); // The first native CPU session may still be loading recognition models.
    socket.onmessage = event => {
      if (this.socket !== socket) return;
      if (event.data instanceof ArrayBuffer) {
        if (!this.playbackSuppressed) this.playAudio(event.data);
        return;
      }
      const message: { type: string; audio_bytes?: number } = JSON.parse(event.data);
      if (message.type === 'ready') {
        clearTimeout(this.connectionTimeout);
        this.connecting.set(false);
        this.connected.set(true);
        socket.send('welcome');
        this.heartbeat = setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) socket.send('ping');
        }, 20000);
      }
      if (message.type === 'paused') this.bytes.set(message.audio_bytes ?? 0);
      if (message.type === 'listening') this.playbackSuppressed = false;
      if (message.type === 'speech_started') this.stopPlayback();
      if (message.type === 'dialog_ended') {
        this.finishing = true;
        if (!this.playing.size) this.disconnect();
      }
      if (message.type === 'speech_error') {
        this.fail('Speech output failed. Start a new session to try again.');
      }
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
    this.playbackSuppressed = true;
    this.stopPlayback();
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
    if (!wasRecording) this.playbackSuppressed = false;
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
    this.stopPlayback();
    const playback = this.playback;
    this.playback = undefined;
    if (playback && playback.state !== 'closed') void playback.close().catch(() => {});
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

  private playAudio(data: ArrayBuffer): void {
    const context = this.playback;
    if (!context || !data.byteLength || data.byteLength % 2) return;
    if (context.state !== 'running') {
      this.fail('Audio playback was suspended. Start a new session to retry.');
      return;
    }
    const start = Math.max(context.currentTime, this.playbackEnd);
    const duration = data.byteLength / 32000;
    if (start + duration - context.currentTime > 15) {
      this.fail('Speech playback cannot keep up. Start a new session to retry.');
      return;
    }
    const buffer = context.createBuffer(1, data.byteLength / 2, 16000);
    const samples = buffer.getChannelData(0);
    const pcm = new DataView(data);
    for (let i = 0; i < samples.length; ++i) samples[i] = pcm.getInt16(i * 2, true) / 32768;
    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);
    this.playing.add(source);
    source.onended = () => {
      source.disconnect();
      this.playing.delete(source);
      if (this.finishing && !this.playing.size) this.disconnect();
    };
    source.start(start);
    this.playbackEnd = start + duration;
  }

  private stopPlayback(): void {
    for (const source of this.playing) { source.stop(); source.disconnect(); }
    this.playing.clear();
    this.playbackEnd = 0;
  }
}
