# Altıncı aşama doğrulaması — top gelmeden gövde hazırlığı (5 Kasım 2026)

Taban, kullanıcının son yayımladığı beşinci aşama motorudur: `70387789…`; yeni kaynak `8c3b3c19…`. Tam taban `docs/validation/baselines/stage5-football-sim.js.gz` içinde, önceki teslim ZIP'iyle birebir kontrol edilerek saklanır. Git HEAD eski yüklemedir ve bu karşılaştırmanın tabanı değildir. Eski testler/raporlar ve aşağıdaki aşamalar tarihsel kayıt olarak korunur.

Alıcı top yaklaşırken gövdesini gelen top ve seçilmiş çıkış yönüne göre açar; uzak koşuda normal bakışını korur. **İlk kontrolün geometrisi düzelir, ancak her hücumun devamı iyileşmez.** Top kaybettiren doğal karşıt ve toplam kayıplardaki artış aşağıda açıkça tutulur.

## Geçen kontroller ve oynanabilir sürüm

`npm run test:stage6`: **97 test geçti**; önceki 85 kontrolün altı dosyası önceki teslimle byte düzeyinde aynıdır, 12 yeni test eklendi. Gerçek step/ballStep temasları iki yönde, dönüş süresi yeten/yetmeyen alımlar, 4,5 rad/sn sınırı, uzak koşu duruşu, farklı çıkış yönleri, gerçek hareketle yalıtılmış tahminin eşitliği ve canlı durumun korunması sınanır. On kapsam dışı durumda hareket beşinci aşamayla tam eşittir. RNG/gizli rakip komutu/gelecek plan okunmaz; serbest top bağımsız ilerler, rakip gerçek pası kesebilir ve doğru kontrol sonrası müdahale edebilir. Eski testler gevşetilmedi.

[Kaynak/kapsam kanıtı](docs/validation/reception-facing-physics-check.json): değişen mevcut yöntemler move ve projectPlayer, yeni yöntem receptionFacing'dir. Diğer **93 yöntem**, BallPhysics'in 13 sabit/fonksiyon üyesi, acquire/firstControlContact, süpürme yarıçapı, vuruş/temas/müdahale ve gol hesabı aynıdır. move içindeki hızlanma, fren ve açısal hız sınırları değiştirilmedi; istenen gövde yönü değişir. Üç doğal dalda ilk gerçek pasın zamanı/türü, hedefi, çıkış noktası, pasör/alıcı ve çıkış öncesi/sonrası top durumu aynıdır; bundan sonraki alıcı hareketi ve temas saati ayrışabilir.

[Gerçek Chromium](docs/validation/reception-facing-browser.json): taktik ekranından maç, 22 oyuncu, 15 saniyeden fazla ilerleme, destek planları, saat ve duraklat/devam hem prosedürel WebGL hem zorlanmış gerçek 2D çizimde geçti. Betik hatası yoktur. Eksik özgün model/font/portre/görsel 404'leri sürer. Yerel HTTP/DOM başlangıcı da 97 test içindedir. Bunlar telefon/60 FPS veya uzun tarayıcı maçı kanıtı değildir.

## Aynı doğal pas, üç farklı devam

Her örnek tam beşinci aşama motorunu başlangıçtan belirtilen tick sınırına kadar aynı sentetik kadro/taktik/tohumla yürütür. Tam oyuncu/top/Map/RNG durumu iki sürüme klonlanır; sonraki **6 saniye** normal plan, koşu, vuruş ve müdahaleyle ilerler. Karma eski sürüm öneki, zorlanmış RNG, hedefe taşıma veya hazır sonuç yoktur. Her dalın gözlemcisiz tam durum eşitliği geçer; bütün bu örneklerin iki skoru da 0–0 kalır.

- **[Olumlu pas zinciri](docs/validation/reception-facing-chain-fork.json):** narrow21, dallanma **166,633333** sn. Aynı 5 → 0 normal pası **166,650**'de çıkar. Eski alım **167,800**'de cushion, topun ileri bileşeni −0,961488 m ve gövde-top açısı 2,782971 rad'dır; rakip 16 **168,383333**'te topu alır. Yeni alım **167,733333**'te open, ileri bileşen +0,940130 m ve açı 0,363694 rad'dır. Alım konumu/saati değişmiştir; aynı temas anı diye sunulmaz. Gerçek hedef alımları 0 → 5 için **168,916667**, 5 → 3 için **171,200**, 3 → 6 için **172,450** olur; altı saniye sonunda kendi oyuncusu 6 topa sahiptir. Bu sınırlı zincir sonrası gol veya sürekli top koruma garantisi yoktur.
- **[Geometrik düzelme, hedef kaçırılan devam](docs/validation/reception-facing-fork.json):** press42, dallanma **24,050** sn. Aynı 13 → 11 pası **24,066667**'de çıkar. Eski alım **25,316667**'de cushion; gövde-top açısı 2,338653 rad, ileri bileşen −0,654844 m. Yeni alım **25,200**'de open; açı 0,982736 rad, ileri bileşen +0,592773 m. Sonraki 11 → 15 pasını **27,466667**'de hedef 15 yerine kendi oyuncusu 13 alır; hedef başarısı sayılmaz. Pencere sonunda top boştadır. Eski dal da daha sonra kendi oyuncusu 13'le topu toparlayıp 13 → 12 pasını **29,500**'de tamamlar; yeni dalın bütün devamı üstün değildir.
- **[Olumsuz karşıt](docs/validation/reception-facing-loss-fork.json):** balanced21, dallanma **24,250** sn. Aynı 5 → 2 pası **24,266667**'de çıkar; iki alım da **25,133333**'tedir. Eski cushion alımında ileri bileşen −0,510029 m; yeni open alımında +0,459432 m olur. Buna rağmen yeni dalda rakip 18 **25,800**'de, yani kontrolden **0,666667 sn** sonra topu kazanır. Eski dal 2 → 5 pasını **26,283333**'te tamamlar. Eski dal da daha geç, **30,233333**'te topu kaybeder; karşılaştırma penceresinde sonsuza dek top koruduğu iddia edilmez.

## Sekiz tam kısa maç

[Matris](docs/validation/reception-facing-matrix.json): 8 senaryo × 2 motor × 300 sn; üç tohum, farklı rakip planları, 65/82/91 sentetik kadro ve 4-3-3/4-4-2/3-5-2. Genişlik ve pas tercihi çiftlerinde aynı kadro/rakiple yalnız ilgili talimat değişir. **16 gözlemcili tam maç, aynı 16 koşulda gözlemcisiz tam durum eşitliği ve iki deterministik tekrar geçti.** Sekiz taban koşusu önceki aşamanın sonuçlarını yeni pasif temas ölçümü dışındaki alanlarda aynen yeniden üretir. Skorlar gerçek gol olaylarıyla eşit, durumlar sonludur. En büyük oyuncu adımı **0,118822 → 0,127858 m/60 Hz**; 0,15 m sınırı aşılmaz.

Temas ölçümü yalnız gerçekten alınmış, hazırlanmış hedefli yerden pass/through/cutback ve kaleci olmayan oyuncuları içerir. Kaçan veya rakibin aldığı paslar bu ölçüme girmez. Eski **863** kapsam içi alımın **485**'i (%56,20), yeni **762** alımın **756**'sı (%99,21) mevcut ayak bölgesine uygundur. Hazır olmayan temas **378 → 6**, ortalama gövde-top açısı **1,427609 → 0,862832 rad** olur. Bu oyunun geometrik kapısıdır; bütün pasların alındığı, ilk dokunuşun güvenli olduğu veya gerçekçi insan başarı oranına ulaşıldığı anlamına gelmez. Yakın rakip <3 m alt kümesinde hazır temas **11/22 → 35/35**; farklı yollar nedeniyle aynı baskı olaylarının birebir karşılaştırması değildir.

Uçuş tablosu iki takımı birlikte sayar; yalnız gerçek release gözlemcisinin izlediği hedefli paslar vardır. Hedefin alması, başka kendi oyuncusunun alması ve rakibin alması ayrı tutulur; pencere sonunda yolda kalanlar çözülen paydaya girmez.

| Senaryo | Hedef alımı / çözülen hedefli uçuş (beşinci → altıncı) | Skor (beşinci → altıncı) |
| --- | --- | --- |
| balanced21 | 118/129 → 109/116 | 0–0 → 0–0 |
| press42 | 121/126 → 97/103 | 0–0 → 0–0 |
| narrow21 | 128/132 → 103/113 | 0–0 → 1–0 |
| wide21 | 98/107 → 89/93 | 0–0 → 0–0 |
| short42 | 120/130 → 104/110 | 0–0 → 0–0 |
| direct42 | 101/114 → 95/102 | 0–0 → 0–0 |
| weak442-77 | 131/136 → 112/118 | 0–0 → 0–0 |
| strong352-21 | 63/71 → 69/79 | 0–0 → 0–0 |

Toplam hedef alımı **880/945 (%93,12) → 778/834 (%93,29)**, rakibin hedefli pası alması **28 → 20**, başka kendi oyuncusunun alması **24 → 29** olur. En küçük örneklenmiş yatay alıcı/top farkı ortalaması **1,9357 → 1,7065 m**; bu merkez farkı süpürme teması veya hava topu yüksekliğinin yerine geçmez. Toplam pas/tamamlanan pas **948/905 → 837/807**. İlk farklı davranıştan sonra yollar ayrışır; oran değişimi tek bir pasın nedensel genel yararını kanıtlamaz. Özellikle narrow21 hedef alım oranı 128/132'den 103/113'e geriler.

**Olumsuzlar:** takımın son dokunuşuyla doğrudan dışarı giden hedefli pas **0 → 1**, toplam telemetri top kaybı **101 → 111**, düello **105 → 126**, boşta top **89 → 100** olur. Şut **1 → 5**, gol **0 → 1** (narrow21 ev sahibi) olur; bu küçük örnek üretken hücum veya skor dengesi kanıtı değildir. Şut/gol kotası veya istenen skora göre katsayı ayarı yapılmadı.

Hazırlıklı gerçek hedef alımından sonraki bir saniyede rakip alımı **4/881 → 4/778** kalır. Eski 881 pencerenin 878'i tamam, üçü maç sonunda eksik; yeni 778'in tamamı kapanır. Yakın rakip <3 m alt kümesinde **2/24 → 2/37**, eksik pencere yoktur. Eksik pencereler korunmuş top sayılmaz. Bir saniye rakip alımı olmaması sürekli sahiplik anlamına gelmez; boşta top, kendi pası veya sonraki geç kayıp olabilir.

