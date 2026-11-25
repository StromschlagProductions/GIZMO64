"""Lokales GIZMO-LAB: Terminalgespräche und reproduzierbare Ollama-Benchmarks."""
import argparse
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

ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL = 'richardyoung/qwen2.5-7b-instruct-abliterated:latest'
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


class Lab:
    def __init__(self, config=None, data=None, opener=None, runner=None):
        self.data = Path(data) if data else private_dir()
        self.config = config or load_config(self.data)
        personality = self.data / 'personality.txt'
        self.personality = (personality if personality.exists() else ROOT / 'personality.example.txt').read_text(encoding='utf-8').strip()
        self.opener = opener or urllib.request.urlopen
        self.runner = runner or subprocess.run
        self.stop_event = threading.Event()
        self.lock = threading.RLock()
        self.process = None
        self.active_response = None
        self.context = []
        self.model = None

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

    def preload(self, model):
        if self.stop_event.is_set():
            raise RuntimeError('Modellladen abgebrochen')
        print(f'[.] Lade Modell {model}...', flush=True)
        with self.request('/api/generate', {'model': model, 'prompt': '', 'stream': False,
                                            'keep_alive': self.config.get('keep_alive', -1)}, timeout=120) as response:
            self.active_response = response
            result = json.load(response)
            self.active_response = None
        if result.get('error'):
            raise RuntimeError(result['error'])
        if self.stop_event.is_set():
            raise RuntimeError('Modellladen abgebrochen')
        self.model = model
        print('[+] Modell vorgeladen', flush=True)

    def switch_model(self, model):
        if model == self.model:
            return
        if self.model:
            try:
                with self.request('/api/generate', {'model': self.model, 'prompt': '', 'stream': False,
                                                    'keep_alive': 0}, timeout=10):
                    pass
            except OSError:
                pass
        self.preload(model)

    def chat(self, prompt, context=None, on_text=None, model=None):
        model = model or self.model or self.config.get('model', DEFAULT_MODEL)
        messages = [{'role': 'system', 'content': self.personality}]
        messages += list(context if context is not None else self.context)[-20:]
        messages.append({'role': 'user', 'content': prompt})
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
        if context is None and aborted == 'completed':
            self.context.extend([messages[-1], {'role': 'assistant', 'content': text}])
            self.context = self.context[-20:]
        speed = metrics.get('eval_count', 0) * 1e9 / metrics.get('eval_duration', 0) if metrics.get('eval_duration') else 0
        return {'model': model, 'config': payload, 'first_text_s': first, 'total_s': elapsed,
                'prompt_tokens': metrics.get('prompt_eval_count'), 'generated_tokens': metrics.get('eval_count'),
                'tokens_per_s': speed, 'abort_reason': aborted, 'answer': text,
                'ollama_metrics': {key: metrics.get(key) for key in ('load_duration', 'prompt_eval_duration', 'eval_duration', 'total_duration')}}

    def stop(self):
        with self.lock:
            if self.stop_event.is_set():
                return
            self.stop_event.set()
            response = self.active_response
            if response:
                try:
                    response.close()
                except OSError:
                    pass
            if os.name == 'nt':
                for image in ('ollama app.exe', 'ollama.exe', 'ollama_llama_server.exe'):
                    self.runner(['taskkill', '/F', '/T', '/IM', image], capture_output=True, check=False, timeout=10)
                for _ in range(3):
                    listing = self.runner(['tasklist', '/FO', 'CSV', '/NH'], capture_output=True, text=True, timeout=10)
                    names = [line for line in listing.stdout.splitlines() if 'ollama' in line.lower()]
                    if not names:
                        break
                    for line in names:
                        parts = next(__import__('csv').reader([line]))
                        if len(parts) > 1:
                            self.runner(['taskkill', '/F', '/T', '/PID', parts[1]], capture_output=True, timeout=10)
                else:
                    print('[!] Ollama-Prozesse noch sichtbar', flush=True)
            elif self.process and self.process.poll() is None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
            print('[+] GIZMO LAB beendet', flush=True)


def run_benchmark(lab, questions, variants, destination):
    results = []
    for variant in variants:
        lab.config.update(variant.get('options', {}))
        model = variant.get('model', lab.config.get('model', DEFAULT_MODEL))
        cold = lab.model != model
        lab.switch_model(model)
        for case in questions:
            context = []
            for prompt in case['turns']:
                record = lab.chat(prompt, context=context, model=model)
                record.update({'case': case['id'], 'prompt': prompt, 'cold_model_start': cold,
                               'variant': variant})
                results.append(record)
                context.extend([{'role': 'user', 'content': prompt}, {'role': 'assistant', 'content': record['answer']}])
            cold = False
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
            report.write(f"Kaltstart: {item['cold_model_start']} · Erstes Zeichen: {item['first_text_s']} s · Gesamt: {item['total_s']:.3f} s  \n")
            report.write(f"Prompt-Tokens: {item['prompt_tokens']} · Antwort-Tokens: {item['generated_tokens']} · Tempo: {item['tokens_per_s']:.2f} Token/s · Abbruch: {item['abort_reason']}\n\n")
            report.write(f"**Frage:** {item['prompt']}\n\n**Antwort:** {item['answer']}\n\n")
    return json_path, md_path


def main():
    parser = argparse.ArgumentParser(description='GIZMO LAB')
    parser.add_argument('--benchmark', action='store_true')
    parser.add_argument('--variants', type=Path, help='JSON-Datei mit Modell- und Parametersätzen')
    args = parser.parse_args()
    lab = Lab()
    def stop_signal(_signal, _frame):
        lab.stop()
        raise KeyboardInterrupt
    signal.signal(signal.SIGINT, stop_signal)
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
        print('[.] GIZMO LAB // LOKALES TERMINAL', flush=True)
        interruptible(lab.start)
        if args.benchmark:
            questions = json.loads((ROOT / 'questions.json').read_text(encoding='utf-8'))
            variants = json.loads(args.variants.read_text(encoding='utf-8')) if args.variants else [{'model': lab.model, 'options': {}}]
            files = interruptible(lambda: run_benchmark(lab, questions, variants, lab.data / 'reports'))
            print(f'[+] Berichte: {files[0]} und {files[1]}')
        else:
            print('[i] Freier Dialog. /quit beendet, /model NAME wechselt das Modell.')
            while not lab.stop_event.is_set():
                try:
                    prompt = input('Du > ')
                except EOFError:
                    break
                if prompt.strip().lower() in ('/quit', '/exit', 'q') or '\x1b' in prompt:
                    break
                if prompt.startswith('/model '):
                    interruptible(lambda: lab.switch_model(prompt[7:].strip()))
                    continue
                if not prompt.strip():
                    continue
                print('GIZMO > ', end='', flush=True)
                result = interruptible(lambda: lab.chat(prompt, on_text=lambda chunk: print(chunk, end='', flush=True)))
                print(f"\n[i] {result['total_s']:.2f} s, {result['tokens_per_s']:.1f} Token/s, {result['abort_reason']}")
    except (KeyboardInterrupt, OSError, RuntimeError) as error:
        if not isinstance(error, KeyboardInterrupt):
            print(f'[!] {error}', flush=True)
    finally:
        lab.stop()


if __name__ == '__main__':
    main()
