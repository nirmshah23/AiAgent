"""CPU inference adapters: Laya classifies; Regex and optional INT8 GLiNER extract."""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor

import regex

from .config import Intent


class LocalModels:
    """Own one serialized inference worker shared by sessions, with bounded admission."""

    def __init__(
        self,
        laya_path: str,
        gliner_path: str,
        entity_threshold: float = 0.5,
        *,
        quantize: bool = True,
    ):
        """Load prepared local models on CPU; never download weights during a call."""
        from pathlib import Path

        from gliner import GLiNER
        from laya import Agent

        if not Path(laya_path).is_dir() or not Path(gliner_path).is_dir():
            raise ValueError("Laya and GLiNER paths must be prepared local model directories")
        self.laya = Agent(laya_path, device="cpu")
        self.gliner = GLiNER.from_pretrained(
            gliner_path,
            map_location="cpu",
            local_files_only=True,
            quantize="int8" if quantize else None,
        )
        self.gliner.eval()
        self.entity_threshold = entity_threshold
        self.worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dialog-models")
        self.admission = asyncio.Semaphore(1)

    async def _run(self, function, *args):
        # Retain the slot until an already-running native operation actually finishes.
        async with self.admission:
            future = asyncio.get_running_loop().run_in_executor(self.worker, function, *args)
            try:
                return await asyncio.shield(future)
            except asyncio.CancelledError as cancelled:
                try:
                    await future
                except Exception:
                    # Preserve interruption even if the native call subsequently fails.
                    pass
                raise cancelled

    def _classify(self, text, intents):
        questions = {
            intent.name: {
                "type": "noul",
                "instructions": "Does the caller request this intent? " + intent.description,
                "criteria": {
                    "true": "The caller requests this intent",
                    "false": "The caller does not request this intent",
                },
            }
            for intent in intents
        }
        answers = self.laya.predict_long(text, questions)["answers"]
        return {intent.name: float(answers[intent.name]["noul"]) for intent in intents}

    async def classify(self, text: str, intents: list[Intent]) -> dict[str, float]:
        """Ask independent yes/no questions, allowing several simultaneous intents."""
        return await self._run(self._classify, text, intents)

    def _extract(self, history, intent):
        values = {}
        labels = [f.label for f in intent.fields if f.label]
        for text in history:
            regex_values = {}
            for f in intent.fields:
                if f.regex:
                    matches = list(regex.finditer(f.regex, text, timeout=0.05))
                    if matches:
                        match = matches[-1]
                        regex_values[f.name] = match.group(1) if match.lastindex else match.group()
            model_values = {}
            if labels:
                # Process each caller response without silently discarding long suffixes.
                prepared = self.gliner.prepare_batch(text, labels)
                if len(prepared["tokens"][0]) > self.gliner.config.max_len:
                    raise ValueError("Caller response exceeds GLiNER input limit")
                entities = self.gliner.predict_entities(
                    text, labels, threshold=self.entity_threshold
                )
                for entity in sorted(entities, key=lambda e: e["start"]):
                    for f in intent.fields:
                        if f.label == entity["label"]:
                            model_values[f.name] = entity["text"]
            # Newer caller responses supersede older values; Regex wins within each response.
            values.update(model_values | regex_values)
        for f in intent.fields:
            if f.name in values:
                value = values[f.name].strip()
                if f.normalize == "digits":
                    value = re.sub(r"\D", "", value)
                elif f.normalize == "upper":
                    value = value.upper()
                elif f.normalize == "lower":
                    value = value.lower()
                values[f.name] = value
        return values

    async def extract(self, history: list[str], intent: Intent) -> dict[str, str]:
        """Run intent-specific Regex followed by GLiNER, merging normalized fields."""
        return await self._run(self._extract, history, intent)

    def close(self):
        """Join the inference worker after active sessions have closed."""
        self.worker.shutdown(wait=True, cancel_futures=True)
