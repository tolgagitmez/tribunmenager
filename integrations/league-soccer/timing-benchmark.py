"""Measured native timing calibration. Never promotes a profile or edits league state."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import time

HERE=Path(__file__).resolve().parent
PROFILES=(("baseline","1.0","0"),("quick-restarts","1.0","1"),("quick-scale125","1.25","1"))

class Timing:
    def __init__(self):
        self.previous=None
        self.first=None
        self.final=None
        self.first_wall=None
        self.final_wall=None
        self.open_ms=0
        self.restart_ms=0
        self.dead_ms=0
        self.transition_ms=0
        self.gap_ms=0
        self.frames=0
        self.previous_wall=None
        self.max_observed_gap_ms=0
    def ingest(self,frame,now):
        if self.final is not None:
            raise ValueError("Frame after full time")
        if frame.get("engine")!="league-soccer" or frame.get("schema")!=1:
            raise ValueError("Wrong native trace")
        if any(type(frame.get(k)) is not bool for k in ("inPlay","setPiece","done")):
            raise ValueError("Missing play-state telemetry")
        if frame["inPlay"] and frame["setPiece"]:
            raise ValueError("Conflicting play states")
        if type(frame.get("elapsedMs")) is not int or frame["elapsedMs"]<0:
            raise ValueError("Invalid native clock")
        if self.previous and frame["elapsedMs"]<self.previous["elapsedMs"]:
            raise ValueError("Regressing clock")
        self.frames+=1
        if self.first is not None and self.previous_wall is not None:
            self.max_observed_gap_ms=max(self.max_observed_gap_ms,round((now-self.previous_wall)*1000))
        self.previous_wall=now
        if self.first is None and frame["inPlay"] and not frame["done"]:
            self.first=frame["elapsedMs"]
            self.first_wall=now
        if self.first is not None and self.previous and self.previous["elapsedMs"]>=self.first:
            dt=frame["elapsedMs"]-self.previous["elapsedMs"]
            if dt>250:
                self.gap_ms+=dt
            elif self.previous["phaseCode"]!=frame["phaseCode"] or any(self.previous[k]!=frame[k] for k in ("inPlay","setPiece")):
                self.transition_ms+=dt
            elif frame["inPlay"]:
                self.open_ms+=dt
            elif frame["setPiece"]:
                self.restart_ms+=dt
            else:
                self.dead_ms+=dt
        if frame["done"]:
            if self.first is None or frame.get("matchMs",0)<5400000:
                raise ValueError("Incomplete regulation match")
            self.final=frame["elapsedMs"]
            self.final_wall=now
        self.previous=frame
    def report(self):
        if self.final is None or self.first is None:
            raise ValueError("Missing observed full time")
        native=self.final-self.first
        wall=round((self.final_wall-self.first_wall)*1000)
        if native<=0 or wall<0:
            raise ValueError("Invalid match duration")
        if self.open_ms+self.restart_ms+self.dead_ms+self.transition_ms+self.gap_ms!=native:
            raise ValueError("Unaccounted timing interval")
        return dict(observedWallMs=wall,targetMs=300000,deviationMs=wall-300000,
                    nativeElapsedMs=native,openPlayMs=self.open_ms,setPieceMs=self.restart_ms,
                    deadBallMs=self.dead_ms,transitionMs=self.transition_ms,gapMs=self.gap_ms,
                    frames=self.frames,maxObservedGapMs=self.max_observed_gap_ms,withinFiveSeconds=abs(wall-300000)<=5000)

def sample_native_pss(group,proc=Path("/proc")):
    """Linux native process PSS, not RSS of shell or full process tree."""
    for path in proc.iterdir():
        if not path.name.isdigit():continue
        try:
            stat=(path/"stat").read_text().rsplit(")",1)[1].split()
            if int(stat[2])!=group:continue
            if Path(os.readlink(path/"exe")).name!="gameplayfootball":continue
            values={}
            for line in (path/"smaps_rollup").read_text().splitlines():
                key,_,value=line.partition(":")
                if key in ("Pss","Private_Dirty"):values[key]=int(value.split()[0])
            for line in (path/"status").read_text().splitlines():
                key,_,value=line.partition(":")
                if key=="Threads":values[key]=int(value.split()[0])
            if set(values)=={"Pss","Private_Dirty","Threads"}:return values
        except (OSError,ValueError,IndexError):continue
    return None

def run(runtime,fixture,out,profile,attack_profile='baseline',fixed_duration=False,retention=False,box_runs=False,timed_attack=False,render_threads=2,render_interval_ms=0,no_draw=False,no_upload=False,null_renderer=False,shared_assets=False,sample_pss=False,lean_scene=False,visual_rng=False,skip_pitch=False,task_workers=0,position_skinning=False,determinism_probe=False,ordered_pose=False,collision_pose=False,contact_interval_ms=100,adaptive_contact=False,surface_impact=False,angular_impact=False,swept_impact=False,split_impact=False,chain_impact=False,limb_impact=False,line_break=False,run_lanes=False,triangle=False,creative_carry=False,duel=False,hold_up=False,finish=False,keeper_ai=False,defense_shape=False):
    name,scale,quick=profile
    if type(defense_shape) is not bool or (defense_shape and (not fixed_duration or not null_renderer or attack_profile!="short-match" or any((keeper_ai,finish,hold_up,duel,creative_carry,triangle,line_break,run_lanes,retention,box_runs,timed_attack,collision_pose,determinism_probe)))):
        raise ValueError("Defense shape requires isolated short-match comparison")
    if type(keeper_ai) is not bool or (keeper_ai and (not fixed_duration or not null_renderer or attack_profile!="short-match" or any((finish,hold_up,duel,creative_carry,triangle,line_break,run_lanes,retention,box_runs,timed_attack,collision_pose,determinism_probe)))):
        raise ValueError("Keeper AI requires isolated short-match attack comparison")
    if type(finish) is not bool or (finish and (not fixed_duration or not null_renderer or attack_profile!="short-match" or any((hold_up,duel,creative_carry,triangle,line_break,run_lanes,retention,box_runs,timed_attack,collision_pose,determinism_probe)))):
        raise ValueError("Finish requires isolated short-match attack comparison")
    if type(hold_up) is not bool or (hold_up and (not fixed_duration or not null_renderer or attack_profile!="short-match" or any((duel,creative_carry,triangle,line_break,run_lanes,retention,box_runs,timed_attack,collision_pose,determinism_probe)))):
        raise ValueError("Hold-up requires isolated short-match attack comparison")
    if type(duel) is not bool or (duel and (not fixed_duration or not null_renderer or attack_profile!="short-match" or any((creative_carry,triangle,line_break,run_lanes,retention,box_runs,timed_attack,collision_pose,determinism_probe)))):
        raise ValueError("Duel requires isolated short-match attack comparison")
    if type(creative_carry) is not bool or (creative_carry and (not fixed_duration or not null_renderer or attack_profile!="short-match" or any((triangle,line_break,run_lanes,retention,box_runs,timed_attack,collision_pose,determinism_probe)))):
        raise ValueError("Creative carry requires isolated short-match attack comparison")
    if type(triangle) is not bool or (triangle and (not fixed_duration or not null_renderer or attack_profile!="short-match" or any((line_break,run_lanes,retention,box_runs,timed_attack,collision_pose,determinism_probe)))):
        raise ValueError("Triangle requires isolated short-match attack comparison")
    if type(run_lanes) is not bool or (run_lanes and (not fixed_duration or not null_renderer or attack_profile!="short-match" or any((line_break,retention,box_runs,timed_attack,collision_pose,determinism_probe)))):
        raise ValueError("Run lanes require isolated short-match attack comparison")
    if type(line_break) is not bool or (line_break and (not fixed_duration or not null_renderer or attack_profile!="short-match" or any((retention,box_runs,timed_attack,collision_pose,determinism_probe)))):
        raise ValueError("Line break requires isolated short-match attack comparison")
    if type(limb_impact) is not bool or (limb_impact and not chain_impact):
        raise ValueError("Limb impact requires chain impact diagnostic")
    if type(chain_impact) is not bool or (chain_impact and not split_impact):
        raise ValueError("Chain impact requires split impact diagnostic")
    if type(split_impact) is not bool or (split_impact and not swept_impact):
        raise ValueError("Split impact requires swept impact diagnostic")
    if type(swept_impact) is not bool or (swept_impact and not angular_impact):
        raise ValueError("Swept impact requires angular impact diagnostic")
    if type(angular_impact) is not bool or (angular_impact and not surface_impact):
        raise ValueError("Angular impact requires surface impact diagnostic")
    if type(surface_impact) is not bool or (surface_impact and (not collision_pose or contact_interval_ms!=10 or adaptive_contact)):
        raise ValueError("Surface impact requires isolated uniform 10 ms contact")
    if type(adaptive_contact) is not bool or (adaptive_contact and (not collision_pose or contact_interval_ms!=10)):
        raise ValueError("Adaptive contact requires collision-only 10 ms reference cadence")
    if type(contact_interval_ms) is not int or contact_interval_ms not in (100,50,20,10) or (contact_interval_ms!=100 and not collision_pose):
        raise ValueError("Contact interval requires collision-only mode; allowed 100,50,20,10 ms")
    if type(collision_pose) is not bool or (collision_pose and not ordered_pose):
        raise ValueError("Collision-only pose requires ordered deterministic null diagnostic")
    if type(ordered_pose) is not bool or (ordered_pose and not determinism_probe):
        raise ValueError("Ordered pose requires deterministic null diagnostic")
    if type(determinism_probe) is not bool or (determinism_probe and not (null_renderer and fixed_duration and sample_pss)):
        raise ValueError("Determinism probe requires fixed-clock sampled null mode")
    if type(position_skinning) is not bool or (position_skinning and not (null_renderer and sample_pss)):
        raise ValueError("Position-only skinning requires isolated null backend and sampling")
    if type(task_workers) is not int or task_workers not in (0,3,4) or (task_workers and not (null_renderer and sample_pss)):
        raise ValueError("Task worker limit requires isolated null backend and native resource sampling")
    if type(visual_rng) is not bool or type(skip_pitch) is not bool or (visual_rng and not (null_renderer and lean_scene)) or (skip_pitch and not visual_rng):
        raise ValueError("Pitch diagnostic requires isolated visual RNG and lean null scene")
    if type(lean_scene) is not bool or (lean_scene and (not null_renderer or shared_assets)):
        raise ValueError("Lean scene requires isolated null backend and full-copy runtime")
    if type(shared_assets) is not bool or type(sample_pss) is not bool or ((shared_assets or sample_pss) and not null_renderer):
        raise ValueError("Shared asset/PSS diagnostic requires null backend")
    if type(null_renderer) is not bool or (null_renderer and not (no_draw and no_upload)):
        raise ValueError("Null renderer requires isolated no-draw/no-upload")
    if type(no_upload) is not bool or (no_upload and not no_draw):
        raise ValueError("Geometry upload diagnostic requires no-draw")
    if type(no_draw) is not bool or (no_draw and (not fixed_duration or render_interval_ms!=100 or scale!="1.0" or quick!="0" or any((retention,box_runs,timed_attack)))):
        raise ValueError("Isolate no-draw diagnostic at fixed clock and 100 ms cadence")
    if type(render_interval_ms) is not int or render_interval_ms not in (0,100):raise ValueError("Invalid render cadence")
    if render_interval_ms and (not fixed_duration or any((retention,box_runs,timed_attack))):raise ValueError("Isolate fixed-clock render cadence")
    if type(render_threads) is not int or render_threads not in (1,2,3,4):raise ValueError("Invalid software renderer thread limit")
    if attack_profile not in ("baseline","short-match"):raise ValueError("Unknown attack profile")
    trace=Path(str(out)+"."+name+".ndjson").resolve()
    trace.unlink(missing_ok=True)
    env={**os.environ,"TRIBUN_NATIVE_REALTIME":"1","TRIBUN_NATIVE_CLOCK_SCALE":scale,
         "TRIBUN_NATIVE_QUICK_RESTARTS":quick,"TRIBUN_LEAGUE_SOCCER_ATTACK":attack_profile,
         "LP_NUM_THREADS":str(render_threads),"OMP_NUM_THREADS":"1"}
    env["TRIBUN_NATIVE_NO_DRAW"]="1" if no_draw else "0"
    env["TRIBUN_NATIVE_NO_UPLOAD"]="1" if no_upload else "0"
    env["TRIBUN_NATIVE_NULL_RENDERER"]="1" if null_renderer else "0"
    env["TRIBUN_NATIVE_SHARED_ASSETS"]="1" if shared_assets else "0"
    env["TRIBUN_NATIVE_LEAN_SCENE"]="1" if lean_scene else "0"
    env["TRIBUN_NATIVE_VISUAL_RNG"]="1" if visual_rng else "0"
    env["TRIBUN_NATIVE_SKIP_PITCH_TEXTURE"]="1" if skip_pitch else "0"
    env["TRIBUN_NATIVE_TASK_WORKERS"]=str(task_workers)
    env["TRIBUN_NATIVE_POSITION_SKINNING"]="1" if position_skinning else "0"
    env["TRIBUN_NATIVE_DETERMINISM"]="1" if determinism_probe else "0"
    env["TRIBUN_NATIVE_ORDERED_POSE"]="1" if ordered_pose else "0"
    env["TRIBUN_NATIVE_COLLISION_POSE"]="1" if collision_pose else "0"
    env["TRIBUN_NATIVE_CONTACT_INTERVAL_MS"]=str(contact_interval_ms)
    env["TRIBUN_NATIVE_ADAPTIVE_CONTACT"]="1" if adaptive_contact else "0"
    env["TRIBUN_NATIVE_SURFACE_IMPACT"]="1" if surface_impact else "0"
    env["TRIBUN_NATIVE_ANGULAR_IMPACT"]="1" if angular_impact else "0"
    env["TRIBUN_NATIVE_SWEPT_IMPACT"]="1" if swept_impact else "0"
    env["TRIBUN_NATIVE_SPLIT_IMPACT"]="1" if split_impact else "0"
    env["TRIBUN_NATIVE_CHAIN_IMPACT"]="1" if chain_impact else "0"
    env["TRIBUN_NATIVE_LIMB_IMPACT"]="1" if limb_impact else "0"
    env["TRIBUN_NATIVE_LINE_BREAK"]="1" if line_break else "0"
    env["TRIBUN_NATIVE_RUN_LANES"]="1" if run_lanes else "0"
    env["TRIBUN_NATIVE_TRIANGLE"]="1" if triangle else "0"
    env["TRIBUN_NATIVE_CREATIVE_CARRY"]="1" if creative_carry else "0"
    env["TRIBUN_NATIVE_DUEL"]="1" if duel else "0"
    env["TRIBUN_NATIVE_HOLD_UP"]="1" if hold_up else "0"
    env["TRIBUN_NATIVE_FINISH"]="1" if finish else "0"
    env["TRIBUN_NATIVE_KEEPER_AI"]="1" if keeper_ai else "0"
    env["TRIBUN_NATIVE_DEFENSE_SHAPE"]="1" if defense_shape else "0"
    env["TRIBUN_NATIVE_FIXED_DURATION"]="1" if fixed_duration else "0"
    env["TRIBUN_NATIVE_FINAL_THIRD_RETENTION"]="1" if retention else "0"
    env["TRIBUN_NATIVE_BOX_LANE_RUNS"]="1" if box_runs else "0"
    env["TRIBUN_NATIVE_TIMED_ATTACK"]="1" if timed_attack else "0"
    if (retention or box_runs or timed_attack) and (attack_profile!="short-match" or not fixed_duration):
        raise ValueError("Attack diagnostic requires fixed-clock short-match")
    if sum((retention,box_runs,timed_attack))>1:
        raise ValueError("Isolate one experimental policy at a time")
    for k in ("TRIBUN_LEAGUE_SOCCER_COMMAND_DIR","TRIBUN_NATIVE_EXPERIMENTAL_SUBSTITUTIONS"):
        env.pop(k,None)
    stats=Timing()
    pss_samples=[]
    next_pss=0.0
    layout=Path(str(trace)+".layout.json")
    layout.unlink(missing_ok=True)
    offset=0
    def drain():
        nonlocal offset
        if not trace.exists():return
        if trace.stat().st_size>100*1024*1024:raise RuntimeError("Trace size limit")
        with trace.open("rb") as handle:
            handle.seek(offset)
            while True:
                line=handle.readline(262145)
                if len(line)>262144:raise RuntimeError("Frame size limit")
                if not line.endswith(b"\n"):break
                stats.ingest(json.loads(line),time.monotonic())
                offset=handle.tell()
    resources=Path(str(trace)+".resources.json")
    resources.unlink(missing_ok=True)
    command=["bash",str(HERE/"run-frozen.sh"),runtime,fixture,str(trace),str(render_interval_ms)]
    if Path("/usr/bin/time").is_file():
        command=["/usr/bin/time","-o",str(resources),"-f",
                 '{"userSeconds":%U,"systemSeconds":%S,"maxRssKiB":%M,"elapsedSeconds":%e}',*command]
    launch=time.monotonic()
    with Path(str(trace)+".log").open("wb") as log:
        process=subprocess.Popen(command,
                                 env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+900
        try:
            while process.poll() is None:
                drain()
                now=time.monotonic()
                if sample_pss and now>=next_pss:
                    sample=sample_native_pss(process.pid)
                    if sample is not None:pss_samples.append({"monotonic":now,**sample})
                    next_pss=now+1.0
                if time.monotonic()>deadline:raise TimeoutError("Timing pilot timeout")
                time.sleep(.1)
            drain()
            if process.returncode:raise RuntimeError("Native runner failed; see "+str(trace)+".log")
        finally:
            if process.poll() is None:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait()
    marker="[tribun-render] scheduled-draw="+("off" if no_draw else "on")
    if no_draw and marker not in Path(str(trace)+".log").read_text(errors="replace"):
        raise ValueError("Missing native no-draw marker")
    if no_upload and "[tribun-render] geometry-upload=off" not in Path(str(trace)+".log").read_text(errors="replace"):
        raise ValueError("Missing native geometry-upload marker")
    if null_renderer and "[tribun-render] null-context=dummy-no-gl" not in Path(str(trace)+".log").read_text(errors="replace"):
        raise ValueError("Missing null renderer context marker")
    if lean_scene:
        log_text=Path(str(trace)+".log").read_text(errors="replace")
        if any(marker not in log_text for marker in ("[tribun-lean] pitch-only=1 crowd-audio=0","[tribun-lean] audio-backend=null")):
            raise ValueError("Missing lean scene evidence")
    if visual_rng:
        marker="[tribun-visual] rng=isolated pitch-texture="+("off" if skip_pitch else "on")
        if marker not in Path(str(trace)+".log").read_text(errors="replace"):
            raise ValueError("Missing visual RNG evidence")
    if determinism_probe and "[tribun-determinism] fixed-grid=100 visual-rng=isolated" not in Path(str(trace)+".log").read_text(errors="replace"):
        raise ValueError("Missing deterministic probe evidence")
    report=stats.report()
    report["determinismProbe"]=determinism_probe
    report["orderedPose"]=ordered_pose
    marker="[tribun-pose] schedule=ordered interval-ticks=10"
    if (marker in Path(str(trace)+".log").read_text(errors="replace")) != ordered_pose:
        raise ValueError("Ordered pose marker mismatch")
    report["positionSkinning"]=position_skinning
    report["collisionPose"]=collision_pose
    log_text=Path(str(trace)+".log").read_text(errors="replace")
    collision_marker="[tribun-collision] pose=simulation visual-mesh=off local-hud=off"
    if (collision_marker in log_text)!=collision_pose:
        raise ValueError("Collision pose marker mismatch")
    report["contactIntervalMs"]=contact_interval_ms
    report["adaptiveContact"]=adaptive_contact
    report["surfaceImpact"]=surface_impact
    report["angularImpact"]=angular_impact
    report["sweptImpact"]=swept_impact
    report["splitImpact"]=split_impact
    report["chainImpact"]=chain_impact
    report["limbImpact"]=limb_impact
    report["lineBreak"]=line_break
    report["runLanes"]=run_lanes
    report["triangle"]=triangle
    report["creativeCarry"]=creative_carry
    report["duel"]=duel
    report["holdUp"]=hold_up
    report["finish"]=finish
    report["keeperAI"]=keeper_ai
    report["defenseShape"]=defense_shape
    if line_break or null_renderer:
        import re
        found=re.findall(r"\[tribun-linebreak\] mode=(linebreak|off) candidates=(\d+),(\d+) selected=(\d+),(\d+)",log_text)
        if len(found)!=1 or found[0][0]!=("linebreak" if line_break else "off"):
            raise ValueError("Missing line break policy evidence")
        _,a,b,c,d=found[0]
        report["lineBreakProbe"]={"candidates":[int(a),int(b)],"selected":[int(c),int(d)]}
        lanes=re.findall(r"\[tribun-runlanes\] mode=(lanes|off) attempts=(\d+),(\d+) primary=(\d+),(\d+) secondary=(\d+),(\d+)",log_text)
        if len(lanes)!=1 or lanes[0][0]!=("lanes" if run_lanes else "off"):
            raise ValueError("Missing run lane evidence")
        _,a,b,c,d,e,f=lanes[0]
        report["runLaneProbe"]={"attempts":[int(a),int(b)],"primary":[int(c),int(d)],"secondary":[int(e),int(f)]}
        tri=re.findall(r"\[tribun-triangle\] mode=(triangle|off) started=(\d+),(\d+) received=(\d+),(\d+) passed=(\d+),(\d+) completed=(\d+),(\d+)",log_text)
        if len(tri)!=1 or tri[0][0]!=("triangle" if triangle else "off"):
            raise ValueError("Missing triangle evidence")
        _,a,b,c,d,e,f,g,h=tri[0]
        report["triangleProbe"]={"started":[int(a),int(b)],"received":[int(c),int(d)],"passed":[int(e),int(f)],"completed":[int(g),int(h)]}
        carry=re.findall(r"\[tribun-carry\] mode=(carry|off) attempts=(\d+),(\d+) progressed=(\d+),(\d+) lost=(\d+),(\d+) cancelled=(\d+),(\d+) technical=(\d+),(\d+) conservative=(\d+),(\d+)",log_text)
        if len(carry)!=1 or carry[0][0]!=("carry" if creative_carry else "off"):
            raise ValueError("Missing creative carry evidence")
        values=list(map(int,carry[0][1:]))
        report["carryProbe"]={k:values[2*j:2*j+2] for j,k in enumerate(("attempts","progressed","lost","cancelled","technical","conservative"))}
        duels=re.findall(r"\[tribun-duel\] mode=(duel|off) attempts=(\d+),(\d+) beaten=(\d+),(\d+) lost=(\d+),(\d+) cancelled=(\d+),(\d+)",log_text)
        if len(duels)!=1 or duels[0][0]!=("duel" if duel else "off"):
            raise ValueError("Missing duel evidence")
        values=list(map(int,duels[0][1:]))
        report["duelProbe"]={k:values[2*j:2*j+2] for j,k in enumerate(("attempts","beaten","lost","cancelled"))}
        holds=re.findall(r"\[tribun-hold\] mode=(hold|off) attempts=(\d+),(\d+) held=(\d+),(\d+) released=(\d+),(\d+) received=(\d+),(\d+) lost=(\d+),(\d+) cancelled=(\d+),(\d+)",log_text)
        if len(holds)!=1 or holds[0][0]!=("hold" if hold_up else "off"):
            raise ValueError("Missing hold-up evidence")
        values=list(map(int,holds[0][1:]))
        report["holdProbe"]={k:values[2*j:2*j+2] for j,k in enumerate(("attempts","held","released","received","lost","cancelled"))}
        finishes=re.findall(r"\[tribun-finish\] mode=(finish|off) decisions=(\d+),(\d+) aims=(\d+),(\d+) priorities=(\d+),(\d+) contacts=(\d+),(\d+)",log_text)
        if len(finishes)!=1 or finishes[0][0]!=("finish" if finish else "off"):
            raise ValueError("Missing finish evidence")
        values=list(map(int,finishes[0][1:]))
        report["finishProbe"]={k:values[2*j:2*j+2] for j,k in enumerate(("decisions","aims","priorities","contacts"))}
        keepers=re.findall(r"\[tribun-keeper\] mode=(keeper|off) narrows=(\d+),(\d+) intercepts=(\d+),(\d+) touches=(\d+),(\d+) controls=(\d+),(\d+) closed=(\d+),(\d+)",log_text)
        if len(keepers)!=1 or keepers[0][0]!=("keeper" if keeper_ai else "off"):
            raise ValueError("Missing keeper AI evidence")
        values=list(map(int,keepers[0][1:]))
        report["keeperProbe"]={k:values[2*j:2*j+2] for j,k in enumerate(("narrows","intercepts","touches","controls","closed"))}
        shape=re.findall(r"\[tribun-defense\] mode=(shape|off) targets=(\d+),(\d+) suppressed=(\d+),(\d+) samples=(\d+),(\d+) exposed=(\d+),(\d+)",log_text)
        if len(shape)!=1 or shape[0][0]!=("shape" if defense_shape else "off"):
            raise ValueError("Missing defense shape evidence")
        values=list(map(int,shape[0][1:]))
        report["defenseProbe"]={k:values[2*j:2*j+2] for j,k in enumerate(("targets","suppressed","samples","exposed"))}
    if collision_pose:
        import re
        matches=re.findall(r"\[tribun-contact\] interval-ms=(\d+) updates=(\d+) max-age-ticks=(\d+) missing=(\d+) ball-overlaps=(\d+) keeper-overlaps=(\d+) tackle-overlaps=(\d+) controlled-requests=(\d+)",log_text)
        if len(matches)!=1:raise ValueError("Missing contact evidence")
        keys=("intervalMs","poseUpdates","maxAgeTicks","missingPoseChecks","ballOverlaps","keeperOverlaps","tackleOverlaps","controlledRequests")
        contact=dict(zip(keys,map(int,matches[0])))
        if contact["intervalMs"]!=contact_interval_ms or contact["poseUpdates"]<=0:
            raise ValueError("Invalid collision cadence evidence")
        report["contactProbe"]=contact
        evidence=re.findall(r"\[tribun-adaptive\] mode=(uniform|adaptive) player-updates=(\d+) high=(\d+) medium=(\d+) low=(\d+) queries=(\d+) missing=(\d+) stale=(\d+) max-age=(\d+)",log_text)
        if len(evidence)!=1 or evidence[0][0]!=("adaptive" if adaptive_contact else "uniform"):
            raise ValueError("Missing adaptive contact evidence")
        keys=("playerUpdates","highUpdates","mediumUpdates","lowUpdates","queries","missingQueries","staleQueries","maxQueryAgeTicks")
        report["adaptiveContactProbe"]=dict(zip(keys,map(int,evidence[0][1:])))
        impacts=re.findall(r"\[tribun-impact\] mode=(surface|legacy) legacy=(\d+) surface=(\d+) rejected=(\d+) regions=(\d+,\d+,\d+,\d+,\d+,\d+) before=(\d+\.\d+) after=(\d+\.\d+) energy-violations=(\d+)",log_text)
        if len(impacts)!=1 or impacts[0][0]!=("surface" if surface_impact else "legacy"):
            raise ValueError("Missing surface impact evidence")
        _,legacy,surface,rejected,regions,before,after,violations=impacts[0]
        report["impactProbe"]={"legacy":int(legacy),"surface":int(surface),"rejected":int(rejected),
            "regions":list(map(int,regions.split(","))),"relativeSpeedBeforeSum":float(before),
            "relativeSpeedAfterSum":float(after),"energyViolations":int(violations)}
        angular=re.findall(r"\[tribun-angular\] mode=(angular|off) impacts=(\d+) changes=(\d+) before=(\d+\.\d+) after=(\d+\.\d+) max-delta=(\d+\.\d+) violations=(\d+)",log_text)
        if len(angular)!=1 or angular[0][0]!=("angular" if angular_impact else "off"):
            raise ValueError("Missing angular impact evidence")
        _,count,changes,before,after,delta,violations=angular[0]
        report["angularProbe"]={"impacts":int(count),"spinChanges":int(changes),
            "energyBeforePerMassSum":float(before),"energyAfterPerMassSum":float(after),
            "maxSpinDeltaRadPerSec":float(delta),"energyViolations":int(violations)}
        swept=re.findall(r"\[tribun-sweep\] mode=(swept|off) tests=(\d+) hits=(\d+) applied=(\d+) through=(\d+) max-lead-ms=(\d+\.\d+)",log_text)
        if len(swept)!=1 or swept[0][0]!=("swept" if swept_impact else "off"):
            raise ValueError("Missing swept contact evidence")
        _,tests,hits,applied,through,lead=swept[0]
        report["sweptProbe"]={"tests":int(tests),"hits":int(hits),"applied":int(applied),
                             "through":int(through),"maxLeadMs":float(lead)}
        split=re.findall(r"\[tribun-split\] mode=(split|off) queued=(\d+) applied=(\d+) cancelled=(\d+) before-ms=(\d+\.\d+) after-ms=(\d+\.\d+)",log_text)
        if len(split)!=1 or split[0][0]!=("split" if split_impact else "off"):
            raise ValueError("Missing split impact evidence")
        _,queued,applied,cancelled,before,after=split[0]
        report["splitProbe"]={"queued":int(queued),"applied":int(applied),"cancelled":int(cancelled),
                              "beforeMs":float(before),"afterMs":float(after)}
        chain=re.findall(r"\[tribun-chain\] mode=(chain|off) ticks=(\d+) extra=(\d+) rejected=(\d+) cap=(\d+) max=(\d+) last-ms=(\d+\.\d+)",log_text)
        if len(chain)!=1 or chain[0][0]!=("chain" if chain_impact else "off"):
            raise ValueError("Missing chain impact evidence")
        _,ticks,extra,rejected,cap,maximum,last=chain[0]
        report["chainProbe"]={"ticks":int(ticks),"extra":int(extra),"rejected":int(rejected),
            "cap":int(cap),"maxContacts":int(maximum),"lastMs":float(last)}
        limb=re.findall(r"\[tribun-limb\] mode=(limb|off) samples=(\d+) queries=(\d+) used=(\d+) fallback=(\d+) max-relative=(\d+\.\d+)",log_text)
        if len(limb)!=1 or limb[0][0]!=("limb" if limb_impact else "off"):
            raise ValueError("Missing limb velocity evidence")
        _,samples,queries,used,fallback,maximum=limb[0]
        report["limbProbe"]={"samples":int(samples),"queries":int(queries),"used":int(used),
            "fallback":int(fallback),"maxRelativeMps":float(maximum)}
    if collision_pose and "[tribun-skinning] runtime=" in log_text:
        raise ValueError("Unexpected runtime skinning in collision-only mode")
    if null_renderer and not collision_pose:
        skinning_marker="[tribun-skinning] runtime="+("position-only" if position_skinning else "full")+" bind-pose=full"
        if skinning_marker not in Path(str(trace)+".log").read_text(errors="replace"):
            raise ValueError("Missing runtime skinning evidence")
    report["requestedTaskWorkers"]=task_workers
    if null_renderer:
        import re
        markers=re.findall(r"\[tribun-workers\] hardware=(\d+) pool=(\d+)",Path(str(trace)+".log").read_text(errors="replace"))
        if len(markers)!=1:raise ValueError("Missing or ambiguous task worker marker")
        hardware,pool=map(int,markers[0])
        expected=max(3,hardware)
        if task_workers:expected=min(expected,task_workers)
        if pool!=expected:raise ValueError("Unexpected native worker pool size")
        report["hardwareThreads"]=hardware
        report["taskWorkerPool"]=pool
    report["visualRng"]=visual_rng
    report["skipPitchTexture"]=skip_pitch
    report["leanScene"]=lean_scene
    report["launchToKickoffMs"]=round((stats.first_wall-launch)*1000)
    report["sharedAssets"]=shared_assets
    if shared_assets:
        if not layout.is_file():raise ValueError("Missing shared asset layout evidence")
        report["layout"]=json.loads(layout.read_text())
    if sample_pss:
        if not pss_samples:raise ValueError("No native PSS samples collected")
        report["nativeMemory"]={"sampleCount":len(pss_samples),
            "peakPssKiB":max(x["Pss"] for x in pss_samples),
            "peakNativeThreads":max(x["Threads"] for x in pss_samples),
            "peakPrivateDirtyKiB":max(x["Private_Dirty"] for x in pss_samples),
            "samples":pss_samples}
    report.update(processWallMs=round((time.monotonic()-launch)*1000),
                  firstObservedMonotonic=stats.first_wall,finalObservedMonotonic=stats.final_wall,
                  traceBytes=trace.stat().st_size,resources=None)
    if resources.exists():
        import math
        r=json.loads(resources.read_text())
        if set(r)!={"userSeconds","systemSeconds","maxRssKiB","elapsedSeconds"} or any(type(v) not in (int,float) or not math.isfinite(v) or v<0 for v in r.values()):
            raise ValueError("Invalid process resource measurement")
        report["resources"]=r
    attack=json.loads(Path(str(trace)+".attack.json").read_text())
    if attack["engine"]!="league-soccer" or not attack.get("sampled"):raise ValueError("Missing attack report")
    report.update(profile=name,attackProfile=attack_profile,softwareRenderThreads=render_threads,configuredRenderIntervalMs=render_interval_ms,noDraw=no_draw,noUpload=no_upload,nullRenderer=null_renderer,retention=retention,boxRuns=box_runs,timedAttack=timed_attack,scale=float(scale),quickRestarts=quick=="1",
                  score=attack["score"],shots=attack["shots"],onTarget=attack["onTarget"],
                  controlledBoxCrossings=attack["sampled"]["controlledBoxCrossings"])
    Path(str(trace)+".timing.json").write_text(json.dumps(report,indent=2)+"\n")
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument("runtime")
    p.add_argument("fixture")
    p.add_argument("out")
    args=p.parse_args()
    results=[]
    for profile in PROFILES:
        results.append(run(args.runtime,args.fixture,args.out,profile))
        Path(args.out+".timing.json").write_text(json.dumps({"schema":1,"authoritative":False,
             "targetMs":300000,"profiles":results,"note":"Single fixture per profile; no rollout or guaranteed duration."},indent=2)+"\n")
        print(json.dumps(results[-1]),flush=True)

if __name__=="__main__":main()
