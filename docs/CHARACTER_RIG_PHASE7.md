# Karakter geliştirme — Aşama 7: GLB animasyon blending, gait loop ve gerçek taban teması

## Yapılan teknik geliştirmeler

Bu dal `feature/character-kick-transition-sole-v1` (PR #7) üzerinde inşa edildi.

### Ağırlıklı animasyon geçişleri

- `character-blend-controller.js`: bağımsız animasyon oynatıcısı için yeniden kullanılabilir bir **crossfade controller**. Önceki ve sonraki kliplerin ağırlıkları `smoothstep` ile yaklaşık **0,28 saniyede** kademeli değiştirilir. Geçiş tamamlanınca önceki klibin oynatımı durdurulur.
- Yeni klibin ilk pelvis pozuyla geçiş öncesi pelvis pozunun X/Z farkı sahne köküne yayılarak aktarılır. Böylece koşu klibinden şut klibine geçerken karakterin tekrar dünya başlangıcına zıplaması azaltılır.
- Tek klipte kare seçimi (`seek`) desteklenir; devam eden crossfade bitişindeki kök düzeltmesi kaybedilmez.
- `character-viewer.html`: bağımsız Three.js GLB oynatıcıya controller bağlandı ve test API'sine `blendInfo`, `step`, `soleContact` eklendi.

**Önemli kapsam sınırı:** Bu bir **bağımsız GLB önizleme sistemi** geliştirmesidir. Gerçek zamanlı maç motorunun mevcut prosedürel rig animasyonunu kontrol eden sistem değiştirilmedi. FIFA seviyesi animasyon ağacı, koşu vektörüyle yönlendirilmiş motion-matching veya kök hareketi replikasyonu yapılmış değildir.

### Üç yeni in-place döngü

- `walk-loop` — 2,2333 sn; `run-loop` — 1,4333 sn; `sprint-loop` — 1,5667 sn.
- `tools/character-animation-baker.cjs` döngüleri, 60 Hz simülasyonun 3 saniyelik ısınma safhasından sonra örnekler. Dairesel laboratuvar rotası pozlardan çıkarılır; karakter döngüyü yerinde tamamlar.
- Başlangıç ve bitişte **tüm 19 kemiğin pozları aynı**. Son birkaç örnek, döngü sonundaki kareler arası değişimin ilk kareler arası değişime yaklaşması için düzeltilir.
- `tools/export-character-glb.cjs` bu üç klibi glTF `animation.extras.loopReady=true` alanıyla işaretler. Önceki 12 klip korunur; toplam **15** klip.
- Gerçek futbol maçında dünya üzerindeki oyuncu hareketini bu in-place kliplerden üretmek için ayrı root-motion / fiziksel oyuncu konumu entegrasyonu gerekir.

### Gerçek skinning ile taban teması

- `tests/character-skinned-sole.test.cjs` sadece ayak bileği IK'sini değil, orijinal **4500 vertex** modelinin krampon tabanındaki köşe noktalarını GPU palette'in kullandığı dört ağırlıklı matris dönüşümüyle CPU'da örnekler.
- Durağan, yürüyüş, koşu, sprint, koşudan şut, koşudan pas için gerçek deformasyonlu taban yüksekliği incelenir. Ayağın yerde olduğu karelerde en alt köşe noktasının **-5 mm ile +12 mm** aralığında kalması gerekir.
- `character-viewer.html` bağımsız glTF sahnesinden `SkinnedMesh.getVertexPosition()` ile **gerçek yüklenmiş GLB modelinin** çizim sonrası taban yüksekliğini okuyabilir.
- Bu, sahnedeki her muhtemel poz için fiziksel çarpışma garantisi değil; kapsanan örnekler için zemin temasına ilişkin geometrik regresyon testidir.

## Dosyalar

- `character-blend-controller.js`
- `character-viewer.html`
- `tools/character-animation-baker.cjs`
- `tools/export-character-glb.cjs`
- `assets/player/tribun-base-footballer-animated.glb` (15 klip)
- `tests/character-blending-loop.test.cjs`
- `tests/character-skinned-sole.test.cjs`
- `tools/check-independent-glb-browser.cjs`
- `.github/workflows/character-rig.yml` ve `.github/workflows/character-visual.yml`

## Çalıştırma ve kalite denetimi

```bash
npm run test:character-rig
npm run test:character-blending
npm run test:character-contact

# Gerçek GLB oynatıcı (gerekli Three.js sürümü kurulduktan sonra)
npm install --no-save --no-package-lock --ignore-scripts three@0.181.2
npm run viewer:character
```

GitHub Actions: **29/29 Node testi başarılı**, resmî Khronos glTF 2.0 validator'da **0 hata, 0 uyarı** (15 Kasım 2026). Bağımsız Chromium/SwiftShader'da 15 klip, ağırlık geçişi ve GLB taban görüntü denetimi başarıyla çalıştı.

### Sayısal yeniden üretilebilirlik notu

Farklı V8/işletim sistemi derlemelerinde uzun 60 Hz trigonometrik animasyonların float32 son biti (ULP) farklı olabilir. Bu nedenle kaydedilmiş GLB ile yeniden derlenen modelin **dosya yapısı/indeksleri birebir**, animasyon float verileri ise küçük tolerans içinde kontrol edilir. Aynı Node.js çalışma ortamında ardışık üretimlerin byte-for-byte eşdeğerliği ayrı testte korunur.

## Sıradaki üretim ihtiyacı

1. Oyun maç motoru ile bağımsız GLB blending controller arasındaki veriyi ortak bir animasyon-state-machine/retarget katmanına taşımak.
2. 22 oyuncu ve mobil cihazlarda yüzey/kemik animasyonu performansını ölçmek.
3. Sanatsal deformasyon incelemesi, yüksek kaliteli insan topolojisi ve gerçek hareket yakalama klipleri eklemek.
4. Zemin ve top temasına göre ayrı ayak IK constraint ve momentum koruyan koşu/kayma geçişleri geliştirmek.
