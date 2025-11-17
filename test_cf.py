"""Smoke test for MovieLens collaborative filtering model build/load."""
import argparse
import os
from movielens_loader import download_movielens, load_movielens
from movielens_cf import build_and_save_cf_model, load_similarity_model, recommend_similar_by_tmdbId
from tmdb_service import TMDbService


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset-path", help="Local MovieLens folder with ratings/movies/links; if omitted, will download small set")
    p.add_argument("--model-path", default=os.path.join("models", "movielens_cf.pkl"))
    p.add_argument("--reuse", action="store_true", help="Reuse existing model if present")
    p.add_argument("--blockwise", action="store_true")
    p.add_argument("--block-size", type=int, default=500)
    p.add_argument("--min-item-ratings", type=int, default=5)
    return p.parse_args()


def main():
    args = parse_args()
    print("== CF Smoke Test ==")

    if args.reuse and os.path.exists(args.model_path):
        print(f"Loading existing model at {args.model_path}")
    else:
        if args.dataset_path:
            path = args.dataset_path
        else:
            path = download_movielens('ml-latest-small')
        ratings, movies, links = load_movielens(path)
        print(f"Loaded ratings: {len(ratings)}, movies: {len(movies)}, links: {len(links)}")
        model_path = build_and_save_cf_model(
            ratings,
            links,
            model_path=args.model_path,
            min_item_ratings=args.min_item_ratings,
            use_blockwise=args.blockwise,
            block_size=args.block_size,
        )
        if not model_path or not os.path.exists(model_path):
            print("Failed to build CF model")
            return
        print(f"Model saved to {model_path}")

    model = load_similarity_model(args.model_path)
    # Pick a known movie via TMDb search and get CF neighbors
    anchor_title = "Interstellar"
    search = TMDbService.search_movies(anchor_title, page=1)
    if not search:
        print("Anchor search failed")
        return
    tmdb_id = search[0]['id']
    neighbors = recommend_similar_by_tmdbId(tmdb_id, model, top_n=10)
    print(f"CF neighbors (tmdb ids) for {anchor_title}: {neighbors}")
    detailed = []
    for nid in neighbors[:5]:
        d = TMDbService.get_movie_details(nid)
        if d:
            detailed.append(d.get('title'))
    print("Sample neighbor titles:", detailed)


if __name__ == '__main__':
    main()
