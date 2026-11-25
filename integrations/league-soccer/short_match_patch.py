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
inline float ControlSkill(float dribble, float control, float agility, float balance) {
  const auto c=[](float v){return std::max(0.0f,std::min(1.0f,v));};
  return .35f*c(dribble)+.30f*c(control)+.20f*c(agility)+.15f*c(balance);
}
inline bool CanAttemptEvasion(float skill,float nearest,float goalDepth,float ballGap) {
  return skill>=.60f && nearest>=1.0f && nearest<=4.5f && goalDepth>=8.0f && ballGap<=1.4f;
}
inline float EvasionScore(float progress,float clearance,float turnAlignment,float skill) {
  if(clearance<1.25f || progress<0.4f || turnAlignment<-.15f)return -100.0f;
  return progress*.45f+std::min(clearance,5.0f)*.8f+turnAlignment*(1.2f-.7f*skill);
}
inline float PressuredCarryCap(float skill,float nearest,float ballGap) {
  if(nearest>4.5f && ballGap<1.4f)return 1.0f;
  return std::max(.45f,std::min(.85f,.48f+.35f*skill));
}
inline float FirstTouchCost(float mismatch,float shortPass,float ballControl,float calmness) {
  const auto c=[](float v){return std::max(0.0f,std::min(1.0f,v));};
  return c(mismatch)*(1.0f-.45f*c(shortPass)-.25f*c(ballControl)-.10f*c(calmness));
}
inline bool SafePressureOutlet(float nearest,float distance,float receiverSpace,float odds,float margin) {
  return nearest<=3.0f && distance>=3.0f && distance<=15.0f && receiverSpace>=.55f && odds>=.72f && margin>=.8f;
}
// A bounded give-and-go state driven by actual pass contacts and controlled receipts.
// IDs are native runtime identities, never roster positions.
struct CombinationState {
  int passer=-1, receiver=-1, stage=0;
  unsigned long started=0, lastPass=0, expires=0, cooldown=0;
  unsigned long attempts=0, returned=0, completed=0;
  void Clear(unsigned long now) {
    if(stage) cooldown=now+1800;
    passer=receiver=-1;stage=0;started=lastPass=expires=0;
  }
  bool Begin(int a,int b,unsigned long now) {
    if(stage || now<cooldown || a<0 || b<0 || a==b)return false;
    passer=a;receiver=b;stage=1;started=lastPass=now;expires=now+2800;
    ++attempts;return true;
  }
  void Observe(int owner,bool expectedTouch,bool interrupted,unsigned long now) {
    if(!stage)return;
    if(interrupted || now>=expires || now<lastPass){Clear(now);return;}
    if(now<=lastPass || !expectedTouch || owner<0)return;
    if(stage==1 && owner==receiver){stage=2;return;}
    if(stage==3 && owner==passer){++completed;Clear(now);return;}
    if((stage==1 && owner!=passer) || (stage==2 && owner!=receiver) ||
       (stage==3 && owner!=receiver))Clear(now);
  }
  bool ReturnPass(int a,int b,unsigned long now) {
    if(stage!=2 || a!=receiver || b!=passer || now>=expires || now<lastPass)return false;
    stage=3;lastPass=now;expires=now+1700;++returned;return true;
  }
};
inline bool StartCombination(float mindset,float skill,float distance,float progress,
                             float ballDepth,float margin) {
  return mindset>=.45f && skill>=.58f && distance>=4.0f && distance<=14.0f &&
         progress>=-3.0f && progress<=10.0f && ballDepth>=13.0f && ballDepth<=42.0f &&
         margin>=1.0f;
}
inline bool SafeReturnPass(float progress,float distance,float margin,float odds) {
  return progress>=2.0f && distance>=3.0f && distance<=20.0f && margin>=.8f && odds>=.72f;
}
// Track actual shot -> accidental opponent touch -> controlled recovery -> next shot.
struct ReboundState {
  int stage=0,recoverer=-1;
  unsigned long shotAt=0,deflectedAt=0,expires=0;
  unsigned long deflections=0,recoveries=0,followupShots=0;
  void Clear(){stage=0;recoverer=-1;shotAt=deflectedAt=expires=0;}
  void Shot(int id,unsigned long now){
    if(stage==3 && id==recoverer && now<expires)++followupShots;
    Clear();stage=1;shotAt=now;expires=now+2200;
  }
  void Deflect(unsigned long touch,unsigned long now){
    if(stage==1 && touch>shotAt && touch<=now && now<expires){
      stage=2;deflectedAt=touch;expires=now+2200;++deflections;
    }
  }
  void Observe(bool interrupted,bool rivalControl,int controlledOwner,
               unsigned long ownerTouch,unsigned long now){
    if(!stage)return;
    if(interrupted || rivalControl || now>=expires){Clear();return;}
    if(stage==2 && controlledOwner>=0 && ownerTouch>deflectedAt){
      stage=3;recoverer=controlledOwner;expires=now+1500;++recoveries;
    }else if(stage==3 && controlledOwner>=0 && controlledOwner!=recoverer)Clear();
  }
};
inline bool ReboundZone(float depth,float lateral,float height){
  return depth>=.5f && depth<=22.0f && lateral<=20.15f && height>=0.0f && height<=2.0f;
}
inline bool ReboundSupportEligible(float mindset,float distance,float onsideMargin){
  return mindset>=.45f && distance>=3.0f && distance<=16.0f && onsideMargin>=1.0f;
}
inline bool PrioritizeReboundShot(float distance,float angle,float odds,float control,float skill){
  // A settled rebound can justify a slightly earlier shot, but only for a skilled finisher.
  return distance>=2.0f && distance<=13.0f && angle>=.60f && odds>=.58f && control>=.65f && skill>=.65f;
}
// Fixed-duration pilot: regulation time includes dead balls and halftime.
inline bool FixedDurationEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_FIXED_DURATION");
    return value && std::strcmp(value,"1")==0;
  }();
  return enabled;
}
struct FixedDurationClock {
  bool started=false,half=false,finished=false;
  unsigned long start=0;
  void Start(unsigned long now){if(!started){started=true;start=now;}}
  unsigned long Elapsed(unsigned long now) const {
    return started && now>=start?std::min(300000UL,now-start):0UL;
  }
  unsigned long Nominal(unsigned long now) const {return Elapsed(now)*18UL;}
  bool HalfDue(unsigned long now) const {return started&&!half&&Elapsed(now)>=150000UL;}
  bool FullDue(unsigned long now) const {return started&&!finished&&Elapsed(now)>=300000UL;}
};
// Isolated comparison against the previous short-match decision policy.
inline bool FinalThirdRetentionEnabled() {
  static const bool enabled=[]{
    const char* v=std::getenv("TRIBUN_NATIVE_FINAL_THIRD_RETENTION");
    return v && std::strcmp(v,"1")==0;
  }();
  return ShortMatchAttackEnabled() && enabled;
}
inline bool FinalThirdControlled(float depth,bool openPlay,bool controlled,bool outfield){
  return openPlay && controlled && outfield && depth>=1.0f && depth<=36.6667f;
}
inline bool SafeGroundOutlet(float progress,float distance,float receiverSpace,
                             float onsideMargin,float odds){
  return progress>=-3.0f && progress<=18.0f && distance>=3.0f && distance<=18.0f &&
      receiverSpace>=.55f && onsideMargin>=1.2f && odds>=.76f;
}
inline bool RetentionPassAllowed(float odds,float pressureDistance){
  // Under immediate pressure preserve the native escape/clearance choices.
  return pressureDistance<=2.2f || odds>=.52f;
}
inline float RetentionRiskCost(float odds,float pressureDistance){
  if(pressureDistance<=2.2f)return 0.0f;
  return std::max(0.0f,.76f-odds)*1.1f;
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

    # Individual pressure response: candidate directions are scored against predicted
    # defender positions; no new skill animation, forced tackle outcome or stat boost.
    edit(root, "src/onthepitch/AIsupport/AIfunctions.cpp", [
        ("  desiredVelocity = RangeVelocity(desiredVelocity);\n}\n\nVector3 AI_GetForceFieldMovement", r'''  if(AITactics::ShortMatchAttackEnabled() && player->HasUniquePossession() &&
      match->IsInPlay() && !match->IsInSetPiece() && !team->GetHumanGamerCount() &&
      player->GetFormationEntry().role!=e_PlayerRole_GK){
    const float skill=AITactics::ControlSkill(player->GetStat("technical_dribble"),
        player->GetStat("technical_ballcontrol"),player->GetStat("physical_agility"),
        player->GetStat("physical_balance"));
    float nearest=100.0f;
    for(const auto& opp:opponentPlayerImages)
      nearest=std::min(nearest,(opp.position-myPos).GetLength());
    const float ballGap=(mentalImage->GetBallPrediction(0).Get2D()-myPos).GetLength();
    const float depth=pitchHalfW+side*myPos.coords[0];
    if(AITactics::CanAttemptEvasion(skill,nearest,depth,ballGap)){
      const Vector3 forward(-side,0,0);
      Vector3 best=desiredDirection;
      float bestScore=-100.0f;
      // Include current decision, so a new angle must actually beat it.
      const Vector3 choices[]={desiredDirection,forward,forward.GetRotated2D(.42f),
          forward.GetRotated2D(-.42f),forward.GetRotated2D(.84f),forward.GetRotated2D(-.84f)};
      for(const auto& dir:choices){
        const auto endpoint=myPos+dir*3.0f;
        if(std::abs(endpoint.coords[0])>pitchHalfW-1.5f ||
           std::abs(endpoint.coords[1])>pitchHalfH-1.5f)continue;
        float clearance=100.0f;
        for(const auto& opp:opponentPlayerImages){
          // Evaluate the middle and end of the projected carry against defenders.
          const auto mid=myPos+dir*1.5f;
          clearance=std::min(clearance,(mid-(opp.position+opp.movement*.25f)).GetLength());
          clearance=std::min(clearance,(endpoint-(opp.position+opp.movement*.5f)).GetLength());
        }
        const auto facing=player->GetDirectionVec();
        const float alignment=dir.coords[0]*facing.coords[0]+dir.coords[1]*facing.coords[1];
        const float score=AITactics::EvasionScore(dir.coords[0]*-side*3.0f,clearance,alignment,skill);
        if(score>bestScore){bestScore=score;best=dir;}
      }
      if(bestScore>-99.0f)desiredDirection=best.GetNormalized(desiredDirection);
    }
    // Carry conservatively when contested or when the ball has separated from the feet.
    // This is a movement preference, not a change to the actual ball-control physics.
    desiredVelocity=std::min(desiredVelocity,sprintVelocity*
        AITactics::PressuredCarryCap(skill,nearest,ballGap));
  }
  desiredVelocity = RangeVelocity(desiredVelocity);
}

Vector3 AI_GetForceFieldMovement'''),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ('  oneTouchIsHard =\n      movementDiff - CastPlayer()->GetStat("technical_shortpass") * movementDiff * 0.8f;', r'''  oneTouchIsHard =
      movementDiff - CastPlayer()->GetStat("technical_shortpass") * movementDiff * 0.8f;
  if(AITactics::ShortMatchAttackEnabled() && !team->GetHumanGamerCount())
    oneTouchIsHard=AITactics::FirstTouchCost(movementDiff,
        CastPlayer()->GetStat("technical_shortpass"),CastPlayer()->GetStat("technical_ballcontrol"),
        CastPlayer()->GetStat("mental_calmness"));'''),
        ("  const float passOffside=runningPassEnabled ? AI_GetOffsideLine(match,_mentalImage,abs(team->GetID()-1))*attackForward : 0.0f;", r'''  const float passOffside=runningPassEnabled ? AI_GetOffsideLine(match,_mentalImage,abs(team->GetID()-1))*attackForward : 0.0f;
  float nearestPressure=100.0f;
  if(runningPassEnabled)for(const auto& opp:opponentPlayerImages)
    nearestPressure=std::min(nearestPressure,(opp.position-player->GetPosition()).GetLength());'''),
        ("      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate) {", r'''      bool pressureOutlet=false;
      float pressureOdds=0.0f;
      if(runningPassEnabled && nearestPressure<=3.0f && mates.at(i)->GetFormationEntry().role!=e_PlayerRole_GK){
        const float distance=(mates.at(i)->GetPosition()-player->GetPosition()).GetLength();
        const float margin=passOffside-mates.at(i)->GetPosition().coords[0]*attackForward;
        if(AITactics::SafePressureOutlet(nearestPressure,distance,mateSit.spaceRating,1.0f,margin)){
          pressureOdds=_GetPassingOdds(mates.at(i),e_FunctionType_ShortPass,opponentPlayerImages);
          pressureOutlet=AITactics::SafePressureOutlet(nearestPressure,distance,mateSit.spaceRating,pressureOdds,margin);
        }
      }
      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet) {'''),
        ("        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +", r'''        if(pressureOutlet && pressureOdds>=mateRating.passRating-.08f){
          mateRating.passRating=pressureOdds;
          mateRating.passType=e_FunctionType_ShortPass;
          mateRating.supportRating+=.22f;
        }
        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +'''),
    ])

    # Track real ball contacts, not the controller's speculative command queue.
    edit(root, "src/onthepitch/teamAIcontroller.hpp", [
        ('#include "base/properties.hpp"', '#include "base/properties.hpp"\n#include "aitactics.hpp"'),
        ("  void ApplyAttackingRun(Player* manualPlayer = 0);", r'''  void ApplyAttackingRun(Player* manualPlayer = 0);
  void TribunPassContact(Player* passer, Player* receiver, bool shortPass);
  Player* TribunReturnTarget(Player* receiver);
  bool TribunCombinationRunner(Player* player) const;
  const AITactics::CombinationState& GetTribunCombination() const { return tribunCombination; }'''),
        ("  Player* forwardSupportPlayer;", "  AITactics::CombinationState tribunCombination;\n  Player* forwardSupportPlayer;"),
    ])
    edit(root, "src/onthepitch/teamAIcontroller.cpp", [
        ("  CalculateSituation();\n  if (!teamHasPossession)", r'''  CalculateSituation();
  if (tribunCombination.stage) {
    const auto now=match->GetActualTime_ms();
    auto* first=team->GetPlayer(tribunCombination.passer);
    auto* second=team->GetPlayer(tribunCombination.receiver);
    auto* own=team->GetDesignatedTeamPossessionPlayer();
    auto* rival=match->GetTeam(abs(team->GetID()-1));
    const bool interrupted=!match->IsInPlay() || match->IsInSetPiece() ||
        match->GetBallRetainer() || oppTeamHasUniquePossession ||
        rival->GetLastTouchTime_ms()>=tribunCombination.started ||
        !first || !second || !first->IsActive() || !second->IsActive();
    const bool confirmed=own && own->HasUniquePossession() &&
        team->GetLastTouchPlayer()==own && own->GetLastTouchTime_ms()>tribunCombination.lastPass;
    const int owner=confirmed ? own->GetID() : -1;
    tribunCombination.Observe(owner,confirmed,interrupted,now);
  }
  if (!teamHasPossession)'''),
        ("      prevTeamHasPossession && !teamHasPossession){", "      prevTeamHasPossession && !teamHasPossession && !tribunCombination.stage){"),
        ("void TeamAIController::ApplyAttackingRun(Player* manualPlayer) {", r'''void TeamAIController::TribunPassContact(Player* passer,Player* receiver,bool shortPass) {
  if(tribunRebound.stage>=2){tribunRebound.Clear();tribunReboundSupportID=-1;}
  if(!AITactics::ShortMatchAttackEnabled() || team->GetHumanGamerCount())return;
  const auto now=match->GetActualTime_ms();
  if(!shortPass || !receiver || !passer || receiver==passer ||
      receiver->GetTeam()!=team || !receiver->IsActive() || !passer->IsActive() ||
      !match->IsInPlay() || match->IsInSetPiece() || match->GetBallRetainer()){
    tribunCombination.Clear(now);return;
  }
  if(tribunCombination.stage){
    if(!tribunCombination.ReturnPass(passer->GetID(),receiver->GetID(),now))
      tribunCombination.Clear(now);
    return;
  }
  const float forward=-team->GetSide();
  const auto pos=passer->GetPosition(), delta=receiver->GetPosition()-pos;
  const float line=AI_GetOffsideLine(match,match->GetMentalImage(0),abs(team->GetID()-1))*forward;
  const float skill=passer->GetStat("technical_shortpass")*.65f+passer->GetStat("mental_vision")*.35f;
  if(receiver->GetFormationEntry().role==e_PlayerRole_GK ||
     passer->GetFormationEntry().role==e_PlayerRole_GK ||
     !AITactics::StartCombination(AI_GetMindSet(passer->GetDynamicFormationEntry().role),
          skill,delta.GetLength(),delta.coords[0]*forward,pitchHalfW-pos.coords[0]*forward,
          line-receiver->GetPosition().coords[0]*forward))return;
  if(tribunCombination.Begin(passer->GetID(),receiver->GetID(),now)){
    ApplyAttackingRun(passer);
    endApplyAttackingRun_ms=now+2800;
  }
}

Player* TeamAIController::TribunReturnTarget(Player* receiver) {
  const auto now=match->GetActualTime_ms();
  if(!receiver || tribunCombination.stage!=2 || now>=tribunCombination.expires ||
      receiver->GetID()!=tribunCombination.receiver || !receiver->HasUniquePossession())
    return nullptr;
  Player* target=team->GetPlayer(tribunCombination.passer);
  return target && target->IsActive() ? target : nullptr;
}

bool TeamAIController::TribunCombinationRunner(Player* player) const {
  return player && tribunCombination.stage>=1 && tribunCombination.stage<=2 &&
      player->GetID()==tribunCombination.passer && match->GetActualTime_ms()<tribunCombination.expires;
}

void TeamAIController::ApplyAttackingRun(Player* manualPlayer) {'''),
        ("void TeamAIController::Reset() {\n  taker = 0;", "void TeamAIController::Reset() {\n  tribunCombination.Clear(match->GetActualTime_ms());\n  taker = 0;"),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoid.cpp", [
        ("        match->GetMatchData()->AddPassAttempt(team->GetID());", r'''        match->GetMatchData()->AddPassAttempt(team->GetID());
        team->GetController()->TribunPassContact(CastPlayer(),targetPlayer,
            currentAnim->functionType==e_FunctionType_ShortPass);'''),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("  float adaptedMakeRun = makeRun;", "  const bool combinationRun=team->GetController()->TribunCombinationRunner(CastPlayer());\n  float adaptedMakeRun = makeRun || combinationRun;"),
        ("      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet) {", r'''      bool returnCandidate=false;
      float returnOdds=0.0f;
      if(runningPassEnabled && team->GetController()->TribunReturnTarget(CastPlayer())==mates.at(i)){
        const auto delta=mates.at(i)->GetPosition()-player->GetPosition();
        const float margin=passOffside-mates.at(i)->GetPosition().coords[0]*attackForward;
        if(AITactics::SafeReturnPass(delta.coords[0]*attackForward,delta.GetLength(),margin,1.0f)){
          returnOdds=_GetPassingOdds(mates.at(i),e_FunctionType_ShortPass,opponentPlayerImages);
          returnCandidate=AITactics::SafeReturnPass(delta.coords[0]*attackForward,delta.GetLength(),margin,returnOdds);
        }
      }
      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate) {'''),
        ("        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +", r'''        if(returnCandidate && returnOdds>=mateRating.passRating-.08f){
          mateRating.passRating=returnOdds;
          mateRating.passType=e_FunctionType_ShortPass;
          mateRating.supportRating+=.45f;
        }
        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +'''),
    ])
    # Explicit run preference survives the brief loose-ball flight of the first pass.
    # The final target is still clamped by GetSupportPosition_ForceField's offside check.
    edit(root, "src/onthepitch/player/controller/strategies/offtheball/default_off.cpp", [
        ("    Vector3 supportPosition =\n        controller->GetSupportPosition_ForceField(mentalImage, desiredPosition, makeRun);", r'''    if(team->GetController()->TribunCombinationRunner(CastPlayer())){
      makeRun=true;attackBias=std::max(attackBias,.85f);
    }
    Vector3 supportPosition =
        controller->GetSupportPosition_ForceField(mentalImage, desiredPosition, makeRun);'''),
    ])
    edit(root, "src/onthepitch/player/controller/strategies/offtheball/default_mid.cpp", [
        ("    Vector3 supportPosition =\n        controller->GetSupportPosition_ForceField(mentalImage, desiredPosition, makeRun);", r'''    if(team->GetController()->TribunCombinationRunner(CastPlayer())){
      makeRun=true;attackBias=std::max(attackBias,.85f);
    }
    Vector3 supportPosition =
        controller->GetSupportPosition_ForceField(mentalImage, desiredPosition, makeRun);'''),
    ])

    # Observe contacts in both benchmark profiles. Only short-match changes decisions.
    edit(root, "src/onthepitch/teamAIcontroller.hpp", [
        ("  void TribunPassContact(Player* passer, Player* receiver, bool shortPass);", r'''  void TribunPassContact(Player* passer, Player* receiver, bool shortPass);
  void TribunShotContact(Player* shooter);
  bool TribunReboundSupport(Player* player, Vector3& target);
  bool TribunRecoveredShot(Player* player) const;
  const AITactics::ReboundState& GetTribunRebound() const { return tribunRebound; }'''),
        ("  AITactics::CombinationState tribunCombination;", r'''  AITactics::CombinationState tribunCombination;
  AITactics::ReboundState tribunRebound;
  int tribunReboundSupportID=-1;
  Vector3 tribunReboundTarget;'''),
    ])
    edit(root, "src/onthepitch/teamAIcontroller.cpp", [
        ("  CalculateSituation();\n  if (tribunCombination.stage) {", r'''  CalculateSituation();
  if(tribunRebound.stage){
    const auto now=match->GetActualTime_ms();
    const auto ball=match->GetBall()->Predict(0);
    const float forward=-team->GetSide();
    const bool invalid=!match->IsInPlay() || match->IsInSetPiece() ||
        match->GetBallRetainer();
    const bool inZone=AITactics::ReboundZone(pitchHalfW-ball.coords[0]*forward,std::abs(ball.coords[1]),ball.coords[2]);
    auto* rival=match->GetTeam(abs(team->GetID()-1));
    auto* touch=match->GetLastTouchPlayer();
    if(!invalid && inZone && !oppTeamHasUniquePossession && touch && touch->GetTeam()==rival &&
        touch->GetLastTouchType()==e_TouchType_Accidental)
      tribunRebound.Deflect(touch->GetLastTouchTime_ms(),now);
    auto* owner=team->GetDesignatedTeamPossessionPlayer();
    const bool ownControl=owner && owner->IsActive() && owner->HasUniquePossession() &&
        match->GetLastTouchPlayer()==owner;
    tribunRebound.Observe(invalid || (tribunRebound.stage>=2 && !inZone),oppTeamHasUniquePossession,ownControl?owner->GetID():-1,
                           ownControl?owner->GetLastTouchTime_ms():0,now);
    if(tribunRebound.stage!=2 || teamHasUniquePossession)tribunReboundSupportID=-1;
    if(AITactics::ShortMatchAttackEnabled() && tribunRebound.stage==2 &&
        !teamHasUniquePossession && !team->GetHumanGamerCount() && now%100==0){
      tribunReboundSupportID=-1;
      // Native designated player still pursues the ball. One distinct outfield
      // teammate supports behind the projected landing point, never all attackers.
      const auto predicted=match->GetBall()->Predict(350);
      const float line=AI_GetOffsideLine(match,match->GetMentalImage(0),rival->GetID())*forward;
      const float x=clamp(std::min(predicted.coords[0]*forward-3.0f,line-1.2f),pitchHalfW-24.0f,pitchHalfW-2.0f);
      float best=10000.0f;
      for(const auto& mate:team->GetAllPlayers()){
        if(x>line-1.2f)break; // no legal support target inside the bounded zone
        if(!mate->IsActive() || mate.get()==owner || mate.get()==team->GetGoalie())continue;
        const auto pos=mate->GetPosition();
        if(!AITactics::ReboundSupportEligible(AI_GetMindSet(mate->GetDynamicFormationEntry().role),
            (pos-predicted.Get2D()).GetLength(),line-pos.coords[0]*forward))continue;
        const float sign=owner && owner->GetPosition().coords[1]>=predicted.coords[1] ? -1.0f : 1.0f;
        const auto target=Vector3(x*forward,clamp(predicted.coords[1]+sign*5.0f,-17.0f,17.0f),0);
        const float cost=(target-pos).GetLength();
        if(cost<best){best=cost;tribunReboundSupportID=mate->GetID();tribunReboundTarget=target;}
      }
    }
  }else tribunReboundSupportID=-1;
  if (tribunCombination.stage) {'''),
        ("void TeamAIController::TribunPassContact(Player* passer,Player* receiver,bool shortPass) {", r'''void TeamAIController::TribunShotContact(Player* shooter) {
  if(!shooter || team->GetHumanGamerCount() || !match->IsInPlay() || match->IsInSetPiece())return;
  tribunRebound.Shot(shooter->GetID(),match->GetActualTime_ms());
  tribunReboundSupportID=-1;
}
bool TeamAIController::TribunReboundSupport(Player* player,Vector3& target) {
  if(!AITactics::ShortMatchAttackEnabled() || !player || !player->IsActive() ||
      tribunRebound.stage!=2 || player->GetID()!=tribunReboundSupportID ||
      player==team->GetDesignatedTeamPossessionPlayer() || team->HasUniquePossession() ||
      !match->IsInPlay() || match->IsInSetPiece() || match->GetBallRetainer() ||
      match->GetActualTime_ms()>=tribunRebound.expires)return false;
  target=tribunReboundTarget;return true;
}
bool TeamAIController::TribunRecoveredShot(Player* player) const {
  return AITactics::ShortMatchAttackEnabled() && player && player->HasUniquePossession() &&
      tribunRebound.stage==3 && player->GetID()==tribunRebound.recoverer &&
      match->GetActualTime_ms()<tribunRebound.expires;
}
void TeamAIController::TribunPassContact(Player* passer,Player* receiver,bool shortPass) {'''),
        ("  tribunCombination.Clear(match->GetActualTime_ms());\n  taker = 0;", "  tribunCombination.Clear(match->GetActualTime_ms());\n  tribunRebound.Clear();\n  tribunReboundSupportID=-1;\n  taker = 0;"),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoid.cpp", [
        ("        match->GetMatchData()->AddShot(team->GetID());", "        match->GetMatchData()->AddShot(team->GetID());\n        team->GetController()->TribunShotContact(CastPlayer());"),
    ])
    for strategy in ("default_off.cpp","default_mid.cpp"):
        edit(root, "src/onthepitch/player/controller/strategies/offtheball/"+strategy, [
            ("  direction = (desiredPosition - player->GetPosition()).GetNormalized(player->GetDirectionVec());", r'''  Vector3 secondBallSupport;
  if(team->GetController()->TribunReboundSupport(CastPlayer(),secondBallSupport))
    desiredPosition=desiredPosition*.35f+secondBallSupport*.65f;
  direction = (desiredPosition - player->GetPosition()).GetNormalized(player->GetDirectionVec());'''),
        ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("         AITactics::PrioritizeGoodShot(distance,angle,odds,CastPlayer()->HasUniquePossession()))", r'''         (AITactics::PrioritizeGoodShot(distance,angle,odds,CastPlayer()->HasUniquePossession()) ||
          (team->GetController()->TribunRecoveredShot(CastPlayer()) &&
           AITactics::PrioritizeReboundShot(distance,angle,odds,
             player->GetStat("technical_ballcontrol"),player->GetStat("technical_shot")))))'''),
    ])

    # Fixed simulation-tick budget, not a wall-clock or throughput guarantee.
    # No scale changes, skipped physics ticks or forced score.
    edit(root, "src/onthepitch/match.hpp", [
        ('#include "AIsupport/mentalimage.hpp"', '#include "AIsupport/mentalimage.hpp"\n#include "aitactics.hpp"\n#include <stdexcept>'),
        ("  unsigned long GetMatchTime_ms() const { return matchTime_ms; }", r'''  unsigned long GetMatchTime_ms() const { return matchTime_ms; }
  const AITactics::FixedDurationClock& GetTribunFixedClock() const {return tribunFixedClock;}'''),
        ("  float matchTimeScale;", "  float matchTimeScale;\n  AITactics::FixedDurationClock tribunFixedClock;"),
    ])
    edit(root, "src/onthepitch/referee.hpp", [
        ("  void Process();", "  void Process();\n  void TribunFixedBoundary(bool fullTime);"),
    ])
    edit(root, "src/onthepitch/referee.cpp", [
        ('#include <algorithm>', '#include <algorithm>\n#include <stdexcept>\n#include "aitactics.hpp"'),
        ("void Referee::Process() {", r'''void Referee::TribunFixedBoundary(bool fullTime) {
  // Do not silently erase a penalty or an unresolved disciplinary foul.
  // Reject this experimental fixture instead of publishing a compromised result.
  if((buffer.active && buffer.desiredSetPiece==e_SetPiece_Penalty) ||
      (foul.foulType!=0 && !foul.hasBeenProcessed))
    throw std::runtime_error("Fixed-duration boundary conflicts with pending foul or penalty");
  match->StopPlay();
  match->StopSetPiece();
  IssuePendingCautions();
  offsidePlayers.clear();
  buffer.active=false;
  buffer.taker=nullptr;
  foul.foulPlayer=nullptr;
  foul.foulVictim=nullptr;
  foul.foulType=0;
  foul.advantage=false;
  foul.hasBeenProcessed=true;
  if(fullTime){
    // Finish before any subsequent physics tick can modify the score.
    match->GameOver();
    return;
  }
  // Use the ordinary referee preparation and phase-change pathway.
  buffer.desiredSetPiece=e_SetPiece_KickOff;
  buffer.stopTime=match->GetActualTime_ms();
  buffer.prepareTime=buffer.stopTime+1000;
  buffer.startTime=buffer.prepareTime+1000;
  buffer.restartPos=Vector3(0);
  buffer.teamID=1;
  buffer.active=true;
  buffer.endPhase=true;
  match->SetMatchPhase(e_MatchPhase_2ndHalf);
}

void Referee::Process() {'''),
        ("    if (timedPeriod && match->GetAddedMinutes() >= 0 && match->GetMatchTime_ms() > periodEnd_ms &&", "    if (!AITactics::FixedDurationEnabled() && timedPeriod && match->GetAddedMinutes() >= 0 && match->GetMatchTime_ms() > periodEnd_ms &&"),
    ])
    edit(root, "src/onthepitch/match.cpp", [
        ("  // Tell the game page once; the full-time screen used to be re-created", r'''  // Imported CPU league fixtures only. Clock starts on first open-play tick.
  if (AITactics::FixedDurationEnabled() && !gameOver && !pause) {
    if (!std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE") || GetTeam(0)->GetHumanGamerCount() ||
        GetTeam(1)->GetHumanGamerCount() || GetConfiguration()->GetBool("match_extra_time",false))
      throw std::runtime_error("Fixed-duration requires CPU-only regulation fixture");
    if (matchPhase==e_MatchPhase_1stHalf && IsInPlay() && !IsInSetPiece())
      tribunFixedClock.Start(actualTime_ms);
    if(tribunFixedClock.started){
      matchTime_ms=tribunFixedClock.Nominal(actualTime_ms);
      matchTimeExact_ms=static_cast<double>(matchTime_ms);
      addedMinutes=0;
      if(tribunFixedClock.HalfDue(actualTime_ms)){
        referee->TribunFixedBoundary(false);
        tribunFixedClock.half=true;
        addedMinutes=0;
      }
      if(tribunFixedClock.FullDue(actualTime_ms)){
        referee->TribunFixedBoundary(true);
        tribunFixedClock.finished=true;
        pause=true;
      }
    }
  }

  // Tell the game page once; the full-time screen used to be re-created'''),
        ("    if (IsInPlay() && !IsInSetPiece()) {\n      matchTimeExact_ms +=", "    if (!AITactics::FixedDurationEnabled() && IsInPlay() && !IsInSetPiece()) {\n      matchTimeExact_ms +="),
    ])

    # Target the final ranking after all earlier runner/delivery/return bonuses.
    # No new animations or ball trajectories; native pass selection remains in charge.
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("  float bestTotalRating = 0.0f;\n  MateRating bestMateRating;", r'''  const bool retentionEnabled=AITactics::FinalThirdRetentionEnabled() &&
      runningPassEnabled && AITactics::FinalThirdControlled(
          pitchHalfW-player->GetPosition().coords[0]*attackForward,
          match->IsInPlay() && !match->IsInSetPiece(),
          CastPlayer()->HasUniquePossession(),CastPlayer()->GetFormationEntry().role!=e_PlayerRole_GK);
  float bestTotalRating = 0.0f;
  MateRating bestMateRating;'''),
        ("      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate) {", r'''      bool retentionOutlet=false;
      float retentionOdds=0.0f;
      if(retentionEnabled && mates.at(i)->GetFormationEntry().role!=e_PlayerRole_GK){
        const auto delta=mates.at(i)->GetPosition()-player->GetPosition();
        const float margin=passOffside-mates.at(i)->GetPosition().coords[0]*attackForward;
        if(AITactics::SafeGroundOutlet(delta.coords[0]*attackForward,delta.GetLength(),
            mateSit.spaceRating,margin,1.0f)){
          retentionOdds=_GetPassingOdds(mates.at(i),e_FunctionType_ShortPass,opponentPlayerImages);
          retentionOutlet=AITactics::SafeGroundOutlet(delta.coords[0]*attackForward,delta.GetLength(),
              mateSit.spaceRating,margin,retentionOdds);
        }
      }
      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet) {'''),
        ("        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +", r'''        float retentionPenalty=0.0f;
        if(retentionEnabled){
          // Prefer a well-positioned short option only if nearly as safe as the
          // best native pass type. Do not displace a clearly safer through ball.
          if(retentionOutlet && retentionOdds>=mateRating.passRating-.04f){
            mateRating.passType=e_FunctionType_ShortPass;
            mateRating.passRating=retentionOdds;
            mateRating.supportRating+=.30f;
          }
          if(!AITactics::RetentionPassAllowed(mateRating.passRating,nearestPressure))continue;
          retentionPenalty=AITactics::RetentionRiskCost(mateRating.passRating,nearestPressure);
        }
        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +'''),
        ("        totalRating /= totalWeight2;", "        totalRating = (totalRating-retentionPenalty) / totalWeight2;"),
    ])
