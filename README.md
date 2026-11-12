## Onuncu aşama: hücum zincirinin nerede bittiğini görme

İnceleme dalı **`codex/team-continuity-perception`** ve [taslak PR #1](https://github.com/tolgagitmez/tribunmenager/pull/1) üzerinde geliştirilir. Bu aşama hücumu ölçer; önceki görev/algı sürümünün maç dengesi kabulünü veya `main` geçişini otomatik sağlamaz.

Maç ekranındaki **Hücum analizi**, top kazanımı → baskıdan çıkış → hat kırma → son bölge → ceza sahası → gerçek şut çıkışını, hücumun bittiği aşama ve olayla birlikte gösterir. Topun oyunda kaldığı süre, duran top/ara süresi ve 10 dakika top oyunda başına şut birlikte okunur. **Analizi JSON olarak indir**, hücum izlerini ve destek/bekleme/koşu kayıtlarını dışarı verir.

Planlanan hedef veya şut hazırlığı gerçekleşmiş ilerleme sayılmaz. İleride başlayan hücumlar, baskısız başlangıçlar ve ölçüm sonunda süren hücumlar ayrı tutulur. Destek mesafesi veya bekleme kaydı olası açıklamadır; tek başına kötü tercih ya da gereksiz bekleme kanıtı değildir.

```sh
npm ci
npm run test:stage10
python3 -m http.server 8000 --bind 127.0.0.1
```

Yerel sunucuda `tactics.html` üzerinden maçı başlat; **Hücum analizi** bağlantısını kullan. **309 test geçti; 0 hata, 0 atlanan.** Gerçek Chromium'da WebGL/prosedürel ve 2D panel, süre paydaları, JSON indirme, duraklat/devam ve yeniden başlatma kontrolleri geçti. Ayrıca 21 kontrollü hava oyunu/kaleci durumu ayrı sınandı; bunlar doğal başarı oranı sayılmaz. Kanıtlar ve ölçüm sınırları [DOGRULAMA.md](DOGRULAMA.md), yöntem [ARCHITECTURE.md](ARCHITECTURE.md) içindedir.

`football-sim.js`, dokuzuncu aşamanın `b29a8f9b…` kaynağıyla byte düzeyinde aynıdır. Ölçüm ek AI veya RNG sorgusu çalıştırmaz. Kayıt dönüşümü gerekmez; transfer ve günlük lig motoru değişmedi. Özgün data/assets eksikleri ve önceki denge kalibrasyonu işleri sürer. Aşağıdaki aşamalar tarihsel kayıttır.


Aynı sekiz kısa maçta iki motorda da dört şut çıktı; iki takım toplamında 10 dakika top oyunda başına yaklaşık **1,185 / 1,218 şut** oldu. Güncel inceleme motorunun baskılı ve uygun hatlı onaylı kazanımlarında sıralı iz **100 → 70 → 29 → 3 → 1 → 1** olur. Hat kırma sonrası son bölgeye sırayla geçemeden biten 21 bölümün 15'i top kaybı, altısı kazanılmış fauldür; ayrıca dört ilk-kayıt sıra uyumsuzluğu ve bir sansürlü kayıt ayrıdır. Ayrıntılar [okunabilir özet](docs/validation/attack-chain-summary.json), [tam JSON.gz izleri](docs/validation/attack-chain-matrix.json.gz) ve DOGRULAMA içindedir. Bu ölçüm hangi pozisyonların inceleneceğini gösterir; tek başına kötü kararın nedenini kanıtlamaz.

---

## Dokuzuncu aşama: görev devamlılığı ve oyuncu algısı

İnceleme dalı: **`codex/team-continuity-perception`**. Ortak görev/algı uygulaması ve regresyon kontrolleri tamamlandı; maç dengesi `main` için henüz kabul edilmedi. Aşağıdaki komutlar bu inceleme sürümü içindir.

Destek, verkaç, bindirme, pres ve markaj ortak görev kurallarıyla sürer. Oyuncu koşusunun amacını, bağlantı kurduğu oyuncuyu ve sürelerini korur; olağan bir yeni öneri önceki görevi anında kesmez. Top kaybı, görünür tehlike, acil temas ve takımın ortak görev devri beklemeyi aşabilir. Güvenli desteğe varışta, kesin görev ömrünü aşmayan **0,45 saniyelik** kısa bir kullanım penceresi açılır. Pasın hedef oyuncusu hazırlık sırasında ayrılır; sahiplik için gerçek top temasını bekler.

Takım planı **topa sahip olma, savunma, top kazanımı ve top kaybı** evrelerini ayrı izler. Aynı takımın yeni bir pası alması diğer oyuncuların görev dönemini sıfırlamaz. Saha oyuncuları rakipleri kendi görüş ve kısa gözlem belleğinden okur; görülmeyen bir rakibin yeni konumu karar sorgusuna sızmaz. Kısa baş taramaları yeni bilgi sağlayabilir. Baş ve boyun çizimi taramayı gösterirken gövde yönü, ayaklar ve temas noktaları korunur.

```sh
npm ci
npm run test:stage9
python3 -m http.server 8000 --bind 127.0.0.1
```

**245 test geçti; hata veya atlanan test yok.** Önceki 154 kontrolün yanında algı, görev yaşamı, motor entegrasyonu, takım görevi devri ve baş çizimi sınanır. BallPhysics ile 16 canlı fizik/kural yöntemi önceki yayımlanmış motorla aynı kaynağı kullanır. Gerçek Chromium'da WebGL/prosedürel ve 2D yolları, 22 oyuncu, algı/görev kayıtları, baş taraması ve duraklat/devam et kontrolleri geçti. Deneyler ve sınırları [DOGRULAMA.md](DOGRULAMA.md), uygulama düzeni [ARCHITECTURE.md](ARCHITECTURE.md) içindedir.

Yerel sunucuda `tactics.html` üzerinden maçı başlat. Yeni alanlar geçici maç durumundadır; kayıt dönüşümü gerekmez. Eksik özgün data/assets nedeniyle yedek çizim yolları kullanılır; transfer ve günlük lig API'si statik sunucuya eklenmedi. Takım koordinatörünün ortak görüntüsü hâlâ anlık iletişim varsayar; görüş engelleri, ses ve ayrıntılı dikkat modeli açık kalır. Önceki aşamalar aşağıda tarihsel kayıttır.

Dört 300 saniyelik sentetik karşılaştırmada kısa topsuz görev değişimi 585/3529'dan 389/3332'ye düştü. Buna karşılık top kaybı 27'den 59'a çıktı, şut 2'den 1'e indi; büyük taşıma dönüşü ve kullanılmayan destek oranları iyileşmedi. Ortak görev/algı temeli hazırdır; hazır bağlantı kullanımı ve maç dengesi sonraki kalibrasyon önceliğidir.

---

## Sekizinci aşama: gövde, momentum ve ayakla ortak top kontrolü

İlk kontrol, top sürme, top koruma ve açık oyundaki pas/vuruş hazırlığı artık aynı fiziksel uygulanabilirlik hesabını kullanır. Yakındaki bir topa erişmek tek başına keskin yön değişimi için yeterli değildir: oyuncunun mevcut hızı, gövdesi, kullanabileceği ayak ve bir sonraki temasa yetişmesi birlikte sınanır. İstenen dokunuş yetişmiyorsa gelen hızın bir kısmı korunur veya dokunuş ertelenir; top normal fizik altında ilerler. Alım ya da top koruma rakip müdahalesini engellemez.

Hesap gerçek hareket/enerji ve BallPhysics kurallarıyla, en fazla **0,65 saniye / 39 sabit adım** boyunca kopyada çalışır. Pas hazırlığı, kullanılan ayağın mevcut **0,14 saniyelik** temas/toparlanma saatini dikkate alır; diğer ayak boşsa sırf top sürme ritmi sürüyor diye pası bekletmez. Gerçek pas çıkışı yine hazır ayak, gövde yönü ve topun temas noktasına gelmesini gerektirir. Bu, yerden ayak kontrolünün ortak modelidir; tam bir biyomekanik yürüyüş modeli değildir.

```sh
npm ci
npm run test:stage8
python3 -m http.server 8000 --bind 127.0.0.1
```

`test:stage8`, önceki aşamalar ve GitHub alıcı yönü uzlaştırmasına ait **119 kontrolü** ve **35 yeni ortak dokunuş testini** birlikte çalıştırır: toplam **154 test**. Canlı dokunuş ile sonraki gerçek temasın kare sırası, sağ/sol ayak, koruma, ilk kontrol ve pas hazırlığı sınanır. Geçen fizik senaryoları genel pas veya hücum kalitesi artışı göstermez; karşılaştırmalar ve ölçüm sınırları [DOGRULAMA.md](DOGRULAMA.md), yöntem [ARCHITECTURE.md](ARCHITECTURE.md) içindedir.

GitHub `main` üzerindeki `82414b9` sürümünün alıcıyı top yaklaşırken açma davranışı, yerel hazırlık tazeliği ve tahmin saati kontrolleriyle birleştirildi. Ortak dokunuşun karşılaştırma tabanı bu birleşimden sonra, fizik değişikliğinden önce saklanan kaynaktır; Git HEAD değildir. Kaynakların ayrımı ve SHA-256 değerleri [taban kaydı](docs/validation/baselines/README.md) içinde korunur.

Yerel sunucunun `tactics.html` sayfasından maçı başlat. Eksik özgün data/assets nedeniyle mevcut prosedürel WebGL veya 2D yedek çizim kullanılır; statik sunucu transfer/günlük lig API'sini açmaz. `server.py` hâlâ eksik transfer kuralları ve oyuncu kataloğunu gerektirir. Yeni alanlar yalnız geçici maç durumundadır; kayıt dönüşümü gerekmez. Mevcut tarayıcı profili/adresini, `tribun-manager-pro09` anahtarını ve SQLite dosyanı koru. Önceki aşamalar aşağıda tarihsel kayıt olarak bırakılmıştır.

---

## Yedinci aşama: alımdan sonra ters bekleme kararını sınama

Oyuncu, alımdan sonraki **1,5 saniyede** hâlâ geçerli bir taşıma niyeti varken koşusunun tersine bir bekleme (`hold`) kararı verirse, yakın veya yaklaşan baskı altında iki komut karşılaştırılır. Mevcut `controlPreparation`, her komutu en fazla **0,75 saniye** gerçek hareket, top ve müdahale kurallarıyla kopyada yürütür. Yeni bekleme müdahaleye açılıyor, önceki hedefe devam ise müdahalesiz ve gerçek bir kontrol dokunuşuyla uygulanabiliyorsa oyuncu o hedefi sürdürür. Güvenli bekleme korunur; önceki hedef de tehlikeliyse körü körüne devam edilmez.

`npm run test:stage7` ile **115 test** çalışır: önceki 101 kontrol ve 14 yeni test. Aynı durumdan karşılaştırmalar, çoklu maç ölçümleri ve sınırlar [DOGRULAMA.md](DOGRULAMA.md) başındadır. Bu kısa karar önizlemesi, sonraki hamlelerde top kaybı olmayacağını veya genel hücum kalitesinin arttığını göstermez.

Yerel maç için proje klasöründe `python3 -m http.server 8000 --bind 127.0.0.1` çalıştırıp aynı sunucunun `tactics.html` sayfasından maçı başlat. Geliştirici kontrolleri için önce `npm ci`, ardından `npm run test:stage7` kullan. Eksik özgün data/assets nedeniyle maç mevcut prosedürel WebGL veya 2D yedek çizimi kullanır; statik sunucu transfer/günlük lig API'sini açmaz. `server.py` hâlâ eksik transfer kuralları ve oyuncu kataloğunu gerektirir.

Kayıt dönüşümü gerekmez. Mevcut tarayıcı profili/adresini, `tribun-manager-pro09` anahtarını ve SQLite dosyanı koru; sentetik denemeyi ayrı profilde yap. Ekonomi, kayıt şeması ve ödeme/reklam kodu değişmedi. Önceki aşamalar aşağıda tarihsel kayıt olarak korunmuştur.

---

## Altıncı aşama: top gelmeden gövdeyi hazırlama

Kendi takımının hedefli normal yerden pası ve yerden geri pasında alıcı, çıkış niyetini korurken gövdesini gelen topa en fazla **1 radyan** açık hazırlıyor. Önceden doğrudan çıkış yönüne dönmek topu oyuncunun arkasında bırakabiliyordu. Yeni yön bir hareket hedefidir: oyuncu mevcut **4,5 rad/sn** dönüş sınırını izler; gerçek alımda `firstControlContact` ayak bölgesini yine kontrol eder. Hazırlık geç kalırsa top hâlâ yavaşlatılıp normal hareketle toparlanır; hazır devam pası da gerçek vuruş hazırlığı ve ayak temasını bekler.

`npm run test:stage6` ile **101 test** çalışır. Aynı durumdan olumlu ve olumsuz doğal karşılaştırmalar, çoklu maç ölçümleri ve sınırlar [DOGRULAMA.md](DOGRULAMA.md) başındadır. Bu dar gövde hazırlığı değişikliği için genel pas veya hücum kalitesi artışı iddia edilmez.

Yerel oynanabilir maç için proje klasöründe:

```sh
npm ci
npm run test:stage6
python3 -m http.server 8000 --bind 127.0.0.1
```

Aynı sunucuda `tactics.html` sayfasından maçı başlat. Eksik özgün data/assets nedeniyle mevcut prosedürel WebGL veya 2D yedek maç modu kullanılır; bu statik sunucu transfer/günlük lig API'sini açmaz. `server.py` için eksik `data/transfer-rules.json` ve oyuncu kataloğu hâlâ gereklidir. Yerel maçın skoru gerçek gol çizgisi olaylarından üretilir; günlük lig ayrı sonuç hesabını kullanır.

Kayıt dönüşümü gerekmez. `tribun-manager-pro09` anahtarını, mevcut tarayıcı profili/adresini ve SQLite dosyanı koru; sentetik yerel denemeyi ayrı profilde yap. Ekonomi, kayıt şeması, oyun varlıkları ve ödeme/reklam kodu değişmedi. Önceki aşamalar aşağıda tarihsel kayıt olarak korunmuştur.

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
