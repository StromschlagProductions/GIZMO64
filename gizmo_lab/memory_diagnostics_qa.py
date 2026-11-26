"""LAB 0.4.3 real Gemma acceptance; synthetic data and public test profile only."""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
FACTS=(
    'I have a sister.',
    'She studied optics.',
    'I restored a shortwave receiver.',
    'The receiver has a wooden case.',
    'Her name is Elena.',
    'My dog is called Pippa.',
    'My new bookshelf is blue.',
    'I also own a brass compass.',
    'Tell me about my dog.',
    'She is a corgi girl.',
    'My other dog is Rex.',
    'Thank you.',
)


def wait_jobs(lab):
    deadline=time.monotonic()+240
    while time.monotonic()<deadline:
        counts=lab.memory.job_counts()
        if not counts.get('pending') and not counts.get('processing'):
            return counts
        time.sleep(.2)
    raise AssertionError('Analysis queue did not drain')


def phase(folder,name):
    from gizmo_lab import Lab
    from qa_local import ollama_process_count
    folder=folder.resolve();folder.mkdir(parents=True,exist_ok=True)
    config=json.loads((ROOT/'config.example.json').read_text(encoding='utf-8'))
    config.update(model='gemma4:12b',ollama_url='http://127.0.0.1:11434',num_predict=160)
    lab=Lab(data=folder/'synthetic-data',config=config,personality_file=ROOT/'qa_personality.en.txt')
    report={'phase':name,'passed':False,'checks':[],'answers':[]}
    try:
        lab.start()
        if name=='seed':
            for text in FACTS:
                result=lab.chat(text)
                assert result['abort_reason']=='completed',result['abort_reason']
            counts=wait_jobs(lab)
            assert not counts.get('failed') and counts.get('done')==len(FACTS),counts
            relations=lab.memory.list_relations()
            for predicate,subject,key,value in [('has_sister','USER','', 'Elena'),
                                                ('attribute','Pippa','breed','corgi')]:
                assert any(r['predicate']==predicate and r['subject']==subject and r['property_key']==key
                    and (r['object'] or r['value'])==value and r['status']=='active' for r in relations),(predicate,key)
                report['checks'].append(subject+'.'+(key or predicate))
            summary=lab.memory.analysis_summary()
            assert summary.get('empty',0)>=1,summary
            report['checks'].append('completed_without_claims_visible')
        elif name=='restart':
            lab.conversation_id=lab.memory.conversation()
            for question,expected in (("What is my sister's name?",r'\belena\b'),
                                      ('Which dog is a corgi?',r'\bpippa\b')):
                result=lab.chat(question)
                answer=result['answer']
                report['answers'].append({'question':question,'answer':answer,'seconds':result['total_s'],
                    'selected':lab.memory.last_retrieval['selected'],'budget':lab.last_diagnostics['budget']})
                assert result['abort_reason']=='completed' and re.search(expected,answer,re.I),(question,answer)
                memory_payload=[m['content'] for m in lab.last_diagnostics['messages'] if m['role']=='system' and m['content'].startswith('Local memory:')]
                assert memory_payload and re.search(expected,memory_payload[0],re.I),(question,'missing model payload')
                report['checks'].append(question)
            assert not lab.memory.job_counts().get('failed'),lab.memory.job_counts()
        else:raise ValueError(name)
        report['passed']=True
    finally:
        lab.stop()
        report['ollama_processes_after']=ollama_process_count()
        report['api_after']=lab.ready()
        (folder/(name+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        assert report['ollama_processes_after']==0 and not report['api_after'],'Ollama still running'
    return report


def run(folder):
    folder=Path(folder).resolve()/'memory-diagnostics'
    for name in ('seed','restart'):
        subprocess.run([sys.executable,str(ROOT/'memory_diagnostics_qa.py'),'--phase',name,str(folder)],check=True,timeout=600)


if __name__=='__main__':
    if len(sys.argv)!=4 or sys.argv[1]!='--phase':
        raise SystemExit('Usage: memory_diagnostics_qa.py --phase seed|restart SYNTHETIC_FOLDER')
    phase(Path(sys.argv[3]),sys.argv[2])
