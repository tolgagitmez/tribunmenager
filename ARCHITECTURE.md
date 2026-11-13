## Aşama 12: ortak hakem, saha ve müsabaka yaşamı

`referee-laws.js` olay konumundan faul/penaltı/kart kararını üretir. `Match.adjudicateFoul` karar kaydını, avantaj durumunu, ertelenen disiplini ve gerçek yeniden başlatmayı yönetir. Penaltı normal hazırlık/ayak/kaleci temas zincirini kullanır. `pitch-laws.js` bütün-top çizgi geçişi ve süpürülmüş kale çerçevesinin ortak geometri kaynağıdır; çizim aynı ölçüleri okur.

`match-rules.js`, iki nominal devre, mola, minimum ek süre ve değişiklik pencerelerini yönetir. `match.time` kronolojik kalır; kullanıcı `clockState()` görür. Mola sırasında fizik/AI çalışmaz. İkinci devrede bütün taktik, kaleci, gol ve ofsayt yönleri `Match.direction(team)` üzerinden tersine döner. Hücum gözlemcisi mola süresini ayrı ölü-top alt bölmesine koyar ve eski devrenin hücumunu sansürler. Sınırdaki bir adım gözlem sınıflandırma belirsizliği rapor sözleşmesinde korunur.

`start.py` yalnız standart kütüphane kullanan yerel/tam mod başlatıcısıdır. Yerel mod statik oyunu sunar ve kapalı API'lere açıklayıcı 503 yanıtı verir; özel dosya yollarını sunmaz. Tam mod eksik veri için açılmadan önce anlaşılır hata verir. Başlatma betikleri ve [KURULUM.md](KURULUM.md) aynı girişi kullanır. [Kural sözleşmesi](docs/MATCH_RULES.md) uygulanan sezgileri ve eksik IFAB kapsamını açıklar.

---

# On birinci aşama — ortak oyuncu ve maç başlangıç sözleşmesi

`player-model.js`, tarayıcı/CommonJS üzerinde ham kadro kaydını etkin maç değerlerine çevirir. `club-data.js` mevki uyumunu ve `manager.js` maç gücünü bu modülden alır. `Match.reset` iki takımın kayıtlarını aynı `forSlot` yolundan geçirir; `substitute` aynı slot hesabını yeniden kullanır. Ham kadro nesnelerine maç yorgunluğu veya etkin puan yazılmaz. Genel kalite göstergesi eski kadro formülünü korur; alt özelliklerin davranışa etkisi ayrı ve açıktır.

`player-model-profiles.json` sekiz kurmaca varsayılan profilin ortak kaynağıdır. Python antrenmanı bu JSON'u okur; tarayıcıdaki `player-model-profiles.js` kopyasının JSON ile birebir eşliği test edilir. Sunucunun `player_match_quality` hesabı JS kalite sözleşmesine karşı sınanır. Katalog doğrulaması verilen ayak, rol ve sayısal özellikleri korur; eksik teknik/fiziksel gözlemleri genel puandan türetip kaynak verisi gibi saklamaz. Maç normalleştirmesi eksikleri `inferredAttributes` ve ayak kaynağıyla gösterir.

`match-config.js`, kadro, taktik ve doğrudan maç girişinin ortak hazırlık sınırıdır. Kendi transfer oturumu varsa önce güncel kadro alınır; aynı profil/sürümde kullanıcının seçtiği ilk 11 korunur, yeni kabul edilmiş sürüm geç kalan eski yanıta yenilmez. Ardından `GET /api/league/local-match`, Bearer lig kimliğiyle fikstür ve futbol alanlarıyla sınırlı rakip görüntüsü verir. Sunucu tek okuma işlemi içinde takımın diziliş/taktiğini ve bağlı transfer kadrosunu okur; cüzdan, teklifler, keşif ve erişim anahtarları bu izdüşüme girmez. Yanıt resmî sonucu hesaplamaz veya kaydetmez.

Hazırlanmış iki kadro `sessionStorage` üzerinden `match.html` sayfasına taşınır; depolama yoksa hash yedeği kullanılır. Maç sayfası aynı lig/transfer oturumu bağlamındaki tamamlanmış başlangıcı tekrar eşitlemez. Lig kimliği veya transfer profili değişirse eski başlangıç yeniden hazırlanır; yapılandırmaya yalnız opak bağlam kimliği girer, erişim anahtarı URL'ye taşınmaz. Kullanıcı her zaman motorun takım 0'ıdır; fikstürde deplasmandaysa `fixture.isHome` etiketleri gerçek ev/deplasman bilgisini korur. Kayıtlı rakip yoksa deneme kaynağı ve açıklaması görünürdür. Bu, bütün bilgisayar kulüpleri için gerçek oyuncu verisi sağlandığı anlamına gelmez.

Ayrıntılı formül, özellik grupları ve açık kapsam [docs/PLAYER_MODEL.md](docs/PLAYER_MODEL.md) içindedir. Önceki aşamaların kaynak ve ölçümleri aşağıda tarihsel olarak korunur.

---

# Onuncu aşama — pasif hücum tanılaması

`attack-diagnostics.js`, CommonJS/tarayıcı modülü olarak gerçek maç çağrılarını gözler. `attach(match)` asıl yöntemleri aynı `this`, argümanlar, dönüş değeri ve hata davranışıyla iletir. Kalıtılan yöntemlerin gözlem kancaları `non-enumerable` olur; hazırlık önizlemelerinin `Object.assign` kopyalarına taşınmaz. Önceden bir own-method override varsa descriptor özellikleri korunur; başka bir `this` ile çalışan kopya yalnız asıl yöntemi çağırır ve olayı kaydetmez. `detach()` önceki own-property descriptor'larını ve kalıtım görünürlüğünü birebir geri yükler. Gözlemci ek karar, plan, pas seçeneği, kaleci tahmini veya RNG sorgusu çalıştırmaz.

Uygulama normal 60 Hz adımını gözlemcinin `step` yolu üzerinden yalnız bir kez yürütür. Süre sınıfı karenin başındaki durumdan, süre miktarı gerçek maç saati farkından alınır. Açık oyundaki vuruş hazırlığı ve kaleci elde topu bekletmesi oyunda; yerleştirilmiş duran top hazırlığı ve gol arası oyunda değildir. Olay sınırında sınıflandırma belirsizliği en fazla verilen bir adımdır. Kontrollü top, uçuş ve boştaki top süreleri oyunda kalma süresini böler. Uzun, örneklenmemiş manuel aralıklar ayrı kaydedilir.

Hücum bölümleri gerçek kazanım, duran top çıkışı, ölçüm başladığında sürmekte olan sahiplik veya aynı takımın şut dönüşü kontrolü kökenlerini taşır. Başlangıç anındaki bir alım teması ile yerleşmiş kontrol ayrı kayıtlarıdır: normal kontrol onayı en az 0,15 sn süreyle top merkezinin 1,45 m içinde ve 0,65 m altında olmasıyla veya gerçek çıkışla oluşur. Gerçek kafa teması ayrı fiziksel temas kanıtıdır. Fiziksel şut bölümü bitirir; şutun gol/kurtarış/blok/dışarı sonucu sonraki olaylarda ayrı çözülür.

| Aşama | Kaydedilen gözlem |
| --- | --- |
| Top kazanımı | Gerçek karşı takım kazanım teması; kontrol onayı ayrıca tutulur |
| Baskıdan çıkış | Başlangıçta 4 m'den yakında saha rakibi bulunması gerekir; kontrollü top ve en yakın rakibe en az 5 m mesafe 0,50 sn sürer |
| Hat kırma | Gerçek başlangıç/çıkışta önde ve 12 m yanal bantta en az iki rakip kimliği dondurulur; kontrol en az 2 m ilerler ve her iki rakibin hem eski hem güncel derinliğini en az 1 m geçer |
| Son bölge | Takım yönüne göre fiziksel top x konumu en az 52/3 m; olağan örneklemede 0,15 sn kontrollü varış |
| Ceza sahası | Takım yönünde x en az 35,5 m ve mutlak z en fazla 20,16 m; aynı gerçek kontrol/temas kuralı |
| Şut | Gerçek ayak çıkışı veya gerçek kafa şutuyla şut sayısının artması; hazırlık sayılmaz |

Hat kırma, ölçülebilir geometrik bir yaklaşımdır; sertifikalı formasyon/hat tanıma değildir. Bölge başında başlayan bir hücumun giriş kaydı `at-start` olarak ayrılır. `stageCounts` bütün gözlenen kayıtları, `eligibleReached/stageEligibility` başlangıçta zaten ileride olanları dışlayan ölçüm penceresi ilerlemesini verir. Bunlar otomatik sıralı huni sayılmaz; doğal profil onaylı kazanım kökenlerini baskı/hat uygunluğuna göre ayırarak sıralı yolları ayrıca çıkarır.

