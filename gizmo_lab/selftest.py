"""Vollautomatischer Windows-Selbsttest mit echtem lokalem Gemma und Testdatenbank."""
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from gizmo_lab import Lab, private_dir
from memory import Memory
from analysis import parse_response

MODEL='gemma4:12b'


def process_check():
    if os.name!='nt':
        return None
    result=subprocess.run(['tasklist','/FO','CSV','/NH'],capture_output=True,text=True,timeout=10)
    return [line.split(',')[0].strip('"') for line in result.stdout.splitlines() if 'ollama' in line.lower()]


def run():
    report_dir=private_dir()/'selftest-reports'
    report_dir.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')
    report_path=report_dir/f'selftest-{stamp}.md'
    checks={}
    errors=[]
    started=time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='gizmo-lab-selftest-') as folder:
        db_path=Path(folder)/'synthetic.sqlite3'
        config={'model':MODEL,'ollama_url':'http://localhost:11434','keep_alive':-1,
                'num_ctx':8192,'num_predict':768,'think':False}
        lab=Lab(data=folder,config=config)
        try:
            lab.start()
            checks['ollama_und_gemma_bereit']=lab.model==MODEL
            c=lab.conversation_id
            samples=[
                'My name is Alex. My sister is named Emma.',
                'She studied psychology.',
                'My dog is named Milo.',
                'I like science fiction movies.',
            ]
            for text in samples:
                mid=lab.memory.add_message(c,'user',text)
                lab.memory.extract_user(text,mid)
                lab.memory.enqueue(mid)
                lab.memory.add_message(c,'assistant','Acknowledged.')
            deadline=time.monotonic()+180
            while time.monotonic()<deadline:
                counts=lab.memory.job_counts()
                if counts.get('pending',0)==0 and counts.get('processing',0)==0:
                    break
                time.sleep(.25)
            else:
                errors.append('Analyse innerhalb von 180 Sekunden nicht abgeschlossen')
            counts=lab.memory.job_counts()
            relations=lab.memory.list_relations()
            entities=lab.memory.list_entities()
            checks['alle_analyseauftraege_erledigt']=counts.get('done',0)==len(samples) and counts.get('failed',0)==0
            checks['person_Emma']=any(e['name'].casefold()=='emma' for e in entities)
            checks['haustier_Milo']=any(e['name'].casefold()=='milo' for e in entities)
            checks['beziehung_Schwester']=any(r['predicate']=='has_sister' and (r['object'] or '').casefold()=='emma' for r in relations)
            checks['beziehung_Hund']=any(r['predicate']=='has_dog' and (r['object'] or '').casefold()=='milo' for r in relations)
            checks['name_abrufbar']=any('Alex' in line for line in lab.memory.retrieve('What is my name?')[0])
            checks['archiv_vollstaendig']=len(lab.memory.recent(c,20))==8
            for job in lab.memory.failed_jobs():
                errors.append(f"Job #{job['id']}: {job['error']}")
            try:
                parse_response({'message':{'content':'{"claims": ['},'done_reason':'length'})
                checks['abgeschnittenes_JSON_erkannt']=False
            except ValueError as error:
                checks['abgeschnittenes_JSON_erkannt']='abgeschnitten' in str(error)
            try:
                parse_response({'message':{'content':'not json'}})
                checks['ungueltiges_JSON_erkannt']=False
            except ValueError:
                checks['ungueltiges_JSON_erkannt']=True
            if counts.get('pending',0)==0 and counts.get('processing',0)==0:
                reopened=Memory(db_path)
                checks['wiederabruf_nach_neustart']=any('Alex' in line for line in reopened.retrieve('What is my name?')[0]) and len(reopened.list_relations())==len(relations)
                reopened.close()
            else:
                checks['wiederabruf_nach_neustart']=False
        except Exception as error:
            errors.append(f'{type(error).__name__}: {error}')
        finally:
            lab.stop()
    remaining=process_check()
    if remaining is not None:
        checks['ollama_prozesse_beendet']=not remaining
        if remaining: errors.append('Ollama-Prozesse noch sichtbar: '+', '.join(remaining))
    elapsed=time.perf_counter()-started
    lines=['# GIZMO LAB 0.3.1 – Selbsttest','',f'Modell: `{MODEL}`',
           'Daten: ausschließlich synthetisch; temporäre Testdatenbank',f'Gesamtdauer: {elapsed:.2f} s','',
           '## Prüfungen','']
    lines += [f"- {'OK' if value else 'FEHLER'}: {name}" for name,value in checks.items()]
    lines += ['','## Fehler',''] + ([f'- {error}' for error in errors] if errors else ['- Keine'])
    report_path.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print('\n'.join(lines))
    print(f'Bericht: {report_path}')
    return 0 if checks and all(checks.values()) and not errors else 1


if __name__=='__main__':
    sys.exit(run())
