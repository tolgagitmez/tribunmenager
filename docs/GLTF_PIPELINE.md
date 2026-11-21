# Blender → standart glTF / GLB akışı

Bu prototip, Blender'ın gerçek glTF içe ve dışa aktarımıyla hazırlanmış bir futbolcuyu standart dosyadan yükler. Kaynak paket [assets/interchange](../assets/interchange/manifest.json), düzenlenebilir dosya [editable.blend](../assets/interchange/editable.blend), tarayıcı karşılaştırması [interop-lab.html](../interop-lab.html) içindedir. Çalışma, içe aktarma ve çizici seçimi için maç simülasyonundan ayrı bir deneme alanıdır.

## Pakette ne var?

| Dosya / özellik | İçerik |
| --- | --- |
| `editable.blend` | Blender 4.3.2 ile kaydedilmiş düzenlenebilir kaynak; bir armature, 19 deform kemiği, mesh'ler, 10 malzeme, iki paketlenmiş görüntü ve dört NLA animasyon izi |
| `footballer.blender.glb` | Blender'ın tek dosyalı glTF 2.0 çıktısı; geometri, iskelet, animasyonlar ve PNG görüntüler dosyanın içinde |
| `footballer.blender.gltf` | Blender'ın JSON çıktısı; yanındaki `.bin` ve `textures/*.png` dosyalarına göreli URI ile başvurur |
| `footballer.blender.bin` | Harici glTF'nin geometri, inverse bind ve animasyon verileri |
| `textures/skin-detail.png`, `textures/fabric-detail.png` | Projede üretilmiş iki CC0 temel renk haritası |
| `manifest.json` | Kaynak, eksen, birim, klipler, sayısal toleranslar ve paket dosyalarının SHA-256 değerleri |
| `rebuild.json` | Araç sürümü, tam üretim komutu, ihracat seçenekleri, kaynak dosya hash'leri ve yeniden üretilebilirlik sınırı |
| `khronos-validation.json` | Sabitlenmiş Khronos glTF Validator raporları |

glTF dosyaları metre cinsinden, +Y yukarı ve +X ileri yönünde hazırlanır. Blender'ın çalışma alanı +Z yukarıdır; içe/dışa aktarım dönüşümü bu farkı karşılar. Sahne 30 fps'dir. Klipler `idle` (1 s), `run` (2 s), `shoot` (1,3 s) ve `dive-right` (1,3 s) adlarını taşır. Şut ve kurtarış için 0,38 s / 0,34 s temas işaretleri manifestte kayıtlıdır; bu işaretler top fiziğini çalıştırmaz.

## Kaynak ve lisans

İnsan modeli, iskelet ve ağırlıkların kaynağı MakeHuman'ın `a8bc2d54ff0ac92e78ff71431b1023eda42bf482` commit'ine sabitlenmiştir. Kaynak URL'ler ve dosya hash'leri [orijinal provenance kaydında](../assets/player/source/provenance.json), bunların paketle taşınan kopyası [manifestte](../assets/interchange/manifest.json) bulunur. Futbol forması ve iki nötr matematiksel doku proje üretimidir. Dört klip, mevcut Tribün rig'inin deterministik örneklerinden üretilmiştir; motion capture içermez.

Varlık paketi CC0-1.0'dır: [krediler](../assets/interchange/CREDITS.md), [CC0 metni](../assets/interchange/LICENSE-CC0.txt), [MakeHuman kaynak/varlık lisans ayrımı](../assets/interchange/SOURCE-LICENSE.md). MakeHuman program kodu bu pakete kopyalanmaz. Blender 4.3.2, GPL-3.0-or-later lisanslı dış üretim aracıdır; Blender program kodu da varlığa eklenmez. Tarayıcıdaki Three.js 0.180.0 ayrı olarak MIT lisansıyla [vendor/three](../vendor/three/LICENSE) altında dağıtılır.

`manifest.json` içindeki `files` listesi, teslim edilen `editable.blend` dahil dosyaların byte uzunluğunu ve SHA-256 değerlerini verir. Bu, hangi düzenlenebilir kaynağın hangi çıktıyla teslim edildiğini izlemeyi sağlar. `.blend` oturum metaverisi içerdiği için yeniden üretimde birebir aynı byte dizisini vermesi beklenmez; geometri, doku ve örneklenmiş pozlar sayısal olarak doğrulanır.

