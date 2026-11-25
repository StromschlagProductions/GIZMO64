"""Validierte, unterbrechbare Analyse mit dem bereits geladenen Ollama-Modell."""
import hashlib
import json
import re
import threading
import time
import urllib.request
from memory import Memory, source_flags, token_bound

KINDS={'person','pet','project','place','film','computer','other'}
PREDICATES={'has_sister','has_brother','has_mother','has_father','has_partner','has_child','has_dog','has_cat','friend_of','studied','works_as','likes','dislikes','lives_in','discussed','created','experienced','related_to'}
SCOPES={'personal','episodic','semantic','narrative','hypothesis'}
SCHEMA={'type':'object','properties':{'claims':{'type':'array','items':{'type':'object','properties':{
    'subject':{'type':'string'},'subject_kind':{'type':'string','enum':sorted(KINDS)},'predicate':{'type':'string','enum':sorted(PREDICATES)},
    'object':{'type':'string'},'object_kind':{'type':'string','enum':sorted(KINDS)},'value':{'type':'string'},
    'evidence':{'type':'string'},'scope':{'type':'string','enum':sorted(SCOPES)},'confidence':{'type':'number','minimum':0,'maximum':1}},
    'required':['subject','subject_kind','predicate','object','object_kind','value','evidence','scope','confidence'],
    'additionalProperties':False}}},'required':['claims'],'additionalProperties':False}
PROMPT=('Extract only information the USER supplied in the newest message. Use earlier turns only to resolve clear references. '
        'Return JSON matching the schema. Quote an exact evidence span from the newest user message. '
        'Never treat assistant claims as personal facts. For ambiguity use scope hypothesis. '
        'For fictional stories use scope narrative. If nothing is supported, return an empty claims list. '
        'Use only the enum values in the schema. '
        'Represent the speaker as USER unless their name is explicitly known from the context. '
        'For "My sister is Emma", use subject USER, predicate has_sister, object Emma, object_kind person. '
        'For "My dog is Milo", use subject USER, predicate has_dog, object Milo, object_kind pet. '
        'For a literal attribute such as a subject studied psychology, use predicate studied, object "", object_kind other, value psychology. '
        'Preserve names and exact evidence in the original language. Earlier messages are context, not new claims. '
        'Use USER for the human speaker even when their name is known. Do not create a related_to claim for the speaker naming themselves; names use the separate personal memory. '
        'Resolve a pronoun only when there is one clear antecedent in user-authored context. Never infer a biography from a question. '
        'For topics the user says they discussed or are working on, use discussed or created with USER as subject. '
        'The response schema is: '+json.dumps(SCHEMA))


def validate_claim(claim, source, context=None):
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
    speculative,fictional=source_flags(source)
    pronoun=bool(re.match(r'\s*(she|he|they|her|his|their|sie|er|ihr|ihre|sein|seine)\b',evidence,re.I))
    resolved=False
    if pronoun and context:
        # Resolve only a named entity from an immediately preceding, factual USER turn.
        # Assistant assertions and turns containing multiple named people are not anchors.
        for previous in reversed(context[:-1]):
            if previous['role']!='user':
                continue
            if any(source_flags(previous['text'])):
                break
            text=previous['text']
            subject=claim['subject']
            role_words='sister|brother|mother|father|dog|cat|friend|partner|schwester|bruder|mutter|vater|hund|katze|freund|freundin|partnerin'
            anchor=re.search(r'\b(?:'+role_words+r")\b(?:['’]s\s+name\s+(?:is|was)|\s+(?:(?:is|was)(?:\s+(?:named|called))?|heißt|heisst|namens|named|called))?\s+"+re.escape(subject)+r'\b',text,re.I)
            if anchor:
                # An additional explicit relationship in the same clause is ambiguous.
                roles=re.findall(r'\b('+role_words+r')\b',text,re.I)
                incompatible=(re.match(r'\s*(she|her|sie|ihr)\b',evidence,re.I) and roles[0].casefold() in ('brother','father','bruder','vater')) or (re.match(r'\s*(he|his|er|sein)\b',evidence,re.I) and roles[0].casefold() in ('sister','mother','schwester','mutter'))
                multiple_names=bool(re.search(r'\band\s+(?:[a-z]+\s+){0,2}[A-Z][a-z]+',text))
                multiple_names=multiple_names or bool(re.search(r'\b(?:met|with|beside|alongside|introduced|visited|knows)\s+(?:[a-z]+\s+){0,2}[A-Z][a-z]+',text))
                resolved=len(roles)==1 and not incompatible and not multiple_names and not re.match(r'\s*(they|their)\b',evidence,re.I)
                break
            if re.search(r'\b(?:she|he|they|sie|er)\b',text,re.I) and re.search(re.escape(subject),text,re.I) is None:
                continue
            break
    status='active' if claim['scope'] in ('personal','semantic','episodic') and confidence>=.8 and not speculative and (not pronoun or resolved) else 'pending'
    if claim['scope']=='narrative' or fictional:
        status='fictional'
    return {**claim,'confidence':confidence,'status':status}


