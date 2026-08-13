from __future__ import annotations
import json
from collections import Counter
from pathlib import Path
from kaggle_environments import make
from agents import v33_industrial_v76 as a

rows=[]
for seed in (399000,399001):
    for seat in (0,1):
        a.reset_state()
        env=make('kaggriculture',configuration={'seed':seed},debug=False)
        env.run([a.agent,'starter'] if seat==0 else ['starter',a.agent])
        state=env.state[seat]
        tel=a.get_telemetry()
        snaps={}
        market=Counter(); labels=Counter(); animal_orders=Counter()
        for r in tel:
            d=int(r.get('day',-1) or -1)
            snaps[d]={
                'money':float(r.get('money',0) or 0),
                'lands':int(r.get('lands',0) or 0),
                'hands':int(r.get('hands',0) or 0),
                'animals':int(r.get('animals',0) or 0),
                'productive':int(r.get('productive',0) or 0),
                'idle':int(r.get('idle',0) or 0),
                'q1_prod':int((r.get('q1') or {}).get('productive',0) or 0),
                'q2_prod':int((r.get('q2') or {}).get('productive',0) or 0),
                'q3_prod':int((r.get('q3') or {}).get('productive',0) or 0),
                'q1_pasture':int((r.get('q1') or {}).get('pasture',0) or 0),
                'q2_pasture':int((r.get('q2') or {}).get('pasture',0) or 0),
                'q3_pasture':int((r.get('q3') or {}).get('pasture',0) or 0),
            }
            for label in r.get('unit_actions',[]): labels[str(label)]+=1
            for order in r.get('market_actions',[]):
                if isinstance(order,list) and order:
                    key=str(order[0]).upper() + ((':'+str(order[1]).upper()) if len(order)>1 else '')
                    market[key]+=int(order[2]) if len(order)>2 and isinstance(order[2],(int,float)) else 1
            for order in (r.get('allocator') or {}).get('v76_animal_orders',[]):
                if isinstance(order,list) and len(order)>=3: animal_orders[str(order[1]).upper()]+=int(order[2])
        rows.append({
            'seed':seed,'seat':seat,'status':str(state.status),'reward':float(state.reward or 0),
            'snapshots':{str(d):snaps.get(d,{}) for d in (0,4,7,8,10,12,15,20,25,29)},
            'market':dict(market),'labels':dict(labels),'animal_orders':dict(animal_orders)
        })
Path('benchmarks/v33_v76_diagnostic.json').write_text(json.dumps(rows,indent=2))
print(json.dumps(rows,indent=2))