## Yeniden üretme

Proje tarafından desteklenen Node sürümü, `npm ci` ile kurulan sabit bağımlılıklar ve `io_scene_gltf2` eklentisi bulunan Blender 4.3.2 gerekir. Depo kökünden:

```bash
npm ci
blender --background --factory-startup --python-exit-code 1 --python tools/build-blender-interchange.py
```

Bu komut [üretim betiğini](../tools/build-blender-interchange.py) çalıştırır ve `assets/interchange/` paketinin tamamını yeniden oluşturur. Kaynaklar depoda bulunduğu için üretim sırasında ağ gerekmez. Sonradan bu klasöre elle yapılan düzenlemeler komut tekrar çalıştırıldığında üretilen dosyalarla değiştirilir.

Akış şöyledir:

1. [bake-licensed-clips.cjs](../tools/bake-licensed-clips.cjs), mevcut 60 Hz simülasyon rig'inden 30 fps standart animasyon kanalları üretir.
2. Her kemik için dünya eklem matrisi `G_i = SkinMatrix_i × FullBindMatrix_i` olarak geri kazanılır. Yerel matris, ebeveyn dünya matrisinin tersiyle hesaplanır. Böylece yalnız bind konumu değil tam bind dönüşümü hesaba katılır; glTF inverse bind matrisi bunun tersidir.
3. Yerel translation ve normalize quaternion kanalları `LINEAR` örnekler olarak yazılır. 60 Hz fizik/rig zamanı ile 30 fps dosya zamanı açıkça ayrılır; maçın sabit adımı değiştirilmez.
4. Geçici standart GLB, Blender'ın gerçek glTF importer'ıyla açılır. Dört klip ayrı NLA izlerinde tutulur; görüntüler `.blend` içine paketlenir.
5. Blender `GLB` ve `GLTF_SEPARATE` çıktılarını verir. Animasyon, skin, UV, normal, malzeme ve görüntü ihracatı açıktır; 30 fps kareler zorunlu örneklenir, animasyon boyutu optimizasyonu kapalıdır.
6. Khronos doğrulaması çalışır; lisans, provenance, yeniden üretim ve hash kayıtları yazılır.

Standart dışa aktarımda `COLOR_0` glTF'nin istediği 0–1 aralığına alınır; sıfır ağırlıklı kullanılmayan joint yuvaları geçerli indekslerle yazılır ve skinned mesh sahne kökünde tutulur. Bunlar dosya uyumluluğu düzenlemeleridir. Maçın fizik koduna veya kullanılan oyuncu geometrisine yeni bir şekil düzeltmesi uygulanmaz.

Blender byte-color içe aktarımının renk kaybını önlemek için kaynak doğrusal renkler `FLOAT_COLOR` katmanına geri yazılır. Blender custom-normal dönüşümü ve çok küçük ağırlıkları elemesi ayrıca hesaba katılır: ölçülen en büyük normal bileşeni farkı 0,003819'dur; stok exporter `<= 0,0001` ağırlıkları atıp kalanları normalize eder. [Manifest](../assets/interchange/manifest.json) bu yüzden ayrı UV, renk, normal, ağırlık, bind geometri ve deforme köşe toleransları tanımlar. Örneğin kemik dünya / skin matrisleri için `2e-5`, deforme köşeler için `3e-5` metre sınırı vardır.

## Blender'da düzenleme ve dışarıdan dosya alma

`editable.blend` Blender 4.3.2'de doğrudan açılabilir. Armature, mesh, malzemeler ve NLA izleri düzenlenebilir; `GLB` veya `glTF Separate` olarak dışa aktarılabilir. Harici glTF taşınırken JSON, `.bin` ve `textures/` dizini birlikte taşınmalı, göreli yollar korunmalıdır. Tüm üretim ayarlarının esas kaydı [rebuild.json](../assets/interchange/rebuild.json) dosyasıdır.

