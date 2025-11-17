"""
Flask web application entrypoint and routes.

Responsibilities:
- Render the main search UI (hero → collection → suggested) and handle filters/sorting.
- Provide JSON APIs for rating, watchlist, movie details, autocomplete, and explainability.
- Maintain a stable per-user ID in session/cookie for personalization.
- Route for actor profiles and a user profile/watchlist pages.

Key routes:
- GET/POST /             → Search and recommendations page
- GET       /explain/<id> → Explanation for a recommendation (shared genres/cast, etc.)
- POST      /rate         → Record a star rating
- POST      /watchlist/*  → Add/remove movies from watchlist
- GET       /movie/<id>   → Full details for modal
- GET       /autocomplete → Movie/actor suggestions for the search box
- GET       /actor/<id>   → Actor page and filmography
- GET       /profile      → User stats and ratings
- GET       /watchlist    → Watchlist grid
"""

from flask import Flask, render_template, request, session, jsonify, redirect, url_for, g, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
import os
from datetime import timedelta
from ai_recommender import recommend, recommendation_engine, _format_movie_for_display, _build_primary_movie_payload
from user_preference import user_engine
from tmdb_service import TMDbService
import secrets
import logging
import time
import uuid

app = Flask(__name__)
# Use stable secret key (prevents session/user_id reset on each app restart)
app.config['SECRET_KEY'] = os.getenv('APP_SECRET_KEY', 'dev-insecure-change-me')
app.permanent_session_lifetime = timedelta(days=365)

# Database configuration (SQLite by default)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize DB and login manager
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: __import__('datetime').datetime.utcnow())

    def set_password(self, password: str):
        from werkzeug.security import generate_password_hash
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        from werkzeug.security import check_password_hash
        return check_password_hash(self.password_hash, password)


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None


# Basic structured-ish logging for requests
logger = logging.getLogger(__name__)
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))


@app.before_request
def _start_timer_and_req_id():
    g._start_time = time.time()
    g.request_id = str(uuid.uuid4())


@app.after_request
def _log_request(response):
    try:
        duration = (time.time() - getattr(g, '_start_time', time.time())) * 1000
        logger.info(
            f"req_id={getattr(g, 'request_id', '-') } method={request.method} path={request.path} status={response.status_code} duration_ms={duration:.1f}"
        )
    except Exception:
        pass
    return response

def get_user_id():
    """Get or create user ID from session"""
    # If authenticated, use DB user id to back preferences & watchlist
    try:
        if current_user.is_authenticated:
            return f"db_{current_user.get_id()}"
    except Exception:
        pass
    if 'user_id' not in session:
        # Try cookie fallback for continuity if session was cleared
        cookie_id = request.cookies.get('user_id')
        if cookie_id:
            session['user_id'] = cookie_id
        else:
            session['user_id'] = secrets.token_hex(8)
    session.permanent = True
    return session['user_id']

@app.after_request
def persist_user_cookie(resp):
    uid = session.get('user_id')
    if uid:
        secure = os.getenv('COOKIE_SECURE', 'false').lower() == 'true'
        resp.set_cookie('user_id', uid, max_age=60*60*24*365, httponly=True, samesite='Lax', secure=secure)
    return resp


# --- Minimal CSRF protection for JSON API endpoints ---
def _ensure_csrf_token():
    tok = session.get('csrf_token')
    if not tok:
        tok = secrets.token_urlsafe(32)
        session['csrf_token'] = tok
    return tok


@app.before_request
def _csrf_protect_api():
    _ensure_csrf_token()
    if request.method == 'POST' and request.path in {"/rate", "/watchlist/add", "/watchlist/remove", "/trailer/click"}:
        header_tok = request.headers.get('X-CSRF-Token')
        if not header_tok or header_tok != session.get('csrf_token'):
            return jsonify({"error": "CSRF token missing or invalid"}), 400


@app.context_processor
def inject_csrf():
    # current_user is provided by Flask-Login
    return {"csrf_token": _ensure_csrf_token(), "current_user": current_user}


@app.errorhandler(404)
def not_found(e):
    return render_template('404.html'), 404


