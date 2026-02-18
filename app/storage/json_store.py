from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from app.models import Platform, Song
from app.matching.normalize import normalize_title


class JsonStateStore:
    def __init__(self, state_dir: Path, *, blacklist_file: Path | None = None) -> None:
        self.state_dir = state_dir
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.spotify_snapshot_file = self.state_dir / "spotify_songs.json"
        self.youtube_snapshot_file = self.state_dir / "youtube_songs.json"
        self.blacklist_file = blacklist_file or self.state_dir / "blacklist_songs.json"

    def load_blacklist_titles(self) -> set[str]:
        records = self._read_json_list(self.blacklist_file)
        titles: set[str] = set()

        for item in records:
            if isinstance(item, str):
                title = item
            elif isinstance(item, dict):
                title = str(item.get("title") or "")
            else:
                continue

            normalized = normalize_title(title)
            if normalized:
                titles.add(normalized)

        return titles

    def load_snapshot(self, platform: Platform) -> list[Song]:
        file_path = self._snapshot_path(platform)
        payload = self._read_json_list(file_path)
        songs: list[Song] = []

        for item in payload:
            if not isinstance(item, dict):
                continue

            song_id = str(item.get("id") or "").strip()
            title = str(item.get("title") or "").strip()
            artist = str(item.get("artist") or "").strip()
            if not song_id or not title:
                continue

            songs.append(Song(id=song_id, title=title, artist=artist, source=platform))

        return songs

    def save_snapshot(self, platform: Platform, songs: list[Song]) -> None:
        path = self._snapshot_path(platform)
        payload = [
            {
                "title": song.title,
                "artist": song.artist,
                "id": song.id,
            }
            for song in songs
        ]
        self._write_json_atomic(path, payload)

    def _snapshot_path(self, platform: Platform) -> Path:
        if platform == "spotify":
            return self.spotify_snapshot_file
        if platform == "youtube":
            return self.youtube_snapshot_file
        raise ValueError(f"Unsupported platform: {platform}")

    def _read_json_list(self, file_path: Path) -> list[object]:
        if not file_path.exists():
            return []

        try:
            with file_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
                return payload if isinstance(payload, list) else []
        except json.JSONDecodeError:
            return []

    def _write_json_atomic(self, file_path: Path, payload: list[object]) -> None:
        parent = file_path.parent
        parent.mkdir(parents=True, exist_ok=True)

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=parent,
            prefix=f".{file_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            json.dump(payload, temp_file, ensure_ascii=False, indent=2)
            temp_name = temp_file.name

        os.replace(temp_name, file_path)
