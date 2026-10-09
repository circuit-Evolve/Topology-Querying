import xml.etree.ElementTree as ET
import pytest
from tests.unit.test_workbench import catalog


def test_renderer_covers_every_typed_terminal_without_changing_source(tmp_path):
    from circuit_workbench.schematic import auto_layout, render_schematic
    db=catalog(tmp_path);record=db.record('analoggenie:1004');original=record.model_dump_json()
    result=render_schematic(record,auto_layout(record),'Circuit 1004')
    assert len(result['pins'])==record.statistics.connection_count
    assert {p['terminal'] for p in result['pins']} >= {'gate','drain','source','bulk','p','n'}
    assert result['checks']['pin_net_coverage'] is True
    assert record.model_dump_json()==original
    ET.fromstring(result['svg'])


def test_placement_cannot_drop_duplicate_named_devices_or_overlap(tmp_path):
    from circuit_workbench.schematic import auto_layout, render_schematic, LayoutPlan
    db=catalog(tmp_path);r=db.record('analoggenie:1004');layout=auto_layout(r)
    broken=layout.model_dump();broken['placements'].pop()
    with pytest.raises(ValueError,match='every device'):
        render_schematic(r,LayoutPlan.model_validate(broken),'bad')
    broken=layout.model_dump();broken['placements'][1]['column']=broken['placements'][0]['column'];broken['placements'][1]['row']=broken['placements'][0]['row']
    with pytest.raises(ValueError,match='overlap'):
        render_schematic(r,LayoutPlan.model_validate(broken),'bad')


def test_names_are_escaped_not_executable_svg():
    from circuit_workbench.uploads import parse_upload
    from circuit_workbench.schematic import auto_layout, render_schematic
    r=parse_upload('R1 (a b) resistor','test','a b')
    result=render_schematic(r,auto_layout(r),'<script>alert(1)</script>')
    root=ET.fromstring(result['svg'])
    assert not any(node.tag.endswith('script') for node in root.iter())
    assert '&lt;script&gt;' in result['svg']


def test_bjt_substrate_and_opaque_macro_pins_are_explicit(tmp_path):
    from circuit_workbench.uploads import parse_upload
    from circuit_workbench.schematic import auto_layout, render_schematic
    r=parse_upload('Q1 (c b e 0) npn','BJT','c b e 0')
    result=render_schematic(r,auto_layout(r),'BJT')
    assert {p['terminal'] for p in result['pins']} == {'collector','base','emitter','substrate'}
    db=catalog(tmp_path);r=db.record('analoggenie:1004').model_copy(deep=True)
    d=r.devices[0];d.canonical_type='inverter'
    result=render_schematic(r,auto_layout(r),'Opaque macro')
    assert any('opaque' in w.lower() for w in result['warnings'])


def test_wire_checker_rejects_cross_net_contact_instead_of_constant_success():
    from circuit_workbench.schematic import verify_wire_paths
    paths=[{'net_id':'a','points':[[0,0],[10,0],[20,0]]},
           {'net_id':'b','points':[[10,-10],[10,0],[10,10]]}]
    with pytest.raises(ValueError,match='Different nets'):
        verify_wire_paths([],paths)


def test_auto_layout_packs_small_groups_without_an_extra_row_per_group():
    from circuit_workbench.uploads import parse_upload
    from circuit_workbench.schematic import auto_layout
    r=parse_upload('P1 (a a VDD VDD) pmos4\nP2 (b a VDD VDD) pmos4\nN1 (a in VSS VSS) nmos4\nN2 (b in VSS VSS) nmos4\nR1 (a b) resistor','layout')
    layout=auto_layout(r)
    assert max(p.row for p in layout.placements)==1


def test_external_signal_label_does_not_sit_on_its_continuing_vertical_wire():
    from circuit_workbench.uploads import parse_upload
    from circuit_workbench.schematic import auto_layout,render_schematic
    r=parse_upload('M1 (OUT IN VSS VSS) nmos4\nR1 (VDD OUT) resistor r=10k','amplifier','IN OUT VDD VSS')
    result=render_schematic(r,auto_layout(r),'amplifier')
    assert 'OUT' not in result['labelled_nets']
    pin=next(p for p in result['pins'] if p['net_name']=='OUT')
    root=ET.fromstring(result['svg']);label=next(n for n in root.iter() if n.tag.endswith('text') and ''.join(child.tail or '' for child in n)=='OUT')
    assert float(label.attrib['x']) != pin['stub'][0]
