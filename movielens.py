"""Unified MovieLens utilities: loading, CF model, tag enrichment, and CLI.

Functions provided:
- load_movielens(path) -> ratings, movies, links
- build_and_save_cf_model(ratings, links, ...) -> model_path
- load_similarity_model(path) -> dict
- recommend_similar_by_tmdbId(tmdb_id, model, top_n) -> List[int]
- load_tags_enrichment(dataset_path, min_tag_freq, max_tags_per_movie) -> Dict[tmdbId, List[str]]

CLI usage (PowerShell):
python movielens.py build --dataset-path "C:\\path\\to\\ml-32m" --blockwise --block-size 1000 --min-item-ratings 10 --top-k 75
"""
import os
import io
import zipfile
import argparse
import pickle
from typing import Tuple, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.metrics.pairwise import cosine_similarity
import requests


# ------------------ Loader ------------------

MOVIELENS_URLS = {
    "ml-latest-small": "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip",
    "ml-latest": "https://files.grouplens.org/datasets/movielens/ml-latest.zip",
}


def download_movielens(dataset: str = "ml-latest-small", dest_dir: Optional[str] = None) -> str:
    dest_dir = dest_dir or os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(dest_dir, exist_ok=True)
    url = MOVIELENS_URLS.get(dataset)
    if not url:
        raise ValueError(f"Unknown dataset '{dataset}'")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        zf.extractall(dest_dir)
        # Try to detect top folder
        names = [n for n in zf.namelist() if n.endswith('/')]
        names.sort(key=len)
        top = names[0] if names else ''
    extracted = os.path.join(dest_dir, top.rstrip('/')) if top else dest_dir
    for f in ("ratings.csv", "movies.csv", "links.csv"):
        if not os.path.exists(os.path.join(extracted, f)):
            raise FileNotFoundError(f"Missing {f} in {extracted}")
    return extracted


def load_movielens(path: str) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ratings = pd.read_csv(os.path.join(path, "ratings.csv"))
    movies = pd.read_csv(os.path.join(path, "movies.csv"))
    links = pd.read_csv(os.path.join(path, "links.csv"))
    return ratings, movies, links


def build_tmdb_mapping(links: pd.DataFrame) -> Tuple[Dict[int, int], Dict[int, int]]:
    clean = links.dropna(subset=["tmdbId"]).copy()
    clean["movieId"] = clean["movieId"].astype(int)
    clean["tmdbId"] = clean["tmdbId"].astype(int)
    movie_to_tmdb = dict(zip(clean["movieId"], clean["tmdbId"]))
    tmdb_to_movie = dict(zip(clean["tmdbId"], clean["movieId"]))
    return movie_to_tmdb, tmdb_to_movie


# ------------------ CF Model ------------------

def build_item_user_matrix(ratings: pd.DataFrame) -> Tuple[csr_matrix, Dict[int, int], Dict[int, int]]:
    unique_users = ratings['userId'].unique()
    unique_items = ratings['movieId'].unique()
    user_index = {uid: i for i, uid in enumerate(unique_users)}
    item_index = {mid: i for i, mid in enumerate(unique_items)}
    rows = ratings['movieId'].map(item_index).values
    cols = ratings['userId'].map(user_index).values
    data = ratings['rating'].astype(float).values
    mat = csr_matrix((data, (rows, cols)), shape=(len(unique_items), len(unique_users)), dtype=np.float32)
    return mat, item_index, user_index


def compute_item_similarities_blockwise(item_user: csr_matrix, top_k: int = 50, block_size: int = 500) -> Tuple[np.ndarray, np.ndarray]:
    n_items = item_user.shape[0]
    norms = np.sqrt(item_user.multiply(item_user).sum(axis=1)).A1 + 1e-10
    top_indices = np.zeros((n_items, top_k), dtype=np.int32)
    top_scores = np.zeros((n_items, top_k), dtype=np.float32)
    item_user_T = item_user.T
    for start in range(0, n_items, block_size):
        end = min(start + block_size, n_items)
        block = item_user[start:end]
        dots = block * item_user_T
        for local_row in range(dots.shape[0]):
            global_row = start + local_row
            row = dots.getrow(local_row)
            idx = row.indices
            vals = row.data.astype(np.float32)
            denom = norms[global_row] * norms[idx]
            sims = vals / denom
            mask = idx != global_row
            idx = idx[mask]
            sims = sims[mask]
            if sims.size == 0:
                continue
            if sims.size <= top_k:
                order = np.argsort(-sims)
            else:
                part = np.argpartition(-sims, top_k)[:top_k]
                order = part[np.argsort(-sims[part])]
            k = min(top_k, order.size)
            top_indices[global_row, :k] = idx[order][:k]
            top_scores[global_row, :k] = sims[order][:k]
    return top_indices, top_scores