Uçuş gözlemcisi aerial() içinde üretilen kafa paslarını izlemez; gerçek acquire gözlemcisi bunları da görebilir. Uçuş tablosunun hedef alımı 880/778, hazırlanmış gerçek alım sayısı 881/778'dir; paydalar birbirinin yerine kullanılmaz. Üretilen kafa pası telemetrisi 2 → 1'dir; üretilen her kafa pası tamamlanmış alım değildir.

Taktiğin yerleşim etkisi korunur: yeni narrow21 ev sahibi ortalama genişliği **36,53 m**, aynı kadro/rakipli wide21 **44,86 m**; ortalama savunma çizgisi sırasıyla −20,24 ve −18,47 m. Bunlar saniyede bir açık oyun örnekleridir. Maç yolları ayrıştığından genişlik talimatının bütün sonuç etkisi izole edilmiş sayılmaz. Pas mesafeleri, genişlik/çizgi ve geçiş telemetrisi her ham satırda vardır.

## Yeniden üretme ve sınırlar

```sh
npm run test:stage6
node tools/profile-reception-facing.cjs --mode matrix --output /tmp/reception-facing-matrix.json
node tools/profile-reception-facing.cjs --mode fork --output /tmp/reception-facing-fork.json
node tools/profile-reception-facing.cjs --mode fork --scenario balanced21 --at 24.25 --output /tmp/reception-facing-loss.json
node tools/profile-reception-facing.cjs --mode fork --scenario narrow21 --at 166.63333333333333 --output /tmp/reception-facing-chain.json
```

Varsayılan doğal örnek press42/24,05 sn, izleme **6 saniye**dir. Araç tam taban/güncel motor, taktik ve gözlemci hash'lerini kaydeder. Gözlemciler bütün parametreleri korur; tam durum eşitliğinde yalnız kendi acquire/release/setRestart sarmalayıcıları silinir. Runtime snapshot zorunlu değildir. Kısa pilot tam maç yerine sayılmaz; yeni motorla tam 90 dakika doğrulandığı iddia edilmez.

Yeni duruş istenen açıdır; 4,5 rad/sn dönüş, hız/baskı ve değişen top yönü nedeniyle temas yine hazır olmayabilir. Ayak bölgesi içindeki çıkış açısı, ilk kontrol mesafesi ve baskıya göre güvenli devam hâlâ sınırlamadır. Sonraki öncelik bu kontrol/çıkış seçimini iyileştirmektir; olumsuz balanced21 örneği saklanır. Hava topu, kaleci, serbest top veya eksik oyunculu kadro/rol sistemi bu aşamada genişletilmedi.

Ekonomi, transfer, günlük lig, kayıt şeması, oyun varlıkları ve ödeme/reklam kodu değişmedi. Eksik özgün data/assets nedeniyle transfer/günlük lig API'si ve depoda bulunmayan tarihsel testlerin tamamı doğrulanamadı. Yerel maç gerçek gol olaylarından skor üretip aynı durumu çizer; günlük lig ayrı sonuç hesabını sürdürür. Çalıştırma ve eski kayıtları koruma talimatları README başındadır.

---

# Beşinci aşama doğrulaması — temas anında ilk kontrol (5 Kasım 2026)

Taban, kullanıcının son yayımladığı dördüncü aşama kaynağıdır: `406526af…`; yeni motor `70387789…`. Tam taban kaynağı `docs/validation/baselines/stage4-football-sim.js.gz` içinde saklanır ve dördüncü aşama ZIP'iyle birebir kontrol edilmiştir. Git HEAD karşılaştırma tabanı değildir. Eski test/raporlar ve aşağıdaki aşamalar tarihsel kayıt olarak korunmuştur.

Bu aşama, top ayak kontrol bölgesinin dışındayken hazırlanmış yönlü dokunuş/hızlı pas uygulanmasını engeller. Mevcut yakın temas topu yavaşlatır; oyuncu bağımsız topu normal hareketle toparlamaya çalışır. Bu her durumda daha iyi top koruma sağlamaz: aynı durumdan gerçek bir top kaybı karşı örneği aşağıdadır.

## Geçen kontroller

`npm run test:stage5`: **85 test geçti**. Önceki 71 kontrolün beş dosyası önceki teslimle byte düzeyinde aynıdır; 14 yeni test eklendi. Gerçek ballStep temasları iki geometrik yönde çalışır; arkadan/yandan temas, through/cutback, açık ayakla eski davranışın korunması, rakibin pası kesmesi ve toparlanma sırasında müdahale, hareket eden topun takibi, saatin bitmesi, gerçek hızlanma/dönüş, bağımsız BallPhysics, sorgu saflığı ve sekiz kapsam dışı durumun eski tam durumla eşitliği sınanır. Düşük teknik/yüksek gelen hızın mevcut yavaşlatma darbesine etkisi korunur. Eski testler gevşetilmedi.

[Kapsam kanıtı](docs/validation/first-control-physics-check.json): değişen mevcut yöntemler yalnız acquire ve plan; 92 diğer yöntem ve BallPhysics'in 13 sabit/fonksiyon üyesi aynıdır. move/effort/release/startKick/kickStep/contactPoint/doTackle/ballStep ve gol hesabı değiştirilmedi. Dört doğal karşılaştırmada ilk alımın hemen öncesindeki bütün kaydedilen oyuncu/top/hazırlık durumu eşittir. Temas topu veya oyuncuyu yeniden konumlandırmaz. Yeni ayak bölgesi kapısı alım yarıçapını büyütmez ve rakibe karşı koruma vermez.

[Gerçek Chromium](docs/validation/first-control-browser.json): taktik ekranından maç başlangıcı, 22 aktif oyuncu, 15 saniyeden fazla simülasyon, destek planları, maç saati ve duraklat/devam hem prosedürel WebGL hem zorlanmış gerçek 2D çizimde geçti. Betik hatası yoktur. Eksik özgün font/model/portre/görsel 404'leri sürer. Bu kısa masaüstü kontrolü telefon performansı veya 60 FPS kanıtı değildir. Yerel HTTP/DOM başlangıç testi de 85 kontrolün içindedir; sandbox'ın yerel soket kısıtı için izinli yürütme kullanıldı.

## Aynı durumdan doğal karşılaştırmalar

Her örnek, tam dördüncü aşama motorunu başlangıçtan belirtilen tick sınırına kadar aynı sentetik kadro/taktik/tohumla çalıştırır. İki dal aynı tam nesne grafiği, top ve RNG durumundan **5 saniye** yürür. Sonraki plan, koşu, müdahale, temas ve rastgelelik normal motor tarafından belirlenir; sonuç zorlanmaz. Dört örnekte de iki dalın skoru 0–0 kalır. Her dalın gözlemcisiz tam durum eşitliği ayrıca geçer.

- [Olumlu hızlı devam karşıtı](docs/validation/first-control-fork.json): narrow21, dallanma 154,616667 sn. 14 → 13 pasını iki dal da **154,633333**'te alır. Topun gövdeye göre ileri bileşeni −0,681442 m, yakın rakip 1,698773 m'dir. Eski one-touch modu 0,045 sn saat verir; rakip 1, **154,983333**'te topu alır. Yeni cushion modu 0,326296 sn kontrol saati kullanır; temasın ilk top hızı iki dalda aynıdır. 13 → 16 pası **155,250**'de çıkar ve **155,616667**'de alınır; sonraki 16 → 15 pası **157,600**'de alınır. Pencere sonundaki 15 → 11 pası hâlâ yoldadır ve başarı sayılmaz.
- [Arkadan yönlü kontrol karşıtı](docs/validation/first-control-protect-fork.json): press42, dallanma 17,466667 sn; through 5 → 2 alımı **17,483333**. Top yaklaşık 0,996 m uzakta ve ileri bileşen −0,980440 m'dir. Eski protect dokunuşu top hızını (2,03435; −0,38883) m/sn yönüne çevirir; yeni dal eski temel yavaşlatma darbesini (2,80237; 0,70777) m/sn ile korur. Eski dalda rakip 15, **20,483333**'te topu kazanır. Yeni dal **17,950**'de kendi lehine serbest vuruş alır. Bu, temiz pas veya sürekli top koruma başarısı diye sayılmaz.
- [Başarılı eski hücumun durduğu karşıt](docs/validation/first-control-counter-fork.json): wide21, dallanma 174,516667 sn; 13 → 15 alımı **174,533333**. Eski hızlı devam 15 → 12 pasını **175,566667**'de tamamlar. Yeni dal cushion modundan sonra **175,183333**'te kendi lehine serbest vuruş alır; aynı akıcı pas devamı gerçekleşmez. Bu da otomatik üstünlük diye yorumlanmaz.
- **[Olumsuz top kaybı karşıtı](docs/validation/first-control-loss-fork.json):** press42, dallanma 22,750 sn; 15 → 11 alımı **22,766667**. Eski protect davranışı 11 → 14 pasını **23,600**'de çıkarır ve **24,766667**'de tamamlar. Yeni cushion davranışında rakip 4, **24,266667**'de topu kazanır. Top kaybı alımdan **1,5 saniye** sonra olduğundan aşağıdaki bir saniyelik ölçümde görünmez. Bu örnek kısa pencere metriğinin sınırını da gösterir.

## Sekiz tam kısa maç: karışık sonuçlar

[Matris](docs/validation/first-control-matrix.json): 8 senaryo × 2 motor × 300 sn. Üç tohum, farklı rakip planları, 65/82/91 sentetik kadro gücü ve 4-3-3/4-4-2/3-5-2 kullanılır. Genişlik ve pas tercihi çiftlerinde aynı kadro/rakiple yalnız ilgili talimat değişir. **16 gözlemcili tam maç, aynı 16 koşulda gözlemcisiz tam durum eşitliği ve iki deterministik tekrar geçti.** Bütün durumlar sonlu, skorlar gerçek gol olaylarıyla eşittir. En büyük oyuncu adımı eski 0,123802 m, yeni 0,118822 m/60 Hz; 0,15 m sınırı aşılmadı.

Tablo iki takımı birlikte sayar. Hedef alımı gerçek acquire olayıdır; başka kendi oyuncusunun alımı başarı hanesine eklenmez. Pencere sonunda yolda kalan uçuşlar çözülen paydaya girmez. İlk farklı davranıştan sonra yollar ayrışır; bu toplamlar aynı tek pasın nedensel etkisi veya genel gerçekçilik testi değildir.

