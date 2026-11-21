# Paketlenmiş insan modeli

v1.33.0, lisanslı insan modelini düzeltilmiş kanonik insan iskeletiyle maç, oyuncu stüdyosu ve hareket atölyesinde kullanır. Model kimliği **`tribun-makehuman-footballer-v1`** olarak sabittir. Üretici ile çizici aynı 19 kemik çerçevesini paylaşır; sabit uzuv uzunlukları, oyun amaçlı eklem sınırları ve rijit dual quaternion skinning [karakter modeli sözleşmesinde](CHARACTER_MODEL.md) açıklanır. Oyunu çalıştırmak için modelleme aracı, MakeHuman kurulumu veya haricî model sunucusu gerekmez.

GitHub `main` karakter geliştirmeleri korunmuştur. Ayrı prosedürel stüdyo ve 15 klipli GLB laboratuvarı bu lisanslı paketin yerine geçmez; kendi dosyalarını kullanır. Lisanslı manifestin 13 dosyalık üretim kapsamına paralel laboratuvar dosyaları eklenmez. Maçın FPS profilleri, hareket geçiş köprüsü, hızlı shader yolu ve çalışma anı LOD'ları lisanslı modele uygulanmaya devam eder.

## Kaynak ve kullanım lisansı

Anatomik temel, [MakeHuman Community resmî deposundaki](https://github.com/makehumancommunity/makehuman) `a8bc2d54ff0ac92e78ff71431b1023eda42bf482` commit'inin hm08 OBJ verisidir. Aynı sürümün varsayılan iskelet ve deri ağırlıkları kullanılır. OBJ başlığı varlığı Eylül 2020'de açıkça CC0 olarak yayımlar; iskelet ve ağırlık dosyaları da CC0 bildirir. Resmî politika grafik varlıkları ile AGPL program kodunu ayırır. Bu pakete program kodu alınmadı.

| Kanıt | İçerik |
| --- | --- |
| [CREDITS.md](../assets/player/CREDITS.md) | İnsan modelinin kaynağı, sahipleri, türev eklemeler ve kullanım kapsamı |
| [source/provenance.json](../assets/player/source/provenance.json) | Beş resmî kaynak/lisans dosyasının tam URL, commit, boyut ve SHA-256 kaydı |
| [SOURCE-LICENSE.md](../assets/player/SOURCE-LICENSE.md) | Program kodu ile CC0 varlıkları ayıran resmî lisans politikası |
| [LICENSE-CC0.txt](../assets/player/LICENSE-CC0.txt) | Kaynak deposundaki CC0 varlık lisansı metni |
| [manifest.json](../assets/player/manifest.json) | Paket kimliği, geometri/iskelet bilgisi ve dağıtılan dosyaların boyut/hash kayıtları |

Kaynak OBJ'nin SHA-256 değeri `8e761e6624b8f54536409135d1636da63b32486a90d4897f84e121d144f6fb4c` olarak sabittir. Üretici, lisans metinleri dahil beş dosyanın hash'ini ve resmî URL'sini denetler; kaynak kaydını değiştirerek başka bir modeli sessizce kabul etmez.

Forma yerleşimi ve giysi uyarlamaları, krampon, göz/kaş ekleri, 19 kemikli deri uyarlaması ve iki ayrıntı dokusu projeye ait CC0 türevlerdir. Doku dosyaları matematiksel üretilen nötr haritalardır. Gerçek futbolcu fotoğrafı, yüz taraması veya kulüp/sponsor işareti kullanılmadı.

Önceki sürüm notlarında adı geçen Blender Studio paketi mevcut çalışma kopyası ve arşivlerden geri getirilemedi. Güncel insan varlığı, kaynağı ayrıca doğrulanmış MakeHuman türevidir; eski Blender paketinin geri yüklenmesi değildir. Düzenlenebilir özgün `.blend` teslimi bu paketin bir özelliği sayılmaz. Portre, font ve stadyum görsellerindeki diğer eksikler bu insan modeli paketiyle tamamlanmış olmaz.

## Paketin içeriği

| Dosya | Görevi |
| --- | --- |
| `assets/player/player-model-data.js` | Maç, stüdyo ve hareket atölyesindeki mevcut WebGL çizicisinin kullandığı geometri, 19 kemik ve deri ağırlıkları |
| `assets/player/footballer.glb` | Aynı türev geometri, 19 eklemli skin, inverse-bind matrisleri, malzemeler ve gömülü dokuların standart glTF 2.0 ikili paketi |
| `assets/player/skeleton.json` | Kemik adları, hiyerarşi ve bağlama bilgileri |
| `assets/player/textures/skin-detail.png` | 256 × 256 ten ayrıntısı; yerel dosyadan GPU'ya yüklenir |
| `assets/player/textures/fabric-detail.png` | 256 × 256 kumaş ayrıntısı; yerel dosyadan GPU'ya yüklenir |
| `assets/player/source/*.gz` | Özgün OBJ, varsayılan iskelet ve ağırlık verisinin deterministik sıkıştırılmış kopyaları |

Modelin ölçeği metredir; yukarı ekseni `+Y`, ileri ekseni `+X` olur. Lisanslı paket tek tam çözünürlüklü LOD içerir. `player-renderer.js`, maç çizim bütçesi için bu geometriden ek çalışma anı LOD'ları üretir; kaynak dosyayı veya manifesti yeniden yazmaz. Runtime, lisanslı GLB'yi ayrıştırmaz; GLB taşınabilir çıktı olarak dağıtılır. Hareketler kanonik `humanoid-rig.js` pozlarından gelir. Bağımsız görüntüleyicinin 15 prosedürel klibi bu lisanslı GLB'ye eklenmemiştir. Mocap, yüz veya parmak animasyon sistemi eklenmedi.

`Rig.boneFrames` üretici ve çizici için ortak uç nokta kaynağıdır. Bağlama ve ters bağlama matrisleri, gözden geçirilmiş rig'le birlikte üretilir. Çalışma anında kemik uzunluğu hedefe göre ölçeklenmez; erişim dışı hedefler sabit uzunluk ve açı sınırlarıyla çözülür. `player-skinning.js`, ölçek ve makaslama içermeyen rijit paleti normalize dual quaternion'a çevirir; GPU aynı sözleşmeyle köşeleri ve normalleri taşır. DQS'nin dönüş kaynaklı eklem çökmesini azaltması, bütün mesh hacminin veya uç poz kalitesinin kabulü yerine geçmez.

Paralel deney dosyaları `procedural-player-model-data.js`, `tribun-base-footballer.glb` ve `tribun-base-footballer-animated.glb` adlarını kullanır. Bunlar `humanoid-rig-procedural.js` / `player-renderer-procedural.js` ile üretilir veya incelenir; lisanslı `footballer.glb` ile aynı varlık gibi karşılaştırılmamalıdır.

## Oyunda kontrol etme

1. [Kurulum rehberindeki](../KURULUM.md) `start.py` başlatıcısıyla oyunu aç.
2. Kadro → Taktik → Maçı başlat yolunu izle. Model panelindeki **İSKELETLİ OYUNCU MODELİ** ayrıntısını aç; model kimliği ve kaynak dosyası yollarını kontrol et.
3. Aynı sunucunun `player-studio.html` sayfasını aç. Tam boy, yüz ve arka kameralarında modeli incele; hareket, forma ve görünüm seçeneklerini değiştir.

Stüdyo yüz kamerası anatomiyi yakından incelemek içindir. Maç kamerasında aynı model çizilir; geniş yayın kadrajındaki küçük oyuncuların görünmesi tek başına yüz kalitesi kabulü sayılmaz.

## Yükleme ve hata sözleşmesi

`player-asset-status.js` ortak doğrulama ve görünür durum panelini sağlar. Model verisi geldiğinde kemikler, matrisler, köşe tamponları, indisler ve deri ağırlıkları denetlenir. Ardından çizici iki dokuyu yükler. **Hazır** durumu, yalnız model bildirimi bulunmasına dayanmaz; çizici ve iki doku hazırlanmış olmalıdır.

| Teknik durum | Anlamı ve davranış |
| --- | --- |
| `loading` | Model veya dokular hazırlanıyor; ayrıntılı çizici henüz etkin değil |
| `ready` | Paketlenmiş iskeletli model ve iki doku çizime hazır |
| `missing` | Model betiği yüklenemedi; beklenen dosya yolu ve biliniyorsa HTTP durumu gösterilir |
| `invalid` | Veri çizici sözleşmesine uymuyor; hatalı alan ve doğrulama kodu gösterilir |
| `webgl-unavailable` | WebGL yok; maç 2D çizime geçer, stüdyo görünür hata verir |
| `renderer-error` | Shader veya doku hazırlanamadı; hata metni ve ilgili doku yolu gösterilir |

Maç, model hatasında prosedürel WebGL yedeğiyle sürebilir. Stüdyo, yüklenemeyen ayrıntılı modeli başarılı saymaz ve hata gösterir. Tarayıcı HTTP durumunu sunmuyorsa panel kesin bir `404` uydurmaz; ağ/yükleme hatası olarak bildirir. Panel metinleri veri bildirimi olarak okunmalıdır: lisansın ve kaynak dosyalarının doğrulanması üretici ve paket testlerinde ayrıca yapılır.

## Çevrimdışı yeniden üretme

Oynamak için gerekli değildir. Doğrulanan üretim araçları **Python 3.11+**, [requirements-player-assets.txt](../requirements-player-assets.txt) içindeki sabit NumPy/Pillow sürümleri ve mevcut rig referansını okumak için Node.js gerektirir. Geliştirme araçlarını ayrı bir sanal ortama kurabilirsin:

```sh
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-player-assets.txt
python3 tools/build-player-assets.py --from-package --output /tmp/tribun-player-rebuild
python3 tools/verify-player-asset-rebuild.py --package assets/player --rebuilt /tmp/tribun-player-rebuild
```

Karşılaştırıcı iki paketin de manifest SHA-256 kayıtlarının geçerli olmasını ister. Özgün CC0 kaynakları, lisans, provenance, indeksler, eklemler ve PNG dosyaları birebir; yalnız türetilmiş GLB/runtime modelin kayan noktalı geometri bileşenleri en çok **2 × 10⁻⁶**, JSON matris/istatistik sayıları en çok **10⁻¹⁰** mutlak farkla eşdeğer olmalıdır. Bu kontrol, farklı BLAS/CPU/NumPy ortamlarında *bayt düzeyinde yeniden üretimi garanti etmez*; kaynak orijinalliğini ve geometri eşitliğini ayrı ayrı doğrular.

Windows'ta sanal ortamı `.venv\Scripts\activate` ile etkinleştir; `python` veya `py -3` ve örneğin `--output oyuncu-yeniden-uretim` kullan. NumPy/Pillow kurulumundan sonra üretici ağ bağlantısı kullanmaz. Paketlenmiş kaynakları geçici dizine açar, beş kaynak/lisans dosyasını denetler, rig referansını karşılaştırır ve çıktıları belirtilen dizine üretir. Özel bir paket dizini için `--from-package /dosya/yolu/assets/player` kullanılabilir. `--source-dir` özgün, doğrulanmış indirme dizinine alternatif giriştir; `--from-package` ile birlikte kullanılmaz.

Gözden geçirilmiş rig referansı, üreticideki `RIG_SHA256` pin'i ve paketin `rigReferenceSHA256` kaydıyla sabitlenir. v1.33.0 kanonik rig düzeltmesi bağlama varlıklarıyla birlikte yeniden üretilir; eski v1.32 rig hash'i güncel üretim pin'i olarak kullanılmaz. Rig değiştiğinde pin'i sessizce değiştirmek yerine deformasyon ve temas uyumu yeniden değerlendirilmelidir. Üretim çıktı dizini değişse de paket yolları standart `assets/player/` yollarını korur. Tam bayt eşliği için sabit bağımlılık sürümlerini kullan; farklı kütüphane sürümlerindeki PNG kodlama farkları ayrıca değerlendirilmelidir. Yeniden üretim karşılaştırması lisanslı manifest kapsamındaki dosyalara uygulanır; aynı dizindeki prosedürel laboratuvar varlıkları bu sayıya katılmaz.

## Doğrulama ve kalan görsel işler

`npm run test:player-assets`, lisanslı varlığın model/durum/paket kontrollerini çalıştırır. Paket testleri GLB ile runtime geometrisinin eşliğini, iskelet/deri/doku yapısını, kaynak/lisans kayıtlarını ve ayrı çıktı dizininde yeniden üretimi kapsar. Değiştirilmiş kaynak veya lisans ve yeniden yazılmış kaynak kaydı reddedilmelidir. Kanonik rig ve gerçek yüzey deformasyonu kontrolleri, maçın FPS/LOD/hareket köprüsü ile ayrı prosedürel laboratuvar regresyonlarıyla birlikte değerlendirilir. Güncel toplu komutlar, kaynak hash'leri ve sonuç raporları [DOGRULAMA.md](../DOGRULAMA.md) içindedir; tarihsel aşama 13 toplamları yeni kabul sonucu olarak kullanılmaz.

Gerçek Chromium aracı:

```sh
python3 tools/check-player-asset-browser.py
```

Araç belgelenmiş yerel başlatıcıyı kullanır; Python Playwright ve Chromium gerektirir. İki sayfada indirilen model yanıtının SHA-256 değerini, GPU'daki iskeletli üçgen çizimini, 19 kemiklik paleti, kök hareketinden ayrılan deformasyonu, gerçek PNG yüklemelerini ve doku örnekleyicilerini ölçer. Eksik model, bozuk veri, shader hatası, WebGL yokluğu ve eksik PNG iki sayfada ayrı denenir. Hata koşullarında maçın fiziksel durumu kontrol koşuluyla karşılaştırılır. Rapor [player-asset-browser.json](validation/player-asset-browser.json), güncel kaynak ve sonuç sınırları [DOGRULAMA.md](../DOGRULAMA.md) içindedir. Bir raporun hangi kaynakla üretildiği kontrol edilmeden önceki sürümün sonucu güncel sayılmaz.

Bu kontroller modelin gerçekten kullanıldığını ve arızaların teşhis edilebildiğini gösterir. Fotoğraf gerçekçiliği, kesintisiz maç boyunca kusursuz giysi/eklem deformasyonu veya gerçek cihaz FPS kabulü sağlamaz. Yakın yüz/saç, giysi ayrıntıları, düzeltici eklem şekilleri, temas uyumu ve mevcut çalışma anı LOD'larının gerçek cihaz ölçümleri sonraki [animasyon yol haritasında](../ANIMASYON_YOL_HARITASI.md) ele alınır.
