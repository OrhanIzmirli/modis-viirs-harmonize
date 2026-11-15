# SONUÇ — The Fire Almanac of Türkiye (NASA Space Apps 2026)

_Son güncelleme: 2026-11-15. Veri kaynağı: **FIRMS yıllık ülke arşivi** (Area API indirmesi sürüyor; bitince bu dosya güncellenecek)._

## Linkler
- Repo: https://github.com/OrhanIzmirli/modis-viirs-harmonize
- Canlı site (GitHub Pages, `docs/`): https://orhanizmirli.github.io/modis-viirs-harmonize/

## Ana sayılar (2001–2025, Türkiye)
| | |
|---|---|
| Ham FIRMS satırı | 1.181.845 |
| Temiz bitki örtüsü tespiti (type=0) | 915.940 (MODIS 243.603 · VIIRS 672.337) |
| Harmonize yangın olayı | 432.881 |
| Tekrar azaltma oranı | 2,12 tespit / olay |
| İki sensör de gördü / sadece MODIS / sadece VIIRS | %8,0 / %25,7 / %66,3 |
| FRP korelasyonu (Aqua vs S-NPP/NOAA-20, ≤30 dk, n=19.434) | Pearson r(log) = **0,67**, Spearman ρ = 0,61 |
| Eşleşme oranı MODIS→VIIRS (≤12 sa) | gündüz %52, gece %57 |
| Eşleşme oranı VIIRS→MODIS (≤12 sa) | gündüz %26, gece %33 |
| En sıra dışı hafta (Türkiye, FRP) | 26 Tem–1 Ağu 2021: ortalamanın 39 katı, z = 68; ardından 2–8 Ağu 2021 (z = 19) |
| Trend | Yangın sezonu uzuyor: MODIS +4,8 gün/yıl (p<0,001), VIIRS S-NPP +7,1 gün/yıl (p=0,014); toplam FRP'de anlamlı trend yok |

**2021 kontrolü:** Temmuz–Ağustos 2021 takvimde en belirgin kritik dönem olarak çıkıyor, **ama sadece yangın enerjisi (FRP) metriğinde**. Ülke genelinde *olay sayısında* sıra dışı değil (z ≈ −0,1…−0,9), çünkü birleştirme dev yangınları tek olaya indiriyor ve yaz boyu binlerce küçük tarımsal yangın sayıyı domine ediyor. Antalya ve Muğla'da iki metrikte de çok belirgin. Bu yüzden takvimin varsayılan metriği FRP.

## Sitede neler var
Hero ("When does Türkiye burn?" + Trust Score cümlesi) → 01 Takvim (yıl × hafta, "Is this week normal?", en sıra dışı haftalar, renk körü modu, ay ay grafik, sensör karşılaştırması) → 02 Two satellites, one truth (29 Tem 2021 Manavgat: 1.540 tespit → 3 olay) → 03 Canlı harita (olay hikâyesi, Trust Score, geçiş zaman çizelgesi, teknik detaylar) → 04 Who is this for? → 05 Download the data → 06 Why it matters (kaynaklı bilgi kutusu, anız notu, Did you know?).

## Figürler (`figures/`)
- Sunum (300 dpi, kağıt zemin): `slide_2021_unusual.png`, `slide_before_after.png`, `slide_frp_scatter.png`, `slide_match_rates.png`
- Doğrulama: `match_rates.png`, `frp_scatter.png`, `dedup.png`, `small_fire_example.png`, `insight.png`, `calendar_2021_check.png`
- Uygulama görüntüsü: `app_calendar.jpg`

## Testler
`pytest`: 21 test geçti (normalleştirme, eşleştirme sınırları, takvim agregasyonu, anomali).

## Bilinen eksikler / notlar
- **Veri kaynağı:** Yayındaki sonuçlar FIRMS yıllık ülke arşivinden (aynı SP ürünleri, ülke sınırına kırpılmış, NOAA-21 yok). Area API indirmesi kota (5.000 işlem/10 dk, istek başına ~10) nedeniyle uzun sürdü; durum aşağıda.
- **facts.json:** firewatch-tr-backend'de `public/nature/facts.json` bulunamadı. Doğrulanmış havuz firewatch-tr uygulamasındaki `assets/data/nature_facts.json`; 15 bilgi oradan (hepsi "Doğrulandı") salt okunarak alındı ve havuzdaki hazır İngilizce metinler kullanıldı. Firewatch repolarına yazılmadı.
- **Pipeline değişikliği reddi:** `meta.json`'a il içi sayaç ekleme denemesi otomatik izin sistemi tarafından reddedildi (pipeline'a dokunma kuralı). Aynı sayılar sunum katmanında `calendar/TR.json`'dan hesaplanıyor.
- **"Use of AI":** README'de araç adı verilmeden genel ifadeyle duruyor (Space Apps beyan ister). Commit'lerde, contributors'ta ve README'de Claude geçmiyor.
- Sensör kaydı homojen değil (2012 VIIRS, 2018 NOAA-20); anomaliler her modun kendi tabanına göre, trend tek sensör kayıtlarıyla hesaplandı.
- Terra/Aqua yörünge kayması (2020+) son MODIS yıllarını etkileyebilir.
- Tekil statik kaynaklar (FIRMS'in işaretlemediği endüstri) uzun ömürlü küçük olay olarak görünebilir.

## Area API durumu
_(güncellenecek)_
