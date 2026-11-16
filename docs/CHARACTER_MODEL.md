# Güncel karakter modeli sözleşmesi — v1.33.0

Bu aşama, tek bir insan gövdesinin oranlarını, sabit kemiklerini, eklem sınırlarını ve deri deformasyonunu üretim maçına bağlar. Lisanslı MakeHuman modeli, maç/stüdyo/atölye çiziminde kullanılan kanonik `humanoid-rig.js` iskeletine uyarlanır. GitHub `main` üzerindeki karakter geliştirmeleri korunur; eski prosedürel deney modeli de ayrı girişleriyle kullanılabilir.

## Üretim ve laboratuvar yolları

| Kullanım | İskelet ve varlık | Çizim / hareket |
| --- | --- | --- |
| `match.html`, `player-studio.html`, `animation-lab.html` | `humanoid-rig.js`, `assets/player/player-model-data.js` | `player-renderer.js`, `player-skinning.js`; kanonik insan pozları |
| `player-studio-procedural.html` | `humanoid-rig-procedural.js`, `assets/player/procedural-player-model-data.js` | `player-renderer-procedural.js`; korunmuş prosedürel deney |
| `character-viewer.html` | `assets/player/tribun-base-footballer-animated.glb` | Bağımsız glTF oynatıcı; dışa aktarılmış 15 prosedürel klip |

Üretimdeki paket kimliği `tribun-makehuman-footballer-v1` olarak kalır. `assets/player/footballer.glb`, lisanslı modelin standart aktarım çıktısıdır; maç mevcut özel model verisini yükler. Animasyonlu laboratuvar GLB'si farklı geometriye ve üretim yoluna aittir; bu dosyanın bulunması maçın GLB animasyon kanallarını oynattığı anlamına gelmez.

## Kanonik insan ölçüleri

Ölçüler metre cinsindedir; yukarı eksen `+Y`, ileri eksen `+X` olur. `Rig.ANATOMY` tek referanstır. Uzuv uzunluğu hareketle veya hedef uzaklığıyla ölçeklenmez.

| Ölçü | Değer |
| --- | ---: |
| Referans boy | 1,88 m |
| Nötr pelvis yüksekliği | 1,03 m |
| Kalça eklemleri arası genişlik | 0,26 m |
| Omuz eklemleri arası genişlik | 0,44 m |
| Nötr omuz yüksekliği | 1,50 m |
| Uyluk / baldır | 0,475 / 0,431 m |
| Üstkol / önkol | 0,315 / 0,290 m |
| Bilekten el ucuna | 0,170 m |
| Bilekten fiziksel avuç referansına | 0,115 m |

Boy, kanonik nötr referansın boyudur; koşu eğimi, diz bükülmesi ve dalış sırasında dünya ekseninde ölçülen anlık yükseklik farklı olabilir. Forma ve krampon yüzeyi, eklem merkezleri arasındaki mesafeden ayrı değerlendirilir.

`Rig.boneFrames(pose)`, beş gövde kemiğini (`pelvis`, `spine`, `chest`, `neck`, `head`) ve her yanda yedi kemiği (`clavicle`, `upper_arm`, `forearm`, `hand`, `thigh`, `shin`, `foot`) verir. Sonuç, poz başına önbelleklenen değişmez uç nokta çiftleridir. Varlık üreticisi ve GPU paleti aynı uç noktaları kullanır; omuz veya el için bağımsız görsel uzaklık eklenmez. Rig değişikliği bağlama matrisleri ve lisanslı türev varlıklarla birlikte yeniden üretilip değerlendirilir.

## Oyun amaçlı eklem sınırları

`Rig.LIMITS` aşağıdaki oyun güvenlik sınırlarını tanımlar. Bunlar tıbbi hareket açıklığı ölçümü, biyomekanik doğrulama veya her insan için anatomik bir standart değildir. Diz/dirsek değeri düz uzuvdan bükülmeyi; kalça/omuz değerleri gövdenin yerel çerçevesindeki açıyı ifade eder.

| Eklem / hareket | İzin verilen aralık |
| --- | --- |
| Diz bükülmesi | 0,045 rad – 150° |
| Dirsek bükülmesi | 0,060 rad – 150° |
| Kalça öne/arkaya | −35° – 125° |
| Kalça yana | −35° – 65° |
| Omuz öne/arkaya | −70° – 175° |
| Omuz yana | −35° – 90° |
| Gövde öne/arkaya | −12° – 55° |
| Gövde yana eğilme | ±12° |

İki kemikli IK, hedefi önce izin verilen bükülmeye karşılık gelen erişim aralığına yansıtır. Omuz/kalça sınırı aşılırsa çözülmüş uzuv bir bütün olarak döndürülür; uzak segment uzatılmaz. Dalışta yerel gövde çerçevesi de döner. Ulaşamayan hedefin farkı `targetError` ile taşınır; ayak ulaşılamayan bir noktada basılı sayılmaz.

Kalecinin eski fiziksel `saveHands`/`catchHands` hedefleri korunur. İnsan boyundaki kollar bu hedefe yetişemediğinde çizim pozuna sınırlı bir kök düzeltmesi uygulanabilir; `presentationReach` üst sınırı 0,28 m'dir. Bu düzeltme oyuncunun fiziksel konumuna yazılmaz. Görünen avuç/hedef farkı ayrıca ölçülmelidir; uzunluk ve açı testlerinin geçmesi tek başına kusursuz temas görüntüsü sayılmaz.

