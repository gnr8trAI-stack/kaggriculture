#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,gzip,io,json,math,statistics,zipfile
from collections import Counter,defaultdict
from pathlib import Path
from typing import Any,Dict,Iterator,List,Mapping,Optional,Sequence,Tuple
CHECKPOINT_DAYS=(0,5,8,10,12,15,20,25,29)
CROPS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON")
ANIMALS=("CHICKEN","GOOSE","COW","SHEEP")
PRODUCTS=("WHEAT","CARROT","TOMATO","STRAWBERRY","MELON","EGG","MILK","WOOL","FERTILIZER")
def m(v): return v if isinstance(v,Mapping) else {}
def fnum(v,d=0.0):
    try:return d if v is None else float(v)
    except:return d
def inum(v,d=0):
    try:return d if v is None else int(v)
    except:return d
def is_episode(v): return isinstance(v,Mapping) and isinstance(v.get('steps'),list) and len(v['steps'])>0
def walk_json(v):
    if is_episode(v): yield v; return
    if isinstance(v,Mapping):
        for c in v.values(): yield from walk_json(c)
    elif isinstance(v,list):
        for c in v: yield from walk_json(c)
def parse_json_bytes(data):
    try:v=json.loads(data.decode('utf-8-sig'))
    except:return
    yield from walk_json(v)
def iter_zip_bytes(data,depth=0):
    if depth>2:return
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                if name.endswith('/'): continue
                try:p=z.read(name)
                except:continue
                low=name.lower()
                if low.endswith('.zip'): yield from iter_zip_bytes(p,depth+1)
                elif low.endswith('.gz'):
                    try: yield from parse_json_bytes(gzip.decompress(p))
                    except: pass
                elif low.endswith('.json'):
                    yield from parse_json_bytes(p)
                elif low.endswith('.jsonl'):
                    for line in p.splitlines():
                        if line.strip(): yield from parse_json_bytes(line)
    except:return
def iter_episodes(root):
    paths=[root] if root.is_file() else sorted(p for p in root.rglob('*') if p.is_file())
    for path in paths:
        low=path.name.lower()
        try:data=path.read_bytes()
        except:continue
        if low.endswith('.zip'): yield from iter_zip_bytes(data)
        elif low.endswith('.gz'):
            try:yield from parse_json_bytes(gzip.decompress(data))
            except:pass
        elif low.endswith('.json'): yield from parse_json_bytes(data)
        elif low.endswith('.jsonl'):
            for line in data.splitlines():
                if line.strip(): yield from parse_json_bytes(line)
def agent_node(step,seat):
    if isinstance(step,list) and seat<len(step): return m(step[seat])
    if isinstance(step,Mapping):
        agents=step.get('agents')
        if isinstance(agents,list) and seat<len(agents): return m(agents[seat])
        if str(seat) in step:return m(step[str(seat)])
    return {}
def observation(node):
    o=node.get('observation',node.get('obs',{}))
    if isinstance(o,str):
        try:o=json.loads(o)
        except:o={}
    return m(o)
def action(node): return node.get('action',node.get('lastAction',node.get('last_action')))
def reward(node):
    try:return None if node.get('reward') is None else float(node.get('reward'))
    except:return None
def final_rewards(ep):
    steps=ep.get('steps') or []
    if not steps:return None,None
    vals=[]
    for seat in (0,1):
        n=agent_node(steps[-1],seat); r=reward(n)
        if r is None:
            o=observation(n); farms=o.get('farms') or []
            if isinstance(farms,list) and seat<len(farms):r=fnum(m(farms[seat]).get('money'))
        vals.append(r)
    return vals[0],vals[1]
def kind(tile):
    if tile is None:return 'EMPTY'
    if tile=='LOCKED':return 'LOCKED'
    if isinstance(tile,Mapping):return str(tile.get('kind',tile.get('type','UNKNOWN'))).upper()
    return str(tile).upper()
