"""Instrument the pinned native Match, not the clock-only unit test."""
import pathlib
import sys

HEADER = r'''
// Tribun Manager modification: opt-in native match trace, Apache-2.0 upstream.
#include <cstdlib>
#include <locale>
#include <iomanip>
#include <map>
#include <cmath>
#include <algorithm>

namespace {
void TribunTrace(Match& match, bool done) {
  const char* path = std::getenv("TRIBUN_LEAGUE_SOCCER_TRACE");
  if (!path || !*path) return;
  static std::ofstream output(path, std::ios::out | std::ios::trunc);
  static bool started = false;
  static bool finished = false;
  static unsigned long last = 0;
  if (!output || finished) return;
  const auto now = match.GetActualTime_ms();
  // Record participation at native 10 ms resolution, not render-frame rate.
  struct Participation {
    unsigned long nominalMs = 0, activeMs = 0, sprintMs = 0;
    bool wasActive = false, wasSprinting = false;
  };
  static std::map<int, Participation> participation;
  static unsigned long previousActual = 0, previousMatch = 0;
  static int previousPeriod = 0;
  static bool havePrevious = false;
  const int period = static_cast<int>(match.GetMatchPhase());
  const auto matchMs = match.GetMatchTime_ms();
  const auto nominal = [](unsigned long value, int phase) -> unsigned long {
    if (phase == static_cast<int>(e_MatchPhase_1stHalf)) return std::min(value, 2700000UL);
    if (phase == static_cast<int>(e_MatchPhase_2ndHalf)) return std::min(std::max(value, 2700000UL), 5400000UL);
    return 0;
  };
  const bool samePeriod = havePrevious && period == previousPeriod &&
      (period == static_cast<int>(e_MatchPhase_1stHalf) || period == static_cast<int>(e_MatchPhase_2ndHalf));
  const auto before = nominal(previousMatch, previousPeriod), after = nominal(matchMs, period);
  const unsigned long clockDelta = samePeriod && after >= before ? after - before : 0;
  const unsigned long actualDelta = havePrevious && now >= previousActual ? now - previousActual : 0;
  for (int team = 0; team < 2; ++team) {
    std::vector<Player*> players;
    match.GetAllTeamPlayers(team, players);
    for (auto* player : players) {
      auto& row = participation[player->GetID()];
      if (row.wasActive && clockDelta > 0 && actualDelta <= 100) {
        row.nominalMs += clockDelta;
        row.activeMs += actualDelta;
        if (row.wasSprinting) row.sprintMs += actualDelta;
      }
      row.wasActive = player->IsActive();
      row.wasSprinting = false;
      if (row.wasActive) {
        const auto movement = player->GetMovement();
        row.wasSprinting = std::hypot(movement.coords[0], movement.coords[1]) >= 6.0f;
      }
    }
  }
  previousActual = now;
  previousMatch = matchMs;
  previousPeriod = period;
  havePrevious = true;
  if (started && !done && now < last + 100) return;
  started = true;
  last = now;
  finished = done;
  output.imbue(std::locale::classic());
  output << std::setprecision(9);
  const auto vec = [&](const Vector3& v) {
    output << '[' << v.coords[0] << ',' << v.coords[1] << ',' << v.coords[2] << ']';
  };
  output << "{\"schema\":1,\"engine\":\"league-soccer\",\"elapsedMs\":" << now
         << ",\"matchMs\":" << match.GetMatchTime_ms()
         << ",\"done\":" << (done ? "true" : "false")
         << ",\"score\":[" << match.GetScore(0) << ',' << match.GetScore(1)
         << "],\"ball\":";
  vec(match.GetBall()->Predict(0));
  output << ",\"ballVelocity\":";
  vec(match.GetBall()->GetMovement());
  const auto data = match.GetMatchData();
  output << ",\"stats\":{\"shots\":[" << data->GetShots(0) << ',' << data->GetShots(1)
         << "],\"onTarget\":[" << data->GetShotsOnTarget(0) << ',' << data->GetShotsOnTarget(1)
         << "],\"passes\":[" << data->GetPassAttempts(0) << ',' << data->GetPassAttempts(1)
         << "],\"completed\":[" << data->GetPassesCompleted(0) << ',' << data->GetPassesCompleted(1)
         << "],\"fouls\":[" << data->GetFouls(0) << ',' << data->GetFouls(1)
         << "],\"possessionMs\":[" << data->GetPossessionTime_ms(0) << ',' << data->GetPossessionTime_ms(1) << "]}";
  output << ",\"inPlay\":" << (match.IsInPlay() && !match.IsInSetPiece() ? "true" : "false")
         << ",\"attackDirection\":[" << -match.GetTeam(0)->GetSide() << ',' << -match.GetTeam(1)->GetSide() << ']';
  output << ",\"players\":[";
  bool first = true;
  for (int team = 0; team < 2; ++team) {
    std::vector<Player*> players;
    match.GetActiveTeamPlayers(team, players);
    for (auto* player : players) {
      if (!first) output << ',';
      first = false;
      output << "{\"id\":" << player->GetID() << ",\"team\":" << team << ",\"databaseId\":" << player->GetPlayerData()->GetDatabaseID() << ",\"position\":";
      vec(player->GetPosition());
      output << ",\"velocity\":";
      vec(player->GetMovement());
      output << ",\"direction\":";
      vec(player->GetDirectionVec());
      output << ",\"goalkeeper\":" << (player->GetFormationEntry().role == e_PlayerRole_GK ? "true" : "false");
      output << ",\"uniquePossession\":" << (player->HasUniquePossession() ? "true" : "false");
      output << '}';
    }
  }
  output << "],\"participation\":[";
  first = true;
  for (int team = 0; team < 2; ++team) {
    std::vector<Player*> players;
    match.GetAllTeamPlayers(team, players);
    for (auto* player : players) {
      if (!first) output << ',';
      first = false;
      const auto& row = participation[player->GetID()];
      output << "{\"databaseId\":" << player->GetPlayerData()->GetDatabaseID()
             << ",\"team\":" << team << ",\"active\":" << (player->IsActive() ? "true" : "false")
             << ",\"cardCode\":" << player->GetCards()
             << ",\"nominalMs\":" << row.nominalMs << ",\"activeMs\":" << row.activeMs
             << ",\"sprintMs\":" << row.sprintMs
             << ",\"fatigueFactor\":" << player->GetFatigueFactorInv() << '}';
    }
  }
  output << "]}" << std::endl;
}
}
'''

def replace_once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit(f"Unexpected upstream layout: {old!r}")
    return text.replace(old, new, 1)

def main():
    from fixture_patch import apply
    from short_match_patch import apply as apply_short_match
    apply(sys.argv[1])
    apply_short_match(sys.argv[1])
    path = pathlib.Path(sys.argv[1]) / "src/onthepitch/match.cpp"
    text = path.read_text(encoding="utf-8")
    if "void TribunTrace(" in text:
        return
    anchor = "const unsigned int replaySize_ms = 10000;"
    text = replace_once(text, anchor, HEADER + "\n" + anchor)
    anchor = "  // Tell the game page once; the full-time screen used to be re-created"
    text = replace_once(text, anchor, "  TribunTrace(*this, gameOver);\n\n" + anchor)
    path.write_text(text, encoding="utf-8")

if __name__ == "__main__":
    main()
