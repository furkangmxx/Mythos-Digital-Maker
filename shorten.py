"""
MythosCards Exporter - Part 3: Dosya Adi Kisaltma

Part 2'den sonra kullanilir.
Excel B kolonundaki gorsel isimlerini okur,
uzun olanlari hem dosyada hem Excel'de kisaltir.
"""

import os
import shutil
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {'.jpg', '.jpeg', '.png'}


@dataclass
class ShortenItem:
    """Kisaltilacak dosya bilgisi"""
    excel_row: int          # Excel satir numarasi
    original_name: str      # Mevcut dosya adi
    new_name: str           # Yeni (kisaltilmis) dosya adi
    needs_shortening: bool  # Kisaltma gerekiyor mu


class ImageShortener:
    """Part 3 ana sinifi - Excel'deki gorsel isimlerini kisalt"""

    def __init__(self, excel_file: Path, image_dir: Path, max_length: int = 97):
        self.excel_file = Path(excel_file)
        self.image_dir = Path(image_dir)
        self.max_length = max_length
        self.date_str = datetime.now().strftime("%Y%m%d")

        self.items_to_process: List[ShortenItem] = []
        self.stats = {'total': 0, 'shortened': 0, 'skipped': 0, 'error': 0}

    def validate_preview(self) -> Dict:
        """On dogrulama - kac dosya etkilenecek"""
        logger.info("=== KISALTMA ON DOGRULAMASI ===")

        self._read_excel_and_analyze()

        needs_shortening = [f for f in self.items_to_process if f.needs_shortening]
        already_ok = [f for f in self.items_to_process if not f.needs_shortening]

        total = len(self.items_to_process)
        to_shorten = len(needs_shortening)
        ok_count = len(already_ok)

        # Kullanici icin anlasilir mesaj
        message_lines = [
            f"Excel'de {total} gorsel ismi bulundu",
            f"{ok_count} dosya zaten uygun uzunlukta",
            f"{to_shorten} dosya kisaltilacak",
        ]

        preview = {
            'total_files': total,
            'needs_shortening': to_shorten,
            'already_ok': ok_count,
            'max_length': self.max_length,
            'examples': [],
            'message': '\n'.join(message_lines)
        }

        # Ornek goster (ilk 5)
        for item in needs_shortening[:5]:
            preview['examples'].append({
                'original': item.original_name,
                'new': item.new_name,
                'saved_chars': len(item.original_name) - len(item.new_name)
            })

        logger.info(f"Excel'de gorsel ismi olan satir: {total}")
        logger.info(f"Kisaltilacak: {to_shorten}")
        logger.info(f"Zaten uygun: {ok_count}")

        return preview

    def process_all(self) -> Dict:
        """Gercek kisaltma islemi"""
        logger.info(f"Part 3 basliyor - Max uzunluk: {self.max_length}")

        # 1. Excel'den gorsel isimlerini oku ve analiz et
        self._read_excel_and_analyze()

        # 2. Yedekleme (tum klasor)
        backup_dir = self._create_backup()

        # 3. Fiziksel rename
        self._rename_files()

        # 4. Excel guncelle
        self._update_excel()

        # 5. Rapor - anlasilir istatistikler
        total = self.stats['total']
        shortened = self.stats['shortened']
        skipped = self.stats['skipped']
        errors = self.stats['error']

        # Kullanici icin anlasilir mesaj olustur
        message_lines = [
            f"Excel'de {total} gorsel ismi bulundu",
            f"{skipped} dosya zaten uygun uzunlukta (degismedi)",
            f"{shortened} dosya kisaltildi",
        ]
        if errors > 0:
            message_lines.append(f"{errors} dosyada hata olustu")

        return {
            'success': True,
            'total_files': total,
            'shortened_count': shortened,
            'skipped_count': skipped,
            'error_count': errors,
            'backup_dir': str(backup_dir) if backup_dir else None,
            'max_length': self.max_length,
            'message': '\n'.join(message_lines)
        }

    def _read_excel_and_analyze(self) -> None:
        """Excel B kolonundan gorsel isimlerini oku ve analiz et"""
        if not self.excel_file.exists():
            raise FileNotFoundError(f"Excel dosyasi bulunamadi: {self.excel_file}")

        try:
            data = pd.read_excel(self.excel_file, sheet_name="Çıktı")
        except ValueError:
            # Sadece sheet adi bulunamadi hatasi - alternatif dene
            logger.info("'Çıktı' sheet'i bulunamadi, ilk sheet kullaniliyor")
            data = pd.read_excel(self.excel_file, sheet_name=0)

        if len(data.columns) < 2:
            raise ValueError("Excel'de B kolonu (Gorsel Dosyasi) yok!")

        self.items_to_process = []
        self.stats = {'total': 0, 'shortened': 0, 'skipped': 0, 'error': 0}

        for idx, row in data.iterrows():
            row_num = idx + 2  # Excel satir numarasi (header=1, data starts at 2)

            # B kolonu (index 1) = Gorsel Dosyasi
            image_name = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ""

            # Bos veya gecersiz degerleri atla
            if not image_name or image_name == "" or image_name == "nan":
                continue

            # CONFLICT satirlarini atla
            if image_name.startswith("CONFLICT"):
                continue

            self.stats['total'] += 1

            # Kisaltma gerekiyor mu?
            current_length = len(image_name)
            needs_shortening = current_length > self.max_length

            new_name = image_name
            if needs_shortening:
                new_name = self._calculate_shortened_name(image_name)

            self.items_to_process.append(ShortenItem(
                excel_row=row_num,
                original_name=image_name,
                new_name=new_name,
                needs_shortening=needs_shortening and (new_name != image_name)
            ))

        logger.info(f"Excel'den okunan gorsel sayisi: {self.stats['total']}")

    def _calculate_shortened_name(self, filename: str) -> str:
        """
        Dosya adini kisalt - icerik kismini sondan KELIME KELIME kes

        KURALLAR:
        1. Denominator (_25, _base) KESiNLiKLE korunur
        2. Signed marker (_s) KESiNLiKLE korunur
        3. Tarih prefix korunur
        4. Uzanti korunur
        5. Icerik sondan KELIME SINIRLARINDA kesilir (arda_kutal_mehmet -> arda_kutal)

        Format: [YYYYMMDD_]content[_s]_denom.ext
        """
        # 1. Uzantiyi ayir
        ext_match = re.search(r'(\.(jpg|jpeg|png))$', filename, re.IGNORECASE)
        if ext_match:
            extension = ext_match.group(1).lower()
            name = filename[:-len(extension)]
        else:
            extension = ""
            name = filename

        # 2. Tarih prefix kontrolu (YYYYMMDD_)
        date_prefix = ""
        date_match = re.match(r'^(\d{8}_)', name)
        if date_match:
            date_prefix = date_match.group(1)
            name = name[len(date_prefix):]

        # 3. Sondaki suffix'i bul (_s_25, _25, _s_base, _base)
        # ONEMLI: Bu kisim KESINLIKLE korunacak!
        suffix_match = re.search(r'(_s)?_(\d+|base)$', name)
        if suffix_match:
            suffix = suffix_match.group(0)  # _s_25 veya _25 veya _base
            content = name[:-len(suffix)]
        else:
            # Suffix bulunamadiysa kisaltma yapma (guvenlik)
            logger.warning(f"Denominator bulunamadi, kisaltma atlanıyor: {filename}")
            return filename

        # 4. Sabit parcalarin uzunlugu
        fixed_length = len(date_prefix) + len(suffix) + len(extension)
        available_for_content = self.max_length - fixed_length

        if available_for_content < 3:
            logger.warning(f"Kisaltma mumkun degil (cok uzun sabit parcalar): {filename}")
            return filename

        if len(content) <= available_for_content:
            # Zaten uygun
            return filename

        # 5. KELIME SINIRLARINDA kisalt (sondan kelime kelime at)
        words = content.split('_')
        shortened_content = content

        while len(shortened_content) > available_for_content and len(words) > 1:
            # Son kelimeyi at
            words.pop()
            shortened_content = '_'.join(words)

        # Hala cok uzunsa karakter bazli kes (son care)
        if len(shortened_content) > available_for_content:
            shortened_content = shortened_content[:available_for_content].rstrip('_')

        new_name = f"{date_prefix}{shortened_content}{suffix}{extension}"
        return new_name

    def _create_backup(self) -> Optional[Path]:
        """Tum gorsel klasorunu yedekle"""
        folder_name = self.image_dir.name
        documents_dir = Path.home() / "Documents" / "MythosCards"
        backup_main_dir = documents_dir / "Backup"
        backup_dir = backup_main_dir / f"{self.date_str}_Shorten_{folder_name}"

        backup_dir.mkdir(parents=True, exist_ok=True)

        backed_up_count = 0

        # Tum desteklenen dosyalari yedekle
        for ext in SUPPORTED_EXTENSIONS:
            for pattern in [f"*{ext}", f"*{ext.upper()}"]:
                for file_path in self.image_dir.glob(pattern):
                    backup_file = backup_dir / file_path.name
                    if not backup_file.exists():
                        shutil.copy2(file_path, backup_file)
                        backed_up_count += 1

        logger.info(f"{backed_up_count} dosya yedeklendi: {backup_dir}")
        return backup_dir

    def _rename_files(self) -> None:
        """Fiziksel dosyalari rename et"""
        for item in self.items_to_process:
            if not item.needs_shortening:
                self.stats['skipped'] += 1
                continue

            old_path = self.image_dir / item.original_name
            new_path = self.image_dir / item.new_name

            if not old_path.exists():
                logger.warning(f"Dosya bulunamadi: {item.original_name}")
                self.stats['error'] += 1
                continue

            if new_path.exists() and old_path != new_path:
                logger.warning(f"Hedef dosya zaten var: {item.new_name}")
                self.stats['error'] += 1
                continue

            try:
                old_path.rename(new_path)
                self.stats['shortened'] += 1
                logger.info(f"Renamed: {item.original_name} -> {item.new_name}")
            except Exception as e:
                logger.error(f"Rename hatasi: {item.original_name} - {str(e)}")
                self.stats['error'] += 1

    def _update_excel(self) -> None:
        """Excel B kolonunu (Gorsel Dosyasi) guncelle"""
        try:
            try:
                data = pd.read_excel(self.excel_file, sheet_name="Çıktı")
            except ValueError:
                # Sadece sheet adi bulunamadi hatasi
                logger.info("'Çıktı' sheet'i bulunamadi, ilk sheet kullaniliyor")
                data = pd.read_excel(self.excel_file, sheet_name=0)

            # Kisaltilan isimleri guncelle
            updated_count = 0
            for item in self.items_to_process:
                if item.needs_shortening:
                    row_idx = item.excel_row - 2  # Excel satir -> DataFrame index

                    if 0 <= row_idx < len(data):
                        current_value = str(data.iloc[row_idx, 1]) if pd.notna(data.iloc[row_idx, 1]) else ""

                        if current_value == item.original_name:
                            data.iloc[row_idx, 1] = item.new_name
                            updated_count += 1

            # Excel'e yaz
            with pd.ExcelWriter(self.excel_file, engine='openpyxl', mode='a',
                               if_sheet_exists='replace') as writer:
                data.to_excel(writer, sheet_name="Çıktı", index=False)

            logger.info(f"Excel guncellendi: {updated_count} satir")

        except Exception as e:
            logger.error(f"Excel guncelleme hatasi: {str(e)}")
            raise


# Public API
def validate_shortening_preview(excel_file: str, image_dir: str,
                                max_length: int = 97) -> Dict:
    """On dogrulama - kac dosya etkilenecek"""
    shortener = ImageShortener(
        Path(excel_file),
        Path(image_dir),
        max_length
    )
    return shortener.validate_preview()


def process_shortening(excel_file: str, image_dir: str,
                       max_length: int = 97) -> Dict:
    """Part 3 ana fonksiyon - dosya adlarini kisalt"""
    shortener = ImageShortener(
        Path(excel_file),
        Path(image_dir),
        max_length
    )
    return shortener.process_all()


def validate_shorten_inputs(excel_file: str, image_dir: str) -> List[str]:
    """Input validation"""
    issues = []

    if not Path(excel_file).exists():
        issues.append(f"Excel dosyasi yok: {excel_file}")

    if not Path(image_dir).exists():
        issues.append(f"Gorsel klasoru yok: {image_dir}")

    return issues


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    print("Part 3 - Image Shortener")
    print("Excel B kolonundaki gorsel isimlerini kisaltir")