Son aşama sıralamada ulaşılan en ileri aşama olur; aynı karede daha erken bir aşamanın sonradan doğrulanması bunu geriye düşürmez. Gerçek bitiş nedeni ile gözlemsel açıklama ayrı saklanır. Rakip kontrolü, pasın rakibe geçmesi, dışarı, ofsayt, mücadele/kontrol toparlama sonrası kayıp, duran top, gol ve şut çıkışı olay kayıtlarıdır. Destek hedefine yakınlık (3 m), bekleme süresi/kararı, hareketsiz kontrol, atanmış hücum koşusu görevi/ceza sahasında görülme ve hazırlık iptali ek kanıttır. Destek yakınlığı açık ve uygulanabilir pas garantisi değildir.

Rapor sorgusu aktif hücumu bitirmez. Ölçüm sonunda süren kayıt `pending`, maç/pencere sınırında gözlenemeyen devam `censored` olarak ayrılır; taktik başarısızlık tablosuna eklenmez. Paydası sıfır oran `null`, ekranda `—` olur. Ayrıntılı bölüm/şut sınırı ve bölüm içi gözlem kesilmesi raporda açıklanır; toplamlar korunur. `summary()` canlı ekrana toplamlar ve son kayıtları, `report()` JSON dışa aktarmaya ayrıntıları verir.

`attack-analysis-ui.js` rapor okur; oyuncu/AI durumuna yazmaz. `match3d.js` gözlemci yaşamını maç başlatma/yeniden başlatma ile yönetir. Her yeni maç eski kancaları kaldırıp yeni sayaçlarla başlar. Fiziksel motor, kayıt şeması ve günlük lig sonucu hesabı bu tanılama için değiştirilmez.

Tam doğal izler standart JSON'un deterministik gzip arşivi olarak, okunabilir özet ayrı JSON olarak yayımlanır. Arşiv ve açılmış içerik için SHA-256, kaynaklar ve gözlemci/plain/tekrar doğrulamaları özette korunur; sıkıştırma ayrıntı atmaz. Rapora yazılan üretim saati deneyin ölçüm paydası değildir. Doğal örneklem ile seçilmiş kontrollü kapsam, sayaç veya kalite oranında birleştirilmez.

Kaynak sınırı: `football-sim.js` SHA-256 değeri `b29a8f9b49638ec6559bc58df6b9504400eaaaf3b44bd14439d4643c3bd394f3` olarak aynı kalır. Gözlemci `259e977f…`, arayüz `5aaa31a8…` ayrı kaynaklardır; tam özetler test ve tarayıcı raporlarında bulunur.


`boxRunnerCommands/boxRunnerArrivals` ham adları korunur: ilk alan box-run/cutback-support/channel-run/penetration görevlerini, ikinci alan bu görevlinin ceza sahasında en az bir kez görülmesini sayar. Görev hedefi kutu dışında olabilir ve oyuncu zaten ceza sahasında bulunabilir; yeni giriş veya kutuya koşu başarı oranı çıkarılmaz.

Son doğal deneyin [okunabilir özeti](docs/validation/attack-chain-summary.json), 8 × 300 sn × iki motorda gözlemci/plain/tekrar ve descriptor kontrollerini doğrular. [Tam JSON.gz](docs/validation/attack-chain-matrix.json.gz) bütün bölüm ve şut izlerini korur. İki motorda dört şut, farklı oyunda kalma süreleriyle 10 dakika başına yaklaşık 1,185/1,218 toplam şuttur. Bu, motor davranışı değişikliği veya denge kabulü değildir; aşama/olay tanımlarıyla mevcut davranışı açıklar.

---

# Dokuzuncu aşama — görev yaşamı, dört evre ve oyuncu algısı

Destek, verkaç/bindirme, taşıma, pres ve markaj tek bir hedefi tekrar seçmekten öte bir görev yaşamına bağlandı. `team-intent.js` görev süresini ve geçişi, `player-perception.js` rakibin hangi gözlemden bilindiğini yönetir. İki modül CommonJS ve tarayıcı UMD olarak yüklenir; `match.html` bunları `football-sim.js` öncesinde açar. Yeni durum yalnız maç belleğindedir.

## Takım evresi ve ortak görev dönemi

`teamPhases[team]`, `phase`, `since`, `epoch` ve `attackEpoch` taşır. `win`/`possession` hücum; `loss`/`defence` savunma ailesidir. Gerçek karşı takım kazanımı hücum dönemini değiştirir ve eski görevleri gain/loss gerekçeleriyle bırakır. Aynı takım alımı bu dönemi değiştirmez. Geçiş süresi bitince uyumlu görev yeni evrede sürer; başlangıç ve kesin bitiş saatleri yenilenmez. Yeniden başlatma geçiş saatlerini, eski planları, görevleri ve gözlem belleğini temizler.

`resolve`, `reserved` ve `clear` ortak görev protokolüdür. `p.task`; amaç/alt durum, evre/dönem, ortak ve odak kimlikleri, hedef, tempo, öncelik, başlangıç, asgari devam, kesin bitiş ve ilerleme bilgisini taşır. Son **24 geçiş gerekçesi** `taskHistory` içinde kalır. Yeni plan aynı görevin kesin bitişini sürekli ileri atmaz.

| Görev | Asgari devam | Kesin ömür | Olağan yeni adayın doğrulanması |
| --- | ---: | ---: | ---: |
| Destek | 0,50 sn | 1,80 sn | 0,32 sn |
| Koşu / bindirme | 0,70 sn | 3,20 sn | 0,36 sn |
| Pres | 0,45 sn | 1,40 sn | 0,32 sn |
| Markaj | 0,60 sn | 2,10 sn | 0,36 sn |
| Kademe | 0,50 sn | 1,80 sn | 0,32 sn |
| Taşıma | 0,45 sn | 1,20 sn | 0,28 sn |

Hareketli markaj/pres hedefi aynı kimlikle takip edilir; bağlılık eski bir rakip konumuna koşmayı zorlamaz. Aynı görevin temposu ve önceliği güncel öneriden gelir. Görünür yol tıkanması, ortak/odak kaybı, oyuncu değişimi, evre ailesi değişimi, görev sonu, varış ve ilerleyememe ayrı bırakma gerekçeleridir. Acil kontrol/alıcı koşusu/blok ve ortak takım devri olağan beklemeyi aşabilir. Destek hedefine **0,85 m** yaklaşmak varış sayılır; kesin ömrü aşmadan **0,45 sn** kullanım penceresi başlatır. Güvenlik ve acil görevler bu pencereyi de kesebilir.

Plan kurucuları bağlı oyuncuyu aday seçmeden önce rezerve eder. Aktif verkaç/geri destek niyeti ceza sahası dağılımıyla ezilmez. Pas hedefi hem hazırlık hem gerçek uçuş sırasında ayrılır; iptal sonrası alıcı görevi bırakılır. Son görev seçildiğinde destek, koşucu, bağlantı, bindirme ve ceza sahası tabloları uygulanacak hedefle uzlaştırılır. Pas değerlendirmesi oyuncunun koşmadığı yeni bir aday noktayı açık bağlantı gibi kullanmaz. Markaj ve pres devrinde eski görev sahibi asgari süreyi bekleyerek ikinci markajcı/presçi olarak kalmaz.

## Görüş ve kısa gözlem belleği

Gözlem yalnız canlı `step` içinde ilerler. `rivals(p,time)` yeni tarama veya canlı rakip okuması yapmadan değer kopyaları döndürür; rakibin hedefini veya gelecekteki kararını taşımaz. Görüş niteliğine bağlı gövde görüşü/menzil, **1,65 m** yakın temas duyumu, uygun aksiyonlar arasında deterministik **160 ms** baş taraması ve en fazla **1,60 sn** bellek vardır. Görülmeyen rakibin hareket kestirimi, son hızdan **0,40 sn** sönüm ufkuyla çıkar; güven azalır, belirsizlik artar ve süre sonunda kayıt silinir. Kör taraftaki yeni yön değişimi bu kestirimi güncellemez. Belirsizlik pas yolu/alıma güveni de sınırlar.

Takım koordinatörü saha oyuncularının gözlemlerinin birleşimini kullanır; takım iletişimi anlık varsayılır. Bireysel markaj ancak o oyuncunun gözlemlediği adaylar arasından seçilir. Top taşıyanın baskı ve tempo okuması da kişiseldir. Pres biriminin alıcı seçimi ve önceki alıcıyı koruma hesabı aynı gözlenen kökene dayanır: kademe/presçinin belleğindeki top sahibi, kayıt yoksa topun ortak konumu. Derindeki markaj devri, topun BallPhysics ile 0,70 sn sonraki konumuna uzanan koridorda koşucunun bulunmasını okur; pasçının özel hedef oyuncu kimliğini okumaz. Şut bloku görünür şutçunun gövde yönünü, uçuş savunması görünen topun fiziksel izini okur; rakibin özel nişan/pas hedefi kullanılmaz.