class Analyzer:
    def __init__(self, db_path, config, opener=None):
        self.memory=Memory(db_path,recover_processing=False)
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
        blocked=self.memory.source_blocked(job['message_id'])
        if blocked:
            self.memory.finish_job(job['id'])
            return True
        started=time.perf_counter()
        try:
            context=self.memory.context_for_message(job['message_id'],5)
            self.memory.extract_user(job['text'],job['message_id'])
            system_prompt=PROMPT
            if re.match(r'\s*(she|he|her|his|sie|er|ihr|sein)\b',job['text'],re.I):
                references=[]
                for entity in self.memory.db.execute("SELECT name,kind FROM entities WHERE status='active' AND kind IN ('person','pet') AND name<>'USER' LIMIT 256"):
                    probe={'subject':entity['name'],'subject_kind':entity['kind'],'predicate':'related_to','object':'','object_kind':'other',
                           'value':'reference','evidence':job['text'][:160],'scope':'personal','confidence':1}
                    checked=validate_claim(probe,job['text'],context)
                    if checked and checked['status']=='active':
                        references.append(entity['name'])
                if len(references)==1:
                    system_prompt+=' Grounded reference from the preceding user-authored turn: '+json.dumps(references[0])+'. Resolve this pronoun and extract the explicit new factual clause; a clear pronoun alone is not a reason for empty claims.'
            limit=int(self.config.get('num_ctx',8192))
            available=limit-700-max(512,limit//8)-64
            while len(context)>1 and token_bound(system_prompt)+token_bound(json.dumps(context,ensure_ascii=False))>available:
                context.pop(0)
            if token_bound(system_prompt)+token_bound(json.dumps(context,ensure_ascii=False))>available:
                raise ValueError('Analysequelle überschreitet das sichere Kontextbudget; nichts abgeschnitten')
            payload={'model':self.config.get('model','gemma4:12b'),
                     'messages':[{'role':'system','content':system_prompt},
                                 {'role':'user','content':json.dumps(context,ensure_ascii=False)}],
                     'format':SCHEMA,'stream':True,'think':False,'keep_alive':self.config.get('keep_alive',-1),
                     'options':{'temperature':0,'num_predict':700,'num_ctx':self.config.get('num_ctx',8192)}}
            request=urllib.request.Request(self.config.get('ollama_url','http://localhost:11434').rstrip('/')+'/api/chat',
                                           data=json.dumps(payload).encode('utf-8'),headers={'Content-Type':'application/json'})
            with self.opener(request,timeout=60) as response:
                self.response=response
                chunks=[];event={}
                for raw in response:
                    if self.stop_event.is_set() or self.pause_event.is_set():
                        break
                    event=json.loads(raw)
                    if event.get('error'):
                        raise ValueError(event['error'])
                    chunks.append(event.get('message',{}).get('content',''))
                    if event.get('done'):
                        break
                self.response=None
            if self.stop_event.is_set() or self.pause_event.is_set():
                self.memory.finish_job(job['id'],'cancelled')
                return False
            if event.get('done_reason')=='length':
                raise ValueError('Analyse am Ausgabetokenlimit abgeschnitten')
            if event.get('done') is False:
                raise ValueError('Analysestream unvollständig; keine Teilantwort gespeichert')
            parsed=json.loads(''.join(chunks))
            if not isinstance(parsed,dict) or not isinstance(parsed.get('claims'),list):
                raise ValueError('Ungueltige JSON-Claims')
            accepted=[]
            for candidate in parsed['claims'][:12]:
                claim=validate_claim(candidate,job['text'],context)
                if claim:
                    accepted.append(claim)
            if parsed['claims'] and not accepted:
                raise ValueError('Keine Analysebehauptung besteht die Beleg- und Typprüfung')
            for claim in accepted:
                    self.memory.add_relation(claim['subject'].strip(),claim['subject_kind'],claim['predicate'],
                                             claim['object'].strip(),claim['object_kind'],claim['value'].strip(),
                                             job['message_id'],claim['evidence'].strip(),claim['confidence'],claim['status'],claim['scope'])
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
