"""Synthetic, real Gemma acceptance for the shared GUI/C64 LAB engine."""
import json
import re
import socket
import sys
import time
from pathlib import Path

from gizmo_lab import Lab, UPLINK_BEGIN, UPLINK_END
from qa_local import ollama_process_count

ROOT=Path(__file__).resolve().parent


def free_port():
    with socket.socket() as listener:
        listener.bind(('127.0.0.1',0))
        return listener.getsockname()[1]


def c64_turn(port,prompt):
    with socket.create_connection(('127.0.0.1',port),timeout=10) as client:
        client.settimeout(160)
        with client.makefile('rb') as stream:
            assert b'UPLINK HERGESTELLT' in stream.readline()
            client.sendall(prompt.encode('ascii')+b'\r')
            records=[]
            while True:
                record=stream.readline().strip()
                assert record,('C64 stream ended',records)
                records.append(record.decode('ascii'))
                client.sendall(b'ACK\r')
                if records[-1]==UPLINK_END:break
            assert records[0]==UPLINK_BEGIN
            return ' '.join(records[1:-1])


def await_analysis(lab,timeout=180):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        jobs=lab.memory.job_counts()
        if not jobs.get('pending') and not jobs.get('processing'):return jobs
        time.sleep(.3)
    raise AssertionError(('analysis backlog',lab.memory.job_counts()))


def await_uplink_state(lab,expected,timeout=5):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        state=lab.uplink.status()['state']
        if state==expected:return state
        time.sleep(.05)
    raise AssertionError(('uplink state',expected,lab.uplink.status()))


def run(folder):
    folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
    config=json.loads((ROOT/'config.example.json').read_text(encoding='utf-8'))
    port=free_port()
    config.update(model='gemma4:12b',num_predict=180,ollama_url='http://127.0.0.1:11434',
                  uplink_enabled=True,uplink_host='127.0.0.1',uplink_port=port)
    data=folder/'synthetic-data'
    report={'passed':False,'port':port,'answers':{}}
    lab=None
    try:
        lab=Lab(config=config,data=data,personality_file=ROOT/'qa_personality.en.txt')
        lab.start()
        assert lab.uplink.status()['state']=='listening',lab.uplink.status()
        gui=lab.chat('My dog is called Pippa. She is a wire-haired terrier.',origin='gui')
        assert gui['abort_reason']=='completed',gui
        report['analysis_after_gui']=await_analysis(lab)
        reply=c64_turn(port,'What breed is my dog Pippa?')
        report['answers']['c64_breed']=reply
        assert re.search(r'terrier',reply,re.I),reply
        assert lab.uplink.status()['connections']==1
        report['status_after_disconnect']=await_uplink_state(lab,'disconnected')
        reply=c64_turn(port,'My sister Elise builds radios.')
        report['answers']['c64_statement']=reply
        assert lab.uplink.status()['connections']==2
        report['analysis_after_c64']=await_analysis(lab)
        gui=lab.chat('What does my sister Elise build?',origin='gui')
        report['answers']['gui_recall']=gui['answer']
        assert gui['abort_reason']=='completed' and re.search(r'radio',gui['answer'],re.I),gui
        origins={row['origin'] for row in lab.memory.db.execute("SELECT origin FROM messages WHERE role='user'")}
        assert origins=={'gui','c64'},origins
        assert lab.personality_path== (ROOT/'qa_personality.en.txt').resolve()
        lab.stop();lab=None
        assert ollama_process_count()==0
        lab=Lab(config=config,data=data,personality_file=ROOT/'qa_personality.en.txt')
        lab.start()
        assert lab.uplink.status()['state']=='listening'
        reply=c64_turn(port,'What breed is Pippa?')
        report['answers']['c64_after_restart']=reply
        assert re.search(r'terrier',reply,re.I),reply
        assert lab.uplink.status()['connections']==1
        report['passed']=True
    finally:
        if lab:lab.stop()
        report['ollama_processes_after']=ollama_process_count()
        (folder/'uplink-real-gemma.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        assert report['ollama_processes_after']==0
    assert report['passed']


if __name__=='__main__':run(sys.argv[1])
