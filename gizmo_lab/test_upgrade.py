import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from memory import Memory, SCHEMA
from version import VERSION, SCHEMA_VERSION


class UpgradeTest(unittest.TestCase):
    def test_v031_relation_columns_and_search_backfill_preserve_original_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'memory.sqlite3'
            with closing(sqlite3.connect(path)) as old:
                old.executescript(SCHEMA)
                old.execute("INSERT INTO conversations VALUES('synthetic','2026-01-01',NULL)")
                old.execute("INSERT INTO messages VALUES(1,'synthetic','user','My dog is Milo.','2026-01-01')")
                old.execute("INSERT INTO entities VALUES(1,'USER','person','active','2026-01-01')")
                old.execute("INSERT INTO entities VALUES(2,'Milo','pet','active','2026-01-01')")
                old.execute("INSERT INTO relations VALUES(1,1,'has_dog',2,'',1,'My dog is Milo.',.95,'active','legacy-fingerprint','2026-01-01')")
                old.execute("INSERT INTO relation_sources VALUES(1,1,'My dog is Milo.')")
                old.execute("INSERT INTO lab_metadata VALUES('app_version','0.3.1')")
                old.execute("INSERT INTO lab_metadata VALUES('analysis_revision','0.3.1')")
                old.execute('PRAGMA user_version=4')
                old.commit()
            upgraded=Memory(path)
            try:
                self.assertEqual(upgraded.db.execute('SELECT text FROM messages').fetchone()[0],'My dog is Milo.')
                self.assertEqual(upgraded.db.execute('SELECT fingerprint FROM relations').fetchone()[0],'legacy-fingerprint')
                self.assertTrue(upgraded.db.execute('SELECT claim_key FROM relations').fetchone()[0])
                self.assertIn('Milo','\n'.join(upgraded.retrieve('What is my dog called?')[0]))
                self.assertEqual(upgraded.reindexed_jobs,1)
                self.assertEqual(len(list(path.parent.glob('*.bak'))),1)
            finally:
                upgraded.close()
    def legacy(self,path):
        store=Memory(path)
        conversation=store.conversation()
        first=store.add_message(conversation,'user','My dog is Milo.')
        second=store.add_message(conversation,'user','My sister is Emma.')
        for source in (first,second):
            store.enqueue(source)
            job=store.next_job()
            store.finish_job(job['id'],'old JSON parse failure' if source==first else None)
        item=store.add_memory('personal','name','Alex',first)
        store.correct(item,'Blake')
        with store.db:
            store.db.execute('DROP TABLE lab_metadata')
            store.db.execute('PRAGMA user_version=3')
        store.close()

    def test_backup_precedes_upgrade_and_retry_is_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'memory.sqlite3'
            self.legacy(path)
            store=Memory(path)
            try:
                self.assertEqual(store.retried_jobs,1)
                self.assertEqual(store.job_counts(),{'pending':2})
                self.assertEqual(store.list_memories()[0]['value'],'Blake')
                backups=list(path.parent.glob('*.bak'))
                self.assertEqual(len(backups),1)
                with closing(sqlite3.connect(backups[0])) as old:
                    self.assertEqual(old.execute('PRAGMA user_version').fetchone()[0],3)
                    self.assertEqual(old.execute("SELECT COUNT(*) FROM analysis_jobs WHERE status='failed'").fetchone()[0],1)
                    self.assertEqual(old.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                job=store.next_job()
                store.finish_job(job['id'],'new model failure')
                completed=store.next_job()
                store.finish_job(completed['id'])
            finally:
                store.close()
            reopened=Memory(path)
            try:
                self.assertEqual(reopened.retried_jobs,0)
                self.assertEqual(reopened.job_counts(),{'failed':1,'done':1})
                self.assertEqual(len(list(path.parent.glob('*.bak'))),1)
                self.assertEqual(reopened.retry_failed(),1)
            finally:
                reopened.close()

    def test_backup_failure_leaves_legacy_database_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'memory.sqlite3'
            self.legacy(path)
            original=path.read_bytes()
            connect=sqlite3.connect
            def deny_backup(destination,*args,**kwargs):
                if str(destination).endswith('.bak'):
                    raise PermissionError('synthetic backup denial')
                return connect(destination,*args,**kwargs)
            with patch('memory.sqlite3.connect',side_effect=deny_backup):
                with self.assertRaises(PermissionError):
                    Memory(path)
            self.assertEqual(path.read_bytes(),original)

    def test_newer_schema_is_refused_without_modification(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'memory.sqlite3'
            with closing(sqlite3.connect(path)) as source:
                source.execute(f'PRAGMA user_version={SCHEMA_VERSION+1}')
            original=path.read_bytes()
            with self.assertRaisesRegex(RuntimeError,'neueren'):
                Memory(path)
            self.assertEqual(path.read_bytes(),original)
            self.assertEqual(list(path.parent.glob('*.bak')),[])

    def test_version_upgrade_backup_includes_committed_wal(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'memory.sqlite3'
            store=Memory(path)
            try:
                with store.db:
                    store.db.execute("UPDATE lab_metadata SET value='0.3.0' WHERE key='app_version'")
                source=store.add_message(store.conversation(),'user','Synthetic committed WAL message')
                upgraded=Memory(path)
                upgraded.close()
                backups=list(path.parent.glob('*.bak'))
                self.assertEqual(len(backups),1)
                with closing(sqlite3.connect(backups[0])) as backup:
                    self.assertEqual(backup.execute('SELECT text FROM messages WHERE id=?',(source,)).fetchone()[0],
                                     'Synthetic committed WAL message')
            finally:
                store.close()
