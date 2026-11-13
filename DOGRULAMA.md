## Aşama 12 — kural, yaşam döngüsü ve kurulum doğrulaması

**Son doğrulama: 435/435 test geçti** (413 JS + 22 Python), hata/atlanan yok. Gerçek Chromium WebGL ve 2D yollarında 16’şar kontrol geçti. Bir normal 300 saniyelik nominal senaryo, gözlemcili/gözlemcisiz/tekrar olarak üç kez aynı tam durumu üretti; 164 + 150 saniyelik devreler ve 8 saniyelik ara ile 322 saniyede tamamlandı. Bu senaryoda bir penaltı kararı ve bir gol gözlendi; tek örnekten denge veya özellik sıklığı sonucu çıkarılmıyor.

`npm run test:stage12`, önceki aşamaları, `match-rules`, `referee-laws`, `pitch-laws`, gerçek motor bütünleştirmesini ve yerel başlatıcı HTTP testlerini içerir. Kanıtlar `docs/validation/match-laws-{tests,browser,coverage,natural}.json` dosyalarındadır. Eski aşama 10/11 raporları yeni motorun kanıtı olarak yeniden etiketlenmez.

- Kontrollü sınırlar: ceza sahası çizgisi/içi/dışı ve iki yön, avantaj geri dönüşü, ertelenen sarı, doğrudan kırmızı/asgari oyuncu, gerçek penaltı ayak çıkışı, son anda penaltı, bütün-top çıkışı, hızlı direk/üst direk ve gol öncesi blok, devre arası donması ve ters santra, kafa pası ofsaytı, rakip kontrolü/sekme ayrımı, değişiklik sayısı/penceresi.
- Chromium: gerçek `start.py` sunucusu üzerinden WebGL/prosedürel ve 2D; mola paneli, duran fizik ve saat, saha değişimi, gerçek değişiklik, son düdük, ek süre ilanı, 390 px ve hata kontrolü. Kısa yapılandırılmış devreler bu kontrollere hız kazandırır; doğal maç örneklemi sayılmaz.
- Normal beş dakikalık nominal maç: gözlemcili, gözlemcisiz ve gözlemcili tekrarın tam seri durum eşitliği, sonlu fizik, saat bölümleri ve tamamlanma doğrulanır. Tek doğal senaryonun üç çalıştırılmasıdır; üç bağımsız doğal maç sayılmaz.
- Başlatıcı: gerçek HTTP'de sayfalar/modüller, yerel sağlık yanıtı, kapalı API açıklaması, özel dosya engeli ve eksik tam-mod verisi için açıklayıcı çıkış. Windows betiği bu Linux ortamında yerel olarak çalıştırılmadı. Tam ekonomi sunucusunun gerçek katalogla uçtan uca çalıştığı iddia edilmez; veri dosyaları bu kopyada bulunmuyor.

Tekrar komutları:

```sh
npm ci
npm run test:stage12
python3 tools/check-match-laws-browser.py
node tools/check-attacking-coverage.cjs
node tools/profile-match-laws.cjs
```

Tarayıcı kontrolü ayrıca Playwright ve Chromium gerektirir. 21 seçilmiş hava oyunu/kaleci durumu doğal frekanslara katılmaz. Merkezlenmiş vücut-blok vuruşunun sabit 0,5 RNG istisnası raporda korunur. Tarihî fizik karşılaştırmaları yalnız yeni devre saatini fizik karşılaştırmasından çıkarır; hareket/top eşitliği ve sınırlar korunur. Eski yapay alıcı örnekleri yeni ofsayt yasasına uygun çıkış konumları kullanır; süre sınırı örnekleri nominal `duration` alanını değiştirmek yerine ikinci devre saatini kurar.

[Uygulama sözleşmesi ve model sınırları](docs/MATCH_RULES.md) · [Kurulum](KURULUM.md).

---

# On birinci aşama — oyuncu kimliği ve kadro sözleşmesi

**361/361 test geçti:** 343 JavaScript + 12 Python oyuncu modeli + 6 gerçek HTTP API testi; hata, atlanan veya iptal edilen test yok. Test kaynağı ve günlük SHA kayıtları [player-identity-tests.json](docs/validation/player-identity-tests.json) içindedir. Gerçek Chromium'da WebGL/prosedürel ve zorunlu 2D yollarında 16'şar kontrol, son kaynak eşliğiyle geçti; [tarayıcı raporu](docs/validation/player-identity-browser.json) bunu saklar.

Tekrar komutu: `npm run test:stage11`. Paket; önceki fizik, algı/görev ve hücum tanılama kontrollerini, ortak oyuncu modeli testlerini, gerçek maç davranışı karşılaştırmalarını, başlangıç akışını ve Python veri/API testlerini çalıştırır. Yeni kabul, farklı alanların var olmasına değil sahadaki etkisine dayanır: eşit genel puanda gerçek koşu mesafesi, aynı çıkış durumundan pas hatası, aynı erişim ve rastgele sayı altında mücadele, aynı uçuşta iki elli kaleci tutuşu karşılaştırılır.

- `tests/player-model.test.cjs`: tarayıcı/JSON eşliği, bütün genel mevki çiftleri, form/kondisyonun ayrı etkileri, eksik veri ve ayak kaynağı, altı diziliş.
- `tests/player-identity-integration.test.cjs`: iki kadro ve yedek aynı slot hesabı, ham girdilerin korunması, koşu/ivme/dönüş, yorgunluğun bir kez uygulanması, dayanıklılık, erişim kapısını aşamayan güç, iki ayak ve kaleci tutuşu.
- `tests/test_player_model.py`: katalog → transfer → SQLite kimliği, alan sınırları, eksik/eski kayıt, antrenman başlangıcı ve JS/Python kalite/varsayılan profil eşliği.
- `tests/fixture-roster.test.cjs` ve `tests/fixture-roster-api.py`: normal taktik → gerçek maç HTML akışı, fikstür rakibi, deplasman etiketi, başlangıç görüntüsünün korunması, geç gelen eski sürüm, profil/lig oturumu değişiminde eski başlangıcın yenilenmesi, eksik rakip ve gerçek HTTP yetkilendirme/futbol alanı izdüşümü.

Eski fizik regresyonları, eski profil varsayımlarının yeni oyuncu modeline taşınmaması için gerekli durumlarda açık nötr fizik özellikleriyle kurulmuştur. Gövde/ayak erişimi ve kesin karşılaştırma koşulları korunur; sıkıştırılmış tarihsel motorlar değiştirilmez. Kontrollü blok örneği merkezlenmiş vuruşla temas yolunu sınar. Kaleci karşılaştırmaları artık genel puanın yanında bağımsız reaksiyon/tutuş değerlerini de açıkça sabitler. Güncel 21 seçilmiş durumun raporu [player-identity-coverage.json](docs/validation/player-identity-coverage.json) içindedir; eski `attacking-coverage.json` tarihsel kanıt olarak korunur. Bunlar doğal maç başarı oranı değildir.

Ayrı kapsam araçları yeniden çalıştırılabilir:

```sh
node tools/check-attacking-coverage.cjs
python3 tools/check-player-identity-browser.py
node tools/profile-player-identity.cjs --seconds 300
```

Tarayıcı aracı Playwright ve Chromium gerektirir. Üretim kataloğu bulunmadığında API testleri geçici SQLite kaydıyla gerçek HTTP yolunu sınar; bu testin geçmesi eksik özgün katalog dosyalarının geri geldiği anlamına gelmez.

Sekiz senaryo iki motorda 300'er saniye yürütüldü. Her motor/senaryo için gözlemcili, gözlemcisiz ve deterministik tekrar birlikte **48 çalıştırma** eder; bunlar 48 bağımsız doğal senaryo değildir. Bütün çiftlerde tam maç durumu, RNG, süre/olay tutarlılığı, sonlu sayılar ve rapor sorgularının salt okunur oluşu doğrulandı. [Doğal rapor](docs/validation/player-identity-natural.json) her senaryoyu, kaynak özetlerini ve karşılaştırma sınırlarını içerir.

| İki takım toplamı, 8 × 300 sn | Önceki b29 motoru | Ortak oyuncu modeli |
| --- | ---: | ---: |
| Gözlenen süre (sn) | 2.400 | 2.400 |
| Top oyunda (sn) | 1.951,367 | 1.889,733 |
| Fiziksel şut | 6 | 3 |
| 10 dakika top oyunda başına şut | 1,845 | 0,953 |
| Tamamlanan / çıkan pas | 722 / 783 | 705 / 754 |
| Top kaybı | 138 | 108 |
| İptal edilen vuruş hazırlığı | 6 | 4 |
| Gözlenen hücum bölümü | 171 | 145 |

Top kaybı ve hazırlık iptali azalırken şut üretimi de azaldı. Bu, genel futbol kalitesinin veya hücum dengesinin iyileştiği kanıtı değildir; daha uzun ve çeşitli kadro/taktik örneklerinde hücum zinciri incelemesi sürmelidir.

Tarayıcı ve doğal maç kabul kayıtları bu aşamanın kendi kaynak özetleriyle `docs/validation/player-identity-browser.json` ve `docs/validation/player-identity-natural.json` altında tutulur. Doğal karşılaştırmada iki sürüme aynı güncel ham kadro girdileri verilir; eski motor rakip kadroyu kullanmadığından bu, yalnız tek bir özelliğin nedensel deneyi değildir. `weak442-77` ve `strong352-21` senaryo adları sırasıyla genel puan 65 ile 4-4-2 ve genel puan 91 ile 3-5-2 girdileridir; atanmış alt özellikler korunur. Bu adlar bütün fizik/teknik özelliklerin birlikte zayıflatıldığı veya güçlendirildiği anlamına gelmez. Şut/top kaybı farkları genel futbol kalitesi kazanımı diye sunulmaz. Dokuzuncu aşamanın denge kabulü ve özgün veri/asset eksikleri açık kalır. Aşağıdaki sayılar önceki aşamalara aittir.

---

# Onuncu aşama — hücum aşamaları, süre paydaları ve kapsam

