"""Prepare pinned English dialog artifacts for offline native and container startup."""

import argparse
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LAYA_REVISION = "7b928d828b7b0e022f929d9bd2e44165aa270148"
GLINER_REVISION = "4e091416cf7c3481db542c2a3d26156916f3a47f"
BACKBONE_REVISION = "a36c739020e01763fe789b4b85e2df55d6180012"


def _download_weights(repo, revision, name, destination, digest):
    import requests

    if destination.is_file():
        with destination.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() == digest:
                return
    partial = destination.with_name(destination.name + ".download")
    if partial.is_file():
        with partial.open("rb") as source:
            if hashlib.file_digest(source, "sha256").hexdigest() == digest:
                partial.replace(destination)
                return
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"Range": f"bytes={offset}-"} if offset else {}
    url = f"https://huggingface.co/{repo}/resolve/{revision}/{name}"
    with requests.get(url, headers=headers, stream=True, timeout=(15, 60)) as response:
        response.raise_for_status()
        append = response.status_code == 206 and offset > 0
        if append and not response.headers.get("Content-Range", "").startswith(f"bytes {offset}-"):
            raise ValueError("Model server returned an invalid resume offset")
        print("Downloading", repo, name, flush=True)
        with partial.open("ab" if append else "wb") as target:
            for chunk in response.iter_content(1024 * 1024):
                target.write(chunk)
    with partial.open("rb") as source:
        if hashlib.file_digest(source, "sha256").hexdigest() != digest:
            raise ValueError("Model checksum mismatch; remove its .download file and retry")
    partial.replace(destination)
    print("Verified", repo, name, flush=True)


def main():
    """Download once as an operator action, never while handling a voice session."""
    from huggingface_hub import snapshot_download
    from transformers import AutoConfig, AutoTokenizer

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, required=True)
    args = parser.parse_args()
    root = args.models_dir.resolve()
    snapshot_download(
        "convaiinnovations/laya",
        revision=LAYA_REVISION,
        local_dir=root / "laya",
        allow_patterns=[
            "config.json",
            "rl_agent_config.json",
            "tokenizer/*",
            "encoder/*",
        ],
    )
    gliner = root / "gliner-small-v2.1"
    snapshot_download(
        "urchade/gliner_small-v2.1",
        revision=GLINER_REVISION,
        local_dir=gliner,
        ignore_patterns=["*.bin", "*.safetensors"],
    )
    backbone = root / "deberta-v3-small"
    snapshot_download(
        "microsoft/deberta-v3-small",
        revision=BACKBONE_REVISION,
        local_dir=backbone,
        allow_patterns=["config.json", "tokenizer*", "spm.model", "special_tokens_map.json"],
    )
    # Make GLiNER self-contained: its upstream checkpoint omits backbone config/tokenizer.
    # Embed config instead of recording a host-specific absolute path in mounted artifacts.
    config_path = gliner / "gliner_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["encoder_config"] = AutoConfig.from_pretrained(backbone, local_files_only=True).to_dict()
    AutoTokenizer.from_pretrained(backbone, local_files_only=True).save_pretrained(gliner)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    # Use ordinary streamed HTTPS for large files, with pinned SHA-256 verification.
    # This also works on hosts where the Hub's optional large-file transport stalls.
    with ThreadPoolExecutor(max_workers=2) as downloads:
        futures = [
            downloads.submit(
                _download_weights,
                "convaiinnovations/laya",
                LAYA_REVISION,
                "model.safetensors",
                root / "laya" / "model.safetensors",
                "891102d372688fc2a094dac56a384bc537b87c63f21f9f3dac0be2b7cbc8d86c",
            ),
            downloads.submit(
                _download_weights,
                "urchade/gliner_small-v2.1",
                GLINER_REVISION,
                "pytorch_model.bin",
                gliner / "pytorch_model.bin",
                "1d4e83e4e4ae4ae0a4fbc81a32ee6de480fb341650d73e808088bb2800312de4",
            ),
        ]
        for future in futures:
            future.result()
    print("Prepared offline English dialog models in", root)


if __name__ == "__main__":
    main()
