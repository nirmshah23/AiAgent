// Runs on the audio rendering thread. The main thread gates every outbound frame.
class PcmCapture extends AudioWorkletProcessor {
  process(inputs) {
    const samples = inputs[0]?.[0];
    if (samples) {
      const pcm = new ArrayBuffer(samples.length * 2);
      const view = new DataView(pcm);
      for (let i = 0; i < samples.length; i++) {
        const value = Math.max(-1, Math.min(1, samples[i]));
        view.setInt16(i * 2, value < 0 ? value * 32768 : value * 32767, true);
      }
      this.port.postMessage(pcm, [pcm]);
    }
    return true;
  }
}
registerProcessor('pcm-capture', PcmCapture);
