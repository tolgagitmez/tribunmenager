"""Inspect complete encoded HLS packet timelines, never infer renderer FPS or event-level sync."""
import json,math,subprocess
from pathlib import Path
def require(ok,message):
    if not ok:raise ValueError(message)
def finite(v):
    n=float(v)
    require(math.isfinite(n),"Nonfinite timestamp")
    return n
def timeline(packets):
    require(isinstance(packets,list) and 0<len(packets)<=100000,"Missing or excessive packets")
    spans=[];last_dts=None;regressions=0
    for p in packets:
        pts=finite(p["pts_time"]);dts=finite(p["dts_time"]);duration=finite(p["duration_time"])
        require(0<duration<=1 and abs(pts)<=1200 and abs(dts)<=1200,"Invalid packet timing")
        if last_dts is not None and dts<last_dts-1e-6:regressions+=1
        last_dts=dts;spans.append((pts,pts+duration))
    spans.sort()
    start,end=spans[0];gap=0.;gap_count=0;covered=end-start
    for a,b in spans[1:]:
        missing=max(0.,a-end)
        if missing>.12:gap_count+=1
        gap=max(gap,missing)
        covered+=max(0.,b-max(a,end))
        end=max(end,b)
    return {"packets":len(spans),"startSeconds":start,"endSeconds":end,
       "spanSeconds":end-start,"coveredSeconds":covered,"maxGapSeconds":gap,
       "gapsOver120ms":gap_count,"dtsRegressions":regressions}
def analyze(data,audio_requested,expected_seconds):
    require(type(expected_seconds) in (float,int) and math.isfinite(expected_seconds) and 0<expected_seconds<=900,"Missing expected capture duration")
    streams=data["streams"];packets=data["packets"]
    require(len(streams)==(2 if audio_requested else 1),"Unexpected stream count")
    by_kind={s["codec_type"]:s for s in streams}
    require(set(by_kind)==({"video","audio"} if audio_requested else {"video"}),"Unexpected media streams")
    require(len({s["index"] for s in streams})==len(streams),"Duplicate stream index")
    v=by_kind["video"]
    require(v["codec_name"]=="h264" and 64<=v["width"]<=1280 and 64<=v["height"]<=720,"Unexpected video format")
    if audio_requested:
        a=by_kind["audio"]
        require(a["codec_name"]=="aac" and a.get("profile")=="LC" and int(a["sample_rate"])==48000 and a["channels"]==2,"Unexpected audio format")
    rows={s["index"]:[] for s in streams}
    for p in packets:
        require(p["stream_index"] in rows,"Unexpected packet stream")
        rows[p["stream_index"]].append(p)
    tracks={kind:timeline(rows[s["index"]]) for kind,s in by_kind.items()}
    checks={kind:row["dtsRegressions"]==0 and row["maxGapSeconds"]<=.5 and row["coveredSeconds"]>=expected_seconds-1 for kind,row in tracks.items()}
    skew=None
    if audio_requested:
        a,b=tracks["audio"],tracks["video"]
        skew={"startDifferenceSeconds":abs(a["startSeconds"]-b["startSeconds"]),
              "endDifferenceSeconds":abs(a["endSeconds"]-b["endSeconds"])}
        checks["avEnvelope"]=max(skew.values())<=2
    return {"timelinePassed":all(checks.values()),"checks":checks,"tracks":tracks,"avEnvelope":skew,
        "note":"Encoded packet timing and coverage only; not unique rendered FPS, end-to-end latency or perceptual sound synchronization."}
def audit_media(playlist,audio_requested,expected_seconds):
    playlist=Path(playlist).resolve()
    data=json.loads(subprocess.check_output(["ffprobe","-v","error","-protocol_whitelist","file,crypto,data","-allowed_extensions","ALL",
      "-show_streams","-show_packets","-show_entries","stream=index,codec_name,codec_type,width,height,profile,sample_rate,channels:packet=stream_index,pts_time,dts_time,duration_time",
      "-of","json",str(playlist)],timeout=90))
    return analyze(data,audio_requested,expected_seconds)
