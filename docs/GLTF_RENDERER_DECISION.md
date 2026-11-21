# Standart glTF için çizici karşılaştırması

Bu belge, aynı Blender futbolcusunun mevcut özel WebGL1 çizicisi ve Three.js r180 çizicisiyle çalıştırıldığı prototipin kapsamını ve karar dayanağını açıklar. Karşılaştırma [interop-lab.html](../interop-lab.html) içindedir; varlık üretimi ve yükleme sözleşmesi [GLTF_PIPELINE.md](GLTF_PIPELINE.md) dosyasındadır. Maç fiziği, taktikler, skor ve top davranışı bu çalışmanın kapsamına girmez.

## Karşılaştırılan iki yol

İki panel aynı [Blender GLB'sini](../assets/interchange/footballer.blender.glb) ortak [resmi GLTFLoader katmanıyla](../gltf-asset-loader.mjs) çözer. Her iki tarafta da `SkeletonUtils.clone` ile oyuncu başına bağımsız iskelet, `AnimationMixer` ile gerçek içe aktarılan klip ve aynı klip zamanı kullanılır. Özel çizicinin animasyon kaynağı prosedürel `Rig` değildir; [köprü](../gltf-runtime-adapter.mjs) ithal kemiklerin dünya matrislerinden GPU paletini üretir. Geometri ve malzemeler oyuncular arasında paylaşılır.

| Boyut | Mevcut WebGL | Three.js |
| --- | --- | --- |
| Çizim API'si | WebGL1, mevcut `PlayerRenderer` | WebGL2, r180 `WebGLRenderer` |
| Skinning | Dual quaternion (DQS) | glTF doğrusal harmanlama (LBS) |
| Gönderilen geometri | Tam kaynak geometri, tek birleşik material-ID mesh | Aynı tam kaynak geometri, glTF'nin on malzeme primitive'i |
| Malzeme girişi | Çözülen iki temel renk haritası, malzeme renk / roughness faktörleri ve sampler ayarları | Aynı kaynakların resmi `MeshStandardMaterial` karşılıkları |
| Kapsam | Rijit, adlandırılmış 19 kemik ve sınırlı malzeme sözleşmesi | Keyfi iskelet ve daha geniş standart glTF malzeme / animasyon desteği |
| Otomatik kalite / LOD | Kapalı | Kapalı |

Kamera, oyuncu yerleşimi, çizim tamponu ve örneklenen zamanlar eşittir. Işıklar sabittir ve düz bir zemin vardır. Özel çizicide prosedürel görünüş ayrıntıları kapalıdır. İki ayrı WebGL bağlamı kullanılır; bir panelin durumu diğerinin hatasını gizlemez.

## Ölçüm yöntemi

Tekrarlanabilir kanıt betiği [tools/check-gltf-comparison.cjs](../tools/check-gltf-comparison.cjs), ham rapor hedefi [validation/gltf-comparison.json](validation/gltf-comparison.json) dosyasıdır. Normal uygulama `python3 start.py --mode local` ile açılır; kanıt betiği aynı dosyaları yerel HTTP sunucusundan servis eder. Ağdan model veya CDN modülü alınmaz.

Betik Chromium'u SwiftShader yazılımsal WebGL ile çalıştırır. Her panel **600 × 560 piksel, DPR 1** olarak ayarlanır. 1 ve 22 futbolcu için her çizicide **üç deneme, her denemede 30 ısınma karesi ve 60 ölçülen kare** vardır. Çalışma sırası denemeler arasında değiştirilir. Ölçüm başlamadan önce `gl.finish()` ve eşzamanlı 1 × 1 RGBA8 `readPixels` önceki işi boşaltır; çizimden sonra aynı dört byte'lık okuma ölçümün içinde tekrarlanır. Ölçüm sırasında `requestAnimationFrame` animasyonu ve otomatik kalite kapalıdır. İlk yükleme ve ilk kare sıcak karelerden ayrı tutulur.

Zamanlanan karelerde GL gözlem sarmalayıcıları kaldırılır; gerçek yerel WebGL metotları çağrılır. Çizim / bellek / upload sayımları ayrı, zamanlanmayan bir probda alınır. Böylece daha fazla GL çağrısı yapan çiziciye ölçüm aracının Map / sayaç işçiliği eklenmez. Sıcak performans örnekleri `run` klibinde 0,05 saniyeden başlayan aynı zaman dizisini kullanır; dört klibin doğruluk ve görüntü kanıtı ayrıca toplanır.

| Alan | Ölçülen iş |
| --- | --- |
| `sharedLoadMs` | Dosya / bağımlılık alımı, ortak resmi parse, doku çözme ve doğrulama |
| `backendSetupMs` | Çizici köprüsü / kaynak / oyuncu hazırlığı |
| `coldLoads.wallMs` | Modüller açıldıktan sonra yeni bağlamda dosya hazırlama ve ilk çizim komutlarını gönderme çağrısının duvar saati süresi |
| `cpuUpdateMs` | Klip örnekleme ve poz / palet güncellemesi |
| `submitMs` | Çizim işlerinin WebGL'e gönderilmesi |
| `completedFrameMs` | CPU güncellemesi + gönderim + `gl.finish()` ve eşzamanlı dört byte `readPixels` tamamlanma beklemesi |

`completedFrameMs`, okuma ve tarayıcı / sürücü eşzamanlama maliyeti dahil duvar saati süresidir. SwiftShader üzerinde seri tamamlanma gecikmesini gösterir; saf GPU çalışma süresini, donanımın işlem örtüşmesini veya gerçek cihaz FPS'ini göstermez. Bu adaptörde yalnız `gl.finish()` ile yapılan tanı ölçümü 0,5–3,4 ms dönerken ardından gelen `readPixels` hâlâ 27–81 ms beklemiştir. Bu nedenle kanıt betiği her zamanlama örneğinde gerçek piksel okuma tamamlanmasını zorunlu tutar. Bu rapordan telefon, tablet veya masaüstü için FPS sözü çıkarılamaz. İki tarafın yüklemesi de aynı parser'ı içerdiği için yükleme sayıları bağımsız parser yarışı olarak yorumlanamaz.

Soğuk hazırlık çağrısındaki ilk çizim GPU tamamlanmasını beklemez; GPU işi bu çağrı döndüğünde kuyrukta kalabilir. `firstFrameAfterLoad` ölçümü önce bu işi kendi zamanlayıcısının dışında boşaltır. Bu iki süreyi toplamak gerçek ilk görüntüye kadar geçen toplam süreyi veya toplam shader derleme maliyetini vermez. Başlangıcın GPU maliyeti bu raporda tam ayrıştırılmamıştır; kararın performans dayanağı ısınmış, eşzamanlı piksel okumasıyla tamamlanan karelerdir.

Sayfa üzerindeki isteğe bağlı kısa ölçüm düğmesi 12 ısınma + 30 kare toplar; bu belgeye esas olan üç denemeli kanıt koşusundan ayrıdır. Canlı sayaçta GPU beklenmeyen karelerin değeri gönderim süresi olarak etiketlenir.

## Eşit olmayan işler ve yorum sınırı

Bu, saf bir motor hızı karşılaştırması değildir. Aynı giriş verisi farklı render işlerine dönüşür:

- DQS ve LBS aynı kemik hareketinde farklı eklem hacmi / yüzey şekli üretir. Kemik matrisi eşitliği piksel eşitliği sağlamaz.
- Özel çizici oyuncu başına bir material-ID çizimi yaparken Three.js on glTF malzeme primitive'i çizer. Zemin her iki tarafta ek bir çizimdir.
- Özel PBR shader'ı ile Three.js'in BRDF, renk / tone mapping ve malzeme kapsamı aynı değildir. Aynı renk ve harita girdisi aynı ışık sonucunu garanti etmez.
- Three.js'in bu fixture'daki klonlarında on skinned primitive için oyuncu başına on skeleton palet dokusu vardır. Özel çizici 19 gerçek + 19 dual quaternion `vec4` uniform'u, yani oyuncu başına 608 byte kemik verisi gönderir. Bu, farklı hazırlama ve upload maliyetleri yaratır.
- Mevcut çizici LOD kapalı olsa da soğuk hazırlıkta kullanılmayan LOD verisi türetebilir. Bu hazırlık maliyeti sıcak çizim maliyetinden ayrılmalıdır.

Bellek sayıları varsa gözlenen GL buffer tahsisleri ve tahmini texture byte'larıdır; tarayıcı / sürücü toplam belleği veya hassas VRAM ölçümü değildir. Özellikle geometry paylaşımı, klon skeleton'ları ve texture mipmap'leri ayrı değerlendirilmelidir.

## Doğruluk ve hata kanıtı

Betik dosyanın gerçekten Blender çıktısı olduğunu, aynı fixture hash'ini, on malzemeyi, 19 kemiği ve dört klibi doğrular. Gerçek GL çizimleri, üçgenler, uniform / texture upload'ları, shader derleme sonuçları ve framebuffer piksel okumaları gözlenir; renderer veya animasyon mock'lanmaz.

`idle`, `run`, `shoot` ve `dive-right` klipleri belirli zamanlarda örneklenir. Dünya kemik matrisleri GLB'nin animasyon accessor'larını bağımsız okuyan örnekleyiciyle karşılaştırılır; en büyük mutlak matris farkı `3e-5` altında olmalıdır. Farklı klip / zamanların gerçek görüntüyü değiştirmesi de piksel okumalarıyla denetlenir. Bu kontroller görsel hareketin dosyadan geldiğini kanıtlar; futbol hareketinin doğal olduğuna dair sanatçı değerlendirmesi yerine geçmez.

Harici glTF'nin `.bin` ve PNG istekleri ayrıca kaydedilir. Tarayıcı kanıtı kayıp ana dosya, bozuk dosya, kayıp `.bin`, kayıp PNG, desteklenmeyen zorunlu uzantı, zaman aşımı ve iptal durumlarını her çizici için ayrı bağlamda sınar. Geçerli metalik materyalin Three.js'te çalışırken özel çizici tarafından açıklamalı reddedilmesi de denetlenir. Bu, standart yükleme başarısıyla özel backend kapsamının ayrı olduğunu gösterir. [Yükleyici testleri](../tests/standard-gltf-loader.test.cjs) ayrıca döngülü hiyerarşi, animasyon kardinalitesi, yinelenen zamanlar ve bağlanamayan animasyon hedeflerini denetler.

## Görüntü karşılaştırması

İncelenen sabit kareler aynı insanı, poz zamanını, kamera açısını ve forma / yüz malzemelerini gösterir. Three.js'te yüz, boyun ve omuz çevresinde ışık kontrastı daha güçlüdür; özel çizici daha açık ve düz görünür. Bu gözlem farklı shader'ların aynı kaynağa verdiği görsel karşılıktır.

| Klip ve zaman | Mevcut DQS görüntüsü | Three.js LBS görüntüsü |
| --- | --- | --- |
| `idle`, 0,150 s | [Duruş](previews/gltf-custom-idle.png) | [Duruş](previews/gltf-three-idle.png) |
| `run`, 0,400 s | [Koşu](previews/gltf-custom-run.png) | [Koşu](previews/gltf-three-run.png) |
| `shoot`, 0,260 s | [Şut hazırlığı](previews/gltf-custom-shoot.png) | [Şut hazırlığı](previews/gltf-three-shoot.png) |
| `dive-right`, 0,270 s | [Kurtarış](previews/gltf-custom-dive-right.png) | [Kurtarış](previews/gltf-three-dive-right.png) |

Kurtarışta yukarı kalkan kolun omuz altı Three.js LBS'de daha fazla daralır. DQS daha çok hacim tutar, ancak belirgin omuz kabarması da üretir. Böylece aynı kemik matrislerinin iki skinning yöntemiyle farklı yüzey verdiği görülür. Şut karesi 0,38 s temas işaretinden öncedir; bu kare ayak / top temas kalitesini değerlendirmez. Kareler standart içe aktarmanın ve hareket örneklemesinin kanıtıdır; bütün klibin doğallığına, fotogerçekçiliğe veya sanatçı kalite onayına eşit değildir.

## Ölçülen sonuçlar ve karar

[21 Kasım 2026 tarihli tamamlanmış rapor](validation/gltf-comparison.json), 12 denemede toplam 720 sıcak kare örneği içerir. Aşağıdaki her satır üç denemenin toplam **180 örneğini** birleştirir; süreler milisaniyedir. Üçgen ve çizim sayıları iki üçgenlik zemin dahil gerçek GL probundan gelir. Adaptör her iki bağlamda ANGLE / Vulkan SwiftShader'dır.

| Futbolcu | Çizici | CPU güncelleme medyan / p95 | Gönderim medyan / p95 | Tamamlanan kare medyan / p95 | Çizim | Üçgen |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Mevcut WebGL | 0,1 / 0,2 | 0,2 / 0,4 | **83,9 / 115,3** | 2 | 28.948 |
| 1 | Three.js | 0,1 / 0,2 | 0,5 / 0,8 | **40,0 / 74,6** | 11 | 28.948 |
| 22 | Mevcut WebGL | 0,4 / 0,9 | 1,9 / 2,7 | **858,6 / 999,6** | 23 | 636.814 |
| 22 | Three.js | 0,5 / 1,0 | 5,5 / 9,1 | **587,7 / 736,2** | 221 | 636.814 |

**Three.js prototipi bu ölçümde her iki oyuncu sayısında da daha düşük tamamlanma gecikmesi verir.** Özel çizicinin daha az çizim çağrısı ve daha düşük CPU gönderim maliyeti bu koşuda daha düşük toplam süreye dönüşmemiştir. Sonuç, yukarıdaki farklı skinning / shader / malzeme işlerini birlikte kapsar; tek başına motor adının veya çizim sayısının etkisini ayırmaz.

22 oyuncuda özel çizicinin kemik uniform gönderimi 13.376 byte/kare, Three.js'in float kemik dokusu gönderimi 506.880 byte/karedir. Geometri oyuncular arasında paylaşıldığı için gözlenen GL buffer tahsisi oyuncu sayısıyla artmaz: özel çizicide 1.851.890 byte, Three.js'te 1.232.792 byte'tır. Tahmini texture alanı 22 oyuncuda sırasıyla 699.050 / 1.205.934 byte'tır. Bunlar gözlenen kaynak tahsisleridir; sürücünün toplam bellek tüketimini vermez. Özel çizicinin kullanılmayan LOD hazırlığı ve Three.js'teki primitive başına skeleton kopyaları farklı maliyetlerdir.

Soğuk dosya hazırlama / ilk komut gönderme çağrısının tek örneği özel çizicide 957,8 ms, Three.js'te 520,3 ms'dir. Bunlar yukarıda açıklanan başlangıç sınırlamasıyla okunmalıdır: modül indirme, ilk tamamlanmış görüntü ve tüm GPU derleme süresini kapsayan uçtan uca açılış ölçümü değildir.

Doğruluk koşusu 16 poz kontrolünü geçmiştir; bağımsız GLB örnekleyicisine göre en büyük kemik dünya matrisi farkı `6,73e-7`'dir. 15 hata / kapsam senaryosu tamamlanmıştır. Normal çizimlerde JavaScript, console, shader derleme / link ve GL hatası yoktur; bağlam kaybı görülmemiştir. Harici glTF'nin `.bin` ve iki PNG'si HTTP üzerinden gerçekten yüklenmiştir. Koşunun başında ve sonunda izlenen 32 kaynak dosya hash'i aynıdır.

Bu verilere göre tercih bileşen bazındadır:

1. **Standart dosya girişi için yerel resmi `GLTFLoader` ve Blender paketi benimsenir.** Düzenlenebilir kaynak, standart GLB / harici glTF, lisans, hash ve Khronos doğrulama zinciri somut bir varlık teslimi sağlar. İki backend aynı dosya girişini kullanmayı sürdürür.
2. **Standart varlık inceleme için Three.js yolu esas alınır.** Keyfi iskeletler ve standart PBR / morph / ölçek özellikleri için daha geniş kapsam sunar. Bu fixture'da daha güçlü PBR kontrastı ve daha düşük tamamlanma gecikmesi de bunu destekler. Özel çizici, açıkça tanımlanmış 19 kemikli alt kümenin karşılaştırma seçeneğidir.
3. **Üretim maçında mevcut DQS çizicisi korunur.** Bu tercih hız üstünlüğü iddiasına dayanmaz. Kurtarış örneğinde LBS'ye geçiş omuz hacmini değiştirmiştir; tam maç geçişinden önce kabul edilebilir deformasyon eşliği, malzeme birleştirme / kemik paleti optimizasyonu ve gerçek cihazda bütün 22 oyunculu maç kontrolleri gerekir. Three.js burada ölçülmüş bir adaydır; laboratuvar sonucu tek başına üretim maçını değiştirmez.

## Kalan sınırlar

Paket, mevcut animasyonun Blender gidiş-dönüşünü güvenilir biçimde taşımayı hedefler. Eski yüksek kurtarış pozlarındaki katlanmaların bütünü bu çalışmada düzeltilmez; DQS ve LBS bunları farklı biçimde gösterebilir. Yeni topoloji, corrective shape key, retargeting, ayak/top constraint'i veya sanatçı üretimi yeni hareket bu prototipe dahil değildir.

Üretim maçı için olası bir çizici geçişi ayrıca gerçek cihaz profili, 22 oyunculu maç sahnesi, gölge / ışık maliyeti, malzeme birleştirme ve kemik paleti paylaşımı değerlendirmesi gerektirir. Bu çalışmadaki standart yükleyici ve dosya denemesi, tek başına maç motorunun yeniden yazılması kararı değildir.
