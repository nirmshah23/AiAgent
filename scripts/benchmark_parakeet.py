"""Measure one Parakeet backend at a time on prepared 16 kHz mono PCM16 audio."""

import argparse
import hashlib
import json
import logging
import statistics
import sys
import time
import wave
from collections import Counter
from importlib.metadata import version
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/backend"))

from voice_api.parakeet_stt import _create_model  # noqa: E402


def main():
    """Report timings and graph execution providers without printing caller text."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("cpu", "openvino"), required=True)
    parser.add_argument("--device", choices=("CPU", "GPU", "NPU"), default="GPU")
    parser.add_argument("--precision", choices=("FP32", "FP16"), default="FP32")
    parser.add_argument("--threads", type=int, choices=range(1, 33), default=4)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--model", type=Path, default=ROOT / "models/parakeet-tdt-0.6b-v3")
    parser.add_argument(
        "--audio", type=Path, default=ROOT / "scripts/provider-watch/assets/speech-16k.wav"
    )
    parser.add_argument("--profile", action="store_true", help="Write private ORT node profiles")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be positive")
    with wave.open(str(args.audio)) as audio:
        if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (16000, 1, 2):
            parser.error("Audio must be uncompressed 16 kHz mono PCM16 WAV")
        waveform = np.frombuffer(audio.readframes(audio.getnframes()), dtype="<i2")
    if not len(waveform):
        parser.error("Audio must contain samples")
    waveform = waveform.astype(np.float32) / 32768.0
    logging.basicConfig(level=logging.INFO)
    profile_prefix = None
    if args.profile:
        directory = ROOT / ".local-run/parakeet-profiles"
        directory.mkdir(parents=True, exist_ok=True)
        profile_prefix = directory / args.backend
    start = time.perf_counter()
    # Fail rather than report CPU fallback as a successful accelerated benchmark.
    model = _create_model(
        args.model, args.threads, args.backend, args.device, args.precision, profile_prefix
    )
    load_seconds = time.perf_counter() - start
    timings, fingerprints = [], []
    for _ in range(args.runs + 1):
        start = time.perf_counter()
        text = model.recognize(waveform, sample_rate=16000)
        timings.append(time.perf_counter() - start)
        fingerprints.append(hashlib.sha256(text.encode()).hexdigest())
    sessions = (model.asr._encoder, model.asr._decoder_joint)
    node_counts = Counter()
    profiles = []
    if args.profile:
        for session in sessions:
            path = Path(session.end_profiling())
            profiles.append(str(path))
            for event in json.loads(path.read_text()):
                provider = event.get("args", {}).get("provider")
                if provider:
                    node_counts[provider] += 1
    print(
        json.dumps(
            {
                "backend": args.backend,
                "device": args.device if args.backend == "openvino" else "CPU",
                "precision": args.precision if args.backend == "openvino" else "FP32",
                "onnxruntime": version("onnxruntime"),
                "openvino_plugin": version("onnxruntime-ep-openvino")
                if args.backend == "openvino"
                else None,
                "cpu_threads": args.threads,
                "audio_seconds": len(waveform) / 16000,
                "load_seconds": load_seconds,
                "first_inference_seconds": timings[0],
                "warm_seconds": timings[1:],
                "warm_median_seconds": statistics.median(timings[1:]),
                "warm_real_time_factor": statistics.median(timings[1:]) / (len(waveform) / 16000),
                "transcript_sha256": fingerprints,
                "session_providers": [session.get_providers() for session in sessions],
                "profile_node_executions": dict(node_counts),
                "profiles": profiles,
                "fallback": False,
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
