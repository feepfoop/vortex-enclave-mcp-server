"""Local embedders.

These are optional. The default `VortexClient` accepts `text` queries and
relies on server-side embedding (configured via `VORTEX_EMBED_URL` on the
proxy Lambda). If you'd rather keep query text on your machine — for
privacy, latency, or because you have a GPU sitting idle — use a local
embedder.

Anything callable as `embedder(text: str) -> list[float]` works. The SDK
calls it before sending, so the server only sees the resulting 1024-dim
vector.

`MxbaiEmbedder` is the recommended local embedder because it produces
vectors in the exact same embedding space as the hosted index.

    Install: pip install 'vortex-enclave[mxbai]'
    Usage:   client = VortexClient(local_embedder=MxbaiEmbedder())

If you want to bring your own embedding model entirely, just write a
function — the SDK doesn't care, but you take responsibility for the
embedding-space match.
"""

from __future__ import annotations
from typing import List, Sequence

from .constants import (
    EMBEDDING_DIMENSION,
    EMBEDDING_MODEL,
    EMBEDDING_NORMALIZED,
)


class MxbaiEmbedder:
    """Loads ``mixedbread-ai/mxbai-embed-large-v1`` via sentence-transformers
    and exposes it as a callable suitable for ``VortexClient(local_embedder=...)``.

    First call downloads ~700MB of model weights into the HuggingFace cache.
    Subsequent loads use the cache. Auto-detects the best device:
    CUDA → MPS (Apple Silicon GPU) → CPU.

    Args:
        device: Override device autodetection. One of "cuda", "mps", "cpu".
        model_name: Override the model. **Don't change this unless you've
            also rebuilt the upstream index with the new model.**
    """

    def __init__(self, device: str | None = None, model_name: str = EMBEDDING_MODEL):
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as e:
            raise ImportError(
                "MxbaiEmbedder requires sentence-transformers. "
                "Install with:  pip install 'vortex-enclave[mxbai]'"
            ) from e

        self.model_name = model_name
        self._model = SentenceTransformer(model_name, device=device)
        try:
            actual_dim = self._model.get_sentence_embedding_dimension()
        except AttributeError:
            actual_dim = self._model.get_embedding_dimension()
        if actual_dim != EMBEDDING_DIMENSION:
            raise RuntimeError(
                f"Embedding dimension mismatch: model produces {actual_dim}, "
                f"upstream index expects {EMBEDDING_DIMENSION}. Index was built "
                f"with {EMBEDDING_MODEL}."
            )

    def __call__(self, text: str) -> List[float]:
        """Embed a single string. Returns a 1024-d L2-normalized list[float]."""
        v = self._model.encode([text], normalize_embeddings=EMBEDDING_NORMALIZED)
        return v[0].tolist()

    def encode_batch(self, texts: Sequence[str], batch_size: int = 32) -> List[List[float]]:
        """Embed many strings at once. Returns a list of 1024-d L2-normalized vectors."""
        v = self._model.encode(
            list(texts),
            normalize_embeddings=EMBEDDING_NORMALIZED,
            batch_size=batch_size,
        )
        return v.tolist()


__all__ = ["MxbaiEmbedder"]
