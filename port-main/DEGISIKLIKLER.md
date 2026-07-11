# Ludens — Yapılan Değişikliklerin Özeti

Bu belge, projede yapılan tüm değişiklikleri, **neden** yapıldıklarını ve nasıl test edeceğinizi
özetler. Kod tarafında her şeyi mevcut mimariye (Clean Architecture + Koin DI + MVVM,
`AGENTS.md`'de tarif edilen kalıplar) birebir uyacak şekilde yazmaya özen gösterdim.

⚠️ **Önemli dürüstlük notu:** Bu ortamda internet erişimi ve Android SDK/Gradle çalıştırma imkanı
yok, yani projeyi gerçekten derleyip test edemedim. Kotlin tarafındaki her dosyayı satır satır,
mevcut kodun birebir aynı kalıplarını (import yolları, Koin annotation'ları, composable
imzaları) referans alarak yazdım ve parantez/süslü parantez dengesini otomatik bir betikle
doğruladım — ama gerçek bir `./gradlew assembleDebug` denemesinin yerini tutmaz. Python tarafını
ise gerçekten çalıştırıp test ettim (aşağıda detay var).

---

## 1) "Paket adı / oyun adı işlenmiyor" hatası — kök neden bulundu ve düzeltildi

**Gerçek sebep:** `build_engine.py`, Ludens'ın okuduğu anahtarlarla **eşleşmeyen** anahtarlar
yazıyordu.

- Yazılan: `ludens.applicationId`, `ludens.applicationVersion`, `ludens.applicationName`, `ludens.applicationLauncherName`
- Ludens'ın gerçekten okuduğu (`build-logic/.../LudensAndroidConfiguration.kt` + `LudensConfigurationReader.kt`): `ludens.android.id`, `ludens.android.version`, `ludens.android.versionCode`, `ludens.android.name`, `ludens.android.launcherName`

Ludens tarafı sadece `ludens.properties` dosyasının **ham içeriğini** ayrıştırıyor;
`-P` Gradle komut satırı parametrelerini **hiç okumuyor**. Yani eski kodun `-Pludens.applicationId=...`
satırı da işlevsizdi. Yanlış anahtarlar Jackson tarafından sessizce yok sayılıyor, şablonun
varsayılan `com.ludens.compose.ludens` / "Ludens" değerleri hep kalıyordu.

**İkinci, daha ciddi bir hata da vardı:** Eski kod `ludens.properties` dosyasındaki `ludens.`
ile başlayan **tüm satırları** silip yerine sadece 4 satır yazıyordu. Ama o dosyadaki hemen her
ayar (minSDK, izinler, immersive mod, action preset'i...) `ludens.` ile başlıyor — yani her
build'de şablonun **diğer tüm ayarları da sessizce siliniyordu**.

**Üçüncü hata:** Plugin otomatik kaydı (`_auto_register_plugins`), MV oyunlarında var olan
`plugins.js` dosyasını **koşulsuz eziyordu** — RPG Maker editöründe düzgün yapılandırılmış
plugin parametreleri ve sırası her build'de siliniyordu (MZ tarafı zaten güvenliydi, sadece
MV tarafı bozuktu).

### Düzeltme (`build_engine.py`, v2.1)
- Doğru anahtarlar (`ludens.android.*`) kullanılıyor.
- `ludens.properties` artık **satır bazında** güncelleniyor — sadece kimlik anahtarları
  değişiyor, geri kalan her şey (yorumlar dahil) korunuyor.
- MV `plugins.js` artık **birleştirme** yapıyor: var olan pluginlere dokunmuyor, sadece eksik
  olanları ekliyor.
- İşe yaramayan `-P` parametreleri ve `gradle.properties` içine kimlik yazma kaldırıldı
  (yalnızca gerçek JVM/daemon ayarları kalıyor).
- Paket adı / sürüm için **erken doğrulama** eklendi: geçersiz girişte (örn. `com.1oyun`,
  `v1.0`) Gradle'ı hiç başlatmadan anlaşılır bir Türkçe hata dönüyor.
- `versionCode` artık otomatik hesaplanıyor (zamana dayalı, her build'de bir öncekinden büyük
  garanti) — aynı paket adıyla üstüne kurarken Android'in "downgrade" reddi yaşanmaz.
- `app.py`, build başlamadan **önce** aynı doğrulamayı yapıp anında geri bildirim veriyor.

**Bunu gerçekten test ettim:** `test_build_engine.py` içinde 41 ayrı test var (geçerli/geçersiz
paket adları, sürüm biçimleri, mevcut `ludens.properties` içeriğinin korunduğunun doğrulanması,
var olan plugin parametrelerinin ezilmediğinin doğrulanması, vb.) — hepsi çalıştırılıp **41/41
geçti**.

---

## 2) Hile Menüsü (yeni: "Cheats")

Projede zaten yarım bırakılmış, **hiçbir yere bağlı olmayan** bir `CheatMenu.kt` +
`JsBridge.kt` çifti vardı (`androidMain/kotlin/cheat/`, `bridge/`). Ne DI'ya, ne navigasyona,
ne de gerçek WebView'e bağlıydı — yani uygulamada hiçbir yerden açılamıyordu, ayrıca kullandığı
ham `android.webkit.WebView` referansı projenin asıl kullandığı
(`compose-webview-multiplatform`) yapıyla uyumsuzdu. Bunları kaldırıp doğru mimariyle yeniden
yazdım:

- `core/domain/port/player/CheatPlayer.kt` — port arayüzü (mevcut `AudioPlayer`/`FPSPlayer` ile
  aynı kalıp).
- `core/infrastructure/adapter/player/CheatPlayerAdapter.kt` — RPG Maker'ın çekirdek motor
  nesnelerini (`$gameParty`, `$gameActors`, `$gamePlayer`, `$dataItems`/`Weapons`/`Armors`,
  `SceneManager`, `DataManager`) doğrudan kullanır; **hiçbir eklentiye bağımlı değildir**, bu
  yüzden hangi RPG Maker oyununu port ederseniz edin çalışır. Her komut, ilgili nesne henüz
  yoksa (örn. hâlâ başlangıç ekranındaysanız) sessizce hiçbir şey yapmayacak şekilde korumalı
  yazıldı.
- Yeni ekran: altın ayarla/ekle, karakter HP/MP/seviye, partiyi iyileştir, eşya/silah/zırh ekle
  (tek tek ya da hepsini birden), ışınlanma, ölümsüzlük modu, duvarlardan geçme, oyun hızı
  çarpanı (1x–8x), slot'a kaydet/yükle, oyun menüsünü aç.
- "Ludens menüsüne" (hızlı eylemler paneline) yeni bir `Cheats` düğmesi olarak eklendi —
  varsayılan olarak **kapalı**, Ayarlar > Actions bölümünden ya da
  `ludens.settings.preset.actionItems=...,cheats` ile açılabilir.

---

## 3) Eklenti Görüntüleyici (yeni: "Plugins")

Aynı şekilde yarım bırakılmış bir `PluginManager.kt` vardı ama `java.io.File(wwwPath)` ile
diske erişmeye çalışıyordu — bu, oyun dosyalarının APK içine Compose Resource olarak
paketlendiği bu mimaride **çalışmazdı**. Onun yerine, çalışan oyunun canlı `window.$plugins`
dizisini JavaScript üzerinden okuyan yeni bir ekran yazdım:

- Her build'de gerçekten yüklenmiş pluginleri (isim, açıklama, durum) listeler.
- Bir pluginin durumunu kapatıp açabilirsiniz. **Dürüst olmak gerekirse:** RPG Maker
  pluginlerinin çoğu betiği sayfa yüklenirken çalışıp bitiyor, bu yüzden bu değişiklik en çok
  kendi durumunu sürekli kontrol eden "debug/yardımcı" tarzı pluginlerde anında etkili olur;
  bazı pluginlerde etkisini görmek için oyunu yeniden başlatmak gerekebilir. Değişiklik yalnızca
  o oturum için geçerlidir, APK'ya ya da `plugins.js`'e yazılmaz (bunu ekranda da belirttim).
- `Plugins` de yeni bir hızlı eylem olarak eklendi, varsayılan kapalı.

---

## 4) Eksik tuş: ESC / geri tuşu

RPG Maker'ın `Escape` (kod 27) tuşu zaten motor tarafında tanımlıydı ve Ayarlar > Controls'ten
istenen bir düğmeye manuel atanabiliyordu — ama **Android'in fiziksel/gesture geri tuşu hiçbir
zaman oyuna iletilmiyordu**; her zaman doğrudan "Uygulamadan çık?" onayı gösteriyordu. Bu,
oyun içinde bir menüyü kapatmak için sürekli ekrandaki dokunmatik kontrolleri kullanmanızı
gerektiriyordu.

**Düzeltme (`BackPopup.kt`):** Artık Ana ekrandayken geri tuşuna basmak, oyuna `Escape` (İptal/
Menü) tuşu gönderiyor — masaüstü sürümdeki gibi. Kısa süre içinde (2 saniye) tekrar geri
basarsanız, çıkış onayı gösteriliyor (Android'de yaygın olan "çıkmak için tekrar basın" kalıbı).
Diğer tüm ekranlarda geri tuşu eskisi gibi çalışıyor.

---

## 5) Diğer küçük ama gerçek iyileştirmeler

- `ActionType.from(value)` artık tanınmayan bir değerde çökmek yerine `Settings`'e geri
  dönüyor (ileride bir action türü kaldırılırsa eski kayıtlı verinin uygulamayı çökertmemesi
  için).
- `actions_cheats` / `actions_plugins` çeviri anahtarları **6 dilin de** (`en`, `es`, `ja`,
  `pt-rBR`, `ru`, `zh`) `strings.xml` dosyalarına eklendi (hepsi XML olarak doğrulandı, anahtar
  sayıları tutarlı).
- Kullanılmayan, işlevsiz bir `GamepadMapper.kt` taslağı da vardı (hiçbir gerçek gamepad/kontrolcü
  girişine bağlı değildi, "Kaydet" butonu bile hiçbir şey yapmıyordu) — yanıltıcı olacağı için
  kaldırdım. Gerçek fiziksel gamepad tuş eşleme desteği, bu projede hiç var olmayan yeni bir alt
  sistem (native `KeyEvent`/`MotionEvent` işleme) gerektirdiği için, derleyicisiz bu ortamda
  riskli bulup kapsam dışı bıraktım — isterseniz ayrı bir görev olarak ele alabiliriz.
- `ludens.properties`, `settings.mdx`, `input-keys.mdx`, `CHANGELOG.md` yeni özellikleri
  yansıtacak şekilde güncellendi.

---

## Test etmeniz gerekenler

1. **Öncelik:** `docker/` (build_engine.py + app.py) tarafını kendi ortamınızda deneyin — bir
   ZIP yükleyip farklı bir `Package ID` / `Uygulama Adı` girip build alın, kurulan APK'nın adının
   ve paket adının artık doğru geldiğini doğrulayın (`adb shell pm list packages` ile).
2. Ludens Android projesini `./gradlew assembleDebug` ile derleyin. Bir hata çıkarsa (ki
   yukarıdaki dürüstlük notunda belirttiğim gibi mümkündür), hata mesajını paylaşırsanız hemen
   düzeltirim.
3. Uygulamada Ayarlar > Actions'tan `Cheats` ve `Plugins`'i açın, hızlı eylemler panelinde
   görünüp görünmediğini kontrol edin.
4. Bir oyunu başlatıp Hile Menüsü'nden birkaç işlemi deneyin (altın, HP, ışınlanma).
5. Oyun içindeyken fiziksel/gesture geri tuşuna basıp bir menünün kapandığını doğrulayın.

Herhangi bir derleme hatası ya da beklenmedik davranış görürseniz, hemen buraya yapıştırın —
birlikte hızlıca düzeltiriz.
