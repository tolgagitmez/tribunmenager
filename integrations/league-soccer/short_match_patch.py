"""Opt-in seeded RNG and conservative short-match attack tuning."""
from pathlib import Path
from instrument import replace_once

def edit(root, name, replacements):
    p = Path(root) / name
    text = p.read_text(encoding="utf-8")
    for old, new in replacements:
        text = replace_once(text, old, new)
    p.write_text(text, encoding="utf-8")

LINE_BREAK_RULES = r'''// Safe progressive pass into the final third; crossing a defender's depth is a proxy, not an xG model.
inline bool LineBreakGeometry(float depth,float targetDepth,float progress,float distance,
    float margin,float receiverClearance,int defenders) {
  return depth>=12.0f && depth<=42.0f && targetDepth>=2.0f && targetDepth<=24.0f &&
      progress>=5.0f && distance>=6.0f && distance<=28.0f && margin>=1.2f &&
      receiverClearance>=2.0f && defenders>=1;
}
inline bool LineBreakPreferred(float odds,float nativeOdds) {
  return odds>=0.72f && odds>=nativeOdds-0.03f;
}
inline float LineBreakBonus(int defenders,float progress) {
  return 0.18f+std::min(3,std::max(0,defenders))*0.05f+
      std::min(20.0f,std::max(0.0f,progress))*0.005f;
}
'''

RUN_LANE_RULES = r'''// Coordinates are expressed in the attacking direction, in metres.
inline float RunLaneY(float carrierY,bool primary,float lane) {
  const float side=carrierY>=0.0f?1.0f:-1.0f;
  return (primary?side:-side)*lane;
}
inline bool RunLaneEligible(float depth,float progress,float distance,float passDistance,
    float margin,float endpoint,float corridor,float teammateGap) {
  return depth>=6.0f && depth<=30.0f && progress>=2.0f && distance>=3.0f &&
    distance<=17.0f && passDistance>=7.0f && passDistance<=32.0f &&
    margin>=1.5f && endpoint>=2.2f && corridor>=1.5f && teammateGap>=3.5f;
}
inline float RunLaneScore(float endpoint,float corridor,float mateGap,float progress,float distance,float lateralChange) {
  return std::min(endpoint,8.0f)*0.40f+std::min(corridor,5.0f)*0.45f+
    std::min(mateGap,9.0f)*0.12f+std::min(progress,12.0f)*0.09f-
    distance*0.10f-lateralChange*0.05f;
}
'''

TRIANGLE_RULES = r'''// Track actual A->B contact, B control, B->C contact, C control.
struct TriangleState {
  int a=-1,b=-1,c=-1,stage=0;
  unsigned long started=0,lastPass=0,expires=0,cooldown=0;
  unsigned long startedCount=0,firstReceipts=0,secondPasses=0,completed=0;
  void Clear(unsigned long now){if(stage)cooldown=now+1200;a=b=c=-1;stage=0;started=lastPass=expires=0;}
  bool Begin(int first,int middle,int third,unsigned long now){
    if(stage||now<cooldown||first<0||middle<0||third<0||first==middle||first==third||middle==third)return false;
    a=first;b=middle;c=third;stage=1;started=lastPass=now;expires=now+2300;++startedCount;return true;
  }
  void Observe(int owner,unsigned long touch,bool invalid,unsigned long now){
    if(!stage)return;
    if(invalid||now>=expires||now<lastPass){Clear(now);return;}
    if(owner<0||touch<=lastPass||touch>now)return;
    if(stage==1 && owner==b){stage=2;++firstReceipts;expires=now+1600;return;}
    if(stage==3 && owner==c){++completed;Clear(now);return;}
    if((stage==1&&owner!=a)||(stage==2&&owner!=b)||(stage==3&&owner!=b))Clear(now);
  }
  bool Pass(int from,int to,unsigned long now){
    if(stage!=2||from!=b||to!=c||now>=expires||now<lastPass)return false;
    stage=3;lastPass=now;expires=now+2000;++secondPasses;return true;
  }
};
inline bool TriangleGeometry(float progress,float distance,float width,float margin,float depth){
  return progress>=3.0f&&progress<=20.0f&&distance>=5.0f&&distance<=22.0f&&
      width>=3.0f&&width<=17.0f&&margin>=1.3f&&depth>=4.0f&&depth<=30.0f;
}
inline bool TrianglePassSafe(float odds,float nativeOdds){return odds>=.74f&&odds>=nativeOdds-.05f;}
'''

CREATIVE_CARRY_RULES = r'''// Scores are relative to the attacking direction; speed fraction is relative to native sprint.
inline float CarrySpeedLimit(float skill,float pressure,float gap,float turn){
  if(gap>1.35f)return .48f;
  const float cap=.60f+.40f*std::clamp(skill,0.0f,1.0f);
  if(pressure<1.7f||turn<.45f)return std::min(cap,.62f);
  if(pressure<3.0f)return std::min(cap,.78f);
  return cap;
}
inline float CarryOption(float progress,float clearance,float alignment,float speed,float skill,float attack){
  if(clearance<1.15f||progress<-.40f||alignment<-.35f)return -1000.0f;
  return progress*(.65f+.45f*attack)+std::min(clearance,5.0f)*.85f+
      alignment*(.9f-.35f*skill)-speed*(1.0f-skill)*.6f;
}
struct CarryTrial {
  int player=-1;
  unsigned long start=0,expires=0,cooldown=0,lastControl=0;
  float x=0,forward=1;
  unsigned long attempts=0,progressed=0,lost=0,cancelled=0;
  unsigned long technical=0,conservative=0;
  void End(unsigned long now){player=-1;cooldown=now+500;}
  void Cancel(unsigned long now){if(player>=0){++cancelled;End(now);}}
  bool Begin(int id,float pos,float dir,float skill,unsigned long now){
    if(player>=0||now<cooldown||id<0)return false;
    player=id;start=lastControl=now;expires=now+1100;x=pos;forward=dir;
    ++attempts;if(skill>=.70f)++technical;else ++conservative;return true;
  }
  void Observe(int owner,bool opponentControl,bool invalid,float pos,unsigned long now){
    if(player<0)return;
    if(invalid||now<start){Cancel(now);return;}
    if(opponentControl){++lost;End(now);return;}
    if(owner>=0&&owner!=player){Cancel(now);return;}
    if(owner==player){
      lastControl=now;
      if(now>=start+250&&(pos-x)*forward>=2.0f){++progressed;End(now);return;}
    }
    if(now>=expires||now>lastControl+200)Cancel(now);
  }
};
'''

DUEL_RULES = r'''// Relative to attacking direction. A duel starts with a defender ahead and closing.
inline bool DuelEligible(float ahead,float distance,float closing,float gap,float skill){
  return ahead>=.45f&&ahead<=4.0f&&distance>=1.4f&&distance<=4.5f&&closing>=.5f&&gap<=1.1f&&skill>=.58f;
}
inline float DuelEscapeScore(float advance,float clearance,float turn,float speed,float skill,float wrongFoot){
  if(advance<.3f||clearance<1.25f||turn<-.15f)return -1000.0f;
  return advance*.65f+std::min(clearance,4.0f)*1.15f+turn*.4f+
    std::clamp(wrongFoot,-1.0f,1.0f)*(.35f+.4f*skill)-speed*(1.0f-skill)*.5f;
}
struct DuelTrial {
  int carrier=-1,defender=-1;float initialX=0,forward=1;
  unsigned long start=0,lastControl=0,cooldown=0,expires=0;
  unsigned long attempts=0,beaten=0,lost=0,cancelled=0;
  void End(unsigned long now){carrier=defender=-1;cooldown=now+650;}
  void Cancel(unsigned long now){if(carrier>=0){++cancelled;End(now);}}
  bool Begin(int a,int b,float x,float dir,unsigned long now){
    if(carrier>=0||now<cooldown||a<0||b<0||a==b)return false;
    carrier=a;defender=b;initialX=x;forward=dir;start=lastControl=now;expires=now+1500;++attempts;return true;
  }
  void Observe(int owner,bool opposition,bool invalid,float cx,float dx,float distance,unsigned long now){
    if(carrier<0)return;
    if(invalid||now<start){Cancel(now);return;}
    if(opposition){++lost;End(now);return;}
    if(owner>=0&&owner!=carrier){Cancel(now);return;}
    if(owner==carrier){
      lastControl=now;
      if(now>=start+250&&(cx-initialX)*forward>=2.0f&&(cx-dx)*forward>=1.0f&&distance>=1.5f){
        ++beaten;End(now);return;
      }
    }
    if(now>=expires||now>lastControl+200)Cancel(now);
  }
};
'''

HOLD_UP_RULES = r'''inline float HoldSkill(float balance,float control,float calm){
  return .45f*std::clamp(balance,0.0f,1.0f)+.35f*std::clamp(control,0.0f,1.0f)+.20f*std::clamp(calm,0.0f,1.0f);
}
inline bool HoldEligible(float depth,float facingForward,float nearest,float gap,float skill){
  return depth>=9&&depth<=38&&facingForward<=.30f&&nearest>=.8f&&nearest<=3.2f&&gap<=1.15f&&skill>=.58f;
}
inline float ShieldScore(float clearance,float alignment,float screen,float progress){
  if(clearance<.95f||alignment<.0f||progress<-1.3f)return -1000.0f;
  return std::min(clearance,4.0f)*1.2f+alignment*.55f+std::clamp(screen,-1.0f,1.0f)*.8f+progress*.15f;
}
inline bool HoldOutlet(float distance,float progress,float margin,float space,float odds,float nativeOdds){
  return distance>=3&&distance<=13&&progress>=-9&&progress<=6&&margin>=1&&space>=.55f&&odds>=.78f&&odds>=nativeOdds-.04f;
}
struct HoldTrial {
  int carrier=-1,receiver=-1,stage=0;
  unsigned long start=0,expires=0,lastControl=0,passAt=0,cooldown=0;
  unsigned long attempts=0,held=0,released=0,received=0,lost=0,cancelled=0;
  void End(unsigned long now){carrier=receiver=-1;stage=0;cooldown=now+700;}
  void Cancel(unsigned long now){if(stage){++cancelled;End(now);}}
  bool Begin(int id,unsigned long now){
    if(stage||now<cooldown||id<0)return false;
    carrier=id;stage=1;start=lastControl=now;expires=now+1200;++attempts;return true;
  }
  bool Ready(int id,unsigned long now)const{return stage==2&&id==carrier&&now<expires;}
  bool Pass(int from,int to,bool shortPass,unsigned long now){
    if(!Ready(from,now)||!shortPass||to<0||to==from)return false;
    receiver=to;stage=3;passAt=now;expires=now+1700;++released;return true;
  }
  void Observe(int owner,unsigned long touch,bool opponent,bool invalid,unsigned long now){
    if(!stage)return;
    if(invalid||now<start){Cancel(now);return;}
    if(opponent){++lost;End(now);return;}
    if(stage==3){
      if(owner==receiver&&touch>passAt&&touch<=now){++received;End(now);return;}
      if(owner>=0&&owner!=carrier&&owner!=receiver){Cancel(now);return;}
    }else{
      if(owner>=0&&owner!=carrier){Cancel(now);return;}
      if(owner==carrier){
        lastControl=now;
        if(stage==1&&now>=start+400){stage=2;++held;}
      }
      if(now>lastControl+100){Cancel(now);return;}
    }
    if(now>=expires)Cancel(now);
  }
};
'''

FINISH_RULES = r'''// A bounded aiming heuristic, not a calibrated expected-goals model.
inline float FinishTargetScore(float odds,float fieldOdds,float keeperGap,float y,float skill){
  if(!std::isfinite(odds)||!std::isfinite(fieldOdds)||!std::isfinite(keeperGap)||
     std::abs(y)>3.0f)return -1000.0f;
  return .48f*odds+.32f*fieldOdds+.20f*std::clamp(keeperGap/3.0f,0.0f,1.0f)-
      .10f*(1.0f-skill)*std::abs(y)/3.0f;
}
inline bool FinishEligible(float distance,float angle,float skill,float odds){
  return distance>=4.0f&&distance<=27.0f&&angle>=.48f&&skill>=.45f&&odds>=.30f;
}
inline bool FinishPreferShot(float distance,float angle,float skill,float odds,float fieldOdds,float passOdds){
  return FinishEligible(distance,angle,skill,odds)&&distance<=19.0f&&angle>=.65f&&
      odds>=.55f&&fieldOdds>=.62f&&odds+.13f>=passOdds;
}
struct FinishProbe {
  int shooter=-1;
  unsigned long issuedAt=0;
  unsigned long decisions=0,aimChanges=0,priorities=0,contacts=0;
  void Clear(){shooter=-1;issuedAt=0;}
  void Issue(int id,unsigned long now,bool changed,bool priority){
    shooter=id;issuedAt=now;++decisions;if(changed)++aimChanges;if(priority)++priorities;
  }
  bool Contact(int id,unsigned long now){
    const bool ok=shooter==id&&now>=issuedAt&&now-issuedAt<=400;
    if(ok)++contacts;Clear();return ok;
  }
};
'''

