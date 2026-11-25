"""Opt-in seeded RNG and conservative short-match attack tuning."""
from pathlib import Path
from instrument import replace_once

def edit(root, name, replacements):
    p = Path(root) / name
    text = p.read_text(encoding="utf-8")
    for old, new in replacements:
        text = replace_once(text, old, new)
    p.write_text(text, encoding="utf-8")

def apply(root):
    header = Path(root) / "src/base/math/bluntmath.hpp"
    if "randomseed(unsigned int seed)" in header.read_text(encoding="utf-8"):
        return
    edit(root, "src/base/math/bluntmath.hpp", [
        ("void randomseed();", "void randomseed();\nvoid randomseed(unsigned int seed);"),
        ("inline void fastrandomseed() {", "inline void fastrandomseed(unsigned int seed) {\n  fastrandseed = seed;\n  max_uint = std::numeric_limits<unsigned int>::max();\n}\n\ninline void fastrandomseed() {"),
    ])
    edit(root, "src/base/math/bluntmath.cpp", [
        ("void randomseed() {", "void randomseed(unsigned int seed) {\n  rng_engine.seed(seed);\n  rng_dist.reset();\n}\n\nvoid randomseed() {"),
    ])
    edit(root, "src/main.cpp", [
        ("#include <cstdlib>", "#include <cstdlib>\n#include <cstdint>\n#include <stdexcept>"),
        ("  srand(time(nullptr));\n  rand();        // mingw32? buggy compiler? first value seems bogus\n  randomseed();  // for the boost random\n  fastrandomseed();", r'''  // Tribun Manager: optional reproducible initial random streams.
  if (const char* raw = std::getenv("TRIBUN_LEAGUE_SOCCER_SEED")) {
    std::string value(raw);
    if (value.empty() || value.find_first_not_of("0123456789") != std::string::npos)
      throw std::runtime_error("Invalid Tribun seed");
    const auto n = std::stoull(value);
    if (n > UINT32_MAX) throw std::runtime_error("Tribun seed out of range");
    const auto seed = static_cast<unsigned int>(n);
    srand(seed);
    rand();
    randomseed(seed);
    fastrandomseed(seed);
    printf("[tribun] initial RNG seed: %u\n", seed);
  } else {
    srand(time(nullptr));
    rand();
    randomseed();
    fastrandomseed();
  }'''),
    ])
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("#include <algorithm>", "#include <algorithm>\n#include <cstdlib>\n#include <cstring>"),
        ("namespace AITactics {", r'''namespace AITactics {
// Tribun Manager: experimental, opt-in 5-minute attack profile.
// No default behavior changes; never bypass shot angle, pass safety or offside.
inline bool ShortMatchAttackEnabled() {
  static const bool enabled = [] {
    const char* mode = std::getenv("TRIBUN_LEAGUE_SOCCER_ATTACK");
    return mode && std::strcmp(mode, "short-match") == 0;
  }();
  return enabled;
}
inline float ShotOddsThreshold() {
  return ShortMatchAttackEnabled() ? 0.50f : 0.55f;
}
'''),
        ("return 0.62f - ClampSetting(counterAttack) * 0.24f;", "return (ShortMatchAttackEnabled() ? 0.56f : 0.62f) - ClampSetting(counterAttack) * 0.24f;"),
        ("return 2800U + static_cast<unsigned int>(ClampSetting(counterAttack) * 2200.0f);", "return (ShortMatchAttackEnabled() ? 3100U : 2800U) + static_cast<unsigned int>(ClampSetting(counterAttack) * 2200.0f);"),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("if (odds + random(0.0f, 0.28f) > 0.55f) {", "if (odds + random(0.0f, 0.28f) > AITactics::ShotOddsThreshold()) {"),
        ("float forwardWeight = 2.0f + AI_GetMindSet(CastPlayer()->GetDynamicFormationEntry().role) * 5.0f;", "float forwardWeight = (AITactics::ShortMatchAttackEnabled() ? 2.5f : 2.0f) + AI_GetMindSet(CastPlayer()->GetDynamicFormationEntry().role) * 5.0f;"),
    ])
