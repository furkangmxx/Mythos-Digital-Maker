"""
MythosCards Exporter - Row Expansion
Checklist satırlarını kart listelerine genişletme
"""

import logging
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass
import pandas as pd

from utils import safe_int, normalize_text
from headers import HeaderProcessor, VariantInfo

logger = logging.getLogger(__name__)


@dataclass
class CardLine:
    """Kart satırı bilgisi"""
    text: str
    player: str
    label: str
    variant_type: str  # '1/1', '/5', 'Base'
    denominator: int
    number: int
    is_signed: bool
    series: str
    group: Optional[str] = None


@dataclass
class ExpansionResult:
    """Genişletme sonucu"""
    lines: List[CardLine]
    summary: Dict[str, Any]
    errors: List[Dict[str, Any]]
    warnings: List[Dict[str, Any]]


class RowExpander:
    """Satır genişletme sınıfı"""
    
    def __init__(self, data: pd.DataFrame, header_processor: HeaderProcessor):
        self.data = data
        self.header_processor = header_processor
        self.lines = []
        self.errors = []
        self.warnings = []
        
        # Sütun indeksleri
        self.series_idx = header_processor.get_series_column_index()
        self.player_idx = header_processor.get_player_column_index()
        self.group_idx = header_processor.get_group_column_index()
        self.base_idx = header_processor.get_base_column_index()
    
    def expand_all_rows(self) -> ExpansionResult:
        """Tüm satırları genişlet"""
        logger.info(f"Satır genişletme başlıyor: {len(self.data)} satır")
        
        # Önce çoklu satırları birleştir
        merged_data = self._merge_duplicate_rows()
        
        # Her satırı genişlet
        for row_idx in range(len(merged_data)):
            try:
                self._expand_single_row(row_idx, merged_data.iloc[row_idx])
            except Exception as e:
                logger.error(f"Satır {row_idx + 2} genişletme hatası: {str(e)}")
                self.errors.append({
                    'row': row_idx + 2,
                    'column': 'All',
                    'type': 'Expansion Error',
                    'message': str(e)
                })
        
        summary = self._generate_expansion_summary()
        
        logger.info(f"Genişletme tamamlandı: {len(self.lines)} kart oluşturuldu")
        
        return ExpansionResult(
            lines=self.lines,
            summary=summary,
            errors=self.errors,
            warnings=self.warnings
        )
    
    def _merge_duplicate_rows(self) -> pd.DataFrame:
        """Çoklu satırları birleştir"""
        if self.player_idx is None:
            return self.data.copy()
        
        # Oyuncu + Label kombinasyonlarını groupby ile birleştir
        data_copy = self.data.copy()
        
        # Grouping key oluştur
        grouping_keys = []
        for row_idx in range(len(data_copy)):
            row_data = data_copy.iloc[row_idx]
            
            player = normalize_text(str(row_data.iloc[self.player_idx]))
            label = self._get_label_for_row(row_data)
            
            grouping_keys.append(f"{player}|{label}")
        
        data_copy['_grouping_key'] = grouping_keys
        
        # Numerik sütunları topla
        numeric_columns = []
        variant_pairs = self.header_processor.get_variant_pairs()
        
        for pair in variant_pairs.values():
            for variant_info in [pair.get('normal'), pair.get('signed')]:
                if variant_info:
                    col_idx = self.header_processor.get_column_index(variant_info.column_name)
                    if col_idx is not None:
                        numeric_columns.append(variant_info.column_name)
        
        if self.base_idx is not None:
            numeric_columns.append('Base')
        
        # Groupby ile topla
        agg_dict = {}
        for col in data_copy.columns:
            if col == '_grouping_key':
                continue
            elif col in numeric_columns:
                agg_dict[col] = lambda x: sum(safe_int(val) for val in x if pd.notna(val) and str(val).strip())
            else:
                agg_dict[col] = 'first'  # İlk değeri al
        
        try:
            merged = data_copy.groupby('_grouping_key').agg(agg_dict).reset_index(drop=True)
            
            if len(merged) < len(data_copy):
                logger.info(f"Çoklu satırlar birleştirildi: {len(data_copy)} -> {len(merged)}")
            
            return merged
        except Exception as e:
            logger.warning(f"Satır birleştirme hatası: {str(e)}, orijinal data kullanılıyor")
            return self.data.copy()
    
    def _expand_single_row(self, row_idx: int, row_data: pd.Series) -> None:
        """Tek satırı genişlet"""
        player = normalize_text(str(row_data.iloc[self.player_idx]))
        if not player:
            return  # Boş oyuncu adı, skip
        
        series = ""
        if self.series_idx is not None:
            series = normalize_text(str(row_data.iloc[self.series_idx]))
        
        group = ""
        if self.group_idx is not None:
            group = normalize_text(str(row_data.iloc[self.group_idx]))
        
        if group:
            label = f"{series} {group}"
        else:
            label = series
        
        # Variant sütunlarını işle
        variant_pairs = self.header_processor.get_variant_pairs()
        
        for denominator, pair in variant_pairs.items():
            for variant_type, variant_info in pair.items():
                if variant_info is None:
                    continue
                
                col_idx = self.header_processor.get_column_index(variant_info.column_name)
                if col_idx is None:
                    continue
                
                cell_value = row_data.iloc[col_idx]
                
                if pd.notna(cell_value) and str(cell_value).strip():
                    count = safe_int(cell_value)
                    if count > 0:
                        self._expand_variant(
                            player, label, series, group,
                            variant_info, count, row_idx + 2
                        )
        
        # Base sütununu işle
        if self.base_idx is not None:
            base_value = row_data.iloc[self.base_idx]
            
            if pd.notna(base_value) and str(base_value).strip():
                base_count = safe_int(base_value)
                if base_count > 0:
                    self._expand_base(
                        player, label, series, group,
                        base_count, row_idx + 2
                    )
        # Custom label sütunlarını işle
        if hasattr(self.header_processor, 'custom_labels'):
            for custom_label_name in self.header_processor.custom_labels.keys():
                col_idx = self.header_processor.get_column_index(custom_label_name)
                if col_idx is not None:
                    cell_value = row_data.iloc[col_idx]
                    
                    if pd.notna(cell_value) and str(cell_value).strip():
                        count = safe_int(cell_value)
                        if count > 0:
                            self._expand_custom_label(
                                player, label, series, group,
                                custom_label_name, count, row_idx + 2
                            )

    def _expand_variant(self, player: str, label: str, series: str, group: Optional[str],
                    variant_info: VariantInfo, count: int, row_num: int) -> None:
        """Variant kartlarını genişlet"""
        
        # Her zaman denominator kadar kart oluştur
        actual_count = variant_info.denominator
        
        # Kartları oluştur
        for i in range(1, actual_count + 1):
            line_text = self._build_variant_line(
                player, label, variant_info.denominator, i, variant_info.is_signed
            )
            
            card_line = CardLine(
                text=line_text,
                player=player,
                label=label,
                variant_type=variant_info.display_name,
                denominator=variant_info.denominator,
                number=i,
                is_signed=variant_info.is_signed,
                series=series,
                group=group
            )
            
            self.lines.append(card_line)
    
    def _expand_base(self, player: str, label: str, series: str, group: Optional[str],
                    base_count: int, row_num: int) -> None:
        """Base kartını genişlet - çoklu satır"""
        
        # Base kartlarını tek tek oluştur
        for i in range(base_count):
            line_text = f"{player} {label} Base"  # "78X" kısmını kaldır
            
            card_line = CardLine(
                text=line_text,
                player=player,
                label=label,
                variant_type="Base",
                denominator=base_count,
                number=i + 1,  # Her satırın numarası
                is_signed=False,
                series=series,
                group=group
            )
            
            self.lines.append(card_line)
            
    def _expand_custom_label(self, player: str, label: str, series: str, group: Optional[str],
                            custom_label: str, count: int, row_num: int) -> None:
        """Custom label kartlarını genişlet - Base mantığıyla"""
        
        for i in range(count):
            line_text = f"{player} {label} {custom_label}"
            
            card_line = CardLine(
                text=line_text,
                player=player,
                label=label,
                variant_type=custom_label,
                denominator=count,
                number=i + 1,
                is_signed="İmzalı" in custom_label,
                series=series,
                group=group
            )
            
            self.lines.append(card_line)
        
        logger.debug(f"Custom label genişletildi: {custom_label} x{count}")        
    
    def _build_variant_line(self, player: str, label: str, denominator: int, number: int, is_signed: bool) -> str:
        """Variant kart satırı oluştur"""
        line = f"{player} {label} ({number}/{denominator})"
        
        if is_signed:
            line += " İmzalı"
        
        return line
    
    def _build_base_line(self, player: str, label: str, base_count: int) -> str:
        """Base kart satırı oluştur"""
        # Format: "{N}X {Player} {Label} Base" (no space before X)
        return f"{base_count}X {player} {label} Base"
    
    def _get_label_for_row(self, row_data: pd.Series) -> str:
        """Satır için label al"""
        if self.group_idx is not None:
            group = normalize_text(str(row_data.iloc[self.group_idx]))
            if group:
                return group
        
        if self.series_idx is not None:
            series = normalize_text(str(row_data.iloc[self.series_idx]))
            return series
        
        return "Unknown"
    
    def _generate_expansion_summary(self) -> Dict[str, Any]:
        """Genişletme özeti oluştur"""
        total_cards = len(self.lines)
        
        # Oyuncu sayısı
        unique_players = set(line.player for line in self.lines)
        
        # Variant özeti
        variant_summary = {}
        base_summary = {}
        
        for line in self.lines:
            if line.variant_type == "Base":
                if line.player not in base_summary:
                    base_summary[line.player] = 0
                base_summary[line.player] += line.number
            else:
                if line.variant_type not in variant_summary:
                    variant_summary[line.variant_type] = {'normal': 0, 'signed': 0}
                
                if line.is_signed:
                    variant_summary[line.variant_type]['signed'] += 1
                else:
                    variant_summary[line.variant_type]['normal'] += 1
        
        # Seri özeti
        series_summary = {}
        for line in self.lines:
            series = line.series if line.series else "Unknown"
            if series not in series_summary:
                series_summary[series] = 0
            series_summary[series] += 1
        
        return {
            'total_cards': total_cards,
            'total_players': len(unique_players),
            'unique_players': list(unique_players),
            'variants': variant_summary,
            'base_summary': base_summary,
            'series_summary': series_summary,
            'total_errors': len(self.errors),
            'total_warnings': len(self.warnings)
        }


