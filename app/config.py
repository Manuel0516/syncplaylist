from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv(dotenv_path: Path) -> None:
    if not dotenv_path.exists():
        return

    for raw_line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value or default


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be an integer.") from exc


def _env_float(name: str, default: float) -> float:
    value = _env(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"Environment variable {name} must be a float.") from exc


@dataclass(frozen=True)
class Settings:
    spotify_client_id: str
    spotify_client_secret: str
    spotify_redirect_uri: str
    spotify_playlist_id: str
    youtube_playlist_id: str
    google_credentials_file: Path
    blacklist_file: Path
    spotify_token_file: Path
    youtube_token_file: Path
    state_dir: Path
    sync_interval_seconds: int
    spotify_search_limit: int
    youtube_search_limit: int
    match_threshold: float
    strict_threshold: float
    youtube_auth_mode: str


SPOTIFY_SCOPE = "playlist-read-private playlist-read-collaborative playlist-modify-private playlist-modify-public"
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]


def load_settings() -> Settings:
    _load_dotenv(Path(".env"))

    missing = [
        name
        for name in (
            "SPOTIFY_CLIENT_ID",
            "SPOTIFY_CLIENT_SECRET",
            "SPOTIFY_PLAYLIST_ID",
            "YOUTUBE_PLAYLIST_ID",
        )
        if not _env(name)
    ]
    if missing:
        joined = ", ".join(sorted(missing))
        raise ValueError(f"Missing required environment variables: {joined}")

    state_dir = Path(_env("STATE_DIR", "data") or "data")
    state_dir.mkdir(parents=True, exist_ok=True)

    spotify_token_file = Path(_env("SPOTIFY_TOKEN_FILE", str(state_dir / "token_spotify.cache")) or state_dir / "token_spotify.cache")
    youtube_token_file = Path(_env("YOUTUBE_TOKEN_FILE", str(state_dir / "token_google.pickle")) or state_dir / "token_google.pickle")

    credentials_file = Path(_env("GOOGLE_CREDENTIALS_FILE", "credentials.json") or "credentials.json")
    default_blacklist = Path("blacklist_songs.json")
    blacklist_value = _env(
        "BLACKLIST_FILE",
        str(default_blacklist if default_blacklist.exists() else state_dir / "blacklist_songs.json"),
    ) or str(default_blacklist if default_blacklist.exists() else state_dir / "blacklist_songs.json")
    blacklist_file = Path(blacklist_value)

    return Settings(
        spotify_client_id=_env("SPOTIFY_CLIENT_ID") or "",
        spotify_client_secret=_env("SPOTIFY_CLIENT_SECRET") or "",
        spotify_redirect_uri=_env("SPOTIFY_REDIRECT_URI", "http://localhost:8888/callback") or "http://localhost:8888/callback",
        spotify_playlist_id=_env("SPOTIFY_PLAYLIST_ID") or "",
        youtube_playlist_id=_env("YOUTUBE_PLAYLIST_ID") or "",
        google_credentials_file=credentials_file,
        blacklist_file=blacklist_file,
        spotify_token_file=spotify_token_file,
        youtube_token_file=youtube_token_file,
        state_dir=state_dir,
        sync_interval_seconds=_env_int("SYNC_INTERVAL_SECONDS", 24 * 60 * 60),
        spotify_search_limit=max(1, min(50, _env_int("SPOTIFY_SEARCH_LIMIT", 8))),
        youtube_search_limit=max(1, min(50, _env_int("YOUTUBE_SEARCH_LIMIT", 8))),
        match_threshold=max(0.5, min(1.0, _env_float("MATCH_THRESHOLD", 0.80))),
        strict_threshold=max(0.5, min(1.0, _env_float("STRICT_MATCH_THRESHOLD", 0.92))),
        youtube_auth_mode=(_env("YOUTUBE_AUTH_MODE", "auto") or "auto").lower(),
    )
