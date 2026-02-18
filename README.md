# Spotify Dashboard Demo

A Python automation pipeline that pulls data from Spotify's API, processes it with AI (Google Gemini), and exports to Google Sheets for Looker Studio dashboards. Runs as a daemon with scheduled refresh cycles.

## Architecture

```
Spotify API → Python Watchdog → Gemini AI Processing → Google Sheets → Looker Studio
```

### What It Does

- **Fetches** your Spotify library data (saved tracks, recently played, playlists)
- **Analyzes** listening patterns with Gemini 2.0 Flash (genre classification, mood analysis, song recommendations, taste profiling)
- **Exports** to 11 Google Sheets tabs optimized for Looker Studio dashboards
- **Tracks history** with 7-day retention and change detection (only appends when data changes)
- **Runs autonomously** via watchdog daemon with configurable schedules

### Data Flow

| Schedule | What Runs | Output |
|----------|-----------|--------|
| Every 1 min | Playback check | Recently Played + History_Playback |
| 6am / 6pm | Full refresh | All 11 sheets + AI analysis |

### Google Sheets Tabs (11 total)

| Tab | Contents |
|-----|----------|
| Summary | Track count, duration, unique artists |
| Top Artists | Ranked artist leaderboard |
| Monthly Trends | Songs added per month |
| Recent Tracks | Latest additions to library |
| Recently Played | Last 40 played tracks (Chicago time) |
| AI Suggestions | Gemini-generated song recommendations |
| Genre_Analysis | AI-classified genre breakdown with visual bars |
| Weekly_Favorite | Most-played track + mood/taste analysis |
| Favorite_Recommendations | Songs similar to your weekly favorite |
| Top_Songs | Top 3 most-played with "Why You Love It" AI analysis |
| Your_Playlist | AI-curated 5-track playlist based on top songs |
| History_Summary | Append-only snapshots (7-day retention) |
| History_Playback | Every play logged with dedup (7-day retention) |

## Setup

### Prerequisites

- Python 3.10+
- Spotify Developer account ([developer.spotify.com](https://developer.spotify.com))
- Google Cloud service account with Sheets API enabled
- Google Gemini API key ([aistudio.google.com](https://aistudio.google.com))

### 1. Clone and Install

```bash
git clone https://github.com/Stavion-Colquitt/Data_Pipeline.git
cd Data_Pipeline
pip install spotipy gspread oauth2client google-generativeai pytz --break-system-packages
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Spotify (from developer.spotify.com)
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8888/callback

# Google Sheets
GOOGLE_SHEETS_CREDS_FILE=path/to/service-account.json
SPREADSHEET_NAME=Spotify Dashboard

# Gemini AI
GEMINI_API_KEY=your_gemini_api_key
```

### 3. Spotify Auth (First Run)

```bash
python spotify_client.py
```

This opens a browser for OAuth. After authorizing, a `.cache` file stores your token for future runs.

### 4. Test Without APIs

```bash
# Uses sample_data.json, exports to CSV (no credentials needed)
bash test_local.sh
```

### 5. Run the Dashboard

```bash
# Single run (fetch + process + export)
python watchdog.py --once

# Daemon mode (runs on schedule)
python watchdog.py
```

## File Structure

```
├── config.py              # Environment variable loading
├── spotify_client.py      # Spotify API client (saved tracks, recently played, playlists)
├── ai_processor.py        # Gemini 2.0 Flash integration (8 AI functions)
├── sheets_exporter.py     # Google Sheets export + history tracking + CSV fallback
├── watchdog.py            # Orchestration daemon (scheduling, modes, error handling)
├── sample_data.json       # 150 generic tracks for testing without Spotify API
├── test_local.sh          # Quick test script (sample data → CSV)
├── .env.example           # Environment variable template
└── .gitignore             # Excludes credentials, caches, output files
```

## AI Functions (Gemini 2.0 Flash)

| Function | What It Does |
|----------|-------------|
| `process_spotify_data()` | Aggregates library stats (track count, duration, artists) |
| `get_ai_suggestions()` | Recommends 3 songs based on your library |
| `analyze_genres()` | Classifies recent tracks into genre percentages |
| `analyze_weekly_favorite()` | Deep-dives your most-played track (mood, taste, recs) |
| `analyze_top_songs()` | Analyzes top 3 songs with "Why You Love It" narratives |
| `generate_playlist()` | Creates themed 5-track playlist from your top songs |
| `get_recently_played()` | Fetches last 50 played tracks with timestamps |
| `get_saved_tracks()` | Pulls full saved library (paginated, up to 500 tracks) |

## Origin Story

This project was built as a proof-of-concept demonstrating how a Python watchdog pipeline can automate API data collection, AI processing, and dashboard generation. The architecture pattern (API → Watchdog → AI → Sheets → Dashboard) proved the viability of automated operations intelligence at enterprise scale.

## License

MIT
