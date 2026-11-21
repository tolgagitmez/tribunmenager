# Aşama 16 — baskı öncesi güvenli ileri pasın bekletilmemesi

## Tek neden ve minimal değişiklik

**Kopuş:** Normal \`choose()\` akışında, topun sahibi 4,2 m'den uzaktaki baskıyı beklerken (destek planının birinci seçeneği hazır değilse) bir veya iki metrelik 'hold' sürüşü yapabiliyordu. Bu, aynı anda erişilebilir, düşük riskli bir **başka ileri pasın** varlığına rağmen olabiliyordu. Savunma kapanırken amaçsız bekleme ardından duello veya pas arası riski taşıyordu.

**Düzeltme:** Yalnızca bu özel bekleme dalında, \`passOptions()\`'ın zaten ürettiği kısa, ileri, düşük riskli seçenekler sırayla yoklanır. İleri kazanım >3 m, mesafe <24 m, şerit riski <0,34, varış riski <0,60, açık alan >2,4 m, uygun gövde dönüşü ve pozitif skor gerekir. Ayrıca normal \`passPreparation()\` izole fizik tahmini vuruşun gerçekten hazırlanabilir olduğunu doğrulamalıdır. İlk iki aday da başarısızsa **eski bekleme davranışı korunur**. Yeni rastgelelik, teleport, vuruş istisnası, hakem kuralı veya savunmacı zayıflatması yoktur. Alıcı dönüşü, destek yerleşimi ve ceza sahası koşusu kodlarına dokunulmadı.

## Ölçülen dört maçın ilk 120 saniyesi

Aynı mevcut motor/aynı tohum/dizilişle karşılaştırılan dört senaryo: \`balanced21\`, \`press42\`, \`narrow21\`, \`wide21\`. Her senaryoda kendi sabit kadrosu ve taktikleri kullanıldı; kullanıcıdan gelen 413 saniye / 2 şut örnekleminin tam konfigürasyonları verilmediğinden **aynı deneymiş gibi gösterilmez**.

| Ölçüt | Eski motor kararı | Tek düzeltme sonrası |
| --- | ---: | ---: |
| İncelenen oyun içi süre | 415,63 sn | 397,85 sn |
| Gerçek şut | 1 | 3 |
| Nitelikli, kontrolü doğrulanmış kazanım hücumu | 29 | 17 |
| Bu kazanım hücumlarında hat kırma | 7 | 6 |
| Bu kazanım hücumlarında son bölge teması | 3 | 4 |
| Aynı cohort'ta gerçek kontrollü ceza sahası girişi | 0 | 1 |
| İkili mücadeleyle sonlanan kazanım hücumu | 12 | 8 |
| Pas arasıyla sonlanan kazanım hücumu | 7 | 3 |
| Gerçek kayıplar: öz takımın hücum yönüne göre ilerleme bölgesi (0–17 m) | 13 | 4 |
| Aynı 8×8 m mekânsal hücrede ikinci ve sonraki kayıplar | 2 | 0 |
| Bekletme yerine güvenli ileri pas seçimi | 0 | 19 |

**Ölçüm sınırı:** Ceza sahası, saha koordinatları ve doğal gerçek kontrolle ölçülür; planlanan koşular veya hazırlanmış ama henüz vurulmamış şutlar sayılmaz. Kayıp bölgeleri topu **kaybeden takımın hücum yönünde** hesaplanır, topu yeni kazananın yönünde değil. 8×8 m tekrar ölçüsü senaryo içinde, yalnızca aynı kazanım cohort'unun gerçek duel/interception/opponent-control bitiş konumları üzerindendir. Başka episode kökenleri (başlangıçta ileri bölgede olanlar, restartlar) bu cohort'a eklenmez. Nitelikli hücum sayıları farklılaştığından, mutlak sonlanma sayıları bir nedensel başarı oranı değildir. Taktiklerin güçlü / zayıf olduğu veya uzun dönem sezon dengesi ispatlanmış değildir.

## Yeniden üretim ve otomatik güvence

- \`node tools/profile-current-attack-chain.cjs\`: dört doğal 120 sn koşuyu, gerçek kararları değiştirmeyen gözlemciyle ölçer. Ayrıntılı rapor \`docs/validation/current-attack-120s.json\` dosyasına üretilir ve GitHub Actions'a eklenir.
- \`node --test tests/attack-breakpoint.test.cjs\`: iki hücum yönünde güvenli ilerleme, riskli/ulaşılamayan paslarda eski temkin ve daha düşük sıralı ama yapılabilir pas seçimini doğrulayan altı test.
- Önceki kaynak: \`football-sim.js\` SHA-256 \`593d6e80f3d4eadbe85f8969d3778773be617c4b3c0fdf65825125b3c62551ba\`, [eski gözlemler](https://github.com/tolgagitmez/tribunmenager/actions/runs/44943962011).
- Yeni kaynak: \`football-sim.js\` SHA-256 \`96095c09e135f7553c715156c82b9de134dc80d90ecb6aab93c4439b591a45b3\`, [güncel gözlemler](https://github.com/tolgagitmez/tribunmenager/actions/runs/44944193508).

**Yorum:** Bu veri belirli örnekte oynanabilir bir pası bekletmenin kopuşa katkıda bulunduğunu destekler. Kanıt sadece sabit dört kısa maç ve belirli bir köken cohoutu içindir; sonraki deney daha çok tohum, farklı takım güçleri ve uzun maçlarda kutu girişleri ile aynı bölgede yinelenen kayıpları ayrı ölçmelidir.
