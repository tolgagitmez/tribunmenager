# Bireysel oyuncu zekâsı — Aşama 1 (2026-11-24)

## Başlangıç durumu

Maç motorunda daha önce dripling, çalım, top saklama ve ara pas fonksiyonları vardı. Yeni karar katmanı bu fizik sistemini yeniden yazmaz: var olan geçerli seçenekler arasında oyuncunun beceri profilini dikkate alır.

## Uygulanan davranışlar

- **Dikine dripling:** Dripling, çeviklik, hızlanma, enerji, açık koridor, mevki ve ters ayaklı kanadın içe kat etmesiyle yön seçimi. İyi ileri pasın önüne geçmez.
- **Vücut çalımı:** Dripling, çeviklik, savunmacının müdahale/soğukkanlılık kalitesi, mesafe ve enerji. Mevcut feintClock animasyonunu kullanır.
- **Sırtı dönük oyun:** ST/CF ve hedef forvetlerde güç, denge, sakinlik, gövde yönü ve gol tarafındaki savunmacı koşullarıyla mevcut fiziksel top saklamayı başlatır.
- **Ara pas:** Görüşü yüksek pasör kısa pas taktiğinde bile gerçekten hizalanmış, ofsaytsız ve erişilebilir bir koşu için ara pası değerlendirir. Şerit riski ve fiziksel hazırlık kontrolleri durur.
- **Genel pas kararı:** Vizyon ve teknik kalite güvenli ileri bağlantıları bir miktar öne çıkarır; riskli paslar korunmuş cezalara tabidir.

## Saha görünürlüğü ve sınırlar

Çalım, dikine dripling ve sırtı dönük oyun kararları maç olaylarına bağlandı. Dikine sürüş ve top saklamada oyuncu başına altı saniyelik anlatım aralığı uygulanır. Telemetride signatureDrives ve holdUpPlays yalnızca karar sayacı; başarıyla adam geçildiği anlamına gelmez. Mevcut top hareketi ve animasyon korunur; bu adım yeni motion-capture klipleri, tam fiziksel sırt dayama veya FIFA kalitesinde animasyon sunmaz.

## Test ve doğrulama

Player-brain testleri oyuncu profilleri arası karar farkını, fiziksel durum ve güvenli pas önceliğini, iki gerçek Match.choose() senaryosunu ve kısa pas taktiğinde hazırlanmış ara koşuyu doğrular. Pull request iş akışında JavaScript sözdizimi ve mevcut kadro/pas/takım niyeti testleri de çalışır. Henüz çok tohumlu uzun maç dengesi, WebGL piksel gözlemi veya performans profili doğrulanmış sayılmaz.

## Sonraki faz

1. Çalım için omuz-kalça aldatması, ayak temasları, hız yönü ve rakip reaksiyonunu aynı zaman çizelgesine bağla.
2. Sırtı dönük top kontrolünde rakiple fiziksel mücadele, duvar pası ve dönerek çıkışı ayrı doğrula.
3. Ara pas öncesinde gerçek koşu başlatma, kör taraf taraması ve savunma çizgisine zamanlamayı iyileştir.
4. Oyun kurucu, ters ayaklı kanat, hedef forvet ve hızlı bitiricinin yeteneklerini gerçek maç istatistikleriyle karşılaştır.
5. Geliştirici HUD'unda her oyuncunun son kararları ve seçilmeyen alternatifleri incelemeyi sağla.
