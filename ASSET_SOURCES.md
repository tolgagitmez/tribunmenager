# Görsel kaynakları — v1.12 tasarımı, v1.17 maç karşılaştırması

## Gece stadyumu

Dosya: `assets/ui/stadium-night.png` — 1672 × 941 PNG. Yeni kurgu stadyum görseli bu çalışma sırasında OpenAI image_gen ile sıfırdan üretildi; başka bir stadyum fotoğrafı veya referans görüntüsü kullanılmadı. Üretim modu: text-to-image, opak arka plan. Çıktı dosyası olduğu gibi kullanılır; kırpma ve karartma CSS arka plan kurallarıyla yapılır. Kaynak dosya yeniden örneklenmedi veya rötuşlanmadı.

Son kullanılan üretim istemi:

> Use case: stylized-concept. Asset type: cinematic stadium background artwork for the commercial football management game Tribün Manager, to be placed behind real HTML interface panels. Primary request: an impressive, original football stadium silhouette and floodlight atmosphere. Scene: a fictional contemporary football stadium at night, viewed from a low corner of the empty pitch toward the far stands, a sweeping curved roof and tall floodlights, subtle haze catching white light, rich dark grass in the foreground. Style: premium architectural sports photography with atmospheric, restrained contrast; detailed credible stadium structure, broad quiet areas for interface text. Composition: very wide landscape 2560x1440, stadium structure and light concentrated on the right half and lower third, the left half mostly dark negative space, far pitch and stands form a strong horizontal horizon. Lighting: deep charcoal and blue-black night with natural muted green pitch, soft bright white stadium lights, no excessive neon. Constraints: original fictional architecture, no recognizable real stadium, no people in foreground, no club logos, no sponsor signage, no text, no watermarks, no UI, no crest, no balls or floating objects. This is a background asset, not a mockup.

İstemde istenen boyut ile gerçek çıktı boyutu farklıdır; teslim edilen boyut yukarıda yazılıdır. Yapay zekâ üretimi bir dosya için marka/kişilik hakkı veya münhasırlık garantisi verilmez.

## Özgün vektör ve hareketler

`assets/ui/stadium-silhouette.svg`, TM kalkanı ve `ui-shell.js` içindeki arayüz simgeleri bu proje için kodla çizilen özgün vektörlerdir. Saha/pas ağı SVG’si, hareketli top yolu ve CSS ışık/canlı durum hareketleri de bu sürümde yazıldı. Bir kulübün arması veya hazır ticari simge paketi kullanılmadı.

## Yazı tipleri

