#!/usr/bin/env python3
"""
MythosCards - Görsel Eşleştirme Debug Script
============================================
Bu scripti şöyle çalıştır:
    python debug_images.py "EXCEL_DOSYASI.xlsx" "GORSEL_KLASORU"

Örnek:
    python debug_images.py "C:/Users/Furkan/Documents/MythosCards/Outputs/SeriesName/SeriesName_Excel.xlsx" "C:/Users/Furkan/Pictures/Gorseller"
"""

import sys
import re
from pathlib import Path
import pandas as pd

# Türkçe karakter dönüşümü
TURKISH_TO_ASCII = str.maketrans('çÇğĞıIİşŞöÖüÜâÂ', 'cCgGiIIsSoOuUaA')

def normalize_for_matching(text: str) -> str:
    if not text:
        return ""
    normalized = str(text).translate(TURKISH_TO_ASCII)
    normalized = normalized.lower()
    normalized = normalized.replace('-', '_')
    normalized = normalized.replace(' ', '_')
    normalized = re.sub(r'[^a-z0-9_]', '', normalized)
    normalized = re.sub(r'_+', '_', normalized)
    normalized = normalized.strip('_')
    return normalized

def parse_filename(filename: str):
    """Dosya adını parse et"""
    name = filename.lower()
    name = re.sub(r'\.(jpg|jpeg|png)$', '', name, flags=re.IGNORECASE)
    
    # Tarih prefix (YYYYMMDD_)
    date_match = re.match(r'^(\d{8})_(.+)$', name)
    if date_match:
        name = date_match.group(2)
    
    # İmzalı kontrolü
    is_signed = '_s_' in f'_{name}_'
    
    # Base kontrolü
    is_base = bool(re.search(r'_base(?:_\d+)?$', name))
    
    # Denominator
    denominator = 0
    if not is_base:
        denom_match = re.search(r'_(\d+)$', name)
        if denom_match:
            denominator = int(denom_match.group(1))
            name = re.sub(r'_\d+$', '', name)
    else:
        name = re.sub(r'_base(?:_\d+)?$', '', name)
    
    # _s_ çıkar
    name = re.sub(r'_s_', '_', name)
    name = re.sub(r'^s_', '', name)
    name = re.sub(r'_s$', '', name)
    
    content_parts = [p for p in name.split('_') if p]
    
    return {
        'denominator': denominator,
        'is_signed': is_signed,
        'is_base': is_base,
        'content_parts': content_parts
    }

