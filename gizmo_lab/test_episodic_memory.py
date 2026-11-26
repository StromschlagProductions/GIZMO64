"""Synthetic episodic grouping, provenance, exclusion, and restart tests."""
import tempfile
import unittest
from pathlib import Path

from memory import Memory


class EpisodicMemoryTest(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.path=Path(self.temporary.name)/'synthetic.sqlite3'
        self.memory=Memory(self.path)

    def tearDown(self):
        self.memory.close();self.temporary.cleanup()

    def dialog(self,*turns):
        conversation=self.memory.conversation()
        return [self.memory.add_message(conversation,role,text) for role,text in turns]

    def index(self):
        while self.memory.episode_step():pass

    def test_sessions_topics_provenance_and_restart(self):
        self.dialog(('user','I visited Bergen with Ada.'),('assistant','I hoped you enjoyed it.'),
                    ('user','We watched the northern lights.'),('user','Now about my radio: the dial is broken.'))
        self.dialog(('user','Ada and I repaired the radio together.'),('assistant','I suggested a replacement part.'))
        self.index()
        rows=self.memory.db.execute('SELECT * FROM episodes ORDER BY id').fetchall()
        self.assertEqual(len(rows),3)
        self.assertEqual([row['domain'] for row in rows],['real','real','real'])
        sources=self.memory.db.execute('SELECT role FROM episode_sources WHERE episode_id=? ORDER BY message_id',(rows[0]['id'],)).fetchall()
        self.assertEqual([row['role'] for row in sources],['user','assistant','user'])
        self.assertIn('northern lights','\n'.join(self.memory.retrieve('When did Ada and I see the northern lights?')[0]))
        self.memory.close();self.memory=Memory(self.path)
        self.assertFalse(self.memory.episode_step())
        self.assertEqual(self.memory.episode_status()['active'],3)

    def test_story_and_hypothesis_are_separate_from_real_life(self):
        self.dialog(('user','I restored an old camera.'),('user','In our story Ada and I found a moon gate.'),
                    ('assistant','I said the gate was glowing.'),('user','We entered the moon gate.'),
                    ('user','Back to real life, the camera needs a new lens.'))
        self.index()
        domains=[row[0] for row in self.memory.db.execute('SELECT domain FROM episodes ORDER BY id')]
        self.assertEqual(domains,['real','fiction','real'])
        result='\n'.join(self.memory.retrieve('What happened at the moon gate?')[0])
        self.assertIn('"domain":"fiction"',result)
        self.assertNotIn('I said the gate was glowing',result)

    def test_similar_events_same_person_keep_separate_dates_and_stated_meaning(self):
        first=self.dialog(('user','Mara and I visited the pier in May and saw a gull.'),
                          ('user','That day was important to me because we reconciled.'))
        second=self.dialog(('user','Mara and I visited the pier in October and found a compass.'))
        with self.memory.db:
            for ident in first:self.memory.db.execute("UPDATE messages SET created_at='2026-05-10T12:00:00+00:00' WHERE id=?",(ident,))
            for ident in second:self.memory.db.execute("UPDATE messages SET created_at='2026-10-10T12:00:00+00:00' WHERE id=?",(ident,))
        self.index()
        episodes=self.memory.db.execute('SELECT id,started_at,significance FROM episodes ORDER BY id').fetchall()
        self.assertEqual(len(episodes),2)
        self.assertTrue(episodes[0]['started_at'].startswith('2026-05'))
        self.assertTrue(episodes[1]['started_at'].startswith('2026-10'))
        self.assertIn('important to me',episodes[0]['significance'])
        self.assertIsNone(episodes[1]['significance'])
        answer='\n'.join(self.memory.retrieve('What did Mara and I find at the pier in October?')[0])
        self.assertIn('compass',answer)

    def test_correction_and_deletion_do_not_leak_through_episode(self):
        source,other=self.dialog(('user','The Atlas receiver has a red case.'),('user','I also repaired its speaker.'))
        relation=self.memory.add_relation('Atlas','object','attribute','','other','red',source,'red case',.95,'active','personal','case_color')
        self.index();episode=self.memory.db.execute('SELECT id FROM episodes').fetchone()[0]
        self.memory.correct_relation(relation,'blue')
        shown=self.memory.episode_display(episode)
        self.assertNotIn('red case',shown['summary'])
        self.assertIn('speaker',shown['summary'])
        result='\n'.join(self.memory.retrieve('What did I repair on the Atlas receiver?')[0])
        self.assertNotIn('red case',result)
        self.assertTrue(self.memory.delete_episode(episode))
        deleted_result='\n'.join(self.memory.retrieve('Atlas speaker repair')[0])
        self.assertNotIn('"episode":',deleted_result)
        self.assertNotIn('speaker',deleted_result)
        self.memory.close();self.memory=Memory(self.path)
        self.assertEqual(self.memory.db.execute('SELECT status FROM episodes WHERE id=?',(episode,)).fetchone()[0],'deleted')

    def test_legacy_metadata_reset_does_not_break_episode_cursor(self):
        self.dialog(('user','I repaired a vintage projector.'))
        with self.memory.db:self.memory.db.execute("UPDATE lab_metadata SET value='0.3.1'")
        self.memory.close();self.memory=Memory(self.path)
        self.assertEqual(self.memory.episode_status()['cursor'],0)
        self.assertTrue(self.memory.episode_step())

    def test_source_text_edit_invalidates_derived_episode_index(self):
        source=self.dialog(('user','I saw a copper lantern at the harbor.'))[0]
        self.index();ident=self.memory.db.execute('SELECT id FROM episodes').fetchone()[0]
        with self.memory.db:self.memory.db.execute("UPDATE messages SET text='I saw a paper lantern at the harbor.' WHERE id=?",(source,))
        self.assertEqual(self.memory.episode_display(ident)['status'],'invalid')
        self.assertEqual(self.memory.db.execute('SELECT COUNT(*) FROM episode_fts WHERE rowid=?',(ident,)).fetchone()[0],0)
        self.assertNotIn('copper','\n'.join(self.memory.retrieve('What lantern did I see at the harbor?')[0]))

    def test_deleted_real_episode_does_not_promote_weakly_related_fiction(self):
        self.dialog(('user','Mara and I studied navigation charts at the museum.'))
        self.dialog(('user','In our story Mara and I entered a glass lighthouse.'))
        self.index()
        real=self.memory.db.execute("SELECT id FROM episodes WHERE domain='real'").fetchone()[0]
        self.memory.delete_episode(real)
        result='\n'.join(self.memory.retrieve('Where did Mara and I study navigation charts?')[0])
        self.assertNotIn('lighthouse',result)
        self.assertNotIn('museum',result)


if __name__=='__main__':unittest.main()
