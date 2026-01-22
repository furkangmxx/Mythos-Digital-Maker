#!/usr/bin/env python3
"""Gerçek Excel dosyasından Teammates satırını debug et"""

import sys
import pandas as pd
import re

# Türkçe karakter dönüşümü
TURKISH_TO_ASCII = str.maketrans('çÇğĞıIİşŞöÖüÜâÂ', 'cCgGiIIsSoOuUaA')

def normalize_for_matching(text: str) -> str:
    """Eşleştirme için normalize et"""
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

if len(sys.argv) < 2:
    print("Kullanım: python debug_excel.py <excel_dosya_yolu>")
    sys.exit(1)

excel_file = sys.argv[1]

print("="*80)
print(f"EXCEL DOSYASI: {excel_file}")
print("="*80)
print()

# Excel'i oku
data = pd.read_excel(excel_file, sheet_name="Çıktı")

print(f"Toplam satır: {len(data)}")
print(f"Kolonlar ({len(data.columns)} adet): {list(data.columns)}")
print()

# "Teammates" içeren satırları bul
print("TEAMMATES içeren satırları arıyorum...")
print()

teammates_found = False
for idx, row in data.iterrows():
    # E kolonunu kontrol et (group)
    group_val = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else ""

    if "teammates" in group_val.lower():
        teammates_found = True
        print(f"{'='*80}")
        print(f"SATIR BULUNDU: Excel satır {idx + 2}")
        print(f"{'='*80}")

        # Tüm kolonları göster
        print(f"A (0) - Kart Listesi: '{row.iloc[0]}'")
        print(f"B (1) - Görsel Dosyası: '{row.iloc[1] if pd.notna(row.iloc[1]) else ''}'")
        print(f"C (2) - player_name: '{row.iloc[2]}'")
        print(f"D (3) - series_name: '{row.iloc[3]}'")
        print(f"E (4) - group: '{row.iloc[4]}'")
        print(f"F (5) - denominator: '{row.iloc[5]}'")
        print(f"G (6) - is_signed: '{row.iloc[6]}'")
        print()

        # Parse et
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

        # Normalize
        player_norm = normalize_for_matching(player)
        series_norm = normalize_for_matching(series)
        group_norm = normalize_for_matching(group)

        print("NORMALIZE EDİLMİŞ:")
        print(f"  player_norm: '{player_norm}'")
        print(f"  series_norm: '{series_norm}'")
        print(f"  group_norm: '{group_norm}'")
        print(f"  denominator: {denominator}")
        print(f"  is_signed: {is_signed}")
        print()

        # Card parts
        card_parts = []
        if player_norm:
            card_parts.extend(player_norm.split('_'))
        if series_norm:
            card_parts.extend(series_norm.split('_'))
        if group_norm:
            card_parts.extend(group_norm.split('_'))
        card_parts = [p for p in card_parts if p]

        print(f"CARD PARTS ({len(card_parts)} adet):")
        print(f"  {card_parts}")
        print()

        # Beklenen dosya adı
        expected_base = "_".join(card_parts)
        expected_file = f"{expected_base}_{denominator}.jpg"
        if is_signed:
            expected_file = f"{expected_base}_s_{denominator}.jpg"

        print(f"BEKLENİYOR:")
        print(f"  Dosya içermeli: {card_parts}")
        print(f"  Örnek dosya adı: {expected_file}")
        print()

        # Sadece ilk 3 Teammates satırını göster
        if teammates_found:
            response = input("Devam etmek için ENTER'a bas, çıkmak için 'q': ")
            if response.lower() == 'q':
                break

if not teammates_found:
    print("❌ Teammates içeren satır bulunamadı!")
    print()
    print("İlk 5 satırı göstereyim:")
    print()
    for idx in range(min(5, len(data))):
        row = data.iloc[idx]
        print(f"Satır {idx+2}:")
        print(f"  A: {row.iloc[0] if pd.notna(row.iloc[0]) else 'BOŞ'}")
        print(f"  E (group): {row.iloc[4] if pd.notna(row.iloc[4]) else 'BOŞ'}")
        print()