@app.errorhandler(500)
def server_error(e):
    return render_template('500.html'), 500


# -------- Authentication routes --------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        confirm = request.form.get('confirm') or ''
        wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        if not email or not password:
            if wants_json:
                return jsonify({"success": False, "message": "Email and password are required."}), 400
            flash('Email and password are required.')
            return render_template('register.html')
        if password != confirm:
            if wants_json:
                return jsonify({"success": False, "message": "Passwords do not match."}), 400
            flash('Passwords do not match.')
            return render_template('register.html')
        # Basic email format check
        if '@' not in email or '.' not in email:
            if wants_json:
                return jsonify({"success": False, "message": "Please enter a valid email address."}), 400
            flash('Please enter a valid email address.')
            return render_template('register.html')
        # Create user
        existing = User.query.filter_by(email=email).first()
        if existing:
            if wants_json:
                return jsonify({"success": False, "message": "An account with that email already exists."}), 400
            flash('An account with that email already exists.')
            return render_template('register.html')
        try:
            user = User(email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            if wants_json:
                return jsonify({"success": True, "message": "Welcome! Your account has been created."})
            flash('Welcome! Your account has been created.')
            return redirect(url_for('home'))
        except Exception as e:
            db.session.rollback()
            if wants_json:
                return jsonify({"success": False, "message": "Registration failed. Please try again."}), 500
            flash('Registration failed. Please try again.')
            return render_template('register.html')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        password = request.form.get('password') or ''
        wants_json = 'application/json' in (request.headers.get('Accept') or '') or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            if wants_json:
                return jsonify({"success": True, "message": "Logged in successfully."})
            flash('Logged in successfully.')
            next_url = request.args.get('next')
            return redirect(next_url or url_for('home'))
        if wants_json:
            return jsonify({"success": False, "message": "Invalid email or password."}), 401
        flash('Invalid email or password.')
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('home'))


def apply_filters(movies, genre_filter, year_filter, min_rating):
    """Apply filters to movie list"""
    filtered = movies
    
    # Filter by genre (need to fetch genre for each movie)
    if genre_filter != "all":
        filtered_by_genre = []
        for movie in filtered:
            details = TMDbService.get_movie_details(movie.get("id"))
            if details:
                movie_genres = [g["name"] for g in details.get("genres", [])]
                if genre_filter in movie_genres:
                    filtered_by_genre.append(movie)
        filtered = filtered_by_genre
    
    # Filter by year
    if year_filter != "all":
        if year_filter == "2020s":
            filtered = [m for m in filtered if m.get("release_date", "").startswith(("2020", "2021", "2022", "2023", "2024", "2025"))]
        elif year_filter == "2010s":
            filtered = [m for m in filtered if m.get("release_date", "")[0:3] == "201"]
        elif year_filter == "2000s":
            filtered = [m for m in filtered if m.get("release_date", "")[0:3] == "200"]
        elif year_filter == "1990s":
            filtered = [m for m in filtered if m.get("release_date", "")[0:3] == "199"]
        elif year_filter == "classic":
            filtered = [m for m in filtered if m.get("release_date", "") < "1990"]
    
    # Filter by minimum rating
    if min_rating > 0:
        filtered = [m for m in filtered if isinstance(m.get("rating"), (int, float)) and m.get("rating") >= min_rating]
    
    return filtered


def apply_sorting(movies, sort_by):
    """Apply sorting to movie list"""
    if sort_by == "rating_desc":
        return sorted(movies, key=lambda m: float(m.get("rating", 0)) if isinstance(m.get("rating"), (int, float)) else 0, reverse=True)
    elif sort_by == "rating_asc":
        return sorted(movies, key=lambda m: float(m.get("rating", 0)) if isinstance(m.get("rating"), (int, float)) else 0)
    elif sort_by == "year_desc":
        return sorted(movies, key=lambda m: m.get("release_date", ""), reverse=True)
    elif sort_by == "year_asc":
        return sorted(movies, key=lambda m: m.get("release_date", ""))
    elif sort_by == "title":
        return sorted(movies, key=lambda m: m.get("title", ""))
    else:  # relevance (default)
        return movies