Hazırlık önizlemeleri karar verenin bildiği rakip kopyalarını ilerletir; görünmeyen canlı rakip sonradan eklenmez. Önizlemede baş taraması, yeni takım planı veya RNG çalışmaz. Görev ve tarihçe kopyaları canlı duruma geri yazılmaz. Doğrudan elle kurulan ve henüz `step` çalıştırılmamış kontrol durumları açıkça verilen dünya durumunu kullanır; normal canlı maç adımı algıyı etkinleştirir.

## Baş çizimi ve kalan kapsam

Rig, algının baş taramasını yalnız çizim için yumuşatarak en fazla **±0,80 rad** baş dönüşüne çevirir; prosedürel yüz ve GPU baş/boyun kemikleri bunu kullanır. Algıdaki **±1,55 rad** tarama ile görsel baş açısı farklı oyun yaklaşımlarıdır. `p.face`, gövde, ayaklar ve temas noktaları etkilenmez. Önbelleklenmiş pozun çizim sorgusu taramayı ilerletmez.

Görüş engellenmesi, sesle fark etme, ayrıntılı dikkat bütçesi ve gecikmeli/sınırlı takım iletişimi henüz yoktur. Topun konumu ve sahiplik/oyun bilgisi ortak maç durumundan gelir; kendi takımının pozisyon ve komutları bilinir. Bu aşama bu bilgileri ayrı bir top/arkadaş algısına dönüştürmez. Fiziksel temas/müdahale, ofsayt hakemi, şut/ilk kontrolün gerçek temas baskısı, duran top yerleşimi ve mevcut kaleci yolları dünya gerçeğini kullanır. Görülmeyen rakip fiziksel müdahaleye devam eder; algı eksikliği koruma sağlamaz. BallPhysics ile 16 canlı fizik/kural yöntemi yayımlanmış sekizinci aşamayla kaynak düzeyinde aynı kalır; değişen görev/algı ve hazırlık önizlemeleri bu eşitlik iddiasına dahil değildir. Ekonomi, kayıt şeması ve ayrı günlük lig motoru birleştirilmedi.

---

# Sekizinci aşama — ortak yerden ayak teması ve sonraki kontrole erişim

Önceki ilk kontrol kapısı topun mevcut ayak bölgesini, yedinci aşama ise alım sonrasındaki dar bir ters bekleme kararını sınırlandırıyordu. Topa bugün erişilmesi, oyuncu mevcut yönde koşarken seçilen her yeni top hızına yetişebileceği anlamına gelmiyordu. `touchContact`, `touchRecovery` ve `touchPlan` artık hazırlıklı yerden ilk kontrol, normal top sürme/top koruma ve açık oyun vuruş hazırlığında ortak kullanılır. Yönün uygulanabilirliği, mevcut hız ve gövdeyle bir sonraki gerçek temas bölgesine ulaşma denemesinden çıkarılır.

## Temas, ayak ve saatler

`touchContact` topu oyuncunun gövdesine göre ileri/yanal bileşenlere ayırır. Mevcut kontrol bölgesi merkezden en fazla **1,20 m**, ileri bileşen en az **−0,18 m**, mutlak yanal bileşen en fazla **1,00 m** olur. Yanal top konumu sol/sağ ayağı seçer; merkeze yakın top tercih edilen ayağı kullanır. Vuruş hazırlığı seçilmiş `kickFoot` ile sınanır. Seçilen ayağın ±0,18 m yanal merkezine göre erişim de denetlenir; erişilemeyen çapraz ayak teması reddedilir. Teknik hesabında tercih edilen ayak, dribbling ve zayıf ayak niteliği korunur. İnaktif veya mücadeleden toparlanan oyuncu hazır temas üretemez.

Top sürmenin `touchClock` saati ile bir ayağın fiziksel toparlanması ayrıdır. Taşıma/koruma yeni dokunuş için top sürme ritmini ve `receiveClock` süresini bekler. Pas hazırlığı ise `receiveClock` ile seçilmiş ayağın saatini bekler: son dribbling ayağı aynıysa mevcut `footTouch` değeri, diğer ayaksa sıfır kullanılır. Dribblingin **0,14 sn** ayak temas saati sürerken aynı ayakla hazırlık yapılamaz; boş diğer ayak veya toparlanmış aynı ayak, daha uzun dribbling ritmi bitmeden pas hazırlayabilir. Bu saat tam bir basış, destek ayağı ve eklem modeli değildir.

## Tek sonraki temas için sınırlı fizik tahmini

`touchPlan` önce mevcut ayak erişimini ve gerekli saatleri denetler. İstenen top hızını; ardından mevcut gelen hız ile istenen hız arasındaki farkın **%75, %50 ve %25** uygulandığı adayları sırayla dener. İlk yetişilebilir aday kullanılır. Tam istek uygulanabiliyorsa sayısal değerleri aynen korunur. Hiçbiri uygun değilse yeni yön darbesi uygulanmaz; top fizik altında devam eder ve kısa süre sonra yeniden denenir. Erteleme mevcut kontrol saatini kısaltmaz.

Her `touchRecovery`, oyuncu ve top kopyasında gerçek `move`/`effort` ve `BallPhysics.step` ile gelecekte en fazla **0,65 sn / 39 adet 60 Hz hareket adımı** yürütür. İçinde bulunulan canlı karenin ayrıca işlenecek top adımı aşağıdaki faz sırasına göre eklenir. Sonraki kullanılabilir kare, gerçek saatlerdeki tekrarlı `max(0, saat − 1/60)` hesabıyla bulunur; küçük pozitif saatler hazır sayılmaz. Geçersiz hız/poz, inaktif oyuncu, fazla ufuk ve gerçek vuruş sahibi bulunmayan setup sorgusu reddedilir. Taşıma sırasında 3,2 m, setup sırasında 2,4 m kontrol kaybı sınırının aşılması sonradan vaat edilen bir temasa çevrilmez.

Mevcut sahip komutu kullanılır; yenileme gerektiğinde aynı taşıma/alım/koruma niyetinin normal takip hedefi ve temposu hesaplanır. Oyuncu, gerektiğinde topun güncel konumu ve 0,12 sn hız uzantısını izler. Arkadaşların gözlenen hızları normal kaçınma hesabına, rakiplerin gözlenen konum/hızları mevcut baskı hesabına girer. Yeni taktik karar, ilave dokunuş, gizli rakip komutu veya RNG çağrısı yoktur. Canlı oyuncu, top, hedef Map ve saatlere yazılmaz. Sonraki kararlar ve omuz temasları tahmini bozabilir; hazır sonuç topa sahip olma veya rakipten kaçma garantisi değildir.

## Canlı kare sırası ve gerçek vuruş

Taşıma/koruma darbesi, o karenin oyuncu hareketinden sonra ve top integrasyonundan önce gelir. Tahmin bu ilk top adımını işler; gelecekteki hareket/top adımlarını izleyip sonraki ayak denemesini **top integrasyonundan önce** gözler. İlk kontrol `acquire` içinde, mevcut karenin top integrasyonundan sonra gelir; bu yüzden fazladan başlangıç top adımı eklenmez. Alım tahmini kopyaya gerçekleşecek `receive` aksiyonunu da uygular; eski bir pas animasyonu oyuncuyu tahminde donduramaz. Setup tahmini de darbeden sonraki mevcut top adımını, ardından gelecekteki hareket ve top adımlarını işler; hazırlanmış vuruşu **top integrasyonundan sonra** değerlendirir. `time` ve `ballTime` bu faz farkını açıkça taşır.

Hazırlıklı `pass`/`through`/`cutback` yerden alımında mevcut temas uygunsa yönlü ilk kontrol ortak sorguyla sınanır. Yetişilemeyen çıkışta mevcut yavaşlatma darbesi kalır, `receiveMode` cushion olur ve eski `nextAction`/`oneTouchUntil` temizlenir. Gerçek alım veya rakibin araya girmesi zorlanmaz. Top sürme ve koruma aynı sorgudan dönen hız darbesini uygular; oyuncu veya top yeni hedefe taşınmaz.

Açık oyun vuruş hazırlığında top seçilmiş ayağın bölgesinde değilse oyuncu normal ivme/frenle gerçek topa yaklaşır ve sınırlı hızla ona döner. Sonraki hazırlık darbeleri de aynı modelden geçer. Gerçek çıkış için mevcut temas noktası farkı **0,11 m'den**, yön hatası **0,07 rad'dan** küçük olmalı; seçilmiş ayak erişilebilir, o ayağın saati ve `receiveClock` sıfır, top yüksekliği **0,45 m'den** küçük olmalıdır. Hızlı devam etiketi bu kapıları kaldırmaz. Rakip müdahalesi normal sırada çalışır; geç veya uzak hazırlık iptal olabilir. Vuruş sonrası uçuş BallPhysics'e aittir.

