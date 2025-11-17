"""
Deprecated: use `movielens.load_tags_enrichment` instead. This module re-exports a wrapper
for backwards compatibility.
"""

from typing import Dict, List
from movielens import load_tags_enrichment as _load_tags_enrichment


def load_tags_enrichment(dataset_path: str, min_tag_freq: int = 5, max_tags_per_movie: int = 20) -> Dict[int, List[str]]:
    return _load_tags_enrichment(dataset_path, min_tag_freq=min_tag_freq, max_tags_per_movie=max_tags_per_movie)


__all__ = ["load_tags_enrichment"]
