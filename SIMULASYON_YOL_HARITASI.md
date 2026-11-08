# Gerçek futbol deneyimi: durum analizi ve geliştirme yol haritası

## Dokuzuncu aşama uygulama durumu

Bu aşama **`codex/team-continuity-perception` inceleme dalı** olarak hazırlanmıştır. Ortak görev/algı işlevi ve regresyonlar tamamdır; doğal maç dengesi kabulü beklediğinden `main` için varsayılan sürüm olarak sunulmaz.

Karar ve takım görevi devamlılığı için ortak yaşam kuralları, dört takım evresi ve oyuncu başına gözlem belleği uygulandı. Destek, verkaç, bindirme, pres ve markaj; amaç/ortak, asgari devam, yeni aday doğrulaması ve kesin görev ömrüyle sürer. Aynı takım alımı görev dönemini sıfırlamaz. Güvenli hazır desteğe kısa kullanım penceresi tanınır; tehlike, gerçek temas ve ortak görev devri önceliklidir. Pas ve koşu tabloları son uygulanacak görevle uzlaştırılır.

Kişisel rakip okuması görüş, baş taraması ve kısa belleği kullanır; kör taraftaki yeni konum değişimi doğrudan okunmaz. Markajcı kendi gözlemine göre seçilir. Takım koordinatörünün ortak görüntüsü hâlâ anlık iletişim varsayar. Görüş engelleri, ses, dikkat bütçesi ve iletişim gecikmesi açık geliştirme alanlarıdır. Baş taraması çizilirken gövde ve ayak temasları korunur.

**245 test**, BallPhysics/16 canlı yöntem kaynak koruması ve WebGL-prosedürel/2D tarayıcı kontrolleri geçti. Kanıt, karşılaştırma yöntemi ve sınırlar DOGRULAMA başındadır. Görev değişimlerinin azalması tek başına hazır bağlantıların daha çok kullanıldığı veya daha iyi hücum oluştuğu anlamına gelmez.

Dört 300 saniyelik son karşılaştırmada kısa topsuz görev değişimi 585/3529 (%16,58) → 389/3332 (%11,67) oldu. Büyük taşıma dönüşü sayısı 100 → 44 azalırken oranı %26,81 → %49,44 arttı; seçilmeden yeniden planlanan destek oranı %81,95 → %82,39 oldu. Top kaybı 27 → 59, tamamlanan pas 397/418 → 346/374, şut 2 → 1 ve yarıda kalan vuruş 1 → 3 oldu. Bu sonuçlar genel futbol/hücum kalitesi kabulü değildir.

`main` öncesindeki öncelik **hazır bağlantının gerçek pas ve pozisyona dönüşmesini, kör baskının fark edilmesini ve fiziksel hazırlık iptallerini birlikte kalibre etmektir**. Bağlılık süresini tek başına artırmak yerine yeni boşluğun kaçırıldığı ve topun kaybedildiği durumlar ayrıştırılmalı. Ardından süreler farklı taktikler ve zayıf/güçlü profillerde, daha uzun maçlarda yorgunlukla birlikte ölçülmeli. Kör baskının geç fark edilmesi hem fiziksel olarak etkili hem izleyici açısından okunabilir olmalı. Aşağıdaki eski aşama durumları ve genel plan tarihsel dayanak olarak korunur.

## Sekizinci aşama uygulama durumu

6 Kasım 2026: Yönlü ilk kontrol, top sürme, koruma ve açık oyun vuruş hazırlığı ortak ayak erişimi/sonraki temas hesabına bağlandı. Hesap gerçek hızlanma, fren, gövde ve top hareketini kısa süreli kopyada yürütür; seçilen ayağın temas süresini normal top sürme aralığından ayırır. Uygun olmayan darbe küçültülür veya ertelenir. Mevcut ayak noktası, mücadele ve serbest top korunur; tam anatomi/kuvvet/denge modeli tamamlanmış değildir.

154 test, 50 seçilmiş canlı fizik durumu ve iki tarayıcı çizim yolu geçti. GitHub'daki geç alıcı gövde hazırlığı korunarak oluşturulan tabana karşı sekiz kısa maçta top kaybı 119 → 60, hedef alımı 798/858 → 873/928 oldu; şut 5 → 4 ve yarıda kalan vuruş 0 → 4. Bu toplamlar genel hücum veya futbol gerçekçiliği kabulü değildir. Kaynaklar, aynı durumdan doğal örnek ve sınırlar DOGRULAMA başındadır.

