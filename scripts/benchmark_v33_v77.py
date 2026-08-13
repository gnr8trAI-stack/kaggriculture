from __future__ import annotations
import json, statistics, subprocess, sys
from pathlib import Path

CHILD = '''import importlib,json,sys\nfrom kaggle_environments import make\na=importlib.import_module("agents.v33_industrial_v77")\na.reset_state()\nseed=int(sys.argv[1]);seat=int(sys.argv[2])\ne=make("kaggriculture",configuration={"seed":seed},debug=False)\ne.run([a.agent,"starter"] if seat==0 else ["starter",a.agent])\ns=e.state[seat];t=a.get_telemetry()\np={k:max([int(x.get(k,0) or 0) for x in t] or [0]) for k in ("lands","hands","animals","productive","idle")}\nprint("R="+json.dumps({"status":str(s.status),"reward":float(s.reward or 0),"peaks":p}))'''

rows=[]
for seed in range(397000,397012):
    for seat in (0,1):
        try:
            p=subprocess.run([sys.executable,'-c',CHILD,str(seed),str(seat)],capture_output=True,text=True,timeout=170)
        except subprocess.TimeoutExpired:
            rows.append({'status':'TIMEOUT','reward':0.0,'peaks':{}}); continue
        line=next((x for x in p.stdout.splitlines() if x.startswith('R=')),None)
        rows.append(json.loads(line[2:]) if p.returncode==0 and line else {'status':'ERROR','reward':0.0,'peaks':{}})
r=[x['reward'] for x in rows]; z=sorted(r)
out={'version':'33.77.0-replay-timed-land','games':len(rows),'invalid':sum(x['status']!='DONE' for x in rows),'mean':statistics.mean(r),'median':statistics.median(r),'min':min(r),'p10':z[2],'p25':z[5],'p75':z[18],'p90':z[-3],'max':max(r)}
for k in ('lands','hands','animals','productive','idle'):
    out['median_peak_'+k]=statistics.median(float(x.get('peaks',{}).get(k,0) or 0) for x in rows)
out['three_land_games']=sum(int(x.get('peaks',{}).get('lands',0) or 0)>=3 for x in rows)
out['four_land_games']=sum(int(x.get('peaks',{}).get('lands',0) or 0)>=4 for x in rows)
out['ready_150k']=out['invalid']==0 and out['games']>=24 and out['median']>=150000 and out['min']>=100000
Path('benchmarks/v33_v77_latest.json').write_text(json.dumps(out,indent=2))
print(json.dumps(out,indent=2))
