import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from analysis import validate_claim
from gizmo_lab import Lab
from memory import Memory, assemble_context, ContextBudgetError, message_cost
from test_analysis import claim


class ActiveMemoryTest(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.store=Memory(Path(self.temporary.name)/'memory.sqlite3')
        self.conversation=self.store.conversation()

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def relation(self,subject,predicate,target,text,status='active',scope='personal',object_kind='other',value=False):
        source=self.store.add_message(self.conversation,'user',text)
        return self.store.add_relation(subject,'person',predicate,'' if value else target,object_kind,target if value else '',source,text,.95,status,scope)

    def test_connected_family_and_pet_facts_with_indirect_english(self):
        self.relation('USER','has_sister','Emma','My sister is Emma.',object_kind='person')
        self.relation('Emma','studied','psychology','Emma studied psychology.',value=True)
        self.relation('USER','has_dog','Milo','My dog is Milo.',object_kind='pet')
        result='\n'.join(self.store.retrieve('What field did my sibling train in?',900)[0])
        for word in ('Emma','psychology','has_sister'):
            self.assertIn(word,result)
        result='\n'.join(self.store.retrieve('What is my four-legged companion called?',900)[0])
        self.assertIn('Milo',result)

    def test_direct_confirmed_family_question_uses_compact_graph_evidence(self):
        self.relation('USER','has_sister','Emma','My sister is Emma.',object_kind='person')
        self.relation('Emma','studied','psychology','Emma studied psychology.',value=True)
        decoy=self.store.add_message(self.conversation,'user','A separate museum conversation.')
        with patch.object(self.store,'archive_matches',return_value=[(decoy,self.conversation,'A separate museum conversation.',.8)]) as archive, \
             patch.object(self.store,'episode_matches',return_value=([(99,'{"episode":99}','episode:99')],[])) as episodes:
            lines=self.store.retrieve('Do you know my sister?',900)[0]
            payload='\n'.join(lines)
            self.assertIn('"relation":"has_sister","target":"Emma"',payload)
            self.assertIn('psychology',payload)
            self.assertEqual(self.store.last_retrieval['selected'][0],'relation:1')
            self.assertNotIn('museum',payload)
            self.assertNotIn('"episode"',payload)
            archive.assert_not_called()
            episodes.assert_not_called()
            self.store.retrieve('When did I tell you about my sister?',900)
            archive.assert_called_once()
            episodes.assert_called_once()

    def test_lean_budget_keeps_relevant_pet_fact_amid_unrelated_memory(self):
        for number in range(24):
            self.relation('USER','likes',f'hobby{number}',f'I like hobby{number}.',value=True)
        self.relation('USER','has_dog','Nori','My dog is Nori.',object_kind='pet')
        source=self.store.add_message(self.conversation,'user','Nori is a terrier.')
        self.store.add_relation('Nori','pet','attribute',None,None,'terrier',source,
                                'Nori is a terrier.',.95,'active',property_key='breed')
        result='\n'.join(self.store.retrieve('What breed is my dog Nori?',450)[0])
        self.assertIn('Nori',result)
        self.assertIn('terrier',result)

    def test_language_neutral_graph_and_legacy_small_budget(self):
        source=self.store.add_message(self.conversation,'user','My name is Alex.')
        self.store.extract_user('My name is Alex.',source)
        self.relation('USER','has_sister','Élodie','Meine Schwester heißt Élodie.',object_kind='person')
        self.relation('Élodie','studied','Psychologie','Élodie studierte Psychologie.',value=True)
        result='\n'.join(self.store.retrieve('What subject did my sister study?',300)[0])
        for word in ('Alex','Élodie','Psychologie','has_sister'):
            self.assertIn(word,result)

    def test_confirmed_only_conflicts_fiction_and_deleted_variants(self):
        first=self.relation('Emma','lives_in','Berlin','Emma lives in Berlin.',value=True)
        self.relation('Emma','lives_in','Rome','Emma lives in Rome.',value=True)
        self.relation('Emma','likes','Mars','In our story Emma likes Mars.','fictional','narrative',value=True)
        result='\n'.join(self.store.retrieve('Where does Emma live and what does she like?',2000)[0])
        self.assertNotIn('Berlin',result)
        self.assertNotIn('Rome',result)
        self.assertNotIn('Mars',result)
        self.store.set_relation_status(first,'deleted')
        new_source=self.store.add_message(self.conversation,'user','Emma lives in Berlin.')
        same=self.store.add_relation('emma','person','lives_in','Berlin','place','Berlin',new_source,'Emma lives in Berlin.',1,'active')
        self.assertEqual(first,same)
        self.assertEqual(self.store.db.execute('SELECT status FROM relations WHERE id=?',(same,)).fetchone()[0],'deleted')
        self.assertNotIn('Berlin','\n'.join(self.store.retrieve('Berlin',2000)[0]))

    def test_interest_set_and_deleted_sources_not_replayed_in_history(self):
        source=self.store.add_message(self.conversation,'user','I like astronomy. I love old radios.')
        self.store.extract_user('I like astronomy. I love old radios.',source)
        self.assertEqual(len(self.store.list_memories()),2)
        repeated=self.store.add_message(self.conversation,'user','I like astronomy.')
        self.store.extract_user('I like astronomy.',repeated)
        self.store.add_message(self.conversation,'assistant','You like astronomy.')
        item=next(m for m in self.store.list_memories() if m['value']=='astronomy')
        self.store.delete(item['id'])
        self.assertEqual(self.store.dialog_history(self.conversation),[])
        self.assertEqual(self.store.extract_user('I like astronomy.',repeated),[])

    def test_manually_corrected_name_overrides_its_old_source(self):
        source=self.store.add_message(self.conversation,'user','My name is Alex.')
        ident=self.store.extract_user('My name is Alex.',source)[0]
        self.relation('USER','related_to','Alex','My name is Alex.',object_kind='person')
        # The real analysis of that exact source is suppressed after a correction.
        self.store.correct(ident,'Blake')
        self.assertTrue(self.store.source_blocked(source))
        result='\n'.join(self.store.retrieve('What is my name?',400)[0])
        self.assertIn('Blake',result)

    def test_speculation_and_quoted_other_person_not_fast_personal_facts(self):
        for text in ('Maybe my name is Alex.','In our story, my name is Alex.','Emma said: my name is Alex.','My name is Alex?'):
            source=self.store.add_message(self.conversation,'user',text)
            self.assertEqual(self.store.extract_user(text,source),[])

    def test_object_and_literal_forms_do_not_duplicate_and_sources_survive(self):
        first=self.relation('Emma','studied','psychology','Emma studied psychology.',value=True)
        source=self.store.add_message(self.conversation,'user','Emma studied psychology again.')
        same=self.store.add_relation('Emma','person','studied','psychology','other','psychology',source,'psychology',.9,'active')
        self.assertEqual(first,same)
        self.assertEqual(len(self.store.relation_sources(first)),2)
        self.assertEqual(len(self.store.list_relations()),1)

    def test_unambiguous_pronoun_only_user_evidence(self):
        item=claim('Emma','studied','','psychology','She studied psychology.')
        context=[{'role':'user','text':'My sister is Emma.'},{'role':'assistant','text':'Fine.'},{'role':'user','text':'She studied psychology.'}]
        self.assertEqual(validate_claim(item,context[-1]['text'],context)['status'],'active')
        for earlier,role in [('My sister Emma and my sister Nora are here.','user'),('My sister Emma met Nora.','user'),('My sister is Emma.','assistant'),('Maybe my sister is Emma.','user')]:
            context[0]={'role':role,'text':earlier}
            self.assertEqual(validate_claim(item,context[-1]['text'],context)['status'],'pending')

    def test_deleted_family_anchor_cannot_be_inferred_from_orphan_attributes(self):
        ident=self.relation('USER','has_sister','Emma','My sister is Emma.',object_kind='person')
        self.relation('Emma','studied','psychology','Emma studied psychology.',value=True)
        self.store.set_relation_status(ident,'deleted')
        result='\n'.join(self.store.retrieve('What did my sister study?',900)[0])
        self.assertNotIn('Emma',result)
        self.assertNotIn('psychology',result)
        self.assertIn('no confirmed relationship',result)

    def test_conflicting_dialogue_is_hidden_until_manual_resolution(self):
        self.relation('Emma','lives_in','Berlin','Emma lives in Berlin.',value=True)
        other=self.relation('Emma','lives_in','Rome','Emma lives in Rome.',value=True)
        self.assertEqual(self.store.dialog_history(self.conversation),[])
        self.store.set_relation_status(other,'active')
        result='\n'.join(self.store.retrieve('Where does Emma live?',900)[0])
        self.assertIn('Rome',result)
        self.assertNotIn('Berlin',result)


class ContextTest(unittest.TestCase):
    def test_budget_retains_whole_turns_and_can_exceed_twenty_messages(self):
        history=[message for i in range(30) for message in [{'role':'user','content':str(i)},{'role':'assistant','content':'OK'}]]
        messages,_,metrics=assemble_context('identity','clock','hello',history,lambda *_:([],0),{'num_ctx':8192,'num_predict':128})
        self.assertGreater(metrics['history_messages'],20)
        self.assertEqual(metrics['input_bound'],sum(map(message_cost,messages)))
        self.assertLessEqual(metrics['input_bound']+metrics['output_reserved']+metrics['template_reserved'],8192)
        messages,_,metrics=assemble_context('identity','clock','hello',history,lambda *_:([],0),{'num_ctx':4096,'num_predict':128,'history_token_budget':300})
        self.assertEqual(metrics['history_messages']%2,0)
        self.assertGreater(metrics['omitted_history_messages'],0)
        self.assertEqual(messages[-1],{'role':'user','content':'hello'})

    def test_oversized_identity_or_current_message_fails_without_truncation(self):
        for identity,prompt in [('X'*10000,'hello'),('identity','ü'*10000)]:
            with self.assertRaises(ContextBudgetError):
                assemble_context(identity,'clock',prompt,[],lambda *_:([],0),{'num_ctx':4096,'num_predict':128})

    def test_exactly_one_generation_request_and_no_memory_model_call(self):
        with tempfile.TemporaryDirectory() as folder:
            calls=[]
            def opener(request,timeout):
                calls.append(json.loads(request.data))
                return io.BytesIO(b'{"message":{"content":"Hello"},"done":true}\n')
            lab=Lab(data=folder,opener=opener,runner=lambda *a,**k: type('Result',(),{'stdout':''})())
            try:
                lab.chat('Hello')
                self.assertEqual(len(calls),1)
                self.assertTrue(calls[0]['stream'])
            finally:
                lab.stop()
