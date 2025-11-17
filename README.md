# 🎬 Movie Recommender AI

An intelligent movie recommendation system powered by The Movie Database (TMDb) API and machine learning algorithms. Built with Flask and designed to provide personalized movie suggestions based on user preferences and content analysis.

## 🚀 Current Features

### ✅ Phases 1–4 Complete + Early Hybrid CF!

- **🤖 AI-Powered Recommendations**: Intelligent content-based filtering using machine learning
  - Analyzes movie genres, keywords, cast, directors, and plot
  - Uses TF-IDF vectorization and cosine similarity
  - Smart ranking with quality boosting for highly-rated movies
  - Shows AI match percentage for each recommendation

- **👤 Personalized Learning**: System that learns from your behavior
  - **5-Star Rating System**: Rate movies to build your taste profile
  - **Smart Recommendations**: Get personalized suggestions based on your ratings
  - **Preference Tracking**: Learns your favorite genres, directors, and actors
  - **Watchlist**: Save movies to watch later
  - **User Profile**: See your stats, ratings, and preferences
  - **Behavior Tracking**: Views, clicks, and searches improve recommendations

- **🔍 Smart Search with Autocomplete**: Live suggestions as you type with movie posters
  - Debounced search (300ms) for optimal performance
  - Keyboard navigation (arrow keys + enter)
  - Shows movie title, year, and poster

- **🎬 Franchise Detection**: Automatically shows sequels, prequels, and series
  - Dedicated collection section for franchises
  - Chronologically ordered movies
  - Works for Marvel, Star Wars, Harry Potter, etc.

- **📋 Advanced Filters & Sorting**:
  - Filter by Genre (Action, Comedy, Sci-Fi, etc.)
  - Filter by Decade (2020s, 2010s, 2000s, 1990s, Classics)
  - Filter by Minimum Rating (7+, 8+, 9+)
  - Sort by Rating, Year, Title, or AI Relevance
  - Auto-submit filters for instant results
  - Reset button to clear all filters

- **🎨 Enhanced UI/UX**:
  - **Loading Skeletons**: Beautiful shimmer animations while loading
  - **Movie Detail Modal**: Full-screen popup with comprehensive info
    - Large backdrop image header
    - Complete cast with photos (top 10)
    - Director, writers, runtime, budget, revenue
    - Tagline and full overview
    - Direct trailer and watchlist buttons
  - **Improved Pagination**: Page numbers with first/prev/next navigation
  - **Scroll to Top**: Floating button appears when scrolling
  - **Results Counter**: Shows number of movies displayed
  - **Smooth Animations**: Fade-in, slide-down, lift effects

- **Early Collaborative Filtering (Hybrid)**: Integrates MovieLens item-item similarity as a boost layer
  - Builds sparse item-user matrix from MovieLens ratings
  - Computes cosine item-item neighbors (top-K)
  - Hybrid scoring combines TF-IDF similarity + quality boosts + CF neighbor boost
  - CF-only fallback when content vectorization fails

- **Movie Search**: Search through TMDb's extensive movie database
- **Rich Movie Information**: Display movie posters, ratings, release dates, overviews, and trailers
- **Responsive Design**: Dark-themed UI with golden accents and smooth animations
- **Interactive UI**: Rating stars, watchlist buttons, real-time updates
- **Trailer Links**: Direct links to watch movie trailers on YouTube

### How the AI Works

When you search for a movie like "Interstellar", the AI:
1. **Analyzes the movie's DNA**: Extracts genres, keywords, cast, director, crew, and plot
2. **Finds candidates**: Gets similar movies from TMDb plus popular releases
3. **Builds feature vectors**: Creates mathematical representations using TF-IDF
4. **Calculates similarity**: Uses cosine similarity to measure how "close" movies are
5. **Ranks intelligently**: Boosts high-quality, well-rated movies
6. **Returns top matches**: Shows you the best recommendations with match scores