KEEPER_RULES = r'''inline float KeeperRead(float positioning,float reaction,float calm){
  return .45f*std::clamp(positioning,0.0f,1.0f)+.35f*std::clamp(reaction,0.0f,1.0f)+.20f*std::clamp(calm,0.0f,1.0f);
}
inline bool NarrowEligible(float depth,float lateral,float gap,float towardGoal,float cover,float helper,float skill){
  return depth>=5.0f&&depth<=19.0f&&lateral<=13.0f&&gap<=1.2f&&towardGoal>=.4f&&
      cover>=3.0f&&helper>=5.0f&&skill>=.45f;
}
inline float NarrowDepth(float depth,float lateral,float skill){
  return std::clamp(depth*(.24f+.18f*skill)-.10f*lateral,1.4f,std::min(7.0f,depth-2.0f));
}
inline bool KeeperIntercept(float depth,float y,float height,float distance,int eta,int arrival,float skill){
  const int reaction=static_cast<int>(100.0f-60.0f*std::clamp(skill,0.0f,1.0f));
  return depth>=.6f&&depth<=7.0f&&std::abs(y)<=5.0f&&height>=.11f&&height<=1.65f&&
      distance>=.35f&&distance<=5.0f&&eta>=0&&arrival>=100&&arrival<=850&&eta+reaction<=arrival;
}
struct KeeperProbe {
  int keeper=-1,kind=0;unsigned long start=0,expires=0,cooldown=0;
  unsigned long narrows=0,intercepts=0,controls=0,touches=0,closed=0;
  void Clear(unsigned long now){if(kind){++closed;cooldown=now+350;}keeper=-1;kind=0;}
  bool Begin(int id,int type,unsigned long now){
    if(kind||now<cooldown||id<0||(type!=1&&type!=2))return false;
    keeper=id;kind=type;start=now;expires=now+1300;
    if(type==1)++narrows;else ++intercepts;return true;
  }
  void Observe(bool touch,bool control,bool invalid,unsigned long touchedAt,unsigned long now){
    if(!kind)return;
    if(!invalid&&touch&&touchedAt>start&&touchedAt<=now){++touches;if(control)++controls;Clear(now);return;}
    if(invalid||now>=expires||now<start)Clear(now);
  }
};
'''

DEFENSE_SHAPE_RULES = r'''// Coordinates are metres from the defending goal; preserve formation-relative ordering.
inline bool CoverEligible(float depth,bool primary,bool secondary,bool marked,bool ownControl){
  return depth>=9.0f&&depth<=40.0f&&!primary&&!secondary&&!marked&&!ownControl;
}
inline float CoverDepth(float formationDepth,float threatDepth,float press,float nearSide){
  const float margin=5.0f+2.0f*(1.0f-std::clamp(press,0.0f,1.0f))+1.5f*nearSide;
  return std::clamp(std::min(formationDepth,threatDepth-margin),2.0f,40.0f);
}
inline float CoverWidth(float formationY,float threatY,float press){
  const float compact=.82f+.08f*std::clamp(press,0.0f,1.0f);
  return std::clamp(formationY*compact+std::clamp(threatY*.22f,-5.0f,5.0f),-24.0f,24.0f);
}
inline bool ShapeExposed(float depthSpread,float largestGap,int goalSide){
  return depthSpread>8.0f||largestGap>13.0f||goalSide<2;
}
struct DefenseProbe {
  unsigned long coverTargets=0,huntsSuppressed=0,samples=0,exposed=0;
  void Sample(float depthSpread,float largestGap,int goalSide){
    ++samples;if(ShapeExposed(depthSpread,largestGap,goalSide))++exposed;
  }
};
'''

TRANSITION_RULES = r'''// Stable team possession changes only after a confirmed 80 ms spell.
// Neutral intervals do not count as turnovers.
struct TransitionState {
  int stable=-1,pending=-1; unsigned long pendingAt=0,lastConfirmed=0,winUntil=0,lossUntil=0;
  bool counter=false,press=false;
  unsigned long wins=0,losses=0,counters=0,presses=0,retreats=0,forwardPasses=0,regains=0;
  void Reset(){stable=pending=-1;pendingAt=lastConfirmed=winUntil=lossUntil=0;counter=press=false;}
  int Observe(int side,unsigned long now,bool open){
    if(!open||now<lastConfirmed){Reset();return 0;}
    if(side<0){pending=-1;if(stable>=0&&now-lastConfirmed>1200){stable=-1;counter=press=false;winUntil=lossUntil=0;}return 0;}
    if(side!=pending){pending=side;pendingAt=now;return 0;}
    if(now-pendingAt<80)return 0;
    lastConfirmed=now;
    if(stable<0){stable=side;return 0;}
    if(stable==side)return 0;
    stable=side;
    if(side==1){if(press&&now<lossUntil)++regains;++wins;winUntil=now+1800;lossUntil=0;press=false;counter=false;return 1;}
    ++losses;lossUntil=now+1000;winUntil=0;counter=false;press=false;return -1;
  }
  bool Winning(unsigned long now)const{return stable==1&&counter&&now<winUntil;}
  bool Losing(unsigned long now)const{return stable==0&&now<lossUntil;}
};
inline bool TransitionCounter(float counter,float depth,int cover,float space,int goalDiff,bool late){
  return depth>=18&&depth<=80&&space>=3.0f&&cover<=4&&counter>=(late&&goalDiff>0?.8f:.58f);
}
inline bool TransitionPress(float press,float territory,float distance,int cover,int goalDiff,bool late){
  return territory>=.45f&&distance<=5.0f&&cover>=3&&press>=(late&&goalDiff<0?.52f:.65f);
}
inline bool TransitionPass(float progress,float distance,float margin,float space,float odds,float nativeOdds){
  return progress>=5&&distance>=7&&distance<=27&&margin>=1.3f&&space>=.55f&&odds>=.73f&&odds>=nativeOdds-.04f;
}
'''

