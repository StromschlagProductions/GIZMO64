"""Synthetic, spoiler-free Story Director integration checks."""
import io
import json
import tempfile
import unittest
from pathlib import Path

from gizmo_lab import Lab
from story import StoryDirector


class FakeModel:
    def __init__(self):
        self.payloads=[]
        self.invalid=False
        self.leak=False
        self.dialogue_leak=False

    def __call__(self,request,timeout):
        data=json.loads(request.data)
        self.payloads.append(data)
        if data.get('stream'):
            text='SYNTHETIC_CANON_TOKEN' if self.dialogue_leak else 'A fictional observation and a free choice.'
            return io.BytesIO((json.dumps({'message':{'content':text}})+'\n{"done":true}\n').encode())
        prompt=data['messages'][-1]['content']
        if 'Explicitly initialize' in prompt:
            output={key:['SYNTHETIC '+key] for key in
                    ('foundational_facts','causal_dependencies','open_questions','evidence_routes','observation_channels')}
            output['public_state']={'campaign':'unrevealed'}
        elif 'Initialize one short playable adventure' in prompt:
            output={'title':'Synthetic Test World','style':'test','truth':'SYNTHETIC_CANON_TOKEN',
                    'reveal_terms':['SYNTHETIC_REVEAL_A','SYNTHETIC_REVEAL_B'],
                    'routes':['inspect virtual object','ask virtual witness'],
                    'public_scene':'A fictional room invites exploration.',
                    'public_state':{'room':{'examined':False},'witness':{'spoken':False}}}
        else:
            if self.invalid:
                return io.BytesIO(b'{"message":{"content":"not json"}}')
            event=json.loads(prompt.split(' Repair invalid output')[0])
            output={'event_id':event['event_id'],'expected_version':event['expected_version'],
                    'public_scene':'SYNTHETIC_CANON_TOKEN' if self.leak else 'A fictional object can now be examined.',
                    'consequence':'The room is marked examined.',
                    'state_patch':{'room':{'examined':True}},'referenced_ids':['room'],'complete':False}
        return io.BytesIO(json.dumps({'message':{'content':json.dumps(output)},'done':True}).encode())


