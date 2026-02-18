from __future__ import annotations

import re
import unicodedata


APOSTROPHE_MAPPING = str.maketrans(
    {
        "’": "'",
        "‘": "'",
        "´": "'",
        "`": "'",
        "‛": "'",
        "＇": "'",
        "ʻ": "'",
        "ʼ": "'",
        "ʽ": "'",
        "ʾ": "'",
        "ʿ": "'",
        "ˈ": "'",
    }
)


NOISE_TERMS = {
    "official",
    "video",
    "audio",
    "lyrics",
    "lyric",
    "hd",
    "4k",
    "topic",
    "visualizer",
    "remaster",
    "remastered",
    "version",
    "live",
    "karaoke",
    "instrumental",
    "extended",
    "speed up",
    "sped up",
    "slowed",
    "nightcore",
    "bass boosted",
    "clip",
    "teaser",
}


ARTIST_SUFFIX_TERMS = {
    "vevo",
    "topic",
    "official",
    "music",
    "records",
    "recordings",
    "channel",
    "tv",
}


COLLAB_SPLIT_RE = re.compile(r"\s*(?:,|&|\+|/| x | and | y | e )\s*", re.IGNORECASE)
FEATURE_RE = re.compile(r"\b(?:feat\.?|ft\.?|featuring|with)\b", re.IGNORECASE)
MULTISPACE_RE = re.compile(r"\s+")


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_basic(text: str) -> str:
    text = strip_accents(text.translate(APOSTROPHE_MAPPING)).lower().strip()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = MULTISPACE_RE.sub(" ", text).strip()
    return text


def _is_noise_segment(segment: str) -> bool:
    normalized = normalize_basic(segment)
    return any(term in normalized for term in NOISE_TERMS)


def _strip_bracket_noise(title: str) -> str:
    def replace_round(match: re.Match[str]) -> str:
        content = match.group(1)
        return " " if _is_noise_segment(content) else f" {content} "

    def replace_square(match: re.Match[str]) -> str:
        content = match.group(1)
        return " " if _is_noise_segment(content) else f" {content} "

    title = re.sub(r"\((.*?)\)", replace_round, title)
    title = re.sub(r"\[(.*?)\]", replace_square, title)
    return title


def normalize_artist_name(artist: str) -> str:
    artist = artist or ""
    artist = artist.translate(APOSTROPHE_MAPPING)
    artist = re.sub(r"\s*[-–]\s*topic$", "", artist, flags=re.IGNORECASE)
    artist = FEATURE_RE.split(artist, maxsplit=1)[0]

    normalized = normalize_basic(artist)
    tokens = normalized.split()
    while tokens and tokens[-1] in ARTIST_SUFFIX_TERMS:
        tokens.pop()
    return " ".join(tokens)


def split_artist_names(artist: str) -> list[str]:
    normalized = normalize_artist_name(artist)
    if not normalized:
        return []

    pieces: list[str] = []
    for chunk in COLLAB_SPLIT_RE.split(normalized):
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk in ARTIST_SUFFIX_TERMS:
            continue
        pieces.append(chunk)

    deduped: list[str] = []
    seen: set[str] = set()
    for artist_name in pieces or [normalized]:
        if artist_name not in seen:
            deduped.append(artist_name)
            seen.add(artist_name)
    return deduped


def normalize_title(title: str, artist_hint: str = "") -> str:
    title = (title or "").translate(APOSTROPHE_MAPPING)

    if " - " in title and artist_hint:
        maybe_artist, maybe_title = title.split(" - ", 1)
        if normalize_artist_name(maybe_artist) == normalize_artist_name(artist_hint):
            title = maybe_title

    title = _strip_bracket_noise(title)
    title = FEATURE_RE.split(title, maxsplit=1)[0]

    # Remove trailing metadata blocks often appended by uploaders.
    title = re.sub(
        r"\s*[-–|:]\s*(official|lyrics?|audio|video|visualizer|topic|remaster(?:ed)?|live|version).*$",
        "",
        title,
        flags=re.IGNORECASE,
    )

    normalized = normalize_basic(title)
    return normalized


def text_tokens(text: str) -> set[str]:
    return {token for token in normalize_basic(text).split() if token}
