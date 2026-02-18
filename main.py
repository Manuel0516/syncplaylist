from __future__ import annotations

import argparse
import logging
import sys
import time

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.sync.engine import SyncEngine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sync a YouTube playlist with a Spotify playlist.")
    parser.add_argument("--once", action="store_true", help="Run one sync cycle and exit.")
    parser.add_argument("--dry-run", action="store_true", help="Compute differences without modifying playlists.")
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=None,
        help="Override sync interval in seconds when running continuously.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging.")
    return parser.parse_args()


def setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )


def run_once(engine: "SyncEngine", *, dry_run: bool, logger: logging.Logger) -> int:
    stats = engine.run(dry_run=dry_run)
    logger.info(
        "Sync completed: yt=%s sp=%s +sp=%s +yt=%s skipped(existing=%s, blacklist=%s) failed_searches=%s",
        stats.youtube_count,
        stats.spotify_count,
        stats.added_to_spotify,
        stats.added_to_youtube,
        stats.skipped_existing,
        stats.skipped_blacklist,
        stats.failed_searches,
    )
    return 0


def main() -> int:
    args = parse_args()
    setup_logging(args.verbose)
    logger = logging.getLogger("syncplaylist")

    from app.clients.spotify_client import SpotifyClient
    from app.clients.youtube_client import YouTubeClient
    from app.config import load_settings
    from app.matching.matcher import SongMatcher
    from app.storage.json_store import JsonStateStore
    from app.sync.engine import SyncEngine

    try:
        settings = load_settings()
    except ValueError as exc:
        logger.error("Configuration error: %s", exc)
        return 2

    matcher = SongMatcher(threshold=settings.match_threshold, strict_threshold=settings.strict_threshold)
    store = JsonStateStore(settings.state_dir, blacklist_file=settings.blacklist_file)

    spotify_client = SpotifyClient(settings=settings, matcher=matcher, logger=logger)
    youtube_client = YouTubeClient(settings=settings, matcher=matcher, logger=logger)
    engine = SyncEngine(
        settings=settings,
        matcher=matcher,
        store=store,
        spotify_client=spotify_client,
        youtube_client=youtube_client,
        logger=logger,
    )

    interval_seconds = args.interval_seconds or settings.sync_interval_seconds

    while True:
        try:
            run_once(engine, dry_run=args.dry_run, logger=logger)
        except KeyboardInterrupt:
            logger.info("Interrupted by user.")
            return 0
        except Exception:
            logger.exception("Sync cycle failed")
            if args.once:
                return 1

        if args.once:
            return 0

        logger.info("Sleeping for %s seconds before next sync cycle", interval_seconds)
        time.sleep(interval_seconds)


if __name__ == "__main__":
    sys.exit(main())
