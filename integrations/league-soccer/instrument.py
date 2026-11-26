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
  if (tribun_visual::deterministicProbe() && fixed.started) {
    const auto tick = fixed.Elapsed(now);
    if (!done && tick % 100UL != 0) return;
    if (tick == 0) {
      std::printf("[tribun-determinism] fixed-grid=100 visual-rng=isolated\n");
      std::fflush(stdout);
    }
  } else if (started && !done && !boundary && now < last + 100) return;
  started = true;
  last = now;
  finished = done;
  if(done) {
    std::printf("[tribun-linebreak] mode=%s candidates=%lu,%lu selected=%lu,%lu\n",
        AITactics::LineBreakEnabled()?"linebreak":"off",
        match.tribunLineBreakCandidates[0],match.tribunLineBreakCandidates[1],
        match.tribunLineBreakSelections[0],match.tribunLineBreakSelections[1]);
    std::fflush(stdout);
  }
  if (done && tribun_visual::collisionOnly()) {
    std::printf("[tribun-contact] interval-ms=%u updates=%lu max-age-ticks=%lu missing=%lu ball-overlaps=%lu keeper-overlaps=%lu tackle-overlaps=%lu controlled-requests=%lu\n",
      tribun_visual::contactIntervalTicks()*10,match.tribunPoseUpdates,match.tribunMaxPoseAgeTicks,
      match.tribunMissingPoseChecks,match.tribunBallOverlaps,match.tribunKeeperOverlaps,
      match.tribunTackleOverlaps,match.tribunControlledRequests);
    std::printf("[tribun-adaptive] mode=%s player-updates=%lu high=%lu medium=%lu low=%lu queries=%lu missing=%lu stale=%lu max-age=%lu\n",
      tribun_visual::adaptiveContact()?"adaptive":"uniform",match.tribunPlayerPoseUpdates,
      match.tribunHighPoseUpdates,match.tribunMediumPoseUpdates,match.tribunLowPoseUpdates,
      match.tribunContactQueries,match.tribunContactMissing,match.tribunContactStale,match.tribunContactMaxAge);
    std::printf("[tribun-impact] mode=%s legacy=%lu surface=%lu rejected=%lu regions=%lu,%lu,%lu,%lu,%lu,%lu before=%.6f after=%.6f energy-violations=%lu\n",
      tribun_visual::surfaceImpact()?"surface":"legacy",match.tribunLegacyImpacts,match.tribunSurfaceImpacts,match.tribunSeparatingRejected,
      match.tribunImpactRegions[0],match.tribunImpactRegions[1],match.tribunImpactRegions[2],match.tribunImpactRegions[3],match.tribunImpactRegions[4],match.tribunImpactRegions[5],
      match.tribunRelativeBefore,match.tribunRelativeAfter,match.tribunEnergyViolations);
    std::printf("[tribun-angular] mode=%s impacts=%lu changes=%lu before=%.6f after=%.6f max-delta=%.6f violations=%lu\n",
      tribun_visual::angularImpact()?"angular":"off",match.tribunAngularImpacts,match.tribunSpinChanges,
      match.tribunAngularEnergyBefore,match.tribunAngularEnergyAfter,match.tribunMaxSpinDelta,match.tribunAngularEnergyViolations);
    std::printf("[tribun-sweep] mode=%s tests=%lu hits=%lu applied=%lu through=%lu max-lead-ms=%.6f\n",
      tribun_visual::sweptImpact()?"swept":"off",match.tribunSweepTests,match.tribunSweepHits,
      match.tribunSweepApplied,match.tribunSweepThrough,match.tribunSweepMaxLeadMs);
    std::printf("[tribun-split] mode=%s queued=%lu applied=%lu cancelled=%lu before-ms=%.6f after-ms=%.6f\n",
      tribun_visual::splitImpact()?"split":"off",match.tribunSplitQueued,match.tribunSplitApplied,match.tribunSplitCancelled,
      match.tribunSplitBeforeMs,match.tribunSplitAfterMs);
    std::printf("[tribun-chain] mode=%s ticks=%lu extra=%lu rejected=%lu cap=%lu max=%lu last-ms=%.6f\n",
      tribun_visual::chainImpact()?"chain":"off",match.tribunChainTicks,match.tribunChainExtra,
      match.tribunChainRejected,match.tribunChainCap,match.tribunChainMax,match.tribunChainMaxTimeMs);
    std::printf("[tribun-limb] mode=%s samples=%lu queries=%lu used=%lu fallback=%lu max-relative=%.6f\n",
      tribun_visual::limbImpact()?"limb":"off",match.tribunLimbSamplesMeasured,match.tribunLimbQueries,
      match.tribunLimbUsed,match.tribunLimbFallback,match.tribunLimbMaxRelativeSpeed);
    std::fflush(stdout);
  }
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
  output << ",\"timedAttacks\":[";
  for(int t=0;t<2;++t){
    if(t)output << ',';
    const auto& a=match.GetTeam(t)->GetController()->GetTribunTimedAttack();
    output << "{\"passes\":" << a.passes << ",\"receipts\":" << a.receipts
           << ",\"shots\":" << a.shots << '}';
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

def suppress_draw_tasks(source):
    """Keep game Put, context, uploads and event pump; omit only frame drawing."""
    anchor = """  graphicsSequence->AddSystemTaskEntry(graphicsSystem, e_TaskPhase_Get);
  graphicsSequence->AddSystemTaskEntry(graphicsSystem, e_TaskPhase_Process);
  graphicsSequence->AddSystemTaskEntry(graphicsSystem, e_TaskPhase_Put);"""
    return replace_once(source, anchor, """  const char* tribunDraw = std::getenv("TRIBUN_NATIVE_NO_DRAW");
  const bool tribunNoDraw = tribunDraw && std::string(tribunDraw) == "1";
  if (!tribunNoDraw) {
    graphicsSequence->AddSystemTaskEntry(graphicsSystem, e_TaskPhase_Get);
    graphicsSequence->AddSystemTaskEntry(graphicsSystem, e_TaskPhase_Process);
    graphicsSequence->AddSystemTaskEntry(graphicsSystem, e_TaskPhase_Put);
  }
  printf("[tribun-render] scheduled-draw=%s\\n", tribunNoDraw ? "off" : "on");
  const char* tribunUpload = std::getenv("TRIBUN_NATIVE_NO_UPLOAD");
  printf("[tribun-render] geometry-upload=%s\\n", tribunNoDraw && tribunUpload && std::string(tribunUpload) == "1" ? "off" : "on");
  fflush(stdout);""")

def suppress_geometry_uploads(source):
    source = replace_once(source, '#include "gametask.hpp"',
                          '#include "gametask.hpp"\n#include <cstdlib>\n#include <string>')
    source = replace_once(source, "void GameTask::PutPhase() {", """void GameTask::PutPhase() {
  const char* draw = std::getenv("TRIBUN_NATIVE_NO_DRAW");
  const char* upload = std::getenv("TRIBUN_NATIVE_NO_UPLOAD");
  const bool tribunNoUpload = draw && std::string(draw) == "1" &&
                              upload && std::string(upload) == "1";""")
    source = replace_once(source, "    match->UploadGoalNetting();",
                          "    if (!tribunNoUpload) match->UploadGoalNetting();")
    return replace_once(source, """  if (match) {
    unsigned int playersPerThread = 7;""", """  if (match && !tribunNoUpload) {
    unsigned int playersPerThread = 7;""")

NULL_RENDERER_HEADER = r'''// Experimental Tribun backend; retains CPU-side simulation assets.
#pragma once
#include "interface_renderer3d.hpp"
#include "types/command.hpp"
#include <SDL2/SDL.h>
#include <SDL2/SDL_image.h>
#include <cstdio>
#include <string>
#include <type_traits>

namespace blunted {
class TribunNullRenderer3D final : public Renderer3D {
public:
  void SwapBuffers() override {}
  void SetMatrix(const std::string& shaderUniformName, const Matrix4& matrix) override {}
  void RenderOverlay2D(const std::vector<Overlay2DQueueEntry>& overlay2DQueue) override {}
  void RenderOverlay2D() override {}
  void RenderLights(std::deque<LightQueueEntry>& lightQueue, const Matrix4& projectionMatrix, const Matrix4& viewMatrix) override {}
  bool CreateContext(int width, int height, int bpp, bool fullscreen) override { w_=width; h_=height; bpp_=bpp;
    if (SDL_InitSubSystem(SDL_INIT_VIDEO) != 0) return false;
    video_=true;
    const char* driver=SDL_GetCurrentVideoDriver();
    if (!driver || std::string(driver)!="dummy") return false;
    const int flags=IMG_INIT_JPG | IMG_INIT_PNG;
    image_=true;
    if ((IMG_Init(flags)&flags)!=flags) return false;
    std::printf("[tribun-render] null-context=dummy-no-gl\n");
    std::fflush(stdout);
    return true; }
  void Exit() override { if (image_) { IMG_Quit(); image_=false; }
    if (video_) { SDL_QuitSubSystem(SDL_INIT_VIDEO); video_=false; } }
  int CreateView(float x_percent, float y_percent, float width_percent, float height_percent) override { View v{}; v.target=e_ViewRenderTarget_Context;
    v.x=static_cast<int>(x_percent*0.01*w_);
    v.y=static_cast<int>(y_percent*0.01*h_);
    v.width=static_cast<int>(width_percent*0.01*w_);
    v.height=static_cast<int>(height_percent*0.01*h_);
    views.push_back(v);
    return static_cast<int>(views.size()-1); }
  View& GetView(int viewID) override { return views.at(viewID); }
  void DeleteView(int viewID) override { views.at(viewID)=View{}; }
  void SetCullingMode(e_CullingMode cullingMode) override {}
  void SetBlendingMode(e_BlendingMode blendingMode) override {}
  void SetDepthFunction(e_DepthFunction depthFunction) override {}
  void SetDepthTesting(bool OnOff) override {}
  void SetDepthMask(bool OnOff) override {}
  void SetBlendingFunction(e_BlendingFunction blendingFunction1, e_BlendingFunction blendingFunction2) override {}
  void SetTextureMode(e_TextureMode textureMode) override {}
  void SetColor(const Vector3& color, float alpha) override {}
  void SetColorMask(bool r, bool g, bool b, bool alpha) override {}
  void ClearBuffer(const Vector3& color, bool clearDepth, bool clearColor) override {}
  Matrix4 CreatePerspectiveMatrix(float aspectRatio, float nearCap, float farCap) override { Matrix4 m; m.ConstructProjection(fov_, aspectRatio, nearCap==-1?0.1f:nearCap, farCap==-1?2000.0f:farCap); return m; }
  Matrix4 CreateOrthoMatrix(float left, float right, float bottom, float top, float nearCap, float farCap) override { Matrix4 m; m.ConstructOrtho(left,right,bottom,top,nearCap==-1?0.1f:nearCap,farCap==-1?2000.0f:farCap); return m; }
  VertexBufferID CreateVertexBuffer(float* vertices, unsigned int verticesDataSize, const std::vector<unsigned int>& indices, e_VertexBufferUsage usage) override { VertexBufferID id; id.bufferID=next_++; id.vertexArrayID=0; id.elementArrayID=0; return id; }
  void UpdateVertexBuffer(VertexBufferID vertexBufferID, float* vertices, unsigned int verticesDataSize) override {}
  void DeleteVertexBuffer(VertexBufferID vertexBufferID) override {}
  void RenderVertexBuffer(const std::deque<VertexBufferQueueEntry>& vertexBufferQueue, e_RenderMode renderMode) override {}
  void RenderAABB(std::list<VertexBufferQueueEntry>& vertexBufferQueue) override {}
  void RenderAABB(std::list<LightQueueEntry>& lightQueue) override {}
  void SetLight(const Vector3& position, const Vector3& color, float radius) override {}
  int CreateTexture(e_InternalPixelFormat internalPixelFormat, e_PixelFormat pixelFormat, int width, int height, bool alpha, bool repeat, bool mipmaps, bool filter, bool multisample, bool compareDepth) override { return next_++; }
  void ResizeTexture(int textureID, SDL_Surface* source, e_InternalPixelFormat internalPixelFormat, e_PixelFormat pixelFormat, bool alpha, bool mipmaps) override {}
  void UpdateTexture(int textureID, SDL_Surface* source, bool alpha, bool mipmaps) override {}
  void DeleteTexture(int textureID) override {}
  void CopyFrameBufferToTexture(int textureID, int width, int height) override {}
  void BindTexture(int textureID) override {}
  void SetTextureUnit(int textureUnit) override {}
  void SetClientTextureUnit(int textureUnit) override {}
  int CreateFrameBuffer() override { return next_++; }
  void DeleteFrameBuffer(int fbID) override {}
  void BindFrameBuffer(int fbID) override {}
  void SetFrameBufferRenderBuffer(e_TargetAttachment targetAttachment, int rbID) override {}
  void SetFrameBufferTexture2D(e_TargetAttachment targetAttachment, int texID) override {}
  bool CheckFrameBufferStatus() override { return true; }
  void SetFramebufferGammaCorrection(bool onOff) override {}
  int CreateRenderBuffer() override { return next_++; }
  void DeleteRenderBuffer(int rbID) override {}
  void BindRenderBuffer(int rbID) override {}
  void SetRenderBufferStorage(e_InternalPixelFormat internalPixelFormat, int width, int height) override {}
  void SetRenderTargets(const std::vector<e_TargetAttachment>& targetAttachments) override {}
  void SetFOV(float angle) override { fov_=angle; }
  void PushAttribute(int attr) override {}
  void PopAttribute() override {}
  void SetViewport(int x, int y, int width, int height) override {}
  void GetContextSize(int& width, int& height, int& bpp) override { width=w_; height=h_; bpp=bpp_; }
  void SetPolygonOffset(float scale, float bias) override {}
  void LoadShader(const std::string& name, const std::string& filename) override {}
  void UseShader(const std::string& name) override {}
  void SetUniformInt(const std::string& shaderName, const std::string& varName, int value) override {}
  void SetUniformFloat(const std::string& shaderName, const std::string& varName, float value) override {}
  void SetUniformFloat2(const std::string& shaderName, const std::string& varName, float value1, float value2) override {}
  void SetUniformFloat3(const std::string& shaderName, const std::string& varName, float value1, float value2, float value3) override {}
  void SetUniformFloat3Array(const std::string& shaderName, const std::string& varName, int count, float* values) override {}
  void SetUniformMatrix4(const std::string& shaderName, const std::string& varName, const Matrix4& mat) override {}
  void HDRCaptureOverallBrightness() override {}
  float HDRGetOverallBrightness() override { return 128.0f; }
  void operator()() override {
    while (true) {
      auto message=messageQueue.WaitForMessage();
      if (!message->Handle(this)) break;
    }
    Exit();
  }
private:
  int w_=0, h_=0, bpp_=0, next_=1;
  float fov_=45.0f;
  bool video_=false, image_=false;
};
static_assert(!std::is_abstract<TribunNullRenderer3D>::value, "Renderer interface must be fully implemented");
}
'''

def select_null_renderer(source):
    source = replace_once(source, '#include "graphics_system.hpp"',
                          '#include "graphics_system.hpp"\n#include "rendering/tribun_null_renderer.hpp"\n#include <cstdlib>\n#include <string>')
    return replace_once(source, '''  if (config.Get("graphics3d_renderer", "opengl") == "opengl")
    renderer3DTask = new OpenGLRenderer3D();''', '''  const char* nullBackend = std::getenv("TRIBUN_NATIVE_NULL_RENDERER");
  const char* noDraw = std::getenv("TRIBUN_NATIVE_NO_DRAW");
  const char* noUpload = std::getenv("TRIBUN_NATIVE_NO_UPLOAD");
  if (nullBackend && std::string(nullBackend) == "1") {
    if (!noDraw || std::string(noDraw) != "1" || !noUpload || std::string(noUpload) != "1")
      Log(e_FatalError, "GraphicsSystem", "Initialize", "Null backend requires isolated no-draw/no-upload mode");
    renderer3DTask = new TribunNullRenderer3D();
  } else if (config.Get("graphics3d_renderer", "opengl") == "opengl") {
    renderer3DTask = new OpenGLRenderer3D();
  }''')

def lightweight_match(source):
    """Omit optional scene assets, not animation collection, pitch RNG or excitement."""
    source = replace_once(source, '#include "match.hpp"',
                          '#include "match.hpp"\n#include <cstdlib>\n#include <cstdio>\n#include <string>')
    source = replace_once(source, "const float crowdGainUpdateThreshold = 0.001f;",
        """const float crowdGainUpdateThreshold = 0.001f;
static bool TribunLeanScene() {
  const char* lean = std::getenv("TRIBUN_NATIVE_LEAN_SCENE");
  const char* nullRenderer = std::getenv("TRIBUN_NATIVE_NULL_RENDERER");
  const char* draw = std::getenv("TRIBUN_NATIVE_NO_DRAW");
  const char* upload = std::getenv("TRIBUN_NATIVE_NO_UPLOAD");
  return lean && std::string(lean) == "1" &&
         nullRenderer && std::string(nullRenderer) == "1" &&
         draw && std::string(draw) == "1" && upload && std::string(upload) == "1";
}""")
    source = replace_once(source, "  if (!SuperDebug()) {\n    tmpStadiumNode",
                          "  if (!SuperDebug() && !TribunLeanScene()) {\n    tmpStadiumNode")
    source = replace_once(source, "  if (SuperDebug())\n    tmpStadiumNode",
                          "  if (SuperDebug() || TribunLeanScene())\n    tmpStadiumNode")
    source = replace_once(source, '  Log(e_Notice, "Match", "Match", "Loading crowd sounds");',
        '''  if (TribunLeanScene()) {
    std::printf("[tribun-lean] pitch-only=1 crowd-audio=0\\n");
    std::fflush(stdout);
  } else {
  Log(e_Notice, "Match", "Match", "Loading crowd sounds");''')
    source = replace_once(source, "  GetScene3D()->AddObject(crowd02);",
                          "  GetScene3D()->AddObject(crowd02);\n  }")
    source = replace_once(source, "  scene3D->DeleteObject(crowd01);\n  scene3D->DeleteObject(crowd02);",
                          "  if (crowd01) scene3D->DeleteObject(crowd01);\n  if (crowd02) scene3D->DeleteObject(crowd02);")
    # Retain excitement and event-decay updates before omitting audio gain handling.
    source = replace_once(source, "  const float effectiveExcitement = clamp(excitement + excitementEventBoost, 0.0f, 1.0f);",
                          "  if (TribunLeanScene()) return;\n  const float effectiveExcitement = clamp(excitement + excitementEventBoost, 0.0f, 1.0f);")
    return source

def lightweight_audio(source):
    source = replace_once(source, '#include "audio_system.hpp"',
                          '#include "audio_system.hpp"\n#include <cstdlib>\n#include <string>')
    source = replace_once(source, "const std::string requestedRenderer = config.Get(",
                          "std::string requestedRenderer = config.Get(")
    return replace_once(source, '''  );

#ifdef GF_USE_OPENAL
  if (requestedRenderer == "openal") {''', '''  );
  const char* lean = std::getenv("TRIBUN_NATIVE_LEAN_SCENE");
  const char* nullRenderer = std::getenv("TRIBUN_NATIVE_NULL_RENDERER");
  const char* draw = std::getenv("TRIBUN_NATIVE_NO_DRAW");
  const char* upload = std::getenv("TRIBUN_NATIVE_NO_UPLOAD");
  if (lean && std::string(lean) == "1" && nullRenderer &&
      std::string(nullRenderer) == "1" && draw && std::string(draw) == "1" &&
      upload && std::string(upload) == "1") {
    requestedRenderer = "null";
    Log(e_Notice, "AudioSystem", "Initialize", "[tribun-lean] audio-backend=null");
  }

#ifdef GF_USE_OPENAL
  if (requestedRenderer == "openal") {''')

VISUAL_RNG_HEADER = r'''#pragma once
#include <cstdint>
#include <cstdlib>
#include <cstring>

namespace tribun_visual {
inline bool flag(const char* key) {
  const char* value=std::getenv(key);
  return value && std::strcmp(value,"1")==0;
}
inline bool deterministicProbe() {
  return flag("TRIBUN_NATIVE_DETERMINISM") && flag("TRIBUN_NATIVE_FIXED_DURATION") &&
         flag("TRIBUN_NATIVE_NULL_RENDERER") && flag("TRIBUN_NATIVE_NO_DRAW") && flag("TRIBUN_NATIVE_NO_UPLOAD");
}
inline bool orderedPose() { return deterministicProbe() && flag("TRIBUN_NATIVE_ORDERED_POSE"); }
inline bool collisionOnly() { return orderedPose() && flag("TRIBUN_NATIVE_COLLISION_POSE"); }
inline bool adaptiveContact() { return collisionOnly() && flag("TRIBUN_NATIVE_ADAPTIVE_CONTACT"); }
inline bool surfaceImpact() { return collisionOnly() && flag("TRIBUN_NATIVE_SURFACE_IMPACT"); }
inline bool angularImpact() { return surfaceImpact() && flag("TRIBUN_NATIVE_ANGULAR_IMPACT"); }
inline bool sweptImpact() { return angularImpact() && flag("TRIBUN_NATIVE_SWEPT_IMPACT"); }
inline bool splitImpact() { return sweptImpact() && flag("TRIBUN_NATIVE_SPLIT_IMPACT"); }
inline bool chainImpact() { return splitImpact() && flag("TRIBUN_NATIVE_CHAIN_IMPACT"); }
inline bool limbImpact() { return chainImpact() && flag("TRIBUN_NATIVE_LIMB_IMPACT"); }
inline unsigned adaptiveTicks(float predictedDistance,bool dangerousAction,bool closeOpponent) {
  if (dangerousAction || closeOpponent || predictedDistance <= 5.0f) return 1;
  if (predictedDistance <= 12.0f) return 2;
  return 10;
}
inline bool adaptiveDue(unsigned long now,unsigned long previous,unsigned interval) {
  return previous==0 || now<previous || now-previous>=interval;
}
inline unsigned collisionTicks(const char* raw) {
  if (!raw || std::strcmp(raw,"100")==0) return 10;
  if (std::strcmp(raw,"50")==0) return 5;
  if (std::strcmp(raw,"20")==0) return 2;
  if (std::strcmp(raw,"10")==0) return 1;
  return 0;
}
inline unsigned contactIntervalTicks() {
  static const unsigned ticks=collisionTicks(std::getenv("TRIBUN_NATIVE_CONTACT_INTERVAL_MS"));
  return ticks;
}
inline bool collisionPoseDue(unsigned long iteration) {
  const unsigned ticks=contactIntervalTicks();
  return ticks && iteration>=2 && (adaptiveContact() || iteration%ticks==0);
}
inline bool poseDue(unsigned long iteration) { return iteration > 0 && iteration % 10UL == 0; }
inline bool enabled() {
  return (flag("TRIBUN_NATIVE_VISUAL_RNG") || deterministicProbe()) && flag("TRIBUN_NATIVE_NULL_RENDERER") &&
         flag("TRIBUN_NATIVE_NO_DRAW") && flag("TRIBUN_NATIVE_NO_UPLOAD");
}
inline bool skipPitch() { return enabled() && flag("TRIBUN_NATIVE_SKIP_PITCH_TEXTURE"); }
inline std::uint32_t seed(std::uint32_t domain) {
  const char* raw=std::getenv("TRIBUN_LEAGUE_SOCCER_SEED");
  const auto base=raw ? static_cast<std::uint32_t>(std::strtoul(raw,nullptr,10)) : 2026u;
  std::uint32_t v=base ^ domain;
  v ^= v >> 16; v *= 0x7feb352du; v ^= v >> 15; v *= 0x846ca68bu; v ^= v >> 16;
  return v;
}
class Stream {
  std::uint32_t state_;
public:
  explicit Stream(std::uint32_t value):state_(value){}
  void reset(std::uint32_t value){state_=value;}
  std::uint32_t next(){state_=state_*1664525u+1013904223u; return state_;}
  float range(float lo,float hi){return lo+(hi-lo)*static_cast<float>(next()>>8)*(1.0f/16777216.0f);}
};
}
'''

def visual_pitch_rng(source):
    source = replace_once(source, '#include "proceduralpitch.hpp"',
                          '#include "proceduralpitch.hpp"\n#include "tribun_visual_rng.hpp"')
    source = replace_once(source, "float* perlinTex;",
        """static thread_local tribun_visual::Stream pitchVisual(0);
static float TribunPitchFast(float lo, float hi) {
  return tribun_visual::enabled() ? pitchVisual.range(lo,hi) : fastrandom(lo,hi);
}
float* perlinTex;""")
    # All fast-random consumers in this translation unit are visual pixel generation.
    old = "fastrandom(-1, 1)"
    if source.count(old) != 7: raise SystemExit("Unexpected pitch fast RNG sites")
    source = source.replace(old, "TribunPitchFast(-1, 1)")
    source = replace_once(source, "  signed int offsetW, offsetH;",
                          "  if (tribun_visual::enabled()) pitchVisual.reset(tribun_visual::seed(0x50495400u + i));\n  signed int offsetW, offsetH;")
    source = replace_once(source, "  int seed = static_cast<int>(time(nullptr));",
                          "  int seed = tribun_visual::enabled() ? static_cast<int>(tribun_visual::seed(0x5045524cu) & 0x3fffffffu) : static_cast<int>(time(nullptr));")
    source = replace_once(source, "  float grassNormalRepeatMultiplier = (random(0, 1) > 0.5f) ? 1.0f : 0.5f;",
        """  tribun_visual::Stream grassVisual(tribun_visual::seed(0x47524153u));
  float grassNormalRepeatMultiplier = ((tribun_visual::enabled() ? grassVisual.range(0,1) : random(0, 1)) > 0.5f) ? 1.0f : 0.5f;""")
    return source

def visual_perlin_header(source):
    source = replace_once(source, "#include <stdlib.h>",
                          '#include <stdlib.h>\n#include "../onthepitch/tribun_visual_rng.hpp"')
    return replace_once(source, "    int   mSeed;",
                          "    int   mSeed;\n    tribun_visual::Stream visualRng{0};")

def visual_perlin_source(source):
    if source.count("    srand(mSeed);") != 3 or source.count("rand() %") != 4:
        raise SystemExit("Unexpected Perlin RNG sites")
    source = source.replace("    srand(mSeed);",
        "    if (tribun_visual::enabled()) visualRng.reset(static_cast<std::uint32_t>(mSeed));\n    else srand(mSeed);")
    # Keep signed arithmetic in the noise table and leave legacy path untouched.
    return source.replace("rand() %", "(tribun_visual::enabled() ? static_cast<int>(visualRng.next() & 0x7fffffffu) : rand()) %")

def visual_match_rng(source):
    source = replace_once(source, '#include "match.hpp"',
                          '#include "match.hpp"\n#include "tribun_visual_rng.hpp"')
    anchor = "void Match::SetRandomSunParams() {"
    start = source.index(anchor)
    end = source.index("void Match::RandomizeAdboards(",start)
    section = source[start:end]
    if section.count("random(") != 6:raise SystemExit("Unexpected sunlight RNG sites")
    section = section.replace("random(", "sunRandom(")
    section = replace_once(section,anchor,anchor+"""
  static tribun_visual::Stream sunlight(tribun_visual::seed(0x53554e31u));
  auto sunRandom = [&](float lo,float hi) {
    return tribun_visual::enabled() ? sunlight.range(lo,hi) : random(lo,hi);
  };""")
    source=source[:start]+section+source[end:]
    source = replace_once(source, "  Vector3 shudder = Vector3(random(-0.1f, 0.1f), random(-0.1f, 0.1f), 0) *",
        """  static tribun_visual::Stream cameraVisual(tribun_visual::seed(0x43414d31u));
  auto cameraRandom = [&](float lo,float hi) {
    return tribun_visual::enabled() ? cameraVisual.range(lo,hi) : random(lo,hi);
  };
  Vector3 shudder = Vector3(cameraRandom(-0.1f, 0.1f), cameraRandom(-0.1f, 0.1f), 0) *""")
    source = replace_once(source, """  if (IsReleaseVersion()) {
    GeneratePitch(2048, 1024, 1024, 512, 2048, 1024);
  } else {
    GeneratePitch(1024, 512, 1024, 512, 2048, 1024);
  }""", """  if (tribun_visual::enabled()) {
    std::printf("[tribun-visual] rng=isolated pitch-texture=%s\\n", tribun_visual::skipPitch() ? "off" : "on");
    std::fflush(stdout);
  }
  if (!tribun_visual::skipPitch()) {
    if (IsReleaseVersion()) {
      GeneratePitch(2048, 1024, 1024, 512, 2048, 1024);
    } else {
      GeneratePitch(1024, 512, 1024, 512, 2048, 1024);
    }
  }""")
    source = replace_once(source, "  std::mt19937 adboardRandom(std::random_device{}());",
        """  std::mt19937 adboardRandom(tribun_visual::deterministicProbe() ?
      tribun_visual::seed(0x41444231u) : std::random_device{}());""")
    return source

WORKER_LIMIT_HEADER = r'''#pragma once
#include <algorithm>
#include <cstring>
#include <stdexcept>
namespace tribun_workers {
inline unsigned count(unsigned hardware,const char* limit,bool isolated) {
  const unsigned original=std::max(3u,hardware);
  if (!limit || std::strcmp(limit,"0")==0) return original;
  if (!isolated) throw std::invalid_argument("Worker limit requires isolated null backend");
  // Retain upstream minimum: scheduler tasks can wait on nested pose jobs.
  if (std::strcmp(limit,"3")==0) return std::min(original,3u);
  if (std::strcmp(limit,"4")==0) return std::min(original,4u);
  throw std::invalid_argument("Worker limit must be 0, 3 or 4");
}
}
'''

def limit_native_workers(source):
    source = replace_once(source, '#include "taskmanager.hpp"',
        '#include "taskmanager.hpp"\n#include "tribun_worker_limit.hpp"\n#include <cstdlib>\n#include <cstdio>\n#include <string>')
    return replace_once(source, """  int numthreads = std::thread::hardware_concurrency();
  if (numthreads < 3)
    numthreads = 3;  // todo: make minimum configurable""", """  const unsigned hardware = std::thread::hardware_concurrency();
  auto enabled = [](const char* key) {
    const char* value = std::getenv(key);
    return value && std::string(value) == "1";
  };
  const char* limit = std::getenv("TRIBUN_NATIVE_TASK_WORKERS");
  const bool isolated = enabled("TRIBUN_NATIVE_NULL_RENDERER") &&
                        enabled("TRIBUN_NATIVE_NO_DRAW") && enabled("TRIBUN_NATIVE_NO_UPLOAD") &&
                        enabled("TRIBUN_NATIVE_FIXED_DURATION");
  const int numthreads = static_cast<int>(tribun_workers::count(hardware,limit,isolated));
  if (isolated) {
    std::printf("[tribun-workers] hardware=%u pool=%d\\n", hardware, numthreads);
    std::fflush(stdout);
  }""")

SKINNING_CHANNEL_HEADER = r'''#pragma once
namespace tribun_skinning {
struct Channels {
  bool vertices;
  bool normals;
  bool tangents;
  bool bitangents;
};
inline Channels channels(bool isolated,bool requested,bool updateSrc) {
  const bool shading=!(isolated && requested && !updateSrc);
  return {true,shading,shading,shading};
}
}
'''

def optimize_skinning_channels(source):
    source = replace_once(source, '#include "humanoid.hpp"',
        '#include "humanoid.hpp"\n#include "tribun_skinning_channels.hpp"\n#include <cstdlib>\n#include <cstdio>\n#include <cstring>')
    return replace_once(source, """void HumanoidBase::UpdateFullbodyModel(bool updateSrc) {
  int uploadVertices = true;
  int uploadNormals = true;
  int uploadTangents = true;
  int uploadBitangents = true;""", """void HumanoidBase::UpdateFullbodyModel(bool updateSrc) {
  const auto enabled = [](const char* key) {
    const char* value = std::getenv(key);
    return value && std::strcmp(value, "1") == 0;
  };
  static const bool isolated = enabled("TRIBUN_NATIVE_NULL_RENDERER") &&
      enabled("TRIBUN_NATIVE_NO_DRAW") && enabled("TRIBUN_NATIVE_NO_UPLOAD") &&
      enabled("TRIBUN_NATIVE_FIXED_DURATION");
  static const bool requested = enabled("TRIBUN_NATIVE_POSITION_SKINNING");
  const auto channels = tribun_skinning::channels(isolated, requested, updateSrc);
  if (!updateSrc && isolated) {
    // C++11 local static initialization serializes this one-time diagnostic.
    static const bool reported = [] {
      std::printf("[tribun-skinning] runtime=%s bind-pose=full\\n", requested ? "position-only" : "full");
      std::fflush(stdout);
      return true;
    }();
    (void)reported;
  }
  const bool uploadVertices = channels.vertices;
  const bool uploadNormals = channels.normals;
  const bool uploadTangents = channels.tangents;
  const bool uploadBitangents = channels.bitangents;""")

def ordered_pose_main(source):
    source = replace_once(source, '#include "framework/scheduler.hpp"',
        '#include "framework/scheduler.hpp"\n#include "onthepitch/tribun_visual_rng.hpp"')
    source = replace_once(source, "  GetScheduler()->RegisterTaskSequence(gameSequence);",
        """  const bool orderedPose = tribun_visual::orderedPose();
  if (orderedPose) {
    if (timeStep_ms != 10 || config->GetInt("graphics3d_frametime_ms",0) != 100)
      throw std::runtime_error("Ordered pose requires 10 ms physics and 100 ms pose cadence");
    gameSequence->AddUserTaskEntry(gameTask, e_TaskPhase_Put);
    std::printf("[tribun-pose] schedule=ordered interval-ticks=10\\n");
    std::fflush(stdout);
  }
  GetScheduler()->RegisterTaskSequence(gameSequence);""")
    return replace_once(source, "  GetScheduler()->RegisterTaskSequence(graphicsSequence);",
        "  if (!orderedPose) GetScheduler()->RegisterTaskSequence(graphicsSequence);")

def ordered_pose_task(source):
    source = replace_once(source, '#include "gametask.hpp"',
        '#include "gametask.hpp"\n#include "onthepitch/tribun_visual_rng.hpp"')
    # PutPhase only: do not change lifetime locking in Action().
    start = source.index("void GameTask::PutPhase() {")
    prefix,body=source[:start],source[start:]
    body = replace_once(body, "  matchLifetimeMutex.lock();",
        """  matchLifetimeMutex.lock();
  if (tribun_visual::orderedPose() && match &&
      !tribun_visual::poseDue(match->GetIterations())) {
    matchLifetimeMutex.unlock();
    return;
  }""")
    return prefix+body

def ordered_pose_clock(source):
    source = replace_once(source, """  previousPutTime_ms =
      EnvironmentManager::GetInstance().GetTime_ms() - gameSequenceInfo.startTime_ms;""",
        """  previousPutTime_ms = tribun_visual::orderedPose() ? 0UL :
      EnvironmentManager::GetInstance().GetTime_ms() - gameSequenceInfo.startTime_ms;""")
    start=source.index("void Match::FetchPutBuffers() {")
    prefix,body=source[:start],source[start:]
    body=replace_once(body, """  unsigned long time_ms =
      EnvironmentManager::GetInstance().GetTime_ms() - gameSequenceInfo.startTime_ms;
  timeSincePreviousPut_ms = time_ms - GetPreviousPutTime_ms();""",
        """  unsigned long time_ms = tribun_visual::orderedPose() ?
      static_cast<unsigned long>(gameSequenceInfo.timesRan) * gameSequenceInfo.sequenceTime_ms :
      EnvironmentManager::GetInstance().GetTime_ms() - gameSequenceInfo.startTime_ms;
  timeSincePreviousPut_ms = time_ms - GetPreviousPutTime_ms();""")
    return prefix+body

def ordered_pose_initial_samples(source):
    source=replace_once(source, '#include "humanoid.hpp"',
        '#include "humanoid.hpp"\n#include "../../tribun_visual_rng.hpp"')
    start=source.index("void FillTemporalHumanoidNodes(")
    end=source.index("HumanoidBase::HumanoidBase(",start)
    body=source[start:end]
    old="EnvironmentManager::GetInstance().GetTime_ms()"
    if body.count(old)!=2:raise SystemExit("Unexpected humanoid temporal initialization")
    body=body.replace(old,"(tribun_visual::orderedPose() ? 0UL : EnvironmentManager::GetInstance().GetTime_ms())")
    return source[:start]+body+source[end:]

def isolate_ball_audio_rng(source):
    # Contact detection and impulse remain unchanged; only sound pitch varies.
    source=replace_once(source, '#include "ball.hpp"',
        '#include "ball.hpp"\n#include "tribun_visual_rng.hpp"')
    return replace_once(source, "    sound->SetPitch(0.9f + random(0.0f, 0.2f));",
        """    if (tribun_visual::deterministicProbe()) {
      tribun_visual::Stream soundRng(tribun_visual::seed(0x42414c4cu) ^
                                      static_cast<std::uint32_t>(match->GetActualTime_ms()));
      sound->SetPitch(0.9f + soundRng.range(0.0f,0.2f));
    } else {
      sound->SetPitch(0.9f + random(0.0f, 0.2f));
    }""")

def collision_pose_header(source):
    return replace_once(source,"  void Put();","  void Put();\n  void TribunUpdateCollisionPose();\n  unsigned long tribunPoseUpdates=0, tribunLastPoseIteration=0, tribunMaxPoseAgeTicks=0, tribunMissingPoseChecks=0;\n  unsigned long tribunBallOverlaps=0, tribunKeeperOverlaps=0, tribunTackleOverlaps=0, tribunControlledRequests=0;")

def collision_pose_match(source):
    return replace_once(source,"void Match::Put() {","""// Simulation-owned collision geometry, using the original humanoid animation path.
void Match::TribunUpdateCollisionPose() {
  if (GetIterations() < 2 || GetPause()) return;
  static const bool reported = [] {
    std::printf("[tribun-collision] pose=simulation visual-mesh=off local-hud=off\\n");
    std::fflush(stdout);
    return true;
  }();
  (void)reported;
  ++tribunPoseUpdates;\n  tribunLastPoseIteration=GetIterations();
  ball->Put();
  teams[0]->Put();
  teams[1]->Put();
  officials->Put();
  GetDynamicNode()->RecursiveUpdateSpatialData(e_SpatialDataType_Both);
  if(tribun_visual::limbImpact()) TribunCaptureLimbPose();
}

void Match::Put() {""")

def collision_pose_task(source):
    source=replace_once(source,"""    match->PreparePutBuffers();
    matchPutBufferMutex.unlock();""","""    match->PreparePutBuffers();
    if (tribun_visual::collisionOnly() &&
        tribun_visual::collisionPoseDue(match->GetIterations()) && !match->GetPause()) {
      match->FetchPutBuffers();
      match->TribunUpdateCollisionPose();
    }
    matchPutBufferMutex.unlock();""")
    start=source.index("void GameTask::PutPhase() {")
    prefix,body=source[:start],source[start:]
    body=replace_once(body,"""  if (match) {
    matchPutBufferMutex.lock();""","""  if (match && !tribun_visual::collisionOnly()) {
    matchPutBufferMutex.lock();""")
    return prefix+body

def contact_probe(source):
    source=replace_once(source,"void Match::CheckBallCollisions() {","""void Match::CheckBallCollisions() {
  if (tribun_visual::collisionOnly()) {
    if (!tribunPoseUpdates) ++tribunMissingPoseChecks;
    else {
      const unsigned long age=GetIterations()-tribunLastPoseIteration;
      tribunMaxPoseAgeTicks=std::max(tribunMaxPoseAgeTicks,age);
    }
  }""")
    source=replace_once(source,"          if (objAABB.Intersects((*victimIter)->GetAABB())) {",
        """          if (objAABB.Intersects((*victimIter)->GetAABB())) {
            if (tribun_visual::collisionOnly()) ++tribunTackleOverlaps;""")
    source=replace_once(source,"            if (objAABB.Intersects(ball->Predict(0), ballRadius)) {",
        """            if (objAABB.Intersects(ball->Predict(0), ballRadius)) {
              if (tribun_visual::collisionOnly()) {
                ++tribunBallOverlaps;
                if (players[i]->GetFormationEntry().role==e_PlayerRole_GK) ++tribunKeeperOverlaps;
              }""")
    return replace_once(source,"                players[i]->TriggerControlledBallCollision();",
        """                if (tribun_visual::collisionOnly()) ++tribunControlledRequests;
                players[i]->TriggerControlledBallCollision();""")

def adaptive_contact_header(source):
    source=replace_once(source,"#include <memory>","#include <memory>\n#include <map>")
    return replace_once(source,"  void TribunUpdateCollisionPose();",
        """  void TribunUpdateCollisionPose();
  void TribunObserveContactPose(Player* player);
  std::map<int,unsigned long> tribunPlayerPoseTick;
  unsigned long tribunPlayerPoseUpdates=0, tribunHighPoseUpdates=0, tribunMediumPoseUpdates=0, tribunLowPoseUpdates=0;
  unsigned long tribunContactQueries=0, tribunContactMissing=0, tribunContactStale=0, tribunContactMaxAge=0;""")

def adaptive_contact_match(source):
    source=replace_once(source,"void Match::TribunUpdateCollisionPose() {",
        """void Match::TribunObserveContactPose(Player* player) {
  if (!tribun_visual::collisionOnly()) return;
  ++tribunContactQueries;
  auto found=tribunPlayerPoseTick.find(player->GetID());
  if (found==tribunPlayerPoseTick.end() || found->second>GetIterations()) {
    ++tribunContactMissing;
    return;
  }
  const auto age=GetIterations()-found->second;
  tribunContactMaxAge=std::max(tribunContactMaxAge,age);
  if(age>1) ++tribunContactStale;
}

void Match::TribunUpdateCollisionPose() {""")
    start=source.index("void Match::TribunUpdateCollisionPose() {")
    end=source.index("void Match::Put() {",start)
    section=source[start:end]
    section=replace_once(section,"""  teams[0]->Put();
  teams[1]->Put();""","""  std::vector<Player*> active;
  GetActiveTeamPlayers(0,active);
  GetActiveTeamPlayers(1,active);
  const auto tick=GetIterations();
  // Query both teams in native order; no physics coefficients or RNG are changed.
  if (tribun_visual::adaptiveContact()) {
    std::map<int,unsigned long> next;
    const auto risky=[](Player* p) {
      const auto action=p->GetCurrentFunctionType();
      return action==e_FunctionType_Sliding || action==e_FunctionType_Interfere ||
             action==e_FunctionType_Deflect;
    };
    for (auto* player:active) {
      float nearest=1000.0f;
      for (int horizon=0;horizon<=200;horizon+=50) {
        const auto projected=player->GetPosition()+player->GetMovement()*(horizon*0.001f);
        nearest=std::min(nearest,(projected.Get2D()-ball->Predict(horizon).Get2D()).GetLength());
      }
      bool closeOpponent=false;
      for(auto* other:active) {
        if(other->GetTeam()!=player->GetTeam() &&
           (other->GetPosition()-player->GetPosition()).GetLength()<=3.5f) {
          closeOpponent=true;break;
        }
      }
      const unsigned interval=tribun_visual::adaptiveTicks(nearest,risky(player),closeOpponent);
      auto found=tribunPlayerPoseTick.find(player->GetID());
      const auto previous=found==tribunPlayerPoseTick.end()?0UL:found->second;
      if(tribun_visual::adaptiveDue(tick,previous,interval)) {
        player->Put();
        next[player->GetID()]=tick;
        ++tribunPlayerPoseUpdates;
        if(interval==1) ++tribunHighPoseUpdates;
        else if(interval==2) ++tribunMediumPoseUpdates;
        else ++tribunLowPoseUpdates;
      } else next[player->GetID()]=previous;
    }
    tribunPlayerPoseTick.swap(next);
  } else {
    teams[0]->Put();
    teams[1]->Put();
    tribunPlayerPoseTick.clear();
    for(auto* player:active) {
      tribunPlayerPoseTick[player->GetID()]=tick;
      ++tribunPlayerPoseUpdates;
    }
  }""")
    source=source[:start]+section+source[end:]
    source=replace_once(source,"    // iterate through all body parts of tackler",
        """    TribunObserveContactPose(p1);
    TribunObserveContactPose(p2);
    // iterate through all body parts of tackler""")
    return replace_once(source,"          players[i]->GetHumanoidNode()->GetObjects(e_ObjectType_Geometry, objectList);",
        """          TribunObserveContactPose(players[i]);
          players[i]->GetHumanoidNode()->GetObjects(e_ObjectType_Geometry, objectList);""")

IMPACT_HEADER = r'''#pragma once
#include <algorithm>
#include <cmath>
#include <string>
#include <vector>
namespace tribun_impact {
struct Vec { float x,y,z; };
inline Vec add(Vec a,Vec b){return {a.x+b.x,a.y+b.y,a.z+b.z};}
inline Vec sub(Vec a,Vec b){return {a.x-b.x,a.y-b.y,a.z-b.z};}
inline Vec mul(Vec a,float s){return {a.x*s,a.y*s,a.z*s};}
inline float dot(Vec a,Vec b){return a.x*b.x+a.y*b.y+a.z*b.z;}
inline Vec cross(Vec a,Vec b){return {a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x};}
inline float length(Vec a){return std::sqrt(dot(a,a));}
inline bool finite(Vec a){return std::isfinite(a.x)&&std::isfinite(a.y)&&std::isfinite(a.z);}
// Estimate translation of one collision body part from consecutive 10 ms samples.
struct LimbEstimate { Vec velocity; bool measured; };
inline LimbEstimate estimateLimb(Vec previous,Vec current,Vec root,unsigned long gap){
  if(gap!=1 || !finite(previous)||!finite(current)||!finite(root))return {root,false};
  const Vec v=mul(sub(current,previous),100.0f);
  if(!finite(v) || length(sub(v,root))>25.0f)return {root,false};
  return {v,true};
}
enum Region { Foot, Leg, Torso, Head, Arm, Other, RegionCount };
inline Region region(const std::string& name) {
  if(name.find("foot")!=std::string::npos || name.find("toe")!=std::string::npos)return Foot;
  if(name.find("leg")!=std::string::npos)return Leg;
  if(name.find("head")!=std::string::npos)return Head;
  if(name.find("arm")!=std::string::npos || name.find("hand")!=std::string::npos ||
     name.find("elbow")!=std::string::npos || name.find("shoulder")!=std::string::npos)return Arm;
  if(name.find("body")!=std::string::npos || name.find("middle")!=std::string::npos ||
     name.find("torso")!=std::string::npos || name.find("chest")!=std::string::npos)return Torso;
  return Other;
}
struct Material {float restitution,tangentRetention;};
inline Material material(Region r){
  switch(r){
    case Foot:return {0.48f,0.78f};
    case Leg:return {0.38f,0.80f};
    case Torso:return {0.25f,0.72f};
    case Head:return {0.42f,0.85f};
    case Arm:return {0.30f,0.72f};
    default:return {0.30f,0.75f};
  }
}
// Approximate normal of the original axis-aligned body-part bounds.
// If the center is inside, use the nearest face with stable tie order.
inline Vec normal(Vec p,Vec lo,Vec hi){
  Vec closest{std::clamp(p.x,lo.x,hi.x),std::clamp(p.y,lo.y,hi.y),std::clamp(p.z,lo.z,hi.z)};
  Vec delta=sub(p,closest);
  const float d=length(delta);
  if(d>1e-6f)return mul(delta,1/d);
  const float gap[]={p.x-lo.x,hi.x-p.x,p.y-lo.y,hi.y-p.y,p.z-lo.z,hi.z-p.z};
  const Vec normals[]={{-1,0,0},{1,0,0},{0,-1,0},{0,1,0},{0,0,-1},{0,0,1}};
  int best=0;for(int j=1;j<6;++j)if(gap[j]<gap[best])best=j;
  return normals[best];
}
// Exact distance-to-box test along a linear segment in the translating body frame.
// Split where a coordinate crosses a box face; squared distance is quadratic on each interval.
struct Sweep {bool hit=false; float time=1; Vec point{0,0,0};};
inline Sweep sweepSphere(Vec start,Vec end,Vec lo,Vec hi,float radius){
  if(!finite(start)||!finite(end)||!finite(lo)||!finite(hi)||!std::isfinite(radius)||radius<0||
     lo.x>hi.x||lo.y>hi.y||lo.z>hi.z)return {};
  const double p[]={start.x,start.y,start.z}, d[]={double(end.x)-start.x,double(end.y)-start.y,double(end.z)-start.z};
  const double l[]={lo.x,lo.y,lo.z}, h[]={hi.x,hi.y,hi.z};
  const double rr=double(radius)*radius;
  auto distance2=[&](double t){
    double result=0;
    for(int j=0;j<3;++j){
      const double v=p[j]+d[j]*t;
      const double gap=v-std::clamp(v,l[j],h[j]);
      result+=gap*gap;
    }
    return result;
  };
  auto found=[&](double t){
    const auto f=static_cast<float>(t);
    return Sweep{true,f,add(start,mul(sub(end,start),f))};
  };
  if(distance2(0)<=rr)return found(0);
  // Fast conservative rejection; rounded corners are checked below.
  for(int j=0;j<3;++j)
    if(std::max(p[j],p[j]+d[j])<l[j]-radius || std::min(p[j],p[j]+d[j])>h[j]+radius)return {};
  double cuts[8]={0,1};int count=2;
  for(int j=0;j<3;++j)if(std::abs(d[j])>1e-12){
    for(double face:{l[j],h[j]}){
      double t=(face-p[j])/d[j];
      if(t>0&&t<1)cuts[count++]=t;
    }
  }
  std::sort(cuts,cuts+count);
  for(int j=0;j<count-1;++j){
    const double a=cuts[j],b=cuts[j+1],mid=(a+b)*0.5;
    if(distance2(a)<=rr)return found(a);
    if(b<=a)continue;
    double aa=0,bb=0;
    for(int k=0;k<3;++k){
      const double v=p[k]+d[k]*mid;
      if(v>=l[k]&&v<=h[k])continue;
      const double face=v<l[k]?l[k]:h[k];
      aa+=d[k]*d[k];bb+=(p[k]-face)*d[k];
    }
    const double minimum=aa>0?std::clamp(-bb/aa,a,b):b;
    if(distance2(minimum)>rr)continue;
    double left=a,right=minimum;
    for(int step=0;step<32;++step){
      const double center=(left+right)*0.5;
      if(distance2(center)<=rr)right=center;else left=center;
    }
    return found(right);
  }
  if(distance2(1)<=rr)return found(1);
  return {};
}
struct Result {bool valid=false; Vec velocity{0,0,0}; float approach=0,relativeBefore=0,relativeAfter=0; Vec spin{0,0,0}; float energyBefore=0,energyAfter=0,spinDelta=0;};
inline Result resolve(Vec p,Vec lo,Vec hi,Vec incoming,Vec body,Region r){
  if(!finite(p)||!finite(lo)||!finite(hi)||!finite(incoming)||!finite(body)||
     lo.x>hi.x||lo.y>hi.y||lo.z>hi.z)return {};
  const Vec n=normal(p,lo,hi), rel=sub(incoming,body);
  const float vn=dot(rel,n);
  if(vn>=-0.02f)return {}; // already separating / nearly tangent
  const auto m=material(r);
  const Vec tangent=sub(rel,mul(n,vn));
  const Vec after=add(mul(tangent,m.tangentRetention),mul(n,-vn*m.restitution));
  const Vec out=add(body,after);
  if(!finite(out))return {};
  return {true,out,-vn,length(rel),length(after)};
}
// Split a nominal 10 ms tick without changing the match or AI clock.
struct SplitDurations {float before,after;};
inline SplitDurations splitDurations(float fraction,float dt=0.01f){
  const float first=std::clamp(fraction,0.0f,1.0f)*dt;
  return {first,dt-first};
}
// Thin-shell sphere (I/m=2R^2/3). Impulse expressed per unit mass.
// Relative contact-point slip includes the ball's existing angular velocity.
inline Result resolveAngular(Vec p,Vec lo,Vec hi,Vec incoming,Vec body,Region r,Vec spin){
  auto base=resolve(p,lo,hi,incoming,body,r);
  if(!base.valid || !finite(spin))return {};
  constexpr float radius=0.11f, inertia=2.0f*radius*radius/3.0f;
  const Vec n=normal(p,lo,hi), arm=mul(n,-radius), rel=sub(incoming,body);
  const float vn=dot(rel,n), jn=-(1.0f+material(r).restitution)*vn;
  const Vec contact=add(rel,cross(spin,arm));
  const Vec slip=sub(contact,mul(n,dot(contact,n)));
  const float slipSpeed=length(slip);
  const float friction=1.0f-material(r).tangentRetention;
  const float jt=std::min(friction*jn,slipSpeed/(1.0f+radius*radius/inertia));
  const Vec tangentImpulse=slipSpeed>1e-6f?mul(slip,-jt/slipSpeed):Vec{0,0,0};
  const Vec after=add(rel,add(mul(n,jn),tangentImpulse));
  const Vec afterSpin=add(spin,mul(cross(arm,tangentImpulse),1.0f/inertia));
  const Vec velocity=add(body,after);
  const float beforeEnergy=0.5f*(dot(rel,rel)+inertia*dot(spin,spin));
  const float afterEnergy=0.5f*(dot(after,after)+inertia*dot(afterSpin,afterSpin));
  if(!finite(velocity)||!finite(afterSpin)||!std::isfinite(beforeEnergy)||!std::isfinite(afterEnergy))return {};
  return {true,velocity,-vn,length(rel),length(after),afterSpin,beforeEnergy,afterEnergy,length(sub(afterSpin,spin))};
}

// Subsequent contacts use translated snapshots, not a rotating limb sweep.
// Never process another part of a player already hit in this tick.
constexpr unsigned MaxChainContacts=3;
struct Collider {int player; Vec lo,hi,body; Region region; float radius;};
struct ChainHit {bool valid=false; float fraction=1; Collider collider{}; Vec point{};};
struct ChainEvent {int player; Region region; Result result; float timeMs;};
inline ChainHit nextChain(Vec p,Vec v,Vec spin,float elapsed,float remaining,
                          const std::vector<Collider>& colliders,const std::vector<int>& used) {
  ChainHit best;
  if(remaining<=0 || elapsed<0 || elapsed+remaining>0.010001f)return best;
  for(const auto& c:colliders){
    if(std::find(used.begin(),used.end(),c.player)!=used.end())continue;
    const Vec shift=mul(c.body,elapsed);
    const Vec start=sub(p,shift), end=add(start,mul(sub(v,c.body),remaining));
    const auto hit=sweepSphere(start,end,c.lo,c.hi,c.radius);
    if(!hit.hit)continue;
    const auto response=resolveAngular(hit.point,c.lo,c.hi,v,c.body,c.region,spin);
    if(!response.valid)continue;
    if(!best.valid || hit.time<best.fraction-1e-6f){
      best={true,hit.time,c,hit.point};
    }
  }
  return best;
}
}
'''

def surface_impact_header(source):
    return replace_once(source,"  void TribunObserveContactPose(Player* player);",
        """  void TribunObserveContactPose(Player* player);
  unsigned long tribunLegacyImpacts=0, tribunSurfaceImpacts=0, tribunSeparatingRejected=0;
  unsigned long tribunImpactRegions[6]={0,0,0,0,0,0};
  double tribunRelativeBefore=0, tribunRelativeAfter=0;
  unsigned long tribunEnergyViolations=0;\n  unsigned long tribunAngularImpacts=0, tribunSpinChanges=0, tribunAngularEnergyViolations=0;\n  double tribunAngularEnergyBefore=0, tribunAngularEnergyAfter=0, tribunMaxSpinDelta=0;\n  unsigned long tribunSweepTests=0, tribunSweepHits=0, tribunSweepApplied=0, tribunSweepThrough=0;\n  double tribunSweepMaxLeadMs=0;\n  Player* tribunSplitPlayer=nullptr;\n  bool tribunSplitThrough=false;\n  unsigned tribunSplitRegionIndex=0;\n  float tribunSplitTime=0;\n  unsigned long tribunSplitQueued=0,tribunSplitApplied=0,tribunSplitCancelled=0;\n  double tribunSplitBeforeMs=0,tribunSplitAfterMs=0;\n  void TribunFinishSplit();\n  unsigned long tribunChainTicks=0,tribunChainExtra=0,tribunChainRejected=0,tribunChainCap=0,tribunChainMax=0;\n  double tribunChainMaxTimeMs=0;\n  struct TribunLimbSample { Vector3 center; unsigned long tick; Vector3 velocity; bool measured; bool unique; };\n  std::map<std::pair<int,std::string>,TribunLimbSample> tribunLimbSamples;\n  void TribunCaptureLimbPose();\n  Vector3 TribunLimbVelocity(Player* player,const std::string& name);\n  unsigned long tribunLimbSamplesMeasured=0,tribunLimbQueries=0,tribunLimbUsed=0,tribunLimbFallback=0;\n  double tribunLimbMaxRelativeSpeed=0;""")

def surface_impact_match(source):
    source=replace_once(source,'#include "tribun_visual_rng.hpp"',
        '#include "tribun_visual_rng.hpp"\n#include "tribun_surface_impact.hpp"')
    start=source.index("void Match::CheckBallCollisions() {")
    end=source.index("void Match::FollowCamera(",start)
    section=source[start:end]
    section=replace_once(section,"  float tackleBallExcitement = 0.0f;", """  float tackleBallExcitement = 0.0f;
  const bool surfaceMode=tribun_visual::surfaceImpact();
  const bool sweptMode=tribun_visual::sweptImpact();
  const auto ballStart=ball->Predict(0);
  const auto ballEnd=ball->Predict(10);
  // Avoid predictive responses across touch/goal lines. Existing rules retain priority.
  const bool sweepInside=sweptMode && std::abs(ballStart.coords[0])<pitchHalfW-0.3f &&
      std::abs(ballEnd.coords[0])<pitchHalfW-0.3f && std::abs(ballStart.coords[1])<pitchHalfH-0.3f &&
      std::abs(ballEnd.coords[1])<pitchHalfH-0.3f;
  float bestTime=2.0f;
  bool bestThrough=false;
  tribun_impact::Vec bestPoint{},bestLo{},bestHi{},bestBody{};
  std::vector<tribun_impact::Collider> chainCandidates;
  tribun_impact::Result bestImpact;
  tribun_impact::Region bestRegion=tribun_impact::Other;
  Player* impactPlayer=nullptr;
  const auto asVec=[](const Vector3& v){return tribun_impact::Vec{v.coords[0],v.coords[1],v.coords[2]};};""")
    section=replace_once(section,"          TribunObserveContactPose(players[i]);",
        """          TribunObserveContactPose(players[i]);
          if (surfaceMode) objectList.clear();""")
    section=replace_once(section,"""        if (((players[i]->GetPosition() + Vector3(0, 0, 0.8f)) - ball->Predict(0)).GetLength() <
            2.5f) {""","""        const float sweepMargin=sweepInside ? (ballEnd-ballStart).GetLength()+
              players[i]->GetMovement().GetLength()*0.01f : 0.0f;
        if (((players[i]->GetPosition() + Vector3(0, 0, 0.8f)) - ball->Predict(0)).GetLength() <
            2.5f+sweepMargin+(tribun_visual::chainImpact()?1.0f:0.0f)+(tribun_visual::limbImpact()?0.25f:0.0f)) {""")
    section=replace_once(section,"            if (objAABB.Intersects(ball->Predict(0), ballRadius)) {",
        """            const Vector3 partVelocity=tribun_visual::limbImpact()?TribunLimbVelocity(players[i],(*objIter)->GetName()):players[i]->GetMovement();\n            if(tribun_visual::chainImpact() && sweepInside &&\n               !(players[i]==players[i]->GetTeam()->GetDesignatedTeamPossessionPlayer() && GetLastTouchBias(200)<0.01f)) {\n              chainCandidates.push_back({players[i]->GetID(),asVec(objAABB.minxyz),asVec(objAABB.maxxyz),\n                  asVec(partVelocity),tribun_impact::region((*objIter)->GetName()),std::abs(ballRadius)});\n            }\n            const bool instant=objAABB.Intersects(ball->Predict(0),ballRadius);
            tribun_impact::Sweep swept;
            bool through=false;
            if(sweepInside && !instant) {
              ++tribunSweepTests;
              const auto relativeEnd=ballEnd-partVelocity*0.01f;
              swept=tribun_impact::sweepSphere(asVec(ballStart),asVec(relativeEnd),
                  asVec(objAABB.minxyz),asVec(objAABB.maxxyz),std::abs(ballRadius));
              if(swept.hit) {
                ++tribunSweepHits;
                through=!objAABB.Intersects(relativeEnd,ballRadius);
              }
            }
            if (instant || swept.hit) {""")
    section=replace_once(section,"                players[i]->TriggerControlledBallCollision();",
        """                // Intentional control remains an instantaneous native decision.
                if (instant) players[i]->TriggerControlledBallCollision();""")
    section=replace_once(section,"                if (tribun_visual::collisionOnly()) ++tribunControlledRequests;",
        "                if (tribun_visual::collisionOnly() && instant) ++tribunControlledRequests;")
    section=replace_once(section,"                // todonow: average bouncevec and bias together per hit",
        """                if (surfaceMode) {
                  const auto region=tribun_impact::region((*objIter)->GetName());
                  const float time=instant?0.0f:swept.time;
                  const auto point=instant?asVec(ballStart):swept.point;
                  const auto result=tribun_visual::angularImpact()
                      ? tribun_impact::resolveAngular(point,
                          asVec(objAABB.minxyz),asVec(objAABB.maxxyz),asVec(ball->GetMovement()),
                          asVec(partVelocity),region,asVec(ball->TribunAngularVelocity()))
                      : tribun_impact::resolve(point,
                          asVec(objAABB.minxyz),asVec(objAABB.maxxyz),asVec(ball->GetMovement()),
                          asVec(partVelocity),region);
                  if (result.valid && (!bestImpact.valid || time<bestTime-1e-6f ||
                      (std::abs(time-bestTime)<=1e-6f && result.approach>bestImpact.approach))) {
                    bestTime=time;
                    bestThrough=through;
                    bestPoint=point;bestLo=asVec(objAABB.minxyz);bestHi=asVec(objAABB.maxxyz);bestBody=asVec(partVelocity);
                    bestImpact=result;
                    bestRegion=region;
                    impactPlayer=players[i];
                  } else if (!result.valid) {
                    ++tribunSeparatingRejected;
                  }
                  ++objIter;
                  continue;
                }
                // todonow: average bouncevec and bias together per hit""")
    section=replace_once(section,"  if (bias > 0.0f) {", """  if (surfaceMode && bestImpact.valid && impactPlayer && tribun_visual::splitImpact() && bestTime>0.0f) {
    // Schedule after referee processing, then finalize only after Ball::Process commits.
    ball->TribunQueueSplit(bestTime, bestPoint,bestLo,bestHi,bestBody,bestRegion);\n    if(tribun_visual::chainImpact()) ball->TribunQueueChain(impactPlayer->GetID(),chainCandidates);
    tribunSplitPlayer=impactPlayer;
    tribunSplitThrough=bestThrough;
    tribunSplitRegionIndex=static_cast<unsigned>(bestRegion);
    tribunSplitTime=bestTime;
    ++tribunSplitQueued;
    return;
  }
  if (surfaceMode && bestImpact.valid && impactPlayer) {
    ++tribunSurfaceImpacts;
    if(sweptMode && bestTime>0.0f) {
      ++tribunSweepApplied;
      if(bestThrough) ++tribunSweepThrough;
      tribunSweepMaxLeadMs=std::max(tribunSweepMaxLeadMs,static_cast<double>(bestTime)*10.0);
    }
    ++tribunImpactRegions[bestRegion];
    tribunRelativeBefore+=bestImpact.relativeBefore;
    tribunRelativeAfter+=bestImpact.relativeAfter;
    if (!tribun_visual::angularImpact() && bestImpact.relativeAfter>bestImpact.relativeBefore+0.0001f) ++tribunEnergyViolations;
    impactPlayer->GetTeam()->SetLastTouchPlayer(impactPlayer,e_TouchType_Accidental);
    Vector3 resultVector(bestImpact.velocity.x,bestImpact.velocity.y,bestImpact.velocity.z);
    if (tribun_visual::angularImpact()) {
      ++tribunAngularImpacts;
      if (bestImpact.spinDelta>0.0001f) ++tribunSpinChanges;
      tribunAngularEnergyBefore+=bestImpact.energyBefore;
      tribunAngularEnergyAfter+=bestImpact.energyAfter;
      tribunMaxSpinDelta=std::max(tribunMaxSpinDelta,static_cast<double>(bestImpact.spinDelta));
      if (bestImpact.energyAfter>bestImpact.energyBefore+0.0001f*std::max(1.0f,bestImpact.energyBefore))
        ++tribunAngularEnergyViolations;
      ball->TribunSetAngularVelocity(Vector3(bestImpact.spin.x,bestImpact.spin.y,bestImpact.spin.z));
    } // Otherwise retain pre-contact spin.
    ball->Touch(resultVector); // refresh prediction and mental images using final spin
    ball->TriggerBallTouchSound(pow(NormalizedClamp(resultVector.GetLength(),4.0f,40.0f),0.7f));
    if (impactPlayer->GetCurrentFunctionType()==e_FunctionType_Sliding)
      AddExcitementBoost(0.35f,1400);
    else if (impactPlayer->GetCurrentFunctionType()==e_FunctionType_Interfere)
      AddExcitementBoost(0.22f,1400);
    lastBodyBallCollisionTime_ms=actualTime_ms;
  }
  if (bias > 0.0f) {
    if (tribun_visual::collisionOnly()) ++tribunLegacyImpacts;""")
    return source[:start]+section+source[end:]

def angular_ball_header(source):
    return replace_once(source,"  Vector3 GetMovement();",
        "  Vector3 GetMovement();\n  Vector3 TribunAngularVelocity() const;\n  void TribunSetAngularVelocity(const Vector3& spin);")

def angular_ball_source(source):
    return replace_once(source,"void Ball::Touch(const Vector3& target) {",
        """// Quaternion represents the rotation for a 1 ms step. Use its shortest
// axis-angle representation directly; legacy Euler setter flips the X axis.
Vector3 Ball::TribunAngularVelocity() const {
  const auto q=rotation_ms.GetNormalized();
  const float sign=q.elements[3]<0 ? -1.0f : 1.0f;
  const Vector3 axis(q.elements[0]*sign,q.elements[1]*sign,q.elements[2]*sign);
  const float magnitude=axis.GetLength();
  if (magnitude<1e-8f) return Vector3(0);
  const float angle=2.0f*std::atan2(magnitude,std::abs(q.elements[3]));
  return axis*(1000.0f*angle/magnitude);
}
void Ball::TribunSetAngularVelocity(const Vector3& spin) {
  const float speed=spin.GetLength();
  if (!std::isfinite(speed)) return;
  if (speed<1e-5f) rotation_ms=QUATERNION_IDENTITY;
  else rotation_ms.SetAngleAxis(speed*0.001f,spin/speed);
  CalculatePrediction();
}
void Ball::Touch(const Vector3& target) {""")

def split_ball_header(source):
    source=replace_once(source,'#include "base/math/vector3.hpp"', '#include "base/math/vector3.hpp"\n#include "tribun_surface_impact.hpp"') if '#include "base/math/vector3.hpp"' in source else replace_once(source,"class Ball {",'#include "tribun_surface_impact.hpp"\n\nclass Ball {')
    source=replace_once(source,"  void TribunSetAngularVelocity(const Vector3& spin);",
        """  void TribunSetAngularVelocity(const Vector3& spin);
  void TribunQueueSplit(float fraction,tribun_impact::Vec point,tribun_impact::Vec lo,
      tribun_impact::Vec hi,tribun_impact::Vec body,tribun_impact::Region region);
  tribun_impact::Result TribunTakeSplitResult();\n  void TribunQueueChain(int first,const std::vector<tribun_impact::Collider>& candidates);\n  std::vector<tribun_impact::ChainEvent> TribunTakeChain(unsigned long& rejected,bool& cap);""")
    return replace_once(source,"  Quaternion rotation_ms;\n\n  Vector3 predictions",
        """  Quaternion rotation_ms;
  bool tribunSplitPending=false,tribunSplitProcessing=false;
  float tribunSplitFraction=0;
  tribun_impact::Vec tribunSplitPoint{},tribunSplitLo{},tribunSplitHi{},tribunSplitBody{};
  tribun_impact::Region tribunSplitRegion=tribun_impact::Other;
  tribun_impact::Result tribunSplitResult{};\n  std::vector<tribun_impact::Collider> tribunChainCandidates;\n  std::vector<tribun_impact::ChainEvent> tribunChainEvents;\n  int tribunChainFirst=-1;\n  unsigned long tribunChainRejected=0;\n  bool tribunChainCap=false;

  Vector3 predictions""")

def split_ball_source(source):
    source=replace_once(source,"Vector3 Ball::TribunAngularVelocity() const {",
        """static Vector3 TribunReadSpin(const Quaternion& rotation_ms) {
  const auto q=rotation_ms.GetNormalized();
  const float sign=q.elements[3]<0 ? -1.0f : 1.0f;
  const Vector3 axis(q.elements[0]*sign,q.elements[1]*sign,q.elements[2]*sign);
  const float magnitude=axis.GetLength();
  if (magnitude<1e-8f) return Vector3(0);
  return axis*(1000.0f*2.0f*std::atan2(magnitude,std::abs(q.elements[3]))/magnitude);
}
void Ball::TribunQueueSplit(float fraction,tribun_impact::Vec point,tribun_impact::Vec lo,
    tribun_impact::Vec hi,tribun_impact::Vec body,tribun_impact::Region region) {
  tribunSplitPending=std::isfinite(fraction) && fraction>0 && fraction<=1;
  tribunSplitFraction=fraction;
  tribunSplitPoint=point;tribunSplitLo=lo;tribunSplitHi=hi;tribunSplitBody=body;tribunSplitRegion=region;
  tribunSplitResult={};\n  tribunChainCandidates.clear();tribunChainFirst=-1;\n}\nvoid Ball::TribunQueueChain(int first,const std::vector<tribun_impact::Collider>& candidates) {\n  tribunChainFirst=first;tribunChainCandidates=candidates;\n}\nstd::vector<tribun_impact::ChainEvent> Ball::TribunTakeChain(unsigned long& rejected,bool& cap) {\n  rejected=tribunChainRejected;cap=tribunChainCap;\n  auto events=tribunChainEvents;tribunChainEvents.clear();return events;\n}\ntribun_impact::Result Ball::TribunTakeSplitResult() {
  auto result=tribunSplitResult;
  tribunSplitResult={};
  return result;
}
Vector3 Ball::TribunAngularVelocity() const {""")
    # Wrap only the first prediction interval; subsequent intervals keep the upstream 10 ms cadence.
    source=replace_once(source,"    BallPhysicsState physicsState{nextPos, momentumPredict};",
        """    const bool split=tribunSplitProcessing && predictTime_ms==10;
    const float fullStep=timeStep;
    const auto durations=tribun_impact::splitDurations(tribunSplitFraction,fullStep);
    float elapsed=0.0f;
    tribun_impact::ChainHit nextHit;
    std::vector<int> used;
    const bool chain=split && tribunChainFirst>=0;
    if(chain)used.push_back(tribunChainFirst);
    const auto asVec=[](const Vector3& v){return tribun_impact::Vec{v.coords[0],v.coords[1],v.coords[2]};};
    auto applyImpact=[&](const tribun_impact::Result& impact){
      const auto& v=impact.velocity;
      momentumPredict=Vector3(v.x,v.y,v.z);
      const auto& spin=impact.spin;
      Vector3 omega(spin.x,spin.y,spin.z);
      const float speed=omega.GetLength();
      if(speed<1e-5f) rotationPredict_ms=QUATERNION_IDENTITY;
      else rotationPredict_ms.SetAngleAxis(speed*0.001f,omega/speed);
    };
    for(int segment=0;segment<(split?static_cast<int>(tribun_impact::MaxChainContacts)+1:1);++segment) {
      if(split) {
        if(segment==0)timeStep=durations.before;
        else {
        if(segment==1) {
          const auto asVec=[](const Vector3& v){return tribun_impact::Vec{v.coords[0],v.coords[1],v.coords[2]};};
          tribunSplitResult=tribun_impact::resolveAngular(tribunSplitPoint,tribunSplitLo,
              tribunSplitHi,asVec(momentumPredict),tribunSplitBody,tribunSplitRegion,
              asVec(TribunReadSpin(rotationPredict_ms)));
          if(tribunSplitResult.valid) applyImpact(tribunSplitResult);
        } else if(nextHit.valid) {
          const auto& c=nextHit.collider;
          const auto actual=tribun_impact::sub(asVec(nextPos),tribun_impact::mul(c.body,elapsed));
          const auto result=tribun_impact::resolveAngular(actual,c.lo,c.hi,
              asVec(momentumPredict),c.body,c.region,asVec(TribunReadSpin(rotationPredict_ms)));
          // Reject a predicted event when the integrated point missed the original sphere.
          const auto overlap=tribun_impact::sweepSphere(actual,actual,c.lo,c.hi,c.radius+0.001f);
          used.push_back(c.player);
          if(result.valid && overlap.hit) {
            applyImpact(result);
            tribunChainEvents.push_back({c.player,c.region,result,elapsed*1000.0f});
          } else ++tribunChainRejected;
        }
        const float remaining=std::max(0.0f,fullStep-elapsed);
        if(remaining<=0)break;
        nextHit={};
        if(chain && tribunSplitResult.valid) {
          nextHit=tribun_impact::nextChain(asVec(nextPos),asVec(momentumPredict),
              asVec(TribunReadSpin(rotationPredict_ms)),elapsed,remaining,tribunChainCandidates,used);
          if(nextHit.valid && segment>=static_cast<int>(tribun_impact::MaxChainContacts)) {
            tribunChainCap=true;nextHit={};
          }
        }
        timeStep=nextHit.valid?remaining*nextHit.fraction:remaining;
        }
        if(timeStep<=0) continue;
      }
    BallPhysicsState physicsState{nextPos, momentumPredict};""")
    source=replace_once(source,"    nextOrientation = rotationPredictTimeStepped * nextOrientation;\n\n    if (predictTime_ms % 10 == 0) {",
        """    nextOrientation = rotationPredictTimeStepped * nextOrientation;
    firstTime=false;\n    elapsed+=timeStep;\n    if(split && segment>0 && !nextHit.valid)break;\n    }\n    timeStep=fullStep;

    if (predictTime_ms % 10 == 0) {""")
    source=replace_once(source,"  BallSpatialInfo spatialInfo = CalculatePrediction();\n  momentum = spatialInfo.momentum;",
        """  tribunSplitProcessing=tribunSplitPending;\n  tribunSplitResult={};\n  tribunChainEvents.clear();tribunChainRejected=0;tribunChainCap=false;
  BallSpatialInfo spatialInfo = CalculatePrediction();
  tribunSplitProcessing=false;
  tribunSplitPending=false;\n  tribunChainCandidates.clear();tribunChainFirst=-1;\n  momentum = spatialInfo.momentum;""")
    for anchor in ("void Ball::SetPosition(const Vector3& target) {",
                   "void Ball::SetMomentum(const Vector3& target) {",
                   "void Ball::ResetSituation(const Vector3& focusPos) {",
                   "void Ball::SetRotation(radian x, radian y, radian z,\n                       float bias) {  // radians per second for each axis"):
        source=replace_once(source,anchor,anchor+"\n  tribunSplitPending=false;tribunSplitResult={};")
    return source

def split_match_source(source):
    source=replace_once(source,"    if (IsInPlay()) {\n      CheckBallCollisions();  // todo: should not read geoms during process\n    }",
        """    if (IsInPlay() && !tribun_visual::splitImpact()) {
      CheckBallCollisions();  // todo: should not read geoms during process
    }""")
    source=replace_once(source,"    referee->Process();\n\n    // ball",
        """    referee->Process();
    if (IsInPlay() && tribun_visual::splitImpact()) CheckBallCollisions();

    // ball""")
    source=replace_once(source,"    ball->Process();\n\n    // create mental images",
        """    ball->Process();
    if (tribunSplitPlayer) TribunFinishSplit();

    // create mental images""")
    return replace_once(source,"void Match::FollowCamera(",
        """void Match::TribunFinishSplit() {
  auto* player=tribunSplitPlayer;
  tribunSplitPlayer=nullptr;
  const auto result=ball->TribunTakeSplitResult();
  unsigned long rejected=0;bool cap=false;
  const auto extra=ball->TribunTakeChain(rejected,cap);
  tribunChainRejected+=rejected;
  if(cap)++tribunChainCap;
  if(!result.valid) {++tribunSplitCancelled;return;}
  ++tribunSplitApplied;
  ++tribunSweepApplied;
  if(tribunSplitThrough) ++tribunSweepThrough;
  tribunSweepMaxLeadMs=std::max(tribunSweepMaxLeadMs,static_cast<double>(tribunSplitTime)*10.0);
  tribunSplitBeforeMs+=tribunSplitTime*10.0;
  tribunSplitAfterMs+=(1.0-tribunSplitTime)*10.0;
  ++tribunSurfaceImpacts;
  ++tribunAngularImpacts;
  // Region is retained by the match below; no inferred body part.
  ++tribunImpactRegions[tribunSplitRegionIndex];
  tribunRelativeBefore+=result.relativeBefore;
  tribunRelativeAfter+=result.relativeAfter;
  if(result.spinDelta>0.0001f) ++tribunSpinChanges;
  tribunAngularEnergyBefore+=result.energyBefore;
  tribunAngularEnergyAfter+=result.energyAfter;
  tribunMaxSpinDelta=std::max(tribunMaxSpinDelta,static_cast<double>(result.spinDelta));
  if(result.energyAfter>result.energyBefore+0.0001f*std::max(1.0f,result.energyBefore)) ++tribunAngularEnergyViolations;
  player->GetTeam()->SetLastTouchPlayer(player,e_TouchType_Accidental);
  ball->TriggerBallTouchSound(pow(NormalizedClamp(ball->GetMovement().GetLength(),4.0f,40.0f),0.7f));
  if(player->GetCurrentFunctionType()==e_FunctionType_Sliding) AddExcitementBoost(0.35f,1400);
  else if(player->GetCurrentFunctionType()==e_FunctionType_Interfere) AddExcitementBoost(0.22f,1400);
  lastBodyBallCollisionTime_ms=actualTime_ms;
  if(tribun_visual::chainImpact()) {
    ++tribunChainTicks;
    tribunChainMax=std::max(tribunChainMax,static_cast<unsigned long>(1+extra.size()));
    for(const auto& event:extra) {
      auto* touched=GetPlayer(event.player);
      const auto& hit=event.result;
      ++tribunChainExtra;
      ++tribunSurfaceImpacts;++tribunAngularImpacts;++tribunImpactRegions[event.region];
      tribunChainMaxTimeMs=std::max(tribunChainMaxTimeMs,static_cast<double>(event.timeMs));
      tribunRelativeBefore+=hit.relativeBefore;tribunRelativeAfter+=hit.relativeAfter;
      if(hit.spinDelta>0.0001f)++tribunSpinChanges;
      tribunAngularEnergyBefore+=hit.energyBefore;tribunAngularEnergyAfter+=hit.energyAfter;
      tribunMaxSpinDelta=std::max(tribunMaxSpinDelta,static_cast<double>(hit.spinDelta));
      if(hit.energyAfter>hit.energyBefore+0.0001f*std::max(1.0f,hit.energyBefore))++tribunAngularEnergyViolations;
      touched->GetTeam()->SetLastTouchPlayer(touched,e_TouchType_Accidental);
    }
  }
}

void Match::FollowCamera(""")

def limb_match_source(source):
    source=replace_once(source,"void Match::ResetSituation(const Vector3& focusPos) {",
        """void Match::ResetSituation(const Vector3& focusPos) {
  tribunLimbSamples.clear();""")
    return replace_once(source,"void Match::TribunFinishSplit() {",
        """void Match::TribunCaptureLimbPose() {
  const auto tick=GetIterations();
  std::vector<Player*> active;
  GetActiveTeamPlayers(0,active);
  GetActiveTeamPlayers(1,active);
  decltype(tribunLimbSamples) next;
  const auto asVec=[](const Vector3& v){return tribun_impact::Vec{v.coords[0],v.coords[1],v.coords[2]};};
  for(auto* player:active) {
    std::list<boost::intrusive_ptr<Geometry>> parts;
    player->GetHumanoidNode()->GetObjects(e_ObjectType_Geometry,parts);
    for(const auto& part:parts) {
      const auto key=std::make_pair(player->GetID(),part->GetName());
      Vector3 center;
      part->GetAABB().GetCenter(center);
      auto existing=next.find(key);
      if(existing!=next.end()) {
        existing->second.unique=false;
        existing->second.measured=false;
        continue;
      }
      const auto root=player->GetMovement();
      auto old=tribunLimbSamples.find(key);
      auto estimate=tribun_impact::LimbEstimate{asVec(root),false};
      if(old!=tribunLimbSamples.end() && old->second.unique && tick>old->second.tick)
        estimate=tribun_impact::estimateLimb(asVec(old->second.center),asVec(center),asVec(root),tick-old->second.tick);
      const auto& v=estimate.velocity;
      next.emplace(key,TribunLimbSample{center,tick,Vector3(v.x,v.y,v.z),estimate.measured,true});
    }
  }
  for(const auto& item:next) if(item.second.measured)++tribunLimbSamplesMeasured;
  tribunLimbSamples.swap(next);
}

Vector3 Match::TribunLimbVelocity(Player* player,const std::string& name) {
  ++tribunLimbQueries;
  const auto root=player->GetMovement();
  const auto found=tribunLimbSamples.find(std::make_pair(player->GetID(),name));
  if(found!=tribunLimbSamples.end() && found->second.unique && found->second.measured &&
      GetIterations()>=found->second.tick && GetIterations()-found->second.tick<=1) {
    ++tribunLimbUsed;
    tribunLimbMaxRelativeSpeed=std::max(tribunLimbMaxRelativeSpeed,
        static_cast<double>((found->second.velocity-root).GetLength()));
    return found->second.velocity;
  }
  ++tribunLimbFallback;
  return root;
}

void Match::TribunFinishSplit() {""")

def main():
    from fixture_patch import apply
    from short_match_patch import apply as apply_short_match
    apply(sys.argv[1])
    apply_short_match(sys.argv[1])
    main_path = pathlib.Path(sys.argv[1]) / "src/main.cpp"
    main_source = main_path.read_text(encoding="utf-8")
    if "[tribun-render] scheduled-draw=" not in main_source:
        main_path.write_text(suppress_draw_tasks(main_source), encoding="utf-8")
    task_path = pathlib.Path(sys.argv[1]) / "src/gametask.cpp"
    task_source = task_path.read_text(encoding="utf-8")
    if "const bool tribunNoUpload" not in task_source:
        task_path.write_text(suppress_geometry_uploads(task_source), encoding="utf-8")
    graphics = pathlib.Path(sys.argv[1]) / "src/systems/graphics"
    (graphics / "rendering/tribun_null_renderer.hpp").write_text(NULL_RENDERER_HEADER, encoding="utf-8")
    system_path = graphics / "graphics_system.cpp"
    system_source = system_path.read_text(encoding="utf-8")
    if "new TribunNullRenderer3D()" not in system_source:
        system_path.write_text(select_null_renderer(system_source), encoding="utf-8")
    audio_path = pathlib.Path(sys.argv[1]) / "src/systems/audio/audio_system.cpp"
    audio_source = audio_path.read_text(encoding="utf-8")
    if "[tribun-lean] audio-backend=null" not in audio_source:
        audio_path.write_text(lightweight_audio(audio_source), encoding="utf-8")
    src = pathlib.Path(sys.argv[1]) / "src"
    humanoid_dir = src / "onthepitch/player/humanoid"
    (humanoid_dir / "tribun_skinning_channels.hpp").write_text(SKINNING_CHANNEL_HEADER, encoding="utf-8")
    humanoid_path = humanoid_dir / "humanoidbase.cpp"
    humanoid_source = humanoid_path.read_text(encoding="utf-8")
    if "[tribun-skinning] runtime=" not in humanoid_source:
        humanoid_path.write_text(optimize_skinning_channels(humanoid_source), encoding="utf-8")
    (src / "managers/tribun_worker_limit.hpp").write_text(WORKER_LIMIT_HEADER, encoding="utf-8")
    worker_path = src / "managers/taskmanager.cpp"
    worker_source = worker_path.read_text(encoding="utf-8")
    if "[tribun-workers] hardware=" not in worker_source:
        worker_path.write_text(limit_native_workers(worker_source), encoding="utf-8")
    (src / "onthepitch/tribun_visual_rng.hpp").write_text(VISUAL_RNG_HEADER, encoding="utf-8")
    (src / "onthepitch/tribun_surface_impact.hpp").write_text(IMPACT_HEADER, encoding="utf-8")
    for relative,marker,transform in (
        ("onthepitch/proceduralpitch.cpp","TribunPitchFast",visual_pitch_rng),
        ("misc/perlin.h","visualRng{0}",visual_perlin_header),
        ("misc/perlin.cpp","visualRng.reset",visual_perlin_source),
        ("onthepitch/match.cpp","[tribun-visual] rng=isolated",visual_match_rng),
    ):
        target = src / relative
        original = target.read_text(encoding="utf-8")
        if marker not in original:
            target.write_text(transform(original), encoding="utf-8")
    for relative,marker,transform in (
        ("main.cpp","[tribun-pose] schedule=ordered",ordered_pose_main),
        ("gametask.cpp","tribun_visual::poseDue",ordered_pose_task),
        ("onthepitch/match.cpp","previousPutTime_ms = tribun_visual::orderedPose()",ordered_pose_clock),
        ("onthepitch/player/humanoid/humanoidbase.cpp","tribun_visual::orderedPose() ?",ordered_pose_initial_samples),
        ("onthepitch/ball.cpp","tribun_visual::Stream soundRng",isolate_ball_audio_rng),
        ("onthepitch/match.hpp","void TribunUpdateCollisionPose();",collision_pose_header),
        ("onthepitch/match.cpp","void Match::TribunUpdateCollisionPose()",collision_pose_match),
        ("gametask.cpp","match->TribunUpdateCollisionPose();",collision_pose_task),
        ("onthepitch/match.cpp","++tribunBallOverlaps",contact_probe),
        ("onthepitch/match.hpp","tribunPlayerPoseTick",adaptive_contact_header),
        ("onthepitch/match.cpp","void Match::TribunObserveContactPose",adaptive_contact_match),
        ("onthepitch/match.hpp","tribunLegacyImpacts",surface_impact_header),
        ("onthepitch/match.cpp","bestImpact.relativeAfter",surface_impact_match),
        ("onthepitch/ball.hpp","TribunAngularVelocity() const",angular_ball_header),
        ("onthepitch/ball.cpp","Vector3 Ball::TribunAngularVelocity()",angular_ball_source),
        ("onthepitch/ball.hpp","void TribunQueueSplit",split_ball_header),
        ("onthepitch/ball.cpp","void Ball::TribunQueueSplit",split_ball_source),
        ("onthepitch/match.cpp","void Match::TribunFinishSplit",split_match_source),
        ("onthepitch/match.cpp","void Match::TribunCaptureLimbPose()",limb_match_source),
    ):
        target=src/relative
        original=target.read_text(encoding="utf-8")
        if marker not in original:
            target.write_text(transform(original),encoding="utf-8")
    path = pathlib.Path(sys.argv[1]) / "src/onthepitch/match.cpp"
    text = path.read_text(encoding="utf-8")
    if "static bool TribunLeanScene()" not in text:
        text = lightweight_match(text)
        path.write_text(text, encoding="utf-8")
    if "void TribunTrace(" in text:
        return
    anchor = "const unsigned int replaySize_ms = 10000;"
    text = replace_once(text, anchor, HEADER + "\n" + anchor)
    anchor = "  // Tell the game page once; the full-time screen used to be re-created"
    text = replace_once(text, anchor, "  TribunApplyTactics(*this, gameOver);\n  TribunTrace(*this, gameOver);\n\n" + anchor)
    path.write_text(text, encoding="utf-8")

if __name__ == "__main__":
    main()
