# 3D maç FPS iyileştirmeleri — v1.33 (çalışma dalı)

## Sorunun kaynakları

v1.32, **tek LOD'lu ve 27.350 üçgenli** lisanslı MakeHuman futbolcusunu 22 oyuncu + hakem için kullanıyordu. TV kamerasında bile yaklaşık **629.050 oyuncu üçgeni** GPU'ya gönderiliyordu. Her fragmanda üç GGX/Smith ışık, prosedürel numara ve doku hesabı işleniyordu. Cihaz piksel oranı **1,8** ile sınırlandığı için birçok ekranda gereğinden fazla piksel çiziliyordu. Ayrıca maç hızı 8×–16× veya düşük FPS durumlarında **tek tarayıcı karesine sınırsız sayıda 60 Hz simülasyon adımı** yüklenebiliyordu.

## Teknik değişiklikler

1. **Lisanslı dosyalar değişmeden GPU LOD:** `player-renderer.js` tek LOD'lu kaynağın 15.544 köşe noktasından çalışma anında, aynı cilt kemik kümesi ve malzeme/normal yönü içinde köşe kümelendirme yöntemiyle iki ek LOD üretir. Dejenere ve yinelenen üçgenler atılır, yönleri kontrol edilir, deri ağırlıkları normalize edilir. Ana `assets/player/player-model-data.js`, `footballer.glb`, manifest ve kaynak SHA-256 değerleri korunur. TV/taktik kamerası düşük LOD'u, yakın ve portre kamerası daha ayrıntılı LOD'u kullanır; tam kalite ayarı özgün yüksek LOD'u kullanır.
2. **Hafif yayın ışıklandırması:** `uFast` shader dalı, TV modunda karmaşık üç ışıklı PBR yerine bir ana + bir dolgu ışığı ve temel renk/doku hesabı yapar. Portre/stüdyoda ve `Kalite` modunda özgün malzeme shader'ı korunur.
3. **FPS'ye göre çözünürlük:** Maç `Performans` grafik modunda başlar (DPR üst sınırı 0,8); `Dengeli` mod 1,1 DPR sınırından başlar ve uzun süre düşük FPS algıladığında çözünürlüğü 0,55 katsayısına kadar azaltabilir; `Kalite` modunda üst sınır 1,6'dır. Sekme gizliyken ve maç duraklatıldığında adaptasyon ilerlemez.
4. **Simülasyon iş bütçesi:** 60 Hz maç fiziği ve oyun kuralları değiştirilmedi. Bir görüntü karesinde düşük hızda en fazla 6, 4× hızda 10, 8×–16× hızlarda 14 fizik adımı yapılır. Cihaz yetişmezse biriken gecikme atılır ve maç geçici olarak **daha yavaş ilerler**; sonuçlar için ara fizik adımları büyütülmez veya daha seyrek hesaplanmaz.
5. **Daha az boş işlem:** Duraklatıldığında sahne çizimi yaklaşık 8 FPS'ye indirilir. Çok hızlı maç modlarında HUD güncellemeleri en fazla ~8 Hz yapılır. Kullanıcı üç grafik profili arasında `Grafik: Performans / Dengeli / Kalite` düğmesiyle geçiş yapar. Yanında yaklaşık FPS bilgisi gösterilir.

## Karşılaştırma ve ölçümün anlamı

Aynı 22 oyuncu ve hakem kullanılan otomatik Chromium SwiftShader testinde:

| Metrik | Önce | Yeni Performans modu |
| --- | ---: | ---: |
| Oyuncu mesh'lerinden gönderilen üçgen | 629.050 | 60.996 |
| Geometri azalması | — | yaklaşık %90,3 |
| Gölgeli materyal | Üç ışıklı GGX/Smith | Basitleştirilmiş tek ana ışık + dolgu |
| 1600 × 1024 test viewport'unda raster alanı (DPR 1,25) | Yüksek kalite yaklaşık 1418 × 681 | Performans modu 908 × 436 |

SwiftShader CPU üzerinde çalışan yazılımsal GPU'dur ve ölçümler `gl.finish()` ile birlikte yapılır. Değerler **gerçek cihazda FPS garantisi değildir**. Shader ilk derlenirken veya işletim sistemi yük altında olduğunda gecikme sıçramaları olabilir. Yakın kamera ve Kalite modunda eski geometri/PBR maliyeti bilerek korunur.

## Kalite sınırları

- Çalışma anında üretilen LOD'lar **sanatçı tarafından elde düzenlenmiş** topoloji değildir; uzak mesafede detay ve kumaş dokusu sadeleşir. İnsan silueti, taban, kemikler ve skin weight regresyon testleriyle korunur; profesyonel görsel kalite incelemesi yine gerekir.
- Mobil GPU ve daha yavaş cihazlarda (özellikle Android) 30/60 FPS için ayrı gerçek cihaz ölçümü ve daha da optimize edilmiş geometri/texture pipeline'ı gerekli olabilir.
- Bu çalışma maç fiziği, skor, top, pas yapay zekâsı, karar algoritması ve lisanslı kaynak verilerini değiştirmez.

## Testler

```sh
npm run test:match-fps
npm run test:match-animation
npm run test:character-rig
```

Tam WebGL görüntü ve karşılaştırma: `tools/benchmark-match-22-browser.cjs` (Playwright/Chromium). JSON raporu `dist/match-animation-benchmark/report.json` altında; görüntü GitHub Actions artifact olarak saklanır. 
