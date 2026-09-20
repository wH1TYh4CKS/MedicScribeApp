// Resamples the mic's float32 stream (device rate, e.g. 48000) down to 16 kHz
// mono 16-bit little-endian PCM and posts each chunk to the main thread.
// `sampleRate` is a global in AudioWorkletGlobalScope = the AudioContext rate.
class PCMDownsampler extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetRate = 16000;
    this.ratio = sampleRate / this.targetRate; // input samples per output sample
    this._buf = [];   // pending input float samples (mono)
    this._pos = 0;    // fractional read position into _buf
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || input.length === 0 || !input[0]) return true;
    const ch = input[0]; // first channel; mic is mono
    for (let i = 0; i < ch.length; i++) this._buf.push(ch[i]);

    const out = [];
    while (this._pos + 1 < this._buf.length) {
      const i0 = Math.floor(this._pos);
      const frac = this._pos - i0;
      let s = this._buf[i0] * (1 - frac) + this._buf[i0 + 1] * frac;
      if (s > 1) s = 1; else if (s < -1) s = -1;
      out.push(s < 0 ? s * 0x8000 : s * 0x7fff);
      this._pos += this.ratio;
    }

    const consumed = Math.floor(this._pos);
    if (consumed > 0) {
      this._buf.splice(0, consumed);
      this._pos -= consumed;
    }

    if (out.length > 0) {
      const pcm = Int16Array.from(out);
      this.port.postMessage(pcm.buffer, [pcm.buffer]); // transfer ownership
    }
    return true;
  }
}

registerProcessor('pcm-downsampler', PCMDownsampler);
