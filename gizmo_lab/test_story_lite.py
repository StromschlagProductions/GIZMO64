"""Synthetic routing, cancellation and structured-stream checks for Story Lite."""
import io
import json
import tempfile
import threading
import unittest
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from story import StoryDirector
from story_lite import StoryLite
from gizmo_lab import Lab


class FakeDirector:
    def __init__(self,row):self.row=row;self.library={'version':'1.1.synthetic'}
    def world(self):return self.row
    def validate_reply(self,*_):return None
    def intent(self,prompt,active):return StoryDirector.intent(prompt,active)
    def public_brief(self):return {'opening':self.row['opening_scene'],'recent_observations':[]}


class StoryLiteTest(unittest.TestCase):
    def lite(self,row):
        lab=SimpleNamespace(config={},active_response=None,analyzer=None,
                            stop_event=threading.Event())
        return StoryLite(lab,FakeDirector(row))

    def test_spontaneous_release_requires_two_scene_terms(self):
        row={'id':'synthetic','status':'prepared','opening_reply':None,
             'opening_scene':'A brass hatch stands beside a silver radio.',
             'created_at':datetime.now(timezone.utc).isoformat(),'mode':'standalone',
             'turn':0,'library_version':'1.1.synthetic'}
        lite=self.lite(row)
        self.assertEqual(lite.route('What do you think of the radio?'),'normal')
        self.assertEqual(lite.route('The brass hatch looks odd today.'),'release')

    def test_unrelated_talk_stays_normal_after_opening(self):
        row={'id':'synthetic','status':'active','opening_reply':'A public opening.',
             'opening_scene':'A brass hatch stands beside a silver radio.'}
        lite=self.lite(row)
        self.assertEqual(lite.route('Tell me a joke about a radio.'),'normal')
        self.assertEqual(lite.route('I inspect the brass hatch carefully.'),'action')

    def test_pause_aborts_a_registered_local_connection(self):
        lite=self.lite(None)
        class Socket:
            def shutdown(self,_):lite.preparing_done.set()
        connection=SimpleNamespace(sock=Socket(),close=lambda:None)
        lite.preparing_done.clear();lite.connection=connection
        lite.pause()
        self.assertTrue(lite.pause_event.is_set())
        self.assertLess(lite.last_pause_s,1)

    def test_structured_director_stream_is_assembled_before_parsing(self):
        parts=['{"value":','"synthetic"}']
        seen=[]
        def request(_endpoint,payload,timeout):
            seen.append(payload)
            lines=[json.dumps({'message':{'content':part},'done':False}) for part in parts]
            lines.append(json.dumps({'message':{'content':''},'done':True}))
            return io.BytesIO(('\n'.join(lines)+'\n').encode())
        with tempfile.TemporaryDirectory() as folder:
            director=StoryDirector(Path(folder)/'story.sqlite3',request,lambda:'synthetic',
                                   context_size=8192,stream_generation=True)
            try:
                result=director._generate('Synthetic instructions','Synthetic request',
                                          {'type':'object','properties':{'value':{'type':'string'}}},64)
                self.assertEqual(result,{'value':'synthetic'})
                self.assertTrue(seen[0]['stream'])
                self.assertEqual(seen[0]['options']['num_ctx'],8192)
            finally:director.close()

    def test_legacy_director_can_be_restored_without_replacing_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            data=Path(folder)
            (data/'GIZMO_Awakening_V2_EN.txt').write_text('Synthetic profile.',encoding='utf-8')
            config={'model':'synthetic','lean_core_enabled':True,'story_lite_enabled':True,
                    'story_enabled':True,'num_ctx':8192,'num_predict':160}
            lab=Lab(data=data,config=config)
            try:
                self.assertIsNone(lab.story)
                lab.ollama_ready=True;lab.configure_story()
                self.assertIsNotNone(lab.story_lite)
                old_path=lab.story.path
                lab.config['lean_core_enabled']=False
                lab.configure_story()
                self.assertIsNone(lab.story_lite)
                self.assertEqual(lab.story.path,old_path)
                self.assertFalse(lab.story.stream_generation)
            finally:
                if lab.story_lite:lab.story_lite.stop()
                if lab.story:lab.story.close()
                lab.memory.close()


if __name__=='__main__':unittest.main()
