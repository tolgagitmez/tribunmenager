# Animasyonu gerçek maç temasına bağlama — tek futbolcu pilotu

Bu belge ilk pilotun tasarımını ve kare bütçesini kaydeder. Güncel deneme ve geliştirici komutları [kanat hücumu rehberinde](WING_ATTACK_PILOT.md) yer alır.

Bu pilot, `feature/aerial-keeper-penalty-offside` dalının güncel
`football-sim.js` motoruyla çalışır. Maç motoru, sunucu işlem günlüğü,
takım taktikleri ve RNG **değiştirilmemiştir**.

## İlk pilot: oyuncu #0

`match.html`, Blender'dan yeniden dışa aktarılmış ve mevcut atölyede
doğrulanmış `assets/interchange/footballer.blender.glb` dosyasını,
**aynı** yerel Three.js `GLTFLoader` ve `gltf-runtime-adapter` üzerinden
asenkron yükler. Klipler: `idle`, `run`, `shoot`, `dive-right`.

- Oyuncu #0'ın gerçek maç `x/z`, `face`, `speed` ve `actionElapsed`
  değerleri sunumun referansıdır. Koşu klibinin döngüsü oyuncunun katettiği
  gerçek mesafeye göre ilerler. Frenleme klip ağırlığını azaltır; gerçek
  oyuncu yönündeki dönüş, mevcut anatomik rig ile korunur.
- GLB'den getirilen **üst gövde** kemik paleti, maçın aynı 19 kemikli
  MakeHuman iskeletinin sunum paletiyle rijit dönüş üzerinden karıştırılır.
  Bacaklar, pelvis ve ayaklar **sürekli** mevcut IK ve yer teması
  sistemindedir. Bu kasıtlı hibrit başlangıçtır; tüm klipte tam
  gövde motion capture oynatıldığı iddia edilmez.
- `match-contact-pilot.js`, gerçek `releaseSerial`, topun
  `flight.from` kimliği ve `contactTime` ile zamanlama yapar.
  Vuruştan sonra yaklaşık 0,3 s boyunca follow-through devam eder.
  Görsel oyuncunun verisi kopyalanır; orijinal simülasyon nesnesine
  kamera veya animasyon tarafından yazılmaz.
- Yerden kalkan destek ayağına karşı yalnız `pilotPlant` görsel
  bayrağında erişilebilir zemin ankrajı uygulanır. `Rig` fiziksel
  el ve ayak temas API'sinin kendisi değişmez. Animasyon, kuralları
  ya da futbol topunun çıkış koordinatını değiştiremez.
- `ball-visual.js` mevcut `ball.spin` skalerini işaretin
  yatay eğrisine; yuvarlanmada `vx/vz` değerlerini top deseninin
  dönüşüne uygular. Topu, hızını veya falso katsayısını değiştirmez.
- Kaynak yüklenemezse maç **mevcut lisanslı GPU animasyonuna**
  döner. Pilotun durumu `TRIBUN_MATCH_TEST.pilotStats()` ile
  görülebilir. `match.html?pilot=1` pilotu açıkça etkinleştirir; varsayılan maçta pilot kapalıdır.

## Testler

```bash
node --test tests/live-contact-animation-pilot.test.cjs
node --test tests/character-footlock.test.cjs tests/character-licensed-rig.test.cjs
npm run test:live-match
node tools/benchmark-live-contact-pilot.cjs
```

Önce birim testleri gerçek vuruş anında bacak IK hedefini ve
destek ayak yüksekliğini, değişmeyen maç state'ini, fren/dönüşü,
tekrarlanan bırakma olayının tek sayılmasını ve işaretin
gerçek `spin` ile sağa/sola dönmesini kontrol eder.

Ardından **gerçek `match.html` üzerinde 22 aktif futbolcuyla** masaüstü
1440×900 / DPR 1 ve telefon boyutunda 390×844 / DPR 2
dokunmatik Chromium emülasyonu denenir. Her profil için
`quality`, `balanced`, `performance` modlarında 48
`requestAnimationFrame` aralığının p95 değeri ve bütçeye uyan
kare oranı ölçülür. Ek olarak senkron `gl.finish` kare maliyeti
ayrı tutulur. Sonuç raporu ve ekran görüntüleri GitHub Actions
artifact'ı olarak saklanır.

**İlk hedef:** karelerin en az %95'inde masaüstü 16,7 ms,
telefon 33,3 ms. Bunlar geçme koşulu olarak önceden ilan
edilmiştir; ölçülmeden başarı gösterilmez. CI'daki
SwiftShader **yazılım GPU'sudur**; telefon boyutu ve dokunmatik
kontrol emüle edilir, gerçek Android/iOS cihazı
ölçülmez. Farklı GPU'ların p95 sürelerine bu rapordan kesin
bir genelleme yapılamaz. Oyundaki üretim WebGL1/DQS ve
kademeli LOD/kalite yolları korunur; atölyedeki Three.js
renderer'ı 22 oyunculu maça taşınmış değildir.

## Sonraki aşama: kaleci ve omuzlar

Bu sürüm tek sahadaki oyuncuya ait pilotu sınırlar. `dive-right`
klibi Blender GLB içinde doğrulanıp yüklenir ancak kaleciyi maç
içinde bu kliple oynatan ayrı pilot **henüz yoktur**.
Kalecide yerden kopma, topa uzanan el ve gerçek fizik temas
hedefleri birlikte sınanmalıdır. Omuz hacim kaybı için de
clavicle–upper arm deformasyonunun çoklu açıdan incelenmesi,
gerekirse sanatçı üretimi düzeltici skin ağırlıkları veya
shape key gerekecektir. Yalnızca klip karışımı, omuzdaki bütün
hacim bozulmalarını düzeltmez.

Bu çalışma mevcut maç kurallarını değiştirmediği için kaleci/omuz
genişlemesi ayrı görsel PR olarak yapılabilir.
