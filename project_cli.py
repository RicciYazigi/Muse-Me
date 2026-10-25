"""Explicit local ingestion, retrieval, checkpoint and Meta draft generation."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from muse_env.project_memory import ProjectMemory
from muse_env.providers import MetaMuseProvider

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='project_memory.sqlite')
    commands = parser.add_subparsers(dest='command', required=True)
    ingest = commands.add_parser('ingest')
    ingest.add_argument('project'); ingest.add_argument('root'); ingest.add_argument('files', nargs='+')
    ingest.add_argument('--scope', choices=['local-only','may_transfer','restricted'], default='local-only')
    search = commands.add_parser('search')
    search.add_argument('project'); search.add_argument('query')
    search.add_argument('--external', action='store_true')
    search.add_argument('--checkpoint', action='store_true')
    for name in ('resume', 'preview', 'generate'):
        sub = commands.add_parser(name); sub.add_argument('mission')
        if name == 'generate':
            sub.add_argument('--approve-payload-sha256', required=True)
            sub.add_argument('--model', default='muse-spark-1.3')
    args = parser.parse_args()
    memory = ProjectMemory(args.db)
    try:
        if args.command == 'ingest':
            result = {f: memory.ingest_text(args.project,args.root,f,args.scope) for f in args.files}
        elif args.command == 'search':
            result = memory.search(args.project,args.query,external=args.external)
            if args.checkpoint:
                result = {'evidence':result,'mission':memory.checkpoint(args.project,args.query,
                          {r['source']:r['revision'] for r in result})}
        elif args.command == 'resume':
            result = memory.resume(args.mission)
        else:
            import hashlib
            payload = memory.payload(args.mission)
            digest = hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
            if args.command == 'preview':
                result = {'payload':payload,'sha256':digest}
            else:
                if digest != args.approve_payload_sha256:
                    raise ValueError('aprobación no corresponde al paquete vigente')
                result = MetaMuseProvider(model=args.model).reply(payload)
        print(json.dumps(result,ensure_ascii=False,indent=2))
    finally:
        memory.close()

if __name__ == '__main__':
    main()