Sonraki öncelik, ilk kontrol/taşıma adaylarını bu uygulanabilirlik bilgisiyle daha erken seçmek, hücum çeşitliliğini ve farklı oyuncu profillerini ölçmek, kısa ufuktan sonraki kayıpları izlemektir. Aşağıdaki genel planın fiziksel temelinde ilerleme sağlandı; diğer ürün/kurallar/lig hedefleri açık kalıyor.

## Genel planın hazırlandığı durum

6 Kasım 2026. Bu plan, yedinci aşama motorunun (`c1c1395a…`) kaynak incelemesine, son sekiz adet 300 saniyelik sentetik maçın raporlarına, mevcut 115 testin önceki sonuçlarına ve kaydedilmiş kısa Chromium kontrollerine dayanır. Bu analiz sırasında yeni maç/test koşulmadı; aşağıdaki hedefler uygulanmış özellik değildir. Mevcut ürünün menajer olarak kadro ve taktik belirleyip maçı izleme odağı esas alınmıştır.

## Ürün hedefi

Oyuncu, verdiği menajer kararının sahada nasıl uygulandığını ve pozisyonun neden böyle sonuçlandığını anlayabilmeli. Bunun için altı tutarlılık birlikte sağlanmalı:

1. Topa ulaşma, dönme, ilk kontrol ve vuruş fiziksel olarak uygulanabilir olmalı.
2. Takımların topla, topsuz ve geçişteki görevleri birbiriyle uyumlu sürmeli.
3. Oyuncu özellikleri ve taktik tercihlerinin farklı davranışları, bedelleri ve zayıflıkları olmalı.
4. Saha kuralları, hakem kararı, gösterilen istatistik ve görüntü aynı olayı anlatmalı.
5. İzlenen resmî maç ile lig/kariyer kaydı tek maçın sonucu olmalı.
6. Kamera, animasyon, ses ve cihaz performansı bu davranışların okunmasını sağlamalı.

Lisanslı oyuncu yüzleri, çok ayrıntılı stadyumlar, hava durumu, spiker ve geniş mocap repertuvarı sonraki kalite katmanlarıdır. İlk kabul için bunların tümü zorunlu değildir. Mevcut rig, IK, ses ve kamera temelleri değerlendirilerek ilerlenmeli.

## Mevcut güçlü temel ve kanıtın sınırı

- Sabit 60 Hz maç çekirdeği, bağımsız top, tahmin ile canlı uçuşun ortak BallPhysics kullanması, dönüş/hazırlık/ayak teması bekleyen vuruşlar var.
- Destek, verkaç, bindirme, pres/kademe, markaj devri, kaleci görüş/tepki ve tutuş/dalış davranışları var.
- Prosedürel rigde ayak kilidi, IK, vuruş hedefi, ilk kontrol, kafa ve kaleci pozları; üç kamera ve sentez tribün/düdük sesi var. Ayrıntılı model için GPU skinning/LOD kodu da var; özgün varlıklar bu checkout'ta eksik.
- Aynı durumdan dallanma, deterministik tekrar ve gözlemcili/gözlemcisiz tam durum eşitliği güçlü doğrulama araçlarıdır.
- Son örneklemde 885 pas, 848 tamamlanan pas, 5 şut ve 104 top kaybı var. Yedinci aşama yalnız bir kısa pas senaryosunda bir kararı değiştirdi; önceki toplam kayıp 105'ti.
- Doğal matriste geriye çıkarma, ofsayt ve kaleci tutuşu sıfır; kafa bir, çalım iki kez sayılmıştır. Bu, ilgili özelliklerin yokluğu/bozukluğu kanıtı değil, doğal örneklemin kapsam açığıdır.
- Sekiz 5 dakikalık maç, 90 dakikalık futbol dengesi veya gerçek telefon performansı kanıtı değildir. Mevcut tarayıcı kontrolü yaklaşık 15 saniyelik açılış/ilerleme/duraklatma kontrolüdür. 115 test, kapsadığı regresyonları sınar; bütün maçın seyir kalitesini ölçmez.

## Eksikler ve deneyime etkileri

