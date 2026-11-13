# Maç kuralları ve yaşam döngüsü — v1.31.0

Motorun hakem kararı, olay kaydı ve yeniden başlatması aynı maç durumundan çıkar. Bu belge uygulanan oyun modelini açıklar; IFAB kitabının tamamının veya hakem değerlendirmelerinin bire bir uygulandığı iddiasını taşımaz.

## Faul, avantaj ve kart

`referee-laws.js`, faulün **temas/olay konumunu** kullanır. Hücum yönünde x=35,5–52 m ve |z|≤20,16 m aralığı ceza sahasıdır; sınır çizgileri alana dahildir. Topun faul anında çizginin öte yanında olması kararı değiştirmez. Savunmacının bu alandaki doğrudan serbest vuruş gerektiren faulü, x=41 m / z=0 penaltı noktasına aktarılır. Ofsayt gibi endirekt kararlar ceza sahasında diye penaltıya dönüşmez.

`Match.adjudicateFoul`, kararı `referee.decisions` içine olay yeri, yeniden başlatma, fail/mağdur, kart ve avantaj sonucu ile kaydeder. Gerçek müdahale yolu önce fiziksel erişimi sınar; hakem kararı uzaktan top kazanma hakkı vermez. Normal faul, kontrolsüz müdahale, ciddi faul ve bariz gol şansını engelleme ayrı değerlendirilir. Ciddi faul doğrudan kırmızıdır. Ceza sahasında gerçek top mücadelesiyle bariz gol şansını engelleme sarıya indirgenebilir; topa yönelik olmayan müdahale bu indirimden yararlanmaz.

Bariz gol şansı hesabı kontrollü top, kaleye doğru yön, mesafe ve müdahale edebilecek savunmacıları kullanan bir **oyun sezgisidir**. Doğal ciddi faul sinyali yaklaşma hızı, arkadan müdahale ve agresifliği kullanır. Bunlar ölçülmüş hakem karar olasılıkları değildir.

Avantajda oyun ve top fiziği devam eder. Üç saniyelik gözlem içinde top kaybı veya avantajın kaybolması ilk faul yerine dönüş sağlar; yeterli ilerleme, korunan kontrol veya gol avantajı gerçekleştirebilir. Sarı kart sonraki duruşa ertelenir. Ciddi/doğrudan kırmızı gerektiren durumda varsayılan karar oyunu durdurmaktır. Penaltıda otomatik avantaj tercih edilmez. Oyuncu çıkarılması sonrası takım müsabakanın asgari sayısının altına düşerse maç tatil edilir ve yeni duran top kurulmaz.

## Penaltı

Top penaltı noktasında durur. Kullanıcı takımının `special.penalty` oyuncusu uygunsa seçilir. Vurucu normal ayak temasına ve vuruş hazırlığına yürür; top vuruş anına kadar yerinde kalır. Savunan kaleci kale çizgisine, diğer oyuncular ceza sahası dışında ve noktanın en az 9,15 m gerisine yerleşir. Bu koşullar **gerçek çıkışta** yeniden denetlenir.

Vuruş normal `startKick → kickStep → release → ballStep` ve kaleci el temasını kullanır. Kaleci çizgiden erken ayrılmışsa hazır olma koşulu sağlanmaz. Bu sürüm ihlale izin verip sonradan yeniden vuruş vermek yerine ihlalli çıkışı engeller. Kalecinin ayağı için tam iskelet geometrisi yerine çizgiye göre gövde merkezi toleransı kullanılır. Tam bir penaltı ihlal/yeniden vuruş matrisi uygulanmış değildir.

Süre dolmuşsa penaltı akışı tamamlanana kadar devre/maç bitmez. Direkten dönme veya kaleci çelmesi devam edebilir; gol, dışarı çıkış, kontrol, topun durması veya başka bir saha oyuncusunun teması uzatılan penaltıyı sonuçlandırır. Vurucunun başka bir oyuncu dokunmadan ikinci teması endirekt serbest vuruştur.

## İki devre ve süreler

`match-rules.js` saf süre ve müsabaka kurallarını yönetir. Varsayılan 5/15/90 dakika seçimi iki eşit nominal devreye bölünür. Devre arası oyuncu hareketini, topu ve taktik kararları durdurur. Gösterim molası varsayılan **8 saniyedir**; devam düğmesiyle geçilebilir, `rules.halftimeSeconds` ile 900 saniyeye kadar ayarlanabilir. İkinci devre takım yönleri, başlangıç konumları, kaleci yönü ve ikinci takımın santrasıyla başlar. Kartlar ve yorgunluk korunur; eski pas/koşu/algı/ofsayt niyetleri temizlenir.

İki ayrı saat vardır:

- `match.time`: AI/bellek ve gözlemci için tek yönlü toplam simülasyon zamanı; mola da bu süreye dahildir.
- `match.clockState()`: devre saati, ilan edilen ek süre, kalan süre ve kullanıcıya gösterilen saat. Devre arasında sabittir; ilk devre uzatması ikinci devrenin nominal süresini azaltmaz. Olaylar aynı gösterim saatini taşır.