## GitHub birleşimi, kanıt ve kapsam

GitHub `main` kaynağı `82414b9`, uzak alıcının önce koşu yönünü koruyup top yakına geldiğinde veya geliş süresi dönüş bütçesine girdiğinde gövdeyi açmasını getiriyordu. Bu davranış, `through` kapsamı ve gelen topa göre **±π/3** açıklık korunarak yerel uçuş kimliği/tazelik/yerden temas kapıları ve tahmin bağlamındaki saat ilerlemesiyle birleştirildi. Önceki belgelerdeki 1 radyanlık erken açıklık anlatımı tarihsel sürüme aittir.

Üç ayrı kaynak saklanır: yerel yedinci aşama, GitHub kaynağı ve fizik değişikliğinden önceki birleşik taban. Ortak dokunuş testleri/profili sonuncuyu kullanır; Git HEAD veya uzaktaki daha eski fizik sürümü tek başına taban sayılmaz. Dosyalar ve tam SHA-256 değerleri [baselines/README.md](docs/validation/baselines/README.md) içindedir. İki uzaktaki tarihsel doğrulama raporu da korunmuştur.

`npm run test:stage8` toplam **154 test** çalıştırır: önceki aşamalar ve dört uzlaştırılmış alıcı yönü senaryosu dahil **119**, ortak model için **35**. Yeni testler canlı dokunuşla sonraki temasın poz/hız/gövde/top sonucunu doğru kare fazında birebir karşılaştırır; iki yön, zayıf/serbest/meşgul ayak, saat sınırları, eski alım aksiyonu, müdahale ve gerçek vuruş kapılarını kapsar. Genel maç metriklerine ilişkin sonuçlar ve sınırlamalar [DOGRULAMA.md](DOGRULAMA.md) içinde ayrı değerlendirilir.

Bu aşama yerden ayak kontrolünü birleştirir; kafa topu, kaleci eli ve duran top/taç prosedürlerini yeniden yazmaz. Mevcut fizik ve hareket katsayıları ölçülmüş biyomekanik değildir. Yeni alanlar yalnız geçici maç durumudur; kayıt dönüşümü, ekonomi veya günlük lig şeması değişikliği gerekmez. Önceki aşamalar aşağıda tarihsel kayıt olarak korunmuştur.

---

# Yedinci aşama — alımdan sonraki ters bekleme kararının uygulanabilirliği

Altıncı aşama gelen topa açık gövde hazırlığını iyileştirmişti; buna rağmen bir alımdan kısa süre sonra seçilen ters yönlü `hold` kararı, oyuncunun mevcut momentumu ve topun bağımsız hareketiyle çatışabiliyordu. Bu aşama ilk kontrol darbesini değiştirmez. Seçilmiş kararın normal hareketle yaklaşan müdahaleye açıldığı dar durumda, hâlâ geçerli önceki taşıma hedefiyle karşılaştırır.

`postReceiveHold(p, choice)` salt okunur bir karar sorgusudur. Yeni yol yalnız şu koşullar birlikte sağlandığında çalışır:

- Seçilen karar sonlu x/z noktası olan `carry` ve `hold` olmalıdır. Oyuncu aktif, kaleci olmayan gerçek sahip olmalı; duran top veya süren vuruş bulunmamalıdır.
- `lastGain` aynı oyuncuya ait ve yaşı **0–1,5 sn** olmalıdır. Gerçek alımdaki `receiveMode`, `open` veya `protect`; kontrol saati bitmiş olmalıdır. Bu kapı pas türünü yeniden sınıflandırmaz; yalnız bu modlarda yapılmış yakın geçmiş alımları kapsar.
- Önceki `carryIntent.until` hâlâ gelecekte olmalı; sonlu `carryTarget` oyuncudan en az **0,8 m** uzakta bulunmalıdır. Top yüksekliği **0,45 m'den**, oyuncu-top farkı **1,45 m'den** küçük olmalıdır.
- Gözlenen hız en az **0,8 m/sn**, yeni hedefin yönüyle mevcut hız yönü arasındaki fark en az **1,1 rad** olmalıdır. Yakın rakip **5,5 m'den** az uzakta olmalı veya **10 m** içinde göreli kapanma hızı **0,75 m/sn** üzerinde bulunmalıdır.

Kapsam dışındaki karar, aynı nesne olarak geri döner. Pas, şut, feint ve bekleme olmayan taşıma seçimleri bu sorguyla yeniden sıralanmaz. Güvenli bir bekleme de aynen korunur; eski hedefin niyet süresi bittiğinde yalnız önceki yön olduğu için kullanılmaz.

Önce seçilen `hold`, mevcut `controlPreparation(p, choice, null, .75)` ile değerlendirilir. Bu yardımcı kopya oyuncu/top üzerinde normal `move`, `dribbleTouch`, `tackleAccess` ve BallPhysics akışını 60 Hz'de yürütür. Seçilen beklemede müdahale erişimi görülmezse karar korunur. Görülürse önceki hedefe normal taşıma komutu, aynı **0,75 sn / 45 adım** ufkunda sınanır. Devam yolunda müdahale görülmemesi ve en az bir gerçek `dribbleTouch` oluşması gerekir. Dokunuş görülmeyen, yalnız boşta kalmış top güvenli devam kabul edilmez.

Uygun devam, eski hedefin değer kopyasıyla `carry`, `commit: .35` ve `holdContinuation: true` döndürür. `hold` kaldırılır; normal `startCarry` bu niyeti uygular. Gerçek `step` içinde sorgu, sahip kararından sonra ve normal karar saati/RNG hesabından önce çağrılır. `telemetry.holdContinuations` yalnız seçilen devam sayısıdır; kazanılan veya kaybedilmeyen top sayısı değildir. Oyuncu ve top taşınmaz, müdahale kapatılmaz; gerçek hareket, dokunuş ve sonraki kararlar normal motor tarafından belirlenir.

Sorgu canlı oyuncu, top, saat, hedef Map, niyet veya RNG'ye yazmaz. `controlPreparation` mevcut gözlenen rakip konumu/hızını kullanır; gizli rakip komutları ve gelecekteki taktik plan çalıştırılmaz. Tahmin yeni bir geleceği bilmez: rakibin sonraki tercihi, arkadaş/omuz temasları ve sonraki komut değişimleri sonucu bozabilir. Önizlemede müdahale görülmemesi gerçek top koruma garantisi değildir; en fazla 0,75 saniyeyi ve tek aday komutun sürmesini kapsar. Yeni seçimden sonra başka bir karar yine top kaybına yol açabilir.

Mevcut yöntemlerden yalnız `step` değişmiştir; `postReceiveHold` eklenmiş, diğer **95 Match yöntemi** ve BallPhysics korunmuştur. `controlPreparation`, alım, vuruş, gövde dönüşü, ayak temas bölgesi ve müdahale yöntemleri aynıdır. Yeni bağımlılık veya kalıcı kayıt alanı yoktur. Taban, önceki turun yerel kaynak ve ZIP görüntüsüyle byte düzeyinde kontrol edilen `docs/validation/baselines/stage6-football-sim.js.gz` dosyasıdır; açılmış SHA-256 değeri `108d47253d775de6638460d5fa90dd6bbe2ab2e1e066b581e17591350c4917b6` olur. Bu, kullanıcının ayrıca yayımladığının doğrulandığı anlamına gelmez. Git HEAD eski yüklemeyi gösterir.

Kontrollü ve doğal karşılaştırmalar ile ölçüm sınırları DOGRULAMA başındadır; önceki aşamalar aşağıda tarihsel kayıt olarak korunmuştur.

---

# Altıncı aşama — alım öncesinde gelen topa açık gövde

Beşinci aşama, gerçek temas ayak bölgesinin dışındaysa yönlü kontrolü erteliyordu. Buna rağmen `move`, alım koşusundaki oyuncuyu koşulsuz olarak `reception.face` çıkış yönüne döndürüyordu. Böylece hazırlık, yaklaşan topu gövdenin arkasında bırakabiliyordu. Bu aşama çıkış niyetini değiştirmeden yalnız alım koşusunun gövde hedefini sınırlar.

`receptionFacing(p)` salt okunur bir sorgudur. Yeni yol yalnız aktif, kaleci olmayan seçili alıcıda çalışır: `flight.target.id === p.id`, pasör aynı takım, tür `pass` veya `cutback`, hazırlığın `flightId` değeri aynı ve yaşı `0 ≤ time − at < 0,55 sn`, top `y ≤ radius + 0,01 m` ve `|vy| < 10⁻⁶ m/sn` olmalıdır. Duran top veya `kick.restartContext` bulunmamalıdır. Kapsam dışındaki alım koşusu eski `reception.face` değerini kullanır; kaleci, ara pas, hava topu, diğer alıcı ve eski/geçersiz hazırlık için yeni yön hesabı yapılmaz.

