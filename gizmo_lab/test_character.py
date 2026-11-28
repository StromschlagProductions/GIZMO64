"""Profile selection and bounded example retrieval with synthetic data only."""
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from character import CharacterExamples, PROFILE_V3, PROFILE_V4, profile_source
from gizmo_lab import Lab, load_config


class CharacterTest(unittest.TestCase):
    def test_profile_sources_keep_original_v2_file(self):
        with tempfile.TemporaryDirectory() as folder:
            data=Path(folder)
            original=data/'GIZMO_Awakening_V2_EN.txt'
            original.write_text('Synthetic V2 profile',encoding='utf-8')
            before=hashlib.sha256(original.read_bytes()).digest()
            config=load_config(data)
            self.assertEqual(profile_source(data,config),('v4',PROFILE_V4))
            for mode,expected in (('v4',PROFILE_V4),('v3_examples',PROFILE_V3),('v3',PROFILE_V3),('v2',original)):
                config['personality_variant']=mode
                lab=Lab(data=data,config=dict(config))
                try:
                    self.assertEqual(lab.personality_variant,mode)
                    self.assertEqual(lab.personality_path,expected.resolve())
                    self.assertEqual(bool(lab.character_examples),mode=='v3_examples')
                finally:lab.memory.close()
            self.assertEqual(hashlib.sha256(original.read_bytes()).digest(),before)

    def test_examples_are_bounded_relevant_and_not_repeated_immediately(self):
        chooser=CharacterExamples()
        first=chooser.select('I found an ugly clock at a flea market.')
        second=chooser.select('I dropped my sandwich on the floor.')
        self.assertEqual(len(first),2)
        self.assertEqual(len(second),2)
        self.assertTrue(all(item['category']=='humour' for item in first+second))
        self.assertFalse({item['id'] for item in first}&{item['id'] for item in second})
        self.assertTrue(all(item['user'].casefold()!='I dropped my sandwich on the floor.'.casefold() for item in second))
        previous={item['id'] for item in second}
        for _ in range(8):
            current=chooser.select('I dropped my sandwich on the floor.')
            self.assertTrue(current)
            self.assertFalse(previous&{item['id'] for item in current})
            previous={item['id'] for item in current}

    def test_one_dialogue_call_with_examples_only_on_normal_route(self):
        with tempfile.TemporaryDirectory() as folder:
            config=load_config(Path(folder));config['memory_token_budget']=0
            config['personality_variant']='v3_examples'
            packets=[]
            def opener(request,timeout):
                packets.append(json.loads(request.data))
                return io.BytesIO(b'{"message":{"content":"Hello."}}\n{"done":true}\n')
            lab=Lab(data=folder,config=config,opener=opener)
            lab.model='synthetic'
            try:
                lab.chat('I found an ugly clock at a flea market.')
                self.assertEqual(len(packets),1)
                supplement=packets[-1]['messages'][0]['content'].split('Additional voice examples;',1)[1]
                self.assertEqual(supplement.count('\nUser: '),2)
                self.assertIn('never memory or story canon',supplement)
                lab.chat('I found an ugly clock at a flea market.',context=[])
                self.assertEqual(len(packets),2)
                self.assertEqual(packets[-1]['messages'][0]['content'],lab.personality)
            finally:lab.memory.close()

    def test_v4_uses_only_its_fixed_examples(self):
        with tempfile.TemporaryDirectory() as folder:
            config=load_config(Path(folder));config['memory_token_budget']=0
            packets=[]
            def opener(request,timeout):
                packets.append(json.loads(request.data))
                return io.BytesIO(b'{"message":{"content":"Hello."}}\n{"done":true}\n')
            lab=Lab(data=folder,config=config,opener=opener)
            try:
                self.assertEqual(lab.personality_variant,'v4')
                lab.chat('I found an ugly clock.')
                self.assertEqual(len(packets),1)
                self.assertEqual(packets[0]['messages'][0]['content'],PROFILE_V4.read_text(encoding='utf-8'))
                self.assertNotIn('Additional voice examples;',packets[0]['messages'][0]['content'])
            finally:lab.memory.close()