def expand_checklist_rows(data: pd.DataFrame, header_processor: HeaderProcessor) -> ExpansionResult:
    """Checklist satırlarını genişlet (convenience function)"""
    expander = RowExpander(data, header_processor)
    return expander.expand_all_rows()


def lines_to_strings(lines: List[CardLine]) -> List[str]:
    """CardLine listesini string listesine çevir"""
    return [line.text for line in lines]


def group_lines_by_series(lines: List[CardLine]) -> Dict[str, List[CardLine]]:
    """Satırları seriye göre grupla"""
    series_groups = {}
    
    for line in lines:
        series = line.series if line.series else "Unknown"
        if series not in series_groups:
            series_groups[series] = []
        series_groups[series].append(line)
    
    return series_groups


if __name__ == "__main__":
    # Test
    import logging
    from .headers import HeaderProcessor
    
    logging.basicConfig(level=logging.INFO)
    
    # Test data
    test_data = pd.DataFrame({
        'Seri Adı': ['Test Series', 'Test Series', 'Test Series'],
        'Grup (opsiyonel)': ['Duo', '', 'Trio'],
        'Oyuncu Adı': ['Okan Buruk', 'Mario Jardel', 'Fernando Muslera'],
        '1/1': [1, 0, 0],
        '1/1 İmzalı': [0, 1, 0],
        '/5': [3, 2, 5],
        '/5 İmzalı': [0, 0, 2],
        '/25': [7, 0, 15],
        '/25 İmzalı': [0, 5, 0],
        'Base': [78, 0, 150]
    })
    
    headers = list(test_data.columns)
    header_processor = HeaderProcessor(headers)
    
    result = expand_checklist_rows(test_data, header_processor)
    
    print(f"Expansion summary: {result.summary}")
    print(f"Total lines: {len(result.lines)}")
    print("\nFirst 10 lines:")
    for i, line in enumerate(result.lines[:10]):
        print(f"{i+1}: {line.text}")
    
    if result.errors:
        print(f"\nErrors: {len(result.errors)}")
    if result.warnings:
        print(f"Warnings: {len(result.warnings)}")