"""Validierte, unterbrechbare Analyse mit dem bereits geladenen Ollama-Modell."""
import hashlib
import json
import re
import threading
import time
import urllib.request
from memory import Memory

KINDS={'person','pet','project','place','film','computer','other'}
PREDICATES={'has_sister','has_brother','has_dog','has_cat','friend_of','studied','works_as','likes','dislikes','lives_in','discussed','created','experienced','related_to'}
SCOPES={'personal','episodic','semantic','narrative','hypothesis'}
SCHEMA={'type':'object','properties':{'claims':{'type':'array','items':{'type':'object','properties':{
    'subject':{'type':'string'},'subject_kind':{'type':'string'},'predicate':{'type':'string'},
    'object':{'type':'string'},'object_kind':{'type':'string'},'value':{'type':'string'},
    'evidence':{'type':'string'},'scope':{'type':'string'},'confidence':{'type':'number'}},
    'required':['subject','subject_kind','predicate','object','object_kind','value','evidence','scope','confidence'],
    'additionalProperties':False}}},'required':['claims'],'additionalProperties':False}
PROMPT=('Extract only information the USER supplied in the newest message. Use earlier turns only to resolve clear references. '
        'Return JSON matching the schema. Quote an exact evidence span from the newest user message. '
        'Never treat assistant claims as personal facts. For ambiguity use scope hypothesis. '
        'For fictional stories use scope narrative. If nothing is supported, return an empty claims list. '
        'Use short canonical predicates from the schema vocabulary.')


def validate_claim(claim, source):
    if not isinstance(claim,dict) or set(claim)!=set(SCHEMA['properties']['claims']['items']['properties']):
        return None
    if any(not isinstance(claim[k],str) or len(claim[k])>160 for k in ('subject','subject_kind','predicate','object','object_kind','value','evidence','scope')):
        return None
    if claim['subject_kind'] not in KINDS or claim['object_kind'] not in KINDS or claim['predicate'] not in PREDICATES or claim['scope'] not in SCOPES:
        return None
    evidence=claim['evidence'].strip()
    if not evidence or evidence.casefold() not in source.casefold():
        return None
    try:
        confidence=float(claim['confidence'])
    except (TypeError,ValueError):
        return None
    if not 0<=confidence<=1 or not claim['subject'].strip() or (not claim['object'].strip() and not claim['value'].strip()):
        return None
    speculative=bool(re.search(r'\b(maybe|perhaps|might|could|possibly|what if|suppose)\b',source,re.I))
    fictional=bool(re.search(r'\b(in our story|in this story|fictional|imagine|roleplay)\b',source,re.I))
    pronoun=bool(re.match(r'\s*(she|he|they|her|his|their)\b',evidence,re.I))
    status='active' if claim['scope'] in ('personal','semantic','episodic') and confidence>=.8 and not speculative and not pronoun else 'pending'
    if claim['scope']=='narrative' or fictional:
        status='fictional'
    return {**claim,'confidence':confidence,'status':status}


class Analyzer:
    def __init__(self, db_path, config, opener=None):
        self.memory=Memory(db_path)
        self.config=config
        self.opener=opener or urllib.request.urlopen
        self.stop_event=threading.Event()
        self.pause_event=threading.Event()
        self.response=None
        self.thread=None
        self.last_duration_s=0
        self.closed=False

    def start(self):
        if not self.thread:
            self.thread=threading.Thread(target=self.loop,daemon=True)
            self.thread.start()

    def pause(self):
        self.pause_event.set()
        if self.response:
            try: self.response.close()
            except OSError: pass

    def resume(self):
        self.pause_event.clear()

    def stop(self):
        self.stop_event.set()
        self.pause()
        if self.thread:
            self.thread.join(timeout=2)
        if (not self.thread or not self.thread.is_alive()) and not self.closed:
            self.memory.close()
            self.closed=True

    def analyze_one(self):
        if self.stop_event.is_set() or self.pause_event.is_set():
            return False
        job=self.memory.next_job()
        if not job:
            return False
        blocked=self.memory.db.execute("SELECT 1 FROM memories WHERE source_message_id=? AND status IN ('deleted','superseded') LIMIT 1",(job['message_id'],)).fetchone()
        if blocked:
            self.memory.finish_job(job['id'])
            return True
        started=time.perf_counter()
        try:
            context=self.memory.context_for_message(job['message_id'],5)
            payload={'model':self.config.get('model','gemma4:12b'),
                     'messages':[{'role':'system','content':PROMPT},
                                 {'role':'user','content':json.dumps(context,ensure_ascii=False)}],
                     'format':SCHEMA,'stream':False,'keep_alive':self.config.get('keep_alive',-1),
                     'options':{'temperature':0,'num_predict':350,'num_ctx':self.config.get('num_ctx',8192)}}
            request=urllib.request.Request(self.config.get('ollama_url','http://localhost:11434').rstrip('/')+'/api/chat',
                                           data=json.dumps(payload).encode('utf-8'),headers={'Content-Type':'application/json'})
            with self.opener(request,timeout=60) as response:
                self.response=response
                event=json.load(response)
                self.response=None
            if self.stop_event.is_set() or self.pause_event.is_set():
                self.memory.finish_job(job['id'],'cancelled')
                return False
            parsed=json.loads(event['message']['content'])
            if not isinstance(parsed,dict) or not isinstance(parsed.get('claims'),list):
                raise ValueError('Ungueltige JSON-Claims')
            for candidate in parsed['claims'][:12]:
                claim=validate_claim(candidate,job['text'])
                if claim:
                    self.memory.add_relation(claim['subject'].strip(),claim['subject_kind'],claim['predicate'],
                                             claim['object'].strip(),claim['object_kind'],claim['value'].strip(),
                                             job['message_id'],claim['evidence'].strip(),claim['confidence'],claim['status'])
            self.memory.finish_job(job['id'])
            return True
        except Exception as error:
            self.response=None
            self.memory.finish_job(job['id'],'cancelled' if self.stop_event.is_set() or self.pause_event.is_set() else str(error)[:200])
            return False
        finally:
            self.last_duration_s=time.perf_counter()-started

    def loop(self):
        while not self.stop_event.is_set():
            if self.pause_event.is_set() or not self.analyze_one():
                self.stop_event.wait(.25)
