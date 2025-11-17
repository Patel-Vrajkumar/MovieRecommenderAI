"""
Side-by-side comparison: Basic Search vs AI Recommendations
"""

from tmdb_service import TMDbService
from ai_recommender import recommendation_engine

def compare_search_methods(query):
    """Compare basic search vs AI recommendations"""
    
    print("=" * 80)
    print(f"🔍 COMPARISON: '{query}'")
    print("=" * 80)
    
    # Basic Search
    print("\n📋 BASIC SEARCH (TMDb Native)")
    print("-" * 80)
    
    basic_results = TMDbService.search_movies(query, page=1)
    if basic_results:
        for i, movie in enumerate(basic_results[:5], 1):
            print(f"{i}. {movie.get('title', 'Unknown')}")
            print(f"   Rating: ⭐ {movie.get('vote_average', 0)}/10")
            genres = movie.get('genre_ids', [])
            print(f"   Genre IDs: {genres}")
            print()
    else:
        print("No results found")
    
    # AI Recommendations
    print("\n🤖 AI-POWERED RECOMMENDATIONS")
    print("-" * 80)
    
    if basic_results:
        movie_id = basic_results[0]['id']
        ai_results = recommendation_engine.get_intelligent_recommendations(
            movie_id,
            num_recommendations=5
        )
        
        if ai_results:
            for i, rec in enumerate(ai_results, 1):
                profile = rec['profile']
                print(f"{i}. {rec['title']}")
                print(f"   🎯 AI Match: {rec['similarity_score']}%")
                print(f"   Rating: ⭐ {profile.get('vote_average', 0)}/10")
                print(f"   Genres: {', '.join(profile.get('genres', [])[:3])}")
                
                # Show why it matched
                keywords = profile.get('keywords', [])[:3]
                if keywords:
                    print(f"   Keywords: {', '.join([k['name'] if isinstance(k, dict) else k for k in keywords])}")
                print()
        else:
            print("AI recommendations failed")
    
    print("=" * 80)
    print()

def main():
    """Run comparisons for different movie types"""
    
    print("\n" + "🎬" * 40)
    print("BASIC SEARCH vs AI RECOMMENDATIONS COMPARISON")
    print("🎬" * 40 + "\n")
    
    test_queries = [
        "Inception",
        "The Matrix",
        "Titanic",
        "The Dark Knight"
    ]
    
    for query in test_queries:
        compare_search_methods(query)
        input("Press Enter to continue to next comparison...")
    
    print("\n✨ Comparison complete! Notice how AI finds thematically similar movies,")
    print("while basic search only finds title matches.\n")

if __name__ == "__main__":
    main()