class StoryTest(unittest.TestCase):
    def setup_lab(self,root,model):
        data=Path(root)
        (data/'GIZMO_Awakening_V2_EN.txt').write_text('Synthetic companion profile.',encoding='utf-8')
        return Lab(data=data,config={'model':'synthetic','story_enabled':True,'lean_core_enabled':False,'num_ctx':8192,'num_predict':128},opener=model)

    def test_story_isolated_from_real_memory_and_resumes(self):
        with tempfile.TemporaryDirectory() as folder:
            model=FakeModel();lab=self.setup_lab(folder,model)
            try:
                result=lab.chat('/story')
                self.assertEqual(result['abort_reason'],'completed')
                world=lab.story.world()
                secret=json.loads(world['secret_json'])['truth']
                self.assertFalse(lab.memory.db.execute('SELECT 1 FROM messages LIMIT 1').fetchone())
                self.assertNotIn(secret,json.dumps(model.payloads[-1]))
                result=lab.chat('I inspect the virtual object.')
                self.assertEqual(result['abort_reason'],'completed')
                self.assertEqual(lab.story.world()['turn'],1)
                self.assertNotIn(secret,json.dumps(model.payloads[-1]))
                self.assertIn('A fictional observation and a free choice.',
                              [item['content'] for item in model.payloads[-1]['messages'] if item['role']=='assistant'])
                lab.chat('/pause')
                count=len(model.payloads)
                lab.chat('How are you?')
                self.assertEqual(len(model.payloads),count+1) # no director call
                self.assertEqual(lab.memory.db.execute('SELECT COUNT(*) FROM messages').fetchone()[0],2)
                lab.story.close();lab.memory.close()
                lab=self.setup_lab(folder,model)
                self.assertEqual(json.loads(lab.story.world()['secret_json'])['truth'],secret)
                self.assertEqual(lab.story.world()['turn'],1)
                self.assertEqual(lab.chat('/story')['abort_reason'],'completed')
                self.assertEqual(lab.story.world()['status'],'active')
            finally:
                lab.story.close();lab.memory.close()

    def test_invalid_proposal_rolls_back_and_retry_is_bounded(self):
        with tempfile.TemporaryDirectory() as folder:
            model=FakeModel();lab=self.setup_lab(folder,model)
            try:
                lab.chat('/story')
                model.invalid=True
                with self.assertRaises(ValueError):lab.chat('I inspect the virtual object.')
                self.assertEqual(lab.story.world()['turn'],0)
                self.assertEqual(lab.story.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],0)
            finally:
                lab.story.close();lab.memory.close()

    def test_origin_campaign_only_on_explicit_activation(self):
        with tempfile.TemporaryDirectory() as folder:
            model=FakeModel();lab=self.setup_lab(folder,model)
            try:
                self.assertFalse(lab.story.campaign_active())
                lab.chat('/story')
                self.assertFalse(lab.story.campaign_active())
                lab.chat('/abandon')
                lab.chat('/origin')
                self.assertTrue(lab.story.campaign_active())
                self.assertEqual(lab.story.world()['mode'],'connected')
                self.assertNotIn('foundational_facts',json.dumps(model.payloads[-1]))
            finally:
                lab.story.close();lab.memory.close()

    def test_reveal_gate_blocks_director_and_dialogue_leaks(self):
        with tempfile.TemporaryDirectory() as folder:
            model=FakeModel();lab=self.setup_lab(folder,model)
            try:
                lab.chat('/story')
                model.leak=True
                with self.assertRaises(ValueError):lab.chat('I inspect the room.')
                self.assertEqual(lab.story.world()['turn'],0)
                model.leak=False;model.dialogue_leak=True
                result=lab.chat('I inspect the room.')
                self.assertEqual(result['abort_reason'],'story_validation_failed')
                self.assertEqual(lab.story.world()['turn'],0)
            finally:
                lab.story.close();lab.memory.close()

    def test_duplicate_decision_cannot_commit_twice(self):
        with tempfile.TemporaryDirectory() as folder:
            model=FakeModel();lab=self.setup_lab(folder,model)
            try:
                lab.chat('/story')
                decision=lab.story.plan('I inspect the room.')
                lab.story.commit(decision,'A fictional consequence.')
                with self.assertRaises(RuntimeError):lab.story.commit(decision,'A duplicate consequence.')
                self.assertEqual(lab.story.db.execute('SELECT COUNT(*) FROM events').fetchone()[0],1)
            finally:
                lab.story.close();lab.memory.close()

    def test_dialogue_uses_public_state_without_director_and_survives_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            model=FakeModel();lab=self.setup_lab(folder,model)
            try:
                lab.chat('/story')
                before=len(model.payloads)
                result=lab.chat('What can you tell me about this room?')
                self.assertEqual(result['abort_reason'],'completed')
                self.assertEqual(result['story_metrics']['route'],'dialogue')
                self.assertEqual(len(model.payloads),before+1)
                self.assertFalse(model.payloads[-1].get('format'))
                self.assertEqual(lab.story.world()['turn'],0)
                self.assertEqual(lab.story.db.execute('SELECT COUNT(*) FROM dialogue').fetchone()[0],1)
                self.assertFalse(lab.memory.db.execute('SELECT 1 FROM messages LIMIT 1').fetchone())
                lab.story.close();lab.memory.close()
                lab=self.setup_lab(folder,model)
                self.assertIn('What can you tell me about this room?',
                              [message['content'] for message in lab.story.dialogue_history(lab.story.world()['id'])])
            finally:
                lab.story.close();lab.memory.close()

    def test_route_covers_question_action_and_ambiguous_conversation(self):
        route=StoryDirector.intent
        self.assertEqual(route('How is your day?',True),'dialogue')
        self.assertEqual(route('What did we already notice?',True),'dialogue')
        self.assertEqual(route('I carefully examine the door.',True),'action')
        self.assertEqual(route('Open the door.',True),'action')
        self.assertEqual(route('Could you open the door?',True),'action')
        self.assertEqual(route('Can you tell me what we know?',True),'dialogue')
        self.assertEqual(route('Tell me what you see',True),'dialogue')
        self.assertEqual(route('Tell me what we already know.',True),'dialogue')
        self.assertEqual(route('Show me what you noticed.',True),'dialogue')
        self.assertEqual(route('Please tell me what you see.',True),'dialogue')
        self.assertEqual(route('Tell the witness about the key.',True),'action')
        self.assertEqual(route('I wonder what the door means.',True),'dialogue')
        self.assertEqual(route('Open the door.',False),'normal')

    def test_dialogue_spoiler_is_buffered(self):
        with tempfile.TemporaryDirectory() as folder:
            model=FakeModel();lab=self.setup_lab(folder,model)
            try:
                lab.chat('/story')
                model.dialogue_leak=True
                visible=[]
                result=lab.chat('What do you notice?',on_text=visible.append)
                self.assertEqual(result['abort_reason'],'story_validation_failed')
                self.assertEqual(visible,['The fictional reply could not be safely shown.'])
                self.assertEqual(lab.story.db.execute('SELECT COUNT(*) FROM dialogue').fetchone()[0],0)
            finally:
                lab.story.close();lab.memory.close()

    def test_tell_me_uses_one_dialogue_call_and_does_not_change_world(self):
        with tempfile.TemporaryDirectory() as folder:
            model=FakeModel();lab=self.setup_lab(folder,model)
            try:
                lab.chat('/story')
                before=len(model.payloads)
                turn=lab.story.world()['turn']
                result=lab.chat('Tell me what you see')
                self.assertEqual(result['abort_reason'],'completed')
                self.assertEqual(result['story_metrics']['route'],'dialogue')
                self.assertEqual(len(model.payloads),before+1)
                self.assertEqual(lab.story.world()['turn'],turn)
            finally:
                lab.story.close();lab.memory.close()

    def test_story_schema_upgrade_backups_existing_world(self):
        with tempfile.TemporaryDirectory() as folder:
            model=FakeModel();lab=self.setup_lab(folder,model)
            try:
                lab.chat('/story')
                world_id=lab.story.world()['id']
                lab.story.db.execute('DROP TABLE dialogue')
                lab.story.db.execute('PRAGMA user_version=1')
                lab.story.db.commit()
                lab.story.close();lab.memory.close()
                lab=self.setup_lab(folder,model)
                self.assertEqual(lab.story.world()['id'],world_id)
                self.assertEqual(lab.story.db.execute('PRAGMA user_version').fetchone()[0],2)
                self.assertTrue((Path(folder)/'story.sqlite3.before-v2.bak').is_file())
            finally:
                lab.story.close();lab.memory.close()

    def test_large_profile_uses_configured_context_without_truncation(self):
        with tempfile.TemporaryDirectory() as folder:
            model=FakeModel();lab=self.setup_lab(folder,model)
            try:
                lab.personality='Synthetic profile sentence. '*150
                result=lab.chat('/story')
                self.assertEqual(result['abort_reason'],'completed')
                dialogue=model.payloads[-1]
                self.assertEqual(dialogue['options']['num_ctx'],8192)
                self.assertEqual(dialogue['messages'][0]['content'],lab.personality)
            finally:
                lab.story.close();lab.memory.close()


if __name__=='__main__':unittest.main()
