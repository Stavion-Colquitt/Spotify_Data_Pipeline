#!/usr/bin/env python3
"""
AI Processor
Local data processing + Gemini AI for validation, suggestions, and analysis
"""

import requests
import json
from config import GEMINI_API_KEY


def process_with_ai(tracks):
    """
    Send track data to Gemini for analysis and formatting.
    Returns structured data ready for dashboard.
    """

    prompt = f"""Analyze this Spotify listening data and return a JSON object.

IMPORTANT: Return ONLY valid JSON, no other text, no markdown code blocks.

Required structure:
{{
    "summary": {{
        "total_tracks": <number>,
        "total_duration_hours": <number rounded to 1 decimal>,
        "avg_duration_minutes": <number rounded to 2 decimals>,
        "unique_artists": <number>,
        "date_range": "<earliest date> to <latest date>"
    }},
    "top_artists": [
        {{"artist": "<n>", "count": <number>}}
    ],
    "monthly_additions": [
        {{"month": "YYYY-MM", "count": <number>}}
    ],
    "recent_tracks": [
        {{"name": "<track>", "artist": "<artist>", "added": "<YYYY-MM-DD>"}}
    ]
}}

Rules:
- top_artists: Include top 15 artists by song count, sorted descending
- monthly_additions: Group by YYYY-MM, include all months with data, sorted chronologically
- recent_tracks: Last 40 tracks added, sorted by date descending
- Calculate duration from duration_ms field (divide by 3600000 for hours, 60000 for minutes)

Track data ({len(tracks)} tracks):
{json.dumps(tracks, indent=2)}
"""

    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
        headers={
            "Content-Type": "application/json"
        },
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json"
            }
        }
    )

    if response.status_code != 200:
        raise Exception(f"Gemini API error: {response.text}")

    result = response.json()
    content = result["candidates"][0]["content"]["parts"][0]["text"]

    # Clean up response if it has markdown code blocks
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
    if content.endswith("```"):
        content = content.rsplit("\n", 1)[0]

    return json.loads(content)


def validate_with_ai(processed_data):
    """
    Use AI to validate locally processed data.
    Returns a brief validation message or None if all looks good.
    """
    summary = processed_data['summary']
    top_artists = processed_data['top_artists'][:5]

    prompt = f"""Review this Spotify data summary for any obvious issues or anomalies.

Summary:
- Total tracks: {summary['total_tracks']}
- Total duration: {summary['total_duration_hours']} hours
- Average song: {summary['avg_duration_minutes']} minutes
- Unique artists: {summary['unique_artists']}
- Date range: {summary['date_range']}

Top 5 artists: {', '.join([f"{a['artist']} ({a['count']})" for a in top_artists])}

Respond with ONLY one of these:
- "OK" if the data looks reasonable
- A brief issue description (max 10 words) if something looks wrong

Examples of issues: negative numbers, impossible dates, avg song over 60 min, 0 tracks, etc.
"""

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}]
            },
            timeout=10
        )

        if response.status_code == 200:
            result = response.json()
            validation = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            return validation
        else:
            return "API error - skipping validation"
    except Exception as e:
        return f"Validation skipped: {str(e)[:30]}"


def get_song_suggestions(recently_played):
    """
    Use Gemini to suggest 5 songs based on recently played tracks.
    Runs at 6am and 6pm to give listening suggestions.
    """
    if not recently_played:
        return None

    # Build a summary of recent listening
    recent_summary = []
    for track in recently_played[:20]:
        recent_summary.append(f"- {track.get('name', 'Unknown')} by {track.get('artist', 'Unknown')}")

    prompt = f"""Based on these recently played songs, suggest 5 songs the listener might enjoy.

Recently played:
{chr(10).join(recent_summary)}

Return ONLY a JSON array with exactly 5 song suggestions. Each suggestion should have:
- "song": the song title
- "artist": the artist name
- "reason": a brief reason why they might like it (max 15 words)

Example format:
[
    {{"song": "Song Name", "artist": "Artist Name", "reason": "Similar vibe to X you played"}}
]

Focus on suggesting songs that match the mood, genre, and style of their recent listening.
Return ONLY the JSON array, no other text."""

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            },
            timeout=30
        )

        if response.status_code == 200:
            result = response.json()
            content = result["candidates"][0]["content"]["parts"][0]["text"].strip()
            suggestions = json.loads(content)
            return suggestions[:5]
        else:
            return None
    except Exception as e:
        print(f"Song suggestions failed: {str(e)[:50]}")
        return None


