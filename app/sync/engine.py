from __future__ import annotations

import logging

from app.config import Settings
from app.matching.matcher import SongMatcher
from app.models import Platform, SyncStats, Song
from app.storage.json_store import JsonStateStore


class SyncEngine:
    def __init__(
        self,
        *,
        settings: Settings,
        matcher: SongMatcher,
        store: JsonStateStore,
        spotify_client,
        youtube_client,
        logger: logging.Logger | None = None,
    ) -> None:
        self.settings = settings
        self.matcher = matcher
        self.store = store
        self.spotify_client = spotify_client
        self.youtube_client = youtube_client
        self.logger = logger or logging.getLogger(__name__)

    def run(self, *, dry_run: bool = False) -> SyncStats:
        stats = SyncStats()

        youtube_songs = self.youtube_client.list_playlist_songs(self.settings.youtube_playlist_id)
        spotify_songs = self.spotify_client.list_playlist_songs(self.settings.spotify_playlist_id)
        stats.youtube_count = len(youtube_songs)
        stats.spotify_count = len(spotify_songs)

        self.store.save_snapshot("youtube", youtube_songs)
        self.store.save_snapshot("spotify", spotify_songs)

        blacklist_titles = self.store.load_blacklist_titles()

        stats.added_to_spotify += self._sync_direction(
            source_songs=youtube_songs,
            target_songs=spotify_songs,
            source_name="YouTube",
            target_platform="spotify",
            blacklist_titles=blacklist_titles,
            dry_run=dry_run,
            stats=stats,
        )

        stats.added_to_youtube += self._sync_direction(
            source_songs=spotify_songs,
            target_songs=youtube_songs,
            source_name="Spotify",
            target_platform="youtube",
            blacklist_titles=blacklist_titles,
            dry_run=dry_run,
            stats=stats,
        )

        return stats

    def _sync_direction(
        self,
        *,
        source_songs: list[Song],
        target_songs: list[Song],
        source_name: str,
        target_platform: Platform,
        blacklist_titles: set[str],
        dry_run: bool,
        stats: SyncStats,
    ) -> int:
        title_index = self._build_title_index(target_songs)
        target_ids = {song.id for song in target_songs}
        added = 0

        for source_song in source_songs:
            if self.matcher.title_key(source_song) in blacklist_titles:
                stats.skipped_blacklist += 1
                self.logger.info("Skipping blacklisted track: %s - %s", source_song.artist, source_song.title)
                continue

            if self._contains_song(source_song, target_songs, title_index):
                stats.skipped_existing += 1
                continue

            match = self._search_target_platform(source_song, target_platform)
            if match is None:
                stats.failed_searches += 1
                self.logger.warning(
                    "No %s match found for %s - %s",
                    target_platform,
                    source_song.artist,
                    source_song.title,
                )
                continue

            if match.song.id in target_ids:
                stats.skipped_existing += 1
                continue

            if dry_run:
                self.logger.info(
                    "[dry-run] Would add to %s: %s - %s (score=%.3f)",
                    target_platform,
                    match.song.artist,
                    match.song.title,
                    match.score,
                )
            else:
                self._add_to_target_platform(target_platform, match.song.id)
                self.logger.info(
                    "Added to %s from %s: %s - %s (score=%.3f)",
                    target_platform,
                    source_name,
                    match.song.artist,
                    match.song.title,
                    match.score,
                )

            target_ids.add(match.song.id)
            target_songs.append(match.song)
            self._index_song(title_index, match.song)
            added += 1

        return added

    def _contains_song(
        self,
        source_song: Song,
        target_songs: list[Song],
        title_index: dict[str, list[Song]],
    ) -> bool:
        title_key = self.matcher.title_key(source_song)
        for candidate in title_index.get(title_key, []):
            if self.matcher.is_match(source_song, candidate):
                return True

        # Fallback fuzzy search over target list when direct-title lookup misses.
        return self.matcher.find_best_match(source_song, target_songs, min_score=self.settings.match_threshold) is not None

    def _search_target_platform(self, source_song: Song, target_platform: Platform):
        if target_platform == "spotify":
            return self.spotify_client.search_best_match(source_song)
        if target_platform == "youtube":
            return self.youtube_client.search_best_match(source_song)
        raise ValueError(f"Unsupported platform: {target_platform}")

    def _add_to_target_platform(self, target_platform: Platform, song_id: str) -> None:
        if target_platform == "spotify":
            self.spotify_client.add_song_to_playlist(self.settings.spotify_playlist_id, song_id)
            return
        if target_platform == "youtube":
            self.youtube_client.add_song_to_playlist(self.settings.youtube_playlist_id, song_id)
            return
        raise ValueError(f"Unsupported platform: {target_platform}")

    def _build_title_index(self, songs: list[Song]) -> dict[str, list[Song]]:
        index: dict[str, list[Song]] = {}
        for song in songs:
            self._index_song(index, song)
        return index

    def _index_song(self, index: dict[str, list[Song]], song: Song) -> None:
        key = self.matcher.title_key(song)
        index.setdefault(key, []).append(song)
