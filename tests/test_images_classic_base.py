"""
Regression: "Classic Base" gibi seri adında "base" geçen kartların
/1, /5, /25 İmzalı varyant görselleri eşleşmiyordu.

Senaryo:
- Görsel: efecan_karaca_classic_base_alanyaspor_s_1.jpg
- Excel'de seri: "Classic Base", grup: "Alanyaspor", /1 İmzalı
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

# images.py iç repo'nun root'unda
sys.path.insert(0, str(Path(__file__).parent.parent))

from images import ImageMatcher


@pytest.fixture
def matcher_with_classic_base_known_denoms(tmp_path):
    """Excel'i olmayan bir matcher — sadece parser/eşleştirme mantığı testi"""
    excel = tmp_path / "fake.xlsx"
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    matcher = ImageMatcher(excel, image_dir, strict_mode=True)
    # Excel'den okunmuş olsaydı text denom yoktu (/1 sayısal)
    matcher.known_text_denoms = set()
    return matcher


class TestParseFilenameBaseInSeriesName:
    """Dosya parser'ı: seri adında 'base' geçen dosyalar"""

    def test_base_in_middle_is_not_base_card(self, matcher_with_classic_base_known_denoms):
        """
        Dosya: efecan_karaca_classic_base_alanyaspor_s_1.jpg
        Buradaki 'base' seri adının ('Classic Base') parçası — base kart değil.
        Beklenen: is_base=False, denominator=1, is_signed=True
        """
        m = matcher_with_classic_base_known_denoms
        info = m._parse_filename("efecan_karaca_classic_base_alanyaspor_s_1.jpg")

        assert info.is_base is False, (
            f"'base' seri adının parçası, base kart değil. "
            f"Ama is_base={info.is_base} geldi."
        )
        assert info.denominator == 1, (
            f"Sondaki _1 denominator olarak çıkarılmalı, geldi: {info.denominator}"
        )
        assert info.is_signed is True
        # 'base' kelimesi content_parts'ta DA olmalı (seri adının parçası)
        assert "base" in info.content_parts, (
            f"'base' seri adının parçası, content_parts'ta kalmalı. "
            f"Şu an: {info.content_parts}"
        )

    def test_true_base_card_at_end_is_base(self, matcher_with_classic_base_known_denoms):
        """
        Dosya: efecan_karaca_classic_base.jpg (sondaki _base = gerçek base işareti)
        Beklenen: is_base=True
        """
        m = matcher_with_classic_base_known_denoms
        info = m._parse_filename("efecan_karaca_classic_base.jpg")
        assert info.is_base is True

    def test_true_base_card_with_sequence(self, matcher_with_classic_base_known_denoms):
        """
        Dosya: efecan_karaca_classic_base_5.jpg
        Sondaki _base_<sayı> hala base kart (sequence numarası).
        """
        m = matcher_with_classic_base_known_denoms
        info = m._parse_filename("efecan_karaca_classic_base_5.jpg")
        assert info.is_base is True

    def test_base_in_middle_with_true_base_at_end(self, matcher_with_classic_base_known_denoms):
        """
        Dosya: efecan_karaca_classic_base_alanyaspor_base.jpg
        Seri adında "base" geçiyor AMA sonda da _base var → gerçek base kart.
        """
        m = matcher_with_classic_base_known_denoms
        info = m._parse_filename("efecan_karaca_classic_base_alanyaspor_base.jpg")
        assert info.is_base is True


class TestReadCardsIsBaseFromExcel:
    """Excel'deki is_base tespiti: 'base' kelimesi sadece sondaysa base sayılmalı"""

    @staticmethod
    def _write_excel(path: Path, raw_text: str, denominator, signed: str = "Evet"):
        """Çıktı sheet'i ile Excel oluştur"""
        df = pd.DataFrame([{
            "Kart Listesi": raw_text,
            "Görsel Dosyası": "",
            "player_name": "Efecan Karaca",
            "series_name": "Classic Base",
            "group": "Alanyaspor",
            "denominator": denominator,
            "is_signed": signed,
        }])
        with pd.ExcelWriter(path, engine="openpyxl") as w:
            df.to_excel(w, sheet_name="Çıktı", index=False)

    def test_classic_base_variant_is_not_base_card(self, tmp_path):
        """
        Seri 'Classic Base' ama satır /1 İmzalı varyantı.
        Raw text: "Efecan Karaca Classic Base Alanyaspor (1/1) İmzalı"
        Sonu " base" ile bitmiyor → is_base=False olmalı.
        """
        excel = tmp_path / "test.xlsx"
        self._write_excel(
            excel,
            "Efecan Karaca Classic Base Alanyaspor (1/1) İmzalı",
            denominator=1,
        )
        image_dir = tmp_path / "images"
        image_dir.mkdir()

        matcher = ImageMatcher(excel, image_dir, strict_mode=True)
        cards = matcher._read_cards_from_excel()

        assert len(cards) == 1
        assert cards[0].is_base is False, (
            f"'/1 İmzalı' varyantı base kart değil, ama is_base={cards[0].is_base} geldi. "
            f"raw_text: {cards[0].raw_text}"
        )

    def test_actual_base_card_ends_with_base(self, tmp_path):
        """
        Gerçek base satır: "Efecan Karaca Classic Base Alanyaspor Base"
        Sonu " base" ile bitiyor → is_base=True.
        """
        excel = tmp_path / "test.xlsx"
        self._write_excel(
            excel,
            "Efecan Karaca Classic Base Alanyaspor Base",
            denominator=78,
            signed="Hayır",
        )
        image_dir = tmp_path / "images"
        image_dir.mkdir()

        matcher = ImageMatcher(excel, image_dir, strict_mode=True)
        cards = matcher._read_cards_from_excel()

        assert len(cards) == 1
        assert cards[0].is_base is True


class TestEndToEndMatchClassicBase:
    """Uçtan uca: dosya + Excel'i kur, eşleşmeyi doğrula"""

    def test_classic_base_one_of_one_signed_matches(self, tmp_path):
        """
        Görsel: efecan_karaca_classic_base_alanyaspor_s_1.jpg
        Excel:  Classic Base / Alanyaspor / /1 İmzalı / Efecan Karaca
        Beklenen: status='found'
        """
        # Excel
        df = pd.DataFrame([{
            "Kart Listesi": "Efecan Karaca Classic Base Alanyaspor (1/1) İmzalı",
            "Görsel Dosyası": "",
            "player_name": "Efecan Karaca",
            "series_name": "Classic Base",
            "group": "Alanyaspor",
            "denominator": 1,
            "is_signed": "Evet",
        }])
        excel = tmp_path / "test.xlsx"
        with pd.ExcelWriter(excel, engine="openpyxl") as w:
            df.to_excel(w, sheet_name="Çıktı", index=False)

        # Görsel (boş dosya yeterli — parser sadece adı kullanıyor)
        image_dir = tmp_path / "images"
        image_dir.mkdir()
        (image_dir / "efecan_karaca_classic_base_alanyaspor_s_1.jpg").touch()

        matcher = ImageMatcher(excel, image_dir, strict_mode=True)
        cards = matcher._read_cards_from_excel()
        matcher._scan_and_parse_images()
        matcher._match_all_cards(cards)

        assert len(matcher.matches) == 1
        match = matcher.matches[0]
        assert match.status == "found", (
            f"Eşleşme bekleniyordu. Status: {match.status}, "
            f"log: {match.log_message}"
        )
        assert match.matched_file == "efecan_karaca_classic_base_alanyaspor_s_1.jpg"
