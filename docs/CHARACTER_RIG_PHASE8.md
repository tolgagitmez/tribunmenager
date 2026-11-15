# Aşama 8 — Maç çizicisinde animasyon geçişi ve 22 oyuncu benchmark'ı

## Gerçek maç entegrasyonu

Önceki PR #8'de `character-blend-controller.js`, **bağımsız Three.js GLB laboratuvarında** çalışıyordu. Gerçek maç ekranı Three.js kullanmıyor; `scene3d.js` ve `player-renderer.js` ile WebGL1 üzerinde ayrı bir 19 kemikli GPU skinning uygulanıyor.

Bu nedenle bu aşamada oyun maç motoruna glTF / Three.js bağımlılığı eklenmedi. Bunun yerine aynı görsel ilkeyi doğrudan maçın mevcut GPU paletine uygulayan `match-animation-bridge.js` eklendi.

- Her oyuncu için bağımsız WeakMap kayıtları, son poz paleti, önceki futbolcu dünya konumu ve mevcut hareket kategorisi saklanır.
- Eylem `run` → `shoot`, `idle` → `tackle` gibi değişirse 280 ms boyunca önceki ve sonraki GPU kemik dönüşümleri arasında **quaternion SLERP** ve pozisyon interpolasyonu kullanılır.
- Dönüş matrisleri yeniden birim quaternion'dan kurulur; kemik ekseni ölçeklenmez. Kayıtların 19 kemikten herhangi birinde kauçuksu deformasyona neden olmaması için otomatik testler vardır.
- `run`, `jog`, `walk`, `sprint` tek locomotion ailesine eşlenir; her hız güncellemesi ayrı bir tam vücut geçişi oluşturmaz.
- Önceki pozun dünya konumu, oyuncunun yeni koordinatına taşınarak geçmiş kareye doğru istemsiz kayma önlenir.
- `scene3d.js` yeni köprüyü yalnızca WebGL oyuncu çizicisine iletir. Oyun simülasyonu yine `humanoid-rig.js` ile sabit 60 Hz çalışır; `football-sim.js`, skor, taktikler ve top yörüngesi değiştirilmez.
- `match3d.js` maç yeniden başladığında köprüyü sıfırlar; duraklatmada görsel blend saati ilerlemez.
- `match.html` gerçek maç sayfasına köprü kodu eklenir.

**Bu, oyun içinde doğrudan glTF/GLB animasyon track oynatma değil; aynı humanoid iskeletin GPU paletiyle eylem geçişini görsel olarak yumuşatan uyum katmanıdır.** Dışa aktarılan 15 klip hâlen bağımsız GLB laboratuvarı için kullanılabilir. Bazı ani fizik/hakem eylemlerinin görsel sıçramaları yumuşatılırken gerçek oyun sonuçları etkilenmez.

## 22 futbolcu ve performans testi

- `tests/match-animation-bridge.test.cjs`: 22 farklı oyuncunun hareket değişimlerini, dönüş matrislerinin sabit birim eksenlerini, eşzamanlı oyuncuların karışmamasını ve oyun durumu alanlarının değişmediğini doğrular.
- `tools/benchmark-match-22-browser.cjs`: **gerçek `match.html`**, gerçek `Stadium3D` ve `PlayerRenderer` ile iki on birdeki 22 futbolcuyu Chromium + SwiftShader'da çizer. CPU'dan başlatılan render ve `gl.finish()` tamamlanması birlikte ölçülür.
- Benchmark, önceki ve yeni görsel geçiş için ayrı **12'şer örneklik** ölçüm toplar; medyan/p95 sürelerini ve render edilmiş sahayı PNG olarak `dist/match-animation-benchmark/` altına raporlar.
- Render ölçümleri sırasında gerçek maç **duraklatılır**; puan ve maç saati değişmemelidir. Kod maç simülasyonunu değiştirmez.
- CI'da test raporları ve 3D görüntüler GitHub Actions artifact olarak indirilir.

Bu ölçümün **mobil cihaz FPS hedefiyle karıştırılmaması** gerekir: CI'da kullanılan SwiftShader yazılımsal GPU ve test makinesinin koşulları farklıdır. Renderer'ın yalnız CPU kod süresi ya da `gl.finish()` ölçümü, tüm cihazların gerçek kullanıcı performansını temsil etmez.

## Testler

```bash
npm run test:match-animation
npm run test:character-rig
```

Gerçek 22 oyuncu Chrome benchmark'ı Playwright/PNGJS kurulduğunda:
```bash
node tools/benchmark-match-22-browser.cjs
```

## Sonraki işler

1. Maç motorunda geçiş kaynağını tek kareye sabitlemek yerine gerçek iki klibin aynı anda ilerlediği state-machine / motion-matching katmanına geçiş.
2. Low-end Android ve orta sınıf iPhone gibi gerçek cihazlarda LOD, shader ve 22 oyuncu FPS profili; geçiş kalitesini ve ağ kullanımını birlikte kontrol.
3. Gerçek top/ayak temas zamanları ile poz blending'i senkronize etme ve ayak zemini fizik constraint'i.
4. Daha gerçekçi insan topolojisi, kemik ağırlıkları ve sanatçı üretimi corrective shape key'ler.

**Not:** Bu dal PR #8 üzerinde oluşturulmuştur. Henüz `main` üzerinde değil.
