# Hava Topu, Kaleci Ulaşılabilirliği ve Kritik Oyun Kuralları

Bu değişiklik [birleşik lig motoru dalını](https://github.com/tolgagitmez/tribunmenager/pull/17)
temel alır. İzlenen/izlenmeyen karşılaşmalar aynı `football-sim.js`
fiziğinden yararlanır; aşağıdaki kararlar menajer bağlantısına göre
ayrı dallara ayrılmaz.

## Hava topu ve ikinci top

- Eski dar kapsam yalnızca belirli yükseklikte düşen **orta** toplarını
  karşılıyordu. Yeni `aerial(previous)`, fiziksel teması
  `cross`, `long-pass`, `clearance`, `throw` ve yükselip yeniden
  düşen sahipsiz top durumlarında kontrol eder.
- Temas noktası gerçek `previous → ball` süpürmesinden bulunur.
  `heading`, mevcut hız ve enerji, oyuncunun sıçrayarak yetişebileceği
  kafa yüksekliğini belirler. Yetişilemeyen top oyuncunun kafasına
  çekilmez.
- Daha düşük düşüşlerde oyuncu topu **göğsüyle yumuşatır**;
  topun dikey hareketi ve ayak seviyesine inişi normal
  `BallPhysics` ile sürer.
- İki rakip aynı düşen topa yetiştiğinde skor farkı ve gerçek mesafe
  ölçülür; yakın hava mücadelesi yön değiştiren bir top üretir,
  kimseye garantili kontrol sağlamaz. Sonraki sahiplik normal
  ikinci top kazanımıyla gerçekleşir.
- Gösterge: `telemetry.aerialLongBalls`, `aerialHeaders`,
  `aerialDuels`, `chestControls`, `aerialSecondBalls`,
  `secondBallContests`, `secondBallRecoveries`.

## Kalecinin yetişebildiği şutlar

Her şut kaleciye aynı müdahale şansını vermez. Kaleci fiziğinden
bağımsız sonuca göre **tüm şutları** tutuş oranının paydası yapmak
yanıltıcı olur.

`keeperReachability()`, kalecinin görüntü alanı, topun tahmini
kesişme zamanı, tepki gecikmesi, yanal mesafe ve erişim yarıçapını
hesaplar. Gerçek `keeper()` içerisinde yalnızca bu ön koşulu
sağlayan şut `keeperReachableShots` sayılır, uçuş başına en fazla bir kez.

- **Tutuş oranı:** `keeperReachableCatches / keeperReachableShots`
- **Çelme oranı:** `keeperReachableParries / keeperReachableShots`
- **Payda sıfırsa:** oran `null` (sıfır yüzde veya hayalî başarı değil)
- Bu oranlar tüm şutlar içinde kaleciye yetişme başarısı değil,
  kalecinin yetişebilir olduğu örneklerdeki **son teması** ölçer.
  Görüşü engellenmiş veya yetişilemez şutlar ayrı değerlendirilmelidir.
- Kaynak: `keeperSummary()` ve doğal maç ölçümünde üretilen
  `docs/validation/aerial-keeper-rules-current.json`.

## IFAB Law 14: penaltı

[IFAB Law 14](https://www.theifab.com/laws/latest/the-penalty-kick/)
için **topa temas anındaki** iki önemli kayıt tutulur:

1. Kalecinin ayaklarından en az bir bölümü kale çizgisinde,
   çizgi hizasında veya gerisinde bulunuyor mu?
2. Vurucu ve kaleci dışında herhangi bir oyuncunun ayağı ceza
   alanına/yayına erken girdi mi, penaltı noktasının önünde mi?

İhlal kaydı **tek başına otomatik düdük değildir**. Kaleci çizgiyi
erken terk edip topu kurtardığında penaltı tekrar edilir; top gol
olduğunda erken çizgi ihlali golü iptal etmez. Sahaya erken giren
hücum oyuncusunun dönen topa müdahalesi endirekt serbest vuruş,
erken giren savunmacının etkili müdahalesi yeniden vuruş ve iki
tarafın etkili girişleri yeniden vuruş üretir. Kuralların etki
kararı `referee-laws.js` ve gerçek top teması anında
`penaltyImpact()` ile uygulanır. Hakem ve ihlal kayıtları
deterministik tutulur.

**Sınırlar:** Bu PR, penaltı vuruşunda geçerli bütün ihlalleri
uygulayan eksiksiz bir hakem sistemi olduğunu iddia etmez;
özellikle kalecinin şutu atmadan önce vurucuyu açıkça etkilemesi,
kasıtlı vuruş aldatması ve kasıtsız çift dokunuşun tüm özel
kararları ayrı geliştirme gerektirebilir. Daha önceki çift dokunuş
engeli korunur.

## IFAB Law 11: ofsayt

[IFAB Law 11](https://www.theifab.com/laws/latest/offside/):
oyuncunun baş, gövde veya ayağının kale çizgisine en yakın
**oynanabilir** bölümü ve sondan ikinci savunmacının aynı
oynanabilir sınırı karşılaştırılır. El ve kollar bu hesabın
dışındadır.

- Pozisyonlar `offsideBodyParts` gerçek rig yer işaretlerinden
  verilebilir; yoksa futbolcunun yönü, hızı ve merkezi üzerinden
  sınırlı fiziksel baş/ayak uzanımı kullanılır.
- Sadece pozisyonda durmak hâlâ ihlal değildir; mevcut temas,
  müdahale ve kalecinin görüşünü kapatma kuralları devam eder.
- Korner, taç ve auttan doğrudan alım istisnaları korunur.

## Tekrarlanabilir kontroller

```bash
node --test tests/aerial-keeper-law-boundaries.test.cjs
node --test tests/match-laws-integration.test.cjs tests/referee-laws.test.cjs tests/match-rules.test.cjs tests/first-control.test.cjs tests/pitch-laws.test.cjs
npm run test:manager-kick
npm run test:live-match
npm run test:engine-invariance
node tools/profile-aerial-keeper-rules.cjs
```

Dört farklı tohumdaki tam 5 dakikalık doğal maçlar sayıları
veri dosyasına yazılır; kısa örneklem sezon boyunca şut, ikinci
top veya kaleci dengesi konusunda istatistiksel güvence değildir.
Motor/animasyon bağımsızlığı ayrıca 60 Hz fizik karşılaştırmasıyla
kontrol edilir.

Bu özellik değişikliği [PR #17](https://github.com/tolgagitmez/tribunmenager/pull/17)
dalını baz alır, henüz `main` dalında değildir.
