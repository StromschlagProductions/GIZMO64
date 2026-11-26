"""Synthetic regression cases for the independent original-archive fallback."""
import tempfile
import unittest
from pathlib import Path

from memory import Memory, CpuE5, e5_directory


class HybridMemoryTest(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.path=Path(self.folder.name)/'synthetic.sqlite3'
        self.store=Memory(self.path)
        self.conversation=self.store.conversation()

    def tearDown(self):
        self.store.close()
        self.folder.cleanup()

    def say(self,text):
        return self.store.add_message(self.conversation,'user',text)

    def test_original_archive_survives_failed_extraction_and_restart(self):
        self.say('My dog is called Pippa.')
        self.say("She's a wire-haired terrier girl.")
        for number in range(30):self.say(f'I discussed topic number {number}.')
        self.store.close()
        self.store=Memory(self.path)
        payload='\n'.join(self.store.retrieve('What breed is my dog?')[0])
        self.assertIn('Pippa',payload)
        self.assertIn('wire-haired terrier',payload)
        self.assertEqual(self.store.db.execute('SELECT COUNT(*) FROM relations').fetchone()[0],0)

    def test_fts_graph_and_vector_are_independent(self):
        self.say('My hand-built receiver is called Meridian.')
        source=self.say('The Meridian receiver has a walnut case.')
        self.store.add_relation('Meridian','object','attribute','','other','walnut',source,
                                'walnut case',.94,'active','personal','case_material')
        payload='\n'.join(self.store.retrieve('What material is the Meridian receiver case?')[0])
        self.assertIn('walnut',payload)
        self.assertIn('original_user_quote',payload)
        self.assertIn('property',payload)

    @unittest.skipUnless((e5_directory()/'onnx'/'model_int8.onnx').is_file(),'Local CPU model unavailable')
    def test_cpu_vector_cross_language_with_no_extracted_claim(self):
        source=self.say('Mein altes Teleskop hat einen Messingspiegel.')
        self.assertTrue(self.store.index_next_embedding())
        self.assertEqual(self.store.embedding_engine().session.get_providers(),['CPUExecutionProvider'])
        hits=self.store.vector_matches('What material is the mirror in my old telescope?')
        self.assertIn(source,[ident for ident,_score in hits])

    def test_fiction_and_questions_are_not_raw_facts(self):
        self.say('In our story my telescope is made of moonlight.')
        self.say('Could my telescope have a gold mirror?')
        payload='\n'.join(self.store.retrieve('What is my telescope made of?')[0])
        self.assertNotIn('moonlight',payload)
        self.assertNotIn('gold mirror',payload)


if __name__=='__main__':unittest.main()
