"""
Deprecated: use `movielens.py` instead. This module re-exports wrappers for backwards compatibility.
"""

from typing import Dict, Tuple, List, Optional
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

from movielens import (
    build_item_user_matrix as _build_item_user_matrix,
    compute_item_similarities_blockwise as _compute_item_similarities_blockwise,
    save_similarity_model as _save_similarity_model,
    load_similarity_model as _load_similarity_model,
    recommend_similar_by_movieId as _recommend_similar_by_movieId,
    recommend_similar_by_tmdbId as _recommend_similar_by_tmdbId,
    build_and_save_cf_model as _build_and_save_cf_model,
)


def build_item_user_matrix(ratings: pd.DataFrame) -> Tuple[csr_matrix, Dict[int, int], Dict[int, int]]:
    return _build_item_user_matrix(ratings)


def compute_item_similarities_blockwise(item_user: csr_matrix, top_k: int = 50, block_size: int = 500) -> Tuple[np.ndarray, np.ndarray]:
    return _compute_item_similarities_blockwise(item_user, top_k=top_k, block_size=block_size)


def save_similarity_model(path: str, item_index: Dict[int, int], user_index: Dict[int, int], top_indices: np.ndarray, top_scores: np.ndarray, index_to_movieId: List[int], movieId_to_tmdbId: Dict[int, int], tmdbId_to_movieId: Dict[int, int]):
    payload = {
        'item_index': item_index,
        'user_index': user_index,
        'top_indices': top_indices,
        'top_scores': top_scores,
        'index_to_movieId': index_to_movieId,
        'movieId_to_tmdbId': movieId_to_tmdbId,
        'tmdbId_to_movieId': tmdbId_to_movieId,
    }
    return _save_similarity_model(path, payload)


def load_similarity_model(path: str):
    return _load_similarity_model(path)


def recommend_similar_by_movieId(movie_id: int, model, index_to_movieId: List[int], top_n: int = 12) -> List[int]:
    return _recommend_similar_by_movieId(movie_id, model, index_to_movieId, top_n=top_n)


def recommend_similar_by_tmdbId(tmdb_id: int, model, top_n: int = 12) -> List[int]:
    return _recommend_similar_by_tmdbId(tmdb_id, model, top_n=top_n)


def build_and_save_cf_model(
    ratings: pd.DataFrame,
    links: pd.DataFrame,
    model_path: str = 'models/movielens_cf.pkl',
    top_k: int = 50,
    min_item_ratings: int = 5,
    use_blockwise: bool = False,
    block_size: int = 500,
) -> Optional[str]:
    # The unified module always uses blockwise; preserve flag for compatibility
    return _build_and_save_cf_model(
        ratings,
        links,
        model_path=model_path,
        top_k=top_k,
        min_item_ratings=min_item_ratings,
        block_size=block_size,
    )


__all__ = [
    "build_item_user_matrix",
    "compute_item_similarities_blockwise",
    "save_similarity_model",
    "load_similarity_model",
    "recommend_similar_by_movieId",
    "recommend_similar_by_tmdbId",
    "build_and_save_cf_model",
]
