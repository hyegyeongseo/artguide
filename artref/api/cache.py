from functools import lru_cache
import hashlib, numpy as np
from ml.embed import embedder

@lru_cache(maxsize=4096)
def _text_vec_cached(text: str, model_id: str) -> bytes:
    return embedder.text(text).astype("float32").tobytes()

def text_vec(text: str) -> np.ndarray:
    return np.frombuffer(_text_vec_cached(text, embedder.model_id), dtype="float32")

def img_hash(pil) -> str:
    return hashlib.sha256(pil.tobytes()).hexdigest()[:16]
