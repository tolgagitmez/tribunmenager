# Rol uyumu ve ligde kalıcı oyuncu rotasyonu

Bu sürüm, tek otoriter saha motorunun bulunduğu mevcut geliştirme
dallarının devamıdır. Fikstür izlemek/izlememek, oyuncu yeteneğini,
maç süresini, kart cezasını veya sezon kaydını değiştirmez.

## 1. Geniş pozisyon gruplarının ötesinde rol uyumu

\`player-model.js\`, yalnızca \`DEF/MID/ATT\` değil, bildirilen
\`subposition\` ve \`positions\` alanlarını da kullanır.

- **Stoper (CB)** topun arkasında, merkezi daraltan savunma ve
  kısa risk yönetimiyle; **bek (LB/RB)** top tarafındaki geniş alan
  desteği ve uygun \`fullbacks\` talimatında ileri koşuyla ayrışır.
- **Ön libero (DM)** topun arkasındaki güvenlik konumunu, kısa
  güvenli pası ve pas kesme alanını; **ofansif orta saha (AM)**
  hatlar arasındaki ileri konumu ve öne pas fırsatını arar.
- \`LWB/RWB\`, \`LM/RM\` ve komşu pozisyonlar için uyum komşuluk
  haritası vardır. Bir oyuncu kendi açıkça bildirdiği birincil
  veya ek mevkisinde tam uyum, yakın mevkide daha düşük uyum alır.
- Sol/sağ çizgideki \`preferredFoot\` yanlış tarafa düşerse
  ilave rol uyum cezası uygulanır. \`both\` ve \`unknown\`
  gerçek dışı bir yanlış ayak cezası almaz.
- Genel pozisyonu dışında ayrıntılı rol belirtmeyen eski
  oyuncular, uydurulmuş bir özel mevki/ayak bilgisi almadan
  mevcut sektör modeliyle değerlendirilir.
- Fikstürlerde geriye dönük oyun dengesi/maç tohumu testlerini
  korumak için \`dataKind=demo\` ve \`league-demo\` kayıtlarına
  yeni ayrıntılı taktik eğilimleri zorla yüklenmez. Gerçek
  profilini açıkça bildiren futbolcularda kullanılır.

Maç motorunda \`teamRole()\`, \`plan()\` ve \`passOptions()\`
bu farkları gerçek koşu hedefi, defansif mesafe ve pas puanına
uygular. Ham \`rating\` değiştirilmez. Aynı 80 genel puanlı,
eşit fizik/teknik becerili iki oyuncunun koridor tercihleri
aynı olmak zorunda değildir.

## 2. Oyuncu bazında maç dakikaları ve sezon DB kaydı

\`Match.appearanceReport()\` ve \`live-match-worker.cjs\` her
futbolcunun \`team\`, kalıcı \`rosterId/rosterUid\`, sahada
geçen saniye, 90 dakika ölçeğine normalize edilmiş dakika,
yüksek tempolu koşu süresi, ilk kondisyonu, sarı kart ve
kırmızı kartını **otoriter tek fizik motorundan** alır.

Yerel 5 dakikalık maçın tüm süresi futbol karşılaşmasının
90 dakika ölçeğine dönüştürülür. Oyuna sonradan giren
oyuncu ile değiştirilen eski futbolcunun kayıtları farklı
kalıcı kimliklerde tutulur; formadaki geçici aktör indeksi
oyuncu kimliği yerine geçmez.

Sunucu \`season_state.py\` üzerinden iki tablo tutar:

- \`season_fixture_appearances\`: fikstür ve oyuncu başına
  **değiştirilemez, tekrar işlenmeyen** dakika/kart/kondisyon özeti
- \`season_player_state\`: toplam maç/dakika, sezon sarı/kırmızı
  sayısı, kondisyon, son maç günü ve geçerli kart cezası

Fikstürün \`home_score\`, \`away_score\`, kart toplamları,
\`live_matches.final_state\` ve oyuncu sezon güncellemesi
**aynı SQLite transaction** içerisinde saklanır.
Sunucu tekrar oynatma günlüğünü işlediğinde aynı oyuncunun
dakikaları ve cezaları tekrar eklenmez. Transfer/e-ticaret
hesabının bakiye veya özel durumu güncellenmez.

### Başlangıç kondisyon ve ceza modeli

Bu MVP'de her maçın sonunda kondisyon, futbolcunun oynadığı
dakika ve yüksek süratli koşu payına göre azalır. Sonraki
fikstür gününe kadar her geçen maç gününde **8 kondisyon puanı**
toparlanır (üst sınır 100). Formül:

\`son kondisyon = clamp(ilk kondisyon - 13 × dakika / 90 - 5 × yüksek tempolu koşu payı, 30, 100)\`

Buradaki 13 / 5 / 8 değerleri ilk oyun dengesi parametreleridir;
profesyonel sakatlık/fizyolojik öngörü veya gerçek kulüp
disiplin yönetmeliği iddiası taşımaz.

- Kırmızı kart: **sonraki 1 lig fikstüründen men**.
- Sezon boyunca **5 sarı kart**: sonraki 1 lig fikstüründen men;
  beşli sayaç yeniden başlar.
- İkinci sarı karttan kırmızı da kırmızı cezası üretir.
- Kart sayısı maç motorundaki gerçek disiplin kararından alınır.
- Cezalı futbolcu sonraki maçın ilk 11'ine giremez. Uygun
  bir yedek varsa önce aynı özel mevki, sonra aynı sektör
  tercih edilerek kickoff fotoğrafında otomatik değiştirilir.
  Yeterli uygun futbolcu yoksa hayalî/cezalı bir oyuncu
  oynatılmaz; yeni kadro kurulması için açık hata verilir.
- Maç gününün öncesindeki kadro/kondisyon projeksiyonu kaydı
  değiştirmez. Fikstürün başlangıç fotoğrafı \`live_matches.config\`
  içinde dondurulur ve sonradan roster düzenlemesiyle değişmez.
- Birden fazla maç günü kaçırılmışsa, önceki günün tüm fikstürleri
  gerçekten bitmeden sonraki günün ilk 11'i dondurulmaz.

Önceden oynanmış ancak oyuncu bazlı veri kaydedilmemiş
tarihsel fikstürler geriye dönük olarak tahmin edilmez.

## 3. Kullanıcı ekranı

\`league.html\` içindeki **Kondisyon, dakika ve kart cezaları**
panelinde futbolcuların mevcut kondisyonu, lig dakikası,
biriken sarı/kırmızı kartı ve sıradaki maçta cezalı olup
olmadığı gösterilir. Panelin kaynağı \`/api/league/status\`
yanıtındaki \`my_rotation\` verisidir; özel transfer cüzdanı,
başkasının hesabı veya ticari kayıtlar gönderilmez.

Oyuncuyu dinlendirmek için transfer/kadro ekranından
ilk 11 seçimlerini değiştirmek mümkündür. Ancak bir
menajerin kendisi kadro güncellemesini açıkça kaydetmeden
bu panel tek başına seçim yapmaz. Cezalı futbolcu varsa
sunucu mecburi uygun yedek yerleşimini kickoff anında yapar.

## 4. Testler

\`\`\`bash
node --test tests/role-behavior-season.test.cjs
node --test tests/player-model.test.cjs tests/player-identity-integration.test.cjs
node --test tests/fixture-watch-parity.test.cjs
python -m unittest discover -s tests -p 'test_season_rotation.py' -v
python -m unittest discover -s tests -p 'test_unified_fixtures.py' -v
python -m unittest discover -s tests -p 'test_live_match.py' -v
python tests/fixture-roster-api.py
\`\`\`

Hedefli testler eşit 80 genel puanlı bek, stoper, ön libero
ve AM için mevkisel uyum, pas değerlendirmesi, defansif yer
tutma ve gerçek koşuyu; yedek değişikliklerinde iki ayrı
oyuncuya yazılan dakikaları, kart birikimi ve maç menini,
server restart/çift işleme direncini ve iki geçmiş
fikstür gününün doğru sırada dondurulmasını kontrol eder.

## 5. Sınırlar

- Gerçek futbolda men süresi müsabaka talimatı ve ihlal türüne
  göre değişebilir; MVP'deki tek maçlık kırmızı / beş sarı
  kuralı lig oyununa özeldir, gerçek federasyon iddiası değildir.
- Yorgunluk burada maçlar arasında oyun mekaniğidir; sakatlık,
  antrenman, sağlık, seyahat ve maç içi oyuncu değiştirme
  animasyonlarının tümünü kapsamaz.
- Otomatik kadro yenileme yalnızca **mevcut uygun** kayıtlı
  oyuncular arasından yapılır. Oyuncu kimliği, maaş/kontrat
  sistemi ve karmaşık pozisyon öğretimi ayrı kapsamdır.
- 90 dakika karşılığı, kısa fiziksel maç ölçeğinden
  türetilmiştir; gerçek saat süresi değildir.
