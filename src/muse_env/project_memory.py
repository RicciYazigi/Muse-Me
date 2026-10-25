"""Local project evidence. Revisions and checkpoints are independent of any model.

Fresh means unchanged since checkpoint, never true or semantically verified.
Callers own authorization; this module does not grant permission to send data.
"""
from __future__ import annotations
import hashlib
import json
import re
import sqlite3
import time
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
        CREATE TABLE IF NOT EXISTS source_files (
          project TEXT, source TEXT, root_path TEXT, relative_path TEXT, file_hash TEXT, mtime REAL,
          PRIMARY KEY(project, source));
        ''')
        self._ensure_schema()

    def _ensure_schema(self):
        cursor = self.db.cursor()
        cursor.execute("PRAGMA table_info(missions)")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        cols_to_add = [
            ("capability", "TEXT"),
            ("criteria", "TEXT"),
            ("proposal", "TEXT"),
            ("approvals", "TEXT"),
            ("artifact_path", "TEXT"),
            ("artifact_hash", "TEXT"),
            ("error", "TEXT"),
            ("completed_at", "REAL")
        ]
        cursor.execute("PRAGMA table_info(sources)")
        src_cols = {row["name"] for row in cursor.fetchall()}
        with self.db:
            for col, col_type in cols_to_add:
                if col not in existing_cols:
                    self.db.execute(f"ALTER TABLE missions ADD COLUMN {col} {col_type}")
            if "status" not in src_cols:
                self.db.execute("ALTER TABLE sources ADD COLUMN status TEXT DEFAULT 'active'")
            if "superseded_by" not in src_cols:
                self.db.execute("ALTER TABLE sources ADD COLUMN superseded_by TEXT")
            self.db.execute('''CREATE TABLE IF NOT EXISTS claims (
                id TEXT PRIMARY KEY,
                project TEXT,
                source TEXT,
                revision TEXT,
                statement TEXT,
                epistemic_status TEXT,
                superseded_by TEXT,
                created_at REAL
            )''')

    def close(self):
        self.db.close()

    def put(self, project, source, content, scope='local-only', status=None, superseded_by=None):
        if not project or not source or not isinstance(content, str):
            raise ValueError('project, source y contenido textual requeridos')
        if scope not in ('local-only', 'may_transfer', 'restricted'):
            raise ValueError('scope inválido')
        if scope == 'restricted':
            # Revocation removes the searchable/current content. Historical revisions
            # remain local for audit; deletion/retention is a separate future feature.
            content = ''
        if status is None:
            content_lower = content.lower()
            source_lower = source.lower()
            if any(k in content_lower for k in ("obsoleto", "deprecated", "outdated", "reemplazado en 2026", "no debe utilizarse en producci")) or                any(k in source_lower for k in ("_outdated", "_obsoleto", "v10_outdated", "v1.0_obsoleto")):
                status = "superseded"
            else:
                status = "active"

        revision = 'evt-' + hashlib.sha256(json.dumps(
            [project, source, content, scope], ensure_ascii=False).encode()).hexdigest()[:32]
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO revisions VALUES (?,?,?,?)',
                            (revision, project, source, content))
            self.db.execute('INSERT OR REPLACE INTO sources (project, source, revision, scope, status, superseded_by) VALUES (?,?,?,?,?,?)',
                            (project, source, revision, scope, status, superseded_by))
            self.db.execute('DELETE FROM evidence_fts WHERE project=? AND source=?', (project, source))
            if scope != 'restricted':
                self.db.execute('INSERT INTO evidence_fts VALUES (?,?,?,?)',
                                (project, source, revision, content))
        return revision

    def ingest_text(self, project, root, relative_path, scope='local-only'):
        root_path = Path(root).resolve(strict=True)
        path = (root_path / relative_path).resolve(strict=True)
        if not path.is_relative_to(root_path):
            raise PermissionError('fuera de la carpeta autorizada')
        rel_posix = path.relative_to(root_path).as_posix()
        if scope == 'restricted':
            with self.db:
                self.db.execute('DELETE FROM source_files WHERE project=? AND source=?', (project, rel_posix))
            return self.put(project, rel_posix, '', scope)
        if path.suffix.lower() not in ('.txt', '.md', '.py', '.json', '.csv'):
            raise ValueError('formato no soportado; convertir explícitamente a texto')
        if path.stat().st_size > 1_000_000:
            raise ValueError('archivo supera 1 MB; segmentación pendiente')

        content = path.read_text(encoding='utf-8')
        file_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        mtime = path.stat().st_mtime
        revision = self.put(project, rel_posix, content, scope)

        with self.db:
            self.db.execute(
                'INSERT OR REPLACE INTO source_files VALUES (?,?,?,?,?,?)',
                (project, rel_posix, str(root_path), rel_posix, file_hash, mtime)
            )
        return revision

    def search(self, project, query, *, external=False, budget=12000, limit=8, allow_superseded=False):
        if budget <= 0 or limit <= 0:
            raise ValueError('presupuesto y límite deben ser positivos')
        tokens = re.findall(r'\w{2,}', query, re.UNICODE)[:64]
        if not tokens:
            return []
        match = ' OR '.join('"' + t + '"' for t in tokens)
        superseded_clause = "AND (s.status IS NULL OR s.status != 'superseded')" if not allow_superseded else ""
        rows = self.db.execute(f'''SELECT f.source,f.revision,f.content,s.scope,s.status
            FROM evidence_fts f JOIN sources s ON s.project=f.project AND s.source=f.source
            WHERE evidence_fts MATCH ? AND f.project=? AND s.scope != 'restricted'
            AND (?=0 OR s.scope='may_transfer') {superseded_clause} ORDER BY bm25(evidence_fts),f.source''',
            (match, project, int(external)))
        selected = []
        for row in rows:
            item = dict(row)
            if len(item['content']) <= budget and len(selected) < limit:
                selected.append(item)
                budget -= len(item['content'])
        return selected

    def search_with_exclusions(self, project, query, *, external=False, budget=12000, limit=8):
        """Context Compiler v2: Returns both selected active evidence and reasoned exclusions."""
        tokens = re.findall(r'\w{2,}', query, re.UNICODE)[:64]
        if not tokens:
            return {"selected": [], "excluded": []}
        match = ' OR '.join('"' + t + '"' for t in tokens)
        
        # Query all matches including restricted and superseded to build complete epistemic record
        rows = self.db.execute('''SELECT f.source,f.revision,f.content,s.scope,s.status
            FROM evidence_fts f JOIN sources s ON s.project=f.project AND s.source=f.source
            WHERE evidence_fts MATCH ? AND f.project=? ORDER BY bm25(evidence_fts),f.source''',
            (match, project))
            
        selected = []
        excluded = []
        rem_budget = budget
        
        for row in rows:
            item = dict(row)
            src_name = item["source"]
            scope = item.get("scope", "local-only")
            status = item.get("status", "active")
            
            if scope == "restricted":
                excluded.append({
                    "source": src_name,
                    "reason": "Excluida por política de confidencialidad: permiso de transferencia revocado (scope='restricted')"
                })
            elif external and scope != "may_transfer":
                excluded.append({
                    "source": src_name,
                    "reason": f"Excluida por alcance local: permiso actual es '{scope}', no autorizado para operador externo"
                })
            elif status == "superseded":
                excluded.append({
                    "source": src_name,
                    "reason": "Excluida por vigencia: la fuente contiene directiva explícita de obsolescencia (OBSOLETO / SUPERSEDED) y está reemplazada por una versión vigente"
                })
            elif len(item["content"]) > rem_budget or len(selected) >= limit:
                excluded.append({
                    "source": src_name,
                    "reason": f"Excluida por límite de presupuesto de contexto ({budget} caracteres máximos)"
                })
            else:
                selected.append(item)
                rem_budget -= len(item["content"])

        # Also declare any project sources explicitly restricted
        restricted_rows = self.db.execute(
            "SELECT source FROM sources WHERE project=? AND scope='restricted'",
            (project,)
        ).fetchall()
        for r_row in restricted_rows:
            if not any(ex["source"] == r_row["source"] for ex in excluded):
                excluded.append({
                    "source": r_row["source"],
                    "reason": "Excluida por política de confidencialidad: permiso de transferencia revocado (scope='restricted')"
                })

        return {"selected": selected, "excluded": excluded}

    def checkpoint(self, project, goal, refs, note='', capability='deliverable_production', criteria=None):
        if not refs or not goal.strip():
            raise ValueError('misión requiere objetivo y evidencia')
        mission = 'mission-' + uuid4().hex
        crit_json = json.dumps(criteria, ensure_ascii=False) if criteria else None
        with self.db:
            # Validate revision ownership; a reference from another project is invalid.
            for source, revision in refs.items():
                row = self.db.execute('SELECT revision,scope FROM sources WHERE project=? AND source=?',
                                      (project, source)).fetchone()
                if not row or row['revision'] != revision or row['scope'] == 'restricted':
                    raise ValueError('referencia no vigente o no autorizada')
            self.db.execute('''INSERT INTO missions (id, project, goal, refs, checkpoint, state, capability, criteria)
                               VALUES (?,?,?,?,?,?,?,?)''',
                            (mission, project, goal, json.dumps(refs), note, 'draft', capability, crit_json))
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
                continue
            # Also check if file on disk has changed or disappeared
            sf = self.db.execute('SELECT root_path, relative_path, file_hash FROM source_files WHERE project=? AND source=?',
                                 (result['project'], source)).fetchone()
            if sf and sf['root_path'] and sf['relative_path']:
                disk_path = Path(sf['root_path']) / sf['relative_path']
                if not disk_path.exists():
                    result['changed_sources'].append(source)
                else:
                    try:
                        cur_text = disk_path.read_text(encoding='utf-8')
                        cur_hash = hashlib.sha256(cur_text.encode('utf-8')).hexdigest()
                        if cur_hash != sf['file_hash']:
                            result['changed_sources'].append(source)
                    except Exception:
                        result['changed_sources'].append(source)

        result['needs_review'] = bool(result['changed_sources'])
        return result

    def update_mission_proposal(self, mission_id, proposal_json, capability=None, criteria=None):
        with self.db:
            if capability and criteria:
                self.db.execute('UPDATE missions SET proposal=?, state=?, capability=?, criteria=? WHERE id=?',
                                (proposal_json, 'proposal_ready', capability, criteria, mission_id))
            elif capability:
                self.db.execute('UPDATE missions SET proposal=?, state=?, capability=? WHERE id=?',
                                (proposal_json, 'proposal_ready', capability, mission_id))
            else:
                self.db.execute('UPDATE missions SET proposal=?, state=? WHERE id=?',
                                (proposal_json, 'proposal_ready', mission_id))

    def update_mission_state(self, mission_id, state, error=None):
        with self.db:
            self.db.execute('UPDATE missions SET state=?, error=? WHERE id=?',
                            (state, error, mission_id))

    def mark_mission_completed(self, mission_id, artifact_path, artifact_hash, approvals=None):
        appr_json = json.dumps(approvals, ensure_ascii=False) if approvals else None
        now = time.time()
        with self.db:
            self.db.execute('''UPDATE missions SET state='completed', artifact_path=?, artifact_hash=?,
                               approvals=?, completed_at=?, error=NULL WHERE id=?''',
                            (artifact_path, artifact_hash, appr_json, now, mission_id))

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
