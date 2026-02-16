"""
MythosCards Exporter - Excel Export (v2.0)
Excel çıktı dosyası oluşturma ve yazma

DEĞİŞİKLİK: CardLine objelerini doğrudan Excel'e gönder (string'e çevirmeden)
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

from utils import create_series_dir, safe_filename, get_current_user, ist_timestamp
from io_ops import ExcelWriter, create_output_excel
from expand import CardLine, lines_to_strings, group_lines_by_series
from sorters import sort_card_lines_turkish
from version import PROGRAM_VERSION

logger = logging.getLogger(__name__)


class ExportManager:
    """Export yönetimi sınıfı"""
    
    def __init__(self, 
                 lines: List[CardLine],
                 errors: List[Dict[str, Any]],
                 warnings: List[Dict[str, Any]],
                 config: Dict[str, Any]):
        
        self.lines = lines
        self.errors = errors
        self.warnings = warnings
        self.config = config
        
        # Sıralanmış satırlar
        self.sorted_lines = sort_card_lines_turkish(lines)
        
        # Seri grupları
        self.series_groups = group_lines_by_series(self.sorted_lines)
        
    def export_all(self, per_series: bool = True) -> List[Path]:
        """Tüm serileri export et"""
        exported_files = []
        
        if per_series and len(self.series_groups) > 1:
            # Her seri için ayrı dosya
            for series_name, series_lines in self.series_groups.items():
                file_path = self._export_single_series(series_name, series_lines)
                if file_path:
                    exported_files.append(file_path)
        else:
            # Tek dosya
            series_name = self._get_primary_series_name()
            file_path = self._export_single_series(series_name, self.sorted_lines)
            if file_path:
                exported_files.append(file_path)
        
        return exported_files
    
    def _export_single_series(self, series_name: str, lines: List[CardLine]) -> Optional[Path]:
        """Tek seri export et"""
        try:
            logger.info(f"Export başlıyor: {series_name} ({len(lines)} kart)")
            
            # Çıktı dizini
            series_dir = create_series_dir(series_name)
            output_file = series_dir / f"{safe_filename(series_name)}_Excel.xlsx"
            
            # ÖNEMLİ: CardLine objelerini doğrudan gönder (string'e çevirmeden!)
            # Eski kod: line_strings = lines_to_strings(lines)
            # Yeni kod: lines'ı doğrudan gönder
            
            # Özet
            summary = self._generate_series_summary(lines)
            
            # Seri-spesifik hata/uyarıları filtrele
            series_errors = self._filter_errors_for_series(series_name)
            series_warnings = self._filter_warnings_for_series(series_name)
            
            # Config
            export_config = self._build_export_config(series_name)
            
            # Excel oluştur - CardLine listesi gönder
            final_path = create_output_excel(
                output_file,
                lines,  # ← DEĞİŞTİ: CardLine listesi (string değil!)
                summary,
                series_errors,
                series_warnings,
                export_config
            )
            
            logger.info(f"Export tamamlandı: {final_path}")
            return final_path
            
        except Exception as e:
            logger.error(f"Export hatası ({series_name}): {str(e)}")
            return None
        
    def _generate_series_summary(self, lines: List[CardLine]) -> Dict[str, Any]:
        """Seri özeti oluştur"""
        
        # Genel sayılar
        total_cards = len(lines)
        unique_players = set(line.player for line in lines)
        
        # Variant özeti
        variant_counts = {}
        base_summary = {}
        player_totals = {}
        
        for line in lines:
            # Player totals
            if line.player not in player_totals:
                player_totals[line.player] = 0
            player_totals[line.player] += 1
            
            # Variant counts
            if line.variant_type == "Base":
                if line.player not in base_summary:
                    base_summary[line.player] = 0
                base_summary[line.player] += 1
                  # Base sayısı
            else:
                if line.variant_type not in variant_counts:
                    variant_counts[line.variant_type] = {'normal': 0, 'signed': 0}
                
                if line.is_signed:
                    variant_counts[line.variant_type]['signed'] += 1
                else:
                    variant_counts[line.variant_type]['normal'] += 1
        
        # Label özeti
        label_counts = {}
        for line in lines:
            label = line.label or "Unknown"
            if label not in label_counts:
                label_counts[label] = 0
            label_counts[label] += 1
        
        return {
            'total_cards': total_cards,
            'total_players': len(unique_players),
            'unique_players': sorted(list(unique_players)),
            'variants': variant_counts,
            'base_summary': base_summary,
            'player_totals': player_totals,
            'label_counts': label_counts,
            'export_timestamp': ist_timestamp()
        }
    
    def _filter_errors_for_series(self, series_name: str) -> List[Dict[str, Any]]:
        """Seri için hataları filtrele"""
        # Şimdilik tüm hataları döndür
        # İleride seri-spesifik filtreleme eklenebilir
        return self.errors.copy()
    
    def _filter_warnings_for_series(self, series_name: str) -> List[Dict[str, Any]]:
        """Seri için uyarıları filtrele"""
        # Şimdilik tüm uyarıları döndür
        return self.warnings.copy()
    
    def _build_export_config(self, series_name: str) -> Dict[str, Any]:
        """Export config oluştur"""
        base_config = {
            'series_name': series_name,
            'export_timestamp': ist_timestamp(),
            'program_version': PROGRAM_VERSION,
            'user': get_current_user(),
            'timezone': 'Europe/Istanbul'
        }
        
        # Orijinal config'i ekle
        base_config.update(self.config)
        
        return base_config
    
    def _get_primary_series_name(self) -> str:
        """Ana seri adını al"""
        if len(self.series_groups) == 1:
            return list(self.series_groups.keys())[0]
        
        # En çok karta sahip seriyi al
        max_count = 0
        primary_series = "MixedSeries"
        
        for series_name, series_lines in self.series_groups.items():
            if len(series_lines) > max_count:
                max_count = len(series_lines)
                primary_series = series_name
        
        return primary_series
    
    def get_export_summary(self) -> Dict[str, Any]:
        """Export özeti"""
        return {
            'total_lines': len(self.lines),
            'total_series': len(self.series_groups),
            'series_names': list(self.series_groups.keys()),
            'total_errors': len(self.errors),
            'total_warnings': len(self.warnings),
            'has_base_cards': any(line.variant_type == "Base" for line in self.lines),
            'unique_players': len(set(line.player for line in self.lines))
        }


class BatchExporter:
    """Toplu export işlemleri"""
    
    def __init__(self):
        self.exported_files = []
        self.failed_exports = []
    
    def export_multiple_series(self, 
                              series_data: Dict[str, List[CardLine]],
                              base_config: Dict[str, Any]) -> Dict[str, Any]:
        """Çoklu seri export"""
        
        results = {
            'successful': [],
            'failed': [],
            'total_files': 0,
            'total_cards': 0
        }
        
        for series_name, lines in series_data.items():
            try:
                # Her seri için ExportManager oluştur
                export_manager = ExportManager(
                    lines=lines,
                    errors=[],  # Seri-spesifik hatalar
                    warnings=[],  # Seri-spesifik uyarılar
                    config=base_config
                )
                
                # Export
                exported_files = export_manager.export_all(per_series=False)
                
                if exported_files:
                    results['successful'].extend(exported_files)
                    results['total_cards'] += len(lines)
                    logger.info(f"Seri export başarılı: {series_name}")
                else:
                    results['failed'].append(series_name)
                    logger.error(f"Seri export başarısız: {series_name}")
                
            except Exception as e:
                results['failed'].append(series_name)
                logger.error(f"Seri export hatası ({series_name}): {str(e)}")
        
        results['total_files'] = len(results['successful'])
        
        return results


def export_card_lines(lines: List[CardLine],
                     errors: List[Dict[str, Any]],
                     warnings: List[Dict[str, Any]], 
                     config: Dict[str, Any],
                     per_series: bool = True) -> List[Path]:
    """Kart satırlarını export et (convenience function)"""
    
    export_manager = ExportManager(lines, errors, warnings, config)
    return export_manager.export_all(per_series)


def create_single_excel_file(output_path: Path,
                            lines: List[CardLine],
                            summary: Dict[str, Any],
                            errors: List[Dict[str, Any]],
                            warnings: List[Dict[str, Any]],
                            config: Dict[str, Any]) -> Path:
    """Tek Excel dosyası oluştur"""
    
    # Satırları sırala
    sorted_lines = sort_card_lines_turkish(lines)
    
    # CardLine objelerini doğrudan gönder
    return create_output_excel(
        output_path,
        sorted_lines,  # CardLine listesi
        summary,
        errors,
        warnings,
        config
    )


def validate_export_requirements(lines: List[CardLine]) -> List[str]:
    """Export gereksinimlerini kontrol et"""
    issues = []
    
    if not lines:
        issues.append("Hiç kart satırı yok")
        return issues
    
    # Player kontrolü
    players_without_names = [line for line in lines if not line.player.strip()]
    if players_without_names:
        issues.append(f"{len(players_without_names)} satırda oyuncu adı eksik")
    
    # Label kontrolü
    lines_without_labels = [line for line in lines if not line.label.strip()]
    if lines_without_labels:
        issues.append(f"{len(lines_without_labels)} satırda label eksik")
    
    # Variant kontrolü (sayılı denominatorlar için)
    invalid_variants = [line for line in lines if isinstance(line.denominator, int) and line.denominator <= 0]
    if invalid_variants:
        issues.append(f"{len(invalid_variants)} satırda geçersiz payda")
    
    return issues


def create_export_config(input_file: str,
                        output_dir: str,
                        per_series: bool,
                        dry_run: bool,
                        locale: str,
                        additional_options: Dict[str, Any] = None) -> Dict[str, Any]:
    """Export config oluştur"""
    
    config = {
        'input_file': input_file,
        'output_directory': output_dir,
        'per_series_export': per_series,
        'dry_run_enabled': dry_run,
        'locale_preference': locale,
        'processing_timestamp': ist_timestamp(),
        'program_version': PROGRAM_VERSION
    }
    
    if additional_options:
        config.update(additional_options)
    
    return config


# Export sonuç sınıfları
class ExportResult:
    """Export sonucu"""
    
    def __init__(self, 
                 success: bool,
                 files: List[Path],
                 errors: List[str],
                 summary: Dict[str, Any]):
        self.success = success
        self.files = files
        self.errors = errors
        self.summary = summary
    
    @property
    def file_count(self) -> int:
        return len(self.files)
    
    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    
    def __str__(self) -> str:
        status = "✅ Başarılı" if self.success else "❌ Başarısız"
        return f"Export {status}: {self.file_count} dosya, {len(self.errors)} hata"


def create_export_result(files: List[Path],
                        errors: List[str],
                        summary: Dict[str, Any]) -> ExportResult:
    """Export result oluştur"""
    success = len(files) > 0 and len(errors) == 0
    return ExportResult(success, files, errors, summary)


if __name__ == "__main__":
    # Test
    import logging
    from expand import CardLine
    
    logging.basicConfig(level=logging.INFO)
    
    # Test data
    test_lines = [
        CardLine("Okan Buruk Duo (1/25)", "Okan Buruk", "Duo", "/25", 25, 1, False, "Test Series", "Grup A"),
        CardLine("Mario Jardel Trio (1/5)", "Mario Jardel", "Trio", "/5", 5, 1, True, "Test Series", "Grup B"),
        CardLine("Fernando Muslera Goalkeeper Base", "Fernando Muslera", "Goalkeeper", "Base", 78, 78, False, "Test Series", None)
    ]
    
    test_errors = []
    test_warnings = []
    test_config = create_export_config(
        "test.xlsx", "output", True, False, "tr"
    )
    
    # Export test
    export_manager = ExportManager(test_lines, test_errors, test_warnings, test_config)
    summary = export_manager.get_export_summary()
    
    print(f"Export summary: {summary}")
    print("Export test completed!")