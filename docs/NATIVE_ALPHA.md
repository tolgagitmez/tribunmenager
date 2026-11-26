# Yeni motorla tek maçlık özel alfa — aşama 169

Bu deneysel dalın **normal başlatıcısı artık League-Soccer** çalıştırır.
Eski WebGL simülasyonu otomatik açılmaz. Yeni motor başlatılamazsa hata
gösterilir; eski motor yalnızca bilinçli `--mode local` seçimiyle açılır.
Bu dal henüz main'e aktarılmamıştır ve ticari sürüm değildir.

## Windows (WSL2 Ubuntu yolu, henüz gerçek Windows maç testi yapılmadı)
Windows Terminal (yönetici) içinde WSL2 Ubuntu kurulu değilse:
```powershell
wsl --install -d Ubuntu
```
Gerekiyorsa yeniden başlat; Ubuntu ilk açılışını tamamla. Ubuntu içinde
Git, Python 3.10+, Node.js 22/npm gerekli. Git için `sudo apt-get install git`.
Bu dalın ZIP'ini çıkar, Windows Python 3.10+ kurulu olsun. İlk çalıştırmada
oyun klasöründeki terminalde:
```bat
BASLAT.bat --native-install-deps
```
Windows başlatıcısı Ubuntu kullanıcı dizininde yalnızca bu GitHub dalını
klonlar; Ubuntu dosya sisteminde gerçek Linux motorunu derler. Sonraki
çalıştırmalarda BASLAT.bat; güncelleme için açıkça
`BASLAT.bat --native-update`. Yerel değişiklik varsa güncelleme durur.
Tarayıcıda terminalin bildirdiği **127.0.0.1:8765** adresini aç.
WSL localhost yönlendirmesi, Chrome ve makinenin performansı henüz
Windows üzerinde doğrulanmadı. Yönlendirme başarısızsa internete açma;
Ubuntu içinden yerel tarayıcı dene. WSL desteği yerel Windows OpenGL
derlemesi değildir.

## Linux
```sh
git clone --branch experiment/native-entrypoint-stage169 https://github.com/tolgagitmez/tribunmenager.git tribun-native-alpha
cd tribun-native-alpha
bash BASLAT.sh --native-install-deps
```
Daha sonra `bash BASLAT.sh`. Eski motoru özellikle açmak için
`bash BASLAT.sh --mode local` veya Windows'ta
`BASLAT.bat --mode local` (8000 portu). Yeni motor 8765 portu.
Bir kez derlenen ve kaynakla eşleşen runtime sonraki çalıştırmalarda
tekrar kullanılabilir. `--native-prepare-only` maç başlatmadan hazırlar.
`--port 8766`, `--native-delay 180` seçenekleri vardır.

## Maçı izle
Ana adres özel giriş ekranına yönlenir. Terminaldeki manager-session.txt
dosyasındaki oturum anahtarını yerel forma gir; paylaşma. Lig ekranında
maç öncesi taktikleri kaydet; maç başlayınca Orijinal motor yayını
bağlantısını kullan. Eski match.html yolu özel alfa sunucusunda lig
ekranına yönlenir. Canlı menajer ekranından taktik değiştir, motorun
onayını bekle. Sonucu özel ligde kontrol et.

Yalnızca bir gerçek maç; diğer fikstürler sırada. Yazılım OpenGL, 720p
kodlanmış video, motor sesi. Görüntü akıcılığı, Windows, genel lig
kapasitesi ve ticari varlık hakları henüz doğrulanmadı. Özel oturumlar
kaynak dizininin dışında; mevcut lig kayıtları değiştirilmez.
