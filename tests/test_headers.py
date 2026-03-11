"""
Test dosyası örneği - Header işlemleri
"""

import pytest
import sys
from pathlib import Path

# src modülünü path'e ekle
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.headers import HeaderProcessor, normalize_headers


class TestHeaderProcessor:
    """Header işlemci testleri"""
    
    def test_normalize_basic_headers(self):
        """Temel header normalizasyonu"""
        headers = ["Seri Adı", "Grup (opsiyonel)", "Oyuncu Adı", "1/1", "1/1 İmzalı", "/5", "/5 İmzalı", "Base"]
        
        processor = HeaderProcessor(headers)
        
        assert not processor.has_errors()
        assert len(processor.variants) == 4  # 1/1, 1/1 İmzalı, /5, /5 İmzalı
        
    def test_detect_variant_pairs(self):
        """Variant çiftlerini tespit etme"""
        headers = ["Seri Adı", "Oyuncu Adı", "/25", "/25 İmzalı", "/67", "Base"]
        
        processor = HeaderProcessor(headers)
        pairs = processor.get_variant_pairs()
        
        assert 25 in pairs
        assert 67 in pairs
        assert pairs[25]['normal'] is not None
        assert pairs[25]['signed'] is not None
        assert pairs[67]['normal'] is not None
        assert pairs[67]['signed'] is None  # Sadece normal var
        
    def test_header_with_spaces(self):
        """Boşluklu header'lar"""
        headers = ["Seri Adı", " /5 ", "/5 İmzalı ", "Base"]
        
        processor = HeaderProcessor(headers)
        
        # Boşluklar temizlenmeli
        assert "/5" in processor.variants
        assert "/5 İmzalı" in processor.variants
        
    def test_missing_required_columns(self):
        """Eksik gerekli sütunlar"""
        headers = ["Grup", "/5", "Base"]  # Seri Adı ve Oyuncu Adı eksik
        
        processor = HeaderProcessor(headers)
        
        assert processor.has_errors()
        error_messages = [e['message'] for e in processor.errors]
        assert any("Seri Adı" in msg for msg in error_messages)
        assert any("Oyuncu Adı" in msg for msg in error_messages)
        
    def test_custom_denominators(self):
        """Özel paydalar"""
        headers = ["Seri Adı", "Oyuncu Adı", "/17", "/17 İmzalı", "/123", "Base"]
        
        processor = HeaderProcessor(headers)
        
        assert not processor.has_errors()
        pairs = processor.get_variant_pairs()
        assert 17 in pairs
        assert 123 in pairs
        assert pairs[17]['normal'].denominator == 17
        assert pairs[17]['signed'].denominator == 17
        
    def test_column_indices(self):
        """Sütun indeks alma"""
        headers = ["Seri Adı", "Grup", "Oyuncu Adı", "/5", "Base"]
        
        processor = HeaderProcessor(headers)
        
        assert processor.get_series_column_index() == 0
        assert processor.get_group_column_index() == 1
        assert processor.get_player_column_index() == 2
        assert processor.get_base_column_index() == 4


# Convenience function testleri
def test_normalize_headers_function():
    """normalize_headers fonksiyonu"""
    headers = ["Seri Adı", "Oyuncu Adı", "/25", "/25 İmzalı", "Base"]  # Eksik sütunları ekledik
    
    processor = normalize_headers(headers)
    
    assert isinstance(processor, HeaderProcessor)
    assert not processor.has_errors()


# Pytest fixtures
@pytest.fixture
def sample_headers():
    """Örnek header listesi"""
    return [
        "Seri Adı", "Grup (opsiyonel)", "Oyuncu Adı",
        "1/1", "1/1 İmzalı", 
        "/5", "/5 İmzalı",
        "/25", "/25 İmzalı",
        "/50", "/50 İmzalı",
        "Base"
    ]


@pytest.fixture
def header_processor(sample_headers):
    """HeaderProcessor instance"""
    return HeaderProcessor(sample_headers)


# Integration testleri
def test_full_header_processing(header_processor):
    """Tam header işleme"""
    
    assert not header_processor.has_errors()
    
    summary = header_processor.get_summary()
    assert summary['total_columns'] == 12
    assert summary['variant_columns'] == 8
    assert summary['has_group_column'] == True
    
    pairs = header_processor.get_variant_pairs()
    assert len(pairs) == 4  # 1, 5, 25, 50


if __name__ == "__main__":
    # Test çalıştırma
    pytest.main([__file__, "-v"])