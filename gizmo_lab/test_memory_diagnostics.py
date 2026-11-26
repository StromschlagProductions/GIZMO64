import tempfile
import unittest
from pathlib import Path

from analysis import contextual_name_claim, validate_claim
from memory import Memory


class MemoryDiagnosticsTest(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory()
        self.memory=Memory(Path(self.folder.name)/'synthetic.sqlite3')
        self.conversation=self.memory.conversation()

    def tearDown(self):
        self.memory.close();self.folder.cleanup()

    def add(self,role,text):
        return self.memory.add_message(self.conversation,role,text)

    def test_name_after_intervening_topics_links_to_user_role(self):
        self.add('user','I have a sister.')
        self.add('assistant','Understood.')
        for topic in ('I restored a receiver.','The receiver has a wooden case.'):
            self.add('user',topic);self.add('assistant','Interesting.')
        source=self.add('user','Her name is Elena.')
        context=self.memory.context_for_message(source)
        anchors=self.memory.analysis_anchors(context,source)
        claim=contextual_name_claim(context[-1]['text'],context,anchors)
        self.assertEqual((claim['predicate'],claim['object'],claim['status']),('has_sister','Elena','active'))
        self.memory.add_relation('USER','person','has_sister','Elena','person','',source,claim['evidence'],1,'active')
        recalled='\n'.join(self.memory.retrieve("What is my sister's name?")[0])
        self.assertIn('Elena',recalled)
        self.assertNotIn('no confirmed relationship',recalled)

    def test_historical_pet_anchor_ignores_later_dog(self):
        first=self.add('user','My dog is Pippa.')
        self.memory.add_relation('USER','person','has_dog','Pippa','pet','',first,'My dog is Pippa.',1,'active')
        self.add('assistant','Noted.')
        self.add('user','Tell me about my dog.')
        self.add('assistant','Pippa is your dog.')
        source=self.add('user',"She's a corgi girl.")
        later=self.add('user','My other dog is Rex.')
        self.memory.add_relation('USER','person','has_dog','Rex','pet','',later,'My other dog is Rex.',1,'active')
        context=self.memory.context_for_message(source)
        anchors=self.memory.analysis_anchors(context,source)
        self.assertEqual(anchors['entities'],['Pippa'])
        claim={'subject':'Pippa','subject_kind':'pet','predicate':'attribute','property_key':'breed',
               'object':'','object_kind':'other','value':'corgi','evidence':"She's a corgi girl.",
               'scope':'personal','confidence':1}
        self.assertEqual(validate_claim(claim,context[-1]['text'],context,anchors)['status'],'active')

    def test_speculative_role_never_confirms_later_name(self):
        self.add('user','Maybe I have a sister.')
        self.add('assistant','That remains uncertain.')
        source=self.add('user','Her name is Elena.')
        context=self.memory.context_for_message(source)
        anchors=self.memory.analysis_anchors(context,source)
        self.assertFalse(anchors['roles'])
        self.assertIsNone(contextual_name_claim(context[-1]['text'],context,anchors))

    def test_ambiguous_pet_reference_stays_pending(self):
        for name in ('Pippa','Rex'):
            source=self.add('user',f'My dog is {name}.')
            self.memory.add_relation('USER','person','has_dog',name,'pet','',source,f'My dog is {name}.',1,'active')
        self.add('user','Tell me about my dog.')
        source=self.add('user',"She's a corgi girl.")
        context=self.memory.context_for_message(source)
        anchors=self.memory.analysis_anchors(context,source)
        self.assertFalse(anchors['entities'])
        claim={'subject':'Pippa','subject_kind':'pet','predicate':'attribute','property_key':'breed',
               'object':'','object_kind':'other','value':'corgi','evidence':"She's a corgi girl.",
               'scope':'personal','confidence':1}
        self.assertEqual(validate_claim(claim,context[-1]['text'],context,anchors)['status'],'pending')

    def test_empty_failed_and_targeted_retry_are_distinct(self):
        first=self.add('user','Hello.');second=self.add('user','A claim?')
        for source in (first,second):self.memory.enqueue(source)
        one=self.memory.next_job();self.memory.finish_job(one['id'],claim_count=0,rejected_count=0,empty_reason='no_extractable_claims')
        two=self.memory.next_job();self.memory.finish_job(two['id'],'synthetic parse failure')
        self.assertEqual(self.memory.analysis_summary()['empty'],1)
        self.assertEqual(self.memory.analysis_summary()['failed'],1)
        self.assertTrue(self.memory.retry_job(two['id']))
        self.assertEqual(self.memory.analysis_summary()['pending'],1)
        self.assertFalse(self.memory.retry_job(one['id']))


if __name__=='__main__':unittest.main()
