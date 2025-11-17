"""
AI-powered movie recommendation engine using content-based filtering.
Analyzes movie features including genres, keywords, cast, crew, and plot.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from tmdb_service import TMDbService
import os
import importlib
from typing import Optional, Set, List, Dict, Any
try:
    from movielens import load_tags_enrichment, recommend_similar_by_tmdbId, load_similarity_model
    _ML_AVAILABLE = True
except Exception as e:
    # Optional dependency: allow app to run without pandas/scikit stack for CF enrichment
    print(f"MovieLens extras unavailable: {e}")
    _ML_AVAILABLE = False
    def load_tags_enrichment(*args, **kwargs):
        return {}
    def recommend_similar_by_tmdbId(*args, **kwargs):
        return []
    def load_similarity_model(*args, **kwargs):
        return None
import config


class MovieRecommendationEngine:
    """
    Content-based recommendation engine that analyzes movie features
    to find similar movies using cosine similarity.
    """
    
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            max_features=5000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        # Optional: external embeddings model (sentence-transformers)
        self._hf_enabled = getattr(config, 'ENABLE_HF_MODEL', False)
        self._hf_model_name = getattr(config, 'HF_MODEL_NAME', 'sentence-transformers/all-MiniLM-L6-v2')
        self._embedder = None
        self._hf_loaded = False
        # Optional Cross-Encoder reranker
        self._reranker_enabled = getattr(config, 'ENABLE_RERANKER', False)
        self._reranker_model_name = getattr(config, 'RERANKER_MODEL_NAME', 'cross-encoder/ms-marco-MiniLM-L6-v2')
        self._reranker = None
        self._reranker_loaded = False
        # Lazy-loaded Collaborative Filtering (MovieLens) model
        self.cf_model = None
        self.cf_loaded = False
        # Optional MovieLens tags enrichment
        self.ml_tags_map = {}
        ml_path = config.MOVIELENS_PATH
        if _ML_AVAILABLE and ml_path and os.path.isdir(ml_path):
            try:
                self.ml_tags_map = load_tags_enrichment(ml_path, min_tag_freq=5, max_tags_per_movie=20)
                if self.ml_tags_map:
                    print(f"Loaded MovieLens tag enrichment for {len(self.ml_tags_map):,} movies.")
            except Exception as e:
                print(f"Failed to load MovieLens tags enrichment: {e}")

    def _ensure_hf_model(self):
        """Lazily load the Hugging Face sentence-transformers model if enabled.
        Falls back silently if unavailable.
        """
        if not self._hf_enabled or self._hf_loaded:
            return
        self._hf_loaded = True
        try:
            st_module = importlib.import_module('sentence_transformers')
            SentenceTransformer = getattr(st_module, 'SentenceTransformer')
            # Use a lightweight, widely available model by default
            self._embedder = SentenceTransformer(self._hf_model_name)
            print(f"Loaded embeddings model: {self._hf_model_name}")
        except Exception as e:
            # Do not hard fail – fallback to TF-IDF
            print(f"Embeddings model unavailable ({e}); falling back to TF-IDF.")
            self._embedder = None

    def _ensure_reranker(self):
        """Lazily load a cross-encoder reranker if enabled; fallback silently."""
        if not self._reranker_enabled or self._reranker_loaded:
            return
        self._reranker_loaded = True
        try:
            st_module = importlib.import_module('sentence_transformers')
            CrossEncoder = getattr(st_module, 'CrossEncoder')
            self._reranker = CrossEncoder(self._reranker_model_name)
            print(f"Loaded reranker model: {self._reranker_model_name}")
        except Exception as e:
            print(f"Reranker unavailable ({e}); continuing without reranking.")
            self._reranker = None

    def _try_load_cf(self):
        """Attempt to load the CF model once; safe no-op if unavailable."""
        if self.cf_loaded:
            return
        self.cf_loaded = True  # attempt only once per process
        if not _ML_AVAILABLE:
            self.cf_model = None
            return
        try:
            if os.path.exists(config.CF_MODEL_PATH):
                self.cf_model = load_similarity_model(config.CF_MODEL_PATH)
                print("Loaded MovieLens CF model for hybrid recommendations.")
        except Exception as e:
            print(f"Failed to load CF model: {e}")
            self.cf_model = None

    def _cf_neighbors_for_tmdb(self, tmdb_id: int, top_n: int = 25) -> Set[int]:
        """Return a set of TMDb IDs that are CF-neighbors of the given TMDb ID."""
        self._try_load_cf()
        if not self.cf_model:
            return set()
        recs = recommend_similar_by_tmdbId(tmdb_id, self.cf_model, top_n=top_n)
        return set(recs)
    
    def build_movie_profile(self, movie_id):
        """
        Build a comprehensive feature profile for a movie by fetching
        and combining multiple attributes from TMDb.
        
        Returns a dictionary with all movie features.
        """
        # Get basic movie details
        details = TMDbService.get_movie_details(movie_id)
        if not details:
            return None
        
        # Get additional data
        credits = TMDbService.get_movie_credits(movie_id)
        keywords = TMDbService.get_movie_keywords(movie_id)
        
        # Extract genres
        genres = [g['name'] for g in details.get('genres', [])]
        
        # Extract top cast (first 5 actors)
        cast = []
        if credits and 'cast' in credits:
            cast = [actor['name'] for actor in credits['cast'][:5]]
        
        # Extract director and key crew
        director = []
        crew_members = []
        if credits and 'crew' in credits:
            for person in credits['crew']:
                if person['job'] == 'Director':
                    director.append(person['name'])
                elif person['job'] in ['Screenplay', 'Writer', 'Producer']:
                    crew_members.append(person['name'])
        
        # Extract keywords
        keyword_list = [kw['name'] for kw in keywords]

        # Optional: add MovieLens tags if available
        ml_tags = self.ml_tags_map.get(movie_id, [])
        
        # Build comprehensive text profile
        profile = {
            'id': movie_id,
            'title': details.get('title', ''),
            'overview': details.get('overview', ''),
            'genres': genres,
            'cast': cast,
            'director': director,
            'crew': crew_members[:3],  # Top 3 crew members
            'keywords': keyword_list,
            'ml_tags': ml_tags,
            'release_year': details.get('release_date', '')[:4] if details.get('release_date') else '',
            'vote_average': details.get('vote_average', 0),
            'popularity': details.get('popularity', 0)
        }
        
        return profile
    
    def create_feature_string(self, profile):
        """
        Convert movie profile into a weighted feature string for vectorization.
        Features are repeated based on importance for better similarity matching.
        """
        if not profile:
            return ""
        
        features = []
        
        # Genres (high weight - repeat 3x)
        if profile.get('genres'):
            genres_str = ' '.join(profile['genres'])
            features.extend([genres_str] * 3)
        
        # Director (high weight - repeat 3x)
        if profile.get('director'):
            director_str = ' '.join(profile['director'])
            features.extend([director_str] * 3)
        
        # Keywords (high weight - repeat 2x)
        if profile.get('keywords'):
            keywords_str = ' '.join(profile['keywords'])
            features.extend([keywords_str] * 2)

        # MovieLens Tags (medium-high weight - repeat 2x)
        if profile.get('ml_tags'):
            tags_str = ' '.join(profile['ml_tags'])
            features.extend([tags_str] * 2)
        
        # Cast (medium weight - repeat 2x)
        if profile.get('cast'):
            cast_str = ' '.join(profile['cast'])
            features.extend([cast_str] * 2)
        
        # Overview (medium weight - once)
        if profile.get('overview'):
            features.append(profile['overview'])
        
        # Crew (lower weight - once)
        if profile.get('crew'):
            crew_str = ' '.join(profile['crew'])
            features.append(crew_str)
        
        return ' '.join(features)
    
    def get_intelligent_recommendations(self, source_movie_id, num_recommendations=12):
        """
        Get intelligent movie recommendations based on content similarity.
        
        Algorithm:
        1. Build profile for source movie
        2. Get TMDb's similar movies as candidates (multiple pages for better coverage)
        3. Build profiles for all candidates
        4. Calculate cosine similarity using TF-IDF vectors
        5. Filter out low-quality matches
        6. Rank by similarity score with quality boost
        7. Return top N recommendations
        """
        # Build profile for the source movie
        source_profile = self.build_movie_profile(source_movie_id)
        if not source_profile:
            return []
        
        print(f"Building AI recommendations for: {source_profile['title']}")
        
        # Get more candidates from TMDb for better recommendations
        similar_movies_p1 = TMDbService.get_similar_movies(source_movie_id, page=1)
        similar_movies_p2 = TMDbService.get_similar_movies(source_movie_id, page=2)
        popular_movies = TMDbService.get_popular_movies(page=1)
        
        # Combine and deduplicate candidates
        candidate_ids = set()
        
        # Prioritize similar movies (higher weight)
        for movie in similar_movies_p1[:15]:
            candidate_ids.add(movie['id'])
        for movie in similar_movies_p2[:10]:
            candidate_ids.add(movie['id'])
            
        # Add some popular movies for diversity
        for movie in popular_movies[:10]:
            candidate_ids.add(movie['id'])
        
        # Remove source movie from candidates
        candidate_ids.discard(source_movie_id)
        
        # Keyword-based expansion for thematic concepts (robots, aliens, cars, etc.)
        from config import ENABLE_CONCEPT_EXPANSION
        if ENABLE_CONCEPT_EXPANSION:
            try:
                kw_list = TMDbService.get_movie_keywords(source_movie_id) or []  # [{'id','name'},...]
                kw_names = { (kw.get('name') or '').lower() for kw in kw_list }
                kw_ids = [ kw.get('id') for kw in kw_list if isinstance(kw, dict) and kw.get('id') ]

                # Concept groups: broaden candidate pool when these themes appear
                CONCEPTS = {
                    'robots': {'robot', 'robots', 'mecha', 'android', 'cyborg', 'giant robot'},
                    'aliens': {'alien', 'aliens', 'extraterrestrial', 'xenomorph', 'space invasion'},
                    'cars':   {'car', 'cars', 'street racing', 'car race', 'racing', 'drag racing'},
                }
                matched = set()
                for concept, synonyms in CONCEPTS.items():
                    if any(any(syn in name for syn in synonyms) for name in kw_names):
                        matched.add(concept)

                # Use the movie's own keyword IDs as a strong signal
                if kw_ids:
                    disc = TMDbService.discover_by_keywords(kw_ids[:3], page=1) or []
                    for m in disc[:12]:
                        candidate_ids.add(m.get('id'))

                # For matched concepts, query canonical keyword by name and discover
                for concept in matched:
                    results = TMDbService.search_keywords(concept)
                    if results:
                        kid = results[0].get('id')
                        themed = TMDbService.discover_by_keywords([kid], page=1) or []
                        for m in themed[:10]:
                            candidate_ids.add(m.get('id'))
            except Exception as e:
                print(f"Keyword expansion failed: {e}")

        # Build profiles for all candidates
        candidate_profiles = []
        for movie_id in candidate_ids:
            profile = self.build_movie_profile(movie_id)
            if profile:
                candidate_profiles.append(profile)
        
        if not candidate_profiles:
            return []
        
        # Create feature strings
        source_features = self.create_feature_string(source_profile)
        candidate_features = [self.create_feature_string(p) for p in candidate_profiles]
        
        # Calculate similarity using HF embeddings if available, otherwise TF-IDF
        all_features = [source_features] + candidate_features
        try:
            # Try HF embeddings path first (if enabled)
            self._ensure_hf_model()
            use_hf = self._embedder is not None
            if use_hf:
                import numpy as _np
                # Some models expect instructions/prefixes for best performance
                name_l = (self._hf_model_name or '').lower()
                if 'e5' in name_l:
                    prefixed = ['query: ' + source_features] + ['passage: ' + cf for cf in candidate_features]
                elif 'bge' in name_l:
                    instruction = "Represent this sentence for searching relevant passages: "
                    prefixed = [instruction + source_features] + candidate_features
                else:
                    prefixed = all_features
                # Normalize to use dot product as cosine similarity
                embeddings = self._embedder.encode(prefixed, convert_to_numpy=True, normalize_embeddings=True)
                query_vec = embeddings[0:1]
                cand_vecs = embeddings[1:]
                # Cosine similarity since normalized
                similarities = (cand_vecs @ query_vec.T).flatten()
            else:
                tfidf_matrix = self.vectorizer.fit_transform(all_features)
                cand_vecs = tfidf_matrix[1:]
                # Calculate cosine similarity
                similarities = cosine_similarity(tfidf_matrix[0:1], cand_vecs).flatten()
            
            # CF neighbors (for hybrid boost)
            cf_neighbors = self._cf_neighbors_for_tmdb(source_movie_id, top_n=50)

            # Combine profiles with similarity scores
            scored_movies = []
            for i, profile in enumerate(candidate_profiles):
                score = similarities[i]
                
                # Filter out very low similarity scores (below 3%)
                if score < 0.03:
                    continue
                
                # Quality boosting:
                # 1. Boost for higher ratings (up to +0.08 for 8+ rating)
                rating = profile['vote_average']
                rating_boost = (rating / 10) * 0.08 if rating >= 6 else 0
                
                # 2. Small boost for popularity (helps surface well-known movies)
                popularity = profile.get('popularity', 0)
                popularity_boost = min(popularity / 1000, 0.02)  # Max +0.02
                
                # 3. Penalty for very old movies (unless it's a classic with high rating)
                release_year = int(profile.get('release_year', '0') or '0')
                age_penalty = 0
                if release_year > 0 and release_year < 1990 and rating < 7.5:
                    age_penalty = -0.05
                
                # 4. Hybrid CF boost if candidate is a CF neighbor of the source
                cf_boost = 0.0
                if cf_neighbors and profile['id'] in cf_neighbors:
                    cf_boost = 0.05  # modest boost to reinforce consensus

                final_score = score + rating_boost + popularity_boost + age_penalty + cf_boost
                
                scored_movies.append({
                    'profile': profile,
                    'similarity_score': score,
                    'final_score': final_score
                })
            
            # Filter: Keep only movies with meaningful similarity
            scored_movies = [m for m in scored_movies if m['similarity_score'] >= 0.03]
            
            # Sort by final score (base ranking)
            scored_movies.sort(key=lambda x: x['final_score'], reverse=True)

            # Optional: Rerank top-K using a Cross-Encoder
            self._ensure_reranker()
            if self._reranker is not None and scored_movies:
                try:
                    top_k = max(1, int(getattr(config, 'RERANKER_TOP_K', 40)))
                    subset = scored_movies[:top_k]
                    # Build (query, doc) pairs
                    def join_text(p):
                        parts = [p.get('title','')]
                        if p.get('overview'): parts.append(p.get('overview'))
                        if p.get('genres'): parts.append(' '.join(p.get('genres')))
                        if p.get('keywords'): parts.append(' '.join(p.get('keywords')))
                        return ' '.join(parts)[:5120]
                    query_text = join_text(source_profile)
                    pairs = [(query_text, join_text(item['profile'])) for item in subset]
                    scores = self._reranker.predict(pairs)
                    # Attach reranker scores and sort subset
                    for item, s in zip(subset, scores):
                        item['rerank_score'] = float(s)
                    subset.sort(key=lambda x: x.get('rerank_score', 0), reverse=True)
                    # Merge reranked subset back with the rest
                    scored_movies = subset + scored_movies[top_k:]
                except Exception as e:
                    print(f"Rerank failed: {e}")

            # Diversify with simple MMR to avoid near-duplicates
            try:
                from sklearn.metrics.pairwise import cosine_similarity as _cs
                if use_hf:
                    # cand_vecs is a numpy array (normalized), use dot product for pairwise
                    pairwise = cand_vecs @ cand_vecs.T
                else:
                    pairwise = _cs(cand_vecs, cand_vecs)
                # Map profile id to index in candidate_profiles
                id_to_idx = {p['id']: idx for idx, p in enumerate(candidate_profiles)}
                lambda_rel = 0.7
                selected = []  # list of indices into scored_movies
                # Work off scored_movies order but compute MMR each step
                available = list(range(len(scored_movies)))
                while available and len(selected) < num_recommendations:
                    best_i = None
                    best_mmr = -1e9
                    for si in available:
                        prof = scored_movies[si]['profile']
                        idx = id_to_idx.get(prof['id'])
                        if idx is None:
                            rel = scored_movies[si]['final_score']
                            div = 0
                        else:
                            rel = scored_movies[si]['final_score']
                            if not selected:
                                div = 0
                            else:
                                # max similarity to any already selected
                                sel_indices = [id_to_idx.get(scored_movies[j]['profile']['id']) for j in selected if id_to_idx.get(scored_movies[j]['profile']['id']) is not None]
                                div = max((pairwise[idx, s] for s in sel_indices), default=0)
                        mmr = lambda_rel * rel - (1 - lambda_rel) * div
                        if mmr > best_mmr:
                            best_mmr = mmr
                            best_i = si
                    selected.append(best_i)
                    available.remove(best_i)
                final_list = [scored_movies[i] for i in selected]
            except Exception:
                # Fallback to top-N if MMR fails
                final_list = scored_movies[:num_recommendations]

            # Return top N recommendations
            recommendations = []
            for item in final_list[:num_recommendations]:
                profile = item['profile']
                recommendations.append({
                    'id': profile['id'],
                    'title': profile['title'],
                    'similarity_score': round(item['similarity_score'] * 100, 1),
                    'profile': profile
                })
            
            return recommendations
            
        except Exception as e:
            print(f"Error calculating similarities: {e}")
            # Fallback: if CF model is available, use its neighbors
            cf_neighbors = self._cf_neighbors_for_tmdb(source_movie_id, top_n=12)
            if cf_neighbors:
                recs = []
                for tmdb_id in list(cf_neighbors)[:12]:
                    # Build minimal profile for uniform downstream formatting
                    prof = self.build_movie_profile(tmdb_id)
                    if not prof:
                        continue
                    recs.append({
                        'id': prof['id'],
                        'title': prof['title'],
                        'similarity_score': 0.0,
                        'profile': prof
                    })
                return recs
            return []
    
    def get_hybrid_recommendations(self, query, page=1):
        """
        Hybrid approach: Search for movies, then use AI to recommend similar ones.
        
        For each search result, get intelligent recommendations and aggregate them.
        """
        # Search for movies matching query
        search_results = TMDbService.search_movies(query, page)
        
        if not search_results:
            return []
        
        # Get the top search result as the primary movie
        primary_movie = search_results[0]
        
        # Get AI recommendations based on the primary movie
        ai_recommendations = self.get_intelligent_recommendations(
            primary_movie['id'],
            num_recommendations=12
        )
        
        # If AI recommendations worked, use them
        if ai_recommendations:
            print(f"✨ AI found {len(ai_recommendations)} similar movies")
            return ai_recommendations
        
        # Fallback to search results if AI fails
        return search_results[:12]


# Global instance
recommendation_engine = MovieRecommendationEngine()


# Simplified UI-facing helpers (merged from recommender.py to reduce file count)
USE_AI_RECOMMENDATIONS = True


def _format_movie_for_display(movie_data, is_ai_result=False):
    if is_ai_result:
        profile = movie_data.get('profile', {})
        movie_id = movie_data.get('id')
        title = movie_data.get('title')
        similarity_score = movie_data.get('similarity_score', 0)
        overview = profile.get('overview', 'No overview available.')
        release_date = profile.get('release_year', 'N/A')
        rating = profile.get('vote_average', 0)
        details = TMDbService.get_movie_details(movie_id)
        poster_path = details.get('poster_path') if details else None
    else:
        movie_id = movie_data.get('id')
        title = movie_data.get('title', 'Unknown')
        overview = movie_data.get('overview', 'No overview available.')
        release_date = movie_data.get('release_date', 'N/A')
        rating = movie_data.get('vote_average', 0)
        poster_path = movie_data.get('poster_path')
        similarity_score = None

    trailer_url = TMDbService.get_youtube_trailer(movie_id)
    movie_dict = {
        "id": movie_id,
        "title": title,
        "poster": TMDbService.format_poster_url(poster_path),
        "rating": round(rating, 1) if rating else "N/A",
        "release_date": release_date if release_date else "N/A",
        "overview": overview[:200] + "..." if len(overview) > 200 else overview,
        "trailer": trailer_url or ""
    }
    if similarity_score is not None:
        movie_dict["ai_match"] = f"{similarity_score}% match"
    return movie_dict


def _get_franchise_movies(movie_details):
    collection_id = movie_details.get('belongs_to_collection', {}).get('id') if movie_details.get('belongs_to_collection') else None
    if not collection_id:
        return []
    collection_data = TMDbService.get_collection(collection_id)
    if not collection_data:
        return []
    collection_movies = []
    for movie in collection_data.get('parts', []):
        try:
            formatted = _format_movie_for_display(movie, is_ai_result=False)
            formatted['collection_name'] = collection_data.get('name', '')
            collection_movies.append(formatted)
        except Exception:
            continue
    collection_movies.sort(key=lambda x: x.get('release_date', ''))
    return collection_movies


def _build_primary_movie_payload(movie_id: int) -> dict:
    """Assemble a rich detail payload for the primary searched movie."""
    details = TMDbService.get_movie_details(movie_id) or {}
    credits = TMDbService.get_movie_credits(movie_id) or {}
    trailer = TMDbService.get_youtube_trailer(movie_id)
    # Watch providers (link)
    try:
        region = getattr(config, 'DEFAULT_REGION', 'US')
        providers = TMDbService.get_watch_providers(movie_id, region=region) or {}
        watch_link = providers.get('link')
    except Exception:
        watch_link = None

    # Director and writers
    crew = credits.get('crew', [])
    directors = [p.get('name') for p in crew if p.get('job') == 'Director']
    writers = [p.get('name') for p in crew if p.get('job') in ['Writer', 'Screenplay']]

    # Top cast
    cast = []
    for p in (credits.get('cast') or [])[:8]:
        cast.append({
            'id': p.get('id'),
            'name': p.get('name'),
            'character': p.get('character'),
            'profile': TMDbService.format_poster_url(p.get('profile_path')),
        })

    payload = {
        'id': details.get('id', movie_id),
        'title': details.get('title', ''),
        'overview': details.get('overview', ''),
        'release_date': details.get('release_date', ''),
        'rating': details.get('vote_average', 0),
        'runtime': details.get('runtime'),
        'genres': [g.get('name') for g in (details.get('genres') or [])],
        'poster': TMDbService.format_poster_url(details.get('poster_path')),
        'backdrop': TMDbService.format_poster_url(details.get('backdrop_path')),
        'trailer': trailer or '',
        'watch_link': watch_link or '',
        'tagline': details.get('tagline', ''),
        'director': directors[0] if directors else 'Unknown',
        'writers': writers[:3] if writers else [],
    }
    if cast:
        payload['cast'] = cast
    return payload


def _choose_search_anchor(query: str, search_results: list) -> int:
    """Select the most appropriate movie id to represent the user's search intent.

    Strategy:
    1. Prefer a result whose title contains all query tokens (case-insensitive).
    2. Otherwise prefer any result whose collection name (if available) contains the query tokens (so 'Harry Potter').
    3. Fallback to first search result.
    """
    if not search_results:
        return None
    tokens = [t for t in query.lower().split() if t]
    def title_matches(m):
        title = (m.get('title') or '').lower()
        return all(tok in title for tok in tokens)
    # 1. Exact token containment in title
    for m in search_results:
        if title_matches(m):
            return m.get('id')
    # 2. Collection name match
    for m in search_results:
        details = TMDbService.get_movie_details(m.get('id')) or {}
        coll = details.get('belongs_to_collection', {}) or {}
        cname = (coll.get('name') or '').lower()
        if cname and all(tok in cname for tok in tokens):
            return m.get('id')
    # 3. Fallback
    return search_results[0].get('id')


def recommend(query, page=1, use_ai=None):
    use_ai_mode = use_ai if use_ai is not None else USE_AI_RECOMMENDATIONS
    print(f"{'🤖 AI' if use_ai_mode else '🔍 Basic'} search for '{query}' (page {page})")
    movies = []
    collection_movies = []
    primary_payload = None
    if use_ai_mode:
        try:
            ai_results = recommendation_engine.get_hybrid_recommendations(query, page)
            if ai_results:
                for ai_movie in ai_results:
                    try:
                        movie = _format_movie_for_display(ai_movie, is_ai_result=True)
                        movies.append(movie)
                    except Exception as e:
                        print(f"Error formatting AI result: {e}")
                        continue
                if movies:
                    print(f"✨ Returning {len(movies)} AI-recommended movies")
                    # IMPORTANT: Primary hero should reflect the searched movie, not a recommendation
                    # Fetch top search result to anchor the hero and collection (e.g., Harry Potter)
                    search_results = TMDbService.search_movies(query, page) or []
                    if search_results:
                        source_id = _choose_search_anchor(query, search_results)
                        if source_id:
                            source_details = TMDbService.get_movie_details(source_id)
                            if source_details:
                                collection_movies = _get_franchise_movies(source_details)
                                try:
                                    primary_payload = _build_primary_movie_payload(source_id)
                                except Exception as e:
                                    print(f"Failed to build primary movie payload: {e}")
                    return {'movies': movies, 'collection_movies': collection_movies, 'primary_movie': primary_payload}
        except Exception as e:
            print(f"AI recommendation failed: {e}, falling back to basic search")
    results = TMDbService.search_movies(query, page)
    if not results:
        return {'movies': [], 'collection_movies': [], 'primary_movie': None}
    for movie in results[:12]:
        try:
            movie_formatted = _format_movie_for_display(movie, is_ai_result=False)
            movies.append(movie_formatted)
        except Exception as e:
            print(f"Error formatting movie: {e}")
            continue
    if movies:
        first_movie_id = movies[0].get('id')
        first_movie_details = TMDbService.get_movie_details(first_movie_id)
        if first_movie_details:
            collection_movies = _get_franchise_movies(first_movie_details)
            try:
                primary_payload = _build_primary_movie_payload(first_movie_id)
            except Exception as e:
                print(f"Failed to build primary movie payload: {e}")
    return {'movies': movies, 'collection_movies': collection_movies, 'primary_movie': primary_payload}


def get_movie_recommendations_by_id(movie_id, num_recommendations=12):
    try:
        ai_results = recommendation_engine.get_intelligent_recommendations(movie_id, num_recommendations=num_recommendations)
        movies = []
        for ai_movie in ai_results:
            movie = _format_movie_for_display(ai_movie, is_ai_result=True)
            movies.append(movie)
        return movies
    except Exception as e:
        print(f"Error getting recommendations by ID: {e}")
        return []
