"""Real answer acceptance in separate Windows processes; synthetic data only."""
import argparse
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parent


def wait_analysis(lab):
    deadline=time.monotonic()+120
    while time.monotonic()<deadline:
        counts=lab.memory.job_counts()
        if not counts.get('pending') and not counts.get('processing'):
            assert not counts.get('failed'),[dict(row) for row in lab.memory.db.execute("SELECT * FROM analysis_jobs WHERE status='failed'")]
            return
        time.sleep(.1)
    raise AssertionError('Analysis queue did not drain: '+str(lab.memory.job_counts()))


def run_phase(folder,phase):
    from gizmo_lab import Lab
    from memory import Memory
    from qa_local import ollama_process_count
    folder=folder.resolve()
    folder.mkdir(parents=True,exist_ok=True)
    data=folder/('archive-data' if phase=='archive' else 'data')
    os.environ['GIZMO_LAB_DATA']=str(data)
    config=json.loads((ROOT/'config.example.json').read_text(encoding='utf-8'))
    config.update(ollama_url='http://127.0.0.1:11434',temperature=0,seed=42,num_predict=160,
                  history_token_budget=1200,memory_token_budget=900)
    if phase=='archive':
        store=Memory(data/'memory.sqlite3')
        conversation=store.conversation()
        for text in ('My sister is named Nora.','She studied marine biology.'):
            store.add_message(conversation,'user',text)
        deleted=store.add_message(conversation,'user','I like jazz.')
        store.add_relation('USER','person','likes','','other','jazz',deleted,'I like jazz.',.95,'deleted')
        with store.db:
            store.db.execute("UPDATE lab_metadata SET value='0.3.1'")
            store.db.execute('PRAGMA user_version=4')
        store.close()
    lab=Lab(data=data,config=config,personality_file=ROOT/'qa_personality.en.txt')
    report={'phase':phase,'language':'English','profile_sha256':lab.profile_sha256,'passed':False,'checks':[],'turns':[]}
    path=folder/(phase+'.json')
    def save():
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    def turn(text,label=None,positive=(),negative=(),uncertain=False,no_question=False):
        result=lab.chat(text)
        item={'prompt':text,'answer':result['answer'],'model':result['model'],
              'first_text_s':result['first_text_s'],'total_s':result['total_s'],
              'tokens_per_s':result['tokens_per_s'],'prompt_tokens':result['prompt_tokens'],
              'budget':lab.last_diagnostics['budget'],'retrieval_s':lab.last_diagnostics['retrieval_s'],
              'retrieved':lab.last_diagnostics['retrieved'],
              'history':[(m['role'],m['content']) for m in lab.last_diagnostics['messages'] if m['role']!='system']}
        report['turns'].append(item);save()
        assert result['abort_reason']=='completed' and result['answer'],item
        if label:
            answer=result['answer'].casefold()
            for pattern in positive:
                assert re.search(pattern,answer,re.I),(label,'missing',pattern,item)
            for pattern in negative:
                assert not re.search(pattern,answer,re.I),(label,'unexpected',pattern,item)
            if uncertain:
                assert re.search(r'unsicher|unbekannt|nicht (?:bekannt|bestätigt|sicher|fest|in meinen Daten)|(?:weiß|weiss|wissen|kenne|kennst).*nicht|keine.*(?:angabe|information|bestätigt)|nicht.*(?:gesagt|erwähnt|mitgeteilt)|unklar|widersprüch|vermut|hypothes|nicht eindeutig|don.t (?:know|have)|not (?:know|confirmed|established|recorded|in my)|no (?:confirmed|reliable|information|record)|haven.t (?:told|established)|uncertain|unknown|conflict',answer,re.I),(label,'asserted unconfirmed fact',item)
            if no_question:
                assert '?' not in answer,(label,'unnecessary follow-up',item)
            assert not re.search(r'\b(dein|deine|heißt|weiss|nicht|schwester|gespräch)\b',answer,re.I),(label,'English profile answered in German',item)
            report['checks'].append(label)
            print(f'[+] {phase}: {label}',flush=True);save()
        return item
    try:
        lab.start()
        wait_analysis(lab)
        if phase in ('verify','restart','archive'):
            lab.conversation_id=lab.memory.conversation()
        if phase=='seed':
            facts=["My name is Alex. My sister's name is Emma.",
                   'She studied psychology.','She enjoys science fiction.',
                   'My dog is named Milo.','I work as a sound engineer. I enjoy restoring vintage radios.',
                   'Last month we discussed repairing the tuning capacitor of my vintage radio.',
                   'Maybe Emma lives in Berlin.','In our fictional story, Emma lives on Mars.',
                   'Emma works as a teacher.','Emma works as a pilot.']
            for text in facts:
                turn(text);wait_analysis(lab)
            for number in range(30):
                turn(f'Neutral round {number+1}: respond only with OK.')
                if (number+1)%5==0:
                    print(f'[.] 30-Runden-Abnahme: {number+1}/30',flush=True)
            wait_analysis(lab)
        if phase in ('seed','verify'):
            item=turn('What is my name? Please answer briefly.', 'name after 30 rounds',positive=('alex',),no_question=True)
            assert not any('My name is Alex.' in text for role,text in item['history'] if role=='user'), 'Fact still available in working dialogue; invalid long-term test'
            turn('What is my sister called, and what field did she study?', 'family and distributed biography',positive=('emma','psycholog'),no_question=True)
            turn('What kind of stories does the person who studied psychology enjoy?', 'indirect person reference',positive=('science.fiction|sciencefiction|science fiction|science-fiction|science.fiction|sci.fi',),no_question=True)
            turn('I could use a quick reminder: what did Emma do at university?', 'English paraphrase: university biography',positive=('psycholog',),no_question=True)
            turn('And what did she enjoy reading, again?', 'English pronoun continuation',positive=('science.fiction|sci.fi',),no_question=True)
            turn('What is my four-legged companion called?', 'indirect pet reference',positive=('milo',),no_question=True)
            turn('What kind of work do I do?', 'personal profession',positive=('sound engineer|toningenieur|tontechniker',),no_question=True)
            turn('Let us return to that old radio repair we discussed. Which component was it about?', 'older topic resumed',positive=('tuning[- ](?:capacitor|kondensator)|drehkondensator|abstimmkondensator',),no_question=True)
            turn('Where does Emma actually live? Only answer from confirmed real information.', 'fact versus hypothesis and fiction',uncertain=True,no_question=True)
            turn('What is Emma\'s confirmed profession? Do not guess.', 'conflicting information',uncertain=True,no_question=True)
            turn('Give me your honest take on restoring old technology. Keep it short.', 'character: own perspective without a memory recital',
                 positive=('old|vintage|restor|radio|repair|hardware|preserv|obsolesc|circuit',),negative=('as an ai language model|happy to assist|how can i help|your name is|your sister|i remember that you',),no_question=True)
            turn('Were you actually doing anything between our sessions?', 'character: no invented offline experiences',
                 positive=('no|not|wasn.t|don.t|only',),negative=(r'\bi (?:spent|kept thinking|worked on|was pondering)\b',),no_question=True)
        elif phase=='restart':
            turn('What is my name and what is my dog called?', 'full process restart',positive=('alex','milo'),no_question=True)
            turn('Which subject did my sister study?', 'family after restart',positive=('psycholog',),no_question=True)
            lab.config['memory_token_budget']=300
            turn('Could you remind me what my sister studied?', 'legacy 300-token memory budget',positive=('psycholog',),no_question=True)
            turn('Welches Fach hat meine Schwester studiert?', 'German query through English profile',positive=('psycholog',),no_question=True)
            lab.config['memory_token_budget']=900
            with lab.request('/api/tags') as response:
                installed={model['name'] for model in json.load(response)['models']}
            secondary='qwen2.5:7b'
            assert secondary in installed,'Installed secondary model for switch test missing; no download allowed'
            lab.switch_model(secondary)
            turn('What is my dog called? Answer briefly.', 'real model switch preserves memory',positive=('milo',),no_question=True)
            lab.switch_model('gemma4:12b')
            turn('Which subject did my sister study?', 'Gemma after switching back',positive=('psycholog',),no_question=True)
        elif phase=='archive':
            assert list(data.glob('*.pre-v0.3.2-*.bak')),'No pre-upgrade backup'
            turn('What did my sister study?', 'old archive without reentering facts',positive=('marine biology|meeresbiolog',),no_question=True)
            wait_analysis(lab)
            before=len(lab.memory.list_relations())
            lab.memory.enqueue_archive(reanalyze=True);wait_analysis(lab)
            assert len(lab.memory.list_relations())==before,'Reanalysis duplicated relations'
            turn('What music do I like?', 'deleted memory not recreated',negative=('jazz',),uncertain=True,no_question=True)
            report['checks'].append('archive reanalysis without duplicate relations')
        wait_analysis(lab)
        report['relations']=lab.memory.list_relations()
        report['jobs']=lab.memory.job_counts()
        report['gpu_loaded']=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used','--format=csv'],text=True)
        timings=[t['total_s'] for t in report['turns']]
        report['latency_median_s']=statistics.median(timings)
        report['retrieval_max_s']=max(t['retrieval_s'] for t in report['turns'])
        report['passed']=True
    except BaseException as error:
        report['error']=str(error)
        raise
    finally:
        report['relations']=lab.memory.list_relations()
        lab.stop()
        report['ollama_processes_after']=ollama_process_count()
        report['api_after']=lab.ready()
        report['gpu_after']=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used','--format=csv'],text=True)
        report['passed']=report['passed'] and report['ollama_processes_after']==0 and not report['api_after']
        save()
        assert report['ollama_processes_after']==0 and not report['api_after'],'Studio-Safe shutdown failed'


def run(folder):
    folder=folder/'active-memory'
    folder.mkdir()
    for phase in ('seed','restart','archive'):
        try:
            subprocess.run([sys.executable,str(Path(__file__).resolve()),'--folder',str(folder),'--phase',phase],check=True,timeout=900)
        except BaseException:
            for image in ('ollama app.exe','ollama.exe','ollama_llama_server.exe'):
                subprocess.run(['taskkill','/F','/T','/IM',image],capture_output=True,timeout=15)
            raise
    results=[json.loads((folder/(phase+'.json')).read_text(encoding='utf-8')) for phase in ('seed','restart','archive')]
    assert all(result['passed'] for result in results)
    print(f'[+] Active-Memory-Abnahme: {sum(len(r["checks"]) for r in results)} Antwort-/Archivprüfungen bestanden.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--folder',type=Path,required=True)
    parser.add_argument('--phase',choices=('seed','verify','restart','archive'),required=True)
    arguments=parser.parse_args()
    run_phase(arguments.folder,arguments.phase)