Bu tanılama **`codex/team-continuity-perception` inceleme dalı** içindir. Motorun karar/fizik davranışı bu aşamada değiştirilmedi; dokuzuncu aşamanın denge kabulü açık kalır. Gözlenen motor `b29a8f9b49638ec6559bc58df6b9504400eaaaf3b44bd14439d4643c3bd394f3`, gözlemci `259e977fe017dd5e38f04ce0abbce765db0a689c58ec17d1709cb6b56c3db237` olur. Yayımlanmış sekizinci aşama `e16642b5…` aynı ölçüm tanımlarıyla ayrı karşılaştırma motorudur. Farklı kaynak ve konfigürasyonlardaki önceki şut toplamları bu deneyle tek örneklem gibi birleştirilmez.

## Test ve motorun korunması

`npm run test:stage10`: **309 geçti, 0 hata, 0 atlanan**. [Test raporu](docs/validation/attack-chain-tests.json), kaynak özetlerini ve motorun yayımlanmış dokuzuncu aşamayla byte düzeyinde aynı olduğunu kaydeder.

| Test grubu | Geçen kontrol |
| --- | ---: |
| Önceki dokuz aşamanın regresyonları | 245 |
| Gözlemci, olay/süre/payda ve kayıt yaşamı | 19 |
| Bağımsız gerçek maç entegrasyonu | 15 |
| Analiz paneli ve dışa aktarma | 7 |
| Kontrollü hava oyunu/kaleci kapsamı | 23 |

Gerçek maçta tam durum/RNG eşitliği, gözlem kancaları kaldırıldıktan sonra descriptor eşitliği, hazırlık önizlemelerine sızmama ve ek AI sorgusu olmaması sınanır. Aynı karedeki gerçek çıkış/alımın korunması, hazırlık ile fiziksel şutun ayrılması, yeni kontrol onayı, iki yönde gerçek hat/bölge geçişi, boş payda, pending/censored kayıtları ve aynı karede son aşamanın geriye düşmemesi ayrıca kapsanır. Kontrol edilmeden planlanan uzak hedef ilerleme kazanamaz. Gözlemci raporunu okumak aktif hücumu bitirmez veya maç durumunu değiştirmez.

## Tanımlar ve yorum sınırı

Süre, gerçek maç saati farkıdır; simülasyon hız düğmesi veya duvar saati payda değildir. Açık oyun vuruş hazırlığı ve kaleci elde topu bekletmesi oyunda; yerleştirilmiş duran top hazırlığı ve gol arası dışarıdadır. Kare başındaki sınıf kullanıldığı için olay sınırında en fazla bir adım sınıflandırma belirsizliği vardır. Kontrollü top/uçuş/boş top süreleri oyunda kalma süresini; duran top/gol arası süreleri oyun dışını böler. Örneklenmemiş uzun manuel aralıklar ayrıca tutulur.

Kazanım teması ile onaylanmış kontrol ayrılır. Olağan onay, top 1,45 m içinde ve 0,65 m altında (veya ellerde) en az 0,15 sn kalınca; gerçek çıkış/temas ise kendi olayıyla oluşur. Başlangıçta 4 m'den yakın rakip varsa baskıdan çıkış değerlendirilebilir: kontrollü top ve en yakın rakibe en az 5 m mesafe 0,50 sn sürmelidir. Baskısız başlangıç başarı sayılmaz. Hat kırma, en az iki öndeki rakibin dondurulmuş ve güncel konumunu gerçek kontrolle geçmeye dayanan operasyonel geometrik yaklaşımdır; tam formasyon tanıma değildir.

Son bölge takım yönünde x≥52/3 m, ceza sahası x≥35,5 m ve |z|≤20,16 m olur. Planlanan pas/koşu noktası veya yalnız havada geçen top bölgeye ulaşma sayılmaz. Başlangıçta zaten ileri olanlar `at-start/startedBeyond` ile ayrılır; panelde ilerleme payı `eligibleReached/stageEligibility` olur. Marjinal aşama kayıtları sıralı huni değildir. Profil, onaylı gerçek kazanımları başlangıç baskısı/uygun rakip hattına göre dört ayrı sıralı yolda inceler; gerekmeyen aşamayı gerçekleşmiş saymaz.

Bitiş aşaması gözlenen en ileri aşamadır. Gerçek bitiş olayı ile destek, bekleme, pas hazırlığı ve ceza sahası koşusu kanıtları ayrı tutulur. Destek hedefine 3 m yakınlık uygulanabilir/açık pas kanıtı değildir. Eski bir mücadele veya iptal izi daha sonraki gerçek pas kesilmesini yanlış neden olarak örtemez. Şut çıkışı hücum bölümünü bitirir; gol/kurtarış/blok/dışarı sonucu ayrı şut kaydında çözülür. Pas/own-goal olayı fiziksel şut üretmez.

`pending` hücum sürüyor, `censored` ölçüm/maç sınırında devamı gözlenemedi demektir; bunlar taktik başarısızlık tablosuna eklenmez. Paydası sıfır oran `null`/`—` olur. Aşama oranları gözlem penceresindeki ilerlemeyi anlatır; bekleyen hücumların nihai başarı oranı değildir. Ayrıntı sınırları açık kaydedilir; toplamlar korunur.

## Gerçek tarayıcı kontrolü

[Chromium raporu](docs/validation/attack-chain-browser.json), son `259e977f…` gözlemci kaynağında WebGL/prosedürel ve zorlanmış 2D yollarını doğrular. İki modda da 22 oyuncu, normal maç ilerlemesi ve **17 kontrol** geçti: doğru aşama payı, ileri başlangıç ayrımı, süre toplamları, gerçek pas/şut eşleşmesi, özet/rapor uyumu, panel/rapor okumalarının tam maç durumunu koruması, duraklatma, açık kullanıcı isteğiyle JSON indirme, dar görünümde indirme/yatay taşma, devam ve yeniden başlatmada temiz sayaçlar. JavaScript hatası yoktur. Eksik özgün varlık/font kaynakları raporda ayrıca listelenir; bu test eksik ayrıntılı modelin cihaz kalite kabulü değildir.

Yeniden üretme: `python3 tools/check-attack-chain-browser.py`. Chromium ve Python Playwright gerekir. Analiz paneli sayısal kayıtları gösterir; kullanıcı tıklamadan JSON indirme başlatmaz.

## Doğal karşılaştırmanın yöntemi

`tools/profile-attack-chain.cjs` aynı sekiz sentetik konfigürasyonu, yayımlanmış sekizinci aşama ile değişmeyen dokuzuncu aşama motorunda 300 sn yürüttü. Gerçek çağrı gözlemcisi ek karar/plan sorgulamaz. Her gözlemcili koşu bağımsız gözlemcisiz koşuyla ve deterministik tekrar ile tam durum olarak karşılaştırılır; orijinal yöntem/descriptor sözleşmesi geri yüklenir. Kaynak özetleri uyuşmayan koşular birleştirilmez.

Onaylı kazanım kökenlerinin sıralı yolu ile bütün kökenlerin marjinal aşama kayıtları ayrıdır. İleride başlayan kazanımlar, baskısız veya hattı uygun olmayan başlangıçlar ayrıca belirtilir. Geçiş paydaları gerçekleşen, sonraki aşamaya geçmeden biten, sırası uyumsuz ilk kilometre taşı olan, süren ve sınırda kesilen kayıtları ayırır. Bunlar karşı-olgusal neden veya bütün futbolda geçerli denge hedefi değildir.

## Sekiz kısa maçta görülen zincir

[Okunabilir özet](docs/validation/attack-chain-summary.json) ve [tam hücum/şut izleri — JSON.gz](docs/validation/attack-chain-matrix.json.gz), aynı sekiz konfigürasyonu iki motor için korur. **16 gözlemcili maçın tümü** bağımsız gözlemcisiz koşusuyla ve gözlemcili deterministik tekrarıyla tam durum/RNG olarak eşittir; yöntem/descriptor geri yükleme kontrolleri de geçti. Tekrarlanan doğrulama koşuları yeni bağımsız örnek diye sayılmaz. Her motorun asıl ölçüm penceresi 8 × 300 = **2400 sn** olur.

| İki takımın toplamı; motor başına sekiz maç | Yayımlanmış aşama 8 (`e166…`) | İnceleme motoru (`b29…`) |
| --- | ---: | ---: |
| Ölçülen maç süresi (sn) | 2400 | 2400 |
| Top oyunda (sn) | 2026,03 | 1969,70 |
| Duran top / gol arası (sn) | 373,97 | 430,30 |
| Kontrollü top (sn) | 1103,38 | 1100,18 |
| Uçuş (sn) | 789,32 | 620,67 |
| Boş top (sn) | 133,33 | 248,85 |
| Gözlenen hücum | 89 | 169 |
| Biten / sınırda kesilen / süren hücum | 82 / 7 / 0 | 162 / 7 / 0 |
| Gerçek şut çıkışı | 4 | 4 |
| Şut / 10 dakika top oyunda | 1,185 | 1,218 |
| Şut / gözlenen hücum | %4,49 | %2,37 |
| Tamamlanan / çıkan pas | 905 / 935 | 677 / 730 |
| Kazanım teması / kontrolü onaylanan | 60 / 53 | 137 / 120 |

İki motorda da dört şut vardır; süre paydasıyla iki takım toplam şut yoğunluğu yaklaşık **1,185 → 1,218 / 10 dakika top oyunda** olur. Buna karşılık hücum sayısı 89 → 169 olduğundan şut/gözlenen hücum %4,49 → %2,37 olur. Bu bir tanılama sonucudur; onuncu aşama motoru değiştirmedi. Bir şut sayısını veya tek oranı futbol dengesi hükmüne çevirmek uygun değildir. Her motorda yedi hücum maç sınırında kesilmiş, örneklenmemiş süre sıfır kalmıştır.

### Sıralı kazanım yolu ve asıl inceleme noktası

Aşağıdaki kohort yalnız **kontrolü onaylanmış, başlangıçta son bölgede olmayan, başlangıç baskısı ve uygun rakip hattı bulunan gerçek kazanımlardır**. Diğer kökenler ve gerekmeyen düğümleri atlayan üç ayrı kazanım yolu tam özette korunur.

| Sıralı ilk kayıt | Aşama 8 | İnceleme motoru |
| --- | ---: | ---: |
| Onaylı kazanım | 43 | 100 |
| Ardından baskıdan çıkış | 26 | 70 |
| Ardından hat kırma | 11 | 29 |
| Ardından son bölge | 1 | 3 |
| Ardından ceza sahası | 0 | 1 |
| Ardından şut | 0 | 1 |

