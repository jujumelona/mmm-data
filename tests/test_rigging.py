import copy
import hashlib
import json
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from native.inp08 import MAGIC, encode, parse, apply_keyform
from rigging.contracts import (
    ContractError, make_anchor, validate_manifest, mesh_fingerprint,
    image_to_local, local_to_image, lineage,
)
from rigging.deform import tps_offsets, RigProposalError, propose_keyform
from rigging.creator_bridge import call_creator, set_node_transform_verified, CreatorBridgeError, creator_probe, creator_manual_edit_context


def specimen():
    points=[[0,0],[10,0],[0,10],[10,10],[5,5]]
    mesh={'verts':points,'uvs':[[0,0],[1,0],[0,1],[1,1],[0.5,0.5]],
          'indices':[0,1,4,1,3,4,3,2,4,2,0,4]}
    node={'guid':'face-001','name':'face','type':'Part', 'transform':{'trans':[3,4,0],'rot':[0,0,0],'scale':[1,1]},
          'zsort':10,'lockToRoot':False,'mesh':mesh,'children':[]}
    doc={'meta':{'name':'Synthetic only','version':'v0.8.6'},
         'nodes':{'guid':'root','name':'Root','type':'Node','transform':{'trans':[0,0,0],'rot':[0,0,0],'scale':[1,1]},
                  'children':[node]},
         'param':[{'name':'Head:: Angle','guid':'param-01', 'axis_points':[[-30,0,30],[-30,0,30]],
                   'bindings':[{'node':'face-001','param_name':'deform',
                                'values':[[[[0,0] for _ in points] for _ in range(3)] for _ in range(3)],
                                'isSet':[[False,False,False],[False,True,False],[False,False,False]]}]}],
         'animations':{}}
    raw=encode(doc,b'TEX_SECT'+struct.pack('>I',0))
    coordinates={'from':'image_pixel_top_left_y_down','to':'mesh_local',
                 'image_origin_px':[100,100], 'local_origin':[0,0],
                 'model_units_per_pixel':1.0,'axes':'x_right_y_up'}
    pixels={'a':[100,100],'b':[110,100],'c':[100,90],'d':[110,90]}
    anchors=[make_anchor(doc,raw,'face-001',label,'landmark',pixel,coordinates)
             for label,pixel in pixels.items()]
    manifest={'format':'inochi-ai-rigging.anchors.v1',
              'source_sha256':hashlib.sha256(raw).hexdigest(),'anchors':anchors}
    return doc,raw,manifest

class TestContracts(unittest.TestCase):
    def test_explicit_coordinate_reversible(self):
        _,_,manifest=specimen()
        c=manifest['anchors'][0]['coordinates']
        self.assertEqual(image_to_local([110,90],c),[10.,10.])
        self.assertEqual(local_to_image([10,10],c),[110.,90.])

    def test_refuse_silent_image_y_flip(self):
        _,_,manifest=specimen()
        c=dict(manifest['anchors'][0]['coordinates']);c.pop('axes')
        with self.assertRaises(ContractError):image_to_local([10,10],c)

    def test_preserve_exact_identity_and_parent(self):
        doc,raw,m=specimen()
        x=validate_manifest(doc,raw,m)
        self.assertEqual(x['count'],4)
        self.assertEqual(x['anchors'][0]['parent_guid'],'root')
        self.assertEqual(lineage(doc,'face-001')[-1]['guid'],'face-001')

    def test_refuse_stale_source_and_stale_pivot(self):
        doc,raw,m=specimen();z=copy.deepcopy(m);z['source_sha256']='0'*64
        with self.assertRaisesRegex(ContractError,'SHA-256'):validate_manifest(doc,raw,z)
        z=copy.deepcopy(m);z['anchors'][0]['point_local']=[10,10]
        with self.assertRaisesRegex(ContractError,'pivot/landmark'):validate_manifest(doc,raw,z)

    def test_refuse_parent_shift_and_mesh_retopology(self):
        doc,raw,m=specimen();d=copy.deepcopy(doc)
        d['nodes']['children'][0]['transform']['trans'][0]+=1
        with self.assertRaisesRegex(ContractError,'stale mesh, parent'):validate_manifest(d,raw,m)
        d=copy.deepcopy(doc);d['nodes']['children'][0]['mesh']['indices'].reverse()
        with self.assertRaisesRegex(ContractError,'stale mesh, parent'):validate_manifest(d,raw,m)

    def test_duplicate_anchor_label_is_not_accepted(self):
        doc,raw,m=specimen();m['anchors'].append(copy.deepcopy(m['anchors'][0]))
        with self.assertRaisesRegex(ContractError,'duplicate'):validate_manifest(doc,raw,m)

    def test_bad_missing_coordinates(self):
        doc,raw,m=specimen();del m['anchors'][0]['coordinates']['model_units_per_pixel']
        with self.assertRaises(ContractError):validate_manifest(doc,raw,m)

