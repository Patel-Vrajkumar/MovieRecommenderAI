"""
Deprecated standalone builder. Use unified CLI:

    python movielens.py build --dataset-path <path> --top-k 75 --min-item-ratings 10 --block-size 1000

Kept only for backwards compatibility; delegates to movielens module.
"""
import argparse
import os
from movielens import load_movielens, build_and_save_cf_model


def parse_args():
    p = argparse.ArgumentParser(description="(Deprecated) Build MovieLens CF model")
    p.add_argument("--dataset-path", required=True)
    p.add_argument("--model-path", default=os.path.join("models", "movielens_cf.pkl"))
    p.add_argument("--top-k", type=int, default=50)
    p.add_argument("--min-item-ratings", type=int, default=5)
    p.add_argument("--block-size", type=int, default=500)
    return p.parse_args()


def main():
    args = parse_args()
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
    main()
