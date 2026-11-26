"""Real Gemma acceptance with synthetic missed-extraction conversations only."""
import json
import re
import sys
import time
from pathlib import Path

from gizmo_lab import Lab
from qa_local import ollama_process_count

ROOT=Path(__file__).resolve().parent


def main(folder):
    folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
    config=json.loads((ROOT/'config.example.json').read_text(encoding='utf-8'))
    config.update(model='gemma4:12b',num_predict=180,ollama_url='http://127.0.0.1:11434')
    lab=Lab(config=config,data=folder/'synthetic-data',personality_file=ROOT/'qa_personality.en.txt')
    report={'passed':False,'answers':[]}
    try:
        conversation=lab.memory.conversation()
        for statement in ('My dog is called Pippa.',"She's a wire-haired terrier girl.",
                          'My sister is named Elena.','She repairs old radios.',
                          'Mein altes Teleskop hat einen Messingspiegel.'):
            lab.memory.add_message(conversation,'user',statement)
        for number in range(30):lab.memory.add_message(conversation,'user',f'I discussed synthetic topic {number}.')
        assert not lab.memory.list_relations() and not lab.memory.list_memories()
        lab.start()
        lab.analyzer.pause()
        deadline=time.monotonic()+90
        lab.analyzer.resume()
        while time.monotonic()<deadline and lab.memory.embedding_status().get('pending',0):time.sleep(.25)
        assert not lab.memory.embedding_status().get('pending',0),lab.memory.embedding_status()
        assert lab.memory.embedding_engine().session.get_providers()==['CPUExecutionProvider']
        lab.stop()
        lab=Lab(config=config,data=folder/'synthetic-data',personality_file=ROOT/'qa_personality.en.txt')
        lab.start()
        assert lab.memory.embedding_status().get('done',0)>=35
        lab.conversation_id=lab.memory.conversation()
        for question,expected in [('What breed is my dog?',r'wire.haired terrier'),
                                  ('Who in my family repairs radios?',r'Elena'),
                                  ('What material is the mirror in my old telescope?',r'brass|Messing')]:
            result=lab.chat(question)
            report['answers'].append({'question':question,'answer':result['answer'],'seconds':result['total_s'],
                                     'retrieval_seconds':lab.last_diagnostics['retrieval_s'],
                                     'selected':lab.memory.last_retrieval['selected']})
            assert result['abort_reason']=='completed' and re.search(expected,result['answer'],re.I),report['answers'][-1]
        report['embedding']=lab.memory.embedding_status()
        report['passed']=True
    finally:
        lab.stop()
        report['ollama_processes_after']=ollama_process_count()
        (folder/'hybrid-real-gemma.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        assert report['ollama_processes_after']==0
    assert report['passed']


if __name__=='__main__':main(sys.argv[1])
