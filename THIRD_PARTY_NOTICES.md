# Üçüncü taraf bileşenler

`vendor/three/` içindeki Three.js **0.180.0**, resmî npm paketinden değiştirilmeden alınmıştır. Lisansı **MIT**'dir; tam metin [vendor/three/LICENSE](vendor/three/LICENSE) dosyasındadır. Kaynak paket adresi, npm bütünlük kaydı ve her dağıtılan dosyanın SHA-256 değeri [manifestte](vendor/three/manifest.json) bulunur. Ana modüller, GLTFLoader, SkeletonUtils, BufferGeometryUtils ve OrbitControls yerel sunucudan yüklenir. `npm ci` sonrasında `node tools/vendor-three.cjs` aynı kopyaları üretir.

Khronos **glTF Validator 2.0.0-dev.3.10** Apache-2.0 lisanslı geliştirme aracıdır. Model doğrulama raporları üretir; oyunda yüklenmez. Kaynak ve lisans bilgisi `package-lock.json` ile npm paketinde yer alır.

MakeHuman kaynak verisi ve projeye ait karakter türevleri **CC0-1.0** kapsamındadır. Kaynak/lisans kayıtları [assets/player/CREDITS.md](assets/player/CREDITS.md) ve [interchange paketi](assets/interchange/CREDITS.md) içindedir. Blender ayrı kurulan GPL lisanslı araçtır; bu paket Blender programını dağıtmaz. Düzenlenebilir `.blend` ve model/animasyon çıktılarının kaynağı interchange belgelerinde açıklanır.
