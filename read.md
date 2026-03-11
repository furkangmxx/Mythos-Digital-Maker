# MythosCards Exporter

Türk spor kartları için Excel checklist işleme, görsel eşleştirme ve dosya adı kısaltma uygulaması.

---

## Proje Yapısı

```
src/
├── main.py      # GUI ve CLI ana dosyası
├── expand.py    # Satır genişletme (1 satır → N kart)
├── export.py    # Excel çıktı oluşturma
├── images.py    # Part 2: Görsel eşleştirme
├── shorten.py   # Part 3: Dosya adı kısaltma
├── headers.py   # Excel header işleme
├── validate.py  # Doğrulama kuralları
├── io_ops.py    # Excel I/O işlemleri
├── sorters.py   # Türkçe sıralama
├── utils.py     # Yardımcı fonksiyonlar
└── version.py   # Versiyon bilgisi
```

---

## Kurulum

```bash
pip install -r requirements.txt
python src/main.py
```

---

# Bölüm 1: Checklist İşleme

Excel checklist'ini bireysel kart listesine çevirir.

## Giriş Excel Formatı

| Seri Adı | Grup | Oyuncu Adı | 1/1 | 1/1 İmzalı | /5 | /5 İmzalı | /25 | /25 İmzalı | Base |
|----------|------|------------|-----|------------|----|-----------|----|------------|------|
| Süper Lig | Duo | Okan Buruk | 1 | 0 | 3 | 2 | 7 | 0 | 78 |

- **Seri Adı**: Zorunlu
- **Grup**: Opsiyonel (Duo, Trio vs.)
- **Oyuncu Adı**: Zorunlu
- **Variant sütunları**: 1/1, /5, /25, /67 gibi özel paydalar desteklenir

## Çıktı Excel Formatı (Çıktı Sheet)

| A: Kart Listesi | B: Görsel Dosyası | C: player_name | D: series_name | E: group | F: denominator | G: is_signed |
|-----------------|-------------------|----------------|----------------|----------|----------------|--------------|
| Okan Buruk Duo (1/5) | | Okan Buruk | Süper Lig | Duo | 5 | Hayır |
| Okan Buruk Duo (1/5) İmzalı | | Okan Buruk | Süper Lig | Duo | 5 | Evet |

- **A kolonu**: Görüntüleme metni
- **B kolonu**: Part 2'de doldurulacak görsel dosya adı
- **C-G kolonları**: Part 2 eşleştirme için yapılandırılmış veri

## Diğer Sheet'ler

- **Özet**: Toplam sayılar, variant dağılımları
- **Hatalar**: Engelleyici hatalar
- **Uyarılar**: Uyarılar
- **Ayarlar**: İşlem detayları

---

# Bölüm 2: Görsel Eşleştirme

Part 1 çıktısındaki kartları görsel dosyalarıyla eşleştirir.

## Kullanım

1. Part 1'den çıkan Excel dosyasını seçin
2. Görsel klasörünü seçin
3. "Kontrol Et" ile ön izleme yapın
4. "Görselleri Eşleştir" ile işlemi başlatın

## Görsel Dosya Adı Formatı

```
[YYYYMMDD_]player_name_series_name[_group][_s]_denominator.jpg
```

### Parçalar:

| Parça | Açıklama | Örnek |
|-------|----------|-------|
| `YYYYMMDD_` | Opsiyonel tarih prefix | `20250120_` |
| `player_name` | Oyuncu adı (normalize) | `okan_buruk` |
| `series_name` | Seri adı (normalize) | `super_lig` |
| `group` | Opsiyonel grup | `duo` |
| `_s` | İmzalı işareti | `_s` |
| `denominator` | Payda veya `base` | `_25` veya `_base` |
| `.ext` | Uzantı | `.jpg`, `.png` |

### Örnekler:

```
okan_buruk_super_lig_duo_s_25.jpg       → İmzalı, /25
mario_jardel_super_lig_5.jpg            → Normal, /5
fernando_muslera_super_lig_base.jpg     → Base kart
20250120_okan_buruk_super_lig_25.jpg    → Tarih prefix'li
```

## Normalizasyon Kuralları

Hem Excel verileri hem dosya adları şu şekilde normalize edilir:

1. **Türkçe karakterler**: ğ→g, ş→s, ç→c, ö→o, ü→u, ı→i
2. **Avrupa karakterleri**: ä→a, é→e, ñ→n vs.
3. **Küçük harf**: Tümü küçük harfe
4. **Boşluklar**: Boşluk ve tire → alt çizgi `_`
5. **Özel karakterler**: Silinir (a-z, 0-9, _ dışındakiler)
6. **Çoklu alt çizgi**: Tek alt çizgiye indirilir

## Eşleştirme Mantığı