ROLE_PROFILE_RULES = r'''// Relative profile, not a new player rating. Equal strengths retain native movement.
enum RoleFamily { CF, Wide, Mid, DM, FB, CB, Other };
enum RoleProfile { Neutral, Poacher, FalseNine, Inside, Touchline, Runner, Creator, Anchor, DeepCreator, Overlap, StayBack, Distributor, Stopper, ProfileCount };
inline int Profile(RoleFamily family,float pace,float pass,float finish,float defense,float work,float control){
  const float attack=.5f*pace+.5f*finish, creative=.65f*pass+.35f*control;
  const float runner=.5f*pace+.5f*work;
  auto choose=[](float a,float b,int positive,int negative){return a-b>.035f?positive:b-a>.035f?negative:Neutral;};
  switch(family){
    case CF:return choose(attack,creative,Poacher,FalseNine);
    case Wide:return choose(.55f*finish+.45f*control,pace,Inside,Touchline);
    case Mid:return choose(runner,creative,Runner,Creator);
    case DM:return choose(defense,creative,Anchor,DeepCreator);
    case FB:return choose(runner,defense,Overlap,StayBack);
    case CB:return choose(creative,defense,Distributor,Stopper);
    default:return Neutral;
  }
}
struct RoleOffset {float advance,lateral;};
inline RoleOffset ProfileOffset(int profile,float y,float ballY,float cover){
  const float side=y>=0?1.0f:-1.0f;
  switch(profile){
    case Poacher:return {2.5f,-side*.5f};
    case FalseNine:return {-2.8f,std::clamp(ballY-y,-1.3f,1.3f)};
    case Inside:return {1.3f,-side*2.5f};
    case Touchline:return {.8f,side*2.2f};
    case Runner:return {2.0f,0};
    case Creator:return {-1.2f,std::clamp(ballY-y,-1.8f,1.8f)};
    case Anchor:return {-2.0f,0};
    case DeepCreator:return {-.6f,std::clamp(ballY-y,-1.8f,1.8f)};
    case Overlap:return {cover>=3?2.5f:0.0f,cover>=3?side*1.0f:0.0f};
    case StayBack:return {-1.8f,0};
    case Distributor:return {0,std::clamp(ballY-y,-1.5f,1.5f)};
    case Stopper:return {-1.0f,0};
    default:return {0,0};
  }
}
struct RoleProbe {
  unsigned long targets[ProfileCount]={},samples[ProfileCount]={};
  long long forwardMm[ProfileCount]={},wideMm[ProfileCount]={};
  void Sample(int profile,float advance,float width){
    if(profile<=Neutral||profile>=ProfileCount)return;
    ++samples[profile];forwardMm[profile]+=static_cast<long long>(advance*1000);
    wideMm[profile]+=static_cast<long long>(width*1000);
  }
};
'''

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
        ("#include <algorithm>", "#include <algorithm>\n#include <cstdlib>\n#include <cstring>\n#include <cmath>"),
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
inline bool BoxLaneRunsEnabled() {
  static const bool enabled=[]{
    const char* v=std::getenv("TRIBUN_NATIVE_BOX_LANE_RUNS");
    return v && std::strcmp(v,"1")==0;
  }();
  return ShortMatchAttackEnabled() && enabled;
}
inline bool BoxLaneTarget(float ballDepth,float targetDepth,float progress,
                         float runDistance,float passDistance,float onsideMargin,
                         float endpointClearance,float corridorClearance) {
  return ballDepth>=17.0f && ballDepth<=34.0f &&
      targetDepth>=4.0f && targetDepth<=16.5f && progress>=2.0f &&
      runDistance>=2.0f && runDistance<=16.0f &&
      passDistance>=6.0f && passDistance<=28.0f && onsideMargin>=1.2f &&
      endpointClearance>=2.5f && corridorClearance>=1.4f;
}
inline float BoxLaneScore(float endpointClearance,float corridorClearance,
                          float runDistance,float lateralChange) {
  return std::min(6.0f,endpointClearance)*.8f+
      std::min(5.0f,corridorClearance)*1.2f-
      runDistance*.20f-lateralChange*.08f;
}
inline bool TimedAttackEnabled() {
  static const bool enabled=[]{
    const char* v=std::getenv("TRIBUN_NATIVE_TIMED_ATTACK");
    return v && std::strcmp(v,"1")==0;
  }();
  return ShortMatchAttackEnabled() && enabled;
}
inline bool LeadRunGeometry(float depth,float progress,float distance,float speed,
                            float margin,float targetDepth,float clearance){
  return depth>=16.5f && depth<=38.0f && progress>=3.0f && progress<=20.0f &&
      distance>=8.0f && distance<=26.0f && speed>=1.8f &&
      margin>=1.2f && targetDepth>=2.0f && targetDepth<=16.5f && clearance>=2.2f;
}
inline bool LeadPassPreferred(float odds,float best){
  return odds>=.72f && odds>=best-.04f;
}
inline bool ReceiptShot(float distance,float angle,float odds,float skill,float ballGap){
  return distance>=3.0f && distance<=16.0f && angle>=.75f &&
      odds>=.59f && skill>=.60f && ballGap<=1.3f;
}
struct TimedAttackState {
  int stage=0,receiver=-1;
  unsigned long started=0,expires=0;
  unsigned int passes=0,receipts=0,shots=0;
  void Clear(){stage=0;receiver=-1;}
  void Begin(int id,unsigned long now){
    Clear();receiver=id;stage=1;started=now;expires=now+2200;++passes;
  }
  void Observe(int owner,unsigned long touch,bool invalid,unsigned long now){
    if(!stage)return;
    if(invalid||now>=expires){Clear();return;}
    if(stage==1 && owner>=0 && touch>started){
      if(owner!=receiver){Clear();return;}
      stage=2;expires=now+1000;++receipts;
    }else if(stage==2 && owner!=receiver){Clear();}
  }
  bool Ready(int id,unsigned long now)const{return stage==2&&receiver==id&&now<expires;}
  void Shot(int id,unsigned long now){if(Ready(id,now))++shots;Clear();}
};
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
  if (AITactics::FixedDurationEnabled() && !gameOver) {
    if (!std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE") || GetTeam(0)->GetHumanGamerCount() ||
        GetTeam(1)->GetHumanGamerCount() || GetConfiguration()->GetBool("match_extra_time",false))
      throw std::runtime_error("Fixed-duration requires CPU-only regulation fixture");
    if (!pause && matchPhase==e_MatchPhase_1stHalf && IsInPlay() && !IsInSetPiece())
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

    # A single existing secondary outlet chooses a passable central box channel.
    # Keep wide deliveries, explicit combinations, and the final native offside clamp.
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("  // stay away from opponents\n  std::vector<Player*> opponents;", r'''  if(AITactics::BoxLaneRunsEnabled() && match->IsInPlay() && !match->IsInSetPiece() &&
      !team->GetHumanGamerCount() && designatedPlayer!=CastPlayer() &&
      designatedPlayer->HasUniquePossession() && dynamicMindSet>=.45f &&
      player==team->GetController()->GetForwardSupportPlayer() &&
      !adaptedMakeRun && !combinationRun && std::abs(mainManPos.coords[1])<13.0f){
    const float forward=-team->GetSide();
    const float depth=pitchHalfW-mainManPos.coords[0]*forward;
    if(depth>=17.0f && depth<=34.0f){
      std::vector<PlayerImage> rivals;
      mentalImage->GetTeamPlayerImages(abs(team->GetID()-1),-1,rivals);
      const float line=AI_GetOffsideLine(match,mentalImage,abs(team->GetID()-1))*forward;
      const float limit=std::min(line,offsideX*forward);
      const float x=std::min(pitchHalfW-9.0f,limit-1.25f);
      float best=-10000.0f;
      Vector3 target;
      for(float y:{-8.0f,0.0f,8.0f}){
        const Vector3 candidate(x*forward,y,0);
        const auto delta=candidate-mainManPos;
        const float passDistance=delta.GetLength();
        const auto run=candidate-currentPos;
        const float runDistance=run.GetLength();
        if(passDistance<.1f)continue;
        float endpoint=100.0f,corridor=100.0f;
        for(const auto& rival:rivals){
          const auto predicted=rival.position+rival.movement*.25f;
          endpoint=std::min(endpoint,(predicted-candidate).GetLength());
          const auto offset=predicted-mainManPos;
          const float u=(offset.coords[0]*delta.coords[0]+offset.coords[1]*delta.coords[1])/
              (passDistance*passDistance);
          if(u>.05f && u<.95f)
            corridor=std::min(corridor,(predicted-(mainManPos+delta*u)).GetLength());
        }
        if(!AITactics::BoxLaneTarget(depth,pitchHalfW-x,run.coords[0]*forward,runDistance,
             passDistance,limit-x,endpoint,corridor))continue;
        const float score=AITactics::BoxLaneScore(endpoint,corridor,runDistance,std::abs(run.coords[1]));
        if(score>best){best=score;target=candidate;}
      }
      if(best>-9999.0f){
        ForceSpot lane;
        lane.origin=target;
        lane.magnetType=e_MagnetType_Attract;
        lane.decayType=e_DecayType_Constant;
        lane.power=1.6f;
        forceField.push_back(lane);
      }
    }
  }

  // stay away from opponents
  std::vector<Player*> opponents;'''),
    ])

    # Track actual native long-pass contacts and verified receiver control.
    edit(root, "src/onthepitch/teamAIcontroller.hpp", [
        ("  void TribunShotContact(Player* shooter);", r'''  void TribunShotContact(Player* shooter);
  void TribunTimedPassContact(Player* passer,Player* receiver,bool longPass);
  bool TribunTimedReceipt(Player* player) const;
  const AITactics::TimedAttackState& GetTribunTimedAttack() const {return tribunTimedAttack;}'''),
        ("  AITactics::ReboundState tribunRebound;", "  AITactics::ReboundState tribunRebound;\n  AITactics::TimedAttackState tribunTimedAttack;"),
    ])
    edit(root, "src/onthepitch/teamAIcontroller.cpp", [
        ("  CalculateSituation();\n  if(tribunRebound.stage){", r'''  CalculateSituation();
  if(tribunTimedAttack.stage){
    const auto now=match->GetActualTime_ms();
    auto* own=team->GetDesignatedTeamPossessionPlayer();
    auto* rival=match->GetTeam(abs(team->GetID()-1));
    auto* target=team->GetPlayer(tribunTimedAttack.receiver);
    const bool invalid=!match->IsInPlay() || match->IsInSetPiece() ||
        match->GetBallRetainer() || oppTeamHasUniquePossession ||
        rival->GetLastTouchTime_ms()>tribunTimedAttack.started ||
        !target || !target->IsActive();
    const bool controlled=own && own->IsActive() && own->HasUniquePossession() &&
        match->GetLastTouchPlayer()==own;
    tribunTimedAttack.Observe(controlled?own->GetID():-1,
        controlled?own->GetLastTouchTime_ms():0,invalid,now);
  }
  if(tribunRebound.stage){'''),
        ("void TeamAIController::TribunShotContact(Player* shooter) {", r'''void TeamAIController::TribunTimedPassContact(Player* passer,Player* receiver,bool longPass){
  if(!AITactics::TimedAttackEnabled())return;
  tribunTimedAttack.Clear();
  if(!longPass || !passer || !receiver || receiver==passer ||
      receiver->GetTeam()!=team || !receiver->IsActive() ||
      passer->GetFormationEntry().role==e_PlayerRole_GK ||
      receiver->GetFormationEntry().role==e_PlayerRole_GK ||
      team->GetHumanGamerCount() || !match->IsInPlay() || match->IsInSetPiece() ||
      match->GetBallRetainer())return;
  const float forward=-team->GetSide();
  const auto pos=passer->GetPosition(), delta=receiver->GetPosition()-pos;
  const float distance=delta.GetLength();
  const float margin=AI_GetOffsideLine(match,match->GetMentalImage(0),abs(team->GetID()-1))*forward-
      receiver->GetPosition().coords[0]*forward;
  const auto predicted=receiver->GetPosition()+receiver->GetMovement()*.5f+
      Vector3(forward*distance*.2f,0,0);
  // A qualifying actual native lead-pass contact, not a speculative command.
  if(AITactics::LeadRunGeometry(pitchHalfW-pos.coords[0]*forward,delta.coords[0]*forward,
      distance,receiver->GetMovement().coords[0]*forward,margin,
      pitchHalfW-predicted.coords[0]*forward,100.0f))
    tribunTimedAttack.Begin(receiver->GetID(),match->GetActualTime_ms());
}
bool TeamAIController::TribunTimedReceipt(Player* player) const{
  return AITactics::TimedAttackEnabled() && player && player->HasUniquePossession() &&
      tribunTimedAttack.Ready(player->GetID(),match->GetActualTime_ms());
}
void TeamAIController::TribunShotContact(Player* shooter) {'''),
        ("  tribunRebound.Shot(shooter->GetID(),match->GetActualTime_ms());", "  tribunTimedAttack.Shot(shooter->GetID(),match->GetActualTime_ms());\n  tribunRebound.Shot(shooter->GetID(),match->GetActualTime_ms());"),
        ("  tribunRebound.Clear();\n  tribunReboundSupportID=-1;\n  taker = 0;", "  tribunRebound.Clear();\n  tribunTimedAttack.Clear();\n  tribunReboundSupportID=-1;\n  taker = 0;"),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoid.cpp", [
        ("            currentAnim->functionType==e_FunctionType_ShortPass);", r'''            currentAnim->functionType==e_FunctionType_ShortPass);
        team->GetController()->TribunTimedPassContact(CastPlayer(),targetPlayer,
            currentAnim->functionType==e_FunctionType_LongPass);'''),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet) {", r'''      bool timedCandidate=false;
      float timedOdds=0.0f;
      if(AITactics::TimedAttackEnabled() && runningPassEnabled &&
          match->IsInPlay() && !match->IsInSetPiece() &&
          mates.at(i)->GetFormationEntry().role!=e_PlayerRole_GK){
        const auto pos=mates.at(i)->GetPosition();
        const auto delta=pos-player->GetPosition();
        const float distance=delta.GetLength();
        const auto predicted=pos+mates.at(i)->GetMovement()*.5f+
            Vector3(attackForward*distance*.2f,0,0);
        const float depth=pitchHalfW-player->GetPosition().coords[0]*attackForward;
        const float targetDepth=pitchHalfW-predicted.coords[0]*attackForward;
        const float speed=mates.at(i)->GetMovement().coords[0]*attackForward;
        const float margin=passOffside-pos.coords[0]*attackForward;
        if(AITactics::LeadRunGeometry(depth,delta.coords[0]*attackForward,distance,
            speed,margin,targetDepth,100.0f) && std::abs(predicted.coords[1])<=14.0f){
          float clearance=100.0f;
          for(const auto& rival:opponentPlayerImages)
            clearance=std::min(clearance,(predicted-(rival.position+rival.movement*.5f)).GetLength());
          if(AITactics::LeadRunGeometry(depth,delta.coords[0]*attackForward,distance,
              speed,margin,targetDepth,clearance)){
            timedOdds=_GetPassingOdds(mates.at(i),e_FunctionType_LongPass,opponentPlayerImages);
            timedCandidate=AITactics::LeadPassPreferred(timedOdds,0.0f);
          }
        }
      }
      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet || timedCandidate) {'''),
        ("        float retentionPenalty=0.0f;", r'''        if(timedCandidate && AITactics::LeadPassPreferred(timedOdds,mateRating.passRating)){
          mateRating.passType=e_FunctionType_LongPass;
          mateRating.passRating=timedOdds;
          mateRating.supportRating+=.35f;
        }
        float retentionPenalty=0.0f;'''),
        ("         (AITactics::PrioritizeGoodShot(distance,angle,odds,CastPlayer()->HasUniquePossession()) ||", r'''         ((team->GetController()->TribunTimedReceipt(CastPlayer()) &&
           AITactics::ReceiptShot(distance,angle,odds,player->GetStat("technical_shot"),
               (match->GetBall()->Predict(0).Get2D()-player->GetPosition()).GetLength())) ||
          AITactics::PrioritizeGoodShot(distance,angle,odds,CastPlayer()->HasUniquePossession()) ||'''),
    ])

    # Goal replay can pause the native UI between an actual tick increment and
    # the next Process entry. Keep the authoritative simulation time in sync
    # at the increment itself and omit the blocking replay in fixed-clock fixtures.
    edit(root, "src/onthepitch/match.cpp", [
        ("    actualTime_ms += 10;\n    if (IsGoalScored())", r'''    actualTime_ms += 10;
    if(AITactics::FixedDurationEnabled() && tribunFixedClock.started){
      matchTime_ms=tribunFixedClock.Nominal(actualTime_ms);
      matchTimeExact_ms=static_cast<double>(matchTime_ms);
    }
    if (IsGoalScored())'''),
        ("    if (goalScoredTimer == 6000) {\n      pause = true;", r'''    // The client can replay recorded frames independently. Do not block
    // the fixed-duration native simulation on an extended replay overlay.
    if (goalScoredTimer == 6000 && !AITactics::FixedDurationEnabled()) {
      pause = true;'''),
    ])

    # Stage 63: isolated safe line-breaking pass preference; no forced touch or ball speed.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool LineBreakEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_LINE_BREAK");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
''' + LINE_BREAK_RULES + "struct FixedDurationClock {"),
    ])
    edit(root, "src/onthepitch/match.hpp", [
        ("  void Put();", """  void Put();
  unsigned long tribunLineBreakCandidates[2]={0,0};
  unsigned long tribunLineBreakSelections[2]={0,0};"""),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("  float bestTotalRating = 0.0f;\n  MateRating bestMateRating;", r'''  const bool lineBreakEnabled=AITactics::LineBreakEnabled() && runningPassEnabled &&
      match->IsInPlay() && !match->IsInSetPiece();
  bool bestLineBreak=false;
  float bestTotalRating = 0.0f;
  MateRating bestMateRating;'''),
        ("      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet || timedCandidate) {", r'''      bool lineBreak=false;
      float lineOdds=0.0f,lineProgress=0.0f;
      int crossed=0;
      e_FunctionType lineType=e_FunctionType_ShortPass;
      if(lineBreakEnabled && mates.at(i)->GetFormationEntry().role!=e_PlayerRole_GK){
        const auto from=player->GetPosition();
        const auto to=mates.at(i)->GetPosition();
        const auto delta=to-from;
        lineProgress=delta.coords[0]*attackForward;
        const float depth=pitchHalfW-from.coords[0]*attackForward;
        const float targetDepth=pitchHalfW-to.coords[0]*attackForward;
        const float margin=passOffside-to.coords[0]*attackForward;
        if(std::abs(to.coords[1])<=18.0f &&
            AITactics::LineBreakGeometry(depth,targetDepth,lineProgress,delta.GetLength(),margin,100.0f,1)){
          float clearance=100.0f;
          for(const auto& rival:opponentPlayerImages){
            const auto predicted=rival.position+rival.movement*.25f;
            const float progress=(predicted.coords[0]-from.coords[0])*attackForward;
            clearance=std::min(clearance,(predicted-to).Get2D().GetLength());
            if(progress>1.0f && progress<lineProgress-1.0f){
              const float y=from.coords[1]+delta.coords[1]*progress/lineProgress;
              if(std::abs(predicted.coords[1]-y)<=7.0f)++crossed;
            }
          }
          if(AITactics::LineBreakGeometry(depth,targetDepth,lineProgress,delta.GetLength(),margin,clearance,crossed)){
            const float shortOdds=_GetPassingOdds(mates.at(i),e_FunctionType_ShortPass,opponentPlayerImages);
            const float longOdds=_GetPassingOdds(mates.at(i),e_FunctionType_LongPass,opponentPlayerImages);
            lineType=shortOdds>=longOdds?e_FunctionType_ShortPass:e_FunctionType_LongPass;
            lineOdds=std::max(shortOdds,longOdds);
            lineBreak=AITactics::LineBreakPreferred(lineOdds,0.0f);
            if(lineBreak)++match->tribunLineBreakCandidates[team->GetID()];
          }
        }
      }
      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet || timedCandidate || lineBreak) {'''),
        ("        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +", r'''        const bool useLineBreak=lineBreak && AITactics::LineBreakPreferred(lineOdds,mateRating.passRating);
        if(useLineBreak){
          mateRating.passType=lineType;
          mateRating.passRating=lineOdds;
          mateRating.supportRating+=AITactics::LineBreakBonus(crossed,lineProgress);
        }
        // A candidate admitted only by this experiment must still use a safe pass.
        if(lineBreak && !useLineBreak && !(progressiveCandidate || supportCandidate || runningCandidate ||
            deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet || timedCandidate))continue;
        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +'''),
        ("          bestMateRating = mateRating;\n          bestMateSit = mateSit;", "          bestMateRating = mateRating;\n          bestMateSit = mateSit;\n          bestLineBreak=useLineBreak;"),
        ("    _AddPass(commandQueue, bestMateRating.player, bestMateRating.passType);", r'''    if(bestLineBreak)++match->tribunLineBreakSelections[team->GetID()];
    _AddPass(commandQueue, bestMateRating.player, bestMateRating.passType);'''),
    ])

    # Stage 64: choose separated, passable targets for the existing two attacking outlets.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool RunLanesEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_RUN_LANES");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
''' + RUN_LANE_RULES + "struct FixedDurationClock {"),
    ])
    edit(root, "src/onthepitch/match.hpp", [
        ("  unsigned long tribunLineBreakSelections[2]={0,0};", """  unsigned long tribunLineBreakSelections[2]={0,0};
  unsigned long tribunRunLanePrimary[2]={0,0},tribunRunLaneSecondary[2]={0,0};
  unsigned long tribunRunLaneAttempts[2]={0,0};"""),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("  if (adaptedMakeRun) {\n    ForceSpot spot;\n    spot.origin =\n        Vector3(-team->GetSide() * pitchHalfW,", r'''  bool chosenLane=false;
  const bool primaryLane=makeRun && !combinationRun;
  const bool secondaryLane=!adaptedMakeRun &&
      player==team->GetController()->GetForwardSupportPlayer();
  if(AITactics::RunLanesEnabled() && match->IsInPlay() && !match->IsInSetPiece() &&
      !team->GetHumanGamerCount() && designatedPlayer!=CastPlayer() &&
      designatedPlayer->HasUniquePossession() && !combinationRun && dynamicMindSet>=.45f &&
      (primaryLane || secondaryLane) && std::abs(mainManPos.coords[1])<13.0f){
    const float forward=-team->GetSide();
    const float carrierDepth=pitchHalfW-mainManPos.coords[0]*forward;
    if(carrierDepth>=17.0f && carrierDepth<=40.0f){
      ++match->tribunRunLaneAttempts[team->GetID()];
      std::vector<PlayerImage> rivals,mates;
      mentalImage->GetTeamPlayerImages(abs(team->GetID()-1),-1,rivals);
      mentalImage->GetTeamPlayerImages(team->GetID(),CastPlayer()->GetID(),mates);
      const float limit=std::min(offsideX*forward,
          AI_GetOffsideLine(match,mentalImage,abs(team->GetID()-1))*forward);
      const float leadX=std::min(pitchHalfW-6.0f,limit-1.5f);
      float best=-10000.0f;
      Vector3 target(0);
      for(float setback:{0.0f,3.0f,6.0f}){
        for(float width:{4.5f,10.0f,15.5f}){
          const float x=leadX-setback;
          const float y=AITactics::RunLaneY(mainManPos.coords[1],primaryLane,width);
          const Vector3 candidate(x*forward,y,0);
          const auto delta=candidate-mainManPos;
          const float passDistance=delta.GetLength();
          const auto run=candidate-currentPos;
          if(passDistance<.1f)continue;
          float endpoint=100.0f,corridor=100.0f,mateGap=100.0f;
          for(const auto& rival:rivals){
            const auto predicted=rival.position+rival.movement*.35f;
            endpoint=std::min(endpoint,(predicted-candidate).Get2D().GetLength());
            const auto offset=predicted-mainManPos;
            const float u=(offset.coords[0]*delta.coords[0]+offset.coords[1]*delta.coords[1])/(passDistance*passDistance);
            if(u>.05f && u<.95f)
              corridor=std::min(corridor,(predicted-(mainManPos+delta*u)).Get2D().GetLength());
          }
          for(const auto& mate:mates)
            mateGap=std::min(mateGap,(mate.position+mate.movement*.35f-candidate).Get2D().GetLength());
          const float progress=run.coords[0]*forward;
          if(!AITactics::RunLaneEligible(pitchHalfW-x,progress,run.GetLength(),passDistance,
                limit-x,endpoint,corridor,mateGap))continue;
          const float score=AITactics::RunLaneScore(endpoint,corridor,mateGap,progress,
                run.GetLength(),std::abs(run.coords[1]));
          if(score>best){best=score;target=candidate;}
        }
      }
      if(best>-9999.0f){
        ForceSpot spot;
        spot.origin=target;
        spot.magnetType=e_MagnetType_Attract;
        spot.decayType=e_DecayType_Constant;
        spot.power=primaryLane?2.0f*runWeight:1.65f;
        forceField.push_back(spot);
        chosenLane=true;
        if(primaryLane)++match->tribunRunLanePrimary[team->GetID()];
        else ++match->tribunRunLaneSecondary[team->GetID()];
      }
    }
  }
  if (adaptedMakeRun && !chosenLane) {
    ForceSpot spot;
    spot.origin =
        Vector3(-team->GetSide() * pitchHalfW,'''),
    ])

    # Stage 65: bounded three-player sequence based on native ball contacts and controlled receipts.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool TriangleEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_TRIANGLE");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
''' + TRIANGLE_RULES + "struct FixedDurationClock {"),
    ])
    edit(root, "src/onthepitch/teamAIcontroller.hpp", [
        ("  const AITactics::CombinationState& GetTribunCombination() const { return tribunCombination; }", r'''  const AITactics::CombinationState& GetTribunCombination() const { return tribunCombination; }
  const AITactics::TriangleState& GetTribunTriangle() const {return tribunTriangle;}
  Player* TribunTriangleTarget(Player* receiver);
  bool TribunTriangleRunner(Player* player) const;
  bool TribunTriangleContact(Player* passer,Player* receiver,bool shortPass);'''),
        ("  AITactics::CombinationState tribunCombination;", "  AITactics::CombinationState tribunCombination;\n  AITactics::TriangleState tribunTriangle;"),
    ])
    edit(root, "src/onthepitch/teamAIcontroller.cpp", [
        ("  CalculateSituation();\n  if(tribunTimedAttack.stage){", r'''  CalculateSituation();
  if(tribunTriangle.stage){
    const auto now=match->GetActualTime_ms();
    auto* a=team->GetPlayer(tribunTriangle.a);
    auto* b=team->GetPlayer(tribunTriangle.b);
    auto* c=team->GetPlayer(tribunTriangle.c);
    auto* own=team->GetDesignatedTeamPossessionPlayer();
    auto* rival=match->GetTeam(abs(team->GetID()-1));
    const bool invalid=!match->IsInPlay() || match->IsInSetPiece() || match->GetBallRetainer() ||
        oppTeamHasUniquePossession || rival->GetLastTouchTime_ms()>=tribunTriangle.started ||
        !a || !b || !c || !a->IsActive() || !b->IsActive() || !c->IsActive();
    const bool confirmed=own && own->IsActive() && own->HasUniquePossession() &&
        match->GetLastTouchPlayer()==own;
    tribunTriangle.Observe(confirmed?own->GetID():-1,confirmed?own->GetLastTouchTime_ms():0,invalid,now);
  }
  if(tribunTimedAttack.stage){'''),
        ("void TeamAIController::TribunPassContact(Player* passer,Player* receiver,bool shortPass) {", r'''bool TeamAIController::TribunTriangleContact(Player* passer,Player* receiver,bool shortPass){
  if(!AITactics::TriangleEnabled()||team->GetHumanGamerCount())return false;
  const auto now=match->GetActualTime_ms();
  const bool valid=shortPass&&passer&&receiver&&passer!=receiver&&receiver->GetTeam()==team&&
    passer->IsActive()&&receiver->IsActive()&&match->IsInPlay()&&!match->IsInSetPiece()&&!match->GetBallRetainer();
  if(tribunTriangle.stage){
    if(!valid||!tribunTriangle.Pass(passer->GetID(),receiver->GetID(),now))tribunTriangle.Clear(now);
    return true;
  }
  if(!valid||tribunCombination.stage||passer->GetFormationEntry().role==e_PlayerRole_GK||
    receiver->GetFormationEntry().role==e_PlayerRole_GK||now<tribunTriangle.cooldown)return false;
  const float forward=-team->GetSide();
  const auto from=passer->GetPosition(),middle=receiver->GetPosition();
  const auto first=middle-from;
  const float depth=pitchHalfW-from.coords[0]*forward;
  if(depth<14.0f||depth>42.0f||first.GetLength()<4.0f||first.GetLength()>16.0f||
      std::abs(first.coords[1])<2.0f||receiver->GetStat("technical_shortpass")<.55f)return false;
  const float line=AI_GetOffsideLine(match,match->GetMentalImage(0),abs(team->GetID()-1))*forward;
  if(line-middle.coords[0]*forward<1.0f)return false;
  std::vector<PlayerImage> rivals;
  match->GetMentalImage(0)->GetTeamPlayerImages(abs(team->GetID()-1),-1,rivals);
  Player* third=nullptr;float best=-1000.0f;
  for(const auto& mate:team->GetAllPlayers()){
    if(!mate->IsActive()||mate.get()==passer||mate.get()==receiver||
        mate->GetFormationEntry().role==e_PlayerRole_GK||AI_GetMindSet(mate->GetDynamicFormationEntry().role)<.45f)continue;
    const auto pos=mate->GetPosition(),delta=pos-middle;
    if(!AITactics::TriangleGeometry(delta.coords[0]*forward,delta.GetLength(),std::abs(delta.coords[1]),
          line-pos.coords[0]*forward,pitchHalfW-pos.coords[0]*forward))continue;
    if((pos-from).GetLength()<5.0f)continue;
    float clearance=100.0f;
    for(const auto& rival:rivals)clearance=std::min(clearance,(rival.position+rival.movement*.25f-pos).Get2D().GetLength());
    if(clearance<2.0f)continue;
    const float score=std::min(clearance,8.0f)+delta.coords[0]*forward*.15f-delta.GetLength()*.08f;
    if(score>best){best=score;third=mate.get();}
  }
  return third&&tribunTriangle.Begin(passer->GetID(),receiver->GetID(),third->GetID(),now);
}
Player* TeamAIController::TribunTriangleTarget(Player* receiver){
  if(!receiver||!receiver->HasUniquePossession()||tribunTriangle.stage!=2||
      receiver->GetID()!=tribunTriangle.b||match->GetActualTime_ms()>=tribunTriangle.expires)return nullptr;
  auto* target=team->GetPlayer(tribunTriangle.c);
  return target&&target->IsActive()?target:nullptr;
}
bool TeamAIController::TribunTriangleRunner(Player* player) const {
  return player&&tribunTriangle.stage>=1&&tribunTriangle.stage<=2&&
    player->GetID()==tribunTriangle.c&&match->GetActualTime_ms()<tribunTriangle.expires&&
    match->IsInPlay()&&!match->IsInSetPiece()&&!match->GetBallRetainer();
}
void TeamAIController::TribunPassContact(Player* passer,Player* receiver,bool shortPass) {
  if(TribunTriangleContact(passer,receiver,shortPass))return;'''),
        ("void TeamAIController::TribunShotContact(Player* shooter) {", "void TeamAIController::TribunShotContact(Player* shooter) {\n  tribunTriangle.Clear(match->GetActualTime_ms());"),
        ("  tribunCombination.Clear(match->GetActualTime_ms());\n  tribunRebound.Clear();", "  tribunTriangle.Clear(match->GetActualTime_ms());\n  tribunCombination.Clear(match->GetActualTime_ms());\n  tribunRebound.Clear();"),
    ])
    for strategy in ("default_off.cpp","default_mid.cpp"):
        edit(root, "src/onthepitch/player/controller/strategies/offtheball/"+strategy, [
            ("if(team->GetController()->TribunCombinationRunner(CastPlayer())){", "if(team->GetController()->TribunCombinationRunner(CastPlayer()) || team->GetController()->TribunTriangleRunner(CastPlayer())){"),
        ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("  if (adaptedMakeRun && !chosenLane) {", r'''  if(team->GetController()->TribunTriangleRunner(CastPlayer())){
    const float forward=-team->GetSide();
    const float x=std::min(currentPos.coords[0]*forward+5.0f,
        std::min(offsideX*forward-1.5f,pitchHalfW-5.0f));
    if(x>currentPos.coords[0]*forward+1.0f){
      ForceSpot spot;
      spot.origin=Vector3(x*forward,clamp(currentPos.coords[1],-17.0f,17.0f),0);
      spot.magnetType=e_MagnetType_Attract;
      spot.decayType=e_DecayType_Constant;
      spot.power=2.0f*runWeight;
      forceField.push_back(spot);
      chosenLane=true;
    }
  }
  if (adaptedMakeRun && !chosenLane) {'''),
        ("      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet || timedCandidate || lineBreak) {", r'''      bool triangleCandidate=false;
      float triangleOdds=0.0f;
      if(runningPassEnabled && team->GetController()->TribunTriangleTarget(CastPlayer())==mates.at(i)){
        const auto pos=mates.at(i)->GetPosition(),delta=pos-player->GetPosition();
        if(AITactics::TriangleGeometry(delta.coords[0]*attackForward,delta.GetLength(),std::abs(delta.coords[1]),
              passOffside-pos.coords[0]*attackForward,pitchHalfW-pos.coords[0]*attackForward)){
          triangleOdds=_GetPassingOdds(mates.at(i),e_FunctionType_ShortPass,opponentPlayerImages);
          triangleCandidate=AITactics::TrianglePassSafe(triangleOdds,0.0f);
        }
      }
      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet || timedCandidate || lineBreak || triangleCandidate) {'''),
        ("        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +", r'''        if(triangleCandidate && AITactics::TrianglePassSafe(triangleOdds,mateRating.passRating)){
          mateRating.passType=e_FunctionType_ShortPass;
          mateRating.passRating=triangleOdds;
          mateRating.supportRating+=.48f;
        }else if(triangleCandidate && !(progressiveCandidate||supportCandidate||runningCandidate||
            deliveryCandidate||pressureOutlet||returnCandidate||retentionOutlet||timedCandidate||lineBreak))continue;
        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +'''),
    ])

    # Stage 66: multi-speed dribbling search using native movement limits and actual control outcomes.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool CreativeCarryEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_CREATIVE_CARRY");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
