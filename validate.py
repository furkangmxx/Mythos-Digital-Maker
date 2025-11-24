"""
MythosCards Exporter - Validation Rules
Checklist doğrulama kuralları ve dry-run raporu
"""

import logging
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass
import pandas as pd

from utils import ValidationError, is_numeric_value, safe_int, normalize_text
from headers import HeaderProcessor, VariantInfo

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Doğrulama sonucu"""
    is_valid: bool
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]
    summary: Dict[str, Any]


class ChecklistValidator:
    """Checklist doğrulama sınıfı"""
    
    def __init__(self, data: pd.DataFrame, header_processor: HeaderProcessor):
        self.data = data
        self.header_processor = header_processor
        self.errors = []
        self.warnings = []
        
    def validate_all(self) -> ValidationResult:
        """Tüm doğrulama kurallarını çalıştır"""
        logger.info("Checklist doğrulama başlıyor")
        
        # Header hatalarını ekle
        self.errors.extend(self.header_processor.errors)
        self.warnings.extend(self.header_processor.warnings)
        
        # Veri doğrulama
        self._validate_required_fields()
        self._validate_variant_pairs()
        self._validate_numeric_values()
        self._validate_base_column()
        self._detect_duplicate_rows()
        
        is_valid = len([e for e in self.errors if e.get('blocking', True)]) == 0
        
        summary = self._generate_summary()
        
        logger.info(f"Doğrulama tamamlandı. Geçerli: {is_valid}, Hata: {len(self.errors)}, Uyarı: {len(self.warnings)}")
        
        return ValidationResult(
            is_valid=is_valid,
            errors=self.errors,
            warnings=self.warnings,
            summary=summary
        )
    
    def _validate_required_fields(self) -> None:
        """Gerekli alanları kontrol et"""
        series_idx = self.header_processor.get_series_column_index()
        player_idx = self.header_processor.get_player_column_index()
        group_idx = self.header_processor.get_group_column_index()
        
        for row_idx in range(len(self.data)):
            row_data = self.data.iloc[row_idx]
            
            # Seri Adı kontrolü
            if series_idx is not None:
                series_value = normalize_text(str(row_data.iloc[series_idx]))
                if not series_value:
                    # Grup varsa kontrol et
                    if group_idx is not None:
                        group_value = normalize_text(str(row_data.iloc[group_idx]))
                        if not group_value:
                            self._add_error(
                                row_idx + 2,  # Excel 1-based + header
                                "Seri Adı",
                                "Required Field",
                                "Seri Adı boş (Grup da boş)"
                            )
                    else:
                        self._add_error(
                            row_idx + 2,
                            "Seri Adı", 
                            "Required Field",
                            "Seri Adı boş"
                        )
            
            # Oyuncu Adı kontrolü
            if player_idx is not None:
                player_value = normalize_text(str(row_data.iloc[player_idx]))
                if not player_value:
                    self._add_error(
                        row_idx + 2,
                        "Oyuncu Adı",
                        "Required Field", 
                        "Oyuncu Adı boş"
                    )
    
    def _validate_variant_pairs(self) -> None:
        """Variant çiftlerini kontrol et"""
        variant_pairs = self.header_processor.get_variant_pairs()
        
        for row_idx in range(len(self.data)):
            row_data = self.data.iloc[row_idx]
            
            for denominator, pair in variant_pairs.items():
                normal_variant = pair.get('normal')
                signed_variant = pair.get('signed')
                
                normal_value = None
                signed_value = None
                
                # Normal variant değeri
                if normal_variant:
                    normal_idx = self.header_processor.get_column_index(normal_variant.column_name)
                    if normal_idx is not None:
                        normal_cell = row_data.iloc[normal_idx]
                        if pd.notna(normal_cell) and str(normal_cell).strip():
                            normal_value = safe_int(normal_cell)
                
                # Signed variant değeri
                if signed_variant:
                    signed_idx = self.header_processor.get_column_index(signed_variant.column_name)
                    if signed_idx is not None:
                        signed_cell = row_data.iloc[signed_idx]
                        if pd.notna(signed_cell) and str(signed_cell).strip():
                            signed_value = safe_int(signed_cell)

                            
    
    def _validate_numeric_values(self) -> None:
        """Sayısal değerleri kontrol et"""
        variant_pairs = self.header_processor.get_variant_pairs()
        base_idx = self.header_processor.get_base_column_index()
        
        for row_idx in range(len(self.data)):
            row_data = self.data.iloc[row_idx]
            
            # Variant sütunları
            for denominator, pair in variant_pairs.items():
                for variant_type, variant_info in pair.items():
                    if variant_info is None:
                        continue
                    
                    col_idx = self.header_processor.get_column_index(variant_info.column_name)
                    if col_idx is None:
                        continue
                    
                    cell_value = row_data.iloc[col_idx]
                    
                    if pd.notna(cell_value) and str(cell_value).strip():
                        if not is_numeric_value(cell_value):
                            self._add_error(
                                row_idx + 2,
                                variant_info.column_name,
                                "Invalid Value",
                                f"Sayısal olmayan değer: {cell_value}"
                            )
                        else:
                            numeric_value = safe_int(cell_value)
                            
                            # Negatif değer kontrolü
                            if numeric_value < 0:
                                self._add_error(
                                    row_idx + 2,
                                    variant_info.column_name,
                                    "Negative Value",
                                    f"Negatif değer: {numeric_value}"
                                )
                            
                            # Payda aşımı kontrolü
                            elif numeric_value > denominator:
                                self._add_warning(
                                    row_idx + 2,
                                    variant_info.column_name,
                                    "Value Exceeds Denominator",
                                    f"Değer paydadan fazla: {numeric_value} > {denominator} (yine de {denominator} kart oluşturulacak)"
                                )

                            elif numeric_value < denominator and numeric_value > 0:
                                self._add_warning(
                                    row_idx + 2,
                                    variant_info.column_name,
                                    "Value Less Than Denominator",
                                    f"Değer paydadan az: {numeric_value} < {denominator} (yine de {denominator} kart oluşturulacak)"
                    )
            # Base sütunu
            if base_idx is not None:
                base_value = row_data.iloc[base_idx]
                
                if pd.notna(base_value) and str(base_value).strip():
                    if not is_numeric_value(base_value):
                        self._add_error(
                            row_idx + 2,
                            "Base",
                            "Invalid Value",
                            f"Base için sayısal olmayan değer: {base_value}"
                        )
                    else:
                        numeric_value = safe_int(base_value)
                        if numeric_value < 0:
                            self._add_error(
                                row_idx + 2,
                                "Base",
                                "Negative Value",
                                f"Base için negatif değer: {numeric_value}"
                            )
    
    def _validate_base_column(self) -> None:
        """Base sütunu özel kontrolü"""
        base_idx = self.header_processor.get_base_column_index()
        if base_idx is None:
            return
        
        for row_idx in range(len(self.data)):
            row_data = self.data.iloc[row_idx]
            base_value = row_data.iloc[base_idx]
            
            if pd.notna(base_value) and str(base_value).strip():
                numeric_value = safe_int(base_value)
                
                # Base değeri çok büyükse uyarı
                if numeric_value > 999:
                    self._add_warning(
                        row_idx + 2,
                        "Base",
                        "Large Base Value",
                        f"Çok büyük Base değeri: {numeric_value}X"
                    )
    
    def _detect_duplicate_rows(self) -> None:
        """Çift satırları tespit et"""
        player_idx = self.header_processor.get_player_column_index()
        group_idx = self.header_processor.get_group_column_index()
        series_idx = self.header_processor.get_series_column_index()
        
        if player_idx is None:
            return
        
        # Her sütun için grupla
        variant_pairs = self.header_processor.get_variant_pairs()
        
        for denominator, pair in variant_pairs.items():
            for variant_type, variant_info in pair.items():
                if variant_info is None:
                    continue
                
                col_idx = self.header_processor.get_column_index(variant_info.column_name)
                if col_idx is None:
                    continue
                
                # Oyuncu + Grup kombinasyonlarını topla
                player_group_sums = {}
                
                for row_idx in range(len(self.data)):
                    row_data = self.data.iloc[row_idx]
                    
                    player = normalize_text(str(row_data.iloc[player_idx]))
                    group = ""
                    if group_idx is not None:
                        group = normalize_text(str(row_data.iloc[group_idx]))
                    elif series_idx is not None:
                        group = normalize_text(str(row_data.iloc[series_idx]))
                    
                    if not player:
                        continue
                    
                    key = (player, group)
                    cell_value = row_data.iloc[col_idx]
                    
                    if pd.notna(cell_value) and str(cell_value).strip():
                        numeric_value = safe_int(cell_value)
                        if numeric_value > 0:
                            if key not in player_group_sums:
                                player_group_sums[key] = {'total': 0, 'rows': []}
                            
                            player_group_sums[key]['total'] += numeric_value
                            player_group_sums[key]['rows'].append(row_idx + 2)
                
                # Çoklu satırları raporla
                for (player, group), data in player_group_sums.items():
                    if len(data['rows']) > 1:
                        self._add_warning(
                            data['rows'][0],  # İlk satır
                            variant_info.column_name,
                            "Duplicate Rows",
                            f"Çoklu satır ({player}, {group}): {data['rows']} -> toplam {data['total']}"
                        )
    
    def _add_error(self, row: int, column: str, error_type: str, message: str, blocking: bool = True) -> None:
        """Hata ekle - geliştirilmiş format"""
        
        # Profesyonel log formatı
        log_message = f"HATA: {error_type}\n"
        log_message += f"│ Satır: {row}, Sütun: {column}\n"
        log_message += f"│ Açıklama: {message}\n"
        log_message += f"└ Durum: {'Engelleyici' if blocking else 'Uyarı'}"
        
        self.errors.append({
            'row': row,
            'column': column,
            'type': error_type,
            'message': message,
            'blocking': blocking,
            'formatted_message': log_message
        })

    def _add_warning(self, row: int, column: str, warning_type: str, message: str) -> None:
        """Uyarı ekle"""
        self.warnings.append({
            'row': row,
            'column': column,
            'type': warning_type,
            'message': message
        })
    
    def _generate_summary(self) -> Dict[str, Any]:
        """Doğrulama özeti oluştur"""
        total_rows = len(self.data)
        blocking_errors = len([e for e in self.errors if e.get('blocking', True)])
        
        # Error türleri
        error_types = {}
        for error in self.errors:
            error_type = error.get('type', 'Unknown')
            error_types[error_type] = error_types.get(error_type, 0) + 1
        
        # Warning türleri
        warning_types = {}
        for warning in self.warnings:
            warning_type = warning.get('type', 'Unknown')
            warning_types[warning_type] = warning_types.get(warning_type, 0) + 1
        
        return {
            'total_rows': total_rows,
            'total_errors': len(self.errors),
            'blocking_errors': blocking_errors,
            'total_warnings': len(self.warnings),
            'error_types': error_types,
            'warning_types': warning_types,
            'is_processable': blocking_errors == 0
        }


def validate_checklist(data: pd.DataFrame, header_processor: HeaderProcessor) -> ValidationResult:
    """Checklist doğrula (convenience function)"""
    validator = ChecklistValidator(data, header_processor)
    return validator.validate_all()


def create_dry_run_report(validation_result: ValidationResult) -> Dict[str, Any]:
    """Dry-run raporu oluştur"""
    return {
        'title': 'Kural Raporu (Önizleme)',
        'timestamp': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S'),
        'summary': validation_result.summary,
        'errors': validation_result.errors,
        'warnings': validation_result.warnings,
        'recommendation': 'Devam Et' if validation_result.is_valid else 'Hataları Düzelt'
    }


if __name__ == "__main__":
    # Test
    import logging
    from .headers import HeaderProcessor
    
    logging.basicConfig(level=logging.INFO)
    
    # Test data oluştur
    test_data = pd.DataFrame({
        'Seri Adı': ['Test Series', '', 'Test Series'],
        'Oyuncu Adı': ['Player 1', 'Player 2', 'Player 1'],
        '1/1': [1, 0, 0],
        '1/1 İmzalı': [0, 1, 1],  # Error: Player 1 çift doldu
        '/5': [3, 7, 2],  # Warning: 7 > 5
        '/5 İmzalı': [0, 0, 0],
        'Base': [10, 'invalid', 0]  # Error: invalid
    })
    
    headers = list(test_data.columns)
    header_processor = HeaderProcessor(headers)
    
    result = validate_checklist(test_data, header_processor)
    print(f"Validation result: {result.summary}")
    print(f"Errors: {len(result.errors)}")
    print(f"Warnings: {len(result.warnings)}")