def main():
    if len(sys.argv) < 3:
        print("Kullanım: python debug_images.py EXCEL.xlsx GORSEL_KLASORU")
        sys.exit(1)
    
    excel_file = Path(sys.argv[1])
    image_dir = Path(sys.argv[2])
    
    if not excel_file.exists():
        print(f"❌ Excel bulunamadı: {excel_file}")
        sys.exit(1)
    
    if not image_dir.exists():
        print(f"❌ Klasör bulunamadı: {image_dir}")
        sys.exit(1)
    
    print("="*70)
    print("MYTHOS CARDS - GÖRSEL EŞLEŞTİRME DEBUG")
    print("="*70)
    
    # Excel'i oku
    print(f"\n📄 Excel: {excel_file}")
    data = pd.read_excel(excel_file, sheet_name="Çıktı")
    print(f"   Kolonlar: {list(data.columns)}")
    print(f"   Satır sayısı: {len(data)}")
    
    # Görselleri tara
    print(f"\n🖼️  Görsel Klasörü: {image_dir}")
    images = list(image_dir.glob("*.jpg")) + list(image_dir.glob("*.png")) + list(image_dir.glob("*.jpeg"))
    print(f"   Görsel sayısı: {len(images)}")
    
    if len(images) > 0:
        print(f"   İlk 3 görsel:")
        for img in images[:3]:
            print(f"     - {img.name}")
    
    # Parse edilmiş görseller
    parsed_images = {}
    for img in images:
        parsed_images[img.name] = parse_filename(img.name)
    
    print("\n" + "="*70)
    print("EXCEL SATIRLARI VE EŞLEŞTİRME")
    print("="*70)
    
    found = 0
    missing = 0
    
    for idx in range(min(10, len(data))):  # İlk 10 satır
        row = data.iloc[idx]
        row_num = idx + 2
        
        # Kolonları oku (images.py ile aynı mantık)
        raw_text = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
        player = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else ""
        series = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else ""
        group = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""
        
        denom_val = row.iloc[5] if pd.notna(row.iloc[5]) else 0
        try:
            denominator = int(float(denom_val))
        except:
            denominator = 0
        
        signed_val = str(row.iloc[6]).strip().lower() if pd.notna(row.iloc[6]) else ""
        is_signed = signed_val in ['evet', 'true', '1', 'yes']
        is_base = 'base' in raw_text.lower()
        
        # Normalize
        player_norm = normalize_for_matching(player)
        series_norm = normalize_for_matching(series)
        group_norm = normalize_for_matching(group)
        
        # Card parts
        card_parts = []
        if player_norm:
            card_parts.extend(player_norm.split('_'))
        if series_norm:
            card_parts.extend(series_norm.split('_'))
        if group_norm:
            card_parts.extend(group_norm.split('_'))
        card_parts = [p for p in card_parts if p]
        
        print(f"\n--- Satır {row_num} ---")
        print(f"  C (player): '{player}'")
        print(f"  D (series): '{series}'")
        print(f"  E (group): '{group}'")
        print(f"  F (denom): {denominator}")
        print(f"  G (signed): {is_signed}")
        print(f"  is_base: {is_base}")
        print(f"  card_parts ({len(card_parts)}): {card_parts}")
        
        # Eşleştirme dene
        best_match = None
        best_score = 0
        rejection_reasons = []
        
        for filename, file_info in parsed_images.items():
            # Hard rules
            if is_signed != file_info['is_signed']:
                if len(rejection_reasons) < 2:
                    rejection_reasons.append(f"{filename}: imzalı uyuşmazlığı (excel={is_signed}, dosya={file_info['is_signed']})")
                continue
            
            if is_base != file_info['is_base']:
                if len(rejection_reasons) < 2:
                    rejection_reasons.append(f"{filename}: base uyuşmazlığı (excel={is_base}, dosya={file_info['is_base']})")
                continue
            
            if not is_base and denominator:
                # Karşılaştırma: her ikisini de normalize et
                card_denom = str(denominator).upper() if denominator else ""
                file_denom = str(file_info['denominator']).upper() if file_info['denominator'] else ""
                if card_denom != file_denom:
                    if len(rejection_reasons) < 2:
                        rejection_reasons.append(f"{filename}: denom uyuşmazlığı (excel={denominator}, dosya={file_info['denominator']})")
                    continue
            
            # İçerik eşleştirmesi
            file_parts = file_info['content_parts']
            matched = sum(1 for p in card_parts if p in file_parts)
            missing_count = len(card_parts) - matched
            
            if missing_count > 0:
                if len(rejection_reasons) < 2:
                    missing_parts = [p for p in card_parts if p not in file_parts]
                    rejection_reasons.append(f"{filename}: {missing_count} parça eksik {missing_parts}")
                continue
            
            extra = max(0, len(file_parts) - len(card_parts))
            score = 100 - (extra * 15)
            
            if score > best_score:
                best_score = score
                best_match = filename
        
        if best_match:
            print(f"  ✅ EŞLEŞTİ: {best_match} (skor: {best_score})")
            found += 1
        else:
            print(f"  ❌ EŞLEŞMEDİ!")
            if rejection_reasons:
                print(f"  Red nedenleri:")
                for reason in rejection_reasons[:3]:
                    print(f"    - {reason}")
            missing += 1
    
    print("\n" + "="*70)
    print("ÖZET")
    print("="*70)
    print(f"İncelenen: {min(10, len(data))} satır")
    print(f"Eşleşen: {found}")
    print(f"Eşleşmeyen: {missing}")
    
    if missing > 0:
        print("\n💡 İPUCU: Eşleşmeyen satırlar için 'Red nedenleri'ne bak.")
        print("   Genellikle sorun şunlardan biri:")
        print("   - Dosya adında fazla/eksik kelime")
        print("   - Denominator uyuşmazlığı") 
        print("   - İmzalı/normal karışıklığı")

if __name__ == "__main__":
    main()
