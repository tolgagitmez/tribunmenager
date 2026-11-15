# Karakter sistemi – Aşama 2

## Teslim edilen teknik uygulama

- assets/player/player-model-data.js: dış modellere bağımlı olmadan çalışan prosedürel bir futbolcu varlığı üretiyor.
- 19 bağlanmış kemik, üç WebGL LOD (4220 / 2954 / 2110 vertex), 20 float/vertex ve Uint16 üçgen indeksleri.
- Kafa, yüz, saç, boyun, gövde, forma, şort, çorap, kol, bacak ve krampon bölgelerinde farklı yüzey döngüleri ve en fazla dört normalize ağırlık.
- Uzunluğu korunmuş iki kemikli IK: 0.50m uyluk, 0.50m baldır, 0.33m üst kol, 0.34m ön kol. Pelvis referansı 1.00m.
- player-renderer.js: GPU kemik ölçeği yok; poz açısına bağlı omuz, dirsek ve dizde yaklaşık doku desteği ekleniyor.
- animation-scenarios.js ve player-studio.html: yürüyüş, jog, koşu, sprint, dönüş, pas, şut ve dalış incelemeleri.
- tests/base-character-asset.test.cjs ve tests/character-rig-anatomy.test.cjs: topoloji, eklem uzunluğu, poz, ağırlık ve skinning kontrolleri.
- .github/workflows/character-rig.yml: Node 22 ile her güncellemede odaklanmış testler.

## Doğrulama kapsamı

npm run test:character-rig komutu çalıştırılmalıdır. GitHub Actions yürütmelerindeki başarı/başarısızlık durumu ayrı kaydedilir.

Bu aşama, oyun için stilize/prosedürel bir futbolcu prototipidir. Profesyonel Blender heykeli, gerçek GLB, twist-bone iskeleti, sanatçı tarafından üretilmiş corrective blendshape, mocap ya da telefonda GPU performans doğrulaması değildir.

Önceki sürümlerde belgelenmiş orijinal Blender kaynak dosyaları ve GLB dosyaları depoda bulunmuyordu; bu uygulama onların geri yüklenmesi veya aslına uygun kopyası olarak sunulamaz.

## Kalan üretim gereksinimleri

1. WebGL/Chromium üzerinde yakın plan render ve görsel kıvrım testleri.
2. Anatomik görünümü artırmak için sanatçı kontrollü topoloji, yüz ve eklem bölgeleri.
3. Kademeli locomotion, ayak kilitleme, temas animasyonu, turn-in-place ve mocap.
4. GLB/glTF 2.0 teslimi, retargeting ve ticari dağıtım için lisans ve performans denetimi.
