# SyncPlaylist

Sync a YouTube playlist and a Spotify playlist in both directions with stronger matching and safer runtime behavior.

## What Changed

- Split the old single-file script into modules (`app/clients`, `app/matching`, `app/storage`, `app/sync`).
- Added robust track matching based on:
  - normalization (accents, apostrophes, noisy suffixes, `Topic/VEVO/Official` cleanup)
  - fuzzy similarity across title + artist
  - candidate scoring instead of first search hit
- Added retries with exponential backoff for Spotify/YouTube API calls.
- Added pagination for full playlist fetches.
- Added CLI flags: `--once`, `--dry-run`, `--interval-seconds`, `--verbose`.
- Added Docker support.

## Project Structure

```text
.
├── app/
│   ├── clients/       # Spotify + YouTube API integrations
│   ├── matching/      # normalization + fuzzy matching
│   ├── storage/       # JSON snapshots + blacklist loading
│   ├── sync/          # orchestration logic
│   ├── config.py
│   ├── models.py
│   └── retry.py
├── main.py            # CLI entrypoint
├── requirements.txt
├── Dockerfile
└── tests/
```

## Configuration

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
```

Required env vars:

- `SPOTIFY_CLIENT_ID`
- `SPOTIFY_CLIENT_SECRET`
- `SPOTIFY_PLAYLIST_ID`
- `YOUTUBE_PLAYLIST_ID`

Important files:

- `credentials.json`: Google OAuth client credentials
- `data/`: tokens + playlist snapshots (created automatically)
- `blacklist_songs.json`: blacklist titles

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py --once --dry-run --verbose
```

Then run without `--dry-run` to perform actual sync.

## Run with Docker

Build image:

```bash
docker build -t syncplaylist .
```

Run one dry cycle:

```bash
docker run --rm -it \
  -p 8888:8888 \
  --env-file .env \
  -e YOUTUBE_AUTH_MODE=console \
  -v "$PWD/credentials.json:/app/credentials.json:ro" \
  -v "$PWD/data:/app/data" \
  -v "$PWD/blacklist_songs.json:/app/blacklist_songs.json" \
  syncplaylist python main.py --once --dry-run --verbose
```

Run continuously:

```bash
docker run --rm -it \
  -p 8888:8888 \
  --env-file .env \
  -e YOUTUBE_AUTH_MODE=console \
  -v "$PWD/credentials.json:/app/credentials.json:ro" \
  -v "$PWD/data:/app/data" \
  -v "$PWD/blacklist_songs.json:/app/blacklist_songs.json" \
  syncplaylist
```

Or with Compose:

```bash
docker compose up --build
```

Notes:

- First OAuth run is interactive and stores tokens in `data/`.
- For Spotify callback flows, keep `SPOTIFY_REDIRECT_URI` aligned with your app configuration.

## Testing

```bash
python -m unittest discover -s tests
```

## Next Step (Optional DB)

When you want DB support, replace `app/storage/json_store.py` with a repository layer (SQLite/Postgres) and keep `app/sync/engine.py` unchanged.
