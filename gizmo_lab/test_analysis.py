import io
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from analysis import Analyzer, validate_claim, KINDS, PREDICATES, SCOPES
from memory import Memory
from version import VERSION


def claim(subject,predicate,obj,value,evidence,confidence=.95,scope='personal',subject_kind='person',object_kind='other'):
    return {'subject':subject,'subject_kind':subject_kind,'predicate':predicate,'object':obj,
            'object_kind':object_kind,'property_key':'','value':value,'evidence':evidence,'scope':scope,'confidence':confidence}


class AnalysisTest(unittest.TestCase):
    def test_redundant_attribute_object_is_normalized(self):
        item=claim('Nora','attribute','antique postcards','antique postcards','Nora collects antique postcards.')
        item['property_key']='collection'
        validated=validate_claim(item,'Nora collects antique postcards.')
        self.assertEqual(validated['object'],'')
        self.assertEqual(validated['property_key'],'collection')
    def test_unmarked_model_narrative_label_does_not_hide_conflict(self):
        item=claim('Emma','works_as','','pilot','Emma works as a pilot.',scope='narrative')
        validated=validate_claim(item,'Emma works as a pilot.')
        self.assertEqual((validated['scope'],validated['status']),('hypothesis','pending'))
    def test_schema_evidence_and_speculation(self):
        direct=claim('Alex','has_sister','Emma','','My sister Emma')
        self.assertEqual(validate_claim(direct,'My sister Emma studies psychology.')['status'],'active')
        self.assertIsNone(validate_claim(direct,'My dog Milo likes walks.'))
        maybe=claim('Alex','related_to','GIZMO','','Maybe my sister created you')
        self.assertEqual(validate_claim(maybe,'Maybe my sister created you')['status'],'pending')
        shortened=claim('Alex','related_to','GIZMO','','my sister created you')
        self.assertEqual(validate_claim(shortened,'Maybe my sister created you')['status'],'pending')
        fiction=claim('Alex','experienced','','space flight','In our story, Alex flew to Mars',scope='narrative')
        self.assertEqual(validate_claim(fiction,'In our story, Alex flew to Mars')['status'],'fictional')
        mistaken=claim('Alex','experienced','','space flight','Alex flew to Mars')
        self.assertEqual(validate_claim(mistaken,'In our story, Alex flew to Mars')['status'],'fictional')
        pronoun=claim('Emma','studied','','psychology','She studied psychology')
        self.assertEqual(validate_claim(pronoun,'She studied psychology')['status'],'pending')

    def test_german_uncertainty_fiction_and_pronouns(self):
        for source,evidence,status in [
            ('Vielleicht wohnt Emma in Berlin.','Emma in Berlin','pending'),
            ('In unserer erfundenen Geschichte lebt Emma auf dem Mars.','Emma auf dem Mars','fictional'),
            ('Sie hat Psychologie studiert.','Sie hat Psychologie studiert.','pending'),
        ]:
            with self.subTest(source=source):
                item=claim('Emma','related_to','','test',evidence)
                self.assertEqual(validate_claim(item,source)['status'],status)

    def test_truncated_model_output_is_failed_not_committed(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'memory.sqlite3'
            store=Memory(path)
            mid=store.add_message(store.conversation(),'user','My dog is named Milo.')
            store.enqueue(mid)
            def opener(request,timeout):
                return io.BytesIO(json.dumps({'done_reason':'length','message':{'content':'{"claims":[]}'}}).encode())
            analyzer=Analyzer(path,{'model':'gemma4:12b'},opener)
            try:
                self.assertFalse(analyzer.analyze_one())
                self.assertEqual(store.job_counts(),{'failed':1})
                self.assertEqual(store.list_relations(),[])
                self.assertIn('Token'.lower(),store.db.execute('SELECT error FROM analysis_jobs').fetchone()[0].lower())
            finally:
                analyzer.stop()
                store.close()

    def test_interrupted_analysis_stream_never_stores_partial_claims(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'memory.sqlite3'
            store=Memory(path)
            store.enqueue(store.add_message(store.conversation(),'user','My dog is Milo.'))
            def opener(request,timeout):
                return io.BytesIO(b'{"message":{"content":"{\\"claims\\":[]}"},"done":false}\n')
            analyzer=Analyzer(path,{'model':'gemma4:12b'},opener)
            try:
                self.assertFalse(analyzer.analyze_one())
                self.assertEqual(store.job_counts(),{'failed':1})
                self.assertEqual(store.list_relations(),[])
            finally:
                analyzer.stop();store.close()

    def test_people_relations_reanalysis_and_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'memory.sqlite3'
            store=Memory(path); conversation=store.conversation()
            texts=["My sister's name was Emma.","She studied psychology.","She loved science fiction.","My dog is named Milo."]
            ids=[store.add_message(conversation,'user',text) for text in texts]
            store.enqueue_archive()
            produced=[claim('Alex','has_sister','Emma','',texts[0],object_kind='person'),
                      claim('Emma','studied','','psychology',texts[1]),
                      claim('Emma','likes','','science fiction',texts[2]),
                      claim('Alex','has_dog','Milo','',texts[3],object_kind='pet')]
            calls=[]
            def opener(request,timeout):
                payload=json.loads(request.data)
                calls.append(payload)
                self.assertIs(payload['think'],False)
                properties=payload['format']['properties']['claims']['items']['properties']
                self.assertEqual(set(properties['predicate']['enum']),PREDICATES)
                self.assertEqual(set(properties['subject_kind']['enum']),KINDS)
                self.assertEqual(set(properties['scope']['enum']),SCOPES)
                self.assertEqual(payload['messages'][-1]['role'],'user')
                source=payload['messages'][-1]['content']
                self.assertIn('reference only',payload['messages'][-2]['content'])
                item=produced[texts.index(source)]
                return io.BytesIO(json.dumps({'message':{'content':json.dumps({'claims':[item]})}}).encode())
            analyzer=Analyzer(path,{'model':'gemma4:12b'},opener)
            for _ in texts:
                self.assertTrue(analyzer.analyze_one())
            self.assertFalse(analyzer.analyze_one())
            relations=store.list_relations()
            self.assertEqual(len(relations),4)
            self.assertEqual(relations[0]['subject'],'Alex')
            self.assertEqual(relations[0]['object'],'Emma')
            self.assertEqual(relations[1]['subject'],'Emma')
            self.assertEqual(relations[1]['status'],'active')
            self.assertEqual(relations[3]['object'],'Milo')
            self.assertTrue(all(request['format']['type']=='object' for request in calls))
            analyzer.stop();store.close()
            resumed=Memory(path)
            resumed.enqueue_archive()
            self.assertEqual(resumed.job_counts().get('pending',0),0)
            self.assertEqual(len(resumed.list_relations()),4)
            resumed.close()

    def test_cancelled_job_is_pending_after_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'memory.sqlite3'
            store=Memory(path); c=store.conversation(); mid=store.add_message(c,'user','My dog is named Milo.')
            store.enqueue(mid)
            job=store.next_job()
            self.assertEqual(store.job_counts().get('processing'),1)
            store.close()
            reopened=Memory(path)
            self.assertEqual(reopened.job_counts().get('pending'),1)
            reopened.finish_job(job['id'],'cancelled')
            self.assertEqual(reopened.job_counts().get('pending'),1)
            reopened.close()

    def test_pause_and_deleted_source_not_recreated(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'memory.sqlite3'
            store=Memory(path); c=store.conversation()
            mid=store.add_message(c,'user','My name is Alex.')
            memory_id=store.add_memory('personal','name','Alex',mid)
            store.delete(memory_id)
            store.enqueue(mid)
            analyzer=Analyzer(path,{'model':'gemma4:12b'},lambda req,timeout: self.fail('deleted source must not be sent'))
            analyzer.pause()
            self.assertFalse(analyzer.analyze_one())
            analyzer.resume()
            self.assertTrue(analyzer.analyze_one())
            self.assertEqual(store.list_relations(),[])
            analyzer.stop();store.close()

    def test_relation_dedup_sources_and_conflict(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Memory(Path(folder)/'memory.sqlite3')
            c=store.conversation()
            a=store.add_message(c,'user','Emma lives in Orion City.')
            b=store.add_message(c,'user','Emma still lives in Orion City.')
            d=store.add_message(c,'user','Emma lives in Vega City now.')
            first=store.add_relation('Emma','person','lives_in','','other','Orion City',a,'Emma lives in Orion City',.9,'active')
            same=store.add_relation('emma','person','lives_in','','other','Orion City',b,'Emma still lives in Orion City',.9,'active')
            self.assertEqual(first,same)
            self.assertEqual(len(store.relation_sources(first)),2)
            other=store.add_relation('Emma','person','lives_in','','other','Vega City',d,'Emma lives in Vega City now',.9,'active')
            self.assertEqual(next(r for r in store.list_relations() if r['id']==other)['status'],'pending')
            store.set_relation_status(other,'active')
            store.set_relation_status(other,'deleted')
            self.assertEqual(store.add_relation('Emma','person','lives_in','','other','Vega City',d,'Emma lives in Vega City now',.9,'active'),other)
            self.assertEqual(next(r for r in store.list_relations() if r['id']==other)['status'],'deleted')
            store.close()

    def test_migration_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'memory.sqlite3'
            old=sqlite3.connect(path)
            old.execute('CREATE TABLE marker(value TEXT)')
            old.execute("INSERT INTO marker VALUES('keep')")
            old.commit();old.close()
            migrated=Memory(path)
            self.assertEqual(migrated.db.execute('SELECT value FROM marker').fetchone()[0],'keep')
            self.assertTrue(list(Path(folder).glob('*.pre-v'+VERSION+'-*.bak')))
            migrated.close()


if __name__=='__main__': unittest.main()