| Senaryo | Hedef alımı / çözülen hedefli uçuş (dördüncü → beşinci) | Skor (dördüncü → beşinci) |
| --- | --- | --- |
| balanced21 | 83/92 → 118/129 | 0–0 → 0–0 |
| press42 | 112/123 → 121/126 | 0–0 → 0–0 |
| narrow21 | 99/107 → 128/132 | 0–0 → 0–0 |
| wide21 | 86/95 → 98/107 | 0–0 → 0–0 |
| short42 | 98/114 → 120/130 | 0–1 → 0–0 |
| direct42 | 96/101 → 101/114 | 0–1 → 0–0 |
| weak442-77 | 104/114 → 131/136 | 0–0 → 0–0 |
| strong352-21 | 78/87 → 63/71 | 0–0 → 0–0 |

Toplam hedef alımı **756/833 (%90,76) → 880/945 (%93,12)**; hedef kaçırma **77 → 65**, takımın son dokunuşuyla doğrudan dışarı çıkan hedefli pas **6 → 0**, en küçük örneklenmiş yatay alıcı/top farkı ortalaması **2,1432 → 1,9357 m**. Toplam pas/tamamlanan pas **835/793 → 948/905**. Yatay merkez farkı süpürme teması veya hava topu yüksekliğinin yerine geçmez.

**Olumsuzlar:** toplam telemetri top kaybı **92 → 101**, rakibin hedefli pası alması **23 → 28**, düello **100 → 105** olur. Strong352 hedef alımı **78/87 → 63/71** ile geriler. Şut **3 → 1**, gol **2 → 0** olur; yeni sekiz kısa maçın hepsi 0–0 biter. Daha yüksek pas alım oranı üretken hücum veya dengeli skor kanıtı değildir. İstenen şut/gol sonucu için katsayı ayarı yapılmadı.

Yeni motorda **863** uygun kapsamdaki temas değerlendirmesi, **378** cushion ve **6** hazırlanmış hızlı aksiyon ertelemesi kaydedilir. Bu sayaçlar başarılı kurtarma veya tamamlanmış pas değildir.

## Alımdan sonraki bir saniye ve payda ayrımı

Gerçek acquire gözlemcisi, hazırlanmış hedef alımlarından sonraki bir saniyeyi ayrıca izler. Eski **757** alımın 755 penceresi tamamlanır, ikisi maç sonunda eksiktir; rakip sekiz kez alır. Yeni **881** alımın 878 penceresi tamamlanır, üçü eksiktir; rakip dört kez alır. Yakın rakip <3 m olan alt kümede bütün pencereler tamamdır: **6/37 → 2/24** rakip alımı. Daha az baskılı duruma girilmesi de yolların ayrışmasının sonucudur; birebir aynı baskı altında genel başarı diye sunulmaz. Rakip duran topu ayrı kaydedilir; eksik pencere ve boşta top otomatik korunmuş top sayılmaz. Yukarıdaki +1,5 sn kayıp bu metriğin dışındadır.

Uçuş tablosu önceki araçtaki **release gözlemcisini** korur; aerial() içinde doğan kafa pasları bu uçuş paydasına girmez. Gerçek alım gözlemcisi bunları da görür. Bu nedenle uçuş tablosundaki hedef alımları 756/880, hazırlıklı gerçek alım sayıları 757/881'dir; birbirinin paydası olarak kullanılmaz. Kafa pası telemetrisi 1 → 2'dir. Kapsam dışı uçuşların eksikliği gizlenerek genel pas doğruluğu iddia edilmez.

Taktiklerin konumsal karşılığı korunur: yeni narrow21 ev sahibi ortalama takım genişliği **37,65 m**, aynı kadro/rakipli wide21 **45,93 m** olur. Bunlar saniyede bir açık oyun örnekleridir; iki maç aynı yolda kalmadığından yalnız genişlik değişiminin bütün skor etkisini izole etmez. Her satırın savunma çizgisi, genişlik, pas ve geçiş telemetrisi ham rapordadır.

## Yeniden üretme ve kalan kapsam

```sh
npm run test:stage5
node tools/profile-first-control.cjs --mode matrix --output /tmp/first-control-matrix.json
node tools/profile-first-control.cjs --mode fork --output /tmp/first-control-fork.json
node tools/profile-first-control.cjs --mode fork --scenario press42 --at 17.466666666666665 --output /tmp/first-control-protect.json
node tools/profile-first-control.cjs --mode fork --scenario wide21 --at 174.51666666666668 --output /tmp/first-control-counter.json
node tools/profile-first-control.cjs --mode fork --scenario press42 --at 22.75 --output /tmp/first-control-loss.json
```

Varsayılan doğal örnek narrow21/154,616667 sn; varsayılan izleme beş saniyedir. Raporlar tam taban/güncel motor, taktik ve gözlemci hash'lerini içerir. Gözlemciler bütün fonksiyon parametrelerini korur; eşitlik denetiminde yalnız kendi acquire/release/setRestart sarmalayıcıları silinir. Kısa pilot tam maç doğrulaması yerine sayılmaz.

Yöntem tam ilk kontrol/ayak anatomisi veya gerçek tek temaslı pas modeli değildir. Uçuş boyunca gövde hazırlığı ve ayak bölgesi içindeki keskin çıkış açıları hâlâ sınırlamadır; hava topu/kaleci/serbest top kontrolü değiştirilmedi. Sonraki öncelik, gövdeyi top gelmeden hazırlamak ve kontrol sonrası güvenli çıkışı bu kısıtla birlikte değerlendirmektir. Top kaybettiren doğal karşıt regresyon örneği olarak tutulur.

Ekonomi, transfer, günlük lig, oyun varlıkları, kayıt şeması ve ödeme/reklam kodu değişmedi. Eksik özgün data/assets nedeniyle transfer/günlük lig API'si ve depoda bulunmayan tarihsel testlerin tamamı doğrulanamadı. Yerel maç skoru gerçek olaylardan gelir; günlük lig ayrı sonuç hesabını sürdürür. Kayıt taşıma ve oynanabilir yerel maç komutları README başındadır.

---

# Dördüncü aşama doğrulaması — fiziksel alım koşusu (5 Kasım 2026)

Taban, kullanıcının yayımladığı üçüncü aşama motorudur: `4c9279ad…`. Tam kaynak `docs/validation/baselines/stage3-football-sim.js.gz` içinde saklanır. Yeni `profile-receiver-interception.cjs`, kaynakları ayrı CommonJS modüllerine yükler; motor/taktik/gözlemci hash'leri raporlardadır. Eski gözlemciler ve raporlar değiştirilmedi. Aşağıdaki önceki aşama bölümleri tarihsel kayıttır.

**Bu aşama belirli bir iyimser yetişme hatasını gideriyor; genel pas kalitesi artışı göstermiyor.** Çoklu maçtaki kötüleşmeler aşağıda açıkça raporlanır.

## Geçen kontroller

`npm run test:stage4`: **71 test geçti** — önceki 60 test aynen korunarak 11 yeni kesişme testi eklendi. İki geometrik yön, duran/uzaklaşan/yaklaşan oyuncu, temas/toparlanma saati, enerji/kondisyon, en iyi sınanan yaklaşma, çizgi dışı adayların elenmesi, gerçek top/oyuncu/komut/seed/gözlemlerin değişmemesi, gizli rakip komutu/gelecek plan/RNG okunmaması, eski kapsam ve zaman sınırları, bir plan içinde tek sorgu ve serbest top fiziği sınanır. Atlanan veya sıfır testli koşu başarı diye sayılmaz.

[Kaynak ve kapsam kanıtı](docs/validation/receiver-interception-physics-check.json): BallPhysics'in bütün fonksiyonları ile move/effort/release/doTackle/acquire/startKick/kickStep/contactPoint gövdeleri üçüncü aşamayla birebir aynıdır. Kapsam dışı 11 durumda yeni `interceptPoint` çıktıları eski motorla sayısal olarak da eşleşir. Alım yarıçapı, vuruş hatası, rakip müdahalesi veya gol hesabı kolaylaştırılmadı. Doğal dalın ilk çıkışında vuruş saati/türü/noktası, pasör/alıcı durumu ve topun çıkış öncesi/sonrası durumu iki sürümde eşittir.

[Gerçek Chromium](docs/validation/receiver-interception-browser.json): taktik ekranından maç, 22 oyuncu, 15 saniyeden fazla simülasyon, destek planları, saat ve duraklat/devam WebGL/prosedürel ve WebGL kapalı gerçek 2D çizimde geçti; betik hatası yoktur. HTTP/DOM testi ayrıca geçer. Eksik model/font/portre 404'leri sürer. Bu testler telefon veya 60 FPS performans kanıtı değildir.

## Kontrollü hareket farkı

Sentetik alıcı (10;2), top (0;0) ve 17 m/sn yerden hızda eski model, alıcı dursa da uzaklaşsa da yaklaşıyor olsa da **0,5 sn** noktasını seçer. Aynı komuta gerçek hareket uygulanınca, yalnız o seçilmiş zamandaki fark yaklaşık duran oyuncuda **1,85 m**, uzaklaşanda **3,62 m**, toparlanma sırasında **2,29 m**'dir. Eski üst hız kapısı bu farkları ayırmıyordu.

Yeni testler seçilen noktaya doğru gerçek 60 Hz hareketi karşılaştırır. Örneğin yaklaşan oyuncuda yaklaşık 0,6 sn/0,599 m örneği 0,7 m planlama payını karşılar; duran oyuncuda en iyi sınanan yaklaşık 0,7 sn/0,831 m noktası `reachable:false` olabilir. **Bu flag gerçek alımın imkânsız olduğu anlamına gelmez:** gerçek hedef alımı 1,10 m swept temas sınırını kullanır ve iki örnek arası temas mümkün olabilir. Planlama payı ile fiziksel temas ayrı tutulur; testler bunu garanti başarı diye kullanmaz.

Kondisyon örneğinde alıcı (12;6), top hızı 6 m/sn ve duran başlangıçtan, tam enerjili oyuncu 1,8 sn'deki adaya, enerji 0,25/kondisyon 45 oyuncu 1,9 sn'deki adaya yetişir. Canlı enerji/kondisyon değeri tahmin çağrısıyla değişmez. Bunlar bütün maçlar için doğruluk garantisi değildir.

## Aynı doğal pasın yeniden yürütülmesi

[Doğal rapor](docs/validation/receiver-interception-fork.json), tam üçüncü aşama motorunun `press42` matris yapılandırmasını başlangıçtan **29,183333 sn**'ye kadar çalıştırır. Bu örnek karma eski aşama öneki kullanmaz. Tam nesne grafiği ve RNG (305224883) iki sürüme klonlanır. Sonraki **5 saniye** normal plan/hareket/müdahale/temas ile yürür; hedef veya RNG sonucu zorlanmaz.

