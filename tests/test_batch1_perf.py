"""
Batch 1 (Quick Wins) performans-doğruluk testleri:

- B2: FileInfo.content_parts_set frozenset olarak doldurulmalı
- B5: normalize_for_matching @lru_cache ile cache'li olmalı, sonuç değişmemeli
- A6: iterdir tabanlı tarama .jpg ve .JPG dosyaları tek seferde bulmalı
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from images import (
    FileInfo,
    ImageMatcher,
    normalize_for_matching,
)


@pytest.fixture
def matcher(tmp_path):
    excel = tmp_path / "fake.xlsx"
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    m = ImageMatcher(excel, image_dir)
    m.known_text_denoms = set()
    return m


class TestB2ContentPartsSet:
    """FileInfo.content_parts_set — O(1) exact match için"""

    def test_set_matches_list_contents(self, matcher):
        info = matcher._parse_filename("efecan_karaca_classic_alanyaspor_s_1.jpg")
        assert isinstance(info.content_parts_set, frozenset)
        assert info.content_parts_set == frozenset(info.content_parts)

    def test_set_membership_works(self, matcher):
        info = matcher._parse_filename("john_smith_premier_alanyaspor_s_5.jpg")
        assert "john" in info.content_parts_set
        assert "smith" in info.content_parts_set
        assert "premier" in info.content_parts_set
        assert "nonexistent" not in info.content_parts_set


class TestB5NormalizeCache:
    """normalize_for_matching @lru_cache testi"""

    def test_cache_returns_same_result(self):
        a = normalize_for_matching("Classic Base")
        b = normalize_for_matching("Classic Base")
        assert a == b == "classic_base"

    def test_cache_info_increments_on_hit(self):
        normalize_for_matching.cache_clear()
        normalize_for_matching("Test String")
        info1 = normalize_for_matching.cache_info()
        normalize_for_matching("Test String")
        info2 = normalize_for_matching.cache_info()
        assert info2.hits > info1.hits, (
            "İkinci çağrıda cache hit olmalı, cache çalışmıyor olabilir"
        )

    def test_different_inputs_separate_entries(self):
        normalize_for_matching.cache_clear()
        normalize_for_matching("Foo")
        normalize_for_matching("Bar")
        info = normalize_for_matching.cache_info()
        assert info.misses >= 2

    def test_turkish_chars_still_normalized(self):
        # Cache'in correctness'i — Türkçe karakterler hala düzgün dönüşmeli
        assert normalize_for_matching("Şahin") == "sahin"
        assert normalize_for_matching("Müslüm Gürses") == "muslum_gurses"
        assert normalize_for_matching("Ağrı") == "agri"


class TestA6IterdirScan:
    """iterdir tabanlı tarama — case mixed dosyalar"""

    def test_mixed_case_extensions_found(self, tmp_path):
        excel = tmp_path / "fake.xlsx"
        image_dir = tmp_path / "images"
        image_dir.mkdir()
        (image_dir / "player1_series_5.jpg").touch()
        (image_dir / "player2_series_5.JPG").touch()
        (image_dir / "player3_series_5.JPEG").touch()
        (image_dir / "player4_series_5.png").touch()
        (image_dir / "player5_series_5.PNG").touch()
        (image_dir / "ignored.txt").touch()
        (image_dir / "ignored.bmp").touch()

        m = ImageMatcher(excel, image_dir)
        m._scan_and_parse_images()

        names = sorted(p.name for p in m.image_files)
        assert names == [
            "player1_series_5.jpg",
            "player2_series_5.JPG",
            "player3_series_5.JPEG",
            "player4_series_5.png",
            "player5_series_5.PNG",
        ]

    def test_no_duplicates_when_real_collision(self, tmp_path):
        # Tek dosya, iki kere taranmamalı
        excel = tmp_path / "fake.xlsx"
        image_dir = tmp_path / "images"
        image_dir.mkdir()
        (image_dir / "card_1.jpg").touch()

        m = ImageMatcher(excel, image_dir)
        m._scan_and_parse_images()
        assert len(m.image_files) == 1

    def test_subdirectories_ignored(self, tmp_path):
        excel = tmp_path / "fake.xlsx"
        image_dir = tmp_path / "images"
        image_dir.mkdir()
        (image_dir / "real_card_1.jpg").touch()
        sub = image_dir / "subfolder"
        sub.mkdir()
        (sub / "should_not_match_5.jpg").touch()

        m = ImageMatcher(excel, image_dir)
        m._scan_and_parse_images()
        names = [p.name for p in m.image_files]
        assert names == ["real_card_1.jpg"]
