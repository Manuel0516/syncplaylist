from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Iterable

from app.models import MatchedSong, Song

from .normalize import normalize_artist_name, normalize_title, split_artist_names


@dataclass(frozen=True)
class NormalizedSong:
    title: str
    artists: tuple[str, ...]


@lru_cache(maxsize=20_000)
def _normalize_song_fields(title: str, artist: str) -> NormalizedSong:
    normalized_title = normalize_title(title, artist_hint=artist)
    artists = tuple(split_artist_names(artist)) or (normalize_artist_name(artist),)
    artists = tuple(artist_name for artist_name in artists if artist_name)
    return NormalizedSong(title=normalized_title, artists=artists)


def _token_jaccard(left: str, right: str) -> float:
    left_tokens = set(left.split())
    right_tokens = set(right.split())
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def _string_similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    sequence = SequenceMatcher(None, left, right).ratio()
    jaccard = _token_jaccard(left, right)
    return (sequence * 0.65) + (jaccard * 0.35)


def _artist_similarity(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    if not left or not right:
        return 0.0

    best = 0.0
    for left_artist in left:
        for right_artist in right:
            best = max(best, _string_similarity(left_artist, right_artist))
    return best


class SongMatcher:
    """Robust song matching using normalized text and fuzzy similarity."""

    def __init__(self, *, threshold: float = 0.80, strict_threshold: float = 0.92) -> None:
        self.threshold = threshold
        self.strict_threshold = strict_threshold

    def _normalized(self, song: Song) -> NormalizedSong:
        return _normalize_song_fields(song.title, song.artist)

    def similarity(self, left: Song, right: Song) -> float:
        left_norm = self._normalized(left)
        right_norm = self._normalized(right)

        title_score = _string_similarity(left_norm.title, right_norm.title)
        artist_score = _artist_similarity(left_norm.artists, right_norm.artists)

        if title_score >= self.strict_threshold and artist_score >= 0.55:
            return 1.0

        score = (title_score * 0.80) + (artist_score * 0.20)
        if title_score < 0.65:
            score *= 0.85
        return score

    def is_match(self, left: Song, right: Song) -> bool:
        return self.similarity(left, right) >= self.threshold

    def find_best_match(
        self,
        source_song: Song,
        candidates: Iterable[Song],
        *,
        min_score: float | None = None,
    ) -> MatchedSong | None:
        threshold = self.threshold if min_score is None else min_score

        best: MatchedSong | None = None
        for candidate in candidates:
            score = self.similarity(source_song, candidate)
            if score < threshold:
                continue
            if best is None or score > best.score:
                best = MatchedSong(song=candidate, score=score)

        return best

    def title_key(self, song: Song) -> str:
        return self._normalized(song).title