Three.js yolu, aşağıdaki dört etki ve decoder sınırları içinde başka kemik adlarını ve hiyerarşilerini de kabul eder. Özel maç çizicisinde görünmesi istenen dosyanın ayrıca 19 kemik ve malzeme sözleşmesini koruması gerekir. Bu prototip retargeting, yeni kemiği otomatik eşleme veya animasyon sanatçısı kalite onayı sağlamaz.

## Ortak standart yükleyici

[gltf-asset-loader.mjs](../gltf-asset-loader.mjs) iki çizici için aynı resmi Three.js r180 `GLTFLoader.parseAsync` yolunu kullanır. Standart accessors, buffer views, skin, inverse bind, animasyon ve PBR verileri resmi yükleyiciyle çözülür. Tarayıcı modülleri [yerel vendor paketine](../vendor/three/manifest.json) sabitlenir; uygulamayı açmak için Node veya CDN bağlantısı gerekmez.

Yükleme sırası belgeyi okuma, harici kaynakları alma, kaynak doğrulama, resmi parse ve çözülmüş sahne doğrulamasıdır. Göreli `.bin` ve PNG yolları model URL'sine göre çözülür. `ready`, yalnız JSON'un okunması anlamına gelmez: kullanılan haritaların çözülen piksel boyutları, mesh verisi, iskelet bağları ve animasyon hedefleri denetlenir.

Yükleyici şu sorunları açık hata olarak verir:

- Hatalı GLB başlığı / uzunluğu, geçersiz JSON, glTF sürümü veya yapılandırılmamış zorunlu uzantı.
- Kayıp kök dosya, `.bin` veya PNG için istek URL'si ve HTTP durumu; çözülemeyen görüntü için kaynak ve aşama.
- Döngülü / birden çok ebeveynli hiyerarşi, eksik joint, uyumsuz inverse bind sayısı, geçersiz indeks / ağırlık veya sonlu olmayan veri.
- Geçersiz animasyon hedefi, yinelenen hedef, yanlış kanal türü / örnek sayısı ve artmayan ya da sonlu olmayan zamanlar. `CUBICSPLINE` örnek sayısı dahil kanal kardinalitesi resmi parse öncesinde kontrol edilir.
- Varsayılan 12 saniye zaman aşımı ve `AbortSignal` ile iptal.

Hatalar `stage`, `url`, `code` ve açıklamayı taşır; laboratuvar bunları ilgili çizicinin üzerinde gösterir. Yükleme başarısız olursa, başka yüklemeyle değiştirilirse veya sayfa kapanırsa sahne kaynakları bırakılır. Geometri, malzeme, doku, skeleton, `ImageBitmap` ve geçici object URL sahipliği temizlenir; iptalden sonra geç tamamlanan parse sonucu da serbest bırakılır.

Bu sürümün ortak sınırı köşe başına en fazla dört etkidir (`JOINTS_0` / `WEIGHTS_0`). `JOINTS_1` veya `WEIGHTS_1` açıkça reddedilir; fazladan etki sessizce kesilmez. Draco ve Meshopt decoder'ları yapılandırılmamıştır; bunları zorunlu tutan dosyalar açıklamalı uzantı hatası verir. Standart yükleme desteği tüm glTF uzantılarının desteklendiği anlamına gelmez.

## Çizici desteği

| Özellik | Three.js çizicisi | Mevcut WebGL çizicisine köprü |
| --- | --- | --- |
| Standart GLB / harici glTF | Ortak resmi yükleyici | Aynı ortak yükleyici |
| İskelet | Keyfi ad ve hiyerarşi; ortak dört etki sınırı | Sabit ad ve ebeveyn sıralı 19 kemik; tüm mesh'lerde uyumlu inverse bind |
| Skinning | glTF doğrusal harmanlama, LBS | Rijit dönüşümlerde dual quaternion, DQS |
| Animasyon | Standart TRS ve morph kanalları | Deform kemiklerinin translation / quaternion kanalları; gerçek ölçek, shear ve yansıma reddedilir |
| Malzeme | Resmi Three.js glTF PBR yolu | On anlamsal malzeme yuvası; opaque, front-side, metalness 0, temel renk ve roughness faktörü |
| Haritalar | Yükleyicinin desteklediği standart haritalar | İki ailede temel renk: skin / fabric; sRGB, UV0 ve temsil edilebilir WebGL1 sampler ayarları |
| Morph, alpha, emissive, normal / metallic-roughness haritaları | Standart Three.js desteği | Açıklamalı `CUSTOM_UNSUPPORTED` |

