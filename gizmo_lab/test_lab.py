import io
import json
import tempfile
import unittest
from pathlib import Path
from gizmo_lab import Lab, run_benchmark, should_quit, DEFAULT_MODEL

class LabTest(unittest.TestCase):
    def test_q_is_normal_text_and_reference_model(self):
        self.assertFalse(should_quit('Q'))
        self.assertFalse(should_quit('Warum?'))
        self.assertTrue(should_quit('/quit'))
        self.assertEqual(DEFAULT_MODEL, 'gemma4:12b')
    def test_stream_context_metrics_and_think_filter(self):
        seen=[]
        def open_request(req, timeout):
            seen.append(json.loads(req.data) if req.data else None)
            if req.full_url.endswith('/api/generate'):
                return io.BytesIO(b'{"done":true}')
            return io.BytesIO(b'{"message":{"content":"Hallo <thi"}}\n'
                              b'{"message":{"content":"nk>intern</think>Welt"}}\n'
                              b'{"done":true,"prompt_eval_count":12,"eval_count":3,"eval_duration":1000000000}\n')
        with tempfile.TemporaryDirectory() as folder:
            lab=Lab(data=folder,opener=open_request)
            lab.preload('testmodell')
            chunks=[]
            result=lab.chat('Grüße?',on_text=chunks.append)
            self.assertEqual(result['answer'],'Hallo Welt')
            self.assertEqual(result['prompt_tokens'],12)
            self.assertEqual(result['generated_tokens'],3)
            self.assertEqual(result['tokens_per_s'],3)
            self.assertEqual(lab.context[-2]['content'],'Grüße?')
            self.assertTrue(seen[-1]['stream'])
            self.assertEqual(seen[-1]['model'],'testmodell')
            lab.stop()
    def test_benchmark_private_reports(self):
        with tempfile.TemporaryDirectory() as folder:
            lab=Lab(data=folder)
            lab.model='test'
            lab.chat=lambda prompt,context,model: {'model':model,'options':{},'personality_sha256':lab.profile_sha256,'first_text_s':0.1,'total_s':0.2,'prompt_tokens':2,'generated_tokens':3,'tokens_per_s':3,'abort_reason':'completed','answer':'Antwort'}
            paths=run_benchmark(lab,[{'id':'neutral','turns':['Frage']}],[{'model':'test','options':{}}],Path(folder)/'reports')
            self.assertTrue(all(path.exists() for path in paths))
            self.assertEqual(json.loads(paths[0].read_text())[0]['answer'],'Antwort')

    def test_real_cold_unload_then_warm_preload(self):
        with tempfile.TemporaryDirectory() as folder:
            requests=[]
            def opener(req, timeout):
                requests.append(json.loads(req.data))
                return io.BytesIO(b'{"done":true}')
            lab=Lab(data=folder,opener=opener)
            lab.model='test'
            lab.chat=lambda prompt,context,model: {'model':model,'options':{},'personality_sha256':lab.profile_sha256,'first_text_s':.1,'total_s':.2,'prompt_tokens':2,'generated_tokens':3,'tokens_per_s':3,'abort_reason':'completed','answer':'Antwort'}
            variants=[{'model':'test','start':'cold','options':{'temperature':.2}},
                      {'model':'test','start':'warm','options':{'top_p':.8}}]
            paths=run_benchmark(lab,[{'id':'neutral','turns':['Frage']}],variants,Path(folder)/'reports')
            rows=json.loads(paths[0].read_text())
            self.assertEqual([row['start_mode'] for row in rows],['cold','warm'])
            self.assertIsNone(rows[0]['preload_s'])
            self.assertIsNotNone(rows[1]['preload_s'])
            self.assertEqual(rows[0]['personality_sha256'],rows[1]['personality_sha256'])
            self.assertEqual([req['keep_alive'] for req in requests],[0,-1])
            self.assertEqual(lab.config['temperature'],.7)

if __name__=='__main__': unittest.main()
