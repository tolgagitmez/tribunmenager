## Altıncı aşama: top gelmeden gövde hazırlığı

Hazırlıklı yerden pasın alıcısı artık doğrudan sonraki pas yönüne bakmıyor. Top yaklaşırken gövdesini, gelen topu önünde tutup seçilmiş çıkış yönüne de açılabilecek şekilde çeviriyor. Uzak koşuda normal koşu duruşunu koruyor. Dönüş süresi yetmezse önceki aşamanın topu yavaşlatıp toparlama davranışı çalışıyor; alım ve rakip müdahalesi gerçek temasa bağlı kalıyor.

```sh
npm ci
npm run test:stage6
python3 -m http.server 8000 --bind 127.0.0.1
```

Yerel sunucunun `tactics.html` sayfasından maçı başlat. Prosedürel WebGL ve 2D yedek çizim çalışır. Testler, aynı durumdan olumlu/olumsuz doğal karşılaştırmalar ve sekiz kısa maçın sonuçları [DOGRULAMA.md](DOGRULAMA.md) başında; algoritma [ARCHITECTURE.md](ARCHITECTURE.md) başındadır. Gövde açısının düzelmesi güvenli ilk dokunuş veya başarılı hücum garantisi değildir.

Kayıt dönüşümü gerekmez: `tribun-manager-pro09` anahtarını, mevcut tarayıcı profili/adresini ve SQLite dosyanı koru. Mevcut transfer oturumuna dokunmadan sentetik yerel maçı ayrı profilde deneyebilirsin. Ekonomi, transfer, oyun varlıkları, kayıt şeması ve ödeme/reklam kodu değişmedi. Gerçek ödeme/reklam sağlayıcısı etkinleştirilmedi.

Eksik özgün data/assets nedeniyle transfer/günlük lig API'si hâlâ doğrulanamıyor; `server.py` depoda olmayan transfer kuralları/oyuncu kataloğunu gerektiriyor. Yerel maçın skoru gerçek gol çizgisi olaylarından oluşur ve görüntü aynı durumu çizer. Günlük lig ayrı katsayı/Poisson sonuç hesabını sürdürür.

Sıradaki öncelik, bu gövde hazırlığını baskı altında ilk dokunuşun mesafesi ve çıkış zamanlamasıyla birleştirmek. Önceki aşamalar aşağıda tarihsel kayıt olarak korunmuştur.

---

## Beşinci aşama: temas anında uygulanabilir ilk kontrol

Hazırlıklı yerden pas alımında top oyuncunun arkasında veya ayak kontrol bölgesinin dışındaysa, eski yönlü kontrol/hızlı pas planı artık uygulanmaz. Mevcut temas topu yavaşlatır; oyuncu gerçek topa dönerek normal hareketle toparlar. Rakip müdahalesi ve bağımsız top fiziği çalışmaya devam eder. Açık ayakla alınan paslar eski davranışı korur.

`npm run test:stage5` ile **85 test** çalışır. Sekiz adet 300 saniyelik senaryoda hedef alımı **756/833 → 880/945**, takımın son dokunuşuyla dışarı giden hedefli pas **6 → 0** oldu. Ancak toplam top kaybı **92 → 101**, rakibin pası alması **23 → 28**, şut **3 → 1** oldu. Bu örneklem bütün hücum kalitesinin iyileştiğini göstermiyor. Aynı durumdan olumlu ve olumsuz karşılaştırmalar, ölçüm paydaları ve sınırlar [DOGRULAMA.md](DOGRULAMA.md) başındadır.

Yerel oynanabilir maç için proje klasöründe:

```sh
npm ci
npm run test:stage5
python3 -m http.server 8000 --bind 127.0.0.1
```

Aynı yerel sunucunun `tactics.html` sayfasından maçı başlat. Eksik özgün data/assets nedeniyle mevcut prosedürel WebGL veya 2D yedek maç modu kullanılır; transfer/günlük lig API'si bu komutla açılmaz. API `server.py` hâlâ depoda bulunmayan `data/transfer-rules.json` ve oyuncu kataloğunu gerektirir. Günlük lig sonucu ayrı bir katsayı/Poisson hesabından gelir; yerel maçın skoru simülasyondaki gerçek gol çizgisi olaylarından oluşur ve görüntü aynı maç durumunu çizer.

