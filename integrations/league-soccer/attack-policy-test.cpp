#include "aitactics.hpp"
#include <cassert>
int main(){
 using namespace AITactics;
 assert(ClearForwardCorridor(4,8,7,3,5));
 assert(!ClearForwardCorridor(-1,8,7,3,5));
 assert(!ClearForwardCorridor(4,2,7,3,5));
 assert(!ClearForwardCorridor(4,8,2,3,5));
 assert(!ClearForwardCorridor(4,8,7,1,5));
 assert(!ClearForwardCorridor(4,8,7,3,1));
 assert(PrioritizeGoodShot(13,.8,.75,true));
 assert(!PrioritizeGoodShot(30,.8,.75,true));
 assert(!PrioritizeGoodShot(13,.2,.75,true));
 assert(!PrioritizeGoodShot(13,.8,.35,true));
 assert(!PrioritizeGoodShot(13,.8,.75,false));
 assert(EligibleProgressiveRun(.7,10,18,2));
 assert(!EligibleProgressiveRun(.1,10,18,2));
 assert(!EligibleProgressiveRun(.7,10,18,.2));
 assert(!EligibleProgressiveRun(.7,10,40,2));
 assert(EligibleRunningPass(12,18,3,2,.8));
 assert(!EligibleRunningPass(12,18,3,2,.4));
 assert(!EligibleRunningPass(12,18,3,.2,.8));
 assert(!EligibleRunningPass(-4,18,3,2,.8));
 assert(!EligibleRunningPass(12,18,.2,2,.8));
 assert(ProgressiveRunCost(10,.9,8)<ProgressiveRunCost(10,.5,1));
}
