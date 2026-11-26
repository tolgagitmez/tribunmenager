"""Opt-in seeded RNG and conservative short-match attack tuning."""
from pathlib import Path
from instrument import replace_once

def edit(root, name, replacements):
    p = Path(root) / name
    text = p.read_text(encoding="utf-8")
    for old, new in replacements:
        text = replace_once(text, old, new)
    p.write_text(text, encoding="utf-8")

PACE_RULES = r'''// Prefer usable forward outlets, never prohibit a necessary backpass.
inline bool PaceOutlet(float depth,float progress,float distance,float margin,float space,float odds){
  return std::isfinite(odds)&&depth>=4.0f&&depth<=55.0f&&progress>=4.0f&&
    distance>=5.0f&&distance<=27.0f&&margin>=1.3f&&space>=.52f&&odds>=.70f;
}
inline float PacePassBonus(float progress,float depth,float tempo){
  return (.12f+.12f*std::clamp(tempo,0.0f,1.0f))*
    std::clamp(progress/9.0f,.45f,1.0f)*(depth<=22.0f?1.25f:1.0f);
}
inline bool PaceShot(float distance,float angle,float odds,float skill,bool controlled){
  return controlled&&distance>=3.0f&&distance<=17.0f&&angle>=.70f&&odds>=.68f&&skill>=.52f;
}
'''

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
  unsigned long inspected=0,context=0,geometry=0,available=0;
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
  return ahead>=.35f&&ahead<=4.8f&&distance>=1.4f&&distance<=5.5f&&closing>=.25f&&gap<=1.25f&&skill>=.48f;
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
  unsigned long inspected=0,context=0,geometry=0,available=0;
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
  return depth>=9&&depth<=48&&facingForward<=.45f&&nearest>=.8f&&nearest<=4.0f&&gap<=1.25f&&skill>=.48f;
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
  unsigned long inspected=0,context=0,geometry=0,available=0;
  void End(unsigned long now){carrier=receiver=-1;stage=0;cooldown=now+700;}
  void Cancel(unsigned long now){if(stage){++cancelled;End(now);}}
  bool Begin(int id,unsigned long now){
    if(stage||now<cooldown||id<0)return false;
    carrier=id;stage=1;start=lastControl=now;expires=now+1200;++attempts;return true;
  }
  bool Ready(int id,unsigned long now)const{return (stage==2||(stage==1&&PressureHold185Enabled()))&&id==carrier&&now>=start&&now<expires;}
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
// Prefer an earlier reachable interception with a reaction-time reserve.
inline float KeeperInterceptScore(float depth,float lateral,float height,int eta,int arrival,float skill){
  if(!std::isfinite(depth)||!std::isfinite(lateral)||!std::isfinite(height)||!std::isfinite(skill)||
      eta<0||arrival<eta)return -1.0f;
  const float reserve=static_cast<float>(arrival-eta);
  return .42f*std::clamp(reserve/350.0f,0.0f,1.0f)+
         .28f*std::clamp(depth/7.0f,0.0f,1.0f)+
         .20f*(1.0f-std::clamp(std::abs(lateral)/5.0f,0.0f,1.0f))+
         .10f*(1.0f-std::clamp(height/2.0f,0.0f,1.0f));
}
// Score only targets that remain safely separated from the attacker.
inline float KeeperChallengeScore(float depth,float lateralError,float carrierGap,int eta,float skill){
  if(!std::isfinite(depth)||!std::isfinite(lateralError)||!std::isfinite(carrierGap)||!std::isfinite(skill)||
     depth<1.4f||depth>7.0f||carrierGap<2.0f||eta<0||eta>850)return -1.0f;
  const float minGap=2.4f-.4f*std::clamp(skill,0.0f,1.0f);
  if(carrierGap<minGap)return -1.0f;
  return .46f*depth/7.0f+.28f*(1.0f-std::clamp(static_cast<float>(eta)/850.0f,0.0f,1.0f))+
    .16f*std::clamp((carrierGap-minGap)/3.0f,0.0f,1.0f)+
    .10f*(1.0f-std::clamp(std::abs(lateralError)/2.0f,0.0f,1.0f));
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

CLOSE_TOUCH_RULES = r'''// Restrict excess planar launch speed, never change pass, shot, trap or knock-on.
inline float CloseTouchCap(float outgoing,float skill,float pressure,float alignment){
  const float allowance=1.6f+1.3f*std::clamp(skill,0.0f,1.0f)+
      .8f*std::clamp((pressure-1.0f)/3.0f,0.0f,1.0f)+.6f*std::clamp(alignment,0.0f,1.0f);
  return std::max(2.0f,outgoing+allowance);
}
inline float CloseTouchScale(float planar,float outgoing,float skill,float pressure,float alignment){
  if(!std::isfinite(planar)||!std::isfinite(outgoing)||!std::isfinite(skill)||
      !std::isfinite(pressure)||!std::isfinite(alignment)||planar<=.01f)return 1.0f;
  return std::clamp(CloseTouchCap(outgoing,skill,pressure,alignment)/planar,.72f,1.0f);
}
struct CloseTouchProbe{
  unsigned long contacts=0,adjusted=0; double before=0,after=0;
  void Record(float original,float applied){
    ++contacts;if(applied<original-.001f)++adjusted;before+=original;after+=applied;
  }
};
'''

MOTION_RULES = r'''// Per-step longitudinal and lateral budgets in m/s. Only locomotion plans use them.
struct MotionDelta {float x,y;};
inline MotionDelta LimitMotion(float vx,float vy,float dx,float dy,float agility,float acceleration,float balance,float dt){
  if(!std::isfinite(vx)||!std::isfinite(vy)||!std::isfinite(dx)||!std::isfinite(dy)||
     !std::isfinite(agility)||!std::isfinite(acceleration)||!std::isfinite(balance)||!std::isfinite(dt)||dt<=0||dt>.05f)return {dx,dy};
  agility=std::clamp(agility,0.0f,1.0f);
  acceleration=std::clamp(acceleration,0.0f,1.0f);
  balance=std::clamp(balance,0.0f,1.0f);
  const float speed=std::hypot(vx,vy);
  const float accel=6.5f+4.0f*acceleration,brake=9.0f+4.0f*balance;
  // At low speed, direction is poorly defined. Blend continuously from a
  // circular acceleration budget to the directional traction envelope.
  const float magnitude=std::hypot(dx,dy);
  const float scale=magnitude>accel*dt?accel*dt/magnitude:1.0f;
  const MotionDelta circular{dx*scale,dy*scale};
  if(speed<=.25f)return circular;
  const float ux=vx/speed,uy=vy/speed;
  const float requestedLong=dx*ux+dy*uy;
  const float requestedLat=-dx*uy+dy*ux;
  const float longLimit=(requestedLong<0.0f?brake:accel)*dt;
  const float lateralLimit=(6.0f+5.0f*agility+2.0f*balance)/(1.0f+.045f*speed)*dt;
  // Combined longitudinal/lateral traction: one shared budget, not two
  // independent maxima. Scale the requested vector without rotating it.
  const float utilization=std::hypot(requestedLong/longLimit,requestedLat/lateralLimit);
  const float tractionScale=utilization>1.0f?1.0f/utilization:1.0f;
  const float longitudinal=requestedLong*tractionScale,lateral=requestedLat*tractionScale;
  const MotionDelta directional{ux*longitudinal-uy*lateral,uy*longitudinal+ux*lateral};
  const float blend=std::clamp((speed-.25f)/.50f,0.0f,1.0f);
  const float weight=blend*blend*(3.0f-2.0f*blend);
  return {circular.x+(directional.x-circular.x)*weight,
          circular.y+(directional.y-circular.y)*weight};
}
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
inline bool Combination187Enabled(){
  static const bool enabled=[]{
    const char* flag=std::getenv("TRIBUN_AV_COMBINATION");
    const char* idle=std::getenv("TRIBUN_AV_IDLE_RECOVERY");
    const char* fixed=std::getenv("TRIBUN_NATIVE_FIXED_DURATION");
    return flag && std::strcmp(flag,"1")==0 && idle && std::strcmp(idle,"1")==0 &&
        fixed && std::strcmp(fixed,"1")==0 && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
inline bool CombinationLane187(float progress,float distance,float margin,float endpoint,float corridor){
  return std::isfinite(progress)&&std::isfinite(distance)&&std::isfinite(margin)&&
      std::isfinite(endpoint)&&std::isfinite(corridor)&&progress>=2.0f&&progress<=12.0f&&
      distance>=3.0f&&distance<=20.0f&&margin>=1.5f&&endpoint>=2.0f&&corridor>=1.3f;
}
inline bool CombinationReturn187(float odds,float nativeOdds,float margin,float corridor){
  return std::isfinite(odds)&&std::isfinite(nativeOdds)&&std::isfinite(margin)&&std::isfinite(corridor)&&
      odds>=.76f&&odds<=1.0f&&nativeOdds>=0.0f&&nativeOdds<=1.0f&&
      odds>=nativeOdds-.04f&&margin>=1.5f&&corridor>=1.3f;
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
inline bool RenderedBoxLaneEnabled() {
  static const bool enabled=[]{
    const char* v=std::getenv("TRIBUN_AV_BOX_LANE");
    return v && std::strcmp(v,"1")==0;
  }();
  return ShortMatchAttackEnabled() && enabled;
}
inline bool BoxLaneRunsEnabled() {
  static const bool enabled=[]{
    const char* v=std::getenv("TRIBUN_NATIVE_BOX_LANE_RUNS");
    return v && std::strcmp(v,"1")==0;
  }();
  return ShortMatchAttackEnabled() && (enabled || RenderedBoxLaneEnabled());
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
inline bool RenderedTimedAttackEnabled() {
  static const bool enabled=[]{
    const char* v=std::getenv("TRIBUN_AV_TIMED_ATTACK");
    return v && std::strcmp(v,"1")==0;
  }();
  return ShortMatchAttackEnabled() && enabled;
}
inline bool TimedAttackEnabled() {
  static const bool enabled=[]{
    const char* v=std::getenv("TRIBUN_NATIVE_TIMED_ATTACK");
    return v && std::strcmp(v,"1")==0;
  }();
  return ShortMatchAttackEnabled() && (enabled || RenderedTimedAttackEnabled());
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
      if(boxFinish207){
        commandQueue.insert(commandQueue.begin()+onBallStart,command);
        if(match->GetActualTime_ms()%250UL==0)
          std::fprintf(stderr,"[tribun-box-finish207] team=%d player=%d match_ms=%lu\n",
              team->GetID(),player->GetID(),static_cast<unsigned long>(match->GetMatchTime_ms()));
      }else if(AITactics::ShortMatchAttackEnabled() &&
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
  const bool progressive = (AITactics::ShortMatchAttackEnabled() || AITactics::Offball188Enabled()) &&
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
        ("    if (possPlayer) {\n      forwardSupportPlayer =\n          AI_GetClosestPlayer(team,", r'''    if ((AITactics::ShortMatchAttackEnabled() || (AITactics::Offball188Enabled() && match->IsInPlay() && !match->IsInSetPiece() && !match->GetBallRetainer())) && possPlayer && possPlayer->HasUniquePossession() &&
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
  const auto shotBall207=match->GetBall()->Predict(0);
  const bool boxProbe207=AITactics::Offball188Enabled() && match->IsInPlay() &&
      !match->IsInSetPiece() && !match->GetBallRetainer() && !team->GetHumanGamerCount() &&
      CastPlayer()->IsActive() && CastPlayer()->HasUniquePossession() &&
      match->GetDesignatedPossessionPlayer()==player && match->GetLastTouchPlayer()==player &&
      CastPlayer()->GetFormationEntry().role!=e_PlayerRole_GK &&
      AITactics::BoxFinish207Geometry(shotVector.coords[0]*-team->GetSide(),
          std::abs(player->GetPosition().coords[1]),shotDistance,shotAngle,
          player->GetStat("technical_shot"),(shotBall207.Get2D()-player->GetPosition().Get2D()).GetLength(),
          shotBall207.coords[2]);
  if (idealShotPosFactor > 0.1f || distanceProbe || boxProbe207) {'''),
        ("    if (odds + random(0.0f, 0.28f) > AITactics::ShotOddsThreshold()) {", r'''    const bool distanceShot=distanceProbe &&
        AITactics::EligibleDistanceShot(shotDistance,shotAngle,player->GetStat("technical_shot"),odds);
    if ((idealShotPosFactor > 0.1f || distanceShot || boxFinish207) &&
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
    const int oldStage=tribunCombination.stage,oldA=tribunCombination.passer,oldB=tribunCombination.receiver;
    const auto oldCompleted=tribunCombination.completed;
    tribunCombination.Observe(owner,confirmed,interrupted,now);
    if(AITactics::Combination187Enabled() && oldStage!=tribunCombination.stage)
      printf("[tribun-combination187] team=%d kind=wall event=%s a=%d b=%d c=%d\n",
          team->GetID(),tribunCombination.stage==2?"receipt":tribunCombination.completed>oldCompleted?"complete":"cancel",
          oldA,oldB,oldA);
  }
  if (!teamHasPossession)'''),
        ("      prevTeamHasPossession && !teamHasPossession){", "      prevTeamHasPossession && !teamHasPossession && !tribunCombination.stage){"),
        ("void TeamAIController::ApplyAttackingRun(Player* manualPlayer) {", r'''void TeamAIController::TribunPassContact(Player* passer,Player* receiver,bool shortPass) {
  if(tribunRebound.stage>=2){tribunRebound.Clear();tribunReboundSupportID=-1;}
  if((!AITactics::ShortMatchAttackEnabled() && !AITactics::Combination187Enabled()) || team->GetHumanGamerCount())return;
  const auto now=match->GetActualTime_ms();
  if(!shortPass || !receiver || !passer || receiver==passer ||
      receiver->GetTeam()!=team || !receiver->IsActive() || !passer->IsActive() ||
      !match->IsInPlay() || match->IsInSetPiece() || match->GetBallRetainer()){
    tribunCombination.Clear(now);return;
  }
  if(tribunCombination.stage){
    const int oldA=tribunCombination.passer,oldB=tribunCombination.receiver;
    const bool returned=tribunCombination.ReturnPass(passer->GetID(),receiver->GetID(),now);
    if(!returned)tribunCombination.Clear(now);
    if(AITactics::Combination187Enabled())
      printf("[tribun-combination187] team=%d kind=wall event=%s a=%d b=%d c=%d\n",
          team->GetID(),returned?"second":"cancel",oldA,oldB,oldA);
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
  if(AITactics::Combination187Enabled()){
    const auto target=pos+Vector3(4.0f*forward,0,0);
    const auto path=target-receiver->GetPosition();
    float clearance=100.0f,corridor=100.0f;
    std::vector<PlayerImage> rivals;
    match->GetMentalImage(0)->GetTeamPlayerImages(abs(team->GetID()-1),-1,rivals);
    for(const auto& opp:rivals){
      clearance=std::min(clearance,(target-opp.position-opp.movement*.6f).Get2D().GetLength());
      for(float f:{.25f,.5f,.75f})
        corridor=std::min(corridor,(receiver->GetPosition()+path*f-opp.position-opp.movement*(.6f*f)).Get2D().GetLength());
    }
    if(!AITactics::CombinationLane187(4.0f,path.Get2D().GetLength(),
        line-target.coords[0]*forward,clearance,corridor) ||
        std::abs(target.coords[0])>=pitchHalfW-2.0f || std::abs(target.coords[1])>=pitchHalfH-1.5f)return;
  }
  if(tribunCombination.Begin(passer->GetID(),receiver->GetID(),now)){
    if(AITactics::Combination187Enabled())
      printf("[tribun-combination187] team=%d kind=wall event=start a=%d b=%d c=%d\n",
          team->GetID(),passer->GetID(),receiver->GetID(),passer->GetID());
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
      if((runningPassEnabled || (AITactics::Combination187Enabled() && CastPlayer()->HasUniquePossession() &&
          !team->GetHumanGamerCount() && match->IsInPlay() && !match->IsInSetPiece() && !match->GetBallRetainer())) &&
          team->GetController()->TribunReturnTarget(CastPlayer())==mates.at(i)){
        const auto delta=mates.at(i)->GetPosition()-player->GetPosition();
        const float line=runningPassEnabled?passOffside:
            AI_GetOffsideLine(match,_mentalImage,abs(team->GetID()-1))*attackForward;
        const float margin=line-mates.at(i)->GetPosition().coords[0]*attackForward;
        if(AITactics::SafeReturnPass(delta.coords[0]*attackForward,delta.GetLength(),margin,1.0f)){
          returnOdds=_GetPassingOdds(mates.at(i),e_FunctionType_ShortPass,opponentPlayerImages);
          returnCandidate=AITactics::SafeReturnPass(delta.coords[0]*attackForward,delta.GetLength(),margin,returnOdds);
          if(AITactics::Combination187Enabled()){
            float corridor=100.0f;
            for(const auto& opp:opponentPlayerImages)for(float f:{.25f,.5f,.75f})
              corridor=std::min(corridor,(player->GetPosition()+delta*f-opp.position-opp.movement*(.6f*f)).Get2D().GetLength());
            returnCandidate=returnCandidate && AITactics::CombinationReturn187(returnOdds,0.0f,margin,corridor);
          }
        }
      }
      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate) {'''),
        ("        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +", r'''        if(returnCandidate && returnOdds>=mateRating.passRating-(AITactics::Combination187Enabled()?.04f:.08f)){
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

    # A single existing secondary outlet chooses a passable box channel.
    # Keep explicit combinations and the final native offside clamp.
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ('#include "elizacontroller.hpp"', '#include "elizacontroller.hpp"\n#include <cstdio>'),
        ("  // stay away from opponents\n  std::vector<Player*> opponents;", r'''  if(AITactics::BoxLaneRunsEnabled() && match->IsInPlay() && !match->IsInSetPiece() &&
      !team->GetHumanGamerCount() && designatedPlayer!=CastPlayer() &&
      designatedPlayer->HasUniquePossession() && dynamicMindSet>=.45f &&
      player==team->GetController()->GetForwardSupportPlayer() &&
      !adaptedMakeRun && !combinationRun &&
      std::abs(mainManPos.coords[1])<(AITactics::RenderedBoxLaneEnabled()?23.0f:13.0f)){
    const float forward=-team->GetSide();
    const float depth=pitchHalfW-mainManPos.coords[0]*forward;
    if(depth>=17.0f && depth<=34.0f){
      std::vector<PlayerImage> rivals;
      mentalImage->GetTeamPlayerImages(abs(team->GetID()-1),-1,rivals);
      const float line=AI_GetOffsideLine(match,mentalImage,abs(team->GetID()-1))*forward;
      const float limit=std::min(line,offsideX*forward);
      const float x=std::min(pitchHalfW-9.0f,limit-1.25f);
      const bool rendered=AITactics::RenderedBoxLaneEnabled();
      float best=-10000.0f;
      Vector3 target;
      for(float y:{-16.0f,-8.0f,0.0f,8.0f,16.0f}){
        if(!rendered && std::abs(y)>8.0f)continue;
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
        if(rendered){
          static const bool observed=[]{
            std::fprintf(stderr,"[tribun-box-entry] lane-selected=1\n");
            return true;
          }();
          (void)observed;
        }
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
          float clearance=100.0f,corridor=100.0f;
          const auto start=player->GetPosition();
          const auto path=predicted-start;
          const float length2=path.GetSquaredLength();
          for(const auto& rival:opponentPlayerImages){
            const auto future=rival.position+rival.movement*.5f;
            clearance=std::min(clearance,(predicted-future).GetLength());
            if(AITactics::RenderedTimedAttackEnabled() && length2>.01f){
              const auto offset=future-start;
              const float u=(offset.coords[0]*path.coords[0]+offset.coords[1]*path.coords[1])/length2;
              if(u>.05f && u<.95f)
                corridor=std::min(corridor,(future-(start+path*u)).GetLength());
            }
          }
          if((!AITactics::RenderedTimedAttackEnabled() || corridor>=1.4f) &&
              AITactics::LeadRunGeometry(depth,delta.coords[0]*attackForward,distance,
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
        ("struct FixedDurationClock {", r'''inline bool CombinedAIEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_COMBINED_AI");
    const char* nullMode=std::getenv("TRIBUN_NATIVE_NULL_RENDERER");
    return value && std::strcmp(value,"1")==0 && nullMode && std::strcmp(nullMode,"1")==0 &&
      ShortMatchAttackEnabled() && FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE") &&
      !std::getenv("TRIBUN_LEAGUE_SOCCER_COMMAND_DIR");
  }();
  return enabled;
}
inline bool CollectiveEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_COLLECTIVE_AI");
    return (CombinedAIEnabled() || (value && std::strcmp(value,"1")==0)) && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
inline bool Offball188Enabled(){
  static const bool enabled=[]{
    const char* flag=std::getenv("TRIBUN_AV_OFFBALL_LANES");
    const char* idle=std::getenv("TRIBUN_AV_IDLE_RECOVERY");
    return flag && std::strcmp(flag,"1")==0 && idle && std::strcmp(idle,"1")==0 &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
inline bool CoordinatedRuns189Enabled(){
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_AV_COORDINATED_RUNS");
    return value && std::strcmp(value,"1")==0 && Offball188Enabled();
  }();
  return enabled;
}
struct RunReservation189 {
  int player=-1,carrier=-1,phase=-1;
  unsigned long at=0;
  float sx=0,sy=0,tx=0,ty=0;
  void Clear(){player=carrier=phase=-1;at=0;}
  void Save(int p,int c,int period,unsigned long now,float x,float y,float endX,float endY){
    player=p;carrier=c;phase=period;at=now;sx=x;sy=y;tx=endX;ty=endY;
  }
  bool Valid(int p,int c,int period,unsigned long now)const{
    return player>=0 && player!=p && carrier==c && phase==period &&
        now>=at && now-at<=250UL;
  }
};
inline bool BoxFinish207Geometry(float depth,float lateral,float distance,float angle,float skill,float ballGap,float ballHeight){
  return std::isfinite(depth)&&std::isfinite(lateral)&&std::isfinite(distance)&&
      std::isfinite(angle)&&std::isfinite(skill)&&std::isfinite(ballGap)&&std::isfinite(ballHeight)&&
      depth>=3.0f&&depth<=16.5f&&lateral>=0.0f&&lateral<=10.0f&&
      distance>=3.0f&&distance<=19.0f&&angle>=.70f&&angle<=1.001f&&
      skill>=.45f&&skill<=1.0f&&ballGap>=0.0f&&ballGap<=1.0f&&ballHeight>=-.05f&&ballHeight<=.45f;
}
inline bool BoxFinish207Prefer(float shotOdds,float passOdds){
  return std::isfinite(shotOdds)&&std::isfinite(passOdds)&&
      shotOdds>=.62f&&shotOdds<=1.0f&&passOdds>=0.0f&&passOdds<=1.0f&&
      shotOdds+.10f>=passOdds;
}
inline bool RunPass206Eligible(const RunReservation189& reservation,int receiver,int carrier,int phase,
    unsigned long now,float x,float y,float vx,float vy){
  if(receiver<0||carrier<0||receiver==carrier||reservation.player!=receiver||
      reservation.carrier!=carrier||reservation.phase!=phase||
      now<reservation.at||now-reservation.at>250UL||
      !std::isfinite(x)||!std::isfinite(y)||!std::isfinite(vx)||!std::isfinite(vy)||
      !std::isfinite(reservation.tx)||!std::isfinite(reservation.ty))return false;
  const float dx=reservation.tx-x,dy=reservation.ty-y;
  const float gap=std::hypot(dx,dy);
  return gap>=1.0f&&gap<=9.0f&&(dx*vx+dy*vy)/gap>=.75f;
}
inline bool RunPass206Target(const RunReservation189& reservation,float x,float y){
  return std::isfinite(x)&&std::isfinite(y)&&
      std::hypot(reservation.tx-x,reservation.ty-y)<=3.5f;
}
inline float CoordinatedRunScore189(float sx,float sy,float tx,float ty,const RunReservation189& other){
  const float endGap=std::hypot(tx-other.tx,ty-other.ty);
  if(!std::isfinite(endGap)||endGap<4.0f)return -1000.0f;
  float pathGap=endGap;
  for(float f:{.5f,.75f}){
    const float dx=sx+(tx-sx)*f-other.sx-(other.tx-other.sx)*f;
    const float dy=sy+(ty-sy)*f-other.sy-(other.ty-other.sy)*f;
    const float gap=std::hypot(dx,dy);
    if(!std::isfinite(gap))return -1000.0f;
    pathGap=std::min(pathGap,gap);
  }
  if(pathGap<2.5f)return -1000.0f;
  return .18f*std::min(endGap,10.0f)+.20f*std::min(pathGap,6.0f)+
      .12f*std::min(std::abs(ty-other.ty),8.0f);
}
inline float OffballArrival188(float distance,float speed){
  return std::clamp(distance/std::clamp(speed+1.5f,3.0f,6.5f),.35f,1.5f);
}
inline bool OffballLane188(float progress,float distance,float margin,float endpoint,float corridor,float teammateGap,float runClearance){
  return std::isfinite(progress)&&std::isfinite(distance)&&std::isfinite(margin)&&
      std::isfinite(endpoint)&&std::isfinite(corridor)&&std::isfinite(teammateGap)&&
      std::isfinite(runClearance)&&progress>=2.0f&&distance>=3.0f&&distance<=9.0f&&
      margin>=1.5f&&endpoint>=2.2f&&corridor>=1.5f&&teammateGap>=3.5f&&runClearance>=1.0f;
}
inline float OffballScore188(float endpoint,float corridor,float teammateGap,float progress,float distance,float lateral,float runClearance){
  return .75f*std::min(endpoint,6.0f)+.9f*std::min(corridor,5.0f)+
      .40f*std::min(teammateGap,8.0f)+.2f*progress-.18f*distance+
      .12f*std::min(lateral,5.0f)+.25f*std::min(runClearance,4.0f);
}
inline bool RunLanesEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_RUN_LANES");
    return Offball188Enabled() || ((CollectiveEnabled() || (value && std::strcmp(value,"1")==0)) && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE"));
  }();
  return enabled;
}
''' + RUN_LANE_RULES + "struct FixedDurationClock {"),
    ])
    edit(root, "src/onthepitch/match.hpp", [
        ("  unsigned long tribunLineBreakSelections[2]={0,0};", """  unsigned long tribunLineBreakSelections[2]={0,0};
  unsigned long tribunRunLanePrimary[2]={0,0},tribunRunLaneSecondary[2]={0,0};
  unsigned long tribunRunLaneAttempts[2]={0,0};
  AITactics::RunReservation189 tribunRunReservations[2][2];"""),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("  if (adaptedMakeRun) {\n    ForceSpot spot;\n    spot.origin =\n        Vector3(-team->GetSide() * pitchHalfW,", r'''  bool chosenLane=false;
  const bool primaryLane=makeRun && !combinationRun;
  const bool secondaryLane=!adaptedMakeRun &&
      player==team->GetController()->GetForwardSupportPlayer();
  if(AITactics::RunLanesEnabled() && match->IsInPlay() && !match->IsInSetPiece() &&
      !team->GetHumanGamerCount() && designatedPlayer!=CastPlayer() &&
      designatedPlayer->HasUniquePossession() && !combinationRun && dynamicMindSet>=.45f &&
      (!(AITactics::CollectiveEnabled() || AITactics::Offball188Enabled()) || team->GetController()->GetTribunTriangle().stage==0) &&
      (primaryLane || secondaryLane) && (!AITactics::Offball188Enabled() || (!match->GetBallRetainer() && CastPlayer()->GetFormationEntry().role!=e_PlayerRole_GK)) && std::abs(mainManPos.coords[1])<(AITactics::Offball188Enabled()?22.0f:13.0f)){
    const float forward=-team->GetSide();
    const float carrierDepth=pitchHalfW-mainManPos.coords[0]*forward;
    if(carrierDepth>=17.0f && carrierDepth<=(AITactics::Offball188Enabled()?46.0f:40.0f)){
      ++match->tribunRunLaneAttempts[team->GetID()];
      std::vector<PlayerImage> rivals,mates;
      mentalImage->GetTeamPlayerImages(abs(team->GetID()-1),-1,rivals);
      mentalImage->GetTeamPlayerImages(team->GetID(),CastPlayer()->GetID(),mates);
      const float limit=std::min(offsideX*forward,
          AI_GetOffsideLine(match,mentalImage,abs(team->GetID()-1))*forward);
      const float leadX=std::min(pitchHalfW-6.0f,limit-1.5f);
      float best=-10000.0f;
      Vector3 target(0);
      const bool coordinated=AITactics::CoordinatedRuns189Enabled();
      const int laneIndex=primaryLane?0:1;
      const int carrierId=designatedPlayer->GetID();
      const int period=static_cast<int>(match->GetMatchPhase());
      const auto now=match->GetActualTime_ms();
      auto& reservation=match->tribunRunReservations[team->GetID()][laneIndex];
      auto& other=match->tribunRunReservations[team->GetID()][1-laneIndex];
      const bool pair=coordinated && other.Valid(CastPlayer()->GetID(),carrierId,period,now);
      if(AITactics::Offball188Enabled())reservation.Clear();
      for(float setback:{0.0f,3.0f,6.0f}){
        for(float width:{4.5f,10.0f,15.5f}){
          const float x=AITactics::Offball188Enabled()?std::min(leadX-setback,currentPos.coords[0]*forward+6.0f):leadX-setback;
          const float y=AITactics::Offball188Enabled()?clamp(currentPos.coords[1]+clamp(AITactics::RunLaneY(mainManPos.coords[1],primaryLane,width)-currentPos.coords[1],-5.0f,5.0f),-24.0f,24.0f):AITactics::RunLaneY(mainManPos.coords[1],primaryLane,width);
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
          float score=AITactics::RunLaneScore(endpoint,corridor,mateGap,progress,
                run.GetLength(),std::abs(run.coords[1]));
          if(AITactics::Offball188Enabled()){
            const float arrival=AITactics::OffballArrival188(run.GetLength(),player->GetMovement().Get2D().GetLength());
            float endGap=100.0f,passGap=100.0f,teamGap=100.0f,runGap=100.0f;
            for(const auto& rival:rivals){
              endGap=std::min(endGap,(rival.position+rival.movement*arrival-candidate).Get2D().GetLength());
              for(float f:{.25f,.5f,.75f}){
                const auto future=rival.position+rival.movement*(arrival*f);
                passGap=std::min(passGap,(future-(mainManPos+delta*f)).Get2D().GetLength());
                runGap=std::min(runGap,(future-(currentPos+run*f)).Get2D().GetLength());
              }
            }
            for(const auto& mate:mates)teamGap=std::min(teamGap,(mate.position+mate.movement*arrival-candidate).Get2D().GetLength());
            if(!AITactics::OffballLane188(progress,run.GetLength(),limit-x,endGap,passGap,teamGap,runGap))continue;
            score=AITactics::OffballScore188(endGap,passGap,teamGap,progress,run.GetLength(),std::abs(run.coords[1]),runGap);
          }
          if(pair){
            const float coordination=AITactics::CoordinatedRunScore189(currentPos.coords[0],currentPos.coords[1],
                candidate.coords[0],candidate.coords[1],other);
            if(coordination<-999.0f)continue;
            score+=coordination;
          }
          if(score>best){best=score;target=candidate;}
        }
      }
      if(best>-9999.0f){
        if(AITactics::Offball188Enabled())
          reservation.Save(CastPlayer()->GetID(),carrierId,period,now,
              currentPos.coords[0],currentPos.coords[1],target.coords[0],target.coords[1]);
        if(coordinated){
          if(now%250UL==0)
            printf("[tribun-coordinated189] team=%d player=%d paired=%d match_ms=%lu\n",
                team->GetID(),CastPlayer()->GetID(),pair?1:0,static_cast<unsigned long>(match->GetMatchTime_ms()));
        }
        ForceSpot spot;
        spot.origin=target;
        spot.magnetType=e_MagnetType_Attract;
        spot.decayType=e_DecayType_Constant;
        spot.power=primaryLane?2.0f*runWeight:1.65f;
        forceField.push_back(spot);
        chosenLane=true;
        if(AITactics::Offball188Enabled() && match->GetActualTime_ms()%250UL==0)
          printf("[tribun-offball188] team=%d player=%d role=%s match_ms=%lu x=%.4f y=%.4f score=%.4f\n",
              team->GetID(),CastPlayer()->GetID(),primaryLane?"primary":"secondary",
              static_cast<unsigned long>(match->GetMatchTime_ms()),target.coords[0],target.coords[1],best);
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
    return Combination187Enabled() || ((CollectiveEnabled() || (value && std::strcmp(value,"1")==0)) && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE"));
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
    const int oldStage=tribunTriangle.stage,oldA=tribunTriangle.a,oldB=tribunTriangle.b,oldC=tribunTriangle.c;
    const auto oldCompleted=tribunTriangle.completed;
    tribunTriangle.Observe(confirmed?own->GetID():-1,confirmed?own->GetLastTouchTime_ms():0,invalid,now);
    if(AITactics::Combination187Enabled() && oldStage!=tribunTriangle.stage)
      printf("[tribun-combination187] team=%d kind=triangle event=%s a=%d b=%d c=%d\n",
          team->GetID(),tribunTriangle.stage==2?"receipt":tribunTriangle.completed>oldCompleted?"complete":"cancel",oldA,oldB,oldC);
  }
  if(tribunTimedAttack.stage){'''),
        ("void TeamAIController::TribunPassContact(Player* passer,Player* receiver,bool shortPass) {", r'''bool TeamAIController::TribunTriangleContact(Player* passer,Player* receiver,bool shortPass){
  if(!AITactics::TriangleEnabled()||team->GetHumanGamerCount())return false;
  const auto now=match->GetActualTime_ms();
  // A confirmed counter owns the attacking plan until its short window ends.
  if(AITactics::CollectiveEnabled()&&tribunTransition.Winning(now)){
    tribunTriangle.Clear(now);return false;
  }
  ++tribunTriangle.inspected;
  const bool valid=shortPass&&passer&&receiver&&passer!=receiver&&receiver->GetTeam()==team&&
    passer->IsActive()&&receiver->IsActive()&&match->IsInPlay()&&!match->IsInSetPiece()&&!match->GetBallRetainer();
  if(tribunTriangle.stage){
    const int oldA=tribunTriangle.a,oldB=tribunTriangle.b,oldC=tribunTriangle.c;
    const bool second=valid&&tribunTriangle.Pass(passer->GetID(),receiver->GetID(),now);
    if(!second)tribunTriangle.Clear(now);
    if(AITactics::Combination187Enabled())
      printf("[tribun-combination187] team=%d kind=triangle event=%s a=%d b=%d c=%d\n",
          team->GetID(),second?"second":"cancel",oldA,oldB,oldC);
    return true;
  }
  if(!valid||tribunCombination.stage||passer->GetFormationEntry().role==e_PlayerRole_GK||
    receiver->GetFormationEntry().role==e_PlayerRole_GK||now<tribunTriangle.cooldown)return false;
  ++tribunTriangle.context;
  const float forward=-team->GetSide();
  const auto from=passer->GetPosition(),middle=receiver->GetPosition();
  const auto first=middle-from;
  const float depth=pitchHalfW-from.coords[0]*forward;
  if(depth<12.0f||depth>58.0f||first.GetLength()<3.0f||first.GetLength()>23.0f||
      std::abs(first.coords[1])<1.0f||receiver->GetStat("technical_shortpass")<.45f)return false;
  const float line=AI_GetOffsideLine(match,match->GetMentalImage(0),abs(team->GetID()-1))*forward;
  if(line-middle.coords[0]*forward<1.0f)return false;
  ++tribunTriangle.geometry;
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
    if(AITactics::Combination187Enabled()){
      float corridor=100.0f;
      for(const auto& rival:rivals)for(float f:{.25f,.5f,.75f})
        corridor=std::min(corridor,(middle+delta*f-rival.position-rival.movement*(.6f*f)).Get2D().GetLength());
      if(!AITactics::CombinationLane187(delta.coords[0]*forward,delta.Get2D().GetLength(),
          line-pos.coords[0]*forward,clearance,corridor))continue;
    }
    const float score=std::min(clearance,8.0f)+delta.coords[0]*forward*.15f-delta.GetLength()*.08f;
    if(score>best){best=score;third=mate.get();}
  }
  if(third)++tribunTriangle.available;
  const bool began=third&&tribunTriangle.Begin(passer->GetID(),receiver->GetID(),third->GetID(),now);
  if(began && AITactics::Combination187Enabled())
    printf("[tribun-combination187] team=%d kind=triangle event=start a=%d b=%d c=%d\n",
        team->GetID(),passer->GetID(),receiver->GetID(),third->GetID());
  return began;
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
      if((runningPassEnabled || (AITactics::Combination187Enabled() && CastPlayer()->HasUniquePossession() &&
          !team->GetHumanGamerCount() && match->IsInPlay() && !match->IsInSetPiece() && !match->GetBallRetainer())) &&
          team->GetController()->TribunTriangleTarget(CastPlayer())==mates.at(i)){
        const auto pos=mates.at(i)->GetPosition(),delta=pos-player->GetPosition();
        const float line=runningPassEnabled?passOffside:
            AI_GetOffsideLine(match,_mentalImage,abs(team->GetID()-1))*attackForward;
        const float margin=line-pos.coords[0]*attackForward;
        if(AITactics::TriangleGeometry(delta.coords[0]*attackForward,delta.GetLength(),std::abs(delta.coords[1]),
              margin,pitchHalfW-pos.coords[0]*attackForward)){
          triangleOdds=_GetPassingOdds(mates.at(i),e_FunctionType_ShortPass,opponentPlayerImages);
          triangleCandidate=AITactics::TrianglePassSafe(triangleOdds,0.0f);
          if(AITactics::Combination187Enabled()){
            float corridor=100.0f;
            for(const auto& opp:opponentPlayerImages)for(float f:{.25f,.5f,.75f})
              corridor=std::min(corridor,(player->GetPosition()+delta*f-opp.position-opp.movement*(.6f*f)).Get2D().GetLength());
            triangleCandidate=triangleCandidate && AITactics::CombinationReturn187(triangleOdds,0.0f,margin,corridor);
          }
        }
      }
      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet || timedCandidate || lineBreak || triangleCandidate) {'''),
        ("        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +", r'''        if(triangleCandidate && AITactics::TrianglePassSafe(triangleOdds,mateRating.passRating) && (!AITactics::Combination187Enabled() || triangleOdds>=mateRating.passRating-.04f)){
          mateRating.passType=e_FunctionType_ShortPass;
          mateRating.passRating=triangleOdds;
          mateRating.supportRating+=.48f;
        }else if(triangleCandidate && !(progressiveCandidate||supportCandidate||runningCandidate||
            deliveryCandidate||pressureOutlet||returnCandidate||retentionOutlet||timedCandidate||lineBreak))continue;
        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +'''),
    ])

    # Stage 66: multi-speed dribbling search using native movement limits and actual control outcomes.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool RenderedCarryEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_AV_CONTROLLED_CARRY");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
inline bool CreativeCarryEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_CREATIVE_CARRY");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled || RenderedCarryEnabled();
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
    const bool renderedCarry=AITactics::RenderedCarryEnabled();
    if(depth>=(renderedCarry?4.0f:8.0f) && depth<=(renderedCarry?38.0f:65.0f) &&
       nearest>=1.0f && nearest<=(renderedCarry?8.0f:6.0f) && gap<=1.35f){
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
        const float base=AITactics::CarryOption(dir.coords[0]*-side*distance,clearance,alignment,fraction,skill,attack);
        // Reward a safe predicted entry into the actual penalty area.
        // Never rescue a rejected direction or change native touch physics.
        if(renderedCarry && base>-999.0f && depth>16.5f &&
           pitchHalfW+side*endpoint.coords[0]<=16.5f && std::abs(endpoint.coords[1])<=20.16f &&
           clearance>=1.8f && dir.coords[0]*-side>0.0f)
          return base+.35f;
        return base;
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
        ("struct FixedDurationClock {", r'''inline bool RenderedDuelEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_AV_DUEL");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
inline bool DuelEscape184Enabled(){
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_AV_DUEL_ESCAPE");
    const char* idle=std::getenv("TRIBUN_AV_IDLE_RECOVERY");
    return value && std::strcmp(value,"1")==0 && idle && std::strcmp(idle,"1")==0 &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
inline float DuelReachTime(float time,float agility){
  // Integrate an exponential transition from incoming to desired velocity.
  const float tau=.30f-.16f*std::clamp(agility,0.0f,1.0f);
  return time-tau*(1.0f-std::exp(-time/tau));
}
inline float DuelReachScore(float progress,float clearance,float endGap,float baselineGap,float turn,float skill){
  if(!std::isfinite(progress)||!std::isfinite(clearance)||!std::isfinite(endGap)||
      !std::isfinite(baselineGap)||!std::isfinite(turn)||!std::isfinite(skill)||
      progress<.25f||clearance<1.3f||turn<-.10f)return -1000.0f;
  return .75f*progress+1.15f*std::min(clearance,4.0f)+
      .5f*std::clamp(endGap-baselineGap,-2.0f,2.0f)+
      (.55f-.2f*std::clamp(skill,0.0f,1.0f))*turn;
}
inline bool DuelEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_DUEL");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled || RenderedDuelEnabled() || DuelEscape184Enabled();
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
        const auto oldBeaten=trial.beaten,oldLost=trial.lost;
        const int oldCarrier=trial.carrier,oldDefender=trial.defender;
        trial.Observe(confirmed?own->GetID():-1,teams[1-t]->HasUniquePossession(),invalid,
            carrier?carrier->GetPosition().coords[0]:0.0f,defender?defender->GetPosition().coords[0]:0.0f,
            carrier&&defender?(carrier->GetPosition()-defender->GetPosition()).Get2D().GetLength():0.0f,actualTime_ms);
        if(AITactics::DuelEscape184Enabled() && trial.carrier<0){
          printf("[tribun-duel-escape] team=%d carrier=%d defender=%d event=%s\n",
              t,oldCarrier,oldDefender,trial.beaten>oldBeaten?"progressed":trial.lost>oldLost?"lost":"cancelled");
        }
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
    ++trial.inspected;
    if(depth>=8.0f&&depth<=65.0f&&(trial.carrier<0||trial.carrier==player->GetID())){
      ++trial.context;
      bool geometry=false;
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
        if(AITactics::DuelEligible(delta.coords[0]*-side,distance,closing,gap,1.0f))geometry=true;
        if(AITactics::DuelEligible(delta.coords[0]*-side,distance,closing,gap,skill)&&distance<closest){
          closest=distance;defender=rival;
        }
      }
      if(geometry)++trial.geometry;
      if(defender){
        ++trial.available;
        const Vector3 forward(-side,0,0);
        const auto facing=player->GetDirectionVec().Get2D().GetNormalized(forward);
        const auto current=desiredDirection.Get2D().GetNormalized(facing);
        const auto rivalMotion=defender->GetMovement().Get2D();
        auto rate=[&](const Vector3& dir,float speed){
          const float turn=dir.coords[0]*facing.coords[0]+dir.coords[1]*facing.coords[1];
          if(AITactics::DuelEscape184Enabled()){
            const auto desired=dir*(sprintVelocity*speed);
            const auto incoming=myMov.Get2D();
            const float agility=player->GetStat("physical_agility");
            float clearance=100.0f;
            Vector3 endpoint=myPos;
            for(float time:{.15f,.30f,.45f,.60f}){
              const float reach=AITactics::DuelReachTime(time,agility);
              endpoint=myPos+incoming*time+(desired-incoming)*reach;
              if(std::abs(endpoint.coords[0])>pitchHalfW-1.5f ||
                  std::abs(endpoint.coords[1])>pitchHalfH-1.5f)return -1000.0f;
              for(const auto& opp:opponentPlayerImages)
                clearance=std::min(clearance,(endpoint-opp.position-opp.movement*time).Get2D().GetLength());
            }
            const float futureGap=(endpoint-defender->GetPosition()-rivalMotion*.60f).Get2D().GetLength();
            return AITactics::DuelReachScore((endpoint-myPos).coords[0]*-side,clearance,
                futureGap,closest,turn,skill);
          }
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
          const float base=AITactics::DuelEscapeScore(dir.coords[0]*-side*advance,clearance,turn,speed,skill,wrongFoot);
          // Favor a lateral escape that opens a real gap from the same
          // defender; never override rejected geometry or speed caps.
          if(AITactics::RenderedDuelEnabled() && base>-999.0f){
            const auto futureDefender=defender->GetPosition()+rivalMotion*.55f;
            const auto gapVector=(end-futureDefender).Get2D();
            const float ahead=gapVector.coords[0]*-side;
            const float gapGain=gapVector.GetLength()-closest;
            return base+.35f*std::clamp(gapGain,0.0f,2.0f)+.20f*std::clamp(ahead,0.0f,2.0f);
          }
          return base;
        };
        const float baseline=rate(current,clamp(desiredVelocity/sprintVelocity,0.0f,1.0f));
        float best=baseline,chosenSpeed=0.0f;Vector3 chosen=current;
        for(float angle:{-1.20f,-.95f,-.60f,-.30f,.30f,.60f,.95f,1.20f}){
          if(!AITactics::RenderedDuelEnabled() && !AITactics::DuelEscape184Enabled() && std::abs(angle)>1.0f)continue;
          const auto dir=forward.GetRotated2D(angle);
          const float turn=dir.coords[0]*facing.coords[0]+dir.coords[1]*facing.coords[1];
          const float cap=AITactics::CarrySpeedLimit(skill,closest,gap,turn);
          for(float fraction:{.45f,.62f,.78f,.90f}){
            if(fraction>cap+.0001f)continue;
            const float actualFraction=AITactics::DuelEscape184Enabled()?clamp(RangeVelocity(sprintVelocity*fraction)/sprintVelocity,0.0f,1.0f):fraction;
            if(actualFraction>cap+.0001f)continue;
            const float score=rate(dir,actualFraction);
            if(score>best){best=score;chosen=dir;chosenSpeed=actualFraction;}
          }
        }
        const bool newDuel=trial.carrier<0;
        if(best>baseline+(AITactics::DuelEscape184Enabled()?.45f:.25f)&&best>-999.0f&&
            (trial.carrier==player->GetID()||trial.Begin(player->GetID(),defender->GetID(),myPos.coords[0],-side,match->GetActualTime_ms()))){
          desiredDirection=chosen;desiredVelocity=sprintVelocity*chosenSpeed;
          if(AITactics::DuelEscape184Enabled() && newDuel)
            printf("[tribun-duel-escape] team=%d carrier=%d defender=%d event=started\n",
                team->GetID(),player->GetID(),defender->GetID());
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
        ("struct FixedDurationClock {", r'''inline bool PressureHold185Enabled(){
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_AV_PRESSURE_HOLD");
    const char* idle=std::getenv("TRIBUN_AV_IDLE_RECOVERY");
    return value && std::strcmp(value,"1")==0 && idle && std::strcmp(idle,"1")==0 &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
inline float PressureShieldScore(float clearance,float alignment,float away,float progress,float gain){
  if(!std::isfinite(clearance)||!std::isfinite(alignment)||!std::isfinite(away)||
      !std::isfinite(progress)||!std::isfinite(gain)||clearance<.95f||
      alignment<.05f||progress<-.65f)return -1000.0f;
  return 1.2f*std::min(clearance,4.0f)+.65f*alignment+
      .7f*std::clamp(away,-1.0f,1.0f)+.35f*progress+
      .55f*std::clamp(gain,-1.0f,1.5f);
}
inline bool HoldUpEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_HOLD_UP");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled || PressureHold185Enabled();
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
        const int oldCarrier=trial.carrier;
        const auto oldHeld=trial.held,oldReceived=trial.received,oldLost=trial.lost;
        trial.Observe(confirmed?own->GetID():-1,confirmed?own->GetLastTouchTime_ms():0,
          teams[1-t]->HasUniquePossession(),invalid,actualTime_ms);
        if(AITactics::PressureHold185Enabled()){
          if(trial.held>oldHeld)printf("[tribun-pressure-hold] team=%d carrier=%d event=held\n",t,oldCarrier);
          if(!trial.stage)printf("[tribun-pressure-hold] team=%d carrier=%d event=%s\n",
              t,oldCarrier,trial.received>oldReceived?"received":trial.lost>oldLost?"lost":"cancelled");
        }
      }
    }
    if(AITactics::DuelEnabled()){'''),
        ("  for(auto& trial:tribunDuelTrials)trial.Cancel(GetActualTime_ms());",
         "  for(auto& trial:tribunDuelTrials)trial.Cancel(GetActualTime_ms());\n  for(auto& trial:tribunHoldTrials)trial.Cancel(GetActualTime_ms());"),
    ])
    edit(root, "src/onthepitch/teamAIcontroller.cpp", [
        ("  if(TribunTriangleContact(passer,receiver,shortPass))return;", r'''  if(AITactics::HoldUpEnabled()){
    auto& trial=match->tribunHoldTrials[team->GetID()];
    if(trial.stage){
      const int oldCarrier=trial.carrier;
      const bool released=trial.Pass(passer?passer->GetID():-1,receiver?receiver->GetID():-1,shortPass,match->GetActualTime_ms());
      if(!released)trial.Cancel(match->GetActualTime_ms());
      if(AITactics::PressureHold185Enabled())
        printf("[tribun-pressure-hold] team=%d carrier=%d event=%s\n",team->GetID(),oldCarrier,released?"released":"cancelled");
    }
  }
  if(TribunTriangleContact(passer,receiver,shortPass))return;'''),
        ("  tribunTriangle.Clear(match->GetActualTime_ms());\n  if(!shooter", "  tribunTriangle.Clear(match->GetActualTime_ms());\n  match->tribunHoldTrials[team->GetID()].Cancel(match->GetActualTime_ms());\n  if(!shooter"),
    ])
    edit(root, "src/onthepitch/AIsupport/AIfunctions.cpp", [
        ("  desiredVelocity = RangeVelocity(desiredVelocity);\n}\n\nVector3 AI_GetForceFieldMovement", r'''  if(AITactics::HoldUpEnabled()&&player->HasUniquePossession()&&match->IsInPlay()&&
      !match->IsInSetPiece()&&!match->GetBallRetainer()&&!team->GetHumanGamerCount()&&
      player->GetFormationEntry().role!=e_PlayerRole_GK){
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
    ++trial.inspected;
    if((!trial.stage||((trial.stage==1||trial.stage==2)&&trial.carrier==player->GetID()))&&
        AI_GetMindSet(player->GetDynamicFormationEntry().role)>=.45f){
      ++trial.context;
      if(AITactics::HoldEligible(depth,facing.coords[0]*-side,nearest,gap,1.0f))++trial.geometry;
      if(AITactics::HoldEligible(depth,facing.coords[0]*-side,nearest,gap,skill)){
      ++trial.available;
      if(AITactics::PressureHold185Enabled()){
        // Compare achievable native movement requests with the current
        // decision, using the same score for baseline and candidates.
        const float cap=sprintVelocity*(.30f+.10f*skill);
        const float speed=RangeVelocity(std::min(desiredVelocity,cap));
        const auto nativeDir=desiredDirection.Get2D().GetNormalized(facing);
        const auto incoming=myMov.Get2D();
        auto score=[&](const Vector3& dir,float v){
          float clearance=100.0f,endClearance=100.0f;
          Vector3 end=myPos;
          for(float time:{.15f,.30f,.45f}){
            const float reach=AITactics::DuelReachTime(time,player->GetStat("physical_agility"));
            end=myPos+incoming*time+(dir*v-incoming)*reach;
            if(std::abs(end.coords[0])>pitchHalfW-1.5f||std::abs(end.coords[1])>pitchHalfH-1.5f)return -1000.0f;
            float sample=100.0f;
            for(const auto& opp:opponentPlayerImages)
              sample=std::min(sample,(end-opp.position-opp.movement*time).Get2D().GetLength());
            clearance=std::min(clearance,sample);endClearance=sample;
          }
          return AITactics::PressureShieldScore(clearance,dir.GetDotProduct(facing),
              -dir.GetDotProduct(threat.GetNormalized(0)),(end-myPos).coords[0]*-side,endClearance-nearest);
        };
        const float baseline=score(nativeDir,RangeVelocity(desiredVelocity));
        float best=baseline;Vector3 chosen=nativeDir;
        if(speed>=1.0f && speed<=sprintVelocity*.48f){
          for(float angle:{-.95f,-.60f,-.30f,0.0f,.30f,.60f,.95f}){
            const auto dir=facing.GetRotated2D(angle);
            const float rating=score(dir,speed);
            if(rating>best){best=rating;chosen=dir;}
          }
        }
        const bool newTrial=!trial.stage;
        if(best>baseline+.30f && best>-999.0f && (trial.stage||trial.Begin(player->GetID(),now))){
          desiredDirection=chosen;desiredVelocity=speed;
          if(newTrial)printf("[tribun-pressure-hold] team=%d carrier=%d event=started\n",team->GetID(),player->GetID());
        }
      }else{
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
    }
  }
  desiredVelocity = RangeVelocity(desiredVelocity);
}

Vector3 AI_GetForceFieldMovement'''),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet || timedCandidate || lineBreak || triangleCandidate) {", r'''      bool holdOutlet=false;
      float holdOdds=0.0f;
      if(AITactics::HoldUpEnabled()&&(runningPassEnabled||
          (AITactics::PressureHold185Enabled()&&CastPlayer()->HasUniquePossession()&&
           !team->GetHumanGamerCount()&&CastPlayer()->GetFormationEntry().role!=e_PlayerRole_GK&&
           match->IsInPlay()&&!match->IsInSetPiece()&&!match->GetBallRetainer()))&&
          match->tribunHoldTrials[team->GetID()].Ready(player->GetID(),match->GetActualTime_ms())&&
          mates.at(i)->GetFormationEntry().role!=e_PlayerRole_GK){
        const auto delta=mates.at(i)->GetPosition()-player->GetPosition();
        const float holdOffside=runningPassEnabled?passOffside:
            AI_GetOffsideLine(match,_mentalImage,abs(team->GetID()-1))*attackForward;
        const float margin=holdOffside-mates.at(i)->GetPosition().coords[0]*attackForward;
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
    const bool boxFinish207=boxProbe207 && AITactics::BoxFinish207Prefer(odds,
        bestMateRating.player?bestMateRating.passRating:0.0f);
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
    return (CombinedAIEnabled() || (value && std::strcmp(value,"1")==0)) && ShortMatchAttackEnabled() &&
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
        float bestScore=-1.0f;Vector3 bestTarget=targetPos;
        for(unsigned int ms=100;ms<=850;ms+=50){
          const auto predicted=mentalImage->GetBallPrediction(ms);
          const float depth=pitchHalfW-predicted.coords[0]*side;
          if(depth<.6f)break;
          const auto ground=predicted.Get2D();
          const float distance=(ground-player->GetPosition()).GetLength();
          if(!AITactics::KeeperIntercept(depth,predicted.coords[1],predicted.coords[2],distance,0,ms,skill))continue;
          if(depth<=pitchHalfW-targetPos.coords[0]*side+.35f)continue;
          const int arrival=eta(ground);
          if(!AITactics::KeeperIntercept(depth,predicted.coords[1],predicted.coords[2],distance,arrival,ms,skill))continue;
          const float score=AITactics::KeeperInterceptScore(depth,predicted.coords[1],predicted.coords[2],arrival,ms,skill);
          if(score>bestScore){bestScore=score;bestTarget=ground;}
        }
        if(bestScore>=0.0f){targetPos=bestTarget;maxVelocity=sprintVelocity;probe.Begin(CastPlayer()->GetID(),2,now);}
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
            const float currentDepth=pitchHalfW-targetPos.coords[0]*side;
            float bestScore=-1.0f;Vector3 bestTarget=targetPos;
            // Evaluate three depths on the goal ray, including a shorter
            // option if the original target is too far to reach safely.
            for(float fraction:{.65f,.82f,1.0f}){
              const float trial=std::clamp(d*fraction,1.4f,d);
              if(trial<=currentDepth+.35f)continue;
              const float rayY=predicted.coords[1]*trial/depth;
              const Vector3 candidate((pitchHalfW-trial)*side,clamp(rayY,-3.3f,3.3f),0);
              const float score=AITactics::KeeperChallengeScore(trial,candidate.coords[1]-rayY,
                (candidate-carrier).GetLength(),eta(candidate),skill);
              if(score>bestScore){bestScore=score;bestTarget=candidate;}
            }
            if(bestScore>=0.0f){targetPos=bestTarget;maxVelocity=sprintVelocity;probe.Begin(CastPlayer()->GetID(),1,now);}
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
    return (CollectiveEnabled() || (value && std::strcmp(value,"1")==0)) && ShortMatchAttackEnabled() &&
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
    return (CollectiveEnabled() || (value && std::strcmp(value,"1")==0)) && ShortMatchAttackEnabled() &&
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
      if(AITactics::CollectiveEnabled())tribunTriangle.Clear(now);
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
          (!AITactics::CollectiveEnabled()||!triangleCandidate)&&
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

    # Stage 77: adjust only the actual native low-ball dribble contact.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool CloseTouchEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_CLOSE_TOUCH");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
''' + CLOSE_TOUCH_RULES + "struct FixedDurationClock {"),
    ])
    edit(root, "src/onthepitch/match.hpp", [
        ("  AITactics::RoleProbe tribunRoleProbes[2];", "  AITactics::RoleProbe tribunRoleProbes[2];\n  AITactics::CloseTouchProbe tribunCloseTouches[2];"),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoid.cpp", [
        ('          printf("bumpyridebias (ballcontrol): %f\\n", bumpyRideBias);\n\n        match->GetBall()->Touch(touchVec);', r'''          printf("bumpyridebias (ballcontrol): %f\n", bumpyRideBias);

        if(AITactics::ShortMatchAttackEnabled()&&AITactics::FixedDurationEnabled()&&
            match->IsInPlay()&&!match->IsInSetPiece()&&!match->GetBallRetainer()&&
            !team->GetHumanGamerCount()&&CastPlayer()->HasUniquePossession()&&
            CastPlayer()->GetFormationEntry().role!=e_PlayerRole_GK&&
            !(currentAnim->originatingCommand.modifier&e_PlayerCommandModifier_KnockOn)&&
            match->GetBall()->Predict(0).coords[2]<=.35f&&bumpyRideBias<=.25f){
          const float original=touchVec.Get2D().GetLength();
          const auto movement=CalculateOutgoingMovement(currentAnim->positions).Get2D();
          const auto facing=movement.GetNormalized(CastPlayer()->GetDirectionVec());
          const float alignment=facing.GetDotProduct(touchVec.Get2D().GetNormalized(facing));
          const float skill=AITactics::ControlSkill(CastPlayer()->GetStat("technical_dribble"),
              CastPlayer()->GetStat("technical_ballcontrol"),CastPlayer()->GetStat("physical_agility"),
              CastPlayer()->GetStat("physical_balance"));
          if(AITactics::CloseTouchEnabled()){
            const float scale=AITactics::CloseTouchScale(original,movement.GetLength(),skill,
                CastPlayer()->GetClosestOpponentDistance(),alignment);
            touchVec.coords[0]*=scale;touchVec.coords[1]*=scale;
            xRot*=scale;yRot*=scale;
          }
          match->tribunCloseTouches[team->GetID()].Record(original,touchVec.Get2D().GetLength());
        }
        match->GetBall()->Touch(touchVec);'''),
    ])

    # Stage 97: a quarantined five-minute chance-creation policy.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool PaceEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_MATCH_PACE");
    return (CombinedAIEnabled() || (value && std::strcmp(value,"1")==0)) && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
''' + PACE_RULES + "struct FixedDurationClock {"),
    ])
    edit(root, "src/onthepitch/match.hpp", [
        ("  AITactics::CloseTouchProbe tribunCloseTouches[2];", "  AITactics::CloseTouchProbe tribunCloseTouches[2];\n  unsigned long tribunPacePasses[2]={0,0};"),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet || timedCandidate || lineBreak || triangleCandidate || holdOutlet || counterCandidate) {", r'''      bool paceCandidate=false;
      float paceOdds=0.0f,paceProgress=0.0f,paceDepth=0.0f;
      if(AITactics::PaceEnabled()&&runningPassEnabled&&match->IsInPlay()&&!match->IsInSetPiece()&&
          (!AITactics::CombinedAIEnabled()||(!triangleCandidate&&!counterCandidate))&&
          !match->GetBallRetainer()&&mates.at(i)->GetFormationEntry().role!=e_PlayerRole_GK){
        const auto delta=mates.at(i)->GetPosition()-player->GetPosition();
        paceProgress=delta.coords[0]*attackForward;
        paceDepth=pitchHalfW-player->GetPosition().coords[0]*attackForward;
        const float margin=passOffside-mates.at(i)->GetPosition().coords[0]*attackForward;
        if(AITactics::PaceOutlet(paceDepth,paceProgress,delta.GetLength(),margin,mateSit.spaceRating,1.0f)){
          paceOdds=_GetPassingOdds(mates.at(i),e_FunctionType_ShortPass,opponentPlayerImages);
          paceCandidate=AITactics::PaceOutlet(paceDepth,paceProgress,delta.GetLength(),margin,mateSit.spaceRating,paceOdds);
        }
      }
      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet || timedCandidate || lineBreak || triangleCandidate || holdOutlet || counterCandidate || paceCandidate) {'''),
        ("        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +", r'''        if(paceCandidate&&paceOdds>=mateRating.passRating-.03f){
          mateRating.passType=e_FunctionType_ShortPass;
          mateRating.passRating=paceOdds;
          mateRating.supportRating+=AITactics::PacePassBonus(paceProgress,paceDepth,tribunTempo);
          ++match->tribunPacePasses[team->GetID()];
        }else if(paceCandidate&&!(progressiveCandidate||supportCandidate||runningCandidate||deliveryCandidate||
            pressureOutlet||returnCandidate||retentionOutlet||timedCandidate||lineBreak||triangleCandidate||holdOutlet||counterCandidate))continue;
        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +'''),
        ("          finishPriority ||", r'''          (AITactics::PaceEnabled()&&match->IsInPlay()&&!match->IsInSetPiece()&&!match->GetBallRetainer()&&
            !team->GetHumanGamerCount()&&CastPlayer()->GetFormationEntry().role!=e_PlayerRole_GK&&
            AITactics::PaceShot(distance,angle,odds,player->GetStat("technical_shot"),CastPlayer()->HasUniquePossession())) ||
          finishPriority ||'''),
    ])
    # Use the already-tested ordinary ball-out restart path; exclude all
    # fouls, goals, half-time and penalty situations as before.
    edit(root, "src/onthepitch/referee.cpp", [
        ('      if (quickRestarts && std::strcmp(quickRestarts, "1") == 0 &&', r'''      const char* pace=std::getenv("TRIBUN_NATIVE_MATCH_PACE");
      const char* fixed=std::getenv("TRIBUN_NATIVE_FIXED_DURATION");
      const char* attack=std::getenv("TRIBUN_LEAGUE_SOCCER_ATTACK");
      const char* combined=std::getenv("TRIBUN_NATIVE_COMBINED_AI");
      const char* nullMode=std::getenv("TRIBUN_NATIVE_NULL_RENDERER");
      const bool combinedRestart=combined&&std::strcmp(combined,"1")==0&&nullMode&&std::strcmp(nullMode,"1")==0&&
        !std::getenv("TRIBUN_LEAGUE_SOCCER_COMMAND_DIR");
      const bool paceRestart=((pace&&std::strcmp(pace,"1")==0)||combinedRestart)&&fixed&&std::strcmp(fixed,"1")==0&&
          attack&&std::strcmp(attack,"short-match")==0&&std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
      if (((quickRestarts && std::strcmp(quickRestarts, "1") == 0)||paceRestart) &&'''),
    ])

    # Stage 78: bounded native locomotion root-motion planning; no touch or special clips.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool MotionSmoothEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_NATIVE_MOTION_SMOOTH");
    return value && std::strcmp(value,"1")==0 && ShortMatchAttackEnabled() &&
        FixedDurationEnabled() && std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
''' + MOTION_RULES + "struct FixedDurationClock {"),
    ])
    edit(root, "src/onthepitch/match.hpp", [
        ("  AITactics::CloseTouchProbe tribunCloseTouches[2];", "  AITactics::CloseTouchProbe tribunCloseTouches[2];\n  unsigned long tribunMotionPlanSteps=0,tribunMotionLimitedSteps=0;"),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoidbase.cpp", [
        ("  const std::string& animType = anim->GetAnimType();", r'''  const std::string& animType = anim->GetAnimType();
  const bool smoothMotion=AITactics::MotionSmoothEnabled()&&animType=="movement"&&!touch&&
      !player->GetExternalController()&&match->IsInPlay()&&!match->IsInSetPiece()&&!match->GetBallRetainer()&&
      anim->GetVariable("incoming_special_state").empty()&&anim->GetVariable("outgoing_special_state").empty();'''),
        ("    Vector3 tmpTemporalMovement = temporalMovement + toDesired;", r'''    if(smoothMotion){
      const auto limited=AITactics::LimitMotion(temporalMovement.coords[0],temporalMovement.coords[1],
          toDesired.coords[0],toDesired.coords[1],stat_agility,stat_acceleration,
          player->GetStat("physical_balance"),timeStep_ms*.001f);
      const Vector3 adjusted(limited.x,limited.y,toDesired.coords[2]);
      ++match->tribunMotionPlanSteps;
      if((adjusted-toDesired).GetLength()>.0001f)++match->tribunMotionLimitedSteps;
      toDesired=adjusted;
    }
    Vector3 tmpTemporalMovement = temporalMovement + toDesired;'''),
        ("      bool hardQuantize = true;", "      bool hardQuantize = !smoothMotion;"),
    ])

    # Stage 158: explicitly isolated lower-resolution shadow depth texture.
    edit(root, "src/systems/graphics/objects/graphics_light.cpp", [
        ('#include "graphics_light.hpp"', '#include "graphics_light.hpp"\n#include <cstdlib>\n#include <cstring>'),
        ('''      map.texture->GetResource()->CreateTexture(e_InternalPixelFormat_DepthComponent16,
                                                e_PixelFormat_DepthComponent, 2048, 2048, false,''',
         '''      const char* shadowSize = std::getenv("TRIBUN_AV_SHADOW_SIZE");
      const int shadowEdge = shadowSize && std::strcmp(shadowSize, "1024") == 0 ? 1024 : 2048;
      map.texture->GetResource()->CreateTexture(e_InternalPixelFormat_DepthComponent16,
                                                e_PixelFormat_DepthComponent, shadowEdge, shadowEdge, false,'''),
    ])
    edit(root, "src/systems/graphics/rendering/r3d_messages.cpp", [
        ('''  map.texture->GetResource()->GetSize(shadowW, shadowH);
  renderer->SetViewport(0, 0, shadowW, shadowH);''',
         '''  map.texture->GetResource()->GetSize(shadowW, shadowH);
  static bool tribunShadowLogged = false;
  if (!tribunShadowLogged) {
    printf("[tribun-render] shadow-viewport=%dx%d\\n", shadowW, shadowH);
    tribunShadowLogged = true;
  }
  renderer->SetViewport(0, 0, shadowW, shadowH);'''),
    ])

    # Stage 160: keep logical VAO identity separate from the resolved
    # double-buffered GL handle within one synchronous draw-queue call.
    edit(root, "src/systems/graphics/rendering/opengl_renderer3d.cpp", [
        ('#include "opengl_renderer3d.hpp"', '#include "opengl_renderer3d.hpp"\n#include <cstdlib>\n#include <cstring>\n#include <cstdio>'),
        ('''  signed int currentBoundBuffer = -1;
''', r'''  signed int currentBoundBuffer = -1;
  const char* vaoMode = std::getenv("TRIBUN_AV_VAO_CACHE");
  const bool measureVao = vaoMode && (std::strcmp(vaoMode,"0")==0 || std::strcmp(vaoMode,"1")==0);
  const bool cacheVao = measureVao && std::strcmp(vaoMode,"1")==0;
  signed int currentLogicalBuffer = -1;
  unsigned long long entries = 0, binds = 0, repeatedLogical = 0;
'''),
        ('''    if (currentBoundBuffer != vertexBuffer->GetVaoID()) {
      bufferSwitches++;

      int vaoID = vertexBuffer->GetVaoID();''', r'''    const int logicalVao = vertexBuffer->GetVaoID();
    if (measureVao) {
      ++entries;
      if (currentLogicalBuffer == logicalVao) ++repeatedLogical;
    }
    // The renderer processes this queue serially. VAOReadIndex and the
    // ping-pong map are not mutated inside this call.
    if ((cacheVao ? currentLogicalBuffer : currentBoundBuffer) != logicalVao) {
      bufferSwitches++;

      int vaoID = logicalVao;'''),
        ('''      currentBoundBuffer = vaoID;
      mapping.glBindVertexArray(vaoID);''', r'''      currentBoundBuffer = vaoID;
      mapping.glBindVertexArray(vaoID);
      if (measureVao) ++binds;'''),
        ('''    // glPushMatrix();

    // slow, why?''', r'''    currentLogicalBuffer = logicalVao;

    // glPushMatrix();

    // slow, why?'''),
        ('''  mapping.glBindVertexArray(0);
}

void OpenGLRenderer3D::RenderAABB''', r'''  mapping.glBindVertexArray(0);
  if (measureVao) {
    // Single renderer thread; no per-entry logging or GL queries.
    static unsigned long long calls=0,totalEntries=0,totalBinds=0,totalRepeated=0;
    ++calls; totalEntries+=entries; totalBinds+=binds; totalRepeated+=repeatedLogical;
    if (calls%256==0)
      std::fprintf(stderr,"[tribun-vao-cache] mode=%d calls=%llu entries=%llu binds=%llu repeats=%llu\n",
                   cacheVao?1:0,calls,totalEntries,totalBinds,totalRepeated);
  }
}

void OpenGLRenderer3D::RenderAABB'''),
    ])

    # Stage 161: the diffuse unit is already tracked inside each draw
    # queue. Retain material/shader updates and the active unit reset.
    edit(root, "src/systems/graphics/rendering/opengl_renderer3d.cpp", [
        ('''  signed int currentDiffuseTextureID = -1;''', r'''  signed int currentDiffuseTextureID = -1;
  const char* textureMode = std::getenv("TRIBUN_AV_TEXTURE_CACHE");
  const bool measureTexture = textureMode &&
      (std::strcmp(textureMode, "0") == 0 || std::strcmp(textureMode, "1") == 0);
  const bool cacheTexture = measureTexture && std::strcmp(textureMode, "1") == 0;
  unsigned long long materialChanges=0, diffuseBinds=0, sameDiffuse=0;'''),
        ('''          SetTextureUnit(0);
          mapping.glBindTexture(GL_TEXTURE_2D, diffuseTextureID);

          if (renderMode == e_RenderMode_Full) {''', r'''          SetTextureUnit(0);
          if (measureTexture) {
            ++materialChanges;
            if (diffuseTextureID == currentDiffuseTextureID) ++sameDiffuse;
          }
          if (!cacheTexture || diffuseTextureID != currentDiffuseTextureID) {
            mapping.glBindTexture(GL_TEXTURE_2D, diffuseTextureID);
            if (measureTexture) ++diffuseBinds;
          }

          if (renderMode == e_RenderMode_Full) {'''),
        ('''  mapping.glBindVertexArray(0);
  if (measureVao) {''', r'''  mapping.glBindVertexArray(0);
  if (measureTexture) {
    static unsigned long long calls=0, changes=0, binds=0, repeats=0;
    ++calls; changes+=materialChanges; binds+=diffuseBinds; repeats+=sameDiffuse;
    if (calls%256==0)
      std::fprintf(stderr,"[tribun-texture-cache] mode=%d calls=%llu changes=%llu binds=%llu repeats=%llu\n",
                   cacheTexture?1:0,calls,changes,binds,repeats);
  }
  if (measureVao) {'''),
    ])


    # Stage 172: sustained controlled stagnation, not animation-state surgery.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool IdleRecoveryEnabled() {
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_AV_IDLE_RECOVERY");
    return value && std::strcmp(value,"1")==0 && FixedDurationEnabled() &&
        std::getenv("TRIBUN_LEAGUE_SOCCER_FIXTURE");
  }();
  return enabled;
}
inline bool RecoveryMoveCandidate202(bool useMovement,bool shotQueued,float speed,float alignment){
  return useMovement && !shotQueued && std::isfinite(speed) &&
      std::isfinite(alignment) && speed>=1.2f && speed<=3.5f &&
      alignment>=.85f && alignment<=1.001f;
}
inline float RecoveryDirectionScore203(float clearance,float forwardDot,bool continuing,float priorDot){
  if(!std::isfinite(clearance)||!std::isfinite(forwardDot)||
      clearance<=1.65f||forwardDot<.20f||forwardDot>1.001f||
      (continuing&&(!std::isfinite(priorDot)||priorDot < -1.001f||priorDot>1.001f)))
    return -1000.0f;
  return std::min(clearance,5.0f)+.65f*forwardDot+
      (continuing?.8f*std::clamp(priorDot,-1.0f,1.0f):0.0f);
}
struct IdleRecoveryWatch {
  bool tracking=false;
  int phase=-1;
  unsigned long since=0,last=0,next=0,moveUntil=0;
  float px=0,py=0,bx=0,by=0,moveX=0,moveY=0;
  void Reset(){tracking=false;phase=-1;since=last=next=moveUntil=0;moveX=moveY=0;}
  void BeginMove(unsigned long now){if(tracking && last==now)moveUntil=now+300UL;}
  void StopMove(){moveUntil=0;moveX=moveY=0;}
  void SetMoveDirection(float x,float y){moveX=x;moveY=y;}
  bool ContinueMove(unsigned long now)const{
    return tracking && now==last && now<moveUntil;
  }
  bool Observe(bool eligible,int period,unsigned long now,
      float x,float y,float ballX,float ballY){
    if(!eligible){Reset();return false;}
    const float dx=x-px,dy=y-py,dbx=ballX-bx,dby=ballY-by;
    if(!tracking || phase!=period || now<last || now-last>250UL ||
       dx*dx+dy*dy>.45f*.45f || dbx*dbx+dby*dby>.55f*.55f){
      tracking=true;phase=period;since=last=now;next=now+1200UL;StopMove();
      px=x;py=y;bx=ballX;by=ballY;return false;
    }
    last=now;
    if(now<next)return false;
    next=now+400UL;
    return true;
  }
};
struct FixedDurationClock {'''),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.hpp", [
        ('#include "playercontroller.hpp"', '#include "playercontroller.hpp"\n#include "../../aitactics.hpp"'),
        ("  float lastDesiredVelocity;", "  float lastDesiredVelocity;\n  AITactics::IdleRecoveryWatch tribunIdleRecovery;"),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("void ElizaController::Reset() {", "void ElizaController::Reset() {\n  tribunIdleRecovery.Reset();"),
        ("  _Preprocess();  // calculate some variables", r'''  _Preprocess();  // calculate some variables
  bool recoverIdle=false;
  if(AITactics::IdleRecoveryEnabled()){
    const auto p=player->GetPosition();
    const auto ball=match->GetBall()->Predict(0);
    const auto phase=match->GetMatchPhase();
    const bool eligible=(phase==e_MatchPhase_1stHalf || phase==e_MatchPhase_2ndHalf) &&
        match->IsInPlay() && !match->IsInSetPiece() && !match->GetBallRetainer() &&
        team->GetHumanGamerCount()==0 && CastPlayer()->GetFormationEntry().role!=e_PlayerRole_GK &&
        CastPlayer()->IsActive() && match->GetDesignatedPossessionPlayer()==player &&
        CastPlayer()->HasUniquePossession() && match->GetLastTouchPlayer()==player &&
        (ball.Get2D()-p.Get2D()).GetLength()<=1.25f && ball.coords[2]<.8f &&
        player->GetMovement().GetLength()<.75f && match->GetBall()->GetMovement().GetLength()<1.0f;
    recoverIdle=tribunIdleRecovery.Observe(eligible,static_cast<int>(phase),
        match->GetActualTime_ms(),p.coords[0],p.coords[1],ball.coords[0],ball.coords[1]);
  }'''),
        ("  _SetInput(rawInputDirection, rawInputVelocityFloat);", r'''  // Only a settled, repeatedly stationary AI-controlled carrier reaches
  // this branch. Ordinary ball protection, running, keeper and set pieces
  // retain the native decisions. No forced ball touch or animation reset.
  bool tribunRecoveryMove202=false;
  const auto recoveryNow=match->GetActualTime_ms();
  const bool continueIdleMove=AITactics::IdleRecoveryEnabled() && tribunIdleRecovery.ContinueMove(recoveryNow);
  if(manualMovement)tribunIdleRecovery.StopMove();
  if((recoverIdle || continueIdleMove) && !manualMovement){
    const auto p=player->GetPosition();
    const float forward=-team->GetSide();
    std::vector<PlayerImage> rivals;
    _mentalImage->GetTeamPlayerImages(abs(team->GetID()-1),-1,rivals);
    std::vector<Player*> mates;
    team->GetActivePlayers(mates);
    const float offside=std::max(match->GetBall()->Predict(0).coords[0]*forward,
        AI_GetOffsideLine(match,_mentalImage,abs(team->GetID()-1))*forward);
    Player* outlet=nullptr;
    float best=-1.0f;
    if(recoverIdle)for(auto* mate:mates){
      if(mate==player || !mate->IsActive())continue;
      const auto target=mate->GetPosition();
      const auto delta=target-p;
      const float distance=delta.GetLength();
      const float advance=delta.coords[0]*forward;
      if(distance<3.0f || distance>23.0f ||
         (target.coords[0]*forward>0.0f && target.coords[0]*forward>offside-.5f))continue;
      float space=100.0f;
      for(const auto& rival:rivals)
        space=std::min(space,(target-rival.position).GetLength());
      if(space<1.4f)continue;
      const float odds=_GetPassingOdds(mate,e_FunctionType_ShortPass,rivals);
      if(!std::isfinite(odds)||odds<.55f)continue;
      const float score=odds+.07f*std::clamp(advance/10.0f,-1.0f,1.0f)+
          .03f*std::min(space,5.0f)/5.0f-
          (mate->GetFormationEntry().role==e_PlayerRole_GK?.10f:0.0f);
      if(score>best){best=score;outlet=mate;}
    }
    const char* action="no-safe-option";
    if(outlet){
      tribunIdleRecovery.StopMove();
      PlayerCommandQueue recovery;
      _AddPass(recovery,outlet,e_FunctionType_ShortPass);
      commandQueue.insert(commandQueue.begin(),recovery.begin(),recovery.end());
      action="safe-pass";
    }else{
      // If a short pass is not safe, look for a nearby forward/lateral
      // opening; retain native movement and touch animation selection.
      float directionBest=-1000.0f;
      Vector3 direction=Vector3(forward,0,0);
      bool found=false;
      for(float angle:{0.0f,-.7f,.7f,-1.35f,1.35f}){
        const auto dir=Vector3(forward,0,0).GetRotated2D(angle);
        const auto mid=p+dir*1.1f,end=p+dir*2.2f;
        if(std::abs(end.coords[0])>pitchHalfW-1.0f ||
           std::abs(end.coords[1])>pitchHalfH-1.0f)continue;
        float clearance=100.0f;
        for(const auto& rival:rivals){
          const auto future=rival.position+rival.movement*.3f;
          clearance=std::min(clearance,std::min((mid-future).GetLength(),(end-future).GetLength()));
        }
        const float priorDot=dir.coords[0]*tribunIdleRecovery.moveX+dir.coords[1]*tribunIdleRecovery.moveY;
        const float score=AITactics::RecoveryDirectionScore203(clearance,dir.coords[0]*forward,continueIdleMove,priorDot);
        if(score>directionBest){directionBest=score;direction=dir;found=true;}
      }
      float nearest=100.0f;
      for(const auto& rival:rivals)nearest=std::min(nearest,(p-rival.position).GetLength());
      if(found){
        rawInputDirection=direction;rawInputVelocityFloat=2.5f;
        tribunRecoveryMove202=true;
        if(recoverIdle)tribunIdleRecovery.BeginMove(recoveryNow);
        tribunIdleRecovery.SetMoveDirection(direction.coords[0],direction.coords[1]);
        action="safe-move";
      }else{
        tribunIdleRecovery.StopMove();
      }
      if(!found && recoverIdle && pitchHalfW+p.coords[0]*forward<20.0f && nearest<2.4f){
        PlayerCommandQueue recovery;
        _AddPanicPass(recovery);
        commandQueue.insert(commandQueue.begin(),recovery.begin(),recovery.end());
        action="defensive-clearance";
      }
    }
    if(recoverIdle)std::fprintf(stderr,"[tribun-idle-recovery] phase=%d match_ms=%lu player=%d action=%s\n",
        static_cast<int>(match->GetMatchPhase()),static_cast<unsigned long>(match->GetMatchTime_ms()),
        player->GetID(),action);
  }
  _SetInput(rawInputDirection, rawInputVelocityFloat);'''),
        (r'''    // ball control?
    _BallControlCommand(commandQueue, false, false,
                        false);  // last param true == enable sticky run direction.''', r'''    // ball control?
    const auto tribunRecoveryQueueSize=commandQueue.size();
    _BallControlCommand(commandQueue, false, false,
                        false);  // last param true == enable sticky run direction.
    if(tribunRecoveryMove202 && commandQueue.size()==tribunRecoveryQueueSize+1){
      const auto& candidate=commandQueue.back();
      bool shotQueued=false;
      for(const auto& queued:commandQueue)
        if(queued.desiredFunctionType==e_FunctionType_Shot)shotQueued=true;
      const float alignment=candidate.desiredDirection.GetDotProduct(rawInputDirection);
      if(candidate.desiredFunctionType==e_FunctionType_BallControl &&
          AITactics::RecoveryMoveCandidate202(candidate.useDesiredMovement,shotQueued,
              candidate.desiredVelocityFloat,alignment)){
        // Keep every command; the native animation selector still validates contact.
        std::rotate(commandQueue.begin(),commandQueue.end()-1,commandQueue.end());
        if(recoverIdle)std::fprintf(stderr,"[tribun-idle-move202] phase=%d match_ms=%lu player=%d queued=1\n",
            static_cast<int>(match->GetMatchPhase()),static_cast<unsigned long>(match->GetMatchTime_ms()),player->GetID());
      }
    }'''),
    ])


    # Stage 174: discard transient decisions at observed restart boundaries.
    # The referee and native animations still own the actual restart.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''struct RestartDecisionWatch {
  bool seen=false,open=false;
  int phase=-1;
  bool Observe(int period,bool playing){
    const bool changed=seen && (phase!=period || open!=playing);
    seen=true;phase=period;open=playing;
    return changed;
  }
};
struct FixedDurationClock {'''),
    ])
    edit(root, "src/onthepitch/teamAIcontroller.hpp", [
        ("  AITactics::TransitionState tribunTransition;", "  AITactics::TransitionState tribunTransition;\n  AITactics::RestartDecisionWatch tribunRestartDecision;"),
    ])
    edit(root, "src/onthepitch/teamAIcontroller.cpp", [
        ("  CalculateSituation();\n  if(AITactics::TransitionEnabled()", r'''  if(AITactics::IdleRecoveryEnabled() && !team->GetHumanGamerCount()){
    const bool open=match->IsInPlay() && !match->IsInSetPiece();
    const int phase=static_cast<int>(match->GetMatchPhase());
    if(tribunRestartDecision.Observe(phase,open)){
      const auto now=match->GetActualTime_ms();
      // Clear only transient open-play plans, never the referee's taker,
      // formation, score, stamina, ball state, or animation state.
      tribunCombination.Clear(now);
      tribunTriangle.Clear(now);
      tribunTimedAttack.Clear();
      tribunRebound.Clear();
      tribunReboundSupportID=-1;
      tribunTransition.Reset();
      zonePressureActive=false;
      endApplyTeamPressure_ms=now;
      teamPressurePlayer=nullptr;
      endApplyAttackingRun_ms=now;
      attackingRunPlayer=nullptr;
      forwardSupportPlayer=nullptr;
      std::fprintf(stderr,"[tribun-restart-decisions] phase=%d team=%d open=%d match_ms=%lu\n",
          phase,team->GetID(),open?1:0,static_cast<unsigned long>(match->GetMatchTime_ms()));
    }
  }
  CalculateSituation();
  if(AITactics::TransitionEnabled()'''),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.hpp", [
        ("  AITactics::IdleRecoveryWatch tribunIdleRecovery;", "  AITactics::IdleRecoveryWatch tribunIdleRecovery;\n  AITactics::RestartDecisionWatch tribunRestartDecision;"),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("  _Preprocess();  // calculate some variables\n  bool recoverIdle=false;", r'''  if(AITactics::IdleRecoveryEnabled() && !team->GetHumanGamerCount() &&
      tribunRestartDecision.Observe(static_cast<int>(match->GetMatchPhase()),
          match->IsInPlay() && !match->IsInSetPiece())){
    tribunIdleRecovery.Reset();
  }
  _Preprocess();  // calculate some variables
  bool recoverIdle=false;'''),
    ])



    # Stage 175: observe the real animation selector and touch geometry.
    # Diagnostic only; no changes to queue priority, selection, or physics.
    edit(root, "src/onthepitch/player/humanoid/humanoid.cpp", [
        ('#include "humanoid.hpp"', '#include "humanoid.hpp"\n#include <cstdio>'),
        ("  if (mayReQueue) {\n    interruptAnim = e_InterruptAnim_ReQueue;\n  }\n\n  if (interruptAnim != e_InterruptAnim_None) {", r'''  if (mayReQueue) {
    interruptAnim = e_InterruptAnim_ReQueue;
  }

  const bool tribunAudit=AITactics::IdleRecoveryEnabled() &&
      match->IsInPlay() && !match->IsInSetPiece() && !match->GetBallRetainer() &&
      !team->GetHumanGamerCount() && !CastPlayer()->GetExternalController() &&
      CastPlayer()->GetFormationEntry().role!=e_PlayerRole_GK;
  const auto tribunActionName=[](e_FunctionType type)->const char*{
    switch(type){
      case e_FunctionType_ShortPass:return "short-pass";
      case e_FunctionType_LongPass:return "long-pass";
      case e_FunctionType_HighPass:return "high-pass";
      case e_FunctionType_Shot:return "shot";
      case e_FunctionType_BallControl:return "ball-control";
      case e_FunctionType_Movement:return "movement";
      default:return nullptr;
    }
  };
  const auto tribunActionLog=[&](const char* event,const char* action){
    if(tribunAudit && action)
      std::fprintf(stderr,"[tribun-action] phase=%d actual_ms=%lu match_ms=%lu team=%d player=%d event=%s action=%s\n",
          static_cast<int>(match->GetMatchPhase()),
          static_cast<unsigned long>(match->GetActualTime_ms()),
          static_cast<unsigned long>(match->GetMatchTime_ms()),team->GetID(),
          CastPlayer()->GetID(),event,action);
  };
  if (interruptAnim != e_InterruptAnim_None) {'''),
        ("      found = SelectAnim(command, interruptAnim, preferPassAndShot);", r'''      const bool auditCandidate=tribunAudit && CastPlayer()->HasUniquePossession();
      found = SelectAnim(command, interruptAnim, preferPassAndShot);
      if(auditCandidate)
        tribunActionLog(found?"accepted":"rejected",tribunActionName(command.desiredFunctionType));'''),
        ("    if (fullBallDistance < touchableDistance &&\n        fabs(desiredBallHeight - match->GetBall()->Predict(0).coords[2]) < 1.0f) {", r'''    if(tribunAudit && !(fullBallDistance < touchableDistance &&
        fabs(desiredBallHeight - match->GetBall()->Predict(0).coords[2]) < 1.0f) &&
        currentAnim->functionType!=e_FunctionType_Movement)
      tribunActionLog("missed-touch",tribunActionName(currentAnim->functionType));
    if (fullBallDistance < touchableDistance &&
        fabs(desiredBallHeight - match->GetBall()->Predict(0).coords[2]) < 1.0f) {'''),
        ("        match->GetMatchData()->AddPassAttempt(team->GetID());", r'''        tribunActionLog("contact",tribunActionName(currentAnim->functionType));
        match->GetMatchData()->AddPassAttempt(team->GetID());'''),
        ("        match->GetMatchData()->AddShot(team->GetID());", r'''        tribunActionLog("contact","shot");
        match->GetMatchData()->AddShot(team->GetID());'''),
        ("          printf(\"bumpyridebias (ballcontrol): %f\\n\", bumpyRideBias);", r'''          printf("bumpyridebias (ballcontrol): %f\n", bumpyRideBias);
        tribunActionLog("contact","ball-control");'''),
    ])



    # Stage 176: temporarily prefer an existing alternative after repeated
    # rejection of the first attacking candidate. Never discard commands.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''struct ActionAlternativeWatch {
  int phase=-1,kind=-1;
  unsigned int rejects=0;
  unsigned long first=0,last=0,next=0;
  void Reset(){phase=kind=-1;rejects=0;first=last=next=0;}
  void Observe(bool eligible,int period,unsigned long now){
    if(!eligible || (phase!=-1 && phase!=period) ||
        (rejects && (now<last || now-last>600UL)))Reset();
    if(eligible)phase=period;
  }
  void Rejected(int type,unsigned long now){
    if(kind!=type || !rejects || now<last || now-last>600UL){
      kind=type;rejects=1;first=last=now;return;
    }
    if(now==last)return;
    last=now;
    if(rejects<1000)++rejects;
  }
  void Accepted(int type){
    if(kind==type){kind=-1;rejects=0;first=last=0;}
  }
  bool Ready(int type,unsigned long now)const{
    return kind==type && rejects>=3 && now>=last &&
        now-last<=600UL && now-first>=160UL && now>=next;
  }
  void Promoted(unsigned long now){next=now+500UL;}
};
struct FixedDurationClock {'''),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoid.hpp", [
        ('#include "humanoidbase.hpp"', '#include "humanoidbase.hpp"\n#include "../../aitactics.hpp"'),
        ("  Team* team;", "  Team* team;\n  AITactics::ActionAlternativeWatch tribunAlternative;"),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoid.cpp", [
        ('#include "humanoid.hpp"', '#include "humanoid.hpp"\n#include <algorithm>'),
        ("void Humanoid::ResetSituation(const Vector3& focusPos) {", "void Humanoid::ResetSituation(const Vector3& focusPos) {\n  tribunAlternative.Reset();"),
        ("  const auto tribunActionName=[]", r'''  const auto tribunNow=match->GetActualTime_ms();
  const auto tribunBall=match->GetBall()->Predict(0);
  const bool tribunAlternativeEligible=tribunAudit &&
      CastPlayer()->IsActive() && CastPlayer()->HasUniquePossession() &&
      match->GetDesignatedPossessionPlayer()==player &&
      match->GetLastTouchPlayer()==player && tribunBall.coords[2]<.8f &&
      (tribunBall.Get2D()-player->GetPosition().Get2D()).GetLength()<=1.25f &&
      player->GetMovement().GetLength()<.75f &&
      match->GetBall()->GetMovement().GetLength()<1.0f;
  tribunAlternative.Observe(tribunAlternativeEligible,
      static_cast<int>(match->GetMatchPhase()),tribunNow);
  const auto tribunAttackCandidate=[](e_FunctionType type){
    return type==e_FunctionType_ShortPass || type==e_FunctionType_LongPass ||
        type==e_FunctionType_HighPass || type==e_FunctionType_Shot;
  };
  const auto tribunActionName=[]'''),
        ("    // iterate through the command queue and pick the first that is applicable", r'''    // Reorder only a native alternative already judged viable by the AI.
    // Retain the original candidate and every fallback.
    bool tribunPromoted=false;
    if(tribunAlternativeEligible && !commandQueue.empty() &&
        tribunAttackCandidate(commandQueue.front().desiredFunctionType) &&
        tribunAlternative.Ready(static_cast<int>(commandQueue.front().desiredFunctionType),tribunNow)){
      const auto original=commandQueue.front().desiredFunctionType;
      auto alternative=commandQueue.end();
      // Prefer another native short pass type over a slow movement fallback.
      for(auto it=commandQueue.begin()+1;it!=commandQueue.end();++it){
        if(it->desiredFunctionType==e_FunctionType_ShortPass && original!=e_FunctionType_ShortPass){
          alternative=it;break;
        }
      }
      if(alternative==commandQueue.end()){
        for(auto it=commandQueue.begin()+1;it!=commandQueue.end();++it){
          if(it->desiredFunctionType==e_FunctionType_BallControl &&
              it->useDesiredMovement && it->desiredVelocityFloat>=1.2f){
            alternative=it;break;
          }
        }
      }
      if(alternative!=commandQueue.end()){
        const auto promoted=alternative->desiredFunctionType;
        std::rotate(commandQueue.begin(),alternative,alternative+1);
        tribunAlternative.Promoted(tribunNow);
        tribunPromoted=true;
        std::fprintf(stderr,"[tribun-action-alternative] phase=%d match_ms=%lu team=%d player=%d from=%s to=%s\n",
            static_cast<int>(match->GetMatchPhase()),
            static_cast<unsigned long>(match->GetMatchTime_ms()),team->GetID(),CastPlayer()->GetID(),
            tribunActionName(original),tribunActionName(promoted));
      }
    }
    // iterate through the command queue and pick the first that is applicable'''),
        ("    bool preferPassAndShot = false;", "    bool preferPassAndShot = tribunPromoted;"),
        ("      if(auditCandidate)\n        tribunActionLog(found?\"accepted\":\"rejected\",tribunActionName(command.desiredFunctionType));", r'''      if(auditCandidate)
        tribunActionLog(found?"accepted":"rejected",tribunActionName(command.desiredFunctionType));
      if(tribunAlternativeEligible && tribunAttackCandidate(command.desiredFunctionType)){
        const int kind=static_cast<int>(command.desiredFunctionType);
        if(found)tribunAlternative.Accepted(kind);
        else if(i==0 && !tribunPromoted)tribunAlternative.Rejected(kind,tribunNow);
      }'''),
    ])



    # Stage 177: distinguish failed touch geometry from selector rejection.
    # Do not enlarge the native contact radius or force a ball touch.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''struct MissedTouchWatch {
  int phase=-1,kind=-1;
  unsigned int misses=0;
  unsigned long first=0,last=0,next=0;
  void Reset(){phase=kind=-1;misses=0;first=last=next=0;}
  void Observe(bool controlled,int period,unsigned long now){
    if(!controlled || (phase!=-1 && phase!=period) ||
       (misses && (now<last || now-first>1500UL)))Reset();
    if(controlled)phase=period;
  }
  void Miss(int type,unsigned long now){
    if(kind!=type || !misses || now<last || now-first>1500UL){
      kind=type;misses=1;first=last=now;return;
    }
    if(now==last)return;
    last=now;if(misses<1000)++misses;
  }
  bool Ready(int type,unsigned long now)const{
    return kind==type && misses>=2 && now>=last &&
        now-first<=1500UL && now>=next;
  }
  void Promoted(unsigned long now){next=now+500UL;misses=0;kind=-1;first=last=0;}
  void Contact(){misses=0;kind=-1;first=last=0;}
};
struct FixedDurationClock {'''),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoid.hpp", [
        ("  AITactics::ActionAlternativeWatch tribunAlternative;", "  AITactics::ActionAlternativeWatch tribunAlternative;\n  AITactics::MissedTouchWatch tribunMissedTouch;"),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoid.cpp", [
        ("  tribunAlternative.Reset();\n  HumanoidBase::ResetSituation", "  tribunAlternative.Reset();\n  tribunMissedTouch.Reset();\n  HumanoidBase::ResetSituation"),
        ("  const auto tribunAttackCandidate=[]", r'''  const bool tribunTouchControlled=tribunAudit &&
      CastPlayer()->IsActive() && CastPlayer()->HasUniquePossession() &&
      match->GetDesignatedPossessionPlayer()==player &&
      match->GetLastTouchPlayer()==player;
  tribunMissedTouch.Observe(tribunTouchControlled,
      static_cast<int>(match->GetMatchPhase()),tribunNow);
  const auto tribunAttackCandidate=[]'''),
        ("        tribunAlternative.Ready(static_cast<int>(commandQueue.front().desiredFunctionType),tribunNow)){", r'''        (tribunAlternative.Ready(static_cast<int>(commandQueue.front().desiredFunctionType),tribunNow) ||
         tribunMissedTouch.Ready(static_cast<int>(commandQueue.front().desiredFunctionType),tribunNow))){
      const bool touchRetry=tribunMissedTouch.Ready(static_cast<int>(commandQueue.front().desiredFunctionType),tribunNow);'''),
        ("        tribunAlternative.Promoted(tribunNow);\n        tribunPromoted=true;", r'''        tribunAlternative.Promoted(tribunNow);
        if(touchRetry){
          tribunMissedTouch.Promoted(tribunNow);
          std::fprintf(stderr,"[tribun-touch-retry] phase=%d match_ms=%lu team=%d player=%d from=%s to=%s\n",
              static_cast<int>(match->GetMatchPhase()),
              static_cast<unsigned long>(match->GetMatchTime_ms()),team->GetID(),CastPlayer()->GetID(),
              tribunActionName(original),tribunActionName(promoted));
        }
        tribunPromoted=true;'''),
        ('      tribunActionLog("missed-touch",tribunActionName(currentAnim->functionType));', r'''      tribunActionLog("missed-touch",tribunActionName(currentAnim->functionType));
    if(tribunTouchControlled && tribunAttackCandidate(currentAnim->functionType) &&
        !(fullBallDistance < touchableDistance &&
          fabs(desiredBallHeight-match->GetBall()->Predict(0).coords[2])<1.0f)){
      tribunMissedTouch.Miss(static_cast<int>(currentAnim->functionType),tribunNow);
      std::fprintf(stderr,"[tribun-touch-geometry] phase=%d match_ms=%lu team=%d player=%d action=%s distance=%.4f limit=%.4f height_error=%.4f body_angle=%.4f player_speed=%.4f ball_speed=%.4f frame=%d touch_frame=%d\n",
          static_cast<int>(match->GetMatchPhase()),
          static_cast<unsigned long>(match->GetMatchTime_ms()),team->GetID(),CastPlayer()->GetID(),
          tribunActionName(currentAnim->functionType),fullBallDistance,touchableDistance,
          fabs(desiredBallHeight-match->GetBall()->Predict(0).coords[2]),
          spatialState.bodyAngle,player->GetMovement().GetLength(),
          match->GetBall()->GetMovement().GetLength(),currentAnim->frameNum,currentAnim->touchFrame);
    }'''),
        ('        tribunActionLog("contact",tribunActionName(currentAnim->functionType));', '        tribunMissedTouch.Contact();\n        tribunActionLog("contact",tribunActionName(currentAnim->functionType));'),
        ('        tribunActionLog("contact","shot");', '        tribunMissedTouch.Contact();\n        tribunActionLog("contact","shot");'),
        ('        tribunActionLog("contact","ball-control");', '        tribunMissedTouch.Contact();\n        tribunActionLog("contact","ball-control");'),
    ])



    # Stage 178: bounded native preparation when repeated contact failures
    # persist and no suitable Stage 176/177 alternative is queued.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool SafeBodyPreparation(float bodyDot,float adjustment,float ballDistance,
    float opponentClearance,float playerSpeed,float ballSpeed){
  return std::isfinite(bodyDot) && std::isfinite(adjustment) &&
      std::isfinite(ballDistance) && std::isfinite(opponentClearance) &&
      std::isfinite(playerSpeed) && std::isfinite(ballSpeed) &&
      bodyDot>=-1.01f && bodyDot<=1.01f && adjustment>=.12f && adjustment<=.8f &&
      ballDistance>=.2f && ballDistance<=.95f && opponentClearance>=2.2f &&
      playerSpeed>=0 && playerSpeed<.75f && ballSpeed>=0 && ballSpeed<.65f &&
      (bodyDot<.5f || adjustment>.35f);
}
struct FixedDurationClock {'''),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoid.cpp", [
        ("    // iterate through the command queue and pick the first that is applicable", r'''    // A short native adjustment is a fallback, not a forced pass or turn.
    // Retain the unmodified queue if preparation cannot safely be attempted.
    if(!tribunPromoted && tribunAlternativeEligible && !commandQueue.empty() &&
        tribunAttackCandidate(commandQueue.front().desiredFunctionType) &&
        tribunMissedTouch.Ready(static_cast<int>(commandQueue.front().desiredFunctionType),tribunNow)){
      const auto original=commandQueue.front().desiredFunctionType;
      const auto pos=player->GetPosition().Get2D();
      const auto ball=match->GetBall()->Predict(100).Get2D();
      const auto aim=commandQueue.front().touchInfo.desiredDirection.Get2D();
      const float aimLength=aim.GetLength();
      if(std::isfinite(aimLength) && aimLength>.1f){
        const auto direction=aim.GetNormalized(spatialState.directionVec);
        // Aim-relative approach, not a prescribed foot placement.
        const auto target=ball-direction*.45f;
        const auto delta=target-pos;
        const float step=delta.GetLength();
        const float bodyDot=spatialState.bodyDirectionVec.Get2D().GetNormalized(spatialState.directionVec).GetDotProduct(direction);
        float clearance=100.0f;
        std::vector<Player*> opponents;
        match->GetTeam(abs(team->GetID()-1))->GetActivePlayers(opponents);
        for(auto* opponent:opponents){
          if(!opponent || !opponent->IsActive())continue;
          const auto future=(opponent->GetPosition()+opponent->GetMovement()*.2f).Get2D();
          clearance=std::min(clearance,std::min((future-target).GetLength(),
              (opponent->GetPosition().Get2D()-pos).GetLength()));
        }
        if(AITactics::SafeBodyPreparation(bodyDot,step,(tribunBall.Get2D()-pos).GetLength(),
            clearance,player->GetMovement().GetLength(),match->GetBall()->GetMovement().GetLength()) &&
            std::abs(target.coords[0])<pitchHalfW-.7f && std::abs(target.coords[1])<pitchHalfH-.7f){
          for(const auto& candidate:commandQueue){
            if(candidate.desiredFunctionType!=e_FunctionType_Movement || !candidate.useDesiredMovement)continue;
            auto preparation=candidate;
            preparation.desiredDirection=delta.GetNormalized(spatialState.directionVec);
            preparation.desiredVelocityFloat=1.2f;
            preparation.useDesiredLookAt=true;
            preparation.desiredLookAt=pos+direction*5.0f;
            commandQueue.insert(commandQueue.begin(),preparation);
            tribunMissedTouch.Promoted(tribunNow);
            tribunAlternative.Promoted(tribunNow);
            tribunPromoted=true;
            std::fprintf(stderr,"[tribun-body-preparation] phase=%d match_ms=%lu team=%d player=%d action=%s body_dot=%.4f adjustment=%.4f clearance=%.4f\n",
                static_cast<int>(match->GetMatchPhase()),
                static_cast<unsigned long>(match->GetMatchTime_ms()),team->GetID(),CastPlayer()->GetID(),
                tribunActionName(original),bodyDot,step,clearance);
            break;
          }
        }
      }
    }
    // iterate through the command queue and pick the first that is applicable'''),
    ])



    # Stage 179: pair accepted native attack animations with their own contact
    # frame. Foot metadata is not a measurement of planted foot geometry.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''struct ContactTimingWatch {
  bool active=false;
  int phase=-1,kind=-1,animation=-1,frame=-1;
  unsigned long selected=0;
  void Reset(){active=false;phase=kind=animation=frame=-1;selected=0;}
  void Begin(int period,int type,int id,int touchFrame,unsigned long now){
    Reset();if(id<0 || touchFrame<0)return;
    active=true;phase=period;kind=type;animation=id;frame=touchFrame;selected=now;
  }
  bool Matches(int period,int type,int id,int touchFrame,unsigned long now)const{
    return active && phase==period && kind==type && animation==id &&
        frame==touchFrame && now>=selected && now-selected<=2000UL;
  }
  bool Finish(int period,int type,int id,int touchFrame,unsigned long now,unsigned long& elapsed){
    if(!Matches(period,type,id,touchFrame,now)){Reset();return false;}
    elapsed=now-selected;Reset();return true;
  }
};
struct FixedDurationClock {'''),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoid.hpp", [
        ("  AITactics::MissedTouchWatch tribunMissedTouch;", "  AITactics::MissedTouchWatch tribunMissedTouch;\n  AITactics::ContactTimingWatch tribunContactTiming;\n  int tribunSelectedFoot=-1;"),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoid.cpp", [
        ("  tribunMissedTouch.Reset();\n  HumanoidBase::ResetSituation", "  tribunMissedTouch.Reset();\n  tribunContactTiming.Reset();\n  HumanoidBase::ResetSituation"),
        ("  const auto tribunAttackCandidate=[]", r'''  if(!tribunAudit || (tribunContactTiming.active &&
      !tribunContactTiming.Matches(static_cast<int>(match->GetMatchPhase()),
          static_cast<int>(currentAnim->functionType),currentAnim->id,currentAnim->touchFrame,tribunNow)))
    tribunContactTiming.Reset();
  const auto tribunAttackCandidate=[]'''),
        ("      const bool auditCandidate=tribunAudit && CastPlayer()->HasUniquePossession();", r'''      const bool auditCandidate=tribunAudit && CastPlayer()->HasUniquePossession();
      const int tribunFootBefore=static_cast<int>(spatialState.foot);'''),
        ("      if(auditCandidate)\n        tribunActionLog", r'''      if(found){
        tribunContactTiming.Reset();
        if(auditCandidate && tribunAttackCandidate(currentAnim->functionType)){
          tribunContactTiming.Begin(static_cast<int>(match->GetMatchPhase()),
              static_cast<int>(currentAnim->functionType),currentAnim->id,currentAnim->touchFrame,tribunNow);
          tribunSelectedFoot=tribunFootBefore;
        }
      }
      if(auditCandidate)
        tribunActionLog'''),
        ("    if(tribunTouchControlled && tribunAttackCandidate(currentAnim->functionType) &&", r'''    unsigned long tribunContactElapsed=0;
    if(tribunAudit && tribunAttackCandidate(currentAnim->functionType) &&
        tribunContactTiming.Finish(static_cast<int>(match->GetMatchPhase()),
            static_cast<int>(currentAnim->functionType),currentAnim->id,currentAnim->touchFrame,
            tribunNow,tribunContactElapsed)){
      const auto part=currentAnim->anim->GetVariable("touch_bodypart");
      const char* contactSide=(part.find("left_foot")!=std::string::npos || part.find("left_leg")!=std::string::npos)?"left":
          (part.find("right_foot")!=std::string::npos || part.find("right_leg")!=std::string::npos)?"right":"other";
      const bool geometryOk=fullBallDistance < touchableDistance &&
          fabs(desiredBallHeight-match->GetBall()->Predict(0).coords[2])<1.0f;
      std::fprintf(stderr,"[tribun-foot-timing] phase=%d match_ms=%lu team=%d player=%d action=%s anim=%d frame=%d elapsed_ms=%lu state_foot=%d anim_foot=%d outgoing_foot=%d contact_side=%s geometry=%s\n",
          static_cast<int>(match->GetMatchPhase()),static_cast<unsigned long>(match->GetMatchTime_ms()),
          team->GetID(),CastPlayer()->GetID(),tribunActionName(currentAnim->functionType),
          currentAnim->id,currentAnim->touchFrame,tribunContactElapsed,tribunSelectedFoot,
          static_cast<int>(currentAnim->anim->GetCurrentFoot()),static_cast<int>(currentAnim->anim->GetOutgoingFoot()),
          contactSide,geometryOk?"pass":"miss");
    }
    if(tribunTouchControlled && tribunAttackCandidate(currentAnim->functionType) &&'''),
    ])



    # Stage 180: sample original skeletal ankle positions at the applied
    # snapshot, before historical rendering interpolation. Never read
    # live ball state from the render side or modify skeleton transforms.
    edit(root, "src/onthepitch/player/humanoid/humanoidbase.hpp", [
        ("  AnimApplyBuffer buf_animApplyBuffer;", r'''  AnimApplyBuffer buf_animApplyBuffer;
  struct TribunFootSnapshot {
    bool enabled=false;
    int playerId=-1,phase=-1,animation=-1,frame=-1,touchFrame=-1;
    unsigned long snapshot=0,matchMs=0;
    Vector3 ball=Vector3(0);
  };
  TribunFootSnapshot tribunFootBuffer,tribunFootFetched;
  bool tribunFootLogged=false;
  unsigned long tribunLastFootSnapshot=0;'''),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoidbase.cpp", [
        ('#include <cmath>', '#include <cmath>\n#include <cstdio>\n#include "../../aitactics.hpp"'),
        ("  buf_animApplyBuffer.snapshotTime_ms = snapshotTime_ms;", r'''  buf_animApplyBuffer.snapshotTime_ms = snapshotTime_ms;
  tribunFootBuffer.enabled=false;
  if(AITactics::IdleRecoveryEnabled() && match->IsInPlay() &&
      !match->IsInSetPiece() && !match->GetBallRetainer() &&
      !player->GetExternalController() && player->IsActive() &&
      match->GetDesignatedPossessionPlayer()==player && currentAnim &&
      currentAnim->anim==animApplyBuffer.anim && currentAnim->frameNum==animApplyBuffer.frameNum){
    const int frame=currentAnim->frameNum,touch=currentAnim->touchFrame;
    const bool nearTouch=touch>=0 && std::abs(frame-touch)<=3;
    const bool movement=currentAnim->functionType==e_FunctionType_Movement;
    if(nearTouch || movement){
      tribunFootBuffer.enabled=true;
      tribunFootBuffer.playerId=player->GetID();
      tribunFootBuffer.phase=static_cast<int>(match->GetMatchPhase());
      tribunFootBuffer.animation=currentAnim->id;
      tribunFootBuffer.frame=frame;tribunFootBuffer.touchFrame=touch;
      tribunFootBuffer.snapshot=snapshotTime_ms;
      tribunFootBuffer.matchMs=match->GetMatchTime_ms();
      tribunFootBuffer.ball=match->GetBall()->Predict(0);
    }
  }'''),
        ("  fetchedbuf_animApplyBuffer = buf_animApplyBuffer;", "  fetchedbuf_animApplyBuffer = buf_animApplyBuffer;\n  tribunFootFetched=tribunFootBuffer;"),
        ("  // we've just set the humanoid positions for time fetchedbuf_animApplyBuffer.snapshotTime_ms.", r'''  const auto& footSnapshot=tribunFootFetched;
  if(footSnapshot.enabled && footSnapshot.snapshot==fetchedbuf_animApplyBuffer.snapshotTime_ms &&
      footSnapshot.frame==fetchedbuf_animApplyBuffer.frameNum &&
      (!tribunFootLogged || footSnapshot.snapshot!=tribunLastFootSnapshot)){
    const auto left=nodeMap.find("left_ankle"),right=nodeMap.find("right_ankle");
    if(left!=nodeMap.end() && right!=nodeMap.end() && left->second && right->second){
      const auto l=left->second->GetDerivedPosition(),r=right->second->GetDerivedPosition();
      const auto b=footSnapshot.ball;
      std::fprintf(stderr,"[tribun-skeleton-feet] snapshot=%lu match_ms=%lu phase=%d player=%d anim=%d frame=%d touch_frame=%d left=%.5f,%.5f,%.5f right=%.5f,%.5f,%.5f ball=%.5f,%.5f,%.5f\n",
          footSnapshot.snapshot,footSnapshot.matchMs,footSnapshot.phase,footSnapshot.playerId,
          footSnapshot.animation,footSnapshot.frame,footSnapshot.touchFrame,
          l.coords[0],l.coords[1],l.coords[2],r.coords[0],r.coords[1],r.coords[2],
          b.coords[0],b.coords[1],b.coords[2]);
      tribunFootLogged=true;tribunLastFootSnapshot=footSnapshot.snapshot;
    }
  }
  // we've just set the humanoid positions for time fetchedbuf_animApplyBuffer.snapshotTime_ms.'''),
    ])



    # Stage 181: smooth the native locomotion pose correction, not root
    # motion, animation playback, touch radius or ball physics.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool LegBlendEnabled(){
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_AV_LEG_BLEND");
    return value && std::strcmp(value,"1")==0 && IdleRecoveryEnabled();
  }();
  return enabled;
}
struct LegBlendWatch {
  bool active=false;
  int phase=-1;
  unsigned long last=0;
  float value=1.0f;
  void Reset(){active=false;phase=-1;last=0;value=1.0f;}
  float Observe(bool eligible,int period,unsigned long now,float native){
    if(!eligible || !std::isfinite(native) || native<.1f || native>1.1f){
      Reset();return native;
    }
    if(!active || phase!=period || now<last || now-last>100UL){
      active=true;phase=period;last=now;value=native;return value;
    }
    if(now==last)return std::clamp(value,native-.12f,native+.12f);
    const float dt=static_cast<float>(now-last);
    last=now;
    const float alpha=dt/(dt+60.0f);
    value=std::clamp(value+(native-value)*alpha,native-.12f,native+.12f);
    value=std::clamp(value,.1f,1.1f);
    return value;
  }
};
struct FixedDurationClock {'''),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoid.hpp", [
        ("  int tribunSelectedFoot=-1;", "  int tribunSelectedFoot=-1;\n  AITactics::LegBlendWatch tribunLegBlend;"),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoid.cpp", [
        ("  tribunContactTiming.Reset();\n  HumanoidBase::ResetSituation", "  tribunContactTiming.Reset();\n  tribunLegBlend.Reset();\n  HumanoidBase::ResetSituation"),
        ("  bool adaptLegsToTrueVelocity = true;", r'''  const bool tribunBlendEligible=AITactics::LegBlendEnabled() &&
      match->IsInPlay() && !match->IsInSetPiece() && !match->GetBallRetainer() &&
      !team->GetHumanGamerCount() && !CastPlayer()->GetExternalController() &&
      CastPlayer()->IsActive() && CastPlayer()->GetFormationEntry().role!=e_PlayerRole_GK &&
      currentAnim->functionType==e_FunctionType_Movement && currentAnim->touchFrame==-1 &&
      currentAnim->anim->GetVariable("incoming_special_state").empty() &&
      currentAnim->anim->GetVariable("outgoing_special_state").empty() &&
      (match->GetBall()->Predict(0).Get2D()-spatialState.position.Get2D()).GetLength()>1.2f &&
      spatialState.actualMovement.GetLength()>=1.0f && spatialState.animMovement.GetLength()>=1.0f;
  if(!tribunBlendEligible)tribunLegBlend.Reset();
  bool adaptLegsToTrueVelocity = true;'''),
        ("        veloFactor = clamp(veloFactor, 0.1f, 1.0f + allowFasterFactor);", r'''        veloFactor = clamp(veloFactor, 0.1f, 1.0f + allowFasterFactor);
        if(tribunBlendEligible){
          const float original=veloFactor;
          veloFactor=tribunLegBlend.Observe(true,static_cast<int>(match->GetMatchPhase()),
              match->GetActualTime_ms(),original);
          // Keep the native faster-stride limit (including ordinary speed).
          veloFactor=clamp(veloFactor,0.1f,1.0f+allowFasterFactor);
          if(match->GetActualTime_ms()%250UL==0 && std::abs(veloFactor-original)>.005f)
            std::fprintf(stderr,"[tribun-leg-blend] phase=%d match_ms=%lu player=%d actual=%.4f anim=%.4f native=%.4f adjusted=%.4f\n",
                static_cast<int>(match->GetMatchPhase()),static_cast<unsigned long>(match->GetMatchTime_ms()),
                player->GetID(),actualVelo,animVelo,original,veloFactor);
        }'''),
    ])



    # Stage 182: reuse the native planner's longitudinal/lateral traction
    # limiter in a separately opted-in rendered fixture. Keep endpoint
    # quantization and all non-locomotion physics native.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool TurnBrakeEnabled(){
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_AV_TURN_BRAKE");
    return value && std::strcmp(value,"1")==0 && IdleRecoveryEnabled() && !LegBlendEnabled();
  }();
  return enabled;
}
inline MotionDelta TurnBrakeDelta(float vx,float vy,float dx,float dy,
    float agility,float acceleration,float balance,float dt){
  if(!std::isfinite(vx)||!std::isfinite(vy)||!std::isfinite(dx)||!std::isfinite(dy)||
      !std::isfinite(agility)||!std::isfinite(acceleration)||!std::isfinite(balance)||
      !std::isfinite(dt)||dt<=0||dt>.05f)return {dx,dy};
  const auto limited=LimitMotion(vx,vy,dx,dy,agility,acceleration,balance,dt);
  // Partial correction to avoid fighting the native clip's trajectory.
  // Stronger on lateral/reverse requests, gentler on straight acceleration.
  const float speed=std::hypot(vx,vy);
  float weight=.35f;
  if(speed>.5f){
    const float along=(dx*vx+dy*vy)/speed;
    const float across=std::abs((dy*vx-dx*vy)/speed);
    const float magnitude=std::hypot(dx,dy);
    if(magnitude>.0001f)
      weight=.35f+.35f*std::clamp((across+std::max(0.0f,-along))/magnitude,0.0f,1.0f);
  }
  return {dx+(limited.x-dx)*weight,dy+(limited.y-dy)*weight};
}
struct FixedDurationClock {'''),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoidbase.cpp", [
        ('#include "../playerbase.hpp"', '#include "../playerbase.hpp"\n#include "../player.hpp"\n#include "../../team.hpp"'),
        ("    Vector3 tmpTemporalMovement = temporalMovement + toDesired;", r'''    if(AITactics::TurnBrakeEnabled() && !smoothMotion && animType=="movement" &&
        !touch && match->IsInPlay() && !match->IsInSetPiece() && !match->GetBallRetainer() &&
        !player->GetExternalController() && player->IsActive() &&
        anim->GetVariable("incoming_special_state").empty() &&
        anim->GetVariable("outgoing_special_state").empty() &&
        (match->GetBall()->Predict(0).Get2D()-spatialState.position.Get2D()).GetLength()>2.0f){
      auto* footballer=dynamic_cast<Player*>(player);
      if(footballer && !footballer->GetTeam()->GetHumanGamerCount() &&
          footballer->GetFormationEntry().role!=e_PlayerRole_GK){
        const auto delta=AITactics::TurnBrakeDelta(temporalMovement.coords[0],temporalMovement.coords[1],
            toDesired.coords[0],toDesired.coords[1],stat_agility,stat_acceleration,
            player->GetStat("physical_balance"),timeStep_ms*.001f);
        toDesired=Vector3(delta.x,delta.y,toDesired.coords[2]);
      }
    }
    Vector3 tmpTemporalMovement = temporalMovement + toDesired;'''),
    ])



    # Stage 183: bound excessive low-ball dribble launch speed using the
    # actual native touch vector, without changing its direction or height.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool DribbleControlEnabled(){
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_AV_DRIBBLE_CONTROL");
    return value && std::strcmp(value,"1")==0 && IdleRecoveryEnabled() &&
        !LegBlendEnabled() && !TurnBrakeEnabled() && !CloseTouchEnabled();
  }();
  return enabled;
}
inline float DribbleControlScale(float planar,float projected,float skill,
    float clearance,float alignment,float bias){
  if(!std::isfinite(planar)||!std::isfinite(projected)||!std::isfinite(skill)||
      !std::isfinite(clearance)||!std::isfinite(alignment)||!std::isfinite(bias)||
      planar<=.01f||projected<0||clearance<1.5f||alignment<.3f||alignment>1.01f||
      bias<0||bias>.25f)return 1.0f;
  const float control=std::clamp(skill,0.0f,1.0f);
  const float allowance=1.5f+.8f*control+.6f*std::clamp((clearance-1.5f)/3.0f,0.0f,1.0f);
  const float cap=std::max(2.0f,projected+allowance);
  return std::clamp(cap/planar,.8f,1.0f);
}
struct FixedDurationClock {'''),
    ])
    edit(root, "src/onthepitch/player/humanoid/humanoid.cpp", [
        ("          match->tribunCloseTouches[team->GetID()].Record(original,touchVec.Get2D().GetLength());\n        }\n        match->GetBall()->Touch(touchVec);", r'''          match->tribunCloseTouches[team->GetID()].Record(original,touchVec.Get2D().GetLength());
        }
        if(tribunAudit && tribunTouchControlled && !AITactics::CloseTouchEnabled() &&
            !(currentAnim->originatingCommand.modifier&e_PlayerCommandModifier_KnockOn) &&
            match->GetBall()->Predict(0).coords[2]>=0.0f &&
            match->GetBall()->Predict(0).coords[2]<=.35f && bumpyRideBias<=.25f){
          const auto planar=touchVec.Get2D();
          const float before=planar.GetLength();
          if(before>.01f && std::isfinite(before)){
            const auto direction=planar.GetNormalized(CastPlayer()->GetDirectionVec());
            const auto planned=CalculateOutgoingMovement(currentAnim->positions).Get2D();
            const auto actual=player->GetMovement().Get2D();
            const float projected=std::max(0.0f,.65f*planned.GetDotProduct(direction)+.35f*actual.GetDotProduct(direction));
            const float alignment=planned.GetNormalized(CastPlayer()->GetDirectionVec()).GetDotProduct(direction);
            const float skill=AITactics::ControlSkill(CastPlayer()->GetStat("technical_dribble"),
                CastPlayer()->GetStat("technical_ballcontrol"),CastPlayer()->GetStat("physical_agility"),
                CastPlayer()->GetStat("physical_balance"));
            const float clearance=CastPlayer()->GetClosestOpponentDistance();
            const float proposed=AITactics::DribbleControlScale(before,projected,skill,clearance,alignment,bumpyRideBias);
            const bool enabled=AITactics::DribbleControlEnabled();
            const float applied=enabled?proposed:1.0f;
            touchVec.coords[0]*=applied;touchVec.coords[1]*=applied;
            xRot*=applied;yRot*=applied;
            std::fprintf(stderr,"[tribun-dribble-control] phase=%d match_ms=%lu team=%d player=%d enabled=%d before=%.5f after=%.5f projected=%.5f clearance=%.5f proposed=%.5f\n",
                static_cast<int>(match->GetMatchPhase()),static_cast<unsigned long>(match->GetMatchTime_ms()),
                team->GetID(),CastPlayer()->GetID(),enabled?1:0,before,touchVec.Get2D().GetLength(),
                projected,clearance,proposed);
          }
        }
        match->GetBall()->Touch(touchVec);'''),
    ])



    # Stage 186: prefer reachable native lead passes using moving defender
    # corridor samples. Do not replace native pass aim, power or physics.
    edit(root, "src/onthepitch/aitactics.hpp", [
        ("struct FixedDurationClock {", r'''inline bool PassTiming186Enabled(){
  static const bool enabled=[]{
    const char* value=std::getenv("TRIBUN_AV_PASS_TIMING");
    return value && std::strcmp(value,"1")==0 && IdleRecoveryEnabled();
  }();
  return enabled;
}
inline float NativeLeadDelay(float distance){
  return .7f*std::pow(std::clamp(.3f+.05f*distance,0.0f,1.0f),.7f);
}
inline bool LeadTimingSafe(float progress,float distance,float runSpeed,float margin,
    float clearance,float corridor,float odds,float reachError){
  return std::isfinite(progress)&&std::isfinite(distance)&&std::isfinite(runSpeed)&&
      std::isfinite(margin)&&std::isfinite(clearance)&&std::isfinite(corridor)&&
      std::isfinite(odds)&&std::isfinite(reachError)&&
      progress>=3.0f&&progress<=23.0f&&distance>=7.0f&&distance<=26.0f&&
      runSpeed>=1.6f&&margin>=1.5f&&clearance>=2.0f&&corridor>=1.4f&&
      odds>=.76f&&odds<=1.0f&&reachError>=0&&reachError<=1.8f;
}
inline float LeadTimingBonus(float corridor,float clearance,float odds){
  return .18f+.12f*std::clamp((corridor-1.4f)/2.0f,0.0f,1.0f)+
      .10f*std::clamp((clearance-2.0f)/3.0f,0.0f,1.0f)+
      .05f*std::clamp((odds-.76f)/.24f,0.0f,1.0f);
}
struct FixedDurationClock {'''),
    ])
    edit(root, "src/onthepitch/player/controller/elizacontroller.cpp", [
        ("    float proximityRating;\n    e_FunctionType passType;", "    float proximityRating;\n    bool timing186=false,runPass206=false;\n    e_FunctionType passType;"),
        ("      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet || timedCandidate || lineBreak || triangleCandidate || holdOutlet || counterCandidate || paceCandidate) {", r'''      bool timing186=false,runPass206=false;
      const bool standaloneTiming=AITactics::PassTiming186Enabled();
      float timingOdds=0.0f,timingCorridor=0.0f,timingClearance=0.0f;
      if((standaloneTiming||AITactics::Offball188Enabled()) && CastPlayer()->HasUniquePossession() &&
          match->GetLastTouchPlayer()==player && !team->GetHumanGamerCount() &&
          CastPlayer()->GetFormationEntry().role!=e_PlayerRole_GK &&
          mates.at(i)->GetFormationEntry().role!=e_PlayerRole_GK &&
          mates.at(i)->IsActive() && match->IsInPlay() && !match->IsInSetPiece() &&
          !match->GetBallRetainer()){
        const auto origin=(player->GetPosition()+player->GetMovement().GetNormalized(0)*.2f).Get2D();
        const auto recipient=mates.at(i)->GetPosition().Get2D();
        const auto movement=mates.at(i)->GetMovement().Get2D();
        const float distance=(recipient-origin).GetLength();
        const float margin=AI_GetOffsideLine(match,_mentalImage,abs(team->GetID()-1))*attackForward-
            recipient.coords[0]*attackForward;
        const float progress=(recipient-origin).coords[0]*attackForward;
        const float runSpeed=movement.coords[0]*attackForward;
        const AITactics::RunReservation189* runReservation=nullptr;
        if(AITactics::Offball188Enabled() && match->GetDesignatedPossessionPlayer()==player){
          for(const auto& lane:match->tribunRunReservations[team->GetID()]){
            if(AITactics::RunPass206Eligible(lane,mates.at(i)->GetID(),player->GetID(),
                static_cast<int>(match->GetMatchPhase()),match->GetActualTime_ms(),
                recipient.coords[0],recipient.coords[1],movement.coords[0],movement.coords[1])){
              runReservation=&lane;break;
            }
          }
        }
        if((standaloneTiming||runReservation) && AITactics::LeadTimingSafe(progress,distance,runSpeed,margin,100,100,1,0)){
          const auto future=recipient+movement*AITactics::NativeLeadDelay(distance);
          // Match the native forced-target long pass's forward offset.
          const auto target=future+Vector3(attackForward*(future-origin).GetLength()*.2f,0,0);
          const float travel=.7f+(target-origin).GetLength()*.03f;
          const float reachError=(target-(recipient+movement*travel)).GetLength();
          const bool nearRunTarget=runReservation &&
              AITactics::RunPass206Target(*runReservation,target.coords[0],target.coords[1]);
          if((standaloneTiming||nearRunTarget) && std::abs(target.coords[0])<pitchHalfW-1.0f && std::abs(target.coords[1])<pitchHalfH-1.0f){
            timingClearance=100;timingCorridor=100;
            for(const auto& opp:opponentPlayerImages){
              timingClearance=std::min(timingClearance,(target-opp.position-opp.movement*travel).Get2D().GetLength());
              for(float fraction:{.2f,.4f,.6f,.8f}){
                const auto point=origin+(target-origin)*fraction;
                timingCorridor=std::min(timingCorridor,(point-opp.position-opp.movement*(travel*fraction)).Get2D().GetLength());
              }
            }
            timingOdds=std::min(_GetPassingOdds(mates.at(i),e_FunctionType_LongPass,opponentPlayerImages),
                _GetPassingOdds(target,e_FunctionType_LongPass,opponentPlayerImages));
            timing186=AITactics::LeadTimingSafe(progress,distance,runSpeed,margin,timingClearance,
                timingCorridor,timingOdds,reachError);
            runPass206=timing186 && nearRunTarget;
          }
        }
      }
      if (progressiveCandidate || supportCandidate || runningCandidate || deliveryCandidate || pressureOutlet || returnCandidate || retentionOutlet || timedCandidate || lineBreak || triangleCandidate || holdOutlet || counterCandidate || paceCandidate || timing186) {'''),
        ("        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +", r'''        if(timing186 && timingOdds>=mateRating.passRating-.025f){
          mateRating.passType=e_FunctionType_LongPass;
          mateRating.passRating=timingOdds;
          mateRating.supportRating+=AITactics::LeadTimingBonus(timingCorridor,timingClearance,timingOdds);
          mateRating.timing186=true;
          mateRating.runPass206=runPass206;
        }else if(timing186 && !(progressiveCandidate||supportCandidate||runningCandidate||deliveryCandidate||
            pressureOutlet||returnCandidate||retentionOutlet||timedCandidate||lineBreak||triangleCandidate||
            holdOutlet||counterCandidate||paceCandidate))continue;
        float totalRating = mateRating.tacticalDiffRating * tacticalDiffWeight +'''),
        ("    _AddPass(commandQueue, bestMateRating.player, bestMateRating.passType);", r'''    _AddPass(commandQueue, bestMateRating.player, bestMateRating.passType);
    if(bestMateRating.runPass206)
      printf("[tribun-run-pass206] team=%d passer=%d receiver=%d match_ms=%lu odds=%.5f\n",
          team->GetID(),player->GetID(),bestMateRating.player->GetID(),
          static_cast<unsigned long>(match->GetMatchTime_ms()),bestMateRating.passRating);
    if(bestMateRating.timing186)
      printf("[tribun-pass-timing] team=%d passer=%d receiver=%d match_ms=%lu odds=%.5f\n",
          team->GetID(),player->GetID(),bestMateRating.player->GetID(),
          static_cast<unsigned long>(match->GetMatchTime_ms()),bestMateRating.passRating);'''),
    ])



    edit(root, "src/onthepitch/player/humanoid/humanoid.cpp", [
        ("        team->GetController()->TribunTimedPassContact(CastPlayer(),targetPlayer,\n            currentAnim->functionType==e_FunctionType_LongPass);", r'''        team->GetController()->TribunTimedPassContact(CastPlayer(),targetPlayer,
            currentAnim->functionType==e_FunctionType_LongPass);
        if((AITactics::PassTiming186Enabled()||AITactics::Offball188Enabled()) && tribunAudit && targetPlayer &&
            currentAnim->functionType==e_FunctionType_LongPass)
          std::fprintf(stderr,"[tribun-pass-timing-contact] team=%d passer=%d receiver=%d match_ms=%lu\n",
              team->GetID(),player->GetID(),targetPlayer->GetID(),
              static_cast<unsigned long>(match->GetMatchTime_ms()));'''),
    ])



def optimize_joint_cache(source):
    # Stage 159: cache repeated joint translation products, preserve all
    # four skinning channels, original rotations and blend operation order.
    for old, new in [
        ('#include <cmath>', '#include <cmath>\n#include <chrono>\n#include <mutex>\n#include <cstdlib>\n#include <cstring>\n#include <cstdio>'),
        ("  const bool uploadBitangents = channels.bitangents;", r'''  const bool uploadBitangents = channels.bitangents;
  const char* skinCacheMode = std::getenv("TRIBUN_AV_SKIN_CACHE");
  const bool measureSkin = !updateSrc && skinCacheMode &&
      (std::strcmp(skinCacheMode, "0") == 0 || std::strcmp(skinCacheMode, "1") == 0);
  const bool cacheSkin = measureSkin && std::strcmp(skinCacheMode, "1") == 0;
  const auto skinStart = measureSkin ? std::chrono::steady_clock::now() :
      std::chrono::steady_clock::time_point();
  std::vector<Vector3> scaledBind, scaledPose;
  if (cacheSkin) {
    scaledBind.reserve(joints.size());
    scaledPose.reserve(joints.size());
    for (const auto& joint : joints) {
      scaledBind.push_back(joint.origPos * zMultiplier);
      scaledPose.push_back(joint.position * zMultiplier);
    }
  }
  const auto bindOffset = [&](unsigned int id) -> Vector3 {
    return cacheSkin ? scaledBind[id] : joints[id].origPos * zMultiplier;
  };
  const auto poseOffset = [&](unsigned int id) -> Vector3 {
    return cacheSkin ? scaledPose[id] : joints[id].position * zMultiplier;
  };'''),
        ("joints[weightedVertices[v].bones[0].jointID].origPos * zMultiplier", "bindOffset(weightedVertices[v].bones[0].jointID)"),
        ("joints[weightedVertices[v].bones[0].jointID].position * zMultiplier", "poseOffset(weightedVertices[v].bones[0].jointID)"),
        ("joints[weightedVertices[v].bones[b].jointID].origPos * zMultiplier", "bindOffset(weightedVertices[v].bones[b].jointID)"),
        ("joints[weightedVertices[v].bones[b].jointID].position * zMultiplier", "poseOffset(weightedVertices[v].bones[b].jointID)"),
        ('''  fullbodyGeometryData->resourceMutex.unlock();
}''', r'''  fullbodyGeometryData->resourceMutex.unlock();
  if (measureSkin) {
    const auto elapsed = std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now() - skinStart).count();
    static std::mutex skinStatsMutex;
    static unsigned long long skinCalls = 0, skinNs = 0;
    std::lock_guard<std::mutex> guard(skinStatsMutex);
    ++skinCalls;
    skinNs += static_cast<unsigned long long>(elapsed);
    if (skinCalls % 256 == 0) {
      std::fprintf(stderr, "[tribun-skin-cache] mode=%d calls=%llu ns=%llu\n",
                   cacheSkin ? 1 : 0, skinCalls, skinNs);
    }
  }
}'''),
    ]:
        source = replace_once(source, old, new)
    return source
