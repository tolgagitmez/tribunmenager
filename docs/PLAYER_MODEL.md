# Oyuncu modeli ve maç girdileri — v1.30.0

Kadro ekranı, yerel maçın iki takımı ve oyuncu değişikliği aynı `player-model.js` sözleşmesini kullanır. Ham futbolcu kaydı ve etkin maç oyuncusu farklı nesnelerdir; maç yorgunluğu, mevki cezası veya etkin puan ham kadroya geri yazılmaz.

## Ham kayıt ve kaynağı

`id`, `name`, `number`, `pos`, `rating`, `fitness`, `form` eski kayıtlarla uyumludur. `subposition`, `positions`, `archetype`, `preferredFoot`, `weakFoot` ve ayrı fizik/teknik özellikler eklenebilir. `pos` dört genel gruptan biridir: GK, DEF, MID, ATT. Altı desteklenen dizilişin slotları özel mevkileri de taşır; mevcut kalite cezası genel mevki grubu üzerinden hesaplanır. İkincil mevki dizisi saklanır, henüz özel mevki cezasını değiştirmez.

Tercih edilen ayak `left`, `right`, `both` veya `unknown` olur. Bilinen sol/sağ ayak gerçek kayıttan korunur. `both`, iki ayakta aynı teknik uygulamayı kullanır. Zayıf ayak bilgisi güçlü ayak becerisini yükseltemez. Eksik ayak bilgisi ekranda **Ayak bilgisi yok** olarak görünür; motorun gerekli sayısal ayak seçimi sağ ayak varsayımıdır ve `model.preferredFootSource: unknown` olarak izlenir. Bu varsayım gerçek futbolcuya ait ayak gözlemi değildir.

Katalog doğrulaması açıkça verilen özellikleri 1–99 aralığında korur; form/kondisyon 0–100 aralığındadır. Eksik teknik/fiziksel özellikler genel puana veya katalog kimliğine eşitlenerek saklanmaz. Maç normalleştirmesi `player-model-profiles.json` içindeki sabit rol varsayımını kullanır ve `model.inferredAttributes` alanında belirtir. Profil seçimi açık `archetype`, yoksa mevki/özel mevki üzerinden yapılır. Oyuncu kimlik numarası, dizideki sırası ve RNG sayısal teknik/fiziksel özellik üretmez.

Sekiz varsayılan profil: kaleci, güçlü stoper, hücumcu bek, oyun kurucu, top kazanan, süratli kanat, hızlı bitirici ve hedef santrfor. Başlangıç kadrosu bu profilleri açıkça atanmış **kurmaca deneme futbolcularıdır**. Profiller kalibre edilmiş gerçek oyuncu ölçümü değildir. Önceden saklanmış sayısal özellikler korunur; yeni kimlik alanları başka bir başlangıç oyuncusunun aynı indeksinden kopyalanmaz.

## Ekrandaki maç gücü

`P` mevki uyumu, `F` form katsayısı, `C` kondisyon katsayısı olsun:

```text
F = 0,91 + 0,09 × form / 100
C = 0,83 + 0,17 × fitness / 100
maç gücü = round(rating × P × F × C)
```

| Yerleşim | P |
| --- | ---: |
| Kendi genel mevki grubunda | 1,00 |
| GK ile saha oyuncusu arasında | 0,45 |
| MID ↔ ATT | 0,87 |
| DEF ↔ MID | 0,82 |
| DEF ↔ ATT | 0,66 |

Kadro kartı, `Match.reset`, iki takım ve yedek girişi aynı etkin puanı alır. Python günlük lig kalite hesabı bu formülle JS sözleşmesine karşı test edilir. Maç gücü tek bir özet göstergedir; bütün alt becerilerin ortalaması veya galibiyet olasılığı değildir.

## Hangi değer hangi davranışı etkiler?

| Özellik grubu | Başlangıç hesabı | Sahadaki kullanım |
| --- | --- | --- |
| Pas, şut, müdahale, dripling, kafa, orta, görüş, soğukkanlılık ve zayıf ayak | Ham değer × P × F | İlgili mevcut karar, temas veya uygulama hesabı |
| Hız, ivme, çeviklik, denge | Ham değer × C | Koşu hızı, hızlanma, gövde dönüşü ve mücadele dengesi |
| Güç ve dayanıklılık | Ham değer | Erişilebilir müdahalede sınırlı fizik farkı; sprint tüketimi ve toparlanma |
| Kaleci reaksiyonu ve tutuşu | Ham değer × P × F | Görülen şuta tepki süresi ve yakalama hız kapasitesi |