''' + CREATIVE_CARRY_RULES + "struct FixedDurationClock {"),
    ])
    edit(root, "src/onthepitch/match.hpp", [
        ("  unsigned long tribunRunLaneAttempts[2]={0,0};", """  unsigned long tribunRunLaneAttempts[2]={0,0};
  AITactics::CarryTrial tribunCarryTrials[2];"""),
    ])
    edit(root, "src/onthepitch/match.cpp", [
        ("    teams[1]->UpdatePossessionStats();\n    CalculateBestPossessionTeamID();", r'''    teams[1]->UpdatePossessionStats();
    if(AITactics::CreativeCarryEnabled()){
      for(int t=0;t<2;++t){
        auto& trial=tribunCarryTrials[t];
        if(trial.player<0)continue;
        auto* carrier=teams[t]->GetPlayer(trial.player);
        auto* own=teams[t]->GetDesignatedTeamPossessionPlayer();
        const bool invalid=!IsInPlay()||IsInSetPiece()||GetBallRetainer()||!carrier||!carrier->IsActive();
        const bool confirmed=own&&own->HasUniquePossession()&&GetLastTouchPlayer()==own;
        trial.Observe(confirmed?own->GetID():-1,teams[1-t]->HasUniquePossession(),
            invalid,carrier?carrier->GetPosition().coords[0]:0.0f,actualTime_ms);
      }
    }
    CalculateBestPossessionTeamID();'''),
        ("void Match::ResetSituation(const Vector3& focusPos) {", r'''void Match::ResetSituation(const Vector3& focusPos) {
  for(auto& trial:tribunCarryTrials)trial.Cancel(GetActualTime_ms());'''),
    ])
    edit(root, "src/onthepitch/AIsupport/AIfunctions.cpp", [
        ("  desiredVelocity = RangeVelocity(desiredVelocity);\n}\n\nVector3 AI_GetForceFieldMovement", r'''  if(AITactics::CreativeCarryEnabled() && player->HasUniquePossession() &&
      match->IsInPlay() && !match->IsInSetPiece() && !match->GetBallRetainer() &&
      !team->GetHumanGamerCount() && player->GetFormationEntry().role!=e_PlayerRole_GK){
    const float skill=AITactics::ControlSkill(player->GetStat("technical_dribble"),
        player->GetStat("technical_ballcontrol"),player->GetStat("physical_agility"),player->GetStat("physical_balance"));
    const float depth=pitchHalfW+side*myPos.coords[0];
    const float gap=(mentalImage->GetBallPrediction(0).Get2D()-myPos).GetLength();
    float nearest=100.0f;
    for(const auto& opp:opponentPlayerImages)nearest=std::min(nearest,(opp.position-myPos).Get2D().GetLength());
    if(depth>=8.0f && depth<=65.0f && nearest>=1.0f && nearest<=6.0f && gap<=1.35f){
      const Vector3 forward(-side,0,0);
      const auto facing=player->GetDirectionVec().Get2D().GetNormalized(forward);
      const auto current=desiredDirection.Get2D().GetNormalized(facing);
      const float attack=clamp(teamTactics.userProperties.GetReal("dribble_offensiveness",.5f),0.0f,1.0f);
      auto score=[&](const Vector3& dir,float fraction){
        const float alignment=dir.coords[0]*facing.coords[0]+dir.coords[1]*facing.coords[1];
        const float distance=sprintVelocity*fraction*.55f;
        const auto endpoint=myPos+dir*distance;
        if(std::abs(endpoint.coords[0])>pitchHalfW-1.5f||std::abs(endpoint.coords[1])>pitchHalfH-1.5f)return -1000.0f;
        float clearance=100.0f;
        for(const auto& opp:opponentPlayerImages)for(float time:{.18f,.36f,.55f}){
          const auto point=myPos+dir*(sprintVelocity*fraction*time);
          const auto rival=opp.position+opp.movement*time;
          clearance=std::min(clearance,(point-rival).Get2D().GetLength());
        }
        return AITactics::CarryOption(dir.coords[0]*-side*distance,clearance,alignment,fraction,skill,attack);
      };
      const float currentSpeed=clamp(desiredVelocity/sprintVelocity,0.0f,1.0f);
      float best=score(current,currentSpeed);
      const float baseline=best;
      Vector3 chosen=current;float chosenSpeed=currentSpeed;
      const Vector3 options[]={current,forward,forward.GetRotated2D(.35f),forward.GetRotated2D(-.35f),
          forward.GetRotated2D(.70f),forward.GetRotated2D(-.70f),
          forward.GetRotated2D(1.05f),forward.GetRotated2D(-1.05f)};
      for(const auto& dir:options){
        const float turn=dir.coords[0]*facing.coords[0]+dir.coords[1]*facing.coords[1];
        const float cap=AITactics::CarrySpeedLimit(skill,nearest,gap,turn);
        for(float fraction:{.45f,.62f,.78f,1.0f}){
          if(fraction>cap+.0001f)continue;
          const float rating=score(dir,fraction);
          if(rating>best){best=rating;chosen=dir;chosenSpeed=fraction;}
        }
      }
      if(best>baseline+.20f && best>-999.0f){
        desiredDirection=chosen;
        desiredVelocity=sprintVelocity*chosenSpeed;
        match->tribunCarryTrials[team->GetID()].Begin(player->GetID(),myPos.coords[0],-side,skill,match->GetActualTime_ms());
      }
    }
  }
  desiredVelocity = RangeVelocity(desiredVelocity);
}