| Alan | Kaynaktan doğrulanan durum | Deneyimde sorun | Geliştirme yönü |
| --- | --- | --- | --- |
| Tam uygulamanın çalışması | Özgün data/assets yok; statik maç açılabiliyor, sunucu transfer kuralları/kataloğu istiyor | Yerel maç, transfer ve günlük lig bir ürün olarak denenemiyor | Eksiksiz kurulum, açık örnek veri modu, sağlık kontrolü ve anlaşılır eksik veri durumları |
| Maçın tek gerçeği | `server.py:outcome` Poisson/katsayı kullanıyor; yerel `Match` ayrı fiziksel maç yürütüyor | İzlenen pozisyonlar lig sonucunu açıklamıyor | Ortak maç motoru, fikstür kimliği, iki kadro, seed, motor sürümü ve olay kaydı |
| Başlangıç görüntüsü | Fikstürde kalıcı başlama kadrosu/taktiği yok; sonuçlandırma güncel takım kaydını okuyor | Sunucu gecikmesinde geçmiş maç girdilerinin kayması riski | Başlama anında değişmez maç girdileri; yeniden başlatma ve geç sonuçlandırma eşitliği |
| Dokunuş/momentum | `dribbleTouch` erişim kapısından sonra top hızını hedefe göre yeniden yazıyor; genel çıkış açısı uygulanabilirliği eksik | Gövde/koşu bir yöne giderken top keskin biçimde başka yöne açılabiliyor | İlk kontrol, taşıma ve vuruş hazırlığında ortak temas/çıkış sınırları |
| Karar devamlılığı | `choose` çok sayıda öncelik/eşik içeriyor; yeni koruma yalnız dar bir ters hold durumunu kapsıyor | Desteklenmiş koşu sonraki komutta bozulabiliyor | Ortak eylem uygulanabilirliği, niyet devri ve kontrollü yeniden değerlendirme |
| İkili mücadele | Erişim, küçük omuz ayrıştırmaları ve olasılıklı temiz müdahale/faul hesabı var | Temasın bedensel gerekçesi ve denge kaybı yeterince ayrışmıyor | Topa önce temas, ayak/omuz, denge ve toparlanma durumları; fiziksel imkânsızlık kapıları |
| Takım oyunu | Destek ve savunma sistemleri var; planlar arasında görev devri karmaşık | Hat kırma, üçüncü adam, ikinci top ve dinlenme savunmasının sürekliliği yeterince kanıtlanmıyor | Dört oyun evresi için açık görev öncelikleri ve taktik kimlik ölçümleri |
| Hücum üretimi | Şut/orta/ara pas seçimi var; son kısa maçlarda toplam beş şut | Hücumun hangi aşamada tıkandığı görünmüyor | Top kazanımı→hat kırma→son bölge→ceza sahası→şut zinciri ve başarısızlık nedenleri |
| Oyuncu kimliği | Pek çok özellik genel puan/indeksten türetiliyor; rakip kadro sentetik | Hızlı forvet, oyun kurucu, güçlü stoper gibi profiller yeterince ayrışmıyor | İki takımda aynı oyuncu şeması; aynı overall ile farklı fizik/teknik/zihinsel profiller |
| Kadro verisinin anlamı | Form/mevki uyumu ekran ve günlük güçte var; yerel motor bunları aynı sözleşmeyle uygulamıyor | Ekrandaki kalite farkının saha karşılığı belirsiz | Mevki, form, kondisyon ve rol etkisini tek tanımda fizik/karara bağlamak |
| Kurallar | Penaltı, avantaj ve doğrudan kırmızı akışı yok; devre yalnız olay mesajı | Temel futbol durumlarında oyuna güven zedeleniyor | Müsabaka kuralları ve maç yaşam döngüsü; penaltı, devre arası, yön değişimi, ek süre |
| Kale ve çizgiler | Merkez eşikleri kullanılıyor; direk/üst direk çarpışması yok | Çizgi üstü top ve kale çerçevesi gerçek futbol gibi davranmıyor | Tam top geçişi, sürekli kesişme, ortak saha/kale ölçüleri ve çerçeve çarpışması |
| Ofsayt | Pas anı işareti ve temasta düdük var; kafa pasında işaret listesi boş, aktif müdahale ayrımı sınırlı | Benzer pozisyonlarda farklı karar oluşabilir | Pas türleri, sekme/bilinçli oynama, rakibi etkileme ve istisnalar için tek kural katmanı |
| Hava oyunu/kaleci | Orta tipine/yükseklik bandına bağlı kafa, temel kaleci görüş/tepki var | Uzun top, sıçrama, göğüs/uyluk kontrolü ve farklı kurtarışların kalitesi belirsiz | Farklı hava temasları ve şut/kurtarış/ikinci top senaryoları |
| Menajer etkisi | Maçta hız/kamera/ses ve değişiklik var; canlı taktik arayüzü yok | Gelişen soruna taktik karşılık verme alanı dar | Az sayıda anlamlı canlı talimat, uygulanma zamanı ve sahadaki etkinin geri bildirimi |
| Bilgi doğruluğu | Momentum çubuğu topun x işaretinden 40/60 hedef üretiyor | Baskı üstünlüğü izlenimi gerçek ölçümle desteklenmiyor | Doğru adlandırma; açık tanımlı tehdit/bölge/şut ölçümleri ve anlamlı maç sonrası analiz |
| Görsel/sesli okunurluk | Kamera/rig/ses var; isim/radar/olay tekrarı ve temas sesi katmanları eksik | Kimin neden ne yaptığı veya temasın ne zaman olduğu zor okunabilir | Kamera/top/etiket yardımları, kayıt üstünden tekrar, temas senkronu ve ses katmanları |
| Kariyer devamlılığı | Yerel sonuç lig sonucunu değiştirmiyor; oyuncu bazlı maç yükü/kart/ceza/istatistik akışı birleşik değil | Rotasyon, oyuncu gelişimi ve sezon hikâyesi yeterince anlam kazanmıyor | Sonucun bir kez uygulanması; dakikalar, kondisyon, form, kart ve sezon istatistikleri |
| Uzun kullanım ve cihazlar | Kısa masaüstü kontrolü var; gerçek mobil ve uzun maç performansı ölçülmemiş | Akıcılık, ısınma, bellek ve bağlantı/kayıt davranışı bilinmiyor | Tanımlı cihaz matrisi, uzun maç, sekme/context kaybı, kayıt ve yeniden açma kabulü |

