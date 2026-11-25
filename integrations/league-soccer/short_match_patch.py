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
// Clear central/diagonal corridor: measured in metres, relative to attacking direction.
inline bool ClearForwardCorridor(float progress, float sideMargin, float nearestAhead,
                                 float lateralClearance, float nearestOpponent) {
  return progress >= 1.0f && sideMargin >= 3.0f && nearestAhead >= 4.0f &&
         lateralClearance >= 1.8f && nearestOpponent >= 2.5f;
}
inline bool PrioritizeGoodShot(float distance, float angle, float odds, bool uniquePossession) {
  return uniquePossession && distance >= 2.0f && distance <= 22.0f &&
         angle >= 0.55f && odds >= 0.62f;
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
        ("float passThreshold = 0.12f - longPossessionFactor * 0.06f;", "const float tribunTempo = clamp(team->GetTeamData()->GetTactics().userProperties.GetReal(\"tribun_tempo\", 0.5f), 0.0f, 1.0f);\n  float passThreshold = 0.12f - longPossessionFactor * 0.06f + (0.5f - tribunTempo) * 0.06f;"),
        ("float forwardWeight = 2.0f + AI_GetMindSet(CastPlayer()->GetDynamicFormationEntry().role) * 5.0f;", "float forwardWeight = (AITactics::ShortMatchAttackEnabled() ? 2.5f : 2.0f) + AI_GetMindSet(CastPlayer()->GetDynamicFormationEntry().role) * 5.0f;"),
    ])

    # Only ordinary ball-out restarts; leave goals, fouls, cards, penalties and half-time intact.
    edit(root, "src/onthepitch/referee.cpp", [
        ('#include "referee.hpp"', '#include "referee.hpp"\n#include <cstdlib>\n#include <cstring>\n#include <algorithm>'),
        ("    if (!match->IsInPlay() && !match->IsInSetPiece() && buffer.active == true) {", r'''    if (!match->IsInPlay() && !match->IsInSetPiece() && buffer.active == true) {
      const char* quickRestarts = std::getenv("TRIBUN_NATIVE_QUICK_RESTARTS");
      if (quickRestarts && std::strcmp(quickRestarts, "1") == 0 &&
          !buffer.endPhase && !foul.foulType &&
          (buffer.desiredSetPiece == e_SetPiece_ThrowIn ||
           buffer.desiredSetPiece == e_SetPiece_Corner ||
           buffer.desiredSetPiece == e_SetPiece_GoalKick)) {
        // Referee uses equality against a 10 ms tick. Never move a deadline
        // backwards past the current tick, or preparation could be skipped.
        const unsigned long now = match->GetActualTime_ms();
        const unsigned long earlier = std::min(buffer.prepareTime, buffer.stopTime + 1000UL);
        if (now <= earlier && now < buffer.prepareTime) {
          buffer.prepareTime = earlier;
          buffer.startTime = std::min(buffer.startTime, earlier + 1000UL);
        }
      }'''),
    ])

    # A manager fixture must have both teams CPU-controlled from initialization.
    edit(root, "src/onthepitch/match.cpp", [
        ("  teams[1]->DeleteHumanGamers();\n\n  // add new", r'''  teams[1]->DeleteHumanGamers();
  if (std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE")) return;

  // add new'''),
    ])
    edit(root, "src/onthepitch/AIsupport/AIfunctions.cpp", [
        ("  desiredDirection = forceFieldMovement.GetNormalized(player->GetDirectionVec());", r'''  // Only a controlled outfield ball carrier in open play can take this branch.
  // Preserve the force-field result whenever a defender blocks the corridor.
  if (AITactics::ShortMatchAttackEnabled() && player->HasUniquePossession() &&
      match->IsInPlay() && !match->IsInSetPiece() &&
      player->GetFormationEntry().role != e_PlayerRole_GK) {
    const Vector3 forward(-side, 0, 0);
    const Vector3 towardGoal = (oppGoalPos-myPos).GetNormalized(forward);
    float nearestOpponent=100.0f, nearestAhead=100.0f, lateralClearance=100.0f;
    const float remaining=pitchHalfW+side*myPos.coords[0];
    for (const auto& opp : opponentPlayerImages) {
      const Vector3 relative=opp.position+opp.movement*future_sec-myPos;
      nearestOpponent=std::min(nearestOpponent,relative.GetLength());
      const float ahead=relative.coords[0]*towardGoal.coords[0]+relative.coords[1]*towardGoal.coords[1];
      const float lateral=std::abs(relative.coords[0]*towardGoal.coords[1]-relative.coords[1]*towardGoal.coords[0]);
      if(ahead>0 && ahead<7.0f) {
        lateralClearance=std::min(lateralClearance,lateral);
        if(lateral<2.2f) nearestAhead=std::min(nearestAhead,ahead);
      }
    }
    if (remaining>8.0f && AITactics::ClearForwardCorridor(
        towardGoal.coords[0]*-side*5.0f,pitchHalfH-std::abs(myPos.coords[1]+towardGoal.coords[1]*5.0f),
        nearestAhead,lateralClearance,nearestOpponent)) {
      // Blend, not teleport or force an animation. Normal velocity limits still apply.
      forceFieldMovement=forceFieldMovement*0.45f+towardGoal*sprintVelocity*0.55f;
    }
  }
  desiredDirection = forceFieldMovement.GetNormalized(player->GetDirectionVec());'''),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("  float oneTouchIsHard = 0.0f;", "  const auto onBallStart = commandQueue.size();\n  float oneTouchIsHard = 0.0f;"),
        ("      commandQueue.push_back(command);\n    }\n  }\n\n  e_Velocity enumVelocity", r'''      const Vector3 toGoal=Vector3(pitchHalfW * -team->GetSide(),0,0)-player->GetPosition();
      const float distance=toGoal.GetLength();
      const float angle=distance>0.01f ? toGoal.coords[0]*-team->GetSide()/distance : 0.0f;
      // Prioritize an already accepted, high-quality shot over ordinary passing.
      // Animation selection may still reject it and fall through to the existing queue.
      if(AITactics::ShortMatchAttackEnabled() &&
         AITactics::PrioritizeGoodShot(distance,angle,odds,CastPlayer()->HasUniquePossession()))
        commandQueue.insert(commandQueue.begin()+onBallStart,command);
      else
        commandQueue.push_back(command);
    }
  }

  e_Velocity enumVelocity'''),
    ])