İnceleme motorunda **hat kırma → son bölge** geçişine giren 29 hücumun üçü sıradaki ilk kayda ulaştı. Kalanların **21'i bu kayıt olmadan bitti**, dördünün ilk bölge/hat kayıt sırası bu dar yol ile uyumsuzdu, biri maç sınırında kesildi. Dolayısıyla 26 kesin kayıp yazılmaz. Biten 21 örnekte altı mücadele sonrası kayıp, altı pasın rakibe geçmesi, üç diğer rakip kontrolü ve **altı kazanılmış faul** vardır: 15 top kaybı ile takımda duran topla devam eden altı bölüm ayrıdır. Bu kohort hat kırma sonrasındaki bağlantıyı incelemeyi önceliklendirir; bütün hücumların tek nedeni olduğu sonucunu vermez.

Bu 21 hücumun tüm aşamalarında 81 bekleme kararı ve 34,42 sn bekleme; 0,38 sn destek görevi yokluğu, 18,92 sn hedefine uzak destek ve 237,42 sn hedefine yakın destek kaydedildi. Süreler yalnız hat kırma sonrası aralığa ait değildir. Yakın destek güvenli/uygulanabilir pas demek olmadığından bu sayılar gereksiz beklemeyi veya kötü pas tercihini kanıtlamaz; ilgili karar/temas izlerine dönmek için işaret sağlar.

### Biten bölümün en ileri aşaması ve saha kanıtları

Bu tablo bütün kökenleri içerir; başlangıç konumu, kazanılan faul veya şutla bitiş de bölüm sonudur. Sansürlü kayıtlar tabloya alınmaz. Bütün bitişleri top kaybı saymak yanlış olur.

| Bitişteki en ileri aşama | Aşama 8 | İnceleme motoru |
| --- | ---: | ---: |
| İlk ilerleme kaydı öncesi | 19 | 35 |
| Kazanım | 20 | 32 |
| Baskıdan çıkış | 9 | 31 |
| Hat kırma | 12 | 33 |
| Son bölge | 11 | 23 |
| Ceza sahası | 7 | 4 |
| Şut çıkışı | 4 | 4 |

İnceleme motorunda bütün bölümlerin terminal olayları 74 mücadele sonrası kayıp, 40 pasın rakibe geçmesi, 22 diğer rakip kontrolü, 19 kazanılan faul, iki rakibe aut, bir hazırlık iptali sonrası kayıp ve dört şut çıkışıdır. Hat kırma en ileri aşamasında biten 33 bölümde 12 mücadele sonrası kayıp, sekiz pas kesilmesi, altı diğer rakip kontrolü ve yedi kazanılan faul bulunur. İlk ilerleme kaydı öncesindeki 35 bitiş de erken kontrol/bağlantı incelemesini gerekli kılar.

| Açıklayıcı kayıt; tek başına neden değildir | Aşama 8 | İnceleme motoru |
| --- | ---: | ---: |
| Bekleme kararı / bekleme süresi (sn) | 235 / 106,45 | 303 / 131,03 |
| Destek görevi yok / hedefine uzak / hedefine yakın (sn) | 1,12 / 67,35 / 1034,92 | 2,90 / 92,22 / 1005,07 |
| Gerçek pas hazırlığı iptali | 4 | 5 |
| Atanmış hücum koşusu görevi / ceza sahasında görülen görevli | 180 / 16 | 286 / 6 |

Son satırın ham alanları `boxRunnerCommands` ve `boxRunnerArrivals` adını korur. Bunlar `box-run`/`cutback-support` yanında `channel-run`/`penetration` görevlerini de kapsar; hedefin ceza sahası içinde olması gerekmez. Görülme sayısı, bu göreve atanmış oyuncunun ceza sahasında en az bir kez gözlenmesidir; önceden orada bulunan oyuncu da dahildir. **Gerçek yeni ceza sahası girişi veya yalnız kutuya yöneltilmiş koşu emri değildir; 6/286 bir varış başarı oranı olarak kullanılamaz.**

### Doğal hava oyunu ve kaleci örneklerinin sınırı

Aşama 8'de beş orta çıkışı/dört kafa teması, bir kafa şutu, üç kafayla pas ve bir başarılı geriye çıkarma görülür. İnceleme motorunda iki orta çıkışı/iki kafa teması, sıfır kafa şutu, bir kafayla pas ve sıfır geriye çıkarma vardır. İki motorda da gerçek ofsayt olayı yoktur; aşama 8'de bir uçuşta bayraklı oyuncu bulunmuş fakat o oyuncuyla bayraklı temas gerçekleşmemiştir. Kalecinin işlediği fırsat anahtarı 5 → 6, hazırlık 3 → 3; iki motorda da tutuş ve çelme sıfırdır. Bunlar tüm olası kaleci fırsatlarının veya genel kaleci kalitesinin paydaları değildir.

Kayıtlar hava/kaleci yollarının az örneklendiğini gösterir; bozukluk hükmü vermez. Aşama 8'deki iki golün biri fiziksel şutla, biri şut olmayan gol olayıyla ilişkilidir; bunları şut/gol dönüşümünde birleştirmemek gerekir. Kontrollü kapsam aşağıda ayrı tutulur.

### Arşiv ve yeniden üretme

Tam JSON arşivi **6.728.052 byte** açılmış içerik ve **447.838 byte** gzip dosyasıdır; hiçbir hücum/şut izi çıkarılmamıştır. Ham SHA-256 `853c73c9c0bc5e2c689d810c2556ff07bb4a9e8bb48c69a4c9a739e4c1b409f6`, gzip SHA-256 `d6e5f8b2a15b9d45145e6eafee5d3519b2cc48cd9d9a92e8abcac05d82ce1003` olur. [Okunabilir özet](docs/validation/attack-chain-summary.json) her senaryonun normalize sayılarını, kaynakları ve bütün tekrar doğrulamalarını saklar. Rapor üretim saati maç süresi değildir.

```sh
node tools/profile-attack-chain.cjs --seconds 300 --engine both --output work/stage10/attack-chain-matrix.raw.json
node tools/check-attacking-coverage.cjs
python3 tools/check-attack-chain-browser.py
```

Yeni örneklem önceliği, kontrol onayından önceki erken bitişleri ve baskıdan çıkış/hat kırma sonrası gerçek pas bağlantısını aynı pozisyon izinden incelemektir. Destek hedefi yakınlığı, oyuncunun gördüğü baskı ve vuruşun fiziksel uygulanabilirliği birlikte değerlendirilmelidir. Ceza sahasına yeni giriş, orada önceden bulunmadan ayrılmalı; hava/kaleci kalitesi daha çeşitli doğal uçuşlarla ve eşleştirilmiş kontrollü örneklerle ölçülmelidir. Tanılama bu incelemeyi görünür kılar; bu aşamada davranış iyileştirmesi yapıldığı iddia edilmez.

## Kontrollü hava oyunu ve kaleci kapsamı

[attacking-coverage.json](docs/validation/attacking-coverage.json), **21 seçilmiş durumu** doğal maçlardan ayrı tutar. Beş gerçek orta çıkışında dört uygun kafa teması: iki kafa şutu, bir kafayla pas, bir savunma uzaklaştırması; bir örnekte uygun kafa teması yoktur. Dört geriye çıkarma örneği takım alımı, rakip alımı ve sert kontrolde boşa top yollarını kapsar. Gerçek şut bloğu ve ofsayt/onside teması ayrı doğrulanır.

Dokuz kaleci tehdit uçuşunun sekizi rakip şutu, biri geri pastır; dört tutuş, iki çelme, bir ayak kontrolü ve iki temas öncesi gol görülür. GK 60/94 eşleştirmesi aynı 30 m/sn top ve gerçek iki el riginde yalnız nitelik farkını sınar. Bütün seçilmiş durumlar tam Match/RNG tekrar eşitliğiyle doğrulandı. Alan uçuşları gerçek hazırlık/çıkıştan sonra sabit gövdeli top adımlarını; kaleci örnekleri normal `Match.step` görüş/tepki/el yollarını kullanır. Oyuncu uçuş sırasında taşınmaz, sonuç veya RNG zorlanmaz.

`node tools/check-attacking-coverage.cjs` kapsam raporunu yeniden üretir. Bu seçilmiş örneklerin tutuş/kafa oranları doğal frekans veya genel kalite oranı değildir. Doğal rapordaki sıfır fırsat da özelliğin eksik/bozuk olduğu hükmü vermez.

---

# Dokuzuncu aşama — görev devamlılığı ve oyuncu algısı

Bu uygulama **`codex/team-continuity-perception` inceleme dalı** içindir. İşlev/regresyon kontrolleri geçti; aşağıdaki doğal maç sonuçları nedeniyle maç dengesi `main` için kabul edilmedi.

Doğrulanan motor SHA-256: `b29a8f9b49638ec6559bc58df6b9504400eaaaf3b44bd14439d4643c3bd394f3`. Karşılaştırma tabanı `docs/validation/baselines/stage8-football-sim.js.gz` içindeki `e16642b50e1d0b7d31cdc375dea7a83af85cf3da194a28362b65007f8420ad2e` kaynağıdır; GitHub'da [68d0ea7](https://github.com/tolgagitmez/tribunmenager/commit/68d0ea748b8ad15d26f22be920a12836fae4ada9) ile yayımlanmıştır. Yerel eski `695f552` Git HEAD'i bu deneyin tabanı değildir. Önceki aşamalar ve raporları aşağıda tarihsel kayıttır.

## Uygulanan davranış

Dört takım evresi ve takımın hücum dönemi, ortak görev yaşamının bağlamıdır. Olağan yeni görev minimum devam/aday doğrulamasını bekler; güvenlik, acil temas, görev sonu ve takım devri ayrı gerekçelerle geçebilir. Desteğe geç varışta açılan bağlantı 0,45 sn kısa kullanım penceresi kazanır; kesin ömür ve güvenlik geçerlidir. Aynı takım alımı diğer görevleri sıfırlamaz. Hazırlanan pasın alıcısı önceden ayrılır; sahiplik gerçek temasla kazanılır. Son görev, pas/koşu plan tablolarına geri yazılır.