## Deri çizimi ve hacim iddiasının sınırı

`player-skinning.js`, paletteki dönüşümlerin sonlu, ortonormal ve pozitif yönlü rijit matrisler olduğunu denetler. Her dönüşüm gerçek ve dual quaternion'a çevrilir. Bir köşenin kemik quaternion'ları aynı işarete hizalanır; ağırlıklı sonuç normalize edilir ve dual bileşen gerçek bileşene dikleştirilir. GPU, bu rijit dönüşümle konumu; aynı rotasyonla normali taşır.

Geçiş köprüsünün dünya uzayındaki kemik rotasyonları korunur; `character-palette-constraints.js` geçiş sırasında çocuk kemiklerin bağlama noktalarını ebeveyne yeniden bağlar. Omuz/kalça açıları ve diz/dirsek bükülmeleri yeniden sınırlandırılır. Böylece yalnız matrisin rijit olmasıyla gözden kaçan, eklem bağlantılarının ayrılması da engellenir. Kök dünya dönüşümü değişmez; düzeltme maç verisine yazılmaz.

Runtime deri ağırlıkları, altı omuz/dirsek/diz bölgesindeki 1.296 kaynak köşede altı yerel Jacobi adımıyla yumuşatılır. 3.556 el/bilek köşesi korunur; bağlama geometrisi, UV, normal ve malzeme sınırları bu ağırlık düzenlemesinde değişmez. Üretim parametreleri manifestte kayıtlıdır; sıkıştırılmış resmî kaynak ağırlıkları aynen tutulur.

Bu yöntem, rotasyon matrislerini doğrudan ağırlıklandıran LBS'nin eklem çevresinde oluşturduğu büzülmeyi azaltır. Sabit kemik ve rijit dönüşüm, bir kemik etkisindeki geometrinin ölçeklenmesini engeller. Birden fazla kemiğin etkilediği bütün mesh için tam hacim korunumu garantisi vermez. Omuz/kalça kabarması, giysi kesişmesi, bilek burulması ve uç poz silueti gerçek köşe/üçgen yüzeyinde ayrıca incelenir. Yüzey ölçümlerinin pozları, karşılaştırma yöntemi ve kabul sınırları güncel doğrulama raporunda belirtilmelidir.

Bu teslimde heykellenmiş corrective shape key, twist bone zinciri, kas/yağ simülasyonu, parmak iskeleti veya lisanslı mocap yoktur. Sanatçı kontrollü bu çalışmalar, temel iskelet ve yüzey doğrulamasının sonraki kalite adımlarıdır.

39 seçilmiş karede en düşük dışbükey kesit alanı oranı 0,97576'dır; ancak uç dalış dirseğinde 2,35 kat genişleme, omuz bölgesinde %18,18 alana dahil sıkı kesişim kalır. Bu ölçüm kapalı doku hacmi değildir ve görsel kusursuzluk sayılmaz. Sıradan futbol pozlarındaki ölçülen kesişim alanı üst gözlemi %2,72'dir. Normal dalış avuç hedefi farkı en çok 2,2 mm, geniş ve fiziksel olarak zorlanmış hedef matrisinde 16,3 cm'dir; ulaşılamayan ayak hedefleri de basış sayılmaz. Ayrıntılı pozlar ve ölçüm sınırları doğrulama raporundadır.

## Maç ve performans sözleşmesi

`football-sim.js`, topun çıkışı, temas kararları, skor, taktikler ve RNG için otorite olarak kalır. Bu aşamada motor kaynağı ve `kickContact` ile fiziksel `saveHands` hedefleri korunur. Kanonik poz ve görünüm düzeltmeleri topu veya oyuncunun fiziksel koordinatlarını yeni bir noktaya taşımaz. `Rig.update` sabit adımda çalışır; çizici hazırlanmış pozu okur.

GitHub'dan gelen `match-animation-bridge.js` hareket geçişi, `scene3d.js` FPS/çözünürlük profilleri, çalışma anı LOD sadeleştirmesi ve `uFast` shader yolu korunur. Lisanslı dağıtım paketi tek tam çözünürlüklü kaynak içerir; çizici maç için bundan daha düşük çalışma anı LOD'ları üretir. Bu ayrım, kaynak manifestinin bütünlüğünü korurken maç çizim bütçesinin yönetilmesini sağlar. SwiftShader veya masaüstü tarayıcı ölçümü gerçek telefon FPS kabulünün yerine geçmez.

Kaynak, CC0 lisansı, beş dosyalık pin ve çevrimdışı yeniden üretim [PLAYER_ASSETS.md](PLAYER_ASSETS.md) içinde; güncel test/görüntü kanıtları [DOGRULAMA.md](../DOGRULAMA.md) içinde tutulur. `CHARACTER_RIG_PHASE1–8` belgeleri kendi dönemlerinin deney kayıtlarıdır; eski eksik Blender/GLB ifadeleri bu güncel paketin durumu olarak okunmamalıdır.
