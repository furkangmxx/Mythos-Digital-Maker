"""
Regression: is_signed tespiti `_s_` substring kontrolüyle yapılıyordu —
oyuncu adında orta s harfi varsa yanlış pozitif veriyordu.

Doğru davranış: _s işaretini denominator/text-denom/base'den hemen
önceki konumunda ara. Sadece "bir yerde _s_ var" yetmez.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from images import ImageMatcher


@pytest.fixture
def matcher_numeric_only(tmp_path):
    """Sadece numerik denom kullanan matcher (text denom yok)"""
    excel = tmp_path / "fake.xlsx"
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    m = ImageMatcher(excel, image_dir)
    m.known_text_denoms = set()
    return m


@pytest.fixture
def matcher_with_x_denom(tmp_path):
    """Text denom "x" tanımlı matcher"""
    excel = tmp_path / "fake.xlsx"
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    m = ImageMatcher(excel, image_dir)
    m.known_text_denoms = {"x"}
    return m


class TestIsSignedTruePositives:
    """Gerçek imzalı dosyalar — is_signed=True olmalı"""

    def test_numeric_denom_signed(self, matcher_numeric_only):
        info = matcher_numeric_only._parse_filename("john_smith_classic_s_5.jpg")
        assert info.is_signed is True
        assert info.denominator == 5

    def test_one_of_one_signed(self, matcher_numeric_only):
        info = matcher_numeric_only._parse_filename("john_smith_classic_s_1.jpg")
        assert info.is_signed is True
        assert info.denominator == 1

    def test_classic_base_one_of_one_signed(self, matcher_numeric_only):
        # Classic Base senaryosu regresyon kontrolü
        info = matcher_numeric_only._parse_filename(
            "efecan_karaca_classic_base_alanyaspor_s_1.jpg"
        )
        assert info.is_signed is True
        assert info.denominator == 1
        assert info.is_base is False

    def test_text_denom_signed(self, matcher_with_x_denom):
        info = matcher_with_x_denom._parse_filename("john_smith_classic_x_s_1.jpg")
        assert info.is_signed is True
        assert info.denominator == "X"


class TestIsSignedFalsePositives:
    """Orta-s yanlış pozitif vakaları — is_signed=False olmalı"""

    def test_middle_s_in_player_name_not_signed(self, matcher_numeric_only):
        # "Jane S Doe" gibi orta-adı tek harf "S" olan oyuncu
        info = matcher_numeric_only._parse_filename("jane_s_doe_classic_5.jpg")
        assert info.is_signed is False, (
            f"'_s_' player adının ortasında, imza markeri değil. "
            f"is_signed={info.is_signed} yanlış."
        )
        assert info.denominator == 5

    def test_middle_s_with_one_of_one(self, matcher_numeric_only):
        info = matcher_numeric_only._parse_filename("jane_s_doe_classic_1.jpg")
        assert info.is_signed is False

    def test_no_signed_marker(self, matcher_numeric_only):
        info = matcher_numeric_only._parse_filename("john_smith_classic_5.jpg")
        assert info.is_signed is False

    def test_text_denom_unsigned(self, matcher_with_x_denom):
        info = matcher_with_x_denom._parse_filename("john_smith_classic_x.jpg")
        assert info.is_signed is False


class TestIsSignedContentPartsCorrect:
    """is_signed sonrası content_parts içinde 's' bırakılmamalı"""

    def test_signed_player_with_middle_s_keeps_s(self, matcher_numeric_only):
        """Signed + ortada S harfli oyuncu: hem signed True, hem 's' content'te"""
        info = matcher_numeric_only._parse_filename("jane_s_doe_classic_s_5.jpg")
        assert info.is_signed is True
        assert "s" in info.content_parts  # Player adının S'i kalmalı
        assert "jane" in info.content_parts
        assert "doe" in info.content_parts
        assert "classic" in info.content_parts
        assert info.denominator == 5

    def test_unsigned_middle_s_keeps_s(self, matcher_numeric_only):
        """Unsigned + ortada S harfli oyuncu: signed False, 's' yine kalır"""
        info = matcher_numeric_only._parse_filename("jane_s_doe_classic_5.jpg")
        assert info.is_signed is False
        assert "s" in info.content_parts