Geliş yönü, oyuncudan **mevcut gerçek top konumuna** bakış açısıdır; pasör konumu veya top hızının tersi değildir. Çıkış niyeti ile bu açı arasındaki fark en fazla 1 radyansa sorgu sayısal olarak da aynı `reception.face` değerini döndürür. Daha büyük farkta hedef, gelen top yönünden çıkışa doğru en fazla 1 radyan açılır. Bu, anında uygulanan gövde dönüşü veya başarılı kontrol garantisi değildir. `move` mevcut 4,5 rad/sn dönüş sınırını, hızlanma/fren, enerji, kondisyon ve arkadaşlardan kaçınma hesabını uygular. Gövde yönü hareket hızını da etkileyebildiği için alıma yetişme ve sonraki kararlar değişebilir.

`reception.face`, `next` ve kontrol noktası çıkış niyeti olarak korunur. Gerçek `acquire` anında beşinci aşamanın `firstControlContact` kapısı aynen çalışır; geç hazırlık hâlâ `cushion` kontrolüne düşebilir. Gerçek alım yarıçapı, rakip müdahalesi ve top fiziği değişmez. Hazırlıklı hızlı devam, normal `preparedChoice` → `startKick` → `kickStep` yolundan geçer; çıkış için süre, dönüş ve ayak-top teması gerekir.

`projectPlayer` aynı sorguyu kopya hareketinde kullanabilmek için mevcut uçuşu salt okunur biçimde ve projeksiyon saatini bağlama taşır. Her adımda saat `this.time + elapsed`, top ise önceki hareket anına uygun olarak `BallPhysics.predict(this.ball, elapsed − dt)` olur. Böylece gövde hedefi, topun ilerlemesi ve hazırlığın tazelik süresinin bitişi kopyada da uygulanır. Canlı oyuncu, top, hedef Map, uçuş veya RNG değiştirilmez; rakip komutları ve gelecekteki takım planı okunmaz. Mevcut tahmin ufukları ve adım bütçeleri korunur.

Yeni sorgu dışında değişen mevcut yöntemler yalnız `move` ve `projectPlayer` olur; diğer **93 yöntem** ve BallPhysics aynı kalır. Yeni bağımlılık, kalıcı kayıt alanı veya ekonomi/lig değişikliği yoktur. Taban, önceki teslimin tam kaynağını içeren `docs/validation/baselines/stage5-football-sim.js.gz` (`70387789…`) dosyasıdır; Git HEAD eski yüklemeyi gösterir.

Bir radyan açıklık oyun katsayısıdır; anatomik ayak veya gövde modeli değildir. Sorgu mevcut top konumunu izler, gelecekteki temas konumunu veya rakibin sonraki hamlesini bilmez. Komut değişimi, omuz teması ve topun oyuncuyu geçmesi hazırlığı bozabilir. Ara pas/hava topu kontrolü, baskı altında çıkış puanları ve sonraki hücum tercihi bu dar aşamada yeniden yazılmaz. Testler ve olumlu/olumsuz doğal sonuçlar DOGRULAMA başındadır; aşağıdaki aşamalar tarihsel kayıttır.

---

# Beşinci aşama — temas anında ilk kontrol

Önceki motor, hazırlıklı alıcıya merkez/süpürme temasından sonra seçilmiş yöne doğrudan ilk dokunuş verebiliyordu. Aynı top konumu `dribbleTouch` tarafından arkada veya fazla yanda olduğu için reddedilse bile bu dokunuş uygulanıyordu. Hazırlanmış hızlı pas da gerçek temas yönüne bakılmadan 0,045 sn kontrol saati alıyordu. Bu aşama yalnız bu tutarsızlığı sınırlar; anatomik ayak/çarpışma modeli getirmez.

`firstControlContact(p)` mevcut top/oyuncu konumundan gövdeye göre ileri ve yanal uzaklığı hesaplar. Mevcut dribbling ayak bölgesi kullanılır: merkez uzaklığı ≤1,20 m, ileri bileşen ≥−0,18 m, mutlak yanal bileşen ≤1,00 m. Sorgu canlı durumu değiştirmez; RNG, gelecek plan veya rakip komutu okumaz.

Kontrol yalnız şu gerçek `acquire` anında uygulanır: hazırlık aynı flight.id'ye ait ve 0,55 sn'den yeni, oyuncu seçilmiş alıcı ve kaleci değil, tür pass/through/cutback, top y ≤ radius+0,01 ve düşey hız yaklaşık sıfır. Önceki 1,10 m seçilmiş alıcı süpürme yarıçapı ve gerçek alım koşulları korunur. Bölge dışı temas alımı garanti eden veya engelleyen yeni bir kapı değildir; alımdan sonra hangi kontrolün uygulanabildiğini sınırlar.

Ayak bölgesi uygunsa eski yönlü kontrol veya hızlı devam aynen çalışır. Uygun değilse, motorun zaten uyguladığı hız/teknik/baskı/gövde yönüne bağlı yavaşlatma darbesi korunur. Seçilmiş kontrol noktasına ek yönlendirme yapılmaz. Hazırlığın yerel kopyası `cushion` moduna geçer; nextAction ve oneTouchUntil temizlenir. Sonraki karar normal kontrol süresinden önce alınmaz. Gövdenin topa yönelmesi için saat, `clamp((açı−0,9)/4,5,0,0,45)` ile bulunan süreye kadar uzatılabilir. 0,9 rad yönelme payı ve 0,45 sn tavanı oyun katsayılarıdır; fiziksel hazır olma garantisi değildir.

Kontrol saati sürerken normal sahip planı güncel top konumu + 0,12 sn hız uzantısını izler. Oyuncu `move` içindeki gerçek hızlanma/fren/dönüşle ilerler. Saat bitince bu özel takip biter; normal karar, vuruş hazırlığı ve gerçek ayak-top temas koşulları devam eder. `receiveClock` boyunca `doTackle` çalışır; dokunulmazlık yoktur. Topun konumu temas nedeniyle değiştirilmez, yalnız hızı değişir; sonraki hareket BallPhysics'e aittir.

Yeni alanlar yalnız geçici maç davranışı/telemetrisidir: firstControlChecks, cushionedReceives ve firstControlDeferrals. Yeni kayıt şeması veya bağımlılık yoktur. Değişen mevcut yöntemler yalnız `acquire` ve `plan`; 92 diğer yöntem ve BallPhysics aynı kalır. Aynı dar kapsam dışındaki kontrol davranışı saklanmış dördüncü aşamayla karşılaştırılır.

Hazırlıktaki `one-touch` etiketi hâlâ hızlı devam niyetidir; gerçek tek temaslı duvar pası garantisi değildir. `startKick` normal dönüş/hazırlık ve gerçek teması bekler. Yeni kontrol, ayak bölgesi içindeki keskin çıkış açılarını, uçuş boyunca erken dışa dönmeyi, hava topu/kaleci/serbest top kontrolünü veya sonraki gizli kararları çözmez. Eski yavaşlatma darbesi de ölçülmüş bir biyomekanik model değildir. Doğal karşı örnekte gecikme top kaybına yol açar; fiziksel kısıt her durumda daha iyi sonuç demek değildir.

Karşılaştırma tabanı `docs/validation/baselines/stage4-football-sim.js.gz` (`406526af…`) içindeki son yayımlanmış kaynaktır. Git HEAD eski yüklemedir. Ölçüm ve olumsuz sonuçlar DOGRULAMA başındadır; aşağıdaki aşamalar tarihsel kayıttır.

---

# Dördüncü aşama — fiziksel alım koşusu

Önceki `interceptPoint`, topu 0,1 sn adımlarla ilerletip `mesafe < 0,7 + üstHız × süre` olan ilk noktayı seçiyordu. Bu koşul, duran/ters yöne giden/yorgun oyuncunun hemen üst hızla doğru yöne koşabildiğini varsayıyordu. Hiçbir nokta uygun görünmezse 2,4 sn sonundaki top noktası sınıra kırpılıp döndürülüyordu. Alım koşusu bu uzak hedefe aniden dönebiliyordu.

## Dar kapsam ve aday seçimi

Yeni yol yalnız aktif, kaleci olmayan seçili alıcı için çalışır: flight.target oyuncunun kendisi, pasör aynı takım, tür pass veya cutback, top yere yakın (`y ≤ radius + 0,01`) ve düşey hız yaklaşık sıfır olmalıdır. Duran top, diğer oyuncu/savunmacı, kaleci, serbest top ve diğer uçuş türleri eski hesapta kalır. Kapsam dışında kalan taktik/fizik davranışları yeniden yazılmadı.

