# Tribün Manager — yeni motorla yerel alfa

Bu deneysel dal tek bir gerçek League-Soccer karşılaşması başlatmak için
hazırlanmıştır. Henüz genel beta, ticari yayın, mobil uygulama veya
tam lig değildir. Mevcut main ve kayıtlı ligler değişmez.

## Linux üzerinde başlatma
Ubuntu 22.04, Python 3.10+, Node.js 22/npm, Git ve uygun donanım gerekir.
İlk çalıştırmada internetten sabitlenmiş motor kaynakları indirilir,
Chrome/Playwright ve sistem bağımlılıkları kurulur; yalnızca
`--install-deps` açıkça verilirse apt/npm kurulumları yürütülür.
Bu komut sudo isteyebilir.

```sh
git clone --branch experiment/native-playable-alpha-stage168 https://github.com/tolgagitmez/tribunmenager.git tribun-native-alpha
cd tribun-native-alpha
bash BASLAT_NATIVE_ALFA.sh --install-deps
```

Bağımlılıklar zaten kuruluysa `bash BASLAT_NATIVE_ALFA.sh` kullan.
Her deneme ayrı bir özel klasöre yazılır. Derleme çıktısını sonraki
denemede tekrar kullanmak için terminalde gösterilen Motor yolunu
`--runtime /tam/yol/runtime` ile ver. Eski motor bu kaynakla
eşleşmiyorsa başlatıcı reddeder. `--prepare-only` maç başlatmadan
hazırlar. `--port 8766` ile farklı bir yerel port seçilebilir.

1. Terminalin gösterdiği http://127.0.0.1:8765/native-beta-login.html adresini aç.
2. Terminalde gösterilen manager-session.txt dosyasındaki anahtarı
   yalnızca yerel giriş ekranına gir. Anahtarı paylaşma.
3. Lig ekranında maç başlangıcını bekle. Varsayılan hazırlık süresi
   120 saniyedir; --delay 180 ile değiştirebilirsin.
4. Canlı maçı izle bağlantısı açılınca tıkla; yayını başlat, sesi aç.
   Mevcut canlı menajer panelinden taktik değiştir.
5. Maç bitince lig ekranında özel sonucu kontrol et. Sonuç kontrolü
   için sunucu 120 saniye açık kalır. Ctrl+C ile durdurabilirsin.
   Ayrıntı match/private-beta-report.json dosyasındadır.

## Bilinen sınırlar
Yalnızca bir maç başlatılır; diğer iki lig maçı sırada kalır.
Otomatik tarayıcı doğrulaması da çalışır ve ek CPU tüketir.
Yazılım OpenGL çizicisi, 720p video, gerçek motor sesi; akıcılık
garanti edilmez. Performans/kapasite ve varlık hakları henüz onaylı
değildir. Windows, WSL, macOS ve telefondan erişim doğrulanmamıştır.
Sunucuyu internete açma. Deneysel grafik ve hücum özellikleri
başlatıcı tarafından temizlenir. Genel oyun dosyaları ile eski
kayıtlar silinmez. Bu deneysel başlatıcı gerçek CI testi geçmeden
hazır sürüm olarak etiketlenmemelidir.