Saha oyuncusunun rakip okuması görüş, baş taraması ve kısa belleğe dayanır. Görünmeyen rakibin yeni yeri/hızı sorgudan öğrenilmez. Kopyadaki hazırlık hesabı yeni gözlem veya RNG üretemez. Bireysel markaj kendi gözlemiyle seçilir; takım koordinatörü anlık ortak gözlem birleşimini kullanır. Pres biriminin pas bağlantısı hesabı gözlenen top sahibini, o görülmüyorsa topun ortak konumunu kullanır. Markaj devri, rakibin özel alıcı kimliği yerine topun 0,70 saniyelik görünen koridorunu sınar. Bu, tüm iletişim/dikkat veya görüş engellenmesi modelinin tamamlandığı anlamına gelmez. Topun ortak durumu ve kendi takımının pozisyon/komut bilgisi ayrıca görüşe bağlanmadı; yeni algı kısıtı rakip okumalarına uygulanır.

## Geçen testler ve fizik koruması

`npm run test:stage9`: **245 geçti, 0 hata, 0 atlanan**. Sayı ve kaynak özetleri [team-continuity-tests.json](docs/validation/team-continuity-tests.json) içindedir.

| Test grubu | Kontrol |
| --- | ---: |
| Önceki aşamaların regresyonları | 154 |
| Görüş, tarama, bellek ve kimlik yaşamı | 19 |
| Ortak görev protokolü | 33 |
| Algı/görev motor entegrasyonu | 15 |
| Plan uzlaştırması, markaj/pres devri ve gizli hedefe erişmeme | 18 |
| Baş çizimi ve gövde/temas saflığı | 6 |

Gizli rakip konum/hız getter'ları hata verecek biçimde kurulur; karar/pas hazırlığının bunları okumaması sınanır. Rakip görünmeden yeni yerine tepki verilmemesi, unutulan kayda canlı konumla dönülmemesi ve aynı takım pasında görev döneminin sürmesi ayrıca kontrol edilir. Aktif verkaçın ceza sahası dağılımıyla ezilmesi, geç varan desteğin erken kesilmesi, aynı görevin yanlış temposu, iki presçi/markajcı oluşması ve uygulanmayan koşu noktasının pasçıya sunulması regresyon kapsamındadır. Pres bağlantısı seçiminde görünmeyen top sahibinin canlı koordinatına erişmeme ve yeni gözlemin seçimi değiştirebilmesi sınanır. Markaj devrinde gizli pas alıcısı kimliği yerine yalnız görünen top koridorunun etkili olması da ayrıca sınanır. Görülmeyen rakibin gerçek fiziksel müdahalesi çalışmaya devam eder.

Önceki testlerdeki üç dosya yeni karar metadatasını fizik karşılaştırmasından ayırır: `first-control.test.cjs` evre metadatasını; `touch-feasibility.test.cjs` algı/görev/evre metadatasını ayırır. `post-receive-hold.test.cjs` canlı kare örneğinde arkadaki presçiyi önceden görülmüş bellekte kurar ve yeni yardımcı metadatayı ayırır. Fizik, saatler, top ve RNG eşitliği korunur. Görülmeyen presçiye karşı aynı düzeltmenin tetiklenmemesi yeni entegrasyon testindedir.

`node tools/check-team-continuity-physics.cjs`, **BallPhysics ve 16 canlı fizik/kural yönteminin** tabanla kaynak düzeyinde aynı olduğunu doğruladı: hareket/efor, ayak temas kapıları, mücadele, top entegrasyonu, pas çıkışı, vuruş karesi, kaleci ve ofsayt dahil. Tam liste ve özetler [team-continuity-physics.json](docs/validation/team-continuity-physics.json) içindedir. Görev/algı ve hazırlık önizlemeleri bilinçli olarak değişir; bu kaynak kontrolü maç sonuçlarının aynı kalacağını iddia etmez.

## Gerçek tarayıcı kontrolü

Chromium/SwiftShader ile WebGL-prosedürel ve zorlanmış 2D yolları geçti. Taktik sayfasından başlatma, 22 aktif oyuncu, en az 15 sn normal maç adımı, modül yükleme sırası, algı/görev/tarihçe kayıtları, geçerli evreler, gözlenen/çizilen baş taraması ve gerçek duraklat/devam et düğmeleri kontrol edildi. Poz sorguları gövde/top/RNG durumunu değiştirmedi; JavaScript hatası oluşmadı. Çizilen baş açısı ±0,80 rad sınırında kaldı. Rapor: [team-continuity-browser.json](docs/validation/team-continuity-browser.json).

`tools/check-team-continuity-browser.py` aynı kontrolün çalıştırılabilir aracıdır; Chromium ve Python Playwright gerektirir. Özgün oyuncu modeli, bazı görsel/font dosyaları mevcut checkout'ta eksiktir; eksik kaynaklar raporda listelenir. WebGL denemesi yedek prosedürel modeli doğrular; eksik ayrıntılı modelin tam cihaz testi değildir. Tarayıcı açılışında yalnız sahip olma/savunma evreleri görülmüştür; dört evrenin tamamı için entegrasyon ve maç ölçümleri esas alınır.

## Maç karşılaştırmasının yöntemi ve sınırı

`tools/profile-team-continuity.cjs`, biten canlı adımların hedef Map'lerini dışarıdan okur; karar, plan veya algı sorgusu çağırmaz ve motor yöntemlerini sarmalamaz. Sabit metrik tanımları iki motora uygulanır. Gözlemli/gözlemsiz ve deterministik tekrar koşuları tam V8 snapshot değerleriyle karşılaştırılır; referans, Map ve undefined değerlerini koruyan kanonik durum özeti de kaydedilir. Ham V8 byte dizisi tek başına değer eşitliği sayılmaz. Ortak/markaj kimliği motorun mevcut görev ve niyet kayıtlarından okunur; tabanda yeni ortak görev kaydı yoktur. Bu yüzden görev değişimi göstergesi yalnız koordinat titreşiminin ölçüsü değildir.

**0,45 sn** içinde görev ailesi/ortak/markaj değişimi kararsızlık için bir göstergedir; acil doğru değişimler de sayılır. Taşıma hedefinin aynı oyuncu konumundan **1,10 rad**'dan fazla dönmesi fiziksel top dönüşü veya başarısız hareket sayılmaz. Kullanılmadan bırakılan destek, pas hazırlığı/çıkışı hedefi ve komut sonu üzerinden ölçülen vekil metriktir. Destek noktasına 3 m yakınlık pas yolunun açık veya vuruşun uygulanabilir olduğunu kanıtlamaz. Hazırlık, gerçek pas çıkışı ve alım birbirinden ayrıdır. Destek komutu alıcı koşusuna dönüşünce o bölüm kapanabilir; destek bölümü sürerken sayılan pas çıkışları, destekten başlayan bütün pasları kapsamaz. Daha az komut değişimi tek başına daha iyi futbol ya da topa sahip olma kanıtı değildir.

## Dört tam kısa maç — sonuçlar ve açık kalan denge

[Son matris](docs/validation/team-continuity-matrix.json), **dört yapılandırma × iki motor × 300 sn** içerir. Her motor/senaryo ayrıca gözlemcisiz eşleniği ve bağımsız deterministik tekrarıyla yürütüldü: toplam 24 tam koşu. Tam durum, kanonik özet ve özet metrik eşitlikleri geçti. Yeni motorda iki takımın dört evresi her senaryoda görüldü. Tüm maçlar tamamlandı; durumlar sonlu, skor gerçek gol olaylarıyla aynıydı. En büyük oyuncu adımı tabanda 0,122051, yenide 0,118704 m/60 Hz oldu; 0,15 m kontrol sınırı aşılmadı. Bu dört yapılandırmanın toplamları, önceki aşamaların farklı sekizli matrisleriyle doğrudan karşılaştırılmaz.

| Devamlılık göstergesi | Sekizinci aşama tabanı | Dokuzuncu aşama |
| --- | ---: | ---: |
| 0,45 sn içinde biten / aynı sahiplik bağlamındaki topsuz görev değişimleri | 585/3529 (%16,58) | 389/3332 (%11,67) |
| 1,10 rad üzeri taşıma dönüşü / ölçülen hedef değişimleri | 100/373 (%26,81) | 44/89 (%49,44) |
| Hazırlık/çıkış hedefi seçilmeden değişen / yeniden planlanarak biten destek bölümleri | 1421/1734 (%81,95) | 1263/1533 (%82,39) |
| Hedefe 3 m yaklaşmışken seçilmeden değişen destek bölümleri | 861 | 897 |

Kısa topsuz görev değişimi hem sayı hem oran bakımından azaldı. Büyük taşıma dönüşlerinin sayısı azalırken, ölçülen tüm hedef değişimleri daha fazla azaldığı için büyük dönüş oranı **arttı**. Seçilmeden yeniden planlanan destek oranı da iyileşmedi; hedefe yaklaşmışken seçilmeden değişen destek sayısı arttı. Bu göstergeler açılmış gerçek pas fırsatlarının sayımı değildir, ancak hazır bağlantı kullanımının tamamlandığı sonucunu desteklemez.

| Senaryo | Tamamlanan / tüm pas (taban → yeni) | Top kaybı | Şut | Skor |
| --- | --- | ---: | ---: | --- |
| balanced21 | 102/108 → 105/110 | 5 → 14 | 0 → 0 | 0–0 → 0–0 |
| wide21 | 76/81 → 80/86 | 11 → 14 | 2 → 0 | 1–0 → 0–0 |
| press42 | 73/82 → 85/95 | 7 → 17 | 0 → 0 | 0–0 → 0–0 |
| weak442-77 | 146/147 → 76/83 | 4 → 14 | 0 → 1 | 0–0 → 0–1 |

Toplam tamamlanan pas 397/418 (%94,98) → 346/374 (%92,51) oldu. Top kaybı **27 → 59**, şut **2 → 1**, yarıda kalan vuruş **1 → 3** oldu. wide21 ev sahibi golü kayboldu; weak442-77 yeni sürümde 0–1 bitti. Bu küçük sentetik örneklemde hücum ve sahiplik sonuçları kötüleşti; görev/algı temelinin eklenmesi genel futbol kalitesi artışı olarak kabul edilmedi. Süreleri uzatmadan önce güvenli hazır bağlantının gerçek pas ve pozisyona dönüşmesini, algı yenilemesinin kaçırdığı baskıyı ve hazırlık iptallerini ayrı kalibre etmek gerekir.