| Aynı ilk pas | Üçüncü aşama | Dördüncü aşama |
| --- | --- | --- |
| Gerçek normal pas 5 → 3 çıkışı | 29,200 sn | 29,200 sn; aynı top/oyuncu/çıkış durumu |
| Hedefle en küçük örneklenmiş yatay merkez farkı | 1,220124 m | 1,056057 m |
| Sonuç | Alım yok; 33,283333 sn'de rakibe taç | Oyuncu 3 gerçekten 30,750 sn'de alır |
| Ardışık receive-run komut hedeflerinde en büyük değişim | 22,261852 m | 3,150063 m |

Son satır oyuncu ışınlanması değildir: komut hedeflerinin değişimidir. Support/between-lines → receive-run ilk görev geçişi bu metrikten ayrıdır; yeni dalda bütün komut değişimleri sayılırsa ilk geçiş yaklaşık 13,35 m'dir. Gerçek oyuncu adımları iki dalda yaklaşık 0,101 m/60 Hz altında kalır.

Yeni dalda 3 → 6 pası da 32,483333'te hedef tarafından alınır. Sonraki 6 → 4 pasını ise 33,733333'te **hedef 4 yerine kendi takımından oyuncu 3** alır. Bu üçüncü hedef başarısı diye sayılmaz; rakip top kazanımı da değildir. Beş saniyelik pencerede iki skor 0–0 kalır. Sınırlı doğal düzeltme, genel başarı veya devamlı korunan top kanıtı değildir.

## Çoklu maç sonuçları — genel ölçümler kötüleşti

[Matris](docs/validation/receiver-interception-matrix.json): 8 senaryo × 2 motor × 300 sn. Üç tohum, farklı rakip planları, 65/82/91 sentetik kadro gücü ve 4-3-3/4-4-2/3-5-2 vardır. Taktik çiftlerinde aynı kadro/rakiple yalnız genişlik veya pas tercihi değiştirilir. **16 gözlemcili tam maç, aynı 16 durumun gözlemcisiz tam maç durumu eşitliği ve iki tam deterministik tekrar geçti.** Gözlemci bütün temel fonksiyonları bir kez çağırır ve restart'ın tüm parametrelerini korur.

Her maç tamamlandı; oyuncu/top durumu sonlu, skorlar gerçek gol olaylarıyla eşitti. En büyük oyuncu adımı yaklaşık **0,123802 m/60 Hz**; 0,15 m sınırı aşılmadı. İlk farklı karar sonrası maç yolları ayrışır; toplam skorlar tek bir yerel davranışın nedensel yarar ölçümü değildir.

Tablo iki takımı birlikte sayar. Dar pas kategorisi normal pass/cutback türleridir; bunların her anında yeni yolun aktif olduğu iddia edilmez (kaleci, yükseklik vb. kapsam kapıları da vardır). Hedefli uçuşlar ancak gerçek alım, kesilme, dışarı çıkış, gol veya uçuşun kapanmasıyla çözülür. Pencere sonunda yolda kalanlar paydadan çıkarılır. Başka kendi oyuncusunun alması, hedef alımı ve rakip kazanımı ayrı kayıttır.

| Senaryo | Normal/geri pas hedef alımı / çözülen uçuş (üçüncü → dördüncü) | Skor (üçüncü → dördüncü) |
| --- | --- | --- |
| balanced21 | 83/87 → 81/89 | 0–0 → 0–0 |
| press42 | 98/106 → 110/121 | 0–0 → 0–0 |
| narrow21 | 95/99 → 99/106 | 1–0 → 0–0 |
| wide21 | 103/110 → 83/87 | 0–0 → 0–0 |
| short42 | 98/108 → 97/111 | 0–1 → 0–1 |
| direct42 | 77/81 → 87/90 | 0–0 → 0–1 |
| weak442-77 | 87/99 → 104/113 | 0–0 → 0–0 |
| strong352-21 | 59/60 → 68/74 | 0–0 → 0–0 |

Bütün pas türleri birlikte:

- Hedef alımı **717/777 (%92,28) → 756/833 (%90,76)**; hedef kaçırma **60 → 77**. Hedef kaçırma başka kendi oyuncusunun almasını da içerdiğinden her kaçırma top kaybı değildir.
- Takımın son dokunuşuyla dışarı giden hedefli uçuş **5 → 6**.
- En küçük örneklenmiş yatay merkez farklarının ortalaması **1,9509 → 2,1432 m** ile kötüleşti. Bu ortalama hava toplarında yükseklik/gerçek temasın yerine geçmez.
- Toplam pas/tamamlanan pas **779/744 → 835/793**. Daha fazla pas, daha yüksek hedef başarısı değildir.

Yalnız normal pass/cutback türlerinde hedef alımı **700/750 (%93,33) → 729/791 (%92,16)**; takımın son dokunuşuyla dışarı çıkış **4 → 3**, ortalama fark **1,6921 → 1,8104 m**. Dar kategoride dışarı çıkış azalırken diğer ölçümler kötüleşir. Ara pasların dışarı çıkışı da **1 → 3** olur; ara pas hesabı doğrudan değiştirilmemiş olsa bile önceki hareket/kararlar sonraki yolları etkiler. Narrow21 skoru 1–0 → 0–0, direct42 0–0 → 0–1 olur; diğer altı satırda skor değişmez. Bu sonuçlar gizlenmez veya istenen skora göre ayarlanmaz.

## Yeniden üretme ve sınırlar

```sh
npm run test:stage4
node tools/profile-receiver-interception.cjs --mode matrix --output /tmp/receiver-matrix.json
node tools/profile-receiver-interception.cjs --mode fork --follow-seconds 5 --output /tmp/receiver-fork.json
```

Varsayılan taban tam saklanmış üçüncü aşama kaynağıdır; araç hash'ini doğrular. Doğal örnek baştan 29,183333 sn'ye kadar aynı yapılandırmayla yürütülebilir. İsteğe bağlı `--save-snapshot /tmp/receiver.bin` / `--snapshot-file /tmp/receiver.bin` taban hash'i, zaman ve kayıtlı provenance kontrolüyle tanıyı hızlandırır; rapor için zorunlu değildir. Kısa `--seconds 30` pilot, 300 sn doğrulama yerine sayılmaz. Gerçek telefon/uzun tarayıcı maçı ve bütün tarihsel CI testleri çalıştırılmadı.

Tahmin yalnız sabit aday komutunu ve gözlenen arkadaş hızlarını kullanır; omuz ayrıştırma temaslarını, sonraki takım/rakip planlarını ve ilk kontrolün değişen gövde yönünü içermez. 0,1 sn örnekleme ve 2,4 sn ufuk sürekli bir optimum araması değildir. Kaleci/savunmacı/hava topu/serbest top iyileştirmesi bu kapsamda yoktur. Eksik özgün veri/varlıklar nedeniyle transfer/günlük lig API'si yine doğrulanamadı. Ekonomi, SQLite/tarayıcı kayıt biçimi ve ödeme/reklam kodu değişmedi.

Sonraki öncelik, bu düzeltilmiş koşuyu baskı altında uygulanabilir ilk kontrol ve gövde yönüyle birleştirmek; özellikle matriste kötüleşen hedef kaçırmaları üzerinde aynı durumdan ayrıntılı karşıtlar çalışmaktır. Bu aşama genel pas kalitesinin iyileştiği iddiasıyla teslim edilmez. Çalıştırma ve kayıt taşıma README başındadır.

---

# Üçüncü aşama doğrulaması — frenleyen alıcıya pas (5 Kasım 2026)

Taban, önceki teslim paketindeki ikinci aşama motorudur (`0adbed0b…`). Tam kaynak `docs/validation/baselines/stage2-football-sim.js.gz` içinde tutulur; Git HEAD başlangıç yüklemesinde kaldığı için taban olarak kullanılmaz. Yeni motor, gözlemci, taktik ve doğal örneğin eski önek kaynakları ham raporlarda SHA-256 ile kaydedilir. Önceki aşamaların raporları aşağıda tarihsel kayıt olarak bırakılmıştır.

## Geçen testler ve oynanabilirlik

`npm run test:stage3`: **60 test geçti**. Önceki 38 testin assertion/eşikleri değiştirilmedi. Yeni 22 test; beş komut türünde iki yönlü frenleme, ters/çapraz dönüş, yüksek momentumla fiziksel hedef aşımı, uzak koşunun korunması, eksik/bozuk komut ve pace değerleri, hareketsiz/geçersiz alıcı, hedef Map/seed/top/gerçek konumların değişmemesi, rakibin gizli komutuna/gelecek plana erişilmemesi, önceden kopyalanmış oyuncunun kendisinden kaçınmaması, 1,6 sn ve eski 0,45 sn sınırları, gerçek normal yerden pas alımları ve gerçek savunmacı kesmesini kapsar. Hareket karşılaştırmaları, aynı komut sürdürülen fiziksel 60 Hz adımlardır; rakibin geleceğini bilen bir maç modeli değildir.

[Kaynak kontrolü](docs/validation/pass-arrival-physics-check.json): BallPhysics'in bütün fonksiyonları ile move, effort, startKick, kickStep, contactPoint, release, doTackle ve acquire gövdeleri ikinci aşamayla birebir aynıdır. Yeni alıcı hedefi bu mevcut fonksiyonların girdilerini/kararlarını etkiler. Ek olarak test, pas çıktıktan sonra alıcı ve komutları değiştirilse bile topun aynı BallPhysics yörüngesini izlediğini doğrular. Temas yarıçapı, vuruş gücü formülü veya savunma müdahalesi kolaylaştırılmadı.

[Gerçek Chromium kontrolü](docs/validation/pass-arrival-browser.json): taktik ekranından maç başlatma, 22 oyuncu, 15 saniyeden fazla gerçek simülasyon, saat ve duraklat/devam iki modda geçti: WebGL/prosedürel çizim ve WebGL kapalı gerçek 2D. Betik hatası yoktu. DOM/HTTP entegrasyonu ayrıca test edildi; onun canvas taklidi tek başına GPU kanıtı sayılmadı. Eksik font/portre/yüksek ayrıntılı model 404'leri sürer; telefon/60 FPS/uzun tarayıcı maçı ölçülmedi.

## Aynı doğal durum: hedef aşımı ve gerçek devam