@app.route("/", methods=["GET", "POST"])
def home():
    recommended_movies = []
    collection_movies = []
    primary_movie = None
    # Default content (latest/trending) placeholders
    latest_hero = None
    latest_movies = []
    trending_hero = None
    trending_movies = []
    query = ""
    page = 1
    previous_query = ""
    user_id = get_user_id()
    
    # Get filters and sort options from request
    genre_filter = request.form.get("genre_filter", "all") if request.method == "POST" else "all"
    year_filter = request.form.get("year_filter", "all") if request.method == "POST" else "all"
    min_rating = request.form.get("min_rating", "0") if request.method == "POST" else "0"
    sort_by = request.form.get("sort_by", "relevance") if request.method == "POST" else "relevance"
    current_search_type = request.form.get("search_type", "movie") if request.method == "POST" else "movie"

    if request.method == "POST":
        query = request.form.get("movie_title", "").strip()
        search_type = request.form.get("search_type", "movie")
        # Input validation
        if search_type not in {"movie", "actor"}:
            search_type = "movie"
        if len(query) > 100:
            query = query[:100]
        previous_query = request.form.get("previous_query", "")
        
        # Reset to page 1 if it's a new search
        if query != previous_query:
            page = 1
        else:
            try:
                page = max(1, int(request.form.get("page", 1)))
            except Exception:
                page = 1
        
        if query and search_type == "movie":
            # Track search
            user_engine.track_search(user_id, query)
            result = recommend(query, page)
            
            # Handle new return format
            if isinstance(result, dict):
                recommended_movies = result.get('movies', [])
                collection_movies = result.get('collection_movies', [])
                primary_movie = result.get('primary_movie')
                # Store primary movie id for explanation endpoint
                if primary_movie and primary_movie.get('id'):
                    session['last_primary_id'] = primary_movie.get('id')
            else:
                # Backward compatibility
                recommended_movies = result
            
            # Apply filters
            recommended_movies = apply_filters(
                recommended_movies, 
                genre_filter, 
                year_filter, 
                float(min_rating)
            )
            
            # Apply sorting
            recommended_movies = apply_sorting(recommended_movies, sort_by)
            
            # Track views
            for movie in recommended_movies:
                user_engine.track_view(user_id, movie.get("id"))

        elif query and search_type == "actor":
            # Redirect to first matching actor (simple flow); else do people search page later
            people = TMDbService.search_people(query, page=1)
            if people:
                top = people[0]
                return redirect(url_for('actor_page', person_id=top.get('id')))

    # If GET and no query, populate default homepage content (latest + trending)
    if request.method == "GET" and not query:
        try:
            # Prefer a "latest" hero that actually has usable details & an image.
            # TMDb /movie/latest often points to an obscure or incomplete record, so we
            # scan the now playing list for the first movie with a poster and overview.
            now_playing = TMDbService.get_now_playing_movies(page=1) or []
            candidate_hero = None
            for m in now_playing:
                if m.get('poster_path') and (m.get('overview') or '').strip():
                    candidate_hero = m
                    break
            # Fallback to first item even if missing overview (keeps page populated)
            if not candidate_hero and now_playing:
                candidate_hero = now_playing[0]
            if candidate_hero and candidate_hero.get('id'):
                try:
                    latest_hero = _build_primary_movie_payload(candidate_hero.get('id'))
                    # Ensure hero has a poster; if not, try next candidate with poster
                    if latest_hero and (not latest_hero.get('poster') or 'no_image' in latest_hero.get('poster','')):
                        for m in now_playing:
                            if m is candidate_hero:
                                continue
                            if m.get('poster_path'):
                                latest_hero = _build_primary_movie_payload(m.get('id'))
                                break
                except Exception:
                    latest_hero = None
            # Build latest movies list (exclude hero id) limit 12
            hero_id = latest_hero.get('id') if latest_hero else None
            for m in now_playing:
                if hero_id and m.get('id') == hero_id:
                    continue
                try:
                    formatted = _format_movie_for_display(m, is_ai_result=False)
                    latest_movies.append(formatted)
                    if len(latest_movies) >= 12:
                        break
                except Exception:
                    continue
            # Trending section
            t_list = TMDbService.get_trending_movies('day') or []
            if t_list:
                trending_hero = _build_primary_movie_payload(t_list[0].get('id'))
                for m in t_list[1:13]:
                    try:
                        formatted = _format_movie_for_display(m, is_ai_result=False)
                        trending_movies.append(formatted)
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Failed to build default homepage content: {e}")

    # Get user stats for display
    user_stats = user_engine.get_user_stats(user_id)
    profile = user_engine.load_user_profile(user_id)
    
    # Get genre list for filter dropdown
    genres = TMDbService.get_genre_list()
    if query and not genres:
        try:
            flash("Some information couldn't load from TMDb. Showing partial results.")
        except Exception:
            pass
    
    return render_template(
        "index.html",
        recommended_movies=recommended_movies,
        collection_movies=collection_movies,
        primary_movie=primary_movie,
        query=query,
        page=page,
        user_stats=user_stats,
        watchlist=profile.get("watchlist", []),
        genres=genres,
        current_genre=genre_filter,
        current_year=year_filter,
        current_rating=min_rating,
        current_sort=sort_by,
        current_search_type=current_search_type,
        latest_hero=latest_hero,
        latest_movies=latest_movies,
        trending_hero=trending_hero,
        trending_movies=trending_movies
    )


