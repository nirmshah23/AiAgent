"""Download the pinned FP32 Parakeet ONNX export before starting voice sessions."""

from pathlib import Path

from huggingface_hub import snapshot_download

REPOSITORY = "istupakov/parakeet-tdt-0.6b-v3-onnx"
REVISION = "8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce"


def main():
    """Keep prepared artifacts in the repository's ignored model directory."""
    destination = Path(__file__).resolve().parents[1] / "models" / "parakeet-tdt-0.6b-v3"
    snapshot_download(
        REPOSITORY,
        revision=REVISION,
        local_dir=destination,
        allow_patterns=[
            "README.md",
            "config.json",
            "vocab.txt",
            "encoder-model.onnx",
            "encoder-model.onnx.data",
            "decoder_joint-model.onnx",
        ],
    )
    print(f"Prepared FP32 ONNX model: {destination}")


if __name__ == "__main__":
    main()
