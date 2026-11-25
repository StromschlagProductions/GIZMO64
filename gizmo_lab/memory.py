"""Lokales, modellunabhaengiges GIZMO-Gedaechtnis mit Herkunftsnachweis."""
import json
import hashlib
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = '''
CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL, role TEXT NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(conversation_id) REFERENCES conversations(id));
CREATE INDEX IF NOT EXISTS messages_conversation ON messages(conversation_id,id);
CREATE TABLE IF NOT EXISTS memories(id INTEGER PRIMARY KEY, domain TEXT NOT NULL, key TEXT NOT NULL, value TEXT NOT NULL, confidence REAL NOT NULL, importance INTEGER NOT NULL DEFAULT 1, source_message_id INTEGER, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(source_message_id) REFERENCES messages(id));
CREATE TABLE IF NOT EXISTS memory_events(id INTEGER PRIMARY KEY, memory_id INTEGER NOT NULL, action TEXT NOT NULL, old_value TEXT, new_value TEXT, created_at TEXT NOT NULL, FOREIGN KEY(memory_id) REFERENCES memories(id));
CREATE TABLE IF NOT EXISTS entities(id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE, kind TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL, UNIQUE(name,kind));
CREATE TABLE IF NOT EXISTS relations(id INTEGER PRIMARY KEY, subject_id INTEGER NOT NULL, predicate TEXT NOT NULL, object_id INTEGER, value TEXT, source_message_id INTEGER NOT NULL, evidence TEXT NOT NULL, confidence REAL NOT NULL, status TEXT NOT NULL, fingerprint TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL, FOREIGN KEY(subject_id) REFERENCES entities(id), FOREIGN KEY(object_id) REFERENCES entities(id), FOREIGN KEY(source_message_id) REFERENCES messages(id));
CREATE TABLE IF NOT EXISTS relation_sources(relation_id INTEGER NOT NULL, message_id INTEGER NOT NULL, evidence TEXT NOT NULL, PRIMARY KEY(relation_id,message_id), FOREIGN KEY(relation_id) REFERENCES relations(id), FOREIGN KEY(message_id) REFERENCES messages(id));
CREATE TABLE IF NOT EXISTS relation_events(id INTEGER PRIMARY KEY, relation_id INTEGER NOT NULL, action TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(relation_id) REFERENCES relations(id));
CREATE TABLE IF NOT EXISTS analysis_jobs(id INTEGER PRIMARY KEY, message_id INTEGER NOT NULL UNIQUE, status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, FOREIGN KEY(message_id) REFERENCES messages(id));
CREATE INDEX IF NOT EXISTS memories_domain_key ON memories(domain,key,status);
CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(key,value,content='memories',content_rowid='id');
CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memories BEGIN INSERT INTO memory_fts(rowid,key,value) VALUES(new.id,new.key,new.value); END;
CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memories BEGIN INSERT INTO memory_fts(memory_fts,rowid,key,value) VALUES('delete',old.id,old.key,old.value); END;
CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON memories BEGIN INSERT INTO memory_fts(memory_fts,rowid,key,value) VALUES('delete',old.id,old.key,old.value); INSERT INTO memory_fts(rowid,key,value) VALUES(new.id,new.key,new.value); END;
'''


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


