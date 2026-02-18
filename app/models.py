from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal


Platform = Literal["spotify", "youtube"]


@dataclass(frozen=True)
class Song:
    """Platform-agnostic representation of a track in a playlist."""

    id: str
    title: str
    artist: str
    source: Platform
    raw_title: str | None = None
    raw_artist: str | None = None


@dataclass
class SyncStats:
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    youtube_count: int = 0
    spotify_count: int = 0
    added_to_spotify: int = 0
    added_to_youtube: int = 0
    skipped_blacklist: int = 0
    skipped_existing: int = 0
    failed_searches: int = 0


@dataclass(frozen=True)
class MatchedSong:
    song: Song
    score: float
