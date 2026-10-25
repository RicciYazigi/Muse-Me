import pytest
from muse_env.project_memory import ProjectMemory

def test_restart_change_revoke_and_scope(tmp_path):
    path = tmp_path / 'memory.sqlite'
    m = ProjectMemory(path)
    r = m.put('p','spec','descuento vigente 15%', 'may_transfer')
    m.put('other','spec','descuento 90%', 'may_transfer')
    m.put('p','private','descuento secreto', 'local-only')
    hits = m.search('p','descuento',external=True)
    assert [h['source'] for h in hits] == ['spec']
    mission = m.checkpoint('p','corregir descuento',{'spec':r})
    m.close()
    m = ProjectMemory(path)
    assert not m.resume(mission)['needs_review']
    assert m.payload(mission)['current_context']['content'] == 'descuento vigente 15%'
    m.put('p','spec','descuento vigente 20%', 'may_transfer')
    assert m.resume(mission)['changed_sources'] == ['spec']
    with pytest.raises(ValueError): m.payload(mission)
    m.put('p','spec','no almacenar', 'restricted')
    assert m.search('p','descuento',external=True) == []
    m.close()

def test_revision_ownership_and_local_transfer(tmp_path):
    m = ProjectMemory(tmp_path/'m.sqlite')
    r = m.put('p','a','evidencia')
    with pytest.raises(ValueError): m.checkpoint('other','goal',{'a':r})
    mission = m.checkpoint('p','goal',{'a':r})
    with pytest.raises(PermissionError): m.payload(mission)
    m.close()

def test_explicit_ingestion_no_escape_and_no_restricted_read(tmp_path):
    root = tmp_path/'root'; root.mkdir()
    (tmp_path/'outside.txt').write_text('private')
    (root/'spec.txt').write_text('válido',encoding='utf-8')
    m = ProjectMemory(tmp_path/'m.sqlite')
    with pytest.raises(PermissionError): m.ingest_text('p',root,'../outside.txt')
    m.ingest_text('p',root,'spec.txt')
    assert m.search('p','valido')[0]['content'] == 'válido'
    m.ingest_text('p',root,'spec.txt','restricted')
    assert not m.search('p','valido')
    m.close()

def test_budget_and_fts_query_escaping(tmp_path):
    m = ProjectMemory(tmp_path/'m.sqlite')
    m.put('p','a','requisito vigente')
    assert not m.search('p','requisito',budget=3)
    assert m.search('p','"requisito" OR (*) --')[0]['source'] == 'a'
    m.close()

def test_action_retrieves_evidence_absent_from_window():
    from muse_env.context_builder import ContextBuilder
    from muse_env.events import ObservationEvent
    from muse_env.episodes import Episode
    current = ObservationEvent('text','editor','def calculate(): pass',ts=2,permission_scope='may_transfer')
    spec = ObservationEvent('text','docs','Descuento regional LATAM 15%',ts=1,permission_scope='may_transfer')
    package = ContextBuilder().build(action='Corregir descuento LATAM',target_application='editor',
        current_content=current.content,episodes=[Episode('e',[spec,current])])
    assert package['additional_context'][0]['source'] == spec.event_id

def test_restricted_content_is_not_stored_and_revocation_blocks_existing_checkpoint(tmp_path):
    m = ProjectMemory(tmp_path/'m.sqlite')
    m.put('p','restricted','secret-token-unique','restricted')
    assert not m.db.execute("SELECT 1 FROM revisions WHERE content LIKE '%secret-token-unique%'").fetchone()
    r = m.put('p','spec','entrega viernes','may_transfer')
    mission = m.checkpoint('p','Preparar entrega',{'spec':r})
    m.put('p','spec','entrega viernes','local-only')
    with pytest.raises(ValueError): m.payload(mission)
    assert m.resume(mission)['needs_review']
    m.close()
