"""
Deprecated thin wrappers around tmdb_service (API key now loaded from .env).

This module is kept for backward compatibility and does NOT contain any API keys.
Prefer importing and using `tmdb_service.TMDbService` directly.
"""

from tmdb_service import TMDbService


def search_movie(title: str):
    results = TMDbService.search_movies(title, page=1) or []
    if not results:
        return None
    movie = results[0]
    details = TMDbService.get_movie_details(movie.get("id")) if movie.get("id") else {}
    return {
        "id": movie.get("id"),
        "title": movie.get("title"),
        "overview": movie.get("overview", ""),
        "poster_path": TMDbService.format_poster_url(movie.get("poster_path")),
        "genres": [g.get("name") for g in details.get("genres", [])],
        "rating": movie.get("vote_average", 0),
        "release_date": movie.get("release_date", ""),
    }


def get_movie_genres(movie_id: int):
    details = TMDbService.get_movie_details(movie_id) or {}
    return [g.get("name") for g in details.get("genres", [])]


def get_similar_movies(movie_id: int, count: int = 5):
    sims = TMDbService.get_similar_movies(movie_id, page=1) or []
    results = []
    for movie in sims[:count]:
        results.append({
            "id": movie.get("id"),
            "title": movie.get("title"),
            "overview": movie.get("overview", ""),
            "poster_path": TMDbService.format_poster_url(movie.get("poster_path")),
            "genres": [],
            "rating": movie.get("vote_average", 0),
            "release_date": movie.get("release_date", ""),
        })
    return results
