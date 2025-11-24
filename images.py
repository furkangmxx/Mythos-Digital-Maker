"""
MythosCards Exporter - Part 2: Image Mapping (Güncellenmiş Versiyon)

A kolonundaki kartları görsel dosyalarıyla eşleştirme
İki Aşamalı Filtreleme Sistemi:

STAGE 1 - HARD RULES (Kesin Kontrol):
  1. Sayı: (X/Y) → dosya _Y.jpg ile bitmeli
  2. İmza: İmzalı → dosyada _s_ olmalı
  3. Base: Base → dosyada _base_ olmalı
  4. Shortprint → dosyada _short_print_ veya _shortprint_
  5. Custom labels (Pre, Noir, X vb.)

STAGE 2 - SEQUENCE MATCHING (Harf Bazlı):
  - %95 karakter benzerliği
  - Türkçe normalizasyon (ş→s, ü→u, ı→i)
  - "Gol" vs "Mac" gibi farkları yakalar
"""

import os
import shutil
import logging
import re
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher
import pandas as pd

from utils import normalize_text, ist_timestamp

logger = logging.getLogger(__name__)

TURKISH_TO_ASCII = str.maketrans('çÇğĞıIiİöÖşŞüÜâÂ', 'cCgGiIiIoOsSuUaA')
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png'}

@dataclass
class MatchResult:
    """Eşleştirme sonucu"""
    row_number: int
    card_text: str
    status: str  # 'found', 'missing', 'conflict'
    matched_file: str = ""
    conflict_files: List[str] = None
    log_message: str = ""
    similarity_score: float = 0.0  # Debug için benzerlik skoru
    
    def __post_init__(self):
        if self.conflict_files is None:
            self.conflict_files = []

