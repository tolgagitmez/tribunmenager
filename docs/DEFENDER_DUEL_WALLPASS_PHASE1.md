# Aşama 3 — Savunmacı çalım tepkisi, sırtı dönük düello ve gerçek duvar pası

## Gerekçe

Önceki aşamalarda teknik oyuncu çalım seçebiliyor ve bunu 3D iskelet gösterebiliyordu. Savunmacının yanlış hamlesi, fiziksel top saklama mücadele avantajı ve duvar pasının gerçek vuruşla bağlantısı eksikti. Bu aşamada mevcut top ve oyun saati tek otorite olarak korunur.

## Savunmacı tepkisi

- `applyFeint()` yalnızca **gördüğü ve üzerine geldiği** çalımda, savunmacının tackling/composure değerleriyle hücumcunun dribbling farkı yeterliyse sınırlı `feintResponseClock` oluşturur.
- `move()` içinde yalnızca normal baskı/markaj görevi devam ederken hedef kısa süre yanlış taraftaki küçük bir noktaya döndürülür. Her hareket hâlâ normal hız, ivme ve saha sınırlarını izler.
- `humanoid-rig.js` aynı süre içinde savunmacının ağırlık aktarımı, omuz eğimi ve kısa aldatılmış ayak adımını gösterir. Top pozisyonu veya skor bu poz hesaplamasından etkilenmez.
- Görüş açısı kötü, oyuncu uzaklaşan veya rakibin becerisi yüksekse yanlış adım yaratılmaz. `feintWrongSteps` sayaçtır; 'rakip geçildi' değildir.

## Güç ve dengeyle sırtı dönük mücadele

- Sadece gerçek `shieldUntil` aktifse, top geometrik olarak savunmacının arkasına saklanmışsa ve rakip fiziksel mesafedeyse güç/denge farkı müdahale ihtimaline küçük, iki yönlü katkı sağlar (en fazla 0,14).
- Korunma rakibi dokunulmaz yapmaz. Mevcut erişilebilir müdahale, faul, kart ve tek rastgelelik düzeni korunur.
- Forvet topu en az kısa bir süre sakladıktan sonra şerit/varış riski düşük ve fiziksel pas hazırlığı yapılabilir bir pas varsa baskıdan çıkabilir. Böyle pas yoksa vuruş kararı zorlanmaz; yeterli alan varsa dönerek top taşıma denenebilir.
- `holdUpOutlets` ancak pas gerçekten ayaktan çıkınca sayılır; `holdUpTurns` seçilen kontrol devamıdır.

## Tek dokunuş gerçek duvar pası

- Yeni 'duvar pası' etiketi yalnızca `giveGoLink` ile doğrulanmış koşuya dönen takım arkadaşına `oneTouch` pas hazırlanırken oluşturulur. Sıradan her pas etiketlenmez.
- `wallPassClock` vuruş hazırlama süresi ile bağlıdır; iskelet asıl vuruş ayağına dokunmaz, karşı denge kolunu kullanır.
- `release()` fiziksel temasın kendi kapısından geçtikten sonra `wallPassReleases` telemetrisini ve olay anlatımını üretir. Animasyon topa gizli ikinci vuruş uygulamaz.
- Sunucu snapshotu ve görüntü interpolasyonu kısa beceri hareketlerini taşır. Blender pilotunun genel koşu klibi bu özel kolları değiştirmez.

## Yeniden üretim

- `npm run test:duel-wallpass` ve `.github/workflows/defender-duel-wallpass.yml`.
- Testler gerçek `Match.applyFeint` + `Match.move`, gerçek `doTackle`, güce göre aynı zar atışında farklı sonuç, gerçek `choose()` ve `passPreparation`, `startKick` + `Rig.update` ve `kickStep` üzerinden gerçek release, sunucu client state, kemik uzunlukları ve önceki fizik regresyonlarını kapsar.
- **Sınır:** Bu bir rijit-cisim omuz/kalça çarpışması veya motion-capture animasyon sistemi değildir. Her başarılı feint ve wall pass ayrıca gerçek oyun zamanında doğrulanmalıdır. 22 oyunculu gerçek WebGL FPS ölçümü ayrı kabul kriteridir.

## Birleştirme

`PR #27 (bireysel oyuncu zekâsı)` → `PR #28 (becerilerin 3D gösterimi)` → `PR #29 (savunmacı / düello / duvar pası)` sırasıyla birleştirilir. Testler başarı göstermeden ana dalı değiştirmeyin.
