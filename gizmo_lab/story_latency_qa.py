"""Synthetic local latency diagnosis; never reads productive profile or memory."""
import json
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from story_qa import synthetic_lab


class MeasuredOpener:
    def __init__(self):
        self.requests=[]

    def __call__(self,request,timeout):
        if request.data and request.full_url.endswith('/api/chat'):
            payload=json.loads(request.data)
            self.requests.append({'structured':bool(payload.get('format')),
                                  'stream':bool(payload.get('stream')),
                                  'num_ctx':payload.get('options',{}).get('num_ctx'),
                                  'prompt_bytes':len(json.dumps(payload.get('messages',[]),ensure_ascii=False).encode('utf-8'))})
        return urllib.request.urlopen(request,timeout=timeout)


def gpu():
    try:
        output=subprocess.run(['nvidia-smi','--query-gpu=memory.used,utilization.gpu',
                               '--format=csv,noheader,nounits'],capture_output=True,text=True,
                              timeout=5,check=True).stdout.strip().splitlines()[0]
        return [int(part.strip()) for part in output.split(',')]
    except (OSError,ValueError,IndexError,subprocess.SubprocessError):
        return None


def residency():
    try:
        with urllib.request.urlopen('http://127.0.0.1:11434/api/ps',timeout=3) as response:
            models=json.load(response).get('models',[])
        return [{'name':item.get('name'),'size_bytes':item.get('size'),'size_vram_bytes':item.get('size_vram'),
                 'context_length':item.get('context_length')} for item in models]
    except (OSError,ValueError):
        return []


def result(lab,opener,prompt):
    before=len(opener.requests)
    started=time.perf_counter()
    visible=[]
    outcome=lab.chat(prompt,on_text=lambda chunk:visible.append((time.perf_counter()-started,len(chunk))),origin='gui')
    if outcome['abort_reason']!='completed':
        raise RuntimeError('Synthetic latency case failed: '+outcome['abort_reason'])
    metrics=outcome.get('story_metrics',{})
    return {'route':metrics.get('route','normal'),'total_s':round(time.perf_counter()-started,3),
            'first_visible_s':round(visible[0][0],3) if visible else None,
            'visible_chunks':len(visible),'context_assembly_s':round(outcome.get('context_assembly_s',0),4),
            'director_s':round(metrics.get('director_s',0),3),
            'dialogue_model_s':round(metrics.get('dialogue_model_s',outcome.get('total_s',0)),3),
            'validation_s':round(metrics.get('validation_s',0),4),
            'prompt_tokens':outcome.get('prompt_tokens'),'generated_tokens':outcome.get('generated_tokens'),
            'ollama_ns':outcome.get('ollama_metrics',{}),
            'director_model':metrics.get('director_model',{}),
            'calls':opener.requests[before:], 'gpu_after':gpu(), 'residency':residency()}


def minimal_probe(lab):
    payload={'model':lab.model,'stream':True,'think':False,'keep_alive':-1,
             'messages':[{'role':'system','content':'Answer briefly in English.'},
                         {'role':'user','content':'Hi.'}],
             'options':{'num_ctx':6144,'num_predict':48,'temperature':0.2}}
    started=time.perf_counter();first=None;metrics={}
    with lab.request('/api/chat',payload,timeout=120) as response:
        for raw in response:
            event=json.loads(raw)
            if event.get('message',{}).get('content') and first is None:
                first=time.perf_counter()-started
            if event.get('done'):
                metrics=event;break
    return {'first_token_s':round(first,3) if first is not None else None,
            'total_s':round(time.perf_counter()-started,3),
            'load_s':round(metrics.get('load_duration',0)/1e9,3),
            'prompt_eval_s':round(metrics.get('prompt_eval_duration',0)/1e9,3),
            'eval_s':round(metrics.get('eval_duration',0)/1e9,3),
            'prompt_tokens':metrics.get('prompt_eval_count'),
            'generated_tokens':metrics.get('eval_count')}


def run(no_analyzer=False):
    with tempfile.TemporaryDirectory(prefix='gizmo-story-latency-',ignore_cleanup_errors=True) as temporary:
        opener=MeasuredOpener();lab=synthetic_lab(Path(temporary),opener)
        report={'synthetic_only':True,'installed_model':'gemma4:12b','gpu_before':gpu(),
                'background_analyzer':not no_analyzer,'cases':{}}
        try:
            lab.start()
            if no_analyzer and lab.analyzer:
                lab.analyzer.stop();lab.analyzer=None
            report['residency_after_preload']=residency()
            if no_analyzer:
                report['minimal_warm_probe_before_chat']=minimal_probe(lab)
            report['cases']['normal_question']=result(lab,opener,'How are you today?')
            report['cases']['start']=result(lab,opener,'/story a quiet synthetic exploration')
            report['cases']['direct_question']=result(lab,opener,'What do you see?')
            report['cases']['tell_question']=result(lab,opener,'Tell me what you see')
            lab.personality='Synthetic personality sentence. '*120
            try:
                report['cases']['larger_profile_question']=result(lab,opener,'What have we noticed so far?')
            except Exception as error:
                report['larger_profile_error_type']=type(error).__name__
            minimal_probe(lab)  # warm the same runner after any prior context switch
            report['minimal_warm_probe']=minimal_probe(lab)
            report['analyzer_paused_after_chat']=bool(lab.analyzer.pause_event.is_set()) if lab.analyzer else None
        finally:
            lab.stop()
            report['gpu_after_shutdown']=gpu()
            try:
                urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=1).close()
                report['ollama_offline']=False
            except OSError:
                report['ollama_offline']=True
        return report


if __name__=='__main__':
    no_analyzer='--no-analyzer' in sys.argv
    report=run(no_analyzer=no_analyzer)
    target=Path(__file__).resolve().parent.parent/('.local-test/story-latency-081-no-analyzer.json' if no_analyzer else '.local-test/story-latency-081.json')
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'report':str(target),'routes':{key:value['route'] for key,value in report['cases'].items()},
                      'times':{key:[value['first_visible_s'],value['total_s']] for key,value in report['cases'].items()},
                      'larger_profile_error_type':report.get('larger_profile_error_type'),
                      'ollama_offline':report['ollama_offline']},indent=2))