Destek bölümünü hazırlıkta seçme sayısı **316 → 271** oldu. Destek bölümü hâlâ sürerken sayılan gerçek pas çıkışı **300 → 0** olarak kaydedildi; yeni alıcı rezervasyonu bölümü `receive-run` ile daha erken kapatabildiğinden bu son değer “destek kökenli hiç pas çıkmadı” anlamına gelmez. Gerçek toplam paslar yukarıdadır; hazırlık seçimi ise başarılı çıkış veya alım değildir.

Karşılaştırmayı yeniden üretmek için `node tools/profile-team-continuity.cjs --seconds 300 --output docs/validation/team-continuity-matrix.json` kullanılabilir. Dört sentetik yapılandırma, iki tohum ve 65/82 oyuncu güçleri; 90 dakika, gerçek kadro, iletişim gecikmesi veya bütün taktikler için futbol dengesi kabulü değildir.

---

# Sekizinci aşama — ortak yerden dokunuş uygulanabilirliği (6 Kasım 2026)

Yeni motor: `e16642b50e1d0b7d31cdc375dea7a83af85cf3da194a28362b65007f8420ad2e`. Karşılaştırma tabanı `docs/validation/baselines/stage8-integration-base.js.gz` içindeki `16d6d78ac01b5490bbb8a178b4134a2f8c41224ad7091fb1e0b6b37aafa07360` kaynağıdır. Bu taban, GitHub main `82414b9` sürümünün uzaktaki alıcı için geç gövde hazırlığını yerel yedinci aşamanın tazelik/duran top/saat korumalarıyla birleştirir; ortak dokunuş modeli henüz eklenmemiştir. Git HEAD veya önceki 104 kayıplı matris bu deneyin tabanı değildir.

Uzak kaynak `8c3b3c19…`, önceki yerel kaynak `c1c1395a…` ve birleştirme tabanı ayrı gzip dosyalarında korunur. Uzak daldaki iki ek tarihsel reception-facing raporu da korunmuştur. Önceki aşamaların metin ve raporları aşağıda tarihsel kayıttır.

## Yeni davranış ve kapsam

`touchContact`, mevcut gövdeye göre ayak erişimini, kullanılacak ayağı/tekniği ve seçilen ayağın kalan temas süresini okur. `touchRecovery`, istenen top hızından sonraki temas zamanına kadar oyuncu/top kopyalarını gerçek `move`, `effort` ve BallPhysics ile ilerletir. `touchPlan` önce istenen darbeyi, yetişilemiyorsa mevcut top hızıyla 0,75/0,50/0,25 oranlı daha küçük değişimleri sınar. Hiçbiri uygun değilse yeni yönlü darbe ertelenir; oyuncu/top taşınmaz.

Aynı hesap normal top sürme ve koruma dokunuşunda, hazırlıklı yerden yönlü ilk kontrolde ve açık oyundaki pas/şut hazırlık dokunuşunda kullanılır. Pasın nihai çıkışı ayrıca mevcut yatay ayak-top farkı <0,11 m ve yön hatası <0,07 rad kapılarını bekler; yeni kapı seçilen ayağın toparlanmasını, alım saatinin bitmesini ve topun alçakta olmasını da arar. Topun vuruştan sonraki serbest uçuşu değişmez.

Normal taşıma/koruma, mevcut dribbling aralığını kullanır. Pas hazırlığında bu aralık iki ayağa birden uygulanmaz: seçilen ayağın önceki dribbling temasından kalan mevcut `footTouch` süresi (başlangıçta 0,14 sn) kullanılır. Diğer ayak serbestse hazırlık başlayabilir. Vuruşun `nextSetup` aralığı ve gerçek temas kapısı ayrıca korunur. Topla mücadeleye karşı koruma eklenmez.

Önizleme en fazla **0,65 sn / 39 gelecek hareket adımıdır**. Saatler canlı motorla aynı sıfıra kırpma ve 60 Hz azalmayla yürür; küçük pozitif kayan nokta kalıntısı erken hazır sayılmaz. Kare sırası da aynıdır: taşıma ve hazırlık darbesinin mevcut karedeki top adımı hesaba katılır; alım sonrasında bu adım tekrar uygulanmaz. Sonraki taşıma/alım teması top entegrasyonundan önce, hazırlanmış vuruş kontrolü sonra okunur. Alım önizlemesi, canlı `acquire` tarafından uygulanacak receive eylemini kullanır; eski pas animasyonunu taşımaz.

Başlık/hava topu, kaleci eli, taç ve yerleştirilmiş duran top modelleri yeniden yazılmadı. Bu bir tam anatomi/kuvvet/denge modeli değildir: ayak erişimi, katsayılar ve kısa süre aynı komutun sürmesi oyun yaklaşımıdır. Rakibin sonraki kararı, omuz teması ve yeni takım planı bilinmez. Uygun sonraki temas, başarılı hücum veya sürekli sahiplik garantisi değildir.

## Geçen kontroller

`npm run test:stage8`: **154/154 test geçti**, atlanan kontrol yok. Önceki 115 kontrole, uzak dalın alıcı davranışıyla uzlaştırılan dört ek kontrol ve 35 yeni ortak dokunuş testi dahildir. Beklenen alıcı açıklığı artık ±π/3 ve ara pası da kapsar; uzaktaki normal koşu, hızlı gelen top ve hazırlığın tazelik bitişi açıkça sınanır.

Yeni testler iki yönde sprintte ters dokunuşun sınırlandırılması/ertelenmesi, normal dokunuşun korunması, gerçek sonraki temas ve komut yenileme eşitliği, koruma, ilk kontrol, eski alım animasyonu, pas hazırlığının toparlanması, sol/sağ/zayıf ayak, seçilen ayağın meşgul olması, serbest diğer ayak, yüksek top, mücadele, serbest top, saat sınırı ve canlı durum/RNG saflığını kapsar. Eski kare sırasını bellekte geri getiren denemeler ilgili yeni testleri düşürür; toleranslar gevşetilerek geçirilmedi.

[Bağımsız kaynak ve canlı adım kontrolü](docs/validation/touch-feasibility-physics-check.json): 10 korunan fonksiyon grubu, BallPhysics ve salt okunur sorgu kontrolleri geçti. 16 taşıma/koruma, sekiz alım, 10 hazırlık, sekiz ayak saati ve sekiz gerçek hızlı vuruş durumu olmak üzere **50 seçilmiş fizik durumu** sınandı. Kabul edilen tahminler doğru canlı karede oyuncu konumu/hızı/gövdesi ve top durumuyla eşleşir. Bu durumlar gelecekteki karar/temas eklenmeden tutulmuş niyet senaryolarıdır; bütün olası maç durumları için kanıt değildir.

BallPhysics, `release`, `doTackle`, `tackleAccess`, `startKick`, `choose`, `plan`, `controlPreparation`, `passPreparation` ve ana `step` gövdeleri birleştirme tabanıyla aynıdır. Yeni model bu mevcut yolların çağırdığı dokunuşları değiştirir. Olasılık/şut gücü veya gol sayısı istenen sonucu elde etmek için ayarlanmadı.

[Gerçek Chromium](docs/validation/touch-feasibility-browser.json): taktik ekranından maç başlangıcı, 22 oyuncu, 15 saniyeden fazla ilerleme, destek planları, saat ve duraklat/devam hem WebGL/prosedürel hem gerçek 2D yedekte geçti; betik hatası yok. Eksik özgün varlıkların 404'leri sürer. Bu masaüstü kontrolü telefon, tam maç seyir kalitesi veya 60 FPS kanıtı değildir.

## Aynı doğal durumdan kontrol örneği

[Doğal temas kaydı](docs/validation/touch-feasibility-natural-contact.json) ve [beş saniyelik dal](docs/validation/touch-feasibility-natural-fork.json), tam birleştirme tabanını balanced21 başlangıcından **63,433333 sn**'ye kadar yürütür. İki dal aynı tam oyuncu/top/Map/RNG durumundan başlar. **63,450000**'de oyuncu 14, yaklaşık 4,911 m/sn hızla gerçek bir top sürme teması dener. Temas öncesindeki tam canlı durum iki dalda eşittir.

Eski motorun ileri dokunuşu topa yaklaşık (−4,298286; −1,843598) m/sn yatay hız verir. Aynı niyet sürdürülürse sonraki ayak farkı **1,3016 m**, mevcut 1,20 m kontrol alanının dışındadır. Yeni motor bu dokunuşu erteler; mevcut (−6,022568; −2,540435) m/sn serbest yuvarlanmayı korur. Bu örnek ters dokunuş değil, ileri dokunuşta yeniden erişim sınırıdır. Keskin ters dönüşler ayrı kontrollü testlerde sınanır.

İki doğal dal da daha sonra topu kaybeder: eski dalın 64,000 civarında çıkan pasını rakip **64,033333**'te alır; yeni dalda rakip **64,550000**'de kazanır. Yaklaşık 0,517 sn gecikme sürekli top koruma başarısı diye sayılmaz. İki dalda gözlemcili/gözlemcisiz tam durum ve RNG tutarlılığı geçti; konum, hedef veya rastgele sonuç zorlanmadı.

## Sekiz tam kısa maç — iyileşen ve kötüleşen ölçümler

[Matris](docs/validation/touch-feasibility-matrix.json): sekiz senaryo × iki motor × 300 sn. Üç tohum, 65/82/91 sentetik kadro gücü, farklı rakip planları ve üç diziliş korunur. Bağımsız senaryo çağrıları aynı kaynak hash'leri doğrulanarak birleştirildi. 16 gözlemcili maçın tümü gözlemcisiz eşleniğiyle tam durum olarak eşit; her senaryo/motor için deterministik tekrar da eşit. Bütün maçlar tamamlandı; değerler sonlu ve skor gerçek gol olaylarıyla eşitti. En büyük oyuncu adımı tabanda 0,127858, yenide 0,122125 m/60 Hz; 0,15 m sınırı aşılmadı.

