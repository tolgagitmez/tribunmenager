# Tribün Manager kurulumu

Yerel futbol simülasyonu için **Python 3.10 veya üzeri** ve güncel Chrome, Edge veya Firefox yeterlidir. Oynamak için Node.js, npm veya Python paketi kurman gerekmez. İnternet bağlantısı olmadan yerel maç oynanabilir; bazı isteğe bağlı font ve görseller yüklenmeyebilir.

## 1. Oyunu indir

Menajer vuruşlarını ve canlı ligi içeren sürüm `codex/manager-kick-control` dalındadır.

- [Güncel sürümü ZIP olarak indir](https://github.com/tolgagitmez/tribunmenager/archive/refs/heads/codex/manager-kick-control.zip), ZIP'i çıkar ve içindeki klasörü aç.
- Git kullanıyorsan:

```sh
git clone --branch codex/manager-kick-control https://github.com/tolgagitmez/tribunmenager.git
cd tribunmenager
```

`main` önceki geliştirme aşamalarını içerir. [Dal karşılaştırması](https://github.com/tolgagitmez/tribunmenager/compare/main...codex/manager-kick-control).

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

Varsayılan başlatıcı **yerel maç modunu** açar. Kadro, taktik ve maç simülasyonu çalışır; transfer hesabı ve günlük lig API'si bu modda kapalıdır. Rakibin kayıtlı kadrosu yoksa maçta deneme kadrosu olduğu belirtilir. İnsan modeli, iskelet ve dokuları pakete dahildir; ayrıca model indirmen gerekmez. Model hazırlanamazsa maç prosedürel WebGL çizimine, WebGL kullanılamazsa 2D çizime geçer.

Modeli incelemek için aynı sunucuda **http://127.0.0.1:8000/player-studio.html** adresini aç. **Tam boy**, **Yüz** ve **Arka** kameralarını kullan; hareket seçimiyle deformasyonu incele. Maç ve stüdyodaki model durumunun ayrıntısını açarak model kimliğini, lisans kaydını ve yükleme hatalarını görebilirsin. Beklenen kimlik `tribun-makehuman-footballer-v1`, hazır durumu **İSKELETLİ OYUNCU MODELİ** olarak görünür. Stüdyo, ayrıntılı model hazırlanamazsa hata gösterir.

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

## Canlı lig

Python'a ek olarak Node.js 24 LTS kur. Lig modu maç motorunu sunucuda çalıştırır ve transfer kataloğu gerektirmez.

```sh
python3 start.py --mode league --host 0.0.0.0
```

Windows'ta `py -3 start.py --mode league --host 0.0.0.0` kullan. İki menajer aynı sunucunun adresindeki `/league.html` sayfasını açmalı. Aynı ağda ikinci cihaz, `127.0.0.1` yerine sunucuyu çalıştıran bilgisayarın ağ adresini kullanır. Bir menajer lig kurar, diğeri davet koduyla katılır. Fikstür saati geldiğinde **Canlı maçı izle** bağlantısı açılır.

Maç sunucuda devam eder. İzlerken kendi takımının vuruşlarını seçebilirsin. Başka sekmeye geçersen izleyici bağlantısı kısa süre içinde düşer ve seçim otomatik kullanıma döner. Sunucu tamamlanan maçın skorunu SQLite lig tablosuna yazar.

## Sorun giderme

| Sorun | Yapılacak işlem |
| --- | --- |
| Python bulunamıyor | Python'u kur; terminali kapatıp yeniden aç. Windows'ta `py -3` dene. |
| 8000 portu kullanımda | `python3 start.py --port 8001` çalıştırıp http://127.0.0.1:8001/ adresini aç. Windows'ta `py -3 start.py --port 8001` kullan. |
| Siteye erişilemiyor | Başlatıcı terminalinin açık olduğunu ve tarayıcı adresiyle portun eşleştiğini kontrol et. |
| Tam mod eksik dosya hatası veriyor | Yerel maç için `--mode local` kullan; tam mod için listelenen gerçek veri dosyalarını temin et. |
| Transfer sayfasında bağlantı hatası | Yerel modda transfer API'si kapalıdır. Kadro ve taktik ekranından yerel maç başlat. |
| Görüntü 2D açılıyor | Tarayıcının donanım hızlandırmasını/WebGL desteğini kontrol et. 2D yedek görünümle maç devam edebilir. |
| Model paneli yedek veya geçersiz model gösteriyor | Ayrıntıları aç; eksik dosya yolunu veya veri alanını kontrol et. ZIP'i tamamen çıkartıp `assets/player/` klasörüyle birlikte başlat. Model dosyasını tek başına başka sürümden kopyalama. |
| Doku veya shader hatası görünüyor | Paneldeki teknik ayrıntıyı kaydet. Doku hatasında belirtilen PNG'nin pakette olduğunu, grafik hatasında tarayıcı/WebGL desteğini kontrol et. Maç yedek çizimle sürebilir. |
| Eski transfer hesabı yerel maç başlangıcını engelliyor | Önce aynı tarayıcıdaki veriyi dışa aktar/yedekle; deneme için ayrı bir tarayıcı profili aç. Kayıtlarını silmek zorunda değilsin. |

## Standart model aktarımı

Yerel sunucu açıkken `http://localhost:8000/interop-lab.html` adresinden aynı Blender GLB/glTF dosyasını iki çizicide karşılaştır. Model türü, klip, zaman, kamera ve 1/22 oyuncu seçenekleri ortak çalışır. Three.js ve yardımcı modüller yerel `vendor/` klasöründedir; bu ekran için Node.js veya CDN gerekmez. Düzenlenebilir Blender kaynağı ve yeniden üretim adımları [GLTF_PIPELINE.md](docs/GLTF_PIPELINE.md), ölçülen karar [GLTF_RENDERER_DECISION.md](docs/GLTF_RENDERER_DECISION.md) içindedir.

## Geliştirici doğrulaması

Oynamak için gerekli değildir. Testler için `package.json` içindeki sürüm aralığına uyan Node.js gerekir; **Node.js 24.15 veya üzerindeki 24.x** uygun bir seçimdir. Başlatıcı ve maç/ekonomi testleri Python standart kütüphanesini kullanır. Modelin yeniden üretimi ve varlık testleri ayrıca **Python 3.11+** ile [requirements-player-assets.txt](requirements-player-assets.txt) içindeki NumPy/Pillow sürümlerini gerektirir; bunları ayrı bir Python sanal ortamına kurabilirsin.

```sh
npm ci
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r requirements-player-assets.txt
npm run test:stage15
npm run test:manager-kick
npm run test:live-match
```

Windows'ta sanal ortamı `.venv\Scripts\activate` ile etkinleştir; Python komutlarında `py -3` veya etkin ortamın `python` komutunu kullan.

Tarayıcı denemeleri için `npx playwright install chromium` çalıştır. Ardından `npm run test:manager-kick-browser` ile masaüstü ve mobil vuruşu, `npm run test:live-match-browser` ile iki menajerin maç ekranını doğrula. Sistemde Chromium kuruluysa `CHROMIUM` değişkeniyle dosya yolunu verebilirsin.

Modeli paketlenmiş kaynaklardan internet kullanmadan ayrı bir dizinde yeniden üretmek için:

```sh
python3 tools/build-player-assets.py --from-package --output /tmp/tribun-player-rebuild
```

Windows'ta `py -3` ve örneğin `--output oyuncu-yeniden-uretim` kullanabilirsin. Çıktı yolu örnektir; mevcut oyun paketinin üzerine yazmak zorunda değilsin. Komut özgün kaynak dosyalarının ve lisansların sabit hash'lerini denetler. Ayrıntılar [oyuncu varlıkları sözleşmesinde](docs/PLAYER_ASSETS.md) bulunur.

Gerçek tarayıcı doğrulaması ayrıca Playwright ve Chromium gerektirir; ayrıntılar [DOGRULAMA.md](DOGRULAMA.md) içindedir. Test raporları ve açık geliştirme işleri [yol haritasında](SIMULASYON_YOL_HARITASI.md) açıklanır.