class ImageMatcher:
    """Part 2 ana sınıf - İki aşamalı filtreleme ile eşleştirme"""
    
    def __init__(self, excel_file: Path, image_dir: Path, date_str: str = None):
        self.excel_file = Path(excel_file)
        self.image_dir = Path(image_dir)
        self.date_str = date_str or datetime.now().strftime("%Y%m%d")
        
        self.matches: List[MatchResult] = []
        self.image_files: List[Path] = []
        self.stats = {'found': 0, 'missing': 0, 'conflict': 0}
        
    def process_all(self) -> Dict[str, any]:
        """Ana işlem"""
        logger.info(f"Part 2 başlıyor - Excel: {self.excel_file.name}")
        
        try:
            # 1. Görsel dosyalarını tara
            self._scan_images()
            
            # 2. Excel'den A kolonunu oku
            card_lines = self._read_a_column()
            
            # 3. Her kart için eşleştirme yap
            self._match_all_cards(card_lines)

            # 4. ÖNCE BACKUP AL
            backup_dir = self._create_backup()

            # 5. SONRA RENAME ET
            self._rename_physical_files()

            # 6. B kolonunu güncelle
            self._update_b_column()

            # 7. Log raporu
            return self._generate_report()
            
        except Exception as e:
            logger.error(f"Part 2 hatası: {str(e)}")
            raise
    
    def _scan_images(self) -> None:
        """Görsel dosyalarını tara - duplicate önleme"""
        if not self.image_dir.exists():
            raise FileNotFoundError(f"Görsel klasörü bulunamadı: {self.image_dir}")
        
        seen_files = set()
        
        for ext in SUPPORTED_EXTENSIONS:
            for pattern in [f"*{ext}", f"*{ext.upper()}"]:
                for file_path in self.image_dir.glob(pattern):
                    # Absolute path ile duplicate kontrolü
                    abs_path = str(file_path.resolve())
                    if abs_path not in seen_files:
                        seen_files.add(abs_path)
                        self.image_files.append(file_path)
        
        if not self.image_files:
            raise ValueError(f"Görsel klasöründe desteklenen dosya yok: {SUPPORTED_EXTENSIONS}")
        
        logger.info(f"Taranan görsel sayısı: {len(self.image_files)}")
    
    def _read_a_column(self) -> List[str]:
        """Excel A kolonunu oku"""
        try:
            data = pd.read_excel(self.excel_file, sheet_name="Çıktı")
            
            if len(data.columns) == 0:
                raise ValueError("Excel'de sütun yok")
            
            # A kolonu
            card_lines = []
            for value in data.iloc[:, 0]:
                if pd.notna(value) and str(value).strip():
                    card_lines.append(str(value).strip())
                else:
                    card_lines.append("")
            
            logger.info(f"A kolonundan okunan kart: {len([c for c in card_lines if c])}")
            return card_lines
            
        except Exception as e:
            raise ValueError(f"Excel okuma hatası: {str(e)}")
    
    def _match_all_cards(self, card_lines: List[str]) -> None:
        """Tüm kartları eşleştir"""
        for i, card_text in enumerate(card_lines, 1):
            if not card_text.strip():
                self.matches.append(MatchResult(i, "", "empty"))
                continue
            
            try:
                result = self._match_single_card(card_text, i)
                self.matches.append(result)
                self.stats[result.status] += 1
                
                # Log
                if result.status == 'found':
                    logger.info(f"Satır {i}: ✅ Eşleşti ({result.similarity_score:.1%}) - {result.matched_file}")
                elif result.status == 'missing':
                    logger.warning(f"Satır {i}: ❌ Bulunamadı - {result.log_message}")
                else:  # conflict
                    logger.warning(f"Satır {i}: ⚠️ Çakışma - {len(result.conflict_files)} dosya")
                    
            except Exception as e:
                logger.error(f"Satır {i} hatası: {str(e)}")
                self.matches.append(MatchResult(i, card_text, "missing", 
                                               log_message=f"Parse hatası: {str(e)}"))
                self.stats['missing'] += 1
    
    def _match_single_card(self, card_text: str, row_num: int) -> MatchResult:
        """
        Tek kart eşleştir - EN YÜKSEK SKORU BUL
        
        1. Parse et
        2. Hard rules geçenleri bul
        3. Her biri için sequence matching skoru hesapla
        4. En yüksek skoru seç
        """
        parsed = self._parse_card(card_text)
        
        candidates = []  # (filename, score) tuple'ları
        
        for img_file in self.image_files:
            filename = img_file.name.lower()
            
            # STAGE 1: Hard Rules
            if not self._check_hard_rules(parsed, filename):
                continue  # Hard rule fail → sonraki dosyaya geç
            
            # STAGE 2: Sequence Matching Score
            score = self._calculate_similarity(parsed, filename)
            candidates.append((img_file.name, score))
        
        if len(candidates) == 0:
            return MatchResult(row_num, card_text, "missing",
                            log_message=self._build_search_criteria(parsed))
        
        # En yüksek skoru seç
        best_file, best_score = max(candidates, key=lambda x: x[1])
        
        logger.debug(f"Satır {row_num}: En iyi eşleşme {best_file} (skor: {best_score:.2%})")
        
        return MatchResult(
            row_num, 
            card_text, 
            "found", 
            matched_file=best_file,
            similarity_score=best_score
        )
    
    def _parse_card(self, card_text: str) -> Dict[str, any]:
        """
        Kart metnini parse et - Basit ve temiz
        
        Çıkarılanlar:
        1. İmzalı → is_signed
        2. Base → is_base
        3. (X/Y) → denominator
        4. Geri kalan TAM METİN → full_text
        """
        
        text = card_text
        
        # 1. İmzalı kontrolü (orijinal metinden)
        is_signed = "İmzalı" in text or "Imzalı" in text
        
        # 2. Base kontrolü (orijinal metinden)
        is_base = "Base" in text
        
        # 3. Denominator (sayı) kontrolü
        denominator = 0
        variant_match = re.search(r'\((\d+)/(\d+)\)', text)
        if variant_match:
            denominator = int(variant_match.group(2))
        
        # 4. Normalize et ve temizle
        text = normalize_text(text)
        
        # İmzalı çıkar
        text = text.replace("Imzali", "").replace("İmzalı", "")
        
        # Base çıkar
        text = text.replace("Base", "")
        
        # (X/Y) çıkar
        text = re.sub(r'\s*\(\d+/\d+\)', '', text)
        
        # Temizle
        text = text.strip()
        text = re.sub(r'\s+', ' ', text)  # Çoklu boşluk tek yap
        
        return {
            'full_text': text,  # TAM METİN (seri + grup + oyuncu + diğer kelimeler)
            'is_signed': is_signed,
            'is_base': is_base,
            'denominator': denominator
        }
    
    def _check_hard_rules(self, parsed: Dict, filename: str) -> bool:
        """
        STAGE 1: Hard Rules (Kesin Kontrol)
        
        3 KURAL:
        1. Sayı: Base yoksa ve denominator > 0 → _X.jpg kontrol
        2. İmza: is_signed → _s_ kontrol
        3. Base: is_base → _base_ kontrol (sayı ignore)
        """
        
        # Tarih prefix'ini temizle
        clean_filename = re.sub(r'^\d{8}_', '', filename)
        
        # ========================================
        # KURAL 1: Sayı Kontrolü (Base YOKSA!)
        # ========================================
        if not parsed['is_base'] and parsed['denominator'] > 0:
            # Base yoksa sayı kesin kontrol edilir
            pattern = rf'_{parsed["denominator"]}\.(jpg|jpeg|png)$'
            if not re.search(pattern, clean_filename):
                return False
        
        # ========================================
        # KURAL 2: İmzalı Kontrolü
        # ========================================
        if parsed['is_signed']:
            if '_s_' not in clean_filename:
                return False
        
        # ========================================
        # KURAL 3: Base Kontrolü
        # ========================================
        if parsed['is_base']:
            if '_base_' not in clean_filename and '_base.' not in clean_filename:
                return False
        
        return True
    
    def _calculate_similarity(self, parsed: Dict, filename: str) -> float:
        """
        Fuzzy Token Matching - Kelime sırasına bakmaz, harf hatası tolere edilir
        
        Mantık:
        1. Her iki taraftaki kelimeleri al
        2. Her Excel kelimesi için dosyadaki en benzer kelimeyi bul
        3. Kelime %80+ benzer → eşleşmiş say
        4. Toplam eşleşen kelime / toplam kelime = skor
        """
        full_text = parsed['full_text']
        
        # Normalize et
        text_normalized = self._normalize_for_matching(full_text)
        
        # Dosya adını temizle
        file_clean = re.sub(r'^\d{8}_', '', filename)  # Tarih
        file_clean = re.sub(r'\.\w+$', '', file_clean)  # Uzantı
        file_normalized = self._normalize_for_matching(file_clean)
        
        # Kelimelere ayır
        text_words = [w for w in text_normalized.split() if len(w) >= 2]  # En az 2 karakter
        file_words = [w for w in file_normalized.split() if len(w) >= 2]
        
        if len(text_words) == 0:
            return 0.0
        
        # Her Excel kelimesi için en iyi eşleşmeyi bul
        matched_count = 0
        
        for text_word in text_words:
            best_similarity = 0.0
            
            # Dosyadaki tüm kelimelerle karşılaştır
            for file_word in file_words:
                # Kelime benzerliği (fuzzy)
                similarity = SequenceMatcher(None, text_word, file_word).ratio()
                
                if similarity > best_similarity:
                    best_similarity = similarity
            
            # Eğer en iyi eşleşme %80'in üzerindeyse, eşleşmiş say
            if best_similarity >= 0.80:  # Kelime benzerlik threshold
                matched_count += 1
        
        # Toplam skor
        total_score = matched_count / len(text_words)
        
        return total_score
    
    def _normalize_for_matching(self, text: str) -> str:
        """Eşleştirme için normalize et"""
        # Türkçe → ASCII
        normalized = text.translate(TURKISH_TO_ASCII)
        # Küçük harf
        normalized = normalized.lower()
        # Alt çizgi ve tire → boşluk
        normalized = re.sub(r'[_\-]', ' ', normalized)
        # Noktalama ve özel karakterleri temizle
        normalized = re.sub(r'[^\w\s]', '', normalized)
        # Çoklu boşlukları tek yap
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def _build_search_criteria(self, parsed: Dict) -> str:
        """Arama kriterleri mesajı (debug için)"""
        criteria = []
        criteria.append(f"Tam Metin: {parsed['full_text']}")
        
        # Sayı
        if parsed['denominator'] > 0:
            if parsed['is_base']:
                criteria.append(f"Sayı: _{parsed['denominator']}.jpg (Base var - ignore)")
            else:
                criteria.append(f"Sayı: _{parsed['denominator']}.jpg (kesin)")
        
        # İmzalı
        if parsed['is_signed']:
            criteria.append("İmzalı: _s_ (kesin)")
        
        # Base
        if parsed['is_base']:
            criteria.append("Base: _base_ (kesin)")
        
        return " | ".join(criteria)
    
    def _create_backup(self) -> Path:
        """Dosyaları rename etmeden önce yedekle"""
        folder_name = self.image_dir.name
        documents_dir = Path.home() / "Documents" / "MythosCards"
        backup_main_dir = documents_dir / "Backup"
        backup_dir = backup_main_dir / f"{self.date_str}_{folder_name}"
        
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        backed_up_count = 0
        
        for match in self.matches:
            if match.status == 'found':
                # Eğer dosya zaten tarih prefix'i ile başlıyorsa yedekleme
                if match.matched_file.startswith(self.date_str + "_"):
                    continue
                
                source_file = self.image_dir / match.matched_file
                backup_file = backup_dir / match.matched_file
                
                if source_file.exists() and not backup_file.exists():
                    shutil.copy2(source_file, backup_file)
                    backed_up_count += 1
        
        logger.info(f"{backed_up_count} dosya yedeklendi: {backup_dir}")
        return backup_dir

    def _rename_physical_files(self) -> None:
        """Fiziksel dosyaları tarih prefix'i ile rename et"""
        renamed_count = 0
        rename_map = {}
        
        # Önce hangi dosyaların rename edileceğini belirle
        for match in self.matches:
            if match.status == 'found':
                if not match.matched_file.startswith(self.date_str + "_"):
                    old_name = match.matched_file
                    new_name = f"{self.date_str}_{old_name}"
                    rename_map[old_name] = new_name
        
        # Fiziksel dosyaları rename et
        for old_name, new_name in rename_map.items():
            old_path = self.image_dir / old_name
            new_path = self.image_dir / new_name
            
            if old_path.exists():
                if new_path.exists():
                    logger.warning(f"Dosya zaten var, atlıyor: {new_name}")
                else:
                    old_path.rename(new_path)
                    renamed_count += 1
                    logger.info(f"Renamed: {old_name} → {new_name}")
        
        # TÜM matches'lerdeki dosya adlarını güncelle
        for match in self.matches:
            if match.status == 'found' and match.matched_file in rename_map:
                match.matched_file = rename_map[match.matched_file]
        
        logger.info(f"{renamed_count} dosya yeniden adlandırıldı")
    
    def _update_b_column(self) -> None:
        """B kolonunu güncelle"""
        try:
            data = pd.read_excel(self.excel_file, sheet_name=0)
            
            if len(data.columns) == 1:
                data['Görsel Dosyası'] = ""
            
            # B kolonu değerlerini oluştur
            b_column_values = []
            for i, match in enumerate(self.matches):
                if i < len(data):
                    if match.status == 'found':
                        b_column_values.append(match.matched_file)
                    else:
                        b_column_values.append("")
                else:
                    b_column_values.append("")
            
            # B kolonunu yeni değerlerle değiştir
            data['Görsel Dosyası'] = b_column_values
            
            # Excel'e yaz
            excel_file = pd.ExcelFile(self.excel_file)
            sheet_name = excel_file.sheet_names[0] if excel_file.sheet_names else 'Sheet1'
            
            with pd.ExcelWriter(self.excel_file, engine='openpyxl', mode='a', 
                            if_sheet_exists='replace') as writer:
                data.to_excel(writer, sheet_name=sheet_name, index=False)
            
            logger.info("B kolonu güncellendi")
            
        except Exception as e:
            raise ValueError(f"Excel güncelleme hatası: {str(e)}")
    
    def _generate_report(self) -> Dict[str, any]:
        """Sonuç raporu"""
        total = len([m for m in self.matches if m.status != 'empty'])
        success_rate = (self.stats['found'] / total * 100) if total > 0 else 0
        
        # Detaylı loglar
        warnings = []
        for match in self.matches:
            if match.status == 'missing':
                warnings.append({
                    'row': match.row_number,
                    'column': 'B',
                    'type': 'Missing Image',
                    'message': f"Görsel bulunamadı - {match.log_message}"
                })
            elif match.status == 'conflict':
                warnings.append({
                    'row': match.row_number,
                    'column': 'B',
                    'type': 'Image Conflict',
                    'message': match.log_message
                })
        
        return {
            'success': True,
            'total_cards': total,
            'found_count': self.stats['found'],
            'missing_count': self.stats['missing'],
            'conflict_count': self.stats['conflict'],
            'success_rate': success_rate,
            'warnings': warnings,
            'errors': [],
            'processing_time': ist_timestamp()
        }


# Public API
def process_image_mapping(excel_file: str, image_dir: str, date: str = None) -> Dict[str, any]:
    """Part 2 ana fonksiyon"""
    matcher = ImageMatcher(Path(excel_file), Path(image_dir), date)
    return matcher.process_all()


def validate_image_inputs(excel_file: str, image_dir: str) -> List[str]:
    """Input validation"""
    issues = []
    
    if not Path(excel_file).exists():
        issues.append(f"Excel dosyası yok: {excel_file}")
    
    if not Path(image_dir).exists():
        issues.append(f"Görsel klasörü yok: {image_dir}")
    
    return issues


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("Part 2 - Image Matcher (İki Aşamalı Filtreleme)")
    print("Kullanım: python main.py images --excel file.xlsx --imgdir ./images")