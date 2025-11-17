"""
Test user preference learning system
"""

from user_preference import user_engine
from tmdb_service import TMDbService

def test_user_preferences():
    """Test the user preference system"""
    
    print("=" * 60)
    print("👤 Testing User Preference Learning System")
    print("=" * 60)
    
    test_user = "test_user_001"
    
    # Test 1: Create user profile
    print("\n1. Creating user profile...")
    profile = user_engine.load_user_profile(test_user)
    print(f"✅ Profile created for user: {test_user}")
    
    # Test 2: Rate some movies
    print("\n2. Rating movies...")
    movies_to_rate = [
        ("Interstellar", 5),
        ("The Dark Knight", 5),
        ("Inception", 5),
        ("The Matrix", 4),
        ("Blade Runner", 4)
    ]
    
    for movie_name, rating in movies_to_rate:
        results = TMDbService.search_movies(movie_name, page=1)
        if results:
            movie = results[0]
            movie_id = movie['id']
            movie_details = TMDbService.get_movie_details(movie_id)
            
            user_engine.track_rating(test_user, movie_id, rating, movie_details)
            print(f"   ⭐ Rated '{movie_name}': {rating}/5")
    
    # Test 3: Add to watchlist
    print("\n3. Building watchlist...")
    watchlist_movies = ["Dune", "The Prestige", "Tenet"]
    
    for movie_name in watchlist_movies:
        results = TMDbService.search_movies(movie_name, page=1)
        if results:
            movie_id = results[0]['id']
            user_engine.add_to_watchlist(test_user, movie_id)
            print(f"   📋 Added '{movie_name}' to watchlist")
    
    # Test 4: Get user stats
    print("\n4. User Statistics:")
    print("-" * 60)
    stats = user_engine.get_user_stats(test_user)
    
    print(f"   Total Ratings: {stats['total_ratings']}")
    print(f"   Watchlist Size: {stats['total_watchlist']}")
    print(f"   Average Rating: {stats['average_rating']:.1f}/5")
    
    print(f"\n   Top Genres:")
    for genre, score in stats['top_genres']:
        print(f"      • {genre}: {score:.1f} points")
    
    print(f"\n   Top Directors:")
    for director, score in stats['top_directors']:
        print(f"      • {director}: {score:.1f} points")
    
    # Test 5: Get personalized recommendations
    print("\n5. Getting personalized recommendations...")
    print("-" * 60)
    
    # Based on Interstellar
    results = TMDbService.search_movies("Interstellar", page=1)
    if results:
        interstellar_id = results[0]['id']
        
        recs = user_engine.get_personalized_recommendations(
            test_user,
            base_movie_id=interstellar_id,
            num_recommendations=5
        )
        
        if recs:
            print(f"\n   Personalized recommendations based on your preferences:")
            for i, rec in enumerate(recs, 1):
                title = rec['title']
                ai_score = rec.get('similarity_score', 0)
                personal_score = rec.get('personalization_score', 0)
                
                print(f"\n   {i}. {title}")
                print(f"      AI Match: {ai_score}%")
                if personal_score:
                    print(f"      Personal Boost: +{personal_score}%")
                print(f"      Final Score: {rec['final_score']:.3f}")
    
    print("\n" + "=" * 60)
    print("✨ User Preference System Test Complete!")
    print("=" * 60)
    print(f"\nUser data saved to: user_data/user_{test_user}.json")
    print("\n💡 Try searching for movies in the web app and rate them!")
    print("   Your preferences will improve recommendations over time.\n")

if __name__ == "__main__":
    test_user_preferences()
