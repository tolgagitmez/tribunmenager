# Aşama 3 — glTF 2.0 / GLB karakter aktarımı

## Hazır çıktı

Bu aşamada mevcut prosedürel futbolcu modelinin **GLB biçiminde, gerçek skin ve kemik hiyerarşisi içeren** bir örneği projeye eklendi:

- Kaynak: `assets/player/player-model-data.js`
- Kaydedilmiş yüksek detaylı çıktı: `assets/player/tribun-base-footballer.glb`
- Üretici: `tools/export-character-glb.cjs`
- Resmî doğrulayıcı çalıştırıcısı: `tools/validate-character-glb.cjs`
- Testler: `tests/character-glb-export.test.cjs`
- İndirilebilir LOD0, LOD1, LOD2 paketleri: GitHub Actions » Character rig and glTF validation » Artifacts.

Model 19 adet bind kemiği, 10 basit PBR materyal, normal/UV verisi, en fazla dört kemik ağırlığı ve inverse bind matrisleri içerir. Dört bayt hizalı GLB JSON + BIN bloklarıyla tek dosya olarak üretilir. Kaydedilmiş GLB kaynak geometrinin tekrar oluşturulmasıyla birebir eşleşmek zorundadır.

## Blender'a aktarma

Blender'da **File > Import > glTF 2.0 (.glb/.gltf)** menüsünden `assets/player/tribun-base-footballer.glb` dosyasını seç. `Footballer mesh` nesnesi ve `pelvis` köklü iskelet hiyerarşisi görünmelidir. Dosya boyutları metre ve Y-up koordinatlarını kullanır; Blender içe aktarırken eksen dönüşümünü kendi yapabilir.

Bu dosyada **animasyon klibi yoktur**. Mevcut canlı koşu/pas/şut animasyonları WebGL oyun motorunun prosedürel poz sisteminde bulunur ve GLB içine kaydedilmez. Blender'daki materyallerin görünümü de oyunun özel shader'ının tüm görsel ayrıntılarını içermez. Profesyonel heykel, lisanslı mocap veya glTF üzerinden oyuna otomatik yükleme bu aşamanın kapsamına girmiyor.

## Yeniden oluşturma

Node.js 22 veya üzeri:

```bash
npm run test:character-rig
npm run build:character-glb
node tools/export-character-glb.cjs --lod 1 --output dist/tribun-base-footballer-lod1.glb
node tools/export-character-glb.cjs --lod 2 --output dist/tribun-base-footballer-lod2.glb
```

Resmî Khronos glTF Validator komutu (gerekli npm paketi ayrı kurulur):

```bash
npm install --no-save --no-package-lock gltf-validator@2.0.0-dev.3.10
node tools/validate-character-glb.cjs assets/player/tribun-base-footballer.glb
```

GitHub Actions'taki ilk resmî doğrulama (15 Kasım 2026): **0 format hatası, 0 uyarı**, dört GLB örneği. Bu sonuç yalnızca glTF formatı için geçerlidir. Gerçek tarayıcıda 3D render, Blender'da elle deformasyon incelemesi, mobil GPU yük testi ve futbol hareketlerinin görsel kalitesi ayrıca kontrol edilmelidir.

## Kod teknik notları

Yüzey oluşturucudaki üçgen sarımı ile normallerin ters düştüğü kısımlar dışa çevrildi. GLB dışa aktarıcı, her malzemeyi ayrı üçgen primitive'ine ayırır. Eklem isimleri, sıra ve bağ pozları WebGL'deki 19 kemikle eşleştirilir. Çıktıdaki PBR renkler uygulamanın forma/ten şablonunun basitleştirilmiş karşılıklarıdır.

İlk sonraki iş: glTF animasyon track'leri için hareketlerin dışa aktarımı, tarayıcıdan alınmış 360° karakter karşılaştırması ve gerçek insan topolojisiyle omuz-kalça ağırlıklarının geliştirilmesi.
