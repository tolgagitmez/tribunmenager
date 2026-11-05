# Sonraki simülasyon geliştirmeleri

v1.27, kendi alıcısının bilinen koşu komutunu gerçek hareket hesabıyla kopyada ilerletir ve farklı hedef varsayımlarının koridor riskini karşılaştırır. Bilinen hata örneğinde hedef tahmini düzelir; her iki gerçek karar dalında top kaybı sürdüğünden genel top koruma başarısı iddia edilmez.

| Sıra | Öneri | Aranacak davranış |
| --- | --- | --- |
| 1 | Yüksek preste ilk kararın uygulanabilirliği | Güvenli görünen alternatif için gereken hazırlık ve yaklaşan müdahale birlikte değerlendirilsin; doğru risk okuması sonrasında hücum fiziksel olarak sürdürülebilsin |
| 2 | Destek devamlılığı ve ikinci top | İlk çıkıştan sonra pas açıları, koşular ve seken top paylaşımı takım halinde yenilensin; herkes topa yığılmasın |
| 3 | Tahmin belirsizliğini genişletmek | Yeni komut, ani duruş/dönüş, yakın arkadaşlardan kaçınma ve geciken temasta yanlış güven ile gereksiz iptal ayrı ölçülsün |
| 4 | Taktik ve kadro çeşitliliği | Farklı rakip planları, güçte kadrolar, üçlü/beşli savunma ve eksik oyuncu örnekleri karşılaştırılsın |
| 5 | Duran top, temas ve cihaz kabulü | Şut/pas/orta tercihi; ayak/top/gövde teması ve kayma; gerçek tarayıcı/telefonda kesintisiz maçlar incelensin |

FIFA/EA FC'nin yayımlanmış oynanış hedefleri referanstır; mevcut kodun motor entegrasyonu veya aynı kaliteye ulaştığı iddiası değildir. Sürüm sayısı ve skor ortalaması, gerçek futbol deneyimi için bitiş garantisi vermez. Kanıtlar ve açık sınırlar DOGRULAMA.md içindedir.