Bu bulguların kaynakları: `football-sim.js` içinde `dribbleTouch`, `choose`, `controlPreparation`, `postReceiveHold`, `doTackle`, `offsideTouch`, `aerial`, `ballStep`, `keeper`, `step`; `server.py` içinde fikstür şeması/`outcome`/`settle_due`; `manager.js` ve `tactics-page.js` maç konfigürasyonu; `match3d.js` içinde `metrics` ve kontroller; `humanoid-rig.js`, `scene3d.js`, `player-renderer.js`. Sayısal kanıtlar [DOGRULAMA](DOGRULAMA.md) ve `docs/validation/control-exit-*.json` içindedir.

## Aşamalı yol haritası

Sıralama bağımlılığa göredir. Ortak maç girdisi sözleşmesi sabitlendikten sonra fizik ve kurallar prototipleri, resmî lig entegrasyonunun tamamlanmasını beklemeden paralel ilerleyebilir. Resmî sonuca geçiş için ortak motor/olay eşitliği ayrıca kabul kapısıdır. Animasyon prototipi ve performans ölçümü de çekirdek çalışmalarıyla paralel ilerleyebilir. Ekip/varlık kapasitesi belirlenmeden takvim yerine gözlenebilir teslim ve kabul koşulları kullanılır.

| Aşama | Öncelik | Somut teslim | Tamamlanma ölçütü |
| --- | --- | --- | --- |
| 0. Çalışır ve ölçülebilir temel | P0 | Eksik veri/varlık durumu çözülmüş kurulum; sağlık kontrolü; doğru göstergeler; hücum ve kayıp izleri | Temiz kurulumdan kadro→taktik→maç çalışır; mevcut kayıt korunur; gerekli kaynaklarda 404 yok; örnek mod açıktır; gözlemci sonucu değiştirmez |
| 1. Ortak maç sözleşmesi | P0 | Oyuncu/takım/maç tanımı; iki kadro; başlama görüntüsü; sürümlü seed/komut/olay kaydı | Aynı fikstür/girdiler/sürümle başsız motor, görüntü ve lig aynı gol/olay/sonucu verir; kapalı tarayıcı ve geç sonuçlandırma sonucu değiştirmez |
| 2. Oyuncu–top ve ortak eylem değerlendirmesi | P0 | Yönlü kontrol/taşıma/koruma/bekleme/pas için fiziksel uygulanabilirlik ve niyet devamlılığı | İki yönde ve farklı hız/profillerde temas gerekçelidir; top/oyuncu ışınlanmaz; rakip müdahalesi korunur; aynı durumdan olumlu ve olumsuz dallar incelenir |
| 3. Futbol kuralları ve maç yaşam döngüsü | P0/P1 | Tam top/çizgi ve direk; penaltı; avantaj/kart; devre arası/yön değişimi; ofsayt ve müsabaka ayarları | Sınırda top, ceza sahası faulü, kafa pası ofsaytı ve yeniden başlatmalar kural senaryolarını geçer; görüntü/karar/istatistik aynıdır |
| 4. Takım kimliği ve pozisyon üretimi | P1 | Dört evrede görev devri; görüş/tarama/gözlem belleği; pres/kademe; üçüncü adam/ceza sahası/ikinci top; hava oyunu ve kaleci çeşitliliği | Aynı kadro/tohum eşleşmelerinde taktiklerin beklenen davranış farkı görülür; kör taraftaki yeni baskı tarama/tepkiye bağlı okunur; hücum zincirindeki tıkanma ölçülür; nadir olaylar ayrı sınanır |
| 5. Görüntü ve futbolun okunması | P1 | Doğrulanmış rig/model yolu; kritik hareket geçişleri; kamera/top/etiket yardımı; olay tekrarı; temas sesi | Vuruş/kontrol görseli otoriter olayla eşleşir; basış kayması ölçülür; kullanıcı top sahibini/alıcıyı okuyabilir; 2D ve 3D aynı maçı gösterir |
| 6. Menajer ve sezon döngüsü | P1 | Canlı taktikler; rol/kondisyonlu değişiklik; oyuncu bazlı sonuçlar; maç sonrası gerekçeli analiz | Talimat aynı maçta uygulanır ve kayda girer; maç yükü/kart/istatistik bir kez uygulanır; yenileme/yeniden açma mükerrer sonuç üretmez |
| 7. Tam maç, cihaz ve denge kabulü | P1/P2 | 5/15/90 dk ayrı doğrulama; tüm desteklenen dizilişler; profil/taktik matrisi; gerçek telefon ve kullanıcı gözlemi | Kritik kurallar ve kayıt hatasız; referans verisiyle davranış dağılımları değerlendirilmiş; hedef cihaz performansı ve anlaşılabilirlik kabulü geçmiş |

