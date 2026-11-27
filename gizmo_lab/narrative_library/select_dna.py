"""Reference selector: no model calls, no stories, no user data. Python 3.12 stdlib."""
import json, random, collections, pathlib
ROOT = pathlib.Path(__file__).resolve().parent

def load_library(path=ROOT/'narrative_library.json'):
    data=json.loads(path.read_text(encoding='utf-8'))
    ids=[item['id'] for axis in data['axes'].values() for item in axis]
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate IDs')
    for axis, items in data['axes'].items():
        if not items or any(not i['id'].startswith(axis+'.') or i['weight']<=0 or not i['guidance'] for i in items):
            raise ValueError('Invalid axis: '+axis)
    for rule in data['selection']['constraints']:
        for a, values in rule.get('exclude',{}).items():
            if not set(values)<= {i['id'] for i in data['axes'][a]}: raise ValueError('Unknown constraint ID')
        for a, value in rule.get('if',{}).items():
            if value not in {i['id'] for i in data['axes'][a]}: raise ValueError('Unknown condition ID')
    return data

def select(data, seed, history=(), profile='short'):
    if profile not in ('micro','short'): raise ValueError('Unsupported prototype profile')
    r=random.Random(seed); cfg=data['selection']; nov=cfg['novelty']; recent=list(history)[-nov['history_size']:]
    counts=collections.Counter(x for h in recent for x in h)
    def pick(axis, n=1, banned=()):
        pool=[i for i in data['axes'][axis] if i['id'] not in banned]; out=[]
        for _ in range(n):
            if not pool: raise ValueError('Empty candidate pool: '+axis)
            weights=[i['weight']*(max(nov['floor_multiplier'],nov['recency_multiplier']**counts[i['id']]) if axis in nov['penalize_axes'] else 1) for i in pool]
            item=r.choices(pool,weights=weights,k=1)[0];out.append(item);pool.remove(item)
        return out
    for _ in range(nov['max_selection_attempts']):
        chosen=pick('explanation'); explanation=chosen[0]['id']; bans={}
        for rule in cfg['constraints']:
            if rule.get('if')=={'explanation':explanation}:
                bans.update(rule.get('exclude',{}))
        for axis in cfg['initial_required_axes']:
            if axis!='explanation': chosen+=pick(axis,banned=bans.get(axis,()))
        for axis,n in cfg['initial_optional_axes'].items():
            if explanation=='explanation.no_mystery' and axis=='evidence': n=0
            if profile=='micro' and axis in ('character_function','evidence'): n=min(n,1)
            chosen+=pick(axis,n,bans.get(axis,()))
        signature=tuple(sorted(i['id'] for i in chosen))
        guidance='\n'.join(i['id']+': '+i['guidance'] for i in chosen)
        if len(chosen)>cfg['max_guidance_items'] or len(guidance)>cfg['max_guidance_chars']: continue
        if any(tuple(sorted(h))==signature for h in recent): continue
        return {'library_version':data['version'],'profile':profile,'ids':list(signature),'guidance':guidance}
    raise RuntimeError('No valid new selection within bounded attempts')

if __name__=='__main__':
    data=load_library(); history=[]; seen=collections.defaultdict(set)
    for seed in range(1000):
        result=select(data,seed,history,profile='micro' if seed%2 else 'short')
        ids=result['ids']; assert len(ids)==len(set(ids));assert tuple(ids) not in [tuple(h) for h in history[-8:]]
        for x in ids: seen[x.split('.')[0]].add(x)
        if 'explanation.no_mystery' in ids:
            assert not any(x.startswith('evidence.') for x in ids)
            assert not set(ids)&{'drive.reconstruct','drive.verify','entry.conflicting_accounts','entry.missing_context','reversal.context_shift','reversal.wrong_assumption','reversal.parallel_convergence','reversal.motive_reframe'}
        assert result==select(data,seed,history,profile=result['profile']);history.append(ids)
    print('PASS: 1000 deterministic selections; bounded guidance, exclusions, unique IDs and recent duplicate checks.')
    print('Selected entries by axis (no story output):', {k:len(v) for k,v in seen.items()})