def analyze_genres_with_spotify(recently_played, spotify_client):
    """
    Hybrid genre analysis: Uses Spotify data when available, Gemini for unknown artists.

    Args:
        recently_played: List of recently played track dicts (must have 'id' key)
        spotify_client: SpotifyClient instance for API calls

    Returns:
        List of dicts: [{"genre": "R&B", "percentage": 35}, ...]
    """
    from collections import Counter

    if not recently_played or not spotify_client:
        return None

    # Get unique track IDs
    track_ids = [t.get('id') for t in recently_played if t.get('id')]
    if not track_ids:
        return None

    # Fetch genres for all tracks (2 API calls max)
    track_genres = spotify_client.get_genres_for_tracks(track_ids)

    if not track_genres:
        print("  No genre data returned from Spotify")
        return None

    # Separate tracks with genres from those without
    tracks_without_genres = []
    genre_counts = Counter()

    for track in recently_played:
        track_id = track.get('id')
        if track_id and track_id in track_genres:
            genres = track_genres[track_id]
            if genres:
                for genre in genres:
                    genre_counts[genre] += 1
            else:
                tracks_without_genres.append(track)

    # Use Gemini to classify tracks without Spotify genres
    if tracks_without_genres:
        print(f"  Using Gemini to classify {len(tracks_without_genres)} tracks without Spotify genres...")
        gemini_genres = _classify_unknown_genres_with_gemini(tracks_without_genres)
        if gemini_genres:
            for genre, count in gemini_genres.items():
                genre_counts[genre] += count

    if not genre_counts:
        return None

    # Convert to percentages
    total_plays = sum(genre_counts.values())
    genre_list = []

    for genre, count in genre_counts.most_common():
        percentage = round(count * 100 / total_plays)
        if percentage > 0:
            genre_name = genre.title()
            genre_list.append({"genre": genre_name, "percentage": percentage})

    # Ensure percentages sum to 100
    current_total = sum(g['percentage'] for g in genre_list)
    if current_total != 100 and genre_list:
        genre_list[0]['percentage'] += (100 - current_total)

    # Limit to top 8 genres, group rest into "Other"
    if len(genre_list) > 8:
        top_7 = genre_list[:7]
        other_pct = sum(g['percentage'] for g in genre_list[7:])
        top_7.append({"genre": "Other", "percentage": other_pct})
        genre_list = top_7

    return genre_list


def _classify_unknown_genres_with_gemini(tracks):
    """
    Use Gemini to classify tracks that don't have Spotify genre data.
    Only called for tracks where Spotify has no genre info.
    """
    from collections import Counter

    if not tracks:
        return Counter()

    # Group by artist to avoid duplicate classifications
    artist_tracks = {}
    for track in tracks:
        artist = track.get('artist', 'Unknown')
        if artist not in artist_tracks:
            artist_tracks[artist] = {'tracks': [], 'count': 0}
        artist_tracks[artist]['tracks'].append(track.get('name', 'Unknown'))
        artist_tracks[artist]['count'] += 1

    artist_list = []
    for artist, data in artist_tracks.items():
        sample_tracks = data['tracks'][:3]
        artist_list.append(f"- {artist} (songs: {', '.join(sample_tracks)})")

    prompt = f"""Classify these music artists into genres. Spotify has no genre data for them.

Artists to classify:
{chr(10).join(artist_list)}

Return ONLY a JSON object mapping each artist name to ONE genre.
Use simple genres: Hip Hop, R&B, Pop, Rock, Electronic, Indie, Country, Latin, Jazz, Metal, Folk, Alternative

Example format:
{{"Artist Name": "Hip Hop", "Another Artist": "Pop"}}

Return ONLY the JSON object, no other text."""

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            },
            timeout=30
        )

        if response.status_code != 200:
            print(f"  Gemini API error: {response.status_code}")
            return Counter()

        result = response.json()
        content = result["candidates"][0]["content"]["parts"][0]["text"].strip()

        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("\n", 1)[0]

        artist_genres = json.loads(content)

        genre_counts = Counter()
        for artist, data in artist_tracks.items():
            genre = artist_genres.get(artist, "Other")
            genre_counts[genre.lower()] += data['count']

        return genre_counts

    except Exception as e:
        print(f"  Gemini classification failed: {str(e)[:50]}")
        return Counter()


def analyze_genres_with_gemini(tracks_data):
    """
    DEPRECATED: Use analyze_genres_with_spotify() instead.
    This function used AI to guess genres, which was inaccurate.
    Kept for backward compatibility but not recommended.
    """
    print("  Warning: analyze_genres_with_gemini is deprecated, use analyze_genres_with_spotify")
    return None