Gol arası ve değişiklik duraklaması kayıp süreye eklenir. Normal yeniden başlatmaların varsayılan 8 saniyelik hazırlık payını aşan gecikmesi telafi edilir. Nominal son anda bir kez yukarı yuvarlanan minimum ilan edilir; ek süredeki yeni gecikmeler bu minimumu uzatabilir. Bu süre politikası oyuna aittir; gerçek futbolun her duran topunu veya sakatlık/VAR gecikmesini modellediği iddia edilmez. Kullanıcı duraklatması maç süresine eklenmez.

## Çizgiler ve kale çerçevesi

`pitch-laws.js` tek boyut kaynağıdır: saha yarı uzunluğu 52 m, yarı genişliği 34 m, kale iç genişliği 7,32 m, yüksekliği 2,44 m, top yarıçapı 0,11 m. Direk yarıçapı 0,06 m oyun katsayısıdır. WebGL ve 2D kale ölçüleri bu kaynağı okur.

Taç ve kale çizgisi kararı, topun **tamamının** çizgiyi geçmesine dayanır. Aynı adımda iki çizgi aşılırsa ilk geçilen çizgi seçilir; yeniden başlatma yeri son taşma konumundan alınmaz. Direk/üst direk çarpışması süpürülmüş temasla çözülür; hızlı top çerçeveyi tek karede delip gol olamaz. Bir adım içindeki kaleci/saha oyuncusu teması gol çizgisinden önceyse golü önler. Gol, hücum yönüne göre doğru takıma yazılır; ikinci devrede kale sahipliği tersine döner.

Direkt taç/endirekt serbest vuruştan başka bir oyuncu dokunmadan rakip kaleye giden top autla; bir yeniden başlatmadan doğrudan kendi kaleye giren top kornerle sonuçlanır. Çerçeve yansıması enerji kaybeden oyun fiziğidir. Normal 60 Hz adımlarda doğrulanır; sertifikalı top/direk malzeme modeli değildir.

## Ofsayt

Ofsayt adayları ayak vuruşu ve **kafa teması** anında yeniden kaydedilir. Kafa pası, gelen ortanın eski aday listesini kullanmaz. Doğrudan taç, korner ve aut istisnaları korunur. Rakip vücut bloğu/kaleci çelmesi adayları silmez; rakibin kasıtlı kontrolü yeni oyun evresi başlatır. Kaleci görüşünü belirgin kapatan dar geometrik koridor ve topla/rakiple yakın fiziksel mücadele, topa dokunmadan aktif etkileme üretebilir. Sadece ileride durmak yeterli değildir.

Oyuncu merkeziyle çizgi karşılaştırılır; ayak/baş/gövdenin ofsayta sayılan en ileri parçası için tam iskelet ölçümü yoktur. Görüş kapatma ve mücadele geometrileri muhafazakâr oyun yaklaşımlarıdır. Hakemin her “rakibi etkileme” yorumunu kapsamaz.

## Oyuncu değişikliği

Varsayılan müsabaka **5 oyuncu / 3 pencere / asgari 7 futbolcu** kullanır. Kaleci değiştirilebilir. Aynı duruşta birden fazla değişiklik tek pencere kullanır; devre arası oyuncu hakkını tüketir ve pencere tüketmez. Canlı oyunda anlık oyuncu değiştirme reddedilir. Çıkışı süren duran top kullanıcısı değiştirilemez. Oyuncu hakkı, pencere ve duruş nedeni ekranda gösterilir. Bağlı fikstürün `competitionRules` alanı bu sınırları taşır; yerel maç yapılandırması da aynı sözleşmeyi kullanır.

```js
rules: {
  maxSubstitutions: 5, substitutionWindows: 3, minPlayers: 7,
  halftimeSeconds: 8, substitutionPauseSeconds: 3,
  addedTime: true, restartGraceSeconds: 8, roundSeconds: 1,
  maxAddedSeconds: null
}
```

## Doğrulama ve kapsam

[Test raporu](validation/match-laws-tests.json), [gerçek tarayıcı raporu](validation/match-laws-browser.json), [seçilmiş temas örnekleri](validation/match-laws-coverage.json) ve [tam doğal maç/tekrar raporu](validation/match-laws-natural.json) ayrı tutulur. Çizginin iki yanı, iki hücum yönü, hızlı direk/üst direk teması, penaltı çıkışı, avantaj dönüşü, disiplin ve son düdük kontrollü durumlarla sınanır. Seçilmiş olumlu/olumsuz olayların oranları doğal başarı oranları değildir.

Tam maçı bitirebilmek hücum dengesinin kalibre edildiğini göstermez. Ayrıntılı penaltı ihlalleri, elle oynama, sakatlık/VAR, tam vücut ofsayt ölçümü, uzatma devreleri/seri penaltılar ve farklı turnuva formatları sonraki çalışmalardır. Kurulum ve mevcut veri sınırları [KURULUM.md](../KURULUM.md) içindedir.