[Doğal rapor](docs/validation/pass-arrival-natural.json), ilk aşamanın önde baskı/77 maçını 3652,25 sn'ye kadar, ardından ikinci aşamayı 3655,30 sn'ye kadar normal adımlarla yeniden kurar. Bu açıkça kayıtlı karma önek, önceki aşamanın auta giden durumuna ulaşmak içindir. **Yeni motorla tam 90 dakikalık maç çalıştırıldığı iddia edilmez.** Sonrasında iki sürüm aynı tam oyuncu/Map/top/vuruş/seed durumundan 8 saniye yürür; hareket, müdahale, karar ve RNG sonuçları zorlanmaz.

İkinci aşama dalında üçüncü top:

- Oyuncu 3 → 1 normal pası 3655,533'te çıkar. Alıcı (26,732; −2,892) konumunda yaklaşık (0,603; 4,540) m/sn hızla, bilinen shape noktasına (27,111; −0,032) yaklaşır.
- Pas hedefi mevcut hız uzantısıyla (27,382; 2,008)'dir. Aynı mesafedeki gerçek top noktası hedefe yaklaşık **3,4 cm** yanal fark yapar. Doğal alıcıyla en küçük örneklenmiş yatay merkez farkı **1,393568 m** kalır; alım olmaz. 3659,400'de rakibe aut vuruşu çıkar.

Üçüncü aşama dalında fren/dönüş tahmini seçenek puanlarını ve gerçek hazırlığı da değiştirir:

- Yeni karar 3 → 1 **ara pasıdır**; gerçek çıkış 3655,833, gerçek alım 3657,0167'dir. Çıkış noktası, pas türü ve vuruş saati değiştiği için bunu “aynı pasın yalnız açısı düzeltildi” diye sunmuyoruz.
- 1 → 2 normal pası 3657,200'de çıkar, 3658,500'de alınır. 2 → 1 ortası 3659,2667'de çıkar, 3660,700'de alınır. Üç hedefli uçuşta gerçek alım vardır; bunlar yalnız tahmin edilen noktalar değildir.
- **Olumsuz devam:** rakip 19, 3661,4667'de top kazanır; 3661,600'de geri alınır. Dördüncü pas sekiz saniyelik pencere sonunda hâlâ yoldadır ve başarı sayılmaz. İki dalın skoru 5–0 kalır. İlk aut hatasının giderilmesi, hücumun sürekli korunacağı veya gol üretileceği anlamına gelmez.

Mevcut receive-run kesişme hesabı hâlâ iyimser üst hız kullanır; gerçek dönüş/frenle alıcının erken veya geç kalması devam eden bir sınırlamadır.

## Sabit komutlu normal pas karşıtları

[Kontrollü rapor](docs/validation/pass-arrival-controlled.json) ve gerçek normal pas testleri, oyuncunun shape noktasında frenlediği daha dar durumu ayırır. Aynı sentetik tohum, başlangıç kadrosu ve bilinen komutlar en fazla altı saniye korunur; bu örneklerde sonraki taktik plan bilerek sabit tutulur. Fiziksel move/step, temas, pas hatası ve savunmacının araya girmesi çalışır. Alıcı hedefe taşınmaz.

- İlk yönde ikinci aşama normal pası kaçırır ve 15,9667'de aut olur; yeni normal pas hedefteki oyuncu tarafından **11,1833**'te alınır.
- Ters geometrik yönde iki sürüm de alır: **11,2333 → 11,1500**. Her iki yönde birden eski sürüm başarısızmış gibi gösterilmez. Aynı oyuncular/ayak özellikleri kullanılır; bu tam bir takım/tercih edilen ayak simetrisi değildir.
- Koridora gerçek bir savunmacı eklenen iki yönde **iki sürümde de rakip alır**. Yeni hedef hesabı rakibe dokunulmazlık veya zorunlu alım sağlamaz. Savunma çizgisi için ayrıca uzak bir savunmacı vardır; alıcı ofsaytla elenerek karşıt sonuç üretilmez.

Yatay merkez örnekleri gerçek swept temas yarıçapının yerine geçmez. Özellikle orta/yüksek toplarda yükseklik ve dokunuş anı da önemlidir; bir metrikte küçük yatay fark tek başına başarılı kontrol değildir.

## Çoklu maç: olumlu ve olumsuz sonuçlar

[Matris](docs/validation/pass-arrival-matrix.json): 8 senaryo × 2 motor, her biri 300 sn. Üç tohum, farklı rakip planları, 65/82/91 sentetik kadro gücü ve 4-3-3/4-4-2/3-5-2 kullanılır. Genişlik ve pas tercihi çiftlerinde aynı kadro/rakiple yalnız tek talimat değişir. Toplam **16 gözlemcili maç**, aynı 16 koşulun **gözlemcisiz tam durum eşitliği** ve **iki tam deterministik tekrar** geçti. Gözlemci restart'ın seçili taker/initial dahil bütün parametrelerini iletir; skor/RNG yanında bütün maç durumu kontrol edilir.

Her maç tamamlandı; oyuncu/top değerleri sonlu ve skorlar gerçek gol olaylarıyla eşitti. En büyük oyuncu adımı **0,122332 m/60 Hz**; 0,15 m sınırı aşılmadı. Kısa maçlar ve daha sonra ayrışan yollar gerçekçilik/denge veya nedensel galibiyet kanıtı değildir.

Aşağıdaki alımlar iki takım birlikte sayılır. “Çözülen hedefli uçuş” gerçek alım, kesilme, dışarı çıkış, gol veya uçuşun kapanmasıyla sonlanır; pencere sonunda yolda kalanlar paydadan çıkarılır. Başka kendi oyuncusunun alması, hedef alımı sayılmaz ama otomatik top kaybı da değildir. Ham JSON bunları ayrı tutar.

| Senaryo | Hedef alımı / çözülen hedefli uçuş (ikinci → üçüncü) | Skor (ikinci → üçüncü) |
| --- | --- | --- |
| balanced21 | 64/68 → 84/89 | 0–0 → 0–0 |
| press42 | 104/118 → 98/107 | 1–0 → 0–0 |
| narrow21 | 123/132 → 95/100 | 0–0 → 1–0 |
| wide21 | 108/115 → 103/111 | 0–0 → 0–0 |
| short42 | 107/119 → 101/112 | 0–0 → 0–1 |
| direct42 | 104/116 → 82/87 | 0–0 → 0–0 |
| weak442-77 | 111/120 → 88/100 | 0–0 → 0–0 |
| strong352-21 | 60/73 → 66/71 | 0–0 → 0–0 |

Bütün örneklemde hedef alımları **781/861 (%90,71) → 717/777 (%92,28)**; toplam pas/tamamlanan pas **864/812 → 779/744**. Daha yüksek örneklem oranı, aynı uçuşlarda nedensel genel iyileşme diye yorumlanmaz: uçuş türleri ve sayıları da değişir. Takımın son dokunuşuyla dışarı giden hedefli top sayısı **5 → 5** kalır. Ortalama en küçük örneklenmiş **yatay** alıcı/top farkı ise **1,9123 → 1,9509 m** ile kötüleşir. Örneğin strong352 ev sahibi yerden hedefli uçuşlarında bu fark yaklaşık **1,052 → 1,588 m**'dir. Press42 skoru 1–0 → 0–0, short42 0–0 → 0–1 olur. Bu olumsuz sonuçlar korunur; gol/şut/galibiyet kotası yoktur.

## Tekrar üretme

```sh
npm run test:stage3
node tools/profile-pass-arrival.cjs --mode matrix --output /tmp/pass-arrival-matrix.json
node tools/profile-pass-arrival.cjs --mode fork --output /tmp/pass-arrival-natural.json
node tools/compare-pass-arrival-controlled.cjs --output /tmp/pass-arrival-controlled.json
```

Taban kaynak gzip'i varsayılandır; `--baseline-file` ile başka açık kaynak verilebilir. Doğal örneğin pahalı öneği için `--save-snapshot /tmp/third-pass.bin` ve sonraki koşuda `--snapshot-file /tmp/third-pass.bin` kullanılabilir. Araç taban hash'ini ve fork saatini doğrular; önbellek raporu yeniden üretmek için zorunlu değildir. Matris `--seconds 30` kısa tanı seçeneği, 300 sn'lik doğrulama yerine geçmez. Test/HTTP sunucu kısıtlı sandbox'ta engellenirse desteklenen izinli yürütme gerekir.

## Kalan kapsam

Ekonomi, SQLite/tarayıcı kayıt biçimi, ödeme/reklam, günlük lig ve oyun varlıkları değiştirilmedi. Özgün eksik data/assets ve eski testler nedeniyle transfer/günlük lig sunucusu ile tarihsel bütün CI testleri hâlâ doğrulanamadı; yeni 60 test bunların tamamının yerini aldığı anlamına gelmez. Kayıt taşıma ve yerel yedek maç çalıştırma adımları README başındadır.

Sıradaki öncelik, alıcının topa koşusunda gerçek hızlanma/dönüş süresini dikkate alan kesişme hesabı ve baskı altında ilk kontrol/son bölge devamıdır. Mevcut kısa komut tahmini sonraki gizli kararları bilmez; başarısız sonuçlar bu nedenle hâlâ mümkündür.

---

# İkinci aşama doğrulaması — destek devamlılığı (5 Kasım 2026)

**Taban:** yayımlanan ilk aşamanın tam motoru, SHA-256 `cb35f481…`. Git HEAD hâlâ ilk yüklemeyi gösterdiğinden ikinci aşama karşılaştırması HEAD'e göre yapılmadı. İlk aşama kaynak paketinden alınan değişmemiş motor `docs/validation/baselines/stage1-football-sim.js.gz` içinde tutulur. Yeni araç `tools/profile-support-continuity.cjs` bu kaynağı ve güncel motoru ayrı CommonJS modüllerine yükler. Her ham raporda motor/taktik/gözlemci hash'leri vardır. Aşağıdaki ilk aşama raporu tarihsel kayıttır.

## Gerçekten geçen kontroller

