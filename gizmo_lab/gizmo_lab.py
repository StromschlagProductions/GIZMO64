"""Lokales GIZMO-LAB: Terminalgespräche und reproduzierbare Ollama-Benchmarks."""
import argparse
import hashlib
import ipaddress
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from memory import Memory, utc_now, assemble_context, ContextBudgetError
from analysis import Analyzer
from version import VERSION

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = 'gemma4:12b'
OPTIONS = ('temperature', 'top_p', 'top_k', 'min_p', 'repeat_penalty', 'num_ctx', 'num_predict', 'seed')


def private_dir():
    base = os.environ.get('GIZMO_LAB_DATA')
    if base:
        return Path(base).expanduser()
    if os.name == 'nt':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'GizmoLab'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'gizmo-lab'


def load_config(data):
    source = data / 'config.json'
    config = json.loads((ROOT / 'config.example.json').read_text(encoding='utf-8'))
    if source.exists():
        config.update(json.loads(source.read_text(encoding='utf-8')))
    return config


def should_quit(prompt):
    return prompt.strip().lower() in ('/quit', '/exit') or '\x1b' in prompt


UPLINK_BEGIN='[[GIZMO:BEGIN]]'
UPLINK_PARA='[[GIZMO:PARA]]'
UPLINK_END='[[GIZMO:END]]'


def c64_records(text):
    """Display-only conversion; never used for the canonical archive."""
    import re
    import unicodedata
    text=re.sub(r'<think\b[^>]*>.*?</think\s*>','',text,flags=re.I|re.S)
    text=re.sub(r'<think\b[^>]*>.*\Z','',text,flags=re.I|re.S)
    text=re.sub(r'</think\s*>','',text,flags=re.I)
    text=re.sub(r'\[([^\]]+)\]\([^)]*\)',r'\1',text)
    text=re.sub(r'(?m)^\s{0,3}(?:#{1,6}\s+|[-*]\s+|>\s+)','',text)
    text=text.replace('```','').replace('**','').replace('__','').replace('`','')
    text=text.replace('—',' - ').replace('–',' - ').replace('’',"'").replace('“','"').replace('”','"')
    for original,replacement in (('Ä','Ae'),('Ö','Oe'),('Ü','Ue'),('ä','ae'),('ö','oe'),('ü','ue'),('ß','ss')):
        text=text.replace(original,replacement)
    text=unicodedata.normalize('NFKD',text).encode('ascii','ignore').decode('ascii')
    text=re.sub(r'[\x00-\x08\x0b-\x1f\x7f]','',text)
    lines=[]
    for paragraph in re.split(r'\n\s*\n',text):
        if lines:lines.append(UPLINK_PARA)
        current=''
        for word in paragraph.split():
            for part in (word[i:i+31] for i in range(0,len(word),31)):
                if len(current)+len(part)+bool(current)>31:
                    lines.append(current);current=''
                current=(current+' '+part).strip()
        if current:lines.append(current)
    return lines or ['SIGNAL EMPFANGEN. KEIN TEXT.']


def uplink_bind_host(configured):
    if configured=='auto':
        candidates={item[4][0] for item in socket.getaddrinfo(socket.gethostname(),None,family=socket.AF_INET,type=socket.SOCK_STREAM)}
        private=[address for address in candidates if ipaddress.ip_address(address).is_private and not ipaddress.ip_address(address).is_loopback]
        if len(private)!=1:raise RuntimeError('LAN-Adresse nicht eindeutig; Uplink-Host in SETTINGS angeben')
        return private[0]
    address=ipaddress.ip_address(configured)
    if address.version!=4 or not address.is_private:raise ValueError('Uplink darf nur an eine private IPv4-Adresse gebunden werden')
    return str(address)


class Uplink:
    """0.2.2 stop-and-wait transport for the one LAB instance."""
    def __init__(self,lab,host='auto',port=6464):
        self.lab=lab;self.host=host;self.port=int(port)
        self.ack_timeout=120
        self.bind_host=None;self.error=None;self.state='disabled';self.running=False
        self.clients=set();self.workers=set();self.listener=None;self.thread=None
        self.stop_event=threading.Event();self.lock=threading.Lock();self.request_lock=threading.Lock()
        self.connections=0;self.last_disconnect=None

    def status(self):
        with self.lock:
            return {'state':self.state,'host':self.bind_host,'port':self.port,'connections':self.connections,
                    'clients':len(self.clients),'last_disconnect':self.last_disconnect,'error':self.error}

    def start(self):
        if self.running:return True
        try:
            if not 1<=self.port<=65535:raise ValueError('Ungültiger Uplink-Port')
            self.bind_host=uplink_bind_host(self.host)
            server=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            try:
                if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
                    server.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
                else:server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                server.bind((self.bind_host,self.port));server.listen(2);server.settimeout(.25)
            except BaseException:
                server.close();raise
            with self.lock:
                self.listener=server;self.state='listening';self.error=None;self.running=True
            self.thread=threading.Thread(target=self.serve,daemon=True,name='gizmo-uplink')
            self.thread.start()
            return True
        except (OSError,ValueError,RuntimeError) as error:
            with self.lock:self.state='error';self.error=str(error)[:180];self.running=False
            return False

    def stop(self):
        self.stop_event.set()
        with self.lock:
            server=self.listener;self.listener=None
            clients=list(self.clients)
            self.running=False;self.state='disabled'
        if server:server.close()
        for client in clients:
            try:client.shutdown(socket.SHUT_RDWR)
            except OSError:pass
            client.close()
        if self.thread and self.thread is not threading.current_thread():self.thread.join(timeout=1)
        for worker in list(self.workers):
            if worker is not threading.current_thread():worker.join(timeout=1)

    def serve(self):
        server=self.listener
        while not self.stop_event.is_set():
            try:client,_address=server.accept()
            except socket.timeout:continue
            except OSError:
                if not self.stop_event.is_set():
                    with self.lock:self.state='error';self.error='Listener nicht verfügbar'
                break
            client.settimeout(1)
            with self.lock:
                self.clients.add(client);self.connections+=1;self.state='connected'
            worker=threading.Thread(target=self.handle,args=(client,),daemon=True,name='gizmo-c64-client')
            with self.lock:self.workers.add(worker)
            worker.start()

    def send(self,client,text):
        client.sendall((text+'\r\n').encode('ascii'))

    def send_acked(self,client,text):
        self.send(client,text)
        previous=client.gettimeout();client.settimeout(self.ack_timeout)
        try:
            reply=bytearray()
            while not self.stop_event.is_set() and not self.lab.stop_event.is_set():
                char=client.recv(1)
                if not char:raise ConnectionError('C64 getrennt')
                if char in (b'\r',b'\n'):
                    if reply:
                        if reply!=b'ACK':raise RuntimeError('C64-ACK ungültig')
                        return
                elif len(reply)<32:reply.extend(char)
                else:raise RuntimeError('C64-ACK zu lang')
            raise ConnectionError('Uplink wird beendet')
        finally:client.settimeout(previous)

    def answer(self,client,prompt):
        with self.request_lock:
            try:
                self.send_acked(client,UPLINK_BEGIN)
                visible='';sent=0
                def stream(chunk):
                    nonlocal visible,sent
                    visible+=chunk
                    records=c64_records(visible)
                    for record in records[sent:-1]:
                        self.send_acked(client,record);sent+=1
                result=self.lab.chat(prompt,on_text=stream,origin='c64')
                if result['abort_reason']=='completed':
                    for record in c64_records(visible)[sent:]:self.send_acked(client,record)
                else:self.send_acked(client,'ANTWORT UNTERBROCHEN.')
                self.send_acked(client,UPLINK_END)
                return True
            except (OSError,ConnectionError,RuntimeError,ValueError):
                # ACK loss/disconnect never replays this user request.
                return False

    def handle(self,client):
        buffer=bytearray()
        try:
            self.send(client,'UPLINK HERGESTELLT. GIZMO ONLINE.')
            while not self.stop_event.is_set() and not self.lab.stop_event.is_set():
                try:data=client.recv(512)
                except socket.timeout:continue
                if not data:break
                for byte in data:
                    if byte in (10,13):
                        if not buffer:continue
                        command=buffer.decode('ascii','replace').strip();buffer.clear()
                        if command.upper()=='PING':self.send(client,'PONG // GIZMO UPLINK AKTIV')
                        elif command.upper()=='STATUS':
                            count=self.lab.memory.db.execute("SELECT (SELECT COUNT(*) FROM memories WHERE status='active')+(SELECT COUNT(*) FROM relations WHERE status='active')").fetchone()[0]
                            self.send(client,f'FACTS: {min(count,255)}')
                        elif command and not self.answer(client,command):return
                    elif len(buffer)<256:buffer.append(byte)
                    else:buffer.clear();self.send(client,'EINGABE ZU LANG')
        except OSError:pass
        finally:
            with self.lock:
                self.clients.discard(client);self.workers.discard(threading.current_thread())
                if not self.stop_event.is_set():
                    self.state='connected' if self.clients else 'disconnected'
                    self.last_disconnect=datetime.now().isoformat(timespec='seconds')
            client.close()


