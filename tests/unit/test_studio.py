import threading
import pytest
from tests.unit.test_workbench import catalog


def test_library_render_persists_an_artifact_without_modifying_catalog(tmp_path):
    from circuit_workbench.studio import Studio,StudioStore
    db=catalog(tmp_path);before=db.row('analoggenie:1004');store=StudioStore(tmp_path/'studio')
    result=Studio(db,store).run({'mode':'library','source_id':'analoggenie:1004'},threading.Event(),lambda s:None)
    assert result['source']['circuit_id']=='analoggenie:1004'
    assert result['checks']['pin_net_coverage']
    assert db.row('analoggenie:1004')==before
    assert store.get(result['id'])['netlist']==before['netlist']


def test_prompt_generation_needs_no_supplied_netlist_and_does_not_auto_ingest(tmp_path):
    from circuit_workbench.studio import Studio,StudioStore,CircuitProposal
    db=catalog(tmp_path);before=db.list()['total']
    proposal=CircuitProposal(name='NMOS mirror',description='Proposed two-device mirror',netlist='M1 (IIN IIN VSS VSS) nmos4\nM2 (OUT IIN VSS VSS) nmos4',ports='IIN OUT VSS',assumptions=['Requires external reference current and output loading'],unverified=['Not simulated'],layout=None)
    studio=Studio(db,StudioStore(tmp_path/'studio'),generate=lambda *a:proposal)
    result=studio.run({'mode':'prompt','prompt':'Draw an NMOS current mirror with exactly 2 transistors','provider':'codex'},threading.Event(),lambda s:None)
    assert result['source']['kind']=='proposed'
    assert result['record']['statistics']['device_count']==2
    assert result['netlist'].startswith('M1')
    assert db.list()['total']==before


def test_prompt_count_mismatch_is_not_saved_as_successful_generation(tmp_path):
    from circuit_workbench.studio import Studio,StudioStore,CircuitProposal
    db=catalog(tmp_path);store=StudioStore(tmp_path/'studio')
    proposal=CircuitProposal(name='wrong',description='Wrong count',netlist='M1 (a a 0 0) nmos4',ports='a 0',assumptions=[],unverified=[],layout=None)
    with pytest.raises(ValueError,match='count'):
        Studio(db,store,generate=lambda *a:proposal).run({'mode':'prompt','prompt':'mirror with exactly 2 transistors'},threading.Event(),lambda s:None)
    assert store.list()==[]


def test_layout_model_cannot_change_existing_circuit_wiring(tmp_path):
    from circuit_workbench.studio import Studio,StudioStore
    from circuit_workbench.schematic import auto_layout
    db=catalog(tmp_path);r=db.record('analoggenie:1004');layout=auto_layout(r)
    result=Studio(db,StudioStore(tmp_path/'studio'),generate=lambda *a:layout).run({'mode':'library','source_id':'analoggenie:1004','polish':True},threading.Event(),lambda s:None)
    assert result['record']==r.model_dump(mode='json')
    assert result['netlist']==db.row(r.circuit_id)['netlist']


def test_upload_diodes_use_canonical_drawable_terminal_names():
    from circuit_workbench.uploads import parse_upload
    r=parse_upload('D1 (a b) diode','diode','a b')
    assert [c.terminal for c in r.devices[0].connections]==['p','n']


def test_automatic_library_render_is_not_blocked_by_a_model_job(tmp_path):
    from fastapi.testclient import TestClient
    from circuit_workbench.app import create_app
    from circuit_workbench.settings import Settings
    from tests.unit.test_workbench import ROOT
    catalog(tmp_path)
    app=create_app(Settings(ROOT,tmp_path/'state',tmp_path/'corpus',ROOT/'AnalogGenie'),background=False)
    entered=threading.Event();release=threading.Event()
    def occupied(request,cancel,progress):
        entered.set();release.wait(3);return {'items':[]}
    app.state.studio_jobs.execute=occupied
    with TestClient(app) as client:
        try:
            client.post('/api/studio/jobs',json={'mode':'prompt','prompt':'test'})
            assert entered.wait(1)
            response=client.post('/api/studio/render',json={'mode':'library','source_id':'analoggenie:1004'})
            assert response.status_code==200
            assert response.json()['checks']['represented_terminals']==60
            assert client.post('/api/studio/render',json={'mode':'prompt','prompt':'test'}).status_code==422
        finally:release.set()