| Senaryo | Hedef alımı / çözülen uçuş (taban → yeni) | Top kaybı | Skor |
| --- | --- | --- | --- |
| balanced21 | 104/117 → 99/105 | 23 → 5 | 0–0 → 0–0 |
| press42 | 118/126 → 110/119 | 9 → 9 | 0–0 → 0–0 |
| narrow21 | 104/110 → 138/142 | 8 → 3 | 1–0 → 1–0 |
| wide21 | 80/86 → 97/101 | 15 → 9 | 0–0 → 0–0 |
| short42 | 72/82 → 112/116 | 23 → 8 | 0–0 → 0–0 |
| direct42 | 121/128 → 87/98 | 8 → 8 | 0–0 → 0–1 |
| weak442-77 | 137/139 → 138/147 | 5 → 4 | 0–1 → 0–0 |
| strong352-21 | 62/70 → 92/100 | 28 → 14 | 0–0 → 0–0 |

İki takım toplamında top kaybı **119 → 60**, hedef alımı **798/858 → 873/928**, pas/tamamlanan pas **862/820 → 935/905** olur. Rakibin hedefli pası alması **28 → 16**, başka kendi oyuncusunun alması **21 → 29**, takımın son dokunuşuyla dışarı giden hedefli uçuş **1 → 1**. Pencere sonunda yoldaki hedefli uçuş **3 → 4** olup çözülen paydadan çıkarılır.

**Her ölçüm iyileşmedi:** şut **5 → 4**, yarıda kalan vuruş **0 → 4**. Direct42 ve weak442-77 hedef alımı oranları kötüleşir; direct42 ev sahibi için skor da kötüleşir. Azalan top kaybı, daha fazla pas veya daha yüksek alım oranı tek başına gerçek futbol/hücum kalitesi kanıtı değildir. İlk farklı davranıştan sonra yollar ayrışır; toplamlar tek dokunuşun bağımsız nedensel kazancı sayılamaz. Bunlar sekiz 5 dakikalık sentetik maçtır; 90 dakika veya gerçek maç dağılımı kalibrasyonu değildir.

Yeni motorda 226 darbe sınırlandırma ve 150 dokunuş erteleme; ayrıca sekiz hazırlık darbesi sınırlandırma ve 713 hazırlık denemesi erteleme sayılmıştır. Bunlar deneme sayaçlarıdır; benzersiz pas, kazanılmış top veya başarı sayısı değildir. Aynı vuruş birkaç kez bekleyebilir.

Dar hazırlanmış yerden alım kümesinde 1 sn penceresi **781 tamamlanan/2 bekleyen → 846/1**, rakip kazanımı **10 → 6**; 2 sn penceresi **779/4 → 843/4**, rakip kazanımı **28 → 18**, rakibe duran top **1 → 2**. Baskı <3 m altında tamamlanan 2 sn penceresi **23 → 37**, kazanım **7 → 4**, rakibe duran top **0 → 1**. Alt kümeler değiştiği için sabit pozisyon eşleştirmesi değildir. Kazanım ve duran top aynı pencerede birlikte olabilir; toplanarak benzersiz kayıp türetilmez. Bekleyen süre başarı sayılmaz; kazanım görülmemesi sürekli sahiplik değildir.

[Gözlemci sınır kontrolü](docs/validation/touch-feasibility-observer-check.json), tam 1/2 sn kazanım/duran top, 1,5 sn kazanımı, süre dışı olay ve bekleyen pencere için yedi kontrollü denemeyi geçer. Önceki yerel raporlar korunur; uzak dalın önceki dosya sürümleri de GitHub `82414b9` ebeveyn commitindedir.

## Yeniden üretme

```sh
npm run test:stage8
node tools/check-touch-physics.cjs
node tools/check-touch-observer.cjs
node tools/profile-touch-feasibility.cjs --mode matrix --seconds 300 --output /tmp/touch-feasibility-matrix.json
node tools/profile-touch-feasibility.cjs --mode fork --scenario balanced21 --at 63.433333333331014 --follow-seconds 5 --output /tmp/touch-feasibility-natural-fork.json
```

Kayıt dönüşümü gerekmez; yeni alanlar geçici maç durumu/telemetridir. İlk kontrolün bütün adaylarının ortak puanlanması, takım kararlarının bu sınırlara daha erken uyarlanması, kuvvet/denge ve tam iki ayaklı adım döngüsü sonraki geliştirmelerdir. Yerel çalıştırma ve eksik data/assets sınırları README başındadır.

---

# Yedinci aşama doğrulaması — alım sonrası ters bekleme kararının uygulanabilirliği (6 Kasım 2026)

Taban, önceki aşamanın tam kaynağıdır: `108d47253d775de6638460d5fa90dd6bbe2ab2e1e066b581e17591350c4917b6`; `docs/validation/baselines/stage6-football-sim.js.gz` içinde saklanır. Yeni motor `c1c1395a97a64f38a4c9704bde953e4f8ff8904f44784462313cfe15c83d694c`. Git HEAD karşılaştırma tabanı değildir. Önceki aşamaların metin ve raporları aşağıda tarihsel kayıt olarak korunmuştur.

Hazırlanmış top alımından hemen sonra seçilen bir `hold` kararı, oyuncu hâlâ önceki koşunun hızıyla giderken topu ters yöne gönderebiliyordu. Yeni `postReceiveHold`, bu dar durumda istenen bekleme ile mevcut taşıma hedefini aynı gerçek hareket/top hesabında karşılaştırır. İstenen bekleme müdahaleye açılıyorsa, önceki hedef ancak önizlemede müdahale görülmemiş ve gerçek bir dribbling dokunuşu oluşmuşsa kısa süre korunur. **Bir doğal kayıp önlendi; başka bir doğal örnekte kayıp yalnız gecikti. Bu örneklem genel baskı altında top koruma artışı göstermiyor.**

## Kapsam ve geçen kontroller

Yeni karşılaştırma yalnız gerçek sahipte, hazırlanmış `open/protect` alımından sonraki en fazla 1,5 sn'de, kontrol saati bitmiş ve mevcut taşıma niyeti hâlâ geçerliyken çalışır. Seçilen karar `carry + hold` olmalı; hız en az 0,8 m/sn, seçilen yön ile hız yönü arasındaki fark en az 1,1 rad olmalıdır. Rakip yakın veya gözlenen hareketle yaklaşıyor olmalıdır. Kaleci, duran top, vuruş, topun en az 0,45 m yüksekte olması ve kapsam dışındaki diğer kararlar eski yolu izler. Kapı önceki pasın türünü yeniden sınıflandırmaz; tam koşullar ARCHITECTURE başındadır.

Her aday mevcut `controlPreparation` ile **0,75 sn / en fazla 45 adım** sınanır; en fazla iki aday vardır. Normal `move`, `dribbleTouch`, `tackleAccess` ve BallPhysics kopyalarda yürütülür. Gelecekteki takım planı, gizli rakip komutu veya RNG okunmaz. Müdahale öngörüsü kazanılmış top değildir; bu kısa sürede müdahale görülmemesi de gelecekteki güvenli sahipliği kanıtlamaz. Dönen sonuç yalnız yeni bir hareket niyetidir; gerçek müdahaleyi veya top kaybını engelleyen bir kural eklenmedi.

`npm run test:stage6` içindeki önceki **101 test** ve `npm run test:post-receive-hold` içindeki **14 yeni test** ayrı koşularda geçti: toplam **115 test**, atlanan kontrol yok. `npm run test:stage7` aynı iki grubu sırayla çalıştırır. Yeni testler iki saha yönünde ters bekleme, güvenli beklemenin korunması, önceki hedefin de riskli olması, önizlemede dokunuş oluşmaması, süresi dolmuş/geçersiz kapsam, diğer kararların korunması, momentumla uyumlu bekleme, uzaktaki uzaklaşan rakip, salt okunurluk ve gerçek sahip adımıyla normal hareket/top fiziğini sınar. Kontrollü yerleşimler doğal maç kazanımı diye sunulmaz; önceki testler gevşetilmedi.

[Kaynak ve fizik kanıtı](docs/validation/hold-continuation-physics-check.json): yalnız mevcut `step` yöntemi değişti; `postReceiveHold` eklendi. Diğer **95 Match yöntemi** ve BallPhysics'in **13 üyesi** birebir aynıdır. İlk alım, ilk kontrol darbesi, ayak/alım yarıçapı, dribbling, vuruş ve müdahale uygulamaları değişmedi. Yeni sorguda tam canlı durum eşitliği ile RNG, gelecek plan ve gizli rakip komutu korumaları da geçti.

[Gerçek Chromium kontrolü](docs/validation/control-exit-browser.json): taktik ekranından maç başlangıcı, 22 oyuncu, 15 saniyeden fazla ilerleme, destek planları, saat, duraklat/devam hem WebGL/prosedürel hem zorlanmış gerçek 2D modda geçti; betik hatası yok. Eksik özgün model/font/portre 404'leri sürer. Bu kısa masaüstü kontrolü telefon veya 60 FPS performans kanıtı değildir.

## Aynı doğal durumdan bir düzeltme ve bir sınır

[Yeni doğal karşılaştırma](docs/validation/control-exit-fork.json), tam altıncı aşama motorunu `short42` yapılandırmasıyla başlangıç vuruşundan **212,133333 sn**'ye kadar çalıştırır. Sahip oyuncu 3'tür; iki dal aynı tam oyuncu/top/Map/RNG durumundan, RNG **681157795** ile sonraki **5 sn** yürür. Sonuç için konum, karar, taktik veya rastgelelik zorlanmaz. Her dalın gözlemcili/gözlemcisiz tam durum eşitliği geçti. Pencere başlamadan alınmış top yeni bir alım diye sayılmaz.

| Aynı başlangıç | Altıncı aşama | Yedinci aşama |
| --- | --- | --- |
| İlk gerçek rakip kazanımı | Rakip 11, **212,933333**'te kazanır | 5 sn pencerede rakip kazanımı yok |
| Kendi pas devamı | İlk sahip topu kaybeder | 3 → 0 pası **214,450000**'de gerçekten çıkar; **215,733333**'te hedef alır |
| Pencere sonundaki devam | Rakip 11 → 16 pası tamamlanır | 0 → 3 pası **216,700000**'de çıkar; pencere sonunda hâlâ yolda, başarı sayılmaz |

Bu sınırlı dalda bir bekleme kararı mevcut koşunun devamına çevrildi. Beş saniye boyunca rakibin kazanmaması sürekli kendi sahipliği anlamına gelmez: kendi pasları sırasında top serbest uçuşta kalır. Daha sonraki başarı veya maç sonucu garanti edilmez.

