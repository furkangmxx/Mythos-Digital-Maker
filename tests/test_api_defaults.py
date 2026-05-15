"""
Public API default değer testleri.

strict_mode'un varsayılan değeri ImageMatcher constructor ve public
fonksiyonlarda tutarlı olmalı — tüm caller'lar False ile çağırıyor.
"""

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import images


class TestStrictModeDefault:
    """strict_mode default değeri tutarlılığı"""

    def test_image_matcher_default_strict_mode_false(self):
        sig = inspect.signature(images.ImageMatcher.__init__)
        assert sig.parameters["strict_mode"].default is False, (
            "ImageMatcher.__init__ strict_mode default False olmalı"
        )

    def test_validate_matching_preview_default_strict_mode_false(self):
        sig = inspect.signature(images.validate_matching_preview)
        assert sig.parameters["strict_mode"].default is False

    def test_process_image_mapping_default_strict_mode_false(self):
        sig = inspect.signature(images.process_image_mapping)
        assert sig.parameters["strict_mode"].default is False

    def test_instance_default_attribute_is_false(self, tmp_path):
        excel = tmp_path / "fake.xlsx"
        image_dir = tmp_path / "images"
        image_dir.mkdir()
        m = images.ImageMatcher(excel, image_dir)
        assert m.strict_mode is False
