# Transfer sistemi — v1.18

Bu kurallar görsellerde tarif edilen transfer döngüsünü temel alır; OSM'nin kapalı satış algoritmasının doğrulanmış parametreleri veya birebir kopyası değildir. Arayüz oyunun kendi tasarım sistemini kullanır.

## Başlangıç kuralları

| Alan | Ayar |
| --- | --- |
| Başlangıç bütçesi / token hediyesi | 25.000.000 K / 120 token |
| Aktif ilan | En fazla 4 |
| İlan fiyatı | Mevcut değerin 1–2,5 katı |
| Alıcı kontrolü | İlan başına rastgele 8–22 dakika |
| Hızlı satış | 5 token; mevcut değer kadar kulüp kredisi |
| Kadro | 14–30 oyuncu |
| Asgari mevki | 1 kaleci, 3 savunmacı, 3 orta saha, 1 hücumcu |
| Pazardaki arz | En fazla 24 ilan; tüm dünya havuzu aynı anda yüklenmez |
| Keşif | 4 saat; 250.000 K; en fazla 3 aday |
| Keşif raporu | Hazır olduktan sonra 24 saat |
| Özel teklif | 6 saat; yeni teklif için en az 24 saat |
| Token paketleri | 100 / 300 / 750; gerçek satış kapalı |
| Doğrulanmış reklam ödülü | 2 token; günde en fazla 3; aralarında en az 4 saat |

Ayarlar `data/transfer-rules.json` dosyasındadır. Değişiklikten sonra sunucuyu yeniden başlat. Mevcut profiller yeniden başlangıç hediyesi almaz. Bunlar ekonomi dengesi için ilk ayarlardır. K oyun içi kulüp kredisidir; gerçek para veya çekilebilir bakiye değildir.

## Satış döngüsü

İlan açılırken sahiplik, fiyat, ilan sayısı ve kadro güvenliği kontrol edilir. Rastgele ilk kontrol zamanı kaydedilir. Her ziyarette fiyat/değer oranı ve varsa gerçek formdan türetilen talep ile satış olasılığı hesaplanır. Yüksek fiyat aynı koşulda daha düşük olasılık üretir. Satılmazsa yeni bir kontrol zamanı kaydedilir. Yenilemek veya fiyat düzenlemek ziyaret saatini yeniden çekmez.

Satışta bütçe artışı, sahipliğin kapanması, ilk 11'in onarılması ve alıcı kulübün geçmişe yazılması tek işlemde olur. Kesin saat verilmez: yüksek fiyat ilk ziyarette de satılabilir; düşük fiyat birkaç ziyaret bekleyebilir. Beklenen fark çok sayıda örnekteki dağılımdır.

Sunucu açıkken çalışan görev satışları işler. Sunucu kapalı kaldıysa yeniden açılışta geçmiş kontrol zamanları ve kayıtlı rastgele durum sırayla ilerletilir. Günlük maç aralığındaki kontroller maç sonrasına ertelenir.

Kadro sınırı satış tamamlanırken tekrar denetlenir. Başka satış nedeniyle artık satılamayan ilan iptal edilir; bütçe eklenmez. Antrenmanla değer değişirse ilan yeni izinli aralığa çekilir. Hızlı satış aktif ilanı da kapatır. İlan geri çekmek ücretsizdir.

## Keşif ve gerçek form

Oyunun mevcut `form` alanı ile dış kaynaktan gelen `realForm` ayrıdır. Keşif ve pazar gerçek form filtresi `realForm.score` kullanır; kaydı olmayan futbolcu, sıfırdan büyük gerçek form filtresinde eşleşmez. Puanın sağlayıcısı, tarihi ve örnek maç sayısı kartta gösterilir.

Keşif filtreleri: mevki, özel mevki, alt/üst yaş, alt/üst güç, uyruk, lig ve asgari gerçek form. Eşleşme yoksa görev başlamaz ve ücret alınmaz. Sonuçlar süre dolmadan tarayıcıya gönderilmez. Rapordaki adayları almak için gösterilen kulüp kredisi ayrıca ödenir; rapor geçerliliği bitince alım reddedilir.

## Token teklifleri

Mevki ortalamalarıyla kadronun daha zayıf bölgesi bulunur; havuzda daha güçlü aday aranır. Aynı futbolcu zaten kadrodaysa tekrar alınamaz. Teklif yalnız bir kez kullanılır; mevcut oyuncu takas edilmez, yeni futbolcu kadroya eklenir. Otuz oyuncu sınırı geçerlidir.

Standart token bedeli: en az 20 token, her 500.000 K değer için bir token. İlk kampanya bunun %20 altındadır. Gerçek hesaplanan standart/teklif bedelleri gösterilir. Teklif süresi ve bakiyeler sunucuda denetlenir.

## Daha sonra futbolcu verisi bağlama

Normal `data/player-catalog.json` boştur. `tests/test_economy.py` içindeki futbolcular yalnız geçici test veritabanlarına alınır. Veri büyüdüğünde pazar sınırlı arz gösterir, gözlemci tüm katalogda arar.

Örnek şema (normal oyuna eklenmiş futbolcu değildir):

```json
{
  "version": 1,
  "players": [{
    "providerId": "veri-saglayici",
    "externalId": "benzersiz-kimlik",
    "name": "Futbolcu adı",
    "club": "Kulüp",
    "league": "Lig",
    "nationality": "TR",
    "age": 24,
    "pos": "MID",
    "subposition": "CM",
    "rating": 85,
    "value": 12000000,
    "updatedAt": "2026-10-30T12:00:00Z",
    "realForm": {"score": 82, "sampleMatches": 5, "asOf": "2026-10-29"},
    "passing": 87, "shooting": 78, "tackling": 74,
    "dribbling": 84, "pace": 80, "agility": 83,
    "heading": 72, "crossing": 79
  }]
}
```