Vector3 AI_GetForceFieldMovement'''),
    ])

    # Stage 67: exploit closing defender momentum; observe the same named defender after the carry.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool DuelEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_DUEL");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
''' + DUEL_RULES + "struct FixedDurationClock {"),
    ])
    edit(root, "src/onthepitch/match.hpp", [
        ("  AITactics::CarryTrial tribunCarryTrials[2];", "  AITactics::CarryTrial tribunCarryTrials[2];\n  AITactics::DuelTrial tribunDuelTrials[2];"),
    ])
    edit(root, "src/onthepitch/match.cpp", [
        ("    if(AITactics::CreativeCarryEnabled()){", r'''    if(AITactics::DuelEnabled()){
      for(int t=0;t<2;++t){
        auto& trial=tribunDuelTrials[t];
        if(trial.carrier<0)continue;
        auto* carrier=teams[t]->GetPlayer(trial.carrier);
        auto* defender=teams[1-t]->GetPlayer(trial.defender);
        auto* own=teams[t]->GetDesignatedTeamPossessionPlayer();
        const bool invalid=!IsInPlay()||IsInSetPiece()||GetBallRetainer()||
            !carrier||!defender||!carrier->IsActive()||!defender->IsActive();
        const bool confirmed=own&&own->HasUniquePossession()&&GetLastTouchPlayer()==own;
        trial.Observe(confirmed?own->GetID():-1,teams[1-t]->HasUniquePossession(),invalid,
            carrier?carrier->GetPosition().coords[0]:0.0f,defender?defender->GetPosition().coords[0]:0.0f,
            carrier&&defender?(carrier->GetPosition()-defender->GetPosition()).Get2D().GetLength():0.0f,actualTime_ms);
      }
    }
    if(AITactics::CreativeCarryEnabled()){'''),
        ("  for(auto& trial:tribunCarryTrials)trial.Cancel(GetActualTime_ms());",
         "  for(auto& trial:tribunCarryTrials)trial.Cancel(GetActualTime_ms());\n  for(auto& trial:tribunDuelTrials)trial.Cancel(GetActualTime_ms());"),
    ])
    edit(root, "src/onthepitch/AIsupport/AIfunctions.cpp", [
        ("  desiredVelocity = RangeVelocity(desiredVelocity);\n}\n\nVector3 AI_GetForceFieldMovement", r'''  if(AITactics::DuelEnabled() && player->HasUniquePossession() &&
      match->IsInPlay()&&!match->IsInSetPiece()&&!match->GetBallRetainer()&&
      !team->GetHumanGamerCount()&&player->GetFormationEntry().role!=e_PlayerRole_GK){
    const float skill=AITactics::ControlSkill(player->GetStat("technical_dribble"),
        player->GetStat("technical_ballcontrol"),player->GetStat("physical_agility"),player->GetStat("physical_balance"));
    const float gap=(mentalImage->GetBallPrediction(0).Get2D()-myPos).GetLength();
    const float depth=pitchHalfW+side*myPos.coords[0];
    auto& trial=match->tribunDuelTrials[team->GetID()];
    if(depth>=8.0f&&depth<=55.0f&&(trial.carrier<0||trial.carrier==player->GetID())){
      Player* defender=nullptr;
      float closest=100.0f;
      for(auto* rival:opponents){
        if(!rival||!rival->IsActive()||rival->GetFormationEntry().role==e_PlayerRole_GK)continue;
        if(trial.carrier>=0&&rival->GetID()!=trial.defender)continue;
        const auto delta=(rival->GetPosition()-myPos).Get2D();
        const float distance=delta.GetLength();
        if(distance<.01f)continue;
        const auto relative=rival->GetMovement()-myMov;
        const float closing=-(relative.coords[0]*delta.coords[0]+relative.coords[1]*delta.coords[1])/distance;
        if(AITactics::DuelEligible(delta.coords[0]*-side,distance,closing,gap,skill)&&distance<closest){
          closest=distance;defender=rival;
        }
      }
      if(defender){
        const Vector3 forward(-side,0,0);
        const auto facing=player->GetDirectionVec().Get2D().GetNormalized(forward);
        const auto current=desiredDirection.Get2D().GetNormalized(facing);
        const auto rivalMotion=defender->GetMovement().Get2D();
        auto rate=[&](const Vector3& dir,float speed){
          const float turn=dir.coords[0]*facing.coords[0]+dir.coords[1]*facing.coords[1];
          const float advance=sprintVelocity*speed*.55f;
          const auto end=myPos+dir*advance;
          if(std::abs(end.coords[0])>pitchHalfW-1.5f||std::abs(end.coords[1])>pitchHalfH-1.5f)return -1000.0f;
          float clearance=100.0f;
          for(const auto& opp:opponentPlayerImages)for(float time:{.18f,.36f,.55f}){
            const auto point=myPos+dir*(sprintVelocity*speed*time);
            clearance=std::min(clearance,(point-opp.position-opp.movement*time).Get2D().GetLength());
          }
          // Reward exiting opposite a defender's lateral momentum, not magical misdirection.
          const float wrongFoot=-dir.coords[1]*std::clamp(rivalMotion.coords[1]/3.0f,-1.0f,1.0f);
          return AITactics::DuelEscapeScore(dir.coords[0]*-side*advance,clearance,turn,speed,skill,wrongFoot);
        };
        const float baseline=rate(current,clamp(desiredVelocity/sprintVelocity,0.0f,1.0f));
        float best=baseline,chosenSpeed=0.0f;Vector3 chosen=current;
        for(float angle:{-.95f,-.60f,-.30f,.30f,.60f,.95f}){
          const auto dir=forward.GetRotated2D(angle);
          const float turn=dir.coords[0]*facing.coords[0]+dir.coords[1]*facing.coords[1];
          const float cap=AITactics::CarrySpeedLimit(skill,closest,gap,turn);
          for(float fraction:{.45f,.62f,.78f,.90f}){
            if(fraction>cap+.0001f)continue;
            const float score=rate(dir,fraction);
            if(score>best){best=score;chosen=dir;chosenSpeed=fraction;}
          }
        }
        if(best>baseline+.25f&&best>-999.0f&&
            (trial.carrier==player->GetID()||trial.Begin(player->GetID(),defender->GetID(),myPos.coords[0],-side,match->GetActualTime_ms()))){
          desiredDirection=chosen;desiredVelocity=sprintVelocity*chosenSpeed;
        }
      }
    }
  }
  desiredVelocity = RangeVelocity(desiredVelocity);
}

Vector3 AI_GetForceFieldMovement'''),
    ])

    # Stage 68: bounded hold-up behavior, followed by a native safe support pass.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool HoldUpEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_HOLD_UP");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
