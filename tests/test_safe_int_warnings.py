"""
Regression: safe_int hatalı veri için sessizce 0 döndürüyordu.
Excel'de "1a", "evet", "2.5.6" gibi geçersiz veri kart oluşmadan
yutuluyor ama uyarı verilmiyordu.

Yeni davranış: Geçersiz numerik hücre tespit edilirse warnings'a eklenir.
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from expand import RowExpander
from headers import HeaderProcessor


def _make_expander(rows):
    """Test için RowExpander oluşturucu"""
    df = pd.DataFrame(rows)
    headers = list(df.columns)
    hp = HeaderProcessor(headers)
    return RowExpander(df, hp)


class TestInvalidNumericWarning:
    """Geçersiz numerik hücreler warnings'a eklenmeli"""

    def test_garbage_in_variant_column_warns(self):
        expander = _make_expander([
            {
                "Seri Adı": "Test", "Oyuncu Adı": "Player",
                "/5": "abc",  # Geçersiz
                "/5 İmzalı": "", "Base": "",
            }
        ])
        result = expander.expand_all_rows()
        assert len(result.lines) == 0, "Geçersiz değerle kart oluşturulmamalı"
        invalid_warns = [w for w in result.warnings if w.get('type') == 'Invalid Number']
        assert len(invalid_warns) >= 1, (
            f"'abc' için 'Invalid Number' uyarısı bekleniyordu. "
            f"Aldığım warnings: {result.warnings}"
        )

    def test_garbage_in_base_column_warns(self):
        expander = _make_expander([
            {
                "Seri Adı": "Test", "Oyuncu Adı": "Player",
                "/5": "", "/5 İmzalı": "",
                "Base": "78x",  # Geçersiz
            }
        ])
        result = expander.expand_all_rows()
        invalid_warns = [w for w in result.warnings if w.get('type') == 'Invalid Number']
        assert len(invalid_warns) >= 1
        assert not any(line.variant_type == "Base" for line in result.lines)

    def test_empty_cell_no_warning(self):
        """Boş hücre eski davranıştaki gibi sessizce atlanmalı, uyarı yok"""
        expander = _make_expander([
            {
                "Seri Adı": "Test", "Oyuncu Adı": "Player",
                "/5": "", "/5 İmzalı": "", "Base": "",
            }
        ])
        result = expander.expand_all_rows()
        invalid_warns = [w for w in result.warnings if w.get('type') == 'Invalid Number']
        assert len(invalid_warns) == 0, (
            f"Boş hücre için uyarı verilmemeli. Aldığım: {invalid_warns}"
        )

    def test_valid_int_no_warning(self):
        expander = _make_expander([
            {
                "Seri Adı": "Test", "Oyuncu Adı": "Player",
                "/5": 3, "/5 İmzalı": "", "Base": "",
            }
        ])
        result = expander.expand_all_rows()
        invalid_warns = [w for w in result.warnings if w.get('type') == 'Invalid Number']
        assert len(invalid_warns) == 0
        # 3 kez doldurulduğu için /5 = 5 kart
        assert len([l for l in result.lines if l.denominator == 5]) == 5

    def test_zero_string_no_warning(self):
        """'0' geçerli, sıfır kart oluşturur, uyarı yok"""
        expander = _make_expander([
            {
                "Seri Adı": "Test", "Oyuncu Adı": "Player",
                "/5": "0", "/5 İmzalı": "", "Base": "",
            }
        ])
        result = expander.expand_all_rows()
        invalid_warns = [w for w in result.warnings if w.get('type') == 'Invalid Number']
        assert len(invalid_warns) == 0
        assert len(result.lines) == 0

    def test_warning_contains_cell_value_and_column(self):
        """Uyarı mesajı hangi hücre/sütun olduğunu belli etmeli"""
        expander = _make_expander([
            {
                "Seri Adı": "Test", "Oyuncu Adı": "Player",
                "/5": "garbage_xyz", "/5 İmzalı": "", "Base": "",
            }
        ])
        result = expander.expand_all_rows()
        invalid_warns = [w for w in result.warnings if w.get('type') == 'Invalid Number']
        assert any("garbage_xyz" in str(w.get('message', '')) for w in invalid_warns)
