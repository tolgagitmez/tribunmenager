# Tribün Manager — Gece maçı tasarım sistemi

## Kimlik

Koyu mürekkep/yeşil zemin üzerinde kemik beyazı metin ve limon yeşili vurgu. Odak, kadro kararları ve maçtır. Kurgu stadyum görseli geniş başlıklara atmosfer verir; özgün vektör silüeti sayfanın altına sessiz bir saha katmanı ekler. Takım mavisi/kırmızısı, skor ve momentum gibi iki tarafın karşılaştırıldığı alanlarda kullanılır.

| İşlev | Değer |
| --- | --- |
| Zemin | `#081410` |
| Ana yüzey | `#10221b` |
| İkincil yüzey | `#172c23` |
| Ana metin | `#f2f4e9` |
| İkincil metin | `#a7b9ad` |
| Vurgu / birincil eylem | `#d8ff65` |
| Uyarı | `#f4c77d` |
| Hata | `#ff9b99` |

**Barlow Condensed 600:** büyük başlıklar, sayılar, skorlar. **Manrope 200–800:** gezinme, açıklama ve kontroller. İkisi de yerel TTF dosyalarıdır; Türkçe karakterleri denetlendi. Simge dili aynı çizgi kalınlığını paylaşan özgün SVG’lerden oluşur. Marka işareti özgün TM kalkanıdır.

## Yerleşim

Üstte ortak gezinme, ardından ekranın amacını açıklayan stadyum başlığı; maçta başlığın yerini skor bandı alır. Çalışma alanları görevlerine göre bölünür. Birincil eylemler vurguludur; ek ayarlar açılır ayrıntılarda kalır.

Kadro, antrenman ve analiz tek uzun sayfa yerine ayrı gezinme durumlarıdır. Geniş ekranda kadro tahtası ve yedekler yan yanadır. Telefonda saha dikey, yedekler alttadır; beşli savunma kartları daraltılır. Taktik alanı üç sütundan tek sütuna, maç yan paneli sahanın altına geçer. Lig tablosu küçük ekranda kendi alanında yatay kayar.

## Hareket ve durumlar

- Pas ağı üzerinde dolaşan top: sekiz saniyelik hafif SVG hareketi.
- Stadyum ışığı: yavaş, düşük kontrastlı atmosfer hareketi.
- Taktik pas yolları: kesikli çizgi akışı.
- Canlı durum göstergesi ve bölüm geçişi: kısa ve ölçülü vurgu.
- Mevcut maç gol geri bildirimi ortak palete uyarlanır; maç animasyon motoru değiştirilmez.

Hareket azaltma seçeneği bu arayüz hareketlerini kapatır. Sistem tercihi, kullanıcının açık seçimi yoksa uygulanır. Sekme gizlenince atmosfer ve SVG hareketleri durur. Bu ayar canlı futbol simülasyonunu duraklatmaz.

Bekleme, başarı ve hata durumları metinle açıklanır. Lig isteği sürerken tekrar gönderim engellenir. Pano kopyası başarısızsa başarı mesajı verilmez; kod seçilebilir. Kadro seçimi görünür bir ipucuyla ve ayrı iptal düğmesiyle sunulur.

## Erişim

Atlama bağlantısı, görünür klavye odağı, etiketli alanlar, seçili durumların ARIA karşılığı, modal içinde Tab/Shift+Tab döngüsü, Escape ile kapatma ve önceki odağa dönüş bulunur. Mobil menü klavyeyle kullanılabilir. Maç olay listesi sürekli sesli okuma yapmaz; kısa anlatım alanı ayrı bir canlı durumdur. Bu özelliklerin varlığı bir erişilebilirlik sertifikası iddiası değildir.

## Teslim ve kabul

İşlev ve kaynak kontrolleri `DOGRULAMA.md` içindedir. Yerel statik önizlemeler, gerçek tarayıcı ve WebGL testi yerine geçmez. Ticari yayın kabulünde tarayıcı/telefon kullanımı, tam maç izleme ve kulüp/marka adlarının kullanım hakları tamamlanmalıdır.
