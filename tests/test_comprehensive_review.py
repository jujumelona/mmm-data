"""Adversarial regressions: prevent edits to another Creator project and broken bindings."""
from __future__ import annotations
import base64,copy,hashlib,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from native.inp08 import encode,parse
from rigging.quality import inspect_geometry,QualityError
from rigging.live_qa import capture_pose_sweep,LiveQAError
from rigging.transactions import execute_transaction,FORMAT
from rigging.contracts import mesh_fingerprint
from test_rigging import specimen

PNG=b'\x89PNG\r\n\x1a\n'+struct.pack('>I',13)+b'IHDR'+struct.pack('>II',1,1)+b'\x08\x06\x00\x00\x00'

class IntegrationReview(unittest.TestCase):
    def test_project_switch_during_capture_does_not_edit_other_project(self):
        state={'project':'/first.inx','value':0,'mutations':[]}
        def rpc(method,params=None):
            if method=='get_status':return {'project_path':state['project'],'armed_parameter':None}
            if method=='list_parameters':
                return {'parameters':[{'uuid':1,'name':'Head','is_group':False,'is_vec2':False,
                        'value':[state['value'],0],'min':[-30,0],'max':[30,0]}]}
            if method=='set_parameter':
                state['mutations'].append((state['project'],params['x']))
                state['value']=params['x'];return {'ok':True}
            if method=='capture_viewport':
                state['project']='/second.inx'
                return {'png_base64':base64.b64encode(PNG).decode(),'width':1,'height':1}
            raise AssertionError(method)
        with patch('rigging.live_qa.call_creator',side_effect=rpc):
            with self.assertRaisesRegex(LiveQAError,'project changed'):
                capture_pose_sweep('1',[[20,0]])
        self.assertEqual(state['mutations'],[('/first.inx',20)])

    def test_non_deform_binding_missing_node_is_rejected_before_publish(self):
        doc,raw,_=specimen()
        scalar=copy.deepcopy(doc['param'][0]['bindings'][0])
        scalar.update({'node':'nonexistent','param_name':'opacity',
                       'values':[[1.0 for _ in range(3)] for _ in range(3)]})
        doc['param'][0]['bindings'].append(scalar)
        with self.assertRaisesRegex(QualityError,'nonexistent node'):
            inspect_geometry(doc)
        raw=encode(doc,parse(raw)[2])
        batch={'format':FORMAT,'request_id':'invalid-scalar','source_sha256':hashlib.sha256(raw).hexdigest(),
               'edits':[{'op':'subdivide_mesh','node_guid':'face-001',
                         'expected_mesh_sha256':mesh_fingerprint(doc['nodes']['children'][0]['mesh'])}]}
        with tempfile.TemporaryDirectory() as tmp:
            original=Path(tmp)/'original.inx';original.write_bytes(raw)
            output=Path(tmp)/'candidate.inx'
            with self.assertRaisesRegex(QualityError,'nonexistent node'):
                execute_transaction(original,batch,destination=output,commit=True)
            self.assertFalse(output.exists());self.assertEqual(original.read_bytes(),raw)

    def test_malformed_scalar_binding_grids_rejected(self):
        doc,_,_=specimen()
        doc['param'][0]['bindings'].append({'node':'face-001','param_name':'opacity','values':[],'isSet':[]})
        with self.assertRaisesRegex(QualityError,'grid|axis|binding'):
            inspect_geometry(doc)

    def test_out_of_range_existing_scalar_binding_rejected(self):
        doc,_,_=specimen()
        doc['param'][0]['bindings'].append({'node':'face-001','param_name':'opacity',
                 'values':[[2.0 for _ in range(3)] for _ in range(3)],
                 'isSet':[[True for _ in range(3)] for _ in range(3)]})
        with self.assertRaisesRegex(QualityError,'opacity'):
            inspect_geometry(doc)