- `npm run test:stage2`: **38 test geçti** — değişmemiş 18 hazırlık/fizik testi, 1 gerçek HTML/HTTP entegrasyonu ve 19 yeni destek testi. Atlanan veya sıfır testli koşu başarı diye sayılmadı.
- Yeni testler: iki yön, erken sahiplik verilmemesi, top/seed/gerçek konumların plan sırasında korunması, eski plan süresi dolunca yenileme, eski plan olmadan destek, gerçek alım devri, tam takım planında yardımcıların hemen başka göreve çekilmemesi, 1,2 sn'lik korumanın bitmesi, kesme/duran top/hedef değişimi, kalabalık koridorun yeniden değerlendirilmesi, ofsayt/saha sınırları, yeni komutlardan alım hazırlığı, yaklaşan baskıda fiziksel olarak uygun devam ve karşıtları, kontra geri pas sınırı, beklerin geride kal talimatı.
- [Gerçek Chromium kontrolü](docs/validation/support-continuity-browser.json): taktik ekranından maç, 22 oyuncu, 15 saniyeden fazla simülasyon, gerçek destek planları/devirleri, saat ve duraklat/devam. WebGL/prosedürel model ve WebGL kapalı gerçek 2D yollarında betik hatası yoktu. DOM testindeki canvas taklidine ek bağımsız tarayıcı kontrolüdür. Portre/font/yüksek ayrıntılı oyuncu dosyaları hâlâ eksik; gerçek telefon performansı sınanmadı.
- [Maç matrisi](docs/validation/support-continuity-matrix.json): 8 senaryo × 2 motor, her biri 5 dakika. İki ek tam deterministik tekrar bütün metrik/RNG'yi eşleştirdi. Ayrıca iki gözlemcisiz 5 dakikalık koşunun skor/şut/pas/tamamlanan pas/RNG'si gözlemcili sonuçla eşleşti ([kanıt](docs/validation/support-continuity-observer-check.json)).

Üç tohum, farklı rakip planları, 65/82/91 sentetik kadro gücü ve 4-3-3/4-4-2/3-5-2 kullanıldı. Eşlenmiş satırlarda aynı kadro, taktik ve başlangıç RNG durumu vardır. Taktik çiftlerinde yalnız genişlik veya pas talimatı değişir. Doğal yollar ilk farklı karardan sonra ayrışır; satır sonu skor farkı yerel kararın nedensel fayda ölçümü değildir.

## Ölçülen saha davranışı

Aşağıdaki değerler ev sahibi takım içindir. Mesafe, **gerçek alım anındaki gerçek yardımcı konumları** arasındaki ortalamadır; komut noktası veya oyuncuyu taşınmış gibi gösteren değer değildir. “Uygun yardımcı”, alım anındaki normal pas seçeneğinde risk <0,35, alım riski <0,65 ve alan >2,4 m koşullarını sağlayan mevcut destek planı üyesidir. Bu bir başarı garantisi veya tamamlanmış pas sayısı değildir. Sayı, o sürümün gerçek alım sayısına bölünür; toplamlar farklı doğal yollarda farklıdır.

| Senaryo | Yardımcı mesafesi, m (ilk → ikinci aşama) | Alım başına uygun yardımcı (ilk → ikinci) | Skor (ilk → ikinci) |
| --- | --- | --- | --- |
| balanced21 | 25.89 → 18.60 | 0.59 → 1.50 | 2–0 → 0–0 |
| press42 | 20.94 → 16.81 | 0.89 → 1.74 | 0–1 → 1–0 |
| narrow21 | 24.59 → 16.59 | 0.95 → 1.71 | 1–0 → 0–0 |
| wide21 | 27.37 → 17.11 | 0.85 → 1.52 | 1–0 → 0–0 |
| short42 | 24.13 → 16.54 | 0.63 → 1.66 | 0–0 → 0–0 |
| direct42 | 24.32 → 17.29 | 0.68 → 1.58 | 0–0 → 0–0 |
| weak442-77 | 20.45 → 16.07 | 0.83 → 1.88 | 0–1 → 0–0 |
| strong352-21 | 20.63 → 16.46 | 0.58 → 1.74 | 1–0 → 0–0 |

Bütün eşlenmiş maçlar tamamlandı; top/oyuncu sayıları sonlu, skorlar gerçek gol olaylarıyla eşitti. En büyük oyuncu adımı **0.12233 m/60 Hz**; 0,15 m sınırı aşılmadı. Taktik genişliği, savunma çizgisi, pas yönü/mesafesi, pres kazanımı ve top kaybı ham JSON'dadır. Pencere içindeki daha fazla uygun yardımcı, daha iyi skor anlamına gelmedi: örneğin balanced21 ilk aşamada 2–0, yeni sürümde 0–0'dır. Galibiyet/şut/gol hedefi uygulanmadı.

## Aynı doğal durumdan gerçek devam

[Doğal dal raporu](docs/validation/support-continuity-natural-press77.json), **tam ilk aşama motorunun** önde baskı/77 maçını 3652,25 sn'ye kadar çalıştırır. Önceki ilk aşama belgesindeki dal v1.27 önekinden alınmıştı; burada yayımlanan ilk aşama öneki yeniden oynatıldığı için oyuncular ve önceki skor farklıdır. Bu iki örnek aynı durum diye sunulmaz.

3652,25 sn'deki tam oyuncu/Map/top/vuruş/seed nesne grafiği iki motora klonlandı; sonrasındaki 8 saniye normal plan, hareket, temas, müdahale ve RNG ile yürüdü:

- Her iki dalda oyuncu 2 pası 3652,400'de çıkarır, oyuncu 5 topu 3652,883'te alır.
- İlk aşamada alım desteği pasör 2'ye aittir; yardımcı 9 vardır. Oyuncu 5 bekler/taşır; rakip 15, 3654,617'de sahip olur.
- İkinci aşamada alıcı 5'in yardımcıları 3 ve 9'dur. İlk gerçek kararında hazır 3'e fiziksel hazırlığı uygun devam pasını seçer. Gerçek çıkış 3653,650, gerçek alım 3654,750'dir. Bu tamamlanmış ikinci bağlantıdır; yalnız daha iyi görünen hedef noktası değildir.
- **Devam hâlâ kusurludur:** sonraki 3 → 1 pası 3655,533'te çıkar ve auta gider. Sekiz saniye sonunda rakip takımın aut vuruşu vardır. Yeni dalda bu pencerede rakip oyuncunun sahipliği görülmemesi, topun kalıcı olarak korunduğu anlamına gelmez. İki dalın skoru 5–0 kalır; gol kurtarıldığı/üretildiği iddia edilmez.

Ön denemede yalnız uçuş desteğini değiştirmek, bu durumda müdahale kaybını daha erkene çekmişti. Görev devri ve hazır-alt-seçenek kararı birlikte değerlendirilerek bu zayıflık giderildi; müdahale kuralları veya eski testler değiştirilmedi. Son doğal örnekte tamamlanan ilk bağlantı, sonraki aut başarısızlığını gizlemez.

## Kontrollü ve olumsuz karşıt

[Kontrollü rapor](docs/validation/support-continuity-controlled.json): sentetik dördüncü orta saha ve mevcut yuvarlanan top yörüngesiyle, iki motor aynı durumda başlar. İlk alım iki dalda da 10,400 sn'dir. Yeni plan doğrudan alıcıya bağlanır; gerçek top/oyuncu konumu planlama sırasında değişmez. Baskısız bu örnekte sonraki gerçek pas **11,983 → 13,883 sn**'ye gecikir; alım sonrası bekleme **1,583 → 3,483 sn** olur. İki dalda da 8 saniyede rakip sahipliği yoktur. Daha yakın destek, her koşulda daha hızlı pas veya üstün hücum diye sunulmaz.

Baskı yaklaşmayan durumlar yeni devam seçimini zorlamaz; normal taktik sabrı çalışır. Yaklaşan baskı, kapalı hazırlık, hazır olmayan yardımcı, bitmiş koruma süresi ve kontra geri pası için karşıt testler vardır. Destek görev koruması fiziksel dokunulmazlık sağlamaz. Sonraki plan/komut değişiklikleri, temaslar ve yorgunluk tahminleri bozabilir.

## Tekrar üretme

```sh
npm run test:stage2
node tools/profile-support-continuity.cjs --mode matrix --output /tmp/support-matrix.json
node tools/profile-support-continuity.cjs --mode controlled --output /tmp/support-controlled.json
node tools/profile-support-continuity.cjs --mode fork --output /tmp/support-fork.json
```

Varsayılan taban sıkıştırılmış saklı ilk aşama kaynağıdır; `--baseline-file /tam/kaynak.js` ile açık kaynak da verilebilir. `--mode fork` varsayılan 3652,25 sn/önde baskı/77 durumunu yeniden üretir; `--at` ve `--follow-seconds` sınırları araçta denetlenir. Aynı öneği tekrar hesaplamadan tanı için `--save-snapshot /tmp/snapshot.bin`, sonra `--snapshot-file /tmp/snapshot.bin` kullanılabilir; snapshot taban hash'i ve zamanı doğrulanır. Bu yardımcı dosya rapor için zorunlu değildir. Matris için `--seconds 60` kısa tanı seçeneğidir; 300 saniyelik rapor yerine geçmiş sayılmaz.

## Kalan sınırlar

Eski özgün test/data/assets eksikliği sürer: eski CI komutlarının tamamı, transfer/SQLite API'si ve gerçek cihaz uzun maç performansı bu aşamada doğrulanamadı. Korunan 19 ilk-aşama testi tekrar geçti; eksik tarihsel testlerin yerine geçtiği iddia edilmez. Ekonomi, kayıt şeması, gerçek ödeme/reklam ve günlük lig sonuç hesabı değiştirilmedi.

Sıradaki öncelik, tamamlanan pres çıkışından sonraki hareketli alıcıya üçüncü pasın gerçekten ulaşabilirliği ve son bölge devamıdır; yukarıdaki auta giden pas başlangıç örneğidir. Kayıt taşıma ve çalıştırma README başındadır.

---

# İlk aşama doğrulaması — pas hazırlığı (5 Kasım 2026)

Bu bölüm mevcut checkout üzerinde gerçekten çalıştırılan yeni kontrolleri anlatır. Alttaki v1.27 raporu önceki dağıtımın tarihsel belgesidir; oradaki 21 Python/30 Node sonucu bu ortamda yeniden doğrulanmış sayılmaz. Depoda AGENTS.md ve özgün test/araç dizinleri bulunmuyordu; aşağıdaki test ve araçlar bu aşamada eklendi. Eski assertion veya eşik gevşetilmedi.

## Hedefli testler ve oynanabilirlik

