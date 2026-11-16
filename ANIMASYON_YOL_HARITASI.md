# Ticari 3D animasyon üretim yolu

## Güncel durum — v1.33.0

İkinci kalite adımı, lisanslı insan gövdesinin oranlarını ve deformasyon temelini üretim maçına bağlar. MakeHuman CC0 modeli, maç/stüdyo/atölyede aynı 1,88 m kanonik rig'i, sabit uzuv uzunluklarını ve oyun amaçlı eklem sınırlarını kullanır. Üretici ve çizici aynı 19 kemik çerçevesini paylaşır; normalize rijit dual quaternion skinning dönüş kaynaklı LBS çökmesini azaltır. Kapsam ve kalan yüzey sorunları [karakter modeli sözleşmesinde](docs/CHARACTER_MODEL.md), kaynak ve çevrimdışı üretim [oyuncu varlıkları sözleşmesindedir](docs/PLAYER_ASSETS.md).

GitHub `main` karakter çalışmaları dahil edilmiştir. Maçın hareket geçiş köprüsü, FPS profilleri, hızlı shader yolu ve çalışma anı LOD'ları korunur. [Prosedürel stüdyo](player-studio-procedural.html) ile [15 klipli bağımsız GLB görüntüleyici](character-viewer.html) ayrı deney yolu olarak kullanılabilir. Maç mevcut kanonik pozları kullanır; bu laboratuvar kliplerini doğrudan oynatmaz. Lisanslı GLB tek tam çözünürlüklü kaynak içerir; maç için ek LOD'lar çalışma anında üretilir.

Güncel test ve görüntü kanıtları [DOGRULAMA.md](DOGRULAMA.md) içindedir. Sabit kemikler ve DQS, bütün doku hacminin veya kusursuz temasın tek başına kanıtı değildir. Bu aşama sanatçı üretimi corrective shape key, mocap ya da ayrıntılı parmak/yüz animasyonu getirmez. Aşağıdaki eski Blender, eksik varlık ve üç LOD notları kendi sürümlerinin tarihsel kaydıdır.

Sıradaki görsel adımlar:

1. Omuz, kalça, diz ve dirsekte gerçek mesh yüzeyini ve uç poz siluetini ölç; ağırlıkları ve gerekiyorsa sanatçı kontrollü düzeltici şekilleri bu kanıta göre geliştir. Yakın kamera için giysi, yüz, saç, cilt ve ışığı birlikte değerlendir.
2. Kaynağı ve lisansı doğrulanmış koşu, fren, dönüş, pas, şut ve kaleci kliplerini mevcut temas/ayak IK sözleşmesine uyarla. Hareket geçişlerini hız ve yönle sür.
3. Mevcut basış ve ayak-top temasını kliplerle birlikte doğrula; top çıkışı ile görünen vuruş aynı zaman ve noktada olmalı.
4. Mevcut çalışma anı LOD'ları ve çizim bütçesini gerçek masaüstü ve düşük güçlü cihazlarda 22 oyunculu maçla ölç; kayıp siluet ve eklem ayrıntısını hız kazanımıyla birlikte değerlendir.
5. Kamera, ışık, malzeme ve hareketleri kesintisiz maç görüntüsünde değerlendir; tek bir stüdyo karesini maçın görsel kalitesi kabulü sayma.

## Uzun vadeli standart ve tarihsel notlar

## Üretime geçiş için varlık ve animasyon standardı

- Oyun içindeki futbolcular için tek bir orijinal/uygun lisanslı 60–80 kemikli humanoid iskelet sistemi tasarlanmalı.
- Blender veya benzeri DCC ortamından GLB/glTF 2.0 olarak, `skinned mesh + inverse bind matrices + animation tracks` ihraç edilmeli; uygulamadaki WebGL çizicisine glTF skinning katmanı (ya da Unity/Godot) entegre edilmeli.
- Asgari klip seti: 8 yönlü yürüyüş, koşu, sprint, hızlanma, yavaşlama, fren, pivot, küçük dönüş, pasın içi, pasın dışı, sert şut, plase, ilk temas, top sürme, yumuşak dokunuş, kayarak müdahale, ayakta top kapma, sıçrama, kafa, kaleci pozisyon alma, uzanma, atlama, kurtarış, itiraz, kart tepkisi, gol kutlama.
- Animasyonlar ayak teması zamanlarını işaretlemeli; oyun motoru pas veya şutu animasyonun temas karesinde gerçekleşen tek otoriter olay olarak ele almalı.
- PBR materyal, forma/şort/çorap/krampon varyasyonları, yüksek/orta/düşük LOD ve instancing stratejisi gerekli.
- Sunucu deterministik maç hareket verisi üretmeli; istemci 3D pozları sonucu etkilemeden o kaydı yeniden oynatmalı.
- Animasyon maliyetleri, 22 oyuncu ve kaleci dahil 60 FPS PC / 30 FPS düşük cihaz hedefleriyle profillenmeli.

## Sonraki teknik aşama

