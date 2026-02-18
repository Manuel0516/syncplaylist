from __future__ import annotations

import logging

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from app.config import SPOTIFY_SCOPE, Settings
from app.matching.matcher import SongMatcher
from app.models import MatchedSong, Song
from app.retry import run_with_retries


class SpotifyClient:
    def __init__(self, settings: Settings, matcher: SongMatcher, logger: logging.Logger | None = None) -> None:
        self.settings = settings
        self.matcher = matcher
        self.logger = logger or logging.getLogger(__name__)
        self._client = self._authenticate()

    def _authenticate(self) -> spotipy.Spotify:
        auth_manager = SpotifyOAuth(
            client_id=self.settings.spotify_client_id,
            client_secret=self.settings.spotify_client_secret,
            redirect_uri=self.settings.spotify_redirect_uri,
            scope=SPOTIFY_SCOPE,
            cache_path=str(self.settings.spotify_token_file),
            open_browser=False,
        )
        return spotipy.Spotify(auth_manager=auth_manager)

    def list_playlist_songs(self, playlist_id: str) -> list[Song]:
        songs: list[Song] = []
        offset = 0

        while True:
            response = run_with_retries(
                lambda: self._client.playlist_items(
                    playlist_id,
                    limit=100,
                    offset=offset,
                    additional_types=("track",),
                ),
                description="Spotify playlist fetch",
                logger=self.logger,
            )

            items = response.get("items", [])
            if not items:
                break

            for item in items:
                track = item.get("track")
                if not track:
                    continue

                song_id = track.get("id")
                title = track.get("name") or ""
                artists = [artist.get("name", "") for artist in track.get("artists", []) if artist.get("name")]
                artist = ", ".join(artists)
                if not song_id or not title:
                    continue

                songs.append(
                    Song(
                        id=song_id,
                        title=title,
                        artist=artist,
                        source="spotify",
                        raw_title=title,
                        raw_artist=artist,
                    )
                )

            if response.get("next") is None:
                break

            offset += len(items)

        return songs

    def search_best_match(self, source_song: Song) -> MatchedSong | None:
        candidates = self._search_candidates(source_song)
        return self.matcher.find_best_match(source_song, candidates)

    def _search_candidates(self, source_song: Song) -> list[Song]:
        query_variants = [
            f'track:"{source_song.title}" artist:"{source_song.artist}"',
            f"{source_song.title} {source_song.artist}",
            f'track:"{source_song.title}"',
        ]

        seen_ids: set[str] = set()
        candidates: list[Song] = []
        source_title_lower = source_song.title.lower()

        for query in query_variants:
            response = run_with_retries(
                lambda q=query: self._client.search(
                    q=q,
                    type="track",
                    limit=self.settings.spotify_search_limit,
                ),
                description=f"Spotify search ({query})",
                logger=self.logger,
            )

            tracks = response.get("tracks", {}).get("items", [])
            for track in tracks:
                song_id = track.get("id")
                title = track.get("name") or ""
                artists = [artist.get("name", "") for artist in track.get("artists", []) if artist.get("name")]
                artist = ", ".join(artists)
                if not song_id or not title or song_id in seen_ids:
                    continue
                title_lower = title.lower()
                if (
                    any(term in title_lower for term in ("karaoke", "cover", "instrumental"))
                    and not any(term in source_title_lower for term in ("karaoke", "cover", "instrumental"))
                ):
                    continue

                seen_ids.add(song_id)
                candidates.append(
                    Song(
                        id=song_id,
                        title=title,
                        artist=artist,
                        source="spotify",
                        raw_title=title,
                        raw_artist=artist,
                    )
                )

        return candidates

    def add_song_to_playlist(self, playlist_id: str, song_id: str) -> None:
        run_with_retries(
            lambda: self._client.playlist_add_items(playlist_id, [song_id]),
            description=f"Spotify add {song_id}",
            logger=self.logger,
        )
