"""Lokales, modellunabhaengiges GIZMO-Gedaechtnis mit Herkunftsnachweis."""
import json
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
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript(SCHEMA)

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
        destination.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        return destination

    def backup(self,destination):
        destination=Path(destination)
        destination.parent.mkdir(parents=True,exist_ok=True)
        with sqlite3.connect(destination) as target:
            self.db.backup(target)
        return destination
