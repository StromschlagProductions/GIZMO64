import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from memory import Memory
from version import VERSION, SCHEMA_VERSION


class UpgradeTest(unittest.TestCase):
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
                self.assertEqual(store.job_counts(),{'pending':1,'done':1})
                self.assertEqual(store.list_memories()[0]['value'],'Blake')
                backups=list(path.parent.glob('*.bak'))
                self.assertEqual(len(backups),1)
                with closing(sqlite3.connect(backups[0])) as old:
                    self.assertEqual(old.execute('PRAGMA user_version').fetchone()[0],3)
                    self.assertEqual(old.execute("SELECT COUNT(*) FROM analysis_jobs WHERE status='failed'").fetchone()[0],1)
                    self.assertEqual(old.execute('PRAGMA integrity_check').fetchone()[0],'ok')
                job=store.next_job()
                store.finish_job(job['id'],'new model failure')
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
