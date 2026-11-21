# Aşama 17 — Tüm lig fikstürleri için tek saha motoru

## Artık iki farklı maç hesaplama yolu yok

Önceden yalnızca izleyicisi bulunan karşılaşma `live_match.py` ve
`live-match-worker.cjs` üzerinden gerçek `football-sim.js` ile
oynatılıyordu. İzleyicisi olmayan karşılaşmaya ise `server.py` içindeki
Python tabanlı Poisson/kalite hesabı skor yazıyordu. Bu ikinci yöntem
kaldırıldı; her lig günü üç fikstürün **üçü de** ortak `Match` motoruna
gönderiliyor.

### Yaşam döngüsü

1. **Başlama anı:** Sunucu zamanlayıcısı 0,5 saniyede bir fikstürleri kontrol
   eder. Başlama saati gelen ve henüz başlatılmayan her karşılaşmanın
   `live_matches.config` kaydı tek SQLite işlemi içinde oluşturulur. Takım
   dizilişleri, taktikler, resmî bağlantılı kadro ve ilk 11, maç tohumu ve
   motor/köprü kaynak SHA-256 değerleri bu kayıtla sabitlenir.
2. **Tek yetkili motor:** Her kayıt için bir `LiveMatch` oturumu açılır.
   `live-match-worker.cjs` her fizik adımında `football-sim.js` kullanır.
   Hiçbir menajerin sayfayı açması şart değildir.
3. **Katılım:** Web istemcisinin aynı oturumu okuması yalnızca o takımın
   menajer vuruşları üzerinde seçim hakkı kazandırır. Komut girilmezse
   `input:null` ile aynı otomatik karar uygulanır. Seyirci sayısı, maç
   tohumu veya başlangıç kadroları için girdi değildir.
4. **Dayanıklılık:** `live_match_operations` tüm motor ilerletme ve vuruş
   komutlarını saklar. Her yaklaşık iki saniyede ve önemli vuruşlarda
   `live_match_frames` içerisine gerçek top/oyuncu konumu yazılır.
   Tamamlanan maçta sonuç ve `final_state` aynı işlemin içinde kaydedilir;
   komut geçmişi **silinmez**.
5. **Kesinti / yeniden açılma:** Kayıtlı `config` ve `operation` dizisi
   tekrar oynatılır; eksik fizik adımları maçın başlama zamanına göre gerçek
   `Match` üzerinden tamamlanır. İstemci sonucu hesaplayamaz.

### Kilit ilkeleri

- Planlanan/henüz başlamayan maçın önizlemesi güncel kadroyu gösterebilir;
  başlama saatinden sonraki önizleme `live_matches.config` içindeki
  sabitlenmiş kadroyu kullanır. Artık yeniden açılan bir ekran, ara transfer
  veya taktik değişikliği canlı maçın XI'ini yenileyemez.
- Geçersiz veya henüz bağlantısı bulunmayan resmî oyuncu kadrolarında
  başlangıç konfigürasyonuna bu durum kaydedilir ve aynı saha motorunun
  deterministik demo/fallback takımı çalışır. İlk gerçek motor kareleri
  oyuncuları içerir.
- Node.js yoksa veya saha motoru hata verirse **hayalî bir skor
  hesaplanmaz**. Sonuç beklemede kalır ve sorun sunucu günlüğüne yazılır.
- Daha önce eski hesapla tamamlanmış fikstürler değiştirilmez; geçiş yeni
  başlamamış maçlar için geçerlidir.

### Kontroller

```bash
python3 -m unittest discover -s tests -p 'test_unified_fixtures.py' -v
python3 -m unittest discover -s tests -p 'test_live_match.py' -v
node --test tests/fixture-watch-parity.test.cjs
```

- Bir lig günündeki üç fikstür izleyicisiz oluşturulur ve yalnızca gerçek
  motor sonucuyla tamamlanır.
- Kadro, ilk 11, diziliş ve taktikler maç başladıktan sonraki değişikliklere
  rağmen aynı kalır.
- 0, 1, 2 izleyici veya iki sekmenin maç sırasında kapanması, manuel vuruş
  komutu verilmediğinde **tüm son maç durumunu** (skor, kartlar, top,
  oyuncular ve olaylar) değiştirmez.
- Dondurulmuş maç konfigürasyonu ve maç boyunca saklanan komutlardan
  birebir aynı bitiş durumu üretilebilir; son kare gerçek 23 saha varlığını
  (22 futbolcu ve hakem) içerir.

### Bilinen sınırlar

**Kesinti sırasında kesin başlama anı:** Sunucu çalışıyorsa fikstürler
başlama zamanına en fazla zamanlayıcı kontrol aralığı kadar yakın
dondurulur. Sunucu başlama anında kapalıysa ilk yeniden çalışmada mevcut
veritabanı durumundan dondurma yapılır; dışarıdan sunucu kapalıyken
değiştirilen kadronun tarihsel hâlini geriye dönük olarak yaratamayız.
`capturedAt` gerçek kayıt zamanını, `snapshotAt` planlı başlama
zamanını gösterir. Tam olarak zamanında, kesinti dayanıklı kadro kilidi
için kadro/taktik değişikliklerinin ileride ayrıca sürüm zaman çizelgesiyle
saklanması gerekir.

**Sürüm değişimi:** `engineSHA256` ve `workerSHA256` geçmişi işaretler;
gelecekte eski maçları yeni motor sürümünde yeniden oynatmadan önce
uygun kaynak sürümü seçilmelidir. Şimdilik otomatik eski motor yükleme ve
pozisyon tekrarları arayüzü yoktur. Canlı oyuncu değişikliği API'si de bu
PR kapsamına alınmamıştır; işlem geçmişi buna altyapı sağlar.

**Performans:** Tüm karşılaşmalar normal 60 Hz motorun işlemlerini yapar;
yük altındaki sunucu gerçek saatin gerisine düşebilir. Maç skorunu
tahmini hesaplayarak bu gecikmeyi gizleme yoktur. Yoğun kullanımda
sıraya alma ve kalıcı worker ölçekleme ayrıca yapılmalıdır.
