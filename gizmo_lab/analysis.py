"""Validierte, unterbrechbare Analyse mit dem bereits geladenen Ollama-Modell."""
import hashlib
import json
import re
import threading
import time
import urllib.request
from memory import Memory, source_flags, token_bound, normalize_property_key

KINDS={'person','pet','project','place','film','computer','object','event','interest','organization','other'}
PREDICATES={'has_sister','has_brother','has_mother','has_father','has_partner','has_child','has_dog','has_cat','friend_of','studied','works_as','likes','dislikes','lives_in','discussed','created','experienced','related_to','attribute'}
SCOPES={'personal','episodic','semantic','narrative','hypothesis'}
SCHEMA={'type':'object','properties':{'claims':{'type':'array','items':{'type':'object','properties':{
    'subject':{'type':'string'},'subject_kind':{'type':'string','enum':sorted(KINDS)},'predicate':{'type':'string','enum':sorted(PREDICATES)},'property_key':{'type':'string'},
    'object':{'type':'string'},'object_kind':{'type':'string','enum':sorted(KINDS)},'value':{'type':'string'},
    'evidence':{'type':'string'},'scope':{'type':'string','enum':sorted(SCOPES)},'confidence':{'type':'number','minimum':0,'maximum':1}},
    'required':['subject','subject_kind','predicate','property_key','object','object_kind','value','evidence','scope','confidence'],
    'additionalProperties':False}}},'required':['claims'],'additionalProperties':False}
PROMPT=('Extract only information the USER supplied in the final user message. Earlier messages are reference context only, never extraction sources. '
        'Return JSON matching the schema. Quote an exact evidence span from the newest user message. '
        'Never treat assistant claims as personal facts. For ambiguity use scope hypothesis. '
        'For fictional stories use scope narrative. If nothing is supported, return an empty claims list. '
        'Use only the enum values in the schema. '
        'Represent the speaker as USER unless their name is explicitly known from the context. '
        'For "My sister is Emma", use subject USER, predicate has_sister, object Emma, object_kind person. '
        'For "My dog is Milo", use subject USER, predicate has_dog, object Milo, object_kind pet. '
        'For a literal attribute such as a subject studied psychology, use predicate studied, property_key "", object "", object_kind other, value psychology. '
        'For ANY other explicit stable property of a named person, pet, place, object, interest or event, use predicate attribute, object "", object_kind other, a concise property_key such as breed, age, temperament, manufacturer, condition, personal_meaning, time or location, and the stated value. These keys are examples, never an exhaustive vocabulary. '
        'For a named relationship not covered by a dedicated predicate, use related_to with a concise property_key describing the relation (owns, participated_in, accompanied_by, etc.) and a named object. '
        'Ground the type of each relationship in the newest evidence: a radio is an object, never a dog; a visit is an event, never an attribute of the speaker. '
        'For "My radio is named Atlas", create related_to USER owns Atlas (object_kind object); never has_dog. '
        'For "The Atlas tuning knob is chipped", attach an attribute such as tuning_knob_condition=chipped to Atlas; do not generalize away the part. '
        'For "Nora collects antique postcards", use attribute collection=antique postcards on Nora, not likes. '
        'For "That Bergen trip was important because it was our first holiday together", use subject Bergen trip (event), attribute personal_meaning=first holiday together. '
        'Use property_key "" for the dedicated predicates. Preserve distinct explicit properties in separate claims. '
        'For a pronoun with one grounded antecedent, attach each explicit property to that antecedent, not to USER or a newly invented entity. '
        'A stated animal type and stated sex are separate properties; do not infer sex from pronouns alone or traits from stereotypes. '
        'Preserve names and exact evidence in the original language. Earlier messages are context, not new claims. '
        'Use USER for the human speaker even when their name is known. Do not create a related_to claim for the speaker naming themselves; names use the separate personal memory. '
        'Resolve a pronoun only when there is one clear antecedent in user-authored context. Never infer a biography from a question. '
        'For topics the user says they discussed or are working on, use discussed or created with USER as subject. '
        'The response schema is: '+json.dumps(SCHEMA))