def state_features(obs,seat):
    farms=obs.get('farms') or []; farm=m(farms[seat]) if isinstance(farms,list) and seat<len(farms) else {}; opp=m(farms[1-seat]) if isinstance(farms,list) and len(farms)>1 else {}
    counts=Counter(); crops=Counter(); animals=Counter(); unlocked=occupied=0
    tiles=farm.get('tiles') or []
    if isinstance(tiles,list):
        for row in tiles:
            if not isinstance(row,list):continue
            for tile in row:
                k=kind(tile); counts[k]+=1
                if k!='LOCKED':unlocked+=1
                if tile is not None and k!='LOCKED':occupied+=1
                if isinstance(tile,Mapping):
                    if k=='PLANT':
                        c=str(tile.get('crop',tile.get('plant',''))).upper(); crops[c]+=1 if c else 0
                    if k in {'PASTURE','COOP'}:
                        a=str(tile.get('animal','')).upper(); animals[a]+=1 if a else 0
    market=m(obs.get('market')); prices=m(market.get('prices')); inv=m(market.get('inventory'))
    out={'day':inum(obs.get('day')),'hour':inum(obs.get('hour')),'step':inum(obs.get('step'),inum(obs.get('day'))*24+inum(obs.get('hour'))),'money':fnum(farm.get('money')),'opp_money':fnum(opp.get('money')),'money_lead':fnum(farm.get('money'))-fnum(opp.get('money')),'hands':len(farm.get('hands') or []),'hires_today':inum(farm.get('hires_today')),'land':len(farm.get('unlocked_quadrants') or ['NW']),'unlocked_tiles':unlocked,'occupied_tiles':occupied,'occupancy':occupied/max(1,unlocked),'plants':counts['PLANT'],'pastures':counts['PASTURE'],'coops':counts['COOP'],'weeds':counts['WEED'],'animals':sum(animals.values())}
    for c in CROPS:out['crop_'+c.lower()]=crops[c]
    for a in ANIMALS:out['animal_'+a.lower()]=animals[a]
    for p in PRODUCTS:out['price_'+p.lower()]=fnum(prices.get(p));out['market_'+p.lower()]=inum(inv.get(p))
    return out
def normalize_action(a):
    if isinstance(a,str):
        try:a=json.loads(a)
        except:return {'raw_action':a,'farmer_op':'','market_ops':'','market_action_count':0}
    if not isinstance(a,Mapping):return {'raw_action':json.dumps(a,default=str),'farmer_op':'','market_ops':'','market_action_count':0}
    farmer=a.get('farmer') or []; fop=str(farmer[0]).upper() if isinstance(farmer,list) and farmer else ''
    market=a.get('market') or []; ops=[]
    if isinstance(market,list):
        for order in market:
            if isinstance(order,list) and order:ops.append(str(order[0]).upper())
    return {'raw_action':json.dumps(a,separators=(',',':'),default=str),'farmer_op':fop,'market_ops':'|'.join(ops),'market_action_count':len(ops)}
def percentile(xs,q):
    vals=sorted(float(x) for x in xs)
    if not vals:return 0.0
    if len(vals)==1:return vals[0]
    pos=(len(vals)-1)*q;lo=math.floor(pos);hi=math.ceil(pos)
    if lo==hi:return vals[lo]
    w=pos-lo;return vals[lo]*(1-w)+vals[hi]*w