### Hard Rules (Kesin Eşleşmeli):
- `is_signed` (imzalı/normal)
- `is_base` (base/variant)
- `denominator` (payda değeri)

### İçerik Eşleşmesi:
- Excel'deki TÜM parçalar dosya adında olmalı
- Fuzzy matching: %70+ benzerlik (typo toleransı)
- Skor: 100 - (fazla_kelime * 15)

### Sonuçlar:
- ✅ **found**: Tek eşleşme bulundu
- ❌ **missing**: Eşleşme yok
- ⚠️ **conflict**: Birden fazla eşleşme (aynı skor)

---

# Bölüm 3: Dosya Adı Kısaltma

Part 2'den sonra kullanılır. Uzun görsel dosya adlarını kısaltır.

## Önemli: Part 2'den Sonra Kullanılmalı

Part 3, Excel B kolonundaki (Görsel Dosyası) isimleri okur. Bu kolon Part 2 tarafından doldurulur.

## Kullanım

1. Part 2 ile eşleştirme yapın (Excel B kolonu dolar)
2. Part 3'te aynı Excel dosyasını seçin
3. Görsel klasörünü seçin
4. Max uzunluk belirleyin (varsayılan: 97 karakter, uzantı dahil)
5. "Kontrol Et" ile kaç dosyanın etkileneceğini görün
6. "Kısalt" ile işlemi başlatın

## Kısaltma Mantığı

Sadece `player_name` kısmı sondan kesilir. Diğer parçalar değişmez.

```
Önce:  mehmet_aurelio_arda_turan_super_lig_duo_s_25.jpg (52 karakter)
Sonra: mehmet_aurelio_ard_super_lig_duo_s_25.jpg (45 karakter)
```

### Sabit Kalan Parçalar:
- Tarih prefix (varsa): `20250120_`
- Series + group: `_super_lig_duo`
- İmzalı işareti: `_s`
- Denominator: `_25`
- Uzantı: `.jpg`

### Kısaltılan:
- `player_name` sondan kesilir

## Ne Yapılır:

1. Excel B kolonundan görsel isimlerini okur
2. Max uzunluğu aşanları bulur
3. Hem fiziksel dosyayı hem Excel B kolonunu günceller
4. İşlem öncesi tüm görsel klasörünü yedekler

## Yedekleme

```
~/Documents/MythosCards/Backup/YYYYMMDD_Shorten_KlasorAdi/
```

---

# Çıktı Klasör Yapısı

```
~/Documents/MythosCards/
├── Outputs/
│   └── SeriAdi/
│       └── SeriAdi_Excel.xlsx
├── Backup/
│   ├── 20250120_KlasorAdi/           # Part 2 backup
│   └── 20250120_Shorten_KlasorAdi/   # Part 3 backup
└── logs/
    └── run-YYYYMMDD.log
```

---

# Doğrulama Kuralları

## Hatalar (Engelleyici)
- ❌ Çift doldurma: Aynı payda için hem normal hem imzalı
- ❌ Geçersiz değer: Sayısal olmayan
- ❌ Eksik alan: Boş Seri Adı veya Oyuncu Adı
- ❌ Bilinmeyen sütun

## Uyarılar (Engelleyici Değil)
- ⚠️ Payda aşımı: N > D (örn: 7 adet /5)
- ⚠️ Çoklu satır: Aynı oyuncu birden fazla
- ⚠️ Büyük Base: >500 base

---

# Akış Özeti

```
1. PART 1: Excel Checklist → Kart Listesi Excel
   - Giriş: checklist.xlsx
   - Çıktı: SeriAdi_Excel.xlsx (B kolonu boş)

2. PART 2: Görsel Eşleştirme
   - Giriş: Part 1 Excel + Görsel klasörü
   - Çıktı: Excel B kolonu dolar (görsel isimleri)

3. PART 3: Dosya Adı Kısaltma (opsiyonel)
   - Giriş: Part 2 Excel + Görsel klasörü
   - Çıktı: Uzun isimler hem dosyada hem Excel'de kısalır
```

---

# Teknik Notlar

## Excel Kolon İndeksleri (Çıktı Sheet)

| İndeks | Kolon | İçerik |
|--------|-------|--------|
| 0 | A | Kart Listesi (görüntüleme) |
| 1 | B | Görsel Dosyası (Part 2 doldurur) |
| 2 | C | player_name |
| 3 | D | series_name |
| 4 | E | group |
| 5 | F | denominator |
| 6 | G | is_signed (Evet/Hayır) |

## Desteklenen Görsel Formatları

- `.jpg`
- `.jpeg`
- `.png`

## Python Gereksinimleri

- Python 3.8+
- pandas
- openpyxl
- xlsxwriter
- click (CLI için)
- tkinter (GUI için)

---

# Yazar

**Furkan Gümüş** - MythosCards
