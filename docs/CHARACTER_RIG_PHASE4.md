# Aşama 4 — GLB iskelet animasyonları ve görsel regresyon

## Teslim

Bu aşamada önceki GLB örneğiyle uyumlu, yerel oyunun prosedürel iskelet hareketlerinden türetilmiş **10 animasyon klipli** bir dosya üretildi:

- `assets/player/tribun-base-footballer-animated.glb` — 671.160 bayt, 19 deform kemiği, 10 klip, 30 FPS animasyon anahtarları.
- `tools/character-animation-baker.cjs` — 60 Hz oyun hareketini örnekler, renderer'ın skin matrix'ini bind matrisiyle birleştirip global kemik pozunu bulur, ebeveynin ters dönüşümüyle glTF local TRS üretir.
- `tools/export-character-glb.cjs --animations` — çıktıdaki GLB'nin `animations` alanlarına her kemik için translation ve rotation kanalları ekler.
- `tests/character-glb-animation.test.cjs` — hiyerarşiden yeniden oluşturulan bone matrislerinin oyun GPU palette'iyle benzerliğini ve poz, süre, quaternion sürekliliğini kontrol eder.
- `tools/check-character-browser.cjs` ve `.github/workflows/character-visual.yml` — Chromium/SwiftShader 3D oyuncu stüdyosu render testi ve ekran görüntüleri.

Klipler: `idle` (1,0 sn), `walk`, `jog`, `run`, `sprint` (her biri 2,0 sn), `turn` (4,5 sn), `pass`, `shoot`, `dive-left`, `dive-right` (her biri 1,3 sn).

Her glTF animation'da 19 kemik için 19 translation ve 19 rotation kanalı; temaslı hareketlerde `animation.extras.contactTime` bilgisi vardır. Quaternion dönüşleri ardışık karelerde aynı yarıkürede tutulur. Kemik eksenlerine ölçek uygulanmaz.

## Kullanım

```bash
npm run test:character-rig
npm run build:character-animated-glb
# İsteğe bağlı daha sık örnekleme:
node tools/export-character-glb.cjs --animations --fps 60 --lod 0 --output dist/character-animation-60fps.glb
```

Oyuncu stüdyosundaki `tribun-base-footballer-animated.glb` bağlantısı, Blender veya glTF görüntüleyicisine aktarılabilecek dosyayı indirir. Aynı ekrandaki hareket önizlemesi hâlen oyunun WebGL renderer'ını kullanır; GLB üzerinden oynatma yapan ayrı bir player değildir.

## Doğrulama ve sınırlar

- 15 Kasım 2026 ilk GitHub Actions denetiminde **20/20 test başarı**, resmi Khronos Validator'da animasyonlu GLB için **0 format hatası, 0 uyarı**.
- İçe aktarma ve görsel kalite Blender'da elle değerlendirilmedi. Bir animasyonun içe aktarılabilir formatta olması, FIFA kalitesinde hareket elde edildiği anlamına gelmez.
- Motion-capture, keyframe sanatçısı düzeltmesi, 60–80 kemik, parmaklar ve elle oluşturulmuş corrective shape keys bu fazda yok.
- Örnekler kavisli/yer değiştiren hareketlerden alındığı için yürüyüş, koşu ve dönüş klipleri kusursuz döngü (seamless loop) veya tam root-motion standardı iddiası taşımaz.
- Kaleci kurtarışları, pas ve şut sahnedeki top animasyonlarını GLB'ye eklemez; yalnız insan iskeletini ve temas zamanlarını içerir.
- Render doğrulaması yalnızca mevcut player-studio WebGL çizicisini kontrol eder; bağımsız glTF renderer ve Blender deformasyon incelemesi hâlâ ayrı görevlerdir.

## Sonraki teknik aşama

En değerli sonraki adım bağımsız bir glTF animasyon oynatıcısı, Blender'da deformasyon fotoğrafları ile omuz-kalça-diz karşılaştırması, foot-lock ve retargeting testleri, ardından oyun içi canlı prosedürel hareket ile GLB kliplerinin ortak animasyon arayüzünden sürülmesidir.
