# Karakter geliştirmesi — Aşama 6: koşu → pas/şut, taban ve kalça

## Kapsam

Aşama 5'teki `feature/character-footlock-glb-viewer-v1` dalını temel alır; önceki karakter çalışmaları yerine geçmez.

### 1. Koşudan vuruşa ve koşuya geri dönüş

- `animation-scenarios.js`: `run-pass` ve `run-shoot` eklendi. 3,3 m/s ile yaklaşma; t=0,75 sn civarında vuruş başlangıcı; pas teması yaklaşık 1,06 sn, şut teması yaklaşık 1,13 sn; devamında yeniden koşu.
- `humanoid-rig.js`: üst gövdedeki vuruş katkısı düşük geçiren bir sönümle kısa sürede çözülür. Vuruş bitişinde hareketli ayağın son pozu saklanır ve yaklaşık 0,22 saniyede güncel gövde konumuna göre yeniden basma adımı uygulanır. Bacakların iki kemikli IK uzunlukları değişmez.
- Vuruş sırasında kalça yaklaşık 1,2 cm'ye kadar alçalarak koşu hızındaki temas hedefinin ulaşılabilirliğine katkı verir. Bu yalnızca animasyon katmanıdır; topun oyun fiziği veya maç kararı değiştirilmemiştir.

Ölçüm: 60 Hz, 3,3 m/s hareketli şut örneğinin bittiği karede vurucu ayak konum sıçraması önce yaklaşık **0,417 m**, sonra **0,0067 m**. Bu yalnız tek bir kontrollü koşulda ölçülmüştür; bütün maç durumlarında kusursuzluk iddiası değildir.

### 2. Krampon tabanı

- `assets/player/player-model-data.js`: yuvarlatılmış kramponun tabanının altına, iki ayağın kemik ağırlığını kullanan çokgen dış taban döngüleri eklendi.
- Statik bind pozu geometrisinde tabanın en alt köşe noktası yaklaşık **0,003 m** zeminin üzerindedir. Önceki gövde şekli yaklaşık 0,028 m yukarıda kalıyordu.
- Geometrinin üç LOD'u **4500 / 3150 / 2250 vertex** içeriyor. Kramponun ana çizim/format yolları değiştirilmedi.

Bu yalnızca bind-pose geometrik yakınlık testidir; oyun içinde her açıdan gerçek çarpışma, fiziksel taban teması veya ayakkabı deformasyon simülasyonu değildir.

### 3. Omuz ve kalça geçişleri

- Omuz çevresi için klavikula / üst kol ağırlıkları ve pelvis / üst bacak ağırlıkları birkaç dikiş halkasına yayılıp yumuşatıldı.
- `player-renderer.js`: mevcut omuz/diz/dirsek görsel desteklerine benzer küçük bir kalça-hacim düzeltmesi eklendi. Sol ve sağ kalça için `uHipRest` ve `uHipFlex` shader değerleri kullanılır.
- Bu değişiklikler profesyonel blendshape, ağırlık boyama veya anatomik hacim koruma algoritmasının tam karşılığı değildir.

### 4. GLB dışa aktarımı ve testler

- Statik `assets/player/tribun-base-footballer.glb` ve animasyonlu `assets/player/tribun-base-footballer-animated.glb` yeniden üretildi.
- GLB'de toplam **12 hareket** var: idle, walk, jog, run, sprint, turn, pass, shoot, run-pass, run-shoot, dive-left, dive-right.
- `tests/character-kick-transition.test.cjs`: vuruş teması, vuruş bitişindeki ayağın sıçramaması, üst gövde sönümlemesi, bacak uzunluğu, taban yüksekliği ve omuz-kalça weight gradient kontrollerini içerir.
- Önceki GLB, Quaternion, Khronos ve WebGL testleri de korunur.

Çalıştırma:

```bash
npm run test:character-transition
npm run test:character-rig
npm run viewer:character
```

Bağımsız GLB animasyon izleyicisi `character-viewer.html` dosyasında yeni iki klibi de açabilir. Yerel görüntüleme için önce `three@0.181.2` kurulu olmalıdır. Kullanıcı arayüzündeki `player-studio.html` seçicisinde de koşu → pas ve koşu → şut bulunur.

## Şu anki sınırlar

Kliplerin yarattığı görünüm ve kök-hareket akışı, profesyonel motion capture veya oyun içinde animasyon-state-machine entegrasyonunun yerine geçmez. Mobil GPU benchmark'ı, el ile Blender deformasyon değerlendirmesi, tam krampon tabanı çarpışması, bütün top/krampon temaslarına fiziksel constraint çözümü, kararlı kesintisiz animasyon döngüleri ve ticari sürüm onayı hâlâ gereklidir.