Mevcut maç motorunda güç/teknik özellikler 1–99, gerçek form 0–100 aralığındadır. `value` dış kaynağın avro/sterlin değerinin otomatik kopyası değildir; oyun ekonomisine dönüştürülmüş tam sayı kredidir. Sağlayıcı adaptörü bu eşlemeyi yapar. Milliyet iki harfli ülke kodudur. Mevki eşleşmeleri: GK→GK; DEF→CB/LB/RB/LWB/RWB; MID→DM/CM/AM/LM/RM; ATT→ST/LW/RW/CF.

Sağlayıcı ve harici kimlikten kararlı `uid` oluşur. Eski `updatedAt`, daha güncel kaydı değiştiremez. Bütün kayıtlar doğrulanınca içe aktarma tek işlemde yapılır. Fotoğraf kaynağı bağlanana kadar katalog futbolcuları özgün silüet kullanır.

```sh
python3 economy.py --database tribun-dev.sqlite3 --import-catalog futbolcular.json
```

Sunucu açılırken `data/player-catalog.json` aynı doğrulayıcıdan geçer. Gelecekteki yetkili veri sağlayıcı adaptörü bu şemayı üretir. Bu sürüm internet taraması yapmaz veya gerçek futbolcu/form verisi indirmez. Katalog güncellemesi pazar kayıtlarını yeniler; satın alınmış futbolcuların teknik gelişimini topluca değiştirmez.

## Günlük lig

Transfer profili ve lig oturumu birlikte doğrulanarak bağlanır. Lig açıldığında veya plan lige kaydedildiğinde eşitleme yapılır. İlk 11'in mevki uyumu, kondisyonu, oyun içi formu ve gücüyle kalite sunucuda hesaplanır. Aynı lig kulübüne iki farklı transfer profili bağlanamaz; devam eden başka lige bağlı profil yeniden kullanılamaz.

Günlük maç sırasında alım, hızlı satış, antrenman ve ilk 11 değişimi reddedilir. Normal ilan açılabilir; o maç aralığındaki alıcı kontrolleri ertelenir. Lig mevcut ayrı sonuç hesabını kullanır; yerel 3D maç bunun kaydı değildir. Bot pazarı profil bazlıdır; insan kullanıcıların birbirine satış yaptığı ortak açık artırma henüz yoktur.

## Ödeme ve reklam köprüsü

İstemci token ekleme, reklam ödülü verme veya ödeme başarılı deme isteğiyle bakiye artıramaz. Gerçek satın alma ve reklam düğmeleri sağlayıcı bağlı olmadığı için kapalıdır.

Hazır köprü: `POST /api/commerce/verified-event`. Tarayıcının ödeme sonucu bildirmesi için değildir. Güvenilen sunucu adaptörü önce gerçek ödeme sağlayıcısının makbuz/webhook'unu veya reklam ağının SSV olayını doğrular; hesabı siparişe bağlar; ardından köprü zarfını imzalar.

- Sunucuda en az 32 karakter `TRIBUN_COMMERCE_SECRET` gerekir. Tarayıcı koduna veya dağıtılan ayar dosyasına yazılmaz.
- `X-Tribun-Signature`: ham UTF-8 JSON gövdesinin HMAC-SHA256 özeti, küçük harfli hex.
- Zarf: `provider`, benzersiz `eventId`, sunucunun verdiği `profileId`, saniye cinsinden `timestamp`, `type`.
- Token alımı: `type=token_purchase`, sunucuda tanımlı `sku`; istemcinin yazdığı miktar/bedel kullanılmaz.
- Reklam: `type=rewarded_ad`, `placement=transfer-reward`; ödül ve limit sunucudandır.
- İmza ve beş dakikalık pencere doğrulanır. `(provider,eventId)` tekildir; tekrar bildirim ikinci ödülü vermez. Farklı hesap/paketle aynı olay kimliği reddedilir.

Bu köprü gerçek sağlayıcı makbuz doğrulaması değildir; onun arkasındaki teslim noktasıdır. Gerçek checkout/mağaza ürünleri, sağlayıcı adaptörü, reklam SDK'sı, iptal/iade akışı ve üretim hesap sistemi henüz bağlı değildir. Python HTTP sunucusu yerel geliştirme sunucusudur; gerçek tahsilat için üretim barındırması kabulü yapılmadı.

## Kayıt ve yükseltme

Sunucu: `transfer_profiles`, `transfer_catalog`, `transfer_commands`, `transfer_ledger`, `transfer_receipts`, `transfer_league_links`. Harcama/sahiplik değişimi `BEGIN IMMEDIATE` ile atomiktir. İstek kimliği kaybolan yanıt sonrası ikinci harcamayı engeller; başka içerikle aynı kimlik reddedilir. Tarayıcı yalnız görünüm önbelleği tutar.

İlk profil açılışında eski örnek kadronun geçerli gelişimi bir defa taşınabilir. Bakiyeler, satın alma kayıtları veya harici futbolcu kimlikleri bu yolla alınmaz. Bu, geliştirme sürümleri arası geçiştir; üretim hesap açılışının yerini tutmaz. Tarayıcı oturumunu ve mevcut SQLite dosyanı birlikte koru.
