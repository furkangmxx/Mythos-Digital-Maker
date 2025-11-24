"""
MythosCards Exporter - Turkish Sorting
Türkçe karakter desteği ile sıralama işlemleri
"""

import logging
import locale
from typing import List, Tuple, Any, Optional, Callable
from functools import cmp_to_key

from expand import CardLine

logger = logging.getLogger(__name__)

# Türkçe karakter sıralaması için mapping
TURKISH_CHAR_ORDER = {
    'a': 1, 'A': 1,
    'b': 2, 'B': 2,
    'c': 3, 'C': 3,
    'ç': 4, 'Ç': 4,
    'd': 5, 'D': 5,
    'e': 6, 'E': 6,
    'f': 7, 'F': 7,
    'g': 8, 'G': 8,
    'ğ': 9, 'Ğ': 9,
    'h': 10, 'H': 10,
    'ı': 11, 'I': 11,
    'i': 12, 'İ': 12,
    'j': 13, 'J': 13,
    'k': 14, 'K': 14,
    'l': 15, 'L': 15,
    'm': 16, 'M': 16,
    'n': 17, 'N': 17,
    'o': 18, 'O': 18,
    'ö': 19, 'Ö': 19,
    'p': 20, 'P': 20,
    'r': 21, 'R': 21,
    's': 22, 'S': 22,
    'ş': 23, 'Ş': 23,
    't': 24, 'T': 24,
    'u': 25, 'U': 25,
    'ü': 26, 'Ü': 26,
    'v': 27, 'V': 27,
    'y': 28, 'Y': 28,
    'z': 29, 'Z': 29
}


class TurkishSorter:
    """Türkçe sıralama sınıfı"""
    
    def __init__(self, use_icu: bool = True, use_locale: bool = True):
        self.use_icu = use_icu
        self.use_locale = use_locale
        self.icu_collator = None
        self.locale_available = False
        
        self._initialize_sorting_methods()
    
    def _initialize_sorting_methods(self) -> None:
        """Sıralama yöntemlerini başlat"""
        
        # PyICU'yu dene
        if self.use_icu:
            try:
                import icu #type: ignore CALISMIYOR 
                self.icu_collator = icu.Collator.createInstance(icu.Locale('tr_TR'))
                logger.info("PyICU Turkish collator başlatıldı")
                return
            except ImportError:
                logger.info("PyICU bulunamadı, locale fallback kullanılacak")
            except Exception as e:
                logger.warning(f"PyICU hatası: {str(e)}, locale fallback kullanılacak")
        
        # Locale'i dene
        if self.use_locale:
            try:
                # Farklı locale isimlerini dene
                turkish_locales = ['tr_TR.UTF-8', 'Turkish_Turkey.1254', 'tr_TR', 'Turkish']
                
                for loc in turkish_locales:
                    try:
                        locale.setlocale(locale.LC_COLLATE, loc)
                        self.locale_available = True
                        logger.info(f"Locale sıralama başlatıldı: {loc}")
                        return
                    except locale.Error:
                        continue
                
                logger.info("Türkçe locale bulunamadı, custom mapping kullanılacak")
                
            except Exception as e:
                logger.warning(f"Locale hatası: {str(e)}, custom mapping kullanılacak")
        
        logger.info("Custom Turkish character mapping kullanılacak")
    
    def turkish_key(self, text: str) -> Tuple[List[int], str]:
        """Türkçe sıralama anahtarı"""
        if not isinstance(text, str):
            text = str(text)
        
        # ICU varsa kullan
        if self.icu_collator:
            try:
                return ([], self.icu_collator.getSortKey(text.lower()))
            except Exception as e:
                logger.warning(f"ICU sıralama hatası: {str(e)}")
        
        # Locale varsa kullan
        if self.locale_available:
            try:
                return ([], locale.strxfrm(text.lower()))
            except Exception as e:
                logger.warning(f"Locale sıralama hatası: {str(e)}")
        
        # Custom mapping kullan
        return (self._custom_turkish_key(text), text.lower())
    
    def _custom_turkish_key(self, text: str) -> List[int]:
        """Custom Turkish character mapping"""
        key = []
        text_lower = text.lower()
        
        for char in text_lower:
            if char in TURKISH_CHAR_ORDER:
                key.append(TURKISH_CHAR_ORDER[char])
            elif char.isalpha():
                # Bilinmeyen harf için ASCII değeri + offset
                key.append(ord(char) + 1000)
            elif char.isdigit():
                # Sayılar harflerden önce
                key.append(ord(char) - ord('0'))
            else:
                # Diğer karakterler
                key.append(ord(char) + 2000)
        
        return key
    
    def compare_turkish(self, a: str, b: str) -> int:
        """Türkçe karşılaştırma (-1, 0, 1)"""
        key_a = self.turkish_key(a)
        key_b = self.turkish_key(b)
        
        if key_a < key_b:
            return -1
        elif key_a > key_b:
            return 1
        else:
            return 0
    
    def sort_strings(self, strings: List[str]) -> List[str]:
        """String listesini Türkçe sırala"""
        return sorted(strings, key=self.turkish_key)
    
    def sort_card_lines(self, lines: List[CardLine]) -> List[CardLine]:
        """Kart satırlarını sırala"""
        def card_sort_key(line: CardLine) -> Tuple:
            """Kart sıralama anahtarı - Base kartlar en sona"""
            
            # Base kartlar için özel sıralama
            if line.variant_type == "Base":
                sort_order = 99999  # Base kartları en sona at
            else:
                sort_order = line.denominator
            
            return (
                self.turkish_key(line.player),      # 1. Oyuncu alfabetik
                self.turkish_key(line.label),       # 2. Label alfabetik
                self.turkish_key(line.variant_type), # 3. Variant tipi alfabetik (bu gruplayacak)
                line.number                         # 4. Numara sıralı
            )
        return sorted(lines, key=card_sort_key)


