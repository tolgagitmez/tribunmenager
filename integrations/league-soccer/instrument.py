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
#include <sstream>
#include <fstream>
#include <string>

namespace {
// Assign only active outfield players, keeping the goalkeeper and physical positions.
bool TribunApplyFormation(Team* target, int formation) {
  if (!formation) return true;
  struct Slot { e_PlayerRole role; float x,y; };
  static const Slot f433[] = {
    {e_PlayerRole_LB,-24,23},{e_PlayerRole_CB,-28,8},{e_PlayerRole_CB,-28,-8},{e_PlayerRole_RB,-24,-23},
    {e_PlayerRole_CM,-2,15},{e_PlayerRole_DM,-8,0},{e_PlayerRole_CM,-2,-15},
    {e_PlayerRole_CF,23,22},{e_PlayerRole_CF,28,0},{e_PlayerRole_CF,23,-22}};
  static const Slot f442[] = {
    {e_PlayerRole_LB,-25,23},{e_PlayerRole_CB,-28,8},{e_PlayerRole_CB,-28,-8},{e_PlayerRole_RB,-25,-23},
    {e_PlayerRole_LM,-1,23},{e_PlayerRole_CM,-5,8},{e_PlayerRole_CM,-5,-8},{e_PlayerRole_RM,-1,-23},
    {e_PlayerRole_CF,25,8},{e_PlayerRole_CF,25,-8}};
  static const Slot f4231[] = {
    {e_PlayerRole_LB,-25,23},{e_PlayerRole_CB,-28,8},{e_PlayerRole_CB,-28,-8},{e_PlayerRole_RB,-25,-23},
    {e_PlayerRole_DM,-9,9},{e_PlayerRole_DM,-9,-9},{e_PlayerRole_LM,13,22},{e_PlayerRole_AM,13,0},
    {e_PlayerRole_RM,13,-22},{e_PlayerRole_CF,27,0}};
  const Slot* slots=formation==433?f433:formation==442?f442:formation==4231?f4231:nullptr;
  if (!slots) return false;
  std::vector<Player*> active, field;
  target->GetActivePlayers(active);
  if (active.size()!=11) return false;
  for (auto* player:active) {
    if (player->GetCards()>=2) return false;
    if (player->GetFormationEntry().role!=e_PlayerRole_GK) field.push_back(player);
  }
  if (field.size()!=10) return false;
  // Minimum cost assignment via a 10-player bitmask DP, favor existing roles and nearby slots.
  const unsigned int total=1U<<10;
  float cost[total];
  int previous[total], chosen[total];
  std::fill(cost,cost+total,1e9f);
  cost[0]=0;
  for (unsigned int mask=0;mask<total-1;++mask) {
    unsigned int n=0;
    for (unsigned int bit=mask;bit;bit>>=1) n+=bit&1U;
    const auto old=field[n]->GetFormationEntry();
    for (unsigned int j=0;j<10;++j) if (!(mask&(1U<<j))) {
      const auto& s=slots[j];
      float dx=old.position.coords[0]-s.x/52.5f,dy=old.position.coords[1]-s.y/34.0f;
      float c=cost[mask]+dx*dx+dy*dy+(old.role==s.role?0.0f:0.35f);
      const unsigned int next=mask|(1U<<j);
      if(c<cost[next]){cost[next]=c;previous[next]=mask;chosen[next]=j;}
    }
  }
  int assignment[10];
  unsigned int mask=total-1;
  for(int n=9;n>=0;--n){assignment[n]=chosen[mask];mask=previous[mask];}
  for(int n=0;n<10;++n){
    auto entry=field[n]->GetFormationEntry();
    const auto& s=slots[assignment[n]];
    entry.role=s.role;
    entry.databasePosition=Vector3(s.x/52.5f,s.y/34.0f,0);
    entry.position=entry.databasePosition;
    target->SetFormationEntry(field[n]->GetID(),entry);
    field[n]->SetDynamicFormationEntry(entry);
  }
  return true;
}
struct TribunTacticAck {
  unsigned long revision=0, appliedMatchMs=0, appliedElapsedMs=0;
  int press=50, counter=50, support=50, width=50, tempo=50, formation=0;
};
TribunTacticAck tribunTactics[2];
void TribunApplyTactics(Match& match, bool done) {
  const char* directory=std::getenv("TRIBUN_LEAGUE_SOCCER_COMMAND_DIR");
  if (!directory || !*directory || done || match.GetPause()) return;
  auto phase=match.GetMatchPhase();
  if (phase!=e_MatchPhase_1stHalf && phase!=e_MatchPhase_2ndHalf) return;
  const auto now=match.GetActualTime_ms();
  static unsigned long lastPoll=0;
  if (now<lastPoll+200) return;
  lastPoll=now;
  if (!match.IsInPlay() || match.IsInSetPiece() || match.GetMatchTime_ms()>=5400000UL) return;
  for (int team=0; team<2; ++team) {
    Team* target=match.GetTeam(team);
    if (target->GetHumanGamerCount()) continue;
    std::ifstream input(std::string(directory)+"/team-"+std::to_string(team)+".txt");
    input.imbue(std::locale::classic());
    std::string magic, extra;
    long long revision, earliest;
    int press,counter,support,width,tempo=50,formation=0;
    if (!(input>>magic>>revision>>earliest>>press>>counter>>support>>width)) continue;
    if (magic=="TRIBUNTACTIC2") {
      if (!(input>>tempo>>formation)) continue;
    } else if (magic!="TRIBUNTACTIC1") continue;
    if (input>>extra) continue;
    const auto unit=[](int v){return v>=0&&v<=100;};
    auto& ack=tribunTactics[team];
    if (revision<=0 || revision>1000000 || static_cast<unsigned long>(revision)<=ack.revision ||
        earliest<0 || earliest>=5400000 || static_cast<unsigned long>(earliest)>match.GetMatchTime_ms() ||
        !unit(press)||!unit(counter)||!unit(support)||!unit(width)||!unit(tempo)) continue;
    if (!TribunApplyFormation(target,formation)) continue;
    auto& props=target->GetTeamData()->GetTacticsWritable().userProperties;
    props.Set("tribun_tempo",tempo/100.0f);
    props.Set("team_pressure",press/100.0f);
    props.Set("counter_attack",counter/100.0f);
    props.Set("support_distance",support/100.0f);
    props.Set("position_offense_width_factor",width/100.0f);
    props.Set("position_defense_width_factor",width/100.0f);
    target->GetController()->UpdateTactics();
    ack.revision=static_cast<unsigned long>(revision);
    ack.appliedMatchMs=match.GetMatchTime_ms();
    ack.appliedElapsedMs=now;
    ack.press=press;ack.counter=counter;ack.support=support;ack.width=width;ack.tempo=tempo;
    if(formation)ack.formation=formation;
    printf("[tribun] Live tactics team=%d revision=%lu minute=%lu\n",team,ack.revision,ack.appliedMatchMs/60000);
  }
}
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
  // Exact first-clock and phase-boundary frames must not be lost to 100 ms sampling.
  const auto& fixed=match.GetTribunFixedClock();
  const bool boundary=AITactics::FixedDurationEnabled() && fixed.started &&
      (now==fixed.start || now-fixed.start==150000UL);
  if (started && !done && !boundary && now < last + 100) return;
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
  output << ",\"phaseCode\":" << static_cast<int>(match.GetMatchPhase())
         << ",\"setPiece\":" << (match.IsInSetPiece() ? "true" : "false")
         << ",\"inPlay\":" << (match.IsInPlay() && !match.IsInSetPiece() ? "true" : "false")
         << ",\"attackDirection\":[" << -match.GetTeam(0)->GetSide() << ',' << -match.GetTeam(1)->GetSide() << ']';
  if(AITactics::FixedDurationEnabled()){
    const auto& c=match.GetTribunFixedClock();
    output << ",\"fixedClock\":{\"started\":" << (c.started?"true":"false")
           << ",\"startMs\":" << c.start << ",\"elapsedMs\":" << c.Elapsed(now)
           << ",\"half\":" << (c.half?"true":"false") << ",\"finished\":" << (c.finished?"true":"false") << '}';
  }
  output << ",\"humanGamers\":[" << match.GetTeam(0)->GetHumanGamerCount() << ',' << match.GetTeam(1)->GetHumanGamerCount() << ']';
  output << ",\"combinations\":[";
  for (int t=0;t<2;++t) {
    if(t)output << ',';
    const auto& c=match.GetTeam(t)->GetController()->GetTribunCombination();
    output << "{\"attempts\":" << c.attempts << ",\"returned\":" << c.returned
           << ",\"completed\":" << c.completed << '}';
  }
  output << ']';
  output << ",\"rebounds\":[";
  for (int t=0;t<2;++t) {
    if(t)output << ',';
    const auto& r=match.GetTeam(t)->GetController()->GetTribunRebound();
    output << "{\"deflections\":" << r.deflections << ",\"recoveries\":" << r.recoveries
           << ",\"followupShots\":" << r.followupShots << '}';
  }
  output << ']';
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
      const auto base = player->GetFormationEntry();
      output << ",\"formationRole\":" << static_cast<int>(base.role)
             << ",\"formationTarget\":";
      vec(base.position);
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
  output << "],\"managerTactics\":[";
  for (int t=0;t<2;++t) {
    if (t) output << ',';
    const auto& ack=tribunTactics[t];
    output << "{\"team\":" << t << ",\"revision\":" << ack.revision
           << ",\"appliedMatchMs\":" << ack.appliedMatchMs << ",\"appliedElapsedMs\":" << ack.appliedElapsedMs
           << ",\"press\":" << ack.press << ",\"counter\":" << ack.counter
           << ",\"support\":" << ack.support << ",\"width\":" << ack.width
           << ",\"tempo\":" << ack.tempo << ",\"formation\":" << ack.formation << '}';
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
    text = replace_once(text, anchor, "  TribunApplyTactics(*this, gameOver);\n  TribunTrace(*this, gameOver);\n\n" + anchor)
    path.write_text(text, encoding="utf-8")

if __name__ == "__main__":
    main()
