# SONUÇ — The Fire Almanac of Türkiye (NASA Space Apps 2026)

_Son güncelleme: 15 Kasım 2026, ~04:20 TR. Veri: **FIRMS Area API**, 3.621/3.621 istek tamam, 0 hata._

---

## 1. DURUM

### Linkler
- Canlı site (GitHub Pages, `docs/`): https://orhanizmirli.github.io/modis-viirs-harmonize/
- Repo: https://github.com/OrhanIzmirli/modis-viirs-harmonize
- Contributors: sadece **OrhanIzmirli**. Tüm commit'ler "Orhan Izmirli" adıyla, Co-Authored-By yok.

### Final sayılar (2001–2025, Türkiye'nin 81 ili içinde)
| | |
|---|---|
| Ham FIRMS satırı (Türkiye bbox, Area API) | 2.054.986 |
| Bitki örtüsü yangını tespiti (type=0), il sınırları içinde | **988.698** (MODIS 232.808 · VIIRS 755.890) |
| Harmonize yangın olayı, il sınırları içinde | **448.364** |
| Tekrar azaltma oranı | **2,2** tespit / olay (tüm bbox: 1.423.446 → 598.750, 2,4×) |
| İki sensör de gördü (olay) | **%7,8** · sadece MODIS %22,9 · sadece VIIRS %69,2 |
| İki sensör de gördü (yangın-günü) | %8,7 (sayfada kullanılan değer) |
| FRP korelasyonu (Aqua vs S-NPP/NOAA-20, ≤30 dk, n=25.171) | **Pearson r(log) = 0,69**, Spearman ρ = 0,63 (gündüz 0,69, gece 0,74) |
| Eşleşme MODIS→VIIRS (≤12 sa) | gündüz %56, gece %62 |
| Eşleşme VIIRS→MODIS (≤12 sa) | gündüz %27, gece %31 |
| En sıra dışı hafta (Türkiye, yangın enerjisi) | 26 Tem–1 Ağu 2021: 601.798 MW, ortalamanın **34,9 katı**, z = 54; ardından 2–8 Ağu 2021 (z = 17) |
| Trend | Toplam FRP'de anlamlı trend yok. Sezon uzunluğu eğimi (MODIS +4,9 gün/yıl) tanım sorunu nedeniyle sunumda **kullanılmıyor**, yalnızca README Limitations'ta |
| İklim (GISTEMP) | MODIS yıllık FRP vs küresel sıcaklık anomalisi: r = 0,10 (p = 0,64), ilişki yok. Birleşik kayıtta r = 0,77 ama uydu eklenmelerinden kaynaklı |
| Testler | `pytest` 21/21 geçti |

**2021 kontrolü:** Temmuz–Ağustos 2021 yangın enerjisinde arşivin en uç dönemi ve takvimde 1. ve 2. sırada. Ülke genelinde *olay sayısında* sıra dışı değil (z −1,3…−0,2), çünkü dev yangınlar tek olaya indiriliyor. Antalya ve Muğla'da iki metrikte de çok belirgin. Varsayılan metrik bu yüzden FRP.

### Üretilen figürler (`figures/`)
- Slayt (300 dpi, kağıt zemin, kaynak satırlı): `slide_2021_unusual.png`, `slide_before_after.png` (1.540 tespit → 3 olay), `slide_frp_scatter.png` (r = 0,69), `slide_match_rates.png`, `slide_dedup.png`, `slide_climate.png`
- Doğrulama: `match_rates.png`, `frp_scatter.png`, `dedup.png`, `small_fire_example.png` (Ankara, Eki 2023: 4 VIIRS tespiti, 15 km içinde MODIS yok), `insight.png`, `calendar_2021_check.png`
- Uygulama görüntüsü: `app_calendar.jpg`; sosyal önizleme kapağı: `docs/og.png`

