#!/usr/bin/env python3
"""
Configuration
All API keys and settings loaded from environment variables.
Copy .env.example to .env and fill in your credentials.
"""

import os
from pathlib import Path

# Load .env file if python-dotenv is available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv is optional

# Base directory (auto-detected)
BASE_DIR = Path(__file__).parent

# Spotify API credentials
# Get these from https://developer.spotify.com/dashboard
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN", "")

# Gemini API key (free tier)
# Get from https://aistudio.google.com/apikey
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Google Sheets settings
GOOGLE_SHEETS_CREDS_FILE = os.getenv(
    "GOOGLE_SHEETS_CREDS_FILE",
    str(BASE_DIR / "google-creds.json")
)
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "Spotify Dashboard Data")

# Processing settings
FETCH_LIMIT = int(os.getenv("FETCH_LIMIT", "500"))  # Max tracks to fetch (set to your total liked songs)
USE_SAMPLE_DATA = os.getenv("USE_SAMPLE_DATA", "false").lower() == "true"
SAMPLE_DATA_FILE = str(BASE_DIR / "sample_data.json")
