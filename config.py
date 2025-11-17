"""Central configuration and paths.

Loads paths from environment variables when provided, with sensible defaults.
"""
import os

# Path to the CF model pickle (used by ai_recommender)
CF_MODEL_PATH = os.getenv("CF_MODEL_PATH", os.path.join("models", "movielens_cf.pkl"))

# Optional MovieLens dataset path for tag enrichment
MOVIELENS_PATH = os.getenv("MOVIELENS_PATH")

# Feature flags
ENABLE_CONCEPT_EXPANSION = os.getenv("ENABLE_CONCEPT_EXPANSION", "true").lower() == "true"

# Default region for watch providers (TMDb JustWatch integration)
DEFAULT_REGION = os.getenv("DEFAULT_REGION", "US").upper()

# External model (Hugging Face) for embeddings-based similarity
ENABLE_HF_MODEL = os.getenv("ENABLE_HF_MODEL", "false").lower() == "true"
HF_MODEL_NAME = os.getenv("HF_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")

# Optional Cross-Encoder reranker to refine top-K candidates
ENABLE_RERANKER = os.getenv("ENABLE_RERANKER", "false").lower() == "true"
RERANKER_MODEL_NAME = os.getenv("RERANKER_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L6-v2")
RERANKER_TOP_K = int(os.getenv("RERANKER_TOP_K", "40"))