`receiverInterceptPoint` aynı BallPhysics ile 0,1–2,4 sn arasında en çok 24 aday üretir. Topun tahmini x/z değeri gerçek 52/34 m çizgilerinin dışına çıkarsa sonraki adaylar aranmaz. Mevcut hız ve en yüksek yürütülebilir koşu hızından gevşek bir üst sınır, açıkça uzak adayları yalnız hesap yükünü azaltmak için eler; bu sınır alıma yetiştiğini kanıtlamaz.

Kalan her aday için oyuncunun kopyası, o sabit noktaya receive-run/pace 1,13 komutuyla gerçek `move`/`effort` üzerinden 60 Hz'de ilerletilir. Gerçek hızlanma, fren, dönüş, enerji, kondisyon, feint ve duel toparlanması kullanılır. Temas/toparlanma saati o aday anına kadar bitmeli ve tahmini gövde/aday yatay farkı en fazla **0,7 m** olmalıdır. Bu koşulları sağlayan ilk **sınanan** aday seçilir; daha erken bir ara anda başka bir temas mümkün olabilir.

0,7 m bir planlama payıdır. Gerçek seçili alıcının 1,10 m swept temas yarıçapı değiştirilmedi. `reachable:false`, sınanan komutların bu temkinli payı karşılamadığını söyler; topun gerçekten alınmasının imkânsız olduğunu kanıtlamaz. Bu durumda fiziksel olarak sınanan en küçük farkın noktası, gerekirse statik en yakın aday da sınanarak döndürülür. Bu nokta da sahiplik veya başarılı alım sayılmaz. Önceki destek hesabı böyle yakın bir geliş için hazırlanabilir; gerçek owner yalnız normal temasla değişir.

## Ortak tahmin ve maliyet

Üçüncü aşamanın hareket tahmini gövdesi `projectPlayer` yardımcısına taşındı. Onun azami sınırı 2,4 sn'dir; `receiverAt` çağrıları **1,6 sn**, `passReceiverAt` çağrıları **0,45 sn** sınırını korur. Kendi oyuncu/arkadaş kopyaları kullanılır, arkadaşlar gözlenen hızla ötelenir. Rakip komutları, gelecekteki taktik plan ve RNG okunmaz. Canlı top/oyuncu/komut/seed'e yazılmaz. Yeni bir kalıcı önbellek veya kayıt alanı yoktur.

Aday hedefler farklı olduğu için her adayın hareketi başlangıç durumundan yeniden sınanır. Her sorgu en fazla 1800 hareket adımıyla sınırlıdır; gevşek sınır ve ilk uygun adayda çıkış tipik maliyeti azaltır. `plan`, seçili alıcının buluşma sonucunu **bir kez** hesaplayıp destek ataması, receive-run hedefi ve alım hazırlığına aynı yerel nesneyi iletir. Üç bağımsız pahalı arama yapılmaz. Bu, sorgunun gerçek maçta önceden hareket yürütmesi anlamına gelmez; bütün hareket yalnız kopyadadır.

## Korunan davranış ve sınırlar

BallPhysics, move/effort uygulaması, vuruş/şut dağılımı, gerçek release/temas/alım/müdahale gövdeleri korunur. Topa uçuş sırasında yeni yön verilmez ve oyuncu taşınmaz. Alım niyeti başarısız olabilir; gerçek rakip müdahalesi aynı kurallarla çalışır. Taktik genişliği, pas/tempo, bek/çapa ve önceki destek görevleri bu yeni koşunun çevresindeki normal planlamayı sürdürür.

Tahmin aday komutunun kısa süre sürmesine dayanır. Gerçek planda sonraki komutlar, ilk kontrolün gövde yönü, takım arkadaşı kaçınması ve omuz ayrıştırma temasları değişebilir. Örneklenmiş yatay fark ile gerçek swept temas aynı metrik değildir. Bu aşama savunmacı/GK kesişme zekâsını veya hava topu alımını iyileştirdiğini iddia etmez. Kayıt biçimi ve ekonomi/lig/ödeme kodu değişmez. Doğal düzeltmenin yanında çoklu maçtaki kötüleşmeler DOGRULAMA başında açıkça tutulur.

---

# Üçüncü aşama — bilinen durma/dönüş komutundan alıcı hedefi

Sorun: normal pas seçimi ve `kickStep`, `receiverPoint` üzerinden alıcının mevcut hızını top uçuşuna kadar uzatıyordu. Önceki durma noktası istisnası yalnız support/build-support/return-support içindi; shape gibi bilinen yerleşim komutları bu sınırı kullanmıyordu. Doğal örnekte alıcı z≈−0,032 noktasına yaklaşırken pas z≈2,008'e yöneldi. Gerçek vuruş yön hatası yaklaşık 3,4 cm iken top alıcının 1,394 m uzağından geçti. Sorun hedef/koşu tahminindeydi; topun uçuşunu sonradan düzeltmek gerekmiyordu.

## Sınırlı fiziksel tahmin

`receiverPoint` süreyi 0–1,6 sn ile sınırlar. Alıcı aktif, komutun x/z/pace değerleri sonlu ve pace negatif değilse; komut restart/wall/goal değilse ve hız >0,2 m/sn ise yakın hedef okunur. Yakınlık kapısı:

`hedef mesafesi < hız × süre + hız² / 22 + 0,5 m`

Bu kapı, kısa uçuşta yaklaşılabilecek nokta ile mevcut 11 m/sn² fren hesabının durma mesafesini kapsayan bir seçim sezgisidir; matematiksel güvenlik sınırı değildir. Uzak koşu, bilinmeyen/geçersiz komut, duran top ve hareketsiz alıcı için eski hız uzantısı kalır. Böylece her uzun koşuya gelecekteki komut biliniyormuş gibi davranılmaz; hesap yükü de yakın durma/dönüşlerle sınırlanır.

Yakın durumda `receiverAt` ortak yardımcısı, oyuncu kopyasına gerçek `Match.move` ve `effort` uygular: 60 Hz adımlar, gerçek hızlanma/fren/dönüş, kondisyon/enerji, toparlanma ve aynı takımdan yakın oyunculardan kaçınma. Her çağrı en fazla 1,6 sn/96 adım. Arkadaş kopyaları gözlenen hızla ötelenir; rakibin komutları veya sonraki taktik plan çalıştırılmaz. Topun kopyası mevcut BallPhysics ile ilerler. Canlı oyuncu, top, hedef Map, seed ve gözlemlere yazılmaz.

Eski `passReceiverAt` artık ortak yardımcıyı çağırır ama kendi **0,45 sn** sözleşmesini korur. Böylece ilk aşamanın çıkış öncesi alıcı okuması genişletilmez. Önceden ilerletilmiş bir alıcı kopyası tahmin edilirken aynı id'li gerçek oyuncu arkadaş listesine tekrar sokulmaz; sahte bir kendinden kaçınma oluşmaz.

## Karara ve fiziksel temasa etkisi

Sonuç, seçili oyuncunun tahmini gövde noktasıdır. Hızlı koşucu kısa durma hedefini aşabilir; hiçbir yerde hedef noktasına yapıştırılmaz. Bu yeni nokta mevcut pas puanlarını, tek pas hazırlığını, inceleme tahminini ve vuruş öncesi hedef yenilemesini etkileyebilir. Ara pas adaylarının taban puanı da değişebildiğinden seçilen pas **türü** ve gerçek vuruş **zamanı** farklılaşabilir. Doğal örneğin yeni dalı bir ara pas seçmiştir; aynı pasın sadece açısı düzelmiş gibi sunulmaz.

`startKick`, gerçek dönüş, hazırlık dokunuşları ve ayak/top temas kapılarını uygulamaya devam eder. `release` sonrası hedef hesabı topa uygulanmaz. BallPhysics, vuruş gücü/dağılımı, savunma müdahalesi ve alım yarıçapı değiştirilmedi. Müdahaleye karşı dokunulmazlık eklenmedi; kontrollü karşıtta savunmacı iki sürümde de pası keser.

## Devam eden sınırlar

Alıcının sonraki komutu bilinmez; tahmin mevcut komutun sürmesine dayanır. Uçuş başladıktan sonra alıcı normal receive-run davranışına geçebilir. Mevcut interceptPoint, tempo tabanlı iyimser erişim hesabını kullanmaya devam eder; gerçek hızlanma/dönüş ve baskıyla her zaman örtüşmez. Rakip/arkadaş temasları, yeni görevler ve zayıf ayak hatası hâlâ kaçırılan top yaratabilir. Uzak koşularda atılan ilk hızlanma adımları bu dar değişikliğin kapsamına alınmadı.

Yeni alanlar kayıt biçimine eklenmedi. Taktik tercihlerinin puan/yerleşim etkileri, ikinci aşamanın görev devri ve ilk aşamanın riskli son çare yolu korunur. Farklı doğal yolların toplam skorundan genel gerçekçilik sonucu çıkarılmaz. Ayrıntılı test/olumsuz sonuçlar DOGRULAMA başındadır.