def create_turkish_sorter(prefer_icu: bool = True) -> TurkishSorter:
    """Türkçe sıralayıcı oluştur"""
    return TurkishSorter(use_icu=prefer_icu, use_locale=True)


def sort_card_lines_turkish(lines: List[CardLine], prefer_icu: bool = True) -> List[CardLine]:
    """Kart satırlarını Türkçe sırala (convenience function)"""
    sorter = create_turkish_sorter(prefer_icu)
    return sorter.sort_card_lines(lines)


def sort_strings_turkish(strings: List[str], prefer_icu: bool = True) -> List[str]:
    """String listesini Türkçe sırala (convenience function)"""
    sorter = create_turkish_sorter(prefer_icu)
    return sorter.sort_strings(strings)


class MultiColumnSorter:
    """Çoklu sütun sıralama"""
    
    def __init__(self, turkish_sorter: TurkishSorter):
        self.turkish_sorter = turkish_sorter
    
    def sort_by_criteria(self, items: List[Any], criteria: List[Tuple[Callable, bool]]) -> List[Any]:
        """Çoklu kritere göre sırala
        
        Args:
            items: Sıralanacak öğeler
            criteria: (key_function, reverse) tuple'ları
        """
        
        def multi_key(item):
            keys = []
            for key_func, reverse in criteria:
                key_value = key_func(item)
                if isinstance(key_value, str):
                    # String ise Turkish key kullan
                    key_value = self.turkish_sorter.turkish_key(key_value)
                keys.append(key_value)
            return keys
        
        # Reverse sıralaması için criteria'yı ters çevir
        reverse_overall = any(reverse for _, reverse in criteria)
        
        return sorted(items, key=multi_key, reverse=reverse_overall)


def create_card_line_sorter() -> Callable[[List[CardLine]], List[CardLine]]:
    """Kart satırı sıralayıcı factory"""
    sorter = create_turkish_sorter()
    
    def sort_lines(lines: List[CardLine]) -> List[CardLine]:
        return sorter.sort_card_lines(lines)
    
    return sort_lines


# Test fonksiyonları
def test_turkish_sorting():
    """Türkçe sıralama testi"""
    test_names = [
        "Çağlar Söyüncü",
        "Arda Güler", 
        "İrfan Can Kahveci",
        "Oğuzhan Özyakup",
        "Şenol Güneş",
        "Cenk Tosun",
        "Zeki Çelik",
        "Abdülkadir Ömür"
    ]
    
    sorter = create_turkish_sorter()
    sorted_names = sorter.sort_strings(test_names)
    
    print("Türkçe sıralama testi:")
    for i, name in enumerate(sorted_names, 1):
        print(f"{i:2d}. {name}")
    
    return sorted_names


def test_card_line_sorting():
    """Kart satırı sıralama testi"""
    from .expand import CardLine
    
    test_lines = [
        CardLine("Zeki Çelik Duo (1/5)", "Zeki Çelik", "Duo", "/5", 5, 1, False, "Test", None),
        CardLine("Arda Güler Base", "Arda Güler", "Super", "Base", 78, 78, False, "Test", None),
        CardLine("Çağlar Söyüncü Trio (2/25)", "Çağlar Söyüncü", "Trio", "/25", 25, 2, False, "Test", None),
        CardLine("Arda Güler Duo (1/10)", "Arda Güler", "Duo", "/10", 10, 1, False, "Test", None),
        CardLine("Çağlar Söyüncü Trio (1/25)", "Çağlar Söyüncü", "Trio", "/25", 25, 1, False, "Test", None),
    ]
    
    sorted_lines = sort_card_lines_turkish(test_lines)
    
    print("\nKart sıralama testi:")
    for i, line in enumerate(sorted_lines, 1):
        print(f"{i:2d}. {line.text}")
    
    return sorted_lines


if __name__ == "__main__":
    # Test çalıştır
    logging.basicConfig(level=logging.INFO)
    
    print("=== TÜRKÇE SIRALAMA TESTLERİ ===")
    test_turkish_sorting()
    test_card_line_sorting()
    
    # PyICU durumu
try:
    import icu # type: ignore CALISMIYOR
    version = getattr(icu, 'ICU_VERSION', 'Available')
    print(f"\n✅ PyICU mevcut: {version}")
except ImportError:
    print("\n❌ PyICU bulunamadı (fallback sıralama kullanılacak)")
except Exception as e:
    print(f"\n⚠️ PyICU hatası: {str(e)}")