from __future__ import annotations
import json, statistics, subprocess, sys
from pathlib import Path

CHILD = r'''
import importlib,json,os,sys
from kaggle_environments import make
root,mod,seed,seat=sys.argv[1],sys.argv[2],int(sys.argv[3]),int(sys.argv[4])
sys.path.insert(0,root);os.chdir(root)
a=importlib.import_module(mod)
if hasattr(a,'reset_state'): a.reset_state()
env=make('kaggriculture',configuration={'seed':seed},debug=False)
env.run([a.agent,'starter'] if seat==0 else ['starter',a.agent])
st=env.state[seat]
peak_straw=peak_prod=peak_cows=0
for step in getattr(env,'steps',[]) or []:
    try:
        obs=step[seat].observation
        if not isinstance(obs,dict): continue
        p=int(obs.get('player',seat) or seat); farms=obs.get('farms') or []
        if p>=len(farms): continue
        farm=farms[p]; prod=straw=cows=0
        for row in farm.get('tiles') or []:
            if not isinstance(row,list): continue
            for t in row:
                if not isinstance(t,dict): continue
                kind=str(t.get('kind','')).upper()
                if kind in ('PLANT','COOP','PASTURE'): prod+=1
                if kind=='PLANT' and str(t.get('crop',t.get('plant',''))).upper()=='STRAWBERRY': straw+=1
                if kind=='PASTURE' and str(t.get('animal','')).upper()=='COW': cows+=1
        peak_prod=max(peak_prod,prod); peak_straw=max(peak_straw,straw); peak_cows=max(peak_cows,cows)
    except Exception: pass
print('RESULTJSON='+json.dumps({'status':str(st.status),'reward':float(st.reward or 0),'peak_strawberries':peak_straw,'peak_productive':peak_prod,'peak_active_cows':peak_cows,'seed_floor_triggers':int(a.seed_floor_trigger_count()) if hasattr(a,'seed_floor_trigger_count') else 0},separators=(',',':')))
'''

def one(root,mod,seed,seat):
    try:
        p=subprocess.run([sys.executable,'-c',CHILD,root,mod,str(seed),str(seat)],text=True,capture_output=True,timeout=150)
    except subprocess.TimeoutExpired:
        return {'status':'TIMEOUT','reward':0.0}
    line=next((x for x in reversed(p.stdout.splitlines()) if x.startswith('RESULTJSON=')),None)
    if p.returncode or not line:
        return {'status':'ERROR','reward':0.0,'stderr':(p.stderr+p.stdout)[-1200:]}
    return json.loads(line.split('=',1)[1])

def summary(rows,key):
    rs=[x[key] for x in rows]; vals=[float(r.get('reward',0) or 0) for r in rs]; s=sorted(vals)
    out={'games':len(rs),'invalid':sum(str(r.get('status')) in ('ERROR','INVALID','TIMEOUT') for r in rs),'mean':statistics.mean(vals),'median':statistics.median(vals),'min':min(vals),'p10':s[2],'p25':s[5],'p75':s[-6],'p90':s[-3],'max':max(vals)}
    if key=='candidate':
        out.update({'triggered_games':sum(int(r.get('seed_floor_triggers',0) or 0)>0 for r in rs),'median_seed_floor_triggers':statistics.median(int(r.get('seed_floor_triggers',0) or 0) for r in rs),'median_peak_strawberries':statistics.median(float(r.get('peak_strawberries',0) or 0) for r in rs),'median_peak_productive':statistics.median(float(r.get('peak_productive',0) or 0) for r in rs),'median_peak_active_cows':statistics.median(float(r.get('peak_active_cows',0) or 0) for r in rs)})
    return out

rows=[]
for seed in range(345100,345112):
    for seat in (0,1):
        c=one('candidate','agents.v34_33_strawberry_seed_floor',seed,seat)
        p=one('candidate','agents.v34_26_terminal_liquidation',seed,seat)
        b=one('control','agents.v19_2_early_scale8',seed,seat)
        rows.append({'seed':seed,'seat':seat,'candidate':c,'parent_v34_26':p,'control_v19_2':b,'delta_parent':c['reward']-p['reward'],'delta_control':c['reward']-b['reward']})
c=summary(rows,'candidate');p=summary(rows,'parent_v34_26');b=summary(rows,'control_v19_2')
dp=[r['delta_parent'] for r in rows];db=[r['delta_control'] for r in rows]
report={'version':'34.33.0-strawberry-seed-floor','mechanism':'V34.26 + six-seed strawberry floor only while specialization eligible and active strawberries <30','candidate':c,'parent_v34_26':p,'control_v19_2':b,'paired_parent':{'wins':sum(x>0 for x in dp),'losses':sum(x<0 for x in dp),'ties':sum(x==0 for x in dp),'median_delta':statistics.median(dp)},'paired_control':{'wins':sum(x>0 for x in db),'losses':sum(x<0 for x in db),'ties':sum(x==0 for x in db),'median_delta':statistics.median(db)},'ready_150k':c['invalid']==0 and c['games']>=24 and c['median']>=150000 and c['min']>=100000,'games_detail':rows}
out=Path('candidate/benchmarks/v34_v33_latest.json');out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(report,indent=2))
print(json.dumps({k:v for k,v in report.items() if k!='games_detail'},indent=2))
