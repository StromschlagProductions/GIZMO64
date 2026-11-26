"""Synthetic real-Gemma acceptance for episode retrieval after restart."""
import json
import re
import sys
import time
from pathlib import Path

from gizmo_lab import Lab
from qa_local import ollama_process_count

ROOT=Path(__file__).resolve().parent


def run(folder):
    folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
    config=json.loads((ROOT/'config.example.json').read_text(encoding='utf-8'))
    config.update(model='gemma4:12b',num_predict=180,ollama_url='http://127.0.0.1:11434')
    lab=Lab(config=config,data=folder/'synthetic-data',personality_file=ROOT/'qa_personality.en.txt')
    report={'passed':False,'answers':[]}
    try:
        lab.start()
        for prompt in ('I went to the Maritime Museum with my friend Mara last Saturday.',
                       'We spent the afternoon looking at old navigation charts.',
                       'Now about my old radio: its tuning knob is loose.',
                       'In our story, Mara and I entered a glass lighthouse.'):
            answer=lab.chat(prompt)
            assert answer['abort_reason']=='completed',answer
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            jobs=lab.memory.job_counts();episodes=lab.memory.episode_status()
            if not jobs.get('pending') and not jobs.get('processing') and not episodes['remaining']:break
            time.sleep(.25)
        assert not lab.memory.episode_status()['remaining'] and not lab.memory.job_counts().get('failed'),(lab.memory.episode_status(),lab.memory.job_counts())
        domains={r['domain'] for r in lab.memory.db.execute('SELECT domain FROM episodes')}
        assert 'real' in domains and 'fiction' in domains,domains
        lab.stop()
        lab=Lab(config=config,data=folder/'synthetic-data',personality_file=ROOT/'qa_personality.en.txt')
        lab.start();lab.conversation_id=lab.memory.conversation()
        checks=[('Where did Mara and I look at navigation charts?',r'maritime museum|museum'),
                ('Did Mara and I really enter a glass lighthouse?',r'story|fiction|imagined|not real|fictional'),
                ('What color were the navigation charts?',r'don.t|didn.t|not|no |unknown|unspecified|unclear')]
        for question,expected in checks:
            result=lab.chat(question)
            record={'question':question,'answer':result['answer'],'seconds':result['total_s'],
                    'selected':lab.memory.last_retrieval['selected']}
            report['answers'].append(record)
            assert result['abort_reason']=='completed' and re.search(expected,result['answer'],re.I),record
            if 'color' in question.casefold():
                assert '?' not in result['answer'] and not re.search(r'\b(red|blue|green|yellow|purple|orange|black|white|brown|gold|silver)\b',result['answer'],re.I),record
        assert any(item.startswith('episode:') for item in report['answers'][0]['selected']),report['answers'][0]
        museum_episode=int(next(item.split(':',1)[1] for item in report['answers'][0]['selected'] if item.startswith('episode:')))
        assert lab.memory.delete_episode(museum_episode)
        lab.conversation_id=lab.memory.conversation()
        forgotten=lab.chat('Where did Mara and I look at navigation charts?')
        report['after_episode_deletion']={'answer':forgotten['answer'],'selected':lab.memory.last_retrieval['selected']}
        assert forgotten['abort_reason']=='completed' and re.search(r'don.t (?:know|have)|unknown|not (?:recorded|mentioned|sure)|no (?:information|record)|can.t recall|didn.t (?:say|mention)',forgotten['answer'],re.I) and not re.search(r'maritime museum|at the museum|glass lighthouse',forgotten['answer'],re.I),report['after_episode_deletion']
        report['episodes']=[{'id':r['id'],'domain':r['domain'],'status':r['status']} for r in lab.memory.db.execute('SELECT id,domain,status FROM episodes')]
        report['passed']=True
    finally:
        lab.stop()
        report['ollama_processes_after']=ollama_process_count()
        (folder/'episodic-real-gemma.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        assert report['ollama_processes_after']==0
    assert report['passed']


if __name__=='__main__':run(sys.argv[1])