Başlangıç `stamina`, kondisyonla başlar. Hız zaten kondisyonla düzeltilmiştir; motor ikinci kez aynı başlangıç cezasını uygulamak yerine maç içinde kalan stamina/başlangıç kondisyonu oranını kullanır. Kısa süreli enerji ve dayanıklılık maç boyunca ek yorgunluğu belirler. Güç/denge farkının temiz müdahale hesabına katkısı sınırlıdır; erişim, gövde ve top koruma geometrisi önce sınanır. Uzaktaki güçlü bir oyuncu bu nedenle top kazanamaz.

`goalkeeping` toplam alanı modelde taşınır; bu sürümde kaleci tepkisini ve yakalamayı doğrudan bağımsız `reactions`/`handling` alanları yönetir. Bir veri alanının saklanması tek başına ayrı davranışın tamamlandığı anlamına gelmez. Katsayılar oyun modeline aittir; fiziksel/biyomekanik doğrulama iddiası taşımaz.

## İki kadroyla başlatma

Kadro ve taktik sayfaları `TribunMatchConfig.prepare` ile kendi kadrosunu eşitler ve fikstür rakibini alır. Aynı profil/sürümde seçilmiş ilk 11 ve özel görevler korunur. Daha yeni kabul edilmiş kadro sürümü, geç dönen eski yanıtla değiştirilmez. Başka transfer profiline geçildiğinde eski hesabın dizi indeksleri yeni kadroya taşınmaz. Kendi yetkili kadrosu alınamazsa başlangıç başarısız olur; eski kayıt sessizce güncel diye sunulmaz.

Lig oturumu varsa `GET /api/league/local-match`, Bearer lig kimliğiyle şu görüntüyü verir:

- Fikstür: lig/tur, gerçek ev/deplasman slotları, başlangıç zamanı, durum ve kullanıcının ev sahibi olup olmadığı.
- İki kulüp: ad, diziliş, taktik ve varsa bağlı kadronun futbol alanları, ilk 11'i ve sürümü.
- Görüntü zamanı; sonuç hesaplaması veya ekonomi hesabı yoktur.

Sunucu başka kulübün cüzdanını, tekliflerini, keşif sonuçlarını veya erişim anahtarını döndürmez. Maçın kendi takımı motor takım 0 olarak kalır; deplasman bilgisi ayrıca etiketlenir. Hazırlanan iki kadro, `tribun-match-config` oturum kaydına alınır. Aynı lig/transfer oturumu bağlamında maç sayfasına giriş ve yeniden başlatma bu görüntüyü kullanır; ikinci bir eşitleme seçimi değiştirmez. Lig kimliği veya transfer profili değişirse eski görüntü yeniden hazırlanır. Yapılandırma yalnız opak bağlam kimliği taşır; erişim anahtarı URL'ye yazılmaz. Depolama yoksa açık yapılandırma hash'i yedektir.

Bağlı/kayıtlı rakip bulunursa `opponentSource: linked-roster` olur. Kayıtlı kadro yoksa ya da lig bağlantısı alınamazsa `demo` kaynağı ve görünür açıklama kullanılır. Bilgisayar kulüplerinin resmî tabloda şu an yalnız genel takım gücü bulunduğundan bütün fikstür rakiplerinin gerçek oyuncuları varmış gibi davranılmaz. Açıkça verilen çevrimdışı iki kadro da aynı oyuncu modelinden geçer.

Yerel maç, `server.py:outcome` günlük Poisson hesabını veya resmî fikstür sonucunu değiştirmez. Gerçek kadroyla yerel önizleme ile resmî sonucu aynı motordan üretme ayrı kapsamlardır.

## Kabul ve kalan işler

`npm run test:stage11`, önceki fizik/algı/hücum zinciri kontrolleriyle yeni model, veri ve başlangıç testlerini birleştirir. Eşit puanlı profiller gerçek koşu, pas çıkışı, yasal mücadele ve aynı uçuşta kaleci temasında karşılaştırılır. JSON profilinin tarayıcı kopyası ve Python/JS kalite/varsayılan değerleri ayrıca karşılaştırılır. Son pakette 361 test ve iki çizim yolunda 16'şar Chromium kontrolü geçti. Sekiz 300 saniyelik doğal karşılaştırmada gözlemcili/gözlemcisiz/tekrar maç durumları eşleşti; şut üretimi azaldığından genel denge kazanımı iddia edilmez. Gerçek Chromium ve doğal maç kayıtları [DOGRULAMA.md](../DOGRULAMA.md) içinde açıklanır.

Sonraki işler gerçek sağlayıcı kapsamı ve kaynak tarihi, kalıcı bilgisayar kadroları, özel/ikincil mevki uyumu, daha uzun yorgunluk örnekleri ve önceki hücum dengesi kalibrasyonudur. Bu sözleşme bu işlerin aynı veriye dayanmasını sağlar; hepsinin tamamlandığını göstermez.
