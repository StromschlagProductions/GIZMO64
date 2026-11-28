"""Idle-time preparation of optional fictional scenes using the existing Director."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
import http.client
import json
import secrets
import socket
import threading
import time
from urllib.parse import urlsplit
from datetime import datetime, timezone


STOPWORDS={'the','and','this','that','with','from','have','what','when','where','would','could',
           'there','about','your','mine','ours','then','they','into','over','under','again',
           'eine','einen','einer','dieser','diese','dieses','und','der','die','das','mit',
           'für','aus','von','hier','dort','nicht','noch','mein','meine','dein','deine',
           'small','quiet','ordinary','moment','little','something','nearby','around'}


def topic_words(text):
    return {word.casefold() for word in re.findall(r'\b\w{4,}\b',text)
            if word.casefold() not in STOPWORDS}


def accepts_previous_scene(prompt,previous_assistant,previous_user=None):
    """A short assent only matters after GIZMO just proposed a fictional scene."""
    if not previous_assistant:return False
    text=prompt.strip().casefold().replace('’',"'")
    if len(text)>48:return False
    text=re.sub(r'[^\w\s\']',' ',text)
    text=' '.join(text.split())
    approvals=("lets go","let's go","let us go","show me","what happens next",
               "open it","yes let's do it","yes lets do it","let's do it","lets do it")
    if not any(SequenceMatcher(None,text,item).ratio()>=.83 for item in approvals):
        return False
    prior=previous_assistant.casefold()
    scene=bool(re.search(r'\b(?:fiction|story|adventure|mystery|imagine|strange|hidden|'
                         r'dusty|secret|closet|cupboard|hatch|portal|door|attic|basement|'
                         r'schrank|flur)\b',prior))
    proposal=bool(re.search(r'\b(?:we|us|our|together|let.s|lets)\b',prior) and
                  re.search(r'\b(?:could|would|should|might|maybe|perhaps|shall|want|ready|'
                            r'imagine|suppose)\b',prior))
    invited_fiction=bool(previous_user and
        re.search(r'\b(?:imagine|fiction|story|adventure|pretend|invent)\b',previous_user,re.I) and
        re.search(r'\b(?:suggest|explore|investigate|show|open|what if|picture)\b',previous_user,re.I))
    concrete_scene=len(topic_words(previous_assistant))>=4
    return (scene and proposal) or (invited_fiction and concrete_scene)


class LocalResponse:
    def __init__(self,owner,connection,response):
        self.owner=owner;self.connection=connection;self.response=response
    def __enter__(self):return self
    def __exit__(self,*_):self.close()
    def __iter__(self):return iter(self.response)
    def read(self,*args):return self.response.read(*args)
    def close(self):
        try:self.response.close()
        finally:
            self.connection.close()
            self.owner._clear_connection(self.connection)


class StoryLite:
    def __init__(self,lab,director):
        self.lab=lab
        self.director=director
        self.pause_event=threading.Event()
        self.stop_event=threading.Event()
        self.wake=threading.Event()
        self.preparing_done=threading.Event();self.preparing_done.set()
        self.worker=None
        self.last_input=time.monotonic()
        self.turns=0
        self.eligible=False
        self.last_error_type=None
        self.last_pause_s=0.0
        self.connection=None
        self.connection_lock=threading.Lock()

    def _clear_connection(self,connection):
        with self.connection_lock:
            if self.connection is connection:self.connection=None

    def _abort_connection(self):
        with self.connection_lock:connection=self.connection
        if connection:
            sock=connection.sock
            if sock:
                try:sock.shutdown(socket.SHUT_RDWR)
                except OSError:pass
            connection.close()

    def request(self,endpoint,payload=None,timeout=5):
        """Cancelable localhost request, including time spent waiting for headers."""
        url=urlsplit(self.lab.config.get('ollama_url','http://localhost:11434'))
        if url.scheme!='http' or url.hostname not in ('localhost','127.0.0.1','::1'):
            raise ValueError('Story Lite Director requires the local Ollama API')
        connection=http.client.HTTPConnection(url.hostname,url.port or 11434,timeout=timeout)
        with self.connection_lock:self.connection=connection
        try:
            body=json.dumps(payload).encode('utf-8') if payload is not None else None
            connection.request('POST' if body is not None else 'GET',url.path.rstrip('/')+endpoint,
                               body=body,headers={'Content-Type':'application/json'})
            response=connection.getresponse()
            if response.status>=400:
                raise RuntimeError('Local Ollama Director HTTP '+str(response.status))
            return LocalResponse(self,connection,response)
        except Exception:
            connection.close();self._clear_connection(connection)
            raise

    def start(self):
        if self.worker is None:
            self.worker=threading.Thread(target=self._loop,name='gizmo-story-lite',daemon=True)
            self.worker.start()

    def pause(self):
        started=time.perf_counter()
        self.pause_event.set()
        if not self.preparing_done.is_set():self._abort_connection()
        response=self.lab.active_response
        if response and not self.preparing_done.is_set():
            try:response.close()
            except OSError:pass
        yielded=self.preparing_done.wait(timeout=3)
        self.last_pause_s=time.perf_counter()-started
        if not yielded:
            raise RuntimeError('Story preparation did not yield to the conversation')

    def resume(self,normal_turn=False):
        if normal_turn:
            self.turns+=1
            self.last_input=time.monotonic()
            threshold=int(self.lab.config.get('story_lite_min_turns',2))
            chance=float(self.lab.config.get('story_lite_chance',.1))
            self.eligible=self.turns>=threshold and secrets.randbelow(10000)<int(max(0,min(1,chance))*10000)
        self.pause_event.clear()
        self.wake.set()

    def stop(self):
        self.stop_event.set();self.pause_event.set();self.wake.set()
        if not self.preparing_done.is_set():self._abort_connection()
        response=self.lab.active_response
        if response and not self.preparing_done.is_set():
            try:response.close()
            except OSError:pass
        if self.worker:
            self.worker.join(timeout=5)
            return not self.worker.is_alive()
        return True

    def _loop(self):
        while not self.stop_event.is_set():
            self.wake.wait(timeout=.2);self.wake.clear()
            if self.pause_event.is_set() or not self.eligible:
                continue
            idle=float(self.lab.config.get('story_lite_idle_seconds',90))
            if time.monotonic()-self.last_input<idle:
                continue
            self.eligible=False
            try:self.prepare_now()
            except Exception as error:self.last_error_type=type(error).__name__

    def prepare_now(self):
        """One bounded idle job; secrets never leave the Director's SQLite archive."""
        if self.stop_event.is_set() or self.pause_event.is_set():return False
        row=self.director.world()
        if row and row['status'] in ('prepared','active','paused'):
            return False
        hours=float(self.lab.config.get('story_lite_min_hours',72))
        if row:
            age=(datetime.now(timezone.utc)-datetime.fromisoformat(row['updated_at'])).total_seconds()/3600
            if age<hours:return False
        self.preparing_done.clear()
        if self.lab.analyzer:self.lab.analyzer.pause()
        try:
            if self.stop_event.is_set() or self.pause_event.is_set():return False
            origin_chance=float(self.lab.config.get('story_lite_origin_chance',.25))
            mode='connected' if secrets.randbelow(10000)<int(max(0,min(1,origin_chance))*10000) else 'standalone'
            prepared=self.director.begin(style='a brief discovery emerging from an ordinary moment',
                                         mode=mode,profile='micro')
            if not prepared['new']:return False
            self.director.validate_reply(prepared['scene'],prepared['world_id'])
            with self.director.db:
                self.director.db.execute("UPDATE worlds SET status='prepared' WHERE id=? AND turn=0 AND opening_reply IS NULL",
                                         (prepared['world_id'],))
            return True
        finally:
            self.preparing_done.set()
            if self.lab.analyzer and not self.lab.stop_event.is_set() and not self.pause_event.is_set():
                self.lab.analyzer.resume()

    def prepared(self):
        row=self.director.world()
        if not row or row['status']!='prepared' or row['opening_reply'] is not None:
            return None
        age=(datetime.now(timezone.utc)-datetime.fromisoformat(row['created_at'])).total_seconds()
        if age>7*86400 or row['turn']!=0 or row['library_version']!=self.director.library['version']:
            self.director.discard_unseen(row['id'])
            return None
        self.director.validate_reply(row['opening_scene'],row['id'])
        return row

    def route(self,prompt,previous_assistant=None,previous_user=None):
        """Deterministic relevance gate; no model call to choose the route."""
        text=prompt.strip().casefold()
        accepted=accepts_previous_scene(prompt,previous_assistant,previous_user)
        prepared=self.prepared()
        if prepared:
            if text.startswith('/origin') and prepared['mode']!='connected':
                self.director.discard_unseen(prepared['id'])
                return 'origin'
            if text.startswith(('/story','/adventure')) and prepared['mode']=='connected':
                self.director.discard_unseen(prepared['id'])
                return 'start'
            explicit=text.startswith(('/story','/origin'))
            overlap=len(topic_words(prompt)&topic_words(prepared['opening_scene']))
            prior_overlap=len(topic_words(previous_assistant or '')&topic_words(prepared['opening_scene']))
            if explicit or (overlap>=2 and self.director.intent(prompt,True)=='dialogue') or (accepted and prior_overlap>=2):
                return 'release'
            return 'followup' if accepted else 'normal'
        row=self.director.world()
        if row and row['status']=='active' and row['opening_reply']:
            intent=self.director.intent(prompt,True)
            brief=self.director.public_brief()
            context=brief['opening'] or ''
            context+=' '.join(str(item) for item in brief['recent_observations'])
            relevant=len(topic_words(prompt)&topic_words(context))>=2 or text.startswith(('/story','/origin'))
            if relevant and intent=='action':return 'action'
            if relevant and intent=='dialogue':return 'dialogue'
        if text.startswith('/origin'):return 'origin'
        if text.startswith(('/story','/adventure')):return 'start'
        return 'followup' if accepted else 'normal'

    def commit_release(self,world_id,reply):
        self.director.validate_reply(reply,world_id)
        self.director.commit_opening(world_id,reply)
        with self.director.db:
            self.director.db.execute("UPDATE worlds SET status='active' WHERE id=? AND status='prepared'",
                                     (world_id,))