## 🎯 Planned / Upcoming Enhancements

### Hybrid Recommendation Expansion
- Refine blending weights between content similarity and CF signals
- Introduce user-personal CF (filter by similar users to the current profile)
- Explore matrix factorization (ALS) for latent factors

### Deeper Personalization
- Use watchlist and rating recency decay
- Diversity balancing (novelty vs similarity)
- Explicit preference sliders (e.g., genre weight)

### UI Improvements
- A/B test list vs grid density modes
- Add persistent user history timeline
- Optional infinite scroll toggle

### Data Enrichment & Quality
- Integrate optional external metadata (awards, certifications) respecting API limits
- Fuzzy duplicate handling / normalization

### Performance Optimization
- Cache CF model & genre lists
- Precompute hybrid vectors for popular anchors
- Batch TMDb details lookups
- Optional Redis layer

## 🧩 MovieLens Integration (New)

We now ingest the MovieLens dataset to power collaborative similarity:

1. `movielens_loader.py` downloads and loads `ratings.csv`, `movies.csv`, `links.csv`.
2. `links.csv` provides `tmdbId` so we can map MovieLens movies to TMDb for posters/details.
3. `movielens_cf.py` builds an item-user matrix and computes top-K cosine neighbors.
4. The model is saved to `models/movielens_cf.pkl` and lazily loaded by `ai_recommender.py`.
5. CF neighbors add a modest hybrid boost (+0.05) to content similarity scoring.
6. If the content vectorization step errors, we fall back to CF neighbors only.

Optional content enrichment: If you have MovieLens tags available alongside links.csv, set an environment variable pointing to the dataset folder to enrich content features with top user tags.

```powershell
$env:MOVIELENS_PATH = "C:\Users\VRAJKUMA.PATEL\Downloads\ml-32m\ml-32m"
```

The app will load top tags per movie (frequency ≥ 5, up to 20 per title) and include them in the feature vectorization.

