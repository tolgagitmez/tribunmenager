# Tribün Manager 3D v1.27 — Hareketli alıcıyı okumak

Pasın çıkış hedefi, alıcının mevcut koşu komutu, frenlemesi ve dönüşüyle yeniden tahmin edilir. Farklı hareket varsayımlarından biri güçlü tehlike gösteriyorsa, açık görünen diğer varsayım tek başına pası sürdürmeye yetmez. FIFA/EA FC oynanış ilkeleri referans alınır; yöntem mevcut Tribün motorunun özgün kodudur.

## Oyunu aç

1. ZIP'in tamamını bir klasöre çıkar.
2. Windows'ta **BASLAT.bat** dosyasını çalıştır. Python 3.10 veya daha yeni sürüm gerekir. macOS/Linux'ta `sh BASLAT.sh` kullan.
3. Tarayıcıda **http://localhost:8000** adresini aç. Üst menüden **Transfer** bölümüne geç.
4. Sunucu konsolunu oyun sırasında açık tut. Yeniden açıldığında önceki bakiyeler, ilanlar ve görevler devam eder.

Komutla başlatmak için oyun klasöründe `python3 server.py` (Windows: `py -3 server.py`) yeterlidir. Oyuncular için Node/npm kurulumu gerekmez; bunlar yalnız geliştirici arayüz testlerinde kullanılır.

`index.html` dosyasına çift tıklayarak önceki yerel kadro/taktik/maç bölümlerini açabilirsin. Transfer ve günlük lig sunucu üzerinden çalışır. Dosya adresi ile localhost ayrı tarayıcı kayıt alanlarıdır; dosya adresindeki kayıt otomatik olarak localhost'a taşınmaz. ZIP yükseltirken eski sunucuyu kapat, mevcut `tribun-dev.sqlite3` dosyanı yeni oyun klasörüne kopyala ve aynı tarayıcı/adresi kullan. Transfer oturumu tarayıcıda, ekonomi SQLite dosyasında saklanır; ikisi birlikte gerekir.

## Neler var?

- Mevcut değerin 1–2,5 katı arasında satış fiyatı ve en fazla 4 ilan.
- Fiyat yükseldikçe azalan satış olasılığı; farklı zamanlarda bilgisayar kulüplerine satış.
- 5 token ile mevcut değerden hızlı satış; son kaleci ve asgari kadro koruması.
- Mevki, özel mevki, yaş, güç, uyruk, lig ve tarihli gerçek form ile keşif.
- Kadro ihtiyacına göre 6 saat açık kalan, yalnız token ile alınabilen teklifler.
- Ayrı kulüp kredisi/token bakiyeleri ve işlem defteri.
- Alınan oyuncunun kadro, antrenman, taktik ve maça taşınması; satılanın yeniden seçilememesi.
- Günlük lige bağlanan kadronun gücünün sunucuda hesaplanması ve canlı günlük maçta kadro kilidi.

**Gerçek ödeme ve reklam sağlayıcısı henüz bağlı değildir.** Satın alma ve reklam izleme düğmeleri bu nedenle kapalıdır; para tahsil edilmez. Başlangıçtaki 120 token deneme hediyesidir. `K`, oyun içi kulüp kredisidir; gerçek para veya çekilebilir bakiye değildir.

Kurallar ve gelecek veri/gelir bağlantıları: **TRANSFER_SISTEMI.md**. Test kapsamı: **DOGRULAMA.md**.

## Geliştirici kontrolleri

```sh
bash test_all.sh
npm ci
npm run test:ui
node tests/transfers-ui.test.cjs
node tests/ball-physics.test.cjs
node tests/press-support.test.cjs
node tests/pressure-exits.test.cjs
node tests/keeper-gather.test.cjs
node tests/defensive-connection.test.cjs
node tests/pass-lane-read.test.cjs
node tests/pass-review.test.cjs
node tests/pass-release-read.test.cjs
node tests/receiver-forecast.test.cjs
python3 tools/profile-transfer-market.py
```

Günlük lig ayrı sonuç hesabını kullanır; yerel 3D maç bunun kaydı değildir. Kontrollü hareketler, aynı durumdan karar karşılaştırması, doğal maçlar ve açık sınırlar **DOGRULAMA.md** içinde açıklanır. Doğru hedef tahmini, başarılı pas veya topu koruma garantisi değildir.

Güncel motorun doğal örneği **previews/ALICI_HAREKETI_v127.mp4** içinde. Gerçek sahnenin yerel 3D çizimidir; tarayıcı/telefon performans testi değildir. Son iki sürümün videoları pakettedir. Referans **FIFA_REFERANSI.md**, sonraki geliştirmeler **SIMULASYON_YOL_HARITASI.md** içinde.
