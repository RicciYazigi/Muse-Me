"""Deterministic cross-domain mechanism checks; not a model benchmark."""
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).parent/'src'))
from muse_env.project_memory import ProjectMemory

SCENARIOS = [
    ('software','Corregir descuento LATAM','Descuento LATAM vigente: 15%.','Descuento LATAM vigente: 20%.'),
    ('research','Comparar resultado experimental','Resultado experimental: muestra de 20 personas.','Resultado experimental: muestra corregida de 12 personas.'),
    ('operations','Preparar entrega proveedor','Entrega proveedor: viernes, 50 unidades.','Entrega proveedor: lunes, 30 unidades.'),
    ('creative','Actualizar propuesta campaña','Campaña: público universitario, tono informal.','Campaña: público profesional, tono sobrio.'),
]

def run():
    results = []
    with TemporaryDirectory(dir=Path(__file__).parent) as folder:
        for project, goal, before, after in SCENARIOS:
            path = Path(folder)/(project+'.sqlite')
            memory = ProjectMemory(path)
            revision = memory.put(project,'brief.md',before,'may_transfer')
            memory.put(project,'privado.md','información confidencial','restricted')
            found = memory.search(project,goal,external=True)
            mission = memory.checkpoint(project,goal,{'brief.md':revision},'Retomar con evidencia')
            memory.close()
            memory = ProjectMemory(path)
            resumed = not memory.resume(mission)['needs_review']
            memory.put(project,'brief.md',after,'may_transfer')
            changed = memory.resume(mission)['needs_review']
            try:
                memory.payload(mission)
                blocked = False
            except ValueError:
                blocked = True
            results.append({'scenario':project,'retrieved':bool(found),'persisted':resumed,
                            'change_detected':changed,'stale_export_blocked':blocked,
                            'model_called':False,'human_time_seconds':None})
            memory.close()
    return {'nature':'synthetic_mechanism_checks','results':results}

if __name__ == '__main__':
    report = run()
    output = Path('validation'); output.mkdir(exist_ok=True)
    (output/'scenarios.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))
    assert all(all(row[k] for k in ('retrieved','persisted','change_detected','stale_export_blocked'))
               for row in report['results'])
