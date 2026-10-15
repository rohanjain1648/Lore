"""Local sentence embeddings (fastembed, no API key). Falls back to a hashing embedder
if the model can't be downloaded, so the app still runs offline."""

from __future__ import annotations

import hashlib
import logging
import math
import re
from functools import lru_cache

from . import config

log = logging.getLogger(__name__)
MAX_CHARS = 2000


@lru_cache(maxsize=1)
def _model():
    try:
        from fastembed import TextEmbedding

        return TextEmbedding(model_name=config.EMBED_MODEL)
    except Exception as e:  # pragma: no cover - offline fallback
        log.warning("fastembed unavailable (%s); using hashing embeddings", e)
        return None


def _hash_embed(text: str) -> list[float]:
    v = [0.0] * config.EMBED_DIM
    for tok in re.findall(r"[a-z0-9\-]+", text.lower()):
        h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
        v[h % config.EMBED_DIM] += 1.0 if (h >> 8) & 1 else -1.0
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


def embed(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    m = _model()
    if m is None:
        return [_hash_embed(t) for t in texts]
    # the model reads ~512 tokens; truncating keeps memory flat on long READMEs / issue bodies
    texts = [t[:MAX_CHARS] for t in texts]
    return [list(map(float, v)) for v in m.embed(texts, batch_size=16)]


def embed_one(text: str) -> list[float]:
    return embed([text])[0]


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
