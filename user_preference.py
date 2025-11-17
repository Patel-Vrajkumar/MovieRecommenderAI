"""
User preference learning system for personalized movie recommendations.
Combines content-based filtering with user behavior analysis.
"""

import json
from json.decoder import JSONDecodeError
import os
from datetime import datetime
from collections import defaultdict
import numpy as np
from ai_recommender import recommendation_engine


class UserPreferenceEngine:
    """
    Tracks user interactions and builds personalized recommendation profiles.
    Uses collaborative filtering concepts combined with content-based filtering.
    """
    
    def __init__(self, data_dir="user_data"):
        self.data_dir = data_dir
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
    
    def get_user_profile_path(self, user_id):
        """Get file path for user profile"""
        return os.path.join(self.data_dir, f"user_{user_id}.json")
    
    def _empty_profile(self, user_id):
        return {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "ratings": {},  # {movie_id: rating}
            "watchlist": [],  # [movie_id, ...]
            "viewed": [],  # [{movie_id, timestamp}, ...]
            "clicked_trailers": [],  # [{movie_id, timestamp}, ...]
            "searches": [],  # [{query, timestamp}, ...]
            "preferences": {
                "genres": {},  # {genre: score}
                "directors": {},  # {director: score}
                "actors": {},  # {actor: score}
                "keywords": {}  # {keyword: score}
            }
        }

    def load_user_profile(self, user_id):
        """Load user profile from disk or create a fresh one if corrupted or missing.

        Recovers gracefully from JSONDecodeError by backing up the bad file and
        returning a new, empty profile structure.
        """
        profile_path = self.get_user_profile_path(user_id)
        
        if os.path.exists(profile_path):
            try:
                with open(profile_path, 'r') as f:
                    data = json.load(f)
                    # Ensure new keys exist for backward compatibility
                    if 'disliked' not in data:
                        data['disliked'] = []
                    if 'liked' not in data:
                        data['liked'] = []
                    return data
            except JSONDecodeError:
                # Backup the corrupt file and start fresh
                try:
                    corrupt_path = profile_path + ".corrupt"
                    if os.path.exists(corrupt_path):
                        os.remove(corrupt_path)
                    os.replace(profile_path, corrupt_path)
                    print(f"Corrupt user profile detected for {user_id}. Backed up to {corrupt_path} and regenerating.")
                except Exception as e:
                    print(f"Failed to back up corrupt profile {profile_path}: {e}")
                return self._empty_profile(user_id)
            except Exception as e:
                print(f"Failed to load user profile {profile_path}: {e}")
                return self._empty_profile(user_id)
        
        # Create new profile
        return self._empty_profile(user_id)
    
    def save_user_profile(self, user_id, profile):
        """Save user profile to disk atomically to avoid partial writes."""
        profile_path = self.get_user_profile_path(user_id)
        tmp_path = profile_path + ".tmp"
        try:
            with open(tmp_path, 'w') as f:
                json.dump(profile, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, profile_path)
        except Exception as e:
            print(f"Failed to save user profile {profile_path}: {e}")
            # Best-effort cleanup of temp file
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
    
    def track_rating(self, user_id, movie_id, rating, movie_data=None):
        """
        Track user rating for a movie.
        Updates preference profile based on rated movie features.
        """
        profile = self.load_user_profile(user_id)
        profile["ratings"][str(movie_id)] = {
            "rating": rating,
            "timestamp": datetime.now().isoformat()
        }
        
        # Update preferences based on rating
        if movie_data and rating >= 4:  # Only learn from highly-rated movies
            self._update_preferences(profile, movie_data, weight=rating/5.0)
        
        self.save_user_profile(user_id, profile)
        return profile
    
    def track_view(self, user_id, movie_id):
        """Track that user viewed a movie"""
        profile = self.load_user_profile(user_id)
        profile["viewed"].append({
            "movie_id": movie_id,
            "timestamp": datetime.now().isoformat()
        })
        # Keep only last 100 views
        profile["viewed"] = profile["viewed"][-100:]
        self.save_user_profile(user_id, profile)
    
    def track_trailer_click(self, user_id, movie_id):
        """Track that user clicked on a trailer"""
        profile = self.load_user_profile(user_id)
        profile["clicked_trailers"].append({
            "movie_id": movie_id,
            "timestamp": datetime.now().isoformat()
        })
        profile["clicked_trailers"] = profile["clicked_trailers"][-50:]
        self.save_user_profile(user_id, profile)

    def track_not_interested(self, user_id, movie_id):
        profile = self.load_user_profile(user_id)
        if 'disliked' not in profile:
            profile['disliked'] = []
        if movie_id not in profile['disliked']:
            profile['disliked'].append(movie_id)
        self.save_user_profile(user_id, profile)

    def track_more_like(self, user_id, movie_id, movie_data=None):
        profile = self.load_user_profile(user_id)
        if 'liked' not in profile:
            profile['liked'] = []
        if movie_id not in profile['liked']:
            profile['liked'].append(movie_id)
        # Modestly reinforce preferences based on this movie
        if movie_data:
            self._update_preferences(profile, movie_data, weight=0.5)
        self.save_user_profile(user_id, profile)
    
    def track_search(self, user_id, query):
        """Track user search query"""
        profile = self.load_user_profile(user_id)
        profile["searches"].append({
            "query": query,
            "timestamp": datetime.now().isoformat()
        })
        profile["searches"] = profile["searches"][-50:]
        self.save_user_profile(user_id, profile)
    
    def add_to_watchlist(self, user_id, movie_id):
        """Add movie to user's watchlist"""
        profile = self.load_user_profile(user_id)
        if movie_id not in profile["watchlist"]:
            profile["watchlist"].append(movie_id)
        self.save_user_profile(user_id, profile)
        return profile["watchlist"]
    
    def remove_from_watchlist(self, user_id, movie_id):
        """Remove movie from user's watchlist"""
        profile = self.load_user_profile(user_id)
        if movie_id in profile["watchlist"]:
            profile["watchlist"].remove(movie_id)
        self.save_user_profile(user_id, profile)
        return profile["watchlist"]
    
    def _update_preferences(self, profile, movie_data, weight=1.0):
        """
        Update user preference profile based on movie features.
        Higher weight = stronger preference signal.
        """
        prefs = profile["preferences"]
        
        # Update genre preferences
        for genre in movie_data.get("genres", []):
            if isinstance(genre, dict):
                genre = genre.get("name", "")
            if genre:
                prefs["genres"][genre] = round(prefs["genres"].get(genre, 0) + weight, 2)
        
        # Update director preferences
        for director in movie_data.get("director", []):
            if director:
                prefs["directors"][director] = round(prefs["directors"].get(director, 0) + weight, 2)
        
        # Update actor preferences
        for actor in movie_data.get("cast", [])[:5]:  # Top 5 actors
            if isinstance(actor, dict):
                actor = actor.get("name", "")
            if actor:
                prefs["actors"][actor] = round(prefs["actors"].get(actor, 0) + weight * 0.5, 2)
        
        # Update keyword preferences
        for keyword in movie_data.get("keywords", [])[:10]:
            if isinstance(keyword, dict):
                keyword = keyword.get("name", "")
            if keyword:
                prefs["keywords"][keyword] = round(prefs["keywords"].get(keyword, 0) + weight * 0.3, 2)
    
    def get_personalized_recommendations(self, user_id, base_movie_id=None, num_recommendations=12):
        """
        Get personalized recommendations based on user preferences.
        
        Algorithm:
        1. Get base AI recommendations (content-based)
        2. Score each movie based on user preferences
        3. Re-rank with personalization boost
        """
        profile = self.load_user_profile(user_id)
        
        # Get base recommendations
        if base_movie_id:
            base_recs = recommendation_engine.get_intelligent_recommendations(
                base_movie_id,
                num_recommendations=num_recommendations * 2  # Get more to filter
            )
        else:
            # No base movie - recommend based on profile
            base_recs = self._get_profile_based_recommendations(profile, num_recommendations * 2)
        
        if not base_recs:
            return []
        
        # Score and re-rank based on user preferences
        personalized_recs = []
        for rec in base_recs:
            movie_profile = rec.get("profile", {})
            base_score = rec.get("final_score", rec.get("similarity_score", 0))
            
            # Calculate personalization boost
            personalization_score = self._calculate_personalization_score(
                profile["preferences"],
                movie_profile
            )
            
            # Combine scores
            final_score = base_score + personalization_score

            # Apply strong penalty for disliked movies
            disliked = set(profile.get('disliked', []))
            if movie_profile.get('id') in disliked:
                final_score -= 0.5  # push far down
            
            # Skip already rated movies
            if str(movie_profile.get("id")) in profile["ratings"]:
                continue
            
            personalized_recs.append({
                **rec,
                "personalization_score": round(personalization_score * 100, 1),
                "final_score": final_score
            })
        
        # Sort by final score
        personalized_recs.sort(key=lambda x: x["final_score"], reverse=True)
        
        return personalized_recs[:num_recommendations]
    
    def _calculate_personalization_score(self, user_prefs, movie_profile):
        """
        Calculate how well a movie matches user preferences.
        Returns a score between 0.0 and 0.3 (adds up to 30% boost max).
        """
        score = 0.0
        
        # Genre matching (max +0.15)
        genre_score = 0.0
        for genre in movie_profile.get("genres", []):
            if genre in user_prefs["genres"]:
                genre_score += user_prefs["genres"][genre] * 0.03
        score += min(genre_score, 0.15)
        
        # Director matching (max +0.10)
        director_score = 0.0
        for director in movie_profile.get("director", []):
            if director in user_prefs["directors"]:
                director_score += user_prefs["directors"][director] * 0.05
        score += min(director_score, 0.10)
        
        # Actor matching (max +0.05)
        actor_score = 0.0
        for actor in movie_profile.get("cast", [])[:5]:
            if actor in user_prefs["actors"]:
                actor_score += user_prefs["actors"][actor] * 0.01
        score += min(actor_score, 0.05)
        
        return min(score, 0.30)  # Cap at 30% boost
    
    def _get_profile_based_recommendations(self, profile, num_recommendations):
        """
        Get recommendations based purely on user profile (no base movie).
        Looks at user's top genres/directors and finds popular movies.
        """
        from tmdb_service import TMDbService
        
        # Get popular movies as candidates
        candidates = TMDbService.get_popular_movies(page=1)
        
        # Build profiles for candidates
        recommendations = []
        for movie in candidates[:num_recommendations * 2]:
            movie_id = movie.get("id")
            
            # Build basic profile
            movie_profile = {
                "id": movie_id,
                "title": movie.get("title"),
                "genres": [],
                "vote_average": movie.get("vote_average", 0),
                "overview": movie.get("overview", "")
            }
            
            # Calculate score based on preferences
            score = self._calculate_personalization_score(
                profile["preferences"],
                movie_profile
            )
            
            recommendations.append({
                "id": movie_id,
                "title": movie.get("title"),
                "profile": movie_profile,
                "similarity_score": score * 100,
                "final_score": score + (movie.get("vote_average", 0) / 100)
            })
        
        recommendations.sort(key=lambda x: x["final_score"], reverse=True)
        return recommendations[:num_recommendations]
    
    def get_user_stats(self, user_id):
        """Get statistics about user activity"""
        profile = self.load_user_profile(user_id)
        
        return {
            "total_ratings": len(profile["ratings"]),
            "total_watchlist": len(profile["watchlist"]),
            "total_views": len(profile["viewed"]),
            "total_searches": len(profile["searches"]),
            "top_genres": sorted(
                profile["preferences"]["genres"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            "top_directors": sorted(
                profile["preferences"]["directors"].items(),
                key=lambda x: x[1],
                reverse=True
            )[:3],
            "average_rating": np.mean([
                r["rating"] for r in profile["ratings"].values()
            ]) if profile["ratings"] else 0
        }


# Global instance
user_engine = UserPreferenceEngine()