''' + HOLD_UP_RULES + "struct FixedDurationClock {"),
    ])
    edit(root, "src/onthepitch/match.hpp", [
        ("  AITactics::DuelTrial tribunDuelTrials[2];", "  AITactics::DuelTrial tribunDuelTrials[2];\n  AITactics::HoldTrial tribunHoldTrials[2];"),
    ])
    edit(root, "src/onthepitch/match.cpp", [
        ("    if(AITactics::DuelEnabled()){", r'''    if(AITactics::HoldUpEnabled()){
      for(int t=0;t<2;++t){
        auto& trial=tribunHoldTrials[t];
        if(!trial.stage)continue;
        auto* carrier=teams[t]->GetPlayer(trial.carrier);
        auto* receiver=trial.stage==3?teams[t]->GetPlayer(trial.receiver):nullptr;
        auto* own=teams[t]->GetDesignatedTeamPossessionPlayer();
        const bool invalid=!IsInPlay()||IsInSetPiece()||GetBallRetainer()||
          !carrier||!carrier->IsActive()||(trial.stage==3&&(!receiver||!receiver->IsActive()));
        const bool confirmed=own&&own->HasUniquePossession()&&GetLastTouchPlayer()==own;
        trial.Observe(confirmed?own->GetID():-1,confirmed?own->GetLastTouchTime_ms():0,
          teams[1-t]->HasUniquePossession(),invalid,actualTime_ms);
      }
    }
    if(AITactics::DuelEnabled()){'''),
        ("  for(auto& trial:tribunDuelTrials)trial.Cancel(GetActualTime_ms());",
         "  for(auto& trial:tribunDuelTrials)trial.Cancel(GetActualTime_ms());\n  for(auto& trial:tribunHoldTrials)trial.Cancel(GetActualTime_ms());"),
    ])
    edit(root, "src/onthepitch/teamAIcontroller.cpp", [
        ("  if(TribunTriangleContact(passer,receiver,shortPass))return;", r'''  if(AITactics::HoldUpEnabled()){
    auto& trial=match->tribunHoldTrials[team->GetID()];
    if(trial.stage&& !trial.Pass(passer?passer->GetID():-1,receiver?receiver->GetID():-1,shortPass,match->GetActualTime_ms()))
      trial.Cancel(match->GetActualTime_ms());
  }
  if(TribunTriangleContact(passer,receiver,shortPass))return;'''),
        ("  tribunTriangle.Clear(match->GetActualTime_ms());\n  if(!shooter", "  tribunTriangle.Clear(match->GetActualTime_ms());\n  match->tribunHoldTrials[team->GetID()].Cancel(match->GetActualTime_ms());\n  if(!shooter"),
    ])
    edit(root, "src/onthepitch/AIsupport/AIfunctions.cpp", [
        ("  desiredVelocity = RangeVelocity(desiredVelocity);\n}\n\nVector3 AI_GetForceFieldMovement", r'''  if(AITactics::HoldUpEnabled()&&player->HasUniquePossession()&&match->IsInPlay()&&
      !match->IsInSetPiece()&&!match->GetBallRetainer()&&!team->GetHumanGamerCount()&&
      AI_GetMindSet(player->GetDynamicFormationEntry().role)>=.55f&&player->GetFormationEntry().role!=e_PlayerRole_GK){
    const auto facing=player->GetDirectionVec().Get2D().GetNormalized(Vector3(-side,0,0));
    const float depth=pitchHalfW+side*myPos.coords[0];
    const float gap=(mentalImage->GetBallPrediction(0).Get2D()-myPos).GetLength();
    const float skill=AITactics::HoldSkill(player->GetStat("physical_balance"),
        player->GetStat("technical_ballcontrol"),player->GetStat("mental_calmness"));
    float nearest=100.0f;Vector3 threat(0);
    for(const auto& opp:opponentPlayerImages){
      const auto offset=(opp.position-myPos).Get2D();
      if(offset.GetLength()<nearest){nearest=offset.GetLength();threat=offset;}
    }
    auto& trial=match->tribunHoldTrials[team->GetID()];
    const auto now=match->GetActualTime_ms();
    if((!trial.stage||((trial.stage==1||trial.stage==2)&&trial.carrier==player->GetID()))&&
        AITactics::HoldEligible(depth,facing.coords[0]*-side,nearest,gap,skill)){
      auto rate=[&](const Vector3& dir){
        const auto end=myPos+dir*1.1f;
        if(std::abs(end.coords[0])>pitchHalfW-1.5f||std::abs(end.coords[1])>pitchHalfH-1.5f)return -1000.0f;
        float clearance=100.0f;
        for(const auto& opp:opponentPlayerImages)
          clearance=std::min(clearance,(end-opp.position-opp.movement*.25f).Get2D().GetLength());
        const auto unit=threat.GetNormalized(0);
        const float alignment=dir.coords[0]*facing.coords[0]+dir.coords[1]*facing.coords[1];
        const float screen=-(dir.coords[0]*unit.coords[0]+dir.coords[1]*unit.coords[1]);
        return AITactics::ShieldScore(clearance,alignment,screen,dir.coords[0]*-side*1.1f);
      };
      Vector3 chosen=facing;float best=rate(facing);
      for(float angle:{-.85f,-.4f,.4f,.85f}){
        const auto dir=facing.GetRotated2D(angle);
        const auto score=rate(dir);
        if(score>best){best=score;chosen=dir;}
      }
      if(best>-999.0f&&(trial.stage||trial.Begin(player->GetID(),now))){
        desiredDirection=chosen;
        desiredVelocity=std::min(desiredVelocity,sprintVelocity*(.30f+.10f*skill));
      }
    }
  }
  desiredVelocity = RangeVelocity(desiredVelocity);
}

Vector3 AI_GetForceFieldMovement'''),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet || timedCandidate || lineBreak || triangleCandidate) {", r'''      bool holdOutlet=false;
      float holdOdds=0.0f;
      if(AITactics::HoldUpEnabled()&&runningPassEnabled&&
          match->tribunHoldTrials[team->GetID()].Ready(player->GetID(),match->GetActualTime_ms())&&
          mates.at(i)->GetFormationEntry().role!=e_PlayerRole_GK){
        const auto delta=mates.at(i)->GetPosition()-player->GetPosition();
        const float margin=passOffside-mates.at(i)->GetPosition().coords[0]*attackForward;
        if(AITactics::HoldOutlet(delta.GetLength(),delta.coords[0]*attackForward,margin,mateSit.spaceRating,1.0f,0.0f)){
          holdOdds=_GetPassingOdds(mates.at(i),e_FunctionType_ShortPass,opponentPlayerImages);
          holdOutlet=AITactics::HoldOutlet(delta.GetLength(),delta.coords[0]*attackForward,margin,mateSit.spaceRating,holdOdds,0.0f);
        }
      }
      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet || timedCandidate || lineBreak || triangleCandidate || holdOutlet) {'''),
        ("        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +", r'''        if(holdOutlet && holdOdds>=mateRating.passRating-.04f){
          mateRating.passType=e_FunctionType_ShortPass;
          mateRating.passRating=holdOdds;
          mateRating.supportRating+=.42f;
        }else if(holdOutlet&&!(progressiveCandidate||supportCandidate||runningCandidate||
          deliveryCandidate||pressureOutlet||returnCandidate||retentionOutlet||timedCandidate||lineBreak||triangleCandidate))continue;
        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +'''),
    ])

    # Stage 69: keeper-aware target comparison. No changes to native shot physics or forced goals.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool FinishEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_FINISH");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
''' + FINISH_RULES + "struct FixedDurationClock {"),
    ])
    edit(root, "src/onthepitch/match.hpp", [
        ("  AITactics::HoldTrial tribunHoldTrials[2];", "  AITactics::HoldTrial tribunHoldTrials[2];\n  AITactics::FinishProbe tribunFinishProbes[2];"),
    ])
    edit(root, "src/onthepitch/match.cpp", [
        ("  for(auto& trial:tribunHoldTrials)trial.Cancel(GetActualTime_ms());",
         "  for(auto& trial:tribunHoldTrials)trial.Cancel(GetActualTime_ms());\n  for(auto& probe:tribunFinishProbes)probe.Clear();"),
    ])
    edit(root, "src/onthepitch/teamAIcontroller.cpp", [
        ("  match->tribunHoldTrials[team->GetID()].Cancel(match->GetActualTime_ms());",
         r'''  match->tribunHoldTrials[team->GetID()].Cancel(match->GetActualTime_ms());
  if(AITactics::FinishEnabled()&&shooter)
    match->tribunFinishProbes[team->GetID()].Contact(shooter->GetID(),match->GetActualTime_ms());'''),
        ("  if(TribunTriangleContact(passer,receiver,shortPass))return;", r'''  if(AITactics::FinishEnabled())match->tribunFinishProbes[team->GetID()].Clear();
  if(TribunTriangleContact(passer,receiver,shortPass))return;'''),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("    odds = std::pow(odds, 0.5f);", r'''    bool finishEvaluated=false,finishChanged=false,finishPriority=false;
    if(AITactics::FinishEnabled()&&CastPlayer()->HasUniquePossession()&&match->IsInPlay()&&
        !match->IsInSetPiece()&&!match->GetBallRetainer()&&!team->GetHumanGamerCount()&&
        CastPlayer()->GetFormationEntry().role!=e_PlayerRole_GK){
      const float skill=player->GetStat("technical_shot");
      const auto from=player->GetPosition()+player->GetMovement()*.12f;
      const float forward=-team->GetSide();
      auto* keeper=match->GetTeam(abs(team->GetID()-1))->GetGoalie();
      if(keeper&&keeper->IsActive()&&AITactics::FinishEligible(shotDistance,shotAngle,skill,odds)){
        std::vector<PlayerImage> outfield;
        for(const auto& rival:opponentPlayerImages)
          if(rival.dynamicFormationEntry.role!=e_PlayerRole_GK)outfield.push_back(rival);
        const auto keeperPos=keeper->GetPosition()+keeper->GetMovement()*.20f;
        const float goalX=(pitchHalfW+1.0f)*forward;
        const float denom=(goalX-from.coords[0])*forward;
        const float u=denom>.01f?clamp((keeperPos.coords[0]-from.coords[0])*forward/denom,0.0f,1.0f):1.0f;
        auto keeperGap=[&](float targetY){
          return std::abs(from.coords[1]+(targetY-from.coords[1])*u-keeperPos.coords[1]);
        };
        auto fieldOdds=[&](float targetY){
          return _GetPassingOdds(Vector3(goalX,targetY,0),e_FunctionType_Shot,outfield,3.0f);
        };
        const float originalY=y,originalOdds=odds;
        // Compare the baseline aim at its actual position (which may be near the post).
        const float baselineField=fieldOdds(y);
        float best=.48f*odds+.32f*baselineField+.20f*clamp(keeperGap(y)/3.0f,0.0f,1.0f)-
            .10f*(1.0f-skill)*std::abs(y)/3.0f;
        const float baseline=best;
        float bestY=y,bestOdds=odds,bestField=baselineField;
        for(float targetY:{-2.9f,-1.45f,0.0f,1.45f,2.9f}){
          const float nativeOdds=_GetPassingOdds(Vector3(goalX,targetY,0),e_FunctionType_Shot,opponentPlayerImages,3.0f);
          if(nativeOdds<originalOdds-.08f||!AITactics::FinishEligible(shotDistance,shotAngle,skill,nativeOdds))continue;
          const float clear=fieldOdds(targetY);
          const float score=AITactics::FinishTargetScore(nativeOdds,clear,keeperGap(targetY),targetY,skill);
          if(score>best){best=score;bestY=targetY;bestOdds=nativeOdds;bestField=clear;}
        }
        if(best>baseline+.025f){y=bestY;odds=bestOdds;finishChanged=std::abs(y-originalY)>.10f;}
        else bestField=baselineField;
        finishEvaluated=true;
        const float passOdds=bestMateRating.player?bestMateRating.passRating:0.0f;
        finishPriority=AITactics::FinishPreferShot(shotDistance,shotAngle,skill,odds,bestField,passOdds);
      }
    }
    odds = std::pow(odds, 0.5f);'''),
        ("          AITactics::PrioritizeGoodShot(distance,angle,odds,CastPlayer()->HasUniquePossession()) ||", r'''          finishPriority ||
          AITactics::PrioritizeGoodShot(distance,angle,odds,CastPlayer()->HasUniquePossession()) ||'''),
        ("        commandQueue.push_back(command);\n    }\n  }\n\n  e_Velocity enumVelocity", r'''        commandQueue.push_back(command);
      if(finishEvaluated)
        match->tribunFinishProbes[team->GetID()].Issue(player->GetID(),match->GetActualTime_ms(),finishChanged,finishPriority);
    }
  }

  e_Velocity enumVelocity'''),
    ])

    # Stage 70: conservative 1v1 angle narrowing and reachable shot interception.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool KeeperAIEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_KEEPER_AI");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
