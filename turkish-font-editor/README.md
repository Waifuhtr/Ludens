---
title: Turkce Font Tamamlayici
emoji: 🇹🇷
colorFrom: red
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
---

# Türkçe Font Tamamlayıcı

TTF/OTF fontlara eksik Türkçe karakterleri (Ç ç Ğ ğ İ ı Ö ö Ş ş Ü ü) otomatik
olarak ekleyen bir düzenleme aracı. Python, [fontTools](https://github.com/fonttools/fonttools)
ve FastAPI ile yazılmıştır; arayüz saf HTML/CSS/JS'tir (Gradio kullanılmamıştır,
çünkü bu düzeyde özelleştirilebilir bir taslak editörü için Gradio'nun bileşen
seti yetersiz kalıyordu).

## Nasıl çalışır?

Her Türkçe karakter, bir **temel harf** (ör. `C`) ile bir **aksan** (ör.
cedilla) biriminin birleşimi olarak tanımlanır:

| Karakter | Taslak |
|---|---|
| Ç / ç | C/c + Cedilla |
| Ğ / ğ | G/g + Breve |
| İ | I + Dot |
| ı | i'nin noktası kaldırılmış hali |
| Ö / ö | O/o + Diaeresis |
| Ş / ş | S/s + Cedilla |
| Ü / ü | U/u + Diaeresis |

Font yüklendiğinde araç sırasıyla şunları dener:

1. **Zaten var mı?** Karakter cmap'te zaten eşliyse dokunulmaz.
2. **Fontta adıyla duruyor mu?** (ör. `Scedilla` glyph'i var ama cmap'te
   `U+015E`'ye eşlenmemiş) — varsa sadece cmap eşlemesi eklenir, yeniden
   çizim yapılmaz.
3. **Bileşenlerden oluştur:** Temel harf font içinden (`C`, `S`, `U`, ...),
   aksan ise önce fontun kendi standalone aksan glyph'lerinden (`cedilla`,
   `breve`, `dieresis`, `dotaccent`), yoksa fontta zaten bulunan başka bir
   aksanlı karakterden (ör. `ç` varsa cedilla şekli oradan otomatik ayıklanır)
   elde edilir. Orijinal glyph anahatları (curve'ler dahil) korunur, sadece
   taşıma (X/Y) ve ölçek uygulanır — genişlik/metrikler temel harften
   miras alınır.
4. **Hiçbir bileşen yoksa:** Yerleşik, basit bir vektör aksan şekli
   kullanılır ve kullanıcı arayüzünde açıkça "sentetik" olarak işaretlenip
   uyarı gösterilir.
5. **ı (noktasız i):** Fontta `dotlessi` glyph'i varsa doğrudan kullanılır;
   yoksa `i` harfinin konturları taranıp x-height üzerindeki (nokta olduğu
   varsayılan) kontur otomatik tespit edilip kaldırılır. Kesme çizgisi (Y)
   arayüzden elle de ayarlanabilir.

Kullanıcı her karakter için temel glyph, aksan glyph'i, X/Y konumu ve ölçeği
canlı önizlemeli olarak elle düzeltebilir; "Otomatik Ayarlara Sıfırla" ile
başa dönebilir.

## Teknik notlar / sınırlamalar

- Hem **TrueType (`glyf`)** hem **CFF tabanlı OpenType (`CFF `)** fontlar
  desteklenir. Yeni glyph'ler her iki formatta da doğrudan gerçek font
  tablolarına (glyf/CFF, hmtx, cmap, maxp) eklenir; ayrı bir "overlay" değil,
  gerçek bir TTF/OTF üretilir.
- Varyable font eksenleri (`fvar`/`gvar`) ve OpenType özellik kuralları
  (GSUB/GPOS) bu sürümde işlenmez; yeni glyph'ler bu tablolara eklenmez.
  Bu genelde sorun yaratmaz çünkü Latin harfler ligature/pozisyonlama
  gerektirmez, ama ekstra stilistik özellik seti kullanan fontlarda yeni
  karakterler bu özelliklerden yararlanamaz.
- Uygulama tek işlemli (single-process) çalışacak şekilde tasarlanmıştır;
  font oturumları bellekte tutulur (2 saat sonra otomatik temizlenir).
  Docker/Spaces ortamında birden fazla `uvicorn` worker'ı **kullanmayın**.
- Yüklenen fontlar diske yazılmaz, yalnızca bellekte işlenir.

## Yerelde çalıştırma

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 7860
```

Sonra tarayıcıda `http://localhost:7860` adresini açın.

## Docker

```bash
docker build -t turkce-font-tamamlayici .
docker run -p 7860:7860 turkce-font-tamamlayici
```

## Hugging Face Spaces'e dağıtım

Bu depoyu doğrudan bir Space olarak kullanabilirsiniz (SDK: **Docker**,
donanım: CPU, 8 vCPU / 32GB RAM önerilen kaynaklarla rahatça çalışır).
Dosyanın en üstündeki YAML bloğu Spaces metadata'sını içerir.

## Dizin yapısı

```
app/
  main.py              FastAPI uygulaması ve API endpoint'leri
  font_engine.py        fontTools tabanlı kompozisyon/dışa aktarma motoru
  recipes.py             Türkçe karakter taslak tanımları
  synthetic_accents.py  Bileşen bulunamadığında kullanılan yedek vektör şekiller
static/
  index.html, style.css, app.js   Arayüz (Gradio değil, saf HTML/CSS/JS)
Dockerfile
requirements.txt
```