### Teknik omurga

- Mevcut motor, fizik/temas, kurallar, oyuncu algısı/eylemi, takım planı ve maç kaydı sınırlarıyla ayrılmalı. Sabit adım ve deterministik tekrar korunmalı.
- Uygulanabilirlik sorguları ortak gerçek hareket/temas yardımcılarını kullanmalı; önce ucuz eleme, sonra sınırlı adayda pahalı önizleme yapılmalı. Bütün futbolu tek uzun geleceğe kopyalayarak tahmin etmeye çalışılmamalı.
- Resmî maç girdileri ve taktik komutları sürümlenmeli. Yeni motor sürümü eski fikstürü farklı kurallarla sessizce yeniden hesaplamamalı.
- Sunum kaydı tüketmeli; skor veya top sonucunu ayrı bir görsel senaryo üretmemeli. Tekrar oynatma canlı RNG ve sonucu değiştirmemeli.
- Mevki/form/fitness, tercihi ayak, teknik/zihinsel ve fiziksel nitelikler kadrodan iki takıma da taşınmalı. Aynı overall farklı davranış profilleriyle sınanmalı.
- Derinlikli oyuncu algısı, görüş alanı/tarama/tepki ve gözlem belirsizliğiyle kademeli kurulmalı; mevcut kaleci görünürlük davranışı korunmalı.

## Ölçüm ve kabul paketi

### Futbol davranışı

