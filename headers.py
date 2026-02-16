"""
MythosCards Exporter - Header Operations
Excel başlık normalizasyonu ve variant tespiti
"""

import re
import logging
from typing import List, Dict, Tuple, Set, Optional, Union
from dataclasses import dataclass

from utils import HeaderError, normalize_text

logger = logging.getLogger(__name__)


@dataclass
class VariantInfo:
    """Variant bilgileri"""
    column_name: str
    denominator: Union[int, str]  # 5, 25 veya "X", "Short Print"
    is_signed: bool
    display_name: str


class HeaderProcessor:
    """Header işleme sınıfı"""
    
    # Standart sütunlar
    REQUIRED_COLUMNS = {
        "Seri Adı", "Oyuncu Adı", "Base"
    }
    
    OPTIONAL_COLUMNS = {
        "Grup (opsiyonel)", "Grup"
    }
    
    # Variant pattern'ları
    VARIANT_PATTERNS = {
        "1/1": re.compile(r"^1/1$"),
        "signed_1/1": re.compile(r"^1/1\s+İmzalı$"),
        "numbered": re.compile(r"^/(\d+)$"),
        "signed_numbered": re.compile(r"^/(\d+)\s+İmzalı$"),
        # Herhangi bir yazılı denominator (Base hariç, o ayrı işleniyor)
        "text_denom": re.compile(r"^([A-Za-zÇçĞğİıÖöŞşÜü][A-Za-zÇçĞğİıÖöŞşÜü0-9\s]*)$"),
        "signed_text_denom": re.compile(r"^([A-Za-zÇçĞğİıÖöŞşÜü][A-Za-zÇçĞğİıÖöŞşÜü0-9\s]*)\s+İmzalı$")
    }

    # Bu isimler yazılı denominator olarak algılanmasın
    RESERVED_COLUMN_NAMES = {
        "seri adı", "seri adi", "oyuncu adı", "oyuncu adi",
        "grup", "grup (opsiyonel)", "base"
    }
    
    def __init__(self, headers: List[str]):
        self.original_headers = headers.copy()
        self.normalized_headers = []
        self.header_mapping = {}  # original -> normalized
        self.variants = {}  # column -> VariantInfo
        self.errors = []
        self.warnings = []
        
        self._process_headers()
        self.custom_labels = self.detect_custom_labels()

    
    def _process_headers(self) -> None:
        """Header'ları işle ve normalize et"""
        logger.info(f"Header işleme başlıyor: {len(self.original_headers)} sütun")
        
        for i, header in enumerate(self.original_headers):
            try:
                normalized = self._normalize_single_header(header)
                self.normalized_headers.append(normalized)
                self.header_mapping[header] = normalized
                
                # Variant tespiti
                variant_info = self._detect_variant(normalized, header)
                if variant_info:
                    self.variants[normalized] = variant_info
                    
            except Exception as e:
                error_msg = f"Header işleme hatası (sütun {i+1}): {str(e)}"
                logger.error(error_msg)
                self.errors.append({
                    'column': header,
                    'type': 'Header Error',
                    'message': error_msg
                })
                self.normalized_headers.append(header)  # Fallback
        
        self._validate_required_columns()
        self._detect_duplicate_variants()
        
        logger.info(f"Header işleme tamamlandı. Variant sayısı: {len(self.variants)}")
    
    def _normalize_single_header(self, header: str) -> str:
        """Tek header'ı normalize et"""
        if not isinstance(header, str):
            header = str(header)
        
        # Boşlukları temizle
        normalized = normalize_text(header)
        
        # Yaygın normalizasyonlar
        normalizations = {
            "Grup (opsiyonel)": "Grup",
            "1/1 İmzalı": "1/1 İmzalı",
            "1/1İmzalı": "1/1 İmzalı",  # Boşluk eksik
        }
        
        # Sayılı variant normalizasyonları
        for pattern, replacement in normalizations.items():
            if normalized == pattern:
                normalized = replacement
                break
        
        # /X ve /X İmzalı format kontrolü
        numbered_match = re.match(r"^/(\d+)\s*İmzalı?$", normalized)
        if numbered_match:
            num = numbered_match.group(1)
            if "İmzalı" in normalized:
                normalized = f"/{num} İmzalı"
            else:
                normalized = f"/{num}"
        
        # Sadece /X formatı
        simple_numbered = re.match(r"^/(\d+)$", normalized)
        if simple_numbered:
            normalized = f"/{simple_numbered.group(1)}"
        
        return normalized
    
    def _detect_variant(self, normalized_header: str, original_header: str) -> Optional[VariantInfo]:
        """Variant tipini tespit et"""
        
        # 1/1 kontrolü
        if self.VARIANT_PATTERNS["1/1"].match(normalized_header):
            return VariantInfo(
                column_name=normalized_header,
                denominator=1,
                is_signed=False,
                display_name="1/1"
            )
        
        # 1/1 İmzalı kontrolü
        if self.VARIANT_PATTERNS["signed_1/1"].match(normalized_header):
            return VariantInfo(
                column_name=normalized_header,
                denominator=1,
                is_signed=True,
                display_name="1/1 İmzalı"
            )
        
        # /X kontrolü
        numbered_match = self.VARIANT_PATTERNS["numbered"].match(normalized_header)
        if numbered_match:
            denominator = int(numbered_match.group(1))
            return VariantInfo(
                column_name=normalized_header,
                denominator=denominator,
                is_signed=False,
                display_name=f"/{denominator}"
            )
        
        # /X İmzalı kontrolü
        signed_numbered_match = self.VARIANT_PATTERNS["signed_numbered"].match(normalized_header)
        if signed_numbered_match:
            denominator = int(signed_numbered_match.group(1))
            return VariantInfo(
                column_name=normalized_header,
                denominator=denominator,
                is_signed=True,
                display_name=f"/{denominator} İmzalı"
            )

        # Yazılı denominator İmzalı kontrolü (X İmzalı, Short Print İmzalı, vs.)
        signed_text_match = self.VARIANT_PATTERNS["signed_text_denom"].match(normalized_header)
        if signed_text_match:
            denom_text = signed_text_match.group(1).strip()
            # Reserved değilse kabul et
            if denom_text.lower() not in self.RESERVED_COLUMN_NAMES:
                return VariantInfo(
                    column_name=normalized_header,
                    denominator=denom_text,
                    is_signed=True,
                    display_name=f"{denom_text} İmzalı"
                )

        # Yazılı denominator kontrolü (X, Short Print, vs.)
        text_denom_match = self.VARIANT_PATTERNS["text_denom"].match(normalized_header)
        if text_denom_match:
            denom_text = text_denom_match.group(1).strip()
            # Reserved değilse kabul et
            if denom_text.lower() not in self.RESERVED_COLUMN_NAMES:
                return VariantInfo(
                    column_name=normalized_header,
                    denominator=denom_text,
                    is_signed=False,
                    display_name=denom_text
                )

        return None
    
    def _validate_required_columns(self) -> None:
        """Gerekli sütunların varlığını kontrol et"""
        found_columns = set(self.normalized_headers)
        
        for required in self.REQUIRED_COLUMNS:
            if required not in found_columns:
                error_msg = f"Gerekli sütun bulunamadı: {required}"
                logger.error(error_msg)
                self.errors.append({
                    'column': required,
                    'type': 'Missing Column',
                    'message': error_msg
                })
        
        # Grup sütunu kontrolü (opsiyonel)
        has_grup = any(col in found_columns for col in self.OPTIONAL_COLUMNS)
        if not has_grup:
            logger.info("Grup sütunu bulunamadı, Series kullanılacak")
    
    def _detect_duplicate_variants(self) -> None:
        """Çift variant tespiti"""
        denominators = {}
        
        for column, variant_info in self.variants.items():
            denom = variant_info.denominator
            if denom not in denominators:
                denominators[denom] = []
            denominators[denom].append(variant_info)
        
        for denom, variants in denominators.items():
            if len(variants) > 2:
                error_msg = f"Aynı payda için 2'den fazla sütun: /{denom}"
                logger.error(error_msg)
                self.errors.append({
                    'column': f"/{denom}",
                    'type': 'Duplicate Variant',
                    'message': error_msg
                })
            elif len(variants) == 2:
                # İki variant varsa biri imzalı biri normal olmalı
                signed_count = sum(1 for v in variants if v.is_signed)
                if signed_count != 1:
                    error_msg = f"/{denom} için hem imzalı hem normal variant gerekli"
                    logger.warning(error_msg)
                    self.warnings.append({
                        'column': f"/{denom}",
                        'type': 'Variant Pair',
                        'message': error_msg
                    })
    def detect_custom_labels(self) -> Dict[str, str]:
        """Base gibi davranan custom label sütunlarını tespit et"""
        custom_labels = {}
        
        skip_columns = {
            'Base', 'Seri Adı', 'Oyuncu Adı', 'Grup', 'Grup (opsiyonel)'
        }
        
        for header in self.normalized_headers:
            if header in skip_columns:
                continue
            
            if self.is_variant_column(header):
                continue
            
            custom_labels[header] = header
            logger.info(f"Custom label bulundu: {header}")
        
        return custom_labels        
                    
    def get_variant_pairs(self) -> Dict[Union[int, str], Dict[str, Optional[VariantInfo]]]:
        """Variant çiftlerini al"""
        pairs = {}
        
        for variant_info in self.variants.values():
            denom = variant_info.denominator
            if denom not in pairs:
                pairs[denom] = {'normal': None, 'signed': None}
            
            if variant_info.is_signed:
                pairs[denom]['signed'] = variant_info
            else:
                pairs[denom]['normal'] = variant_info
        
        return pairs
    
    def get_column_index(self, column_name: str) -> Optional[int]:
        """Sütun indeksini al"""
        try:
            return self.normalized_headers.index(column_name)
        except ValueError:
            # Original header'larda ara
            for orig, norm in self.header_mapping.items():
                if norm == column_name:
                    try:
                        return self.original_headers.index(orig)
                    except ValueError:
                        continue
            return None
    
    def is_variant_column(self, column_name: str) -> bool:
        """Sütunun variant olup olmadığını kontrol et"""
        return column_name in self.variants
    
    def get_base_column_index(self) -> Optional[int]:
        """Base sütun indeksini al"""
        return self.get_column_index("Base")
    
    def get_series_column_index(self) -> Optional[int]:
        """Seri Adı sütun indeksini al"""
        return self.get_column_index("Seri Adı")
    
    def get_player_column_index(self) -> Optional[int]:
        """Oyuncu Adı sütun indeksini al"""
        return self.get_column_index("Oyuncu Adı")
    
    def get_group_column_index(self) -> Optional[int]:
        """Grup sütun indeksini al"""
        for col_name in self.OPTIONAL_COLUMNS:
            idx = self.get_column_index(col_name)
            if idx is not None:
                return idx
        return None
    
    def has_errors(self) -> bool:
        """Hata olup olmadığını kontrol et"""
        return len(self.errors) > 0
    
    def has_warnings(self) -> bool:
        """Uyarı olup olmadığını kontrol et"""
        return len(self.warnings) > 0
    
    def get_summary(self) -> Dict[str, any]:
        """Header işleme özeti"""
        return {
            'total_columns': len(self.original_headers),
            'variant_columns': len(self.variants),
            'errors': len(self.errors),
            'warnings': len(self.warnings),
            'variants': {v.display_name: v.denominator for v in self.variants.values()},
            'has_group_column': self.get_group_column_index() is not None
        }


def normalize_headers(headers: List[str]) -> HeaderProcessor:
    """Header'ları normalize et (convenience function)"""
    return HeaderProcessor(headers)


def detect_variant_pairs(headers: List[str]) -> Dict[int, Dict[str, Optional[VariantInfo]]]:
    """Variant çiftlerini tespit et (convenience function)"""
    processor = HeaderProcessor(headers)
    return processor.get_variant_pairs()


if __name__ == "__main__":
    # Test
    import logging
    logging.basicConfig(level=logging.INFO)
    
    test_headers = [
        "Seri Adı", "Grup (opsiyonel)", "Oyuncu Adı",
        "1/1", "1/1 İmzalı", "/5", "/5 İmzalı",
        "/25", "/25 İmzalı", "/67", "/67 İmzalı", "Base"
    ]
    
    processor = HeaderProcessor(test_headers)
    print(f"Summary: {processor.get_summary()}")
    print(f"Errors: {processor.errors}")
    print(f"Warnings: {processor.warnings}")
    print(f"Variant pairs: {processor.get_variant_pairs()}")