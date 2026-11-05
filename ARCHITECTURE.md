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