- Pas ve alım: çıkış sayısı, hedefe gerçek alım, başka kendi oyuncusunun alması, rakip kesmesi, dışarı gidiş ve bekleyen uçuş ayrı olmalı.
- Top koruma: 1/2/5 sn pencereler, aynı hücumun sonu, serbest top süresi ve rakibe duran top ayrı ölçülmeli. Örtüşen pencereler benzersiz top kaybı gibi toplanmamalı; bekleyen pencere başarı sayılmamalı.
- Hücum: top kazanma bölgesi, hat kırma, ileri taşıma, son bölge/ceza sahası girişleri, şut hazırlığı, şut ve pozisyonun bitiş nedeni kaydedilmeli. Hem maç saati hem topun oyunda olduğu süreye göre oranlar incelenmeli.
- Takım şekli: blok yüksekliği, en/boy, hat aralıkları, yardımcıya erişim süresi, pres yönü, arka güvenlik ve ikinci top paylaşımı ölçülmeli.
- Kimlik: eşit overall ile farklı hız/denge/pas/görüş/ayak profilleri; iki takımda farklı kadro güçleri ve tüm desteklenen dizilişler karşılaştırılmalı.
- Şut, kafa, geriye çıkarma, ofsayt ve kaleci olayları doğal örneklemde azsa kontrollü durumlar eklenmeli. Doğal maçta görülen kalite ile kontrollü kapsam birbirinin yerine raporlanmamalı.
- Gerçek maç referansları süre, seviye ve istatistik tanımı eşleştirilerek kullanılmalı. xG şu an sezgisel puandır; kalibre edilmiş olasılık diye sunulmamalı. Gol/galibiyet kotası dayatılmamalı.

### Görsel ve kullanım kabulü — önerilen başlangıç hedefleri

- Kritik pas/şut/kontrol anında görsel temas ile motor olayı aynı kayıttan izlenmeli. Temas farkı ve ayak kayması kameraya/görüntü ölçeğine göre ölçülüp kabul eşiği belirlenmeli.
- Küçük bir kullanıcı grubuyla top sahibi, pas alıcısı ve son top kaybının nedeni sorulmalı. İlk ürün hedefi, örnek kritik anlarda katılımcıların en az %90'ının top sahibini/alıcıyı iki saniye içinde gösterebilmesi olabilir; bu mevcut sürümde ölçülmüş sonuç değildir.
- Başlangıç performans hedefi: tanımlı masaüstünde 1× hızda p95 kare süresi ≤16,7 ms; hedef düşük/orta telefonda ≤33,3 ms. Donanım, model yolu, çözünürlük ve kalite ayarı raporlanmalı. 4×/16× kullanım ayrıca ölçülmeli.
- En az gerçek iOS ve Android üzerinde dikey/yatay görünüm, dokunma, %200 metin büyütme, ses açma, sekme değişimi ve yeniden açma denenmeli. Uzun kullanımda bellek artışı ve ısınma izlenmeli.
- Ses kapalı, WebGL kapalı ve azaltılmış hareket tercihinde de skor/olay/karar bilgisi anlaşılır kalmalı. Tam paket ve kasıtlı eksik paket ayrı kabul yolları olmalı.

## Bir sonraki geliştirme paketleri

1. **Kurulum ve ölçüm:** kaynak/veri envanteri, çalışır tam örnek akış, dürüst momentum göstergesi, topun oyunda kaldığı süre ve hücum/kayıp nedenleri. Bu, sonraki değişikliklerin gerçekten neyi düzelttiğini görünür yapar.
2. **Ortak oyuncu ve maç girdileri:** iki kadro, gerçek özellik/rol aktarımı, hücum yönü, başlangıç görüntüsü, seed ve motor sürümü. Lig ile yerel maçın bağlanacağı sözleşme burada sabitlenir.
3. **Temas ve temel güven kuralları:** keskin yönlü ilk kontrol/taşıma için genel uygulanabilirlik; tam top çizgisi/direk ve penaltı senaryoları. Yeni dar istisnaların ortak değerlendirme yapısına taşınması hedeflenir.
4. **Tam bir oynanabilir kesit:** bir fikstürü gerçek iki kadroyla hazırla, izle, 2–3 canlı talimat ver, maçı bitir, sonucu lige uygula, ilgili pozisyonu tekrar izle ve kaydı yeniden aç. Sonraki özellikler bu akışın kalitesini artırmalı.

Doğrudan futbolcu kontrolü seçilecekse oyuncu değiştirme, koşu/pas/şut girdileri, yardımlar ve giriş gecikmesi için ayrı ürün/teknik plan gerekir. Şimdiki menajer deneyiminde bu özellik eksikliği tek başına kusur sayılmaz. Gerçek ödeme/reklam bağlantısı da futbol gerçekçiliğinin ön koşulu değildir.

---

# Önceki aşamaların tarihsel yol haritası

