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

Optional auth vars:

- `YOUTUBE_AUTH_MODE` (`auto`, `console`, `local`; default `auto`)
- `YOUTUBE_AUTH_PORT` (default `8888`; set to `0` for random port)
- `YOUTUBE_AUTH_BIND_ADDR` (default `127.0.0.1`; use `0.0.0.0` in Docker)

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
  -e YOUTUBE_AUTH_BIND_ADDR=0.0.0.0 \
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
  -e YOUTUBE_AUTH_BIND_ADDR=0.0.0.0 \
  -v "$PWD/credentials.json:/app/credentials.json:ro" \
  -v "$PWD/data:/app/data" \
  -v "$PWD/blacklist_songs.json:/app/blacklist_songs.json" \
  syncplaylist
```

Or with Compose:

```bash
docker compose up --build
```

## First-Time OAuth Login (Docker)

Use this flow the first time so you can complete both Google and Spotify auth in the terminal:

```bash
docker compose down
docker compose run --rm --service-ports syncplaylist python main.py --once --verbose
```

Steps:

1. Open the Google auth URL shown in logs and approve access.
2. If Google redirects to `http://localhost:8888/...`, let it finish; token is saved to `data/token_google.pickle`.
3. Open the Spotify auth URL and approve access.
4. If the browser shows `ERR_SOCKET_NOT_CONNECTED` on `http://127.0.0.1:8888/callback?...`, copy that full URL.
5. Paste the full callback URL into the terminal when prompted: `Enter the URL you were redirected to:`.
6. After success, start normally with `docker compose up --build`.

Notes:

- First OAuth run is interactive and stores tokens in `data/`.
- Google OAuth loopback callback uses `http://localhost:<YOUTUBE_AUTH_PORT>/` (default port `8888`).
  If your environment only exposes specific ports (for example Docker), keep this fixed and mapped.
  In Docker also set `YOUTUBE_AUTH_BIND_ADDR=0.0.0.0` so host callbacks can reach the container.
- For Spotify callback flows, keep `SPOTIFY_REDIRECT_URI` aligned with your app configuration.
  Use `http://127.0.0.1:8888/callback` (not `localhost`) and whitelist that exact URI in Spotify Dashboard.
  In Docker/manual auth, the callback page may show a connection error; copy that full callback URL and paste it into the terminal when prompted.

## Testing

```bash
python -m unittest discover -s tests
```

## Next Step (Optional DB)

When you want DB support, replace `app/storage/json_store.py` with a repository layer (SQLite/Postgres) and keep `app/sync/engine.py` unchanged.