Köprü [gltf-runtime-adapter.mjs](../gltf-runtime-adapter.mjs) içindedir. Kemik sözleşmesi `pelvis`, `spine`, `chest`, `neck`, `head`; iki tarafta `clavicle`, `upper_arm`, `forearm`, `hand`, `thigh`, `shin`, `foot` adları ve `.L` / `.R` ekleridir. Malzeme adları `skin`, `shirt`, `shorts`, `socks`, `boots`, `hair`, `eye-white`, `iris`, `pupil`, `brows` olmalıdır. Aynı anlamsal adı kullanan farklı malzemeler ve yinelenen kemik adları da reddedilir.

Bir doku ailesinde farklı görüntü / sampler kullanımı, dönüşümlü UV, başka UV kanalı, desteklenmeyen NPOT repeat/mipmap veya karışık dokulu/dokusuz yuvalar özel çizicide temsil edilemiyorsa dosya gerekçesiyle reddedilir. Blender'ın birim ölçeğe `0,00002` yakın bake izleri uyarıyla rijit kabul edilir; gerçek ölçek animasyonu Three.js gerektirir. Bu ayrım standart dosyanın bozuk olduğunu söylemez: örneğin geçerli metalik malzeme Three.js'te açılırken özel çizici sınırına takılabilir.

## Açma ve doğrulama

Depo kökünde normal başlatıcıyı çalıştırın:

```bash
python3 start.py --mode local --port 8000
```

`http://127.0.0.1:8000/interop-lab.html` adresinde GLB / harici glTF, dört klip, ortak zaman, 1 / 22 futbolcu ve kamera kontrolleri bulunur. İki panel aynı kaynak klibi `AnimationMixer` ile örnekler. Özel çizici paleti içe aktarılan kemiklerden alır; görüntü için prosedürel rig animasyonuna dönmez. Eski [character-viewer.html](../character-viewer.html) de yerel Three.js paketini kullanır.

[Khronos raporunda](../assets/interchange/khronos-validation.json) kanonik animasyon GLB'si, kaynak oyuncu GLB'si, Blender GLB'si ve Blender harici glTF'si için **dört ayrı raporda 0 hata / 0 uyarı** vardır. Bu standart biçim denetimidir; hareket estetiğini veya gerçek cihaz performansını onaylamaz.

Otomatik paket / yükleyici / köprü kontrolleri ve tarayıcı kanıtı:

```bash
npm run test:gltf
npm run test:stage15
npx playwright install chromium
CHROMIUM="$(node -p 'require("playwright").chromium.executablePath()')" node tools/check-gltf-comparison.cjs
```

Playwright ve PNGJS geliştirme bağımlılıklarıdır; Chromium ayrıca kurulur. `CHROMIUM` açıkça verilmezse betik `/usr/bin/chromium` yolunu kullanır. Uygulamanın normal çalışma zamanı bu test araçlarına ihtiyaç duymaz. `npm run rebuild:interchange` aynı Blender üretim komutunun, `npm run vendor:three` sabitlenmiş yerel Three.js paketini yenilemenin kısa yoludur.

Tam ölçüm yöntemi, sonuçlar ve çizici tercihi [GLTF_RENDERER_DECISION.md](GLTF_RENDERER_DECISION.md) dosyasındadır. Tamamlanmış tarayıcı koşusu 16 poz karşılaştırmasını ve 15 hata / kapsam senaryosunu geçmiştir. Makine tarafından okunabilir sonuç [docs/validation/gltf-comparison.json](validation/gltf-comparison.json) yoluna, karşılaştırma sayfası [gltf-comparison-idle.png](previews/gltf-comparison-idle.png) dosyasına ve ayrı klip kareleri `docs/previews/gltf-{custom,three}-*.png` yollarına yazılır.