# Sonraki simülasyon geliştirmeleri

6 Kasım 2026, yedinci aşama: Alımdan sonraki kısa pencerede momentuma ters bekleme kararı, mevcut hareket/top/müdahale önizlemesiyle karşılaştırılıyor. Eski taşıma hedefinde yeniden dokunuş mümkün ve müdahale görünmüyorsa o hedef sürdürülüyor. Sekiz senaryoda yalnız short42'de bir karar değişti; toplam top kaybı 105 → 104. Önceki sorunlu karışık önekte ise kayıp yalnız 1,37 sn gecikti; beş saniye içinde yine gerçekleşti. Genel top koruma hedefi tamamlanmış değildir.

Güncel öncelik, yönlü ilk kontrolün kendisini ve bekleme dışındaki ani taşıma dönüşlerini gövde yönü, mevcut hız ve yeniden ayak temasıyla birlikte değerlendirmek. Şimdiki 0,75 sn önizlemenin sonrasındaki gerçek kayıplar, kaçınılmaz baskı ile yanlış devam kararı ayrı ölçülerek izlenmeli. Kanıtlar ve yeniden üretme komutları DOGRULAMA başındadır.

Aşağıdaki altıncı aşama ve v1.27 notları tarihsel kayıttır.

6 Kasım 2026: Altıncı aşamada hedefli yerden pas/geri pas alıcısı, gerçek dönüş sınırıyla gelen topa yarı açık hazırlanıyor. Dar temas kapsamında ayak uygunluğu 485/860 → 772/786 oldu; sekiz maçta toplam top kaybı 101 → 105 olduğundan top koruma hedefi tamamlanmış değildir. Ayrıntılar ve olumsuz aynı-durum örneği DOGRULAMA başındadır.

Güncel öncelik, yönlü ilk kontrol ve hızlı devam seçimini hazırlanmış gövde yönü, gerçek vuruş süresi ve yaklaşan rakibin müdahalesiyle birlikte değerlendirmektir. Özellikle daha iyi ayak temasından sonra 1–2 saniye içindeki top kayıpları ve rakibe duran toplar izlenmeli. Ara pas/hava topu hazırlığı ve tam arka eksendeki sol/sağ duruş kararlılığı sonraki ayrı kapsamlar olarak duruyor.

Aşağıdaki tablo özgün v1.27 yol haritasıdır; önceki aşamaların uygulanması bütün hedeflerin tamamlandığı anlamına gelmez.

v1.27, kendi alıcısının bilinen koşu komutunu gerçek hareket hesabıyla kopyada ilerletir ve farklı hedef varsayımlarının koridor riskini karşılaştırır. Bilinen hata örneğinde hedef tahmini düzelir; her iki gerçek karar dalında top kaybı sürdüğünden genel top koruma başarısı iddia edilmez.

| Sıra | Öneri | Aranacak davranış |
| --- | --- | --- |
| 1 | Yüksek preste ilk kararın uygulanabilirliği | Güvenli görünen alternatif için gereken hazırlık ve yaklaşan müdahale birlikte değerlendirilsin; doğru risk okuması sonrasında hücum fiziksel olarak sürdürülebilsin |
| 2 | Destek devamlılığı ve ikinci top | İlk çıkıştan sonra pas açıları, koşular ve seken top paylaşımı takım halinde yenilensin; herkes topa yığılmasın |
| 3 | Tahmin belirsizliğini genişletmek | Yeni komut, ani duruş/dönüş, yakın arkadaşlardan kaçınma ve geciken temasta yanlış güven ile gereksiz iptal ayrı ölçülsün |
| 4 | Taktik ve kadro çeşitliliği | Farklı rakip planları, güçte kadrolar, üçlü/beşli savunma ve eksik oyuncu örnekleri karşılaştırılsın |
| 5 | Duran top, temas ve cihaz kabulü | Şut/pas/orta tercihi; ayak/top/gövde teması ve kayma; gerçek tarayıcı/telefonda kesintisiz maçlar incelensin |

FIFA/EA FC'nin yayımlanmış oynanış hedefleri referanstır; mevcut kodun motor entegrasyonu veya aynı kaliteye ulaştığı iddiası değildir. Sürüm sayısı ve skor ortalaması, gerçek futbol deneyimi için bitiş garantisi vermez. Kanıtlar ve açık sınırlar DOGRULAMA.md içindedir.