[Önceki olumsuz örneğin yeniden yürütülmesi](docs/validation/hold-continuation-physics-check.json), farklı bir önektir: tam beşinci aşama başlangıçtan **149 sn**'ye, ardından tam altıncı aşama **86 adım** ile **150,433333 sn**'ye yürür. Bu karışık önek açıkça raporlanır; tam altıncı aşama başlangıç maçı diye sunulmaz. İki yeni dal aynı tam durumdan 5 sn ilerler. **150,450000**'de ters `hold`, önceki taşıma hedefine çevrilir; buna rağmen rakip 4 iki dalda da kazanır: eski dalda **151,033333**, yeni dalda **152,400000**. Kayıp yaklaşık **1,366667 sn gecikir**, önlenmez. İlk alımdan sonraki 2 sn'lik pencerenin dışına kayması, beş saniyelik başarı olarak yorumlanamaz. Bu iki dalda da gözlemcili/gözlemcisiz durum eşitliği geçti.

## Sekiz tam maç: dar ve seyrek etki

[Matris](docs/validation/control-exit-matrix.json), aynı sekiz senaryoyu iki motorda **300'er sn** çalıştırır. Üç tohum, farklı rakip planları, 65/82/91 sentetik kadro gücü ve 4-3-3/4-4-2/3-5-2 korunur. Sekiz bağımsız `--scenario` çağrısı, aynı kaynak hash'leri doğrulanarak özgün sırada birleştirilmiştir. **16 gözlemcili tam maçın her biri gözlemcisiz eşleniğiyle tam durum olarak eşit; her senaryo/motor için deterministik tekrar da eşit.** Bütün maçlar tamamlandı; değerler sonlu, skorlar gerçek gol olaylarıyla eşittir. İki motorda da en büyük oyuncu adımı **0,125617 m/60 Hz** oldu; 0,15 m sınırı aşılmadı.

Yeni `holdContinuations` sayacı yalnız kararı sayar; top kazanımı veya tamamlanan pas saymaz. Matrisin yalnız **short42** satırında bir kez çalıştı; diğer yedi satırda sıfırdı ve raporlanan ölçümler aynı kaldı. Short42'de hedef alımı **100/110 → 104/114**, toplam top kaybı **17 → 16**, pas/tamamlanan pas **111/106 → 114/111** olur; skor iki dalda da **0–1** kalır. İlk değişen karar sonrası yollar ayrıştığı için sonraki bütün farklar tek bir yerel kararın bağımsız nedensel kazancı sayılamaz.

| İki takım ve sekiz maç toplamı | Altıncı aşama | Yedinci aşama |
| --- | --- | --- |
| Gerçek hedef alımı / çözülen hedefli uçuş | 808 / 871 | 812 / 875 |
| Pas / tamamlanan pas | 882 / 843 | 885 / 848 |
| Toplam top kaybı | 105 | 104 |
| Rakibin hedefli pası alması / başka kendi oyuncusunun alması | 19 / 30 | 19 / 31 |
| Takımın son dokunuşuyla dışarı giden hedefli uçuş | 1 | 1 |
| Pencere sonunda hâlâ yoldaki hedefli uçuş | 4 | 3 |
| Şut | 5 | 5 |

Hedef alımı gerçek başarılı `acquire` olayıdır. Payda yalnız gerçek alım, kesilme, dışarı çıkış, gol veya uçuş kapanmasıyla çözülen hedefli uçuşları içerir; bekleyenler çıkarılır. Başka kendi oyuncusunun alması hedef başarısı veya rakip kazanımı diye sayılmaz. Toplamın bir kayıp azalması, yedi senaryoda hiç devreye girmeyen bu dar değişiklik için genel üstünlük kanıtı değildir.

Alım sonrası gözlem, önceki aşamayla aynı dar temas kümesini kullanır: hedefli, kaleci olmayan, taze hazırlıklı, yerden normal pas/geri pas alımları; bu küme yeni kararın her alımda çalıştığını söylemez. Gerçek ayak bölgesine uygun temas **772/786 → 776/790**, uygun olmayan temas **14 → 14** olur. Alım kodu değişmedi; sayılar sonraki maç yollarının değişmesinden etkilenir.

| Dar alım kümesindeki kısa pencere | Altıncı aşama | Yedinci aşama |
| --- | --- | --- |
| Alım / tamamlanan 1 sn pencere / bekleyen | 786 / 784 / 2 | 790 / 787 / 3 |
| 1 sn içinde gerçek rakip kazanımı | 11 | 10 |
| Tamamlanan 2 sn pencere / bekleyen | 782 / 4 | 784 / 6 |
| 2 sn içinde gerçek rakip kazanımı / rakibe duran top | 29 / 2 | 26 / 2 |
| Baskı <3 m: tamamlanan 2 sn pencere / bekleyen | 28 / 0 | 26 / 0 |
| Baskı <3 m: 2 sn içinde gerçek rakip kazanımı / rakibe duran top | 7 / 1 | 7 / 1 |

Rakip kazanımı yalnız gerçek başarılı `acquire` olayından kaydedilir; rakibe duran top ayrı tutulur ve aynı pencerede ikisi de olabileceğinden toplanıp benzersiz kayıp sayısı türetilmez. Bekleyen pencere başarı sayılmaz; rakip kazanımı görülmeyen süre sürekli sahiplik anlamına gelmez. Alım alt kümeleri iki motorda değiştiği için paydalar sabit bir pozisyon eşleştirmesi değildir. Özellikle baskı <3 m grubunda **7/28 → 7/26** sonucu, baskılı alımlarda genel iyileşme göstermiyor.

[Gözlemci sınır kontrolü](docs/validation/control-exit-observer-check.json), **7 kontrollü denemede** tam 1/2 sn rakip kazanımı ve duran topu, 1,5 sn kazanımı, süre dışı olayı ve bekleyen pencereyi doğrular. Gerçek motor yöntemleri gözlemcili/gözlemcisiz eşlenik durumlarda çalışır; elle seçilmiş olay zamanları doğal maç örneği diye sunulmaz. Eski araç ve raporlar değiştirilmedi.

## Yeniden üretme ve sınırlar

```sh
npm run test:stage7
node tools/check-hold-physics.cjs
node tools/check-control-exit-observer.cjs
node tools/profile-control-exit.cjs --mode matrix --seconds 300 --output /tmp/control-exit-matrix.json
node tools/profile-control-exit.cjs --mode fork --scenario short42 --at 212.1333333333943 --follow-seconds 5 --output /tmp/control-exit-fork.json
```

Önizleme, mevcut komut ve gözlenen rakip hareketinin kısa süre devamını varsayar; yeni taktik karar, omuz ayrıştırması veya rakibin sonraki hamlesini bilmez. Eski hedefte bir dokunuş gözlenmesi, sonraki dokunuşun veya pasın da uygulanabileceğini kanıtlamaz. Hızlı pas seçimi, ilk kontrol yönünün bütün adayları ve daha uzun süreli taşıma kararları bu dar aşamada yeniden yazılmadı. Yerel çalıştırma, eksik data/assets ve kayıt koruma bilgileri README başındadır.

---

# Altıncı aşama doğrulaması — alım öncesi gövde hazırlığı (6 Kasım 2026)

Taban, önceki teslim ZIP'iyle birebir kontrol edilen beşinci aşama kaynağıdır: `7038778922feb9f8f24389003b5ddf92fb8c0790280af84ae9818a04198acf60`. Tam kaynak `docs/validation/baselines/stage5-football-sim.js.gz` içinde tutulur. Güncel motor `108d47253d775de6638460d5fa90dd6bbe2ab2e1e066b581e17591350c4917b6`; Git HEAD eski yüklemeyi gösterir. Önceki aşamalar ve raporları aşağıda tarihsel kayıt olarak korunmuştur.

Yeni davranış, hedefli normal yerden pas/geri pas alıcısının çıkışa tamamen dönmek yerine gelen topa yarı açık hazırlanmasıdır. **Ayak bölgesi uygunluğu belirgin arttı; bu örneklem genel top koruma artışı göstermedi.** Uygun temas, seçilmiş çıkışın baskı altında güvenli olduğunu göstermiyor.

## Geçen kontroller

`npm run test:stage6`: **101/101 test geçti**, atlanan test yok. Önceki 85 test korunarak 16 yeni test eklendi. İki saha yönünde gerçek hareket ve `ballStep` ile yeterli/geç hazırlık, aynı alım yarıçapı, dönüş hızı, hazırlığın çıkış niyetini koruması, gerçek devam pası ve 16 kapsam dışı durumda tam beşinci aşama durum eşitliği sınanır. Tahmin ile aynı komutun gerçek hareketi 0,3 ve 0,7 sn'de, hazırlığın tazelik bitişi dahil karşılaştırılır. Canlı durum/RNG değişmemesi, gizli rakip komutu ve gelecek plan okunmaması, bağımsız top fiziği ve gerçek rakip kesmesi de sınanır. HTTP maç başlatma testi, localhost soketi açılmasına izin verilen yürütmede geçti; ilk kısıtlı denemedeki EPERM başarı sayılmadı.

Hazır devam testinde yalnız normal `step` ilerletilir: alım saati bitmeden vuruş başlamaz; gerçek `preparedChoice` → `startKick` → `kickStep` çıkışında ayak-top farkı <0,11 m, yön hatası <0,07 rad ve hazırlık saati tamamlanmış olmalıdır. `one-touch` etiketi sıfır gecikmeli veya tek anatomik temaslı pas diye sayılmaz.

[Kaynak/kapsam raporu](docs/validation/reception-facing-physics-check.json): yalnız mevcut `move` ve `projectPlayer` yöntemleri değişti; `receptionFacing` eklendi. Diğer **93 Match yöntemi** ve BallPhysics'in 13 üyesi birebir aynıdır. `acquire`, `firstControlContact`, `release`, `doTackle`, `startKick`, `kickStep`, `contactPoint` ve top entegrasyonu korunur. Alım/ayak yarıçapı, müdahale veya vuruş hatası kolaylaştırılmadı.

