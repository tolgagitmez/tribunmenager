# Tribün Manager kurulumu

Yerel futbol simülasyonu için **Python 3.10 veya üzeri** ve güncel Chrome, Edge veya Firefox yeterlidir. Oynamak için Node.js, npm veya Python paketi kurman gerekmez. İnternet bağlantısı olmadan yerel maç oynanabilir; bazı isteğe bağlı font ve görseller yüklenmeyebilir.

## 1. Oyunu indir

Güncel geliştirme sürümü `codex/team-continuity-perception` dalındadır:

- [Güncel sürümü ZIP olarak indir](https://github.com/tolgagitmez/tribunmenager/archive/refs/heads/codex/team-continuity-perception.zip), ZIP'i çıkar ve içindeki klasörü aç.
- Git kullanıyorsan:

```sh
git clone --branch codex/team-continuity-perception https://github.com/tolgagitmez/tribunmenager.git
cd tribunmenager
```

`main` dalı, taslak geliştirme dalından daha eski olabilir. [Değişiklikleri ve doğrulama durumunu PR #1'den takip edebilirsin](https://github.com/tolgagitmez/tribunmenager/pull/1).

## 2. Python'u kontrol et

[python.org/downloads](https://www.python.org/downloads/) adresinden Python 3.10 veya üzerini kur. Windows kurulumunda **Add Python to PATH** seçeneğini işaretle.

Windows terminalinde:

```bat
py -3 --version
```

macOS / Linux terminalinde:

```sh
python3 --version
```

## 3. Oyunu başlat

**Windows:** `BASLAT.bat` dosyasını çift tıkla. Tarayıcı açılmazsa aşağıdaki adresi kendin aç. Alternatif komut:

```bat
py -3 start.py
```

**macOS / Linux:** oyun klasöründe terminal aç:

```sh
sh BASLAT.sh
```

Alternatif komut:

```sh
python3 start.py
```

Tarayıcıda **http://127.0.0.1:8000/** adresini aç. **Kadro → Taktik → Maçı başlat** yolunu izle. Sunucu açık kaldığı sürece oyun çalışır; kapatmak için terminalde **Ctrl+C** kullan. HTML dosyalarını çift tıklayarak `file://` üzerinden açmak yerine bu adresi kullan.

## Çalışma modları

Varsayılan başlatıcı **yerel maç modunu** açar. Kadro, taktik ve maç simülasyonu çalışır; transfer hesabı ve günlük lig API'si bu modda kapalıdır. Rakibin kayıtlı kadrosu yoksa maçta deneme kadrosu olduğu belirtilir. Eksik özgün oyuncu modellerinde prosedürel WebGL çizimi, WebGL kullanılamadığında 2D çizim devreye girer.

Tam sunucu modu, ayrıca şu üç dosyayı gerektirir:

```text
data/transfer-rules.json
data/player-catalog.json
data/club-seed.json
```

Bu çalışma kopyasında bu dosyalar bulunmuyor; boş veya rastgele içerik oluşturarak tam modu açmaya çalışma. Uygun ekonomi kuralları, doğrulanmış oyuncu kataloğu ve başlangıç kadrosu ayrıca sağlandıysa:

```sh
python3 start.py --mode full
```

Windows'ta aynı komutun başında `py -3` kullanabilirsin. Tam modun geliştirme sunucusu SQLite verisini `tribun-dev.sqlite3` dosyasında saklar. Mevcut veri dosyasını ve tarayıcı depolamasını koru. Kayıtlar tarayıcı profiline, adrese ve porta bağlıdır; `localhost` ile `127.0.0.1` ayrı tarayıcı depoları kullanır. Yerel gösterim maçının sonucu günlük lig fikstürünü değiştirmez.

## Sorun giderme

| Sorun | Yapılacak işlem |
| --- | --- |
| Python bulunamıyor | Python'u kur; terminali kapatıp yeniden aç. Windows'ta `py -3` dene. |
| 8000 portu kullanımda | `python3 start.py --port 8001` çalıştırıp http://127.0.0.1:8001/ adresini aç. Windows'ta `py -3 start.py --port 8001` kullan. |
| Siteye erişilemiyor | Başlatıcı terminalinin açık olduğunu ve tarayıcı adresiyle portun eşleştiğini kontrol et. |
| Tam mod eksik dosya hatası veriyor | Yerel maç için `--mode local` kullan; tam mod için listelenen gerçek veri dosyalarını temin et. |
| Transfer sayfasında bağlantı hatası | Yerel modda transfer API'si kapalıdır. Kadro ve taktik ekranından yerel maç başlat. |
| Görüntü 2D açılıyor | Tarayıcının donanım hızlandırmasını/WebGL desteğini kontrol et. 2D yedek görünümle maç devam edebilir. |
| Eski transfer hesabı yerel maç başlangıcını engelliyor | Önce aynı tarayıcıdaki veriyi dışa aktar/yedekle; deneme için ayrı bir tarayıcı profili aç. Kayıtlarını silmek zorunda değilsin. |

## Geliştirici doğrulaması

Oynamak için gerekli değildir. Testler için `package.json` içindeki sürüm aralığına uyan Node.js gerekir; **Node.js 24.15 veya üzerindeki 24.x** uygun bir seçimdir. Proje Python tarafında standart kütüphaneyi kullanır.

```sh
npm ci
npm run test:stage12
```

Gerçek tarayıcı doğrulaması ayrıca Playwright ve Chromium gerektirir; ayrıntılar [DOGRULAMA.md](DOGRULAMA.md) içindedir. Test raporları ve açık geliştirme işleri [yol haritasında](SIMULASYON_YOL_HARITASI.md) açıklanır.