Kayıt dönüşümü gerekmez. `tribun-manager-pro09` anahtarını, mevcut tarayıcı profili/adresini ve SQLite dosyanı koru. Sentetik yerel denemeyi ayrı profilde yapmak mevcut transfer oturumunu korur. Ekonomi, oyun varlıkları, ödeme/reklam ve kayıt şeması değişmedi. Gerçek ödeme/reklam sağlayıcısı etkinleştirilmedi.

Sıradaki öncelik, top gelmeden gövdeyi hazırlama ve baskı altında çıkış seçimini bu temas kısıtıyla birleştirerek kontrol sonrası top kaybını azaltmak. Önceki aşamalar aşağıda tarihsel kayıt olarak korunmuştur.

---

## Dördüncü aşama: alıcının fiziksel olarak yetişebildiği koşu

Hedefli yerden pasın alıcısı için buluşma noktası artık yalnız üst hız varsayımıyla seçilmiyor. Aday noktalara gerçek hareket motoruyla hızlanma, frenleme, dönüş, enerji ve toparlanma hesabı uygulanıyor. Hiçbir aday planlama payına yetişmiyorsa uzak 2,4 saniye ufkuna koşmak yerine sınanan en yakın yaklaşma kullanılıyor. Bu bir alım garantisi değildir; gerçek temas kuralları korunur.

Değişiklik yalnız kendi takımının hedefli normal yerden pası/yerden geri pası alıcısındadır. Kaleci, savunmacı, serbest top, şut, hava topu ve ara pasın eski hesap yolları korunur. Aynı doğal örnekte kaçan pas artık gerçekten alındı; **genel maç metrikleri kötüleştiği için genel pas kalitesi artışı iddia edilmez.** Sayılar ve olumsuz sonuçlar [DOGRULAMA.md](DOGRULAMA.md) başındadır.

```sh
npm ci
npm run test:stage4
node tools/profile-receiver-interception.cjs --mode matrix --output /tmp/receiver-matrix.json
node tools/profile-receiver-interception.cjs --mode fork --follow-seconds 5 --output /tmp/receiver-fork.json
```

Yerel oynatma değişmedi: proje klasöründe `python3 -m http.server 8000 --bind 127.0.0.1` çalıştır; aynı sunucuda `tactics.html` üzerinden maçı başlat. Eksik özgün data/assets nedeniyle bu, mevcut WebGL/prosedürel veya 2D yedek maç modudur; statik sunucu transfer/günlük lig API'sini açmaz. Mevcut transfer oturumunu silmeden ayrı tarayıcı profiliyle sentetik maç denenebilir.

Kayıt dönüşümü gerekmez. `tribun-manager-pro09` anahtarını, tarayıcı profili/adresini ve mevcut SQLite dosyanı birlikte koru. Ekonomi, ödeme/reklam, kayıt şeması ve günlük lig kodu değişmedi. Önceki aşamaların açıklamaları aşağıda tarihsel kayıt olarak saklanmıştır.

---

## Üçüncü aşama: frenleyen alıcıya pas hedefi

Alıcı bilinen yerleşim noktasına yaklaşırken pas hedefi artık mevcut hızını sınırsız sürdüreceğini varsaymıyor. Yakın durma/dönüşlerde mevcut hareket motoru, oyuncu kopyası üzerinde kısa süre yürütülüyor. Hızlı oyuncu gerektiğinde hedefini fiziksel olarak aşabiliyor; oyuncu veya top durma noktasına taşınmıyor. Uzak koşu ve bilinmeyen komutlarda mevcut hız uzantısı korunuyor. Vuruştan sonra top aynı serbest fiziği izliyor.

```sh
npm ci
npm run test:stage3
node tools/profile-pass-arrival.cjs --mode matrix --output /tmp/pass-arrival-matrix.json
node tools/profile-pass-arrival.cjs --mode fork --output /tmp/pass-arrival-natural.json
node tools/compare-pass-arrival-controlled.cjs --output /tmp/pass-arrival-controlled.json
```