---

# İkinci aşama — alıcıya destek ve baskı altında devam pası

Bu aşama ilk aşamanın yayımlanan motoru (`cb35f481…`) üzerine uygulanır. İlk aşamanın kodu ve raporları altta tarihsel olarak korunur. Yerel maç yine tek `Match` durumunu çizer; günlük lig/ekonomi ayrı kalır.

## Uçuş sırasında hazırlanan destek

Eski `supportUnit`, sahiplik yokken pasörün destek noktalarını taşır, alıcı olan yardımcıyı çıkarır ve planın süresi dolunca destekleri bırakırdı. Yeni dal, kendi takımının hedefli pass/through/cutback/long-pass uçuşunda alıcının `interceptPoint` noktasını kullanır. Bu nokta gerçek BallPhysics ile mevcut top yörüngesinden hesaplanır; karşı takımın komutları okunmaz. Uçuş 2,4 sn'den eskiyse, buluşma 1,2 sn'den geç/alıcının 8 m ötesindeyse veya top 3 m'den yüksekse bu destek tahmini kurulmaz. Orta/şut için mevcut ceza sahası görevleri korunur.

Yalnız destek hesabı için bir alıcı kopyası yaratılır; gerçek `owner` hâlâ null'dır. Ortak `supportTargets` en fazla iki yardımcı seçer, mevcut risk/alan/seyahat/histerezis hesabını kullanır. `supportLead` (0–1,2 sn), top yoldayken yardımcının hazırlanabileceği süreyi mevcut baskı penceresine ekler. Oyuncular yalnız gerçek `move` ivme, fren ve dönüş sınırlarıyla hareket eder. Kopyanın konumu gerçek oyuncuya yazılmaz; topa yönlendirme veya bonus temas eklenmez.

Plan `ownerId=alıcının kimliği` ile her geçerli uçuş planında yenilenir. Böylece eski pasörün 1,3 sn'lik süresi dolduğu için alıcının desteği düşmez. Aynı alıcı gerçekten topu aldığında aynı kimlik/epoch ve açık açı histerezisi devam eder. Hedef değişince eski alıcı teklifleri temizlenir; rakip kazanımı veya duran top mevcut epoch/temizleme yoluyla planı kaldırır.

## Görev çatışmaları

Mevcut koşucu, verkaç/geri destek, bindirme, ceza sahası ve sabit çapa rezervasyonları destek seçiminden önce ayrılır. Merkez stoperler yeni yardımcı yapılmaz; `fullbacks:hold` bekleri de destek için yukarı çekmez. Alıcının yanında ileri alanda çapa korunur. Geçerli alım destekleri, son uçuş planından itibaren en fazla 1,2 sn `handoffUntil` taşır. Bu kısa sürede yeni coordinatedAttack/buildOutSupport/flankSupport/boxAttack ataması aynı yardımcıyı hemen başka göreve çekmez. Süre uzatılmaz; koridor kapanırsa yardımcı hedefi normal risk hesabıyla yeniden seçilebilir veya düşebilir. Bu koruma oyuncuya değil, görev atamasına aittir; müdahale engellenmez.

`prepareReception` artık yeni `targets` atandıktan sonra normal görüşe bağlı yenileme hızında çalışır. Sonraki pas/ilk kontrol okuması kendi takımına henüz verilmiş komutları görür; gelecekteki takım/rakip planını çalıştırmaz.

## Hazır desteği gerçek pas kararına bağlama

Mevcut net şut, orta, yüksek değerli ara pas ve verkaç öncelikleri korunur. Sonraki kısa alım penceresinde, yakın baskı (<5,5 m) veya gözlenen hızla yaklaşan rakip (<12 m, kapanma >0,75 m/sn) varsa, puanı pozitif ve zaten hedefinin 3 m yakınındaki yardımcı da değerlendirilir. Topla geçen en az 0,18 sn aranır. En yüksek puanlı hücum seçeneği hazır değil diye daha düşük puanlı açık destek göz ardı edilmez.

Yeni devam yolunda normal pas, koridor <0,35, alım riski <0,65 ve alıcı alanı >2,4 m koşulları aranır. En fazla iki aday, ilk aşamanın gerçek hazırlık/temas önizlemesi `passPreparation` ile sınanır. Sadece uygun aday yeni `supportContinuation` kararı olabilir; ilk aşamanın riskli son çare istisnası burada kullanılmaz. Kontra talimatında bu yol 2 m'den fazla geri pası zorlamaz. Baskı yaklaşmıyorsa, görev penceresi dolmuşsa veya hazırlık yetişmiyorsa eski taktik karar sırası devam eder. Karar gerçek `startKick` ve temas gerektirir; otomatik tamamlama yoktur.

`arrivalSupportPlans/Samples/Handoffs` plan/örnek/devretme sayıları, `arrivalSupportChoices` karar ve `arrivalSupportReleases` gerçek çıkış sayısıdır. Bunlar kazanılmış top veya başarılı pas sayısı değildir. Yeni alanların tamamı geçici maç durumudur; tarayıcı kayıt anahtarı ve SQLite şeması değişmez.

## Sınırlar

Varış tahmini, destek riski ve kısa hazırlık bilinen top hareketi/gözlenen rakip hızına dayanır. Yeni komutlar, diğer oyuncuların sonraki tercihleri ve ayrıştırma temasları tahmini değiştirebilir. Bu aşama her pası veya bütün rol/kadro modelini yeniden yazmaz. İlk gerçek devam pasının tamamlanması üçüncü pasın başarılı olmasını garanti etmez; ölçülen doğal örnekte sonraki pas rakibe aut vuruşu bıraktı. Kanıt ve olumsuz sonuçlar DOGRULAMA başındadır.

---

# İlk aşama — pas alternatifinin uygulanabilirliği

Yerel akış: `tactics-page.js`/`manager.js` → kadro/taktik yapılandırması → `Match` (`football-sim.js`) → `match3d.js` → `scene3d.js`/`humanoid-rig.js`. Sabit 60 Hz motorun gerçek top/oyuncu konumları çizilir. Gol düzlemi geçişi `Match.score` üretir; görüntü ayrı bir sonuç senaryosu oynatmaz. **Günlük lig ayrıdır:** `server.py:outcome` hâlâ tohumlu Poisson/katsayı hesabıyla sonuç verir. Bu aşamada ekonomi ve lig kayıtlarına dokunulmadı.

## Sorun ve yeni karar sırası

Eski `reviewPass`, koridoru/resepsiyonu uygun ve dönüşü 2,2 rad altında olan ilk alternatife doğrudan `startKick` yapıyordu. Dönüş sınırı hazırlık için gerçekten zaman bulunduğunu göstermiyordu. Yeni sıra:

1. Mevcut v1.27 inceleme kapıları korunur: değişen/süregelen koridor tehlikesi, görüşe bağlı tepki, son 0,12 saniyedeki bağlılık ve 0,9 saniyelik yeniden karar bütçesi.
2. Aynı alternatif listesi `passPreparation` ile okunur. Gerçek `startKick`, `move`, `kickStep`, `contactPoint`, `BallPhysics` kullanılarak 60 Hz'de en fazla 0,75 saniyelik izole hazırlık yürütülür. Süre sabit bir dönüş formülünden ibaret değildir; geciken temas ve ek hazırlık dokunuşları da hesaba girer.
3. Pas ancak gerçek temas koşullarına ulaşırsa (ayak/top <0,11 m, yön <0,07 rad), öncesinde tahmini erişilebilir müdahale yoksa ve çıkışta koridor <0,35/resepsiyon <0,65 risk koşulları sağlanırsa aday kalır. Bunlar mutlak başarı garantisi değil, mevcut eşiklerin gelecekteki temas konumuna uygulanmasıdır.
4. Uygun adaylar mevcut `passOptions` taktik puanından `contactTime × (2 + tempo/25)` çıkarılarak sıralanır. Kısa/dikine pas, oyun planı ve top kazanımındaki kontra tercihleri mevcut seçenek üretiminde kalır; tempo geç hazırlanan seçeneğin maliyetini artırır. Çelişkide fiziksel uygulanabilirlik önceliklidir; tempo bir adayı fiziksel olarak uygun ilan etmez.
5. Uygun aday yoksa mevcut `carryOption`/`shieldOption` için `controlPreparation` çalışır. Gerçek `move`/`dribbleTouch`/`tackleAccess` ile, adayların temas süresine eşlenen 0,15–0,75 saniyelik sınırlı bir kontrol projeksiyonu yapılır. `startCarry`, normal kararlar ile bu geri dönüşün aynı süreli top koruma bütçesini kullanmasını sağlar. İmpuls yalnız kopyadaki veya gerçek `dribbleTouch` anında uygulanır; karar gerçek top/oyuncuyu taşımaz.
6. Kontrolün topu **daha erken** erişilebilir müdahaleye açacağı tahmin edilirse, koridor/resepsiyon koşulları iyi kalan ama hazırlık sırasında müdahale riski taşıyan bir alternatif son çare olarak seçilebilir. Seçilen adayın müdahale zamanı kontrolünkinden en az bir fizik adımı daha geç olmalı; müdahale–temas farkı en iyi olan aday önceliklidir. Bu bir **riskli acil çıkış**tır (`emergency:true`), uygun/güvenli pas diye etiketlenmez ve hiçbir müdahale kapısını atlamaz. Böylece yalnız riskli pası iptal etmek uğruna daha erken top kaybına dönülmez. Daha güvenli tahmin edilen kontrol varsa riskli alternatif elenir.