class TestTPS(unittest.TestCase):
    def test_nonrigid_tps_exact_landmarks(self):
        src=[[0.,0.],[10.,0.],[0.,10.],[10.,10.]]
        dst=[[0.,0.],[10.,0.],[0.,10.],[10.,11.]]
        off=tps_offsets(src+[[5.,5.]],src,dst)
        for i in range(4):
            self.assertAlmostEqual(src[i][0]+off[i][0],dst[i][0],places=6)
            self.assertAlmostEqual(src[i][1]+off[i][1],dst[i][1],places=6)
        # Not simply translating all vertices identically.
        self.assertNotEqual(off[0],off[3])
        self.assertGreater(off[4][1],0)

    def test_collinear_rejected(self):
        with self.assertRaisesRegex(RigProposalError,'collinear'):
            tps_offsets([[0,0]],[[0,0],[1,0],[2,0]],[[0,0],[1,1],[2,2]])

    def test_generate_real_binding_keyform_safely(self):
        doc,raw,m=specimen()
        target={'a':[0,0],'b':[10,0],'c':[0,10],'d':[10,11]}
        plan=propose_keyform(doc,raw,m,{'node_guid':'face-001','parameter':'Head:: Angle',
                                       'key_index':[2,2],'targets_local':target})
        self.assertEqual(plan['status'],'CANDIDATE_ONLY')
        self.assertEqual(len(plan['patches'][0]['vertex_offsets']),5)
        clone=copy.deepcopy(doc)
        apply_keyform(clone,plan['patches'][0])
        self.assertTrue(clone['param'][0]['bindings'][0]['isSet'][2][2])
        self.assertEqual(parse(encode(clone,parse(raw)[2]))[2],parse(raw)[2])
        self.assertFalse(doc['param'][0]['bindings'][0]['isSet'][2][2])

    def test_refuse_overwrite_authored_center(self):
        doc,raw,m=specimen()
        with self.assertRaisesRegex(RigProposalError,'keyform safety gate failed'):
            propose_keyform(doc,raw,m,{'node_guid':'face-001','parameter':'Head:: Angle',
                                       'key_index':[1,1],
                                       'targets_local':{'a':[0,0],'b':[10,0],'c':[0,10],'d':[10,10]}})

    def test_refuse_missing_target_and_triangle_inversion(self):
        doc,raw,m=specimen()
        with self.assertRaises(RigProposalError):
            propose_keyform(doc,raw,m,{'node_guid':'face-001','parameter':'Head:: Angle',
                                       'key_index':[0,0],'targets_local':{'a':[0,0]}})
        with self.assertRaisesRegex(RigProposalError,'geometry/keyform'):
            propose_keyform(doc,raw,m,{'node_guid':'face-001','parameter':'Head:: Angle',
                                       'key_index':[0,0],
                                       'targets_local':{'a':[0,0],'b':[0,10],'c':[10,0],'d':[10,10]}})

class TestCreatorGuard(unittest.TestCase):
    def test_mutations_disabled_by_default(self):
        with patch.dict(os.environ,{'INOCHI_CREATOR_MUTATIONS':'0'}):
            with self.assertRaisesRegex(CreatorBridgeError,'explicitly'):
                call_creator('set_parameter',{'uuid':'id','x':0})

    def test_unlisted_methods_denied(self):
        with self.assertRaisesRegex(CreatorBridgeError,'allowlisted'):
            call_creator('delete_node',{})

    def test_pivot_translation_requires_explicit_compensation(self):
        with patch('rigging.creator_bridge.call_creator',return_value={
            'uuid':'123','translation':[0,0,0],'rotation':[0,0,0],
            'scale':[1,1],'parent_uuid':'root'}):
            with self.assertRaisesRegex(CreatorBridgeError,'pivot/children'):
                set_node_transform_verified('123',translation=[1,0,0],expected={
                    'translation':[0,0,0],'rotation':[0,0,0],
                    'scale':[1,1],'parent_uuid':'root'})

    def test_pivot_guard_cannot_be_disabled_by_expected_flag(self):
        with patch('rigging.creator_bridge.call_creator',return_value={
            'uuid':'123','translation':[0,0,0],'rotation':[0,0,0],
            'scale':[1,1],'parent_uuid':'root'}):
            with self.assertRaisesRegex(CreatorBridgeError,'pivot/children'):
                set_node_transform_verified('123',translation=[1,0,0],expected={
                    'translation':[0,0,0],'rotation':[0,0,0],
                    'scale':[1,1],'parent_uuid':'root',
                    'pivot_compensation_required':False})

    def test_creator_probe_is_real_handshake(self):
        with patch('rigging.creator_bridge.call_creator',side_effect=CreatorBridgeError('offline')):
            self.assertFalse(creator_probe()['creator_connected'])
        with patch('rigging.creator_bridge.call_creator',side_effect=lambda method,*a,**kw: {'ok':method}):
            self.assertTrue(creator_probe()['creator_connected'])

    def test_manual_snapshot_preserves_parent_chain_and_missing_fields(self):
        node={'uuid':2,'translation':[3,4,0],'rotation':[0,0,0],
              'scale':[1,1],'parent_uuid':1,'enabled':True,'zsort':4}
        parent={'uuid':1,'translation':[0,0,0],'rotation':[0,0,0],
                'scale':[1,1],'children':[{'uuid':2,'translation':[3,4,0],
                'rotation':[0,0,0],'scale':[1,1],'zsort':4,'enabled':True}]}
        def mock(method,params=None):
            return {'get_node':node,'list_nodes':{'root':parent},
                    'list_parameters':{'parameters':[]}}[method]
        with patch('rigging.creator_bridge.call_creator',side_effect=mock):
            context=creator_manual_edit_context('2')
            self.assertEqual([a['uuid'] for a in context['ancestor_chain']],[1,2])
            self.assertIn('actual_pivot',context['authoring_context_missing'])
            self.assertFalse(context['safe_for_automatic_pivot_relocation'])

    def test_stale_live_creator_snapshot(self):
        with patch('rigging.creator_bridge.call_creator',return_value={
            'uuid':'123','translation':[0,0,0],'rotation':[0,0,0],
            'scale':[1,1],'parent_uuid':'root'}):
            with self.assertRaisesRegex(CreatorBridgeError,'changed'):
                set_node_transform_verified('123',rotation=[0,0,1],expected={
                    'translation':[0,0,0],'rotation':[0,0,2],
                    'scale':[1,1],'parent_uuid':'root'})

