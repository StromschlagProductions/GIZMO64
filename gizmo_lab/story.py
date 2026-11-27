"""Isolated, persistent fictional worlds for GIZMO and future STORYFORGE hosts.

The director sees the concealed truth. The speaking model receives only a
validated public scene brief; neither the real archive nor personality lives
in this database.
"""
from __future__ import annotations

import json
import re
import secrets
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from narrative_library.select_dna import load_library, select


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def clean(value, limit):
    if not isinstance(value, str):
        raise ValueError('Director returned a non-text field')
    value = value.strip()
    if not value or len(value) > limit:
        raise ValueError('Director returned an empty or oversized field')
    return value


def state_ids(value):
    """IDs and keys of nested public objects, never secret canon values."""
    found=set()
    def visit(node):
        if isinstance(node,dict):
            for key,item in node.items():
                found.add(str(key))
                if key=='id' and isinstance(item,(str,int)):
                    found.add(str(item))
                visit(item)
        elif isinstance(node,list):
            for item in node:visit(item)
    visit(value)
    return found


def merge_patch(state, patch):
    """Apply a small JSON merge patch; the stored state remains authoritative."""
    if not isinstance(state, dict) or not isinstance(patch, dict):
        raise ValueError('Invalid public state patch')
    result = dict(state)
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        elif isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge_patch(result[key], value)
        else:
            result[key] = value
    return result