Araçların tabanı saklanmış ikinci aşama motorudur; HEAD eski yüklemeyi gösterdiği için karşılaştırma tabanı olarak kullanılmaz. Doğal örnek aynı oyuncu/top/seed durumundan dallanır; karar türü ve hazırlık zamanı değişebilir. Geçen testler, kontrol örnekleri ve olumsuz sonuçlar [DOGRULAMA.md](DOGRULAMA.md) başında; algoritma [ARCHITECTURE.md](ARCHITECTURE.md) başındadır.

Yerel oynatma aynıdır: proje klasöründe `python3 -m http.server 8000 --bind 127.0.0.1`, ardından aynı sunucuda `tactics.html` üzerinden başlat. Node yalnız geliştirici testleri için gerekir. Eksik özgün data/assets sebebiyle yerel maç mevcut WebGL/prosedürel veya 2D yedek çizimle çalışır; statik sunucu transfer/günlük lig API'sini açmaz. Önceki transfer oturumunu silmeden ayrı profille sentetik yerel maç denenebilir.

Kayıt dönüşümü gerekmez. Tarayıcı profili/adresi ve SQLite dosyasını birlikte koru; aynı `tribun-manager-pro09` kayıt anahtarı ve oyuncu kimlikleri kullanılır. Ekonomi, ödeme/reklam ve günlük lig kodu değiştirilmedi. Doğal örnekte birkaç bağlantı tamamlandıktan sonra rakip yine top kazanabiliyor; genel başarı/galibiyet garantisi yoktur.

Önceki aşamaların açıklamaları aşağıda tarihsel kayıt olarak korunmuştur.

---

## İkinci aşama: pres çıkışından sonra destek devamlılığı

Top pasla giderken yardımcılar artık eski pasörün çevresinde beklemek yerine alıcının tahmini buluşma noktasına göre hazırlanır. Alım çevresindeki kısa pencerede destek görevi korunur. Baskı yaklaşırken hazır devam pası, dönüş/temas/müdahale süresi uygun olduğunda gerçekten oynanabilir. Çapa, ayrılmış koşular ve `bekler geride kal` talimatı korunur.

Çalıştırma önceki aşamayla aynıdır: proje klasöründe `python3 -m http.server 8000 --bind 127.0.0.1`, ardından aynı sunucuda `tactics.html` üzerinden maçı başlat. Eksik özgün data/assets sebebiyle bu, mevcut yedek WebGL/2D yerel maç modudur; transfer/günlük lig API'sini açmaz. Mevcut transfer oturumunu silmeden ayrı tarayıcı profiliyle sentetik yerel maç denenebilir.

```sh
npm ci
npm run test:stage2
node tools/profile-support-continuity.cjs --mode matrix --output /tmp/support-matrix.json
node tools/profile-support-continuity.cjs --mode controlled --output /tmp/support-controlled.json
node tools/profile-support-continuity.cjs --mode fork --output /tmp/support-fork.json
```

Karşılaştırma aracının varsayılan tabanı, ilk aşamanın saklanmış tam motor kaynağıdır; Git HEAD değildir. Ayrıntılar [taban kaynağı](docs/validation/baselines/README.md), [mimari](ARCHITECTURE.md) ve [doğrulama/olumsuz sonuçlar](DOGRULAMA.md) içinde. Yeni aşama eski 19 kontrolü ve yeni destek testlerini birlikte çalıştırır. Kaynak raporları `docs/validation/support-continuity-*.json` dosyalarıdır.

Kayıt dönüşümü gerekmez: `tribun-manager-pro09`, oyuncu kimlikleri ve SQLite şeması korunur. Aynı tarayıcı profili/adresi ile mevcut SQLite dosyasını birlikte sakla; port/adres değişikliği tarayıcı kayıt alanını değiştirir. Ekonomi ve gerçek ödeme/reklam durumu değiştirilmedi. Daha sonraki pasın auta çıkması gibi başarısız devamlar hâlâ mümkündür; genel galibiyet/gerçekçilik artışı iddia edilmez.

Aşağıdaki ilk aşama açıklaması ve eski v1.27 belgeleri tarihsel kayıt olarak bırakılmıştır.

---

## Yeni geliştirme: alternatif pasın hazırlık süresi