### Değişen cümleler (önce → sonra)
- Hero'daki "Every fire event gets a trust score — like a credit score…" → hero'dan çıktı, olay kartında Trust Score'un altına taşındı.
- Normal hafta: "…has been calm — below its long-term average — in 8 of the last 14 years." → "Since VIIRS joined in 2012, this week (9 Nov–15 Nov) has been **mixed** across Türkiye: below its long-term average in 7 of 14 years and above it in 7." (≥%60 "usually calm", ≤%40 "usually busy", arası "mixed")
- Başlıklar: "Two satellites, one truth" → "What two satellites saw"; "Why it matters" → "Before the season"; "Fire story" → "Fire record"; "Real fire events" → "Fire events"; "Figure N" → italik "Fig. N".
- Persona 1: "“Her crews can't be everywhere.” …— before the season starts." → "A fire manager in Muğla cannot position crews everywhere. The almanac shows which weeks have historically demanded them, so teams can be placed before the season starts."
- Persona 2: "“Every October, stubble burning escapes into orchards.” …" → "In Diyarbakır, more fires start in October than in any other month. Stubble fires can spread into neighbouring orchards and fields. …" (Ekim zirvesi veride doğrulandı.)
- Persona 3: "…— one download away." → "Matching MODIS and VIIRS takes time. The merged events are in the files below."
- Kartlar: "Same fire, counted twice?" / "Different confidence scales?" / "1 km vs 375 m pixels?" → "Duplicates" / "Confidence" / "Pixel size" (farklı uzunluklarda).
- Fig. 3: "…so no satellite's view of a fire is lost." → "The merged line adds both: … MW." + altına enerjinin nasıl toplandığına dair not (geçiş içinde çift sayım yok; birleşik çizgi gözlemlerin toplamı).
- Bölüm 02'ye eklenen cümle: "Only 8.7% of fire-days were recorded by both satellites. …neither instrument on its own sees the whole season."
- Did you know: "…One whole trip in the time of a movie!" → "Aqua orbits Earth in about 99 minutes." 15 kartta ünlem ve "even" kalmadı.

---

## 2. TAMAMLANAMAYANLAR / DİKKAT

1. **Geçmişte kalan tek satır:** Bu dosyanın önceki bir sürümü yanlışlıkla 6ca96e7 commit'ine girdi. İçindeki bir cümlede kullanılan AI aracının adı geçiyordu. Güncel sürümde (bu dosya) yok, repodaki hiçbir dosyada da yok. Ama o commit'in geçmişinde duruyor. Silmek için geçmişi yeniden yazıp **force-push** gerekir. Force-push yasak olduğu için yapılmadı; karar sizin. (Komut: Devam planı, madde 4.)
2. **firewatch-tr-backend facts dosyası yok:** `public/nature/facts.json` bulunamadı. Doğrulanmış havuz firewatch-tr uygulamasındaki `assets/data/nature_facts.json`. 15 bilgi oradan (hepsi "Doğrulandı") salt okunarak alındı, üslubu sadeleştirildi, anlam ve kaynak aynı. Firewatch repolarına yazılmadı.
3. **İzin engeli:** Pipeline'a (`meta.json`) il içi sayaç ekleme isteği otomatik izin sistemi tarafından reddedildi (pipeline'a dokunma kuralı). Aynı sayılar sunum katmanında `calendar/TR.json`'dan hesaplanıyor, sonuç etkilenmedi.
4. **MODIS sayısı farkı:** Area API'deki MODIS tespiti (il içi 232.808), ülke arşivindekinden (242.661) biraz az. Ülke dosyası sınır ve kıyıda tampon kullanıyor olabilir; incelenmedi.
5. **`figures/app_calendar.jpg`** ve `docs/og.png` Area API verisiyle yenilendi (988.698 tespit → 448.364 olay görünüyor). `figures/insight.png` başlığındaki "season lengthened" cümlesi eski; figür sadece doğrulama amaçlı, sunumda kullanmayın.
6. Bilinen yöntem sınırlamaları README "Limitations" bölümünde: homojen olmayan sensör kaydı, Terra/Aqua yörünge kayması, statik kaynaklar, il = olay merkezi.

---

## 3. DEVAM PLANI (sabah)

1. Siteyi açın: https://orhanizmirli.github.io/modis-viirs-harmonize/ (takvim → 2021, harita, indirme linkleri).
2. Yerelde çalıştırmak: `cd C:\Users\rhn23\Desktop\modis-viirs-harmonize` → `python -m http.server -d docs 8000` → http://localhost:8000
3. Veriyi baştan üretmek (indirme önbellekte, yeniden istek atılmaz):
   ```
   python src/fetch_firms.py --region turkey --start 2001-01-01 --end 2025-12-31 --sources VIIRS_SNPP_SP VIIRS_NOAA20_SP VIIRS_NOAA21_SP MODIS_SP
   python src/pipeline.py --raw data/raw
   python src/validate.py
   python src/make_story.py
   python src/export_csv.py
   python src/present_figures.py
   python -m pytest -q
   ```
   Kontrol dosyaları: `output/summary.json`, `output/validation.json`, `docs/data/meta.json`.
4. (İsteğe bağlı, karar sizde) 6ca96e7'deki satırı geçmişten silmek: geçmiş yeniden yazılıp `git push --force-with-lease` gerekir. Yapmadan önce yedek alın.
5. Bilgisayar kapatıldıysa çalışan bir süreç kalmadı. Tüm iş commit'li ve push'lu.
