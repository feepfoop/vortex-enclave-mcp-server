"""Single source of truth for embedding-space constants.

Every vector in the upstream index comes from this exact model. Mixing
models silently returns garbage (cosine similarity across mismatched
embedding spaces is meaningless).

If you self-host Vortex Enclave with a different model, override these
when constructing the client — but be aware the constants represent the
hosted production deployment.
"""

EMBEDDING_MODEL = "mixedbread-ai/mxbai-embed-large-v1"
"""HuggingFace model ID. The hosted index is built with this exact model."""

EMBEDDING_DIMENSION = 1024
"""Every vector — ingested OR query — must have this length."""

EMBEDDING_DISTANCE = "cosine"
"""Distance metric configured on the S3 Vectors index."""

EMBEDDING_NORMALIZED = True
"""Vectors must be L2-normalized so cosine == dot product."""
