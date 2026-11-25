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
// All progress values are expressed relative to the attacking direction.
inline bool EligibleProgressiveRun(float mindset, float progress, float distance,
                                  float onsideMargin) {
  return mindset >= 0.45f && progress >= -3.0f && progress <= 32.0f &&
         distance >= 5.0f && distance <= 36.0f && onsideMargin >= 0.8f;
}
inline bool EligibleRunningPass(float progress, float distance, float forwardSpeed,
                                float onsideMargin, float odds) {
  return progress >= 4.0f && distance >= 9.0f && distance <= 32.0f &&
         forwardSpeed >= 1.5f && onsideMargin >= 0.8f && odds >= 0.65f;
}
inline float ProgressiveRunCost(float probeDistance, float mindset, float lateralGap) {
  return probeDistance + 6.0f*(1.0f-std::max(0.0f,std::min(1.0f,mindset)))
         - std::min(10.0f,std::max(0.0f,lateralGap))*0.4f;
}
inline bool WideDeliveryZone(float goalDepth, float lateral) {
  return goalDepth >= 1.0f && goalDepth <= 24.0f && lateral >= 13.0f && lateral <= 34.0f;
}
inline bool EligibleBoxDelivery(float recipientDepth, float recipientLateral, float distance,
                                float onsideMargin, float odds) {
  return recipientDepth >= 3.0f && recipientDepth <= 16.0f && recipientLateral <= 11.0f &&
         distance >= 5.0f && distance <= 32.0f && onsideMargin >= 0.8f && odds >= 0.65f;
}
inline bool EligibleAerialDelivery(float recipientDepth, float recipientLateral, float distance,
                                   float onsideMargin, float odds) {
  // Native high-pass odds include a fixed 0.4 penalty. 0.54 means <=0.06 additional danger.
  return recipientDepth >= 3.0f && recipientDepth <= 16.0f && recipientLateral <= 11.0f &&
         distance >= 10.0f && distance <= 32.0f && onsideMargin >= 0.8f && odds >= 0.54f;
}
inline bool EligibleCutback(float senderDepth, float recipientDepth, float distance, float odds) {
  return senderDepth <= 10.0f && recipientDepth >= senderDepth+2.0f &&
         distance <= 20.0f && odds >= 0.65f;
}
inline bool EligibleDistanceShot(float distance, float angle, float skill, float odds) {
  return distance >= 17.0f && distance <= 26.0f && angle >= 0.88f && skill >= 0.70f && odds >= 0.78f;
}
// Time estimates are milliseconds, geometry metres. Avoid high balls, byline
// exits, opponent races and teammates who can already clear the ball.
inline bool SafeKeeperClaim(float depth, float lateral, float height, float distance,
                            int keeperEta, int nearestRivalEta, int nearestMateEta,
                            bool loose, bool shot) {
  return loose && !shot && depth>=1.0f && depth<=15.0f && lateral<=18.0f &&
         height>=0.0f && height<=1.0f && distance>=1.1f && distance<=10.0f &&
         keeperEta>=0 && keeperEta<=1300 && nearestRivalEta>=keeperEta+450 &&
         nearestMateEta>=keeperEta+200;
}
inline bool KeepCentralCover(bool centreBack, bool primary, bool secondary,
                             bool opponentHasBall, int goalSideCover, float ownGoalDepth) {
  return centreBack && !primary && !secondary && opponentHasBall &&
         goalSideCover<=1 && ownGoalDepth<=36.0f;
}
inline int CoordinatedHunters(float ownGoalDepth, int goalSideCover) {
  return (ownGoalDepth<=32.0f || goalSideCover<=1)?1:2;
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

    # Retain the ordinary runner selector as baseline. Prefer eligible midfielders/forwards
    # in a passable lane when a teammate has controlled possession.
    edit(root, "src/onthepitch/teamAIcontroller.cpp", [
        ("  float closestDistance = 10000.0f;\n  for (const auto& candidate : team->GetAllPlayers()) {", r'''  float closestDistance = 10000.0f;
  const bool progressive = AITactics::ShortMatchAttackEnabled() &&
      possessionPlayer->HasUniquePossession() && team->GetHumanGamerCount()==0;
  const float forward = -team->GetSide();
  const float offside = progressive ? AI_GetOffsideLine(team->GetMatch(),team->GetMatch()->GetMentalImage(0),abs(team->GetID()-1))*forward : 0.0f;
  for (const auto& candidate : team->GetAllPlayers()) {'''),
        ("    const float distance = (candidate->GetPosition() - offenseFocusPos).GetLength();\n    if (distance < closestDistance) {", r'''    float distance = (candidate->GetPosition() - offenseFocusPos).GetLength();
    if (progressive) {
      const Vector3 delta=candidate->GetPosition()-possessionPlayer->GetPosition();
      const float mindset=AI_GetMindSet(candidate->GetDynamicFormationEntry().role);
      const float margin=offside-candidate->GetPosition().coords[0]*forward;
      if (!AITactics::EligibleProgressiveRun(mindset,delta.coords[0]*forward,delta.GetLength(),margin)) continue;
      distance=AITactics::ProgressiveRunCost(distance,mindset,std::abs(delta.coords[1]));
    }
    if (distance < closestDistance) {'''),
        ("    if (possPlayer) {\n      forwardSupportPlayer =\n          AI_GetClosestPlayer(team,", r'''    if (AITactics::ShortMatchAttackEnabled() && possPlayer && possPlayer->HasUniquePossession() &&
        team->GetHumanGamerCount()==0) {
      // Choose a second outlet, distinct from the committed runner. Keep centre backs
      // and holding midfielders in their ordinary support shape.
      forwardSupportPlayer=nullptr;
      float best=10000.0f;
      const float forward=-team->GetSide();
      const float line=AI_GetOffsideLine(match,match->GetMentalImage(0),abs(team->GetID()-1))*forward;
      for (const auto& mate:team->GetAllPlayers()) {
        if(!mate->IsActive() || mate.get()==possPlayer ||
           (mate.get()==attackingRunPlayer && endApplyAttackingRun_ms>match->GetActualTime_ms())) continue;
        const Vector3 delta=mate->GetPosition()-possPlayer->GetPosition();
        const float mindset=AI_GetMindSet(mate->GetDynamicFormationEntry().role);
        if(!AITactics::EligibleProgressiveRun(mindset,delta.coords[0]*forward,delta.GetLength(),
             line-mate->GetPosition().coords[0]*forward)) continue;
        const float cost=std::abs(delta.coords[0]*forward-8.0f)+std::abs(std::abs(delta.coords[1])-9.0f);
        if(cost<best){best=cost;forwardSupportPlayer=mate.get();}
      }
    } else if (possPlayer) {
      forwardSupportPlayer =
          AI_GetClosestPlayer(team,'''),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("  float bestTotalRating = 0.0f;\n  MateRating bestMateRating;", r'''  const bool runningPassEnabled=AITactics::ShortMatchAttackEnabled() &&
      CastPlayer()->HasUniquePossession() && !team->GetHumanGamerCount() &&
      CastPlayer()->GetFormationEntry().role!=e_PlayerRole_GK;
  const float attackForward=-team->GetSide();
  const float passOffside=runningPassEnabled ? AI_GetOffsideLine(match,_mentalImage,abs(team->GetID()-1))*attackForward : 0.0f;
  float bestTotalRating = 0.0f;
  MateRating bestMateRating;'''),
        ("      if (progressiveCandidate || supportCandidate) {", r'''      bool runningCandidate=false;
      float runningOdds=0.0f;
      if(runningPassEnabled && mates.at(i)->GetFormationEntry().role!=e_PlayerRole_GK) {
        const Vector3 delta=mates.at(i)->GetPosition()-player->GetPosition();
        const float progress=delta.coords[0]*attackForward;
        const float distance=delta.GetLength();
        const float speed=mates.at(i)->GetMovement().coords[0]*attackForward;
        const float margin=passOffside-mates.at(i)->GetPosition().coords[0]*attackForward;
        if(AITactics::EligibleRunningPass(progress,distance,speed,margin,1.0f)) {
          runningOdds=_GetPassingOdds(mates.at(i),e_FunctionType_LongPass,opponentPlayerImages);
          runningCandidate=AITactics::EligibleRunningPass(progress,distance,speed,margin,runningOdds);
        }
      }
      if (progressiveCandidate || supportCandidate || runningCandidate) {'''),
        ("        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +", r'''        // A running pass is the native lead/long pass, not an invented new ball action.
        // Only prefer it when its existing interception score is competitive.
        if(runningCandidate && runningOdds>=mateRating.passRating-0.08f){
          mateRating.passType=e_FunctionType_LongPass;
          mateRating.passRating=runningOdds;
          mateRating.supportRating+=0.20f;
        }
        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +'''),
    ])

    # Short-match wide attacks: only the two assigned attacking outlets receive special
    # targets. Existing offside clamp, formation/repulsion and physical movement stay intact.
    edit(root, "src/onthepitch/teamAIcontroller.cpp", [
        ("    if (!AITactics::IsAutomaticRunnerEligible(\n            candidate->IsActive(),", "    if (!candidate->IsActive()) continue;\n    if (!AITactics::IsAutomaticRunnerEligible(\n            candidate->IsActive(),"),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("  // stay away from opponents\n  std::vector<Player*> opponents;", r'''  // Distinct box targets only while a wide teammate controls possession.
  // A ball-side runner attacks the near-post channel; the second outlet
  // supports centrally/far-side. No extra players are committed.
  if (AITactics::ShortMatchAttackEnabled() && !team->GetHumanGamerCount() &&
      designatedPlayer != CastPlayer() && designatedPlayer->HasUniquePossession() &&
      dynamicMindSet >= 0.45f && AITactics::WideDeliveryZone(
          pitchHalfW + mainManPos.coords[0]*team->GetSide(), std::abs(mainManPos.coords[1]))) {
    const bool nearRun=adaptedMakeRun;
    const bool secondOutlet=player==team->GetController()->GetForwardSupportPlayer();
    if (nearRun || secondOutlet) {
      const float lateralSign=mainManPos.coords[1]>=0 ? 1.0f : -1.0f;
      const float depth=nearRun ? 7.0f : 13.0f;
      const float y=nearRun ? lateralSign*5.5f : -lateralSign*6.0f;
      ForceSpot boxSpot;
      boxSpot.origin=Vector3((pitchHalfW-depth)*-team->GetSide(),y,0);
      boxSpot.magnetType=e_MagnetType_Attract;
      boxSpot.decayType=e_DecayType_Constant;
      boxSpot.power=nearRun ? 1.6f : 1.25f;
      forceField.push_back(boxSpot);
    }
  }

  // stay away from opponents
  std::vector<Player*> opponents;'''),
        ("      bool runningCandidate=false;\n      float runningOdds=0.0f;", r'''      bool runningCandidate=false;
      float runningOdds=0.0f;
      bool deliveryCandidate=false;
      float deliveryOdds=0.0f;
      e_FunctionType deliveryType=e_FunctionType_ShortPass;
      if(runningPassEnabled && AITactics::WideDeliveryZone(
           pitchHalfW-player->GetPosition().coords[0]*attackForward,std::abs(player->GetPosition().coords[1])) &&
           mates.at(i)->GetFormationEntry().role!=e_PlayerRole_GK){
        const float senderDepth=pitchHalfW-player->GetPosition().coords[0]*attackForward;
        const auto pos=mates.at(i)->GetPosition();
        const float recipientDepth=pitchHalfW-pos.coords[0]*attackForward;
        const float distance=(pos-player->GetPosition()).GetLength();
        const float margin=passOffside-pos.coords[0]*attackForward;
        const float lateral=std::abs(pos.coords[1]);
        if(AITactics::EligibleBoxDelivery(recipientDepth,lateral,distance,margin,1.0f)){
          const float ground=_GetPassingOdds(mates.at(i),e_FunctionType_ShortPass,opponentPlayerImages);
          const float aerial=_GetPassingOdds(mates.at(i),e_FunctionType_HighPass,opponentPlayerImages);
          if(AITactics::EligibleCutback(senderDepth,recipientDepth,distance,ground) ||
             (distance<=20.0f && ground>=0.72f && ground>=aerial)){
            deliveryOdds=ground;
            deliveryType=e_FunctionType_ShortPass;
          }else{
            deliveryOdds=aerial;
            deliveryType=e_FunctionType_HighPass;
          }
          deliveryCandidate=deliveryType==e_FunctionType_HighPass
              ? AITactics::EligibleAerialDelivery(recipientDepth,lateral,distance,margin,deliveryOdds)
              : AITactics::EligibleBoxDelivery(recipientDepth,lateral,distance,margin,deliveryOdds);
        }
      }'''),
        ("      if (progressiveCandidate || supportCandidate || runningCandidate) {", "      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate) {"),
        ("        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +", r'''        if(deliveryCandidate && deliveryOdds>=mateRating.passRating-0.05f){
          mateRating.passRating=deliveryOdds;
          mateRating.passType=deliveryType;
          mateRating.supportRating+=0.28f;
        }
        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +'''),
        ("  if (idealShotPosFactor > 0.1f) {", r'''  const Vector3 shotVector=Vector3(pitchHalfW * -team->GetSide(),0,0)-player->GetPosition();
  const float shotDistance=shotVector.GetLength();
  const float shotAngle=shotDistance>0.01f ? shotVector.coords[0]*-team->GetSide()/shotDistance : 0.0f;
  const bool distanceProbe=AITactics::ShortMatchAttackEnabled() &&
      CastPlayer()->HasUniquePossession() && CastPlayer()->GetFormationEntry().role!=e_PlayerRole_GK &&
      AITactics::EligibleDistanceShot(shotDistance,shotAngle,player->GetStat("technical_shot"),1.0f);
  if (idealShotPosFactor > 0.1f || distanceProbe) {'''),
        ("    if (odds + random(0.0f, 0.28f) > AITactics::ShotOddsThreshold()) {", r'''    const bool distanceShot=distanceProbe &&
        AITactics::EligibleDistanceShot(shotDistance,shotAngle,player->GetStat("technical_shot"),odds);
    if ((idealShotPosFactor > 0.1f || distanceShot) &&
        odds + random(0.0f, 0.28f) > AITactics::ShotOddsThreshold()) {'''),
    ])

    # Independent goalkeeper collection decision, retaining the native save and
    # pickup animation paths. The new behaviour is opt-in with the short-match profile.
    edit(root, "src/onthepitch/player/controller/strategies/offtheball/goalie_default.hpp", [
        ("  bool IsBallBoundForGoal() const { return ballBoundForGoal; }", "  bool IsBallBoundForGoal() const { return ballBoundForGoal; }\n  bool IsClaimingLooseBall() const { return claimingLooseBall; }"),
        ("  bool ballBoundForGoal;", "  bool claimingLooseBall = false;\n  bool ballBoundForGoal;"),
    ])
    edit(root, "src/onthepitch/player/controller/strategies/offtheball/goalie_default.cpp", [
        ('#include "goalie_default.hpp"', '#include "goalie_default.hpp"\n#include "../../../../aitactics.hpp"'),
        ("  // base position\n  float lineDistance", "  claimingLooseBall=false;\n  // base position\n  float lineDistance"),
        ("  direction = targetPos - player->GetPosition();", r'''  // Leave actual shot interception and hand-contact rules to the existing engine.
  if (AITactics::ShortMatchAttackEnabled() && match->IsInPlay() && !match->IsInSetPiece() &&
      !match->GetBallRetainer() && !team->GetHumanGamerCount() &&
      !team->HasUniquePossession() && !controller->GetOppTeam()->HasUniquePossession()) {
    CalculateIfBallIsBoundForGoal(mentalImage);
    const auto ballNow=mentalImage->GetBallPrediction(0);
    const auto candidate=mentalImage->GetBallPrediction(400);
    const auto ground=candidate.Get2D();
    const float distance=(ground-player->GetPosition()).GetLength();
    const float depth=pitchHalfW-ground.coords[0]*team->GetSide();
    // Cheap spatial gate before the native arrival estimator, to avoid a per-tick
    // full team search when the ball is on the other half.
    if (AITactics::SafeKeeperClaim(depth,std::abs(ground.coords[1]),candidate.coords[2],
        distance,0,2000,2000,true,IsBallBoundForGoal()) &&
        ballNow.coords[2]<=1.0f &&
        pitchHalfW-ballNow.coords[0]*team->GetSide()>=0.5f &&
        pitchHalfW-ballNow.coords[0]*team->GetSide()<=16.5f &&
        std::abs(ballNow.coords[1])<=20.15f) {
      std::vector<Player*> rivals,mates;
      controller->GetOppTeam()->GetActivePlayers(rivals);
      team->GetActivePlayers(mates);
      const int keeperEta=static_cast<int>(AI_GetTimeNeededForDistance_ms(
          player->GetPosition(),player->GetMovement(),ground,player->GetMaxVelocity(),false,-1,false).usual_ms);
      // Lower-bound competing arrival times at the same intercept point.
      // A simple straight-line sprint is deliberately optimistic for rivals.
      const auto earliest=[&](const std::vector<Player*>& list) {
        int result=100000;
        for (auto* other:list) if(other!=CastPlayer() && other->IsActive()) {
          const float d=(ground-other->GetPosition()).GetLength();
          const float speed=std::max(0.1f,other->GetMaxVelocity());
          result=std::min(result,static_cast<int>(std::max(0.0f,d-0.9f)/speed*1000.0f));
        }
        return result;
      };
      if (AITactics::SafeKeeperClaim(depth,std::abs(ground.coords[1]),candidate.coords[2],
          distance,keeperEta,earliest(rivals),earliest(mates),true,false)) {
        targetPos=ground;
        maxVelocity=sprintVelocity;
        claimingLooseBall=true;
      }
    }
  }
  direction = targetPos - player->GetPosition();'''),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("    goalieStrategy->RequestInput(keeperMentalImage, manualMovementDirection,\n                                 manualMovementVelocityFloat);", r'''    goalieStrategy->RequestInput(keeperMentalImage, manualMovementDirection,
                                 manualMovementVelocityFloat);
    if (static_cast<GoalieDefaultStrategy*>(goalieStrategy)->IsClaimingLooseBall())
      manualMovement=true;'''),
        ("        int huntingPlayersNum = 3;  // was 2; includes players with man marking id", r'''        int huntingPlayersNum = 3;  // baseline
        if(AITactics::ShortMatchAttackEnabled() && !team->GetHumanGamerCount()){
          std::vector<Player*> mates;
          team->GetActivePlayers(mates);
          int cover=0;
          const float side=team->GetSide();
          const float ballX=_mentalImage->GetBallPrediction(0).coords[0]*side;
          for(auto* mate:mates)if(mate!=CastPlayer() && mate!=team->GetGoalie() &&
              mate->GetPosition().coords[0]*side>=ballX+2.0f &&
              std::abs(mate->GetPosition().coords[1])<=18.0f)++cover;
          huntingPlayersNum=AITactics::CoordinatedHunters(pitchHalfW-ballX,cover);
          const bool secondary=team->GetController()->GetEndApplyTeamPressure_ms()>match->GetActualTime_ms() &&
              team->GetController()->GetTeamPressurePlayer()==player;
          if(AITactics::KeepCentralCover(CastPlayer()->GetFormationEntry().role==e_PlayerRole_CB,
              player==team->GetDesignatedTeamPossessionPlayer(),secondary,
              opp && opp->HasUniquePossession(),cover,pitchHalfW-ballX))
            huntingPlayersNum=0;
        }'''),
        ("        AI_GetClosestPlayers(team, opp->GetPosition() + opp->GetMovement() * 0.1f, false,\n                             closestPlayers, huntingPlayersNum);", r'''        if(huntingPlayersNum>0)
          AI_GetClosestPlayers(team, opp->GetPosition() + opp->GetMovement() * 0.1f, false,
                               closestPlayers, huntingPlayersNum);'''),
    ])
    edit(root, "src/onthepitch/teamAIcontroller.cpp", [
        ("  prevTeamHasPossession = teamHasPossession;\n\n  // trigger attacking runs", r'''  if(AITactics::ShortMatchAttackEnabled() && !team->GetHumanGamerCount() &&
      prevTeamHasPossession && !teamHasPossession){
    // Cancel stale offensive assignments as soon as possession is lost.
    endApplyAttackingRun_ms=match->GetActualTime_ms();
    attackingRunPlayer=nullptr;
    forwardSupportPlayer=nullptr;
  }
  prevTeamHasPossession = teamHasPossession;

  // trigger attacking runs'''),
        ("      const float pressureRating = distance + rolePenalty;", r'''      float pressureRating = distance + rolePenalty;
      if(AITactics::ShortMatchAttackEnabled() && !team->GetHumanGamerCount() &&
          candidate->GetFormationEntry().role==e_PlayerRole_CB){
        int cover=0;
        const float side=team->GetSide();
        const float depth=pitchHalfW-opponentPos.coords[0]*side;
        for(auto* mate:candidates)if(mate!=candidate && mate!=primaryDefender &&
            mate!=team->GetGoalie() && mate->GetPosition().coords[0]*side>=opponentPos.coords[0]*side+2.0f &&
            std::abs(mate->GetPosition().coords[1])<=18.0f)++cover;
        if(AITactics::KeepCentralCover(true,false,false,opp->HasUniquePossession(),cover,depth))
          continue;
        pressureRating+=3.0f;
      }'''),
        ("  if (previousPresser &&\n      AITactics::ShouldKeepPressurePlayer(previousPressureRating, bestPressureRating))", "  if (previousPresser && previousPressureRating < 10000.0f &&\n      AITactics::ShouldKeepPressurePlayer(previousPressureRating, bestPressureRating))"),
    ])
