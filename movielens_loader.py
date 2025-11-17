"""
Deprecated: use `movielens.py` instead. This module re-exports wrappers for backwards compatibility.
"""

from typing import Tuple, Optional, Dict
import pandas as pd

from movielens import download_movielens as _download_movielens
from movielens import load_movielens as _load_movielens
from movielens import build_tmdb_mapping as _build_tmdb_mapping


def download_movielens(dataset: str = "ml-latest-small", dest_dir: Optional[str] = None) -> str:
    return _download_movielens(dataset=dataset, dest_dir=dest_dir)


def load_movielens(path: Optional[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    # In the unified module, path is required; keep previous behavior if None
    if path is None:
        import os
        default_path = os.path.join(os.path.dirname(__file__), "data", "ml-latest-small")
        return _load_movielens(default_path)
    return _load_movielens(path)


def build_tmdb_mapping(links: pd.DataFrame) -> Tuple[Dict[int, int], Dict[int, int]]:
    return _build_tmdb_mapping(links)


__all__ = [
    "download_movielens",
    "load_movielens",
    "build_tmdb_mapping",
]
