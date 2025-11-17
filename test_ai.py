"""
Test script for the AI recommendation engine
"""

from ai_recommender import recommendation_engine
from tmdb_service import TMDbService

def test_ai_recommendations():
    """Test the AI recommendation engine with a sample movie"""
    
    print("=" * 60)
    print("🤖 Testing AI Movie Recommendation Engine")
    print("=" * 60)
    
    # Test 1: Search for a movie
    test_query = "Interstellar"
    print(f"\n1. Searching for: '{test_query}'")
    
    search_results = TMDbService.search_movies(test_query, page=1)
    if not search_results:
        print("❌ No search results found")
        return
    
    movie = search_results[0]
    movie_id = movie['id']
    movie_title = movie['title']
    
    print(f"✅ Found: {movie_title} (ID: {movie_id})")
    
    # Test 2: Get AI recommendations
    print(f"\n2. Getting AI recommendations for: {movie_title}")
    print("   (This may take a moment as we analyze movie features...)\n")
    
    recommendations = recommendation_engine.get_intelligent_recommendations(
        movie_id,
        num_recommendations=10
    )
    
    if not recommendations:
        print("❌ No recommendations generated")
        return
    
    print(f"✅ Generated {len(recommendations)} AI-powered recommendations:\n")
    
    # Display recommendations
    for i, rec in enumerate(recommendations, 1):
        title = rec['title']
        score = rec['similarity_score']
        profile = rec['profile']
        genres = ', '.join(profile.get('genres', [])[:3])
        
        print(f"{i:2d}. {title}")
        print(f"    Match Score: {score}%")
        print(f"    Genres: {genres}")
        print(f"    Rating: ⭐ {profile.get('vote_average', 0)}/10")
        print()
    
    print("=" * 60)
    print("✨ AI Recommendation Engine Test Complete!")
    print("=" * 60)

if __name__ == "__main__":
    test_ai_recommendations()