def validate_claim(claim, source, context=None, anchors=None):
    if not isinstance(claim,dict) or set(claim)!=set(SCHEMA['properties']['claims']['items']['properties']):
        return None
    if any(not isinstance(claim[k],str) or len(claim[k])>160 for k in ('subject','subject_kind','predicate','property_key','object','object_kind','value','evidence','scope')):
        return None
    if claim['subject_kind'] not in KINDS or claim['object_kind'] not in KINDS or claim['predicate'] not in PREDICATES or claim['scope'] not in SCOPES:
        return None
    property_key=normalize_property_key(claim['property_key']) if claim['predicate'] in ('attribute','related_to') else ''
    attribute_object=claim['object'].strip()
    if claim['predicate']=='attribute' and (not property_key or not claim['value'].strip() or
        (attribute_object and attribute_object.casefold()!=claim['value'].strip().casefold())):
        return None
    evidence=claim['evidence'].strip()
    if not evidence or evidence.casefold() not in source.casefold():
        return None
    # Dedicated kinship and pet edges require the stated relationship in the
    # quoted source. This blocks model category errors before they enter memory.
    required_terms={'has_dog':r'\b(dog|hund)\b','has_cat':r'\b(cat|katze)\b',
                    'has_sister':r'\b(sister|schwester)\b','has_brother':r'\b(brother|bruder)\b',
                    'has_mother':r'\b(mother|mutter)\b','has_father':r'\b(father|vater)\b'}
    anchors=anchors or {'roles':[],'entities':[]}
    named_role=(claim['predicate'] in anchors['roles'] and claim['object'] and
        re.search(r'\b(?:name\s+(?:is|was)|called|named|heißt|heisst|ist)\s+'+re.escape(claim['object'])+r'\b',evidence,re.I))
    if claim['predicate'] in required_terms and not re.search(required_terms[claim['predicate']],evidence,re.I) and not named_role:
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
    if pronoun and named_role:
        resolved=True
    if pronoun and claim['subject'].casefold() in {name.casefold() for name in anchors['entities']}:
        resolved=True
    if pronoun and context and not resolved:
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
    scope=claim['scope']
    if scope=='narrative' and not fictional:
        # A model label alone cannot turn a plain user statement into a story.
        # Keep it unconfirmed, but let it dispute an earlier factual value.
        scope='hypothesis'
    status='active' if scope in ('personal','semantic','episodic') and confidence>=.8 and not speculative and (not pronoun or resolved) else 'pending'
    if fictional:
        status='fictional'
    return {**claim,'property_key':property_key,'object':'' if claim['predicate']=='attribute' else claim['object'],'scope':scope,
            'confidence':confidence,'status':status}


