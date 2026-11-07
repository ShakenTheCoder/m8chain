"""Local multilingual sentence embeddings, batched once and reused across comparisons."""

from collections import OrderedDict
from functools import lru_cache
from threading import Lock
import numpy as np

MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
MAX_TOKENS = 128
_cache: OrderedDict[str, np.ndarray] = OrderedDict()
_lock = Lock()


class SemanticUnavailable(Exception):
    pass


@lru_cache(maxsize=1)
def _load():
    from transformers import AutoModel, AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision=MODEL_REVISION)
    model = AutoModel.from_pretrained(MODEL_ID, revision=MODEL_REVISION).to("cpu").eval()
    return tokenizer, model


def embed_texts(texts: list[str]) -> dict[str, np.ndarray]:
    unique = list(dict.fromkeys(text for text in texts if text.strip()))
    if not unique:
        return {}
    with _lock:
        try:
            missing = [text for text in unique if text not in _cache]
            if missing:
                import torch
                tokenizer, model = _load()
                encoded = tokenizer(missing, truncation=True, max_length=MAX_TOKENS,
                                    return_overflowing_tokens=True, padding=False)
                owners = encoded.pop("overflow_to_sample_mapping")
                chunks = [{key: values[index] for key, values in encoded.items()} for index in range(len(owners))]
                special = tokenizer.num_special_tokens_to_add(pair=False)
                lengths = [max(1, len(chunk["input_ids"]) - special) for chunk in chunks]
                sums = [np.zeros(model.config.hidden_size, dtype=np.float32) for _ in missing]
                totals = [0] * len(missing)
                for start in range(0, len(chunks), 24):
                    inputs = tokenizer.pad(chunks[start:start + 24], padding=True, return_tensors="pt")
                    with torch.inference_mode():
                        hidden = model(**inputs).last_hidden_state
                        mask = inputs["attention_mask"].unsqueeze(-1).to(hidden.dtype)
                        pooled = ((hidden * mask).sum(1) / mask.sum(1).clamp(min=1)).cpu().numpy()
                    for index, vector in enumerate(pooled, start):
                        owner = owners[index]
                        sums[owner] += vector * lengths[index]
                        totals[owner] += lengths[index]
                for text, vector, total in zip(missing, sums, totals):
                    if not total or not np.isfinite(vector).all() or np.linalg.norm(vector) == 0:
                        raise ValueError("Invalid semantic vector")
                    vector /= np.linalg.norm(vector)
                    vector.setflags(write=False)
                    _cache[text] = vector
            result = {text: _cache[text] for text in unique}
            for text in unique:
                _cache.move_to_end(text)
            while len(_cache) > 8192:
                _cache.popitem(last=False)
            return result
        except Exception:
            # Never pretend lexical-only matching satisfies the requested 50/50 blend.
            raise SemanticUnavailable("Meaning matching is unavailable. Check connectivity to Hugging Face and the local embedding model; saved video analyses are retained.") from None


def cosine(left: np.ndarray, right: np.ndarray) -> float:
    value = float(np.dot(left, right))
    if not np.isfinite(value):
        raise SemanticUnavailable("Meaning matching returned an invalid similarity.")
    return min(1.0, max(0.0, value))