## Bilgi ve müdahale sınırı

Önizleme gerçek oyuncu, top, komut ve gözlem nesnelerine yazmaz; seed değiştirmez ve rastgelelik çağrısı hata verir. Kendi takımının mevcut komutları yürütülür. Rakip komutları/gelecek planı okunmaz; yalnız gözlenen konum, hız, yön, toparlanma ve kısa ivme eğilimi kullanılır. Rakibin yeni bir kararı tahmini bozabilir.

`tackleAccess`, eski `doTackle` geometrisini ve toparlanma/gövde/top koruma kapılarını yan etkisiz hesaplar. Gerçek müdahale aynı erişimden sonra aynı rastgele temiz müdahale/faul hesabını çalıştırır. Önizleme bir müdahalenin **denenebileceğini** risk sayar; kazanılmış top uydurmaz. Top koruma dokunulmazlık sağlamaz. Gerçek `kickStep` içinde müdahale, inceleme ve vuruştan önce kalır.

Önizlemede omuz ayrıştırma itmeleri ve gelecekteki takım planı yoktur; kendi komutları sabit varsayılır. Tahmin ufku kısa ve sınırlıdır. Bu aşama başlangıçtaki bütün pas kararlarını, şutları, duran topları veya tek pası değiştirmez; yalnız mevcut pas yeniden değerlendirmesinin alternatiflerini süzer. Beklenmeyen baskıda başarısızlık mümkündür.

`lastPassPreparation` son adaylar, süreler, riskler, seçim ve geri dönüşü tutar; `passPreparationChecks/Rejects` değerlendirme sayısıdır, kurtarılan top sayısı değildir. `passEmergencyOutlets` riskli son çare sayısını, `control` kontrolün ilk dokunuş/müdahale tahminini tutar. Alanlar `reset` ile temizlenir; kayıt biçimleri değişmez. Pas sonrasında mevcut verkaç/geri destek mekanizması korunur. Bu devamlılığın kalite iyileştirmesi henüz uygulanmadı.

Aşağıdaki v1.27 açıklaması tarihsel tabandır; yeni test kanıtları `DOGRULAMA.md` başındadır.

---

# v1.27 — Hareketli alıcı ve pas tahmini

v1.26'nın normal yerden pas inceleme kapıları aynıdır: hedefli, duran top/tek dokunuş olmayan, en az 0,30 saniyelik hazırlık; mevcut risk en az 0,75 ve başlangıçtan en az 0,30 yüksek; görüşe bağlı tepki süresi; son 0,12 saniyede bağlılık; fiziksel müdahaleden sonra inceleme; aynı alternatif/kontrol ve 0,9 saniyelik yeniden karar bütçesi.

## Alıcıyı çıkış anına ilerletme

passReceiverAt yalnız seçilen kendi takım arkadaşının mevcut targets komutunu okur. Rakibin komutu veya gelecekteki planı okunmaz. Süre 0–0,45 saniye ile sınırlıdır; sonlu olmayan süre sıfır alınır. Komut eksikse veya restart/wall/goal durumundaysa eski hızla ilerleme varsayımı korunur.

Bilinen komutta alıcı kopyası, en fazla 1/60 saniyelik adımlarla gerçek Match.move ve Match.effort üzerinden ilerletilir. Böylece mevcut motorun hızlanma/frenleme, dönüş, hız, kondisyon/enerji, rol ve yakın takım arkadaşlarından kaçınma hesabı yeniden kullanılır. İlgili toparlanma, reaksiyon, kontrol, tutma ve eylem saatleri yalnız kopyada ilerler. Yakın arkadaşlar, gözlenen hızlarıyla ötelenen kopyalardır; onların gelecek komutları yeniden çalıştırılmaz. Top, hareket adımından önceki zamana normal BallPhysics ile tahmin edilir.

Kopya bağlamında owner/kick/restart boş, players yalnız kendi takımının kopyalarıdır. Normal hareket kodu gerçek maç nesnesine yazmaz; RNG kullanmaz. Gelecekte m.plan çağrılmaz. Kopya, mevcut komutun kısa süre sürmesi varsayımıdır; takımın sonraki kararını önceden bilmez.

receiverPoint, isteğe bağlı açık komut alabilir. Normal çağrıların varsayılan hesabı aynıdır. Kopya alıcının konumu/hızı ve tahmini vurucu konumundan uçuş süresi yeniden hesaplanır; bu alıcıya receiverPoint çağrılır. Böylece zaten öne hesaplanmış eski pas noktasına sadece bir kez daha hız eklemek yerine, çıkış anındaki tahmini gövdeden yeni hedef üretilir.

## Birden fazla hedef varsayımı

passReleaseRisk, mevcut alıcı komutuyla hesaplanan hedefi nominal nokta olarak kullanır. Önceki sürümün mevcut hedef+hız uzantısı da alternatif olarak korunur; iki noktanın ortası ayrıca okunur. receiverSpread bu noktaların metre cinsinden ayrımıdır. nominalRisk, coastRisk ve midRisk aynı tahmini ayak başlangıcından, aynı rakip hareket tahmini ve normal yerden top yasasıyla değerlendirilir. Yeni risk bunların en yükseğidir.

Yalnız üç örnek nokta incelenir; bütün olası hedefleri veya yolları kapsayan matematiksel bir güven sınırı değildir. Bir varsayım güçlü tehlike gösterdiğinde, başka bir varsayımın açık olması incelemeyi tek başına bastıramaz. Bütün okunan riskler 0,75 altındaysa ve mevcut temas güven koşulu sağlanıyorsa önceki erteleme kararı mümkündür. Bu eşiğin altı risksiz pas demek değildir.

Vurucunun kendi yaklaşma projeksiyonu, 60 Hz en erken temas zamanı, rakibin gözlenen ivme tahmini, ayak/top 0,11 m ve yön 0,07 rad güven koşulları v1.26 temeliyle sürer. Nominal hedef değiştiğinden tahmini yüz/ayak konumu buna göre hesaplanır. Gerçek vuruşun yön, temas veya top hızı sonradan yönlendirilmez.

## Gözlem ve sınırlar

Eski sayaçlar aynıdır; risk varsayımları, alıcının tahmini x/z/vx/vz değerleri, receiverPlanned, receiverSpread ve coastPoint son tahmin kaydına eklenir. Bunlar başarılı pas veya kurtarılan top sayısı değildir. tools/profile-pass-release.cjs aynı kaynakla v1.26 kayıtlarını ve yeni v1.27 maçlarını gözler. Eski kayıtların kaynak/gözlemci hash'leri doğrulanarak tekrar kullanılabilir.

Yeni tools/profile-receiver-fork.cjs, bilinen doğal hata anından hemen önceki durumu structuredClone ile iki sürüme kopyalar. Oyuncu, hedef Map, top ve vuruş kimlik ilişkileri korunur; aynı RNG durumundan özgün inceleme birer kez çalıştırılır. Ardından dört saniyelik normal fizik ve müdahale izlenir. Bu tanı aracında --baseline-root ile önceki sürüm klasörü verilmelidir. Sonuç zorlanmaz; her iki dalda da kayıp varsa açıkça kaydedilir.

Yeni tools/verify-match-parallel.cjs, eski seri doğrulayıcının measure fonksiyonunu byte düzeyinde aynı tutar ve bağımsız senaryoları yalıtılmış Node worker'larına dağıtır. Maç içindeki adım sırası veya RNG değişmez. Önceki raporun üç girdisi ve senaryo anahtarları kontrol edilir; doğal gözlemcili skor/şut da yeni matrisle karşılaştırılır.

Çekirdek farkı receiverPoint'in açık komut parametresi, passReceiverAt ve passReleaseRisk hedef/risk hesabıdır. Bu bölgeler geri alındığında v1.26 kaynağı birebir elde edilir. Gerçek hareket, top/şut/kaleci fiziği, reviewPass politikası, rig, çizici, taktik ve ekonomi kaynakları korunur. Kaynak kanıtı previews/source-validation-v127.json; önceki mimari docs/ARCHITECTURE-v1.26.md içindedir. EA referansı FIFA_REFERANSI.md içinde, kullanılan algoritma Tribün'e aittir.
