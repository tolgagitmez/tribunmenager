# v1.27 doğrulama

## Değişiklik ve testler

Yeni alıcı tahmini, seçilen kendi takım arkadaşının bilinen komutunu mevcut Match.move/effort hesabıyla kopyada ilerletir. Çıkış anındaki gövdeden hedef yeniden hesaplanır. Eski hız uzantısı ve aradaki hedef ayrıca okunur; en yüksek risk kullanılır. Mevcut tepki, son 0,12 saniye sınırı, alternatif/kontrol, yeniden karar bütçesi ve fiziksel müdahale sırası korunur. Yöntem ARCHITECTURE.md, EA'nın kamuya açık tasarım referansı FIFA_REFERANSI.md içindedir. EA motoru entegrasyonu veya eşdeğerliği iddia edilmez.

Genel regresyon 21 Python testi ve 30 Node komutuyla geçti. Önceki 37 test/yardımcı dosyasının tamamı byte düzeyinde aynıdır; eski assertion veya eşik değiştirilmedi. Yeni tests/receiver-forecast.test.cjs iki yönde durma, dönüş ve yeniden hızlanma için altı gerçek hareket karşılaştırması yapar; üç durumda tahmini hedefi gerçek vuruş hedefiyle karşılaştırır. Top/oyuncu/seed/gözlem kaydının değişmemesi, gelecekteki planın çağrılmaması ve bilinmeyen komutta hızla ilerleme geri dönüşü sınanır. Gelecek komut sabit tutulduğunda hareket hatası 0,015 m, hız farkı 0,02 m/s, çıkış hedef farkı 0,06 m altında aranır. Bunlar bütün maçlar için hata garantisi değildir.

Kontrollü koridor denemeleri aynı gözlemciyle korunur: rakip koşup geçtiğinde iki yönde ve yardımcı varken/yokken iptal olmadan ilk hedef 1,70 sn'de alır. Rakip koridorda kaldığında açık yardımcı 1,15 sn'de alır; yardımcı yokken kontrol sonrası ilk hedef 2,30 sn'de alır. Normal hareket, dönüş, fizik, vuruş ve alım kullanılır; sonuç veya RNG zorlanmaz. Dört örnek bir doğal maç başarı oranı değildir.

## Aynı durumdan karşılaştırma

Bilinen doğal dengeli/21 hata anı 2004,93 sn'dir. tools/profile-receiver-fork.cjs, özgün v1.26 maçında inceleme öncesi durumu alır. Oyuncu/Map/top/vuruş kimlik ilişkilerini koruyan iki structuredClone, aynı RNG durumuyla iki sürümün incelemesini birer kez çalıştırır. Top, konum, yön ve seed'in inceleme çağrısıyla değişmediği doğrulanır. Sonraki dört saniyede özgün hareket, müdahale, pas ve alım akışı çalışır.

| Ölçüm | v1.26 | v1.27 |
| --- | --- | --- |
| İlk hedef tahmininin özgün pas çıkış hedefine farkı | yaklaşık 1,172 m | bu örnekte 0 m |
| Tahmin edilen koridor riski | yaklaşık 0,515 | nominal 0,920; hız uzantısı 0,634; orta nokta 0,773 |
| Karar | ilk pası sürdür | alternatifi yeniden hazırla |
| Gerçek sonuç | pas çıkar, rakip 4 alır | alternatif pas çıkmadan kesilir; rakip 5 topu alır |

Alıcının mevcut komutu geriye destekken hızı henüz ters yöndedir. Yeni kopya normal ivme/dönüş hesabıyla bu değişimi okur; hedeflerin ayrımı yaklaşık 1,172 m'dir. Yeni nominal hedefin tam eşleşmesi bu sabit komutlu tek durumun sonucudur; geleceğin kusursuz bilindiği anlamına gelmez. Her iki dalda da ilk rakip sahipliği yaklaşık 2005,17 sn'dedir. Bu bir kurtarılmış top değildir; doğru risk değerlendirmesinden sonra yeni hazırlığın uygulanabilirliği hâlâ sorundur. Ham hata, karar, gerçek kayıp ve hareket kayıtları receiver-fork-v127.json içindedir.

## Doğal maçlar

Aynı tools/profile-pass-release.cjs, v1.27 için dengeli/21 ve pres/42 maçlarında 90 dakika çalıştı. v1.26'nın aynı gözlemciyle alınmış mevcut raporları; üç kaynak, gözlemci hash'i ve senaryo anahtarları doğrulanarak tekrar kullanıldı. Eski maçlar yeniden çalıştırılmış gibi sunulmaz. Gözlemcili skor ve şut iki sürümün gözlemcisiz matrisleriyle birebir eşleşir. Özgün eylemler birer kez çağrılır; ek RNG/politika yoktur.

