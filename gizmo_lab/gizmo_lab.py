"""Lokales GIZMO-LAB: Terminalgespräche und reproduzierbare Ollama-Benchmarks."""
import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from memory import Memory, utc_now
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
    config = json.loads(source.read_text(encoding='utf-8')) if source.exists() else json.loads((ROOT / 'config.example.json').read_text(encoding='utf-8'))
    return config


def should_quit(prompt):
    return prompt.strip().lower() in ('/quit', '/exit') or '\x1b' in prompt


class Lab:
    def __init__(self, config=None, data=None, opener=None, runner=None, personality_file=None):
        self.data = Path(data) if data else private_dir()
        self.config = config or load_config(self.data)
        personality = Path(personality_file) if personality_file else (self.data / 'GIZMO_Awakening_V2_EN.txt' if (self.data / 'GIZMO_Awakening_V2_EN.txt').exists() else self.data / 'personality.txt')
        if personality_file and not personality.is_file():
            raise FileNotFoundError(f'Persoenlichkeitsprofil fehlt: {personality}')
        self.personality = (personality if personality.exists() else ROOT / 'personality.example.txt').read_text(encoding='utf-8').strip()
        self.profile_sha256 = hashlib.sha256(self.personality.encode('utf-8')).hexdigest()
        self.opener = opener or urllib.request.urlopen
        self.runner = runner or subprocess.run
        self.stop_event = threading.Event()
        self.lock = threading.RLock()
        self.process = None
        self.active_response = None
        self.context = []
        self.memory = Memory(self.data / 'memory.sqlite3')
        self.analyzer = None
        self.previous_message_at = self.memory.last_message_time()
        self.session_started = utc_now()
        self.conversation_id = self.memory.conversation(self.memory.latest_conversation())
        self.last_diagnostics = {}
        self.model = None
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
        self.preload(self.config.get('model', DEFAULT_MODEL))
        self.analyzer = Analyzer(self.memory.path,self.config,self.opener)
        self.analyzer.start()

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
        if self.analyzer:
            self.analyzer.pause()
        if model == self.model:
            if self.analyzer: self.analyzer.resume()
            return
        if self.model:
            self.unload(self.model)
        self.preload(model)
        self.config['model']=model
        if self.analyzer: self.analyzer.resume()

    def chat(self, prompt, context=None, on_text=None, model=None):
        if self.analyzer:
            self.analyzer.pause()
        model = model or self.model or self.config.get('model', DEFAULT_MODEL)
        messages = [{'role': 'system', 'content': self.personality}]
        retrieved = []
        retrieval_s = 0
        if context is None:
            retrieved,retrieval_s = self.memory.retrieve(prompt, self.config.get('memory_token_budget', 300))
            elapsed_since_previous = (datetime.fromisoformat(utc_now()) - datetime.fromisoformat(self.previous_message_at)).total_seconds() if self.previous_message_at else None
            clock = f"Aktuelle UTC-Zeit: {utc_now()}. Sitzungsbeginn: {self.session_started}. Letzte Nachricht vor Sitzungsbeginn: {self.previous_message_at or 'keine'}. Vergangene Sekunden seitdem: {elapsed_since_previous if elapsed_since_previous is not None else 'unbekannt'}. Behaupte keine Aktivitaeten waehrend ausgeschalteter Sitzungen."
            messages.append({'role':'system','content':clock})
            if retrieved:
                messages.append({'role':'system','content':'Bestaetigte lokale Erinnerungen (mit Herkunft; Fiktion nicht als Realitaet behandeln):\n'+'\n'.join(retrieved)})
            messages += self.memory.recent(self.conversation_id, self.config.get('working_messages', 20))
        else:
            messages += list(context)[-self.config.get('working_messages', 20):]
        messages.append({'role': 'user', 'content': prompt})
        self.last_diagnostics = {'messages':messages,'retrieved':retrieved,'retrieval_s':retrieval_s,
                                 'context_chars':sum(len(message['content']) for message in messages)}
        source_id = self.memory.add_message(self.conversation_id,'user',prompt) if context is None else None
        options = {key: self.config[key] for key in OPTIONS if self.config.get(key) is not None}
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
            if text:
                self.memory.add_message(self.conversation_id,'assistant',text)
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
            if self.analyzer:
                self.analyzer.stop()
            response = self.active_response
            if response:
                try:
                    response.close()
                except OSError:
                    pass
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


def main():
    parser = argparse.ArgumentParser(description='GIZMO LAB')
    parser.add_argument('--benchmark', action='store_true')
    parser.add_argument('--variants', type=Path, help='JSON-Datei mit Modell- und Parametersätzen')
    parser.add_argument('--personality', type=Path, help='UTF-8-Profil, für alle Varianten identisch')
    parser.add_argument('--debug', action='store_true', help='Gesendete Nachrichten und Erinnerungsabruf anzeigen')
    args = parser.parse_args()
    lab = Lab(personality_file=args.personality)
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
                    print('[i] Archiv eingereiht:',lab.memory.enqueue_archive())
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
                result = interruptible(lambda: lab.chat(prompt, on_text=lambda chunk: print(chunk, end='', flush=True)))
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