`npm run test:stage1`: **18 fizik/karar testi + 1 HTTP/DOM maç entegrasyon testi geçti**. Kontroller iki yönlü güvenli/tehlikeli karşıt durumları, aynı top/oyuncu/seed/komut/gözlem durumunun korunmasını, rakibin gizli komutuna/gelecek plana/RNG'ye erişilmemesini, gerçek koşan/duran temas zamanlarıyla dokuz karşılaştırmayı, 0,75 sn sınırını, tepki/son 0,12 sn kapılarını ve top korurken müdahalenin hâlâ denenebildiğini, daha erken açıkta kalacak bir kontrol yerine riskli son çare pasının açıkça etiketlendiğini ve kontrol için zaman varken riskli alternatifin elendiğini kapsar. Pas sonrası top, alıcı sonradan hareket ettirildiğinde bile aynı serbest BallPhysics yörüngesini izler. HTTP testinde canvas taklittir; piksel/GPU kalitesi kanıtı değildir.

Ayrıca gerçek headless Chromium'da `tactics.html` → maç başlat → 22 oyuncu, 10 saniyeden fazla gerçek simülasyon, pas/olaylar, saat/HUD ve duraklat/devam kontrolleri iki ayrı modda denendi: WebGL/prosedürel oyuncu ve WebGL kapalıyken gerçek 2D çizim. Sayfa betik hatası görülmedi. Model, portre, font ve bazı arayüz varlıkları 404 döndü; bunlar eksik checkout'un görsel sınırlamasıdır. Gerçek telefon ve uzun tarayıcı performansı ölçülmedi.

**Geçmeyen/eski kontroller:** `bash test_all.sh`, Python test keşfinde **0 test** ve `NO TESTS RAN`/çıkış 5 ile durdu. `npm run test:ui`, eksik `tests/tactics-ui.test.cjs` nedeniyle çıkış 1 verdi. `python3 server.py`, eksik `data/transfer-rules.json` nedeniyle başlayamadı. Bunlar yeni motor testinin yerine geçen başarılar değildir. Transfer/SQLite/ekonomi davranışı yeniden doğrulanamadı; ilgili kod/veriler ve ödeme/reklam durumu değiştirilmedi.

## Aynı senaryoda eski/yeni doğal maç matrisi

[Ham ölçümler](docs/validation/pass-preparation-matrix.json): 8 senaryonun her biri eski ve yeni motorla 5 dakika, ayrıca her sürümde bir deterministik tekrar (toplam 18 çalışma). Üç tohum (21/42/77), farklı rakip planları, sentetik kadro gücü 65/82/91 ve 4-3-3/4-4-2/3-5-2 dizilişleri kullanıldı. Aynı satırda oyuncular, talimatlar ve başlangıç RNG durumu eşittir. Taktik çiftlerinde yalnız genişlik veya pas tercihi değiştirilir; farklı satırlardan galibiyet etkisi çıkarılmaz.

| Tek talimat karşılaştırması | Yeni motor ölçümü |
| --- | --- |
| Dar / geniş (21, aynı kadro/rakip) | Gerçek saha genişliği 35,15 / 44,41 m |
| Kısa / dikine pas (42, aynı kadro/rakip) | Çıkış hedeflerine ortalama pas mesafesi 12,99 / 15,58 m |

Genişlik, duran top/gol arası hariç saniyelik örneklerde saha oyuncularının gerçek z aralığıdır. Pas mesafesi, gerçek `release` anındaki top ile çıkış hedefi arasındadır; tamamlanmış pasın katettiği yol veya başarılı pas oranı değildir. Ham JSON pas yönü, destek uzaklığı/sayısı, savunma çizgisi, pres kazanımı, top kaybı ve geçiş örneklerini de tutar.

16 eşlenmiş maç tamamlandı; iki deterministik tekrarın bütün ölçümleri/RNG'si eşleşti. Sonlu oyuncu/top durumu ve gerçek gol olaylarıyla skor eşitliği doğrulandı. En büyük oyuncu adımı yaklaşık **0,12134 m/60 Hz**; 0,15 m sınırı aşılmadı. Bu ölçüm topun vuruş sonrası hızı için bir üst sınır değildir.

Bu kısa matriste skorlar değişmedi. Yeni uygulanabilirlik kontrolü yalnız `weak-442-77` satırında **1 adayda** çalıştı ve onu uygun buldu. Dolayısıyla bu matris yeni süzgecin genel top kaybını azalttığını göstermez; yeni davranışı esas sınayanlar kontrollü örnekler ve aynı durumdan doğal dallardır.

## Doğal durumdan dallanma: güvenli karşı örnek ve olumsuz sonuç

`tools/profile-preparation-fork.cjs`, doğal eski maçta karar öncesi tam nesne grafiğini `structuredClone` ile iki sürüme taşır. Oyuncu/Map/vuruş kimlikleri ve RNG aynıdır; incelemenin top/oyuncu/seed'i değiştirmediği doğrulanır. Sonraki 4 saniye özgün plan, fizik, müdahale ve alımla yürütülür; rastgelelik veya sonuç zorlanmaz.

- [Güvenli doğal örnek](docs/validation/pass-preparation-natural-safe.json): dengeli/21, **1476,833 sn**. Yeni sürüm üç adayın birini çıkış koridoru riski nedeniyle eler, eskiyle aynı güvenli hedef 2'yi seçer. Tahmini/gerçek temas gecikmesi **0,1833 sn**; iki dalda da hedef topu alır, dört saniyede rakip sahipliği yoktur. Bu yeni kurtarılan top değildir.
- [Olumsuz doğal örnek](docs/validation/pass-preparation-natural-press77.json): önde baskı/77, **3652,250 sn**. İki alternatif de uygulanabilir tahmin edilir. Tempo maliyeti eski hedef 0 yerine daha hızlı hazırlanan hedef 3'ü seçtirir: gerçek pas **+0,3333 → +0,1833 sn**. Yeni dal iki pas/orta sonrasında **+2,6333 sn**'de rakip 14'e kaybeder. Eski dalın dört saniyelik penceresinde rakip sahipliği yoktur; son orta hâlâ uçuştadır. Daha erken çıkışın daha iyi devamlılık garanti etmediği açıkça görülür. Dört saniye uzun vadeli üstünlük karşılaştırması değildir.

Önceki belgede geçen **2004,93 sn** anı, özgün eski gözlemci/yapılandırma dosyaları olmadığı için birebir yeniden üretilemedi. Yeni doğal örnekler bağımsızdır; eski hata anının onarıldığı iddia edilmez.

## Kontrollü karşıtlar ve başarısızlık analizi

İlk denemede yalnız pas hazırlığı süzüldü ve uygun olmayan alternatif doğrudan top korumaya döndürüldü. **Bu politika erken/mirrored örnekte daha kötüydü:** eski motor pası çıkarırken yeni geri dönüş 0,1333 sn'de kaybediyordu. Varsayım hatası testin kapsamı genişletilerek açığa çıkarıldı; müdahale devre dışı bırakılmadı, eski testler gevşetilmedi. Bu aşamada yazılan tek “daima korumaya dön” testi, gözlenen hatayı yakalayan kontrol/son çare karşılaştırmasıyla değiştirildi.

Son kod kontrolün fiziksel ilk dokunuşunu ve erişilebilir müdahaleyi de aynı sınırlı ufukta tahmin eder:

| Aynı durumdan örnek | Eski / son kod |
| --- | --- |
| [Önden erken baskı](docs/validation/pass-preparation-controlled-early.json) | Pasın tahmini müdahalesi +0,1167 sn, teması +0,2000 sn. Kontrolün müdahalesi daha erken (+0,0167 sn); son kod alternatifi **riskli son çare** olarak tutar. Gerçek normal adımlarda iki motor da +0,2000 sn'de pası çıkarır; dört saniyede rakip sahipliği yoktur. Temkinli tahminin yanlış pozitif olabildiği korunur. |
| [Ters yön](docs/validation/pass-preparation-controlled-mirrored.json) | Aynı karşıtın ters yönü; yine son çare etiketiyle gerçek pas korunur. |
| [Daha geç baskı](docs/validation/pass-preparation-controlled-late.json) | Aday uygun bulunur; iki dalda gerçek temas +0,2000 sn, dört saniyede rakip sahipliği yoktur. |
| [Dönüşte müdahale](docs/validation/pass-preparation-controlled-control.json) | Koridor açık; eski alternatifin hazırlığı gerçek müdahaleyle +0,1667 sn'de kesilir, beklenen temas +0,2000 sn'dir. Son kod aynı müdahale anını tahmin ederek kontrol/top korumayı seçer. **İki dal da kaybeder:** rakip sahipliği +0,2833 → +0,4000 sn. Bu bir kurtarılan top değildir; yalnız kesilecek hazırlığın elendiğini ve kontrolün de sınırlı kaldığını gösterir. |

Bunlar elle kurulmuş, süregelen koridor tehlikesi taşıyan sentetik durumlardır. Sonraki adımlar normal plan/hareket/dokunuş/müdahaleyle yürür; seed veya müdahale sonucu zorlanmaz. Son örnekte başlangıç pasına baskı kuran ayrı bir savunmacı ve alıcının ofsaytta olmamasını sağlayan kaleci vardır. Sonuç, bütün maçlara genellenmez.

## Tekrar komutları

Taban commit: `695f552e3f529f1b011e20ddc0c34c7dce99dad8`. Araçlar motor, taktik ve gözlemci SHA-256 değerlerini rapora yazar. Varsayılan `HEAD` ileride değişebileceğinden açık taban kullan:

```sh
npm ci
npm run test:stage1
node tools/compare-pass-preparation.cjs --baseline-ref 695f552e3f529f1b011e20ddc0c34c7dce99dad8 --output /tmp/matrix.json
node tools/profile-preparation-fork.cjs --baseline-ref 695f552e3f529f1b011e20ddc0c34c7dce99dad8 --mode safe --output /tmp/safe.json
node tools/profile-preparation-fork.cjs --baseline-ref 695f552e3f529f1b011e20ddc0c34c7dce99dad8 --mode divergent --home press --seed 77 --output /tmp/press77.json
node tools/profile-preparation-fork.cjs --baseline-ref 695f552e3f529f1b011e20ddc0c34c7dce99dad8 --mode controlled --output /tmp/early.json
node tools/profile-preparation-fork.cjs --baseline-ref 695f552e3f529f1b011e20ddc0c34c7dce99dad8 --mode controlled --defender-x -1 --defender-z 1.5 --blocker --output /tmp/control.json
```

Git alt süreç izni yoksa `git show <taban>:football-sim.js > /tmp/baseline-football-sim.js` dosyasını desteklenen yürütmeyle üret; araçlarda `--baseline-ref` yerine `--baseline-file /tmp/baseline-football-sim.js` kullan. Ağ gerekmez. HTTP entegrasyonu yerel soket izni ister.

## Sınırlar ve sonraki aşama