v1.27 üzerine ilk aşama uygulandı. Açık pas koridoru artık tek başına yeterli değil: alternatif pasın gerçek dönüşü, hazırlık dokunuşları ve ayak-top teması, gözlenen rakip hareketinden tahmin edilen müdahaleyle birlikte okunur. Uygulanabilir alternatif yoksa kontrol/top koruma davranışının müdahaleye ne kadar erken açılacağı da karşılaştırılır. Kontrol daha erken tehlikeye giriyorsa riskli bir alternatif son çare olarak tutulabilir; güvenli pas diye etiketlenmez. Müdahale ve top fiziği korunur.

Taktik önceliği: önce fiziksel uygulanabilirlik; sonra mevcut pas/oyun planı puanı ve tempoya bağlı hazırlık süresi maliyeti. Yüksek tempo güvenlik kapısını kaldırmaz. Bu, bütün taktik/rol/kadro hedeflerinin tamamlandığı anlamına gelmez. Pres çıkışından sonraki destek devamlılığı sıradaki aşamadır.

### Bu eksik checkout ile yerel maçı çalıştırma

Python 3.10+ ile proje klasöründe:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

Aynı yerel sunucuda `tactics.html` sayfasından sentetik kadro/taktikleri seçip maçı başlat; doğrudan `match.html` da açılabilir. Maç WebGL'de mevcut prosedürel oyuncu modeline, WebGL yoksa mevcut 2D çizime döner. Bu çalışma ortamında iki yol da gerçek Chromium ile denendi. Statik sunucu yalnız yerel kadro/taktik/maç içindir; transfer ve günlük lig API'sini sağlamaz. Daha önce transfer oturumu açılmış tarayıcı, güncel kadroyu API'den ister; eksik API yüzünden maçı engelleyebilir. Yerel sentetik deneme için ayrı bir tarayıcı profili kullan, mevcut kayıtları silme.

Depoda özgün `data/`, `assets/` ve eski test/araç dosyaları bulunmuyor. `server.py` hâlâ `data/transfer-rules.json` eksikliğiyle duruyor; sahte ekonomi verisi eklenmedi. Özgün veri/varlıklar geri geldiğinde aşağıdaki normal `python3 server.py` akışı geçerlidir. Eksik portre/font/yüksek ayrıntılı model, yedek maç çizimini engellemese de görsel kaliteyi sınırlar.

### Yeni aşamayı doğrulama

Node sürümü `package.json` şartını sağlamalıdır (bu ortamda 24.22.1).

```sh
npm ci
npm run test:stage1
node tools/compare-pass-preparation.cjs --baseline-ref 695f552e3f529f1b011e20ddc0c34c7dce99dad8 --output /tmp/pass-preparation-matrix.json
node tools/profile-preparation-fork.cjs --baseline-ref 695f552e3f529f1b011e20ddc0c34c7dce99dad8 --mode safe --output /tmp/pass-preparation-fork.json
```

HTTP entegrasyon testi yerel dinleme soketi gerektirir. Yönetilen ortamın komut sandbox'ı bunu engellerse desteklenen izinli yürütmeyi kullan. Git alt süreçleri kısıtlıysa eski motoru ayrı bir dosyaya alıp iki araca `--baseline-file /dosya/yolu` ver. Karşılaştırma raporları [docs/validation](docs/validation/) altında; kapsam, olumsuz sonuçlar ve tekrar komutları [DOGRULAMA.md](DOGRULAMA.md) içinde.

### Eski kayıtlar

`tribun-manager-pro09` tarayıcı kayıt anahtarı, kadro kimlikleri ve SQLite şeması değiştirilmedi; yeni alanlar yalnız maçın geçici belleğinde. Kayıt dönüşümü gerekmez. Mevcut tarayıcı profili/adresi ile SQLite dosyanı birlikte koru; dosya adresi, farklı port ve sunucu adresleri ayrı tarayıcı kayıt alanlarıdır. Özgün transfer verileri geri yüklenmeden kayıtlı ekonominin çalıştığı iddia edilmez. Ödeme/reklam sağlayıcısı etkinleştirilmedi.

---

# Tribün Manager 3D v1.27 — Hareketli alıcıyı okumak

Pasın çıkış hedefi, alıcının mevcut koşu komutu, frenlemesi ve dönüşüyle yeniden tahmin edilir. Farklı hareket varsayımlarından biri güçlü tehlike gösteriyorsa, açık görünen diğer varsayım tek başına pası sürdürmeye yetmez. FIFA/EA FC oynanış ilkeleri referans alınır; yöntem mevcut Tribün motorunun özgün kodudur.