class Memory:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            probe=sqlite3.connect(self.path)
            needs_migration=not probe.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='analysis_jobs'").fetchone()
            if needs_migration:
                backup=self.path.with_name(self.path.name+'.pre-v03-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'.bak')
                with sqlite3.connect(backup) as target:
                    probe.backup(target)
            probe.close()
        self.db = sqlite3.connect(self.path,check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript(SCHEMA)
        self.db.execute('PRAGMA user_version=3')
        with self.db:
            self.db.execute("UPDATE analysis_jobs SET status='pending' WHERE status='processing'")

    def close(self):
        self.db.close()

    def conversation(self, previous=None):
        if previous and self.db.execute('SELECT 1 FROM conversations WHERE id=?', (previous,)).fetchone():
            return previous
        ident = str(uuid.uuid4())
        with self.db:
            self.db.execute('INSERT INTO conversations VALUES(?,?,NULL)', (ident, utc_now()))
        return ident

    def latest_conversation(self):
        row = self.db.execute('SELECT id FROM conversations ORDER BY started_at DESC,rowid DESC LIMIT 1').fetchone()
        return row['id'] if row else None

    def add_message(self, conversation_id, role, text):
        with self.db:
            cur = self.db.execute('INSERT INTO messages(conversation_id,role,text,created_at) VALUES(?,?,?,?)',
                                  (conversation_id, role, text, utc_now()))
        return cur.lastrowid

    def enqueue(self, message_id):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO analysis_jobs(message_id,status,created_at,updated_at) VALUES(?,'pending',?,?)",(message_id,utc_now(),utc_now()))

    def enqueue_archive(self):
        with self.db:
            self.db.execute("INSERT OR IGNORE INTO analysis_jobs(message_id,status,created_at,updated_at) SELECT id,'pending',?,? FROM messages WHERE role='user'",(utc_now(),utc_now()))
        return self.job_counts()

    def job_counts(self):
        return {row['status']:row['count'] for row in self.db.execute('SELECT status,COUNT(*) count FROM analysis_jobs GROUP BY status')}

    def retry_failed(self):
        with self.db:
            cur=self.db.execute("UPDATE analysis_jobs SET status='pending',error=NULL,updated_at=? WHERE status='failed'",(utc_now(),))
        return cur.rowcount

    def failed_jobs(self,limit=30):
        return [dict(row) for row in self.db.execute("SELECT id,message_id,attempts,error,updated_at FROM analysis_jobs WHERE status='failed' ORDER BY id LIMIT ?",(limit,))]

    def next_job(self):
        row=self.db.execute("SELECT j.id,j.message_id,m.text,m.conversation_id FROM analysis_jobs j JOIN messages m ON m.id=j.message_id WHERE j.status='pending' ORDER BY j.id LIMIT 1").fetchone()
        if not row:
            return None
        with self.db:
            self.db.execute("UPDATE analysis_jobs SET status='processing',attempts=attempts+1,updated_at=? WHERE id=?",(utc_now(),row['id']))
        return dict(row)

    def finish_job(self, job_id, error=None):
        with self.db:
            self.db.execute('UPDATE analysis_jobs SET status=?,error=?,updated_at=? WHERE id=?',
                            ('pending' if error=='cancelled' else ('failed' if error else 'done'),error,utc_now(),job_id))

    def context_for_message(self, message_id, limit=5):
        row=self.db.execute('SELECT conversation_id FROM messages WHERE id=?',(message_id,)).fetchone()
        if not row:
            return []
        return [dict(item) for item in self.db.execute('SELECT id,role,text FROM messages WHERE conversation_id=? AND id<=? ORDER BY id DESC LIMIT ?', (row['conversation_id'],message_id,limit))][::-1]

    def entity(self,name,kind):
        name=name.strip()
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO entities(name,kind,created_at) VALUES(?,?,?)',(name,kind,utc_now()))
        return self.db.execute('SELECT id FROM entities WHERE name=? AND kind=?',(name,kind)).fetchone()['id']

    def add_relation(self,subject,subject_kind,predicate,obj,object_kind,value,source_id,evidence,confidence,status):
        subject_id=self.entity(subject,subject_kind)
        object_id=self.entity(obj,object_kind) if obj else None
        fingerprint=hashlib.sha256(json.dumps([subject.casefold(),predicate,obj.casefold(),value.casefold()],ensure_ascii=False).encode('utf-8')).hexdigest()
        if predicate in ('lives_in','works_as'):
            other=self.db.execute("SELECT 1 FROM relations WHERE subject_id=? AND predicate=? AND fingerprint<>? AND status='active' LIMIT 1",(subject_id,predicate,fingerprint)).fetchone()
            if other:
                status='pending'
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO relations(subject_id,predicate,object_id,value,source_message_id,evidence,confidence,status,fingerprint,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)',
                            (subject_id,predicate,object_id,value,source_id,evidence,confidence,status,fingerprint,utc_now()))
            relation_id=self.db.execute('SELECT id FROM relations WHERE fingerprint=?',(fingerprint,)).fetchone()['id']
            self.db.execute('INSERT OR IGNORE INTO relation_sources(relation_id,message_id,evidence) VALUES(?,?,?)',(relation_id,source_id,evidence))
        return relation_id

    def list_entities(self):
        return [dict(row) for row in self.db.execute('SELECT * FROM entities ORDER BY id')]

    def list_relations(self):
        return [dict(row) for row in self.db.execute('SELECT r.*,s.name subject,o.name object FROM relations r JOIN entities s ON s.id=r.subject_id LEFT JOIN entities o ON o.id=r.object_id ORDER BY r.id')]

    def relation_sources(self,relation_id):
        return [dict(row) for row in self.db.execute('SELECT * FROM relation_sources WHERE relation_id=? ORDER BY message_id',(relation_id,))]

    def set_relation_status(self,relation_id,status):
        if status not in ('active','deleted'):
            raise ValueError(status)
        row=self.db.execute('SELECT status FROM relations WHERE id=?',(relation_id,)).fetchone()
        if not row:
            raise KeyError(relation_id)
        if row['status']=='deleted' and status=='active':
            raise ValueError('Geloeschte Beziehung nicht automatisch reaktivieren')
        with self.db:
            self.db.execute('UPDATE relations SET status=? WHERE id=?',(status,relation_id))
            self.db.execute('INSERT INTO relation_events(relation_id,action,created_at) VALUES(?,?,?)',
                            (relation_id,'manual_'+status,utc_now()))

    def recent(self, conversation_id, limit=20):
        rows = self.db.execute('SELECT role,text FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT ?',
                               (conversation_id, limit)).fetchall()
        return [{'role': row['role'], 'content': row['text']} for row in reversed(rows)]

    def last_message_time(self, conversation_id=None):
        if conversation_id:
            row = self.db.execute('SELECT created_at FROM messages WHERE conversation_id=? ORDER BY id DESC LIMIT 1', (conversation_id,)).fetchone()
        else:
            row = self.db.execute('SELECT created_at FROM messages ORDER BY id DESC LIMIT 1').fetchone()
        return row['created_at'] if row else None

    def add_memory(self, domain, key, value, source_message_id=None, confidence=.8, importance=1):
        if domain not in ('identity','personal','episodic','semantic','narrative','temporal'):
            raise ValueError('Ungueltiger Gedaechtnisbereich')
        existing = self.db.execute("SELECT * FROM memories WHERE domain=? AND key=? AND status='active' ORDER BY id DESC LIMIT 1", (domain,key)).fetchone()
        if existing and existing['value'].casefold() == value.casefold():
            return existing['id']
        pending = self.db.execute("SELECT id FROM memories WHERE domain=? AND key=? AND value=? AND status='pending' ORDER BY id DESC LIMIT 1", (domain,key,value)).fetchone()
        if pending:
            return pending['id']
        tombstone=self.db.execute("SELECT id FROM memories WHERE domain=? AND key=? AND value=? AND status IN ('deleted','superseded') ORDER BY id DESC LIMIT 1",(domain,key,value)).fetchone()
        if tombstone:
            return tombstone['id']
        status = 'pending' if existing else 'active'
        stamp = utc_now()
        with self.db:
            cur = self.db.execute('INSERT INTO memories(domain,key,value,confidence,importance,source_message_id,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)',
                                  (domain,key,value,confidence,importance,source_message_id,status,stamp,stamp))
        return cur.lastrowid

    def correct(self, memory_id, value):
        row = self.db.execute('SELECT domain,key,value FROM memories WHERE id=?', (memory_id,)).fetchone()
        if not row:
            raise KeyError(memory_id)
        stamp = utc_now()
        with self.db:
            self.db.execute("UPDATE memories SET status='superseded',updated_at=? WHERE domain=? AND key=? AND status='active'", (stamp,row['domain'],row['key']))
            self.db.execute("UPDATE memories SET value=?,status='active',confidence=1,updated_at=? WHERE id=?", (value,stamp,memory_id))
            self.db.execute('INSERT INTO memory_events(memory_id,action,old_value,new_value,created_at) VALUES(?,?,?,?,?)',
                            (memory_id,'manual_correction',row['value'],value,stamp))

    def delete(self, memory_id):
        with self.db:
            cur = self.db.execute("UPDATE memories SET status='deleted',updated_at=? WHERE id=?", (utc_now(),memory_id))
            if cur.rowcount:
                self.db.execute('INSERT INTO memory_events(memory_id,action,created_at) VALUES(?,?,?)',
                                (memory_id,'manual_delete',utc_now()))
        return cur.rowcount

    def list_memories(self, include_pending=False):
        status = "status IN ('active','pending')" if include_pending else "status='active'"
        return [dict(row) for row in self.db.execute(f'SELECT * FROM memories WHERE {status} ORDER BY id DESC')]

    def extract_user(self, text, source_id):
        """Konservative Regeln: nur ausdrueckliche Selbstaussagen, keine Modellaussagen."""
        rules = [
            (r'\b(?:ich heiße|ich heisse|mein name ist)\s+([\w-]{2,40})\b','name',5),
            (r'\b(?:my name is|you can call me|i am called)\s+([\w-]{2,40})\b','name',5),
            (r'\b(?:ich interessiere mich für|ich interessiere mich fuer)\s+([^.!?\n]{2,80})','interest',2),
            (r'\b(?:i am interested in|i like|i love)\s+([^.!?\n]{2,80})','interest',2),
            (r'\b(?:mein lieblingsfilm ist)\s+([^.!?\n]{2,80})','favorite_film',2),
            (r'\b(?:my favorite (?:movie|film) is)\s+([^.!?\n]{2,80})','favorite_film',2),
            (r'\b(?:meine lieblingsmusik ist)\s+([^.!?\n]{2,80})','favorite_music',2),
            (r'\b(?:my favorite music is)\s+([^.!?\n]{2,80})','favorite_music',2),
        ]
        found=[]
        for pattern,key,importance in rules:
            for match in re.finditer(pattern,text,flags=re.I):
                value = match.group(1).strip(' ,;:')
                found.append(self.add_memory('personal',key,value,source_id,.9,importance))
        return found

    def retrieve(self, query, budget=300):
        started=time.perf_counter()
        rows=self.db.execute("SELECT * FROM memories WHERE status='active' AND ((domain='identity') OR (domain='personal' AND importance>=4)) ORDER BY importance DESC,id DESC LIMIT 12").fetchall()
        selected={row['id']:dict(row) for row in rows}
        words=[word for word in re.findall(r'\w+',query,flags=re.UNICODE) if len(word)>2]
        if words:
            expression=' OR '.join('"'+word.replace('"','')+'"' for word in words[:8])
            try:
                matches=self.db.execute("SELECT m.* FROM memory_fts f JOIN memories m ON m.id=f.rowid WHERE memory_fts MATCH ? AND m.status='active' ORDER BY bm25(memory_fts),m.importance DESC LIMIT 12", (expression,)).fetchall()
                selected.update((row['id'],dict(row)) for row in matches)
            except sqlite3.OperationalError:
                pass
        output=[]; used=0
        for item in sorted(selected.values(),key=lambda row:(-row['importance'],-row['id'])):
            line=f"[{item['domain']} #{item['id']} {item['created_at']}] {item['key']}: {item['value']}"
            cost=max(1,len(line)//4)
            if used+cost>budget:
                continue
            output.append(line);used+=cost
        return output,time.perf_counter()-started

    def export(self,destination):
        destination=Path(destination)
        destination.parent.mkdir(parents=True,exist_ok=True)
        data={'conversations':[dict(row) for row in self.db.execute('SELECT * FROM conversations')],
              'messages':[dict(row) for row in self.db.execute('SELECT * FROM messages ORDER BY id')],
              'memories':[dict(row) for row in self.db.execute('SELECT * FROM memories ORDER BY id')]}
        data['memory_events']=[dict(row) for row in self.db.execute('SELECT * FROM memory_events ORDER BY id')]
        data['entities']=[dict(row) for row in self.db.execute('SELECT * FROM entities ORDER BY id')]
        data['relations']=[dict(row) for row in self.db.execute('SELECT * FROM relations ORDER BY id')]
        data['relation_sources']=[dict(row) for row in self.db.execute('SELECT * FROM relation_sources ORDER BY relation_id,message_id')]
        data['relation_events']=[dict(row) for row in self.db.execute('SELECT * FROM relation_events ORDER BY id')]
        destination.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        return destination

    def backup(self,destination):
        destination=Path(destination)
        destination.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(destination) as target:
            self.db.backup(target)
        return destination
