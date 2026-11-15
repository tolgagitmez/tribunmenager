> Güncelleme: [Aşama 2](CHARACTER_RIG_PHASE2.md) kapsamında eksik olan prosedürel WebGL karakter verisi artık eklendi; Blender/GLB kaynakları hâlâ yok.

# Temel futbolcu — anatomi ve kemik kısıtları (ilk uygulama)

Bu dal, mevcut 19 kemikli WebGL karakterinin **hareket/rig** katmanına odaklanır. Bir profesyonel Blender karakteri, yeni humanoid mesh, sculpt edilmiş corrective blendshape veya motion-capture klipleri **henüz üretilmedi**.

## Uygulananlar
- `humanoid-rig.js`: tek bir `solveLimb` iki kemikli IK çözücüsü; hedef uzaktaysa uç noktayı erişilebilir aralığa yansıtır. Uyluk/baldır, üstkol/önkol uzunlukları sabittir.
- Diz ve dirsek aşırı düzleşme ve katlanmadan korunur (görsel IK için diz ~0.085–2.60 rad, dirsek ~0.08–2.70 rad). Bunlar anatomik referans ölçümü değil, ilk oyun kısıtlarıdır.
- `player-renderer.js`: skin palette hesabında kemik eksenine konan 0.5–1.7 arası ölçek kaldırıldı; kemiğin yönü değişebilir fakat ölçeği sabit kalır.
- `tests/character-rig-anatomy.test.cjs`: uç pozlarda uzunluk, animasyon senaryoları ve palette rotasyon birim uzunluk kontrolleri.
- `npm run test:character-rig` ile odaklanmış test komutu.

## Uyarılar ve eksik kabul koşulları
- Depoda `assets/player/` altındaki riglenmiş mesh, Blender dosyası, GLB ve `player-model-data.js` görünmüyor; stüdyo kaynakları bu varlıklara başvuruyor. Bunlar eklenmeden kaliteli model teslim edilmiş sayılamaz.
- Sadece sabit kemik uzunlukları doku hacmini korumaz. Omuz/kalça topolojisi, weight painting, twist bones, corrective shape keys ve motion-capture eksiktir.
- Ayak temas noktasını erişim dışına düşüren istisnai hedeflerde IK ucu hedefe ulaşmak yerine güvenli konuma taşınır; bu nedenle ayak-top temas animasyonları görsel olarak ayrıca doğrulanmalıdır. Simülasyon top fiziği bu dalda değiştirilmedi.
- Çalıştırılabilir proje dosyaları bu oturumda yerel ortamda bulunmadığından tarayıcı/WebGL testi ve performans ölçümü yapılmadı. Test dosyaları GitHub'a eklendi ancak testlerin geçtiği iddia edilmiyor.

## Sonraki üretim işi
1. Özgün veya kullanımı doğrulanmış, düzenlenebilir ve uygun topolojiye sahip tek bir atletik insan gövde mesh'i depoya ekle.
2. Anatomik bind pose ve inverse bind matrisiyle ölçekten bağımsız rig skinning testleri yap; gerekirse mevcut kemiklerin yön ve konumlarını yeni mesh ile yeniden eşle.
3. Omuz, kalça, diz, dirsek ve bileklerde normalize weight paint ve corrective shape keys üret; ekstrem poz test görüntülerini kaydet.
4. Idle, walk, jog, sprint, pas, şut, dönme, mücadele kliplerini gerçek tarayıcıda incele; ayak kilidi, temas karesi ve 22 oyuncu performansını doğrula.
