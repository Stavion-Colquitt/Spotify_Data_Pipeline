#!/usr/bin/env python3
"""
Spotify Dashboard Watchdog
==========================
Main orchestration script that runs on schedule.

This demonstrates the ServiceNow-to-PowerBI automation pattern:
1. Pull data from API (Spotify = ServiceNow)
2. Process with AI (Gemini)
3. Export to spreadsheet (Google Sheets = Excel/SharePoint)
4. Dashboard auto-refreshes (Looker Studio = PowerBI)

Usage:
    python3 watchdog.py              # Run normally
    python3 watchdog.py --ai         # Use full AI processing instead of local
    python3 watchdog.py --csv        # Output to CSV instead of Google Sheets
    python3 watchdog.py --test       # Use sample data, local processing, CSV output
"""

import sys
import logging
import argparse
from datetime import datetime
from pathlib import Path

from config import BASE_DIR, FETCH_LIMIT, USE_SAMPLE_DATA
from spotify_client import SpotifyClient
from ai_processor import (
    process_with_ai, process_locally, validate_with_ai,
    get_song_suggestions, analyze_genres_with_spotify,
    get_weekly_favorite_analysis, analyze_top_songs
)
from sheets_exporter import (
    export_to_sheets, export_to_csv, get_7_day_play_counts,
    export_top_songs_analysis
)

