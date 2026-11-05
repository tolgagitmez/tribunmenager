# Tribün Manager 3D v1.27

Hareketli alıcı hedefi, bilinen koşu komutu ve normal motorun ivme, frenleme, dönüş ve kondisyon hesabıyla kopyada ilerletilerek yeniden tahmin edilir. Eski hız uzantısı ve aradaki nokta da risk açısından okunur. Bir hedef varsayımı güçlü tehlike gösteriyorsa diğerinin açık olması tek başına pas incelemesini bastırmaz.

Bilinen doğal örnekte hedef farkı yaklaşık 1,172 m'den 0'a iner ve yanlış açılma tahmini reddedilir. Aynı durumun iki gerçek karar dalında da top kaybı sürer; kurtarılmış top iddiası yoktur. FIFA/EA FC'nin kamuya açık tasarım ilkeleri referans alınır; uygulama Tribün'ün özgün motor kodudur. FIFA_REFERANSI.md ve DOGRULAMA.md ayrıntıları içerir.

21 Python testi, 30 Node komutu, arayüz/transfer akışı ve 28 maç kontrolü geçti. Önceki 37 test dosyası ve 30 oyun varlığı korunur. Yedi uzun maçın gol ortalaması 3,86 → 4,00; genel denge/gerçekçilik kabulü değildir.

ZIP'in tamamını çıkarıp BASLAT.bat ile aç. Python 3.10+ gerekir. Yükseltirken eski sunucuyu kapat; tribun-dev.sqlite3 dosyanı yeni klasöre kopyala ve aynı tarayıcı/adresi kullan. Oyuncu için Node/npm gerekmez. Gerçek futbolcu kataloğu ve ticaret sağlayıcılarının durumu korunur.