def write_csv(path,rows):
    if not rows:path.write_text('',encoding='utf-8');return
    fields=sorted({k for r in rows for k in r})
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--input',required=True,type=Path);ap.add_argument('--output',type=Path,default=Path('research/v31/artifacts'));ap.add_argument('--elite-quantile',type=float,default=.90);ap.add_argument('--max-episodes',type=int,default=0);args=ap.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    episodes=[]
    for i,ep in enumerate(iter_episodes(args.input)):
        episodes.append(ep)
        if args.max_episodes and i+1>=args.max_episodes:break
    meta=[]
    for ei,ep in enumerate(episodes):
        r0,r1=final_rewards(ep)
        for seat,own,opp in ((0,r0,r1),(1,r1,r0)):
            if own is not None:meta.append({'episode_index':ei,'seat':seat,'reward':own,'opponent_reward':opp or 0.0,'win':bool(opp is not None and own>opp)})
    winners=[r['reward'] for r in meta if r['win']];threshold=percentile(winners,args.elite_quantile) if winners else 0.0
    elite={(r['episode_index'],r['seat']) for r in meta if r['win'] and r['reward']>=threshold}
    rows=[]
    for ei,seat in sorted(elite):
        ep=episodes[ei];steps=ep.get('steps') or [];terminal=next((r['reward'] for r in meta if r['episode_index']==ei and r['seat']==seat),0.0)
        for si,step in enumerate(steps[:-1]):
            n=agent_node(step,seat);obs=observation(n)
            if not obs:continue
            nxtobs=observation(agent_node(steps[si+1],seat));feat=state_features(obs,seat);nxt=state_features(nxtobs,seat) if nxtobs else {};act=normalize_action(action(n))
            rows.append({'episode_index':ei,'seat':seat,'terminal_reward':terminal,'terminal_uplift':terminal-feat['money'],'next_money':nxt.get('money',feat['money']),'next_money_delta':nxt.get('money',feat['money'])-feat['money'],**feat,**act})
    checkpoints=[]
    for day in CHECKPOINT_DAYS:
        first={}
        for r in sorted((x for x in rows if x['day']==day),key=lambda x:x['hour']):first.setdefault((r['episode_index'],r['seat']),r)
        vals=list(first.values())
        if not vals:continue
        cp={'day':day,'trajectories':len(vals)}
        for field in ('money','hands','land','plants','animals','pastures','coops','occupancy'):
            xs=[fnum(v.get(field)) for v in vals]
            for q,name in ((.5,'p50'),(.75,'p75'),(.9,'p90')):cp[f'{field}_{name}']=percentile(xs,q)
        checkpoints.append(cp)
    grouped=defaultdict(list)
    for r in rows:
        phase='early' if r['day']<8 else 'mid' if r['day']<20 else 'late';grouped[(phase,r['farmer_op'],r['market_ops'],r['land'],min(r['hands'],12))].append(r)
    av=[]
    for sig,rs in grouped.items():
        if len(rs)<3:continue
        av.append({'phase':sig[0],'farmer_op':sig[1],'market_ops':sig[2],'land':sig[3],'hands':sig[4],'samples':len(rs),'mean_terminal_reward':statistics.mean(r['terminal_reward'] for r in rs),'mean_terminal_uplift':statistics.mean(r['terminal_uplift'] for r in rs),'mean_next_money_delta':statistics.mean(r['next_money_delta'] for r in rs)})
    av.sort(key=lambda r:(r['phase'],-r['mean_terminal_reward'],-r['samples']))
    write_csv(args.output/'elite_transitions.csv',rows);write_csv(args.output/'elite_checkpoints.csv',checkpoints);write_csv(args.output/'elite_action_value.csv',av)
    summary={'episodes_scanned':len(episodes),'trajectory_count':len(meta),'winner_count':len(winners),'elite_quantile':args.elite_quantile,'elite_reward_threshold':threshold,'elite_trajectories':len(elite),'elite_transition_rows':len(rows),'max_winner_reward':max(winners) if winners else None,'winner_reward_p50':percentile(winners,.5) if winners else None,'winner_reward_p90':percentile(winners,.9) if winners else None,'winner_reward_p99':percentile(winners,.99) if winners else None}
    (args.output/'elite_summary.json').write_text(json.dumps(summary,indent=2,sort_keys=True),encoding='utf-8');print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__':main()
