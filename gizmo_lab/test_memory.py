import io
import json
import tempfile
import unittest
from pathlib import Path
from gizmo_lab import Lab
from memory import Memory


class MemoryTest(unittest.TestCase):
    def test_name_after_thirty_turns_and_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            requests=[]
            def opener(request, timeout):
                if request.full_url.endswith('/api/chat'):
                    requests.append(json.loads(request.data))
                    return io.BytesIO(b'{"message":{"content":"Understood."},"done":false}\n{"done":true,"eval_count":2,"eval_duration":1000000000}\n')
                return io.BytesIO(b'{"done":true}')
            lab=Lab(data=folder,opener=opener)
            lab.model='gemma4:12b'
            lab.chat('My name is Alex.')
            for number in range(30):
                lab.chat(f'Neutral question {number}?')
            lab.chat('What is my name?')
            system='\n'.join(message['content'] for message in requests[-1]['messages'] if message['role']=='system')
            self.assertIn('Alex',system)
            self.assertNotIn('My name is Alex.',[m['content'] for m in requests[-1]['messages'][-20:]])
            conversation=lab.conversation_id
            lab.stop()
            resumed=Lab(data=folder,opener=opener)
            self.assertEqual(resumed.conversation_id,conversation)
            resumed.chat('Do you remember my name?')
            system='\n'.join(message['content'] for message in requests[-1]['messages'] if message['role']=='system')
            self.assertIn('Alex',system)
            resumed.stop()

    def test_interests_conflict_correction_delete_and_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Memory(Path(folder)/'memory.sqlite3')
            conversation=db.conversation()
            source=db.add_message(conversation,'user','I like astronomy. My name is Alex.')
            ids=db.extract_user('I like astronomy. My name is Alex.',source)
            self.assertEqual(len(ids),2)
            name=next(item for item in db.list_memories() if item['key']=='name')
            self.assertEqual(name['source_message_id'],source)
            self.assertTrue(any('astronomy' in line for line in db.retrieve('astronomy')[0]))
            next_source=db.add_message(conversation,'user','My name is Blake.')
            db.extract_user('My name is Blake.',next_source)
            pending=next(item for item in db.list_memories(True) if item['status']=='pending')
            self.assertEqual(pending['value'],'Blake')
            self.assertEqual(next(item for item in db.list_memories() if item['key']=='name')['value'],'Alex')
            db.correct(pending['id'],'Blake')
            self.assertEqual(next(item for item in db.list_memories() if item['key']=='name')['value'],'Blake')
            db.delete(pending['id'])
            self.assertFalse(any(item['key']=='name' for item in db.list_memories()))
            self.assertTrue(db.backup(Path(folder)/'backup.sqlite3').exists())
            self.assertEqual(len(json.loads(db.export(Path(folder)/'export.json').read_text())['messages']),2)
            db.close()

    def test_model_change_keeps_archive_and_domains_separate(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Memory(Path(folder)/'memory.sqlite3')
            story=db.add_memory('narrative','ship','Aurora',importance=2)
            personal=db.add_memory('personal','name','Alex',importance=5)
            result=db.retrieve('What is my name?')[0]
            self.assertTrue(any('Alex' in line for line in result))
            self.assertFalse(any('Aurora' in line for line in result))
            db.close()
            lab=Lab(data=folder)
            lab.model='gemma4:12b'
            lab.unload=lambda model: setattr(lab,'model',None)
            lab.preload=lambda model: setattr(lab,'model',model)
            lab.switch_model('another-model')
            self.assertEqual(lab.memory.list_memories()[0]['id'],personal)
            lab.stop()


if __name__=='__main__': unittest.main()