@app.route("/explain/<int:movie_id>", methods=["GET"])
def explain_recommendation(movie_id: int):
    """Return an explanation for why a recommended movie appeared.

    Uses data stored on the recommendation card plus fresh TMDb lookups.
    Relies on session['last_primary_id'] for the context (source movie).
    """
    source_id = session.get('last_primary_id')
    if not source_id:
        return jsonify({"error": "No source movie in session"}), 400
    try:
        source = TMDbService.get_movie_details(source_id) or {}
        target = TMDbService.get_movie_details(movie_id) or {}
        if not target:
            return jsonify({"error": "Target movie not found"}), 404
        # Shared genres
        source_genres = {g.get('name') for g in source.get('genres', [])}
        target_genres = {g.get('name') for g in target.get('genres', [])}
        shared_genres = sorted(source_genres.intersection(target_genres))
        # Simple cast overlap (top 10 names)
        source_credits = TMDbService.get_movie_credits(source_id) or {}
        target_credits = TMDbService.get_movie_credits(movie_id) or {}
        source_cast = {c.get('name') for c in (source_credits.get('cast') or [])[:10] if c.get('name')}
        target_cast = {c.get('name') for c in (target_credits.get('cast') or [])[:10] if c.get('name')}
        shared_cast = sorted(source_cast.intersection(target_cast))
        # Director overlap
        def directors(credits):
            return {p.get('name') for p in (credits.get('crew') or []) if p.get('job') == 'Director'}
        shared_director = sorted(directors(source_credits).intersection(directors(target_credits)))
        # Bring back similarity string if present via client (optionally parse)
        # Client can pass ?ai_match=82%25%20match etc.
        ai_match_raw = request.args.get('ai_match')
        ai_match_pct = None
        if ai_match_raw:
            try:
                ai_match_pct = float(ai_match_raw.split('%')[0])
            except Exception:
                ai_match_pct = None
        personalization_raw = request.args.get('personalization')  # expects number like '12'
        personalization_pct = None
        if personalization_raw:
            try:
                personalization_pct = float(personalization_raw)
            except Exception:
                personalization_pct = None
        reason_parts = []
        if shared_genres:
            reason_parts.append(f"Shared genres: {', '.join(shared_genres)}")
        if shared_director:
            reason_parts.append(f"Same director: {', '.join(shared_director)}")
        if shared_cast:
            reason_parts.append(f"Cast overlap: {', '.join(shared_cast[:4])}{'...' if len(shared_cast) > 4 else ''}")
        if ai_match_pct is not None:
            reason_parts.append(f"Content similarity score ≈ {ai_match_pct}%")
        if personalization_pct is not None:
            reason_parts.append(f"Personalization boost +{personalization_pct}%")
        if not reason_parts:
            reason_parts.append("Recommended via hybrid similarity and popularity signals.")
        return jsonify({
            "source_id": source_id,
            "target_id": movie_id,
            "shared_genres": shared_genres,
            "shared_cast": shared_cast,
            "shared_director": shared_director,
            "content_similarity_pct": ai_match_pct,
            "personalization_pct": personalization_pct,
            "reason": " | ".join(reason_parts)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/rate", methods=["POST"])
def rate_movie():
    """Rate a movie"""
    user_id = get_user_id()
    movie_id = request.form.get("movie_id")
    rating = int(request.form.get("rating"))
    
    # Get movie details to update preferences
    movie_details = TMDbService.get_movie_details(movie_id)
    
    # Track rating
    user_engine.track_rating(user_id, movie_id, rating, movie_details)
    
    return jsonify({"success": True, "rating": rating})


@app.route("/watchlist/add", methods=["POST"])
def add_to_watchlist():
    """Add movie to watchlist"""
    user_id = get_user_id()
    movie_id = int(request.form.get("movie_id"))
    slot = request.form.get("slot")
    
    watchlist = user_engine.add_to_watchlist(user_id, movie_id)
    logger.info(f"event=watchlist_add user={user_id} movie={movie_id} slot={slot} req_id={getattr(g,'request_id','-')}")
    
    return jsonify({"success": True, "watchlist": watchlist})


@app.route("/watchlist/remove", methods=["POST"])
def remove_from_watchlist():
    """Remove movie from watchlist"""
    user_id = get_user_id()
    movie_id = int(request.form.get("movie_id"))
    slot = request.form.get("slot")
    
    watchlist = user_engine.remove_from_watchlist(user_id, movie_id)
    logger.info(f"event=watchlist_remove user={user_id} movie={movie_id} slot={slot} req_id={getattr(g,'request_id','-')}")
    
    return jsonify({"success": True, "watchlist": watchlist})


@app.route("/watchlist")
def view_watchlist():
    """View user's watchlist"""
    user_id = get_user_id()
    profile = user_engine.load_user_profile(user_id)
    
    # Get movie details for watchlist items
    watchlist_movies = []
    for movie_id in profile.get("watchlist", []):
        movie = TMDbService.get_movie_details(movie_id)
        if movie:
            trailer_url = TMDbService.get_youtube_trailer(movie_id)
            watchlist_movies.append({
                "id": movie_id,
                "title": movie.get("title"),
                "poster": TMDbService.format_poster_url(movie.get("poster_path")),
                "rating": round(movie.get("vote_average", 0), 1),
                "release_date": movie.get("release_date", "N/A"),
                "overview": movie.get("overview", "")[:200] + "...",
                "trailer": trailer_url or ""
            })
    
    user_stats = user_engine.get_user_stats(user_id)
    
    return render_template(
        "watchlist.html",
        watchlist_movies=watchlist_movies,
        user_stats=user_stats
    )


@app.route("/actor/<int:person_id>")
def actor_page(person_id: int):
    """Show actor profile and filmography."""
    # Fetch person details and credits
    details = TMDbService.get_person_details(person_id)
    credits = TMDbService.get_person_movie_credits(person_id) or {}

    if not details:
        return render_template("index.html", recommended_movies=[], collection_movies=[], query="", page=1)

    # Build filmography from cast credits (acting roles)
    cast_credits = credits.get("cast", [])
    movies = []
    for m in cast_credits:
        try:
            movies.append({
                "id": m.get("id"),
                "title": m.get("title"),
                "poster": TMDbService.format_poster_url(m.get("poster_path")),
                "rating": round(m.get("vote_average", 0), 1),
                "release_date": m.get("release_date", ""),
                "overview": (m.get("overview") or "")[:200] + ("..." if (m.get("overview") and len(m.get("overview")) > 200) else ""),
                "character": m.get("character", ""),
            })
        except Exception:
            continue

    # Sort by popularity or release date (desc)
    movies.sort(key=lambda x: (x.get("release_date", "")), reverse=True)

    actor = {
        "id": details.get("id"),
        "name": details.get("name"),
        "profile": TMDbService.format_poster_url(details.get("profile_path")),
        "biography": details.get("biography", ""),
        "known_for_department": details.get("known_for_department", ""),
        "birthday": details.get("birthday", ""),
        "place_of_birth": details.get("place_of_birth", ""),
    }

    # Reuse watchlist for button labels
    user_id = get_user_id()
    profile = user_engine.load_user_profile(user_id)

    return render_template(
        "actor.html",
        actor=actor,
        movies=movies,
        watchlist=profile.get("watchlist", []),
        user_stats=user_engine.get_user_stats(user_id),
    )


@app.route("/profile")
def user_profile():
    """View user profile and stats"""
    user_id = get_user_id()
    profile = user_engine.load_user_profile(user_id)
    stats = user_engine.get_user_stats(user_id)
    
    # Get rated movies with details
    rated_movies = []
    for movie_id, rating_data in profile.get("ratings", {}).items():
        movie = TMDbService.get_movie_details(int(movie_id))
        if movie:
            rated_movies.append({
                "id": movie_id,
                "title": movie.get("title"),
                "poster": TMDbService.format_poster_url(movie.get("poster_path")),
                "rating": rating_data.get("rating"),
                "user_rating": rating_data.get("rating"),
                "tmdb_rating": round(movie.get("vote_average", 0), 1)
            })
    
    return render_template(
        "profile.html",
        stats=stats,
        rated_movies=rated_movies,
        profile=profile
    )


@app.route("/trailer/click", methods=["POST"])
def track_trailer_click():
    """Track trailer click"""
    user_id = get_user_id()
    movie_id = int(request.form.get("movie_id"))
    slot = request.form.get("slot")
    
    user_engine.track_trailer_click(user_id, movie_id)
    logger.info(f"event=trailer_click user={user_id} movie={movie_id} slot={slot} req_id={getattr(g,'request_id','-')}")
    
    return jsonify({"success": True})


@app.route("/random")
def random_movie():
    """Pick a random popular/trending movie and show a single hero with full details."""
    import random
    user_id = get_user_id()
    # Pool: popular + trending day page 1
    pool = []
    try:
        pop = TMDbService.get_popular_movies(page=1) or []
        trend = TMDbService.get_trending_movies('day') or []
        pool = pop[:20] + trend[:20]
    except Exception:
        pool = []
    if not pool:
        return redirect(url_for('home'))
    anchor = random.choice(pool)
    movie_id = anchor.get('id')
    primary_movie = None
    recommended_movies = []  # Intentionally empty for single random view
    collection_movies = []   # Suppress franchise list for simplicity
    if movie_id:
        try:
            # Build hero payload
            primary_movie = _build_primary_movie_payload(movie_id)
            # Inject extended details (budget/revenue) if available
            details_full = TMDbService.get_movie_details(movie_id) or {}
            if primary_movie is not None:
                primary_movie['budget'] = details_full.get('budget')
                primary_movie['revenue'] = details_full.get('revenue')
                # Keywords list (names only) for richness
                try:
                    kw = TMDbService.get_movie_keywords(movie_id) or []
                    primary_movie['keywords'] = [k.get('name') for k in kw if isinstance(k, dict) and k.get('name')]
                except Exception:
                    primary_movie['keywords'] = []
        except Exception:
            primary_movie = None
    profile = user_engine.load_user_profile(user_id)
    user_stats = user_engine.get_user_stats(user_id)
    genres = TMDbService.get_genre_list()
    return render_template(
        'index.html',
        recommended_movies=recommended_movies,
        collection_movies=collection_movies,
        primary_movie=primary_movie,
        query='',
        page=1,
        user_stats=user_stats,
        watchlist=profile.get('watchlist', []),
        genres=genres,
        current_genre='all',
        current_year='all',
        current_rating='0',
        current_sort='relevance',
        current_search_type='movie',
        latest_hero=None,
        latest_movies=[],
        trending_hero=None,
        trending_movies=[],
        random_mode=True
    )


@app.route("/feedback/not_interested", methods=["POST"])
def feedback_not_interested():
    user_id = get_user_id()
    try:
        movie_id = int(request.form.get("movie_id"))
    except Exception:
        return jsonify({"success": False, "error": "Invalid movie_id"}), 400
    user_engine.track_not_interested(user_id, movie_id)
    logger.info(f"event=not_interested user={user_id} movie={movie_id} req_id={getattr(g,'request_id','-')}")
    return jsonify({"success": True})


@app.route("/feedback/more_like", methods=["POST"])
def feedback_more_like():
    user_id = get_user_id()
    try:
        movie_id = int(request.form.get("movie_id"))
    except Exception:
        return jsonify({"success": False, "error": "Invalid movie_id"}), 400
    # Enrich preferences using movie features
    movie_details = TMDbService.get_movie_details(movie_id) or {}
    credits = TMDbService.get_movie_credits(movie_id) or {}
    enriched = {
        "genres": movie_details.get("genres", []),
        "director": [p.get('name') for p in (credits.get('crew') or []) if p.get('job') == 'Director'],
        "cast": [p.get('name') for p in (credits.get('cast') or [])[:5]],
        "keywords": TMDbService.get_movie_keywords(movie_id) or []
    }
    user_engine.track_more_like(user_id, movie_id, movie_data=enriched)
    logger.info(f"event=more_like user={user_id} movie={movie_id} req_id={getattr(g,'request_id','-')}")
    return jsonify({"success": True})


@app.route("/autocomplete", methods=["GET"])
def autocomplete():
    """Autocomplete search endpoint"""
    query = request.args.get("q", "").strip()
    search_type = request.args.get("type", "movie")
    
    if not query or len(query) < 2:
        return jsonify([])
    if search_type == "actor":
        people = TMDbService.search_people(query, page=1) or []
        result = []
        for p in people[:7]:
            result.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "profile": TMDbService.format_poster_url(p.get("profile_path")),
                "known_for_department": p.get("known_for_department", ""),
                "type": "person",
            })
        return jsonify(result)
    else:
        suggestions = TMDbService.autocomplete_search(query, limit=7) or []
        # annotate type so client can branch
        for s in suggestions:
            s["type"] = "movie"
        return jsonify(suggestions)


