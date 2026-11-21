# Tribün Manager 3D — uzman duran top fiziği

Bu çalışma, penaltı, frikik ve kornerde **AI ile menajerin seçtiği niyeti** (hedef yönü, güç, ayak temas noktası) **aynı fiziksel vuruş hesaplayıcısına** bağlar. Vuruşu oluşturan tek otorite gerçek 60 Hz maç motorundaki `Match.release()` fonksiyonudur. Görsel animasyon, gol şansı veya olay anlatımı sonucu sonradan değiştirmez.

## Kapsam

- **Penaltı:** `penalty` uzmanlığı, kullanılan ayak, kondisyon, enerji, beden dengesi, seçilen yön/güç ve temas yeri topun ilk hızına etki eder. Kaleci kararı, ayak çizgisi, tekrar ve çift dokunuş hâlâ mevcut hakem/fizik kurallarından geçer.
- **Frikik:** `freeKick` uzmanlığı doğrudan ya da dolaylı serbest vuruşta topun gerçek çıkış yönüne uygulanır. Baraj, hakem, dolaylı vuruş ve ofsayt kuralları değişmez.
- **Korner:** `corner` uzmanlığı aynı ayak teması üzerinden kullanılan orta/şut/pas türüne bakılmaksızın uygulanır. Köşe vuruşundan doğrudan ofsayt muafiyeti korunur.
- **Açık oyun:** Menajerin manuel olarak yönettiği kanat ortası önceki uzmanlık kontrollü `cross` yolunu kullanır. **Otomatik açık oyun ortaları**, daha önce doğrulanmış yüksek top, kafa vuruşu, göğüs kontrolü ve savunma uzaklaştırma fiziğini korumak için değiştirilmedi. Normal pas, şut ve uzun pas da eski fiziğini korur.

`specialistKickType(k)`, yalnızca gerçek `restartContext` içindeki `penalty`, `free-kick`, `corner` olaylarını otomatik uzman vuruşu olarak seçer. `automaticSpecialistControl`, AI'nın istediği yönü/gücü `managerKickTypes` aralığına dönüştürür. `specialistKickVelocity`, AI ve manuel vuruşlarda **aynı** hesaplama ve deterministik RNG kullanımını gerçekleştirir. Çıkan `vx,vy,vz,spin` doğrudan fiziksel top durumuna yazılır. Böylece sahaya yansımayan kozmetik beceri bonusu eklenmez.

## Tekrarlanabilir karşılaştırma

Aynı tohum, oyuncu, ilk 11 ve rakip; sadece seçili `penalty` / `freeKick` / `corner` becerisi **20 ↔ 94** olarak değiştirilir. `tools/compare-specialist-kicks.cjs` önce birleştirme öncesi `254b0c67041490f312fff9c8022ce186cf7e61a9` motorunu Git geçmişinden okuyup sabitler, sonra yeni motoru aynı deneyden geçirir. İlk fiziksel vuruş, topun ilk inişi ve kaleci tepkileri kaydedilir. Sonraki sıradan paslar **ilk duran topun yerine ölçülmez**.

| Otomatik vuruş | Beceri 20: yön sapması | Beceri 94: yön sapması |
| --- | ---: | ---: |
| Penaltı | 11,85° | 1,96° |
| Frikik | 1,01° | 0,16° |
| Korner | 11,40° | 1,75° |

Bu değerler **yalnızca aynı tohumlu kontrollü örneklerden** gelir; gerçek maç genelinde gol, isabet, serbest vuruş sıklığı ya da kurtarış oranı garantisi değildir. Kornerde ilk iniş, aynı örnekte 20 puan için yaklaşık **(37,82 m, −11,39 m)**; 94 puan için **(40,26 m, −5,67 m)** olur. Yüksek beceri belirli tek denemede her zaman gol demek değildir.

## Gerileme ve güvenlik doğrulaması

```bash
node --test tests/kick-skill-parity.test.cjs
node tools/compare-specialist-kicks.cjs
npm run test:manager-kick
node --test tests/attacking-coverage.test.cjs tests/aerial-keeper-law-boundaries.test.cjs
npm run test:live-match
node --test tests/fixture-watch-parity.test.cjs
npm run test:engine-invariance
npm run test:stage15
```

`.github/workflows/specialist-kick-current.yml`, gerçek menajer/AI kontrol eşitliği, iki taraftan canlı lig/worker, 21 kontrollü temas, hakem kanunları, animasyon-fizik değişmezliği ve tam geçmiş maç/karakter/glTF testlerini ayrı iş gruplarında izler. Oynanabilirliğin saha fiziği doğrulaması, gerçek cihazda 22 oyunculu FPS veya yeni Blender animasyon kalitesi iddiası taşımaz.