class StoryDirector:
    """Story storage and director decisions, independent of LAB's Memory."""

    def __init__(self, path, request, model, library_dir=None, stopping=None, response_opened=None):
        self.path = Path(path)
        self.request = request
        self.model = model
        self.stopping = stopping or (lambda: False)
        self.response_opened = response_opened or (lambda response: None)
        library_dir = Path(library_dir or Path(__file__).resolve().parent/'narrative_library')
        self.library = load_library(library_dir/'narrative_library.json')
        self.policy = json.loads((library_dir/'origin_campaign_policy.json').read_text(encoding='utf-8'))
        self.director_prompt = (library_dir/'director_prompt_en.txt').read_text(encoding='utf-8')
        if not self.library['version'].startswith('1.1.') or not self.policy.get('enabled'):
            raise ValueError('Unsupported Narrative Library or campaign policy')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        existing=self.path.is_file() and self.path.stat().st_size>0
        self.db = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=10000')
        schema_version=self.db.execute('PRAGMA user_version').fetchone()[0]
        if schema_version>2:
            self.db.close()
            raise RuntimeError('Story database schema is newer than this program')
        if existing and schema_version<2 and self.db.execute("SELECT 1 FROM sqlite_master WHERE type='table' LIMIT 1").fetchone():
            backup=self.path.with_name(self.path.name+'.before-v2.bak')
            target=sqlite3.connect(backup)
            try:
                self.db.backup(target)
                if target.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
                    self.db.close()
                    raise RuntimeError('Story database backup failed integrity check')
            finally:
                target.close()
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS worlds (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, title TEXT NOT NULL,
                style TEXT NOT NULL, secret_json TEXT NOT NULL,
                public_state_json TEXT NOT NULL, turn INTEGER NOT NULL DEFAULT 0,
                seed INTEGER NOT NULL, library_version TEXT NOT NULL,
                dna_json TEXT NOT NULL, mode TEXT NOT NULL, profile TEXT NOT NULL,
                opening_scene TEXT NOT NULL, opening_reply TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, world_id TEXT NOT NULL, turn INTEGER NOT NULL,
                event_id TEXT NOT NULL UNIQUE,
                action TEXT NOT NULL, public_scene TEXT NOT NULL,
                consequence TEXT NOT NULL, reply TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(world_id) REFERENCES worlds(id),
                UNIQUE(world_id,turn)
            );
            CREATE INDEX IF NOT EXISTS events_world_turn ON events(world_id,turn);
            CREATE TABLE IF NOT EXISTS dialogue (
                id INTEGER PRIMARY KEY, world_id TEXT NOT NULL, turn INTEGER NOT NULL,
                prompt TEXT NOT NULL, reply TEXT NOT NULL, created_at TEXT NOT NULL,
                FOREIGN KEY(world_id) REFERENCES worlds(id)
            );
            CREATE INDEX IF NOT EXISTS dialogue_world_turn ON dialogue(world_id,turn,id);
            CREATE TABLE IF NOT EXISTS campaign (
                id TEXT PRIMARY KEY, schema_version INTEGER NOT NULL,
                library_version TEXT NOT NULL, seed INTEGER NOT NULL,
                secret_json TEXT NOT NULL, public_state_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
        ''')
        self.db.execute('PRAGMA user_version=2')
        self.last_metrics = {}

    def close(self):
        self.db.close()

    def status(self):
        row = self.db.execute("SELECT id,status,title,style,turn FROM worlds ORDER BY updated_at DESC,rowid DESC LIMIT 1").fetchone()
        if not row:
            return {'status': 'ready', 'turn': 0}
        return {'status': row['status'], 'turn': row['turn']}

    def world(self):
        return self.db.execute("SELECT * FROM worlds ORDER BY updated_at DESC,rowid DESC LIMIT 1").fetchone()

    def events(self, world_id, limit=4):
        rows = self.db.execute('SELECT action,consequence FROM events WHERE world_id=? ORDER BY turn DESC LIMIT ?', (world_id, limit)).fetchall()
        return [dict(row) for row in reversed(rows)]

    def dialogue_history(self,world_id,limit=4):
        row=self.db.execute('SELECT opening_reply FROM worlds WHERE id=?',(world_id,)).fetchone()
        history=[]
        if row and row['opening_reply']:
            history.extend(({'role':'user','content':'Begin the fictional adventure.'},
                            {'role':'assistant','content':row['opening_reply']}))
        rows=self.db.execute('SELECT turn,action,reply FROM events WHERE world_id=? ORDER BY turn DESC LIMIT ?',
                             (world_id,limit)).fetchall()
        first_turn=rows[-1]['turn']-1 if rows else 0
        talks=self.db.execute('SELECT turn,prompt,reply FROM dialogue WHERE world_id=? AND turn>=? ORDER BY id DESC LIMIT 8',
                              (world_id,first_turn)).fetchall()
        by_turn={}
        for item in reversed(talks):by_turn.setdefault(item['turn'],[]).append(item)
        for item in by_turn.get(first_turn,[]):
            history.extend(({'role':'user','content':item['prompt']},{'role':'assistant','content':item['reply']}))
        for event in reversed(rows):
            history.extend(({'role':'user','content':event['action']},
                            {'role':'assistant','content':event['reply']}))
            for item in by_turn.get(event['turn'],[]):
                history.extend(({'role':'user','content':item['prompt']},{'role':'assistant','content':item['reply']}))
        return history

    def public_brief(self):
        row=self.world()
        if not row or row['status']!='active':
            raise RuntimeError('No active fictional world')
        events=self.events(row['id'],limit=2)
        return {'world_id':row['id'],'turn':row['turn'],
                'opening':row['opening_scene'] if row['turn']==0 else None,
                'public_state':json.loads(row['public_state_json']),
                'recent_observations':events}

    def save_dialogue(self,world_id,turn,prompt,reply):
        if self.stopping():raise RuntimeError('Story Director is stopping')
        prompt=clean(prompt,1200);reply=clean(reply,5000)
        with self.db:
            row=self.db.execute('SELECT turn,status FROM worlds WHERE id=?',(world_id,)).fetchone()
            if not row or row['turn']!=turn or row['status']!='active':
                raise RuntimeError('Story state changed while dialogue was generated')
            self.db.execute('INSERT INTO dialogue(world_id,turn,prompt,reply,created_at) VALUES(?,?,?,?,?)',
                            (world_id,turn,prompt,reply,now()))

    def _generate(self, instructions, request, schema, max_tokens=650):
        if self.stopping():raise RuntimeError('Story Director is stopping')
        if len(instructions.encode('utf-8'))+len(request.encode('utf-8'))>20000:
            raise ValueError('Director context exceeds the safe local budget')
        payload = {'model': self.model(), 'stream': False, 'format': schema,
                   'keep_alive': -1, 'think': False,
                   'options': {'temperature': 0.55, 'num_predict': max_tokens, 'num_ctx': 6144},
                   'messages': [{'role': 'system', 'content': instructions},
                                {'role': 'user', 'content': request}]}
        started=time.perf_counter()
        with self.request('/api/chat', payload, timeout=150) as response:
            self.response_opened(response)
            try:packet = json.load(response)
            finally:self.response_opened(None)
        if self.stopping():raise RuntimeError('Story Director is stopping')
        if packet.get('error'):
            raise RuntimeError(packet['error'])
        self.last_metrics={'wall_s':time.perf_counter()-started,
                           'load_s':packet.get('load_duration',0)/1e9,
                           'prompt_eval_s':packet.get('prompt_eval_duration',0)/1e9,
                           'eval_s':packet.get('eval_duration',0)/1e9,
                           'prompt_tokens':packet.get('prompt_eval_count'),
                           'generated_tokens':packet.get('eval_count')}
        result = json.loads(packet['message']['content'])
        if not isinstance(result, dict):
            raise ValueError('Director returned no JSON object')
        return result

    def _safe_scene(self, scene, secret):
        scene = clean(scene, 2400)
        # The public model must not receive an exact concealed claim or a
        # director-provided reveal phrase before the story reaches its gate.
        forbidden = [secret['truth'], *secret['reveal_terms']]
        for phrase in forbidden:
            if len(phrase) >= 5 and phrase.casefold() in scene.casefold():
                raise ValueError('Director attempted an early revelation')
        campaign=self.db.execute('SELECT secret_json FROM campaign LIMIT 1').fetchone()
        if campaign:
            private=json.loads(campaign['secret_json'])
            for values in private.values():
                if not isinstance(values,list):continue
                for phrase in values:
                    if len(phrase)>=12 and phrase.casefold() in scene.casefold():
                        raise ValueError('Director attempted an early campaign revelation')
        return scene

    def campaign_active(self):
        return self.db.execute('SELECT id FROM campaign LIMIT 1').fetchone() is not None

    def activate_campaign(self):
        existing = self.db.execute('SELECT id FROM campaign LIMIT 1').fetchone()
        if existing:
            return existing['id']
        campaign_id = uuid.uuid4().hex
        seed = secrets.randbits(62)
        instructions = self.director_prompt + '\nCampaign policy:\n' + json.dumps(self.policy, ensure_ascii=False)
        request = ('Explicitly initialize the private fictional origin campaign now. '
                   'No episode or player-facing observation yet. Generate a coherent causal foundation '
                   'without a fixed plot or ending. Return JSON with foundational_facts (array of strings), '
                   'causal_dependencies (array of strings), open_questions (array of strings), '
                   'evidence_routes (array of strings), observation_channels (array of strings), '
                   'public_state (object). Do not use real names or private user data.')
        schema = {'type':'object','properties':{
            **{name:{'type':'array','items':{'type':'string'}} for name in
               ('foundational_facts','causal_dependencies','open_questions','evidence_routes','observation_channels')},
            'public_state':{'type':'object'}},
            'required':['foundational_facts','causal_dependencies','open_questions','evidence_routes','observation_channels','public_state']}
        last_error = None
        for attempt in range(2):
            try:
                proposal = self._generate(instructions, request if attempt == 0 else request+' Repair the schema and constraints.', schema, 1000)
                secret = {key:[clean(item, 400) for item in proposal[key][:12]] for key in
                          ('foundational_facts','causal_dependencies','open_questions','evidence_routes','observation_channels')}
                if any(not secret[key] for key in secret):
                    raise ValueError('Incomplete private campaign foundation')
                public = proposal['public_state']
                if not isinstance(public,dict) or len(json.dumps(public))>3000:
                    raise ValueError('Invalid campaign public state')
                with self.db:
                    self.db.execute('INSERT INTO campaign VALUES(?,?,?,?,?,?,?)',
                                    (campaign_id,1,self.library['version'],seed,json.dumps(secret),json.dumps(public),now()))
                return campaign_id
            except (KeyError, TypeError, ValueError) as error:
                last_error = error
        raise ValueError('Campaign initialization failed validation') from last_error

    def begin(self, style='open', mode='standalone', profile='short'):
        if mode not in ('standalone','resonance','connected') or profile not in ('micro','short'):
            raise ValueError('Unsupported adventure mode or length')
        prior = self.world()
        if prior and prior['status'] in ('active','paused'):
            if prior['status'] != 'active':
                with self.db:
                    self.db.execute("UPDATE worlds SET status='active',updated_at=? WHERE id=?", (now(),prior['id']))
            if prior['turn']==0 and prior['opening_reply'] is None:
                return {'world_id':prior['id'],'new':True,'scene':prior['opening_scene']}
            return {'world_id': prior['id'], 'new': False,
                    'scene': prior['opening_scene'] if prior['turn']==0 else prior['opening_reply']}
        if mode == 'connected' and not self.campaign_active():
            self.activate_campaign()
        history=[json.loads(row['dna_json'])['ids'] for row in self.db.execute('SELECT dna_json FROM worlds ORDER BY created_at DESC,rowid DESC LIMIT 8')]
        for _ in range(12):
            seed=secrets.randbits(62)
            dna=select(self.library,seed,history,profile=profile)
            if mode!='connected' or 'explanation.no_mystery' not in dna['ids']:
                break
        else:
            raise RuntimeError('No suitable campaign DNA in bounded selection')
        mystery='explanation.no_mystery' not in dna['ids']
        instructions=self.director_prompt+'\nSelected creative guidance:\n'+dna['guidance']
        campaign=None
        if mode=='connected':
            campaign=self.db.execute('SELECT secret_json,public_state_json FROM campaign LIMIT 1').fetchone()
        request=json.dumps({'instruction':('Initialize one short playable adventure with two distinct access routes for each essential clue. Supply at least two nonempty distinctive reveal_terms and two concrete, different routes.' if mystery else 'Initialize one short playable adventure without a mystery. A causal foundation still exists, but reveal_terms and clue routes may be empty.')+' No prescribed ending. Never use empty placeholder strings. Return only the requested schema.',
                            'style':clean(style,120),'mode':mode,'profile':profile,
                            'campaign_private':json.loads(campaign['secret_json']) if campaign else None,
                            'campaign_public':json.loads(campaign['public_state_json']) if campaign else None},ensure_ascii=False)
        schema={'type':'object','properties':{
            'title':{'type':'string'},'style':{'type':'string'},'truth':{'type':'string'},
            'reveal_terms':{'type':'array','minItems':2 if mystery else 0,'maxItems':8,
                            'items':{'type':'string','minLength':5,'maxLength':160}},
            'routes':{'type':'array','minItems':2 if mystery else 0,'maxItems':8,
                      'items':{'type':'string','minLength':8,'maxLength':300}},
            'public_scene':{'type':'string'},'public_state':{'type':'object'}},
            'required':['title','style','truth','reveal_terms','routes','public_scene','public_state']}
        last_error=None
        for attempt in range(2):
            try:
                result=self._generate(instructions,request if attempt==0 else request+' Repair invalid schema/route/reveal fields.',schema,1000)
                terms=result['reveal_terms'];routes=result['routes']
                if not isinstance(terms,list) or not isinstance(routes,list):
                    raise ValueError('Invalid reveal or route arrays')
                secret={'truth':clean(result['truth'],2000),
                        'reveal_terms':[term.strip() for term in terms[:8] if isinstance(term,str) and 5<=len(term.strip())<=160],
                        'routes':[route.strip() for route in routes[:8] if isinstance(route,str) and 8<=len(route.strip())<=300]}
                if mystery and (len(secret['reveal_terms'])<2 or len(set(secret['routes']))<2):
                    raise ValueError(f'Insufficient reveal guards or alternate routes (valid {len(secret["reveal_terms"])}/{len(terms)}, {len(secret["routes"])}/{len(routes)})')
                scene=self._safe_scene(result['public_scene'],secret)
                state=result['public_state']
                if not isinstance(state,dict) or len(json.dumps(state))>4000:
                    raise ValueError('Invalid public world state')
                world_id=uuid.uuid4().hex
                with self.db:
                    self.db.execute('INSERT INTO worlds VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                                    (world_id,'active',clean(result['title'],120),clean(result['style'],120),
                                     json.dumps(secret),json.dumps(state),0,seed,self.library['version'],
                                     json.dumps({'ids':dna['ids']}),mode,profile,scene,None,now(),now()))
                return {'world_id':world_id,'new':True,'scene':scene}
            except (KeyError,TypeError,ValueError) as error:
                last_error=error
        raise ValueError('Adventure initialization failed validation') from last_error

    def plan(self, action):
        row = self.world()
        if not row or row['status'] != 'active':
            raise RuntimeError('No active fictional world')
        action = clean(action, 1200)
        secret = json.loads(row['secret_json'])
        current_state=json.loads(row['public_state_json'])
        allowed_ids=sorted(state_ids(current_state))[:100]
        campaign=self.db.execute('SELECT secret_json FROM campaign LIMIT 1').fetchone() if row['mode']=='connected' else None
        event_id=uuid.uuid4().hex
        dna=json.loads(row['dna_json'])
        guidance=[]
        for axis,items in self.library['axes'].items():
            guidance.extend(item['id']+': '+item['guidance'] for item in items if item['id'] in dna['ids'])
        request = json.dumps({'player_action': action, 'turn': row['turn']+1,
                              'event_id':event_id,'expected_version':row['turn'],
                              'hidden_truth': secret['truth'],
                              'campaign_private':json.loads(campaign['secret_json']) if campaign else None,
                              'routes':secret['routes'],
                              'public_state': current_state,
                              'allowed_reference_ids':allowed_ids,
                              'recent_events': self.events(row['id'])}, ensure_ascii=False)
        instructions = self.director_prompt + '\nSelected creative guidance:\n'+'\n'.join(guidance) + '\n' + (
            'Decide actual consequences of the free-form action. '
            'Preserve the hidden truth and established world facts. Keep fiction separate from real biography. '
            'Do not reveal or paraphrase the hidden truth; the current adventure may be unrelated. '
            'Return JSON with matching event_id, expected_version, public_scene (observations only), '
            'consequence (concrete change or valid reason action could not occur), '
            'state_patch (only changed public keys, using JSON Merge Patch; empty object for no change), '
            'referenced_ids (only IDs from allowed_reference_ids; empty is valid), '
            'complete (boolean; only after a genuinely earned local ending). '
            'Use short, concrete public_scene and consequence fields. Do not repeat the whole world state. '
            'Never write future plot or secret information in public fields. '
            'Respect player choice; no forced path. During an active opt-in adventure, '
            'an occasional small incidental discovery may arise from the established world '
            'without requiring the player to pursue it. Quiet turns are valid. '
            'Do not claim a real system action.'
        )
        schema={'type':'object','properties':{
            'event_id':{'type':'string'},'expected_version':{'type':'integer'},
            'public_scene':{'type':'string'},'consequence':{'type':'string'},
            'state_patch':{'type':'object'},
            'referenced_ids':{'type':'array','items':{'type':'string','enum':allowed_ids},'maxItems':12},
            'complete':{'type':'boolean'}},
            'required':['event_id','expected_version','public_scene','consequence','state_patch','referenced_ids','complete']}
        last_error=None
        for attempt in range(2):
            try:
                result=self._generate(instructions,request if attempt==0 else request+' Repair invalid output; keep the same event ID and version.',schema,400)
                if result['event_id']!=event_id or result['expected_version']!=row['turn']:
                    raise ValueError('Director event ID or version mismatch')
                scene=self._safe_scene(result['public_scene'],secret)
                consequence=self._safe_scene(result['consequence'],secret)
                patch=result['state_patch']
                if not isinstance(patch,dict) or len(json.dumps(patch))>2000:
                    raise ValueError('Invalid public world patch')
                state=merge_patch(current_state,patch)
                if len(json.dumps(state))>4000:
                    raise ValueError('Invalid public world state')
                self._safe_scene(json.dumps(state,ensure_ascii=False),secret)
                if not isinstance(result['referenced_ids'],list) or not set(result['referenced_ids'])<=set(allowed_ids):
                    raise ValueError('Director referenced an unknown state ID')
                if not isinstance(result['complete'],bool):
                    raise ValueError('Invalid completion flag')
                return {'world_id':row['id'],'turn':row['turn']+1,'event_id':event_id,
                        'action':action,'scene':scene,'consequence':consequence,
                        'state':state,'complete':result['complete']}
            except (KeyError,TypeError,ValueError) as error:
                last_error=error
        raise ValueError('Story event failed validation') from last_error

    def commit(self, decision, reply):
        if self.stopping():raise RuntimeError('Story Director is stopping')
        reply = clean(reply, 5000)
        with self.db:
            cursor = self.db.execute(
                "UPDATE worlds SET public_state_json=?,turn=?,status=?,updated_at=? WHERE id=? AND turn=? AND status='active'",
                (json.dumps(decision['state']), decision['turn'],
                 'completed' if decision['complete'] else 'active',now(),
                 decision['world_id'], decision['turn']-1))
            if cursor.rowcount != 1:
                raise RuntimeError('Story state changed while response was generated')
            self.db.execute('INSERT INTO events(world_id,turn,event_id,action,public_scene,consequence,reply,created_at) VALUES(?,?,?,?,?,?,?,?)',
                            (decision['world_id'], decision['turn'], decision['event_id'], decision['action'],
                             decision['scene'], decision['consequence'], reply, now()))

    def commit_opening(self, world_id, reply):
        if self.stopping():raise RuntimeError('Story Director is stopping')
        reply=clean(reply,5000)
        with self.db:
            cursor=self.db.execute('UPDATE worlds SET opening_reply=?,updated_at=? WHERE id=? AND opening_reply IS NULL',
                                   (reply,now(),world_id))
            if cursor.rowcount!=1:raise RuntimeError('Opening was already committed or removed')

    def discard_unseen(self,world_id):
        with self.db:
            self.db.execute('DELETE FROM worlds WHERE id=? AND turn=0 AND opening_reply IS NULL',(world_id,))

    def validate_reply(self,reply,world_id):
        row=self.db.execute('SELECT secret_json FROM worlds WHERE id=?',(world_id,)).fetchone()
        if not row:raise ValueError('Unknown story world')
        self._safe_scene(reply,json.loads(row['secret_json']))

    def pause(self):
        row = self.world()
        if row and row['status'] == 'active':
            with self.db:
                self.db.execute("UPDATE worlds SET status='paused',updated_at=? WHERE id=?", (now(),row['id']))

    def abandon(self):
        row=self.world()
        if row and row['status'] in ('active','paused'):
            with self.db:
                self.db.execute("UPDATE worlds SET status='abandoned',updated_at=? WHERE id=?",(now(),row['id']))

    @staticmethod
    def intent(prompt, active):
        value = prompt.strip().casefold()
        if value=='/origin' or value.startswith('/origin '):
            return 'origin'
        if value in ('/story', '/adventure') or value.startswith('/story ') or re.search(r'\b(start|begin|resume|continue) (?:the |our |an? )?(?:story|adventure)\b', value):
            return 'start'
        if value in ('/abandon', '/endstory'):
            return 'abandon'
        if value in ('/talk','/pause','/stopstory') or re.search(r'\b(pause|stop|leave) (?:the |our )?(?:story|adventure)\b|\b(let us|let\'s) (?:just )?talk\b',value):
            return 'pause'
        if not active:
            return 'normal'
        # Deterministic routing. Ambiguous utterances stay in dialogue and
        # cannot change the world state or create new canon.
        verbs=(r'inspect|examine|look|search|open|close|take|pick|grab|put|place|'
               r'give|show|ask|speak|talk to|tell|walk|go|move|enter|leave|'
               r'follow|touch|press|pull|push|read|write|use|try|test|wait|'
               r'hide|listen|investigate|explore|choose|turn|unlock|knock|'
               r'untersuche|schaue|suche|öffne|schließe|nehme|gehe|frage|'
               r'spreche|lese|drücke|ziehe|lege|folge|betrete|verlasse')
        if re.match(rf'^(?:i |ich |we |wir |let\'s |lass uns )(?:will |would like to |want to |am going to |möchte |werde )?(?:carefully |slowly |quietly |quickly |vorsichtig |leise )?(?:{verbs})\b',value):
            return 'action'
        if re.match(rf'^(?:can|could|would) you (?:please )?(?:{verbs})\b',value) and not re.match(r'^(?:can|could|would) you (?:please )?(?:tell|show) me\b',value):
            return 'action'
        if re.match(rf'^(?:please |bitte )?(?:{verbs})\b',value) and not value.endswith('?'):
            return 'action'
        return 'dialogue'
