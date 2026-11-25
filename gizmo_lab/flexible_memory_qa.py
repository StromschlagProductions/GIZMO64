"""Real Gemma acceptance with synthetic English conversations and a fresh restart."""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
FACTS=(
    'My dog is called Lucy.', "She's a beagle girl.",
    'My radio is named Atlas.', 'The Atlas tuning knob is chipped.',
    'My friend Nora works at the observatory.', 'Nora collects antique postcards.',
    'Last spring I visited Bergen with Nora.',
    'That Bergen trip was important because it was our first holiday together.',
)
QUESTIONS=(
    ("What is my dog's name and breed?",r'\blucy\b.*\bbeagle\b|\bbeagle\b.*\blucy\b'),
    ('What is unusual about the Atlas tuning knob?',r'\bchipped\b'),
    ('What does Nora collect?',r'antique postcards'),
    ('Why was my Bergen trip important?',r'first holiday.*(?:nora|together)|(?:nora|together).*first holiday'),
)


def phase(folder,name):
    from gizmo_lab import Lab
    from qa_local import ollama_process_count
    data=folder/'synthetic-data'
    config=json.loads((ROOT/'config.example.json').read_text(encoding='utf-8'))
    config.update(model='gemma4:12b',ollama_url='http://127.0.0.1:11434',temperature=0,
                  num_predict=130,history_token_budget=400,memory_token_budget=1200)
    lab=Lab(data=data,config=config,personality_file=ROOT/'qa_personality.en.txt')
    report={'phase':name,'checks':[],'answers':[],'passed':False}
    try:
        lab.start()
        if name=='seed':
            for text in FACTS:
                reply=lab.chat(text)
                assert reply['abort_reason']=='completed',reply
            deadline=time.monotonic()+240
            while time.monotonic()<deadline:
                counts=lab.memory.job_counts()
                if not counts.get('pending') and not counts.get('processing'):break
                time.sleep(.2)
            assert lab.memory.job_counts()=={'done':len(FACTS)},lab.memory.job_counts()
            relations=lab.memory.list_relations()
            for subject,key,value in [('Lucy','breed','beagle'),('Atlas','tuning_knob_condition','chipped'),
                                      ('Nora','collection','antique postcards'),('Bergen trip','personal_meaning','first holiday together')]:
                assert any(r['subject']==subject and r['property_key']==key and r['value']==value and r['status']=='active' for r in relations),(subject,key,value)
                report['checks'].append(subject+'.'+key)
        else:
            lab.conversation_id=lab.memory.conversation()
            for question,expected in QUESTIONS:
                reply=lab.chat(question)
                answer=reply['answer']
                report['answers'].append({'question':question,'answer':answer,'seconds':reply['total_s'],
                                          'retrieved':lab.last_diagnostics['retrieved']})
                assert reply['abort_reason']=='completed' and re.search(expected,answer,re.I),(question,answer)
                report['checks'].append(question)
        report['passed']=True
    finally:
        lab.stop()
        report['ollama_processes_after']=ollama_process_count()
        report['api_after']=lab.ready()
        (folder/(name+'.json')).write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding='utf-8')
        assert report['ollama_processes_after']==0 and not report['api_after'],'Ollama not fully stopped'
    return report


def run(folder):
    folder=Path(folder).resolve()/'flexible-memory'
    folder.mkdir(parents=True,exist_ok=True)
    for name in ('seed','restart'):
        subprocess.run([sys.executable,str(ROOT/'flexible_memory_qa.py'),'--phase',name,str(folder)],check=True,timeout=600)


if __name__=='__main__':
    if len(sys.argv)!=4 or sys.argv[1]!='--phase':
        raise SystemExit('Usage: flexible_memory_qa.py --phase seed|restart SYNTHETIC_FOLDER')
    phase(Path(sys.argv[3]),sys.argv[2])
