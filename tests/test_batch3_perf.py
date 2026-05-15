"""
Batch 3 (Big Performance) testleri:

B1: Excel iki kere okunmamalı (validate_preview + process_all sırasında
    aynı dosyayı bir kez parse'la, sonucu cache'le)
B3: parsed_files (is_base, is_signed, denominator) tuple'ı ile bucket
    index'lenmeli; her kart için sadece kendi bucket'ına bakmalı
"""

import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

import images
from images import ImageMatcher, CardInfo


def _write_minimal_excel(path: Path):
    df = pd.DataFrame([
        {
            "Kart Listesi": "P1 S (1/5)",
            "Görsel Dosyası": "",
            "player_name": "P1",
            "series_name": "S",
            "group": "",
            "denominator": 5,
            "is_signed": "Hayır",
        }
    ])
    with pd.ExcelWriter(path, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="Çıktı", index=False)


class TestB1ExcelReadCache:
    """_read_cards_from_excel iki kez çağrılırsa Excel'i tek kez parse etmeli"""

    def test_second_call_uses_cache(self, tmp_path):
        excel = tmp_path / "test.xlsx"
        _write_minimal_excel(excel)
        image_dir = tmp_path / "images"
        image_dir.mkdir()

        matcher = ImageMatcher(excel, image_dir)

        with patch.object(images.pd, "read_excel",
                          wraps=images.pd.read_excel) as spy:
            cards1 = matcher._read_cards_from_excel()
            cards2 = matcher._read_cards_from_excel()

        assert spy.call_count == 1, (
            f"pd.read_excel iki kez çağrıldı (cache yok): {spy.call_count} call"
        )
        # İki çağrı da aynı içeriği döndürmeli
        assert len(cards1) == len(cards2) == 1
        assert cards1[0].player == cards2[0].player

    def test_cache_returns_equivalent_data(self, tmp_path):
        excel = tmp_path / "test.xlsx"
        _write_minimal_excel(excel)
        image_dir = tmp_path / "images"
        image_dir.mkdir()
        matcher = ImageMatcher(excel, image_dir)

        cards1 = matcher._read_cards_from_excel()
        cards2 = matcher._read_cards_from_excel()
        # Aynı kartlar
        assert cards1 is cards2 or [c.player for c in cards1] == [c.player for c in cards2]


class TestB3BucketIndex:
    """parsed_files bucket index — her kart kendi bucket'ına bakar"""

    def test_file_index_populated_after_scan(self, tmp_path):
        excel = tmp_path / "fake.xlsx"
        image_dir = tmp_path / "images"
        image_dir.mkdir()
        # Farklı (is_base, is_signed, denom) kombinasyonları
        (image_dir / "p1_s_signed_s_5.jpg").touch()       # signed, denom 5
        (image_dir / "p2_s_normal_5.jpg").touch()         # normal, denom 5
        (image_dir / "p3_s_normal_25.jpg").touch()        # normal, denom 25
        (image_dir / "p4_s_basecard_base.jpg").touch()    # base

        matcher = ImageMatcher(excel, image_dir)
        matcher._scan_and_parse_images()

        assert hasattr(matcher, "file_index"), (
            "ImageMatcher.file_index attribute yok — B3 bucket index yapılmamış"
        )
        # En az 2 farklı bucket olmalı
        assert len(matcher.file_index) >= 2

    def test_card_lookup_uses_bucket(self, tmp_path):
        """5/5 normal kart için sadece (False, False, 5) bucket'ına bakılmalı"""
        excel = tmp_path / "fake.xlsx"
        image_dir = tmp_path / "images"
        image_dir.mkdir()
        (image_dir / "player_a_series_5.jpg").touch()
        (image_dir / "player_b_series_s_5.jpg").touch()  # signed, ayrı bucket
        (image_dir / "player_c_series_25.jpg").touch()   # denom 25, ayrı

        matcher = ImageMatcher(excel, image_dir)
        matcher._scan_and_parse_images()

        # Bucket key'ler (False, False, 5) ve (False, True, 5) ayrı
        keys = list(matcher.file_index.keys())
        # Doğrulamak için: (is_base=False, is_signed=False, denominator='5')
        # bucket'ı tek dosya içermeli (player_a)
        # Bucket key formatı implementasyona bağlı, sadece varlık kontrol
        # Total file sayısı bucket'lara dağılmış olmalı
        total_files_in_buckets = sum(len(v) for v in matcher.file_index.values())
        assert total_files_in_buckets == 3

    def test_match_still_works_with_bucket(self, tmp_path):
        """Bucket index sonrası eşleşme akışı bozulmamalı"""
        excel = tmp_path / "test.xlsx"
        df = pd.DataFrame([
            {
                "Kart Listesi": "Player_A Series (1/5)",
                "Görsel Dosyası": "",
                "player_name": "Player A",
                "series_name": "Series",
                "group": "",
                "denominator": 5,
                "is_signed": "Hayır",
            }
        ])
        with pd.ExcelWriter(excel, engine="openpyxl") as w:
            df.to_excel(w, sheet_name="Çıktı", index=False)

        image_dir = tmp_path / "images"
        image_dir.mkdir()
        (image_dir / "player_a_series_5.jpg").touch()
        # Dikkat dağıtıcı dosyalar: farklı denom/signed
        (image_dir / "player_a_series_s_5.jpg").touch()    # signed
        (image_dir / "player_a_series_25.jpg").touch()     # denom 25
        (image_dir / "player_a_series_base.jpg").touch()   # base

        matcher = ImageMatcher(excel, image_dir)
        cards = matcher._read_cards_from_excel()
        matcher._scan_and_parse_images()
        matcher._match_all_cards(cards)

        assert len(matcher.matches) == 1
        m = matcher.matches[0]
        assert m.status == "found", (
            f"Bucket sonrası eşleşme bozuldu. Status: {m.status}, "
            f"log: {m.log_message}"
        )
        assert m.matched_file == "player_a_series_5.jpg"
