import unittest

from app.matching.matcher import SongMatcher
from app.models import Song


class MatcherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.matcher = SongMatcher(threshold=0.8, strict_threshold=0.92)

    def _song(self, source: str, title: str, artist: str, song_id: str = "id") -> Song:
        return Song(id=song_id, title=title, artist=artist, source=source)

    def test_matches_accent_and_channel_suffix_noise(self) -> None:
        yt = self._song("youtube", "Ojala", "Silvio Rodriguez - Topic", "yt1")
        sp = self._song("spotify", "Ojalá", "Silvio Rodríguez", "sp1")
        self.assertTrue(self.matcher.is_match(yt, sp))

    def test_matches_title_with_official_lyric_noise(self) -> None:
        yt = self._song("youtube", "Butterflies (feat. AURORA) | Official Lyric Video", "Tom Odell", "yt1")
        sp = self._song("spotify", "Butterflies (feat. AURORA)", "Tom Odell", "sp1")
        self.assertTrue(self.matcher.is_match(yt, sp))

    def test_rejects_different_titles_with_same_artist(self) -> None:
        one = self._song("spotify", "Mystery of Love", "Sufjan Stevens", "sp1")
        two = self._song("youtube", "Love On The Brain", "Rihanna", "yt1")
        self.assertFalse(self.matcher.is_match(one, two))


if __name__ == "__main__":
    unittest.main()
