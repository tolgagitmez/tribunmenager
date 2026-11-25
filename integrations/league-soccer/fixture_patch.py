"""Opt-in transfer of a frozen Tribun fixture into the actual upstream TeamData."""
from pathlib import Path
from instrument import replace_once

STAT_KEYS = ["physical_balance","physical_reaction","physical_acceleration","physical_velocity","physical_stamina","physical_agility","physical_shotpower","technical_standingtackle","technical_slidingtackle","technical_ballcontrol","technical_dribble","technical_shortpass","technical_highpass","technical_header","technical_shot","technical_volley","mental_calmness","mental_workrate","mental_resilience","mental_defensivepositioning","mental_offensivepositioning","mental_vision"]
def edit(root, name, anchor, replacement):
    p = Path(root) / name
    p.write_text(replace_once(p.read_text(encoding="utf-8"), anchor, replacement), encoding="utf-8")

def apply(root):
    header = Path(root) / "src/data/teamdata.hpp"
    if "LoadTribunFixture" in header.read_text(encoding="utf-8"):
        return
    edit(root, "src/data/teamdata.hpp", "#include <memory>", "#include <memory>\n#include <iosfwd>")
    edit(root, "src/data/teamdata.hpp", "  void SaveLineup();", "  // Tribun Manager modification: pilot-only fixture override.\n  void LoadTribunFixture(std::istream& input, int expectedTeam);\n  void SaveLineup();")
    edit(root, "src/data/playerdata.hpp", "  float GetStat(const char* name);", "  float GetStat(const char* name);\n  // Tribun Manager modification: import already-effective attributes.\n  void SetTribunStat(const char* name, float value) { stats.Set(name, value); }")
    edit(root, "src/data/teamdata.cpp", "#include <algorithm>", "#include <algorithm>\n#include <iomanip>\n#include <istream>\n#include <stdexcept>\n#include <cmath>")
    method = r'''
// Tribun Manager modification: replace database starters with the frozen fixture.
void TeamData::LoadTribunFixture(std::istream& input, int expectedTeam) {
  const auto require = [](bool ok) { if (!ok) throw std::runtime_error("Invalid Tribun fixture"); };
  const auto unit = [](float v) { return std::isfinite(v) && v >= 0.0f && v <= 1.0f; };
  int team;
  float press, counter, distance;
  require(bool(input >> team >> press >> counter >> distance) && team == expectedTeam &&
          unit(press) && unit(counter) && unit(distance));
  tactics.userProperties.Set("team_pressure", press);
  tactics.userProperties.Set("counter_attack", counter);
  tactics.userProperties.Set("support_distance", distance);
  const char* keys[] = {STAT_KEYS_PLACEHOLDER};
  std::vector<std::unique_ptr<PlayerData>> selected;
  bool seen[12] = {};
  for (int i = 0; i < playerNum; ++i) {
    int id;
    std::string role, name;
    float x, y, rating;
    require(bool(input >> id >> role >> x >> y >> rating >> std::quoted(name)));
    const int local = id - team * 11;
    require(local >= 1 && local <= 11 && !seen[local] && !name.empty() &&
            std::isfinite(x) && std::abs(x) <= 1 && std::isfinite(y) && std::abs(y) <= 1 && unit(rating));
    seen[local] = true;
    require(role == "GK" || role == "CB" || role == "LB" || role == "RB" ||
            role == "DM" || role == "CM" || role == "AM" || role == "LM" || role == "RM" || role == "CF");
    require((i == 0) == (role == "GK"));
    auto player = std::make_unique<PlayerData>(id, name, "", role, rating, 25);
    for (const char* key : keys) {
      float value;
      require(bool(input >> value) && unit(value));
      player->SetTribunStat(key, value);
    }
    player->SetCondition(e_PlayerCondition_Normal);
    selected.push_back(std::move(player));
    FormationEntry entry = GetFormationEntry(i);
    entry.role = GetRoleFromString(role);
    entry.databasePosition = Vector3(x, y, 0);
    entry.position = entry.databasePosition;
    SetFormationEntry(i, entry);
  }
  playerData.swap(selected);
  lockedPlayerDatabaseID = 0;
}
'''
    method = method.replace("STAT_KEYS_PLACEHOLDER", ", ".join('"' + k + '"' for k in STAT_KEYS))
    edit(root, "src/data/teamdata.cpp", "TeamData::~TeamData() {}", method + "\nTeamData::~TeamData() {}")
    edit(root, "src/data/matchdata.cpp", '#include "matchdata.hpp"', '#include "matchdata.hpp"\n#include <cstdlib>\n#include <fstream>\n#include <locale>\n#include <stdexcept>')
    hook = r'''
  // Tribun Manager modification: opt-in input; never change normal upstream matches.
  if (const char* path = std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE")) {
    std::ifstream input(path);
    input.imbue(std::locale::classic());
    std::string magic, extra;
    if (!(input >> magic) || magic != "TRIBUN1") throw std::runtime_error("Invalid Tribun fixture header");
    teamData[0]->LoadTribunFixture(input, 0);
    teamData[1]->LoadTribunFixture(input, 1);
    if (input >> extra) throw std::runtime_error("Unexpected Tribun fixture data");
  }
'''
    anchor = "  teamData[1] = std::make_unique<TeamData>(team2DatabaseID);"
    edit(root, "src/data/matchdata.cpp", anchor, anchor + "\n" + hook)