# Setup logging
LOG_FILE = BASE_DIR / "watchdog.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def main(use_local_processing=False, use_csv_output=False):
    """Main watchdog function"""
    
    logger.info("=" * 60)
    logger.info("WATCHDOG STARTED")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info(f"Mode: {'LOCAL + AI validation' if use_local_processing else 'GEMINI API only'}")
    logger.info(f"Output: {'CSV' if use_csv_output else 'Google Sheets'}")
    logger.info("=" * 60)
    
    try:
        # Check if this is a full refresh (6am/6pm) or just playback tracking
        current_hour = datetime.now().hour
        is_full_refresh = current_hour in [6, 18]

        # =============================================
        # STEP 1: Fetch data from Spotify API
        # =============================================

        logger.info("STEP 1: Fetching data from Spotify API...")
        spotify = SpotifyClient()

        # Always fetch recently played (for playback history tracking)
        recently_played = spotify.get_recently_played(limit=50)
        logger.info(f"  ✓ Fetched {len(recently_played)} recently played tracks")

        # Only fetch liked songs at 6am and 6pm to avoid rate limits
        tracks = None
        processed = None
        suggestions = None
        genre_data = None
        favorite_analysis = None
        top_songs_analysis = None

        if is_full_refresh:
            logger.info(f"  Full refresh (hour={current_hour}) - fetching liked songs...")
            tracks = spotify.get_all_saved_tracks(max_tracks=FETCH_LIMIT)
            logger.info(f"  ✓ Fetched {len(tracks)} saved tracks")

            # =============================================
            # STEP 2: Process data and run AI features
            # =============================================

            logger.info("STEP 2: Processing data...")
            if use_local_processing:
                logger.info("  Using local processing...")
                processed = process_locally(tracks)

                logger.info("  Running AI validation check...")
                validation = validate_with_ai(processed)
                if validation:
                    logger.info(f"  AI validation: {validation}")

                logger.info("  Getting song suggestions from Gemini...")
                suggestions = get_song_suggestions(recently_played)
                if suggestions:
                    logger.info(f"  Got {len(suggestions)} song suggestions")
                    for i, s in enumerate(suggestions, 1):
                        logger.info(f"    {i}. {s['song']} by {s['artist']}")
                else:
                    logger.info("  No suggestions returned")

                logger.info("  Running genre analysis (using Spotify data)...")
                genre_data = analyze_genres_with_spotify(recently_played, spotify)
                if genre_data:
                    logger.info(f"  Got genre analysis ({len(genre_data)} genres)")
                    for g in genre_data:
                        logger.info(f"    {g['genre']}: {g['percentage']}%")
                    total = sum(g['percentage'] for g in genre_data)
                    if total != 100:
                        logger.warning(f"  Warning: Genre percentages sum to {total}%, not 100%")
                else:
                    logger.info("  No genre data returned")

                logger.info("  Running weekly favorite analysis (with track details)...")
                # Get 7-day history from Google Sheets for accurate play counts
                sheets_history = get_7_day_play_counts()
                favorite_analysis = get_weekly_favorite_analysis(
                    recently_played, spotify_client=spotify, sheets_history=sheets_history
                )
                if favorite_analysis:
                    fav = favorite_analysis['favorite']
                    logger.info(f"  Most-played song: {fav['track']} by {fav['artist']} ({fav['play_count']} plays)")
                    if favorite_analysis.get('track_details'):
                        td = favorite_analysis['track_details']
                        genres = ", ".join(td['artist_genres']) if td['artist_genres'] else "indie"
                        logger.info(f"  Track info: popularity={td['popularity']}, genres={genres}")
                    logger.info(f"  Mood: {favorite_analysis.get('mood_analysis', 'N/A')[:80]}...")
                    if favorite_analysis.get('recommendations'):
                        logger.info(f"  Got {len(favorite_analysis['recommendations'])} recommendations based on taste")
                else:
                    logger.info("  No favorite analysis returned")

                # Analyze top 3 songs with AI insights and playlist
                logger.info("  Analyzing top 3 songs with AI...")
                from collections import Counter
                if sheets_history:
                    play_counts = Counter(sheets_history)
                    top_3 = [(track, artist, count) for (track, artist), count in play_counts.most_common(3)]
                    top_songs_analysis = analyze_top_songs(top_3, spotify_client=spotify)
                    if top_songs_analysis:
                        logger.info(f"  ✓ Top songs analysis complete")
                        playlist = top_songs_analysis.get('playlist', {})
                        if playlist:
                            logger.info(f"  Playlist: {playlist.get('name', 'N/A')}")
                    else:
                        logger.info("  No top songs analysis returned")
            else:
                logger.info("  Sending to Gemini API for analysis...")
                processed = process_with_ai(tracks)

            logger.info(f"  ✓ Processing complete")
            logger.info(f"    - Total tracks: {processed['summary']['total_tracks']}")
            logger.info(f"    - Unique artists: {processed['summary']['unique_artists']}")
            logger.info(f"    - Top artist: {processed['top_artists'][0]['artist']} ({processed['top_artists'][0]['count']} songs)")
        else:
            logger.info(f"  Playback tracking only (hour={current_hour}) - skipping liked songs fetch")
            logger.info("STEP 2: Skipping processing (runs at 6am/6pm)")
        
        # =============================================
        # STEP 3: Export to spreadsheet
        # =============================================
        # For ServiceNow/PowerBI: Replace with SharePoint upload
        
        logger.info("STEP 3: Exporting data...")
        if use_csv_output:
            output_location = export_to_csv(
                processed, recently_played,
                suggestions=suggestions, favorite_analysis=favorite_analysis
            )
            logger.info(f"  ✓ Exported to CSV: {output_location}")
        else:
            sheet_url = export_to_sheets(
                processed, recently_played,
                suggestions=suggestions, genre_data=genre_data,
                favorite_analysis=favorite_analysis
            )
            logger.info(f"  ✓ Exported to Google Sheets: {sheet_url}")

            # Export top songs analysis if available
            if top_songs_analysis and sheets_history:
                try:
                    import gspread
                    from oauth2client.service_account import ServiceAccountCredentials
                    from config import GOOGLE_SHEETS_CREDS_FILE, SPREADSHEET_NAME
                    from collections import Counter

                    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
                    creds = ServiceAccountCredentials.from_json_keyfile_name(GOOGLE_SHEETS_CREDS_FILE, scope)
                    client = gspread.authorize(creds)
                    spreadsheet = client.open(SPREADSHEET_NAME)

                    play_counts = Counter(sheets_history)
                    top_3 = [(track, artist, count) for (track, artist), count in play_counts.most_common(3)]
                    export_top_songs_analysis(spreadsheet, top_songs_analysis, top_3)
                    logger.info("  ✓ Top Songs & Playlist exported")
                except Exception as e:
                    logger.warning(f"  Top songs export failed: {str(e)[:50]}")
        
        # =============================================
        # STEP 4: Done!
        # =============================================
        # Looker Studio / PowerBI will auto-refresh from the spreadsheet
        
        logger.info("=" * 60)
        logger.info("SUCCESS - Dashboard data updated!")
        logger.info("=" * 60)
        
        # Log summary for quick review
        if processed:
            logger.info("SUMMARY:")
            logger.info(f"  Total Tracks: {processed['summary']['total_tracks']}")
            logger.info(f"  Total Duration: {processed['summary']['total_duration_hours']} hours")
            logger.info(f"  Unique Artists: {processed['summary']['unique_artists']}")
            logger.info(f"  Date Range: {processed['summary']['date_range']}")
        else:
            logger.info("SUMMARY: Playback tracking only (full refresh at 6am/6pm)")

        return True
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"FAILED: {str(e)}")
        logger.error("=" * 60)
        import traceback
        logger.error(traceback.format_exc())
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Spotify Dashboard Watchdog")
    parser.add_argument("--ai", action="store_true",
                        help="Use full AI processing instead of local (less accurate)")
    parser.add_argument("--csv", action="store_true",
                        help="Output to CSV files instead of Google Sheets")
    parser.add_argument("--test", action="store_true",
                        help="Test mode: sample data + local processing + CSV output")

    args = parser.parse_args()

    if args.test:
        # Test mode - no API calls needed
        success = main(use_local_processing=True, use_csv_output=True)
    else:
        # Default is local processing (accurate) with AI validation
        success = main(
            use_local_processing=not args.ai,  # Local by default, AI if --ai flag
            use_csv_output=args.csv
        )
    
    sys.exit(0 if success else 1)
