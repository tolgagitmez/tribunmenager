# Kanat hücumu animasyon pilotu

Kontrollü prova, kanat oyuncusunun hızlanıp frenlemesini, pası açık gövdeyle almasını ve geriye çıkarmasını izler. Üçüncü oyuncu ceza sahasına koşar ve şutu çeker. Kaleci gelen topa maç motorunun zamanlamasıyla tepki verir.

## Maçta açma

Başlatıcıyı açıp yerel maça gir. Adrese `pilot=1&pilotPlayer=0` sorgu parametrelerini ekle. Örneğin `http://127.0.0.1:8000/match.html?pilot=1&pilotPlayer=0`. Canlı izleme adresindeki mevcut parametreleri koruyup sonuna `&pilot=1&pilotPlayer=0` ekle. Pilot bir futbolcuyu kapsar. `pilotPlayer`, maç motorundaki `0–21` oyuncu sırasını kullanır. [Oyunu kurma ve başlatma](../KURULUM.md)

Tarayıcı konsolunda `TRIBUN_MATCH_TEST.pilotStats()` seçilen oyuncuyu ve yükleme durumunu gösterir. Blender dosyası veya WebGL kullanılamazsa görünüm yedeğe geçer ve durum `fallback` olur. `lastBootContact` son vuruşun fiziksel çıkış konumu ile ilk çizilen tam detaylı referans krampon yüzeyi arasındaki mesafeyi metre cinsinden verir. `baselineGapMetres` düzeltme öncesini, `gapMetres` uygulanan pozu ölçer. Pozitif değer boşluğu, negatif değer örtüşmeyi gösterir. `firstRenderedSampleMs` fiziksel temas ile o örneğin çizimi arasındaki maç zamanı farkıdır. Poz düzeltmesi çizim temastan itibaren iki fizik adımı içinde gerçekleştiğinde ve eklem sınırları elverdiğinde uygulanır.

## Tekrar üretme

Proje kökünde Node.js 24 ile çalıştır.

```sh
npm ci
npm run test:wing-attack
node tools/wing-attack-scenario.cjs
npx playwright install chromium
npm run test:wing-attack-browser
```

İlk test, sağ ve sol ayak ile yakın ve uzak savunmacı düzeninin dört birleşimini aynı motorla çalıştırır. Senaryo başlangıç yerleşimini ve pas niyetini belirler. Alım, pas çıkışı, şut ve kaleci tepkisi maç motorunda gerçekleşir. JSON raporda frenleme, ilk kontrol, pas çıkışı, koşu, şut ve kaleci tepkisi takip edilebilir. Kanat yaklaşık 7,2 m/sn hıza çıktı, pası 3,33. saniyede açık gövdeyle aldı ve 3,80–4,10. saniyede geriye çıkardı. Kaleci şuttan yaklaşık 183 ms sonra atıldı. Dört şutun ikisi gol oldu ve ikisini kaleci çeldi. Doğal maçlarda hücum görülme sıklığını ölçmek daha geniş bir örneklem gerektirir.

Chromium kontrolü `match.html` sayfasının WebGL çizimini ve iki bağımsız canlı izleme oturumunu kullanır. Canlı oturumlara aynı fizik adımlarından alınan maç görüntüleri düzensiz aralıklarla gönderilir. Oturumlar top durumunu, skoru ve olayları sunucu çıktısıyla karşılaştırır. Bu tekrar, kontrollü bir maç akışının sunum yolunu kapsar. Planlı fikstür ve menajer vuruşları için ayrı canlı lig kontrolleri vardır. Ekran görüntüleri `work/wing-attack-browser/` klasörüne ve GitHub Actions çıktısına yazılır.

Canlı görüntü arada bir çizim karesi kaçırdığında oyuncu ve top aynı temas anında bir kez çizilir. Sonraki kareler canlı saate yaklaşır. Pilot yerel maçta da aynı çizim aralığına birden fazla fizik adımı denk geldiğinde vuruş çıkışını gösterir. Bu sunum işlemleri fizik adımlarındaki topu, skoru ve hakem kararlarını değiştirmez.
