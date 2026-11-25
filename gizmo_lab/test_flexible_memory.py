import tempfile
import unittest
from pathlib import Path

from memory import Memory, normalize_property_key


class FlexibleMemoryTest(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.store=Memory(Path(self.temporary.name)/'synthetic.sqlite3')
        self.conversation=self.store.conversation()

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def source(self,text):
        return self.store.add_message(self.conversation,'user',text)

    def attribute(self,subject,kind,key,value,text,status='active'):
        return self.store.add_relation(subject,kind,'attribute','','other',value,self.source(text),text,.96,status,'personal',key)

    def test_arbitrary_properties_retrieve_together_and_deduplicate(self):
        dog=self.store.add_relation('USER','person','has_dog','Lucy','pet','',self.source('My dog is called Lucy.'),'My dog is called Lucy.',.95,'active')
        breed=self.attribute('Lucy','pet','Breed','beagle',"She's a beagle girl.")
        knob=self.attribute('Atlas','object','Tuning knob condition','chipped','The Atlas tuning knob is chipped.')
        again=self.attribute('Atlas','object','tuning_knob_condition','chipped','Atlas has a chipped tuning knob.')
        self.assertEqual(knob,again)
        self.assertEqual(normalize_property_key('Tuning knob condition'),'tuning_knob_condition')
        self.assertEqual(len(self.store.relation_sources(knob)),2)
        recalled='\n'.join(self.store.retrieve('What breed is my dog?')[0])
        self.assertIn('Lucy',recalled)
        self.assertIn('beagle',recalled)
        self.assertIn('chipped','\n'.join(self.store.retrieve('What is the Atlas tuning knob condition?')[0]))

    def test_correction_and_deletion_prevent_resurrection(self):
        original=self.attribute('Atlas','object','finish','red','The Atlas finish is red.')
        self.store.correct_relation(original,'blue')
        self.assertEqual(self.attribute('Atlas','object','finish','red','The Atlas finish is red again.'),original)
        recalled='\n'.join(self.store.retrieve('What is the Atlas finish?')[0])
        self.assertIn('blue',recalled)
        self.assertNotIn('red',recalled)
        self.store.set_relation_status(original,'deleted')
        self.attribute('Atlas','object','finish','blue','The Atlas finish is blue.')
        self.assertNotIn('blue','\n'.join(self.store.retrieve('What is the Atlas finish?')[0]))

    def test_fiction_and_conflict_are_not_confirmed(self):
        self.attribute('Lucy','pet','breed','beagle','Lucy is a beagle.')
        self.attribute('Lucy','pet','breed','collie','Lucy is a collie.')
        self.attribute('Lucy','pet','imaginary_power','flight','In our story Lucy can fly.','fictional')
        recalled='\n'.join(self.store.retrieve('What breed is Lucy?')[0])
        self.assertNotIn('beagle',recalled)
        self.assertNotIn('collie',recalled)
        self.assertNotIn('flight','\n'.join(self.store.retrieve('What is Lucy imaginary power?')[0]))


if __name__=='__main__':
    unittest.main()