def contextual_name_claim(source,context,anchors):
    """Link a name to one recent user-stated role; never use assistant text as evidence."""
    roles=anchors.get('roles',[])
    if len(roles)!=1 or '?' in source or any(source_flags(source)):
        return None
    role=roles[0]
    patterns=[(r'\bher name (?:is|was) ([\w-]{2,60})\b',{'has_sister','has_mother','has_dog','has_cat'}),
              (r'\bhis name (?:is|was) ([\w-]{2,60})\b',{'has_brother','has_father','has_dog','has_cat'}),
              (r'\bsie (?:heißt|heisst) ([\w-]{2,60})\b',{'has_sister','has_mother','has_dog','has_cat'}),
              (r'\ber (?:heißt|heisst) ([\w-]{2,60})\b',{'has_brother','has_father','has_dog','has_cat'})]
    for pattern,allowed in patterns:
        match=re.search(pattern,source,re.I)
        if match and role in allowed:
            candidate={'subject':'USER','subject_kind':'person','predicate':role,'property_key':'',
                       'object':match.group(1),'object_kind':'pet' if role in ('has_dog','has_cat') else 'person',
                       'value':'','evidence':match.group(0),'scope':'personal','confidence':1.0}
            return validate_claim(candidate,source,context,anchors)
    return None


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
            self.memory.finish_job(job['id'],claim_count=0,rejected_count=0,empty_reason='source_blocked')
            return True
        started=time.perf_counter()
        rejected_count=None
        try:
            context=self.memory.context_for_message(job['message_id'],16)
            self.memory.extract_user(job['text'],job['message_id'])
            system_prompt=PROMPT
            anchors=self.memory.analysis_anchors(context,job['message_id'])
            if anchors['roles']:
                system_prompt+=' Earlier USER evidence supports a recent '+anchors['roles'][0]+' reference.'
            if anchors['entities']:
                system_prompt+=' A confirmed earlier USER relationship uniquely names '+json.dumps(anchors['entities'][0])+'.'
            if re.match(r'\s*(she|he|her|his|sie|er|ihr|sein)\b',job['text'],re.I):
                references=[]
                for entity in self.memory.db.execute("SELECT name,kind FROM entities WHERE status='active' AND kind IN ('person','pet') AND name<>'USER' LIMIT 256"):
                    probe={'subject':entity['name'],'subject_kind':entity['kind'],'predicate':'related_to','property_key':'','object':'','object_kind':'other',
                           'value':'reference','evidence':job['text'][:160],'scope':'personal','confidence':1}
                    checked=validate_claim(probe,job['text'],context,anchors)
                    if checked and checked['status']=='active':
                        references.append(entity['name'])
                if len(references)==1:
                    system_prompt+=' Grounded reference from the preceding user-authored turn: '+json.dumps(references[0])+'. Resolve this pronoun and extract the explicit new factual clause; a clear pronoun alone is not a reason for empty claims.'
            limit=int(self.config.get('num_ctx',8192))
            available=limit-700-max(512,limit//8)-64
            prior=[{'id':item['id'],'text':item['text']} for item in context[:-1] if item['role']=='user'][-8:]
            reference='Earlier USER statements for reference only; do not extract claims from this list: '
            while prior and token_bound(system_prompt)+token_bound(reference)+token_bound(json.dumps(prior,ensure_ascii=False))+token_bound(job['text'])>available:
                prior.pop(0)
            if token_bound(system_prompt)+token_bound(reference)+token_bound(json.dumps(prior,ensure_ascii=False))+token_bound(job['text'])>available:
                raise ValueError('Analysequelle überschreitet das sichere Kontextbudget; nichts abgeschnitten')
            payload={'model':self.config.get('model','gemma4:12b'),
                     'messages':[{'role':'system','content':system_prompt},
                                 {'role':'system','content':reference+json.dumps(prior,ensure_ascii=False)},
                                 {'role':'user','content':job['text']}],
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
                claim=validate_claim(candidate,job['text'],context,anchors)
                if claim:
                    accepted.append(claim)
            model_accepted=len(accepted)
            linked=contextual_name_claim(job['text'],context,anchors)
            if linked and not any(item['subject']==linked['subject'] and item['predicate']==linked['predicate'] and item['object']==linked['object'] for item in accepted):
                accepted.append(linked)
            rejected_count=min(len(parsed['claims']),12)-model_accepted
            if parsed['claims'] and not accepted:
                raise ValueError('Keine Analysebehauptung besteht die Beleg- und Typprüfung')
            for claim in accepted:
                    self.memory.add_relation(claim['subject'].strip(),claim['subject_kind'],claim['predicate'],
                                             claim['object'].strip(),claim['object_kind'],claim['value'].strip(),
                                             job['message_id'],claim['evidence'].strip(),claim['confidence'],claim['status'],claim['scope'],claim['property_key'])
            self.memory.finish_job(job['id'],claim_count=len(accepted),rejected_count=rejected_count,
                empty_reason='no_extractable_claims' if not parsed['claims'] else 'claims_rejected' if not accepted else None)
            return True
        except Exception as error:
            self.response=None
            self.memory.finish_job(job['id'],'cancelled' if self.stop_event.is_set() or self.pause_event.is_set() else str(error)[:200],
                rejected_count=rejected_count)
            return False
        finally:
            self.last_duration_s=time.perf_counter()-started

    def loop(self):
        while not self.stop_event.is_set():
            if self.pause_event.is_set():
                self.stop_event.wait(.25)
                continue
            if self.analyze_one():
                continue
            if self.pause_event.is_set() or self.stop_event.is_set() or not self.memory.index_next_embedding():
                self.stop_event.wait(.25)
