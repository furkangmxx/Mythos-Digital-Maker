#!/usr/bin/env python3
"""Test Teammates eşleşmesi"""

import re

# Türkçe karakter dönüşümü
TURKISH_TO_ASCII = str.maketrans('çÇğĞıIİşŞöÖüÜâÂ', 'cCgGiIIsSoOuUaA')

def normalize_for_matching(text: str) -> str:
    """Eşleştirme için normalize et"""
    if not text:
        return ""

    # 1. Türkçe → ASCII
    normalized = str(text).translate(TURKISH_TO_ASCII)

    # 2. Küçük harf
    normalized = normalized.lower()

    # 3. Tire ve boşluk → alt çizgi (ÖNCE bu işlemi yap)
    normalized = normalized.replace('-', '_')
    normalized = normalized.replace(' ', '_')

    # 4. Diğer özel karakterleri SİL (a-z, 0-9, alt çizgi dışındaki her şey)
    normalized = re.sub(r'[^a-z0-9_]', '', normalized)

    # 5. Çoklu alt çizgi → tek
    normalized = re.sub(r'_+', '_', normalized)

    # 6. Baş/son alt çizgi temizle
    normalized = normalized.strip('_')

    return normalized

print("="*60)
print("TEAMMATES DURUMU")
print("="*60)
print()

# Excel'den
player = "Freddie Ljungberg"
series = "Mythos Legends Johan Elmander"
group = "Teammates"
denominator = 10
is_signed = False

player_norm = normalize_for_matching(player)
series_norm = normalize_for_matching(series)
group_norm = normalize_for_matching(group)

print("EXCEL BİLGİLERİ:")
print(f"  player_name: {player}")
print(f"  series_name: {series}")
print(f"  group: {group}")
print(f"  denominator: {denominator}")
print(f"  is_signed: {is_signed}")
print()

print("NORMALIZE EDİLMİŞ:")
print(f"  player_norm: {player_norm}")
print(f"  series_norm: {series_norm}")
print(f"  group_norm: {group_norm}")
print()

# Tüm parçalar
card_parts = []
if player_norm:
    card_parts.extend(player_norm.split('_'))
if series_norm:
    card_parts.extend(series_norm.split('_'))
if group_norm:
    card_parts.extend(group_norm.split('_'))

card_parts = [p for p in card_parts if p]

print(f"CARD PARTS ({len(card_parts)} adet):")
print(card_parts)
print()

# Dosya
filename = "mythos_legends_johan_elmander_teammates_freddie_ljungberg_10.jpg"
print("DOSYA ADI:")
print(f"  {filename}")
print()

# Parse
name = filename.lower()
name = re.sub(r'\.(jpg|jpeg|png)$', '', name, flags=re.IGNORECASE)

# Denominator
denom_match = re.search(r'_(\d+)$', name)
file_denominator = 0
if denom_match:
    file_denominator = int(denom_match.group(1))
    name = re.sub(r'_\d+$', '', name)

# _s_ kontrolü
file_is_signed = '_s_' in f'_{name}_'
if file_is_signed:
    name = re.sub(r'_s_', '_', name)
    name = re.sub(r'^s_', '', name)
    name = re.sub(r'_s$', '', name)

file_parts = name.split('_')
file_parts = [p for p in file_parts if p]

print("PARSE EDİLMİŞ:")
print(f"  denominator: {file_denominator}")
print(f"  is_signed: {file_is_signed}")
print(f"  content_parts ({len(file_parts)} adet): {file_parts}")
print()

# Hard rules kontrolü
print("HARD RULES KONTROLÜ:")
print(f"  is_signed match? {is_signed} == {file_is_signed} → {is_signed == file_is_signed}")
print(f"  denominator match? {denominator} == {file_denominator} → {denominator == file_denominator}")
print()

# İçerik eşleşmesi
matched_parts = 0
missing = []
for card_part in card_parts:
    if card_part in file_parts:
        matched_parts += 1
    else:
        missing.append(card_part)

extra = []
for file_part in file_parts:
    if file_part not in card_parts:
        extra.append(file_part)

print("İÇERİK EŞLEŞMESİ:")
print(f"  Card parts: {len(card_parts)}")
print(f"  File parts: {len(file_parts)}")
print(f"  Matched: {matched_parts}/{len(card_parts)}")
print(f"  Missing: {missing}")
print(f"  Extra: {extra}")
print()

missing_count = len(card_parts) - matched_parts
extra_count = len(extra)

print("SONUÇ:")
if is_signed != file_is_signed:
    print("  ❌ REJECTED: is_signed uyuşmuyor")
elif denominator != file_denominator:
    print("  ❌ REJECTED: denominator uyuşmuyor")
elif missing_count > 0:
    print(f"  ❌ REJECTED: {missing_count} eksik parça var")
else:
    if extra_count > 0:
        print(f"  ⚠️  STRICT MODE = True  → REJECTED (fazla kelime)")
        print(f"  ✅ STRICT MODE = False → MATCHED (score: {100 - extra_count * 15})")
    else:
        print(f"  ✅ PERFECT MATCH! (score: 100)")
