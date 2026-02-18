#!/usr/bin/env python3
"""
Spotify API Client
Handles authentication and data fetching from Spotify
"""

import requests
import base64
import json
from config import (
    SPOTIFY_CLIENT_ID, 
    SPOTIFY_CLIENT_SECRET, 
    SPOTIFY_REFRESH_TOKEN,
    USE_SAMPLE_DATA,
    SAMPLE_DATA_FILE
)


class SpotifyClient:
    def __init__(self):
        self.access_token = None
        if not USE_SAMPLE_DATA:
            self.refresh_access_token()
    
    def refresh_access_token(self):
        """Get new access token using refresh token"""
        auth_string = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
        auth_b64 = base64.b64encode(auth_string.encode()).decode()
        
        response = requests.post(
            "https://accounts.spotify.com/api/token",
            headers={"Authorization": f"Basic {auth_b64}"},
            data={
                "grant_type": "refresh_token",
                "refresh_token": SPOTIFY_REFRESH_TOKEN
            }
        )
        
        if response.status_code == 200:
            self.access_token = response.json()["access_token"]
        else:
            raise Exception(f"Failed to refresh token: {response.text}")
    
    def get_saved_tracks(self, limit=50, offset=0):
        """Fetch user's liked songs from Spotify API"""
        if USE_SAMPLE_DATA:
            return self._get_sample_data(limit, offset)
        
        response = requests.get(
            f"https://api.spotify.com/v1/me/tracks?limit={limit}&offset={offset}",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"API error: {response.text}")
    
    def _get_sample_data(self, limit, offset):
        """Return sample data for testing without API calls"""
        with open(SAMPLE_DATA_FILE, 'r') as f:
            data = json.load(f)
        
        tracks = data.get("tracks", [])
        return {
            "items": [
                {"track": t, "added_at": t.get("added_at")} 
                for t in tracks[offset:offset+limit]
            ],
            "total": len(tracks)
        }
    
    def get_all_saved_tracks(self, max_tracks=400):
        """Paginate through all saved tracks"""
        all_tracks = []
        offset = 0
        
        while offset < max_tracks:
            data = self.get_saved_tracks(limit=50, offset=offset)
            items = data.get("items", [])
            
            if not items:
                break
            
            for item in items:
                track = item.get("track", item)
                
                # Handle both API response and sample data formats
                if "artists" in track:
                    artist = ", ".join([a["name"] for a in track["artists"]])
                else:
                    artist = track.get("artist", "Unknown")
                
                all_tracks.append({
                    "name": track.get("name", "Unknown"),
                    "artist": artist,
                    "album": track["album"]["name"] if isinstance(track.get("album"), dict) else track.get("album", "Unknown"),
                    "duration_ms": track.get("duration_ms", 0),
                    "added_at": item.get("added_at", track.get("added_at", "")),
                    "id": track.get("id", "")
                })
            
            offset += 50
            print(f"Fetched {len(all_tracks)} tracks...")
        
        return all_tracks


    def get_recently_played(self, limit=50):
        """Fetch user's recently played tracks"""
        if USE_SAMPLE_DATA:
            return []  # No sample data for recently played

        response = requests.get(
            f"https://api.spotify.com/v1/me/player/recently-played?limit={limit}",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )

        if response.status_code != 200:
            raise Exception(f"API error: {response.text}")

        data = response.json()
        tracks = []

        for item in data.get("items", []):
            track = item["track"]
            tracks.append({
                "name": track["name"],
                "artist": ", ".join([a["name"] for a in track["artists"]]),
                "album": track["album"]["name"],
                "duration_ms": track["duration_ms"],
                "played_at": item["played_at"],
                "id": track["id"]
            })

        return tracks


    def get_track_details(self, track_id):
        """
        Fetch detailed track and artist info from Spotify.

        Note: audio-features endpoint was deprecated by Spotify in late 2024.
        This uses the track and artist endpoints instead.

        Returns dict with:
            - popularity: 0-100 track popularity
            - duration_ms: track duration
            - explicit: boolean
            - album_name: album name
            - release_date: album release date
            - artist_genres: list of artist genres (may be empty for indie artists)
            - artist_popularity: 0-100 artist popularity
        """
        if USE_SAMPLE_DATA or not track_id:
            return None

        # Get track info
        response = requests.get(
            f"https://api.spotify.com/v1/tracks/{track_id}",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )

        if response.status_code != 200:
            print(f"Failed to get track details: {response.status_code}")
            return None

        track = response.json()
        artist_id = track['artists'][0]['id'] if track.get('artists') else None

        result = {
            "popularity": track.get("popularity", 0),
            "duration_ms": track.get("duration_ms", 0),
            "explicit": track.get("explicit", False),
            "album_name": track.get("album", {}).get("name", "Unknown"),
            "release_date": track.get("album", {}).get("release_date", "Unknown"),
            "artist_genres": [],
            "artist_popularity": 0
        }

        # Get artist info for genres
        if artist_id:
            artist_response = requests.get(
                f"https://api.spotify.com/v1/artists/{artist_id}",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            if artist_response.status_code == 200:
                artist = artist_response.json()
                result["artist_genres"] = artist.get("genres", [])
                result["artist_popularity"] = artist.get("popularity", 0)

        return result

    def get_genres_for_tracks(self, track_ids):
        """
        Fetch genres for a list of tracks by getting their artist info.
        Uses batch endpoints for efficiency (max 2 API calls for 50 tracks).

        Args:
            track_ids: List of Spotify track IDs

        Returns:
            Dict mapping track_id to list of genres
        """
        if USE_SAMPLE_DATA or not track_ids:
            return {}

        # Remove duplicates while preserving order
        unique_ids = list(dict.fromkeys(track_ids))[:50]  # Spotify limit is 50

        # Get tracks in batch
        ids_param = ",".join(unique_ids)
        response = requests.get(
            f"https://api.spotify.com/v1/tracks?ids={ids_param}",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )

        if response.status_code != 200:
            print(f"Failed to get tracks: {response.status_code}")
            return {}

        tracks_data = response.json().get("tracks", [])

        # Collect unique artist IDs
        artist_ids = set()
        track_to_artist = {}  # Map track_id to primary artist_id

        for track in tracks_data:
            if track and track.get("artists"):
                artist_id = track["artists"][0]["id"]
                artist_ids.add(artist_id)
                track_to_artist[track["id"]] = artist_id

        if not artist_ids:
            return {}

        # Get artists in batch (up to 50)
        artist_ids_param = ",".join(list(artist_ids)[:50])
        artist_response = requests.get(
            f"https://api.spotify.com/v1/artists?ids={artist_ids_param}",
            headers={"Authorization": f"Bearer {self.access_token}"}
        )

        if artist_response.status_code != 200:
            print(f"Failed to get artists: {artist_response.status_code}")
            return {}

        artists_data = artist_response.json().get("artists", [])

        # Build artist_id to genres map
        artist_genres = {}
        for artist in artists_data:
            if artist:
                artist_genres[artist["id"]] = artist.get("genres", [])

        # Build final track_id to genres map
        result = {}
        for track_id, artist_id in track_to_artist.items():
            result[track_id] = artist_genres.get(artist_id, [])

        return result


if __name__ == "__main__":
    # Test the client
    client = SpotifyClient()
    tracks = client.get_all_saved_tracks(max_tracks=100)
    print(f"\nTotal tracks fetched: {len(tracks)}")
    print(f"\nFirst 5 tracks:")
    for t in tracks[:5]:
        print(f"  - {t['name']} by {t['artist']}")
