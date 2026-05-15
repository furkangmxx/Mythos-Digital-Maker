"""
Modül-seviyesi yan etki testleri.

Tarihçe: sorters.py'da modül scope'unda PyICU import ve emoji print vardı —
Windows cp1254 console encoding'inde UnicodeEncodeError ile crash ediyordu.
Bu testler modüllerin import edildiğinde sessiz olduğunu doğrular.
"""

import sys
from pathlib import Path

# images.py iç repo'nun root'unda
sys.path.insert(0, str(Path(__file__).parent.parent))


def _fresh_import(module_name, capsys):
    """Modülü kaldırıp tekrar import et, stdout/stderr yakala"""
    sys.modules.pop(module_name, None)
    __import__(module_name)
    return capsys.readouterr()


class TestModuleLevelSideEffects:
    """İmport sırasında modüller stdout/stderr'e yazmamalı"""

    def test_sorters_import_silent(self, capsys):
        """sorters.py: PyICU detection module-level print yapıyordu, artık __main__ içinde"""
        captured = _fresh_import("sorters", capsys)
        assert captured.out == "", (
            f"sorters import sırasında stdout'a yazdı: {captured.out!r}. "
            f"Module-level print veya emoji çıktısı olmamalı."
        )
        assert captured.err == "", (
            f"sorters import sırasında stderr'e yazdı: {captured.err!r}"
        )

    def test_images_import_silent(self, capsys):
        captured = _fresh_import("images", capsys)
        assert captured.out == ""
        assert captured.err == ""

    def test_expand_import_silent(self, capsys):
        captured = _fresh_import("expand", capsys)
        assert captured.out == ""
        assert captured.err == ""

    def test_headers_import_silent(self, capsys):
        captured = _fresh_import("headers", capsys)
        assert captured.out == ""
        assert captured.err == ""