''' + KEEPER_RULES + "struct FixedDurationClock {"),
    ])
    edit(root, "src/onthepitch/match.hpp", [
        ("  AITactics::FinishProbe tribunFinishProbes[2];", "  AITactics::FinishProbe tribunFinishProbes[2];\n  AITactics::KeeperProbe tribunKeeperProbes[2];"),
    ])
    edit(root, "src/onthepitch/match.cpp", [
        ("    if(AITactics::HoldUpEnabled()){", r'''    if(AITactics::KeeperAIEnabled()){
      for(int t=0;t<2;++t){
        auto& probe=tribunKeeperProbes[t];
        if(!probe.kind)continue;
        auto* keeper=teams[t]->GetGoalie();
        const bool invalid=!IsInPlay()||IsInSetPiece()||!keeper||!keeper->IsActive()||keeper->GetID()!=probe.keeper;
        const bool touch=keeper&&GetLastTouchPlayer()==keeper;
        const bool control=keeper&&(keeper->HasUniquePossession()||GetBallRetainer()==keeper);
        probe.Observe(touch,control,invalid,keeper?keeper->GetLastTouchTime_ms():0,actualTime_ms);
      }
    }
    if(AITactics::HoldUpEnabled()){'''),
        ("  for(auto& probe:tribunFinishProbes)probe.Clear();",
         "  for(auto& probe:tribunFinishProbes)probe.Clear();\n  for(auto& probe:tribunKeeperProbes)probe.Clear(GetActualTime_ms());"),
    ])
    edit(root, "src/onthepitch/player/controller/strategies/offtheball/goalie_default.cpp", [
        ("  direction = targetPos - player->GetPosition();", r'''  if(AITactics::KeeperAIEnabled()&&match->IsInPlay()&&!match->IsInSetPiece()&&
      !match->GetBallRetainer()&&!team->GetHumanGamerCount()&&!claimingLooseBall&&
      !team->HasUniquePossession()&&team->GetController()->GetEndApplyKeeperRush_ms()<=match->GetActualTime_ms()){
    const float side=team->GetSide();
    const float skill=AITactics::KeeperRead(player->GetStat("mental_defensivepositioning"),
        player->GetStat("physical_reaction"),player->GetStat("mental_calmness"));
    const auto now=match->GetActualTime_ms();
    auto& probe=match->tribunKeeperProbes[team->GetID()];
    const auto eta=[&](const Vector3& point){
      return static_cast<int>(AI_GetTimeNeededForDistance_ms(player->GetPosition(),player->GetMovement(),
          point,player->GetMaxVelocity(),false,-1,false).usual_ms);
    };
    if(IsBallBoundForGoal()){
      // Existing native deflect/pickup commands remain authoritative.
      // Select an earlier reachable low trajectory point only before goal-line crossing.
      const auto current=mentalImage->GetBallPrediction(0);
      if(pitchHalfW-current.coords[0]*side>0.6f&&pitchHalfW-current.coords[0]*side<30.0f){
        for(unsigned int ms=100;ms<=850;ms+=50){
          const auto predicted=mentalImage->GetBallPrediction(ms);
          const float depth=pitchHalfW-predicted.coords[0]*side;
          if(depth<.6f)break;
          const auto ground=predicted.Get2D();
          const float distance=(ground-player->GetPosition()).GetLength();
          if(!AITactics::KeeperIntercept(depth,predicted.coords[1],predicted.coords[2],distance,0,ms,skill))continue;
          if(depth<=pitchHalfW-targetPos.coords[0]*side+.35f)continue;
          if(!AITactics::KeeperIntercept(depth,predicted.coords[1],predicted.coords[2],distance,eta(ground),ms,skill))continue;
          targetPos=ground;maxVelocity=sprintVelocity;
          probe.Begin(CastPlayer()->GetID(),2,now);
          break;
        }
      }
    }else{
      auto* opp=controller->GetOppTeam()->GetDesignatedTeamPossessionPlayer();
      if(opp&&opp->IsActive()&&opp->HasUniquePossession()){
        const auto ball=mentalImage->GetBallPrediction(0).Get2D();
        const auto carrier=opp->GetPosition().Get2D();
        const auto predicted=(carrier+opp->GetMovement()*.20f).Get2D();
        const float depth=pitchHalfW-predicted.coords[0]*side;
        const float lateral=std::abs(predicted.coords[1]);
        const float gap=(ball-carrier).GetLength();
        if(AITactics::NarrowEligible(depth,lateral,gap,opp->GetMovement().coords[0]*side,100,100,skill)){
          std::vector<Player*> mates,rivals;
          team->GetActivePlayers(mates);controller->GetOppTeam()->GetActivePlayers(rivals);
          float cover=100.0f,helper=100.0f;
          for(auto* mate:mates)if(mate!=CastPlayer()&&mate->IsActive()&&
              mate->GetPosition().coords[0]*side>=carrier.coords[0]*side-.5f)
            cover=std::min(cover,(mate->GetPosition()+mate->GetMovement()*.2f-predicted).Get2D().GetLength());
          for(auto* rival:rivals)if(rival!=opp&&rival->IsActive()&&
              rival->GetPosition().coords[0]*side>=carrier.coords[0]*side-2.0f)
            helper=std::min(helper,(rival->GetPosition()-carrier).Get2D().GetLength());
          if(AITactics::NarrowEligible(depth,lateral,gap,opp->GetMovement().coords[0]*side,cover,helper,skill)){
            const float d=AITactics::NarrowDepth(depth,lateral,skill);
            // Position on the ball-to-goal-center ray, bounded away from the attacker.
            const Vector3 candidate((pitchHalfW-d)*side,clamp(predicted.coords[1]*d/depth,-3.3f,3.3f),0);
            const float currentDepth=pitchHalfW-targetPos.coords[0]*side;
            if(d>currentDepth+.35f&&(candidate-carrier).GetLength()>=2.0f&&eta(candidate)<=850){
              targetPos=candidate;maxVelocity=sprintVelocity;
              probe.Begin(CastPlayer()->GetID(),1,now);
            }
          }
        }
      }
    }
  }
  direction = targetPos - player->GetPosition();'''),
    ])

    # Stage 71: keep non-pressing defenders in staggered, formation-relative cover.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool DefenseShapeEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_DEFENSE_SHAPE");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
''' + DEFENSE_SHAPE_RULES + "struct FixedDurationClock {"),
    ])
    edit(root, "src/onthepitch/match.hpp", [
        ("  AITactics::KeeperProbe tribunKeeperProbes[2];", "  AITactics::KeeperProbe tribunKeeperProbes[2];\n  AITactics::DefenseProbe tribunDefenseProbes[2];"),
    ])
    edit(root, "src/onthepitch/player/controller/strategies/offtheball/default_def.cpp", [
        ("    // offside trap (used to be applied before AddDefensiveComponent)", r'''    if(AITactics::DefenseShapeEnabled()&&match->IsInPlay()&&!match->IsInSetPiece()&&
        !match->GetBallRetainer()&&!team->GetHumanGamerCount()){
      auto* rival=controller->GetOppTeam()->GetDesignatedTeamPossessionPlayer();
      const auto role=CastPlayer()->GetFormationEntry().role;
      if(rival&&rival->IsActive()&&rival->HasUniquePossession()&&
          (role==e_PlayerRole_CB||role==e_PlayerRole_LB||role==e_PlayerRole_RB)){
        const float side=team->GetSide();
        const auto threat=(rival->GetPosition()+rival->GetMovement()*.25f).Get2D();
        const float depth=pitchHalfW-threat.coords[0]*side;
        const bool secondary=team->GetController()->GetEndApplyTeamPressure_ms()>match->GetActualTime_ms()&&
            team->GetController()->GetTeamPressurePlayer()==CastPlayer();
        if(AITactics::CoverEligible(depth,CastPlayer()==team->GetDesignatedTeamPossessionPlayer(),
            secondary,CastPlayer()->GetManMarkingID()!=-1,team->HasUniquePossession())){
          const float press=clamp(team->GetTeamData()->GetTactics().userProperties.GetReal("team_pressure",.5f),0.0f,1.0f);
          const float staticDepth=pitchHalfW-desiredPosition_static.coords[0]*side;
          const float nearSide=desiredPosition_static.coords[1]*threat.coords[1]>0?1.0f:0.0f;
          const float targetDepth=AITactics::CoverDepth(staticDepth,depth,press,nearSide);
          const float targetY=AITactics::CoverWidth(desiredPosition_static.coords[1],threat.coords[1],press);
          const Vector3 cover((pitchHalfW-targetDepth)*side,targetY,0);
          const auto correction=cover-desiredPosition;
          // Limit correction to a 4 m target adjustment, no position teleportation.
          if(correction.GetLength()>.3f){
            desiredPosition+=correction.GetNormalized(0)*std::min(4.0f,correction.GetLength())*.75f;
            ++match->tribunDefenseProbes[team->GetID()].coverTargets;
          }
        }
      }
    }
    // offside trap (used to be applied before AddDefensiveComponent)'''),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("        std::vector<Player*> closestPlayers;\n        if(huntingPlayersNum>0)", r'''        if(AITactics::DefenseShapeEnabled()&&huntingPlayersNum>0&&match->IsInPlay()&&
            !match->IsInSetPiece()&&!match->GetBallRetainer()&&!team->GetHumanGamerCount()&&opp&&opp->HasUniquePossession()){
          const auto role=CastPlayer()->GetFormationEntry().role;
          const bool secondary=team->GetController()->GetEndApplyTeamPressure_ms()>match->GetActualTime_ms()&&
              team->GetController()->GetTeamPressurePlayer()==CastPlayer();
          const float depth=pitchHalfW-opp->GetPosition().coords[0]*team->GetSide();
          if((role==e_PlayerRole_CB||role==e_PlayerRole_LB||role==e_PlayerRole_RB)&&
              AITactics::CoverEligible(depth,CastPlayer()==team->GetDesignatedTeamPossessionPlayer(),
                  secondary,CastPlayer()->GetManMarkingID()!=-1,team->HasUniquePossession())){
            huntingPlayersNum=0;
            ++match->tribunDefenseProbes[team->GetID()].huntsSuppressed;
          }
        }
        std::vector<Player*> closestPlayers;
        if(huntingPlayersNum>0)'''),
    ])
    edit(root, "src/onthepitch/match.cpp", [
        ("    if(AITactics::KeeperAIEnabled()){", r'''    // Measure actual line positions in both reference and candidate. No inference from targets.
    if(AITactics::ShortMatchAttackEnabled()&&AITactics::FixedDurationEnabled()&&
        IsInPlay()&&!IsInSetPiece()&&!GetBallRetainer()&&actualTime_ms%100==0){
      for(int t=0;t<2;++t){
        auto* own=GetTeam(t);
        auto* rival=teams[1-t]->GetDesignatedTeamPossessionPlayer();
        if(!rival||!rival->HasUniquePossession()||own->HasUniquePossession())continue;
        const float side=own->GetSide();
        const float depth=pitchHalfW-rival->GetPosition().coords[0]*side;
        if(depth<9.0f||depth>40.0f)continue;
        std::vector<Player*> active;own->GetActivePlayers(active);
        std::vector<float> ys;
        float minDepth=100.0f,maxDepth=-100.0f;
        int goalSide=0;
        for(auto* defender:active){
          const auto role=defender->GetFormationEntry().role;
          if(role!=e_PlayerRole_CB&&role!=e_PlayerRole_LB&&role!=e_PlayerRole_RB)continue;
          const auto pos=defender->GetPosition();
          const float d=pitchHalfW-pos.coords[0]*side;
          minDepth=std::min(minDepth,d);maxDepth=std::max(maxDepth,d);
          ys.push_back(pos.coords[1]);if(d<=depth-1.0f)++goalSide;
        }
        if(ys.size()<3)continue;
        std::sort(ys.begin(),ys.end());
        float gap=0;for(size_t j=1;j<ys.size();++j)gap=std::max(gap,ys[j]-ys[j-1]);
        tribunDefenseProbes[t].Sample(maxDepth-minDepth,gap,goalSide);
      }
    }
    if(AITactics::KeeperAIEnabled()){'''),
    ])

    # Stage 72: confirmed turnovers, bounded counter windows and safe recovery policy.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool TransitionEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_TRANSITION");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