| Dosya | Kaynak | Dağıtılan lisans |
| --- | --- | --- |
| `assets/ui/fonts/manrope-variable.ttf` | [Google Fonts resmî deposu — Manrope](https://github.com/google/fonts/tree/main/ofl/manrope) | `assets/ui/fonts/Manrope-OFL.txt` |
| `assets/ui/fonts/barlow-condensed-semibold.ttf` | [Google Fonts resmî deposu — Barlow Condensed](https://github.com/google/fonts/tree/main/ofl/barlowcondensed) | `assets/ui/fonts/BarlowCondensed-OFL.txt` |

Her iki dosya da kaynak depodaki SIL Open Font License 1.1 metniyle birlikte dağıtılır. Türkçe Ç/Ğ/İ/Ö/Ş/Ü ve küçük harf karşılıkları font cmap’inde doğrulandı. Fontlar yerel yüklenir; üçüncü taraf font sunucusuna istek yapılmaz.

## Yeni arayüz portreleri

`assets/face0.png`–`assets/face16.png`: 17 adet yeni 256 × 320 portre. Eski portrelerin hiçbir pikseli bu dosyaların üretiminde kullanılmadı. Oyundaki gerçek mesh, sunum pozu ve shader ile yerel EGL/llvmpipe çiziminden doğrudan üretildi; aynı anatomik temelin ten, saç, göz, sakal ve sınırlı yüz oranı varyasyonlarıdır. Gerçek futbolcuların fotoğrafı veya yüz taraması değildir. Yeni bir karakter modelleme/animasyon sürümü değildir.

Kaynak modeli ve kredisi `assets/player/CREDITS.md` içinde. Bu kaynakta anatomik temel Blender Studio Human Base Meshes v1.4.1, Body Male - Realistic, CC0 olarak kaydedilmiştir. Forma, saç, kaş, malzemeler ve entegrasyon proje varlıklarıdır. 3D model ve çizici v1.11’den değiştirilmeden kullanılır.

Tekrar üretim:

    node tools/export-ui-portraits.cjs
    python3 tools/render-ui-portraits.py

İkinci komut isteğe bağlı `tools/preview-requirements.txt` grafik ortamını gerektirir. Oyunu açmak için bu bağımlılıklar gerekmez. Doğrudan render örnekleri ve üretim paleti `previews/ui-portrait-source.json` içindedir.

## Ticari yayın sınırı

Bu liste kaynak izini kaydeder; ticari ürün kabul belgesi değildir. Oyunda önceki sürümlerden gelen Moreirense/Estrela Amadora gibi kulüp adları bulunmaktadır. Bu adların kullanım hakları ve dağıtım koşulları yayıncı tarafından kesinleştirilmelidir. Hazır gerçek kulüp armaları veya sponsor logoları eklenmedi. Yerel lig sunucusu üretim hizmeti olarak hazırlanmış değildir.

## v1.13 serbest vuruş örneği

`previews/SERBEST_VURUS_v113.mp4` ve aynı adlı PNG kareleri, gerçek maç motoru ve mevcut 3D çizicinin draw verilerinden yerel EGL ile çizildi. Yapay maç olayı, fotoğraf veya kavram görseli kullanılmadı. Tohum 42, dengeli plan, yakın kamera; maçın 103,45–123,45 saniyeleri, 1024 × 576, 24 FPS. Skor/saati ve yöntemi açıklayan küçük video katmanı çizim aracında eklenir.

Kaynak özeti ve dosya doğrulaması `previews/free-kick-replay-v113.json` içindedir. Bu örnek kesintisiz gerçek simülasyon verisini gösterir; tarayıcı kaydı veya cihaz performans ölçümü değildir. v1.12 görsel varlıkları bu sürümde değiştirilmedi.

## v1.14 savunma geçişi örneği

`previews/SAVUNMA_GECISI_v114.mp4` ve aynı adlı PNG kareleri, mevcut oyun mesh/shader/çizicisi ve güncel kaleci rig hareketiyle yerel EGL'de üretildi. Yeni fotoğraf, dış video veya yapay maç olayı kullanılmadı. Tohum 42, kanat planı, 15 dakikalık maç, yakın kamera; 834,08–854,08 saniyeleri. Doğal top kaybı ve ardından açık oyun içeren bölüm seçildi.

Motor, rig, taktik, sahne, oyuncu çizici ve model verisi özetleri `previews/recovery-replay-v114.json` içindedir. Native çizim tarayıcı kaydı değildir. Tema, fontlar, portreler ve model dosyaları v1.13 ile aynıdır; kalecinin prosedürel uzanma hareketi bu sürümde değişir.

## v1.15 verkaç örneği

`previews/VERKAC_v115.mp4` ve aynı adlı PNG kareleri, mevcut oyun mesh/shader/çizicisi ve v1.14 rig'iyle yerel EGL'de üretildi. Tohum 42, dengeli plan, 15 dakikalık maç, yakın kamera; 68,17–88,17 saniyeleri. Seçim, doğal maç akışında fiziksel olarak tamamlanan bir verkaç üzerinden yapılır; yapay olay, dış video veya fotoğraf eklenmedi.

Kaynak özetleri `previews/combination-replay-v115.json` içindedir. Bu bir tarayıcı kaydı değildir. Tema, model, rig, fontlar ve portre dosyaları v1.14 ile aynıdır.

## v1.16 top kontrolü örneği

`previews/TOP_KONTROLU_v116.mp4` ve aynı adlı PNG kareleri, oyunun gerçek motor/rig/sahne/oyuncu çizicisi/model draw verilerinden yerel EGL ile üretilir. Yeni fotoğraf, dış video, kavram görseli veya yapay maç olayı kullanılmaz. Doğal maçta gerçekleşen bir rakibi geçme ve ardından açık oyun içeren bölüm seçilir. Kesit saati, tohum, plan ve dosya özetleri `previews/control-replay-v116.json` içindedir.

Bu sürümde rig’in çalım gövde işareti, gerçek seçilen aldatma yönüne bağlanır. Model, malzemeler, stadyum, fontlar ve portreler v1.15 ile aynıdır. Video tarayıcı kaydı veya cihaz performans testi değildir.

## v1.17 takım oyunu karşılaştırması

`previews/TAKIM_OYUNU_ONCE_v116.mp4` ve `previews/TAKIM_OYUNU_v117.mp4`, iki sürümün kendi gerçek motor/rig/sahne/oyuncu çizici/model draw verilerinden yerel EGL ile üretilir. Her biri aynı başlangıç kadrosu/tohum, dengeli plan ve TV kamerasıyla 25–85. saniyeleri gösterir. Kaynak ve çıktı özetleri `previews/teamplay-replay-v117.json` içindedir. Kontrol girdileri aynıdır; kararlar farklılaştığında maç yolları da farklılaşır.

Yeni fotoğraf, dış video, yapay maç olayı veya yeni karakter modeli eklenmedi. Rig’in yana/geriye ayak hedefleri gerçek hareket yönüne bağlanır; hareketler prosedüreldir. Stadyum, model, malzemeler, portreler, fontlar ve tasarım dosyaları v1.16 ile aynıdır. Bunlar yerel 3D çizimleri; gerçek tarayıcı, ses veya cihaz performans kaydı değildir.

## v1.18 transfer arayüzü

`assets/ui/player-silhouette.svg` bu sürüm için kodla üretilen özgün, genel futbolcu silüetidir. Transfer ekranı önceki lisans kayıtlı örnek portreleri ve mevcut stadyum/font varlıklarını yeniden kullanır. Kullanıcının paylaştığı OSM ekran görüntüleri ürün paketine veya görsel varlık olarak alınmadı. Gerçek futbolcu fotoğrafı veya yeni dış kaynaklı varlık indirilmedi.