## Oyunu aç

1. ZIP'in tamamını bir klasöre çıkar.
2. Windows'ta **BASLAT.bat** dosyasını çalıştır. Python 3.10 veya daha yeni sürüm gerekir. macOS/Linux'ta `sh BASLAT.sh` kullan.
3. Tarayıcıda **http://localhost:8000** adresini aç. Üst menüden **Transfer** bölümüne geç.
4. Sunucu konsolunu oyun sırasında açık tut. Yeniden açıldığında önceki bakiyeler, ilanlar ve görevler devam eder.

Komutla başlatmak için oyun klasöründe `python3 server.py` (Windows: `py -3 server.py`) yeterlidir. Oyuncular için Node/npm kurulumu gerekmez; bunlar yalnız geliştirici arayüz testlerinde kullanılır.

`index.html` dosyasına çift tıklayarak önceki yerel kadro/taktik/maç bölümlerini açabilirsin. Transfer ve günlük lig sunucu üzerinden çalışır. Dosya adresi ile localhost ayrı tarayıcı kayıt alanlarıdır; dosya adresindeki kayıt otomatik olarak localhost'a taşınmaz. ZIP yükseltirken eski sunucuyu kapat, mevcut `tribun-dev.sqlite3` dosyanı yeni oyun klasörüne kopyala ve aynı tarayıcı/adresi kullan. Transfer oturumu tarayıcıda, ekonomi SQLite dosyasında saklanır; ikisi birlikte gerekir.

## Neler var?

- Mevcut değerin 1–2,5 katı arasında satış fiyatı ve en fazla 4 ilan.
- Fiyat yükseldikçe azalan satış olasılığı; farklı zamanlarda bilgisayar kulüplerine satış.
- 5 token ile mevcut değerden hızlı satış; son kaleci ve asgari kadro koruması.
- Mevki, özel mevki, yaş, güç, uyruk, lig ve tarihli gerçek form ile keşif.
- Kadro ihtiyacına göre 6 saat açık kalan, yalnız token ile alınabilen teklifler.
- Ayrı kulüp kredisi/token bakiyeleri ve işlem defteri.
- Alınan oyuncunun kadro, antrenman, taktik ve maça taşınması; satılanın yeniden seçilememesi.
- Günlük lige bağlanan kadronun gücünün sunucuda hesaplanması ve canlı günlük maçta kadro kilidi.

**Gerçek ödeme ve reklam sağlayıcısı henüz bağlı değildir.** Satın alma ve reklam izleme düğmeleri bu nedenle kapalıdır; para tahsil edilmez. Başlangıçtaki 120 token deneme hediyesidir. `K`, oyun içi kulüp kredisidir; gerçek para veya çekilebilir bakiye değildir.

Kurallar ve gelecek veri/gelir bağlantıları: **TRANSFER_SISTEMI.md**. Test kapsamı: **DOGRULAMA.md**.

## Geliştirici kontrolleri

```sh
bash test_all.sh
npm ci
npm run test:ui
node tests/transfers-ui.test.cjs
node tests/ball-physics.test.cjs
node tests/press-support.test.cjs
node tests/pressure-exits.test.cjs
node tests/keeper-gather.test.cjs
node tests/defensive-connection.test.cjs
node tests/pass-lane-read.test.cjs
node tests/pass-review.test.cjs
node tests/pass-release-read.test.cjs
node tests/receiver-forecast.test.cjs
python3 tools/profile-transfer-market.py
```

Günlük lig ayrı sonuç hesabını kullanır; yerel 3D maç bunun kaydı değildir. Kontrollü hareketler, aynı durumdan karar karşılaştırması, doğal maçlar ve açık sınırlar **DOGRULAMA.md** içinde açıklanır. Doğru hedef tahmini, başarılı pas veya topu koruma garantisi değildir.

Güncel motorun doğal örneği **previews/ALICI_HAREKETI_v127.mp4** içinde. Gerçek sahnenin yerel 3D çizimidir; tarayıcı/telefon performans testi değildir. Son iki sürümün videoları pakettedir. Referans **FIFA_REFERANSI.md**, sonraki geliştirmeler **SIMULASYON_YOL_HARITASI.md** içinde.