Dengeli/21'in ilk okuması aynı durum karşılaştırmasıyla eşleşir. Yeni sürümde 1 yönlendirme, 0 erteleme vardır; skor 0–1 → 1–1, şut 14–3 → 13–8. Pres/42'de 3 reset, 0 erteleme sürer; skor 3–2, şut 20–4. İki yeni doğal maçın toplam 4 çıkış okumasında 1 kez hedef varsayımları güçlü tehlike eşiğinin farklı taraflarındadır. Bu sayaç kurtarılmış pas sayısı değildir.

Bir karar sonrasında maç yolları ayrışır. Son skor/şut farkı, ilk kararın doğrudan yerel faydası veya genel pas başarısı kanıtı olarak yorumlanmaz. Rakibin sonraki ivmesi, takımın yeni komutu, başka oyuncuların kaçınma hareketi ve geciken temas tahmini bozabilir. Yalnız üç hedef örneği bütün olası koridorları kapsamaz.

## 28 maç kontrolü

15 × 5 dakika (üç tohum/beş plan), 7 × 90 dakika ve 6 × 5 dakika diziliş tamamlandı. Bitiş, 0,15 m/adım, 18 sn sahipsiz top, 8 sn durağan sahiplik ve 60 sn duran top sınırları geçti. Kaynak/rig/taktik hash'leri sabit kaldı.

Yeni paralel doğrulayıcı, eski seri doğrulayıcının measure fonksiyonunu byte düzeyinde aynı tutar ve maçları iki yalıtılmış Node worker'ında çalıştırır. Bir maçın adım veya RNG sırası değiştirilmez. Önceki raporun üç girdisi ve senaryo anahtarları doğrulanır. Yeni doğal gözlemcilerin skor/şut eşleşmesi de bağımsız kontrol sağlar.

| Plan / tohum | v1.26 skor / şut | v1.27 skor / şut |
| --- | --- | --- |
| balanced / 21 | 0–1 / 14–3 | 1–1 / 13–8 |
| balanced / 42 | 5–3 / 14–10 | 5–3 / 14–10 |
| balanced / 77 | 3–0 / 11–5 | 3–0 / 11–5 |
| possession / 42 | 2–1 / 7–10 | 2–1 / 7–10 |
| wide / 42 | 2–3 / 8–10 | 2–3 / 8–10 |
| counter / 42 | 1–1 / 10–13 | 1–1 / 10–13 |
| press / 42 | 3–2 / 20–4 | 3–2 / 20–4 |

Yedi uzun maçın toplam golü 27 → 28 (ortalama 3,86 → 4,00), şutu 139 → 143. Bir skor ortalaması gerçekçilik veya taktik denge kabulü değildir. 5–3 sonucu ve pres örneğinin 20–4 şut dağılımı sürer. Küçük örneklem, sabit rakip ve ayrışan maç yolları nedeniyle genellenemez. Şut/gol kotası eklenmez; top, şut ve kaleci fiziği değiştirilmez.

## Arayüz, video ve paket

DOM ve gerçek yerel HTTP/SQLite transfer akışları geçti: ui-status-v127.json, ui-regression-v127.txt ve transfer-ui-v127.txt. Bunlar gerçek tarayıcı/GPU/telefon performans testi değildir. Eski 37 test dosyası ve 30 oyun varlığı aynıdır. Yedi HTML sayfasında yalnız sürüm altbilgisi değişir. Gerçek futbolcu eklenmez; ödeme/reklam sağlayıcılarının durumu korunur. Günlük lig ayrı sonuç hesabını kullanır; yerel 3D maç onun kaydı değildir.

ALICI_HAREKETI_v127.mp4 doğal dengeli/21 maçının 2001,93–2021,93 saniyeleridir. Yeni hedef/risk okuması, yeniden değerlendirme ve ardından süren gerçek top kaybı korunur. 20 sn, 480 kare, 1024×576, 24 FPS; gerçek sahne/model/rig verisinin yerel EGL çizimidir. İlk tahmin zamanı, nokta ve karar hem aynı durum karşılaştırması hem tam doğal maç gözlemcisiyle eşleşir. Tam ffmpeg çözümü ve dört örnek kare incelemesi yapılır. Video tarayıcı kaydı, FIFA motoru kaydı veya başarılı top koruma kanıtı değildir.

Başlangıç ZIP'inin 551 manifest girdisi ve CRC'si doğrulandı. Dağıtım son iki sürümün videosunu tutar; v1.25 videosu çıkarılır, oyun varlıkları korunur. Yeni ZIP bağımsız açma/CRC ve her dosyanın SHA-256 kontrolüyle doğrulanır. Kaydedilen kopyanın birebir teyidi ZIP dışında teslim kaydında tutulur.

## Sonraki öncelik

Baskı altında güvenli görünen alternatif için gerçekten hazırlık süresi bulunup bulunmadığı; ilk çıkıştan sonraki destek/ikinci top; ani yeni komutlarda tahmin belirsizliği; farklı rakip/kadro ve gerçek cihazda kesintisiz maç kabulü üzerinde çalışılmalıdır.
