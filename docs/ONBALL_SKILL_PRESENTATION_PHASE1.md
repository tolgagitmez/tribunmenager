# Topla hareket animasyonları — 3D bağlantı Aşama 1

## Kapsam

Bu çalışma oyuncu zekâsının önceki pull request'te ürettiği **çalım**, **korumalı top saklama** ve **dripling teması** kararlarını, mevcut 1,88 m lisanslı insan iskeletinin gerçek kemik uzunlukları ve mevcut ters kinematik (IK) sınırları üzerinden gösterir. Simülasyonun top, oyuncu ya da savunmacı pozisyonlarını animasyon değiştiremez.

### 1. Çalımın eklem hareketi

- Match.applyFeint tarafından zaten üretilen `feintClock`/`feintSign` bir 0,35 saniyelik sahte adımı tetikler.
- Çalım yapılan taraftaki ayak zeminden hafif kalkar, karşı ayak destek rolünü korur. Omuz/kol karşı ağırlığı ve küçük gövde eğimi eklenir.
- Ayağa ilave top vuruşu uygulanmaz. Mevcut müdahale kararı ve savunmacı reaksiyonu değişmez.

### 2. Sırtı dönük koruma

- Match.startCarry'de fizik motorunun kabul ettiği `shield` durumu, planlama yenilemesi beklenmeden görsel duruşa aktarılır.
- Gövdede küçük çömelme/dönüş, top tarafında bent-kol kalkanı; koruma sona erdiğinde ani zıplama yerine yumuşak gevşeme.
- Bu bir **görsel top saklama duruşudur**. Gerçek vücut temas çözümü veya fiziksel sırt dayama hâlâ ayrı aşamadır.

### 3. Gerçek temas noktası

- Dripling ayak animasyonu `touchPosition`, `footTouch` ve `dribbleFoot` verilerinden beslenir. Top pozisyonunu rig hesaplamaz; mevcut maç fiziğinin kaydını okur.
- Görsel ayak, erişilemez top noktasına zorla uzatılmaz: destek ayağı ve orijinal kemik boyları korunur, IK erişim sınırları ihlal edilmez.
- Vuruş, müdahale ve diğer uzman hareketlerdeki gerçek temas, çalım ve saklama gösteriminden önceliklidir.

### 4. Çevrim içi maç ve glTF pilotu

- Sunucu `brainRole`, `touchMode`, `shieldFace` değerlerini mevcut oyuncu durumuyla birlikte aktarır; UI yalnızca görsel çalım/touch sayaçlarını paketler arası ilerletir.
- Blender pilotunun genel koşu animasyonu, çalım ve koruma pozlarının üst vücut eklemlerini ezmez. Fiziksel ayak pozisyonları mevcut rig'ten gelir.

## Doğrulama

Çalıştır: `npm run test:onball-presentation`. İlgili testlerde kemik uzunluğu, destek ayağı, ağ gecikmesindeki hareket saatleri, duraklatma, gerçek Match.startCarry bağlantısı, bağımsız top fizikleri, sunucu snapshottaki cue alanları ve vuruşun önceliği kontrol edilir. Ek regresyonlar karakter rig anatomisi, vuruş geçişleri ve FPS profilleridir.

## Performans sınırı

Bütün 22 oyuncu için ekstra fizik çözümü, görüntü karesinde saha çapında rakip taraması veya yeni model indirme işlemi yoktur. Her aktörün mevcut poz hazırlığına birkaç skaler ağırlık ve IK hedefi eklenir. Bu, gerçek cihaz FPS ölçümünün yerini **tutmaz**; zor sahnelerde GPU maliyeti ayrıca izlenmelidir.

## Bağımlılık ve sonraki hedef

Bu branch, henüz ana projeye alınmamış **oyuncu zekâsı PR #27** üzerine yığılmıştır. Önce PR #27, sonra **animasyon PR #28** birleştirilir.

Bir sonraki hedef çalımın rakiple temasını ve sırtı dönük duvar pasının kinematik/fiziksel olaylarını birlikte doğrulamak; ardından çok oyunculu sahnede gerçek FPS ve render maliyeti ölçmektir.
