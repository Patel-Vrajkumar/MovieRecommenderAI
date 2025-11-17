"""
TMDb service wrapper.

Loads API key from .env (TMDB_API_KEY) and exposes convenience methods to call
The Movie Database (TMDb) REST API, including movies, collections, people, and
utility helpers like poster formatting and a YouTube trailer finder.

Do NOT hardcode API keys. Use a .env file or environment variables.
"""

import requests
import os
import time
import logging
from threading import RLock
from dotenv import load_dotenv
from typing import Optional

# Load environment variables
load_dotenv()

API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"
IMAGE_URL = "https://image.tmdb.org/t/p/w500"

# Simple in-process TTL cache for TMDb JSON responses
_cache = {}
_cache_lock = RLock()
logger = logging.getLogger(__name__)


def _cache_key(path: str, params: dict) -> str:
    # Exclude API key from cache key (it is constant per process)
    items = tuple(sorted((k, v) for k, v in (params or {}).items() if k != "api_key"))
    return f"{path}|{items}"


def _get_json(path: str, params: Optional[dict] = None, ttl: int = 600, retries: int = 3, timeout: int = 10):
    """Fetch JSON from TMDb with TTL cache and retry/backoff.

    Returns parsed JSON (dict) on 200; else None.
    """
    if params is None:
        params = {}
    params = {**params, "api_key": API_KEY}
    key = _cache_key(path, params)

    now = time.time()
    with _cache_lock:
        entry = _cache.get(key)
        if entry and entry[0] > now:
            return entry[1]

    url = f"{BASE_URL}{path}"
    backoffs = [0.3, 0.6, 1.2]
    attempts = max(1, retries)
    last_err = None
    for i in range(attempts):
        try:
            resp = requests.get(url, params=params, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                with _cache_lock:
                    _cache[key] = (now + ttl, data)
                return data
            # Handle rate limit or transient server errors
            if resp.status_code in (429, 500, 502, 503, 504):
                last_err = f"HTTP {resp.status_code}"
            else:
                logger.warning(f"TMDb request failed {path}: HTTP {resp.status_code}")
                return None
        except Exception as e:
            last_err = str(e)
        # Backoff before next attempt
        if i < attempts - 1:
            time.sleep(backoffs[min(i, len(backoffs)-1)])
    logger.warning(f"TMDb request failed after retries {path}: {last_err}")
    return None

class TMDbService:
    """Service class for interacting with The Movie Database API"""
    
    @staticmethod
    def search_movies(query, page=1):
        """Search for movies by title"""
        try:
            data = _get_json(
                "/search/movie",
                {"query": query, "language": "en-US", "page": page},
                ttl=300,
            )
            return (data or {}).get("results", [])
        except Exception as e:
            logger.warning(f"Error searching movies: {e}")
            return []
    
    @staticmethod
    def get_movie_details(movie_id):
        """Get detailed information about a specific movie"""
        try:
            return _get_json(f"/movie/{movie_id}", {"language": "en-US"}, ttl=3600)
        except Exception as e:
            logger.warning(f"Error fetching movie details: {e}")
            return None
    
    @staticmethod
    def get_movie_videos(movie_id):
        """Get videos (trailers, teasers) for a specific movie"""
        try:
            data = _get_json(f"/movie/{movie_id}/videos", {"language": "en-US"}, ttl=3600)
            return (data or {}).get("results", [])
        except Exception as e:
            logger.warning(f"Error fetching movie videos: {e}")
            return []
    
    @staticmethod
    def get_similar_movies(movie_id, page=1):
        """Get movies similar to a specific movie"""
        try:
            data = _get_json(
                f"/movie/{movie_id}/similar",
                {"language": "en-US", "page": page},
                ttl=1800,
            )
            return (data or {}).get("results", [])
        except Exception as e:
            logger.warning(f"Error fetching similar movies: {e}")
            return []
    
    @staticmethod
    def get_movie_credits(movie_id):
        """Get cast and crew information for a movie"""
        try:
            return _get_json(f"/movie/{movie_id}/credits", {}, ttl=3600)
        except Exception as e:
            logger.warning(f"Error fetching movie credits: {e}")
            return None
    
    @staticmethod
    def get_movie_keywords(movie_id):
        """Get keywords associated with a movie"""
        try:
            data = _get_json(f"/movie/{movie_id}/keywords", {}, ttl=7200)
            return (data or {}).get("keywords", [])
        except Exception as e:
            logger.warning(f"Error fetching movie keywords: {e}")
            return []
    
    @staticmethod
    def get_trending_movies(time_window="week"):
        """Get trending movies (day or week)"""
        try:
            data = _get_json(f"/trending/movie/{time_window}", {}, ttl=600)
            return (data or {}).get("results", [])
        except Exception as e:
            logger.warning(f"Error fetching trending movies: {e}")
            return []

    @staticmethod
    def get_now_playing_movies(page=1):
        """Get currently playing (latest releases) movies."""
        try:
            data = _get_json("/movie/now_playing", {"language": "en-US", "page": page}, ttl=900)
            return (data or {}).get("results", [])
        except Exception as e:
            logger.warning(f"Error fetching now playing movies: {e}")
            return []

    @staticmethod
    def get_latest_movie():
        """Get the very latest added movie (single object). TMDb may return incomplete data sometimes."""
        try:
            data = _get_json("/movie/latest", {"language": "en-US"}, ttl=1800)
            return data or None
        except Exception as e:
            logger.warning(f"Error fetching latest movie: {e}")
            return None
    
    @staticmethod
    def get_popular_movies(page=1):
        """Get popular movies"""
        try:
            data = _get_json("/movie/popular", {"language": "en-US", "page": page}, ttl=600)
            return (data or {}).get("results", [])
        except Exception as e:
            logger.warning(f"Error fetching popular movies: {e}")
            return []
    
    @staticmethod
    def format_poster_url(poster_path):
        """Format poster path to full URL"""
        if poster_path:
            return IMAGE_URL + poster_path
        return "/static/no_image.svg"
    
    @staticmethod
    def get_youtube_trailer(movie_id):
        """Get YouTube trailer URL for a movie"""
        videos = TMDbService.get_movie_videos(movie_id)
        
        for video in videos:
            if video.get("site") == "YouTube" and video.get("type") == "Trailer":
                return f"https://www.youtube.com/watch?v={video['key']}"
        
        return None
    
    @staticmethod
    def get_collection(collection_id):
        """Get all movies in a collection (franchise/series)"""
        try:
            return _get_json(f"/collection/{collection_id}", {"language": "en-US"}, ttl=7200)
        except Exception as e:
            logger.warning(f"Error fetching collection: {e}")
            return None

    @staticmethod
    def get_watch_providers(movie_id, region: str = "US"):
        """Get watch provider information for a movie for a given region.

        Returns a dict with keys like 'link', 'flatrate', 'rent', 'buy' when available.
        """
        try:
            data = _get_json(f"/movie/{movie_id}/watch/providers", {}, ttl=3600)
            results = (data or {}).get("results", {})
            region_code = (region or "US").upper()
            info = results.get(region_code) or results.get("US") or {}
            # Shape minimal response: preserve link and plan categories
            out = {
                "link": info.get("link"),
            }
            for key in ("flatrate", "rent", "buy", "free", "ads"):
                if key in info and isinstance(info.get(key), list):
                    out[key] = info.get(key)
            return out
        except Exception as e:
            logger.warning(f"Error fetching watch providers: {e}")
            return {}
    
    @staticmethod
    def autocomplete_search(query, limit=5):
        """Quick search for autocomplete suggestions"""
        try:
            data = _get_json(
                "/search/movie",
                {"query": query, "language": "en-US", "page": 1},
                ttl=120,
                timeout=5,
            )
            results = (data or {}).get("results", [])
            return [{
                "id": movie.get("id"),
                "title": movie.get("title"),
                "year": movie.get("release_date", "")[:4] if movie.get("release_date") else "",
                "poster": TMDbService.format_poster_url(movie.get("poster_path"))
            } for movie in results[:limit]]
        except Exception as e:
            logger.warning(f"Error in autocomplete search: {e}")
            return []
    
    @staticmethod
    def get_genre_list():
        """Get list of all movie genres from TMDb"""
        try:
            data = _get_json("/genre/movie/list", {"language": "en-US"}, ttl=86400)
            return (data or {}).get("genres", [])
        except Exception as e:
            logger.warning(f"Error fetching genre list: {e}")
            return []

    # ---------------- Keywords / Discovery -----------------
    @staticmethod
    def search_keywords(query):
        """Search TMDb keywords by name. Returns list of {id, name}."""
        try:
            data = _get_json("/search/keyword", {"query": query}, ttl=86400)
            return (data or {}).get("results", [])
        except Exception as e:
            logger.warning(f"Error searching keywords: {e}")
            return []

    @staticmethod
    def discover_by_keywords(keyword_ids, page=1):
        """Discover movies by TMDb keyword ids (list or comma string)."""
        try:
            ids = keyword_ids
            if isinstance(keyword_ids, (list, tuple)):
                ids = ",".join(str(int(k)) for k in keyword_ids if k is not None)
            data = _get_json(
                "/discover/movie",
                {
                    "language": "en-US",
                    "page": page,
                    "sort_by": "popularity.desc",
                    "with_keywords": ids,
                    "include_adult": "false",
                },
                ttl=600,
            )
            return (data or {}).get("results", [])
        except Exception as e:
            logger.warning(f"Error discovering by keywords: {e}")
            return []

    # ---------------- People / Cast -----------------
    @staticmethod
    def search_people(query, page=1):
        """Search for people (actors, directors) by name."""
        try:
            data = _get_json(
                "/search/person",
                {"query": query, "language": "en-US", "page": page},
                ttl=600,
            )
            return (data or {}).get("results", [])
        except Exception as e:
            logger.warning(f"Error searching people: {e}")
            return []

    @staticmethod
    def get_person_details(person_id):
        """Get details (name, biography, profile) for a person."""
        try:
            return _get_json(f"/person/{person_id}", {"language": "en-US"}, ttl=7200)
        except Exception as e:
            logger.warning(f"Error fetching person details: {e}")
            return None

    @staticmethod
    def get_person_movie_credits(person_id):
        """Get combined movie credits for a person (cast + crew)."""
        try:
            return _get_json(f"/person/{person_id}/movie_credits", {"language": "en-US"}, ttl=7200)
        except Exception as e:
            logger.warning(f"Error fetching person credits: {e}")
            return None