### Dataset Notes
- Source: [MovieLens](https://grouplens.org/datasets/movielens/)
- License: Non-commercial, research/educational use.
- Recommended starting set: `ml-latest-small` for quick builds; upgrade to `ml-latest` for richer signals.

### Building the CF Model (Manual Step)
Quick build (small set):
```bash
python -c "from movielens_loader import download_movielens, load_movielens; from movielens_cf import build_and_save_cf_model; p=download_movielens(); r,m,l=load_movielens(p); build_and_save_cf_model(r,l)"
```

Large local dataset (e.g. ml-32m) with scalable block-wise similarity:
```powershell
python movielens.py build --dataset-path "C:\\path\\to\\ml-32m" --block-size 1000 --min-item-ratings 10 --top-k 75
```

Outputs `models/movielens_cf.pkl`. The app lazily loads it for hybrid boosts.

Performance tips:
1. Increase `min-item-ratings` to prune very sparse items (improves quality + speed).
2. Use `--blockwise` for datasets > 5M ratings.
3. Adjust `--top-k` downward (e.g. 40) to reduce memory footprint.
4. Keep `block-size` in 500–1500 range; higher uses more RAM but fewer passes.

## 🛠️ Tech Stack

- **Backend**: Flask (Python 3.9+)
- **API**: TMDb (The Movie Database)
- **ML Libraries**: NumPy, scikit-learn, pandas, SciPy (CF + content vectorization)
- **Frontend**: HTML5, CSS3, Jinja2 templates
- **Environment Management**: python-dotenv

## 📦 Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd MovieRecommenderAI
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   - Copy `.env.example` to `.env`
   - Get your TMDb API key from [TMDb Settings](https://www.themoviedb.org/settings/api)
   - Add your API key to `.env`:
     ```
     TMDB_API_KEY=your_api_key_here
     ```

4. **Run the application**
   ```bash
   python app.py
   ```

5. **Open your browser**
   Navigate to `http://127.0.0.1:5000`

## 📁 Project Structure

```
MovieRecommenderAI/
├── app.py                 # Flask application and routes
├── recommender.py         # Recommendation logic
├── tmdb_service.py        # TMDb API service wrapper
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (not in git)
├── .env.example          # Environment template
├── .gitignore            # Git ignore rules
├── static/
│   ├── style.css         # Main stylesheet
│   ├── Loader.css        # Loading animations
│   ├── script.js         # Client-side JavaScript
│   └── no_image.svg      # Placeholder for missing posters
└── templates/
    └── index.html        # Main HTML template
```

## 🔑 Environment Variables

- `TMDB_API_KEY`: Your TMDb API key (required)

## 🎓 Development Notes

This project is being developed as part of an IT Web Development diploma program. The goal is to create a production-ready movie recommendation system with modern AI/ML features while learning best practices in:

- Web application development
- API integration and management
- Machine learning implementation
- User experience design
- Code organization and security

## 🤝 Contributing

This is an educational project, but suggestions and improvements are welcome!

## 📝 License

This project uses the TMDb API but is not endorsed or certified by TMDb.

## 🔗 Resources

- [TMDb API Documentation](https://developers.themoviedb.org/3)
- [Flask Documentation](https://flask.palletsprojects.com/)
- [scikit-learn Documentation](https://scikit-learn.org/)

## 🧪 Testing

Run the AI test to see recommendations in action:

```bash
python test_ai.py
```

This will demonstrate the AI finding similar movies for "Interstellar" with match scores.

## 🔧 Configuration

You can toggle between AI and basic search in `ai_recommender.py` by changing `USE_AI_RECOMMENDATIONS` near the bottom.

---

**Status**: ✅ Phase 1 | ✅ Phase 2 | ✅ Phase 3 | 🚧 Phase 4: Enhanced UI (Next)

## 💫 What Makes This Special

1. **Real Machine Learning**: Not just keyword matching - actual AI that understands movies
2. **Personal Learning**: Gets smarter as you rate movies
3. **Hybrid Intelligence**: Combines content-based + user preferences + collaborative similarity
4. **Production Quality**: Session management, persistent storage, error handling
5. **Beautiful UI**: Interactive, responsive, modern design
6. **Complete Features**: Rating, watchlist, profiles - everything you need

## 🎨 Theme Customization Panel

Open the “🎨 Colors” button in the header to customize the site's brand colors:

- Accent (`--accent`): borders, headings, buttons, chips
- Neon (`--neon`): title glow, button hover glow, stars glow

Apply saves to your browser (localStorage) and updates instantly. Reset returns to defaults.

## ❓ Recommendation Explanations ("Why?")

Each recommendation includes a “Why?” button that explains the suggestion using:

- Shared genres
- Cast or director overlap
- Content similarity percentage (from the AI match)
- Personalization boost (if available)

The endpoint `/explain/<movie_id>` returns a reason string and structured fields.

## 👥 Actor Discovery

Switch the search mode to Actor or click any cast avatar to open an actor profile page with biography and filmography. The filmography grid lists roles and integrates with your watchlist actions.

## 🗂 Updated Project Structure (Key Files)

```
├── app.py                 # Routes + /explain endpoint
├── ai_recommender.py      # Hybrid recommender and UI formatting helpers
├── movielens.py           # Unified MovieLens loader + CF model builder
├── templates/
│   ├── index.html         # Hero, collection, recommendations, filters, theme panel
│   └── actor.html         # Actor profile page
├── static/
│   ├── style.css          # Uses CSS variables: --accent and --neon
│   └── script.js          # Theme toggle, color panel, explanation handler
```

## 🔮 Next Enhancements

- Cache TMDb responses (LRU) and tag enrichment lazy-load
- Diversity slider for balancing similarity vs novelty
- Rich "Why?" modal with feature weight breakdown