1. Bir adet özgün riglenmiş insan modelinin GLB yükleme ve skinning prototipini oluştur.
2. Altı kritik hareketi (idle, run, pass, shot, tackle, GK save) iskelet üzerinde blend tree olarak doğrula.
3. Koşu–durma geçişinde ayak kilidini test et; kaleci animasyonlarını bağımsız durum makinesine taşı.
4. Maç olaylarının sunucuda tek kaynak olması için 300 saniyelik deterministik replay formatı tanımla.
5. Yüksek kalite UI, profil, gerçek cihaz testleri, yük/oturum/güvenlik kontrolleri tamamlanmadan ticari sürüm ilan etme.

**Lisans:** Transfermarkt fotoğrafları ve üçüncü taraf rig/animasyonlar lisans ve izin doğrulaması olmadan dağıtıma dahil edilmemeli. v1.6'ya kadar önceki projedeki portreler ve kodla oluşturulmuş karakterler kullanıldı. v1.7 anatomisi Blender Studio CC0 temelinden gelir; kaynak `assets/player/CREDITS.md` dosyasındadır.

## v1.3 ilerleme notu

Yerel simülasyon 60 Hz sabit adıma taşındı; farklı oynatma hızları ve kare hızlarında sonuç eşitliği test edildi. Pas/şut animasyon saati ile top bırakma anı bağlandı. Bunlar sunucu otoriteli replay veya GLB/skinning aşamasının tamamlandığı anlamına gelmez. Sonraki öncelik gerçek tarayıcıda ayak-top temasının görsel denetimi ve sunucu ile ortak maç kaydıdır.

## v1.4 ilerleme notu

Hızla değişen adım uzunluğu, fren/dönüş adımları, simülasyondan beslenen hazır pozlar, ortak ayak-top temas noktası ve yönlü kaleci dalışı eklendi. Hareket Atölyesi altı senaryoyu yakın kamerada incelemeye açar. Sayısal ve yazılımla çizilen poz kontrolleri tamamlandı; gerçek tarayıcı görsel ve performans doğrulaması hâlâ yapılmalıdır. GLB/skinning ve sunucu replay aşamaları henüz tamamlanmadı.

## v1.5 öncelik değişikliği

Oyuncu geri bildirimi üzerine öncelik futbol akışına verildi: bağımsız top, ilk kontrol/dokunuş, destek koşuları, pres/kademe, ribaund ve yerinde yeniden başlama. Model ayrıntısından önce top kaybı/pozisyon üretimi/karar çeşitliliği ve kullanıcı gözlemiyle futbol zevki değerlendirilecek. Profesyonel model/GLB aşaması hâlâ bekliyor.

## v1.6 ilerleme

Santra ve mücadele durumu düzeltmeleri; açık şut, ara pas, orta/geriye çıkarma, kafa teması, yeteneğe göre çalım; yetişkin oranlı daha ayrıntılı prosedürel model eklendi. GLB/skinning/mocap aşaması henüz tamamlanmadı.


## v1.7 görünüm aşaması

Anatomik model, 19 deform kemiği, normalize ağırlıklar, üç LOD, standart GLB ve GPU skinning katmanı eklendi. Maçın mevcut prosedürel pozlarına çizim katmanında bağlanır. Düzenlenebilir Blender dosyası ve oyuncu stüdyosu pakettedir. Animasyon klipleri / mocap ve sunucu replay bu görünüm çalışmasının kapsamında değildir.


## v1.8 maç davranışları

Görsel karakter korunarak takım planlama, pas seçenekleri, geçişler, pres/kademe ve taktik merkezi geliştirildi. Yeni animasyon klibi veya mocap eklenmedi. Gerçek maçla görsel benzerlik ve cihaz performansı için tarayıcıda gözlemsel kontrol gereklidir.


## v1.9 futbol akışı

Hareketli vuruşta kısa destek ayağı basışı, hazırlık ve devam adımları; kalecide tutuş için el pozları ve hedefe göre yanal uzanma eklendi. Aynı model ve shader ile bir hareketli pasın gerçek motor pozları yerel EGL'de çizildi. Bu kontrol tarayıcı görüntüsü veya maçın tamamının görsel doğrulaması değildir. Klip/mocap, gerçek cihaz ölçümü ve uzun maç dengesi tamamlanmadı.

## v1.10 maç kararları

Görünüm, rig ve çizim varlıkları v1.9 ile aynı tutuldu. Çalışma savunma bloğu, koşu/kademe paylaşımı, taktiğe bağlı tempo, zor ilk kontrol ve kaleci yerleşimine odaklandı. Hareketli pasın yerel 3D temas örneği güncel motorla yeniden çizildi; bu, tam maç veya tarayıcı/telefon performansı doğrulaması değildir. Yeni mocap/animasyon klibi eklenmedi.

## v1.11 görev devamlılığı

Görünüm ve rig korunarak pasın alıcıya etkisi, dripling güzergâhı, pas sonrası role uygun görev, markaj devri ve ilk görüşü kapalı kaleci okuması geliştirildi. Güncel konumlardan takım akışı diyagramı ile hareketli pasın yerel 3D temas örneği üretildi. Kesintisiz tarayıcı maçı/telefon performansı doğrulanmadı; yeni mocap veya animasyon klibi eklenmedi.