0,75 saniyelik tahmin mevcut arkadaş komutları/gözlenen rakip hareketine dayanır; yeni komutları ve omuz ayrıştırma itmelerini içermez. Müdahale ihtimali risk sayılır, kesin top kazanımı değildir. Gerçek vuruş, yön ve top serbest hareketi aynı kodda kalır. Üç tohum ve kısa maçlar genel gerçekçilik/denge kabulü değildir; gol/şut/galibiyet kotası yoktur.

Sonraki öncelik, pres çıkışı sonrasında alıcının uygulanabilir kontrolü ve ikinci/üçüncü desteğin devamıdır; özellikle yukarıdaki olumsuz doğal dal regresyon örneği olarak tutulmalıdır. Bireysel roller, eksik kadro ve bütün özelliklerin kapsamlı modellenmesi bu aşamada tamamlanmadı. Günlük lig hâlâ ayrı sonuç hesabını kullanır. Kayıt taşıma ve yerel oynatma adımları README başındadır.

---

# v1.27 doğrulama

## Değişiklik ve testler

Yeni alıcı tahmini, seçilen kendi takım arkadaşının bilinen komutunu mevcut Match.move/effort hesabıyla kopyada ilerletir. Çıkış anındaki gövdeden hedef yeniden hesaplanır. Eski hız uzantısı ve aradaki hedef ayrıca okunur; en yüksek risk kullanılır. Mevcut tepki, son 0,12 saniye sınırı, alternatif/kontrol, yeniden karar bütçesi ve fiziksel müdahale sırası korunur. Yöntem ARCHITECTURE.md, EA'nın kamuya açık tasarım referansı FIFA_REFERANSI.md içindedir. EA motoru entegrasyonu veya eşdeğerliği iddia edilmez.

Genel regresyon 21 Python testi ve 30 Node komutuyla geçti. Önceki 37 test/yardımcı dosyasının tamamı byte düzeyinde aynıdır; eski assertion veya eşik değiştirilmedi. Yeni tests/receiver-forecast.test.cjs iki yönde durma, dönüş ve yeniden hızlanma için altı gerçek hareket karşılaştırması yapar; üç durumda tahmini hedefi gerçek vuruş hedefiyle karşılaştırır. Top/oyuncu/seed/gözlem kaydının değişmemesi, gelecekteki planın çağrılmaması ve bilinmeyen komutta hızla ilerleme geri dönüşü sınanır. Gelecek komut sabit tutulduğunda hareket hatası 0,015 m, hız farkı 0,02 m/s, çıkış hedef farkı 0,06 m altında aranır. Bunlar bütün maçlar için hata garantisi değildir.

Kontrollü koridor denemeleri aynı gözlemciyle korunur: rakip koşup geçtiğinde iki yönde ve yardımcı varken/yokken iptal olmadan ilk hedef 1,70 sn'de alır. Rakip koridorda kaldığında açık yardımcı 1,15 sn'de alır; yardımcı yokken kontrol sonrası ilk hedef 2,30 sn'de alır. Normal hareket, dönüş, fizik, vuruş ve alım kullanılır; sonuç veya RNG zorlanmaz. Dört örnek bir doğal maç başarı oranı değildir.

## Aynı durumdan karşılaştırma

Bilinen doğal dengeli/21 hata anı 2004,93 sn'dir. tools/profile-receiver-fork.cjs, özgün v1.26 maçında inceleme öncesi durumu alır. Oyuncu/Map/top/vuruş kimlik ilişkilerini koruyan iki structuredClone, aynı RNG durumuyla iki sürümün incelemesini birer kez çalıştırır. Top, konum, yön ve seed'in inceleme çağrısıyla değişmediği doğrulanır. Sonraki dört saniyede özgün hareket, müdahale, pas ve alım akışı çalışır.

| Ölçüm | v1.26 | v1.27 |
| --- | --- | --- |
| İlk hedef tahmininin özgün pas çıkış hedefine farkı | yaklaşık 1,172 m | bu örnekte 0 m |
| Tahmin edilen koridor riski | yaklaşık 0,515 | nominal 0,920; hız uzantısı 0,634; orta nokta 0,773 |
| Karar | ilk pası sürdür | alternatifi yeniden hazırla |
| Gerçek sonuç | pas çıkar, rakip 4 alır | alternatif pas çıkmadan kesilir; rakip 5 topu alır |

Alıcının mevcut komutu geriye destekken hızı henüz ters yöndedir. Yeni kopya normal ivme/dönüş hesabıyla bu değişimi okur; hedeflerin ayrımı yaklaşık 1,172 m'dir. Yeni nominal hedefin tam eşleşmesi bu sabit komutlu tek durumun sonucudur; geleceğin kusursuz bilindiği anlamına gelmez. Her iki dalda da ilk rakip sahipliği yaklaşık 2005,17 sn'dedir. Bu bir kurtarılmış top değildir; doğru risk değerlendirmesinden sonra yeni hazırlığın uygulanabilirliği hâlâ sorundur. Ham hata, karar, gerçek kayıp ve hareket kayıtları receiver-fork-v127.json içindedir.

## Doğal maçlar

Aynı tools/profile-pass-release.cjs, v1.27 için dengeli/21 ve pres/42 maçlarında 90 dakika çalıştı. v1.26'nın aynı gözlemciyle alınmış mevcut raporları; üç kaynak, gözlemci hash'i ve senaryo anahtarları doğrulanarak tekrar kullanıldı. Eski maçlar yeniden çalıştırılmış gibi sunulmaz. Gözlemcili skor ve şut iki sürümün gözlemcisiz matrisleriyle birebir eşleşir. Özgün eylemler birer kez çağrılır; ek RNG/politika yoktur.

Dengeli/21'in ilk okuması aynı durum karşılaştırmasıyla eşleşir. Yeni sürümde 1 yönlendirme, 0 erteleme vardır; skor 0–1 → 1–1, şut 14–3 → 13–8. Pres/42'de 3 reset, 0 erteleme sürer; skor 3–2, şut 20–4. İki yeni doğal maçın toplam 4 çıkış okumasında 1 kez hedef varsayımları güçlü tehlike eşiğinin farklı taraflarındadır. Bu sayaç kurtarılmış pas sayısı değildir.

Bir karar sonrasında maç yolları ayrışır. Son skor/şut farkı, ilk kararın doğrudan yerel faydası veya genel pas başarısı kanıtı olarak yorumlanmaz. Rakibin sonraki ivmesi, takımın yeni komutu, başka oyuncuların kaçınma hareketi ve geciken temas tahmini bozabilir. Yalnız üç hedef örneği bütün olası koridorları kapsamaz.

## 28 maç kontrolü

15 × 5 dakika (üç tohum/beş plan), 7 × 90 dakika ve 6 × 5 dakika diziliş tamamlandı. Bitiş, 0,15 m/adım, 18 sn sahipsiz top, 8 sn durağan sahiplik ve 60 sn duran top sınırları geçti. Kaynak/rig/taktik hash'leri sabit kaldı.

Yeni paralel doğrulayıcı, eski seri doğrulayıcının measure fonksiyonunu byte düzeyinde aynı tutar ve maçları iki yalıtılmış Node worker'ında çalıştırır. Bir maçın adım veya RNG sırası değiştirilmez. Önceki raporun üç girdisi ve senaryo anahtarları doğrulanır. Yeni doğal gözlemcilerin skor/şut eşleşmesi de bağımsız kontrol sağlar.

| Plan / tohum | v1.26 skor / şut | v1.27 skor / şut |
| --- | --- | --- |
| balanced / 21 | 0–1 / 14–3 | 1–1 / 13–8 |
| balanced / 42 | 5–3 / 14–10 | 5–3 / 14–10 |
| balanced / 77 | 3–0 / 11–5 | 3–0 / 11–5 |
| possession / 42 | 2–1 / 7–10 | 2–1 / 7–10 |
| wide / 42 | 2–3 / 8–10 | 2–3 / 8–10 |
| counter / 42 | 1–1 / 10–13 | 1–1 / 10–13 |
| press / 42 | 3–2 / 20–4 | 3–2 / 20–4 |

Yedi uzun maçın toplam golü 27 → 28 (ortalama 3,86 → 4,00), şutu 139 → 143. Bir skor ortalaması gerçekçilik veya taktik denge kabulü değildir. 5–3 sonucu ve pres örneğinin 20–4 şut dağılımı sürer. Küçük örneklem, sabit rakip ve ayrışan maç yolları nedeniyle genellenemez. Şut/gol kotası eklenmez; top, şut ve kaleci fiziği değiştirilmez.

## Arayüz, video ve paket

DOM ve gerçek yerel HTTP/SQLite transfer akışları geçti: ui-status-v127.json, ui-regression-v127.txt ve transfer-ui-v127.txt. Bunlar gerçek tarayıcı/GPU/telefon performans testi değildir. Eski 37 test dosyası ve 30 oyun varlığı aynıdır. Yedi HTML sayfasında yalnız sürüm altbilgisi değişir. Gerçek futbolcu eklenmez; ödeme/reklam sağlayıcılarının durumu korunur. Günlük lig ayrı sonuç hesabını kullanır; yerel 3D maç onun kaydı değildir.

ALICI_HAREKETI_v127.mp4 doğal dengeli/21 maçının 2001,93–2021,93 saniyeleridir. Yeni hedef/risk okuması, yeniden değerlendirme ve ardından süren gerçek top kaybı korunur. 20 sn, 480 kare, 1024×576, 24 FPS; gerçek sahne/model/rig verisinin yerel EGL çizimidir. İlk tahmin zamanı, nokta ve karar hem aynı durum karşılaştırması hem tam doğal maç gözlemcisiyle eşleşir. Tam ffmpeg çözümü ve dört örnek kare incelemesi yapılır. Video tarayıcı kaydı, FIFA motoru kaydı veya başarılı top koruma kanıtı değildir.

Başlangıç ZIP'inin 551 manifest girdisi ve CRC'si doğrulandı. Dağıtım son iki sürümün videosunu tutar; v1.25 videosu çıkarılır, oyun varlıkları korunur. Yeni ZIP bağımsız açma/CRC ve her dosyanın SHA-256 kontrolüyle doğrulanır. Kaydedilen kopyanın birebir teyidi ZIP dışında teslim kaydında tutulur.

## Sonraki öncelik

Baskı altında güvenli görünen alternatif için gerçekten hazırlık süresi bulunup bulunmadığı; ilk çıkıştan sonraki destek/ikinci top; ani yeni komutlarda tahmin belirsizliği; farklı rakip/kadro ve gerçek cihazda kesintisiz maç kabulü üzerinde çalışılmalıdır.
