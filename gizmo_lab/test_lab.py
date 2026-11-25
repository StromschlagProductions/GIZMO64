import io
import json
import tempfile
import unittest
from pathlib import Path
from gizmo_lab import Lab, run_benchmark

class LabTest(unittest.TestCase):
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
            lab.chat=lambda prompt,context,model: {'model':model,'config':{},'first_text_s':0.1,'total_s':0.2,'prompt_tokens':2,'generated_tokens':3,'tokens_per_s':3,'abort_reason':'completed','answer':'Antwort'}
            paths=run_benchmark(lab,[{'id':'neutral','turns':['Frage']}],[{'model':'test','options':{}}],Path(folder)/'reports')
            self.assertTrue(all(path.exists() for path in paths))
            self.assertEqual(json.loads(paths[0].read_text())[0]['answer'],'Antwort')

if __name__=='__main__': unittest.main()