''' + TRANSITION_RULES + "struct FixedDurationClock {"),
    ])
    edit(root, "src/onthepitch/teamAIcontroller.hpp", [
        ("  const AITactics::TriangleState& GetTribunTriangle() const {return tribunTriangle;}", "  const AITactics::TriangleState& GetTribunTriangle() const {return tribunTriangle;}\n  const AITactics::TransitionState& GetTribunTransition() const {return tribunTransition;}"),
        ("  AITactics::TriangleState tribunTriangle;", "  AITactics::TriangleState tribunTriangle;\n  AITactics::TransitionState tribunTransition;\n  float tribunTransitionPassX=0;"),
    ])
    edit(root, "src/onthepitch/teamAIcontroller.cpp", [
        ("  CalculateSituation();\n  if(tribunTriangle.stage){", r'''  CalculateSituation();
  if(AITactics::TransitionEnabled()&&!team->GetHumanGamerCount()){
    const auto now=match->GetActualTime_ms();
    auto* rival=match->GetTeam(abs(team->GetID()-1));
    auto* ownPlayer=team->GetDesignatedTeamPossessionPlayer();
    auto* oppPlayer=rival->GetDesignatedTeamPossessionPlayer();
    const bool open=match->IsInPlay()&&!match->IsInSetPiece()&&!match->GetBallRetainer();
    const bool ownControl=ownPlayer&&ownPlayer->HasUniquePossession()&&match->GetLastTouchPlayer()==ownPlayer;
    const bool oppControl=oppPlayer&&oppPlayer->HasUniquePossession()&&match->GetLastTouchPlayer()==oppPlayer;
    const int event=tribunTransition.Observe(ownControl&&!oppControl?1:oppControl&&!ownControl?0:-1,now,open);
    if(event){
      const float side=team->GetSide();
      const auto ball=match->GetBall()->Predict(0).Get2D();
      const auto& tactics=team->GetTeamData()->GetTactics().userProperties;
      const float press=tactics.GetReal("team_pressure",.5f),counter=tactics.GetReal("counter_attack",.5f);
      const int goalDiff=match->GetMatchData()->GetGoalCount(team->GetID())-match->GetMatchData()->GetGoalCount(rival->GetID());
      const bool late=match->GetMatchTime_ms()>=4200000;
      std::vector<Player*> mates,rivals;team->GetActivePlayers(mates);rival->GetActivePlayers(rivals);
      if(event==1&&ownPlayer){
        int cover=0;float space=100.0f;
        const auto probe=ball+Vector3(-side*5.0f,0,0);
        for(auto* other:rivals)if(other!=rival->GetGoalie()){
          if(other->GetPosition().coords[0]*side<ball.coords[0]*side&&
              std::abs(other->GetPosition().coords[1]-ball.coords[1])<15.0f)++cover;
          space=std::min(space,(other->GetPosition()+other->GetMovement()*.2f-probe).Get2D().GetLength());
        }
        if(AITactics::TransitionCounter(counter,pitchHalfW+ball.coords[0]*side,cover,space,goalDiff,late)){
          tribunTransition.counter=true;++tribunTransition.counters;
          auto* runner=SelectAttackingRunPlayer(team);
          if(runner&&runner!=ownPlayer&&runner->IsActive()&&AI_GetMindSet(runner->GetDynamicFormationEntry().role)>=.55f&&
              (runner->GetPosition()-ball).GetLength()<=30.0f)ApplyAttackingRun(runner);
        }
      }else if(event==-1){
        int cover=0;float nearest=1000.0f;
        for(auto* mate:mates)if(mate!=team->GetGoalie()){
          if(mate->GetPosition().coords[0]*side>=ball.coords[0]*side+1.0f)++cover;
          nearest=std::min(nearest,(mate->GetPosition()-ball).Get2D().GetLength());
        }
        const float territory=AITactics::GetAttackingTerritory(ball.coords[0],side,pitchHalfW);
        tribunTransition.press=AITactics::TransitionPress(press,territory,nearest,cover,goalDiff,late);
        if(tribunTransition.press){++tribunTransition.presses;ApplyZonePressure();}
        else{++tribunTransition.retreats;zonePressureActive=false;endApplyTeamPressure_ms=now;teamPressurePlayer=nullptr;}
        endApplyAttackingRun_ms=now;attackingRunPlayer=nullptr;forwardSupportPlayer=nullptr;
      }
    }
  }
  if(tribunTriangle.stage){'''),
        ("      if (AITactics::ShouldStartZonePressure(pressureSetting, territory, primaryDistance))", r'''      if ((!AITactics::TransitionEnabled() ||
            (tribunTransition.Losing(match->GetActualTime_ms())&&tribunTransition.press)) &&
          AITactics::ShouldStartZonePressure(pressureSetting, territory, primaryDistance))'''),
        ("  if(TribunTriangleContact(passer,receiver,shortPass))return;", r'''  if(AITactics::TransitionEnabled()&&passer&&receiver&&receiver->GetTeam()==team&&
      tribunTransition.Winning(match->GetActualTime_ms())&&
      (receiver->GetPosition().coords[0]-passer->GetPosition().coords[0])*-team->GetSide()>=5.0f)
    ++tribunTransition.forwardPasses;
  if(TribunTriangleContact(passer,receiver,shortPass))return;'''),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet || timedCandidate || lineBreak || triangleCandidate || holdOutlet) {", r'''      bool counterCandidate=false;
      float counterOdds=0;
      e_FunctionType counterType=e_FunctionType_ShortPass;
      if(runningPassEnabled&&AITactics::TransitionEnabled()&&
          team->GetController()->GetTribunTransition().Winning(match->GetActualTime_ms())&&
          mates.at(i)->GetFormationEntry().role!=e_PlayerRole_GK){
        const auto pos=mates.at(i)->GetPosition(),delta=pos-player->GetPosition();
        const float progress=delta.coords[0]*attackForward;
        const float margin=passOffside-pos.coords[0]*attackForward;
        if(AITactics::TransitionPass(progress,delta.GetLength(),margin,mateSit.spaceRating,1.0f,0.0f)){
          const float a=_GetPassingOdds(mates.at(i),e_FunctionType_ShortPass,opponentPlayerImages);
          const float b=_GetPassingOdds(mates.at(i),e_FunctionType_LongPass,opponentPlayerImages);
          counterType=b>a?e_FunctionType_LongPass:e_FunctionType_ShortPass;counterOdds=std::max(a,b);
          counterCandidate=AITactics::TransitionPass(progress,delta.GetLength(),margin,mateSit.spaceRating,counterOdds,0.0f);
        }
      }
      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet || timedCandidate || lineBreak || triangleCandidate || holdOutlet || counterCandidate) {'''),
        ("        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +", r'''        if(counterCandidate&&counterOdds>=mateRating.passRating-.04f){
          mateRating.passType=counterType;mateRating.passRating=counterOdds;mateRating.supportRating+=.32f;
        }else if(counterCandidate&&!(progressiveCandidate||supportCandidate||runningCandidate||deliveryCandidate||
            pressureOutlet||returnCandidate||retentionOutlet||timedCandidate||lineBreak||triangleCandidate||holdOutlet))continue;
        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +'''),
    ])

    # Stage 73: player-stat-driven formation-relative off-ball role profiles.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool RoleProfileEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_ROLE_PROFILE");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
''' + ROLE_PROFILE_RULES + "struct FixedDurationClock {"),
    ])
    edit(root, "src/onthepitch/teamAIcontroller.hpp", [
        ("  Vector3 GetAdaptedFormationPosition(Player* player, bool useDynamicFormationPosition = true);", r'''  Vector3 GetAdaptedFormationPosition(Player* player, bool useDynamicFormationPosition = true);
  int TribunRoleProfile(Player* player);
  void TribunApplyRoleProfile(Player* player,Vector3& desired,const Vector3& formation);'''),
    ])
    edit(root, "src/onthepitch/match.hpp", [
        ("  AITactics::DefenseProbe tribunDefenseProbes[2];", "  AITactics::DefenseProbe tribunDefenseProbes[2];\n  AITactics::RoleProbe tribunRoleProbes[2];"),
    ])
    edit(root, "src/onthepitch/teamAIcontroller.cpp", [
        ("Vector3 TeamAIController::GetAdaptedFormationPosition(Player* player,", r'''int TeamAIController::TribunRoleProfile(Player* player){
  if(!player||!player->IsActive())return AITactics::Neutral;
  AITactics::RoleFamily family=AITactics::Other;
  switch(player->GetFormationEntry().role){
    case e_PlayerRole_CF:family=AITactics::CF;break;
    case e_PlayerRole_LM:case e_PlayerRole_RM:family=AITactics::Wide;break;
    case e_PlayerRole_CM:case e_PlayerRole_AM:family=AITactics::Mid;break;
    case e_PlayerRole_DM:family=AITactics::DM;break;
    case e_PlayerRole_LB:case e_PlayerRole_RB:family=AITactics::FB;break;
    case e_PlayerRole_CB:family=AITactics::CB;break;
    default:break;
  }
  return AITactics::Profile(family,player->GetStat("physical_velocity"),
      .6f*player->GetStat("technical_shortpass")+.4f*player->GetStat("mental_vision"),
      player->GetStat("technical_shot"),
      .6f*player->GetStat("mental_defensivepositioning")+.4f*player->GetStat("technical_standingtackle"),
      .5f*player->GetStat("mental_workrate")+.5f*player->GetStat("physical_stamina"),
      player->GetStat("technical_ballcontrol"));
}
void TeamAIController::TribunApplyRoleProfile(Player* player,Vector3& desired,const Vector3& formation){
  if(!AITactics::ShortMatchAttackEnabled()||!AITactics::FixedDurationEnabled()||
      !match->IsInPlay()||match->IsInSetPiece()||match->GetBallRetainer()||
      team->GetHumanGamerCount()||!team->HasUniquePossession()||!player||player->HasUniquePossession()||
      player->GetManMarkingID()!=-1||player==team->GetDesignatedTeamPossessionPlayer()||
      (player==attackingRunPlayer&&endApplyAttackingRun_ms>match->GetActualTime_ms()))return;
  const int profile=TribunRoleProfile(player);
  if(profile==AITactics::Neutral)return;
  const auto ball=match->GetBall()->Predict(0).Get2D();
  const float side=team->GetSide(),depth=pitchHalfW+ball.coords[0]*side;
  if(depth<9.0f||depth>75.0f||(ball-player->GetPosition()).GetLength()>35.0f)return;
  auto& probe=match->tribunRoleProbes[team->GetID()];
  if(match->GetActualTime_ms()%100==0)
    probe.Sample(profile,(player->GetPosition().coords[0]-formation.coords[0])*-side,
        std::abs(player->GetPosition().coords[1])-std::abs(formation.coords[1]));
  if(!AITactics::RoleProfileEnabled())return;
  int cover=0;
  if(profile==AITactics::Overlap){
    std::vector<Player*> mates;team->GetActivePlayers(mates);
    for(auto* mate:mates)if(mate!=player&&mate!=team->GetGoalie()&&
        mate->GetPosition().coords[0]*side>=ball.coords[0]*side+2.0f)++cover;
  }
  const auto offset=AITactics::ProfileOffset(profile,formation.coords[1],ball.coords[1],cover);
  auto candidate=desired+Vector3(-side*offset.advance,offset.lateral,0);
  const float forward=-side;
  const float line=AI_GetOffsideLine(match,match->GetMentalImage(0),abs(team->GetID()-1))*forward;
  if(offset.advance>0&&candidate.coords[0]*forward>std::max(ball.coords[0]*forward,line)-1.2f)
    candidate.coords[0]=desired.coords[0];
  candidate.coords[0]=clamp(candidate.coords[0],-pitchHalfW+1.5f,pitchHalfW-1.5f);
  candidate.coords[1]=clamp(candidate.coords[1],-pitchHalfH+1.5f,pitchHalfH-1.5f);
  if((candidate-desired).GetLength()>.1f){desired=candidate;++probe.targets[profile];}
}
Vector3 TeamAIController::GetAdaptedFormationPosition(Player* player,'''),
    ])
    for strategy in ("default_off.cpp","default_mid.cpp","default_def.cpp"):
        edit(root, "src/onthepitch/player/controller/strategies/offtheball/"+strategy, [
            ("  direction = (desiredPosition - player->GetPosition()).GetNormalized(player->GetDirectionVec());", r'''  team->GetController()->TribunApplyRoleProfile(CastPlayer(),desiredPosition,desiredPosition_static);
  direction = (desiredPosition - player->GetPosition()).GetNormalized(player->GetDirectionVec());'''),
        ])