def analyze_top_songs(top_songs, spotify_client=None):
    """
    Analyze top 3 songs with AI to explain why the user likes them
    and generate a mini playlist based on their taste.

    Args:
        top_songs: List of tuples [(track, artist, play_count), ...]
        spotify_client: Optional SpotifyClient for fetching track details

    Returns:
        dict with song analyses and playlist recommendations
    """
    if not top_songs or len(top_songs) == 0:
        return None

    songs_context = []
    for i, (track, artist, count) in enumerate(top_songs[:3], 1):
        songs_context.append(f'{i}. "{track}" by {artist} ({count} plays)')

    prompt = f"""Analyze why this listener loves these songs and create a playlist for them.

Their top 3 most-played songs (last 7 days):
{chr(10).join(songs_context)}

Return ONLY a JSON object with this exact structure:
{{
    "song_analyses": [
        {{"track": "<song 1 name>", "artist": "<artist>", "why_you_love_it": "<2 sentences explaining the appeal of this song>"}},
        {{"track": "<song 2 name>", "artist": "<artist>", "why_you_love_it": "<2 sentences explaining the appeal of this song>"}},
        {{"track": "<song 3 name>", "artist": "<artist>", "why_you_love_it": "<2 sentences explaining the appeal of this song>"}}
    ],
    "playlist": {{
        "name": "<creative playlist name based on their taste>",
        "description": "<1 sentence describing the vibe>",
        "songs": [
            {{"track": "<song name>", "artist": "<artist>"}},
            {{"track": "<song name>", "artist": "<artist>"}},
            {{"track": "<song name>", "artist": "<artist>"}},
            {{"track": "<song name>", "artist": "<artist>"}},
            {{"track": "<song name>", "artist": "<artist>"}}
        ]
    }}
}}

Rules:
- For "why_you_love_it": Be specific about the musical elements, mood, or themes that make each song appealing
- For the playlist: Suggest 5 songs that match the overall vibe of their top 3 (do NOT include any of their top 3 songs)
- Make the playlist name creative and personal
- Return ONLY the JSON object, no other text"""

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            },
            timeout=30
        )

        if response.status_code != 200:
            print(f"  Gemini API error: {response.status_code}")
            return None

        result = response.json()
        content = result["candidates"][0]["content"]["parts"][0]["text"].strip()

        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("\n", 1)[0]

        analysis = json.loads(content)

        for i, song_analysis in enumerate(analysis.get('song_analyses', [])):
            if i < len(top_songs):
                song_analysis['play_count'] = top_songs[i][2]

        return analysis

    except Exception as e:
        print(f"  Top songs analysis failed: {str(e)[:50]}")
        return None


def get_weekly_favorite_analysis(recently_played, spotify_client=None, sheets_history=None):
    """
    Find the most-played song from the last 7 days using History_Playback data,
    then use Gemini to analyze the mood/taste and recommend 3 similar songs.

    Args:
        recently_played: List of recently played track dicts (used as fallback and for track IDs)
        spotify_client: Optional SpotifyClient instance to fetch track details
        sheets_history: Optional list of history rows from History_Playback sheet

    Returns:
        dict with favorite track info, mood analysis, taste profile, and 3 recommendations
    """
    from collections import Counter

    # Use 7-day history if available, otherwise fall back to recently_played
    if sheets_history and len(sheets_history) > 0:
        print(f"  Using History_Playback data ({len(sheets_history)} plays from last 7 days)")
        track_counts = Counter(sheets_history)
        (favorite_track, favorite_artist), play_count = track_counts.most_common(1)[0]

        # Try to find track ID from recently_played for Spotify lookup
        favorite_id = ''
        for t in recently_played:
            if t.get('name') == favorite_track and t.get('artist') == favorite_artist:
                favorite_id = t.get('id', '')
                break
    else:
        print("  Using recently_played (last 50 tracks) - History_Playback not available")
        if not recently_played or len(recently_played) < 2:
            return None

        track_counts = Counter(
            (t.get('name', 'Unknown'), t.get('artist', 'Unknown'), t.get('id', ''))
            for t in recently_played
        )
        (favorite_track, favorite_artist, favorite_id), play_count = track_counts.most_common(1)[0]

    # Fetch track details if spotify_client provided
    track_details = None
    track_details_text = ""
    if spotify_client and favorite_id:
        track_details = spotify_client.get_track_details(favorite_id)
        if track_details:
            duration_min = track_details['duration_ms'] / 60000
            genres_text = ", ".join(track_details['artist_genres']) if track_details['artist_genres'] else "not categorized (indie artist)"

            track_details_text = f"""
Spotify Track Info for "{favorite_track}":
- Duration: {duration_min:.1f} minutes
- Track Popularity: {track_details['popularity']}/100
- Artist Popularity: {track_details['artist_popularity']}/100
- Artist Genres: {genres_text}
- Album: {track_details['album_name']}
- Release Date: {track_details['release_date']}
- Explicit: {track_details['explicit']}

Use this info along with the song title, artist name, and listening context to analyze the mood and recommend similar songs.
"""

    # Build context of other frequently played tracks
    top_tracks = track_counts.most_common(5)
    context_list = []
    for item, count in top_tracks:
        if len(item) == 2:
            track, artist = item
        else:
            track, artist, _ = item
        context_list.append(f"- {track} by {artist} ({count} plays)")

    prompt = f"""Analyze this listener's favorite song and their music taste.

Their most-played song recently: "{favorite_track}" by {favorite_artist} (played {play_count} times)
{track_details_text}
Other frequently played songs:
{chr(10).join(context_list)}

Return ONLY a JSON object with this exact structure:
{{
    "mood_analysis": "<2-3 sentences about the mood/vibe of their favorite song>",
    "taste_profile": "<2-3 sentences about what this says about their music taste>",
    "recommendations": [
        {{"song": "<song name>", "artist": "<artist name>", "reason": "<specific connection to {favorite_track}, max 15 words>"}},
        {{"song": "<song name>", "artist": "<artist name>", "reason": "<specific connection to {favorite_track}, max 15 words>"}},
        {{"song": "<song name>", "artist": "<artist name>", "reason": "<specific connection to {favorite_track}, max 15 words>"}}
    ]
}}

Rules:
- Recommend exactly 3 songs that match the mood and style of "{favorite_track}"
- Each recommendation reason MUST reference "{favorite_track}" by name and explain the specific similarity
- Use the track info and listening context to make accurate mood assessments
- Keep mood_analysis and taste_profile concise but insightful
- Do NOT recommend songs already in their listening history
- Return ONLY the JSON object, no other text"""

    try:
        response = requests.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}",
            headers={"Content-Type": "application/json"},
            json={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "responseMimeType": "application/json"
                }
            },
            timeout=30
        )

        if response.status_code != 200:
            print(f"Gemini API error: {response.status_code}")
            return None

        result = response.json()
        content = result["candidates"][0]["content"]["parts"][0]["text"].strip()

        if content.startswith("```"):
            content = content.split("\n", 1)[1]
        if content.endswith("```"):
            content = content.rsplit("\n", 1)[0]

        analysis = json.loads(content)

        analysis['favorite'] = {
            'track': favorite_track,
            'artist': favorite_artist,
            'play_count': play_count
        }

        if track_details:
            analysis['track_details'] = track_details

        if 'recommendations' in analysis:
            analysis['recommendations'] = analysis['recommendations'][:3]

        return analysis

    except Exception as e:
        print(f"Weekly favorite analysis failed: {str(e)[:50]}")
        return None


