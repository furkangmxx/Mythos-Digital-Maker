#!/usr/bin/env python3
"""Test normalize ve eşleştirme mantığı"""

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

# TEST 1: Excel'deki bilgileri normalize et
print("="*60)
print("TEST 1: EXCEL BİLGİLERİ")
print("="*60)

player = "2006-07 Sezonunun Son Maçında Hat-Trick Yaparak Toulouse'u Şampiyonlar Ligi'ne Taşıdı"
series = "Mythos Legends Johan Elmander"
group = "Moments"

player_norm = normalize_for_matching(player)
series_norm = normalize_for_matching(series)
group_norm = normalize_for_matching(group)

print(f"Player: {player}")
print(f"  → Normalize: {player_norm}")
print(f"  → Parçalar: {player_norm.split('_')}")
print()
print(f"Series: {series}")
print(f"  → Normalize: {series_norm}")
print(f"  → Parçalar: {series_norm.split('_')}")
print()
print(f"Group: {group}")
print(f"  → Normalize: {group_norm}")
print(f"  → Parçalar: {group_norm.split('_')}")
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

print(f"TOPLAM CARD PARTS ({len(card_parts)} adet):")
print(card_parts)
print()

# TEST 2: Dosya adını parse et
print("="*60)
print("TEST 2: DOSYA ADI")
print("="*60)

filename = "mythos_legends_johan_elmander_moments_2006_07_sezonunun_son_macinda_hat_trick_yaparak_toulouseu_sampiyonlar_ligine_tasidi_10.jpg"
print(f"Dosya: {filename}")
print()

# Parse
name = filename.lower()
name = re.sub(r'\.(jpg|jpeg|png)$', '', name, flags=re.IGNORECASE)
print(f"1. Uzantı çıkarıldı: {name}")

# Denominator çıkar
denom_match = re.search(r'_(\d+)$', name)
if denom_match:
    denominator = int(denom_match.group(1))
    name = re.sub(r'_\d+$', '', name)
    print(f"2. Denominator çıkarıldı ({denominator}): {name}")

# Parçalar
file_parts = name.split('_')
file_parts = [p for p in file_parts if p]

print(f"\nTOPLAM FILE PARTS ({len(file_parts)} adet):")
print(file_parts)
print()

# TEST 3: Eşleştirme
print("="*60)
print("TEST 3: EŞLEŞTİRME ANALİZİ")
print("="*60)

# Her card_part dosyada var mı?
matched_parts = 0
missing_from_file = []

for card_part in card_parts:
    if card_part in file_parts:
        matched_parts += 1
    else:
        missing_from_file.append(card_part)

print(f"Card parts: {len(card_parts)}")
print(f"File parts: {len(file_parts)}")
print(f"Matched: {matched_parts}")
print(f"Missing from file: {missing_from_file}")
print()

# Fazla parçalar (dosyada olup Excel'de olmayan)
extra_in_file = []
for file_part in file_parts:
    if file_part not in card_parts:
        extra_in_file.append(file_part)

print(f"Extra in file: {extra_in_file}")
print()

# Skor hesapla
missing_parts = len(card_parts) - matched_parts
extra_parts = len(extra_in_file)

print(f"Missing parts: {missing_parts}")
print(f"Extra parts: {extra_parts}")
print()

# Strict mode kontrolü
print("STRICT MODE = True:")
if missing_parts > 0:
    print(f"  ❌ REJECT: {missing_parts} eksik parça var")
elif extra_parts > 0:
    print(f"  ❌ REJECT: {extra_parts} fazla parça var")
else:
    print(f"  ✅ MATCH: Perfect match!")

print()
print("STRICT MODE = False:")
if missing_parts > 0:
    print(f"  ❌ REJECT: {missing_parts} eksik parça var")
else:
    score = 100 - (extra_parts * 15)
    if score >= 70:
        print(f"  ✅ MATCH: Score = {score}")
    else:
        print(f"  ❌ REJECT: Score = {score} < 70")
