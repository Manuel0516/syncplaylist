from __future__ import annotations

import logging
import os
import pickle

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from app.config import Settings, YOUTUBE_SCOPES
from app.matching.matcher import SongMatcher
from app.models import MatchedSong, Song
from app.retry import run_with_retries


class YouTubeClient:
    def __init__(self, settings: Settings, matcher: SongMatcher, logger: logging.Logger | None = None) -> None:
        self.settings = settings
        self.matcher = matcher
        self.logger = logger or logging.getLogger(__name__)
        self._service = self._authenticate()

    def _authenticate(self):
        creds: Credentials | None = None

        def run_local_auth_server(*, open_browser: bool):
            kwargs = {
                "host": "localhost",
                "port": self.settings.youtube_auth_port,
                "open_browser": open_browser,
            }
            bind_addr = self.settings.youtube_auth_bind_addr.strip()
            if bind_addr:
                kwargs["bind_addr"] = bind_addr
            self.logger.info(
                "Starting YouTube OAuth callback server at http://localhost:%s/ (bind_addr=%s)",
                self.settings.youtube_auth_port,
                bind_addr or "default",
            )
            try:
                return flow.run_local_server(**kwargs)
            except TypeError:
                kwargs.pop("bind_addr", None)
                return flow.run_local_server(**kwargs)

        if self.settings.youtube_token_file.exists():
            with self.settings.youtube_token_file.open("rb") as token_file:
                creds = pickle.load(token_file)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not self.settings.google_credentials_file.exists():
                    raise FileNotFoundError(
                        f"Google credentials file not found: {self.settings.google_credentials_file}"
                    )

                flow = InstalledAppFlow.from_client_secrets_file(
                    str(self.settings.google_credentials_file),
                    YOUTUBE_SCOPES,
                )
                auth_mode = self.settings.youtube_auth_mode
                if auth_mode not in {"auto", "console", "local"}:
                    raise ValueError("YOUTUBE_AUTH_MODE must be one of: auto, console, local")

                has_display = bool(os.getenv("DISPLAY"))
                if auth_mode == "local":
                    open_browser = has_display
                elif auth_mode == "console":
                    open_browser = False
                else:
                    open_browser = has_display
                creds = run_local_auth_server(open_browser=open_browser)

            self.settings.youtube_token_file.parent.mkdir(parents=True, exist_ok=True)
            with self.settings.youtube_token_file.open("wb") as token_file:
                pickle.dump(creds, token_file)

        return build("youtube", "v3", credentials=creds)

    def list_playlist_songs(self, playlist_id: str) -> list[Song]:
        songs: list[Song] = []
        page_token: str | None = None

        while True:
            response = run_with_retries(
                lambda token=page_token: self._service.playlistItems()
                .list(
                    part="snippet,contentDetails",
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=token,
                )
                .execute(),
                description="YouTube playlist fetch",
                logger=self.logger,
            )

            for item in response.get("items", []):
                snippet = item.get("snippet", {})
                title = snippet.get("title") or ""
                if title in {"Private video", "Deleted video"}:
                    continue

                song_id = (
                    item.get("contentDetails", {}).get("videoId")
                    or snippet.get("resourceId", {}).get("videoId")
                    or ""
                )
                artist = (
                    snippet.get("videoOwnerChannelTitle")
                    or snippet.get("channelTitle")
                    or ""
                )

                if not song_id or not title:
                    continue

                songs.append(
                    Song(
                        id=song_id,
                        title=title,
                        artist=artist,
                        source="youtube",
                        raw_title=title,
                        raw_artist=artist,
                    )
                )

            page_token = response.get("nextPageToken")
            if not page_token:
                break

        return songs

    def search_best_match(self, source_song: Song) -> MatchedSong | None:
        candidates = self._search_candidates(source_song)
        return self.matcher.find_best_match(source_song, candidates)

    def _search_candidates(self, source_song: Song) -> list[Song]:
        query_variants = [
            f"{source_song.title} {source_song.artist}",
            source_song.title,
        ]

        seen_ids: set[str] = set()
        candidates: list[Song] = []
        source_title_lower = source_song.title.lower()

        for query in query_variants:
            response = run_with_retries(
                lambda q=query: self._service.search()
                .list(
                    q=q,
                    part="snippet",
                    type="video",
                    videoCategoryId="10",
                    maxResults=self.settings.youtube_search_limit,
                )
                .execute(),
                description=f"YouTube search ({query})",
                logger=self.logger,
            )

            for item in response.get("items", []):
                song_id = item.get("id", {}).get("videoId") or ""
                snippet = item.get("snippet", {})
                title = snippet.get("title") or ""
                artist = snippet.get("channelTitle") or ""
                if not song_id or not title or song_id in seen_ids:
                    continue
                title_lower = title.lower()
                if (
                    any(term in title_lower for term in ("karaoke", "cover", "nightcore", "sped up", "slowed"))
                    and not any(term in source_title_lower for term in ("karaoke", "cover", "nightcore", "sped up", "slowed"))
                ):
                    continue

                seen_ids.add(song_id)
                candidates.append(
                    Song(
                        id=song_id,
                        title=title,
                        artist=artist,
                        source="youtube",
                        raw_title=title,
                        raw_artist=artist,
                    )
                )

        return candidates

    def add_song_to_playlist(self, playlist_id: str, song_id: str) -> None:
        run_with_retries(
            lambda: self._service.playlistItems()
            .insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": song_id,
                        },
                    }
                },
            )
            .execute(),
            description=f"YouTube add {song_id}",
            logger=self.logger,
        )
