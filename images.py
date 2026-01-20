"""
MythosCards Exporter - Part 2: Image Mapping (v2.1)

Excel'deki yapılandırılmış kolonlardan okuma:
- B: player_name
- C: series_name
- D: group
- E: denominator
- F: is_signed

Eşleştirme: Tam eşleşme öncelikli, fazlalık/eksiklik kontrolü
"""

import os
import shutil
import logging
import re
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
import pandas as pd

logger = logging.getLogger(__name__)

# Türkçe karakter dönüşümü
TURKISH_TO_ASCII = str.maketrans('çÇğĞıIİşŞöÖüÜâÂ', 'cCgGiIIsSoOuUaA')
SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png'}


def normalize_for_matching(text: str) -> str:
    """Eşleştirme için normalize et"""
    if not text:
        return ""
    # Türkçe → ASCII
    normalized = str(text).translate(TURKISH_TO_ASCII)
    # Küçük harf
    normalized = normalized.lower()
    # Boşluk ve özel karakterler → alt çizgi
    normalized = re.sub(r'[^a-z0-9]', '_', normalized)
    # Çoklu alt çizgi → tek
    normalized = re.sub(r'_+', '_', normalized)
    # Baş/son alt çizgi temizle
    normalized = normalized.strip('_')
    return normalized


@dataclass
class CardInfo:
    """Excel'den okunan kart bilgisi"""
    row_number: int
    raw_text: str
    player: str
    series: str
    group: str
    denominator: int
    is_signed: bool
    is_base: bool
    
    # Normalize edilmiş (eşleştirme için)
    player_norm: str = ""
    series_norm: str = ""
    group_norm: str = ""
    
    def __post_init__(self):
        self.player_norm = normalize_for_matching(self.player)
        self.series_norm = normalize_for_matching(self.series)
        self.group_norm = normalize_for_matching(self.group)
    
    def get_all_parts(self) -> List[str]:
        """Tüm normalize parçaları döndür"""
        parts = []
        if self.player_norm:
            parts.extend(self.player_norm.split('_'))
        if self.series_norm:
            parts.extend(self.series_norm.split('_'))
        if self.group_norm:
            parts.extend(self.group_norm.split('_'))
        # Boş ve kısa olanları filtrele
        return [p for p in parts if len(p) >= 2]


@dataclass
class FileInfo:
    """Dosya adından parse edilmiş bilgi"""
    original_name: str
    has_date: bool
    date_prefix: str
    denominator: int
    is_signed: bool
    is_base: bool
    
    # Tüm parçalar (normalize edilmiş)
    all_parts: List[str] = field(default_factory=list)
    
    # İçerik parçaları (tarih, s, base, denominator hariç)
    content_parts: List[str] = field(default_factory=list)


@dataclass
class MatchResult:
    """Eşleştirme sonucu"""
    row_number: int
    card_text: str
    status: str  # 'found', 'missing', 'conflict'
    matched_file: str = ""
    conflict_files: List[str] = field(default_factory=list)
    log_message: str = ""
    match_score: float = 0.0


