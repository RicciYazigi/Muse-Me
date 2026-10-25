"""Local project evidence. Revisions and checkpoints are independent of any model.

Fresh means unchanged since checkpoint, never true or semantically verified.
Callers own authorization; this module does not grant permission to send data.
"""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
from pathlib import Path
from uuid import uuid4


class ProjectMemory:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS sources (
          project TEXT, source TEXT, revision TEXT, scope TEXT,
          PRIMARY KEY(project,source));
        CREATE TABLE IF NOT EXISTS revisions (
          revision TEXT PRIMARY KEY, project TEXT, source TEXT, content TEXT);
        CREATE VIRTUAL TABLE IF NOT EXISTS evidence_fts USING fts5(
          project UNINDEXED, source UNINDEXED, revision UNINDEXED, content,
          tokenize='unicode61 remove_diacritics 2');
        CREATE TABLE IF NOT EXISTS missions (
          id TEXT PRIMARY KEY, project TEXT, goal TEXT, refs TEXT,
          checkpoint TEXT, state TEXT);
        ''')

    def close(self):
        self.db.close()

    def put(self, project, source, content, scope='local-only'):
        if not project or not source or not isinstance(content, str):
            raise ValueError('project, source y contenido textual requeridos')
        if scope not in ('local-only', 'may_transfer', 'restricted'):
            raise ValueError('scope inválido')
        if scope == 'restricted':
            # Revocation removes the searchable/current content. Historical revisions
            # remain local for audit; deletion/retention is a separate future feature.
            content = ''
        revision = 'evt-' + hashlib.sha256(json.dumps(
            [project, source, content, scope], ensure_ascii=False).encode()).hexdigest()[:32]
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO revisions VALUES (?,?,?,?)',
                            (revision, project, source, content))
            self.db.execute('INSERT OR REPLACE INTO sources VALUES (?,?,?,?)',
                            (project, source, revision, scope))
            self.db.execute('DELETE FROM evidence_fts WHERE project=? AND source=?', (project, source))
            if scope != 'restricted':
                self.db.execute('INSERT INTO evidence_fts VALUES (?,?,?,?)',
                                (project, source, revision, content))
        return revision

    def ingest_text(self, project, root, relative_path, scope='local-only'):
        root = Path(root).resolve(strict=True)
        path = (root / relative_path).resolve(strict=True)
        if not path.is_relative_to(root):
            raise PermissionError('fuera de la carpeta autorizada')
        if scope == 'restricted':
            return self.put(project, path.relative_to(root).as_posix(), '', scope)
        if path.suffix.lower() not in ('.txt', '.md', '.py', '.json', '.csv'):
            raise ValueError('formato no soportado; convertir explícitamente a texto')
        if path.stat().st_size > 1_000_000:
            raise ValueError('archivo supera 1 MB; segmentación pendiente')
        return self.put(project, path.relative_to(root).as_posix(), path.read_text(encoding='utf-8'), scope)

    def search(self, project, query, *, external=False, budget=12000, limit=8):
        if budget <= 0 or limit <= 0:
            raise ValueError('presupuesto y límite deben ser positivos')
        tokens = re.findall(r'\w{2,}', query, re.UNICODE)[:64]
        if not tokens:
            return []
        match = ' OR '.join('"' + t + '"' for t in tokens)
        rows = self.db.execute('''SELECT f.source,f.revision,f.content,s.scope
            FROM evidence_fts f JOIN sources s ON s.project=f.project AND s.source=f.source
            WHERE evidence_fts MATCH ? AND f.project=? AND s.scope != 'restricted'
            AND (?=0 OR s.scope='may_transfer') ORDER BY bm25(evidence_fts),f.source''',
            (match, project, int(external)))
        selected = []
        for row in rows:
            item = dict(row)
            if len(item['content']) <= budget and len(selected) < limit:
                selected.append(item)
                budget -= len(item['content'])
        return selected

    def checkpoint(self, project, goal, refs, note=''):
        if not refs or not goal.strip():
            raise ValueError('misión requiere objetivo y evidencia')
        mission = 'mission-' + uuid4().hex
        with self.db:
            # Validate revision ownership; a reference from another project is invalid.
            for source, revision in refs.items():
                row = self.db.execute('SELECT revision,scope FROM sources WHERE project=? AND source=?',
                                      (project, source)).fetchone()
                if not row or row['revision'] != revision or row['scope'] == 'restricted':
                    raise ValueError('referencia no vigente o no autorizada')
            self.db.execute('INSERT INTO missions VALUES (?,?,?,?,?,?)',
                            (mission, project, goal, json.dumps(refs), note, 'draft'))
        return mission

    def resume(self, mission):
        row = self.db.execute('SELECT * FROM missions WHERE id=?', (mission,)).fetchone()
        if not row:
            raise KeyError(mission)
        result = dict(row)
        result['refs'] = json.loads(result['refs'])
        result['changed_sources'] = []
        for source, revision in result['refs'].items():
            current = self.db.execute('SELECT revision,scope FROM sources WHERE project=? AND source=?',
                                      (result['project'], source)).fetchone()
            if not current or current['revision'] != revision or current['scope'] == 'restricted':
                result['changed_sources'].append(source)
        result['needs_review'] = bool(result['changed_sources'])
        return result

    def payload(self, mission):
        state = self.resume(mission)
        if state['needs_review']:
            raise ValueError('fuentes cambiaron: crear un checkpoint revisado')
        records = []
        for source, revision in state['refs'].items():
            row = self.db.execute('''SELECT r.content,s.scope FROM revisions r JOIN sources s
              ON r.project=s.project AND r.source=s.source WHERE r.revision=?''', (revision,)).fetchone()
            if row['scope'] != 'may_transfer':
                raise PermissionError('fuente no autorizada para transferencia')
            records.append({'source': revision, 'status': 'observed', 'content': row['content']})
        return {'action': state['goal'], 'current_context': records[0], 'additional_context': records[1:]}