if __name__=='__main__':unittest.main()

from rigging.spaces import (mesh_local_to_world,world_to_mesh_local,pivot_handoff,
                            reparent_plan_2d,world_matrix)

class TestCoordinateFrames(unittest.TestCase):
    def test_world_local_round_trip_with_parent_rotation(self):
        doc,raw,manifest=specimen()
        doc['nodes']['transform']['trans']=[11,2,0]
        doc['nodes']['transform']['rot']=[0,0,0.2]
        doc['nodes']['children'][0]['transform']['rot']=[0,0,0.8]
        q=[2.5,-3.7]
        world=mesh_local_to_world(doc,'face-001',q)
        recovered=world_to_mesh_local(doc,'face-001',world)
        for x,y in zip(q,recovered):self.assertAlmostEqual(x,y,places=7)

    def test_control_point_not_confused_with_pivot(self):
        doc,raw,m=specimen()
        validated=validate_manifest(doc,raw,m)
        handoff=pivot_handoff(doc,validated['anchors'][1])
        self.assertEqual(handoff['current_node_pivot_world'],[3.,4.])
        self.assertEqual(handoff['landmark_world'],[13.,4.])
        self.assertFalse(handoff['pivot_is_at_landmark'])
        self.assertEqual(handoff['apply_policy'],'PLAN_ONLY_REQUIRES_CREATOR_COMPENSATION')

    def test_refuse_root_lock_3d_and_unsupported_serialization(self):
        doc,raw,m=specimen()
        doc['nodes']['children'][0]['lockToRoot']=True
        with self.assertRaisesRegex(ContractError,'lockToRoot'):
            mesh_local_to_world(doc,'face-001',[0,0])
        doc['nodes']['children'][0]['lockToRoot']=False
        doc['nodes']['children'][0]['transform']['rot']=[.5,0,0]
        with self.assertRaisesRegex(ContractError,'3D'):
            mesh_local_to_world(doc,'face-001',[0,0])
        doc['nodes']['children'][0]['transform']=1.2
        with self.assertRaisesRegex(ContractError,'missing/unsupported'):
            mesh_local_to_world(doc,'face-001',[0,0])

    def test_world_preserving_reparent_plan_and_cycle(self):
        doc,raw,m=specimen()
        doc['nodes']['children'].append({'guid':'other','name':'Other', 'type':'Node',
            'transform':{'trans':[1,2,0],'rot':[0,0,0.25],'scale':[1,1]},'children':[]})
        proposal=reparent_plan_2d(doc,'face-001','other')
        self.assertTrue(proposal['preserve_world_in_plan'])
        self.assertFalse(proposal['applied_to_model'])
        with self.assertRaisesRegex(ContractError,'cycle'):
            reparent_plan_2d(doc,'root','face-001')

    def test_shear_reparent_refused(self):
        doc,raw,m=specimen()
        doc['nodes']['children'][0]['transform']['scale']=[2,1]
        doc['nodes']['children'].append({'guid':'other','name':'Other', 'type':'Node',
            'transform':{'trans':[0,0,0],'rot':[0,0,.7],'scale':[1.2,.8]},'children':[]})
        with self.assertRaisesRegex(ContractError,'sheared'):
            reparent_plan_2d(doc,'face-001','other')
