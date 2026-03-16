# 🎬 Movie Recommender AI

A smart movie recommendation app powered by AI and the TMDb API. Search for any movie and get personalized recommendations based on genres, cast, directors, and more.

## ✨ Features

- **AI-Powered Recommendations** — Content-based filtering with TF-IDF and cosine similarity
- **5-Star Rating System** — Rate movies to get better personalized suggestions
- **Smart Search with Autocomplete** — Live results with posters as you type
- **Franchise Detection** — Automatically shows sequels and series (Marvel, Harry Potter, etc.)
- **Watchlist** — Save movies to watch later
- **Advanced Filters** — Filter by genre, decade, and rating; sort by relevance, year, or title
- **Actor Discovery** — Browse actor profiles and filmographies
- **Beautiful Dark UI** — Responsive design with smooth animations and a theme customizer

## 🛠️ Tech Stack

- **Backend**: Python 3.9+, Flask
- **API**: [TMDb (The Movie Database)](https://www.themoviedb.org/)
- **ML**: scikit-learn, NumPy, pandas, SciPy
- **Frontend**: HTML5, CSS3, Jinja2

## 🚀 How to Run

1. **Download the project**
   - Click the green **Code** button on GitHub and select **Download ZIP**, then extract it
   - Or clone it: `git clone https://github.com/Patel-Vrajkumar/MovieRecommenderAI.git`

2. **Open in Visual Studio Code**
   - Open VS Code, go to **File → Open Folder**, and select the project folder

3. **Install dependencies**
   - Open the VS Code terminal (**Terminal → New Terminal**) and run:
     ```bash
     pip install -r requirements.txt
     ```

4. **Set up your API key**
   - Copy `.env.example` to a new file named `.env`
   - Get a free API key from [TMDb Settings](https://www.themoviedb.org/settings/api)
   - Add your key to `.env`:
     ```
     TMDB_API_KEY=your_api_key_here
     ```

5. **Run the app**
   - In the VS Code terminal, open `app.py` and run:
     ```bash
     python app.py
     ```

6. **Open in your browser**
   - Go to: `http://127.0.0.1:5000`

> ⚠️ **Note:** The project's built-in API key is expired. You can get your own free key from [TMDb](https://www.themoviedb.org/settings/api) (see step 4), or contact the developer and they can set it up for you upon request.

## 📁 Project Structure

```
MovieRecommenderAI/
├── app.py              # Main Flask app and routes
├── ai_recommender.py   # AI recommendation engine
├── tmdb_service.py     # TMDb API wrapper
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── static/             # CSS, JS, and image assets
└── templates/          # HTML templates
```

## 📝 Notes

- This project is built as part of an IT Web Development diploma program.
- Uses the TMDb API but is not endorsed or certified by TMDb.
- MovieLens dataset integration is available for collaborative filtering — see the developer for setup details.
