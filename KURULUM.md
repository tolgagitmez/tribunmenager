# Orijinal League-Soccer masaüstü modu

Bu mod motorun sabitlenmiş upstream sürümünü (087414cde936c3e26ed0b8c244d9d85425ec5657) hiçbir Tribün Manager oynanış yaması olmadan derler. Linux veya grafik oturumu olan WSL için hazırlanmıştır. Git, Python 3.10+, CMake ve [upstream Linux derleme bağımlılıkları](https://github.com/awest813/League-Soccer/blob/087414cde936c3e26ed0b8c244d9d85425ec5657/scripts/setup_linux_deps.sh) önceden kurulu olmalıdır.

```sh
sh BASLAT_ORIJINAL.sh
# veya:
python3 start.py --mode original
# sadece kur/derle:
python3 start.py --mode original --original-build-only
```

İlk açılış ağ bağlantısı ve derleme gerektirir. Kaynak ve derlenmiş dosyalar web kökü dışında, kullanıcının ev dizinindeki `~/.cache/tribun-manager-original/` altında tutulur. Başlatıcı kaynak revizyonunu, temiz Git ağacını ve çalışma dosyalarının hash'lerini doğrular; her açılışta özel bir çalışma kopyası kullanır. Motor kendi varsayılan `football.config` dosyasıyla, argümansız açılır. Motorun kendisinin oturum sırasında değiştirdiği çalışma kopyası ayarları sonraki oturuma taşınmaz.

Motor kurulduktan sonra `sh BASLAT.sh` ile varsayılan yerel web sunucusunu aç; kulüp merkezindeki **Orijinal motor** bağlantısından motoru başlat. Bu bağlantı yalnızca 127.0.0.1 üzerinde çalışan yerel sunucuda ve aynı kaynak isteğinde çalışır. Tarayıcı kurulum yapmaz; bütünlük doğrulaması ve motorun başlatılması terminaldeki süreçte gerçekleşir. Aynı yerel sunucuda çift başlatma engellenir; ayrıca revizyon başına kayıt deposu kilidi iki ayrı normal başlatıcının eşzamanlı oturum açmasını engeller.

Normal kapanışta motorun kendi `saves/<lig>/autosave.sqlite` kayıtlarından yalnızca kullanıcının oynanmış olarak işaretlenen lig fikstürleri salt okunur biçimde özetlenir. Özet, yerel motor önbelleğinde son tamamlanan oturuma ait JSON dosyası olarak tutulur ve Orijinal motor ekranından **Durumu yenile** ile görüntülenir. Bu sonuçlar hızlı maç/kariyer verisi değildir; motorun görüntülü oynatımını kanıtlamaz ve Tribün ligine otomatik işlenmez. Motorun kendi `saves` klasörü normal kapanışta `~/.local/share/tribun-manager-original/<revizyon>/` altında ayrı bir anlık kopya olarak saklanır ve sonraki açılışta geri yüklenir. Yalnızca bu klasör saklanır; motor ayarları ve varsayılan veri tabanı taşınmaz. Başarısız kapanış veya geçersiz kayıt ağacı önceki kopyayı değiştirmez; son oturumdaki kaydedilmemiş ilerleme kaybolabilir. Eski anlık kopyalar yedek olarak kalır ve disk alanı kullanır. Kayıt yazma işlemi başarısız olduğunda son oturumun kayıtları mümkünse aynı depodaki `recovery-...` klasörüne taşınır; terminal kurtarma konumunu bildirir. Taşıma da başarısız olursa çalışma klasörü korunur. Kurtarma içeriği otomatik yüklenmez. Orijinal motor ekranı saklanmış kayıt ve kurtarma klasörü sayısını salt okunur biçimde gösterir. Çalışma klasörü başka bir açık oturuma ait olabilir; silmeden önce kontrol et. Her kopya 2 GiB ve 10.000 dosya/klasör sınırına tabidir. Bu mekanizma kariyer kayıtlarının çalıştığını veya Tribün ligine aktarımı doğrulamaz.

**Yerel maç görüntüsü:** Orijinal motor ekranında motoru aç, kendi menüsünden maçı başlat ve `Motor penceresini izle` düğmesine bas. Masaüstü tarayıcısının paylaşım seçicisinden League-Soccer uygulama penceresini seç. Bu özellik tarayıcının `getDisplayMedia` desteğine bağlıdır; tam ekran/sekme paylaşımı ve tanımlanamayan görüntü yüzeyleri reddedilir. Uygulama seçilen pencerenin gerçekten motor olduğunu otomatik doğrulayamaz. Görüntü sunucuya yüklenmez, kaydedilmez veya uzaktan yayınlanmaz; motorun sesi kendi penceresinden gelmeye devam eder. `İzlemeyi durdur` ile görüntü paylaşımını kesebilirsin. Motorun ayarlarına ve kaynak koduna dokunulmaz. Görüntü izlenirken tarayıcıya sunulan karelerden FPS, video çözünürlüğü, en uzun gözlem aralığı, 1 saniyeyi aşan gözlem boşlukları ve atlanan gözlem sayısı ölçülür. Bunlar motorun gerçek çizim FPS'i, ağ gecikmesi veya fizik donması değildir; arka plan ve duraklatılmış video ölçümleri sıfırlanır. Tarayıcı örnek akışındaki sonuçlar, gerçek maç FPS'i yerine kullanılamaz.

**Gerçek GPU üzerinde doğrulama:** Linux grafik oturumunda `glxinfo -B` çıktısında donanım hızlandırmasını ve OpenGL renderer adını kontrol et (llvmpipe yazılım çizimidir). Motoru varsayılan ayarlarıyla çalıştır; maçın her iki yarısında pencere önizlemesini görünür tut. `FPS raporunu indir` düğmesi son izleme oturumundan yalnızca sayısal kare ölçümlerini JSON olarak dışa aktarır; ekran görüntüsü, pencere adı ve ses içermez. Motorun gerçek çizim FPS'i veya benzersiz piksel değişimi olarak yorumlanmamalıdır. Yeni oturum eski raporu sıfırlar; gizli/duraklatılmış ölçümler hariç tutulur. Donanım bilgisi, maçın normal hızda oynatıldığı bilgisi ve raporu birlikte değerlendir. CI'da 27 Kasım 2026 tarihinde llvmpipe ortamında 29,99 kare/s aktarım, 1,62 piksel değişimi/s ve 2,70 s en uzun aynı piksel aralığı gözlendi; bu sonuç gerçek GPU ölçümü değildir.

Bu yol ayrı bir native masaüstü oyunudur: Tribün Manager web menajerlik arayüzünden kadro/taktik aktarımı, otomatik maç sonucu kaydı ve 30→5 dakika yayın bağlantısı henüz yoktur. Mevcut web maç rotası ve lig işlevleri değiştirilmemiştir; orijinal motor ayrı bir bağlantıdan açılır. Orijinal kaynaklar ve lisanslar yerel upstream checkout içinde saklanır; bu değişiklik motoru veya varlıklarını yeniden dağıtmaz.

---

# Tribün Manager kurulumu

Yerel futbol simülasyonu için **Python 3.10 veya üzeri** ve güncel Chrome, Edge veya Firefox yeterlidir. Oynamak için Node.js, npm veya Python paketi kurman gerekmez. İnternet bağlantısı olmadan yerel maç oynanabilir; bazı isteğe bağlı font ve görseller yüklenmeyebilir.

## 1. Oyunu indir

Doğrulanmış güncel oyun sürümü `main` dalındadır. Açık deneysel Pull Request'ler bu sürüme otomatik olarak dahil değildir.

- [Güncel sürümü ZIP olarak indir](https://github.com/tolgagitmez/tribunmenager/archive/refs/heads/main.zip), ZIP'i çıkar ve içindeki klasörü aç.
- Git kullanıyorsan:

```sh
git clone --branch main https://github.com/tolgagitmez/tribunmenager.git
cd tribunmenager
```

Mevcut Git kopyasını güncellemek için, kaydedilmemiş yerel değişikliklerin varsa önce koru; ardından `git switch main` ve `git pull --ff-only origin main` çalıştır. ZIP ile kurduysan yeni ZIP'i ayrı bir klasöre çıkar. Mevcut SQLite veritabanını silme.

## 2. Python'u kontrol et

[python.org/downloads](https://www.python.org/downloads/) adresinden Python 3.10 veya üzerini kur. Windows kurulumunda **Add Python to PATH** seçeneğini işaretle.

Windows terminalinde:

```bat
py -3 --version
```

macOS / Linux terminalinde:

```sh
python3 --version
```

## 3. Oyunu başlat

**Windows:** `BASLAT.bat` dosyasını çift tıkla. Tarayıcı açılmazsa aşağıdaki adresi kendin aç. Alternatif komut:

```bat
py -3 start.py
```

**macOS / Linux:** oyun klasöründe terminal aç:

```sh
sh BASLAT.sh
```

Alternatif komut:

```sh
python3 start.py
```

Tarayıcıda **http://127.0.0.1:8000/** adresini aç. **Kadro → Taktik → Maçı başlat** yolunu izle. Sunucu açık kaldığı sürece oyun çalışır; kapatmak için terminalde **Ctrl+C** kullan. HTML dosyalarını çift tıklayarak `file://` üzerinden açmak yerine bu adresi kullan.

## Yerel karşılaştırmalı maç testi

Sunucuyu varsayılan yerel modda aç. Aynı deneme kadrosu ve taktiklerle karşılaştırmak için hesabına bağlı olmayan temiz bir tarayıcı profili kullan. Aşağıdaki iki adres mevcut maç yapılandırmasının URL fragment desteğini kullanır. Her ikisi de seed 301 ile beş dakikalık yerel maç açar; menajer vuruşları otomatik kullanılır. Canlı lig maçının sonucu etkilenmez.

- [Normal motor](http://127.0.0.1:8000/match.html#%7B%22seed%22%3A301%2C%22matchMinutes%22%3A5%2C%22managerKicks%22%3Afalse%2C%22technicalTouchExperiment%22%3Afalse%7D)
- [Deneysel teknik kontrol](http://127.0.0.1:8000/match.html#%7B%22seed%22%3A301%2C%22matchMinutes%22%3A5%2C%22managerKicks%22%3Afalse%2C%22technicalTouchExperiment%22%3Atrue%7D)

Adres değişince sayfayı yeniden yükle; yalnızca fragment değiştirmek çalışan motoru yeniden başlatmaz. İki maçta aynı kadroyu, dizilişi ve taktiği koru. Skor, şut, isabet, pas ve hücum analizi verilerini karşılaştır. FPS için aynı kamera, grafik profili ve maç hızını kullan. Tek maçtan kalite artışı sonucu çıkarma. Teknik kontrol varsayılan olarak kapalıdır; diğer açık PR'lerdeki deneyler bu sürümde bulunmayabilir.

Geri bildirim verirken maç bağlantısını (seed ve deney ayarı), bilgisayar/telefon modelini, tarayıcıyı, grafik profilini, maç içi dakikayı ve mümkünse ekran kaydını belirt. Grafik performansı için TV kamera ve Performans profiliyle başla; GPU instancing ayrı deneysel bir seçenektir ve normal kullanımda kapalı kalmalıdır.

## Beş dakikalık hücum yoğunluğu — #69 deneme protokolü

Normal oyun hedefi beş dakikalık nominal maçtır (mevcut kurallardaki ek süre hariç). 15/90 dakikalık seçenekler karşılaştırmalı tanı içindir; daha uzun maç, düşük hücum yoğunluğunun çözümü sayılmaz.

Compact Attack henüz ana oyuna birleştirilmemiştir. Bu iki bağlantının farklı motor davranışı göstermesi için [#69 deneme dalını ZIP olarak indir](https://github.com/tolgagitmez/tribunmenager/archive/refs/heads/fix/five-minute-attack-density-20261125.zip), ayrı klasörde aç ve o klasörün sunucusunu başlat. Önceki sunucuyu kapat. Ana dal bu yeni bayrağı henüz okumaz. Aşağıdaki bağlantılar aynı seed, dizilişler ve yüksek pres rakibiyle, otomatik menajer vuruşları açık olmayan beş dakikalık denemeyi yapılandırır:

- [Mevcut hücum temposu](http://127.0.0.1:8000/match.html#%7B%22seed%22%3A42%2C%22matchMinutes%22%3A5%2C%22managerKicks%22%3Afalse%2C%22individualAI%22%3Atrue%2C%22territorialProgression%22%3Atrue%2C%22compactAttack%22%3Afalse%2C%22formation%22%3A%224-3-3%22%2C%22awayFormation%22%3A%224-2-3-1%22%2C%22tactics%22%3A%7B%22mentality%22%3A%22balanced%22%2C%22playstyle%22%3A%22possession%22%2C%22press%22%3A58%2C%22tempo%22%3A61%7D%2C%22awayTactics%22%3A%7B%22mentality%22%3A%22attacking%22%2C%22playstyle%22%3A%22direct%22%2C%22press%22%3A86%2C%22tempo%22%3A80%2C%22line%22%3A%22high%22%2C%22onLoss%22%3A%22counterpress%22%2C%22onWin%22%3A%22counter%22%7D%7D)
- [Compact Attack](http://127.0.0.1:8000/match.html#%7B%22seed%22%3A42%2C%22matchMinutes%22%3A5%2C%22managerKicks%22%3Afalse%2C%22individualAI%22%3Atrue%2C%22territorialProgression%22%3Atrue%2C%22compactAttack%22%3Atrue%2C%22formation%22%3A%224-3-3%22%2C%22awayFormation%22%3A%224-2-3-1%22%2C%22tactics%22%3A%7B%22mentality%22%3A%22balanced%22%2C%22playstyle%22%3A%22possession%22%2C%22press%22%3A58%2C%22tempo%22%3A61%7D%2C%22awayTactics%22%3A%7B%22mentality%22%3A%22attacking%22%2C%22playstyle%22%3A%22direct%22%2C%22press%22%3A86%2C%22tempo%22%3A80%2C%22line%22%3A%22high%22%2C%22onLoss%22%3A%22counterpress%22%2C%22onWin%22%3A%22counter%22%7D%7D)

Temiz, hesaba bağlı olmayan aynı tarayıcı profilini kullan; her bağlantıdan sonra sayfayı yenile. Maçları tamamla ve iki takımın ayrı ayrı şut, isabetli şut, ceza sahasına giriş (Hücum Analizi), top kaybı ve oynanan süre verilerini kaydet. Rakibin daha fazla şut atması tek başına baskı altındaki takımın iyileşmesi değildir. Tek seed sonucu genellenemez; otomatik denetim 8 eşleşmede iki motoru karşılaştırır. Fiziksel vuruş, top kontrolü, savunma ve ofsayt kontrolleri korunmalıdır. Bu protokolün bağlantı parametreleri kontrol edilmiştir; tarayıcıda oynanış doğrulaması ayrıca gerekir.

## Çalışma modları

Varsayılan başlatıcı **yerel maç modunu** açar. Kadro, taktik ve maç simülasyonu çalışır; transfer hesabı ve günlük lig API'si bu modda kapalıdır. Rakibin kayıtlı kadrosu yoksa maçta deneme kadrosu olduğu belirtilir. İnsan modeli, iskelet ve dokuları pakete dahildir; ayrıca model indirmen gerekmez. Model hazırlanamazsa maç prosedürel WebGL çizimine, WebGL kullanılamazsa 2D çizime geçer.

Modeli incelemek için aynı sunucuda **http://127.0.0.1:8000/player-studio.html** adresini aç. **Tam boy**, **Yüz** ve **Arka** kameralarını kullan; hareket seçimiyle deformasyonu incele. Maç ve stüdyodaki model durumunun ayrıntısını açarak model kimliğini, lisans kaydını ve yükleme hatalarını görebilirsin. Beklenen kimlik `tribun-makehuman-footballer-v1`, hazır durumu **İSKELETLİ OYUNCU MODELİ** olarak görünür. Stüdyo, ayrıntılı model hazırlanamazsa hata gösterir.

Tam sunucu modu, ayrıca şu üç dosyayı gerektirir:

```text
data/transfer-rules.json
data/player-catalog.json
data/club-seed.json
```

Bu çalışma kopyasında bu dosyalar bulunmuyor; boş veya rastgele içerik oluşturarak tam modu açmaya çalışma. Uygun ekonomi kuralları, doğrulanmış oyuncu kataloğu ve başlangıç kadrosu ayrıca sağlandıysa:

```sh
python3 start.py --mode full
```

Windows'ta aynı komutun başında `py -3` kullanabilirsin. Tam modun geliştirme sunucusu SQLite verisini `tribun-dev.sqlite3` dosyasında saklar. Mevcut veri dosyasını ve tarayıcı depolamasını koru. Kayıtlar tarayıcı profiline, adrese ve porta bağlıdır; `localhost` ile `127.0.0.1` ayrı tarayıcı depoları kullanır. Yerel gösterim maçının sonucu günlük lig fikstürünü değiştirmez.

## Canlı lig

Python'a ek olarak Node.js 24 LTS kur. Lig modu maç motorunu sunucuda çalıştırır ve transfer kataloğu gerektirmez.

```sh
python3 start.py --mode league --host 0.0.0.0
```

Windows'ta `py -3 start.py --mode league --host 0.0.0.0` kullan. İki menajer aynı sunucunun adresindeki `/league.html` sayfasını açmalı. Aynı ağda ikinci cihaz, `127.0.0.1` yerine sunucuyu çalıştıran bilgisayarın ağ adresini kullanır. Bir menajer lig kurar, diğeri davet koduyla katılır. Fikstür saati geldiğinde **Canlı maçı izle** bağlantısı açılır.

Maç sunucuda devam eder. İzlerken kendi takımının vuruşlarını seçebilirsin. Başka sekmeye geçersen izleyici bağlantısı kısa süre içinde düşer ve seçim otomatik kullanıma döner. Sunucu tamamlanan maçın skorunu SQLite lig tablosuna yazar.

## Sorun giderme

| Sorun | Yapılacak işlem |
| --- | --- |
| Python bulunamıyor | Python'u kur; terminali kapatıp yeniden aç. Windows'ta `py -3` dene. |
| 8000 portu kullanımda | `python3 start.py --port 8001` çalıştırıp http://127.0.0.1:8001/ adresini aç. Windows'ta `py -3 start.py --port 8001` kullan. |
| Siteye erişilemiyor | Başlatıcı terminalinin açık olduğunu ve tarayıcı adresiyle portun eşleştiğini kontrol et. |
| Tam mod eksik dosya hatası veriyor | Yerel maç için `--mode local` kullan; tam mod için listelenen gerçek veri dosyalarını temin et. |
| Transfer sayfasında bağlantı hatası | Yerel modda transfer API'si kapalıdır. Kadro ve taktik ekranından yerel maç başlat. |
| Görüntü 2D açılıyor | Tarayıcının donanım hızlandırmasını/WebGL desteğini kontrol et. 2D yedek görünümle maç devam edebilir. |
| Model paneli yedek veya geçersiz model gösteriyor | Ayrıntıları aç; eksik dosya yolunu veya veri alanını kontrol et. ZIP'i tamamen çıkartıp `assets/player/` klasörüyle birlikte başlat. Model dosyasını tek başına başka sürümden kopyalama. |
| Doku veya shader hatası görünüyor | Paneldeki teknik ayrıntıyı kaydet. Doku hatasında belirtilen PNG'nin pakette olduğunu, grafik hatasında tarayıcı/WebGL desteğini kontrol et. Maç yedek çizimle sürebilir. |
| Eski transfer hesabı yerel maç başlangıcını engelliyor | Önce aynı tarayıcıdaki veriyi dışa aktar/yedekle; deneme için ayrı bir tarayıcı profili aç. Kayıtlarını silmek zorunda değilsin. |

## Standart model aktarımı

Yerel sunucu açıkken `http://localhost:8000/interop-lab.html` adresinden aynı Blender GLB/glTF dosyasını iki çizicide karşılaştır. Model türü, klip, zaman, kamera ve 1/22 oyuncu seçenekleri ortak çalışır. Three.js ve yardımcı modüller yerel `vendor/` klasöründedir; bu ekran için Node.js veya CDN gerekmez. Düzenlenebilir Blender kaynağı ve yeniden üretim adımları [GLTF_PIPELINE.md](docs/GLTF_PIPELINE.md), ölçülen karar [GLTF_RENDERER_DECISION.md](docs/GLTF_RENDERER_DECISION.md) içindedir.

## Geliştirici doğrulaması

Oynamak için gerekli değildir. Testler için `package.json` içindeki sürüm aralığına uyan Node.js gerekir; **Node.js 24.15 veya üzerindeki 24.x** uygun bir seçimdir. Başlatıcı ve maç/ekonomi testleri Python standart kütüphanesini kullanır. Modelin yeniden üretimi ve varlık testleri ayrıca **Python 3.11+** ile [requirements-player-assets.txt](requirements-player-assets.txt) içindeki NumPy/Pillow sürümlerini gerektirir; bunları ayrı bir Python sanal ortamına kurabilirsin.

```sh
npm ci
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-player-assets.txt
npm run test:stage15
npm run test:manager-kick
npm run test:live-match
```

Windows'ta sanal ortamı `.venv\Scripts\activate` ile etkinleştir; Python komutlarında `py -3` veya etkin ortamın `python` komutunu kullan.

Tarayıcı denemeleri için `npx playwright install chromium` çalıştır. Ardından `npm run test:manager-kick-browser` ile masaüstü ve mobil vuruşu, `npm run test:live-match-browser` ile iki menajerin maç ekranını doğrula. Sistemde Chromium kuruluysa `CHROMIUM` değişkeniyle dosya yolunu verebilirsin.

Modeli paketlenmiş kaynaklardan internet kullanmadan ayrı bir dizinde yeniden üretmek için:

```sh
python3 tools/build-player-assets.py --from-package --output /tmp/tribun-player-rebuild
```

Windows'ta `py -3` ve örneğin `--output oyuncu-yeniden-uretim` kullanabilirsin. Çıktı yolu örnektir; mevcut oyun paketinin üzerine yazmak zorunda değilsin. Komut özgün kaynak dosyalarının ve lisansların sabit hash'lerini denetler. Ayrıntılar [oyuncu varlıkları sözleşmesinde](docs/PLAYER_ASSETS.md) bulunur.

Gerçek tarayıcı doğrulaması ayrıca Playwright ve Chromium gerektirir; ayrıntılar [DOGRULAMA.md](DOGRULAMA.md) içindedir. Test raporları ve açık geliştirme işleri [yol haritasında](SIMULASYON_YOL_HARITASI.md) açıklanır.


### Deneysel kayıtlı web kadrosu aktarımı (PR 95)

Orijinal motor ekranındaki **Kadro aktarım hazırlığını indir (JSON)** düğmesi yalnızca bu tarayıcıdaki kayıtlı kadroyu dışa aktarır. Sunucudaki güncel kadroyu doğrulamaz. Motor kurulduktan sonra seçilen native takımın kimliklerini ve diziliş yuvalarını incele:

```sh
python3 original_roster_import.py tribun-roster-preflight.json --inspect-team 1
```

Buradaki 1 yalnızca örnek kimliktir; gerçek takım kimliğini katalogdan seç. Ayrı bir eşleştirme JSON dosyası hazırla: `schema: 1`, `teamId`, `nativeSlotOrder` (native p1–p11 sırasındaki 11 web localIndex değeri) ve `assignments` (her kayıtlı oyuncu için `localIndex`, `nativePlayerId`, `firstName`, `lastName`, `nativeRole`). Tüm oyuncular bire bir eşleştirilmeli, ilk 11 değiştirilmemeli ve seçilen native dizilişin rolleri uyumlu olmalı. Otomatik isim/mevki tahmini yapılmaz.

```sh
python3 original_roster_import.py tribun-roster-preflight.json reviewed-mapping.json
```

Bu komut geçici çalışma dizininde ayrı bir veri paketi oluşturur. Orijinal menüde League Mode > New League > tribun-roster-pilot seç ve eşleştirilen takımla yeni lig oluştur. Paket isimleri, mevkileri ve ilk 11 sırasını aktarır, yerel motorun yedek sırasını korur. Oturum kapanınca geçici veriler silinir. Eşleşen kadroların oyuncu sayıları ve ilk 11 diziliş rolleri aynı olmalıdır.

Yeteneği aktarılacak oyuncunun eşleştirmesine isteğe bağlı `"reviewedSkills": ["passing", "pace"]` eklenebilir. Değerler kayıtlı oyuncunun web dışa aktarımından alınır. `passing` yerel motorun kısa pas, `pace` hız alanını hedefler. Ulaşılabilir aralık yerel motorun oyuncu profili, yaş ve taban puanına göre doğrulanır. Üst düzey bir `"reviewedTactics": {"team_pressure": 0.81, "support_distance": 0.29, "counter_attack": 0.73}` nesnesi doğrudan incelenmiş yerel taktik değerlerini kullanır. Her iki alan da isteğe bağlıdır ve yalnızca alternatif pakete yazılır. [Motorun doğrulanan yetenek anahtarları](original_skill_mapping.py)

### Özel HLS ses ve görüntü testi

Linux'ta orijinal motorun derleme bağımlılıklarına ek olarak Xvfb, FFmpeg, PulseAudio ve Chromium gerekir. Test, orijinal motorun ayrı smoke senaryosundan görüntü ve sesi yakalar ve iki bağımsız Chromium oturumuna yerel bağlantı üzerinden sunar.

```sh
npm ci --ignore-scripts
npx playwright install chromium
python3 start.py --mode original --original-build-only
python3 original_native_av_probe.py --browser
```

Sistemde kurulu Chromium için `CHROMIUM=/usr/bin/chromium` kullanılabilir. Rapor her izleyicinin ilk kare ve ilk ses sürelerini, ekrana sunulan kareleri, ses sinyalini, tampon beklemelerini ve kısa bağlantı kesintisi sonrası alınan segmentleri gösterir. Segment yaşı ve ilk ses/görüntü zaman damgası farkı kodlayıcı çıkışına aittir. Test, hızlandırılmış yerel örneğin bir bölümünü kapsar. [PR #95 doğrulaması](https://github.com/tolgagitmez/tribunmenager/pull/95)
