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
    edit(root, "src/data/teamdata.hpp", "  void SaveLineup();", "  // Tribun Manager modification: pilot-only fixture override.\n  void LoadTribunFixture(std::istream& input, int expectedTeam);\n  std::vector<std::pair<int,int>> tribunSubstitutions;\n  void SaveLineup();")
    edit(root, "src/data/playerdata.hpp", "  float GetStat(const char* name);", "  float GetStat(const char* name);\n  // Tribun Manager modification: import already-effective attributes.\n  void SetTribunStat(const char* name, float value) { stats.Set(name, value); }")
    edit(root, "src/data/teamdata.cpp", "#include <algorithm>", "#include <algorithm>\n#include <iomanip>\n#include <istream>\n#include <stdexcept>\n#include <cmath>")
    method = r'''
// Tribun Manager modification: replace database starters with the frozen fixture.
void TeamData::LoadTribunFixture(std::istream& input, int expectedTeam) {
  const auto require = [](bool ok) { if (!ok) throw std::runtime_error("Invalid Tribun fixture"); };
  const auto unit = [](float v) { return std::isfinite(v) && v >= 0.0f && v <= 1.0f; };
  int team, bench, changes;
  float press, counter, distance;
  require(bool(input >> team >> press >> counter >> distance >> bench >> changes) && team == expectedTeam &&
          bench >= 0 && bench <= 7 && changes >= 0 && changes <= 5 && changes <= bench &&
          unit(press) && unit(counter) && unit(distance));
  tactics.userProperties.Set("team_pressure", press);
  tactics.userProperties.Set("counter_attack", counter);
  tactics.userProperties.Set("support_distance", distance);
  const char* keys[] = {STAT_KEYS_PLACEHOLDER};
  std::vector<std::unique_ptr<PlayerData>> selected;
  bool seen[37] = {};
  for (int i = 0; i < playerNum + bench; ++i) {
    int id;
    std::string role, name;
    float x, y, rating;
    require(bool(input >> id >> role >> x >> y >> rating >> std::quoted(name)));
    const bool starter = i < playerNum;
    const bool validId = starter ? id > team*11 && id <= team*11+11 : id >= 23+team*7 && id < 23+team*7+7;
    require(validId && !seen[id] && !name.empty() &&
            std::isfinite(x) && std::abs(x) <= 1 && std::isfinite(y) && std::abs(y) <= 1 && unit(rating));
    seen[id] = true;
    require(role == "GK" || role == "CB" || role == "LB" || role == "RB" ||
            role == "DM" || role == "CM" || role == "AM" || role == "LM" || role == "RM" || role == "CF");
    require(!starter || (i == 0) == (role == "GK"));
    auto player = std::make_unique<PlayerData>(id, name, "", role, rating, 25);
    for (const char* key : keys) {
      float value;
      require(bool(input >> value) && unit(value));
      player->SetTribunStat(key, value);
    }
    player->SetCondition(e_PlayerCondition_Normal);
    selected.push_back(std::move(player));
    if (!starter) continue;
    FormationEntry entry = GetFormationEntry(i);
    entry.role = GetRoleFromString(role);
    entry.databasePosition = Vector3(x, y, 0);
    entry.position = entry.databasePosition;
    SetFormationEntry(i, entry);
  }
  tribunSubstitutions.clear();
  bool usedOut[37] = {}, usedIn[37] = {};
  for (int i=0; i<changes; ++i) {
    int out, in;
    require(bool(input >> out >> in) && out > team*11 && out <= team*11+11 && in >= 23+team*7 && in < 23+team*7+7 && seen[out] && seen[in] && !usedOut[out] && !usedIn[in]);
    usedOut[out] = usedIn[in] = true;
    tribunSubstitutions.emplace_back(out,in);
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
    if (!(input >> magic) || magic != "TRIBUN2") throw std::runtime_error("Invalid Tribun fixture header");
    teamData[0]->LoadTribunFixture(input, 0);
    teamData[1]->LoadTribunFixture(input, 1);
    if (input >> extra) throw std::runtime_error("Unexpected Tribun fixture data");
  }
'''
    anchor = "  teamData[1] = std::make_unique<TeamData>(team2DatabaseID);"
    edit(root, "src/data/matchdata.cpp", anchor, anchor + "\n" + hook)

    # Half-time only. Reuse the original starting slot and its role; do not reactivate a former player.
    edit(root, "src/onthepitch/team.hpp", "  void Exit();", "  void Exit();\n  Player* TribunSubstitute(int outID, int inID);")
    edit(root, "src/onthepitch/team.hpp", "  int activePlayerCount;", "  int activePlayerCount;\n  boost::intrusive_ptr<Node> tribunFullbodyNode;\n  std::map<Vector3, Vector3> tribunColorCoords;\n  std::map<int, FormationEntry> tribunFormerSlots;")
    edit(root, "src/onthepitch/team.cpp", "  activePlayerCount = playerNum;", "  activePlayerCount = playerNum;\n  if (!teamData->tribunSubstitutions.empty()) { tribunFullbodyNode = fullbodyNode; tribunColorCoords = colorCoords; }")
    method = r'''
// Tribun Manager: one-way substitution during the half-time dead ball.
Player* Team::TribunSubstitute(int outID, int inID) {
  if (!tribunFullbodyNode || GetHumanGamerCount() || match->IsInPlay()) return nullptr;
  int out = -1, in = -1;
  for (int i=0; i<static_cast<int>(players.size()); ++i) {
    int dbid = players[i]->GetPlayerData()->GetDatabaseID();
    if (dbid == outID) out=i;
    if (dbid == inID) in=i;
  }
  if (out < 0 || out >= playerNum || in < playerNum || !players[out]->IsActive() ||
      players[out]->GetCards() >= 2 || players[in]->IsActive() ||
      tribunFormerSlots.count(players[in]->GetID())) return nullptr;
  Player* leaving = players[out].get();
  Player* entering = players[in].get();
  if (match->GetBallRetainer() == leaving) return nullptr;
  FormationEntry entry = GetFormationEntry(leaving->GetID());
  tribunFormerSlots.emplace(leaving->GetID(),entry);
  std::string filename = entry.role == e_PlayerRole_GK ? "media/objects/players/textures/goalie_kit.png"
    : GetTeamData()->GetKitUrl() + "_kit_0" + int_to_str(kitNumber) + ".png";
  if (!std::filesystem::exists(filename))
    filename = GetID()==0 ? "media/textures/almost_white.png" : "media/textures/almost_black.png";
  auto nextKit = ResourceManagerPool::GetInstance().GetManager<Surface>(e_ResourceType_Surface)->Fetch(filename);
  leaving->Deactivate();
  teamData->SwitchPlayers(outID,inID);
  std::swap(players[out],players[in]);
  entering->Activate(playerNode,tribunFullbodyNode,tribunColorCoords,nextKit,match->GetAnimCollection());
  if (designatedTeamPossessionPlayer == leaving) designatedTeamPossessionPlayer=entering;
  printf("[tribun] Half-time substitution %d -> %d\n",outID,inID);
  return entering;
}
'''
    edit(root, "src/onthepitch/team.cpp", "signed int Team::GetSide() {", method + "\n signed int Team::GetSide() {")
    edit(root, "src/onthepitch/team.cpp", "FormationEntry Team::GetFormationEntry(int playerID) {", "FormationEntry Team::GetFormationEntry(int playerID) {\n  auto former=tribunFormerSlots.find(playerID);\n  if (former!=tribunFormerSlots.end()) return former->second;")
    # Match owns the global possession pointer. Replace it before the next AI step.
    anchor = "  matchTimeExact_ms = static_cast<double>(matchTime_ms);"
    hook = r'''
  if (newMatchPhase == e_MatchPhase_2ndHalf) {
    for (int t=0; t<2; ++t) {
      for (const auto& change : teams[t]->GetTeamData()->tribunSubstitutions) {
        Player* previous = designatedPossessionPlayer;
        Player* next = teams[t]->TribunSubstitute(change.first,change.second);
        if (next && previous && previous->GetPlayerData()->GetDatabaseID()==change.first)
          designatedPossessionPlayer=next;
      }
      teams[t]->GetTeamData()->tribunSubstitutions.clear();
    }
  }
'''
    edit(root, "src/onthepitch/match.cpp", anchor, anchor + "\n" + hook)
