# Aşama 5 — sprint ayak temas dengesi ve bağımsız GLB oynatıcısı

## Güncellemeler

Bu dal, `feature/character-glb-animation-v1` (PR #5) üzerinde iki soruna odaklanır.

### Sprint ayağı yeniden yere basıyor

Önceki 60 Hz sprint örneğinde 10 saniyede sol ayak yalnızca 3 kare, sağ ayak 183 kare görsel olarak yere basıyordu. Dizleri sabit uzunluklu tutan IK doğru davranıyordu ancak fazla uzun sprint adımı nedeniyle sol ayak yere erişemiyordu.

`humanoid-rig.js` içinde normal yürüyüş/koşu parametreleri korunarak yüksek hızda yumuşak geçiş eklendi: yaklaşık 6,4 m/s hızda adım uzaklığı 3,0 m'den 2,5 m'ye, yer temas görev oranı %34'ten %20'ye düşürüldü.

Aynı sprint senaryosunda gözlenen temas kareleri: **sol 64, sağ 61**. Her ayak yaklaşık 14 kez yere iner. Ayak duruşta kaldığı sürece poz örnekleri arasında zemin kayma mesafesi hesaplanan ölçümde sıfıra çok yakındır. `tests/character-footlock.test.cjs` iki taraflı ayak temasını, uç nokta sabitliğini, 0,5 m bacak kemik uzunluğunu, yürüyüş/koşu/dönüş/şut durumlarını test eder.

Bu ayar top fiziği veya oyuncu taktik kararlarını değiştirmez. Tek karakter görsel yürüyüş üretiminde değişikliktir.

### Orijinal oyun çizicisinden bağımsız GLB animasyon inceleme

- `character-viewer.html`: Three.js + GLTFLoader ile GLB dosyasını kendi GPU renderer'ına yükler; glTF içindeki gerçek kemik animasyonlarını seçer ve oynatır.
- `tools/serve-character-viewer.cjs`: aynı-origin HTTP sunucu, statik JS/GLB dosyalarını güvenli yerel URL'den açar.
- `tools/check-independent-glb-browser.cjs`: Chromium/SwiftShader ile `idle`, `walk`, `sprint`, `shoot`, `dive-left` hareketleri için görüntüler ve hata raporu kaydeder.
- `player-studio.html`: GLB animasyon inceleme ekranına geçiş bağlantısı eklendi.
- `assets/player/tribun-base-footballer-animated.glb`: yeni sprint hareketleriyle birebir yeniden üretildi.

## Yerelde görüntüleme

Node.js kuruluyken, bağımsız viewer için gerekli Three.js paketini yükle (3D oynatıcının kaynak kodları internetten CDNe gitmez):

```bash
npm install --no-save --no-package-lock --ignore-scripts three@0.181.2
npm run viewer:character
```

Tarayıcıda `http://127.0.0.1:8088/character-viewer.html` adresine git. Kamera sürüklenebilir, fare tekerleğiyle yakınlaşılabilir. Klip listesi, duraklat/oynat ve zaman sürgüsü kullanılabilir.

Aynı anda çalışan oyun stüdyosunda (`player-studio.html`) 19 kemikli özel oyun shader'ı; yeni sayfada ise bağımsız Three.js PBR malzemeleri kullanılır. Görsel farklar bu nedenle beklenir.

## Otomatik doğrulamalar

```bash
npm run test:character-rig
npm run test:footlock
```

GitHub Actions'ta `Character rig and glTF validation` koşusu Node/geometri/GLB/Khronos doğrulamalarını yapar. `Character WebGL visual smoke`, hem eski 3D stüdyonun hem de bağımsız GLB oynatıcısının Chromium görüntülerini ve raporlarını saklar.

## Devam edecekler

Bu aşama profesyonel anatomik karakter, sanatçı üretimi skinning/shape key, mocap, animasyon geçiş ağacı, gerçek zamanlı çevrimiçi GLB animasyon entegrasyonu veya telefonda performans onayı değildir. Kalan kritik çalışma: ayağın yere temas zamanına göre 3D krampon tabanını kalibre etmek, koşudan şuta yumuşak geçiş, birden fazla animasyonun ağırlıklı blend'i, root-motion ve döngü kenarı temizliği.
