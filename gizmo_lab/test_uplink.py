"""Synthetic 0.2.2 ACK and shared-engine integration tests."""
import io
import json
import select
import socket
import tempfile
import threading
import time
import unittest
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
try:
    from gizmo_lab.gizmo_lab import Lab,Uplink,UPLINK_BEGIN,UPLINK_PARA,UPLINK_END,c64_records
except ModuleNotFoundError:
    from gizmo_lab import Lab,Uplink,UPLINK_BEGIN,UPLINK_PARA,UPLINK_END,c64_records
from memory import Memory


class FakeLab:
    def __init__(self,path):
        self.stop_event=threading.Event();self.memory=Memory(path);self.calls=[]
        self.answer='First? Sentence!\n\n'+'Word '*800
    def chat(self,prompt,on_text,origin):
        self.calls.append((prompt,origin))
        for part in (self.answer[:17],self.answer[17:]):on_text(part)
        return {'abort_reason':'completed','answer':self.answer}


class UplinkProtocolTest(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.lab=FakeLab(Path(self.folder.name)/'synthetic.sqlite3')
        self.uplink=Uplink(self.lab,host='127.0.0.1',port=6464)
        self.client,server=socket.socketpair();self.client.settimeout(3)
        self.uplink.clients.add(server)
        self.thread=threading.Thread(target=self.uplink.handle,args=(server,),daemon=True);self.thread.start()
        self.stream=self.client.makefile('rb')
        self.assertEqual(self.stream.readline().strip(),b'UPLINK HERGESTELLT. GIZMO ONLINE.')
    def tearDown(self):
        self.uplink.stop();self.stream.close();self.client.close();self.thread.join(timeout=2)
        self.lab.memory.close();self.folder.cleanup()
    def ack(self):
        record=self.stream.readline().strip();self.client.sendall(b'ACK\r');return record
    def test_fragmented_ping_ack_long_stream_and_paragraphs(self):
        self.client.sendall(b'PI');self.client.sendall(b'NG\r')
        self.assertEqual(self.stream.readline().strip(),b'PONG // GIZMO UPLINK AKTIV')
        self.client.sendall(b'HELLO\r')
        self.assertEqual(self.stream.readline().strip(),UPLINK_BEGIN.encode())
        self.assertFalse(select.select([self.client],[],[],.05)[0])
        self.client.sendall(b'A');self.client.sendall(b'CK\r')
        records=[]
        while True:
            record=self.ack()
            if record==UPLINK_END.encode():break
            records.append(record)
        self.assertIn(UPLINK_PARA.encode(),records)
        self.assertGreaterEqual(len(records),100)
        self.assertEqual(sum(record.count(b'Word') for record in records),800)
        self.assertEqual(self.lab.calls,[('HELLO','c64')])
    def test_missing_begin_ack_closes_without_model_call(self):
        self.uplink.ack_timeout=.15
        self.client.sendall(b'QUESTION\r')
        self.assertEqual(self.stream.readline().strip(),UPLINK_BEGIN.encode())
        self.assertEqual(self.stream.readline(),b'')
        self.assertEqual(self.lab.calls,[])
    def test_delayed_ack_stalls_stream_until_received(self):
        self.client.sendall(b'QUESTION\r')
        self.assertEqual(self.stream.readline().strip(),UPLINK_BEGIN.encode())
        self.assertFalse(select.select([self.client],[],[],.12)[0])
        self.client.sendall(b'ACK\r')
        self.assertTrue(self.stream.readline().strip())
    def test_disconnect_during_stream_does_not_replay(self):
        self.client.sendall(b'QUESTION\r')
        self.assertEqual(self.ack(),UPLINK_BEGIN.encode())
        self.assertTrue(self.stream.readline().strip())
        self.client.shutdown(socket.SHUT_RDWR);self.client.close()
        self.thread.join(timeout=2)
        self.assertEqual(self.lab.calls,[('QUESTION','c64')])


class SharedEngineTest(unittest.TestCase):
    def test_concurrent_frontend_requests_share_one_model_queue(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);profile=path/'synthetic-profile.txt'
            profile.write_text('You are synthetic GIZMO.',encoding='utf-8')
            active=0;peak=0;counter_lock=threading.Lock()
            def opener(request,timeout):
                nonlocal active,peak
                self.assertTrue(request.full_url.endswith('/api/chat'))
                with counter_lock:
                    active+=1;peak=max(peak,active)
                time.sleep(.08)
                with counter_lock:active-=1
                return io.BytesIO(b'{"message":{"content":"Acknowledged."},"done":true}\n')
            config=json.loads((ROOT/'config.example.json').read_text(encoding='utf-8'))
            lab=Lab(config=config,data=path/'data',personality_file=profile,opener=opener,
                    runner=lambda *_args,**_kwargs:SimpleNamespace(stdout='',returncode=0))
            barrier=threading.Barrier(3);results=[]
            def run(origin):
                barrier.wait()
                results.append(lab.chat('Synthetic question from '+origin,origin=origin))
            workers=[threading.Thread(target=run,args=(origin,)) for origin in ('gui','c64')]
            try:
                for worker in workers:worker.start()
                barrier.wait()
                for worker in workers:worker.join(timeout=5)
                self.assertTrue(all(not worker.is_alive() for worker in workers))
                self.assertEqual(peak,1)
                self.assertEqual(len(results),2)
                self.assertTrue(all(result['abort_reason']=='completed' for result in results))
                self.assertEqual(lab.memory.db.execute('SELECT COUNT(*) FROM messages').fetchone()[0],4)
                self.assertEqual({row['origin'] for row in lab.memory.db.execute('SELECT origin FROM messages')},{'gui','c64'})
            finally:lab.stop()

    def test_port_conflict_and_idempotent_start(self):
        with tempfile.TemporaryDirectory() as folder:
            lab=FakeLab(Path(folder)/'synthetic.sqlite3')
            with socket.socket() as reserve:
                reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1]
            first=Uplink(lab,'127.0.0.1',port)
            second=Uplink(lab,'127.0.0.1',port)
            try:
                self.assertTrue(first.start())
                self.assertTrue(first.start())
                self.assertFalse(second.start())
                self.assertEqual(second.status()['state'],'error')
                self.assertTrue(second.status()['error'])
            finally:
                first.stop();second.stop();lab.memory.close()

    def test_gui_and_tcp_use_one_lab_profile_model_conversation_and_database(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder);profile=path/'synthetic-profile.txt'
            profile.write_text('You are synthetic GIZMO. Speak plainly.',encoding='utf-8')
            reserve=socket.socket();reserve.bind(('127.0.0.1',0));port=reserve.getsockname()[1];reserve.close()
            config=json.loads((ROOT/'config.example.json').read_text(encoding='utf-8'))
            config.update(uplink_enabled=True,uplink_host='127.0.0.1',uplink_port=port)
            payloads=[]
            def opener(request,timeout):
                if request.full_url.endswith('/api/tags'):return io.BytesIO(b'{"models":[{"name":"gemma4:12b"}]}')
                payload=json.loads(request.data);payloads.append(payload)
                if request.full_url.endswith('/api/generate'):return io.BytesIO(b'{"done":true}')
                if 'format' in payload:return io.BytesIO(b'{"message":{"content":"{\\"claims\\":[]}"},"done":true}\n')
                return io.BytesIO(b'{"message":{"content":"Shared answer."},"done":true}\n')
            lab=Lab(config=config,data=path/'data',personality_file=profile,opener=opener,
                    runner=lambda *_args,**_kwargs:SimpleNamespace(stdout='',returncode=0))
            try:
                lab.start();self.assertEqual(lab.uplink.status()['state'],'listening')
                lab.analyzer.stop();lab.analyzer=None
                gui=lab.chat('First from GUI.',origin='gui')
                self.assertEqual(gui['abort_reason'],'completed')
                with socket.create_connection(('127.0.0.1',port),timeout=3) as client:
                    client.settimeout(3);stream=client.makefile('rb')
                    self.assertIn(b'UPLINK',stream.readline())
                    client.sendall(b'Second from C64.\r')
                    records=[]
                    while True:
                        record=stream.readline().strip();records.append(record);client.sendall(b'ACK\r')
                        if record==UPLINK_END.encode():break
                    self.assertEqual(records[0],UPLINK_BEGIN.encode())
                    self.assertIn(b'Shared answer.',records)
                messages=list(lab.memory.db.execute("SELECT role,origin,text,conversation_id FROM messages ORDER BY id"))
                self.assertEqual([(r['role'],r['origin']) for r in messages],[('user','gui'),('assistant','gui'),('user','c64'),('assistant','c64')])
                self.assertEqual(len({r['conversation_id'] for r in messages}),1)
                dialogs=[item for item in payloads if 'messages' in item and 'format' not in item]
                self.assertEqual(len(dialogs),2)
                self.assertTrue(all(item['model']=='gemma4:12b' and item['messages'][0]['content']==profile.read_text(encoding='utf-8') for item in dialogs))
                self.assertIn('First from GUI.',str(dialogs[1]['messages']))
            finally:lab.stop()
            self.assertEqual(lab.uplink.status()['state'],'disabled')


if __name__=='__main__':unittest.main()
