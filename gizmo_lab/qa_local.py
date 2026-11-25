"""Local QA, optionally using the installed Gemma. Synthetic data only."""
import argparse
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent


def ollama_process_count():
    if os.name!='nt':
        raise RuntimeError('Der reale Studio-Safe-Test erfordert Windows.')
    return int(subprocess.check_output(['powershell','-NoProfile','-Command',
        '@(Get-Process *ollama* -ErrorAction SilentlyContinue).Count'],text=True).strip())


def real_gemma(folder):
    from analysis import Analyzer
    from gizmo_lab import Lab
    config=json.loads((ROOT/'config.example.json').read_text(encoding='utf-8'))
    config.update(model='gemma4:12b',ollama_url='http://127.0.0.1:11434')
    os.environ['OLLAMA_HOST']='127.0.0.1:11434'
    os.environ['OLLAMA_NOPRUNE']='true'
    calls=[]
    def capture(request,timeout):
        call={'endpoint':request.full_url,'request':json.loads(request.data) if request.data else None}
        calls.append(call)
        started=time.perf_counter()
        try:
            with urllib.request.urlopen(request,timeout=timeout) as response:
                body=response.read()
            call['response']=body.decode('utf-8')
            return io.BytesIO(body)
        finally:
            call['seconds']=time.perf_counter()-started
            (folder/'synthetic-api-calls.json').write_text(json.dumps(calls,ensure_ascii=False,indent=2),encoding='utf-8')
    lab=Lab(config=config,data=folder/'data',opener=capture,personality_file=ROOT/'personality.example.txt')
    report={'model':'gemma4:12b','passed':False}
    analyzer=None
    try:
        report['api_before']=lab.ready()
        lab.start()
        with lab.request('/api/tags') as response:
            report['installed_model']=next(m for m in json.load(response)['models'] if m['name']=='gemma4:12b')
        report['chat']=lab.chat('Mein Hund heißt Milo. Antworte kurz auf Deutsch.')
        assert report['chat']['answer'] and report['chat']['abort_reason']=='completed',report['chat']
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            counts=lab.memory.job_counts()
            if counts and not counts.get('pending') and not counts.get('processing'):
                break
            time.sleep(.25)
        assert lab.memory.job_counts()=={'done':1},lab.memory.job_counts()
        assert any(r['predicate']=='has_dog' and r['object']=='Milo' for r in lab.memory.list_relations())
        lab.analyzer.stop()
        lab.analyzer=None
        cases=[['Ich heiße Alex. Meine Schwester heißt Emma.','Sie hat Psychologie studiert.'],
               ['Mein Hund heißt Milo.'],['Vielleicht wohnt Emma in Berlin.'],
               ['In unserer erfundenen Geschichte lebt Emma auf dem Mars.']]
        for texts in cases:
            conversation=lab.memory.conversation()
            for text in texts:
                source=lab.memory.add_message(conversation,'user',text)
                lab.memory.enqueue(source)
        analyzer=Analyzer(lab.memory.path,config,capture)
        durations=[]
        for _ in range(5):
            assert analyzer.analyze_one(),lab.memory.job_counts()
            durations.append(analyzer.last_duration_s)
        relations=lab.memory.list_relations()
        for predicate,obj,status in [('has_sister','Emma','active'),('studied','psycholog','active'),
                                     ('has_dog','Milo','active'),('lives_in','Berlin','pending'),('lives_in','Mars','fictional')]:
            assert any(r['predicate']==predicate and obj.casefold() in (r['object'] or r['value'] or '').casefold() and r['status']==status for r in relations),(predicate,obj,status,relations)
        assert lab.memory.job_counts()=={'done':6},lab.memory.job_counts()
        # Exercise the real retry path on synthetic jobs, without repeating successful jobs.
        source=lab.memory.add_message(lab.memory.conversation(),'user','Mein Hund heißt Milo.')
        lab.memory.enqueue(source)
        job=lab.memory.next_job()
        lab.memory.finish_job(job['id'],'synthetic LAB 0.3 parse failure')
        assert lab.memory.retry_failed()==1
        assert analyzer.analyze_one()
        assert lab.memory.job_counts()=={'done':7}
        lab.conversation_id=lab.memory.conversation()
        report['german_memory_reply']=lab.chat('Wie heißt mein Hund? Bitte kurz antworten.')
        assert 'milo' in report['german_memory_reply']['answer'].casefold()
        assert '?' not in report['german_memory_reply']['answer']
        assert analyzer.analyze_one()
        assert lab.memory.job_counts()=={'done':8}
        report.update(passed=True,analysis_seconds=durations,relations=lab.memory.list_relations(),jobs=lab.memory.job_counts())
        with lab.request('/api/ps') as response:
            report['loaded']=json.load(response)
        report['gpu_loaded']=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used','--format=csv'],text=True)
    finally:
        if analyzer:
            analyzer.stop()
        lab.stop()
        report['api_after']=lab.ready()
        report['ollama_processes_after']=ollama_process_count()
        report['gpu_after']=subprocess.check_output(['nvidia-smi','--query-gpu=name,memory.total,memory.used','--format=csv'],text=True)
        report['passed']=report['passed'] and not report['api_after'] and report['ollama_processes_after']==0
        (folder/'real-gemma.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        assert not report['api_after'] and report['ollama_processes_after']==0,'Ollama nicht vollständig beendet'
    assert report['passed']


def installed_launcher_check(folder):
    """Run the shipped CLI through the installed launcher, using fake private data."""
    import deployment
    root=folder/'installation'
    data=folder/'synthetic-production-data'
    data.mkdir()
    config=(ROOT/'config.example.json').read_bytes()
    profile=b'You are a synthetic quality assurance assistant. Reply briefly.'
    (data/'config.json').write_bytes(config)
    (data/'personality.txt').write_bytes(profile)
    git=shutil.which('git') or str(ROOT.parent/'.local-tools/git/cmd/git.exe')
    deployment.install(root,ROOT,git,data)
    process=None
    report={'passed':False}
    try:
        process=subprocess.Popen([sys.executable,str(root/'launcher.py'),'start','--offline','--terminal'],
                                 stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8')
        output,_=process.communicate('/quit\n',timeout=120)
        (folder/'installed-launcher.txt').write_text(output,encoding='utf-8')
        assert process.returncode==0,output
        assert 'Modell vorgeladen' in output and 'GIZMO LAB beendet' in output,output
        assert (data/'config.json').read_bytes()==config
        assert (data/'personality.txt').read_bytes()==profile
        assert (data/'memory.sqlite3').is_file()
        report['passed']=True
    finally:
        if process and process.poll() is None:
            subprocess.run(['taskkill','/F','/T','/PID',str(process.pid)],capture_output=True,timeout=15)
        # Cleanup remains mandatory even when a launcher regression breaks shutdown.
        if ollama_process_count():
            report['passed']=False
            for image in ('ollama app.exe','ollama.exe','ollama_llama_server.exe'):
                subprocess.run(['taskkill','/F','/T','/IM',image],capture_output=True,timeout=15)
        report['ollama_processes_after']=ollama_process_count()
        (folder/'installed-launcher.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    assert report['passed'] and report['ollama_processes_after']==0,report


def control_center_check(folder):
    """Exercise the real Qt event loop, Gemma streaming, memory and Studio-Safe."""
    import deployment
    destination=folder/'control-center'
    destination.mkdir()
    data=destination/'synthetic-data'
    data.mkdir()
    (data/'GIZMO_Awakening_V2_EN.txt').write_text((ROOT/'qa_personality.en.txt').read_text(encoding='utf-8'),encoding='utf-8')
    root=destination/'installation'
    git=shutil.which('git') or str(ROOT.parent/'.local-tools/git/cmd/git.exe')
    deployment.install(root,ROOT,git,data)
    settings=json.loads((root/'installation.json').read_text(encoding='utf-8'))
    settings['python']=sys.executable
    deployment.atomic_json(root/'installation.json',settings)
    deployment.refresh_launchers(root)
    environment=dict(os.environ,GIZMO_GUI_LOG=str(destination/'pythonw-debug.log'))
    report=destination/'report.json'
    screenshot=destination/'control-center.png'
    process=None
    try:
        pythonw=str(Path(sys.executable).with_name('pythonw.exe'))
        process=subprocess.Popen([pythonw,str(root/'launcher.py'),'start','--offline',
            '--gui-qa-report',str(report),'--screenshot',str(screenshot)],
            env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8')
        output,_=process.communicate(timeout=240)
        (destination/'console.txt').write_text(output,encoding='utf-8')
        assert process.returncode==0,output
        evidence=json.loads(report.read_text(encoding='utf-8'))
        assert evidence['error'] is None and all(evidence['checks'].values()),evidence
        assert screenshot.is_file()
    finally:
        if process and process.poll() is None:
            subprocess.run(['taskkill','/F','/T','/PID',str(process.pid)],capture_output=True,timeout=15)
        if ollama_process_count():
            for image in ('ollama app.exe','ollama.exe','ollama_llama_server.exe'):
                subprocess.run(['taskkill','/F','/T','/IM',image],capture_output=True,timeout=15)
        assert ollama_process_count()==0,'Ollama nach Qt-QA nicht vollständig beendet'


def main():
    parser=argparse.ArgumentParser(description='Lokale LAB-QA mit ausschließlich synthetischen Daten')
    parser.add_argument('--real-gemma',action='store_true',help='Installiertes gemma4:12b real testen; Ollama danach vollständig beenden')
    args=parser.parse_args()
    os.environ['PYTHONUTF8']='1'
    os.environ['PYTHONIOENCODING']='utf-8'
    folder=ROOT.parent/'.local-test'/'qa'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    folder.mkdir(parents=True)
    os.environ['GIZMO_LAB_DATA']=str(folder/'data')
    temporary=folder/'tmp'
    temporary.mkdir()
    os.environ['TEMP']=os.environ['TMP']=str(temporary)
    # Locate an existing installation only. Never download a model or install software.
    if not shutil.which('ollama'):
        candidate=Path.home()/'AppData/Local/Programs/Ollama'
        if (candidate/'ollama.exe').is_file():
            os.environ['PATH']=str(candidate)+os.pathsep+os.environ.get('PATH','')
    try:
        with (folder/'unit-tests.txt').open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,'-m','unittest','discover','-s',str(ROOT),'-p','test_*.py','-v'],
                           stdout=log,stderr=subprocess.STDOUT,check=True,timeout=120)
        if args.real_gemma:
            if not shutil.which('ollama'):
                raise RuntimeError('Vorhandene Ollama-Installation nicht gefunden')
            real_gemma(folder)
            from active_memory_qa import run as active_memory_acceptance
            active_memory_acceptance(folder)
            installed_launcher_check(folder)
            control_center_check(folder)
        print(f'[+] Lokale QA bestanden. Synthetische Berichte: {folder}',flush=True)
        return 0
    except (Exception,KeyboardInterrupt) as error:
        print(f'[!] QA fehlgeschlagen: {error}. Bericht: {folder}',file=sys.stderr,flush=True)
        return 1


if __name__=='__main__':
    raise SystemExit(main())