@app.route("/movie/<int:movie_id>", methods=["GET"])
def get_movie_details(movie_id):
    """Get full movie details including cast, crew, and reviews"""
    try:
        # Get basic details
        details = TMDbService.get_movie_details(movie_id)
        if not details:
            return jsonify({"error": "Movie not found"}), 404
        
        # Get credits (cast and crew)
        credits = TMDbService.get_movie_credits(movie_id)
        
        # Get trailer
        trailer = TMDbService.get_youtube_trailer(movie_id)
        
        # Watch providers
        try:
            from config import DEFAULT_REGION
            providers = TMDbService.get_watch_providers(movie_id, region=DEFAULT_REGION)
        except Exception:
            providers = {}

        # Format response
        response = {
            "id": details.get("id"),
            "title": details.get("title"),
            "overview": details.get("overview"),
            "release_date": details.get("release_date"),
            "rating": details.get("vote_average"),
            "runtime": details.get("runtime"),
            "genres": [g["name"] for g in details.get("genres", [])],
            "poster": TMDbService.format_poster_url(details.get("poster_path")),
            "backdrop": TMDbService.format_poster_url(details.get("backdrop_path")),
            "trailer": trailer,
            "watch_link": providers.get("link") if isinstance(providers, dict) else None,
            "tagline": details.get("tagline", ""),
            "budget": details.get("budget", 0),
            "revenue": details.get("revenue", 0),
        }
        
        # Add cast (top 10)
        if credits:
            response["cast"] = [
                {
                    "name": person.get("name"),
                    "character": person.get("character"),
                    "profile": TMDbService.format_poster_url(person.get("profile_path"))
                }
                for person in credits.get("cast", [])[:10]
                                ]
            
            # Add director and key crew
            crew = credits.get("crew", [])
            directors = [p["name"] for p in crew if p.get("job") == "Director"]
            writers = [p["name"] for p in crew if p.get("job") in ["Writer", "Screenplay"]]
            
            response["director"] = directors[0] if directors else "Unknown"
            response["writers"] = writers[:3] if writers else []
        
        return jsonify(response)
    
    except Exception as e:
        print(f"Error fetching movie details: {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # Ensure database tables exist
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print(f"DB init failed: {e}")
    app.run(debug=True)