def process_locally(tracks):
    """
    Process data locally without AI API.
    Use this for testing or if you don't have API access.
    """
    from collections import Counter
    from datetime import datetime
    
    total_duration_ms = sum(t.get("duration_ms", 0) for t in tracks)
    artists = [t.get("artist", "Unknown") for t in tracks]
    artist_counts = Counter(artists)
    
    dates = [t.get("added_at", "")[:10] for t in tracks if t.get("added_at")]
    dates = [d for d in dates if d]
    
    summary = {
        "total_tracks": len(tracks),
        "total_duration_hours": round(total_duration_ms / 3600000, 1),
        "avg_duration_minutes": round(total_duration_ms / len(tracks) / 60000, 2) if tracks else 0,
        "unique_artists": len(set(artists)),
        "date_range": f"{min(dates) if dates else 'N/A'} to {max(dates) if dates else 'N/A'}"
    }
    
    top_artists = [
        {"artist": artist, "count": count}
        for artist, count in artist_counts.most_common(15)
    ]
    
    monthly = Counter()
    for t in tracks:
        added = t.get("added_at", "")[:7]
        if added:
            monthly[added] += 1
    
    monthly_additions = [
        {"month": month, "count": count}
        for month, count in sorted(monthly.items())
    ]
    
    sorted_tracks = sorted(
        [t for t in tracks if t.get("added_at")],
        key=lambda x: x.get("added_at", ""),
        reverse=True
    )[:40]
    
    recent_tracks = [
        {
            "name": t.get("name", "Unknown"),
            "artist": t.get("artist", "Unknown"),
            "added": t.get("added_at", "")[:10]
        }
        for t in sorted_tracks
    ]
    
    return {
        "summary": summary,
        "top_artists": top_artists,
        "monthly_additions": monthly_additions,
        "recent_tracks": recent_tracks
    }


if __name__ == "__main__":
    # Test with sample data
    sample_tracks = [
        {"name": "Song 1", "artist": "Artist A", "duration_ms": 200000, "added_at": "2025-01-15"},
        {"name": "Song 2", "artist": "Artist B", "duration_ms": 180000, "added_at": "2025-01-14"},
        {"name": "Song 3", "artist": "Artist A", "duration_ms": 220000, "added_at": "2025-01-13"},
    ]
    
    print("Testing local processing...")
    result = process_locally(sample_tracks)
    print(json.dumps(result, indent=2))