def save_similarity_model(path: str, payload: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        pickle.dump(payload, f)


def load_similarity_model(path: str):
    with open(path, 'rb') as f:
        return pickle.load(f)


def build_and_save_cf_model(
    ratings: pd.DataFrame,
    links: pd.DataFrame,
    model_path: str = os.path.join('models', 'movielens_cf.pkl'),
    top_k: int = 50,
    min_item_ratings: int = 5,
    block_size: int = 500,
) -> Optional[str]:
    movie_to_tmdb, tmdb_to_movie = build_tmdb_mapping(links)
    valid = ratings[ratings['movieId'].isin(movie_to_tmdb.keys())].copy()
    if min_item_ratings > 1:
        counts = valid.groupby('movieId')['rating'].count()
        keep_ids = set(counts[counts >= min_item_ratings].index.tolist())
        valid = valid[valid['movieId'].isin(keep_ids)]
        print(f"Pruned ratings from {len(ratings)} to {len(valid)} using min_item_ratings={min_item_ratings}")
    if valid.empty:
        return None
    item_user, item_index, user_index = build_item_user_matrix(valid)
    top_indices, top_scores = compute_item_similarities_blockwise(item_user, top_k=top_k, block_size=block_size)
    index_to_movie = [None] * len(item_index)
    for mid, idx in item_index.items():
        index_to_movie[idx] = mid
    save_similarity_model(model_path, {
        'item_index': item_index,
        'user_index': user_index,
        'top_indices': top_indices,
        'top_scores': top_scores,
        'index_to_movieId': index_to_movie,
        'movieId_to_tmdbId': movie_to_tmdb,
        'tmdbId_to_movieId': tmdb_to_movie,
    })
    return model_path


def recommend_similar_by_movieId(movie_id: int, model, index_to_movieId: List[int], top_n: int = 12) -> List[int]:
    item_index = model['item_index']
    if movie_id not in item_index:
        return []
    idx = item_index[movie_id]
    neighbors = model['top_indices'][idx]
    scores = model['top_scores'][idx]
    order = np.argsort(-scores)
    recs = []
    for j in order:
        mid = index_to_movieId[neighbors[j]]
        if mid != movie_id and scores[j] > 0:
            recs.append(mid)
        if len(recs) >= top_n:
            break
    return recs


def recommend_similar_by_tmdbId(tmdb_id: int, model, top_n: int = 12) -> List[int]:
    tmdb_to_movie = model.get('tmdbId_to_movieId', {})
    movie_to_tmdb = model.get('movieId_to_tmdbId', {})
    index_to_movie = model.get('index_to_movieId')
    if tmdb_id not in tmdb_to_movie or index_to_movie is None:
        return []
    ml_movie_id = tmdb_to_movie[tmdb_id]
    rec_ml_ids = recommend_similar_by_movieId(ml_movie_id, model, index_to_movie, top_n=top_n*2)
    tmdb_recs = []
    for mid in rec_ml_ids:
        tid = movie_to_tmdb.get(mid)
        if tid:
            tmdb_recs.append(tid)
        if len(tmdb_recs) >= top_n:
            break
    return tmdb_recs


# ------------------ Tags Enrichment ------------------

import re
TAG_TOKEN_RE = re.compile(r"[^a-z0-9]+")


def _normalize_tag(tag: str) -> str:
    t = tag.strip().lower()
    t = TAG_TOKEN_RE.sub(" ", t)
    t = " ".join(t.split())
    return t


def load_tags_enrichment(dataset_path: str, min_tag_freq: int = 5, max_tags_per_movie: int = 20) -> Dict[int, List[str]]:
    tags_fp = os.path.join(dataset_path, "tags.csv")
    links_fp = os.path.join(dataset_path, "links.csv")
    if not (os.path.exists(tags_fp) and os.path.exists(links_fp)):
        return {}
    tags = pd.read_csv(tags_fp)
    links = pd.read_csv(links_fp)
    links = links.dropna(subset=["tmdbId"])[["movieId", "tmdbId"]].copy()
    links["tmdbId"] = links["tmdbId"].astype(int)
    tags = tags[["movieId", "tag"]].dropna()
    tags["tag"] = tags["tag"].astype(str).map(_normalize_tag)
    tags = tags[tags["tag"] != ""]
    merged = tags.merge(links, on="movieId", how="inner")
    counts = merged.groupby(["tmdbId", "tag"]).size().reset_index(name="count")
    counts = counts[counts["count"] >= min_tag_freq]
    counts.sort_values(["tmdbId", "count"], ascending=[True, False], inplace=True)
    top = counts.groupby("tmdbId").head(max_tags_per_movie)
    result: Dict[int, List[str]] = {}
    for tmdb_id, group in top.groupby("tmdbId"):
        result[int(tmdb_id)] = group["tag"].tolist()
    return result


# ------------------ CLI ------------------

def _parse_args():
    p = argparse.ArgumentParser(description="MovieLens utilities")
    sub = p.add_subparsers(dest="cmd")
    b = sub.add_parser("build", help="Build CF model from dataset path")
    b.add_argument("--dataset-path", required=True)
    b.add_argument("--model-path", default=os.path.join("models", "movielens_cf.pkl"))
    b.add_argument("--top-k", type=int, default=50)
    b.add_argument("--min-item-ratings", type=int, default=5)
    b.add_argument("--block-size", type=int, default=500)
    return p.parse_args()


def _main():
    args = _parse_args()
    if args.cmd == "build":
        ratings, movies, links = load_movielens(args.dataset_path)
        print(f"Loaded ratings={len(ratings):,}, movies={len(movies):,}, links={len(links):,}")
        model_path = build_and_save_cf_model(
            ratings,
            links,
            model_path=args.model_path,
            top_k=args.top_k,
            min_item_ratings=args.min_item_ratings,
            block_size=args.block_size,
        )
        if model_path and os.path.exists(model_path):
            print(f"✅ CF model saved: {model_path}")
        else:
            print("❌ Failed to build CF model")


if __name__ == "__main__":
    _main()