class Lab:
    def __init__(self, config=None, data=None, opener=None, runner=None, personality_file=None):
        self.data = Path(data) if data else private_dir()
        self.config = config or load_config(self.data)
        expected = Path(personality_file) if personality_file else self.data / 'GIZMO_Awakening_V2_EN.txt'
        if personality_file and not expected.is_file():
            raise FileNotFoundError(f'Persoenlichkeitsprofil fehlt: {expected}')
        if expected.is_file():
            personality=expected
            self.personality_warning=None
        elif (self.data/'personality.txt').is_file():
            personality=self.data/'personality.txt'
            self.personality_warning=f'Englisches Profil fehlt: {expected}. Aktiv: {personality}.'
        else:
            personality=ROOT/'personality.example.txt'
            self.personality_warning=f'Persönlichkeitsprofil fehlt: {expected}. Nur mitgelieferte Standardpersönlichkeit aktiv: {personality}.'
        self.personality = personality.read_text(encoding='utf-8')
        self.personality_path = personality.resolve()
        self.expected_personality_path = expected.resolve()
        self.profile_sha256 = hashlib.sha256(self.personality.encode('utf-8')).hexdigest()
        self.opener = opener or urllib.request.urlopen
        self.runner = runner or subprocess.run
        self.stop_event = threading.Event()
        self.chat_done = threading.Event()
        self.chat_done.set()
        self.lock = threading.RLock()
        self.chat_lock = threading.Lock()
        self.process = None
        self.active_response = None
        self.context = []
        self.memory = Memory(self.data / 'memory.sqlite3')
        self.analyzer = None
        self.uplink = None
        self.previous_message_at = self.memory.last_message_time()
        self.session_started = utc_now()
        self.conversation_id = self.memory.conversation(self.memory.latest_conversation())
        self.last_diagnostics = {}
        self.model = None
        self.ollama_ready = False
        self.preload_s = None

    def request(self, endpoint, payload=None, timeout=5):
        url = self.config.get('ollama_url', 'http://localhost:11434').rstrip('/') + endpoint
        request = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8') if payload is not None else None,
                                         headers={'Content-Type': 'application/json'})
        return self.opener(request, timeout=timeout)

    def ready(self):
        try:
            with self.request('/api/tags', timeout=2) as response:
                json.load(response)
            return True
        except (OSError, ValueError):
            return False

    def start(self):
        if self.stop_event.is_set():
            raise RuntimeError('GIZMO LAB wird beendet')
        if not self.ready():
            print('[.] Starte Ollama...', flush=True)
            flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
            process = subprocess.Popen(['ollama', 'serve'], creationflags=flags,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with self.lock:
                self.process = process
                if self.stop_event.is_set():
                    process.terminate()
                    raise RuntimeError('Start abgebrochen')
            for _ in range(120):
                if self.stop_event.wait(.25):
                    raise RuntimeError('Start abgebrochen')
                if self.ready():
                    break
            else:
                raise RuntimeError('Ollama wurde nicht bereit')
        print('[+] Ollama bereit', flush=True)
        self.ollama_ready = True
        self.preload(self.config.get('model', DEFAULT_MODEL))
        self.analyzer = Analyzer(self.memory.path,self.config,self.opener)
        self.analyzer.start()
        if self.config.get('uplink_enabled'):
            self.start_uplink()

    def start_uplink(self):
        if self.uplink and self.uplink.running:return self.uplink
        self.uplink=Uplink(self,host=self.config.get('uplink_host','auto'),port=int(self.config.get('uplink_port',6464)))
        self.uplink.start()
        return self.uplink

    def stop_uplink(self):
        if self.uplink:self.uplink.stop()
        self.uplink=None

    def preload(self, model):
        if self.stop_event.is_set():
            raise RuntimeError('Modellladen abgebrochen')
        print(f'[.] Lade Modell {model}...', flush=True)
        started = time.perf_counter()
        try:
            with self.request('/api/generate', {'model': model, 'prompt': '', 'stream': False,
                                                'keep_alive': self.config.get('keep_alive', -1)}, timeout=120) as response:
                self.active_response = response
                try:
                    result = json.load(response)
                finally:
                    self.active_response = None
        except (OSError, ValueError) as error:
            if self.stop_event.is_set():
                raise RuntimeError('Modellladen abgebrochen') from error
            raise
        if result.get('error'):
            raise RuntimeError(result['error'])
        if self.stop_event.is_set():
            raise RuntimeError('Modellladen abgebrochen')
        self.model = model
        self.preload_s = time.perf_counter() - started
        print('[+] Modell vorgeladen', flush=True)

    def unload(self, model):
        with self.request('/api/generate', {'model': model, 'prompt': '',
                                            'stream': False, 'keep_alive': 0}, timeout=30) as response:
            result = json.load(response)
        if result.get('error'):
            raise RuntimeError(result['error'])
        if self.model == model:
            self.model = None

    def switch_model(self, model):
        with self.chat_lock:
            if self.analyzer:self.analyzer.pause()
            try:
                if model == self.model:return
                if self.model:self.unload(self.model)
                self.preload(model)
                self.config['model']=model
            finally:
                if self.analyzer:self.analyzer.resume()

    def chat(self, prompt, context=None, on_text=None, model=None, origin='terminal'):
        with self.chat_lock:
            with self.lock:
                if self.stop_event.is_set():raise RuntimeError('GIZMO LAB wird beendet')
                self.chat_done.clear()
            try:return self._chat(prompt,context,on_text,model,origin)
            finally:self.chat_done.set()

    def _chat(self, prompt, context=None, on_text=None, model=None, origin='terminal'):
        if self.analyzer:
            self.analyzer.pause()
        model = model or self.model or self.config.get('model', DEFAULT_MODEL)
        elapsed_since_previous = (datetime.fromisoformat(utc_now()) - datetime.fromisoformat(self.previous_message_at)).total_seconds() if self.previous_message_at else None
        clock = f"Aktuelle UTC-Zeit: {utc_now()}. Sitzungsbeginn: {self.session_started}. Letzte Nachricht vor Sitzungsbeginn: {self.previous_message_at or 'keine'}. Vergangene Sekunden seitdem: {elapsed_since_previous if elapsed_since_previous is not None else 'unbekannt'}. Behaupte keine Aktivitaeten waehrend ausgeschalteter Sitzungen."
        try:
            history=self.memory.dialog_history(self.conversation_id) if context is None else list(context)
            retrieve=self.memory.retrieve if context is None else lambda *_:([],0)
            messages,retrieved,budget=assemble_context(self.personality,clock,prompt,history,retrieve,self.config)
        except Exception:
            if self.analyzer: self.analyzer.resume()
            raise
        retrieval_s=budget['retrieval_s']
        self.last_diagnostics = {'messages':messages,'retrieved':retrieved,'retrieval_s':retrieval_s,
                                 'context_chars':sum(len(message['content']) for message in messages),'budget':budget,
                                 'memory_selection':getattr(self.memory,'last_retrieval',{})}
        source_id = self.memory.add_message(self.conversation_id,'user',prompt,origin=origin) if context is None else None
        options = {key: self.config[key] for key in OPTIONS if self.config.get(key) is not None}
        options.setdefault('num_ctx',8192)
        options.setdefault('num_predict',768)
        payload = {'model': model, 'messages': messages, 'stream': True,
                   'keep_alive': self.config.get('keep_alive', -1), 'options': options,
                   'think': self.config.get('think', False)}
        started = time.perf_counter()
        first = None
        output = []
        metrics = {}
        aborted = 'completed'
        hiding = False
        pending = ''
        try:
            with self.request('/api/chat', payload, timeout=120) as response:
                self.active_response = response
                for raw in response:
                    if self.stop_event.is_set():
                        aborted = 'cancelled'
                        break
                    event = json.loads(raw)
                    if event.get('error'):
                        raise RuntimeError(event['error'])
                    chunk = event.get('message', {}).get('content', '')
                    pending += chunk
                    visible = ''
                    while pending:
                        if hiding:
                            end = pending.lower().find('</think>')
                            if end < 0:
                                pending = pending[-7:]
                                break
                            pending = pending[end + 8:]
                            hiding = False
                        else:
                            start = pending.lower().find('<think>')
                            if start >= 0:
                                visible += pending[:start]
                                pending = pending[start + 7:]
                                hiding = True
                            else:
                                safe = max(0, len(pending) - 6)
                                visible += pending[:safe]
                                pending = pending[safe:]
                                break
                    if visible:
                        if first is None:
                            first = time.perf_counter() - started
                        output.append(visible)
                        if on_text:
                            on_text(visible)
                    if event.get('done'):
                        metrics = event
                        break
                self.active_response = None
            if pending and not hiding and not self.stop_event.is_set():
                output.append(pending)
                if on_text:
                    on_text(pending)
        except (OSError, ValueError, RuntimeError) as error:
            aborted = f'error: {error}'
            if self.stop_event.is_set():
                aborted = 'cancelled'
        finally:
            self.active_response = None
        elapsed = time.perf_counter() - started
        text = ''.join(output)
        extraction_s = 0
        if context is None:
            if text and aborted=='completed':
                self.memory.add_message(self.conversation_id,'assistant',text,origin=origin)
            extraction_started=time.perf_counter()
            self.memory.extract_user(prompt,source_id)
            self.memory.enqueue(source_id)
            extraction_s=time.perf_counter()-extraction_started
            self.context = self.memory.recent(self.conversation_id,20)
        if self.analyzer and not self.stop_event.is_set():
            self.analyzer.resume()
        self.last_diagnostics['extraction_s']=extraction_s
        self.last_diagnostics['analysis_s']=self.analyzer.last_duration_s if self.analyzer else 0
        self.last_diagnostics['analysis_jobs']=self.memory.job_counts()
        speed = metrics.get('eval_count', 0) * 1e9 / metrics.get('eval_duration', 0) if metrics.get('eval_duration') else 0
        return {'model': model, 'options': options, 'personality_sha256': self.profile_sha256,
                'memory_retrieval_s':retrieval_s,'memory_extraction_s':extraction_s,
                'first_text_s': first, 'total_s': elapsed,
                'prompt_tokens': metrics.get('prompt_eval_count'), 'generated_tokens': metrics.get('eval_count'),
                'tokens_per_s': speed, 'abort_reason': aborted, 'answer': text,
                'ollama_metrics': {key: metrics.get(key) for key in ('load_duration', 'prompt_eval_duration', 'eval_duration', 'total_duration')}}

    def stop(self):
        with self.lock:
            if self.stop_event.is_set():
                return
            self.stop_event.set()
            if self.uplink:self.uplink.stop()
            if self.analyzer:
                self.analyzer.stop()
            response = self.active_response
            if response:
                try:
                    response.close()
                except OSError:
                    pass
            # Chat owns message persistence; do not close SQLite underneath it.
            self.chat_done.wait(timeout=15)
            if os.name == 'nt':
                for image in ('ollama app.exe', 'ollama.exe', 'ollama_llama_server.exe'):
                    try:
                        self.runner(['taskkill', '/F', '/T', '/IM', image], capture_output=True, check=False, timeout=10)
                    except (OSError, subprocess.TimeoutExpired) as error:
                        print(f'[!] Prozessabschluss {image}: {error}', flush=True)
                for _ in range(3):
                    try:
                        listing = self.runner(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True, timeout=10)
                    except (OSError, subprocess.TimeoutExpired) as error:
                        print(f'[!] Prozesspruefung fehlgeschlagen: {error}', flush=True)
                        break
                    names = [line for line in listing.stdout.splitlines() if 'ollama' in line.lower()]
                    if not names:
                        break
                    for line in names:
                        parts = next(__import__('csv').reader([line]))
                        if len(parts) > 1:
                            try:
                                self.runner(['taskkill', '/F', '/T', '/PID', parts[1]], capture_output=True, timeout=10)
                            except (OSError, subprocess.TimeoutExpired) as error:
                                print(f'[!] Prozessabschluss PID {parts[1]}: {error}', flush=True)
                else:
                    print('[!] Ollama-Prozesse noch sichtbar', flush=True)
            elif self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            if self.analyzer:
                self.analyzer.stop()
            print('[+] GIZMO LAB beendet', flush=True)
            self.ollama_ready = False
            self.memory.close()


def run_benchmark(lab, questions, variants, destination):
    results = []
    base_config = dict(lab.config)
    for variant in variants:
        lab.config = {**base_config, **variant.get('options', {})}
        model = variant.get('model', lab.config.get('model', DEFAULT_MODEL))
        mode = variant.get('start', 'warm')
        if mode not in ('cold', 'warm'):
            raise ValueError('start muss cold oder warm sein')
        if lab.model and lab.model != model:
            lab.unload(lab.model)
        if mode == 'cold':
            lab.unload(model)
            preload_s = None
        else:
            already_loaded = lab.model == model
            lab.switch_model(model)
            preload_s = None if already_loaded else lab.preload_s
        first_request = True
        for case in questions:
            context = []
            for prompt in case['turns']:
                record = lab.chat(prompt, context=context, model=model)
                cold = mode == 'cold' and first_request
                record.update({'case': case['id'], 'prompt': prompt, 'cold_model_start': cold,
                               'start_mode': 'cold' if cold else 'warm',
                               'preload_s': preload_s if first_request else None,
                               'variant': variant})
                results.append(record)
                context.extend([{'role': 'user', 'content': prompt}, {'role': 'assistant', 'content': record['answer']}])
                first_request = False
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    json_path = destination / f'benchmark-{stamp}.json'
    md_path = destination / f'benchmark-{stamp}.md'
    json_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    with md_path.open('w', encoding='utf-8') as report:
        report.write('# GIZMO LAB Benchmark\n\n')
        for item in results:
            report.write(f"## {item['case']} · {item['model']}\n\n")
            report.write(f"Konfiguration: `{json.dumps(item['variant'], ensure_ascii=False)}`  \n")
            report.write(f"Start: {item['start_mode']} · Vorladen: {item['preload_s']} s · Erstes Zeichen: {item['first_text_s']} s · Gesamt: {item['total_s']:.3f} s  \n")
            report.write(f"Profil-SHA256: `{item['personality_sha256']}`  \n")
            report.write(f"Prompt-Tokens: {item['prompt_tokens']} · Antwort-Tokens: {item['generated_tokens']} · Tempo: {item['tokens_per_s']:.2f} Token/s · Abbruch: {item['abort_reason']}\n\n")
            report.write(f"**Frage:** {item['prompt']}\n\n**Antwort:** {item['answer']}\n\n")
    return json_path, md_path


def run_gui(screenshot=None, qa_report=None):
    """Qt presentation layer. LAB remains the sole owner of model and memory work."""
    diagnostic=os.environ.get('GIZMO_GUI_LOG',os.devnull)
    if sys.stdout is None:sys.stdout=open(diagnostic,'a',encoding='utf-8')
    if sys.stderr is None:sys.stderr=open(diagnostic,'a',encoding='utf-8')
    from PySide6.QtCore import Qt, QTimer, Signal, QObject, QProcess, QUrl
    from PySide6.QtGui import QColor, QPainter, QPen, QTextCursor
    from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import (QApplication, QWidget, QMainWindow, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QFrame, QStackedWidget, QTextEdit, QLineEdit, QComboBox, QCheckBox,
        QGridLayout, QMessageBox, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
        QFormLayout, QDoubleSpinBox, QSpinBox, QFileDialog, QInputDialog)

    class Pulse(QWidget):
        def __init__(self, parent=None):
            super().__init__(parent); self.phase=0; self.active=False; self.setFixedSize(76,76)
            self.timer=QTimer(self); self.timer.timeout.connect(self.advance); self.timer.start(100)
        def advance(self):
            if self.active: self.phase=(self.phase+1)%30; self.update()
        def paintEvent(self, event):
            p=QPainter(self); p.setRenderHint(QPainter.Antialiasing)
            c=QColor('#9bd6b8' if self.active else '#5a7871')
            p.setPen(QPen(c,1)); p.drawEllipse(8,8,60,60)
            p.setPen(QPen(c,2)); p.drawEllipse(18,18,40,40)
            p.setBrush(QColor('#a9e1c3' if self.active else '#536e66')); p.setPen(Qt.NoPen)
            radius=10+(self.phase//6 if self.active else 0); p.drawEllipse(38-radius,38-radius,2*radius,2*radius)
            p.setBrush(Qt.NoBrush); p.setPen(QPen(c,1))
            for i in range(12):
                p.save(); p.translate(38,38); p.rotate(i*30); p.drawLine(0,-34,0,-30); p.restore()

    class ActivityGraph(QWidget):
        def __init__(self,parent=None):
            super().__init__(parent);self.active=False;self.phase=0;self.setFixedHeight(138)
            self.timer=QTimer(self);self.timer.timeout.connect(self.advance);self.timer.start(120)
        def advance(self):
            if self.active:self.phase+=1;self.update()
        def paintEvent(self,event):
            p=QPainter(self);p.fillRect(self.rect(),QColor('#172021'))
            p.setPen(QPen(QColor('#29463f'),1))
            for x in range(0,self.width(),48):p.drawLine(x,0,x,self.height())
            for y in range(0,self.height(),24):p.drawLine(0,y,self.width(),y)
            p.setRenderHint(QPainter.Antialiasing);p.setPen(QPen(QColor('#a4dfbd'),2.5))
            middle=self.height()//2;last=None
            for x in range(0,self.width()+6,6):
                position=(x//18+self.phase)%34
                spike={3:-16,4:19,5:-44,6:47,7:-23,8:14,13:-30,14:32,15:-55,16:58,17:-19,18:15,23:-23,24:30,25:-49,26:45,27:-18}.get(position,0) if self.active else 0
                current=(x,middle+spike)
                if last:p.drawLine(last[0],last[1],current[0],current[1])
                last=current

    class Task(QObject):
        chunk=Signal(str); done=Signal(object); failed=Signal(str)
        def __init__(self, action):
            super().__init__(); self.action=action
        def run(self):
            try: self.done.emit(self.action(self.chunk.emit))
            except Exception as error: self.failed.emit(str(error))

    class Window(QMainWindow):
        def __init__(self):
            super().__init__(); self.lab=None; self.busy=False; self.closing=False
            self.last_error=None
            self.pending_prompts=[]
            self.archive_page=0;self.archive_data_version=None
            self.shutdown_requested=threading.Event()
            self.thread=None; self.task=None; self.last_speed=None; self.last_time=None
            self.setWindowTitle('GIZMO // CENTRAL INTELLIGENCE CORE'); self.resize(850,960)
            self.setMinimumSize(800,820)
            self.setStyleSheet('''
                QMainWindow,QWidget#central {background:#222a2b}
                QWidget {color:#c5d9d1;font-family:Consolas,monospace;font-size:17px}
                QLabel {background:transparent}
                QFrame#panel {background:#1b2223;border:1px solid #3c5b53;border-radius:6px}
                QLabel#dim {color:#91b3a8;font-size:14px}
                QLabel#title {font-size:38px;font-weight:bold;letter-spacing:8px;color:#b9e4d1}
                QLabel#value {font-size:21px;font-weight:bold;color:#afe2c2}
                QPushButton {background:#2a4039;border:1px solid #53776b;border-radius:5px;padding:12px;color:#b9e4d1;font-size:16px}
                QPushButton:hover {background:#36594a} QPushButton:disabled {color:#74847e;background:#27312e}
                QPushButton#shutdown {background:#49312f;border-color:#80514d;color:#f0b4aa}
                QLineEdit,QTextEdit,QComboBox,QSpinBox,QDoubleSpinBox,QTableWidget {background:#151d1e;color:#c4dfd2;border:1px solid #456158;padding:6px;selection-background-color:#376251}
                QHeaderView::section {background:#2b3d39;color:#b4dbc5;padding:5px;border:0}
                QTabWidget::pane {border:1px solid #456158} QTabBar::tab {background:#273a35;padding:9px}
            ''')
            outer=QWidget();outer.setObjectName('central');self.setCentralWidget(outer); root=QVBoxLayout(outer); root.setContentsMargins(24,22,24,18);root.setSpacing(12)
            head=QHBoxLayout(); names=QVBoxLayout(); names.addWidget(self.label('GIZMO','title'))
            names.addWidget(self.label('CENTRAL INTELLIGENCE CORE','dim'));names.addWidget(self.label('STROMSCHLAG SYSTEMS // REV 0.1','dim'))
            head.addLayout(names);head.addStretch();self.pulse=Pulse();head.addWidget(self.pulse);root.addLayout(head)
            self.pages=QStackedWidget();root.addWidget(self.pages,1)
            self.home=QWidget();self.pages.addWidget(self.home);home=QVBoxLayout(self.home);home.setContentsMargins(0,8,0,0);home.setSpacing(11)
            grid=QGridLayout();grid.setSpacing(8);self.indicators={}
            for index,(key,title) in enumerate([('core','INTELLIGENCE CORE'),('ollama','OLLAMA'),('model','ACTIVE MODEL'),('memory','MEMORY ENGINE'),('c64','COMMODORE UPLINK'),('story','STORY DIRECTOR')]):
                box=self.panel();lay=QVBoxLayout(box);lay.addWidget(self.label(title,'dim'));value=self.label('OFFLINE','value');lay.addWidget(value)
                self.indicators[key]=value;grid.addWidget(box,index//2,index%2)
            home.addLayout(grid)
            self.uplink_detail=self.label('UPLINK // DISABLED','dim');self.uplink_detail.setWordWrap(True);home.addWidget(self.uplink_detail)
            monitor=self.panel();ml=QVBoxLayout(monitor);top=QHBoxLayout();top.addWidget(self.label('NEURAL ACTIVITY MONITOR','dim'));top.addStretch()
            self.activity=self.label('IDLE','dim');top.addWidget(self.activity);ml.addLayout(top)
            self.graph=ActivityGraph();ml.addWidget(self.graph)
            metrics=QGridLayout();self.metrics={}
            for index,(key,title) in enumerate([('gpu','GPU LOAD'),('vram','VRAM'),('speed','INFERENCE'),('latency','RESPONSE'),('memories','MEMORIES'),('jobs','PENDING ANALYSES')]):
                metrics.addWidget(self.label(title,'dim'),0,index%3) if index<3 else metrics.addWidget(self.label(title,'dim'),2,index%3)
                item=self.label('—','value');self.metrics[key]=item;metrics.addWidget(item,1 if index<3 else 3,index%3)
            ml.addLayout(metrics);home.addWidget(monitor)
            self.analysis_status=self.label('ANALYSIS // CORE OFFLINE','dim');self.analysis_status.setWordWrap(True);home.addWidget(self.analysis_status)
            self.log=QTextEdit();self.log.setReadOnly(True);self.log.setMinimumHeight(112);self.log.setMaximumHeight(136);home.addWidget(self.log)
            nav=QHBoxLayout()
            for name,action in [('MODEL LAB',self.open_model),('SETTINGS',self.open_settings),('ARCHIVE',self.open_archive)]:
                button=QPushButton(name);button.clicked.connect(action);nav.addWidget(button)
            home.addLayout(nav)
            actions=QHBoxLayout();self.start_button=QPushButton('◉  START CORE');self.start_button.clicked.connect(self.start_core)
            self.stop_button=QPushButton('⏻  SHUTDOWN');self.stop_button.setObjectName('shutdown');self.stop_button.clicked.connect(self.shutdown)
            actions.addWidget(self.start_button);actions.addWidget(self.stop_button);home.addLayout(actions)
            home.addWidget(self.label('GIZMO CONTROL CENTER // REV 0.1','dim'));home.addStretch(1)
            self.build_model_page();self.build_settings_page();self.build_archive_page()
            self.gpu_process=QProcess(self);self.gpu_process.finished.connect(self.gpu_finished)
            self.api_manager=QNetworkAccessManager(self);self.api_pending=False;self.external_ollama=False
            self.api_timer=QTimer(self);self.api_timer.timeout.connect(self.check_ollama_api);self.api_timer.start(3000)
            self.poller=QTimer(self);self.poller.timeout.connect(self.refresh_status);self.poller.start(1500)
            self.log_line('CONTROL CENTER READY // CORE OFFLINE')
            self.refresh_status()
            self.check_ollama_api()
        def label(self,text,role=None):
            item=QLabel(text)
            if role:item.setObjectName(role)
            return item
        def panel(self):
            box=QFrame();box.setObjectName('panel');return box
        def page(self,title):
            page=QWidget();layout=QVBoxLayout(page);layout.setSpacing(10);header=QHBoxLayout();back=QPushButton('← CONTROL CENTER');back.clicked.connect(lambda:self.pages.setCurrentIndex(0));header.addWidget(back);header.addStretch();header.addWidget(self.label(title,'value'));layout.addLayout(header);self.pages.addWidget(page);return layout
        def build_model_page(self):
            layout=self.page('MODEL LAB');self.chat_view=QTextEdit();self.chat_view.setReadOnly(True);layout.addWidget(self.chat_view,1)
            self.chat_view.setFocusPolicy(Qt.NoFocus)
            row=QHBoxLayout();self.model_select=QComboBox();self.model_select.setEditable(True);self.model_select.addItem(DEFAULT_MODEL)
            self.model_button=QPushButton('LOAD MODEL');self.model_button.clicked.connect(self.switch_model)
            row.addWidget(self.model_select,1);row.addWidget(self.model_button);layout.addLayout(row)
            row=QHBoxLayout();self.prompt=QLineEdit();self.prompt.setPlaceholderText('Speak to GIZMO…');self.prompt.returnPressed.connect(self.send)
            self.send_button=QPushButton('SEND');self.send_button.clicked.connect(self.send);row.addWidget(self.prompt,1);row.addWidget(self.send_button);layout.addLayout(row)
            self.chat_status=self.label('CORE OFFLINE','dim');layout.addWidget(self.chat_status)
        def build_settings_page(self):
            layout=self.page('SETTINGS');form=QFormLayout();self.settings_fields={}
            for key,minimum,maximum in [('temperature',0,2),('top_p',0,1),('min_p',0,1),('repeat_penalty',0,3)]:
                spin=QDoubleSpinBox();spin.setRange(minimum,maximum);spin.setDecimals(2);spin.setSingleStep(.05);self.settings_fields[key]=spin;form.addRow(key.upper(),spin)
            for key,minimum,maximum in [('num_ctx',1024,65536),('num_predict',32,8192),('top_k',0,500),('seed',0,2147483647)]:
                spin=QSpinBox();spin.setRange(minimum,maximum);self.settings_fields[key]=spin;form.addRow(key.upper(),spin)
            self.settings_fields['seed'].setMinimum(-1)
            self.settings_fields['seed'].setSpecialValueText('AUTO')
            layout.addLayout(form);self.profile_path=self.label('ACTIVE PROFILE // CORE OFFLINE','dim')
            self.profile_path.setWordWrap(True);self.profile_path.setTextInteractionFlags(Qt.TextSelectableByMouse)
            layout.addWidget(self.profile_path)
            self.profile_warning=self.label('','dim');self.profile_warning.setWordWrap(True)
            self.profile_warning.setStyleSheet('color:#edc27b;font-weight:bold')
            layout.addWidget(self.profile_warning)
            self.uplink_enabled=QCheckBox('ENABLE COMMODORE UPLINK WHEN CORE STARTS')
            layout.addWidget(self.uplink_enabled)
            self.uplink_host=QLineEdit();self.uplink_host.setPlaceholderText('auto (private LAN address)')
            form.addRow('UPLINK HOST',self.uplink_host)
            self.uplink_port=QSpinBox();self.uplink_port.setRange(1,65535);form.addRow('UPLINK PORT',self.uplink_port)
            profile_button=QPushButton('SELECT PERSONALITY FILE…');profile_button.clicked.connect(self.select_profile);layout.addWidget(profile_button)
            save=QPushButton('SAVE SETTINGS');save.clicked.connect(self.save_settings);layout.addWidget(save);layout.addStretch()
            layout.addWidget(self.label('Saved locally. Changes to model parameters take effect on the next request.','dim'))
        def build_archive_page(self):
            layout=self.page('ARCHIVE // LOCAL');self.archive_tabs=QTabWidget();self.tables={}
            self.archive_summary=self.label('ANALYSIS // CORE OFFLINE','dim');self.archive_summary.setWordWrap(True);layout.addWidget(self.archive_summary)
            search_row=QHBoxLayout();self.archive_search=QLineEdit();self.archive_search.setPlaceholderText('Search archive...')
            self.archive_search.textChanged.connect(self.reset_archive_page);search_row.addWidget(self.archive_search);layout.addLayout(search_row)
            for key,columns in [('memories',['ID','STATUS','DOMAIN','KEY','VALUE']),('entities',['ID','STATUS','KIND','NAME']),('relations',['ID','STATUS','SUBJECT','RELATION','TARGET','SOURCE']),('episodes',['ID','STATUS','DOMAIN','TITLE','TIME','TOPICS','SIGNIFICANCE','SOURCES']),('messages',['ID','ROLE','CONVERSATION','TEXT']),('jobs',['ID','STATUS','ATTEMPTS','CLAIMS','REJECTED','EMPTY REASON','ERROR'])]:
                table=QTableWidget(0,len(columns));table.setHorizontalHeaderLabels(columns);table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch);table.setEditTriggers(QTableWidget.NoEditTriggers)
                self.archive_tabs.addTab(table,key.upper());self.tables[key]=table
            self.inspector=QTextEdit();self.inspector.setReadOnly(True);self.archive_tabs.addTab(self.inspector,'MEMORY INSPECTOR')
            self.archive_tabs.currentChanged.connect(self.reset_archive_page)
            layout.addWidget(self.archive_tabs,1)
            navigation=QHBoxLayout();previous=QPushButton('PREVIOUS');previous.clicked.connect(lambda:self.move_archive_page(-1))
            following=QPushButton('NEXT');following.clicked.connect(lambda:self.move_archive_page(1))
            self.archive_page_label=self.label('PAGE 1','dim');navigation.addWidget(previous);navigation.addWidget(self.archive_page_label);navigation.addWidget(following);layout.addLayout(navigation)
            row=QHBoxLayout();refresh=QPushButton('REFRESH');refresh.clicked.connect(self.refresh_archive)
            edit=QPushButton('CORRECT MEMORY');edit.clicked.connect(self.correct_memory)
            delete=QPushButton('DELETE MEMORY');delete.setObjectName('shutdown');delete.clicked.connect(self.delete_memory)
            approve=QPushButton('APPROVE RELATION');approve.clicked.connect(lambda:self.change_relation('active'))
            correct_relation=QPushButton('CORRECT PROPERTY');correct_relation.clicked.connect(self.correct_property)
            remove_relation=QPushButton('DELETE RELATION');remove_relation.setObjectName('shutdown');remove_relation.clicked.connect(lambda:self.change_relation('deleted'))
            retry_job=QPushButton('RETRY FAILED JOB');retry_job.clicked.connect(self.retry_selected_job)
            correct_episode=QPushButton('CORRECT EPISODE TITLE');correct_episode.clicked.connect(self.correct_episode)
            delete_episode=QPushButton('DELETE EPISODE');delete_episode.setObjectName('shutdown');delete_episode.clicked.connect(self.delete_episode)
            row.addWidget(refresh);row.addWidget(edit);row.addWidget(delete);layout.addLayout(row)
            relations_row=QHBoxLayout();relations_row.addWidget(approve);relations_row.addWidget(correct_relation);relations_row.addWidget(remove_relation);layout.addLayout(relations_row)
            layout.addWidget(retry_job)
            episodes_row=QHBoxLayout();episodes_row.addWidget(correct_episode);episodes_row.addWidget(delete_episode);layout.addLayout(episodes_row)
            layout.addWidget(self.label('Deletion requires confirmation. The archive stays on this PC.','dim'))
        def log_line(self,text):
            self.log.append(datetime.now().strftime('%H:%M:%S')+'  '+text)
        def set_busy(self,busy,activity='IDLE'):
            self.busy=busy;self.activity.setText(activity);self.pulse.active=busy or bool(self.lab and self.lab.model);self.graph.active=busy
            self.start_button.setEnabled(not busy and not self.lab);self.send_button.setEnabled(not busy and bool(self.lab and self.lab.model))
            self.model_button.setEnabled(not busy and bool(self.lab));self.prompt.setEnabled(bool(self.lab and self.lab.model) and not self.closing)
            if busy or not self.last_error:self.chat_status.setText(activity)
        def work(self,action,activity,on_done=None):
            if self.busy:return
            self.last_error=None
            self.set_busy(True,activity);self.log_line(activity)
            task=Task(action);thread=threading.Thread(target=task.run,daemon=True)
            def finish(result):
                self.log_line(activity+' // COMPLETE')
                if on_done:on_done(result)
                self.refresh_status()
            def fail(error):
                self.last_error=error
                self.log_line('ERROR // '+error);self.chat_status.setText(error)
                if not self.shutdown_requested.is_set() and not qa_report:QMessageBox.warning(self,'GIZMO',error)
                self.refresh_status()
            task.done.connect(finish);task.failed.connect(fail)
            task.done.connect(lambda _result:self.on_task_finished(thread))
            task.failed.connect(lambda _error:self.on_task_finished(thread))
            self.thread=thread;self.task=task;thread.start()
        def on_task_finished(self,thread):
            self.archive_data_version=None
            if self.thread is thread:self.thread=None;self.task=None
            if not self.closing:self.set_busy(False)
            if self.shutdown_requested.is_set() and self.lab and not self.closing:
                self.shutdown();return
            if getattr(self,'close_after_shutdown',False) and self.lab and not self.closing:
                self.shutdown();return
            if getattr(self,'close_after_shutdown',False) and self.lab is None and not self.closing:
                QTimer.singleShot(0,self.close)
            elif self.lab is None and not self.closing:self.shutdown_requested.clear()
            if self.pages.currentIndex()==1 and self.lab and self.lab.model and not self.closing:
                QTimer.singleShot(0,self.focus_prompt)
            if self.pending_prompts and self.lab and self.lab.model and not self.closing:
                QTimer.singleShot(0,self.send_queued)
        def start_core(self):
            def action(_emit):
                lab=Lab();self.lab=lab
                try:
                    if self.shutdown_requested.is_set():
                        raise RuntimeError('Start abgebrochen')
                    lab.start()
                    with lab.request('/api/tags') as response:
                        models=[item['name'] for item in json.load(response).get('models',[]) if item.get('name')]
                    return {'active':lab.model,'installed':models}
                except Exception:
                    lab.stop();self.lab=None;raise
            def done(result):
                self.model_select.clear();self.model_select.addItems(result['installed'])
                self.model_select.setCurrentText(result['active'])
                self.log_line('MODEL READY // '+result['active'])
                self.show_profile()
                if self.lab.personality_warning:
                    self.log_line('PROFILE WARNING // '+self.lab.personality_warning)
                    if not qa_report:QMessageBox.warning(self,'Personality profile missing',self.lab.personality_warning)
            self.work(action,'INITIALIZING CORE',done)
        def send(self):
            prompt=self.prompt.text().strip()
            if not prompt or not self.lab or not self.lab.model:return
            if self.busy:
                if self.activity.text()=='GENERATING RESPONSE':
                    self.pending_prompts.append(prompt)
                    self.prompt.clear()
                    self.log_line('MESSAGE QUEUED')
                    self.focus_prompt()
                return
            self.prompt.clear();self.send_prompt(prompt)
        def send_queued(self):
            if self.busy or not self.pending_prompts or not self.lab or self.closing:return
            self.send_prompt(self.pending_prompts.pop(0))
        def focus_prompt(self):
            if self.pages.currentIndex()==1 and self.prompt.isEnabled() and not self.closing:
                self.prompt.setFocus(Qt.OtherFocusReason)
        def append_chat(self,action):
            bar=self.chat_view.verticalScrollBar()
            follow=bar.value()>=bar.maximum()-3
            position=bar.value()
            action()
            bar.setValue(bar.maximum() if follow else position)
        def send_prompt(self,prompt):
            self.append_chat(lambda:self.chat_view.append('<span style="color:#e5c681">YOU &gt; '+self.escape(prompt)+'</span>'))
            self.append_chat(lambda:self.chat_view.append('<span style="color:#a9dec0">GIZMO &gt; </span>'))
            self.focus_prompt()
            def stream(chunk):
                def insert():
                    cursor=self.chat_view.textCursor()
                    cursor.movePosition(QTextCursor.End)
                    cursor.insertText(chunk)
                    self.chat_view.setTextCursor(cursor)
                self.append_chat(insert)
            def done(result):
                self.append_chat(lambda:self.chat_view.append(''))
                self.last_speed=result['tokens_per_s'];self.last_time=result['total_s']
                self.log_line(f"RESPONSE // {result['total_s']:.2f}s // {result['tokens_per_s']:.1f} t/s // {result['abort_reason']}")
                if result['abort_reason']!='completed' and not self.shutdown_requested.is_set():
                    self.last_error=result['abort_reason']
                    self.chat_status.setText('GENERATION ERROR // '+result['abort_reason'])
                    if not qa_report:QMessageBox.warning(self,'Generation failed',result['abort_reason'])
                self.focus_prompt()
            self.work(lambda emit:self.lab.chat(prompt,on_text=emit,origin='gui'),'GENERATING RESPONSE',done)
            self.task.chunk.connect(stream)
        @staticmethod
        def escape(value):
            import html
            return html.escape(value)
        def switch_model(self):
            if not self.lab:return
            model=self.model_select.currentText().strip()
            installed={self.model_select.itemText(index) for index in range(self.model_select.count())}
            if model and model not in installed:
                QMessageBox.warning(self,'Model not installed','Select an already installed model. No model will be downloaded.');return
            if model:
                def done(_result):
                    try:self.persist_config(self.lab.config)
                    except OSError as error:
                        self.log_line('SETTINGS SAVE ERROR // '+str(error))
                        QMessageBox.warning(self,'GIZMO','Model loaded, but the selection could not be saved: '+str(error))
                    self.log_line('ACTIVE MODEL // '+model)
                self.work(lambda _emit:self.lab.switch_model(model),'LOADING MODEL '+model,done)
        def open_model(self):
            self.pages.setCurrentIndex(1)
            self.focus_prompt()
            QTimer.singleShot(0,self.focus_prompt)
        def open_settings(self):
            if self.lab:
                for key,field in self.settings_fields.items():
                    value=self.lab.config.get(key)
                    number=-1 if key=='seed' and value is None else (value or 0)
                    field.setValue(int(number) if isinstance(field,QSpinBox) else float(number))
                self.uplink_enabled.setChecked(bool(self.lab.config.get('uplink_enabled',False)))
                self.uplink_host.setText(str(self.lab.config.get('uplink_host','auto')))
                self.uplink_port.setValue(int(self.lab.config.get('uplink_port',6464)))
            self.show_profile()
            self.pages.setCurrentIndex(2)
        def show_profile(self):
            if not self.lab:
                self.profile_path.setText('ACTIVE PROFILE // CORE OFFLINE')
                self.profile_warning.setText('')
                return
            path=self.lab.personality_path
            self.profile_path.setText('ACTIVE PROFILE // '+path.name+'\n'+str(path))
            self.profile_warning.setText('WARNING // '+self.lab.personality_warning if self.lab.personality_warning else '')
        def select_profile(self):
            filename,_=QFileDialog.getOpenFileName(self,'Select local personality profile','','Text files (*.txt);;All files (*)')
            if filename:self.selected_profile=filename;self.profile_path.setText('Selected: '+Path(filename).name)
        def save_settings(self):
            if not self.lab:
                QMessageBox.information(self,'GIZMO','Start the core before changing settings.');return
            if self.busy:return
            config=dict(self.lab.config)
            for key,field in self.settings_fields.items():config[key]=None if key=='seed' and field.value()==-1 else field.value()
            config['uplink_enabled']=self.uplink_enabled.isChecked()
            config['uplink_host']=self.uplink_host.text().strip() or 'auto'
            config['uplink_port']=self.uplink_port.value()
            if config['uplink_enabled']:
                try:uplink_bind_host(config['uplink_host'])
                except (OSError,ValueError,RuntimeError) as error:
                    QMessageBox.warning(self,'Uplink configuration',str(error));return
            if getattr(self,'selected_profile',None):
                if QMessageBox.question(self,'Confirm profile change','Replace the active local personality profile with the selected file?')!=QMessageBox.Yes:return
                source=Path(self.selected_profile);content=source.read_text(encoding='utf-8')
                target=self.lab.personality_path
                if not target.is_relative_to(self.lab.data.resolve()):
                    target=self.lab.data/'personality.txt'
                if target.exists():
                    import shutil
                    shutil.copy2(target,target.with_name(target.name+'.'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.bak'))
                target.write_text(content,encoding='utf-8')
                self.lab.personality=content;self.lab.personality_path=target.resolve()
                self.lab.personality_warning=(f'Englisches Profil fehlt: {self.lab.expected_personality_path}. Aktiv: {target}.'
                    if not self.lab.expected_personality_path.is_file() and target!=self.lab.expected_personality_path else None)
                self.lab.profile_sha256=hashlib.sha256(self.lab.personality.encode()).hexdigest()
                self.selected_profile=None
                self.show_profile()
            self.persist_config(config)
            prior=self.lab.uplink.status() if self.lab.uplink else None
            self.lab.config=config
            if not config['uplink_enabled']:self.lab.stop_uplink()
            elif not prior or prior['host']!=uplink_bind_host(config['uplink_host']) or prior['port']!=config['uplink_port'] or prior['state']=='error':
                self.lab.stop_uplink();self.lab.start_uplink()
            self.log_line('SETTINGS SAVED LOCALLY');self.refresh_status()
        def persist_config(self,config):
            config_path=self.lab.data/'config.json';temp=config_path.with_suffix('.tmp')
            temp.write_text(json.dumps(config,indent=2,ensure_ascii=False),encoding='utf-8');os.replace(temp,config_path)
        def open_archive(self):self.pages.setCurrentIndex(3);self.archive_data_version=None;self.refresh_archive()
        def reset_archive_page(self,*_args):
            self.archive_page=0;self.refresh_archive()
        def move_archive_page(self,step):
            self.archive_page=max(0,self.archive_page+step);self.refresh_archive()
        def refresh_archive(self):
            if not self.lab or self.busy:return
            memory=self.lab.memory
            summary=memory.analysis_summary()
            episodes=memory.episode_status()
            self.archive_summary.setText(self.format_analysis_summary(summary)+'\n'+self.format_embedding_summary(memory.embedding_status())+
                '\nEPISODES // ACTIVE '+str(episodes.get('active',0))+'  REMAINING '+str(episodes.get('remaining',0)))
            if self.archive_tabs.currentIndex()>=len(self.tables):
                self.refresh_inspector();self.archive_data_version=memory.db.execute('PRAGMA data_version').fetchone()[0];return
            key=list(self.tables)[self.archive_tabs.currentIndex()]
            if key=='episodes':
                term=self.archive_search.text().strip().casefold()
                where=" WHERE lower(title) LIKE ? OR lower(summary) LIKE ?" if term else ''
                args=['%'+term+'%']*2 if term else []
                total=memory.db.execute('SELECT COUNT(*) FROM episodes'+where,args).fetchone()[0]
                pages=max(1,(total+99)//100);self.archive_page=min(self.archive_page,pages-1)
                rows=memory.db.execute('SELECT id FROM episodes'+where+' ORDER BY id DESC LIMIT 100 OFFSET ?',args+[self.archive_page*100]).fetchall()
                shown=[memory.episode_display(row['id']) for row in rows]
                shown=[item for item in shown if item and (not term or term in (item['title']+' '+item['summary']).casefold())]
                table=self.tables[key];table.setRowCount(len(shown))
                for i,item in enumerate(shown):
                    for j,value in enumerate((item['id'],item['status'],item['domain'],item['title'],item['started_at'],item['topics'],item['significance'] or '',','.join(map(str,item['sources'])))):
                        table.setItem(i,j,QTableWidgetItem(str(value)))
                self.archive_page_label.setText(f'PAGE {self.archive_page+1} / {pages}  //  {total} RECORDS')
                self.archive_data_version=memory.db.execute('PRAGMA data_version').fetchone()[0]
                return
            queries={
                'memories':('memories','id,status,domain,key,value','status,domain,key,value'),
                'entities':('entities','id,status,kind,name','status,kind,name'),
                'relations':('relations r JOIN entities s ON s.id=r.subject_id LEFT JOIN entities o ON o.id=r.object_id',
                    "r.id,r.status,s.name,CASE WHEN r.property_key<>'' THEN r.property_key ELSE r.predicate END,COALESCE(o.name,r.value,''),r.source_message_id",
                    'r.status,s.name,r.predicate,r.property_key,o.name,r.value,r.evidence'),
                'messages':('messages','id,role,conversation_id,text','role,conversation_id,text'),
                'jobs':('analysis_jobs',"id,status,attempts,COALESCE(claim_count,''),COALESCE(rejected_count,''),COALESCE(empty_reason,''),COALESCE(error,'')",'status,error,empty_reason')}
            source,columns,search_columns=queries[key]
            term=self.archive_search.text().strip()
            fields=search_columns.split(',')
            where=' WHERE ('+' OR '.join('COALESCE('+field+",'') LIKE ?" for field in fields)+')' if term else ''
            args=['%'+term+'%']*len(fields) if term else []
            total=memory.db.execute('SELECT COUNT(*) FROM '+source+where,args).fetchone()[0]
            pages=max(1,(total+99)//100);self.archive_page=min(self.archive_page,pages-1)
            rows=memory.db.execute('SELECT '+columns+' FROM '+source+where+' ORDER BY '+('r.id' if key=='relations' else 'id')+' DESC LIMIT 100 OFFSET ?',args+[self.archive_page*100]).fetchall()
            table=self.tables[key];table.setRowCount(len(rows))
            for i,row in enumerate(rows):
                for j,value in enumerate(row):table.setItem(i,j,QTableWidgetItem(str(value if value is not None else '')))
            self.archive_page_label.setText(f'PAGE {self.archive_page+1} / {pages}  //  {total} RECORDS')
            self.archive_data_version=memory.db.execute('PRAGMA data_version').fetchone()[0]
        @staticmethod
        def format_analysis_summary(counts):
            return ('ANALYSIS // PENDING {pending}  PROCESSING {processing}  COMPLETED {done}  FAILED {failed}\n'
                    'UNRESOLVED CLAIMS {unresolved}  COMPLETED WITHOUT CLAIMS {empty}').format(**{
                        key:counts.get(key,0) for key in ('pending','processing','done','failed','unresolved','empty')})
        @staticmethod
        def format_embedding_summary(counts):
            state='CPU READY' if counts.get('model_ready') and not counts.get('error') else 'UNAVAILABLE'
            return ('ORIGINAL ARCHIVE // FTS READY  E5 '+state+'  INDEXED '+str(counts.get('done',0))+
                    '  PENDING '+str(counts.get('pending',0))+'  FAILED '+str(counts.get('failed',0)))
        def refresh_inspector(self):
            if not self.lab:return
            diagnostics=self.lab.last_diagnostics
            if not diagnostics:
                self.inspector.setPlainText('No answer has been generated in this session.');return
            selection=diagnostics.get('memory_selection',{})
            delivered=[item['content'] for item in diagnostics.get('messages',[]) if item['role']=='system' and item['content'].startswith('Local memory:')]
            details={'budget':diagnostics.get('budget',{}),'episode_index':self.lab.memory.episode_status(),'candidate_count':selection.get('candidate_count',0),
                'found_candidates':selection.get('candidates',[]),'selected_with_sources':selection.get('selected_details',[]),
                'excluded_with_reasons':selection.get('excluded',[]),
                'exact_memory_payload':delivered}
            self.inspector.setPlainText(json.dumps(details,ensure_ascii=False,indent=2))
        def retry_selected_job(self):
            if not self.lab or self.busy:return
            table=self.tables['jobs'];row=table.currentRow()
            if row<0 or table.item(row,1).text()!='failed':return
            ident=int(table.item(row,0).text())
            if QMessageBox.question(self,'Retry analysis',f'Retry failed analysis job #{ident}?')!=QMessageBox.Yes:return
            if self.lab.memory.retry_job(ident):
                self.refresh_archive();self.log_line(f'ANALYSIS JOB #{ident} RETRIED')
        def correct_episode(self):
            if not self.lab or self.busy:return
            table=self.tables['episodes'];row=table.currentRow()
            if row<0:return
            ident=int(table.item(row,0).text());old=table.item(row,3).text()
            value,accepted=QInputDialog.getText(self,'Correct episode title','Grounded title:',text=old)
            if not accepted or not value.strip() or value.strip()==old:return
            if QMessageBox.question(self,'Confirm episode title',f'Correct title of episode #{ident}?')!=QMessageBox.Yes:return
            self.lab.memory.correct_episode_title(ident,value);self.refresh_archive()
        def delete_episode(self):
            if not self.lab or self.busy:return
            table=self.tables['episodes'];row=table.currentRow()
            if row<0:return
            ident=int(table.item(row,0).text())
            if QMessageBox.question(self,'Confirm episode deletion',f'Delete episode #{ident}? Original conversation remains stored.')!=QMessageBox.Yes:return
            self.lab.memory.delete_episode(ident);self.refresh_archive()
        def correct_property(self):
            if not self.lab or self.busy:return
            table=self.tables['relations'];row=table.currentRow()
            if row<0:return
            ident=int(table.item(row,0).text())
            record=self.lab.memory.db.execute('SELECT predicate,value FROM relations WHERE id=?',(ident,)).fetchone()
            if not record or record['predicate']!='attribute':
                QMessageBox.information(self,'Correct property','Select an attribute relation first.');return
            value,accepted=QInputDialog.getText(self,'Correct property','Confirmed value:',text=record['value'] or '')
            if not accepted or not value.strip() or value.strip()==record['value']:return
            if QMessageBox.question(self,'Confirm correction',f'Correct property #{ident}? The previous value will be recorded.')!=QMessageBox.Yes:return
            self.lab.memory.correct_relation(ident,value.strip());self.refresh_archive()
        def delete_memory(self):
            if not self.lab or self.busy:return
            table=self.tables['memories'];row=table.currentRow()
            if row<0:return
            ident=int(table.item(row,0).text())
            if QMessageBox.question(self,'Confirm deletion',f'Delete memory #{ident}? This action will be recorded and cannot be undone automatically.')!=QMessageBox.Yes:return
            self.lab.memory.delete(ident);self.refresh_archive();self.log_line(f'MEMORY #{ident} DELETED')
        def correct_memory(self):
            if not self.lab or self.busy:return
            table=self.tables['memories'];row=table.currentRow()
            if row<0:return
            ident=int(table.item(row,0).text());old=table.item(row,4).text()
            value,accepted=QInputDialog.getText(self,'Correct memory','Confirmed value:',text=old)
            if not accepted or not value.strip() or value==old:return
            if QMessageBox.question(self,'Confirm correction',f'Correct memory #{ident}? The previous value will be recorded.')!=QMessageBox.Yes:return
            self.lab.memory.correct(ident,value.strip());self.refresh_archive();self.log_line(f'MEMORY #{ident} CORRECTED')
        def change_relation(self,status):
            if not self.lab or self.busy:return
            table=self.tables['relations'];row=table.currentRow()
            if row<0:return
            ident=int(table.item(row,0).text())
            if QMessageBox.question(self,'Confirm relation change',f'Set relation #{ident} to {status.upper()}?')!=QMessageBox.Yes:return
            self.lab.memory.set_relation_status(ident,status);self.refresh_archive();self.log_line(f'RELATION #{ident} {status.upper()}')
        def refresh_status(self):
            active=bool(self.lab and self.lab.model and not self.lab.stop_event.is_set())
            self.indicators['core'].setText('ONLINE' if active else ('STARTING' if self.busy and self.lab else 'OFFLINE'))
            self.indicators['ollama'].setText('CONNECTED' if self.lab and self.lab.ollama_ready else ('AVAILABLE' if self.external_ollama else 'OFFLINE'))
            self.indicators['model'].setText(self.lab.model if active else 'NOT LOADED')
            self.indicators['memory'].setText('ACTIVE' if active else ('MOUNTED' if self.lab else 'OFFLINE'))
            uplink=self.lab.uplink.status() if self.lab and self.lab.uplink else {'state':'disabled','host':None,'port':None,'error':None,'clients':0}
            self.indicators['c64'].setText(uplink['state'].upper())
            endpoint=f"{uplink['host']}:{uplink['port']}" if uplink['host'] else 'OFF'
            self.uplink_detail.setText('UPLINK // '+uplink['state'].upper()+'  '+endpoint+('  ERROR: '+uplink['error'] if uplink['error'] else ''))
            self.indicators['story'].setText('NOT INSTALLED')
            if active and not self.busy:
                try:
                    self.metrics['memories'].setText(str(self.lab.memory.db.execute("SELECT (SELECT COUNT(*) FROM memories WHERE status='active')+(SELECT COUNT(*) FROM relations WHERE status='active')").fetchone()[0]))
                    summary=self.lab.memory.analysis_summary()
                    self.metrics['jobs'].setText(str(summary.get('pending',0)))
                    self.analysis_status.setText(self.format_analysis_summary(summary)+'\n'+self.format_embedding_summary(self.lab.memory.embedding_status()))
                except Exception:self.metrics['memories'].setText('—');self.metrics['jobs'].setText('—')
            else:
                self.metrics['memories'].setText('—');self.metrics['jobs'].setText('—')
                if not self.lab:self.analysis_status.setText('ANALYSIS // CORE OFFLINE')
            self.metrics['speed'].setText(f'{self.last_speed:.1f} t/s' if self.last_speed is not None else '—')
            self.metrics['latency'].setText(f'{self.last_time:.2f} s' if self.last_time is not None else '—')
            if self.gpu_process.state()==QProcess.NotRunning:
                self.gpu_process.start('nvidia-smi',['--query-gpu=utilization.gpu,memory.used,memory.total','--format=csv,noheader,nounits'])
            self.pulse.active=active or self.busy
            self.graph.active=self.busy
            if self.pages.currentIndex()==3 and self.lab and not self.busy:
                try:
                    version=self.lab.memory.db.execute('PRAGMA data_version').fetchone()[0]
                    if self.archive_data_version is None or version!=self.archive_data_version:self.refresh_archive()
                except Exception:pass
        def check_ollama_api(self):
            if self.api_pending:return
            self.api_pending=True
            url=self.lab.config.get('ollama_url','http://127.0.0.1:11434') if self.lab else 'http://127.0.0.1:11434'
            reply=self.api_manager.get(QNetworkRequest(QUrl(url.rstrip('/')+'/api/tags')))
            def finished():
                self.external_ollama=reply.error()==QNetworkReply.NoError
                self.api_pending=False;reply.deleteLater()
                if not self.lab:self.indicators['ollama'].setText('AVAILABLE' if self.external_ollama else 'OFFLINE')
            reply.finished.connect(finished)
        def gpu_finished(self,_exit_code,_status):
            try:
                output=bytes(self.gpu_process.readAllStandardOutput()).decode('utf-8')
                values=[int(v.strip()) for v in output.splitlines()[0].split(',')]
                self.metrics['gpu'].setText(f'{values[0]} %')
                self.metrics['vram'].setText(f'{values[1]/1024:.1f} / {values[2]/1024:.1f} GB')
            except (ValueError,IndexError):
                self.metrics['gpu'].setText('—');self.metrics['vram'].setText('—')
        def shutdown(self):
            if self.closing:return
            self.shutdown_requested.set()
            self.closing=True;self.log_line('STUDIO-SAFE SHUTDOWN REQUESTED');self.activity.setText('SHUTTING DOWN')
            stopped={'value':False}
            def terminate():
                if self.lab:self.lab.stop()
                listing=subprocess.run(['tasklist','/FO','CSV','/NH'],capture_output=True,text=True,timeout=10)
                stopped['value']=not any('ollama' in line.lower() for line in listing.stdout.splitlines())
            def end():
                self.lab=None;self.closing=False;self.last_error=None;self.set_busy(False,'IDLE');self.refresh_status()
                self.log_line('OLLAMA STOPPED // CORE OFFLINE' if stopped['value'] else 'WARNING // OLLAMA STILL RUNNING')
                if getattr(self,'log_shutdown_error',None):self.log_line('SHUTDOWN ERROR // '+self.log_shutdown_error)
                if not self.close_after_shutdown and not (self.thread and self.thread.is_alive()):self.shutdown_requested.clear()
                if self.close_after_shutdown and not (self.thread and self.thread.is_alive()):QTimer.singleShot(0,self.close)
            self.close_after_shutdown=getattr(self,'close_after_shutdown',False)
            def stop_async():
                try:terminate()
                except Exception as error:self.log_shutdown_error=str(error)
                finally:QTimer.singleShot(0,self,end)
            threading.Thread(target=stop_async,daemon=True).start()
        def closeEvent(self,event):
            if self.lab:
                event.ignore();self.close_after_shutdown=True;self.shutdown();return
            if self.busy or self.closing:
                event.ignore();self.close_after_shutdown=True;return
            if self.gpu_process.state()!=QProcess.NotRunning:self.gpu_process.kill()
            event.accept()

    app=QApplication(sys.argv);app.setApplicationName('GIZMO Control Center')
    window=Window();window.show()
    if qa_report:
        report={'started_at':utc_now(),'checks':{},'error':None,'stream_chunks':0}
        state={'phase':'start','at':time.monotonic(),'first_answer':None,'busy_ticks':0}
        progress=Path(qa_report).with_suffix('.progress.json')
        progress.parent.mkdir(parents=True,exist_ok=True)
        def finish_qa():
            report['ended_at']=utc_now()
            report['checks']['ollama_stopped']=not any('ollama' in line.lower() for line in subprocess.run(
                ['tasklist','/FO','CSV','/NH'],capture_output=True,text=True,timeout=10).stdout.splitlines())
            try:
                with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=1):
                    report['checks']['api_offline']=False
            except OSError:report['checks']['api_offline']=True
            gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.total','--format=csv,noheader,nounits'],capture_output=True,text=True,timeout=5)
            report['gpu_after']=gpu.stdout.strip() if gpu.returncode==0 else None
            path=Path(qa_report);path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            app.exit(0 if report['error'] is None and all(report['checks'].values()) else 1)
        def tick_body():
            phase=state['phase']
            progress.write_text(json.dumps({'phase':phase,'busy':window.busy,'core':bool(window.lab),'checks':report['checks']},ensure_ascii=False),encoding='utf-8')
            if window.busy:state['busy_ticks']+=1
            if time.monotonic()-state['at']>180:
                report['error']='Timeout in '+phase
                state['phase']='shutdown';window.shutdown();state['at']=time.monotonic();return
            if phase=='start':
                window.start_core();state['phase']='loading';state['at']=time.monotonic()
            elif phase=='loading' and not window.busy:
                if not window.lab or not window.lab.model:
                    report['error']='Core did not load: '+str(window.last_error);state['phase']='shutdown';window.shutdown();return
                report['checks']['real_model_loaded']=window.lab.model==DEFAULT_MODEL
                report['checks']['ui_responsive']=window.isVisible() and window.pulse.timer.isActive() and state['busy_ticks']>=2
                report['checks']['real_status']=window.indicators['model'].text()==DEFAULT_MODEL
                import socket
                with socket.socket() as reserve:
                    reserve.bind(('127.0.0.1',0))
                    uplink_port=reserve.getsockname()[1]
                window.lab.config.update(uplink_host='127.0.0.1',uplink_port=uplink_port)
                window.lab.start_uplink();window.refresh_status()
                report['checks']['uplink_listening_visible']=window.indicators['c64'].text()=='LISTENING'
                with socket.create_connection(('127.0.0.1',uplink_port),timeout=3) as client:
                    client.settimeout(3)
                    assert b'UPLINK HERGESTELLT' in client.recv(128)
                    window.refresh_status()
                    report['checks']['uplink_connected_visible']=window.indicators['c64'].text()=='CONNECTED'
                window.lab.stop_uplink();window.refresh_status()
                report['checks']['uplink_shutdown_visible']=window.indicators['c64'].text()=='DISABLED'
                window.open_settings();report['checks']['settings_page']=window.pages.currentIndex()==2 and window.settings_fields['num_ctx'].value()>0
                report['checks']['active_profile_path_in_settings']='GIZMO_Awakening_V2_EN.txt' in window.profile_path.text() and not window.profile_warning.text()
                previous_warning=window.lab.personality_warning
                window.lab.personality_warning='SYNTHETIC PROFILE MISSING'
                window.show_profile()
                report['checks']['missing_profile_warning_in_settings']='SYNTHETIC PROFILE MISSING' in window.profile_warning.text()
                window.lab.personality_warning=previous_warning
                window.show_profile()
                window.open_archive();report['checks']['archive_page']=window.pages.currentIndex()==3 and 'jobs' in window.tables and 'messages' in window.tables
                report['checks']['analysis_statuses_visible']=all(name in window.archive_summary.text() for name in ('PENDING','PROCESSING','COMPLETED','FAILED','UNRESOLVED CLAIMS','COMPLETED WITHOUT CLAIMS'))
                import sqlite3
                archive_conversation=window.lab.memory.conversation()
                with sqlite3.connect(window.lab.memory.path) as synthetic:
                    synthetic.executemany('INSERT INTO messages(conversation_id,role,text,created_at) VALUES(?,?,?,?)',
                        [(archive_conversation,'user',f'SYNTHETIC ARCHIVE ITEM {number}',utc_now()) for number in range(520)])
                window.archive_tabs.setCurrentIndex(list(window.tables).index('messages'))
                window.refresh_status()
                report['checks']['archive_auto_refresh']=window.archive_page_label.text().endswith('520 RECORDS')
                report['checks']['archive_pagination']='PAGE 1 / 6' in window.archive_page_label.text()
                window.move_archive_page(5)
                report['checks']['archive_beyond_500']=window.archive_page==5 and window.tables['messages'].rowCount()==20
                window.archive_search.setText('ITEM 519')
                report['checks']['archive_search']=window.tables['messages'].rowCount()==1 and '519' in window.tables['messages'].item(0,3).text()
                window.archive_tabs.setCurrentIndex(len(window.tables))
                report['checks']['inspector_tab']=window.archive_tabs.tabText(len(window.tables))=='MEMORY INSPECTOR'
                window.pages.setCurrentIndex(0)
                if screenshot:window.grab().save(str(screenshot))
                # The automated call bypasses a real navigation click, which
                # normally activates the window before focus is assessed.
                window.raise_();window.activateWindow();QApplication.processEvents()
                window.open_model()
                report['checks']['focus_on_open']=window.prompt.hasFocus()
                for number in range(80):window.chat_view.append(f'SYNTHETIC SCROLL ROW {number}')
                window.prompt.setText('My dog is Milo.');QTest.keyClick(window.prompt,Qt.Key_Return)
                report['checks']['enter_sends']=window.busy and window.prompt.text()==''
                window.task.chunk.connect(lambda _text:report.__setitem__('stream_chunks',report['stream_chunks']+1))
                state['phase']='first';state['at']=time.monotonic()
            elif phase=='first' and window.busy and not state.get('draft_typed'):
                QTest.keyClicks(window.prompt,'Draft retained during streaming')
                report['checks']['focus_during_stream']=window.prompt.hasFocus()
                report['checks']['typing_during_stream']=window.prompt.text()=='Draft retained during streaming'
                window.chat_view.verticalScrollBar().setValue(0)
                state['draft_typed']=True
            elif phase=='first' and not window.busy:
                state['first_answer']=window.chat_view.toPlainText()
                report['checks']['streaming']=report['stream_chunks']>1
                report['checks']['first_response']='GIZMO >' in state['first_answer']
                report['checks']['draft_preserved']=window.prompt.text()=='Draft retained during streaming'
                report['checks']['focus_after_answer']=window.prompt.hasFocus()
                report['checks']['scroll_position_preserved']=window.chat_view.verticalScrollBar().value()==0
                window.prompt.clear()
                state['phase']='analysis';state['at']=time.monotonic()
            elif phase=='analysis':
                counts=window.lab.memory.job_counts()
                if counts.get('pending',0)==0 and counts.get('processing',0)==0:
                    report['checks']['memory_processing']=counts.get('done',0)>0
                    bar=window.chat_view.verticalScrollBar();bar.setValue(bar.maximum())
                    window.prompt.setText("What's my dog's name?");QTest.keyClick(window.prompt,Qt.Key_Return)
                    state['phase']='recall';state['at']=time.monotonic()
            elif phase=='recall' and window.busy and not state.get('queued'):
                window.prompt.setText('Say hello briefly.');QTest.keyClick(window.prompt,Qt.Key_Return)
                report['checks']['enter_queues_next']=len(window.pending_prompts)==1 and window.prompt.text()==''
                state['queued']=True;state['phase']='queued';state['at']=time.monotonic()
            elif phase=='queued' and not window.busy:
                answer=window.chat_view.toPlainText()[len(state['first_answer']):]
                report['answer']=answer[-500:]
                report['checks']['gemma_memory_recall']='milo' in answer.lower()
                report['checks']['queued_message_sent']='YOU > Say hello briefly.' in answer and not window.pending_prompts
                bar=window.chat_view.verticalScrollBar()
                report['checks']['auto_follow_latest']=bar.value()>=bar.maximum()-3
                window.open_archive();window.archive_tabs.setCurrentIndex(len(window.tables));window.refresh_inspector()
                inspector_text=window.inspector.toPlainText()
                report['checks']['inspector_shows_payload_and_budget']='exact_memory_payload' in inspector_text and 'selected_with_sources' in inspector_text and 'budget' in inspector_text
                window.open_model()
                window.prompt.setText('Write a long technical essay about vacuum tube computers, at least 1000 words.');window.send()
                state['phase']='interrupt';state['at']=time.monotonic()
            elif phase=='interrupt' and window.busy and time.monotonic()-state['at']>.7:
                report['checks']['shutdown_during_generation']=True
                state['phase']='shutdown';state['at']=time.monotonic();window.shutdown()
            elif phase=='interrupt' and not window.busy:
                report['checks']['shutdown_during_generation']=False
                state['phase']='shutdown';state['at']=time.monotonic();window.shutdown()
            elif phase=='shutdown' and not window.closing and window.lab is None and not (window.thread and window.thread.is_alive()):
                finish_qa()
        def tick():
            try:tick_body()
            except Exception as error:
                report['error']=repr(error)
                progress.write_text(json.dumps({'phase':state['phase'],'error':repr(error)},ensure_ascii=False),encoding='utf-8')
                if state['phase']!='shutdown':
                    state['phase']='shutdown';state['at']=time.monotonic();window.shutdown()
                else:finish_qa()
        timer=QTimer(window);timer.timeout.connect(tick);timer.start(250)
        QTimer.singleShot(100,tick)
    elif screenshot:
        path=Path(screenshot);path.parent.mkdir(parents=True,exist_ok=True)
        QTimer.singleShot(700,lambda:window.grab().save(str(path)))
        QTimer.singleShot(1100,app.quit)
    return app.exec()


def main():
    parser = argparse.ArgumentParser(description='GIZMO LAB')
    parser.add_argument('--gui',action='store_true',help='Grafisches Control Center')
    parser.add_argument('--screenshot',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--gui-qa-report',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--benchmark', action='store_true')
    parser.add_argument('--variants', type=Path, help='JSON-Datei mit Modell- und Parametersätzen')
    parser.add_argument('--personality', type=Path, help='UTF-8-Profil, für alle Varianten identisch')
    parser.add_argument('--debug', action='store_true', help='Gesendete Nachrichten und Erinnerungsabruf anzeigen')
    args = parser.parse_args()
    if args.gui:
        return run_gui(args.screenshot,args.gui_qa_report)
    lab = Lab(personality_file=args.personality)
    if lab.personality_warning:
        print('[!] '+lab.personality_warning,flush=True)
    def stop_signal(_signal, _frame):
        lab.stop()
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, stop_signal)
    if os.name=='nt':
        signal.signal(signal.SIGBREAK, stop_signal)
    def windows_watch(done):
        import msvcrt
        while not done.is_set() and not lab.stop_event.is_set():
            if msvcrt.kbhit() and msvcrt.getwch() in ('\x1b', 'q', 'Q'):
                lab.stop()
                return
            done.wait(.05)

    def interruptible(action):
        if os.name != 'nt':
            return action()
        done = threading.Event()
        watcher = threading.Thread(target=windows_watch, args=(done,), daemon=True)
        watcher.start()
        try:
            return action()
        finally:
            done.set()
            watcher.join(timeout=1)
    try:
        print(f'[.] GIZMO LAB {VERSION} // LOKALES TERMINAL', flush=True)
        if lab.memory.retried_jobs:
            print(f'[i] {lab.memory.retried_jobs} fehlgeschlagene Altanalysen erneut eingereiht.',flush=True)
        if lab.memory.reindexed_jobs:
            print(f'[i] {lab.memory.reindexed_jobs} Archivnachrichten zur aktualisierten Analyse eingereiht.',flush=True)
        interruptible(lab.start)
        if args.benchmark:
            questions = json.loads((ROOT / 'questions.json').read_text(encoding='utf-8'))
            variants = json.loads(args.variants.read_text(encoding='utf-8')) if args.variants else [{'model': lab.model, 'options': {}}]
            files = interruptible(lambda: run_benchmark(lab, questions, variants, lab.data / 'reports'))
            print(f'[+] Berichte: {files[0]} und {files[1]}')
        else:
            print('[i] Freier Dialog. /quit, /model NAME, /memory, /entities, /relations, /reanalyze, /memstatus.')
            while not lab.stop_event.is_set():
                try:
                    prompt = input('Du > ')
                except EOFError:
                    break
                if should_quit(prompt):
                    break
                if prompt.startswith('/model '):
                    interruptible(lambda: lab.switch_model(prompt[7:].strip()))
                    continue
                if prompt.strip() == '/memory':
                    for item in lab.memory.list_memories(include_pending=True):
                        print(f"#{item['id']} {item['status']} {item['domain']} {item['key']}: {item['value']}")
                    continue
                if prompt.strip() == '/entities':
                    for item in lab.memory.list_entities():
                        print(f"#{item['id']} {item['kind']}: {item['name']}")
                    continue
                if prompt.strip() == '/relations':
                    for item in lab.memory.list_relations():
                        print(f"#{item['id']} {item['status']} {item['subject']} {item['predicate']} {item['object'] or item['value']} [Quelle #{item['source_message_id']}]")
                    continue
                if prompt.startswith('/approve-relation '):
                    lab.memory.set_relation_status(int(prompt[18:]),'active')
                    continue
                if prompt.startswith('/delete-relation '):
                    lab.memory.set_relation_status(int(prompt[17:]),'deleted')
                    continue
                if prompt.strip() == '/reanalyze':
                    print('[i] Archiv eingereiht:',lab.memory.enqueue_archive(reanalyze=True))
                    continue
                if prompt.strip() == '/retry-analysis':
                    print('[i] Fehlgeschlagene Analysen erneut eingereiht:',lab.memory.retry_failed())
                    continue
                if prompt.strip() == '/memstatus':
                    print('[i] Schema-Version:',lab.memory.db.execute('PRAGMA user_version').fetchone()[0],
                          'Auftraege:',lab.memory.job_counts(),
                          'letzte Analyse:',round(lab.analyzer.last_duration_s,3) if lab.analyzer else 0,'s')
                    continue
                if prompt.startswith('/correct '):
                    ident, value = prompt[9:].split(' ', 1)
                    lab.memory.correct(int(ident), value)
                    continue
                if prompt.startswith('/delete '):
                    lab.memory.delete(int(prompt[8:]))
                    continue
                if prompt.startswith('/export '):
                    print(lab.memory.export(lab.data / Path(prompt[8:].strip()).name))
                    continue
                if prompt.startswith('/backup '):
                    print(lab.memory.backup(lab.data / Path(prompt[8:].strip()).name))
                    continue
                if not prompt.strip():
                    continue
                print('GIZMO > ', end='', flush=True)
                try:
                    result = interruptible(lambda: lab.chat(prompt, on_text=lambda chunk: print(chunk, end='', flush=True)))
                except ContextBudgetError as error:
                    print(f'\n[!] {error}',flush=True)
                    continue
                print(f"\n[i] {result['total_s']:.2f} s, {result['tokens_per_s']:.1f} Token/s, {result['abort_reason']}")
                if args.debug:
                    print(json.dumps(lab.last_diagnostics,ensure_ascii=False,indent=2))
    except (KeyboardInterrupt, OSError, RuntimeError) as error:
        if not isinstance(error, KeyboardInterrupt):
            print(f'[!] {error}', flush=True)
    finally:
        lab.stop()


if __name__ == '__main__':
    main()