class ImageMatcher:
    """Part 2 ana sınıf - Yapılandırılmış eşleştirme"""
    
    def __init__(self, excel_file: Path, image_dir: Path, 
                 date_str: str = None, add_date_prefix: bool = False):
        self.excel_file = Path(excel_file)
        self.image_dir = Path(image_dir)
        self.date_str = date_str or datetime.now().strftime("%Y%m%d")
        self.add_date_prefix = add_date_prefix
        
        self.matches: List[MatchResult] = []
        self.image_files: List[Path] = []
        self.parsed_files: Dict[str, FileInfo] = {}
        self.stats = {'found': 0, 'missing': 0, 'conflict': 0}
        
    def process_all(self) -> Dict[str, any]:
        """Ana işlem"""
        logger.info(f"Part 2 başlıyor - Excel: {self.excel_file.name}")
        logger.info(f"Tarih ekleme: {'Açık' if self.add_date_prefix else 'Kapalı'}")
        
        try:
            # 1. Görsel dosyalarını tara ve parse et
            self._scan_and_parse_images()
            
            # 2. Excel'den kart bilgilerini oku
            cards = self._read_cards_from_excel()
            
            # 3. Her kart için eşleştirme yap
            self._match_all_cards(cards)

            # 4. Backup al (sadece rename edilecekler için)
            if self.add_date_prefix:
                self._create_backup()

            # 5. Rename et (sadece tarih ekle açıksa)
            if self.add_date_prefix:
                self._rename_physical_files()

            # 6. G kolonunu güncelle (Görsel Dosyası)
            self._update_image_column()

            # 7. Rapor
            return self._generate_report()
            
        except Exception as e:
            logger.error(f"Part 2 hatası: {str(e)}")
            raise
    
    def _scan_and_parse_images(self) -> None:
        """Görsel dosyalarını tara ve parse et"""
        if not self.image_dir.exists():
            raise FileNotFoundError(f"Görsel klasörü bulunamadı: {self.image_dir}")
        
        seen_files = set()
        
        for ext in SUPPORTED_EXTENSIONS:
            for pattern in [f"*{ext}", f"*{ext.upper()}"]:
                for file_path in self.image_dir.glob(pattern):
                    abs_path = str(file_path.resolve())
                    if abs_path not in seen_files:
                        seen_files.add(abs_path)
                        self.image_files.append(file_path)
                        
                        # Parse et
                        parsed = self._parse_filename(file_path.name)
                        self.parsed_files[file_path.name] = parsed
        
        if not self.image_files:
            raise ValueError(f"Görsel klasöründe desteklenen dosya yok: {SUPPORTED_EXTENSIONS}")
        
        logger.info(f"Taranan görsel sayısı: {len(self.image_files)}")
    
    def _parse_filename(self, filename: str) -> FileInfo:
        """
        Dosya adını parse et
        
        Format: [YYYYMMDD_]part1_part2_...[_s]_denominator.jpg
        Veya:   [YYYYMMDD_]part1_part2_..._base[_N].jpg
        """
        original = filename
        name = filename.lower()
        
        # Uzantıyı çıkar
        name = re.sub(r'\.(jpg|jpeg|png)$', '', name, flags=re.IGNORECASE)
        
        # Tarih prefix kontrolü (YYYYMMDD_)
        has_date = False
        date_prefix = ""
        date_match = re.match(r'^(\d{8})_(.+)$', name)
        if date_match:
            has_date = True
            date_prefix = date_match.group(1)
            name = date_match.group(2)
        
        # İmzalı kontrolü (_s_ var mı)
        is_signed = '_s_' in f'_{name}_'  # Kenar durumları için
        
        # Base kontrolü
        is_base = False
        denominator = 0
        
        # Base pattern: _base veya _base_N
        base_match = re.search(r'_base(?:_(\d+))?$', name)
        if base_match:
            is_base = True
            if base_match.group(1):
                denominator = int(base_match.group(1))
            name = re.sub(r'_base(?:_\d+)?$', '', name)
        else:
            # Normal denominator: _10 veya _25 (sondaki sayı)
            denom_match = re.search(r'_(\d+)$', name)
            if denom_match:
                denominator = int(denom_match.group(1))
                name = re.sub(r'_\d+$', '', name)
        
        # _s_ çıkar (içerik parçalarından)
        name = re.sub(r'_s_', '_', name)
        name = re.sub(r'^s_', '', name)
        name = re.sub(r'_s$', '', name)
        
        # İçerik parçaları
        all_parts = name.split('_')
        content_parts = [p for p in all_parts if len(p) >= 2]
        
        return FileInfo(
            original_name=original,
            has_date=has_date,
            date_prefix=date_prefix,
            denominator=denominator,
            is_signed=is_signed,
            is_base=is_base,
            all_parts=all_parts,
            content_parts=content_parts
        )
    
    def _read_cards_from_excel(self) -> List[CardInfo]:
        """
        Excel'den kart bilgilerini oku
        
        Beklenen kolonlar:
        A (0): Kart Listesi
        B (1): Görsel Dosyası (Part 2 dolduracak)
        C (2): player_name
        D (3): series_name
        E (4): group
        F (5): denominator
        G (6): is_signed
        """
        try:
            data = pd.read_excel(self.excel_file, sheet_name="Çıktı")
            
            if len(data.columns) < 7:
                raise ValueError(f"Excel'de yeterli kolon yok. Beklenen: 7, Bulunan: {len(data.columns)}")
            
            cards = []
            for idx, row in data.iterrows():
                row_num = idx + 2  # Excel satır numarası
                
                # Kolonları oku - YENİ İNDEKSLER
                raw_text = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""  # A: Kart Listesi
                # B (1) = Görsel Dosyası - atla, Part 2 dolduracak
                player = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""    # C: player_name
                series = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""    # D: series_name
                group = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""     # E: group
                
                # F: Denominator
                denom_val = row.iloc[5] if pd.notna(row.iloc[5]) else 0
                try:
                    denominator = int(float(denom_val))
                except:
                    denominator = 0
                
                # G: is_signed
                signed_val = str(row.iloc[6]).strip().lower() if pd.notna(row.iloc[6]) else ""
                is_signed = signed_val in ['evet', 'true', '1', 'yes']
                
                # Base kontrolü
                is_base = 'base' in raw_text.lower()
                
                if not raw_text:
                    continue
                
                card = CardInfo(
                    row_number=row_num,
                    raw_text=raw_text,
                    player=player,
                    series=series,
                    group=group,
                    denominator=denominator,
                    is_signed=is_signed,
                    is_base=is_base
                )
                cards.append(card)
            
            logger.info(f"Excel'den okunan kart: {len(cards)}")
            return cards
            
        except Exception as e:
            raise ValueError(f"Excel okuma hatası: {str(e)}")
    
    def _match_all_cards(self, cards: List[CardInfo]) -> None:
        """Tüm kartları eşleştir"""
        for card in cards:
            try:
                result = self._match_single_card(card)
                self.matches.append(result)
                self.stats[result.status] += 1
                
                # Log
                if result.status == 'found':
                    logger.info(f"Satır {card.row_number}: ✅ Eşleşti (skor: {result.match_score:.0f}) - {result.matched_file}")
                elif result.status == 'missing':
                    logger.warning(f"Satır {card.row_number}: ❌ Bulunamadı - {result.log_message}")
                else:  # conflict
                    logger.error(f"Satır {card.row_number}: ⚠️ CONFLICT - {len(result.conflict_files)} dosya")
                    
            except Exception as e:
                logger.error(f"Satır {card.row_number} hatası: {str(e)}")
                self.matches.append(MatchResult(
                    card.row_number, card.raw_text, "missing",
                    log_message=f"Hata: {str(e)}"
                ))
                self.stats['missing'] += 1
    
    def _match_single_card(self, card: CardInfo) -> MatchResult:
        """
        Tek kart eşleştir
        
        Eşleştirme mantığı:
        1. Hard rules: is_signed, is_base, denominator eşleşmeli
        2. İçerik eşleşmesi:
           - Excel'deki TÜM parçalar dosyada olmalı
           - Dosyada FAZLALIK olmamalı (veya çok az)
        
        Skor: 100 - (eksik_parça * 10) - (fazla_parça * 5)
        """
        card_parts = card.get_all_parts()
        candidates = []
        
        for filename, file_info in self.parsed_files.items():
            # HARD RULES
            
            # 1. İmzalı kontrolü
            if card.is_signed != file_info.is_signed:
                continue
            
            # 2. Base kontrolü
            if card.is_base != file_info.is_base:
                continue
            
            # 3. Denominator kontrolü (base değilse)
            if not card.is_base and card.denominator > 0:
                if file_info.denominator != card.denominator:
                    continue
            
            # İÇERİK EŞLEŞMESİ
            file_parts = file_info.content_parts
            
            # Excel'deki parçaların kaçı dosyada var?
            matched_parts = 0
            for card_part in card_parts:
                # Exact match önce kontrol
                if card_part in file_parts:
                    matched_parts += 1
                else:
                    # Fuzzy: 2 karakter tolerans (typo için)
                    # singo vs snigo gibi durumlar için
                    best_similarity = 0
                    for file_part in file_parts:
                        # Uzunluk çok farklıysa atla
                        len_diff = abs(len(card_part) - len(file_part))
                        if len_diff > 2:
                            continue
                        
                        similarity = SequenceMatcher(None, card_part, file_part).ratio()
                        best_similarity = max(best_similarity, similarity)
                    
                    # %75+ benzerlik = 2 karakter tolerans
                    # 5 harfli kelimede 2 harf fark = %60, ama swap için daha yüksek
                    # singo vs snigo = %80 (swap)
                    # singo vs sango = %80 (1 değişik)
                    if best_similarity >= 0.70:
                        matched_parts += 1
            
            # Eksik parça sayısı
            missing_parts = len(card_parts) - matched_parts
            
            # Fazla parça sayısı (dosyada olup Excel'de olmayan)
            extra_parts = len(file_parts) - len(card_parts)
            if extra_parts < 0:
                extra_parts = 0
            
            # SKOR HESAPLA
            # Tam eşleşme: 100
            # Her eksik parça: -20 (kritik)
            # Her fazla parça: -15 (önemli - TO THE FINALS PATCH gibi)
            
            if missing_parts > 0:
                # Eksik parça varsa eşleşme yok
                continue
            
            score = 100 - (extra_parts * 15)
            
            if score >= 70:  # Minimum eşik
                candidates.append((filename, score, extra_parts))
        
        if len(candidates) == 0:
            return MatchResult(
                card.row_number, card.raw_text, "missing",
                log_message=self._build_debug_info(card)
            )
        
        # En yüksek skora göre sırala
        candidates.sort(key=lambda x: (-x[1], x[2]))  # Yüksek skor, az fazlalık
        
        best_score = candidates[0][1]
        best_extra = candidates[0][2]
        
        # Aynı skora ve fazlalığa sahip birden fazla dosya var mı?
        top_matches = [c for c in candidates if c[1] == best_score and c[2] == best_extra]
        
        if len(top_matches) > 1:
            # CONFLICT!
            return MatchResult(
                card.row_number, card.raw_text, "conflict",
                conflict_files=[c[0] for c in top_matches],
                log_message=f"Aynı skor ({best_score}) ile {len(top_matches)} dosya eşleşti",
                match_score=best_score
            )
        
        # Tek eşleşme - en iyi match
        return MatchResult(
            card.row_number, card.raw_text, "found",
            matched_file=candidates[0][0],
            match_score=candidates[0][1]
        )
    
    def _build_debug_info(self, card: CardInfo) -> str:
        """Debug bilgisi oluştur"""
        info = []
        info.append(f"Player: {card.player_norm}")
        info.append(f"Series: {card.series_norm}")
        info.append(f"Group: {card.group_norm}")
        info.append(f"Denom: {card.denominator}")
        
        if card.is_signed:
            info.append("İmzalı: Evet")
        if card.is_base:
            info.append("Base: Evet")
        
        return " | ".join(info)
    
    def _create_backup(self) -> Optional[Path]:
        """Rename edilecek dosyaları yedekle"""
        if not self.add_date_prefix:
            return None
        
        folder_name = self.image_dir.name
        documents_dir = Path.home() / "Documents" / "MythosCards"
        backup_main_dir = documents_dir / "Backup"
        backup_dir = backup_main_dir / f"{self.date_str}_{folder_name}"
        
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        backed_up_count = 0
        
        for match in self.matches:
            if match.status == 'found':
                parsed = self.parsed_files.get(match.matched_file)
                
                # Zaten tarih prefix'i varsa yedekleme
                if parsed and parsed.has_date:
                    continue
                
                source_file = self.image_dir / match.matched_file
                backup_file = backup_dir / match.matched_file
                
                if source_file.exists() and not backup_file.exists():
                    shutil.copy2(source_file, backup_file)
                    backed_up_count += 1
        
        if backed_up_count > 0:
            logger.info(f"{backed_up_count} dosya yedeklendi: {backup_dir}")
        
        return backup_dir

    def _rename_physical_files(self) -> None:
        """Fiziksel dosyaları tarih prefix'i ile rename et"""
        if not self.add_date_prefix:
            logger.info("Tarih ekleme kapalı, rename atlanıyor")
            return
        
        renamed_count = 0
        rename_map = {}
        
        for match in self.matches:
            if match.status == 'found':
                parsed = self.parsed_files.get(match.matched_file)
                
                # Zaten tarih prefix'i varsa EKLEME
                if parsed and parsed.has_date:
                    continue
                
                old_name = match.matched_file
                new_name = f"{self.date_str}_{old_name}"
                rename_map[old_name] = new_name
        
        # Fiziksel rename
        for old_name, new_name in rename_map.items():
            old_path = self.image_dir / old_name
            new_path = self.image_dir / new_name
            
            if old_path.exists():
                if new_path.exists():
                    logger.warning(f"Hedef dosya zaten var, atlıyor: {new_name}")
                else:
                    old_path.rename(new_path)
                    renamed_count += 1
                    logger.info(f"Renamed: {old_name} → {new_name}")
        
        # Match'lerdeki dosya adlarını güncelle
        for match in self.matches:
            if match.status == 'found' and match.matched_file in rename_map:
                match.matched_file = rename_map[match.matched_file]
        
        logger.info(f"{renamed_count} dosya yeniden adlandırıldı")
    
    def _update_image_column(self) -> None:
        """B kolonunu (Görsel Dosyası) güncelle"""
        try:
            data = pd.read_excel(self.excel_file, sheet_name="Çıktı")
            
            # B kolonu (index 1) zaten var olmalı
            if len(data.columns) < 2:
                raise ValueError("Excel'de B kolonu yok!")
            
            # Match sonuçlarını B kolonuna yaz
            for match in self.matches:
                row_idx = match.row_number - 2  # Excel satır → DataFrame index
                
                if 0 <= row_idx < len(data):
                    if match.status == 'found':
                        data.iloc[row_idx, 1] = match.matched_file  # B kolonu = index 1
                    elif match.status == 'conflict':
                        data.iloc[row_idx, 1] = f"CONFLICT: {', '.join(match.conflict_files[:3])}"
                    else:
                        data.iloc[row_idx, 1] = ""
            
            # Excel'e yaz
            with pd.ExcelWriter(self.excel_file, engine='openpyxl', mode='a',
                               if_sheet_exists='replace') as writer:
                data.to_excel(writer, sheet_name="Çıktı", index=False)
            
            logger.info("Görsel Dosyası kolonu (B) güncellendi")
            
        except Exception as e:
            raise ValueError(f"Excel güncelleme hatası: {str(e)}")
    
    def _generate_report(self) -> Dict[str, any]:
        """Sonuç raporu"""
        total = len(self.matches)
        success_rate = (self.stats['found'] / total * 100) if total > 0 else 0
        
        warnings = []
        for match in self.matches:
            if match.status == 'missing':
                warnings.append({
                    'row': match.row_number,
                    'column': 'G',
                    'type': 'Missing Image',
                    'message': f"Görsel bulunamadı - {match.log_message}"
                })
            elif match.status == 'conflict':
                warnings.append({
                    'row': match.row_number,
                    'column': 'G',
                    'type': 'Image Conflict',
                    'message': f"CONFLICT: {match.log_message} - Dosyalar: {match.conflict_files}"
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
            'date_added': self.add_date_prefix
        }


# Public API
def process_image_mapping(excel_file: str, image_dir: str, 
                         date: str = None, add_date_prefix: bool = False) -> Dict[str, any]:
    """Part 2 ana fonksiyon"""
    matcher = ImageMatcher(
        Path(excel_file), 
        Path(image_dir), 
        date,
        add_date_prefix
    )
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
    
    print("Part 2 - Image Matcher v2.1")
    print("Excel kolonları: player_name, series_name, group, denominator, is_signed")