[Gerçek Chromium kontrolü](docs/validation/reception-facing-browser.json): taktik ekranından açılan maç WebGL/prosedürel ve gerçek 2D yedek modunda çalıştı; 22 oyuncu, 15 saniyeden fazla motor ilerlemesi, saat, destek planları ve duraklat/devam geçti. Betik hatası yok. Özgün model/font/portre varlıkları hâlâ eksik; bu kontrol telefon veya 60 FPS performans kanıtı değildir.

## Aynı doğal durumdan olumlu ve olumsuz sonuçlar

Üç karşılaştırma da tam beşinci aşama motorunu başlangıç vuruşundan belirtilen ana kadar çalıştırır. Tam oyuncu/top/Map/RNG durumu iki motora aynı biçimde klonlanır; sonraki 5 saniye normal plan, hareket, müdahale ve temasla yürür. Konum, hedef, taktik veya rastgele sonuç zorlanmaz. Her dalda gözlemcili/gözlemcisiz tam durum eşitliği geçti. Fork başladığında zaten yolda olan pas, yeni çıkış diye sayılmaz; en küçük fark ölçümü yalnız bu pencerenin başlangıcından itibaren geçerlidir.

| Aynı durum | Beşinci aşama | Altıncı aşama |
| --- | --- | --- |
| [press42, 9,433333 sn](docs/validation/reception-facing-fork.json), 4 → 5 pası | 10,416667'de gerçek alım; top gövdeye göre arkada, `cushion` | 10,400000'de gerçek alım; ayak uygun, `open`; 5 → 3 pası 13,433333'te çıkar ve 14,250000'de alınır |
| [short42, 193,233333 sn](docs/validation/reception-facing-pressure-fork.json), 13 → 12 pası | 194,116667'de gerçek alım; yanal fark 1,085677 m, hazırlanan hızlı devam `cushion` olur; 12 → 16 çıkışı 194,616667 | Aynı anda gerçek alım; yanal fark 0,863575 m, hızlı devam niyeti korunur; gerçek çıkış 194,383333, yani yaklaşık 0,233333 sn erken |
| [balanced21, 149 sn](docs/validation/reception-facing-counter-fork.json), 14 → 11 pası | 149,833333'te `cushion`; sonra 11 → 14 ve 14 → 12 pasları gerçekten alınır; 5 sn içinde rakip kazanımı yok | Aynı anda ayak uygun `protect` alımı; rakip 4, 151,033333'te, alımdan **1,2 sn sonra** gerçekten kazanır |

İkinci örnekte başlangıç RNG 3868005481 ve ilk alım öncesi gerçek top konumu/hızı aynıdır. Gövde hedefi hareket hızını da etkilediği için alıcı konumu yaklaşık 5,8 cm farklıdır; aynı oyuncu konumunda yalnız açının değiştirildiği bir deney diye sunulmaz. İki dal da sonraki pasları tamamlar; daha erken çıkış kendi başına top koruma artışı değildir. İlk örneğin ilk alımından sonraki 2 sn'de iki dalda da rakip kazanımı yoktur; sonraki alım pencere sonunda hâlâ bekliyor olabilir.

Olumsuz örnekte yeni dal daha iyi ayak açısıyla yine top kaybeder. İlk 1 sn ölçümü bu farkı kaçırır; 2 sn penceresi kaybı yakalar. Çıkış seçimi ve kontrol darbesinin baskıyla birlikte yeniden değerlendirilmesi hâlâ gereklidir.

## Sekiz tam maçın ölçümleri

[Matris](docs/validation/reception-facing-matrix.json): 8 senaryo × 2 motor × 300 sn. Üç tohum, farklı rakip planları, 65/82/91 sentetik kadro gücü ve 4-3-3/4-4-2/3-5-2 kullanılır. Dar/geniş ve kısa/doğrudan çiftlerinde aynı kadro/rakiple yalnız belirtilen taktik alanı değiştirilir. **16 gözlemcili tam maçın her biri gözlemcisiz eşleniğiyle tam durum olarak eşit; iki tam deterministik tekrar da eşit.** Bütün maçlar tamamlandı; top/oyuncu değerleri sonlu ve skor gerçek gol olaylarıyla eşitti. En büyük oyuncu adımı eski motorda 0,118822, yenide 0,125617 m/60 Hz; 0,15 m sınırı aşılmadı.

Aşağıdaki hedef alımı bütün pas türleri içindir. Payda yalnız gerçek alım, kesilme, dışarı çıkış, gol veya uçuş kapanmasıyla çözülen hedefli uçuşları içerir. Başka kendi oyuncusunun alması ayrı tutulur. İlk farklı hareket/karardan sonra maç yolları ayrışır; bu tablo tek bir kontrol kararının nedensel fayda ölçümü değildir.

| Senaryo | Hedef alımı / çözülen hedefli uçuş (5 → 6) | Top kaybı (5 → 6) | Skor (5 → 6) |
| --- | --- | --- | --- |
| balanced21 | 118/129 → 115/119 | 17 → 11 | 0–0 → 0–0 |
| press42 | 121/126 → 115/123 | 12 → 13 | 0–0 → 0–0 |
| narrow21 | 128/132 → 105/113 | 12 → 16 | 0–0 → 0–0 |
| wide21 | 98/107 → 89/95 | 9 → 14 | 0–0 → 1–0 |
| short42 | 120/130 → 100/110 | 7 → 17 | 0–0 → 0–1 |
| direct42 | 101/114 → 106/115 | 15 → 8 | 0–0 → 0–0 |
| weak442-77 | 131/136 → 122/131 | 3 → 9 | 0–0 → 0–0 |
| strong352-21 | 63/71 → 56/65 | 26 → 17 | 0–0 → 0–0 |

İki takımın toplamı: hedef alımı **880/945 (%93,12) → 808/871 (%92,77)**; pas/tamamlanan pas **948/905 → 882/843**; toplam top kaybı **101 → 105**. Rakibin hedefli pası alması **28 → 19**, başka kendi oyuncusunun alması **24 → 30**; takımın son dokunuşuyla dışarı giden hedefli uçuş **0 → 1**. Uçuş sonunda hâlâ yolda kalan hedefli paslar **1 → 4** olup paydalardan çıkarılır. Şut **1 → 5** olur; iki gol içeren yeni yol genel hücum başarısı kanıtı değildir. Yalnız normal pass/cutback kategorisinde hedef alımı **860/911 → 786/833**; bu geniş uçuş kategorisi her temasın dar gövde hazırlığı kapsamında olduğunu söylemez.

Yeni davranışın dar temas kapsamındaki **gerçek başarılı alımlar** ayrıca ölçülür: hedefli, kaleci olmayan, taze hazırlıklı, yerden pass/cutback, duran top dışında. Bu alımlarda mevcut ayak bölgesine uygun temas **485/860 (%56,40) → 772/786 (%98,22)**; uygun olmayan temas **375 → 14**. Bu oran kaçırılan bütün pasların paydası değildir; gerçek alınmış topun kontrol geometrisidir.

| Dar kapsamdaki alım sonrası gözlem | Beşinci aşama | Altıncı aşama |
| --- | --- | --- |
| Alımlar / tamamlanan 1 sn pencere / bekleyen | 860 / 857 / 3 | 786 / 784 / 2 |
| 1 sn içinde gerçek rakip kazanımı | 3 | 11 |
| Tamamlanan 2 sn pencere / bekleyen | 855 / 5 | 782 / 4 |
| 2 sn içinde gerçek rakip kazanımı | 19 | 29 |
| 2 sn içinde rakibe duran top | 0 | 2 |
| Baskı <3 m: alım / tamamlanan 2 sn pencere | 19 / 19 | 28 / 28 |
| Baskı <3 m: 2 sn içinde rakip kazanımı / rakibe duran top | 1 / 0 | 7 / 1 |

Rakip kazanımı yalnız başarılı gerçek `acquire` olayından sayılır; duran top ayrı sütundur ve aynı pencerede ikisi birden olabileceğinden toplanarak benzersiz kayıp sayısı türetilmez. Bekleyen pencereler başarı kabul edilmez. Rakip kazanımı görülmeyen süre, sürekli kendi sahipliği anlamına gelmez; serbest top veya kendi pası bulunabilir. Dar alım alt kümeleri ve baskı durumu iki motorda değiştiği için yüzdeler aynı sabit pozisyonların eşleştirilmiş sonucu değildir.

[Gözlemci sınır kontrolü](docs/validation/reception-facing-observer-check.json) **7 kontrollü denemede** tam 1/2 sn rakip kazanımı ve duran topu, 1,5 sn kaybı, süre dışı olayı ve bekleyen pencereyi doğrular. Gerçek motor yöntemleri eşlenik gözlemcili/gözlemcisiz durumlarda çalışır; kontrollü zamanlar doğal maç olayı diye sunulmaz. Yeni aracın duran top sarmalayıcısında olay, tam sınır anında pencere kapanmadan kaydedilir; önceki tarihsel raporlar değiştirilmedi.

## Yeniden üretme ve açık sınırlar

```sh
npm run test:stage6
node tools/check-reception-observer.cjs
node tools/profile-reception-facing.cjs --mode matrix --seconds 300 --output /tmp/reception-facing-matrix.json
node tools/profile-reception-facing.cjs --mode fork --scenario press42 --at 9.433333333333382 --follow-seconds 5 --output /tmp/reception-facing-fork.json
node tools/profile-reception-facing.cjs --mode fork --scenario short42 --at 193.23333333337925 --follow-seconds 5 --output /tmp/reception-facing-pressure-fork.json
node tools/profile-reception-facing.cjs --mode fork --scenario balanced21 --at 149 --follow-seconds 5 --output /tmp/reception-facing-counter-fork.json
```

Bir radyan açıklık oyun katsayısıdır; anatomik gövde/ayak modeli değildir. Tam arka eksende küçük top yönü değişimleri yarı açık duruşun sol/sağ tercihini değiştirebilir; mevcut dönüş sınırı yine uygulanır. Tahmin mevcut komutun sürmesini varsayar; yeni plan, omuz teması ve rakibin sonraki kararı bilinmez. Daha iyi ayak açısı ile ilk kontrolün seçilmiş yönünün güvenliği ayrı sorunlardır. Sıradaki öncelik, baskı altında yönlü kontrol/hızlı devam seçimini gerçek gövde hazırlığı ve rakibin yetişme süresiyle birlikte değerlendirmek. Yerel maç çalıştırma, eksik data/assets ve kayıt koruma bilgileri README başındadır.

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
