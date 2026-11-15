# Paketlenmiş insan modeli

v1.32.0, insan modelinin maç ve oyuncu stüdyosunda gerçekten kullanıldığını izlenebilir bir paketle doğrular. Model kimliği **`tribun-makehuman-footballer-v1`** olarak sabittir. Oyunu çalıştırmak için modelleme aracı, MakeHuman kurulumu veya haricî model sunucusu gerekmez.

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

Önceki sürüm notlarında adı geçen Blender Studio paketi mevcut çalışma kopyası ve arşivlerden geri getirilemedi. Bu sürüm, o dosyaların geri yüklenmesi değildir. Eski notlardaki Blender kaynak dosyası ve üç LOD güncel pakete ait özellikler sayılmaz. Portre, font ve stadyum görsellerindeki diğer eksikler bu insan modeli paketiyle tamamlanmış olmaz.

## Paketin içeriği

| Dosya | Görevi |
| --- | --- |
| `assets/player/player-model-data.js` | Maç, stüdyo ve hareket atölyesindeki mevcut WebGL çizicisinin kullandığı geometri, 19 kemik ve deri ağırlıkları |
| `assets/player/footballer.glb` | Aynı türev geometri, 19 eklemli skin, inverse-bind matrisleri, malzemeler ve gömülü dokuların standart glTF 2.0 ikili paketi |
| `assets/player/skeleton.json` | Kemik adları, hiyerarşi ve bağlama bilgileri |
| `assets/player/textures/skin-detail.png` | 256 × 256 ten ayrıntısı; yerel dosyadan GPU'ya yüklenir |
| `assets/player/textures/fabric-detail.png` | 256 × 256 kumaş ayrıntısı; yerel dosyadan GPU'ya yüklenir |
| `assets/player/source/*.gz` | Özgün OBJ, varsayılan iskelet ve ağırlık verisinin deterministik sıkıştırılmış kopyaları |

Modelin ölçeği metredir; yukarı ekseni `+Y`, ileri ekseni `+X` olur. Paket tek LOD içerir. Runtime, GLB'yi ayrıştırmaz; GLB taşınabilir kaynak çıktısı olarak dağıtılır. Hareketler mevcut `humanoid-rig.js` pozlarından gelir. Yeni animasyon klibi, mocap, yüz veya parmak animasyon sistemi eklenmedi. Mevcut ayak IK/basış ve ayak-top temas sistemi korunur.

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
```

Windows'ta sanal ortamı `.venv\Scripts\activate` ile etkinleştir; `python` veya `py -3` ve örneğin `--output oyuncu-yeniden-uretim` kullan. NumPy/Pillow kurulumundan sonra üretici ağ bağlantısı kullanmaz. Paketlenmiş kaynakları geçici dizine açar, beş kaynak/lisans dosyasını denetler, rig referansını karşılaştırır ve çıktıları belirtilen dizine üretir. Özel bir paket dizini için `--from-package /dosya/yolu/assets/player` kullanılabilir. `--source-dir` özgün, doğrulanmış indirme dizinine alternatif giriştir; `--from-package` ile birlikte kullanılmaz.

Gözden geçirilmiş rig referansının SHA-256 değeri `2c024a0fd130d50baa04533ae255a8f72b7dc93c269ef3d0af86ae6771820b3d` olur. Rig değiştiğinde pin'i sessizce değiştirmek yerine deformasyon ve temas uyumu yeniden değerlendirilmelidir. Üretim çıktı dizini değişse de paket yolları standart `assets/player/` yollarını korur. Tam bayt eşliği için sabit bağımlılık sürümlerini kullan; farklı kütüphane sürümlerindeki PNG kodlama farkları ayrıca değerlendirilmelidir.

## Doğrulama ve kalan görsel işler

`npm run test:stage13`, önceki maç kontrollerini ve yeni model/durum/paket testlerini çalıştırır. Yalnız yeni varlık kontrolleri için `npm run test:player-assets` kullanılabilir. Paket testleri GLB ile runtime geometrisinin eşliğini, iskelet/deri/doku yapısını, kaynak/lisans kayıtlarını ve ayrı çıktı dizininde yeniden üretimi kapsar. Değiştirilmiş kaynak veya lisans ve yeniden yazılmış kaynak kaydı reddedilmelidir. `python3 tools/check-player-asset-tests.py` tam paketi çalıştırarak kaynak hash'lerini ve ham günlük kaydını içeren [test raporunu](validation/player-asset-tests.json) üretir.

Gerçek Chromium aracı:

```sh
python3 tools/check-player-asset-browser.py
```

Araç belgelenmiş yerel başlatıcıyı kullanır; Python Playwright ve Chromium gerektirir. İki sayfada indirilen model yanıtının SHA-256 değerini, GPU'daki iskeletli üçgen çizimini, 19 kemik matrisini, kök hareketinden ayrılan deformasyonu, gerçek PNG yüklemelerini ve doku örnekleyicilerini ölçer. Eksik model, bozuk veri, shader hatası, WebGL yokluğu ve eksik PNG iki sayfada ayrı denenir. Hata koşullarında maçın fiziksel durumu kontrol koşuluyla karşılaştırılır. Rapor [player-asset-browser.json](validation/player-asset-browser.json), güncel sonuç ve sınırlar [DOGRULAMA.md](../DOGRULAMA.md) içindedir.

Bu kontroller modelin gerçekten kullanıldığını ve arızaların teşhis edilebildiğini gösterir. Fotoğraf gerçekçiliği, kesintisiz maç boyunca kusursuz giysi/eklem deformasyonu veya gerçek cihaz FPS kabulü sağlamaz. Yakın yüz/saç, giysi ayrıntıları, hareket geçişleri ve birden fazla LOD sonraki [animasyon yol haritasında](../ANIMASYON_YOL_HARITASI.md) ele alınır.
